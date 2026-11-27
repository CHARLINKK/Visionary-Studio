import React from "react";
import { useToast } from "../../contexts/ToastContext";
import { clientApi } from "../../api/bridge";
import {
  reindexBubbleOrders,
  getBubbleGroupId,
  stripBubbleGroupId,
  toggleBubbleSfxState,
} from "../../utils/bubbleNormalizer";
import {
  inflatePolygon,
  computeBboxFromPolygon,
} from "../../utils/polygonGeometry";
import LayoutToolsDock from "./LayoutToolsDock";
import LayoutReadingOrderPane from "./LayoutReadingOrderPane";
import LayoutBubblePropertiesPane from "./LayoutBubblePropertiesPane";

const SeamlessLayoutInspector = React.memo(function SeamlessLayoutInspector({
  activeTool,
  setActiveTool,
  dragStartPos = null,
  setDragStartPos,
  activeBubbleId,
  setActiveBubbleId,
  setDrawingRect,
  setPenPoints,
  bubbles,
  setBubbles,
  setOcrData,
  pushHistory,
  page,
  pageIndex = 0,
  totalPages = 1,
  ocrData,
  zoomToSpecificBubble,
  rectStartPos = null,
  setRectStartPos,
  bubbleContourMode = "polygon",
  setBubbleContourMode,
  bubbleEditMode = "box",
  setBubbleEditMode,
  bgSize = { width: 800, height: 1200 },
}) {
  const { addToast } = useToast();
  const boxes = React.useMemo(() => ocrData?.boxes || [], [ocrData?.boxes]);
  const [activeTab, setActiveTab] = React.useState(
    activeBubbleId ? "properties" : "list"
  );
  const [draggedId, setDraggedId] = React.useState(null);
  const [dragOverId, setDragOverId] = React.useState(null);

  React.useEffect(() => {
    if (activeBubbleId) {
      const el = document.getElementById(`panel-block-${activeBubbleId}`);
      if (el && typeof el.scrollIntoView === "function") {
        el.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  }, [activeBubbleId]);

  const activeBoxIndex = boxes.findIndex((x) => x.id === activeBubbleId);

  const realPageW = React.useMemo(() => {
    if (bgSize && bgSize.width > 0) return bgSize.width;
    if (boxes.length > 0) {
      const maxX = Math.max(...boxes.map((x) => Math.max(x.x1 || 0, x.x2 || 0)));
      return Math.max(maxX, 800);
    }
    return 800;
  }, [bgSize, boxes]);

  const realPageH = React.useMemo(() => {
    if (bgSize && bgSize.height > 0) return bgSize.height;
    if (boxes.length > 0) {
      const maxY = Math.max(...boxes.map((x) => Math.max(x.y1 || 0, x.y2 || 0)));
      return Math.max(maxY, 1200);
    }
    return 1200;
  }, [bgSize, boxes]);

  const getBubbleLocationTag = React.useCallback(
    (b) => {
      const minX = Math.min(b.x1 || 0, b.x2 || 0);
      const minY = Math.min(b.y1 || 0, b.y2 || 0);
      const w = Math.abs((b.x2 || 0) - (b.x1 || 0));
      const h = Math.abs((b.y2 || 0) - (b.y1 || 0));
      const cx = (minX + w / 2) / realPageW;
      const cy = (minY + h / 2) / realPageH;

      const vTag = cy < 0.35 ? "Topo" : cy > 0.65 ? "Base" : "Centro";
      const hTag = cx > 0.65 ? "Dir" : cx < 0.35 ? "Esq" : "Centro";

      if (vTag === "Centro" && hTag === "Centro") return "Centro";
      if (vTag === hTag) return vTag;
      return `${vTag} ${hTag}`;
    },
    [realPageW, realPageH]
  );

  const handleNavBubble = (direction) => {
    if (!boxes.length) return;
    let nextIdx = activeBoxIndex + direction;
    if (nextIdx < 0) nextIdx = boxes.length - 1;
    if (nextIdx >= boxes.length) nextIdx = 0;
    const target = boxes[nextIdx];
    if (target) {
      setActiveBubbleId(target.id);
      if (zoomToSpecificBubble) zoomToSpecificBubble(target.id);
    }
  };

  const handleAutoSort = () => {
    if (!boxes.length) return;
    clientApi
      .autoSortBoxes(page?.path, boxes)
      .then((res) => {
        if (res && res.success && res.boxes) {
          setOcrData((data) => {
            if (pushHistory) pushHistory(data);
            const next = { ...data };
            const sortedBoxes = res.boxes.map((b) => ({
              ...(next.boxes?.find((x) => x.id === b.id) || b),
            }));
            next.boxes = reindexBubbleOrders(sortedBoxes);
            if (res.panels && res.panels.length > 0) {
              next.panels = res.panels;
            }
            return next;
          });
          addToast("Ordem de leitura auto-organizada!", "success");
        } else {
          addToast(
            "Erro ao ordenar: " + (res?.error || "Desconhecido"),
            "error"
          );
        }
      })
      .catch((err) =>
        addToast("Erro na requisição: " + err.message, "error")
      );
  };

  const handleDeleteActiveBubble = () => {
    setOcrData((data) => {
      if (pushHistory) pushHistory(data);
      const next = { ...data };
      if (next.boxes) {
        const gId = getBubbleGroupId(
          next.boxes.find((x) => x.id === activeBubbleId)
        );
        let filtered = next.boxes.filter((x) => x.id !== activeBubbleId);
        if (gId && filtered.filter((x) => getBubbleGroupId(x) === gId).length === 1) {
          filtered = filtered.map((x) =>
            getBubbleGroupId(x) === gId ? stripBubbleGroupId(x) : x
          );
        }
        next.boxes = reindexBubbleOrders(filtered);
      }
      return next;
    });
    setActiveBubbleId(null);
  };

  const handleToggleSfx = (targetId) => {
    setOcrData((data) => {
      if (pushHistory) pushHistory(data);
      const next = { ...data };
      if (next.boxes) {
        const updated = next.boxes.map((b) =>
          b.id === targetId ? toggleBubbleSfxState(b) : b
        );
        next.boxes = reindexBubbleOrders(updated);
      }
      return next;
    });
  };

  const handleResetPosition = (targetId) => {
    setOcrData((data) => {
      if (!data?.boxes) return data;
      const target = data.boxes.find((x) => x.id === targetId);
      if (!target) return data;

      const ibox =
        Array.isArray(target.initial_box) && target.initial_box.length === 4
          ? target.initial_box
          : [target.x1, target.y1, target.x2, target.y2];

      const ipoly =
        Array.isArray(target.initial_polygon) &&
        target.initial_polygon.length > 0
          ? target.initial_polygon
          : target.polygon;

      if (pushHistory) pushHistory(data);

      return {
        ...data,
        boxes: data.boxes.map((b) => {
          if (b.id !== targetId) return b;
          return {
            ...b,
            x1: ibox[0],
            y1: ibox[1],
            x2: ibox[2],
            y2: ibox[3],
            polygon: ipoly ? JSON.parse(JSON.stringify(ipoly)) : b.polygon,
          };
        }),
      };
    });
    addToast("Balão restaurado para a posição e contorno iniciais!", "info");
  };

  const handleInflateMargin = (targetId, deltaPx) => {
    setOcrData((data) => {
      if (!data?.boxes) return data;
      const target = data.boxes.find((x) => x.id === targetId);
      if (!target) return data;

      if (pushHistory) pushHistory(data);

      return {
        ...data,
        boxes: data.boxes.map((b) => {
          if (b.id !== targetId) return b;
          if (b.polygon && Array.isArray(b.polygon) && b.polygon.length >= 3) {
            const nextPoly = inflatePolygon(b.polygon, deltaPx);
            const nextBbox = computeBboxFromPolygon(nextPoly);
            return {
              ...b,
              polygon: nextPoly,
              ...nextBbox,
              user_edited: true,
            };
          }
          return {
            ...b,
            x1: Math.max(0, b.x1 - deltaPx),
            y1: Math.max(0, b.y1 - deltaPx),
            x2: Math.max(b.x1 + 10, b.x2 + deltaPx),
            y2: Math.max(b.y1 + 10, b.y2 + deltaPx),
            user_edited: true,
          };
        }),
      };
    });
    addToast(
      deltaPx > 0
        ? "Margem expandida em +6px para o OCR!"
        : "Margem reduzida em -6px!",
      "info"
    );
  };

  return (
    <div className="inspector-section layout-inspector-root">
      <LayoutToolsDock
        activeTool={activeTool}
        setActiveTool={setActiveTool}
        dragStartPos={dragStartPos}
        setDragStartPos={setDragStartPos}
        rectStartPos={rectStartPos}
        setRectStartPos={setRectStartPos}
        bubbles={bubbles}
        setBubbles={setBubbles}
        boxes={boxes}
        activeBubbleId={activeBubbleId}
        setActiveBubbleId={setActiveBubbleId}
        setDrawingRect={setDrawingRect}
        setPenPoints={setPenPoints}
        bubbleContourMode={bubbleContourMode}
        setBubbleContourMode={setBubbleContourMode}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        boxesCount={boxes.length}
        activeBoxIndex={activeBoxIndex}
        addToast={addToast}
      />

      {activeTab === "list" ? (
        <LayoutReadingOrderPane
          boxes={boxes}
          pageIndex={pageIndex}
          totalPages={totalPages}
          activeTool={activeTool}
          setActiveTool={setActiveTool}
          activeBubbleId={activeBubbleId}
          setActiveBubbleId={setActiveBubbleId}
          bubbles={bubbles}
          setBubbles={setBubbles}
          setOcrData={setOcrData}
          pushHistory={pushHistory}
          zoomToSpecificBubble={zoomToSpecificBubble}
          setActiveTab={setActiveTab}
          draggedId={draggedId}
          setDraggedId={setDraggedId}
          dragOverId={dragOverId}
          setDragOverId={setDragOverId}
          realPageW={realPageW}
          realPageH={realPageH}
          getBubbleLocationTag={getBubbleLocationTag}
          handleAutoSort={handleAutoSort}
          handleToggleSfx={handleToggleSfx}
          handleResetPosition={handleResetPosition}
          addToast={addToast}
        />
      ) : (
        <LayoutBubblePropertiesPane
          boxes={boxes}
          activeBubbleId={activeBubbleId}
          setActiveBubbleId={setActiveBubbleId}
          activeBoxIndex={activeBoxIndex}
          bubbleContourMode={bubbleContourMode}
          bubbleEditMode={bubbleEditMode}
          setBubbleEditMode={setBubbleEditMode}
          setActiveTab={setActiveTab}
          handleNavBubble={handleNavBubble}
          handleInflateMargin={handleInflateMargin}
          handleResetPosition={handleResetPosition}
          handleToggleSfx={handleToggleSfx}
          handleDeleteActiveBubble={handleDeleteActiveBubble}
          addToast={addToast}
        />
      )}
    </div>
  );
});

SeamlessLayoutInspector.displayName = "SeamlessLayoutInspector";

export default SeamlessLayoutInspector;
