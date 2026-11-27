import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSettingsManager } from '../useSettingsManager';
import { useWorkspaceStore, DEFAULT_APP_SETTINGS } from '../../../stores/useWorkspaceStore';
import { useLibraryStore } from '../../../stores/useLibraryStore';
import { useLibraryViewerStore } from '../../../stores/useLibraryViewerStore';
import * as soundUtils from '../../../utils/sound';
import * as notifUtils from '../../../utils/notification';

vi.mock('../../../utils/sound', () => ({
  setSoundEnabled: vi.fn(),
  setSoundStyle: vi.fn(),
  setSoundVolume: vi.fn(),
  playChime: vi.fn(),
}));

vi.mock('../../../utils/notification', () => ({
  setNotificationEnabled: vi.fn(),
  setNotifyOnlyInBackground: vi.fn(),
  sendNativeNotification: vi.fn(),
  isNotifyOnlyInBackground: true,
}));

describe('useSettingsManager', () => {
  const mockAddToast = vi.fn();
  const mockOnBaseFolderChange = vi.fn();
  let originalElectronApi;
  let originalPywebview;
  let mockGetSettings;
  let mockSaveSettings;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    originalElectronApi = window.electronAPI;
    originalPywebview = window.pywebview;

    window.electronAPI = {
      setCloseAction: vi.fn(),
      selectFolder: vi.fn(),
    };

    mockGetSettings = vi.fn().mockResolvedValue({
      theme: 'Dark',
      accent: 'Azul Elétrico',
      baseFolder: 'C:/Manga/Raw',
      uiDensity: 'compact',
      soundFeedback: true,
      soundStyle: 'tech',
      soundVolume: 90,
      systemNotifications: true,
      notifyOnlyInBackground: false,
      showPagePills: true,
      showStatusDots: false,
      close_action: 'smart',
      autoResumePending: false,
      autoTurnPage: true,
      autoZoomLibrary: true,
      quickSymbols: true,
    });
    mockSaveSettings = vi.fn().mockResolvedValue({ success: true });

    window.pywebview = {
      api: {
        getSettings: mockGetSettings,
        saveSettings: mockSaveSettings,
      },
    };

    // Reset Zustand stores
    useWorkspaceStore.setState({
      appSettings: { ...DEFAULT_APP_SETTINGS },
      modifiedSettingsKeys: new Set(),
      quickSymbolsEnabled: false,
      settingsRevision: 0,
    });
    useLibraryStore.setState({
      autoResumePending: true,
      autoTurnPage: false,
    });
    useLibraryViewerStore.setState({
      autoZoomEnabled: false,
    });
  });

  afterEach(() => {
    window.electronAPI = originalElectronApi;
    window.pywebview = originalPywebview;
  });

  const renderSettingsHook = async () => {
    let hookResult;
    await act(async () => {
      hookResult = renderHook(() => useSettingsManager(mockAddToast, mockOnBaseFolderChange));
    });
    return hookResult;
  };

  it('hydrates initial settings from backend and keeps stores in sync', async () => {
    const { result } = await renderSettingsHook();

    expect(mockGetSettings).toHaveBeenCalledTimes(1);
    expect(result.current.theme).toBe('Dark');
    expect(result.current.accent).toBe('Azul Elétrico');
    expect(result.current.baseFolder).toBe('C:/Manga/Raw');
    expect(result.current.baseFolderInput).toBe('C:/Manga/Raw');
    expect(result.current.uiDensity).toBe('compact');
    expect(result.current.showStatusDots).toBe(false);
    expect(result.current.closeAction).toBe('smart');

    expect(soundUtils.setSoundEnabled).toHaveBeenCalledWith(true);
    expect(soundUtils.setSoundStyle).toHaveBeenCalledWith('tech');
    expect(soundUtils.setSoundVolume).toHaveBeenCalledWith(0.9);
    expect(notifUtils.setNotificationEnabled).toHaveBeenCalledWith(true);
    expect(notifUtils.setNotifyOnlyInBackground).toHaveBeenCalledWith(false);

    expect(useLibraryStore.getState().autoResumePending).toBe(false);
    expect(useLibraryStore.getState().autoTurnPage).toBe(true);
    expect(useLibraryViewerStore.getState().autoZoomEnabled).toBe(true);
    expect(useWorkspaceStore.getState().quickSymbolsEnabled).toBe(true);
  });

  it('updates theme atomically and saves to backend', async () => {
    const { result } = await renderSettingsHook();

    await act(async () => {
      result.current.setTheme('WarmPaper');
    });

    expect(result.current.theme).toBe('WarmPaper');
    expect(useWorkspaceStore.getState().appSettings.theme).toBe('WarmPaper');
    expect(mockSaveSettings).toHaveBeenCalledWith({ theme: 'WarmPaper' });
  });

  it('updates accent color and saves to backend', async () => {
    const { result } = await renderSettingsHook();

    await act(async () => {
      result.current.setAccent('Verde Esmeralda');
    });

    expect(result.current.accent).toBe('Verde Esmeralda');
    expect(useWorkspaceStore.getState().appSettings.accent).toBe('Verde Esmeralda');
    expect(mockSaveSettings).toHaveBeenCalledWith({ accent: 'Verde Esmeralda' });
  });

  it('updates UI density, motion and acrylic blur', async () => {
    const { result } = await renderSettingsHook();

    await act(async () => {
      result.current.setUiDensity('compact');
      result.current.setReduceMotion(true);
      result.current.setAcrylicBlur(false);
    });

    expect(result.current.uiDensity).toBe('compact');
    expect(result.current.reduceMotion).toBe(true);
    expect(result.current.acrylicBlur).toBe(false);

    const storeSettings = useWorkspaceStore.getState().appSettings;
    expect(storeSettings.uiDensity).toBe('compact');
    expect(storeSettings.reduceMotion).toBe(true);
    expect(storeSettings.acrylicBlur).toBe(false);
  });

  it('handles baseFolder lifecycle (input, apply, clear, browse)', async () => {
    const { result } = await renderSettingsHook();

    // Input typing
    act(() => {
      result.current.setBaseFolderInput('D:/Scanlation/ProjectA');
    });
    expect(result.current.baseFolderInput).toBe('D:/Scanlation/ProjectA');

    // Apply
    await act(async () => {
      result.current.applyBaseFolder();
    });
    expect(result.current.baseFolder).toBe('D:/Scanlation/ProjectA');
    expect(useWorkspaceStore.getState().appSettings.baseFolder).toBe('D:/Scanlation/ProjectA');
    expect(mockOnBaseFolderChange).toHaveBeenCalledWith('D:/Scanlation/ProjectA');
    expect(mockAddToast).toHaveBeenCalledWith('Pasta base do explorador atualizada!', 'success');

    // Clear
    await act(async () => {
      result.current.handleClearBaseFolder();
    });
    expect(result.current.baseFolder).toBe('');
    expect(result.current.baseFolderInput).toBe('');
    expect(mockOnBaseFolderChange).toHaveBeenCalledWith('');
    expect(mockAddToast).toHaveBeenCalledWith('Pasta base redefinida para o padrão', 'info');

    // Browse Folder
    window.electronAPI.selectFolder.mockResolvedValue({ success: true, path: 'E:/MangaVault' });
    await act(async () => {
      await result.current.handleBrowseFolder();
    });
    expect(result.current.baseFolder).toBe('E:/MangaVault');
    expect(mockOnBaseFolderChange).toHaveBeenCalledWith('E:/MangaVault');
  });

  it('updates audio and notification settings correctly', async () => {
    const { result } = await renderSettingsHook();

    await act(async () => {
      result.current.setSoundFeedback(false);
      result.current.setSoundStyleState('pop');
      result.current.setSoundVolumeState(50);
      result.current.setSystemNotifications(false);
      result.current.setNotifyOnlyInBackgroundState(true);
    });

    expect(soundUtils.setSoundEnabled).toHaveBeenCalledWith(false);
    expect(soundUtils.setSoundStyle).toHaveBeenCalledWith('pop');
    expect(soundUtils.setSoundVolume).toHaveBeenCalledWith(0.5);
    expect(notifUtils.setNotificationEnabled).toHaveBeenCalledWith(false);
    expect(notifUtils.setNotifyOnlyInBackground).toHaveBeenCalledWith(true);

    const storeSettings = useWorkspaceStore.getState().appSettings;
    expect(storeSettings.soundFeedback).toBe(false);
    expect(storeSettings.soundStyle).toBe('pop');
    expect(storeSettings.soundVolume).toBe(50);
    expect(storeSettings.systemNotifications).toBe(false);
    expect(storeSettings.notifyOnlyInBackground).toBe(true);
  });

  it('updates close action and notifies electronAPI', async () => {
    const { result } = await renderSettingsHook();

    await act(async () => {
      result.current.handleSetCloseAction('tray');
    });

    expect(result.current.closeAction).toBe('tray');
    expect(window.electronAPI.setCloseAction).toHaveBeenCalledWith('tray');
    expect(useWorkspaceStore.getState().appSettings.close_action).toBe('tray');
    expect(mockAddToast).toHaveBeenCalledWith(expect.stringContaining('Sempre minimizar para a bandeja'), 'info');
  });

  it('restores UI defaults when handleResetUiDefaults is called', async () => {
    const { result } = await renderSettingsHook();

    await act(async () => {
      result.current.setTheme('Light');
      result.current.setAccent('Vermelho Carmim');
    });

    expect(result.current.theme).toBe('Light');

    await act(async () => {
      result.current.handleResetUiDefaults();
    });

    expect(result.current.theme).toBe('Dark');
    expect(result.current.accent).toBe('Roxo (Padrão)');
    expect(result.current.uiDensity).toBe('comfortable');
    expect(soundUtils.setSoundEnabled).toHaveBeenCalledWith(true);
    expect(mockAddToast).toHaveBeenCalledWith('Preferências de interface restauradas com sucesso!', 'info');
  });

  it('handles external toggles for autoResume, autoTurnPage, autoZoomLibrary, and quickSymbols', async () => {
    const { result } = await renderSettingsHook();

    await act(async () => {
      result.current.handleToggleAutoResume(true);
      result.current.handleToggleAutoTurnPage(true);
      result.current.handleToggleAutoZoomLibrary(true);
      result.current.handleToggleQuickSymbols(true);
    });

    expect(useLibraryStore.getState().autoResumePending).toBe(true);
    expect(useLibraryStore.getState().autoTurnPage).toBe(true);
    expect(useLibraryViewerStore.getState().autoZoomEnabled).toBe(true);
    expect(useWorkspaceStore.getState().quickSymbolsEnabled).toBe(true);

    const storeSettings = useWorkspaceStore.getState().appSettings;
    expect(storeSettings.autoResumePending).toBe(true);
    expect(storeSettings.autoTurnPage).toBe(true);
    expect(storeSettings.autoZoomLibrary).toBe(true);
    expect(storeSettings.quickSymbols).toBe(true);
  });

  it('prevents late-resolving backend fetch from overwriting user changes made before fetch completes', async () => {
    let resolveLateFetch;
    mockGetSettings.mockImplementation(() => new Promise((resolve) => {
      resolveLateFetch = resolve;
    }));

    const { result } = renderHook(() => useSettingsManager(mockAddToast, mockOnBaseFolderChange));

    // User changes theme before backend responds
    await act(async () => {
      result.current.setTheme('WarmPaper');
    });
    expect(result.current.theme).toBe('WarmPaper');

    // Late backend response arrives with stale 'Dark'
    await act(async () => {
      resolveLateFetch({
        theme: 'Dark',
        accent: 'Rosa Sakura',
      });
    });

    // Theme must remain 'WarmPaper' (not overwritten!), but unedited 'accent' gets updated
    expect(result.current.theme).toBe('WarmPaper');
    expect(result.current.accent).toBe('Rosa Sakura');
  });
});
