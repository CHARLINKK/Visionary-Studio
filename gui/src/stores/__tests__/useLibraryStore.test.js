import { describe, it, expect } from 'vitest';
import { useLibraryStore, safeSetStorageItem } from '../useLibraryStore';

describe('useLibraryStore', () => {
  it('should initialize with default typography rules', () => {
    const rules = useLibraryStore.getState().typographyRules;
    expect(rules).toEqual({
      travessao: true,
      reticencias: true,
      caixaAlta: false,
    });
  });

  it('should update typography rules and persist to localStorage', () => {
    useLibraryStore.getState().updateTypographyRules({ caixaAlta: true, reticencias: false });

    const rules = useLibraryStore.getState().typographyRules;
    expect(rules.caixaAlta).toBe(true);
    expect(rules.reticencias).toBe(false);
    expect(rules.travessao).toBe(true);

    expect(window.localStorage.setItem).toHaveBeenCalledWith(
      'visionary:typography_rules',
      JSON.stringify(rules)
    );
  });

  it('should toggle autoTurnPage and sync with localStorage', () => {
    useLibraryStore.getState().setAutoTurnPage(true);
    expect(useLibraryStore.getState().autoTurnPage).toBe(true);
    expect(window.localStorage.setItem).toHaveBeenCalledWith('visionary:auto_turn_page', 'true');

    useLibraryStore.getState().setAutoTurnPage(false);
    expect(useLibraryStore.getState().autoTurnPage).toBe(false);
    expect(window.localStorage.setItem).toHaveBeenCalledWith('visionary:auto_turn_page', 'false');
  });

  it('should manage file load and delete request lifecycles', () => {
    const file = { name: 'capitulo_01.txt', path: '/library/capitulo_01.txt' };

    useLibraryStore.getState().requestLoadFile(file);
    expect(useLibraryStore.getState().requestedFileToLoad).toEqual(file);

    useLibraryStore.getState().clearRequestedFileToLoad();
    expect(useLibraryStore.getState().requestedFileToLoad).toBeNull();

    useLibraryStore.getState().requestDeleteFile(file);
    expect(useLibraryStore.getState().requestedFileToDelete).toEqual(file);

    useLibraryStore.getState().clearRequestedFileToDelete();
    expect(useLibraryStore.getState().requestedFileToDelete).toBeNull();
  });

  it('should bump libraryRevision reactively', () => {
    expect(useLibraryStore.getState().libraryRevision).toBe(0);
    useLibraryStore.getState().bumpLibraryRevision();
    expect(useLibraryStore.getState().libraryRevision).toBe(1);
  });

  it('evicts oldest entries via LRU cap and survives QuotaExceededError', () => {
    for (let i = 0; i < 18; i++) {
      safeSetStorageItem(`visionary:cached_pages:ch_${i}`, `data_${i}`, 'visionary:cached_pages:');
    }
    expect(localStorage.getItem('visionary:cached_pages:ch_0')).toBeNull();
    expect(localStorage.getItem('visionary:cached_pages:ch_17')).toBe('data_17');

    // Simulate QuotaExceededError on first setItem attempt
    localStorage.setItem.mockImplementationOnce(() => {
      const err = new Error('QuotaExceededError');
      err.name = 'QuotaExceededError';
      throw err;
    });

    expect(safeSetStorageItem('visionary:important_key', 'ok')).toBe(true);
    expect(localStorage.getItem('visionary:important_key')).toBe('ok');
  });
});
