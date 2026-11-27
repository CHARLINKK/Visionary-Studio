const { BrowserWindow, shell, Notification, session, Menu, MenuItem, nativeImage, ipcMain, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const { getProjectRoot, getIconPath, getPngIconPath, loadUserThemePreference, getServerUrl, SERVER_URL } = require('./paths');

let mainWindow = null;
let bootstrapWindow = null;
let isBootstrapReady = false;
let pendingBootstrapMessages = [];

function getAppNativeIcon() {
  try {
    const pngPath = getPngIconPath();
    if (fs.existsSync(pngPath)) {
      const img = nativeImage.createFromPath(pngPath);
      if (img && !img.isEmpty()) return img;
    }
    const icoPath = getIconPath();
    if (fs.existsSync(icoPath)) {
      const img = nativeImage.createFromPath(icoPath);
      if (img && !img.isEmpty()) return img;
    }
  } catch (_) {}
  return null;
}

function getMainWindow() {
  return mainWindow;
}

function getBootstrapWindow() {
  return bootstrapWindow;
}

function sendToBootstrap(channel, payload) {
  if (!bootstrapWindow || bootstrapWindow.isDestroyed()) return false;
  if (isBootstrapReady) {
    try {
      bootstrapWindow.webContents.send(channel, payload);
      return true;
    } catch (_) {
      return false;
    }
  }
  if (channel === 'bootstrap:progress') {
    const idx = pendingBootstrapMessages.findIndex((item) => item.channel === 'bootstrap:progress');
    if (idx !== -1) {
      pendingBootstrapMessages[idx] = { channel, payload };
      return true;
    }
  }
  pendingBootstrapMessages.push({ channel, payload });
  return true;
}

function resizeBootstrapWindow(height = 265) {
  if (!bootstrapWindow || bootstrapWindow.isDestroyed()) return;
  try {
    const safeHeight = Math.max(240, Math.min(460, Math.round(Number(height) || 265)));
    bootstrapWindow.setResizable(true);
    bootstrapWindow.setSize(500, safeHeight, true);
    bootstrapWindow.center();
    bootstrapWindow.setResizable(false);
  } catch (_) {}
}

function createBootstrapWindow(app) {
  if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
    return bootstrapWindow;
  }

  const themePref = loadUserThemePreference(app);
  const iconImg = getAppNativeIcon();
  const iconPath = getIconPath();

  isBootstrapReady = false;
  pendingBootstrapMessages = [];

  bootstrapWindow = new BrowserWindow({
    width: 500,
    height: 265,
    frame: false,
    resizable: false,
    maximizable: false,
    minimizable: false,
    center: true,
    show: false,
    backgroundColor: themePref.bgColor || '#0c0d12',
    icon: iconImg || iconPath,
    skipTaskbar: true,
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      backgroundThrottling: false,
    },
  });

  bootstrapWindow.once('ready-to-show', () => {
    if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
      bootstrapWindow.show();
      bootstrapWindow.focus();
    }
  });

  bootstrapWindow.webContents.once('did-finish-load', () => {
    isBootstrapReady = true;
    const queued = pendingBootstrapMessages.splice(0);
    for (const item of queued) {
      if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
        try {
          bootstrapWindow.webContents.send(item.channel, item.payload);
        } catch (_) {}
      }
    }
  });

  bootstrapWindow
    .loadFile(path.join(__dirname, 'bootstrap.html'), {
      query: {
        theme: themePref.theme || 'dark',
        accent: themePref.accent || '#8b5cf6',
      },
    })
    .catch((err) => {
      console.error('[Electron] Erro ao carregar bootstrap:', err);
    });

  bootstrapWindow.on('closed', () => {
    bootstrapWindow = null;
    isBootstrapReady = false;
    pendingBootstrapMessages = [];
  });

  return bootstrapWindow;
}

let hasShownTrayMinimizeHint = false;

function createMainWindow({ app, getCloseAction, getHasActiveWork, onCloseActionTriggered, onVisibilityChanged, waitForBackendPromise = null }) {
  return new Promise((resolve) => {
    const iconImg = getAppNativeIcon();
    const iconPath = getIconPath();
    const themePref = loadUserThemePreference(app);

    let initialWidth = 1400;
    let initialHeight = 900;
    let initialX = undefined;
    let initialY = undefined;
    try {
      const cursorPt = typeof screen.getCursorScreenPoint === 'function' ? screen.getCursorScreenPoint() : null;
      const targetDisplay = (cursorPt && typeof screen.getDisplayNearestPoint === 'function')
        ? screen.getDisplayNearestPoint(cursorPt)
        : screen.getPrimaryDisplay();
      const primaryDisplay = targetDisplay || screen.getPrimaryDisplay();
      if (primaryDisplay && primaryDisplay.workAreaSize) {
        initialWidth = primaryDisplay.workAreaSize.width;
        initialHeight = primaryDisplay.workAreaSize.height;
        if (primaryDisplay.workArea) {
          initialX = primaryDisplay.workArea.x;
          initialY = primaryDisplay.workArea.y;
        }
      }
    } catch (_) {}

    mainWindow = new BrowserWindow({
      title: 'Visionary Studio - PRO EDITION',
      width: initialWidth,
      height: initialHeight,
      x: initialX,
      y: initialY,
      minWidth: 1100,
      minHeight: 700,
      frame: false,
      titleBarStyle: 'hidden',
      backgroundColor: themePref.bgColor || '#0c0d12',
      icon: iconImg || iconPath,
      show: false, // Abre no ready-to-show com o splash nativo já desenhado em 0ms
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
        webSecurity: true,
        webviewTag: false,
        spellcheck: false,
        backgroundThrottling: false,
      },
    });

    // Janela principal compilada na memória (DOM inicial montado).
    // Permanece estritamente oculta (show: false) até que a passagem de bastão atômica (app:ready)
    // destrua a splash e revele o Estúdio 100% renderizado (Zero Coexistência de janelas).
    mainWindow.once('ready-to-show', () => {
      // Intencionalmente mantida oculta até dismissSplashAndRevealStudio()
    });

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      try {
        const parsed = new URL(url);
        if (['http:', 'https:', 'mailto:'].includes(parsed.protocol)) {
          shell.openExternal(url);
        }
      } catch (_) {}
      return { action: 'deny' };
    });

    mainWindow.webContents.on('will-navigate', (event, url) => {
      try {
        const parsedUrl = new URL(url);
        if (parsedUrl.origin !== 'http://localhost:5173' && !url.startsWith('file://')) {
          event.preventDefault();
          if (['http:', 'https:', 'mailto:'].includes(parsedUrl.protocol)) {
            shell.openExternal(url);
          }
        }
      } catch (_) {
        event.preventDefault();
      }
    });

    // Menu contextual com sugestões do corretor ortográfico
    mainWindow.webContents.on('context-menu', (_event, params) => {
      if (params.dictionarySuggestions && params.dictionarySuggestions.length > 0) {
        const menu = new Menu();
        params.dictionarySuggestions.forEach((suggestion) => {
          menu.append(
            new MenuItem({
              label: suggestion,
              click: () => mainWindow.webContents.replaceMisspelling(suggestion),
            })
          );
        });
        menu.append(new MenuItem({ type: 'separator' }));
        menu.append(
          new MenuItem({
            label: 'Adicionar ao dicionário',
            click: () => mainWindow.webContents.session.addWordToSpellCheckerDictionary(params.misspelledWord),
          })
        );
        menu.popup();
      }
    });

    // Passagem de Bastão Atômica: Encerra a splash nativa e revela o Estúdio no mesmo tick
    let hasDismissedSplash = false;
    let isBackendConfirmed = !waitForBackendPromise;
    let isRendererReady = false;
    let fallbackRevealTimer = null;

    const tryRevealStudio = () => {
      if (hasDismissedSplash || !isBackendConfirmed || !isRendererReady) return;
      if (!mainWindow || mainWindow.isDestroyed()) return;
      hasDismissedSplash = true;

      if (fallbackRevealTimer) {
        clearTimeout(fallbackRevealTimer);
        fallbackRevealTimer = null;
      }
      ipcMain.removeListener('app:ready', onAppReadySignal);

      // 1. Destrói a janela de splash nativa ANTES de exibir o Estúdio (Zero Coexistência)
      if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
        try {
          bootstrapWindow.destroy();
        } catch (_) {}
        bootstrapWindow = null;
      }
      isBootstrapReady = false;
      pendingBootstrapMessages = [];

      // 2. Exibe o Estúdio maximizado
      mainWindow.maximize();
      mainWindow.show();
      mainWindow.focus();
      onVisibilityChanged?.(true);

      const currentAppIcon = getAppNativeIcon();
      if (currentAppIcon && !currentAppIcon.isEmpty()) {
        mainWindow.setIcon(currentAppIcon);
      } else if (fs.existsSync(iconPath)) {
        mainWindow.setIcon(nativeImage.createFromPath(iconPath));
      }

      // Configura corretor após a janela já estar visível para não atrasar a abertura
      setTimeout(() => {
        try {
          session.defaultSession.setSpellCheckerLanguages(['pt-BR']);
        } catch (_) {}
      }, 500);

      resolve(mainWindow);
    };

    const onAppReadySignal = () => {
      isRendererReady = true;
      tryRevealStudio();
    };

    ipcMain.on('app:ready', onAppReadySignal);

    const armFallbackTimer = () => {
      if (fallbackRevealTimer || hasDismissedSplash) return;
      // Fallback de segurança absoluto para garantir corte direto caso o sinal atrase após o backend subir
      fallbackRevealTimer = setTimeout(() => {
        isRendererReady = true;
        tryRevealStudio();
      }, 7000);
    };

    if (waitForBackendPromise && typeof waitForBackendPromise.then === 'function') {
      waitForBackendPromise.then((ok) => {
        if (!ok) return;
        isBackendConfirmed = true;
        armFallbackTimer();
        tryRevealStudio();
      }).catch(() => {});
    } else {
      armFallbackTimer();
    }

    mainWindow.on('show', () => onVisibilityChanged?.(true));
    mainWindow.on('restore', () => onVisibilityChanged?.(true));
    mainWindow.on('hide', () => onVisibilityChanged?.(false));
    mainWindow.on('minimize', () => onVisibilityChanged?.(false));

    // Carregamento do frontend compilado (injeta serverUrl na query para descoberta síncrona em 0ms)
    const distPath = path.join(getProjectRoot(app), 'gui', 'dist', 'index.html');
    const targetHtml = fs.existsSync(distPath)
      ? distPath
      : path.join(__dirname, '..', 'gui', 'dist', 'index.html');
    const initialServerUrl = typeof getServerUrl === 'function' ? getServerUrl() : SERVER_URL;
    mainWindow.loadFile(targetHtml, { query: { serverUrl: initialServerUrl } }).catch((err) => {
      console.error('[Electron] Erro ao carregar frontend:', err);
    });

    mainWindow.on('close', (event) => {
      const closeAction = typeof getCloseAction === 'function' ? getCloseAction() : 'smart';
      const hasActiveWork = typeof getHasActiveWork === 'function' ? getHasActiveWork() : false;
      const shouldMinimize = closeAction === 'tray' || (closeAction === 'smart' && hasActiveWork);

      if (shouldMinimize) {
        event.preventDefault();
        mainWindow.hide();
        onVisibilityChanged?.(false);
        try {
          mainWindow.webContents.send('app:session-reset');
        } catch (_) {}

        const shouldNotify = hasActiveWork || !hasShownTrayMinimizeHint;
        if (shouldNotify) {
          hasShownTrayMinimizeHint = true;
          try {
            if (Notification.isSupported()) {
              const notif = new Notification({
                title: 'Visionary Studio',
                body: hasActiveWork
                  ? 'Processamento mantido em segundo plano na bandeja do sistema.'
                  : 'Aplicativo minimizado para a bandeja do sistema. Clique no ícone para restaurar.',
                icon: fs.existsSync(iconPath) ? iconPath : undefined,
                silent: true,
              });
              notif.on('click', () => {
                if (mainWindow && !mainWindow.isDestroyed()) {
                  if (mainWindow.isMinimized()) mainWindow.restore();
                  mainWindow.show();
                  mainWindow.focus();
                }
              });
              notif.show();
            }
          } catch (_) {}
        }
      } else {
        if (typeof onCloseActionTriggered === 'function') {
          event.preventDefault();
          onCloseActionTriggered();
        }
      }
    });

    mainWindow.on('closed', () => {
      if (fallbackRevealTimer) {
        clearTimeout(fallbackRevealTimer);
        fallbackRevealTimer = null;
      }
      ipcMain.removeListener('app:ready', onAppReadySignal);
      mainWindow = null;
      if (!hasDismissedSplash) {
        hasDismissedSplash = true;
        resolve(null);
      }
    });
  });
}

module.exports = {
  createMainWindow,
  createBootstrapWindow,
  getMainWindow,
  getBootstrapWindow,
  sendToBootstrap,
  resizeBootstrapWindow,
};
