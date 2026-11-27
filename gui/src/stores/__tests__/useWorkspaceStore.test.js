import { describe, it, expect, vi } from 'vitest';
import {
  useWorkspaceStore,
  DEFAULT_APP_SETTINGS,
  createNavigationSlice,
  createChapterSlice,
  createJobSlice,
  createSettingsSlice,
  createRevisionSlice,
} from '../useWorkspaceStore';

describe('useWorkspaceStore', () => {
  it('should initialize with default states', () => {
    const state = useWorkspaceStore.getState();
    expect(state.activeTab).toBe('processamento');
    expect(state.activeChapterPath).toBeNull();
    expect(state.pendingJumpPage).toBeNull();
    expect(state.workspaceRevision).toBe(0);
    expect(state.explorerRevision).toBe(0);
  });

  it('should update active tab with direct value and functional updater', () => {
    useWorkspaceStore.getState().setActiveTab('biblioteca');
    expect(useWorkspaceStore.getState().activeTab).toBe('biblioteca');

    useWorkspaceStore.getState().setActiveTab((prev) => (prev === 'biblioteca' ? 'processamento' : prev));
    expect(useWorkspaceStore.getState().activeTab).toBe('processamento');
  });

  it('should manage isDevUnlocked state correctly', () => {
    expect(useWorkspaceStore.getState().isDevUnlocked).toBe(false);
    useWorkspaceStore.getState().setIsDevUnlocked(true);
    expect(useWorkspaceStore.getState().isDevUnlocked).toBe(true);
    useWorkspaceStore.getState().setIsDevUnlocked(false);
    expect(useWorkspaceStore.getState().isDevUnlocked).toBe(false);
  });

  it('should handle pendingJumpPage lifecycle', () => {
    useWorkspaceStore.getState().requestJumpToPage('  page_005.png  ');
    expect(useWorkspaceStore.getState().pendingJumpPage).toBe('page_005.png');

    useWorkspaceStore.getState().clearPendingJumpPage();
    expect(useWorkspaceStore.getState().pendingJumpPage).toBeNull();
  });

  it('should navigate to studio page and update state atomically', () => {
    useWorkspaceStore.getState().navigateToStudioPage({
      folderPath: 'C:/Manga/Chapter_01',
      pageName: '003.jpg',
    });

    const state = useWorkspaceStore.getState();
    expect(state.activeTab).toBe('processamento');
    expect(state.activeChapterPath).toBe('C:/Manga/Chapter_01');
    expect(state.activeChapterName).toBe('Chapter_01');
    expect(state.pendingJumpPage).toBe('003.jpg');
    expect(state.chapterData).toEqual({});
  });

  it('should dispatch and clear data-cleared events correctly', () => {
    const paths = ['page1.png', 'page2.png'];
    const stages = ['ocr', 'translation'];

    useWorkspaceStore.getState().triggerDataCleared(paths, stages);
    const event = useWorkspaceStore.getState().clearedDataEvent;

    expect(event).not.toBeNull();
    expect(event.selectedPaths).toEqual(paths);
    expect(event.stages).toEqual(stages);
    expect(typeof event.timestamp).toBe('number');

    useWorkspaceStore.getState().clearDataClearedEvent();
    expect(useWorkspaceStore.getState().clearedDataEvent).toBeNull();
  });

  it('should bump workspace and explorer revisions incrementally', () => {
    expect(useWorkspaceStore.getState().workspaceRevision).toBe(0);
    useWorkspaceStore.getState().bumpWorkspaceRevision();
    expect(useWorkspaceStore.getState().workspaceRevision).toBe(1);

    expect(useWorkspaceStore.getState().explorerRevision).toBe(0);
    useWorkspaceStore.getState().bumpExplorerRevision();
    expect(useWorkspaceStore.getState().explorerRevision).toBe(1);
  });

  it('should synchronize active chapter and job badgeState to electronAPI.updateTrayStatus', () => {
    const trayUpdates = [];
    const prevElectronApi = window.electronAPI;
    const prevPywebview = window.pywebview;
    window.pywebview = { api: { cancelJob: vi.fn().mockResolvedValue({ success: true }) } };
    window.electronAPI = {
      setActiveWork: () => {},
      setProgressBar: () => {},
      updateTrayStatus: (status, isWorking, extra) => {
        trayUpdates.push({ status, isWorking, extra });
      },
    };

    try {
      useWorkspaceStore.getState().setActiveChapter('C:/Manga/Solo_Ch10', 'Solo_Ch10');
      expect(trayUpdates.length).toBeGreaterThan(0);
      const chapUpdate = trayUpdates[trayUpdates.length - 1];
      expect(chapUpdate.extra?.activeChapterName).toBe('Solo_Ch10');

      useWorkspaceStore.getState().addJob({
        id: 'tray_test_job',
        status: 'running',
        progress: 45,
        currentStepLabel: 'Traduzindo balões',
      });

      const workUpdate = trayUpdates[trayUpdates.length - 1];
      expect(workUpdate.isWorking).toBe(true);
      expect(workUpdate.extra?.badgeState).toBe('working');
      expect(workUpdate.extra?.progressPercent).toBe(45);

      useWorkspaceStore.getState().updateJob('tray_test_job', { status: 'completed', progress: 100 });
      const doneUpdate = trayUpdates[trayUpdates.length - 1];
      expect(doneUpdate.isWorking).toBe(false);
      expect(doneUpdate.extra?.badgeState).toBe('success');

      useWorkspaceStore.getState().removeJob('tray_test_job');
      // cancelJob test
      useWorkspaceStore.getState().addJob({
        id: 'tray_cancel_job',
        status: 'running',
        progress: 20,
        currentStepLabel: 'Iniciando OCR',
      });
      useWorkspaceStore.getState().cancelJob('tray_cancel_job');
      expect(useWorkspaceStore.getState().jobQueue.find(j => j.id === 'tray_cancel_job').status).toBe('cancelled');

      const cancelUpdate = trayUpdates[trayUpdates.length - 1];
      expect(cancelUpdate.isWorking).toBe(false);
      expect(cancelUpdate.extra?.badgeState).toBe('idle');
      expect(cancelUpdate.status).toBe('Cancelado pelo usuário');

      useWorkspaceStore.getState().removeJob('tray_cancel_job');
    } finally {
      window.electronAPI = prevElectronApi;
      window.pywebview = prevPywebview;
    }
  });

  it('should initialize appSettings with canonical defaults and update atomically', async () => {
    const saveMock = vi.fn().mockResolvedValue({ success: true });
    window.pywebview = {
      api: {
        saveSettings: saveMock,
      },
    };
    
    expect(DEFAULT_APP_SETTINGS.theme).toBe('Dark');
    expect(DEFAULT_APP_SETTINGS.accent).toBe('Roxo (Padrão)');
    expect(DEFAULT_APP_SETTINGS.uiDensity).toBe('comfortable');

    const initialRevision = useWorkspaceStore.getState().settingsRevision;

    // In-memory update without backend persistence
    useWorkspaceStore.getState().updateAppSettings({ theme: 'OLED', showPagePills: false });
    
    let state = useWorkspaceStore.getState();
    expect(state.appSettings.theme).toBe('OLED');
    expect(state.appSettings.showPagePills).toBe(false);
    expect(state.appSettings.accent).toBe('Roxo (Padrão)');
    expect(state.settingsRevision).toBe(initialRevision + 1);
    expect(saveMock).not.toHaveBeenCalled();

    // Check localStorage sync
    const stored = JSON.parse(localStorage.getItem('visionary:app_settings'));
    expect(stored.theme).toBe('OLED');
    expect(stored.showPagePills).toBe(false);

    // Update with backend persistence
    useWorkspaceStore.getState().updateAppSettings({ accent: 'Ciano Cyber' }, true);
    state = useWorkspaceStore.getState();
    expect(state.appSettings.accent).toBe('Ciano Cyber');
    expect(saveMock).toHaveBeenCalledWith({ accent: 'Ciano Cyber' });
  });

  it('should verify that all modular store slice creators are exported and callable independently', () => {
    const dummySet = vi.fn();
    const dummyGet = vi.fn();

    const navSlice = createNavigationSlice(dummySet);
    expect(navSlice.activeTab).toBe('processamento');
    expect(typeof navSlice.setActiveTab).toBe('function');
    expect(navSlice.isDevUnlocked).toBe(false);
    expect(typeof navSlice.setIsDevUnlocked).toBe('function');

    const chapSlice = createChapterSlice(dummySet);
    expect(typeof chapSlice.setActiveChapter).toBe('function');

    const jobSlice = createJobSlice(dummySet, dummyGet);
    expect(Array.isArray(jobSlice.jobQueue)).toBe(true);
    expect(typeof jobSlice.addJob).toBe('function');

    const settingsSlice = createSettingsSlice(dummySet);
    expect(settingsSlice.appSettings).toBeDefined();
    expect(typeof settingsSlice.updateAppSettings).toBe('function');

    const revSlice = createRevisionSlice(dummySet);
    expect(revSlice.workspaceRevision).toBe(0);
    expect(typeof revSlice.bumpWorkspaceRevision).toBe('function');
  });

  it('should sanitize deprecated tutorial tab into processamento at store level', () => {
    useWorkspaceStore.getState().setActiveTab('tutorial');
    expect(useWorkspaceStore.getState().activeTab).toBe('processamento');
  });
});
