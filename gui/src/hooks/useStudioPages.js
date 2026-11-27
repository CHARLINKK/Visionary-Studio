import { useState, useEffect, useRef, useCallback } from 'react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { safeSetStorageItem } from '../stores/useLibraryStore';
import { clientApi, getServerUrl } from '../api/bridge.js';
import { prefetchPageData } from './useSeamlessDataLoader.js';

export function useStudioPages({ folderPath, isActive = true }) {
  const [pages, setPages] = useState(() => {
    if (!folderPath) return [];
    try {
      const cached = localStorage.getItem(`visionary:cached_pages:${folderPath}`);
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  });

  const [currentIndex, setCurrentIndex] = useState(() => {
    if (!folderPath) return 0;
    try {
      const saved = localStorage.getItem(`visionary:last_index:${folderPath}`);
      return saved !== null ? Number(saved) : 0;
    } catch {
      return 0;
    }
  });

  const [loading, setLoading] = useState(false);
  const [hasFetchedOnce, setHasFetchedOnce] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [selectedPages, setSelectedPages] = useState(new Set());

  const pendingJumpPage = useWorkspaceStore(state => state.pendingJumpPage);
  const clearPendingJumpPage = useWorkspaceStore(state => state.clearPendingJumpPage);
  const workspaceRevision = useWorkspaceStore(state => state.workspaceRevision);
  const bumpExplorerRevision = useWorkspaceStore(state => state.bumpExplorerRevision);
  const jobsStatusSignature = useWorkspaceStore(state =>
    state.jobQueue.map(j => `${j.id}:${j.status}`).join('|')
  );

  const previousJobs = useRef([]);
  const pendingJumpRef = useRef(null);
  const pagesLengthRef = useRef(pages.length);
  pagesLengthRef.current = pages.length;

  const fetchDirectory = useCallback((resetSelection = true, silent = false) => {
    if (!folderPath) {
      setPages([]);
      setSelectedPages(new Set());
      return;
    }
    const isSilent = silent || pagesLengthRef.current > 0;
    if (!isSilent) setLoading(true);
    clientApi.listDirectory(folderPath).then(res => {
      if (res?.success && res.items) {
        const imgPages = res.items.filter(i => i.isImage);
        setPages(imgPages);
        safeSetStorageItem(
          `visionary:cached_pages:${folderPath}`,
          JSON.stringify(imgPages),
          'visionary:cached_pages:'
        );
        if (resetSelection) {
          setCurrentIndex(prev => (prev < imgPages.length ? prev : 0));
          setSelectedPages(new Set());
        }
        if (pendingJumpRef.current) {
          const target = pendingJumpRef.current;
          pendingJumpRef.current = null;
          const cleanTarget = target.trim().toLowerCase();
          const foundIdx = imgPages.findIndex(p =>
            p.name.toLowerCase() === cleanTarget ||
            p.name.toLowerCase().includes(cleanTarget) ||
            cleanTarget.includes(p.name.toLowerCase())
          );
          if (foundIdx !== -1) {
            setCurrentIndex(foundIdx);
          }
        }
      }
    }).catch(err => {
      console.error("Erro ao listar diretório:", err);
    }).finally(() => {
      if (!isSilent) setLoading(false);
      setHasFetchedOnce(true);
    });
  }, [folderPath]);

  // Salto para página solicitada
  useEffect(() => {
    if (!pendingJumpPage || pages.length === 0) return;
    const cleanTarget = pendingJumpPage.trim().toLowerCase();
    const foundIdx = pages.findIndex(p =>
      p.name.toLowerCase() === cleanTarget ||
      p.name.toLowerCase().includes(cleanTarget) ||
      cleanTarget.includes(p.name.toLowerCase())
    );
    if (foundIdx !== -1) {
      setCurrentIndex(foundIdx);
      clearPendingJumpPage();
    }
  }, [pendingJumpPage, pages, clearPendingJumpPage]);

  // Auto-scroll da lista de páginas quando muda o índice ativo
  useEffect(() => {
    const activeEl = document.getElementById(`batch-page-${currentIndex}`);
    if (activeEl) {
      activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [currentIndex]);

  // Atualização após conclusão de jobs da fila
  useEffect(() => {
    const queue = useWorkspaceStore.getState().jobQueue;
    if (queue && queue.length > 0) {
      let shouldRefresh = false;
      let newIndex = -1;

      queue.forEach(job => {
        const prevJob = previousJobs.current.find(j => j.id === job.id);
        if (prevJob && prevJob.status !== 'completed' && job.status === 'completed') {
          shouldRefresh = true;
          if (job.payload?.isPauseJob && job.payload?.firstPageIndex !== undefined) {
            newIndex = job.payload.firstPageIndex;
          }
        }
      });

      if (shouldRefresh) {
        fetchDirectory(false, true);
        if (newIndex >= 0) setCurrentIndex(newIndex);
        setRefreshTrigger(prev => prev + 1);
        bumpExplorerRevision();
      }

      previousJobs.current = queue.map(j => ({ id: j.id, status: j.status, payload: j.payload }));
    }
  }, [jobsStatusSignature, folderPath, bumpExplorerRevision, fetchDirectory]);

  // Invalidação por revisão de workspace
  useEffect(() => {
    if (workspaceRevision > 0 && folderPath) {
      fetchDirectory(false, true);
    }
  }, [workspaceRevision, folderPath, fetchDirectory]);

  // Reseta seleção sempre que o capítulo/pasta ativa mudar
  const lastFolderRef = useRef(folderPath);
  useEffect(() => {
    if (lastFolderRef.current !== folderPath) {
      lastFolderRef.current = folderPath;
      setSelectedPages(new Set());
    }
  }, [folderPath]);

  // Limpa seleção ao receber sinal de reset de sessão do Electron (minimizar/fechar para bandeja ou segunda instância)
  useEffect(() => {
    if (window.electronAPI?.onSessionReset) {
      return window.electronAPI.onSessionReset(() => {
        setSelectedPages(new Set());
      });
    }
  }, []);

  // Limpa seleção ao descarregar a janela
  useEffect(() => {
    const handleUnload = () => {
      setSelectedPages(new Set());
    };
    window.addEventListener('beforeunload', handleUnload);
    return () => window.removeEventListener('beforeunload', handleUnload);
  }, []);

  // Salva no localStorage a última página navegada
  useEffect(() => {
    if (folderPath && currentIndex >= 0) {
      safeSetStorageItem(
        `visionary:last_index:${folderPath}`,
        String(currentIndex),
        'visionary:last_index:'
      );
    }
  }, [folderPath, currentIndex]);

  // Carrega cache e diretório inicial
  useEffect(() => {
    let syncTimer = null;
    let hasLocalCache = false;
    if (folderPath) {
      try {
        const cached = localStorage.getItem(`visionary:cached_pages:${folderPath}`);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length > 0) {
            setPages(parsed);
            hasLocalCache = true;
          }
        }
        const savedIdx = localStorage.getItem(`visionary:last_index:${folderPath}`);
        if (savedIdx !== null && !isNaN(Number(savedIdx))) {
          setCurrentIndex(Number(savedIdx));
        }
      } catch {}
    }
    if (hasLocalCache) {
      // Com cache local válido, revalida silenciosamente após a abertura para não disputar I/O/GIL no boot
      syncTimer = setTimeout(() => {
        fetchDirectory(false, true);
      }, 350);
    } else {
      fetchDirectory(false);
    }
    return () => {
      if (syncTimer) clearTimeout(syncTimer);
    };
  }, [folderPath, fetchDirectory]);

  // Polling leve durante jobs ativos
  useEffect(() => {
    if (!isActive) return;
    const intervalId = setInterval(() => {
      const currentQueue = useWorkspaceStore.getState().jobQueue;
      const hasRunningJobs = currentQueue?.some(job => job.status === 'running');

      if (hasRunningJobs && folderPath) {
        clientApi.listDirectory(folderPath).then(res => {
          if (res?.success && res.items) {
            const imgPages = res.items.filter(i => i.isImage);
            setPages(prev => {
              if (
                prev.length === imgPages.length &&
                prev.every(
                  (p, i) =>
                    p.name === imgPages[i].name &&
                    p.hasMap === imgPages[i].hasMap &&
                    p.hasOcr === imgPages[i].hasOcr &&
                    p.hasTrans === imgPages[i].hasTrans
                )
              ) {
                return prev;
              }
              return imgPages;
            });
          }
        }).catch(() => {});
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [isActive, folderPath]);

  // Sincroniza silenciosamente ao reativar aba
  useEffect(() => {
    if (isActive && folderPath) {
      fetchDirectory(false, true);
    }
  }, [isActive, folderPath, fetchDirectory]);

  // Pré-carregamento de imagens adjacentes
  useEffect(() => {
    if (!pages || pages.length === 0) return;
    const serverUrl = getServerUrl();
    if (currentIndex + 1 < pages.length) {
      const nextPath = pages[currentIndex + 1]?.path;
      if (nextPath) {
        const nextImg = new Image();
        nextImg.crossOrigin = 'anonymous';
        nextImg.src = `${serverUrl}/api/image?path=${encodeURIComponent(nextPath)}`;
        prefetchPageData(nextPath);
      }
    }
    if (currentIndex - 1 >= 0) {
      const prevPath = pages[currentIndex - 1]?.path;
      if (prevPath) {
        const prevImg = new Image();
        prevImg.crossOrigin = 'anonymous';
        prevImg.src = `${serverUrl}/api/image?path=${encodeURIComponent(prevPath)}`;
        prefetchPageData(prevPath);
      }
    }
  }, [pages, currentIndex]);

  const handleTogglePage = useCallback((idx) => {
    setSelectedPages(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelectedPages(prev => {
      if (prev.size === pages.length) return new Set();
      return new Set(pages.map((_, i) => i));
    });
  }, [pages]);

  const activePage = pages[currentIndex] || null;

  return {
    pages,
    setPages,
    currentIndex,
    setCurrentIndex,
    activePage,
    loading,
    hasFetchedOnce,
    refreshTrigger,
    setRefreshTrigger,
    selectedPages,
    setSelectedPages,
    fetchDirectory,
    handleTogglePage,
    handleSelectAll,
  };
}
