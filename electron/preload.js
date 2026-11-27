const { contextBridge, ipcRenderer, webFrame } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window:minimize'),
  toggleMaximize: () => ipcRenderer.invoke('window:toggle-maximize'),
  isMaximized: () => ipcRenderer.invoke('window:is-maximized'),
  close: () => ipcRenderer.send('window:close'),
  focusWindow: () => ipcRenderer.send('window:focus'),
  copyToClipboard: (text) => ipcRenderer.invoke('clipboard:write-text', text),
  showNotification: (data) => ipcRenderer.invoke('notification:show', data),
  onNotificationClicked: (callback) => {
    const subscription = (_event, data) => callback(data);
    ipcRenderer.on('notification:clicked', subscription);
    return () => ipcRenderer.removeListener('notification:clicked', subscription);
  },
  selectFolder: (defaultPath) => ipcRenderer.invoke('dialog:select-folder', defaultPath),
  openPath: (fullPath) => ipcRenderer.invoke('shell:open-path', fullPath),
  showItemInFolder: (fullPath) => ipcRenderer.invoke('shell:show-item-in-folder', fullPath),
  startAutoSetup: () => ipcRenderer.invoke('bootstrap:start-auto-setup'),
  selectEngineArchive: () => ipcRenderer.invoke('bootstrap:select-engine-archive'),
  setBootstrapErrorMode: (isError) => ipcRenderer.send('bootstrap:set-error-mode', Boolean(isError)),
  checkPython: () => ipcRenderer.invoke('bootstrap:check-python'),
  openPythonSite: () => ipcRenderer.invoke('bootstrap:open-python-site'),
  openExternal: (url) => ipcRenderer.invoke('system:open-external', url),
  factoryReset: () => ipcRenderer.invoke('bootstrap:factory-reset'),
  openBootstrapLog: () => ipcRenderer.invoke('bootstrap:open-log'),
  onBootstrapProgress: (callback) => {
    const subscription = (_event, data) => callback(data);
    ipcRenderer.on('bootstrap:progress', subscription);
    return () => ipcRenderer.removeListener('bootstrap:progress', subscription);
  },
  onSplashMode: (callback) => {
    const subscription = (_event, data) => callback(data);
    ipcRenderer.on('bootstrap:splash-mode', subscription);
    return () => ipcRenderer.removeListener('bootstrap:splash-mode', subscription);
  },
  onBootstrapDone: (callback) => {
    const subscription = () => callback();
    ipcRenderer.on('bootstrap:done', subscription);
    return () => ipcRenderer.removeListener('bootstrap:done', subscription);
  },
  onBootstrapError: (callback) => {
    const subscription = (_event, data) => callback(data);
    ipcRenderer.on('bootstrap:error', subscription);
    return () => ipcRenderer.removeListener('bootstrap:error', subscription);
  },
  setProgressBar: (value, options) => ipcRenderer.send('window:set-progress-bar', { value, options }),
  setActiveWork: (hasActiveWork) => ipcRenderer.send('power:set-active-work', hasActiveWork),
  updateTrayStatus: (statusOrPayload, isWorking, extra = {}) => {
    if (statusOrPayload && typeof statusOrPayload === 'object') {
      ipcRenderer.send('tray:update-status', statusOrPayload);
    } else {
      ipcRenderer.send('tray:update-status', { status: statusOrPayload, isWorking, ...extra });
    }
  },
  addRecentChapter: (folderPath, folderName) => ipcRenderer.invoke('jumplist:add-recent', folderPath, folderName),
  onSessionReset: (callback) => {
    const subscription = () => callback();
    ipcRenderer.on('app:session-reset', subscription);
    return () => ipcRenderer.removeListener('app:session-reset', subscription);
  },
  onNavigateTab: (callback) => {
    const subscription = (_event, tab) => callback(tab);
    ipcRenderer.on('app:navigate-tab', subscription);
    return () => ipcRenderer.removeListener('app:navigate-tab', subscription);
  },
  onCancelJobFromTray: (callback) => {
    const subscription = () => callback();
    ipcRenderer.on('tray:cancel-job', subscription);
    return () => ipcRenderer.removeListener('tray:cancel-job', subscription);
  },
  onOpenSymbolsFromTray: (callback) => {
    const subscription = () => callback();
    ipcRenderer.on('tray:open-symbols', subscription);
    return () => ipcRenderer.removeListener('tray:open-symbols', subscription);
  },
  onOpenRecentChapterFromTray: (callback) => {
    const subscription = (_event, chapter) => callback(chapter);
    ipcRenderer.on('tray:open-recent-chapter', subscription);
    return () => ipcRenderer.removeListener('tray:open-recent-chapter', subscription);
  },
  onCloseActionChangedFromTray: (callback) => {
    const subscription = (_event, action) => callback(action);
    ipcRenderer.on('tray:close-action-changed', subscription);
    return () => ipcRenderer.removeListener('tray:close-action-changed', subscription);
  },
  onOllamaStoppedFromTray: (callback) => {
    const subscription = () => callback();
    ipcRenderer.on('tray:ollama-stopped', subscription);
    return () => ipcRenderer.removeListener('tray:ollama-stopped', subscription);
  },
  sendTrayFlyoutAction: (action, payload) => ipcRenderer.send('tray:flyout-action', { action, payload }),
  onTrayFlyoutState: (callback) => {
    const subscription = (_event, state) => callback(state);
    ipcRenderer.on('tray:flyout-state', subscription);
    return () => ipcRenderer.removeListener('tray:flyout-state', subscription);
  },
  setZoomFactor: (factor) => {
    if (typeof factor === 'number' && factor >= 0.5 && factor <= 2.5) {
      webFrame.setZoomFactor(factor);
    }
  },
  getZoomFactor: () => webFrame.getZoomFactor(),
  setCloseAction: (action) => ipcRenderer.send('window:set-close-action', action),
  notifyAppReady: () => ipcRenderer.send('app:ready'),
  sendBootstrapProgress: (payload) => ipcRenderer.send('bootstrap:progress', payload),
  getServerUrl: () => ipcRenderer.invoke('system:get-server-url'),
  getServerPort: () => ipcRenderer.invoke('system:get-server-port'),
  getInitialAction: () => ipcRenderer.invoke('system:get-initial-action'),
  restartSidecar: () => ipcRenderer.invoke('sidecar:restart'),
  onSidecarStatus: (callback) => {
    const subscription = (_event, status) => callback(status);
    ipcRenderer.on('sidecar:status', subscription);
    return () => ipcRenderer.removeListener('sidecar:status', subscription);
  },
  checkForUpdates: () => ipcRenderer.invoke('updater:check'),
  downloadUpdate: () => ipcRenderer.invoke('updater:download'),
  installUpdate: () => ipcRenderer.invoke('updater:install'),
  getUpdaterStatus: () => ipcRenderer.invoke('updater:get-status'),
  onUpdaterStatus: (callback) => {
    const subscription = (_event, status) => callback(status);
    ipcRenderer.on('updater:status', subscription);
    return () => ipcRenderer.removeListener('updater:status', subscription);
  },
  isElectron: true,
});
