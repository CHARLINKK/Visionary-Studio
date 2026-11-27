const { app, BrowserWindow, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');

const {
  initPortableMode,
  registerWindowsAumid,
  loadCloseActionPreference,
  resolveBundledEngineArchive,
  SERVER_PORT,
  SERVER_URL,
  getServerPort,
  getServerUrl,
  setServerPort,
  findAvailablePort,
} = require('./paths');

const { TOKEN_HEADER, getSessionToken, installSessionAuth } = require('./sessionAuth');

const {
  detectPython,
  autoSetupPython,
  startPythonBackend,
  waitForServer,
  startRuntimeWatchdog,
  stopRuntimeWatchdog,
  recoverPythonSidecar,
  cleanOrphanedOllama,
  cleanup,
  factoryReset,
  getCachedPython,
  setCachedPython,
  invalidateCachedPython,
} = require('./sidecarManager');

const {
  createMainWindow,
  createBootstrapWindow,
  getMainWindow,
  getBootstrapWindow,
  sendToBootstrap,
  resizeBootstrapWindow,
} = require('./windowManager');

const {
  createTray,
  destroyTray,
  updateTrayMenu,
  addRecentChapterToTray,
  getTaskbarOverlayIcon,
  setPowerSaveState,
  setupJumpList,
  handleActionArg,
} = require('./trayManager');

const { registerIpcHandlers } = require('./ipcHandlers');

app.setName('Visionary Studio');

// Modo portátil e registro do AUMID no Windows
const portableRoot = initPortableMode(app);
registerWindowsAumid(app, shell, portableRoot);

// Flags de GPU do Chromium para manter pan/zoom fluidos em páginas em alta resolução.
app.commandLine.appendSwitch('enable-gpu-rasterization');
app.commandLine.appendSwitch('enable-zero-copy');
app.commandLine.appendSwitch('enable-accelerated-2d-canvas');
app.commandLine.appendSwitch('enable-features', 'CanvasOopRasterization,SmoothScrolling,VaapiVideoDecoder');
app.commandLine.appendSwitch('ignore-gpu-blocklist');
app.commandLine.appendSwitch('high-dpi-support', '1');

// Estados de ciclo de vida
let hasActiveWork = false;
let closeAction = 'smart';
let isAppLaunched = false;

function syncTaskbarOverlay(mainWindow, badgeState, statusText) {
  if (process.platform !== 'win32' || !mainWindow || mainWindow.isDestroyed()) return;
  try {
    const overlayImg = getTaskbarOverlayIcon(badgeState);
    mainWindow.setOverlayIcon(overlayImg, overlayImg ? String(statusText || 'Visionary Studio') : '');
  } catch (_) {}
}

function showAndFocusMainWindow() {
  const mainWindow = getMainWindow();
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
    updateTrayMenu({ isWindowVisible: true });
    return mainWindow;
  }
  const bootstrapWindow = getBootstrapWindow();
  if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
    if (bootstrapWindow.isMinimized()) bootstrapWindow.restore();
    bootstrapWindow.show();
    bootstrapWindow.focus();
  }
  return null;
}

function handleSidecarStatusChange(statusPayload) {
  if (!statusPayload || typeof statusPayload !== 'object') return;
  const { state, port } = statusPayload;

  if (state === 'reconnecting') {
    updateTrayMenu({
      status: 'Reiniciando motor de IA...',
      isWorking: true,
      badgeState: 'warning',
    });
  } else if (state === 'online') {
    if (port) {
      try {
        installSessionAuth(session.defaultSession, getSessionToken(), port);
      } catch (_) {}
    }
    updateTrayMenu({
      status: hasActiveWork ? 'Processando...' : 'Ocioso',
      isWorking: hasActiveWork,
      badgeState: hasActiveWork ? 'working' : 'idle',
    });
  } else if (state === 'failed') {
    updateTrayMenu({
      status: 'Falha no motor de IA',
      isWorking: false,
      badgeState: 'error',
    });
  }

  const mainWindow = getMainWindow();
  if (mainWindow && !mainWindow.isDestroyed()) {
    try {
      mainWindow.webContents.send('sidecar:status', statusPayload);
    } catch (_) {}
  }
}

function getActiveWindows() {
  return [getMainWindow(), getBootstrapWindow()].filter((w) => w && !w.isDestroyed());
}

function hideAllAppWindows() {
  for (const win of getActiveWindows()) {
    try {
      win.hide();
    } catch (_) {}
  }
}

async function initiateGracefulQuit() {
  if (isQuitting) return;
  isQuitting = true;

  // Feedback visual instantâneo ao usuário: oculta as janelas e remove o tray antes do cleanup em background
  hideAllAppWindows();
  destroyTray();
  setPowerSaveState(false);

  await handleFullTerminationAsync();

  for (const win of getActiveWindows()) {
    try {
      win.destroy();
    } catch (_) {}
  }
  app.quit();
}

// Inicialização da aplicação
async function launchApp(pythonInfo) {
  if (isAppLaunched) return true;
  isAppLaunched = true;

  let resolveBackendReady = null;
  const backendReadyPromise = new Promise((resolve) => {
    resolveBackendReady = resolve;
  });

  startPythonBackend(app, pythonInfo, (progress) => {
    sendToBootstrap('bootstrap:progress', progress);
  });

  // Paraleliza carregamento do Chromium/React (hidden até app:ready + backend ok) com o boot do FastAPI
  const mainWindowPromise = createMainWindow({
    app,
    getCloseAction: () => closeAction,
    getHasActiveWork: () => hasActiveWork,
    waitForBackendPromise: backendReadyPromise,
    onCloseActionTriggered: () => {
      initiateGracefulQuit();
    },
    onVisibilityChanged: (isVisible) => {
      updateTrayMenu({ isWindowVisible: isVisible });
    },
  });

  // Inicializa ícone na bandeja enquanto Python e Chromium sobem em paralelo
  createTray(getTrayCallbacks());
  updateTrayMenu('Iniciando Inteligência...', true, getTrayCallbacks());

  const serverResult = await waitForServer();

  if (!serverResult || !serverResult.success) {
    resolveBackendReady?.(false);
    const pendingWin = getMainWindow();
    if (pendingWin && !pendingWin.isDestroyed()) {
      try {
        pendingWin.destroy();
      } catch (_) {}
    }
    invalidateCachedPython(app);
    isAppLaunched = false;
    console.error('[Electron] Falha na conexão com o backend Python:', serverResult);
    const activePortMsg = typeof getServerPort === 'function' ? getServerPort() : SERVER_PORT;
    let errorDetail = `Tempo limite esgotado ao aguardar o servidor de IA (porta ${activePortMsg}).`;
    if (serverResult?.reason === 'exited') {
      errorDetail = `O motor Python encerrou inesperadamente (código: ${serverResult.exitCode}).\n${serverResult.lastStderr || ''}`.trim();
    }
    sendToBootstrap('bootstrap:error', { message: errorDetail });
    return false;
  }

  resolveBackendReady?.(true);

  // Memoriza o motor Python verificado com sucesso para fast-path no próximo boot
  setCachedPython(app, pythonInfo);

  const preloadedWin = getMainWindow();
  if (preloadedWin && !preloadedWin.isDestroyed()) {
    try {
      preloadedWin.webContents.send('sidecar:status', {
        state: 'online',
        reason: 'initial_boot',
        serverUrl: typeof getServerUrl === 'function' ? getServerUrl() : SERVER_URL,
        port: typeof getServerPort === 'function' ? getServerPort() : SERVER_PORT,
      });
    } catch (_) {}
  }

  sendToBootstrap('bootstrap:progress', {
    percent: 50,
    mode: 'normal',
    message: 'Servidor conectado! Carregando espaço de trabalho...',
  });

  const mainWindow = await mainWindowPromise;

  startRuntimeWatchdog(app, {
    onStatusChange: handleSidecarStatusChange,
  });

  updateTrayMenu(
    {
      status: 'Ocioso',
      isWorking: false,
      badgeState: 'idle',
      closeAction,
      isWindowVisible: true,
    },
    false,
    getTrayCallbacks()
  );
  hasActiveWork = false;
  setupJumpList(app);
  handleActionArg(process.argv, mainWindow);
  const { scheduleAutoUpdateCheck } = require('./updaterManager');
  scheduleAutoUpdateCheck({ app, getMainWindow, delayMs: 12000 });
  return true;
}

function getTrayCallbacks() {
  return {
    onOpenApp: () => {
      showAndFocusMainWindow();
    },
    onToggleApp: () => {
      const mainWindow = getMainWindow();
      if (mainWindow && !mainWindow.isDestroyed()) {
        if (mainWindow.isVisible() && !mainWindow.isMinimized() && mainWindow.isFocused()) {
          mainWindow.hide();
          updateTrayMenu({ isWindowVisible: false });
        } else {
          showAndFocusMainWindow();
        }
      } else {
        showAndFocusMainWindow();
      }
    },
    onNavigateTab: (tab) => {
      const mainWindow = showAndFocusMainWindow();
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('app:navigate-tab', tab);
      }
    },
    onOpenRecentChapter: (chapter) => {
      const mainWindow = showAndFocusMainWindow();
      if (mainWindow && !mainWindow.isDestroyed() && chapter?.path) {
        mainWindow.webContents.send('tray:open-recent-chapter', chapter);
      }
    },
    onOpenSymbols: () => {
      const mainWindow = showAndFocusMainWindow();
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('tray:open-symbols');
      }
    },
    onCancelJob: () => {
      const mainWindow = getMainWindow();
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('tray:cancel-job');
      }
    },
    onStopOllama: () => {
      try {
        const req = http.request(
          `${typeof getServerUrl === 'function' ? getServerUrl() : SERVER_URL}/api/rpc/stopOllamaServer`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              [TOKEN_HEADER]: getSessionToken(),
            },
          },
          () => {
            const mainWindow = getMainWindow();
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send('tray:ollama-stopped');
            }
          }
        );
        req.on('error', () => {});
        req.write(JSON.stringify({ args: [], kwargs: {} }));
        req.end();
      } catch (_) {}
    },
    onOpenLogs: () => {
      try {
        const { spawn } = require('child_process');
        const logsDir = path.join(app.getPath('userData'), 'logs');
        fs.mkdirSync(logsDir, { recursive: true });
        spawn('explorer.exe', [logsDir], { detached: true, stdio: 'ignore' }).unref();
      } catch (_) {}
    },
    onSetCloseAction: (action) => {
      if (!['smart', 'tray', 'quit'].includes(action)) return;
      closeAction = action;
      updateTrayMenu({ closeAction: action });
      const mainWindow = getMainWindow();
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('tray:close-action-changed', action);
      }
    },
    onQuit: () => {
      initiateGracefulQuit();
    },
  };
}

// Registro central de handlers IPC
registerIpcHandlers({
  getMainWindow,
  getBootstrapWindow,
  sendToBootstrap,
  resizeBootstrapWindow,
  setCloseAction: (action) => {
    closeAction = action;
    updateTrayMenu({ closeAction: action });
  },
  setPowerSaveState: (active) => {
    hasActiveWork = !!active;
    setPowerSaveState(active);
  },
  updateTrayMenu: (statusOrPayload, isWorking) => {
    const workingFlag =
      statusOrPayload && typeof statusOrPayload === 'object'
        ? !!statusOrPayload.isWorking
        : !!isWorking;
    hasActiveWork = workingFlag;
    updateTrayMenu(statusOrPayload, workingFlag, getTrayCallbacks());

    const mainWindow = getMainWindow();
    if (mainWindow && !mainWindow.isDestroyed()) {
      const { getTrayState } = require('./trayManager');
      const st = getTrayState();
      syncTaskbarOverlay(mainWindow, st.badgeState, st.statusText);
    }
  },
  addRecentChapterToTray,
  autoSetupPython,
  detectPython,
  launchApp,
  factoryReset,
  recoverPythonSidecar,
  onQuitApp: () => initiateGracefulQuit(),
});

// Garante instância única para evitar conflito de porta no backend local
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  console.log('[Electron] Outra instância já está em execução. Encerrando...');
  app.quit();
} else {
  app.on('second-instance', (_event, commandLine) => {
    const mainWindow = getMainWindow();
    const bootstrapWindow = getBootstrapWindow();

    if (mainWindow && !mainWindow.isDestroyed()) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      if (!mainWindow.isVisible()) mainWindow.show();
      mainWindow.focus();
      handleActionArg(commandLine, mainWindow);
      try {
        mainWindow.webContents.send('app:session-reset');
      } catch (_) {}
    } else if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
      if (bootstrapWindow.isMinimized()) bootstrapWindow.restore();
      bootstrapWindow.show();
      bootstrapWindow.focus();
    }
  });

  // Inicialização do ciclo de vida
  app.whenReady().then(async () => {
    // 1. Exibe a Splash Flutuante Compacta Nativa imediatamente (500x265, skipTaskbar: true)
    createBootstrapWindow(app);
    closeAction = loadCloseActionPreference(app);

    // Detecção dinâmica de conflito de porta para o servidor FastAPI
    const chosenPort = await findAvailablePort(SERVER_PORT);
    if (chosenPort !== SERVER_PORT) {
      setServerPort(chosenPort);
      console.log(`[Electron] Porta padrão ${SERVER_PORT} ocupada. Utilizando porta dinâmica ${chosenPort}.`);
    }
    const activePort = typeof getServerPort === 'function' ? getServerPort() : SERVER_PORT;

    // Autenticação do backend local: anexa X-Visionary-Token às requisições da GUI para o FastAPI.
    installSessionAuth(session.defaultSession, getSessionToken(), activePort);
    cleanOrphanedOllama(app);

    let pythonInfo = await detectPython(app);
    console.log('[Electron] Python Detection Result:', pythonInfo);

    let wasFirstBoot = false;
    let setupError = null;
    if (!pythonInfo.found && resolveBundledEngineArchive(app)) {
      wasFirstBoot = true;
      try {
        console.log('[Electron] First boot detected. Auto-extracting bundled engine runtime...');
        const extractedExe = await autoSetupPython(app, (progress) => {
          sendToBootstrap('bootstrap:progress', progress);
        });
        pythonInfo = { found: true, executable: extractedExe, source: 'userData' };
      } catch (setupErr) {
        setupError = setupErr;
        console.error('[Electron] Auto-setup failed, falling back to manual bootstrap UI:', setupErr);
      }
    }

    if (pythonInfo.found) {
      sendToBootstrap('bootstrap:progress', {
        percent: wasFirstBoot ? 94 : 15,
        mode: wasFirstBoot ? 'first' : 'normal',
        message: `Iniciando servidor FastAPI local (127.0.0.1:${activePort})...`,
      });

      await launchApp(pythonInfo);
    } else {
      sendToBootstrap('bootstrap:error', {
        message:
          setupError?.message ||
          'Pacote de runtime do motor Python (engine-runtime.tar.zst ou prebuilt-engine.zip) não encontrado ao lado do instalador ou diretórios de busca.',
        code: setupError?.code || 'ARCHIVE_NOT_FOUND',
      });
    }

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        const main = getMainWindow();
        if (main) {
          createMainWindow({
            app,
            getCloseAction: () => closeAction,
            getHasActiveWork: () => hasActiveWork,
            onCloseActionTriggered: () => {
              initiateGracefulQuit();
            },
          });
        } else {
          createBootstrapWindow(app);
        }
      }
    });
  });
}

// Encerramento seguro e liberação de recursos
function handleFullTermination() {
  if (!gotTheLock) return;
  stopRuntimeWatchdog();
  destroyTray();
  setPowerSaveState(false);
  cleanup(app);
}

let isQuitting = false;
// Teto de 1.5s no cleanup aguarda encerramento gracioso de jobs/Ollama sem segurar o processo no Windows.
async function handleFullTerminationAsync() {
  if (!gotTheLock) return;
  stopRuntimeWatchdog();
  destroyTray();
  setPowerSaveState(false);
  try {
    await Promise.race([
      cleanup(app),
      new Promise((resolve) => setTimeout(resolve, 1500)),
    ]);
  } catch (_) {}
}

app.on('before-quit', (event) => {
  if (!gotTheLock || isQuitting) return;
  event.preventDefault();
  isQuitting = true;
  hideAllAppWindows();
  handleFullTerminationAsync().finally(() => {
    app.quit();
  });
});

const _legacyQuit = (() => {
  handleFullTermination();
});

app.on('window-all-closed', () => {
  if (!isQuitting) {
    handleFullTermination();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

process.on('SIGINT', () => {
  handleFullTermination();
  process.exit(0);
});

process.on('SIGTERM', () => {
  handleFullTermination();
  process.exit(0);
});

process.on('unhandledRejection', (reason) => {
  console.error('[Electron Unhandled Rejection]:', reason);
});

process.on('uncaughtException', (err) => {
  console.error('[Electron Uncaught Exception]:', err);
  try {
    const { dialog } = require('electron');
    if (app.isReady()) {
      dialog.showErrorBox(
        'Erro Inesperado no Visionary Studio',
        `Ocorreu uma falha no processo principal:\n${err?.message || err}\n\nO aplicativo será encerrado com segurança.`
      );
    }
  } catch (_) {}
  handleFullTermination();
  app.exit(1);
});

// Endpoint local de captura para inspeção automatizada (restrito a dev)
if (!app.isPackaged && process.env.VISIONARY_ENABLE_SCREENSHOT_SERVER === '1') {
  const agentServer = http.createServer(async (req, res) => {
    const mainWindow = getMainWindow();
    if (req.url === '/screenshot' && mainWindow && !mainWindow.isDestroyed()) {
      try {
        const img = await mainWindow.webContents.capturePage();
        const buf = img.toPNG();
        res.writeHead(200, { 'Content-Type': 'image/png' });
        res.end(buf);
      } catch (e) {
        res.writeHead(500);
        res.end(e.message);
      }
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  agentServer.on('error', (err) => {
    console.warn('[Agent Server] Could not bind port 5005:', err.message);
  });
  agentServer.listen(5005, '127.0.0.1');
}
