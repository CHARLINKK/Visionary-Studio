import React, { useEffect } from "react";
import { RefreshCw, AlertTriangle, FolderOpen, RotateCcw } from "lucide-react";
import { useLibraryViewerStore } from "../../stores/useLibraryViewerStore";
import { useLibraryStore } from "../../stores/useLibraryStore";
import { clientApi } from "../../api/bridge";
import LibraryBalloonRow from "./LibraryBalloonRow";
import LibrarySplitToolbar from "./LibrarySplitToolbar";
import { useLibrarySplitViewport } from "../../hooks/useLibrarySplitViewport";
import { getBubbleText, getBubbleTranslation } from "../../utils/bubbleNormalizer";

export default function LibrarySplitView({
  activeFile,
  activePageData,
  getPreviewUrl,
  currentPageCards,
  copyBalloon,
  undoCopyBalloon,
  activeTab,
  setActiveTab,
  saveBalloonText,
  searchMatches = [],
  activeSearchMatchKey = null,
}) {
  const zoomScale = useLibraryViewerStore((s) => s.zoomScale);
  const setZoomScale = useLibraryViewerStore((s) => s.setZoomScale);
  const panPos = useLibraryViewerStore((s) => s.panPos);
  const setPanPos = useLibraryViewerStore((s) => s.setPanPos);
  const isPanning = useLibraryViewerStore((s) => s.isPanning);
  const setIsPanning = useLibraryViewerStore((s) => s.setIsPanning);
  const autoZoomEnabled = useLibraryViewerStore((s) => s.autoZoomEnabled);
  const showMarkers = useLibraryViewerStore((s) => s.showMarkers);
  const imageSize = useLibraryViewerStore((s) => s.imageSize);
  const setImageSize = useLibraryViewerStore((s) => s.setImageSize);
  const isImageLoading = useLibraryViewerStore((s) => s.isImageLoading);
  const setIsImageLoading = useLibraryViewerStore((s) => s.setIsImageLoading);
  const imageError = useLibraryViewerStore((s) => s.imageError);
  const setImageError = useLibraryViewerStore((s) => s.setImageError);
  const activeBlockId = useLibraryViewerStore((s) => s.activeBlockId);
  const setActiveBlockId = useLibraryViewerStore((s) => s.setActiveBlockId);
  const zoomTargetRect = useLibraryViewerStore((s) => s.zoomTargetRect);
  const setZoomTargetRect = useLibraryViewerStore((s) => s.setZoomTargetRect);

  const copiedBlocks = useLibraryStore((s) => s.copiedBlocks);
  const activeCopiedId = useLibraryStore((s) => s.activeCopiedId);
  const setActiveCopiedId = useLibraryStore((s) => s.setActiveCopiedId);

  const {
    setContainerRef,
    activeScale,
    isFullscreen,
    isReady,
    setIsReady,
    hasValidDimensions,
    allowTransition,
    isDragging,
    handlePanStart,
    zoomToRect,
  } = useLibrarySplitViewport({
    activePageName: activePageData?.pageName,
    imageSize,
    zoomScale,
    setZoomScale,
    panPos,
    setPanPos,
    setIsPanning,
    isPanning,
    autoZoomEnabled,
    zoomTargetRect,
    setZoomTargetRect,
  });

  useEffect(() => {
    if (activePageData?.pageName) {
      setIsImageLoading(true);
      setImageError(false);
    }
  }, [activePageData?.pageName, setIsImageLoading, setImageError]);

  useEffect(() => {
    if (activeCopiedId) {
      const el = document.getElementById(`split-balloon-${activeCopiedId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      } else {
        const timer = setTimeout(() => {
          document.getElementById(`split-balloon-${activeCopiedId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 120);
        return () => clearTimeout(timer);
      }
    }
  }, [activeCopiedId, activePageData?.pageNumber]);

  const openInExplorer = async (folderPath) => {
    if (!folderPath) return;
    try {
      await clientApi.openFileInExplorer(folderPath);
    } catch (err) {
      console.error("Falha ao abrir pasta no Explorer:", err);
    }
  };

  return (
    <div className="library-split-view">
      <div className="split-image-panel">
        <div className="split-floating-canvas-toolbar">
          <LibrarySplitToolbar />
        </div>
        <div
          ref={setContainerRef}
          className={`split-image-viewport ${isPanning ? "is-panning" : ""}`}
          onMouseDown={handlePanStart}
        >
          {isImageLoading && (
            <div className="split-image-loading">
              <RefreshCw size={22} className="spin" />
              <div>Carregando página...</div>
            </div>
          )}
          {imageError ? (
            <div className="split-image-error">
              <AlertTriangle size={36} />
              <div className="error-title">Imagem não encontrada</div>
              <div className="error-filename">{activePageData?.pageName}</div>
              <div className="error-desc">Verifique se o arquivo de imagem está na mesma pasta do capítulo.</div>
              <button
                type="button"
                className="btn-lib-cta secondary"
                onClick={() => openInExplorer(activeFile?.chapter_dir || activeFile?.path)}
              >
                <FolderOpen size={13} /> Abrir Pasta
              </button>
            </div>
          ) : (
            <div
              className="split-zoom-container"
              style={{
                transform: `translate(-50%, -50%) translate(${panPos.x}px, ${panPos.y}px) scale(${activeScale})`,
                transformOrigin: "center center",
                transition: (!allowTransition || isPanning || isFullscreen || !isReady)
                  ? "none"
                  : "transform 0.22s cubic-bezier(0.1, 0.9, 0.2, 1)",
                position: "absolute",
                top: "50%",
                left: "50%",
                width: imageSize.width ? `${imageSize.width}px` : "auto",
                height: imageSize.height ? `${imageSize.height}px` : "auto",
                opacity: isReady && hasValidDimensions ? 1 : 0,
                pointerEvents: isReady && hasValidDimensions ? "auto" : "none",
                "--zoom-scale": activeScale || 1,
              }}
            >
              <div
                className="split-image-wrapper"
                style={
                  imageSize.width
                    ? {
                        width: `${imageSize.width}px`,
                        height: `${imageSize.height}px`,
                        position: "relative",
                        flexShrink: 0,
                      }
                    : {
                        position: "relative",
                      }
                }
              >
                <img
                  ref={(imgNode) => {
                    if (imgNode && imgNode.complete && imgNode.naturalWidth > 0 &&
                      (imageSize.width !== imgNode.naturalWidth || imageSize.height !== imgNode.naturalHeight)) {
                      setImageSize({ width: imgNode.naturalWidth, height: imgNode.naturalHeight });
                      setIsImageLoading(false);
                      setImageError(false);
                    }
                  }}
                  src={getPreviewUrl(activePageData?.pageName)}
                  alt={activePageData?.pageName}
                  className="split-manga-img"
                  draggable={false}
                  style={{
                    width: "100%",
                    height: "100%",
                    display: "block",
                    borderRadius: "4px",
                    boxShadow: "0 4px 24px rgba(0, 0, 0, 0.55)",
                    userSelect: "none",
                    pointerEvents: "none",
                    imageRendering: "high-quality",
                  }}
                  onLoad={(e) => {
                    setImageSize({ width: e.currentTarget.naturalWidth || 1000, height: e.currentTarget.naturalHeight || 1400 });
                    setIsImageLoading(false);
                    setImageError(false);
                  }}
                  onError={() => {
                    setIsImageLoading(false);
                    setImageError(true);
                    setIsReady(true);
                  }}
                />
                {imageSize.width > 0 &&
                  currentPageCards.map((card, idx) => {
                    const balloonIdx =
                      card.id != null
                        ? activePageData?.balloons?.findIndex(
                            (b) => b.id != null && String(b.id) === String(card.id)
                          )
                        : -1;
                    const balloon =
                      balloonIdx !== -1 && balloonIdx != null
                        ? activePageData.balloons[balloonIdx]
                        : activePageData?.balloons?.[idx];
                    const targetIdx = balloonIdx !== -1 && balloonIdx != null ? balloonIdx : idx;
                    const key = `${activePageData.pageNumber}-${targetIdx}`;
                    const isCopied = !!copiedBlocks[key];
                    const isActive = activeCopiedId === key;
                    const isHovered = activeBlockId === targetIdx;
                    const xMin = Math.min(card.x1, card.x2);
                    const yMin = Math.min(card.y1, card.y2);
                    const boxWidth = Math.abs(card.x2 - card.x1);
                    const boxHeight = Math.abs(card.y2 - card.y1);
                    const left = (xMin / imageSize.width) * 100;
                    const top = (yMin / imageSize.height) * 100;
                    const width = (boxWidth / imageSize.width) * 100;
                    const height = (boxHeight / imageSize.height) * 100;
                    const textBR = balloon?.br && balloon.br !== "[PENDENTE]" ? balloon.br : getBubbleTranslation(card);
                    const textEN = balloon?.en || getBubbleText(card);
                    return (
                      <div
                        key={key}
                        className={`balloon-overlay-box ${isCopied ? "copied" : ""} ${isActive ? "active" : ""} ${isHovered ? "hovered" : ""}`}
                        style={{ left: `${left}%`, top: `${top}%`, width: `${width}%`, height: `${height}%` }}
                        onClick={(e) => {
                          if (!isDragging.current) {
                            e.stopPropagation();
                            if (balloon) copyBalloon(key, balloon);
                            else if (textBR || textEN) copyBalloon(key, textBR || textEN);
                            setActiveCopiedId(key);
                            zoomToRect(card);
                            document.getElementById(`split-balloon-${key}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
                          }
                        }}
                        onMouseEnter={() => setActiveBlockId(targetIdx)}
                        onMouseLeave={() => setActiveBlockId(null)}
                      >
                        {showMarkers && <div className="balloon-overlay-badge">{targetIdx + 1}</div>}
                        <div className="balloon-overlay-tooltip">
                          <div className="tooltip-top-row">
                            <div className="tooltip-num">#{targetIdx + 1}</div>
                            {isCopied && (
                              <button
                                type="button"
                                className="tooltip-badge-copied clickable"
                                onClick={(e) => { e.stopPropagation(); undoCopyBalloon(key, e); }}
                                title="Clique para desmarcar cópia"
                              >
                                ✓ Colado <RotateCcw size={9} style={{ marginLeft: 3 }} />
                              </button>
                            )}
                          </div>
                          {textBR && <div className="tooltip-trans-text">{textBR}</div>}
                          {textEN && <div className="tooltip-lang-en"><div>EN:</div> {textEN}</div>}
                          <div className="tooltip-cta-hint">{isCopied ? "Clique para copiar novamente" : "Clique para copiar"}</div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="split-script-panel">
        <div className="split-script-list">
          {activePageData?.balloons?.length === 0 ? (
            <div className="split-empty-balloons">Nenhum balão registrado para esta página no roteiro.</div>
          ) : (
            activePageData?.balloons?.map((balloon, idx) => {
              const rowKey = `${activePageData.pageNumber}-${idx}`;
              const matchingCard =
                (balloon.id != null
                  ? currentPageCards.find(
                      (c) => c.id != null && String(c.id) === String(balloon.id)
                    )
                  : null) || currentPageCards[idx];
              return (
                <LibraryBalloonRow
                  key={rowKey}
                  pageData={activePageData}
                  balloonData={balloon}
                  bIdx={idx}
                  isSplitMode={true}
                  activeTab={activeTab}
                  setActiveTab={setActiveTab}
                  copyBalloon={copyBalloon}
                  undoCopyBalloon={undoCopyBalloon}
                  saveBalloonText={saveBalloonText}
                  currentPageCard={matchingCard}
                  isSearchMatch={searchMatches.includes(rowKey)}
                  isSearchActive={activeSearchMatchKey === rowKey}
                />
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
