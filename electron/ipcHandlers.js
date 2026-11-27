const { ipcMain, dialog, shell, Notification, clipboard, app } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const {
  getIconPath,
  getServerUrl,
  getServerPort,
  saveEngineSourcePointer,
  SERVER_PORT,
  SERVER_URL,
} = require('./paths');
const { detectArchiveFormat } = require('./engineArchive');
const {
  checkForUpdates,
  downloadUpdate,
  quitAndInstallUpdate,
  getUpdaterState,
} = require('./updaterManager');

function registerIpcHandlers({
  getMainWindow,
  getBootstrapWindow,
  sendToBootstrap,
  resizeBootstrapWindow,
  setCloseAction,
  setPowerSaveState,
  updateTrayMenu,
  addRecentChapterToTray,
  autoSetupPython,
  detectPython,
  launchApp,
  factoryReset,
  recoverPythonSidecar,
  onQuitApp,
}) {
  // ── Controles da Janela Principal ──
  ipcMain.on('window:set-close-action', (_event, action) => {
    if (['smart', 'tray', 'quit'].includes(action)) {
      setCloseAction?.(action);
      console.log(`[Lifecycle] Preferência de fechamento atualizada: ${action}`);
    }
  });

  ipcMain.on('window:minimize', () => {
    const mainWindow = getMainWindow?.();
    const bootstrapWindow = getBootstrapWindow?.();
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.minimize();
    else if (bootstrapWindow && !bootstrapWindow.isDestroyed()) bootstrapWindow.minimize();
  });

  ipcMain.handle('window:toggle-maximize', () => {
    const mainWindow = getMainWindow?.();
    if (!mainWindow || mainWindow.isDestroyed()) return false;
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
      return false;
    } else {
      mainWindow.maximize();
      return true;
    }
  });

  ipcMain.handle('window:is-maximized', () => {
    const mainWindow = getMainWindow?.();
    return (mainWindow && !mainWindow.isDestroyed()) ? mainWindow.isMaximized() : false;
  });

  ipcMain.on('window:close', () => {
    const mainWindow = getMainWindow?.();
    const bootstrapWindow = getBootstrapWindow?.();
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.close();
    else if (bootstrapWindow && !bootstrapWindow.isDestroyed()) bootstrapWindow.close();
  });

  ipcMain.on('window:focus', () => {
    const mainWindow = getMainWindow?.();
    if (mainWindow && !mainWindow.isDestroyed()) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  ipcMain.on('window:set-progress-bar', (_event, { value, options }) => {
    const mainWindow = getMainWindow?.();
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.setProgressBar(value, options);
    }
  });

  // ── Área de Transferência Nativa (Electron) ──
  ipcMain.handle('clipboard:write-text', (_event, text) => {
    try {
      clipboard.writeText(String(text ?? ''));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  // ── Notificações Nativas ──
  ipcMain.handle('notification:show', (_event, { title, body, actionTab }) => {
    try {
      const iconPath = getIconPath();
      const notif = new Notification({
        title: title || 'Visionary Studio',
        body: body || '',
        icon: fs.existsSync(iconPath) ? iconPath : undefined,
      });

      notif.on('click', () => {
        const mainWindow = getMainWindow?.();
        if (mainWindow && !mainWindow.isDestroyed()) {
          if (mainWindow.isMinimized()) mainWindow.restore();
          mainWindow.show();
          mainWindow.focus();
          if (actionTab) {
            mainWindow.webContents.send('notification:clicked', { actionTab });
          }
        }
      });

      notif.show();
      return { success: true };
    } catch (err) {
      console.warn('[Notification] Erro ao exibir notificação Electron:', err);
      return { success: false, error: err.message };
    }
  });

  // ── Diálogos de Arquivo ──
  ipcMain.handle('dialog:select-folder', async (_event, defaultPath) => {
    const mainWindow = getMainWindow?.();
    if (!mainWindow || mainWindow.isDestroyed()) return { success: false, error: 'Janela não encontrada' };
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Selecionar Pasta de Imagens (Capítulo)',
      properties: ['openDirectory'],
      defaultPath: (defaultPath && fs.existsSync(defaultPath)) ? defaultPath : undefined,
    });
    if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
      return { success: false, error: 'Seleção cancelada pelo usuário' };
    }
    return { success: true, path: result.filePaths[0] };
  });

  // ── Operações de Shell e Windows Explorer ──
  ipcMain.handle('shell:open-path', async (_event, fullPath) => {
    if (typeof fullPath !== 'string' || !fullPath) return { success: false, error: 'Caminho não fornecido ou inválido' };
    try {
      const cleanPath = path.normalize(fullPath);
      const ext = path.extname(cleanPath).toLowerCase();
      const unsafeExts = ['.exe', '.bat', '.cmd', '.vbs', '.ps1', '.msi', '.scr', '.pif', '.application', '.gadget', '.wsf', '.hta', '.cpl', '.msc', '.jar'];
      if (unsafeExts.includes(ext)) {
        return { success: false, error: 'Abertura de executáveis não é permitida por segurança.' };
      }

      if (fs.existsSync(cleanPath)) {
        const err = await shell.openPath(cleanPath);
        return { success: !err, error: err || null };
      }
      const parentDir = path.dirname(cleanPath);
      if (fs.existsSync(parentDir)) {
        const err = await shell.openPath(parentDir);
        return { success: !err, error: err || null };
      }
      return { success: false, error: 'Caminho não encontrado no disco' };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  // Respeita estritamente a regra do AGENTS.md: abertura direta de explorer.exe sem /select
  ipcMain.handle('shell:show-item-in-folder', async (_event, fullPath) => {
    if (typeof fullPath !== 'string' || !fullPath) return { success: false, error: 'Caminho não fornecido ou inválido' };
    try {
      const cleanPath = path.normalize(fullPath);
      if (fs.existsSync(cleanPath)) {
        const stat = fs.statSync(cleanPath);
        const target = stat.isDirectory() ? cleanPath : path.dirname(cleanPath);
        spawn('explorer.exe', [target], { detached: true, stdio: 'ignore' }).unref();
        return { success: true };
      }
      const parentDir = path.dirname(cleanPath);
      if (fs.existsSync(parentDir)) {
        spawn('explorer.exe', [parentDir], { detached: true, stdio: 'ignore' }).unref();
        return { success: true };
      }
      return { success: false, error: 'Caminho não encontrado no disco' };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  // ── Power Save & Tray ──
  ipcMain.on('power:set-active-work', (_event, hasActiveWork) => {
    setPowerSaveState?.(hasActiveWork);
  });

  ipcMain.on('tray:update-status', (_event, payload) => {
    if (payload && typeof payload === 'object') {
      updateTrayMenu?.(payload, Boolean(payload.isWorking));
    }
  });

  ipcMain.handle('jumplist:add-recent', (_event, folderPath, folderName) => {
    if (folderPath && typeof folderPath === 'string') {
      addRecentChapterToTray?.(folderPath, folderName);
      if (fs.existsSync(folderPath)) {
        try {
          app.addRecentDocument(folderPath);
          return { success: true };
        } catch (e) {
          return { success: false, error: e.message };
        }
      }
      return { success: true };
    }
    return { success: false };
  });

  // ── Bootstrap & Setup de Runtime ──
  ipcMain.handle('bootstrap:start-auto-setup', async () => {
    try {
      const pythonExe = await autoSetupPython?.(app, (progress) => {
        if (sendToBootstrap) {
          sendToBootstrap('bootstrap:progress', progress);
        } else {
          const bootstrapWindow = getBootstrapWindow?.();
          if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
            bootstrapWindow.webContents.send('bootstrap:progress', progress);
          }
        }
      });

      const launched = await launchApp?.({ found: true, executable: pythonExe, source: 'userData' });
      if (launched === false) {
        return { success: false, error: 'O servidor local falhou ao iniciar após a configuração.' };
      }

      const bootstrapWindow = getBootstrapWindow?.();
      if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
        bootstrapWindow.close();
      }
      return { success: true };
    } catch (err) {
      console.error('[Bootstrap] Erro no auto-setup:', err);
      return { success: false, error: err.message || 'Falha na configuração' };
    }
  });

  ipcMain.handle('bootstrap:select-engine-archive', async () => {
    try {
      const bootstrapWindow = getBootstrapWindow?.();
      const targetWin = (bootstrapWindow && !bootstrapWindow.isDestroyed()) ? bootstrapWindow : undefined;
      const result = await dialog.showOpenDialog(targetWin, {
        title: 'Selecionar Pacote do Motor (engine-runtime.tar.zst ou .zip)',
        properties: ['openFile'],
        filters: [
          { name: 'Pacote do Motor Visionary', extensions: ['zst', 'zip'] },
          { name: 'Todos os arquivos', extensions: ['*'] },
        ],
      });
      if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
        return { canceled: true, success: false };
      }

      const selectedPath = result.filePaths[0];
      const format = detectArchiveFormat(selectedPath);
      if (!format) {
        return {
          success: false,
          error: `O arquivo "${path.basename(selectedPath)}" não é um pacote .tar.zst ou .zip válido.`,
        };
      }

      saveEngineSourcePointer(app, selectedPath);
      resizeBootstrapWindow?.(265);

      const pythonExe = await autoSetupPython?.(
        app,
        (progress) => {
          if (sendToBootstrap) {
            sendToBootstrap('bootstrap:progress', progress);
          } else {
            const bWin = getBootstrapWindow?.();
            if (bWin && !bWin.isDestroyed()) {
              bWin.webContents.send('bootstrap:progress', progress);
            }
          }
        },
        { archivePath: selectedPath }
      );

      const launched = await launchApp?.({ found: true, executable: pythonExe, source: 'userData' });
      if (launched === false) {
        return { success: false, error: 'O motor foi extraído, mas o servidor local falhou ao iniciar.' };
      }

      const currentBootstrap = getBootstrapWindow?.();
      if (currentBootstrap && !currentBootstrap.isDestroyed()) {
        currentBootstrap.close();
      }
      return { success: true, path: selectedPath };
    } catch (err) {
      console.error('[Bootstrap] Erro ao selecionar/instalar pacote manual:', err);
      return { success: false, error: err.message || 'Falha ao instalar pacote selecionado.' };
    }
  });

  ipcMain.on('bootstrap:set-error-mode', (_event, isError) => {
    resizeBootstrapWindow?.(isError ? 330 : 265);
  });

  ipcMain.handle('bootstrap:check-python', async () => {
    const pythonInfo = await detectPython?.(app);
    if (pythonInfo?.found) {
      const launched = await launchApp?.(pythonInfo);
      if (launched === false) {
        return { found: false, error: 'Motor Python detectado, mas o servidor local falhou ao iniciar.' };
      }
      const bootstrapWindow = getBootstrapWindow?.();
      if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
        bootstrapWindow.close();
      }
    }
    return pythonInfo;
  });

  ipcMain.handle('bootstrap:open-python-site', () => {
    shell.openExternal('https://www.python.org/downloads/release/python-3119/');
  });

  ipcMain.handle('system:open-external', (_event, url) => {
    try {
      const parsed = new URL(url);
      if (['http:', 'https:', 'mailto:'].includes(parsed.protocol)) {
        shell.openExternal(url);
        return { success: true };
      }
      return { success: false, error: 'Protocolo não suportado' };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  ipcMain.handle('bootstrap:factory-reset', async () => {
    factoryReset?.(app);
  });

  ipcMain.handle('sidecar:restart', async () => {
    try {
      if (typeof recoverPythonSidecar === 'function') {
        return await recoverPythonSidecar(app, 'manual_user_restart', { manual: true });
      }
      return { success: false, error: 'Recuperador de sidecar não disponível.' };
    } catch (err) {
      return { success: false, error: err?.message || 'Erro ao reiniciar motor.' };
    }
  });

  ipcMain.handle('bootstrap:open-log', () => {
    try {
      const logsDir = path.join(app.getPath('userData'), 'logs');
      fs.mkdirSync(logsDir, { recursive: true });
      spawn('explorer.exe', [logsDir], { detached: true, stdio: 'ignore' }).unref();
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  ipcMain.handle('system:get-server-url', () => {
    return typeof getServerUrl === 'function' ? getServerUrl() : SERVER_URL;
  });

  ipcMain.handle('system:get-server-port', () => {
    return typeof getServerPort === 'function' ? getServerPort() : SERVER_PORT;
  });

  ipcMain.handle('system:get-initial-action', () => {
    const { getPendingInitialAction, clearPendingInitialAction } = require('./trayManager');
    const act = getPendingInitialAction?.();
    clearPendingInitialAction?.();
    return act || null;
  });

  // ── Auto-Updater via GitHub Releases ──
  ipcMain.handle('updater:get-status', () => {
    return getUpdaterState();
  });

  ipcMain.handle('updater:check', async () => {
    return await checkForUpdates({ getMainWindow });
  });

  ipcMain.handle('updater:download', async () => {
    return await downloadUpdate({ app, getMainWindow });
  });

  ipcMain.handle('updater:install', () => {
    return quitAndInstallUpdate({ onBeforeQuit: onQuitApp });
  });

  // Repasse de telemetria de inicialização em tempo real da janela principal para a Splash nativa
  ipcMain.on('bootstrap:progress', (_event, payload) => {
    if (sendToBootstrap) {
      sendToBootstrap('bootstrap:progress', payload);
      return;
    }
    const bootstrapWindow = getBootstrapWindow?.();
    if (bootstrapWindow && !bootstrapWindow.isDestroyed()) {
      bootstrapWindow.webContents.send('bootstrap:progress', payload);
    }
  });
}

module.exports = {
  registerIpcHandlers,
};
