const path = require('path');
const fs = require('fs');
const { spawn, spawnSync } = require('child_process');
const {
  ENGINE_MANIFEST_FILE,
  ENGINE_SEAL_FILE,
  getProjectRoot,
  getExpectedEngineVersion,
  resolveBundledEngineArchive,
} = require('./paths');
const {
  detectArchiveFormat,
  readSidecarManifest,
  computeArchiveFingerprint,
  estimateRequiredBytes,
  checkDiskSpace,
  formatBytes,
  extractEngineArchive,
} = require('./engineArchive');

const CRITICAL_VC_DLLS = ['msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'vcomp140.dll'];
const HEALTH_CHECK_SCRIPT = 'import fastapi, uvicorn, websockets, psutil, PIL, requests';

let activeBootstrapProc = null;
let activeAbortController = null;

function execPromise(cmd, args = [], cwd) {
  return new Promise((resolve, reject) => {
    const cp = spawn(cmd, args, { shell: false, cwd, windowsHide: true });
    activeBootstrapProc = cp;
    let errOutput = '';
    if (cp.stderr) {
      cp.stderr.on('data', (d) => { errOutput += d.toString(); });
    }
    cp.on('close', (code) => {
      if (activeBootstrapProc === cp) activeBootstrapProc = null;
      if (code === 0) resolve();
      else reject(new Error(`Comando falhou (${code}): ${errOutput.trim()}`));
    });
    cp.on('error', (err) => {
      if (activeBootstrapProc === cp) activeBootstrapProc = null;
      reject(err);
    });
  });
}

function killActiveBootstrapProc() {
  if (activeAbortController) {
    try { activeAbortController.abort(); } catch (_) {}
    activeAbortController = null;
  }
  if (activeBootstrapProc && activeBootstrapProc.pid) {
    try {
      if (process.platform === 'win32') {
        spawnSync('taskkill', ['/pid', String(activeBootstrapProc.pid), '/f', '/t'], { windowsHide: true });
      } else {
        activeBootstrapProc.kill('SIGKILL');
      }
    } catch (_) {}
    activeBootstrapProc = null;
  }
}

function sleepSync(ms) {
  try {
    const sab = new SharedArrayBuffer(4);
    const int32 = new Int32Array(sab);
    Atomics.wait(int32, 0, 0, ms);
  } catch (_) {
    const end = Date.now() + ms;
    while (Date.now() < end) {}
  }
}

function renameWithRetry(src, dst, maxRetries = 6, delayMs = 250) {
  let lastErr = null;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      fs.renameSync(src, dst);
      return;
    } catch (err) {
      lastErr = err;
      const retryable = err && ['EPERM', 'EBUSY', 'EACCES'].includes(err.code);
      if (!retryable || attempt === maxRetries) break;
      sleepSync(delayMs);
    }
  }
  throw lastErr;
}

function rmWithRetry(targetDir, maxRetries = 4, delayMs = 200) {
  if (!targetDir || !fs.existsSync(targetDir)) return;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      fs.rmSync(targetDir, { recursive: true, force: true });
      return;
    } catch (err) {
      if (attempt === maxRetries) return;
      sleepSync(delayMs);
    }
  }
}

function readEngineManifest(engineDir) {
  try {
    const manifestPath = path.join(engineDir, ENGINE_MANIFEST_FILE);
    if (!fs.existsSync(manifestPath)) return null;
    const raw = fs.readFileSync(manifestPath, 'utf-8');
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch (_) {
    return null;
  }
}

function writeEngineManifest(engineDir, manifest) {
  fs.mkdirSync(engineDir, { recursive: true });
  const payload = {
    schemaVersion: 1,
    installedAt: new Date().toISOString(),
    ...manifest,
  };
  const manifestPath = path.join(engineDir, ENGINE_MANIFEST_FILE);
  const sealPath = path.join(engineDir, ENGINE_SEAL_FILE);
  fs.writeFileSync(manifestPath, JSON.stringify(payload, null, 2), 'utf-8');
  fs.writeFileSync(sealPath, payload.installedAt, 'utf-8');
  return payload;
}

function isEngineManifestCompatible(manifest, { expectedEngineVersion, sidecarManifest } = {}) {
  if (!manifest || typeof manifest !== 'object') {
    return { compatible: false, reason: 'missing_manifest' };
  }
  if (manifest.schemaVersion !== 1) {
    return { compatible: false, reason: 'unsupported_schema' };
  }
  if (expectedEngineVersion && manifest.engineVersion && manifest.engineVersion !== expectedEngineVersion) {
    return {
      compatible: false,
      reason: 'version_mismatch',
      currentVersion: manifest.engineVersion,
      expectedVersion: expectedEngineVersion,
    };
  }
  if (
    sidecarManifest &&
    sidecarManifest.engineVersion &&
    manifest.engineVersion &&
    sidecarManifest.engineVersion !== manifest.engineVersion
  ) {
    return {
      compatible: false,
      reason: 'archive_version_mismatch',
      currentVersion: manifest.engineVersion,
      expectedVersion: sidecarManifest.engineVersion,
    };
  }
  return { compatible: true };
}

/**
 * Encerra apenas processos executando dentro de targetDir (ex: userData/engine) para liberar locks de DLLs.
 */
function terminateOrphanedEngineProcesses(targetDir, logBootEvent) {
  if (process.platform !== 'win32' || !targetDir || !fs.existsSync(targetDir)) {
    return { executed: false };
  }
  try {
    const resolvedDir = path.resolve(targetDir);
    const psScript = [
      "$d = [IO.Path]::GetFullPath($env:VISIONARY_ENGINE_DIR).TrimEnd('\\') + '\\';",
      'Get-CimInstance Win32_Process | Where-Object {',
      '  $_.ExecutablePath -and $_.ExecutablePath.StartsWith($d, [System.StringComparison]::OrdinalIgnoreCase)',
      '} | ForEach-Object {',
      '  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue',
      '}',
    ].join(' ');

    const res = spawnSync(
      'powershell.exe',
      ['-NoProfile', '-NonInteractive', '-Command', psScript],
      {
        env: { ...process.env, VISIONARY_ENGINE_DIR: resolvedDir },
        windowsHide: true,
        stdio: 'ignore',
        timeout: 6000,
      }
    );
    logBootEvent?.(`[Pre-Flight] Limpeza de processos sob ${resolvedDir} concluída (status: ${res.status}).`);
    return { executed: true, status: res.status };
  } catch (err) {
    logBootEvent?.(`[Pre-Flight] Aviso ao limpar processos sob ${targetDir}: ${err.message}`, true);
    return { executed: false, error: err.message };
  }
}

/**
 * Ativa 'import site' nos arquivos python*._pth do Python Embeddable.
 */
function patchEmbeddablePthFiles(engineDir) {
  let patchedCount = 0;
  if (!engineDir || !fs.existsSync(engineDir)) return patchedCount;

  const pthFiles = fs.readdirSync(engineDir).filter((f) => f.endsWith('._pth'));
  for (const pthFile of pthFiles) {
    const fullPth = path.join(engineDir, pthFile);
    const original = fs.readFileSync(fullPth, 'utf-8');
    let updated = original.replace(/^\s*#\s*import\s+site\b/gm, 'import site');
    if (!/^\s*import\s+site\b/m.test(updated)) {
      updated = `${updated.replace(/\s*$/, '')}\nimport site\n`;
    }
    if (updated !== original) {
      fs.writeFileSync(fullPth, updated, 'utf-8');
      patchedCount++;
    }
  }
  return patchedCount;
}

/**
 * Injeta DLLs App-Local do Visual C++ na engine e valida presença das bibliotecas críticas.
 */
function validateAndInjectVcRuntimeDlls(app, engineDir, logBootEvent) {
  let injectedCount = 0;
  const projectRoot = getProjectRoot(app);
  const vcDirCandidates = [
    path.join(projectRoot, 'assets', 'windows', 'vc_dlls'),
    process.resourcesPath ? path.join(process.resourcesPath, 'app.asar.unpacked', 'assets', 'windows', 'vc_dlls') : null,
    process.resourcesPath ? path.join(process.resourcesPath, 'assets', 'windows', 'vc_dlls') : null,
    path.resolve(__dirname, '..', 'assets', 'windows', 'vc_dlls'),
  ].filter(Boolean);

  const vcDllDir = vcDirCandidates.find((dir) => fs.existsSync(dir));
  if (vcDllDir) {
    const dllFiles = fs.readdirSync(vcDllDir).filter((f) => f.toLowerCase().endsWith('.dll'));
    const targetDirs = [
      engineDir,
      path.join(engineDir, 'ollama'),
      path.join(engineDir, 'Lib', 'site-packages', 'torch', 'lib'),
    ];
    for (const tDir of targetDirs) {
      if (!fs.existsSync(tDir)) continue;
      for (const dll of dllFiles) {
        const src = path.join(vcDllDir, dll);
        const dst = path.join(tDir, dll);
        let shouldCopy = !fs.existsSync(dst);
        if (!shouldCopy) {
          try {
            shouldCopy = fs.statSync(dst).size === 0;
          } catch (_) {
            shouldCopy = true;
          }
        }
        if (shouldCopy) {
          try {
            fs.copyFileSync(src, dst);
            injectedCount++;
          } catch (_) {}
        }
      }
    }
  }

  const sysRoot = process.env.SystemRoot || 'C:\\Windows';
  const sys32Dir = path.join(sysRoot, 'System32');
  const missingCritical = [];
  const presentInEngine = [];

  for (const dll of CRITICAL_VC_DLLS) {
    const inEngine = fs.existsSync(path.join(engineDir, dll));
    const inSystem = process.platform === 'win32' && fs.existsSync(path.join(sys32Dir, dll));
    if (inEngine) presentInEngine.push(dll);
    if (!inEngine && !inSystem) {
      missingCritical.push(dll);
    }
  }

  logBootEvent?.(
    `[VC++ App-Local] Injetadas: ${injectedCount} | Em engine/: ${presentInEngine.length} | Faltantes críticas: ${missingCritical.length}`
  );

  return {
    ok: missingCritical.length === 0,
    injectedCount,
    missingCritical,
    presentInEngine,
  };
}

function verifyPythonHealthDetailed(exePath, argsPrefix = [], { logBootEvent, timeoutMs = 8000 } = {}) {
  return new Promise((resolve) => {
    let finished = false;
    let stderrBuf = '';
    const checkProc = spawn(exePath, [...argsPrefix, '-c', HEALTH_CHECK_SCRIPT], {
      windowsHide: true,
      stdio: ['ignore', 'ignore', 'pipe'],
    });

    if (checkProc.stderr) {
      checkProc.stderr.on('data', (chunk) => {
        if (stderrBuf.length < 4096) {
          stderrBuf += chunk.toString('utf8');
        }
      });
    }

    const timer = setTimeout(() => {
      if (!finished) {
        finished = true;
        try {
          if (process.platform === 'win32' && checkProc.pid) {
            spawnSync('taskkill', ['/pid', String(checkProc.pid), '/f', '/t'], { windowsHide: true });
          } else {
            checkProc.kill('SIGKILL');
          }
        } catch (_) {}
        logBootEvent?.(`[Timeout] Verificação de integridade expirou para ${exePath}`, true);
        resolve({ healthy: false, timeout: true, exitCode: null, stderr: stderrBuf.trim(), missingModule: null, isDllError: false });
      }
    }, timeoutMs);

    checkProc.on('close', (code) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      const stderrText = stderrBuf.trim();
      if (code === 0) {
        resolve({ healthy: true, timeout: false, exitCode: 0, stderr: stderrText, missingModule: null, isDllError: false });
        return;
      }
      const modMatch = stderrText.match(/No module named ['"]([^'"]+)['"]/);
      const isDllError = /DLL load failed|vcruntime|msvcp|0xc0000135|não foi possível encontrar o módulo especificado/i.test(stderrText);
      resolve({
        healthy: false,
        timeout: false,
        exitCode: code,
        stderr: stderrText,
        missingModule: modMatch ? modMatch[1] : null,
        isDllError,
      });
    });

    checkProc.on('error', (err) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      resolve({
        healthy: false,
        timeout: false,
        exitCode: null,
        stderr: err.message || String(err),
        missingModule: null,
        isDllError: false,
      });
    });
  });
}

function getCachedPython(app) {
  try {
    const cachePath = path.join(app.getPath('userData'), '.python_cache.json');
    if (!fs.existsSync(cachePath)) return null;
    const raw = fs.readFileSync(cachePath, 'utf-8');
    const data = JSON.parse(raw);
    if (data && data.executable && typeof data.executable === 'string' && fs.existsSync(data.executable)) {
      const currentMtime = fs.statSync(data.executable).mtimeMs;
      if (Math.abs(currentMtime - data.mtime) >= 1000) {
        return null;
      }
      if (data.source === 'userData') {
        const expectedVer = getExpectedEngineVersion(app);
        if (data.engineVersion && data.engineVersion !== expectedVer) {
          return null;
        }
        const engineDir = path.dirname(data.executable);
        const manifest = readEngineManifest(engineDir);
        if (manifest) {
          if (!isEngineManifestCompatible(manifest, { expectedEngineVersion: expectedVer }).compatible) {
            return null;
          }
        } else if (!fs.existsSync(path.join(engineDir, ENGINE_SEAL_FILE)) && resolveBundledEngineArchive(app)) {
          return null;
        }
      }
      return { found: true, executable: data.executable, source: data.source || 'cached' };
    }
  } catch (_) {}
  return null;
}

function setCachedPython(app, pythonInfo) {
  try {
    if (!pythonInfo || !pythonInfo.found || !pythonInfo.executable) return;
    const cachePath = path.join(app.getPath('userData'), '.python_cache.json');
    if (!fs.existsSync(pythonInfo.executable)) return;
    const mtime = fs.statSync(pythonInfo.executable).mtimeMs;
    fs.writeFileSync(
      cachePath,
      JSON.stringify({
        executable: pythonInfo.executable,
        source: pythonInfo.source || 'unknown',
        engineVersion: getExpectedEngineVersion(app),
        mtime,
        savedAt: Date.now(),
      }),
      'utf-8'
    );
  } catch (_) {}
}

function invalidateCachedPython(app, logBootEvent) {
  try {
    const cachePath = path.join(app.getPath('userData'), '.python_cache.json');
    if (fs.existsSync(cachePath)) {
      fs.unlinkSync(cachePath);
      logBootEvent?.('[Lifecycle] Cache de detecção do motor Python invalidado.');
    }
  } catch (_) {}
}

async function detectPython(app, { initBootLogger, logBootEvent } = {}) {
  initBootLogger?.(app);

  // Fast-path: se o executável do Python já foi validado e não sofreu modificação de mtime ou versão
  const cached = getCachedPython(app);
  if (cached) {
    logBootEvent?.(`[Fast-Path] Motor Python verificado em cache: ${cached.executable}`);
    return cached;
  }

  const verifyPythonHealth = async (exePath, argsPrefix = []) => {
    const res = await verifyPythonHealthDetailed(exePath, argsPrefix, { logBootEvent });
    return res.healthy;
  };

  const projectRoot = getProjectRoot(app);

  // 1. Python embutido no instalador de produção (resources/engine/python.exe)
  const bundledEngine = path.join(process.resourcesPath || '', 'engine', 'python.exe');
  if (process.resourcesPath && fs.existsSync(bundledEngine)) {
    if (await verifyPythonHealth(bundledEngine)) {
      const res = { found: true, executable: bundledEngine, source: 'bundled' };
      setCachedPython(app, res);
      return res;
    }
  }

  // 2. Python embutido na raiz do projeto ou modo portátil (engine/python.exe)
  const projectEngine = path.join(projectRoot, 'engine', 'python.exe');
  if (fs.existsSync(projectEngine)) {
    if (await verifyPythonHealth(projectEngine)) {
      const res = { found: true, executable: projectEngine, source: 'project_engine' };
      setCachedPython(app, res);
      return res;
    }
  }

  // 3. Python em assets do projeto (assets/python/engine/python.exe)
  const assetsEngine = path.join(projectRoot, 'assets', 'python', 'engine', 'python.exe');
  if (fs.existsSync(assetsEngine)) {
    if (await verifyPythonHealth(assetsEngine)) {
      const res = { found: true, executable: assetsEngine, source: 'assets_engine' };
      setCachedPython(app, res);
      return res;
    }
  }

  // 4. Python extraído na pasta de dados do usuário (%APPDATA%/Visionary Studio/engine/python.exe)
  const userEngineDir = path.join(app.getPath('userData'), 'engine');
  const userEngine = path.join(userEngineDir, 'python.exe');
  const userEngineSeal = path.join(userEngineDir, ENGINE_SEAL_FILE);
  const archivePath = resolveBundledEngineArchive(app);

  if (fs.existsSync(userEngine)) {
    const expectedEngineVersion = getExpectedEngineVersion(app);
    const sidecarManifest = archivePath ? readSidecarManifest(archivePath) : null;
    const manifest = readEngineManifest(userEngineDir);
    const hasSeal = fs.existsSync(userEngineSeal);

    let engineValid = false;
    let needsUpgradeWithArchive = false;

    if (manifest) {
      const compat = isEngineManifestCompatible(manifest, { expectedEngineVersion, sidecarManifest });
      if (compat.compatible) {
        engineValid = true;
      } else if (archivePath) {
        needsUpgradeWithArchive = true;
        logBootEvent?.(`[Lifecycle] Motor Python desatualizado (${compat.reason}): ${manifest.engineVersion} -> ${expectedEngineVersion}.`);
      } else {
        // Atualização de app sem pacote sidecar: mantém motor se saudável
        engineValid = true;
      }
    } else if (hasSeal) {
      if (sidecarManifest && sidecarManifest.engineVersion && sidecarManifest.engineVersion !== expectedEngineVersion && archivePath) {
        needsUpgradeWithArchive = true;
      } else {
        engineValid = true;
      }
    } else if (!archivePath) {
      engineValid = true;
    }

    if (engineValid && !needsUpgradeWithArchive) {
      const health = await verifyPythonHealthDetailed(userEngine, [], { logBootEvent });
      if (health.healthy) {
        const res = { found: true, executable: userEngine, source: 'userData' };
        setCachedPython(app, res);
        return res;
      }
      logBootEvent?.(`[Lifecycle] Saúde do motor em userData falhou: ${health.stderr}`, true);
    }

    if (!needsUpgradeWithArchive) {
      console.warn('[Electron] O motor Python na AppData está incompleto ou corrompido. Executando auto-heal...');
      terminateOrphanedEngineProcesses(userEngineDir, logBootEvent);
      rmWithRetry(userEngineDir);
    }
  } else if (fs.existsSync(userEngineDir) && archivePath) {
    // Pasta engine/ parcial sem python.exe
    terminateOrphanedEngineProcesses(userEngineDir, logBootEvent);
    rmWithRetry(userEngineDir);
  }

  // Se estiver empacotado (produção) e houver arquivo de motor embutido para extrair no 1º boot,
  // não cai no Python global do sistema para garantir isolamento completo.
  if (app.isPackaged && archivePath) {
    return { found: false };
  }

  // 5. Ambiente Virtual Ativo (VIRTUAL_ENV ou .venv local)
  const venvCandidates = [
    process.env.VIRTUAL_ENV ? path.join(process.env.VIRTUAL_ENV, 'Scripts', 'python.exe') : null,
    path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    path.join(projectRoot, 'venv', 'Scripts', 'python.exe'),
  ].filter(Boolean);

  for (const venvExe of venvCandidates) {
    if (fs.existsSync(venvExe)) {
      if (await verifyPythonHealth(venvExe)) {
        const res = { found: true, executable: venvExe, source: 'virtualenv' };
        setCachedPython(app, res);
        return res;
      }
    }
  }

  // 6. Python do sistema (PATH do Windows)
  return new Promise((resolve) => {
    const proc = spawn('python', ['-c', 'import sys; print(sys.version_info[0])'], {
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'ignore'],
    });

    let out = '';
    proc.stdout.on('data', (d) => { out += d.toString(); });

    const tryPyLauncher = () => {
      const pyProc = spawn('py', ['-3', '-c', 'import sys; print(sys.version_info[0])'], {
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'ignore'],
      });
      let pyOut = '';
      pyProc.stdout.on('data', (d) => { pyOut += d.toString(); });
      pyProc.on('error', () => resolve({ found: false }));
      pyProc.on('close', async (code) => {
        if (code === 0 && pyOut.trim() === '3') {
          if (await verifyPythonHealth('py', ['-3'])) {
            const res = { found: true, executable: 'py', argsPrefix: ['-3'], source: 'py_launcher' };
            setCachedPython(app, res);
            resolve(res);
          } else {
            resolve({ found: false });
          }
        } else {
          resolve({ found: false });
        }
      });
    };

    proc.on('error', () => tryPyLauncher());
    proc.on('close', async (code) => {
      if (code === 0 && out.trim() === '3') {
        if (await verifyPythonHealth('python')) {
          const res = { found: true, executable: 'python', source: 'system' };
          setCachedPython(app, res);
          resolve(res);
        } else {
          tryPyLauncher();
        }
      } else {
        tryPyLauncher();
      }
    });
  });
}

function formatEta(seconds) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds <= 0) return '';
  if (seconds < 60) return `~${Math.ceil(seconds)}s restantes`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.ceil(seconds % 60);
  return `~${mins}m ${secs}s restantes`;
}

function normalizeExtractedStagingRoot(stagingDir) {
  const rootPython = path.join(stagingDir, 'python.exe');
  if (fs.existsSync(rootPython)) return;

  const nestedDir = path.join(stagingDir, 'engine');
  const nestedPython = path.join(nestedDir, 'python.exe');
  if (!fs.existsSync(nestedPython)) return;

  const tempNested = path.join(stagingDir, `__engine_nested_${Date.now()}`);
  renameWithRetry(nestedDir, tempNested);
  for (const entry of fs.readdirSync(tempNested)) {
    const src = path.join(tempNested, entry);
    const dst = path.join(stagingDir, entry);
    if (fs.existsSync(dst)) {
      rmWithRetry(dst);
    }
    renameWithRetry(src, dst);
  }
  rmWithRetry(tempNested);
}

async function autoSetupPython(app, onProgress, options = {}) {
  const userDataDir = app.getPath('userData');
  const engineDir = path.join(userDataDir, 'engine');
  const stagingDir = path.join(userDataDir, 'engine.staging');
  const backupDir = path.join(userDataDir, 'engine.bak');
  const logBootEvent = options.logBootEvent;

  // 1. Localiza e valida o formato do pacote de runtime antes de tocar no disco
  const archivePath = options.archivePath || resolveBundledEngineArchive(app);
  if (!archivePath || !fs.existsSync(archivePath)) {
    const err = new Error(
      'Pacote de runtime do motor Python (engine-runtime.tar.zst ou prebuilt-engine.zip) não encontrado na pasta do instalador ou diretórios de busca.'
    );
    err.code = 'ARCHIVE_NOT_FOUND';
    throw err;
  }

  const format = detectArchiveFormat(archivePath);
  if (!format) {
    const err = new Error(
      `O arquivo "${path.basename(archivePath)}" não é um pacote .tar.zst ou .zip válido (pode estar corrompido ou truncado).`
    );
    err.code = 'INVALID_ARCHIVE';
    throw err;
  }

  const sidecarManifest = readSidecarManifest(archivePath);
  const archiveStat = fs.statSync(archivePath);
  const expectedEngineVersion = sidecarManifest?.engineVersion || getExpectedEngineVersion(app);

  // 2. Pre-Flight Check: encerra processos órfãos, limpa staging quebrado e checa espaço em disco
  onProgress?.({
    percent: 6,
    mode: 'first',
    deterministic: true,
    message: 'Executando verificações de integridade e espaço em disco...',
    detail: `Pacote: ${path.basename(archivePath)} (${formatBytes(archiveStat.size)})`,
  });

  terminateOrphanedEngineProcesses(engineDir, logBootEvent);
  terminateOrphanedEngineProcesses(stagingDir, logBootEvent);
  rmWithRetry(stagingDir);
  rmWithRetry(backupDir);

  // Se houver uma pasta engine/ prévia corrompida (sem selo nem manifesto), remove antes para liberar espaço
  if (
    fs.existsSync(engineDir) &&
    !fs.existsSync(path.join(engineDir, ENGINE_MANIFEST_FILE)) &&
    !fs.existsSync(path.join(engineDir, ENGINE_SEAL_FILE))
  ) {
    rmWithRetry(engineDir);
  }

  const requiredBytes = options.requiredBytes ?? estimateRequiredBytes(archivePath, sidecarManifest);
  const diskCheck = checkDiskSpace(userDataDir, requiredBytes);
  if (!diskCheck.ok) {
    const err = new Error(
      `Espaço insuficiente em disco para instalar o motor de IA. Necessário: ${formatBytes(diskCheck.requiredBytes)} | Disponível em ${diskCheck.checkedPath}: ${formatBytes(diskCheck.freeBytes)}.`
    );
    err.code = 'INSUFFICIENT_DISK_SPACE';
    throw err;
  }

  // 3. Extração em staging atômico com telemetria real contínua (12% -> 86%)
  const isZst = format === 'tar.zst';
  onProgress?.({
    percent: 12,
    mode: 'first',
    deterministic: true,
    message: isZst ? 'Descompactando motor PyTorch CUDA...' : 'Extraindo arquivos do motor Python...',
    detail: `0 B / ${formatBytes(archiveStat.size)}`,
  });

  activeAbortController = new AbortController();

  try {
    await extractEngineArchive(archivePath, stagingDir, {
      signal: activeAbortController.signal,
      forcePureNode: Boolean(options.forcePureNode),
      onSpawnChild: (cp) => { activeBootstrapProc = cp; },
      onProgress: (prog) => {
        const ratio = typeof prog.ratio === 'number' ? Math.max(0, Math.min(1, prog.ratio)) : 0;
        const pct = Math.round(12 + ratio * 74);

        let detail = '';
        if (typeof prog.bytesRead === 'number' && typeof prog.totalBytes === 'number' && prog.totalBytes > 0) {
          const speedMb = prog.speedBytesPerSec > 0 ? `${(prog.speedBytesPerSec / (1024 * 1024)).toFixed(1)} MB/s` : '';
          const eta = formatEta(prog.etaSec);
          detail = [`${formatBytes(prog.bytesRead)} / ${formatBytes(prog.totalBytes)}`, speedMb, eta]
            .filter(Boolean)
            .join(' • ');
        } else if (typeof prog.extractedEntries === 'number') {
          detail = prog.totalEntries
            ? `${prog.extractedEntries} / ${prog.totalEntries} arquivos`
            : `${prog.extractedEntries} arquivos extraídos`;
        }

        onProgress?.({
          percent: pct,
          mode: 'first',
          deterministic: true,
          message: isZst ? 'Descompactando motor PyTorch CUDA...' : 'Extraindo arquivos do motor Python...',
          detail,
        });
      },
    });
  } catch (extractErr) {
    activeAbortController = null;
    activeBootstrapProc = null;
    rmWithRetry(stagingDir);
    throw extractErr;
  }

  activeAbortController = null;
  activeBootstrapProc = null;

  normalizeExtractedStagingRoot(stagingDir);

  const stagingPython = path.join(stagingDir, 'python.exe');
  if (!fs.existsSync(stagingPython)) {
    rmWithRetry(stagingDir);
    const err = new Error('O pacote extraído não contém o executável python.exe na raiz do motor.');
    err.code = 'INVALID_ARCHIVE';
    throw err;
  }

  // 4. Injeção e validação de DLLs App-Local do Visual C++ (evita UAC se DLLs críticas estiverem presentes)
  onProgress?.({
    percent: 88,
    mode: 'first',
    deterministic: true,
    message: 'Configurando bibliotecas nativas Visual C++...',
    detail: '',
  });

  let vcResult = validateAndInjectVcRuntimeDlls(app, stagingDir, logBootEvent);
  if (!vcResult.ok) {
    const vcCandidates = [
      process.resourcesPath ? path.join(process.resourcesPath, 'vc_redist.x64.exe') : null,
      path.join(getProjectRoot(app), 'assets', 'windows', 'vc_redist.x64.exe'),
    ].filter(Boolean);
    const bundledVcPath = vcCandidates.find((p) => fs.existsSync(p));
    if (bundledVcPath) {
      try {
        await execPromise(bundledVcPath, ['/install', '/quiet', '/norestart'], userDataDir);
        vcResult = validateAndInjectVcRuntimeDlls(app, stagingDir, logBootEvent);
      } catch (_) {}
    }
  }

  // 5. Ativação do módulo 'site' no Python Embeddable (python*._pth)
  onProgress?.({
    percent: 90,
    mode: 'first',
    deterministic: true,
    message: 'Configurando caminhos do Python embutido...',
    detail: '',
  });
  try {
    patchEmbeddablePthFiles(stagingDir);
  } catch (err) {
    console.warn('[Bootstrap] Aviso ao ajustar ._pth:', err);
  }

  // 6. Validação obrigatória de saúde (com fallback restrito para pip apenas para ModuleNotFoundError)
  onProgress?.({
    percent: 92,
    mode: 'first',
    deterministic: true,
    message: 'Validando integridade das bibliotecas de IA...',
    detail: '',
  });

  const runHealthCheck = async () => (
    typeof options.verifyHealth === 'function'
      ? options.verifyHealth(stagingPython)
      : verifyPythonHealthDetailed(stagingPython, [], { logBootEvent })
  );

  let health = await runHealthCheck();

  if (!health.healthy && health.missingModule && !options.disablePipFallback) {
    const reqPath = path.join(getProjectRoot(app), 'requirements.txt');
    if (fs.existsSync(reqPath)) {
      onProgress?.({
        percent: 94,
        mode: 'first',
        deterministic: true,
        message: 'Instalando dependências base pré-compiladas...',
        detail: `Módulo pendente: ${health.missingModule}`,
      });
      try {
        await execPromise(
          stagingPython,
          ['-m', 'pip', 'install', '--only-binary=:all:', '--no-warn-script-location', '-r', reqPath],
          stagingDir
        );
        health = await runHealthCheck();
      } catch (pipErr) {
        logBootEvent?.(`[Bootstrap] Fallback pip falhou: ${pipErr.message}`, true);
      }
    }
  }

  if (!health.healthy) {
    rmWithRetry(stagingDir);
    const reasonDetail = health.stderr ? `\nDetalhe: ${health.stderr.slice(0, 320)}` : '';
    const err = new Error(
      health.isDllError
        ? `Falha ao carregar DLL nativa do runtime (Visual C++ Redistributable ou CUDA ausente).${reasonDetail}`
        : `O motor Python extraído falhou na verificação de integridade.${reasonDetail}`
    );
    err.code = health.isDllError ? 'VC_RUNTIME_MISSING' : 'ENGINE_HEALTH_FAILED';
    throw err;
  }

  // 7. Gravação do manifesto de integridade + selo e promoção atômica staging -> engine
  onProgress?.({
    percent: 97,
    mode: 'first',
    deterministic: true,
    message: 'Finalizando instalação atômica do motor...',
    detail: `Versão do motor: ${expectedEngineVersion}`,
  });

  const fingerprint = computeArchiveFingerprint(archivePath);
  writeEngineManifest(stagingDir, {
    engineVersion: expectedEngineVersion,
    archiveName: path.basename(archivePath),
    archiveFormat: format,
    archiveSize: archiveStat.size,
    archiveFingerprint: fingerprint,
    vcDllsValidated: vcResult.ok,
  });

  const hadPreviousEngine = fs.existsSync(engineDir);
  if (hadPreviousEngine) {
    terminateOrphanedEngineProcesses(engineDir, logBootEvent);
    rmWithRetry(backupDir);
    renameWithRetry(engineDir, backupDir);
  }

  try {
    renameWithRetry(stagingDir, engineDir);
  } catch (swapErr) {
    if (hadPreviousEngine && fs.existsSync(backupDir) && !fs.existsSync(engineDir)) {
      try { renameWithRetry(backupDir, engineDir); } catch (_) {}
    }
    rmWithRetry(stagingDir);
    throw swapErr;
  }

  rmWithRetry(backupDir);

  const finalPythonExe = path.join(engineDir, 'python.exe');
  setCachedPython(app, { found: true, executable: finalPythonExe, source: 'userData' });

  onProgress?.({
    percent: 100,
    mode: 'first',
    deterministic: true,
    message: 'Motor configurado com sucesso!',
    detail: '',
  });
  return finalPythonExe;
}

module.exports = {
  CRITICAL_VC_DLLS,
  getCachedPython,
  setCachedPython,
  invalidateCachedPython,
  detectPython,
  autoSetupPython,
  killActiveBootstrapProc,
  readEngineManifest,
  writeEngineManifest,
  isEngineManifestCompatible,
  terminateOrphanedEngineProcesses,
  patchEmbeddablePthFiles,
  validateAndInjectVcRuntimeDlls,
  verifyPythonHealthDetailed,
};
