/**
 * Slice 2: Capítulo Ativo, Memória de Páginas e Ciclo de Limpeza
 */
export const createChapterSlice = (set) => ({
  activeChapterPath: (() => {
    try {
      const saved = localStorage.getItem('visionary:last_folder');
      return saved ? JSON.parse(saved).path : null;
    } catch (_) {
      return null;
    }
  })(),
  activeChapterName: (() => {
    try {
      const saved = localStorage.getItem('visionary:last_folder');
      return saved ? JSON.parse(saved).name : null;
    } catch (_) {
      return null;
    }
  })(),
  chapterData: {}, // { 'page_001.png': { layout: {...}, ocr: {...}, translation: {...}, locked_layers: [] } }

  // Sincronização e Ciclo Atômico de Limpeza (Kill Global Flag)
  isClearingData: false,
  setIsClearingData: (isClearing) => set({ isClearingData: Boolean(isClearing) }),
  clearedDataEvent: null, // { timestamp, selectedPaths, stages }
  triggerDataCleared: (selectedPaths, stages) => set({
    clearedDataEvent: {
      timestamp: Date.now(),
      selectedPaths: Array.isArray(selectedPaths) ? selectedPaths : [],
      stages: Array.isArray(stages) ? stages : []
    }
  }),
  clearDataClearedEvent: () => set({ clearedDataEvent: null }),

  setActiveChapter: (path, name) => set({ activeChapterPath: path, activeChapterName: name, chapterData: {} }),

  setPageData: (pageName, data) => set((state) => ({
    chapterData: {
      ...state.chapterData,
      [pageName]: data
    }
  })),
});
