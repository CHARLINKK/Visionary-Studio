/**
 * Slice 1: Navegação, Modais e Atalhos de Interface
 */
export const createNavigationSlice = (set) => ({
  activeTab: (() => {
    try {
      if (typeof window !== 'undefined') {
        const param = new URLSearchParams(window.location.search).get('tab');
        if (param === 'biblioteca' || param === 'library') return 'biblioteca';
        if (param === 'lightbox') return 'lightbox';
        if (param === 'modulos' || param === 'modules') return 'modulos';
        if (param === 'configuracoes' || param === 'settings') return 'configuracoes';
      }
    } catch {}
    return 'processamento';
  })(),
  setActiveTab: (tab) => set((state) => {
    const resolved = typeof tab === 'function' ? tab(state.activeTab) : tab;
    return { activeTab: resolved === 'tutorial' ? 'processamento' : resolved };
  }),

  // Modo Desenvolvedor
  isDevUnlocked: false,
  setIsDevUnlocked: (isDevUnlocked) => set({ isDevUnlocked: Boolean(isDevUnlocked) }),

  // Navegação Declarativa & Saltos de Página (Kill Race Conditions)
  pendingJumpPage: null,
  requestJumpToPage: (pageName) => set({ pendingJumpPage: pageName ? String(pageName).trim() : null }),
  clearPendingJumpPage: () => set({ pendingJumpPage: null }),
  navigateToStudioPage: ({ folderPath, folderName, pageName }) => {
    const updates = { activeTab: 'processamento' };
    if (folderPath) {
      const name = folderName || folderPath.split(/[/\\]/).filter(Boolean).pop();
      updates.activeChapterPath = folderPath;
      updates.activeChapterName = name;
      updates.chapterData = {};
    }
    if (pageName) {
      updates.pendingJumpPage = String(pageName).trim();
    }
    set(updates);
  },

  // Onboarding Wizard (Modais Declarativos)
  isOnboardingOpen: false,
  onboardingConfig: { view: 'selection', isDebugPreview: false },
  openOnboarding: (config = {}) => set({
    isOnboardingOpen: true,
    onboardingConfig: {
      view: config?.view || 'selection',
      isDebugPreview: Boolean(config?.isDebugPreview)
    }
  }),
  closeOnboarding: () => set({ isOnboardingOpen: false }),

  // UI, Modais e Atalhos Globais
  isQueueOpen: false,
  toggleQueue: (force) => set((state) => ({ isQueueOpen: typeof force === 'boolean' ? force : !state.isQueueOpen })),
  quickSymbolsEnabled: (() => {
    try {
      return localStorage.getItem('visionary:quick_symbols') === 'true';
    } catch (_) {
      return false;
    }
  })(),
  setQuickSymbolsEnabled: (val) => {
    try {
      localStorage.setItem('visionary:quick_symbols', String(val));
    } catch (_) {}
    set({ quickSymbolsEnabled: Boolean(val) });
  },
  isQuickSymbolsOpen: false,
  toggleQuickSymbols: (force) => set((state) => ({ isQuickSymbolsOpen: typeof force === 'boolean' ? force : !state.isQuickSymbolsOpen })),
});
