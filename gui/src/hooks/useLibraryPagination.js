import { useEffect, useCallback, useRef } from "react";
import { useLibraryStore } from "../stores/useLibraryStore";

/**
 * Hook para navegação e automação de páginas do Library:
 * - Navegação direta (goToPage) e salto para páginas pendentes (jumpToNextPending)
 * - Auto-avanço de página (autoTurnPage) quando todos os balões são copiados
 * - Auto-retomada na primeira página pendente (autoResumePending) ao carregar capítulo
 */
export function useLibraryPagination({
  parsedPages = [],
  activePageIndex = 0,
  setActivePageIndex,
  resetZoom,
  viewMode = "script",
  setCollapsedPages,
  lastCopiedId,
  setLastCopiedId,
  copiedBlocks = {},
  activeFile,
  loadCounter,
  addToast,
  setActiveCopiedId,
}) {
  const autoResumePending = useLibraryStore((s) => s.autoResumePending);
  const setAutoResumePending = useLibraryStore((s) => s.setAutoResumePending);
  const autoTurnPage = useLibraryStore((s) => s.autoTurnPage);
  const wheelDelta = useRef(0);

  const toggleAutoResume = useCallback((forceVal) => {
    const next = typeof forceVal === "boolean" ? forceVal : !useLibraryStore.getState().autoResumePending;
    setAutoResumePending(next);
    addToast?.(
      next
        ? "Auto-Retomar ativado: abre direto na primeira página pendente"
        : "Auto-Retomar desativado: abre sempre na Pág. 01",
      "info"
    );
  }, [setAutoResumePending, addToast]);

  const goToPage = useCallback((index) => {
    if (!parsedPages || parsedPages.length === 0) return;
    const targetIdx = Math.max(0, Math.min(parsedPages.length - 1, index));
    if (typeof setActivePageIndex === "function") {
      setActivePageIndex(targetIdx);
    }
    if (typeof resetZoom === "function") {
      resetZoom();
    }

    if (viewMode === "script" && typeof setCollapsedPages === "function") {
      const pageNum = parsedPages[targetIdx]?.pageNumber;
      if (pageNum) {
        setCollapsedPages((prev) => ({ ...prev, [pageNum]: false }));
        setTimeout(() => {
          document.getElementById(`page-card-${pageNum}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 50);
      }
    }
  }, [parsedPages, viewMode, resetZoom, setActivePageIndex, setCollapsedPages]);

  // Auto-avanço ao copiar todos os balões da página atual
  useEffect(() => {
    if (!autoTurnPage || !lastCopiedId || !parsedPages || parsedPages.length === 0) return;

    const [pageStr] = lastCopiedId.split("-");
    const pageNum = parseInt(pageStr, 10);
    const page = parsedPages.find((p) => p.pageNumber === pageNum);

    if (page && page.balloons && page.balloons.length > 0 && page.balloons.every((_, idx) => copiedBlocks[`${pageNum}-${idx}`])) {
      const pageIdx = parsedPages.findIndex((p) => p.pageNumber === pageNum);
      if (pageIdx !== -1 && pageIdx < parsedPages.length - 1 && (viewMode !== "split" || pageIdx === activePageIndex)) {
        const timer = setTimeout(() => {
          goToPage(pageIdx + 1);
          addToast?.(`Avançou para Pág. ${parsedPages[pageIdx + 1].pageNumber} automaticamente`, "info");
          if (typeof setLastCopiedId === "function") {
            setLastCopiedId(null);
          }
        }, 450);
        return () => clearTimeout(timer);
      }
    }
  }, [lastCopiedId, copiedBlocks, parsedPages, autoTurnPage, goToPage, viewMode, activePageIndex, addToast, setLastCopiedId]);

  // Salta para a primeira fala pendente do capítulo
  const jumpToNextPending = useCallback(() => {
    if (!parsedPages || parsedPages.length === 0) return;

    const pageIdx = parsedPages.findIndex((p) =>
      (!p.balloons || p.balloons.length === 0) ? false : p.balloons.some((_, idx) => !copiedBlocks[`${p.pageNumber}-${idx}`])
    );

    if (pageIdx === -1) {
      addToast?.("Todas as falas deste capítulo já foram copiadas!", "info");
      return;
    }

    goToPage(pageIdx);
    const page = parsedPages[pageIdx];
    const balloonIdx = page.balloons.findIndex((_, idx) => !copiedBlocks[`${page.pageNumber}-${idx}`]);

    if (balloonIdx !== -1) {
      const balloonId = `${page.pageNumber}-${balloonIdx}`;
      if (typeof setActiveCopiedId === "function") {
        setActiveCopiedId(balloonId);
      }
      setTimeout(() => {
        const elementId = viewMode === "split" ? `split-balloon-${balloonId}` : `balloon-${balloonId}`;
        document.getElementById(elementId)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }, 100);
    }
    addToast?.(`Saltou para a Pág. ${String(page.pageNumber).padStart(2, "0")} (primeira pendente)`, "info");
  }, [parsedPages, copiedBlocks, goToPage, viewMode, addToast, setActiveCopiedId]);

  // Auto-retoma na primeira página pendente ao carregar o capítulo
  useEffect(() => {
    const currentLoad = loadCounter?.current || 0;
    if (!autoResumePending || !activeFile || parsedPages.length === 0 || currentLoad === 0 || wheelDelta.current === currentLoad) {
      return;
    }
    wheelDelta.current = currentLoad;

    const pageIdx = parsedPages.findIndex((p) =>
      (!p.balloons || p.balloons.length === 0) ? false : p.balloons.some((_, idx) => !copiedBlocks[`${p.pageNumber}-${idx}`])
    );

    if (pageIdx > 0) {
      if (typeof setActivePageIndex === "function") {
        setActivePageIndex(pageIdx);
      }
      if (viewMode === "script" && typeof setCollapsedPages === "function") {
        const pageNum = parsedPages[pageIdx]?.pageNumber;
        if (pageNum) {
          setCollapsedPages((prev) => ({ ...prev, [pageNum]: false }));
          setTimeout(() => {
            document.getElementById(`page-card-${pageNum}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 120);
        }
      }
    }
  }, [parsedPages, autoResumePending, activeFile, copiedBlocks, viewMode, loadCounter, setActivePageIndex, setCollapsedPages]);

  return {
    goToPage,
    jumpToNextPending,
    autoResumePending,
    toggleAutoResume,
  };
}
