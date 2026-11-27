import { useState, useRef, useEffect, useCallback, useMemo } from "react";

export function useSeamlessZoom({ containerRef, bgImage, bgSize, ocrDataRef, setActiveBubbleId, addToast }) {
  const [scale, setScale] = useState(1);
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 });
  const zoomStateRef = useRef({ scale: 1, position: { x: 0, y: 0 } });
  const hasUserAdjustedZoomRef = useRef(false);
  const panAnimFrame = useRef(null);

  const [autoZoom, setAutoZoom] = useState(
    () => localStorage.getItem("visionary_auto_zoom") === "true"
  );
  const [autoZoomActive, setAutoZoomActive] = useState(
    () => localStorage.getItem("visionary_auto_zoom") === "true"
  );
  const [autoZoomTranslation, setAutoZoomTranslation] = useState(
    () => localStorage.getItem("visionary_auto_zoom_translation") !== "false"
  );
  const autoZoomRef = useRef(autoZoom);

  useEffect(() => {
    autoZoomRef.current = autoZoom;
  }, [autoZoom]);

  useEffect(() => {
    zoomStateRef.current = { scale, position: stagePos };
  }, [scale, stagePos]);

  useEffect(() => {
    return () => {
      if (panAnimFrame.current) {
        cancelAnimationFrame(panAnimFrame.current);
        panAnimFrame.current = null;
      }
    };
  }, []);

  const toggleAutoZoom = useCallback((val) => {
    const target = typeof val === "boolean" ? val : !autoZoomRef.current;
    setAutoZoom(target);
    setAutoZoomActive(target);
    setAutoZoomTranslation(target);
    autoZoomRef.current = target;
    try {
      localStorage.setItem("visionary_auto_zoom", String(target));
      localStorage.setItem("visionary_auto_zoom_translation", String(target));
    } catch {}
    if (addToast) {
      addToast(target ? "Auto-Zoom ativado" : "Auto-Zoom desativado", "info");
    }
  }, [addToast]);

  const fitToScreen = useCallback(() => {
    if (!containerRef.current || !bgImage) return;
    const cw = containerRef.current.offsetWidth,
      ch = containerRef.current.offsetHeight;
    const iw = bgImage.naturalWidth || bgImage.width || bgSize.width;
    const ih = bgImage.naturalHeight || bgImage.height || bgSize.height;
    if (cw <= 0 || ch <= 0 || iw <= 0 || ih <= 0) return;
    const newScale = Math.max(0.1, Math.min((cw - 80) / iw, (ch - 80) / ih));
    setScale(newScale);
    const newPos = { x: (cw - iw * newScale) / 2, y: (ch - ih * newScale) / 2 };
    setStagePos(newPos);
    zoomStateRef.current = { scale: newScale, position: newPos };
    hasUserAdjustedZoomRef.current = false;
  }, [containerRef, bgImage, bgSize]);

  const handleCanvasWheelZoom = useCallback((e) => {
    e.evt.preventDefault();
    const stage = e.target.getStage();
    if (!stage) return;
    const pointer = stage.getPointerPosition();
    if (!pointer) return;
    hasUserAdjustedZoomRef.current = true;
    const scaleFactor = 1.1;
    const oldScale = zoomStateRef.current.scale;
    const oldPos = zoomStateRef.current.position;
    const mousePointTo = {
      x: pointer.x / oldScale - oldPos.x / oldScale,
      y: pointer.y / oldScale - oldPos.y / oldScale,
    };
    let newScale =
      e.evt.deltaY < 0 ? oldScale * scaleFactor : oldScale / scaleFactor;
    newScale = Math.max(0.1, Math.min(newScale, 10));
    const newPos = {
      x: -(mousePointTo.x - pointer.x / newScale) * newScale,
      y: -(mousePointTo.y - pointer.y / newScale) * newScale,
    };
    zoomStateRef.current = { scale: newScale, position: newPos };
    stage.scale({ x: newScale, y: newScale });
    stage.position(newPos);
    stage.batchDraw();
    if (!panAnimFrame.current) {
      panAnimFrame.current = requestAnimationFrame(() => {
        panAnimFrame.current = null;
        setScale(zoomStateRef.current.scale);
        setStagePos(zoomStateRef.current.position);
      });
    }
  }, []);

  const zoomToSpecificBubble = useCallback((id, boxes = null) => {
    const box = (boxes || (ocrDataRef && ocrDataRef.current ? ocrDataRef.current.boxes : [])).find(
      (b) => b.id === id
    );
    if (
      !box ||
      !containerRef.current ||
      (setActiveBubbleId(id), !autoZoomRef.current)
    )
      return;
    hasUserAdjustedZoomRef.current = true;
    let cx, cy;
    if (box.polygon && box.polygon.length === 4 && box.label === "text_tool") {
      const xs = box.polygon.map((p) => p[0]);
      const ys = box.polygon.map((p) => p[1]);
      cx = (Math.min(...xs) + Math.max(...xs)) / 2;
      cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    } else {
      cx = (box.x1 + box.x2) / 2;
      cy = (box.y1 + box.y2) / 2;
    }
    const cw = containerRef.current.offsetWidth,
      ch = containerRef.current.offsetHeight;
    setScale(2);
    setStagePos({ x: cw / 2 - cx * 2, y: ch / 2 - cy * 2 });
  }, [containerRef, ocrDataRef, setActiveBubbleId]);

  return useMemo(() => ({
    scale,
    setScale,
    stagePos,
    setStagePos,
    zoomStateRef,
    hasUserAdjustedZoomRef,
    autoZoom,
    autoZoomActive,
    autoZoomTranslation,
    toggleAutoZoom,
    fitToScreen,
    handleCanvasWheelZoom,
    zoomToSpecificBubble,
  }), [
    scale,
    stagePos,
    autoZoom,
    autoZoomActive,
    autoZoomTranslation,
    toggleAutoZoom,
    fitToScreen,
    handleCanvasWheelZoom,
    zoomToSpecificBubble
  ]);
}
