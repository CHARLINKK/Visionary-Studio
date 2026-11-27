const https = require('https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawn } = require('child_process');

let updaterState = {
  state: 'idle', // 'idle' | 'checking' | 'available' | 'up-to-date' | 'downloading' | 'downloaded' | 'error'
  currentVersion: '1.0.0',
  latestVersion: null,
  releaseUrl: null,
  downloadUrl: null,
  assetName: null,
  expectedSha256: null,
  stagedInstallerPath: null,
  progress: 0,
  message: null,
  checkedAt: null,
};

let autoCheckTimer = null;

function readPackageJson() {
  try {
    const pkgPath = path.join(__dirname, '..', 'package.json');
    return JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
  } catch (_) {
    return { version: '1.0.0' };
  }
}

function normalizeVersion(ver) {
  return String(ver || '')
    .trim()
    .replace(/^v/i, '')
    .split('-')[0];
}

function compareSemver(a, b) {
  const pa = normalizeVersion(a).split('.').map((n) => parseInt(n, 10) || 0);
  const pb = normalizeVersion(b).split('.').map((n) => parseInt(n, 10) || 0);
  const len = Math.max(pa.length, pb.length, 3);
  for (let i = 0; i < len; i++) {
    const va = pa[i] || 0;
    const vb = pb[i] || 0;
    if (va > vb) return 1;
    if (va < vb) return -1;
  }
  return 0;
}

function resolveGithubRepoConfig(pkg = readPackageJson()) {
  const envRepo = (process.env.VISIONARY_GITHUB_REPO || '').trim();
  if (envRepo && envRepo.includes('/')) {
    const [owner, repo] = envRepo.split('/');
    if (owner && repo) return { owner: owner.trim(), repo: repo.trim() };
  }
  const pub = pkg?.build?.publish;
  const pubObj = Array.isArray(pub) ? pub[0] : pub;
  if (pubObj && pubObj.owner && pubObj.repo) {
    return { owner: String(pubObj.owner).trim(), repo: String(pubObj.repo).trim() };
  }
  return { owner: 'CHARLINKK', repo: 'Visionary-Studio' };
}

function notifyUpdaterStatus(getMainWindow, patch = {}) {
  updaterState = { ...updaterState, ...patch };
  try {
    const win = typeof getMainWindow === 'function' ? getMainWindow() : null;
    if (win && !win.isDestroyed()) {
      win.webContents.send('updater:status', updaterState);
    }
  } catch (_) {}
  return updaterState;
}

function fetchJsonHttps(url, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const headers = {
      'User-Agent': 'Visionary-Studio-Updater/1.0',
      Accept: 'application/vnd.github+json',
    };
    if (process.env.GH_TOKEN || process.env.GITHUB_TOKEN) {
      headers.Authorization = `Bearer ${process.env.GH_TOKEN || process.env.GITHUB_TOKEN}`;
    }
    const req = https.get(url, { headers, timeout: timeoutMs }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        fetchJsonHttps(res.headers.location, timeoutMs).then(resolve, reject);
        return;
      }
      if (res.statusCode !== 200) {
        res.resume();
        reject(new Error(`HTTP ${res.statusCode}`));
        return;
      }
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        try {
          resolve(JSON.parse(Buffer.concat(chunks).toString('utf-8')));
        } catch (err) {
          reject(err);
        }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Tempo limite esgotado ao consultar GitHub Releases.'));
    });
  });
}

function selectWindowsInstallerAsset(assets = []) {
  if (!Array.isArray(assets)) return null;
  const exeAssets = assets.filter(
    (a) =>
      a &&
      typeof a.name === 'string' &&
      a.name.toLowerCase().endsWith('.exe') &&
      !a.name.toLowerCase().includes('unins')
  );
  return (
    exeAssets.find((a) => /setup/i.test(a.name) && !/portable/i.test(a.name)) ||
    exeAssets.find((a) => !/portable/i.test(a.name)) ||
    exeAssets[0] ||
    null
  );
}

function extractSha256FromRelease(release, assetName) {
  if (!release || !assetName) return null;
  const asset = (release.assets || []).find((a) => a.name === assetName);
  if (asset && typeof asset.digest === 'string' && asset.digest.startsWith('sha256:')) {
    return asset.digest.slice('sha256:'.length).trim().toLowerCase();
  }
  const body = String(release.body || '');
  const regex = new RegExp(`([a-fA-F0-9]{64})\\s+\\*?${assetName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'i');
  const match = body.match(regex);
  return match ? match[1].toLowerCase() : null;
}

async function checkForUpdates({ getMainWindow, fetchFn = fetchJsonHttps } = {}) {
  const pkg = readPackageJson();
  const currentVersion = pkg.version || '1.0.0';
  const { owner, repo } = resolveGithubRepoConfig(pkg);

  notifyUpdaterStatus(getMainWindow, {
    state: 'checking',
    currentVersion,
    message: 'Verificando atualizações no GitHub Releases...',
  });

  try {
    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/releases/latest`;
    const release = await fetchFn(apiUrl);
    const latestTag = release?.tag_name || release?.name || '';
    const latestVersion = normalizeVersion(latestTag);

    if (!latestVersion) {
      throw new Error('Release sem tag de versão válida.');
    }

    const isNewer = compareSemver(latestVersion, currentVersion) > 0;
    const installerAsset = selectWindowsInstallerAsset(release?.assets || []);
    const expectedSha256 = installerAsset ? extractSha256FromRelease(release, installerAsset.name) : null;

    if (isNewer) {
      return notifyUpdaterStatus(getMainWindow, {
        state: 'available',
        currentVersion,
        latestVersion,
        releaseUrl: release?.html_url || `https://github.com/${owner}/${repo}/releases/latest`,
        downloadUrl: installerAsset?.browser_download_url || null,
        assetName: installerAsset?.name || null,
        expectedSha256,
        checkedAt: new Date().toISOString(),
        message: `Nova versão v${latestVersion} disponível!`,
      });
    }

    return notifyUpdaterStatus(getMainWindow, {
      state: 'up-to-date',
      currentVersion,
      latestVersion,
      releaseUrl: release?.html_url || `https://github.com/${owner}/${repo}/releases`,
      checkedAt: new Date().toISOString(),
      message: `Você já está na versão mais recente (v${currentVersion}).`,
    });
  } catch (err) {
    return notifyUpdaterStatus(getMainWindow, {
      state: 'error',
      currentVersion,
      checkedAt: new Date().toISOString(),
      message: `Não foi possível verificar atualizações (${err?.message || 'offline'}).`,
    });
  }
}

function downloadFileWithProgress(url, destPath, onProgress) {
  return new Promise((resolve, reject) => {
    const headers = { 'User-Agent': 'Visionary-Studio-Updater/1.0' };
    const req = https.get(url, { headers }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        downloadFileWithProgress(res.headers.location, destPath, onProgress).then(resolve, reject);
        return;
      }
      if (res.statusCode !== 200) {
        res.resume();
        reject(new Error(`Falha no download (HTTP ${res.statusCode})`));
        return;
      }
      const totalBytes = parseInt(res.headers['content-length'] || '0', 10);
      let receivedBytes = 0;
      const hash = crypto.createHash('sha256');
      const fileStream = fs.createWriteStream(destPath);

      res.on('data', (chunk) => {
        receivedBytes += chunk.length;
        hash.update(chunk);
        if (totalBytes > 0 && typeof onProgress === 'function') {
          onProgress(Math.min(99, Math.round((receivedBytes / totalBytes) * 100)));
        }
      });

      res.pipe(fileStream);

      fileStream.on('finish', () => {
        fileStream.close(() => {
          resolve({ filePath: destPath, sha256: hash.digest('hex').toLowerCase() });
        });
      });

      fileStream.on('error', (err) => {
        try { fs.unlinkSync(destPath); } catch (_) {}
        reject(err);
      });
    });

    req.on('error', (err) => {
      try { fs.unlinkSync(destPath); } catch (_) {}
      reject(err);
    });
  });
}

async function downloadUpdate({ app, getMainWindow, downloadFn = downloadFileWithProgress } = {}) {
  if (!updaterState.downloadUrl || !updaterState.assetName) {
    return notifyUpdaterStatus(getMainWindow, {
      state: 'error',
      message: 'Nenhum instalador anexado à release do GitHub.',
    });
  }

  const updatesDir = path.join(app.getPath('userData'), 'updates');
  fs.mkdirSync(updatesDir, { recursive: true });
  const safeAssetName = path.basename(updaterState.assetName);
  const destPath = path.join(updatesDir, safeAssetName);

  notifyUpdaterStatus(getMainWindow, {
    state: 'downloading',
    progress: 0,
    message: `Baixando atualização v${updaterState.latestVersion}...`,
  });

  try {
    const { filePath, sha256 } = await downloadFn(updaterState.downloadUrl, destPath, (pct) => {
      notifyUpdaterStatus(getMainWindow, {
        state: 'downloading',
        progress: pct,
        message: `Baixando atualização v${updaterState.latestVersion} (${pct}%)...`,
      });
    });

    if (updaterState.expectedSha256 && sha256 !== updaterState.expectedSha256.toLowerCase()) {
      try { fs.unlinkSync(filePath); } catch (_) {}
      throw new Error('Falha na verificação de integridade SHA-256 do instalador.');
    }

    return notifyUpdaterStatus(getMainWindow, {
      state: 'downloaded',
      progress: 100,
      stagedInstallerPath: filePath,
      message: `Atualização v${updaterState.latestVersion} pronta para instalar!`,
    });
  } catch (err) {
    return notifyUpdaterStatus(getMainWindow, {
      state: 'error',
      progress: 0,
      message: `Erro ao baixar atualização: ${err?.message || err}`,
    });
  }
}

function quitAndInstallUpdate({ onBeforeQuit } = {}) {
  const installerPath = updaterState.stagedInstallerPath;
  if (!installerPath || !fs.existsSync(installerPath)) {
    return { success: false, error: 'Instalador da atualização não encontrado.' };
  }
  try {
    spawn(installerPath, ['--updated'], {
      detached: true,
      stdio: 'ignore',
    }).unref();

    if (typeof onBeforeQuit === 'function') {
      setTimeout(() => onBeforeQuit(), 50);
    }
    return { success: true };
  } catch (err) {
    return { success: false, error: err?.message || String(err) };
  }
}

function scheduleAutoUpdateCheck({ app, getMainWindow, delayMs = 12000 } = {}) {
  if (autoCheckTimer) clearTimeout(autoCheckTimer);
  if (!app?.isPackaged && process.env.VISIONARY_FORCE_UPDATER_CHECK !== '1') {
    return;
  }
  autoCheckTimer = setTimeout(() => {
    checkForUpdates({ getMainWindow }).catch(() => {});
  }, delayMs);
  if (autoCheckTimer.unref) autoCheckTimer.unref();
}

function getUpdaterState() {
  const pkg = readPackageJson();
  return {
    ...updaterState,
    currentVersion: pkg.version || updaterState.currentVersion || '1.0.0',
  };
}

module.exports = {
  compareSemver,
  normalizeVersion,
  resolveGithubRepoConfig,
  selectWindowsInstallerAsset,
  extractSha256FromRelease,
  checkForUpdates,
  downloadUpdate,
  quitAndInstallUpdate,
  scheduleAutoUpdateCheck,
  getUpdaterState,
};
