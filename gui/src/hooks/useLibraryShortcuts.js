import { useEffect } from "react";
import { useLibraryViewerStore } from "../stores/useLibraryViewerStore";

export function useLibraryShortcuts({
  isActive,
  activeCopiedId,
  allBalloonsList,
  copiedBlocks,
  activeTab,
  activeFile,
  viewMode,
  parsedPages,
  activePageIndex,
  goToPage,
  currentPageCards,
  setActiveCopiedId,
  setActivePageIndex,
  setZoomTargetRect,
  copyBalloon,
  undoCopyBalloon,
  scrollContainerRef,
}) {
  useEffect(() => {
    let handleKeyDown = (e) => {
      if (
        isActive &&
        !(
          ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName) ||
          e.target.isContentEditable ||
          activeTab ||
          !activeFile ||
          (allBalloonsList.length === 0 && !((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f"))
        )
      ) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
          e.preventDefault();
          scrollContainerRef.current?.focus();
          return;
        }
        if (!e.ctrlKey && !e.altKey && !e.metaKey && e.key.toLowerCase() === "z") {
          e.preventDefault();
          let current = useLibraryViewerStore.getState().autoZoomEnabled;
          useLibraryViewerStore.getState().setAutoZoomEnabled(!current);
          return;
        }
        if (!e.ctrlKey && !e.altKey && !e.metaKey && (e.key === "ArrowLeft" || e.key === "[" || e.key === "PageUp")) {
          e.preventDefault();
          goToPage(activePageIndex - 1);
          return;
        }
        if (!e.ctrlKey && !e.altKey && !e.metaKey && (e.key === "ArrowRight" || e.key === "]" || e.key === "PageDown")) {
          e.preventDefault();
          goToPage(activePageIndex + 1);
          return;
        }
        if (
          activeCopiedId &&
          copiedBlocks[activeCopiedId] &&
          (e.key.toLowerCase() === "u" || e.key === "Backspace")
        ) {
          e.preventDefault();
          undoCopyBalloon(activeCopiedId);
          return;
        }
        const isCopyShortcut =
          (!e.ctrlKey && !e.metaKey && !e.altKey && e.key.toLowerCase() === "c") ||
          ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "c" && !window.getSelection()?.toString());

        if (isCopyShortcut) {
          e.preventDefault();
          let targetKey = activeCopiedId;
          let item = targetKey ? allBalloonsList.find((b) => b.key === targetKey) : null;
          if (!item && allBalloonsList.length > 0) {
            item = allBalloonsList.find((b) => !copiedBlocks[b.key]) || allBalloonsList[0];
          }
          if (item) {
            copyBalloon(item.key, item.balloon);
            setActiveCopiedId(item.key);
          }
          return;
        }
        if (e.code === "Space" || e.key === "ArrowDown" || e.key === "Enter") {
          e.preventDefault();
          let nextIdx = 0;
          if (activeCopiedId) {
            let idx = allBalloonsList.findIndex((b) => b.key === activeCopiedId);
            nextIdx = idx !== -1 && idx < allBalloonsList.length - 1 ? idx + 1 : 0;
          } else {
            let idx = allBalloonsList.findIndex((b) => !copiedBlocks[b.key]);
            nextIdx = idx === -1 ? 0 : idx;
          }
          if (allBalloonsList[nextIdx]) {
            let item = allBalloonsList[nextIdx];
            copyBalloon(item.key, item.balloon);
            setActiveCopiedId(item.key);
            if (viewMode === "split") {
              let pageChanged = false;
              if (item.pageNumber) {
                let pIdx = parsedPages.findIndex(
                  (p) => p.pageNumber === item.pageNumber
                );
                if (pIdx !== -1 && pIdx !== activePageIndex) {
                  setActivePageIndex(pIdx);
                  pageChanged = true;
                }
              }
              if (!pageChanged) {
                let card = currentPageCards[item.bIdx];
                if (card) setZoomTargetRect(card);
              }
            }
            setTimeout(() => {
              document
                .getElementById(
                  viewMode === "split"
                    ? `split-balloon-${item.key}`
                    : `balloon-${item.key}`
                )
                ?.scrollIntoView({
                  behavior: "smooth",
                  block: "nearest",
                });
            }, 60);
          }
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          if (!activeCopiedId) return;
          let idx = allBalloonsList.findIndex((b) => b.key === activeCopiedId);
          if (idx > 0) {
            let item = allBalloonsList[idx - 1];
            setActiveCopiedId(item.key);
            if (viewMode === "split") {
              let pageChanged = false;
              if (item.pageNumber) {
                let pIdx = parsedPages.findIndex(
                  (p) => p.pageNumber === item.pageNumber
                );
                if (pIdx !== -1 && pIdx !== activePageIndex) {
                  setActivePageIndex(pIdx);
                  pageChanged = true;
                }
              }
              if (!pageChanged) {
                let card = currentPageCards[item.bIdx];
                if (card) setZoomTargetRect(card);
              }
            }
            setTimeout(() => {
              document
                .getElementById(
                  viewMode === "split"
                    ? `split-balloon-${item.key}`
                    : `balloon-${item.key}`
                )
                ?.scrollIntoView({
                  behavior: "smooth",
                  block: "nearest",
                });
            }, 60);
          }
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    isActive,
    activeCopiedId,
    allBalloonsList,
    copiedBlocks,
    activeTab,
    activeFile,
    viewMode,
    parsedPages,
    activePageIndex,
    goToPage,
    currentPageCards,
    setActiveCopiedId,
    setActivePageIndex,
    setZoomTargetRect,
    copyBalloon,
    undoCopyBalloon,
    scrollContainerRef,
  ]);
}
