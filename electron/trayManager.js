const { Tray, BrowserWindow, screen, ipcMain, powerSaveBlocker } = require('electron');
const path = require('path');
const { getJumpListIconPath } = require('./paths');
const {
  getBadgedTrayIcon,
  getTaskbarOverlayIcon,
  resolveBadgeState,
} = require('./trayIconRenderer');

let tray = null;
let flyoutWindow = null;
let flyoutIpcRegistered = false;
let powerSaveBlockerId = null;
let lastFlyoutBlurAt = 0;

const FLYOUT_WIDTH = 304;
const FLYOUT_HEIGHT = 408;

// Estado interno sincronizado da bandeja
const trayState = {
  statusText: 'Ocioso',
  isWorking: false,
  badgeState: 'idle', // 'idle' | 'working' | 'success' | 'error' | 'warning'
  activeChapterName: null,
  activeChapterPath: null,
  recentChapters: [], // [{ name, path }]
  closeAction: 'smart',
  isWindowVisible: true,
  progressPercent: null,
  runningCount: 0,
};

let savedCallbacks = {};

// Prevenção de suspensão do sistema (powerSaveBlocker):
// Quando o usuário minimiza o Visionary e dispara uma tradução em lote de centenas de páginas de mangá,
// o gerenciador de energia do Windows 11 pode suspender o processo em segundo plano (Modern Standby).
// O 'powerSaveBlocker' com 'prevent-app-suspension' garante que a CPU e GPU continuem processando
// os modelos neurais sem interrupção mesmo com a tampa do notebook fechada ou tela desligada.
function setPowerSaveState(isActive) {
  if (isActive && powerSaveBlockerId === null) {
    powerSaveBlockerId = powerSaveBlocker.start('prevent-app-suspension');
    console.log(`[PowerSave] Bloqueador de suspensão ativo durante processamento (ID: ${powerSaveBlockerId})`);
  } else if (!isActive && powerSaveBlockerId !== null) {
    if (powerSaveBlocker.isStarted(powerSaveBlockerId)) {
      powerSaveBlocker.stop(powerSaveBlockerId);
      console.log(`[PowerSave] Bloqueador de suspensão liberado (ID: ${powerSaveBlockerId})`);
    }
    powerSaveBlockerId = null;
  }
  refreshTrayTooltip();
}

/**
 * Atualiza o Tooltip rico multilinha do ícone na bandeja do Windows (sóbrio, sem excesso de emojis).
 */
function refreshTrayTooltip() {
  if (!tray) return;
  try {
    const prefix = trayState.isWorking
      ? '●'
      : trayState.badgeState === 'error'
        ? '!'
        : trayState.badgeState === 'success'
          ? '✓'
          : '○';

    const lines = [
      'Visionary Studio · PRO',
      `${prefix} Status: ${trayState.statusText || 'Ocioso'}`,
    ];

    if (trayState.activeChapterName) {
      lines.push(`Capítulo: ${trayState.activeChapterName}`);
    }

    if (powerSaveBlockerId !== null) {
      lines.push('Energia: Suspensão bloqueada (GPU Ativa)');
    }

    tray.setToolTip(lines.join('\n'));
  } catch (_) {}
}

/**
 * Sincroniza o estado atual com a janela Flyout customizada (se estiver carregada).
 */
function pushStateToFlyout() {
  if (!flyoutWindow || flyoutWindow.isDestroyed()) return;
  try {
    flyoutWindow.webContents.send('tray:flyout-state', { ...trayState });
  } catch (_) {}
}

/**
 * Registra o listener IPC para ações disparadas pelos botões do trayFlyout.html.
 */
function ensureFlyoutIpcRegistered() {
  if (flyoutIpcRegistered) return;
  flyoutIpcRegistered = true;

  ipcMain.on('tray:flyout-action', (_event, data) => {
    const { action, payload } = data || {};
    const {
      onOpenApp,
      onToggleApp,
      onNavigateTab,
      onOpenSymbols,
      onOpenRecentChapter,
      onCancelJob,
      onStopOllama,
      onOpenLogs,
      onSetCloseAction,
      onQuit,
    } = savedCallbacks;

    const hideFlyout = () => {
      if (flyoutWindow && !flyoutWindow.isDestroyed()) {
        flyoutWindow.hide();
      }
    };

    switch (action) {
      case 'toggle-app':
        hideFlyout();
        if (onToggleApp) onToggleApp();
        else onOpenApp?.();
        break;
      case 'navigate':
        hideFlyout();
        onNavigateTab?.(payload);
        break;
      case 'open-symbols':
        hideFlyout();
        onOpenSymbols?.();
        break;
      case 'open-recent':
        hideFlyout();
        onOpenRecentChapter?.(payload);
        break;
      case 'cancel-job':
        onCancelJob?.();
        break;
      case 'stop-ollama':
        onStopOllama?.();
        break;
      case 'open-logs':
        hideFlyout();
        onOpenLogs?.();
        break;
      case 'set-close-action':
        if (['smart', 'tray', 'quit'].includes(payload)) {
          trayState.closeAction = payload;
          onSetCloseAction?.(payload);
          pushStateToFlyout();
        }
        break;
      case 'quit':
        hideFlyout();
        onQuit?.();
        break;
      case 'close-flyout':
        hideFlyout();
        break;
      default:
        break;
    }
  });
}

/**
 * Cria (lazy) ou retorna a janela sem bordas do Custom Tray Flyout (Mix A + B).
 */
function ensureFlyoutWindow() {
  ensureFlyoutIpcRegistered();
  if (flyoutWindow && !flyoutWindow.isDestroyed()) {
    return flyoutWindow;
  }

  flyoutWindow = new BrowserWindow({
    width: FLYOUT_WIDTH,
    height: FLYOUT_HEIGHT,
    minWidth: FLYOUT_WIDTH,
    maxWidth: FLYOUT_WIDTH,
    minHeight: FLYOUT_HEIGHT,
    maxHeight: FLYOUT_HEIGHT,
    useContentSize: true,
    show: false,
    frame: false,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    backgroundColor: '#1e1e1e',
    hasShadow: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });

  const flyoutHtml = path.join(__dirname, 'trayFlyout.html');
  flyoutWindow.loadFile(flyoutHtml).catch((err) => {
    console.warn('[Tray] Erro ao carregar trayFlyout.html:', err);
  });

  flyoutWindow.webContents.on('did-finish-load', () => {
    pushStateToFlyout();
  });

  // Fecha automaticamente ao clicar fora (comportamento nativo Windows 11 Flyout)
  flyoutWindow.on('blur', () => {
    if (flyoutWindow && !flyoutWindow.isDestroyed() && flyoutWindow.isVisible()) {
      lastFlyoutBlurAt = Date.now();
      flyoutWindow.hide();
    }
  });

  flyoutWindow.on('closed', () => {
    flyoutWindow = null;
  });

  return flyoutWindow;
}

/**
 * Calcula a posição delimitada (clamped) do Tray Flyout dentro do monitor ativo.
 * Trata displays secundários com coordenadas negativas, taskbars superiores e DPIs customizados.
 */
function calculateFlyoutBounds(trayBounds, cursorPt, workArea, flyoutWidth = FLYOUT_WIDTH, flyoutHeight = FLYOUT_HEIGHT) {
  const hasTrayBounds = Boolean(
    trayBounds &&
    typeof trayBounds.x === 'number' &&
    typeof trayBounds.y === 'number' &&
    typeof trayBounds.width === 'number' &&
    typeof trayBounds.height === 'number' &&
    trayBounds.width > 0 &&
    trayBounds.height > 0
  );

  let x = Math.round(
    (hasTrayBounds
      ? trayBounds.x + trayBounds.width / 2
      : (cursorPt?.x ?? 0)) - flyoutWidth / 2
  );
  let y = Math.round(
    (hasTrayBounds ? trayBounds.y : (cursorPt?.y ?? 0)) - flyoutHeight - 8
  );

  // Se a barra de tarefas estiver no topo da tela (ou próxima do topo da área de trabalho)
  if (hasTrayBounds && trayBounds.y < (workArea?.y ?? 0) + 60) {
    y = Math.round(trayBounds.y + trayBounds.height + 8);
  }

  // Clamp estrito dentro da área útil do monitor (workArea) com margem de 8px
  const areaX = workArea?.x ?? 0;
  const areaY = workArea?.y ?? 0;
  const areaWidth = workArea?.width ?? 1920;
  const areaHeight = workArea?.height ?? 1080;

  const minX = areaX + 8;
  const maxX = areaX + areaWidth - flyoutWidth - 8;
  const minY = areaY + 8;
  const maxY = areaY + areaHeight - flyoutHeight - 8;

  x = Math.max(minX, Math.min(maxX, x));
  y = Math.max(minY, Math.min(maxY, y));

  return { x, y, width: flyoutWidth, height: flyoutHeight };
}

/**
 * Posiciona e abre (ou fecha) o Custom Tray Flyout ancorado próximo ao ícone da bandeja.
 */
function toggleTrayFlyout(trayBounds) {
  const win = ensureFlyoutWindow();
  if (!win || win.isDestroyed()) return;

  if (win.isVisible()) {
    win.hide();
    return;
  }

  // Se o clique no próprio ícone da bandeja acabou de causar 'blur' (< 180ms atrás),
  // respeita a intenção de fechar no toggle em vez de reabrir imediatamente.
  if (Date.now() - lastFlyoutBlurAt < 180) {
    return;
  }

  try {
    const cursorPt = screen.getCursorScreenPoint();
    const hasTrayBounds = Boolean(
      trayBounds &&
      typeof trayBounds.x === 'number' &&
      typeof trayBounds.y === 'number' &&
      typeof trayBounds.width === 'number' &&
      typeof trayBounds.height === 'number' &&
      trayBounds.width > 0 &&
      trayBounds.height > 0
    );

    const anchorPoint = hasTrayBounds
      ? { x: trayBounds.x + trayBounds.width / 2, y: trayBounds.y + trayBounds.height / 2 }
      : cursorPt;

    const display = screen.getDisplayNearestPoint(anchorPoint);
    const bounds = calculateFlyoutBounds(trayBounds, cursorPt, display.workArea, FLYOUT_WIDTH, FLYOUT_HEIGHT);

    // No Windows com DPI Scaling != 100%, win.setPosition(x, y) sofre de um bug clássico do Electron
    // onde o tamanho físico é re-dividido pelo scaleFactor a cada chamada, encolhendo a janela.
    // Usar setBounds com width e height explícitos trava as dimensões em DIPs.
    win.setBounds(bounds, false);
    pushStateToFlyout();
    win.show();
    win.focus();
  } catch (err) {
    console.warn('[Tray] Erro ao posicionar Tray Flyout:', err);
  }
}

/**
 * Atualiza o estado da bandeja, ícone com badge, tooltip e sincroniza o Flyout customizado.
 */
function updateTrayMenu(statusOrPayload = 'Ocioso', isWorking = false, callbacks = null) {
  if (callbacks && typeof callbacks === 'object') {
    savedCallbacks = { ...savedCallbacks, ...callbacks };
  }

  if (statusOrPayload && typeof statusOrPayload === 'object') {
    if (statusOrPayload.status !== undefined) trayState.statusText = String(statusOrPayload.status || 'Ocioso');
    if (statusOrPayload.isWorking !== undefined) trayState.isWorking = Boolean(statusOrPayload.isWorking);
    if (statusOrPayload.activeChapterName !== undefined) trayState.activeChapterName = statusOrPayload.activeChapterName || null;
    if (statusOrPayload.activeChapterPath !== undefined) trayState.activeChapterPath = statusOrPayload.activeChapterPath || null;
    if (Array.isArray(statusOrPayload.recentChapters)) {
      trayState.recentChapters = statusOrPayload.recentChapters.slice(0, 6);
    }
    if (statusOrPayload.closeAction && ['smart', 'tray', 'quit'].includes(statusOrPayload.closeAction)) {
      trayState.closeAction = statusOrPayload.closeAction;
    }
    if (typeof statusOrPayload.isWindowVisible === 'boolean') {
      trayState.isWindowVisible = statusOrPayload.isWindowVisible;
    }
    if (statusOrPayload.progressPercent !== undefined) {
      trayState.progressPercent = statusOrPayload.progressPercent;
    }
    if (statusOrPayload.runningCount !== undefined) {
      trayState.runningCount = statusOrPayload.runningCount;
    }
    trayState.badgeState = resolveBadgeState(
      trayState.statusText,
      trayState.isWorking,
      statusOrPayload.badgeState
    );
  } else {
    trayState.statusText = String(statusOrPayload || 'Ocioso');
    trayState.isWorking = Boolean(isWorking);
    trayState.badgeState = resolveBadgeState(trayState.statusText, trayState.isWorking, null);
  }

  if (!tray) return;

  // 1. Atualiza o ícone com badge dinâmico
  try {
    const iconImg = getBadgedTrayIcon(trayState.badgeState);
    if (iconImg) {
      tray.setImage(iconImg);
    }
  } catch (_) {}

  // 2. Atualiza o Tooltip multilinha
  refreshTrayTooltip();

  // 3. Sincroniza em tempo real com a janela Flyout (Mix A + B)
  pushStateToFlyout();
}

/**
 * Registra um capítulo na lista de recentes da bandeja (sem duplicatas, máx 6).
 */
function addRecentChapterToTray(folderPath, folderName) {
  if (!folderPath || typeof folderPath !== 'string') return;
  const cleanPath = path.normalize(folderPath);
  const name = folderName || path.basename(cleanPath);

  const filtered = trayState.recentChapters.filter(
    (item) => path.normalize(item.path).toLowerCase() !== cleanPath.toLowerCase()
  );
  trayState.recentChapters = [{ name, path: cleanPath }, ...filtered].slice(0, 6);
  trayState.activeChapterName = name;
  trayState.activeChapterPath = cleanPath;

  updateTrayMenu(trayState);
}

function createTray(callbacks = {}) {
  if (tray) return tray;
  savedCallbacks = { ...savedCallbacks, ...callbacks };

  const iconImg = getBadgedTrayIcon('idle');
  if (!iconImg) return null;

  try {
    tray = new Tray(iconImg);
    refreshTrayTooltip();
    updateTrayMenu('Ocioso', false, callbacks);

    // Flyout HTML (BrowserWindow) é instanciado sob demanda no primeiro clique direito,
    // evitando consumo extra de memória/processo Chromium durante a inicialização.

    // Clique esquerdo simples: alterna (mostrar/ocultar) a janela principal
    tray.on('click', () => {
      if (flyoutWindow && !flyoutWindow.isDestroyed() && flyoutWindow.isVisible()) {
        flyoutWindow.hide();
      }
      if (savedCallbacks.onToggleApp) {
        savedCallbacks.onToggleApp();
      } else {
        savedCallbacks.onOpenApp?.();
      }
    });

    // Clique direito: abre o Custom Tray Flyout (Mix A + B) ancorado na bandeja
    tray.on('right-click', (_event, bounds) => {
      toggleTrayFlyout(bounds);
    });

    // Duplo clique: garante abertura e foco na janela principal
    tray.on('double-click', () => {
      savedCallbacks.onOpenApp?.();
    });
  } catch (err) {
    console.warn('[Tray] Erro ao instanciar System Tray:', err);
  }
  return tray;
}

function destroyTray() {
  if (flyoutWindow && !flyoutWindow.isDestroyed()) {
    try { flyoutWindow.destroy(); } catch (_) {}
    flyoutWindow = null;
  }
  if (tray) {
    try { tray.destroy(); } catch (_) {}
    tray = null;
  }
}

let pendingInitialAction = null;

function extractActionFromArgs(args) {
  if (!args) return null;
  const list = Array.isArray(args) ? args : [String(args)];
  for (const item of list) {
    if (typeof item !== 'string') continue;
    const match = item.match(/--action=["']?([a-zA-Z0-9_-]+)["']?/i);
    if (match) {
      return match[1].toLowerCase().trim();
    }
  }
  return null;
}

function setupJumpList(app) {
  if (process.platform !== 'win32') return;
  try {
    const targetProgram = process.execPath;
    const rootArg = !app.isPackaged ? `"${path.resolve(__dirname, '..')}"` : '';

    app.setUserTasks([
      {
        program: targetProgram,
        arguments: `${rootArg} --action=processamento`.trim(),
        iconPath: getJumpListIconPath('task_studio.ico'),
        iconIndex: 0,
        title: 'Estúdio',
        description: 'Abrir o Studio de edição e tradução visual',
      },
      {
        program: targetProgram,
        arguments: `${rootArg} --action=biblioteca`.trim(),
        iconPath: getJumpListIconPath('task_library.ico'),
        iconIndex: 0,
        title: 'Biblioteca',
        description: 'Navegar por volumes, capítulos e roteiros',
      },
      {
        program: targetProgram,
        arguments: `${rootArg} --action=lightbox`.trim(),
        iconPath: getJumpListIconPath('task_lightbox.ico'),
        iconIndex: 0,
        title: 'Lightbox',
        description: 'Mesa de preparação e montagem de páginas',
      },
      {
        program: targetProgram,
        arguments: `${rootArg} --action=modulos`.trim(),
        iconPath: getJumpListIconPath('task_modules.ico'),
        iconIndex: 0,
        title: 'Módulos',
        description: 'Gerenciar Ollama e modelos de visão',
      },
      {
        program: targetProgram,
        arguments: `${rootArg} --action=configuracoes`.trim(),
        iconPath: getJumpListIconPath('task_settings.ico'),
        iconIndex: 0,
        title: 'Configurações',
        description: 'Ajustar preferências do estúdio e do sistema',
      },
    ]);
  } catch (err) {
    console.warn('[JumpList] Erro ao registrar tarefas do usuário:', err);
  }
}

function handleActionArg(args, mainWindow) {
  if (!args) return;
  const tab = extractActionFromArgs(args);
  if (!tab) return;

  const validTabs = ['processamento', 'biblioteca', 'lightbox', 'modulos', 'configuracoes', 'testes', 'queue', 'dev'];
  if (!validTabs.includes(tab)) return;

  pendingInitialAction = tab;

  if (!mainWindow || mainWindow.isDestroyed()) return;

  const executeNavigation = () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('app:navigate-tab', tab);
    }
  };

  if (mainWindow.webContents.isLoading()) {
    mainWindow.webContents.once('did-finish-load', () => {
      setTimeout(executeNavigation, 120);
    });
  } else {
    executeNavigation();
  }
}

module.exports = {
  createTray,
  destroyTray,
  updateTrayMenu,
  addRecentChapterToTray,
  toggleTrayFlyout,
  calculateFlyoutBounds,
  getBadgedTrayIcon,
  getTaskbarOverlayIcon,
  getTrayState: () => ({ ...trayState }),
  setPowerSaveState,
  setupJumpList,
  handleActionArg,
  getPendingInitialAction: () => pendingInitialAction,
  clearPendingInitialAction: () => { pendingInitialAction = null; },
  getTray: () => tray,
};
