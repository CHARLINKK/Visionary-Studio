const path = require('path');
const fs = require('fs');

const net = require('net');

const APP_AUMID = 'com.visionary.studio.v2';
let SERVER_PORT = 5000;
let SERVER_URL = `http://127.0.0.1:${SERVER_PORT}`;

function setServerPort(port) {
  SERVER_PORT = Number(port);
  SERVER_URL = `http://127.0.0.1:${SERVER_PORT}`;
}

function getServerPort() {
  return SERVER_PORT;
}

function getServerUrl() {
  return SERVER_URL;
}

function isPortAvailable(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close(() => resolve(true));
    });
    server.listen(port, host);
  });
}

async function findAvailablePort(startPort = 5000, maxAttempts = 20) {
  for (let i = 0; i < maxAttempts; i++) {
    const port = startPort + i;
    if (await isPortAvailable(port)) {
      return port;
    }
  }
  return startPort;
}

const ENGINE_PACKAGE_NAMES = ['engine-runtime.tar.zst', 'prebuilt-engine.zip'];
const ENGINE_SOURCE_POINTER_FILE = 'engine-source.path';
const ENGINE_MANIFEST_FILE = '.engine-manifest.json';
const ENGINE_SEAL_FILE = '.engine-complete';

/**
 * Lê um arquivo de texto detectando automaticamente UTF-16LE (com/sem BOM), UTF-16BE (com BOM) e UTF-8.
 * Essencial para ler ponteiros gravados pelo NSIS com suporte pleno a acentos e caracteres Unicode.
 */
function readTextFileUnicodeSafe(filePath) {
  const buf = fs.readFileSync(filePath);
  if (!buf || buf.length === 0) return '';

  let text = '';
  if (buf.length >= 2 && buf[0] === 0xff && buf[1] === 0xfe) {
    text = buf.subarray(2).toString('utf16le');
  } else if (buf.length >= 2 && buf[0] === 0xfe && buf[1] === 0xff) {
    const payload = Buffer.from(buf.subarray(2));
    for (let i = 0; i + 1 < payload.length; i += 2) {
      const tmp = payload[i];
      payload[i] = payload[i + 1];
      payload[i + 1] = tmp;
    }
    text = payload.toString('utf16le');
  } else if (buf.length >= 3 && buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf) {
    text = buf.subarray(3).toString('utf8');
  } else if (buf.length >= 4 && buf.length % 2 === 0) {
    let oddNulls = 0;
    let evenNonNulls = 0;
    const pairs = buf.length / 2;
    for (let i = 0; i < buf.length; i += 2) {
      if (buf[i] !== 0x00) evenNonNulls++;
      if (buf[i + 1] === 0x00) oddNulls++;
    }
    if (oddNulls / pairs >= 0.35 && evenNonNulls / pairs >= 0.5) {
      text = buf.toString('utf16le');
    } else {
      text = buf.toString('utf8');
    }
  } else {
    text = buf.toString('utf8');
  }

  return text.replace(/^\uFEFF/, '').replace(/\0/g, '').trim();
}

/**
 * Retorna a versão esperada do motor Python empacotado a partir do package.json.
 */
function getExpectedEngineVersion(app) {
  const candidates = [];
  try {
    if (app) {
      candidates.push(path.join(getProjectRoot(app), 'package.json'));
    }
  } catch (_) {}
  candidates.push(path.resolve(__dirname, '..', 'package.json'));

  for (const pkgPath of candidates) {
    try {
      if (pkgPath && fs.existsSync(pkgPath)) {
        const parsed = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
        if (parsed && (parsed.engineVersion || parsed.version)) {
          return String(parsed.engineVersion || parsed.version);
        }
      }
    } catch (_) {}
  }
  return '1.0.0';
}

/**
 * Lê o ponteiro engine-source.path em userData de forma segura para Unicode.
 */
function readEngineSourcePointer(app) {
  try {
    const pointerFile = path.join(app.getPath('userData'), ENGINE_SOURCE_POINTER_FILE);
    if (!fs.existsSync(pointerFile)) return null;
    const raw = readTextFileUnicodeSafe(pointerFile);
    if (!raw) return null;

    let candidate = '';
    if (raw.startsWith('{')) {
      try {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.path === 'string') {
          candidate = parsed.path.trim();
        }
      } catch (_) {}
    }
    if (!candidate) {
      candidate = raw.split(/\r?\n/).map((line) => line.trim()).find(Boolean) || '';
    }

    candidate = candidate.replace(/^"(.*)"$/, '$1').trim();
    if (candidate && fs.existsSync(candidate)) {
      return path.normalize(candidate);
    }
  } catch (_) {}
  return null;
}

/**
 * Persiste atomicamente o caminho selecionado pelo usuário para o pacote do motor em UTF-8.
 */
function saveEngineSourcePointer(app, archivePath) {
  if (!app || typeof archivePath !== 'string' || !archivePath.trim()) {
    throw new Error('Caminho do pacote do motor inválido.');
  }
  const userDataDir = app.getPath('userData');
  fs.mkdirSync(userDataDir, { recursive: true });
  const pointerFile = path.join(userDataDir, ENGINE_SOURCE_POINTER_FILE);
  const resolvedArchive = path.resolve(archivePath.trim());
  const tmpFile = `${pointerFile}.${process.pid}.${Date.now()}.tmp`;
  try {
    fs.writeFileSync(tmpFile, resolvedArchive, 'utf-8');
    fs.renameSync(tmpFile, pointerFile);
  } catch (_) {
    try { fs.unlinkSync(tmpFile); } catch (_) {}
    fs.writeFileSync(pointerFile, resolvedArchive, 'utf-8');
  }
  return pointerFile;
}

/**
 * Resolução do diretório raiz do projeto (suporta empacotado em app.asar.unpacked ou modo de desenvolvimento).
 */
function getProjectRoot(app) {
  if (!app.isPackaged) {
    return path.resolve(__dirname, '..');
  }
  const unpacked = path.join(process.resourcesPath, 'app.asar.unpacked');
  const plain = path.join(process.resourcesPath, 'app');
  if (fs.existsSync(unpacked)) {
    return unpacked;
  }
  return plain;
}

/**
 * Retorna o caminho absoluto do ícone da aplicação (.ico).
 */
function getIconPath() {
  const unpackedRoot = process.resourcesPath ? path.join(process.resourcesPath, 'app.asar.unpacked') : '';
  if (unpackedRoot) {
    const unpackedV2 = path.join(unpackedRoot, 'assets', 'icon_v2.ico');
    if (fs.existsSync(unpackedV2)) return unpackedV2;
    const unpackedIco = path.join(unpackedRoot, 'assets', 'icon.ico');
    if (fs.existsSync(unpackedIco)) return unpackedIco;
  }
  const v2Path = path.resolve(__dirname, '..', 'assets', 'icon_v2.ico');
  if (fs.existsSync(v2Path)) {
    return v2Path;
  }
  return path.resolve(__dirname, '..', 'assets', 'icon.ico');
}

/**
 * Retorna o caminho absoluto do ícone PNG transparente de alta resolução.
 */
function getPngIconPath() {
  const unpackedRoot = process.resourcesPath ? path.join(process.resourcesPath, 'app.asar.unpacked') : '';
  if (unpackedRoot) {
    const unpackedPng = path.join(unpackedRoot, 'assets', 'icon.png');
    if (fs.existsSync(unpackedPng)) return unpackedPng;
  }
  const pngAssets = path.resolve(__dirname, '..', 'assets', 'icon.png');
  if (fs.existsSync(pngAssets)) {
    return pngAssets;
  }
  return path.resolve(__dirname, '..', 'gui', 'public', 'icon.png');
}

/**
 * Retorna o caminho absoluto do ícone (.ico) de uma tarefa da JumpList do Windows.
 */
function getJumpListIconPath(iconFileName) {
  const unpackedRoot = process.resourcesPath ? path.join(process.resourcesPath, 'app.asar.unpacked') : '';
  if (unpackedRoot) {
    const unpackedIco = path.join(unpackedRoot, 'assets', 'jumplist', iconFileName);
    if (fs.existsSync(unpackedIco)) return unpackedIco;
  }
  const localIco = path.resolve(__dirname, '..', 'assets', 'jumplist', iconFileName);
  if (fs.existsSync(localIco)) {
    return localIco;
  }
  return getIconPath();
}

/**
 * Detecção e isolamento de dados no modo portátil (True Portable).
 */
function initPortableMode(app) {
  const isManualPortable =
    fs.existsSync(path.join(path.dirname(process.execPath), '.portable')) ||
    fs.existsSync(path.join(__dirname, '..', '.portable'));
  const portableRoot =
    process.env.PORTABLE_EXECUTABLE_DIR || (isManualPortable ? path.dirname(process.execPath) : null);

  if (portableRoot) {
    const portableDataDir = path.join(portableRoot, 'data');
    try {
      fs.mkdirSync(portableDataDir, { recursive: true });
      app.setPath('userData', portableDataDir);
      console.log('[Electron] Executando em Modo Portátil Genuíno. UserData isolado:', portableDataDir);
    } catch (err) {
      console.warn('[Electron] Falha ao configurar pasta de dados portátil:', err);
    }
  }
  return portableRoot;
}

/**
 * Registro oficial do atalho no menu Iniciar para AUMID (notificações nativas e agrupamento na barra de tarefas).
 */
function registerWindowsAumid(app, shell, portableRoot) {
  if (process.platform === 'win32' && !portableRoot) {
    app.setAppUserModelId(APP_AUMID);
    // Adia escrita Win32 COM do atalho (.lnk) para fora da janela crítica de boot
    const timer = setTimeout(() => {
      try {
        const startMenuDir = path.join(app.getPath('appData'), 'Microsoft', 'Windows', 'Start Menu', 'Programs');
        const shortcutPath = path.join(startMenuDir, 'Visionary Studio.lnk');
        const iconPath = getIconPath();
        const launcherExe = path.resolve(__dirname, '..', 'Visionary.exe');

        const targetExe = (!app.isPackaged && fs.existsSync(launcherExe)) ? launcherExe : process.execPath;
        const targetArgs = (!app.isPackaged && targetExe === process.execPath) ? `"${path.resolve(__dirname, '..')}"` : '';

        shell.writeShortcutLink(shortcutPath, fs.existsSync(shortcutPath) ? 'replace' : 'create', {
          target: targetExe,
          args: targetArgs,
          icon: fs.existsSync(iconPath) ? iconPath : targetExe,
          iconIndex: 0,
          appUserModelId: APP_AUMID,
          description: 'Visionary Studio - PRO Manga AI Suite',
        });
      } catch (err) {
        console.warn('[AUMID] Registro de atalho no Start Menu:', err);
      }
    }, 3500);
    if (timer && typeof timer.unref === 'function') {
      timer.unref();
    }
  }
}

/**
 * Lê a preferência de fechamento do usuário no settings.json ('smart' | 'tray' | 'quit').
 */
function loadCloseActionPreference(app) {
  try {
    const userData = app.getPath('userData');
    const settingsPaths = [
      path.join(userData, 'settings.json'),
      path.join(getProjectRoot(app), 'settings.json'),
    ];
    for (const p of settingsPaths) {
      if (fs.existsSync(p)) {
        const raw = fs.readFileSync(p, 'utf-8');
        const parsed = JSON.parse(raw);
        if (parsed.close_action && ['smart', 'tray', 'quit'].includes(parsed.close_action)) {
          return parsed.close_action;
        }
      }
    }
  } catch (_) {}
  return 'smart';
}

/**
 * Lê o tema e a cor de destaque salvos pelo usuário no settings.json para sincronizar a janela de Splash/Bootstrap.
 */
function loadUserThemePreference(app) {
  const colorMap = {
    'Roxo (Padrão)': '#8b5cf6',
    'Azul Elétrico': '#3b82f6',
    'Azul': '#3b82f6',
    'Ciano Cyber': '#06b6d4',
    'Verde Esmeralda': '#10b981',
    'Verde': '#10b981',
    'Laranja Solar': '#f59e0b',
    'Laranja': '#f59e0b',
    'Rosa Sakura': '#ec4899',
    'Vermelho Carmim': '#ef4444',
    'Vermelho': '#ef4444',
  };
  const themeAttrMap = {
    'Dark': 'dark',
    'Light': 'light',
    'OLED': 'oled',
    'WarmPaper': 'warm-paper',
    'EInk': 'e-ink',
    'NeoTokyo': 'neo-tokyo',
  };
  const bgMap = {
    'dark': '#0c0d12',
    'warm-paper': '#f5efe4',
    'oled': '#000000',
    'e-ink': '#191c21',
    'neo-tokyo': '#060a12',
    'light': '#f8fafc',
  };

  let themeAttr = 'dark';
  let accentHex = '#8b5cf6';

  try {
    const userData = app.getPath('userData');
    const settingsPaths = [
      path.join(userData, 'settings.json'),
      path.join(getProjectRoot(app), 'settings.json'),
    ];
    for (const p of settingsPaths) {
      if (fs.existsSync(p)) {
        const parsed = JSON.parse(fs.readFileSync(p, 'utf-8'));
        if (parsed.theme) {
          if (parsed.theme === 'System') {
            try {
              const { nativeTheme } = require('electron');
              themeAttr = nativeTheme.shouldUseDarkColors ? 'dark' : 'light';
            } catch (_) {
              themeAttr = 'dark';
            }
          } else if (themeAttrMap[parsed.theme]) {
            themeAttr = themeAttrMap[parsed.theme];
          }
        }
        if (parsed.accent) {
          if (colorMap[parsed.accent]) {
            accentHex = colorMap[parsed.accent];
          } else if (typeof parsed.accent === 'string' && parsed.accent.startsWith('#')) {
            accentHex = parsed.accent;
          }
        }
        break;
      }
    }
  } catch (_) {}

  return {
    theme: themeAttr,
    accent: accentHex,
    bgColor: bgMap[themeAttr] || '#0c0d12',
  };
}

/**
 * Localiza o pacote de runtime embutido do motor Python/PyTorch (engine-runtime.tar.zst ou prebuilt-engine.zip).
 */
function resolveBundledEngineArchive(app) {
  const projectRoot = getProjectRoot(app);
  const execDir = path.dirname(process.execPath);

  const pointedPath = readEngineSourcePointer(app);
  if (pointedPath) {
    return pointedPath;
  }

  let downloadsDir = '';
  let desktopDir = '';
  try { downloadsDir = app.getPath('downloads'); } catch (_) {}
  try { desktopDir = app.getPath('desktop'); } catch (_) {}

  const resDir = process.resourcesPath || '';

  const candidates = [
    resDir ? path.join(resDir, 'engine-runtime.tar.zst') : null,
    path.join(execDir, 'engine-runtime.tar.zst'),
    path.join(projectRoot, 'assets', 'python', 'engine-runtime.tar.zst'),
    downloadsDir ? path.join(downloadsDir, 'engine-runtime.tar.zst') : null,
    desktopDir ? path.join(desktopDir, 'engine-runtime.tar.zst') : null,
    resDir ? path.join(resDir, 'prebuilt-engine.zip') : null,
    resDir ? path.join(resDir, 'assets', 'python', 'prebuilt-engine.zip') : null,
    path.join(execDir, 'assets', 'python', 'prebuilt-engine.zip'),
    path.join(projectRoot, 'assets', 'python', 'prebuilt-engine.zip'),
    downloadsDir ? path.join(downloadsDir, 'prebuilt-engine.zip') : null,
    desktopDir ? path.join(desktopDir, 'prebuilt-engine.zip') : null,
  ];
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

module.exports = {
  APP_AUMID,
  get SERVER_PORT() { return SERVER_PORT; },
  get SERVER_URL() { return SERVER_URL; },
  setServerPort,
  getServerPort,
  getServerUrl,
  isPortAvailable,
  findAvailablePort,
  ENGINE_PACKAGE_NAMES,
  ENGINE_SOURCE_POINTER_FILE,
  ENGINE_MANIFEST_FILE,
  ENGINE_SEAL_FILE,
  readTextFileUnicodeSafe,
  getExpectedEngineVersion,
  readEngineSourcePointer,
  saveEngineSourcePointer,
  getProjectRoot,
  getIconPath,
  getPngIconPath,
  getJumpListIconPath,
  initPortableMode,
  registerWindowsAumid,
  loadCloseActionPreference,
  loadUserThemePreference,
  resolveBundledEngineArchive,
};
