/**
 * Smoke test de inicialização e integridade do Electron.
 * Executa o runtime do Electron de forma headless, valida carregamento dos módulos,
 * preload scripts, contextBridge e encerramento seguro.
 */
const { app, BrowserWindow } = require('electron');
const path = require('path');

// Timeout de segurança global para o smoke test (15s)
const safetyTimeout = setTimeout(() => {
  console.error('[Smoke Test Timeout] Electron initialization took more than 15 seconds.');
  process.exit(1);
}, 15000);

// Suprimir janelas e dialogs visíveis
app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('disable-software-rasterizer');

async function runSmokeTest() {
  console.log('[Smoke Test] Starting Electron smoke test...');

  try {
    // 1. Validar módulos principais do Electron e suporte nativo a Zstandard
    const zlib = require('zlib');
    if (typeof zlib.createZstdDecompress !== 'function') {
      throw new Error('Runtime Electron sem zlib.createZstdDecompress nativo!');
    }
    console.log('[Smoke Test] Native zlib.createZstdDecompress available.');

    const paths = require('../electron/paths');
    console.log('[Smoke Test] paths.js loaded successfully. Server port:', paths.SERVER_PORT);

    require('../electron/engineArchive');
    require('../electron/pythonBootstrap');
    console.log('[Smoke Test] engineArchive.js and pythonBootstrap.js loaded successfully.');

    const sessionAuth = require('../electron/sessionAuth');
    console.log('[Smoke Test] sessionAuth.js loaded. Token generated:', !!sessionAuth.getSessionToken());

    const { registerIpcHandlers } = require('../electron/ipcHandlers');
    registerIpcHandlers({ setCloseAction: () => 'smart' });
    console.log('[Smoke Test] ipcHandlers registered cleanly.');

    // 2. Aguardar app ready
    await app.whenReady();
    console.log('[Smoke Test] app.whenReady() resolved.');

    // 2.5 Validar trayManager (ícones com badge BGRA, overlay icon e estado de recentes)
    const trayManager = require('../electron/trayManager');
    for (const badgeState of ['idle', 'working', 'success', 'error', 'warning']) {
      const iconImg = trayManager.getBadgedTrayIcon(badgeState);
      if (!iconImg || iconImg.isEmpty()) {
        throw new Error(`getBadgedTrayIcon failed or returned empty for state: ${badgeState}`);
      }
    }
    const overlayWorking = trayManager.getTaskbarOverlayIcon('working');
    if (!overlayWorking || overlayWorking.isEmpty()) {
      throw new Error('getTaskbarOverlayIcon("working") failed or returned empty');
    }
    if (trayManager.getTaskbarOverlayIcon('idle') !== null) {
      throw new Error('getTaskbarOverlayIcon("idle") should return null');
    }

    trayManager.addRecentChapterToTray('C:\\Manga\\Ch01', 'Ch01');
    trayManager.addRecentChapterToTray('C:\\Manga\\Ch02', 'Ch02');
    trayManager.addRecentChapterToTray('c:\\manga\\ch01', 'Ch01_Updated');
    const st = trayManager.getTrayState();
    if (st.recentChapters.length !== 2 || st.recentChapters[0].name !== 'Ch01_Updated') {
      throw new Error(`Recent chapters deduplication failed: ${JSON.stringify(st.recentChapters)}`);
    }
    console.log('[Smoke Test] trayManager icons and state verified.');

    // 3. Criar janela de teste oculta com o preload real
    const preloadPath = path.resolve(__dirname, '../electron/preload.js');
    const win = new BrowserWindow({
      show: false,
      width: 400,
      height: 300,
      webPreferences: {
        preload: preloadPath,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });

    // 4. Carregar trayFlyout.html real e testar contextBridge + renderização de estado
    const flyoutHtmlPath = path.resolve(__dirname, '../electron/trayFlyout.html');
    await win.loadFile(flyoutHtmlPath);

    const isExposed = await win.webContents.executeJavaScript(`
      (function() {
        const apiOk = Boolean(
          window.electronAPI &&
          window.electronAPI.isElectron === true &&
          typeof window.electronAPI.minimize === 'function' &&
          typeof window.electronAPI.updateTrayStatus === 'function' &&
          typeof window.electronAPI.onOpenRecentChapterFromTray === 'function' &&
          typeof window.electronAPI.onCloseActionChangedFromTray === 'function' &&
          typeof window.electronAPI.onOllamaStoppedFromTray === 'function' &&
          typeof window.electronAPI.sendTrayFlyoutAction === 'function' &&
          typeof window.electronAPI.onTrayFlyoutState === 'function' &&
          typeof window.renderTrayState === 'function'
        );
        if (!apiOk) return false;
        window.renderTrayState({
          statusText: 'Traduzindo balões (2 tarefas)',
          isWorking: true,
          badgeState: 'working',
          progressPercent: 64,
          activeChapterName: 'Solo_Leveling_Ch01',
          recentChapters: [{ name: 'Berserk_Ch364', path: 'C:/Manga/Berserk_Ch364' }],
          closeAction: 'tray',
          isWindowVisible: true,
        });
        return document.getElementById('step-pct').textContent === '64%' &&
               document.getElementById('active-chapter').textContent === 'Solo_Leveling_Ch01';
      })()
    `);

    if (!isExposed) {
      throw new Error('electronAPI contextBridge or trayFlyout.html state rendering failed!');
    }

    console.log('[Smoke Test] electronAPI contract and trayFlyout.html verified in renderer context.');

    // 4.5 Carregar bootstrap.html real com query de tema e validar UI de recuperação/seletor de pacote
    const bootstrapHtmlPath = path.resolve(__dirname, '../electron/bootstrap.html');
    await win.loadFile(bootstrapHtmlPath, {
      query: { theme: 'neo-tokyo', accent: '#06b6d4' },
    });

    const bootstrapOk = await win.webContents.executeJavaScript(`
      (function() {
        const themeApplied = document.documentElement.getAttribute('data-theme') === 'neo-tokyo';
        const apiExposed = Boolean(
          window.electronAPI &&
          typeof window.electronAPI.selectEngineArchive === 'function' &&
          typeof window.electronAPI.setBootstrapErrorMode === 'function' &&
          typeof window.showError === 'function'
        );
        if (!themeApplied || !apiExposed) return false;
        window.showError('Pacote de teste ausente');
        const optionsVisible = getComputedStyle(document.getElementById('optionsView')).display !== 'none';
        const btnSelectExists = Boolean(document.getElementById('btnSelectArchive'));
        const errTextOk = document.getElementById('errorBox').textContent.includes('Pacote de teste ausente');
        return optionsVisible && btnSelectExists && errTextOk;
      })()
    `);

    if (!bootstrapOk) {
      throw new Error('bootstrap.html theme query, electronAPI hooks, or error recovery UI failed!');
    }

    console.log('[Smoke Test] bootstrap.html recovery UI and theme synchronization verified.');

    // 5. Cleanup
    win.destroy();
    clearTimeout(safetyTimeout);
    console.log('[Smoke Test] All checks passed successfully.');
    app.quit();
    process.exit(0);
  } catch (err) {
    clearTimeout(safetyTimeout);
    console.error('[Smoke Test Error]:', err);
    app.quit();
    process.exit(1);
  }
}

runSmokeTest();
