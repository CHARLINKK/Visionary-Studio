import { clientApi } from '../../api/bridge';

/**
 * Configurações padrão canônicas do Visionary Studio (espelho de src/config.py).
 */
export const DEFAULT_APP_SETTINGS = {
  theme: 'Dark',
  accent: 'Roxo (Padrão)',
  sidebarWidth: 250,
  rememberZoom: false,
  last_opened_folder: '',
  baseFolder: '',
  pipeline_steps: { layout: true, ocr: true, translate: true },
  translation_tone: 'neutral',
  selected_models: {},
  systemNotifications: true,
  notifyOnlyInBackground: true,
  debugPanelMaps: false,
  autoUpdate: true,
  enableVLM: true,
  uiDensity: 'comfortable',
  soundFeedback: true,
  soundStyle: 'harmonic',
  soundVolume: 80,
  reduceMotion: false,
  acrylicBlur: true,
  fontFamily: 'modern',
  uiScale: '100%',
  showPagePills: true,
  showStatusDots: true,
  autoResumePending: true,
  autoTurnPage: false,
  autoZoomLibrary: false,
  quickSymbols: false,
  first_run_completed: false,
  close_action: 'smart',
};

/**
 * Slice 4: Configurações do Sistema e Sincronização
 */
export const createSettingsSlice = (set) => ({
  settingsRevision: 0,
  modifiedSettingsKeys: new Set(),
  appSettings: (() => {
    try {
      const cached = localStorage.getItem('visionary:app_settings');
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed && typeof parsed === 'object') {
          return { ...DEFAULT_APP_SETTINGS, ...parsed };
        }
      }
    } catch (_) {}
    return { ...DEFAULT_APP_SETTINGS };
  })(),
  updateAppSettings: (newSettings, persist = false) => {
    if (!newSettings || typeof newSettings !== 'object') return;
    set((state) => {
      const modified = new Set(state.modifiedSettingsKeys);
      if (persist) {
        Object.keys(newSettings).forEach((key) => modified.add(key));
      }
      const settingsToApply = { ...newSettings };
      if (!persist && modified.size > 0) {
        modified.forEach((key) => {
          if (state.appSettings && key in state.appSettings) {
            delete settingsToApply[key];
          }
        });
      }

      const merged = { ...(state.appSettings || DEFAULT_APP_SETTINGS), ...settingsToApply };
      try {
        localStorage.setItem('visionary:app_settings', JSON.stringify(merged));
      } catch (_) {}
      return {
        appSettings: merged,
        modifiedSettingsKeys: modified,
        settingsRevision: state.settingsRevision + 1,
      };
    });
    if (persist) {
      clientApi.saveSettings(newSettings).catch((err) => {
        console.warn('[WorkspaceStore] Falha ao persistir configurações no backend:', err);
      });
    }
  },
});
