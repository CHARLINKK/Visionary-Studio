import { useState, useCallback, useRef, useMemo } from "react";
import { reindexBubbleOrders } from "../utils/bubbleNormalizer";

export function useSeamlessTools({ viewMode, setOcrData, pushHistory }) {
  const [activeTool, setActiveTool] = useState("select");
  const [bubbles, setBubbles] = useState([]);
  const [penPoints, setPenPoints] = useState([]);
  const penPointsRef = useRef([]);
  penPointsRef.current = penPoints;
  const [drawingRect, setDrawingRect] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [selectedBubbleIndex, setSelectedBubbleIndex] = useState(0);
  const [dragStartPos, setDragStartPos] = useState(null);
  const [rectStartPos, setRectStartPos] = useState(null);

  const resetTools = useCallback(() => {
    penPointsRef.current = [];
    setPenPoints([]);
    setDrawingRect(null);
    setDragStartPos(null);
    setRectStartPos(null);
    setBubbles([]);
  }, []);

  const addPenPoint = useCallback(
    (e) => {
      if (viewMode !== "layout" || activeTool !== "pen") return;
      const stage = e.target.getStage();
      const pos = stage.getRelativePointerPosition();
      const point = [pos.x, pos.y];
      const currentPoints = penPointsRef.current;
      const nextPoints = [...currentPoints, point];

      if (nextPoints.length === 4) {
        penPointsRef.current = [];
        setPenPoints([]);
        setOcrData((data) => {
          if (pushHistory) pushHistory(data);
          const res = { ...data };
          const maxId =
            data.boxes && data.boxes.length > 0
              ? Math.max(
                  ...data.boxes.map((b) =>
                    isNaN(parseInt(b.id, 10)) ? 0 : parseInt(b.id, 10)
                  )
                ) + 1
              : 1;
          const newBox = {
            id: maxId,
            order: null,
            x1: Math.round(Math.min(...nextPoints.map((p) => p[0]))),
            y1: Math.round(Math.min(...nextPoints.map((p) => p[1]))),
            x2: Math.round(Math.max(...nextPoints.map((p) => p[0]))),
            y2: Math.round(Math.max(...nextPoints.map((p) => p[1]))),
            polygon: nextPoints.map((p) => [Math.round(p[0]), Math.round(p[1])]),
            is_bubble: true,
            label: "text_tool",
          };
          res.boxes = reindexBubbleOrders([...(res.boxes || []), newBox]);














          return res;
        });
      } else {
        penPointsRef.current = nextPoints;
        setPenPoints(nextPoints);
      }
    },
    [viewMode, activeTool, setOcrData, pushHistory]
  );

  return useMemo(() => ({
    activeTool,
    setActiveTool,
    bubbles,
    setBubbles,
    penPoints,
    setPenPoints,
    drawingRect,
    setDrawingRect,
    mousePos,
    setMousePos,
    selectedBubbleIndex,
    setSelectedBubbleIndex,
    dragStartPos,
    setDragStartPos,
    rectStartPos,
    setRectStartPos,
    resetTools,
    addPenPoint,
  }), [
    activeTool,
    bubbles,
    penPoints,
    drawingRect,
    mousePos,
    selectedBubbleIndex,
    dragStartPos,
    rectStartPos,
    resetTools,
    addPenPoint
  ]);
}
