import { create } from 'zustand';
import {
  safeSetStorageItem,
  safeGetStorageItem,
  safeGetStorageJSON,
  safeRemoveStorageItem,
} from '../utils/storage';

export {
  safeSetStorageItem,
  safeGetStorageItem,
  safeGetStorageJSON,
  safeRemoveStorageItem,
};

export const DEFAULT_TYPOGRAPHY_RULES = {
  travessao: true,
  reticencias: true,
  caixaAlta: false,
};

export function readTypographyRulesFromStorage() {
  try {
    const val = localStorage.getItem('visionary:typography_rules');
    if (val) {
      const parsed = JSON.parse(val);
      if (parsed && typeof parsed === 'object') {
        return { ...DEFAULT_TYPOGRAPHY_RULES, ...parsed };
      }
    }
  } catch {}
  return { ...DEFAULT_TYPOGRAPHY_RULES };
}

export const useLibraryStore = create((set, get) => ({
  // Domain State
  libraryFiles: (() => {
    try {
      const cached = localStorage.getItem('visionary:cached_lib_files');
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  })(),
  activeFile: (() => {
    try {
      const cached = localStorage.getItem('visionary:cached_lib_active_file');
      return cached ? JSON.parse(cached) : null;
    } catch {
      return null;
    }
  })(),
  fileContent: (() => {
    try {
      const lastFile = localStorage.getItem('visionary:cached_lib_active_file');
      if (lastFile) {
        const parsed = JSON.parse(lastFile);
        if (parsed?.path) {
          const cachedContent = localStorage.getItem(`visionary:cached_lib_content:${parsed.path}`);
          if (cachedContent) return cachedContent;
        }
      }
      return '';
    } catch {
      return '';
    }
  })(),
  copiedBlocks: {},
  activeCopiedId: null,
  typographyRules: readTypographyRulesFromStorage(),
  isLoading: false,
  
  // Actions
  setIsLoading: (val) => set({ isLoading: Boolean(val) }),
  setLibraryFiles: (files) => {
    safeSetStorageItem('visionary:cached_lib_files', JSON.stringify(files));
    set({ libraryFiles: files });
  },
  setActiveFile: (file) => {
    try {
      if (file) safeSetStorageItem('visionary:cached_lib_active_file', JSON.stringify(file));
      else localStorage.removeItem('visionary:cached_lib_active_file');
    } catch {}
    set({ activeFile: file });
  },
  setFileContent: (content) => {
    const state = get();
    if (state.activeFile?.path && content && content !== 'Carregando...') {
      safeSetStorageItem(
        `visionary:cached_lib_content:${state.activeFile.path}`,
        content,
        'visionary:cached_lib_content:'
      );
    }
    set({ fileContent: content });
  },
  setCopiedBlocks: (blocks) => set({ copiedBlocks: typeof blocks === 'function' ? blocks(get().copiedBlocks) : blocks }),
  setActiveCopiedId: (id) => set({ activeCopiedId: id }),
  setTypographyRules: (rulesOrUpdater) => set((state) => {
    const updates = typeof rulesOrUpdater === 'function' ? rulesOrUpdater(state.typographyRules) : rulesOrUpdater;
    const nextRules = { ...DEFAULT_TYPOGRAPHY_RULES, ...state.typographyRules, ...updates };
    safeSetStorageItem('visionary:typography_rules', JSON.stringify(nextRules));
    return { typographyRules: nextRules };
  }),

  // ── Preferências da Biblioteca ──
  autoResumePending: (() => {
    try { return localStorage.getItem('visionary:auto_resume_pending') !== 'false'; } catch (_) { return true; }
  })(),
  setAutoResumePending: (val) => {
    safeSetStorageItem('visionary:auto_resume_pending', String(val));
    set({ autoResumePending: Boolean(val) });
  },
  autoTurnPage: (() => {
    try { return localStorage.getItem('visionary:auto_turn_page') === 'true'; } catch (_) { return false; }
  })(),
  setAutoTurnPage: (val) => {
    safeSetStorageItem('visionary:auto_turn_page', String(val));
    set({ autoTurnPage: Boolean(val) });
  },

  // ── Invalidação Reativa e Ações Declarativas da Sidebar ──
  libraryRevision: 0,
  bumpLibraryRevision: () => set((state) => ({ libraryRevision: state.libraryRevision + 1 })),
  requestedFileToLoad: null,
  requestLoadFile: (file) => set({ requestedFileToLoad: file }),
  clearRequestedFileToLoad: () => set({ requestedFileToLoad: null }),
  requestedFileToDelete: null,
  requestDeleteFile: (file) => set({ requestedFileToDelete: file }),
  clearRequestedFileToDelete: () => set({ requestedFileToDelete: null }),
  requestedOpenLibraryFolder: false,
  requestOpenLibraryFolder: () => set({ requestedOpenLibraryFolder: true }),
  clearRequestedOpenLibraryFolder: () => set({ requestedOpenLibraryFolder: false }),
  
  // High-level Actions
  updateTypographyRules: (updates) => {
    get().setTypographyRules(updates);
  },
  
  initializeTypographyRules: () => {
    set({ typographyRules: readTypographyRulesFromStorage() });
  }
}));

if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
  window.addEventListener('storage', (event) => {
    if (event.key === 'visionary:typography_rules') {
      useLibraryStore.getState().initializeTypographyRules();
    }
  });
}
