import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "../contexts/ToastContext";
import { clientApi } from "../api/bridge";
import { useLibraryStore } from "../stores/useLibraryStore";
import { useLibraryViewerStore } from "../stores/useLibraryViewerStore";
import { useLibraryShortcuts } from "./useLibraryShortcuts";
import { useLibraryParser } from "./useLibraryParser";
import { useLibraryBackend } from "./useLibraryBackend";
import { useTypographyRules } from "./useTypographyRules";
import { useLibrarySearch } from "./useLibrarySearch";
import { useLibraryClipboard } from "./useLibraryClipboard";
import { useLibraryPagination } from "./useLibraryPagination";
import { useLibrarySplitCards } from "./useLibrarySplitCards";

/**
 * Controller desacoplado da tela de Biblioteca (Library).
 * Centraliza a orquestração de sub-hooks, sincronização com stores Zustand,
 * telemetria de cópia, navegação de páginas e I/O com backend.
 */
export function useLibraryController({ activeChapterName, activeChapterPath, isActive = false }) {
  const { addToast } = useToast();

  // Stores Zustand
  const activeFile = useLibraryStore((s) => s.activeFile);
  const fileContent = useLibraryStore((s) => s.fileContent);
  const setLibraryFiles = useLibraryStore((s) => s.setLibraryFiles);
  const setActiveFile = useLibraryStore((s) => s.setActiveFile);
  const setFileContent = useLibraryStore((s) => s.setFileContent);
  const setCopiedBlocks = useLibraryStore((s) => s.setCopiedBlocks);
  const copiedBlocks = useLibraryStore((s) => s.copiedBlocks);
  const activeCopiedId = useLibraryStore((s) => s.activeCopiedId);
  const setActiveCopiedId = useLibraryStore((s) => s.setActiveCopiedId);
  const libraryRevision = useLibraryStore((s) => s.libraryRevision);

  const requestedFileToLoad = useLibraryStore((s) => s.requestedFileToLoad);
  const clearRequestedFileToLoad = useLibraryStore((s) => s.clearRequestedFileToLoad);
  const requestedFileToDelete = useLibraryStore((s) => s.requestedFileToDelete);
  const clearRequestedFileToDelete = useLibraryStore((s) => s.clearRequestedFileToDelete);
  const requestedOpenLibraryFolder = useLibraryStore((s) => s.requestedOpenLibraryFolder);
  const clearRequestedOpenLibraryFolder = useLibraryStore((s) => s.clearRequestedOpenLibraryFolder);

  const activePageIndex = useLibraryViewerStore((s) => s.activePageIndex);
  const setActivePageIndex = useLibraryViewerStore((s) => s.setActivePageIndex);
  const setActiveBlockId = useLibraryViewerStore((s) => s.setActiveBlockId);
  const setZoomTargetRect = useLibraryViewerStore((s) => s.setZoomTargetRect);
  const resetZoom = useLibraryViewerStore((s) => s.resetZoom);

  // Estados locais de interface
  const isLoading = useLibraryStore((s) => s.isLoading);
  const setIsLoading = useLibraryStore((s) => s.setIsLoading);
  const [viewMode, setViewMode] = useState(() => {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const urlView = urlParams.get("view");
      if (urlView && ["script", "split", "raw"].includes(urlView)) {
        return urlView;
      }
      const saved = localStorage.getItem("visionary:library_view_mode");
      if (saved && ["script", "split", "raw"].includes(saved)) {
        return saved;
      }
    } catch {}
    return "script";
  });
  const isRawMode = viewMode === "raw";

  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      const val = localStorage.getItem("visionary:lib_sidebar_collapsed");
      return val === null ? window.innerWidth <= 1400 : JSON.parse(val);
    } catch { return false; }
  });

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("visionary:lib_sidebar_collapsed", JSON.stringify(next)); } catch {}
      return next;
    });
  };

  const [collapsedPages, setCollapsedPages] = useState({});
  const [blockInputs, setBlockInputs] = useState({});
  const [activeTab, setActiveTab] = useState(null);

  const [isTypographyRulesOpen, setIsTypographyRulesOpen] = useState(false);
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false);

  // Refs de controle de ciclo de vida
  const loadCounter = useRef(0);
  const activeFileRef = useRef(activeFile);
  const searchInputRef = useRef(null);

  useEffect(() => {
    activeFileRef.current = activeFile;
  }, [activeFile]);

  // Fechamento de dropdowns ao clicar fora
  useEffect(() => {
    if (!isExportMenuOpen && !isTypographyRulesOpen) return;
    const handleOutsideClick = (e) => {
      if (!e.target?.closest?.(".dropdown-wrapper")) {
        setIsExportMenuOpen(false);
        setIsTypographyRulesOpen(false);
      }
    };
    window.addEventListener("mousedown", handleOutsideClick);
    return () => window.removeEventListener("mousedown", handleOutsideClick);
  }, [isExportMenuOpen, isTypographyRulesOpen]);

  // Hook 1: Regras Tipográficas
  const { typographyRules, updateTypographyRules, applyTypographyRules } = useTypographyRules();

  // Hook 2: Clipboard e Histórico de Cópia
  const {
    lastCopiedId,
    setLastCopiedId,
    isRawCopied,
    copyBalloon,
    undoCopyBalloon,
    copyFullPage,
    copyRawContent,
    resetProgress,
  } = useLibraryClipboard({
    activeFile,
    fileContent,
    applyTypographyRules,
    addToast,
  });

  // Hook 3: Parser de Roteiro
  const { parsedPages, activePageData, allBalloonsList } = useLibraryParser(fileContent, activePageIndex);

  // Hook 4: Paginação, Auto-Turn e Auto-Resume
  const {
    goToPage,
    jumpToNextPending,
    autoResumePending,
    toggleAutoResume,
  } = useLibraryPagination({
    parsedPages,
    activePageIndex,
    setActivePageIndex,
    resetZoom,
    viewMode,
    setCollapsedPages,
    lastCopiedId,
    setLastCopiedId,
    copiedBlocks,
    activeFile,
    loadCounter,
    addToast,
    setActiveCopiedId,
  });

  // Hook 5: Busca Textual no Roteiro
  const {
    activeSearchQuery,
    setActiveSearchQuery,
    searchMatches,
    currentMatchIndex,
    activeMatchKey,
    handleNextSearchMatch,
    handlePrevSearchMatch,
    clearSearch,
  } = useLibrarySearch({
    allBalloonsList,
    parsedPages,
    activePageIndex,
    setActivePageIndex,
    viewMode,
    setCollapsedPages,
  });

  // Carregamento de arquivo individual
  const loadLibraryFile = useCallback(async (file) => {
    if (!file) return;
    loadCounter.current += 1;
    const currentLoad = loadCounter.current;
    if (viewMode === "split") setSidebarCollapsed(true);
    setActiveFile(file);

    try {
      const cached = localStorage.getItem(`visionary:cached_lib_content:${file.path}`);
      if (cached && cached.trim()) {
        setFileContent(cached);
      }
    } catch {}

    setActiveCopiedId(null);
    clearSearch();
    setActiveTab(null);
    setBlockInputs({});
    resetZoom();

    try {
      const stored = localStorage.getItem(`visionary:copied_${file.path}`);
      setCopiedBlocks(stored ? JSON.parse(stored) : {});
    } catch {
      setCopiedBlocks({});
    }

    try {
      const res = await clientApi.readLibraryFile(file.path);
      if (loadCounter.current !== currentLoad) return;
      if (res && res.success) {
        setFileContent(res.content);
      } else if (!fileContent) {
        setFileContent("[ERRO] " + (res?.error || "Não foi possível ler o arquivo."));
      }
    } catch (err) {
      if (loadCounter.current !== currentLoad) return;
      if (!fileContent) {
        setFileContent("[ERRO] Falha ao contatar backend: " + err.message);
      }
    }
  }, [viewMode, fileContent, setActiveFile, setFileContent, setActiveCopiedId, clearSearch, setCopiedBlocks, resetZoom]);

  // Hook 6: Backend Integrator (Studio link, exportação, exclusão, salvamento)
  const refreshLibrary = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await clientApi.listLibraryFiles();
      if (res && res.success && Array.isArray(res.files)) {
        const filesList = res.files
          .filter((f) => !f.name.toLowerCase().endsWith("_letrista.txt"))
          .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
        setLibraryFiles(filesList);

        let targetFile = null;
        if (activeChapterName) {
          const nameLower = activeChapterName.toLowerCase();
          targetFile = filesList.find((f) =>
            f.name.toLowerCase().includes(nameLower) ||
            nameLower.includes(f.name.replace(".txt", "").toLowerCase())
          );
        }

        if (activeFile) {
          const match = filesList.find((f) => f.path === activeFile.path);
          if (match) setActiveFile(match);
          else if (targetFile) loadLibraryFile(targetFile);
          else if (filesList.length > 0) loadLibraryFile(filesList[0]);
        } else {
          if (targetFile) loadLibraryFile(targetFile);
          else if (filesList.length > 0) loadLibraryFile(filesList[0]);
        }
      }
    } catch (err) {
      console.error("[Library] Error refreshing library:", err);
    } finally {
      setIsLoading(false);
    }
  }, [activeChapterName, activeFile, loadLibraryFile, setActiveFile, setIsLoading, setLibraryFiles]);

  const { openInStudio, exportScript, deleteLibraryFile, saveBalloonText, syncChapterTxt, isSyncing } = useLibraryBackend({
    activeFile,
    setActiveFile,
    fileContent,
    setFileContent,
    parsedPages,
    setBlockInputs,
    setActiveTab,
    addToast,
    refreshLibrary,
  });

  // Efeito de escaneamento inicial ao mudar capítulo ou ativar a aba
  useEffect(() => {
    let isCanceled = false;
    (async () => {
      if (!isActive) return;
      const hasExistingFiles = useLibraryStore.getState().libraryFiles.length > 0;
      if (!hasExistingFiles) setIsLoading(true);
      try {
        const res = await clientApi.listLibraryFiles();
        if (isCanceled) return;
        if (res && res.success && Array.isArray(res.files)) {
          const filesList = res.files
            .filter((f) => !f.name.toLowerCase().endsWith("_letrista.txt"))
            .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
          setLibraryFiles(filesList);

          let targetFile = null;
          if (activeChapterName) {
            const nameLower = activeChapterName.toLowerCase();
            targetFile = filesList.find((f) =>
              f.name.toLowerCase().includes(nameLower) ||
              nameLower.includes(f.name.replace(".txt", "").toLowerCase())
            );
          }

          const currentActive = activeFileRef.current;
          if (currentActive) {
            const match = filesList.find((f) => f.path === currentActive.path);
            if (match) {
              setActiveFile(match);
              clientApi.readLibraryFile(match.path).then((readRes) => {
                if (!isCanceled && readRes && readRes.success) {
                  setFileContent(readRes.content);
                }
              }).catch(() => {});
            } else if (targetFile) {
              loadLibraryFile(targetFile);
            } else if (filesList.length > 0) {
              loadLibraryFile(filesList[0]);
            }
          } else {
            if (targetFile) loadLibraryFile(targetFile);
            else if (filesList.length > 0) loadLibraryFile(filesList[0]);
          }
        }
      } catch (err) {
        console.error("[Library] Error loading library files:", err);
      } finally {
        if (!isCanceled) setIsLoading(false);
      }
    })();
    return () => { isCanceled = true; };
  }, [activeChapterName, activeChapterPath, isActive, loadLibraryFile, setActiveFile, setFileContent, setIsLoading, setLibraryFiles]);

  // Abertura de diretório no Windows Explorer
  const openInExplorer = useCallback(async (pathOverride) => {
    const target = pathOverride || activeFile?.chapter_dir || activeFile?.path;
    if (!target) return;
    try {
      await clientApi.openFileInExplorer(target);
      addToast("Pasta aberta no Windows Explorer!", "info");
    } catch (err) {
      console.error("Erro ao abrir pasta no Explorer:", err);
      addToast("Não foi possível abrir a pasta no Explorer.", "error");
    }
  }, [activeFile?.chapter_dir, activeFile?.path, addToast]);

  const openLibraryFolder = useCallback(async () => {
    try {
      if (activeFile?.path) {
        const res = await clientApi.openFileInExplorer(activeFile.path);
        if (res && res.success) {
          addToast("Pasta do capítulo aberta no Explorer!", "info");
          return;
        }
      }
      const res = await clientApi.openLibraryFolder();
      if (res && res.success === false) {
        addToast(`Erro: ${res.error}`, "error");
      } else {
        addToast("Pasta dos capítulos aberta no Explorer!", "info");
      }
    } catch (err) {
      console.error("Erro ao abrir pasta dos capítulos:", err);
      addToast("Não foi possível abrir a pasta no Explorer.", "error");
    }
  }, [activeFile?.path, addToast]);

  // Sincronização declarativa com o Zustand Store
  useEffect(() => {
    if (requestedFileToLoad) {
      loadLibraryFile(requestedFileToLoad);
      clearRequestedFileToLoad();
    }
  }, [requestedFileToLoad, clearRequestedFileToLoad, loadLibraryFile]);

  useEffect(() => {
    if (requestedOpenLibraryFolder) {
      openLibraryFolder();
      clearRequestedOpenLibraryFolder();
    }
  }, [requestedOpenLibraryFolder, clearRequestedOpenLibraryFolder, openLibraryFolder]);

  useEffect(() => {
    if (requestedFileToDelete) {
      deleteLibraryFile({ stopPropagation: () => {} }, requestedFileToDelete);
      clearRequestedFileToDelete();
    }
  }, [requestedFileToDelete, clearRequestedFileToDelete, deleteLibraryFile]);

  useEffect(() => {
    if (libraryRevision > 0) {
      refreshLibrary();
    }
  }, [libraryRevision, refreshLibrary]);

  const changeViewMode = useCallback((mode) => {
    setViewMode(mode);
    try { localStorage.setItem("visionary:library_view_mode", mode); } catch {}
    if (mode === "split") {
      setSidebarCollapsed(true);
      try { localStorage.setItem("visionary:lib_sidebar_collapsed", JSON.stringify(true)); } catch {}
      resetZoom();
    }
  }, [resetZoom, setSidebarCollapsed, setViewMode]);

  // Hook 7: Resolução de caminhos, cards e navegação no SplitView
  const {
    getPreviewUrl,
    currentPageCards,
    jumpToBalloonInSplit,
  } = useLibrarySplitCards({
    viewMode,
    activeFile,
    activePageData,
    parsedPages,
    activePageIndex,
    setActivePageIndex,
    setActiveBlockId,
    setActiveCopiedId,
    changeViewMode,
    blockInputs,
    setBlockInputs,
    setZoomTargetRect,
  });

  // Hook 8: Atalhos globais de teclado
  useLibraryShortcuts({
    isActive,
    activeCopiedId,
    allBalloonsList,
    copiedBlocks,
    activeTab,
    activeFile,
    viewMode,
    setCollapsedPages,
    parsedPages,
    activePageIndex,
    goToPage,
    currentPageCards,
    setActiveCopiedId,
    setActivePageIndex,
    setZoomTargetRect,
    copyBalloon,
    undoCopyBalloon,
    scrollContainerRef: searchInputRef,
  });

  // Métricas de progresso de letreiramento
  const totalBalloons = allBalloonsList.length;
  const copiedBalloons = allBalloonsList.filter((b) => copiedBlocks[b.key]).length;
  const progressPercentage = totalBalloons > 0 ? Math.round((copiedBalloons / totalBalloons) * 100) : 0;

  return {
    // Estado & Store
    activeFile,
    fileContent,
    isLoading,
    viewMode,
    isRawMode,
    sidebarCollapsed,
    setSidebarCollapsed,
    toggleSidebar,
    changeViewMode,
    setViewMode,

    // Páginas & Balões
    parsedPages,
    activePageIndex,
    activePageData,
    currentPageCards,
    collapsedPages,
    setCollapsedPages,
    blockInputs,
    setBlockInputs,

    // Clipboard & Cópia
    copiedBlocks,
    isRawCopied,
    activeCopiedId,
    setActiveCopiedId,
    setActivePageIndex,
    copyBalloon,
    undoCopyBalloon,
    copyFullPage,
    copyRawContent,
    resetProgress,

    // Busca Textual
    searchInputRef,
    activeSearchQuery,
    setActiveSearchQuery,
    searchMatches,
    currentMatchIndex,
    activeMatchKey,
    handlePrevSearchMatch,
    handleNextSearchMatch,
    clearSearch,

    // Abas & Edição de Balões
    activeTab,
    setActiveTab,
    saveBalloonText,

    // Regras Tipográficas
    typographyRules,
    updateTypographyRules,
    isTypographyRulesOpen,
    setIsTypographyRulesOpen,

    // Exportação & Menus
    isExportMenuOpen,
    setIsExportMenuOpen,
    exportScript,
    syncChapterTxt,
    isSyncing,

    // Navegação & Ações
    goToPage,
    jumpToNextPending,
    jumpToBalloonInSplit,
    autoResumePending,
    toggleAutoResume,
    loadLibraryFile,
    deleteLibraryFile,
    refreshLibrary,
    openInExplorer,
    openLibraryFolder,
    openInStudio,
    getPreviewUrl,

    // Métricas
    totalBalloons,
    copiedBalloons,
    progressPercentage,
  };
}
