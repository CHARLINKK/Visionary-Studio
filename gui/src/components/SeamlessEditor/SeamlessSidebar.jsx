import React, { useCallback } from "react";
import { useSeamlessContext } from "../../contexts/SeamlessContext";
import SeamlessLayoutInspector from "./SeamlessLayoutInspector";
import SeamlessTextInspector from "./SeamlessTextInspector";
import SeamlessOverviewInspector from "./SeamlessOverviewInspector";

export default function SeamlessSidebarContainer() {
  const context = useSeamlessContext();
  const { setOcrData } = context;

  const debouncedHistoryUpdate = useCallback((arg1, arg2) => {
    if (typeof arg1 === "object" && arg1 !== null && arg2 === undefined) {
      setOcrData(arg1);
    } else {
      const bubbleId = arg1;
      const partialProps = arg2;
      setOcrData((data) => {
        const next = { ...data };
        if (next.boxes) {
          next.boxes = next.boxes.map((x) =>
            x.id === bubbleId ? { ...x, ...partialProps } : x
          );
        }
        return next;
      });
    }
  }, [setOcrData]);

  return (
    <div className="editor-sidebar">
      <div className="sidebar-header">
        <h3>Inspetor</h3>
        {context.activeBubbleId !== null && (
          <button
            type="button"
            className="btn-deselect-header"
            onClick={() => context.setActiveBubbleId(null)}
            title="Desmarcar balão ativo (Esc ou clique no fundo)"
          >
            Limpar Seleção
          </button>
        )}
      </div>

      <div className={`sidebar-content ${context.viewMode === "layout" ? "layout-mode" : ""}`}>
        {context.viewMode === "view" && (
          <SeamlessOverviewInspector
            page={context.page}
            bgSize={context.bgSize}
            canEditLayout={context.canEditLayout}
            canEditOcr={context.canEditOcr}
            canEditTranslation={context.canEditTranslation}
            ocrData={context.ocrData}
            setIsRestartModalOpen={context.setIsRestartModalOpen}
            showOcrDebug={context.showOcrDebug}
            setShowOcrDebug={context.setShowOcrDebug}
            setViewMode={context.setViewMode}
            setActiveBubbleId={context.setActiveBubbleId}
            zoomToSpecificBubble={context.zoom?.zoomToSpecificBubble}
            overlayVisibility={context.overlayVisibility}
            setOverlayVisibility={context.setOverlayVisibility}
          />
        )}

        {context.viewMode === "layout" && (
          <SeamlessLayoutInspector
            activeTool={context.tools.activeTool}
            setActiveTool={context.tools.setActiveTool}
            dragStartPos={context.tools.dragStartPos}
            setDragStartPos={context.tools.setDragStartPos}
            activeBubbleId={context.activeBubbleId}
            setActiveBubbleId={context.setActiveBubbleId}
            setDrawingRect={context.tools.setDrawingRect}
            setPenPoints={context.tools.setPenPoints}
            bubbles={context.tools.bubbles}
            setBubbles={context.tools.setBubbles}
            setOcrData={context.setOcrData}
            pushHistory={context.history.pushHistory}
            page={context.page}
            pageIndex={context.pageIndex}
            totalPages={context.totalPages}
            ocrData={context.ocrData}
            zoomToSpecificBubble={context.zoom.zoomToSpecificBubble}
            rectStartPos={context.tools.rectStartPos}
            setRectStartPos={context.tools.setRectStartPos}
            bubbleContourMode={context.bubbleContourMode}
            setBubbleContourMode={context.setBubbleContourMode}
            bubbleEditMode={context.bubbleEditMode}
            setBubbleEditMode={context.setBubbleEditMode}
            bgSize={context.bgSize}
          />
        )}

        {(context.viewMode === "ocr" || context.viewMode === "translation") && (
          <SeamlessTextInspector
            viewMode={context.viewMode}
            canEditLayout={context.canEditLayout}
            canEditOcr={context.canEditOcr}
            canEditTranslation={context.canEditTranslation}
            ocrData={context.ocrData}
            setOcrData={context.setOcrData}
            activeBubbleId={context.activeBubbleId}
            setActiveBubbleId={context.setActiveBubbleId}
            previewSrc={context.previewSrc}
            setPreviewSrc={context.setPreviewSrc}
            zoomToSpecificBubble={context.zoom.zoomToSpecificBubble}
            debouncedHistoryUpdate={debouncedHistoryUpdate}
            pushHistory={context.history.pushHistory}
            startHistoryTransaction={context.history.startHistoryTransaction}
            commitHistoryTransaction={context.history.commitHistoryTransaction}
          />
        )}
      </div>
    </div>
  );
}
