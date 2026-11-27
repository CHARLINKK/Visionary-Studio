import { useState, useEffect, useCallback } from 'react';
import { setSoundEnabled, setSoundStyle, setSoundVolume } from '../../utils/sound';
import { setNotificationEnabled, setNotifyOnlyInBackground } from '../../utils/notification';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';
import { useLibraryStore } from '../../stores/useLibraryStore';
import { useLibraryViewerStore } from '../../stores/useLibraryViewerStore';
import { clientApi } from '../../api/bridge';

export function useSettingsManager(addToast, onBaseFolderChange) {
  // Global Canonical State (Zustand - Single Source of Truth)
  const appSettings = useWorkspaceStore((s) => s.appSettings);
  const updateAppSettings = useWorkspaceStore((s) => s.updateAppSettings);
  const quickSymbols = useWorkspaceStore((s) => s.quickSymbolsEnabled);
  const autoResumePending = useLibraryStore((s) => s.autoResumePending);
  const autoTurnPage = useLibraryStore((s) => s.autoTurnPage);
  const autoZoomLibrary = useLibraryViewerStore((s) => s.autoZoomEnabled);

  // Uncommitted folder input in UI
  const [baseFolderInput, setBaseFolderInput] = useState(appSettings?.baseFolder || '');

  // Derived settings
  const theme = (appSettings?.theme && appSettings.theme !== 'System') ? appSettings.theme : 'Dark';
  const accent = appSettings?.accent || 'Roxo (Padrão)';
  const uiDensity = appSettings?.uiDensity || 'comfortable';
  const reduceMotion = Boolean(appSettings?.reduceMotion);
  const acrylicBlur = appSettings?.acrylicBlur !== false;
  const fontFamily = appSettings?.fontFamily || 'modern';
  const uiScale = appSettings?.uiScale || '100%';
  const baseFolder = appSettings?.baseFolder || '';
  const showPagePills = appSettings?.showPagePills !== false;
  const showStatusDots = appSettings?.showStatusDots !== false;
  const systemNotifications = appSettings?.systemNotifications !== false;
  const notifyOnlyInBackgroundState = appSettings?.notifyOnlyInBackground !== false;
  const soundFeedback = appSettings?.soundFeedback !== false;
  const soundStyle = appSettings?.soundStyle || 'harmonic';
  const soundVolume = typeof appSettings?.soundVolume === 'number' ? appSettings.soundVolume : 80;
  const closeAction = appSettings?.close_action || 'smart';

  // Sincroniza o campo de input quando a pasta base mudar externamente
  useEffect(() => {
    if (appSettings?.baseFolder !== undefined) {
      setBaseFolderInput(appSettings.baseFolder || '');
    }
  }, [appSettings?.baseFolder]);

  // Sincronização inicial com o backend
  useEffect(() => {
    clientApi.getSettings().then((settings) => {
      if (!settings) return;
      updateAppSettings(settings, false);

      const notifOn = settings.systemNotifications !== false;
      setNotificationEnabled(notifOn);
      const bgOnly = settings.notifyOnlyInBackground !== false;
      setNotifyOnlyInBackground(bgOnly);

      const soundOn = settings.soundFeedback !== false;
      setSoundEnabled(soundOn);
      const sStyle = settings.soundStyle || 'harmonic';
      setSoundStyle(sStyle);
      const sVol = typeof settings.soundVolume === 'number' ? settings.soundVolume : 80;
      setSoundVolume(sVol / 100);

      const cAction = settings.close_action || 'smart';
      window.electronAPI?.setCloseAction?.(cAction);

      if (typeof settings.autoResumePending === 'boolean') {
        useLibraryStore.getState().setAutoResumePending(settings.autoResumePending);
      }
      if (typeof settings.autoTurnPage === 'boolean') {
        useLibraryStore.getState().setAutoTurnPage(settings.autoTurnPage);
      }
      if (typeof settings.autoZoomLibrary === 'boolean') {
        useLibraryViewerStore.getState().setAutoZoomEnabled(settings.autoZoomLibrary);
      }
      if (typeof settings.quickSymbols === 'boolean') {
        useWorkspaceStore.getState().setQuickSymbolsEnabled(settings.quickSymbols);
      }
    }).catch((err) => {
      console.error('Erro ao carregar configurações:', err);
    });
  }, [updateAppSettings]);

  // Setters atômicos e reativos
  const setTheme = useCallback((val) => {
    const next = (val && val !== 'System') ? val : 'Dark';
    updateAppSettings({ theme: next }, true);
  }, [updateAppSettings]);

  const setAccent = useCallback((val) => {
    updateAppSettings({ accent: val }, true);
  }, [updateAppSettings]);

  const setUiDensity = useCallback((val) => {
    updateAppSettings({ uiDensity: val }, true);
  }, [updateAppSettings]);

  const setReduceMotion = useCallback((val) => {
    updateAppSettings({ reduceMotion: Boolean(val) }, true);
  }, [updateAppSettings]);

  const setAcrylicBlur = useCallback((val) => {
    updateAppSettings({ acrylicBlur: Boolean(val) }, true);
  }, [updateAppSettings]);

  const setFontFamily = useCallback((val) => {
    updateAppSettings({ fontFamily: val }, true);
  }, [updateAppSettings]);

  const setUiScale = useCallback((val) => {
    updateAppSettings({ uiScale: val }, true);
  }, [updateAppSettings]);

  const setShowPagePills = useCallback((val) => {
    updateAppSettings({ showPagePills: Boolean(val) }, true);
  }, [updateAppSettings]);

  const setShowStatusDots = useCallback((val) => {
    updateAppSettings({ showStatusDots: Boolean(val) }, true);
  }, [updateAppSettings]);

  const setSoundFeedback = useCallback((val) => {
    const next = Boolean(val);
    setSoundEnabled(next);
    updateAppSettings({ soundFeedback: next }, true);
  }, [updateAppSettings]);

  const setSoundStyleState = useCallback((val) => {
    setSoundStyle(val);
    updateAppSettings({ soundStyle: val }, true);
  }, [updateAppSettings]);

  const setSoundVolumeState = useCallback((val) => {
    const num = typeof val === 'number' ? val : Number(val);
    setSoundVolume(num / 100);
    updateAppSettings({ soundVolume: num }, true);
  }, [updateAppSettings]);

  const setSystemNotifications = useCallback((val) => {
    const next = Boolean(val);
    setNotificationEnabled(next);
    updateAppSettings({ systemNotifications: next }, true);
  }, [updateAppSettings]);

  const setNotifyOnlyInBackgroundState = useCallback((val) => {
    const next = Boolean(val);
    setNotifyOnlyInBackground(next);
    updateAppSettings({ notifyOnlyInBackground: next }, true);
  }, [updateAppSettings]);

  const handleSetCloseAction = useCallback((val) => {
    window.electronAPI?.setCloseAction?.(val);
    updateAppSettings({ close_action: val }, true);
    if (addToast) {
      const labels = {
        smart: 'Ao fechar (X): Minimizar para a bandeja se houver tarefa, senão encerrar',
        tray: 'Ao fechar (X): Sempre minimizar para a bandeja do sistema (Tray)',
        quit: 'Ao fechar (X): Sempre encerrar a aplicação completamente'
      };
      addToast(labels[val] || 'Preferência atualizada!', 'info');
    }
  }, [updateAppSettings, addToast]);

  const handleToggleAutoResume = useCallback((val) => {
    const next = Boolean(val);
    useLibraryStore.getState().setAutoResumePending(next);
    updateAppSettings({ autoResumePending: next }, true);
    if (addToast) addToast(next ? 'Auto-Retomar ativado: abre direto na primeira página pendente' : 'Auto-Retomar desativado: abre sempre na Pág. 01', 'info');
  }, [updateAppSettings, addToast]);

  const handleToggleAutoTurnPage = useCallback((val) => {
    const next = Boolean(val);
    useLibraryStore.getState().setAutoTurnPage(next);
    updateAppSettings({ autoTurnPage: next }, true);
    if (addToast) addToast(next ? 'Auto-Avanço de Página ativado' : 'Auto-Avanço de Página desativado', 'info');
  }, [updateAppSettings, addToast]);

  const handleToggleAutoZoomLibrary = useCallback((val) => {
    const next = Boolean(val);
    useLibraryViewerStore.getState().setAutoZoomEnabled(next);
    updateAppSettings({ autoZoomLibrary: next }, true);
    if (addToast) addToast(next ? 'Auto-Zoom ativado na Biblioteca' : 'Auto-Zoom desativado na Biblioteca', 'info');
  }, [updateAppSettings, addToast]);

  const handleToggleQuickSymbols = useCallback((val) => {
    const next = Boolean(val);
    useWorkspaceStore.getState().setQuickSymbolsEnabled(next);
    updateAppSettings({ quickSymbols: next }, true);
    if (addToast) addToast(next ? 'Teclado Virtual de Símbolos ativado' : 'Teclado Virtual de Símbolos desativado', 'info');
  }, [updateAppSettings, addToast]);

  const applyBaseFolder = useCallback((explicitVal) => {
    const val = (explicitVal !== undefined ? explicitVal : baseFolderInput).trim();
    if (!val) return;
    setBaseFolderInput(val);
    updateAppSettings({ baseFolder: val }, true);
    if (onBaseFolderChange) onBaseFolderChange(val);
    if (addToast) addToast('Pasta base do explorador atualizada!', 'success');
  }, [baseFolderInput, updateAppSettings, onBaseFolderChange, addToast]);

  const handleBrowseFolder = useCallback(async () => {
    const api = window.electronAPI || clientApi;
    if (api?.selectFolder) {
      try {
        const res = await api.selectFolder(baseFolderInput || baseFolder || '');
        if (res && res.success && res.path) applyBaseFolder(res.path);
      } catch (e) { console.error('Erro ao abrir seletor:', e); }
    }
  }, [baseFolderInput, baseFolder, applyBaseFolder]);

  const handleClearBaseFolder = useCallback(() => {
    setBaseFolderInput('');
    updateAppSettings({ baseFolder: '' }, true);
    if (onBaseFolderChange) onBaseFolderChange('');
    if (addToast) addToast('Pasta base redefinida para o padrão', 'info');
  }, [updateAppSettings, onBaseFolderChange, addToast]);

  const handleResetUiDefaults = useCallback(() => {
    const resetPayload = {
      theme: 'Dark',
      accent: 'Roxo (Padrão)',
      uiDensity: 'comfortable',
      soundFeedback: true,
      systemNotifications: true,
      reduceMotion: false,
      acrylicBlur: true,
      fontFamily: 'modern',
      uiScale: '100%',
      showPagePills: true,
      showStatusDots: true,
      soundStyle: 'harmonic',
      soundVolume: 80,
      notifyOnlyInBackground: true,
    };
    setSoundEnabled(true);
    setSoundStyle('harmonic');
    setSoundVolume(0.8);
    setNotificationEnabled(true);
    setNotifyOnlyInBackground(true);

    updateAppSettings(resetPayload, true);
    if (addToast) addToast('Preferências de interface restauradas com sucesso!', 'info');
  }, [updateAppSettings, addToast]);

  return {
    theme, setTheme, accent, setAccent, uiDensity, setUiDensity,
    reduceMotion, setReduceMotion, acrylicBlur, setAcrylicBlur,
    fontFamily, setFontFamily, uiScale, setUiScale,
    baseFolder, baseFolderInput, setBaseFolderInput,
    showPagePills, setShowPagePills, showStatusDots, setShowStatusDots,
    autoResumePending, handleToggleAutoResume,
    autoTurnPage, handleToggleAutoTurnPage,
    autoZoomLibrary, handleToggleAutoZoomLibrary,
    quickSymbols, handleToggleQuickSymbols,
    systemNotifications, setSystemNotifications,
    notifyOnlyInBackgroundState, setNotifyOnlyInBackgroundState,
    soundFeedback, setSoundFeedback,
    soundStyle, setSoundStyleState, soundVolume, setSoundVolumeState,
    closeAction, handleSetCloseAction,
    applyBaseFolder, handleBrowseFolder, handleClearBaseFolder, handleResetUiDefaults
  };
}
