const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn, spawnSync } = require('child_process');
const {
  getProjectRoot,
  SERVER_PORT,
  SERVER_URL,
  getServerPort,
  getServerUrl,
  setServerPort,
  findAvailablePort,
} = require('./paths');
const { TOKEN_HEADER, getSessionToken } = require('./sessionAuth');
const {
  getCachedPython,
  setCachedPython,
  invalidateCachedPython: baseInvalidateCachedPython,
  detectPython: baseDetectPython,
  autoSetupPython,
  killActiveBootstrapProc,
  terminateOrphanedEngineProcesses,
} = require('./pythonBootstrap');

let pythonProcess = null;
let pythonProcessExited = false;
let pythonExitCode = null;
let ollamaProcess = null;
let recentStderr = [];
let recentStdout = [];
let bootLogPath = null;

// Estados de Resiliência em Runtime (Watchdog & Graceful Shutdown Idempotente)
let isShuttingDown = false;
let cleanupPromise = null;
let lastPythonInfo = null;
let watchdogTimer = null;
let consecutiveHealthFailures = 0;
let isRecoveringSidecar = false;
let restartTimestamps = [];
let sidecarStatusCallback = null;

const WATCHDOG_INTERVAL_MS = 10000;
const MAX_CONSECUTIVE_HEALTH_FAILURES = 3;
const MAX_RESTARTS_PER_WINDOW = 3;
const RESTART_WINDOW_MS = 60000;

function initBootLogger(app) {
  if (bootLogPath) return;
  try {
    const logsDir = path.join(app.getPath('userData'), 'logs');
    fs.mkdirSync(logsDir, { recursive: true });
    bootLogPath = path.join(logsDir, 'sidecar_boot.log');

    // Rotação se o arquivo exceder 1MB
    if (fs.existsSync(bootLogPath) && fs.statSync(bootLogPath).size > 1024 * 1024) {
      try {
        const oldLog = path.join(logsDir, 'sidecar_boot.old.log');
        fs.copyFileSync(bootLogPath, oldLog);
        fs.unlinkSync(bootLogPath);
      } catch (_) {}
    }
  } catch (_) {}
}

function logBootEvent(msg, isError = false) {
  const line = `[${new Date().toISOString()}] ${isError ? '[ERROR] ' : '[INFO] '}${msg}\n`;
  if (isError) console.error(msg);
  else console.log(msg);

  if (bootLogPath) {
    try {
      fs.appendFileSync(bootLogPath, line, 'utf-8');
    } catch (_) {}
  }
}

const sleepAsync = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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

function cleanOrphanedOllama(app) {
  // Limpeza segura de instâncias órfãs do Ollama no Windows:
  // Se o app fechar abruptamente, o Ollama pode continuar rodando em segundo plano.
  // CUIDADO DE ENGENHARIA: No Windows, PIDs são reciclados pelo sistema operacional.
  // Usamos o filtro '/fi IMAGENAME eq ollama.exe' para garantir que o taskkill NUNCA mate
  // acidentalmente um processo não relacionado do usuário (ex: Chrome, Steam) que tenha recebido o mesmo PID.
  initBootLogger(app);
  try {
    const userData = app.getPath('userData');
    const projectRoot = getProjectRoot(app);
    const pidFiles = [
      path.join(userData, '.ollama_visionary.pid'),
      path.join(projectRoot, '.ollama_visionary.pid'),
    ];

    for (const pidFile of pidFiles) {
      if (fs.existsSync(pidFile)) {
        try {
          const rawPid = fs.readFileSync(pidFile, 'utf-8').trim();
          if (rawPid && /^\d+$/.test(rawPid)) {
            const numericPid = Number(rawPid);
            let isAlive = false;
            try {
              process.kill(numericPid, 0);
              isAlive = true;
            } catch (_) {
              isAlive = false;
            }
            if (isAlive && process.platform === 'win32') {
              // Blindagem: só mata se o PID pertencer de fato ao ollama.exe para evitar matar processos reutilizados
              spawnSync('taskkill', ['/pid', rawPid, '/fi', 'IMAGENAME eq ollama.exe', '/f', '/t'], { windowsHide: true });
            }
          }
          fs.unlinkSync(pidFile);
          logBootEvent(`[Lifecycle] Limpeza de Ollama órfão realizada (PID ${rawPid}).`);
        } catch (_) {}
      }
    }
  } catch (_) {}
}

function invalidateCachedPython(app) {
  return baseInvalidateCachedPython(app, logBootEvent);
}

function detectPython(app) {
  return baseDetectPython(app, { initBootLogger, logBootEvent });
}

function startPythonBackend(app, pythonInfo, onProgress) {
  if (pythonProcess) {
    console.log('[Electron] Python backend is already running.');
    return;
  }

  initBootLogger(app);
  if (pythonInfo) {
    lastPythonInfo = pythonInfo;
  }
  const projectRoot = getProjectRoot(app);
  const pythonScript = path.join(projectRoot, 'src', 'server.py');
  const myPid = process.pid;

  const pythonExecutable = pythonInfo?.executable || 'python';
  const extraArgs = pythonInfo?.argsPrefix || [];
  const activeServerPort = typeof getServerPort === 'function' ? getServerPort() : SERVER_PORT;
  const args = [...extraArgs, pythonScript, '--port', String(activeServerPort), '--parent-pid', String(myPid)];

  logBootEvent(`[Electron] Starting Python Backend: ${pythonExecutable} ${args.join(' ')}`);

  pythonProcessExited = false;
  pythonExitCode = null;
  recentStderr = [];
  recentStdout = [];

  const userDataDir = app.getPath('userData');
  const userGlobalOllamaModels = path.join(require('os').homedir(), '.ollama', 'models');
  const canonicalOllamaModels = process.env.OLLAMA_MODELS || userGlobalOllamaModels;
  const isolatedHfHome = path.join(userDataDir, 'models');

  fs.mkdirSync(isolatedHfHome, { recursive: true });

  pythonProcess = spawn(pythonExecutable, args, {
    cwd: projectRoot,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUNBUFFERED: '1',
      VISIONARY_USER_DATA: userDataDir,
      VISIONARY_PROJECT_ROOT: projectRoot,
      HF_HOME: isolatedHfHome,
      OLLAMA_MODELS: canonicalOllamaModels,
      // Segredo efêmero de sessão: o backend exige o cabeçalho X-Visionary-Token (injetado pelo
      // processo main em sessionAuth.js). Vai por ambiente, nunca por argumento de linha de comando.
      VISIONARY_AUTH_TOKEN: getSessionToken(),
    },
  });

  let bootProgress = 10;
  const handleLog = (data, isError = false) => {
    const msg = data.toString().trim();
    if (!msg) return;
    logBootEvent(`[Python ${isError ? 'stderr' : 'stdout'}] ${msg}`, isError);
    if (isError) {
      recentStderr.push(msg);
      if (recentStderr.length > 30) recentStderr.shift();
    } else {
      recentStdout.push(msg);
      if (recentStdout.length > 30) recentStdout.shift();
    }

    if (onProgress) {
      let displayMsg = 'Inicializando motor local...';
      if (bootProgress < 15) bootProgress = 15;

      if (msg.includes('Iniciando FastAPI') || msg.includes('router') || msg.includes('Config') || msg.includes('ModelManager')) {
        bootProgress = Math.max(bootProgress, 25);
        displayMsg = 'Carregando módulos do sistema...';
      }
      if (msg.includes('Started server process')) {
        bootProgress = Math.max(bootProgress, 35);
        displayMsg = 'Processo do servidor iniciado...';
      }
      if (msg.includes('Waiting for application startup')) {
        bootProgress = Math.max(bootProgress, 40);
        displayMsg = 'Inicializando serviços de IA...';
      }
      if (msg.includes('Application startup complete')) {
        bootProgress = Math.max(bootProgress, 45);
        displayMsg = 'Serviços inicializados com sucesso.';
      }
      if (msg.includes('Uvicorn running on')) {
        bootProgress = 48;
        displayMsg = 'Servidor local pronto...';
      }

      onProgress({
        percent: Math.min(50, Math.round(bootProgress)),
        mode: 'normal',
        message: displayMsg,
      });
    }
  };

  if (pythonProcess.stdout) pythonProcess.stdout.on('data', (d) => handleLog(d, false));
  if (pythonProcess.stderr) pythonProcess.stderr.on('data', (d) => handleLog(d, true));

  pythonProcess.on('error', (err) => {
    logBootEvent(`[Electron] Failed to start Python backend: ${err.message || err}`, true);
  });

  const spawnedRef = pythonProcess;
  pythonProcess.on('exit', (code, signal) => {
    if (pythonProcess === spawnedRef) {
      pythonProcess = null;
    }
    pythonProcessExited = true;
    pythonExitCode = code;
    logBootEvent(`[Electron] Python backend exited with code ${code}, signal ${signal}`, code !== 0);

    // Se o watchdog estiver ativo e não for um encerramento intencional, dispara auto-recuperação imediata
    if (!isShuttingDown && !isRecoveringSidecar && watchdogTimer !== null) {
      setImmediate(() => {
        recoverPythonSidecar(app, `exit_code_${code ?? 'null'}`).catch((err) => {
          logBootEvent(`[Watchdog] Erro inesperado na auto-recuperação: ${err?.message || err}`, true);
        });
      });
    }
  });
}

function getRecentStderr() {
  return recentStderr.join('\n');
}

function waitForServer(timeoutMs = 30000) {
  const startTime = Date.now();
  return new Promise((resolve) => {
    let settled = false;
    let retryTimer = null;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      if (retryTimer) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
      resolve(result);
    };

    const retry = () => {
      if (settled) return;
      if (Date.now() - startTime > timeoutMs) {
        const currentPort = typeof getServerPort === 'function' ? getServerPort() : SERVER_PORT;
        logBootEvent(`[Electron] Tempo limite esgotado (${timeoutMs}ms) aguardando o servidor Python na porta ${currentPort}.`, true);
        finish({
          success: false,
          reason: 'timeout',
          exitCode: pythonExitCode,
          lastStderr: getRecentStderr(),
        });
      } else {
        retryTimer = setTimeout(check, 45);
      }
    };

    const check = () => {
      if (settled) return;
      if (pythonProcessExited) {
        const exitMsg = `O servidor Python encerrou prematuramente (código: ${pythonExitCode}).`;
        logBootEvent(`[Electron] ${exitMsg}`, true);
        finish({
          success: false,
          reason: 'exited',
          exitCode: pythonExitCode,
          lastStderr: getRecentStderr(),
        });
        return;
      }

      const currentUrl = typeof getServerUrl === 'function' ? getServerUrl() : SERVER_URL;
      const req = http.get(`${currentUrl}/api/health?quick=1`, { timeout: 1500 }, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          logBootEvent('[Electron] Conexão com backend FastAPI estabelecida com sucesso.');
          finish({ success: true });
        } else {
          retry();
        }
      });
      req.on('error', () => {
        retry();
      });
      req.on('timeout', () => {
        req.destroy();
        retry();
      });
    };

    check();
  });
}

function checkServerHealthQuick(timeoutMs = 2500) {
  return new Promise((resolve) => {
    try {
      const currentUrl = typeof getServerUrl === 'function' ? getServerUrl() : SERVER_URL;
      const req = http.get(`${currentUrl}/api/health?quick=1`, { timeout: timeoutMs }, (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      });
      req.on('error', () => resolve(false));
      req.on('timeout', () => {
        req.destroy();
        resolve(false);
      });
    } catch (_) {
      resolve(false);
    }
  });
}

function emitSidecarStatus(payload) {
  if (typeof sidecarStatusCallback === 'function') {
    try {
      sidecarStatusCallback(payload);
    } catch (_) {}
  }
}

function stopRuntimeWatchdog() {
  if (watchdogTimer !== null) {
    clearInterval(watchdogTimer);
    watchdogTimer = null;
  }
  consecutiveHealthFailures = 0;
}

async function recoverPythonSidecar(app, reason = 'unexpected_exit', options = {}) {
  const { manual = false, waitForServerFn = waitForServer, startBackendFn = startPythonBackend } = options;
  if (isShuttingDown) {
    return { success: false, reason: 'shutting_down' };
  }
  if (isRecoveringSidecar) {
    return { success: false, reason: 'already_recovering' };
  }

  initBootLogger(app);
  const now = Date.now();
  if (manual) {
    restartTimestamps = [];
  } else {
    restartTimestamps = restartTimestamps.filter((ts) => now - ts < RESTART_WINDOW_MS);
  }

  if (restartTimestamps.length >= MAX_RESTARTS_PER_WINDOW) {
    stopRuntimeWatchdog();
    const msg = `O motor Python falhou repetidamente (${MAX_RESTARTS_PER_WINDOW} quedas em 60s). Auto-restart pausado.`;
    logBootEvent(`[Watchdog] ${msg}`, true);
    emitSidecarStatus({
      state: 'failed',
      reason: 'crash_loop',
      message: msg,
      exitCode: pythonExitCode,
      lastStderr: getRecentStderr(),
    });
    return { success: false, reason: 'crash_loop', message: msg };
  }

  const targetPython = lastPythonInfo || getCachedPython(app);
  if (!targetPython || !targetPython.executable) {
    const msg = 'Executável do motor Python não disponível para reinicialização.';
    logBootEvent(`[Watchdog] ${msg}`, true);
    emitSidecarStatus({ state: 'failed', reason: 'no_python_info', message: msg });
    return { success: false, reason: 'no_python_info', message: msg };
  }

  isRecoveringSidecar = true;
  consecutiveHealthFailures = 0;
  restartTimestamps.push(now);
  const attempt = restartTimestamps.length;

  logBootEvent(`[Watchdog] Iniciando recuperação do backend Python (motivo: ${reason}, tentativa ${attempt}/${MAX_RESTARTS_PER_WINDOW})...`);
  emitSidecarStatus({
    state: 'reconnecting',
    reason,
    attempt,
    maxAttempts: MAX_RESTARTS_PER_WINDOW,
  });

  try {
    // 1. Se o processo anterior ainda estiver pendurado (ex: health_timeout), encerra sua árvore
    if (pythonProcess && pythonProcess.pid) {
      const hungPid = pythonProcess.pid;
      try {
        if (process.platform === 'win32') {
          spawnSync('taskkill', ['/pid', String(hungPid), '/f', '/t'], { windowsHide: true });
        } else {
          pythonProcess.kill('SIGKILL');
        }
      } catch (_) {}
      pythonProcess = null;
    }

    // 2. Verifica se a porta atual está livre (ou escolhe nova porta dinâmica caso esteja em TIME_WAIT)
    const currentPort = typeof getServerPort === 'function' ? getServerPort() : SERVER_PORT;
    if (typeof findAvailablePort === 'function' && typeof setServerPort === 'function') {
      try {
        const chosenPort = await findAvailablePort(currentPort);
        if (chosenPort && chosenPort !== currentPort) {
          setServerPort(chosenPort);
          logBootEvent(`[Watchdog] Porta ${currentPort} ocupada após queda; migrando backend para porta ${chosenPort}.`);
        }
      } catch (_) {}
    }

    // 3. Relança o processo Python e aguarda health check
    startBackendFn(app, targetPython);
    const serverRes = await waitForServerFn(25000);
    if (serverRes && serverRes.success) {
      const activeUrl = typeof getServerUrl === 'function' ? getServerUrl() : SERVER_URL;
      const activePort = typeof getServerPort === 'function' ? getServerPort() : SERVER_PORT;
      logBootEvent(`[Watchdog] Backend Python recuperado com sucesso em ${activeUrl} (tentativa ${attempt}).`);
      emitSidecarStatus({
        state: 'online',
        reason,
        attempt,
        serverUrl: activeUrl,
        port: activePort,
      });
      return { success: true, serverUrl: activeUrl, port: activePort, attempt };
    }

    const errMsg = `Falha ao recuperar motor Python na tentativa ${attempt}/${MAX_RESTARTS_PER_WINDOW}.`;
    logBootEvent(`[Watchdog] ${errMsg}`, true);
    if (restartTimestamps.length >= MAX_RESTARTS_PER_WINDOW) {
      stopRuntimeWatchdog();
      emitSidecarStatus({
        state: 'failed',
        reason: 'crash_loop',
        message: errMsg,
        exitCode: pythonExitCode,
        lastStderr: getRecentStderr(),
      });
    }
    return { success: false, reason: serverRes?.reason || 'boot_failed', message: errMsg };
  } finally {
    isRecoveringSidecar = false;
  }
}

function startRuntimeWatchdog(app, options = {}) {
  const {
    onStatusChange,
    intervalMs = WATCHDOG_INTERVAL_MS,
    maxFailures = MAX_CONSECUTIVE_HEALTH_FAILURES,
    healthCheckFn = checkServerHealthQuick,
  } = options;

  if (typeof onStatusChange === 'function') {
    sidecarStatusCallback = onStatusChange;
  }

  stopRuntimeWatchdog();
  if (isShuttingDown) return;

  watchdogTimer = setInterval(async () => {
    if (isShuttingDown || isRecoveringSidecar) return;

    if (pythonProcessExited || !pythonProcess) {
      await recoverPythonSidecar(app, 'process_exited');
      return;
    }

    const healthy = await healthCheckFn(2500);
    if (healthy) {
      consecutiveHealthFailures = 0;
      return;
    }

    consecutiveHealthFailures += 1;
    logBootEvent(
      `[Watchdog] Aviso: falha no heartbeat /api/health?quick=1 (${consecutiveHealthFailures}/${maxFailures}).`,
      true
    );

    if (consecutiveHealthFailures >= maxFailures) {
      consecutiveHealthFailures = 0;
      await recoverPythonSidecar(app, 'health_timeout');
    }
  }, intervalMs);

  if (watchdogTimer && typeof watchdogTimer.unref === 'function') {
    watchdogTimer.unref();
  }
}

function requestShutdownNative(timeoutMs = 800) {
  return new Promise((resolve) => {
    try {
      const currentUrl = typeof getServerUrl === 'function' ? getServerUrl() : SERVER_URL;
      const parsedUrl = new URL(currentUrl);
      const req = http.request(
        {
          hostname: parsedUrl.hostname || '127.0.0.1',
          port: parsedUrl.port || (typeof getServerPort === 'function' ? getServerPort() : SERVER_PORT),
          path: '/api/shutdown',
          method: 'POST',
          headers: {
            [TOKEN_HEADER]: getSessionToken(),
            'Content-Length': 0,
            Connection: 'close',
          },
          timeout: timeoutMs,
        },
        (res) => {
          res.resume();
          res.on('end', () => resolve(true));
        }
      );
      req.on('error', () => resolve(false));
      req.on('timeout', () => {
        req.destroy();
        resolve(false);
      });
      req.end();
    } catch (_) {
      resolve(false);
    }
  });
}

function waitForPidExit(procRef, pyPid, maxWaitMs = 900) {
  return new Promise((resolve) => {
    let settled = false;
    let pollTimer = null;
    let deadlineTimer = null;

    const finish = (exited) => {
      if (settled) return;
      settled = true;
      if (pollTimer) clearInterval(pollTimer);
      if (deadlineTimer) clearTimeout(deadlineTimer);
      if (procRef && typeof procRef.removeListener === 'function') {
        procRef.removeListener('exit', onProcExit);
      }
      resolve(exited);
    };

    const onProcExit = () => finish(true);

    if (procRef && typeof procRef.once === 'function') {
      procRef.once('exit', onProcExit);
    }

    const checkAlive = () => {
      try {
        process.kill(pyPid, 0);
      } catch (_) {
        finish(true);
      }
    };

    checkAlive();
    if (settled) return;

    pollTimer = setInterval(checkAlive, 25);
    if (pollTimer.unref) pollTimer.unref();

    deadlineTimer = setTimeout(() => finish(false), maxWaitMs);
    if (deadlineTimer.unref) deadlineTimer.unref();
  });
}

function cleanup(app) {
  isShuttingDown = true;
  stopRuntimeWatchdog();

  if (cleanupPromise) {
    return cleanupPromise;
  }

  cleanupPromise = (async () => {
    killActiveBootstrapProc();

    // 1. Encerramento gracioso do servidor Python via /api/shutdown com http.request nativo
    const procRef = pythonProcess;
    pythonProcess = null;

    if (procRef && procRef.pid) {
      const pyPid = procRef.pid;
      const exitPromise = waitForPidExit(procRef, pyPid, 900);

      try {
        await requestShutdownNative(800);
      } catch (_) {}

      const exitedCleanly = await exitPromise;

      // 2. Fallback de segurança: mata a árvore de processos caso o Python tenha travado
      if (!exitedCleanly) {
        logBootEvent(`[Lifecycle] Python PID ${pyPid} não encerrou no tempo limite; aplicando taskkill na árvore.`, true);
        try {
          if (process.platform === 'win32') {
            spawnSync('taskkill', ['/pid', String(pyPid), '/f', '/t'], { windowsHide: true });
          } else {
            procRef.kill('SIGKILL');
          }
        } catch (_) {}
      }
    }

    // 3. Limpeza de processo Ollama iniciado pelo Visionary (.ollama_visionary.pid)
    cleanOrphanedOllama(app);

    if (ollamaProcess && ollamaProcess.pid) {
      try {
        if (process.platform === 'win32') {
          spawnSync('taskkill', ['/pid', String(ollamaProcess.pid), '/fi', 'IMAGENAME eq ollama.exe', '/f', '/t'], { windowsHide: true });
        } else {
          ollamaProcess.kill('SIGKILL');
        }
      } catch (_) {}
      ollamaProcess = null;
    }
  })();

  return cleanupPromise;
}

function factoryReset(app) {
  logBootEvent('[Electron] Initiating Factory Reset / Environment Repair...');
  invalidateCachedPython(app);
  const userData = app.getPath('userData');
  const engineDir = path.join(userData, 'engine');
  const modelsDir = path.join(userData, 'models');
  const settingsFile = path.join(userData, 'settings.json');

  if (pythonProcess && pythonProcess.pid) {
    try { spawnSync('taskkill', ['/pid', String(pythonProcess.pid), '/f', '/t'], { windowsHide: true }); } catch (_) {}
  }
  if (ollamaProcess && ollamaProcess.pid) {
    try { spawnSync('taskkill', ['/pid', String(ollamaProcess.pid), '/fi', 'IMAGENAME eq ollama.exe', '/f', '/t'], { windowsHide: true }); } catch (_) {}
  }
  try { spawnSync('taskkill', ['/im', 'ollama.exe', '/f', '/t'], { windowsHide: true }); } catch (_) {}

  try { fs.rmSync(engineDir, { recursive: true, force: true }); } catch (_) {}
  try { fs.rmSync(modelsDir, { recursive: true, force: true }); } catch (_) {}
  try { fs.rmSync(settingsFile, { force: true }); } catch (_) {}

  app.relaunch();
  app.exit(0);
}

function resetWatchdogStateForTests() {
  stopRuntimeWatchdog();
  isShuttingDown = false;
  cleanupPromise = null;
  isRecoveringSidecar = false;
  restartTimestamps = [];
  consecutiveHealthFailures = 0;
  pythonProcessExited = false;
  pythonExitCode = null;
}

module.exports = {
  detectPython,
  autoSetupPython,
  startPythonBackend,
  waitForServer,
  checkServerHealthQuick,
  startRuntimeWatchdog,
  stopRuntimeWatchdog,
  recoverPythonSidecar,
  cleanOrphanedOllama,
  cleanup,
  factoryReset,
  getCachedPython,
  setCachedPython,
  invalidateCachedPython,
  getBootLogPath: () => bootLogPath,
  getRecentStderr,
  getPythonProcess: () => pythonProcess,
  getOllamaProcess: () => ollamaProcess,
  isSidecarShuttingDown: () => isShuttingDown,
  resetWatchdogStateForTests,
};
