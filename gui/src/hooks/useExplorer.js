import { useState, useCallback, useMemo, useEffect } from 'react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { clientApi } from '../api/bridge';
import { safeSetStorageItem, safeRemoveStorageItem } from '../utils/storage';

const normalizeForSearch = (str) => {
  if (!str) return '';
  return str
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
};

export function useExplorer() {
  const [currentPath, setCurrentPath] = useState(() => {
    try {
      return localStorage.getItem('visionary:last_explorer_path') || null;
    } catch (_) {
      return null;
    }
  });
  const [entries, setEntries] = useState(() => {
    try {
      const saved = localStorage.getItem('visionary:cached_explorer_entries');
      const parsed = saved ? JSON.parse(saved) : [];
      return Array.isArray(parsed) ? parsed.filter(e => e.isDrive || e.isBack || e.isDir) : [];
    } catch (_) {
      return [];
    }
  });
  const [isAtRoot, setIsAtRoot] = useState(() => {
    try {
      const saved = localStorage.getItem('visionary:last_explorer_is_at_root');
      if (saved !== null) return saved === 'true';
      return !localStorage.getItem('visionary:last_explorer_path');
    } catch (_) {
      return true;
    }
  });
  const [searchQuery, setSearchQuery] = useState('');
  
  const [selectedFolder, setSelectedFolder] = useState(() => {
    try {
      const saved = localStorage.getItem('visionary:last_folder');
      return saved ? JSON.parse(saved) : null;
    } catch (_) {
      return null;
    }
  });

  const setActiveChapter = useWorkspaceStore(state => state.setActiveChapter);
  const explorerRevision = useWorkspaceStore(state => state.explorerRevision);

  const filteredEntries = useMemo(() => {
    const rawQuery = searchQuery.trim();
    if (!rawQuery) return entries;
    const q = normalizeForSearch(rawQuery);
    const words = q.split(/\s+/).filter(Boolean);

    return entries.filter(e => {
      if (e.isBack) return false;
      if (!e.name) return false;
      const normName = normalizeForSearch(e.name);
      return words.every(word => {
        if (normName.includes(word)) return true;
        if (word === 'cap' && normName.includes('capitulo')) return true;
        if (/^\d+$/.test(word)) {
          const num = parseInt(word, 10);
          const numbersInName = normName.match(/\d+/g);
          if (numbersInName && numbersInName.some(n => parseInt(n, 10) === num)) {
            return true;
          }
        }
        return false;
      });
    });
  }, [entries, searchQuery]);

  const loadDrives = useCallback(async () => {
    let driveEntries = [{ name: 'C:', path: 'C:\\', isDrive: true }, { name: 'D:', path: 'D:\\', isDrive: true }];
    try {
      const drives = await clientApi.listDrives();
      if (Array.isArray(drives) && drives.length > 0) {
        driveEntries = drives;
      }
    } catch {
      // keep fallback
    }
    setEntries(driveEntries);
    setIsAtRoot(true);
    setCurrentPath(null);
    setSearchQuery('');
    safeSetStorageItem('visionary:cached_explorer_entries', JSON.stringify(driveEntries));
    safeSetStorageItem('visionary:last_explorer_is_at_root', 'true');
    safeRemoveStorageItem('visionary:last_explorer_path');
  }, []);

  const navigateTo = useCallback(async (path) => {
    try {
      const dirEntries = await clientApi.listDirectory(path);
      if (dirEntries && dirEntries.success === false) {
        console.error(dirEntries.error);
        return loadDrives();
      }
      const rawItems = dirEntries?.items || (Array.isArray(dirEntries) ? dirEntries : []);
      const items = rawItems.filter(e => e.isDrive || e.isBack || e.isDir);
      setEntries(items);
      setCurrentPath(path);
      setIsAtRoot(false);
      setSearchQuery('');
      // Limita o cache inicial a 100 itens para evitar estouro de storage em pastas gigantescas
      const cachedSlice = items.slice(0, 100);
      safeSetStorageItem('visionary:cached_explorer_entries', JSON.stringify(cachedSlice));
      safeSetStorageItem('visionary:last_explorer_is_at_root', 'false');
      safeSetStorageItem('visionary:last_explorer_path', path);
    } catch (e) {
      console.error(e);
      loadDrives();
    }
  }, [loadDrives]);

  const refreshCurrentDirectory = useCallback(async () => {
    if (!currentPath && isAtRoot) {
      loadDrives();
      return;
    }
    if (!currentPath) return;
    try {
      const dirEntries = await clientApi.listDirectory(currentPath);
      let rawItems = null;
      if (dirEntries && dirEntries.items) {
        rawItems = dirEntries.items;
      } else if (Array.isArray(dirEntries)) {
        rawItems = dirEntries;
      }
      if (rawItems) {
        const items = rawItems.filter(e => e.isDrive || e.isBack || e.isDir);
        setEntries(items);
        const cachedSlice = items.slice(0, 100);
        safeSetStorageItem('visionary:cached_explorer_entries', JSON.stringify(cachedSlice));
      }
    } catch (e) {
      console.error("Error refreshing explorer:", e);
    }
  }, [currentPath, isAtRoot, loadDrives]);

  const handleGoUp = useCallback(async () => {
    if (isAtRoot) return;
    try {
      const parent = await clientApi.getParentPath(currentPath);
      if (parent && parent.success !== false) {
        navigateTo(parent);
      } else {
        loadDrives();
      }
    } catch {
      loadDrives();
    }
  }, [isAtRoot, currentPath, navigateTo, loadDrives]);

  // Sync com Zustand & LocalStorage
  useEffect(() => {
    if (selectedFolder) {
      safeSetStorageItem('visionary:last_folder', JSON.stringify(selectedFolder));
      setActiveChapter(selectedFolder.path, selectedFolder.name);
      clientApi.saveSettings({ last_opened_folder: selectedFolder.path }).catch(() => {});
    }
  }, [selectedFolder, setActiveChapter]);

  // Invalidação reativa em tempo real via revisão numérica do store e foco da janela
  useEffect(() => {
    if (explorerRevision > 0) {
      refreshCurrentDirectory();
    }
  }, [explorerRevision, refreshCurrentDirectory]);

  useEffect(() => {
    const handleFocus = () => refreshCurrentDirectory();
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [refreshCurrentDirectory]);

  return {
    currentPath,
    entries,
    isAtRoot,
    searchQuery,
    setSearchQuery,
    selectedFolder,
    setSelectedFolder,
    filteredEntries,
    loadDrives,
    navigateTo,
    refreshCurrentDirectory,
    handleGoUp
  };
}
