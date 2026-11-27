import React, { createContext, useContext, useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { useToast } from '../contexts/ToastContext';
import { useSeamlessTools } from '../hooks/useSeamlessTools';
import { useSeamlessHistory } from '../hooks/useSeamlessHistory';
import { useSeamlessZoom } from '../hooks/useSeamlessZoom';
import { useSeamlessBackend } from '../hooks/useSeamlessBackend';
import { useSeamlessShortcuts } from '../hooks/useSeamlessShortcuts';
import { useSeamlessStage } from '../hooks/useSeamlessStage';
import { useSeamlessModals } from '../hooks/useSeamlessModals';
import { useSeamlessDataLoader } from '../hooks/useSeamlessDataLoader';

const SeamlessDocContext = createContext(null);
const SeamlessViewportContext = createContext(null);
const SeamlessToolsContext = createContext(null);
const SeamlessUiContext = createContext(null);
const SeamlessContext = createContext(null);

// oxlint-disable-next-line react/only-export-components
export function useSeamlessDoc() {
  const context = useContext(SeamlessDocContext);
  if (!context) {
    throw new Error('useSeamlessDoc must be used within a SeamlessProvider');
  }
  return context;
}

// oxlint-disable-next-line react/only-export-components
export function useSeamlessViewport() {
  const context = useContext(SeamlessViewportContext);
  if (!context) {
    throw new Error('useSeamlessViewport must be used within a SeamlessProvider');
  }
  return context;
}

// oxlint-disable-next-line react/only-export-components
export function useSeamlessToolsState() {
  const context = useContext(SeamlessToolsContext);
  if (!context) {
    throw new Error('useSeamlessToolsState must be used within a SeamlessProvider');
  }
  return context;
}

// oxlint-disable-next-line react/only-export-components
export function useSeamlessUi() {
  const context = useContext(SeamlessUiContext);
  if (!context) {
    throw new Error('useSeamlessUi must be used within a SeamlessProvider');
  }
  return context;
}

// oxlint-disable-next-line react/only-export-components
export function useSeamlessContext() {
  const context = useContext(SeamlessContext);
  if (!context) {
    throw new Error('useSeamlessContext must be used within a SeamlessProvider');
  }
  return context;
}

export function SeamlessProvider({
  page,
  initialMode = "layout",
  onNavigate,
  pageIndex,
  totalPages,
  refreshTrigger,
  children
}) {
  const chapterPath = useWorkspaceStore((s) => s.activeChapterPath);
  const isClearingData = useWorkspaceStore((s) => s.isClearingData);
  const clearedDataEvent = useWorkspaceStore((s) => s.clearedDataEvent);
  const { addToast } = useToast();

  // 1. FLAGS DE DADOS DISPONÍVEIS
  const hasLayout = page?.pageData?.layout || false;
  const hasOcr = page?.pageData?.ocr || false;
  const hasTranslation = page?.pageData?.translation || false;

  const [isViewOnlyMode, setIsViewOnlyMode] = useState(false);
  const [saveStatus, setSaveStatus] = useState("saved");
  const [isSyncing, setIsSyncing] = useState(false);

  const saveStatusRef = useRef(saveStatus);
  useEffect(() => { saveStatusRef.current = saveStatus; }, [saveStatus]);

  const canEditLayout = !isViewOnlyMode;
  const canEditOcr = !isViewOnlyMode && hasOcr;
  const canEditTranslation = !isViewOnlyMode && hasTranslation;

  // 2. ESTADOS DO EDITOR & FERRAMENTAS
  const [viewMode, setViewMode] = useState(
    canEditLayout || canEditOcr || canEditTranslation ? initialMode : "view",
  );
  const [activeBubbleId, setActiveBubbleId] = useState(null);
  const [ocrData, setOcrDataRaw] = useState({ boxes: [], panels: [] });
  const [showOcrDebug, setShowOcrDebug] = useState(false);
  const [bubbleContourMode, setBubbleContourModeState] = useState(() => {
    try {
      const saved = localStorage.getItem("visionary_bubble_contour_mode");
      return saved === "box" ? "rect" : (saved || "polygon");
    } catch {
      return "polygon";
    }
  });

  const [bubbleEditMode, setBubbleEditMode] = useState("box"); // "box" | "nodes" | "raw"
  const [overlayVisibility, setOverlayVisibility] = useState("all"); // "all" | "clean" | "dialogue" | "sfx"

  useEffect(() => {
    if (viewMode !== "view") {
      setOverlayVisibility("all");
    }
  }, [viewMode]);

  useEffect(() => {
    setBubbleEditMode("box");
  }, [activeBubbleId]);

  const setBubbleContourMode = useCallback((modeOrUpdater) => {
    setBubbleContourModeState((prev) => {
      const rawNext = typeof modeOrUpdater === "function" ? modeOrUpdater(prev) : modeOrUpdater;
      const next = rawNext === "box" ? "rect" : rawNext;
      try {
        localStorage.setItem("visionary_bubble_contour_mode", next);
      } catch {}
      return next;
    });
  }, []);

  const ocrDataRef = useRef(ocrData);
  useEffect(() => { ocrDataRef.current = ocrData; }, [ocrData]);

  const setOcrData = useCallback((updater) => {
    setOcrDataRaw((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      ocrDataRef.current = next;
      return next;
    });
    if (!useWorkspaceStore.getState().isClearingData) {
      setSaveStatus("unsaved");
    }
  }, []);

  const activeBubbleIdRef = useRef(activeBubbleId);
  useEffect(() => { activeBubbleIdRef.current = activeBubbleId; }, [activeBubbleId]);

  // HOOKS INJETADOS
  const history = useSeamlessHistory(ocrDataRef, setOcrData);
  const tools = useSeamlessTools({ viewMode, setOcrData, pushHistory: history.pushHistory });

  const hasBoxesRef = useRef(false);
  const mousePosRef = useRef({ x: 0, y: 0 });

  const prevPathRef = useRef(page?.path);
  const prevHasLayoutRef = useRef(hasLayout);
  const prevHasOcrRef = useRef(hasOcr);

  useEffect(() => {
    if (!hasLayout && !hasOcr && !hasTranslation && isViewOnlyMode) {
      setIsViewOnlyMode(false);
    }
    setViewMode((curr) => {
      if (curr === "translation" && !hasTranslation)
        return hasOcr ? "ocr" : hasLayout ? "layout" : "view";
      if (curr === "ocr" && !hasOcr) return hasLayout ? "layout" : "view";
      if (curr === "layout" && !hasLayout) return "view";
      return curr;
    });

    if (prevPathRef.current === page?.path) {
      if (!prevHasLayoutRef.current && hasLayout) {
        setIsViewOnlyMode(false);
        setViewMode((c) => (c === "view" ? "layout" : c));
      }
      if (!prevHasOcrRef.current && hasOcr) {
        setIsViewOnlyMode(false);
        setViewMode("ocr");
      }
    }

    prevPathRef.current = page?.path;
    prevHasLayoutRef.current = hasLayout;
    prevHasOcrRef.current = hasOcr;
  }, [page?.path, hasLayout, hasOcr, hasTranslation, isViewOnlyMode]);

  // 3. PALCO (STAGE), ZOOM & CARREGAMENTO DE PÁGINA
  const containerRef = useRef(null);
  const [bgImage, setBgImage] = useState(null);
  const [bgSize, setBgSize] = useState({ width: 800, height: 1200 });

  const zoom = useSeamlessZoom({ containerRef, bgImage, bgSize, ocrDataRef, setActiveBubbleId, addToast });
  const { setScale: setZoomScale, setStagePos: setZoomStagePos, hasUserAdjustedZoomRef, zoomStateRef } = zoom;

  const stage = useSeamlessStage({
    containerRef,
    bgImage,
    setBgImage,
    bgSize,
    setBgSize,
    hasUserAdjustedZoomRef,
    zoomStateRef,
    setZoomScale,
    setZoomStagePos,
  });
  const { stageSize, setStageSize, fitImageToContainer } = stage;

  // Reseta a trava de auto-ajuste de zoom quando a página muda
  useEffect(() => {
    if (hasUserAdjustedZoomRef) {
      hasUserAdjustedZoomRef.current = false;
    }
  }, [page?.path, hasUserAdjustedZoomRef]);

  // 4. DIÁLOGOS E MODAIS
  const modals = useSeamlessModals();

  const {
    previewSrc, setPreviewSrc,
    isRestartModalOpen, setIsRestartModalOpen,
  } = modals;

  // 5. CARREGAMENTO REATIVO DE DADOS DA PÁGINA E OCR
  useSeamlessDataLoader({
    page,
    refreshTrigger,
    bgImage,
    history,
    tools,
    setActiveBubbleId,
    setIsViewOnlyMode,
    setSaveStatus,
    setBgImage,
    setBgSize,
    fitImageToContainer,
    setOcrDataRaw,
    hasBoxesRef,
  });

  const lastCanEditLayoutRef = useRef(canEditLayout);
  const lastCanEditOcrRef = useRef(canEditOcr);
  useEffect(() => {
    if (page?.path) {
      if (!lastCanEditLayoutRef.current && canEditLayout && viewMode === "view") setViewMode("layout");
      if (!lastCanEditOcrRef.current && canEditOcr && viewMode === "view") setViewMode("ocr");
      lastCanEditLayoutRef.current = canEditLayout;
      lastCanEditOcrRef.current = canEditOcr;
    }
  }, [canEditLayout, canEditOcr, viewMode, page?.path]);

  useEffect(() => {
    if (!clearedDataEvent) return;
    const { clearHistory } = history;
    const { resetTools } = tools;
    const affectsPage =
      clearedDataEvent.path === page?.path ||
      (Array.isArray(clearedDataEvent.selectedPaths) && clearedDataEvent.selectedPaths.includes(page?.path)) ||
      (Array.isArray(clearedDataEvent.paths) && clearedDataEvent.paths.includes(page?.path));

    if (affectsPage) {
      setOcrDataRaw({ boxes: [], panels: [] });
      setSaveStatus("saved");
      hasBoxesRef.current = false;
      clearHistory();
      resetTools();
      setActiveBubbleId(null);
      if (canEditLayout) setViewMode("layout");
    }
  }, [clearedDataEvent, page?.path, history.clearHistory, tools.resetTools, canEditLayout]);

  const backend = useSeamlessBackend({
    page,
    chapterPath,
    ocrDataRef,
    hasBoxesRef,
    setSaveStatus,
    setIsSyncing,
    setIsViewOnlyMode,
    setOcrData: setOcrDataRaw,
    addToast,
  });

  const savePageLayout = backend.savePageLayout;
  useEffect(() => {
    if (saveStatus !== "unsaved" || isClearingData || !page?.path) return;
    const timer = setTimeout(() => {
      savePageLayout(true);
    }, 800);
    return () => clearTimeout(timer);
  }, [ocrData, saveStatus, page?.path, savePageLayout, isClearingData]);

  const savePageLayoutRef = useRef(savePageLayout);
  useEffect(() => {
    savePageLayoutRef.current = savePageLayout;
  }, [savePageLayout]);

  const handleNavigate = useCallback(async (dir) => {
    if (saveStatusRef.current === "unsaved" && !useWorkspaceStore.getState().isClearingData) {
      await savePageLayoutRef.current?.(true);
    }
    if (onNavigate) onNavigate(dir);
  }, [onNavigate]);

  useSeamlessShortcuts({
    savePageLayout: backend.savePageLayout,
    handleUndo: history.handleUndo,
    handleRedo: history.handleRedo,
    setActiveBubbleId,
    bubbleEditMode,
    setBubbleEditMode,
    setPenPoints: tools.setPenPoints,
    setDrawingRect: tools.setDrawingRect,
    setDragStartPos: tools.setDragStartPos,
    setRectStartPos: tools.setRectStartPos,
    setBubbles: tools.setBubbles,
    viewMode,
    setActiveTool: tools.setActiveTool,
    canEditLayout,
    canEditOcr,
    canEditTranslation,
    setViewMode,
    toggleAutoZoom: zoom.toggleAutoZoom,
    fitToScreen: zoom.fitToScreen,
    isViewOnlyMode,
    activeBubbleId,
    setOcrData,
    pushHistory: history.pushHistory,
    ocrData,
    zoomToSpecificBubble: zoom.zoomToSpecificBubble,
    addToast,
    onNavigate: onNavigate ? handleNavigate : undefined,
    pageIndex,
    totalPages,
    setSelectedBubbleIndex: tools.setSelectedBubbleIndex
  });

  const docValue = useMemo(() => ({
    page,
    onNavigate: onNavigate ? handleNavigate : undefined,
    pageIndex,
    totalPages,
    refreshTrigger,
    chapterPath,
    hasLayout, hasOcr, hasTranslation,
    isViewOnlyMode, setIsViewOnlyMode,
    saveStatus, setSaveStatus,
    isSyncing, setIsSyncing,
    canEditLayout, canEditOcr, canEditTranslation,
    viewMode, setViewMode,
    activeBubbleId, setActiveBubbleId,
    ocrData, setOcrData, setOcrDataRaw,
    showOcrDebug, setShowOcrDebug,
    bubbleContourMode, setBubbleContourMode,
    bubbleEditMode, setBubbleEditMode,
    overlayVisibility, setOverlayVisibility,
    ocrDataRef, activeBubbleIdRef,
    history, backend
  }), [
    page, onNavigate, handleNavigate, pageIndex, totalPages, refreshTrigger,
    chapterPath, hasLayout, hasOcr, hasTranslation,
    isViewOnlyMode, saveStatus, isSyncing, canEditLayout, canEditOcr, canEditTranslation,
    viewMode, activeBubbleId, ocrData, setOcrData, showOcrDebug,
    bubbleContourMode, setBubbleContourMode,
    bubbleEditMode, setBubbleEditMode,
    overlayVisibility, setOverlayVisibility,
    history, backend
  ]);

  const viewportValue = useMemo(() => ({
    bgImage, setBgImage,
    bgSize, setBgSize,
    stageSize, setStageSize,
    containerRef,
    zoom
  }), [bgImage, bgSize, stageSize, zoom, containerRef, setBgImage, setBgSize, setStageSize]);

  const toolsValue = useMemo(() => ({
    tools,
    hasBoxesRef,
    mousePosRef
  }), [tools]);

  const uiValue = useMemo(() => ({
    previewSrc, setPreviewSrc,
    isRestartModalOpen, setIsRestartModalOpen,
    addToast
  }), [
    previewSrc, setPreviewSrc,
    isRestartModalOpen, setIsRestartModalOpen,
    addToast
  ]);

  const unifiedValue = useMemo(() => ({
    ...docValue,
    ...viewportValue,
    ...toolsValue,
    ...uiValue
  }), [docValue, viewportValue, toolsValue, uiValue]);

  return (
    <SeamlessDocContext.Provider value={docValue}>
      <SeamlessViewportContext.Provider value={viewportValue}>
        <SeamlessToolsContext.Provider value={toolsValue}>
          <SeamlessUiContext.Provider value={uiValue}>
            <SeamlessContext.Provider value={unifiedValue}>
              {children}
            </SeamlessContext.Provider>
          </SeamlessUiContext.Provider>
        </SeamlessToolsContext.Provider>
      </SeamlessViewportContext.Provider>
    </SeamlessDocContext.Provider>
  );
}
