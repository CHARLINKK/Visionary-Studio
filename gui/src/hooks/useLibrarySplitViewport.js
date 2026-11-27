import { useState, useRef, useEffect, useMemo, useCallback } from "react";

export function useLibrarySplitViewport({
  activePageName,
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
}) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [allowTransition, setAllowTransition] = useState(false);

  useEffect(() => {
    setIsReady(false);
    setAllowTransition(false);
  }, [activePageName]);

  const [containerNode, setContainerNode] = useState(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });

  const containerRef = useRef(null);
  const setContainerRef = useCallback((node) => {
    containerRef.current = node;
    setContainerNode(node);
    if (node) {
      const w = node.clientWidth || 0;
      const h = node.clientHeight || 0;
      if (w > 0 && h > 0) {
        setContainerSize({ width: w, height: h });
      }
    }
  }, []);

  const hasValidDimensions = Boolean(
    imageSize.width > 0 &&
    imageSize.height > 0 &&
    (containerSize.width > 0 || containerRef.current?.clientWidth > 0) &&
    (containerSize.height > 0 || containerRef.current?.clientHeight > 0)
  );

  useEffect(() => {
    if (hasValidDimensions) {
      setIsReady(true);
      const timer = setTimeout(() => {
        setAllowTransition(true);
      }, 150);
      return () => clearTimeout(timer);
    } else {
      setIsReady(false);
      setAllowTransition(false);
    }
  }, [hasValidDimensions, activePageName]);

  const transformRef = useRef({ scale: 1, pos: { x: 0, y: 0 } });
  useEffect(() => {
    transformRef.current = { scale: zoomScale, pos: panPos };
  }, [zoomScale, panPos]);

  const autoZoomRef = useRef(autoZoomEnabled);
  useEffect(() => {
    autoZoomRef.current = autoZoomEnabled;
  }, [autoZoomEnabled]);

  const dragStartPos = useRef({ x: 0, y: 0 });
  const lastPanPos = useRef({ x: 0, y: 0 });
  const isDragging = useRef(false);
  const zoomTimeoutRef = useRef(null);

  useEffect(() => {
    if (!containerNode) return;
    const handleResize = () => {
      if (containerNode) {
        setContainerSize({
          width: containerNode.clientWidth || 0,
          height: containerNode.clientHeight || 0,
        });
      }
    };
    handleResize();
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setContainerSize({ width, height });
        }
      }
    });
    observer.observe(containerNode);
    window.addEventListener("resize", handleResize);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", handleResize);
    };
  }, [containerNode]);

  const baseScale = useMemo(() => {
    const node = containerRef.current;
    const w = containerSize.width || node?.clientWidth || 0;
    const h = containerSize.height || node?.clientHeight || 0;
    if (!imageSize.width || !imageSize.height || !w || !h) return 1;
    const mw = Math.max(50, w - 16);
    const mh = Math.max(50, h - 16);
    return Math.min(mw / imageSize.width, mh / imageSize.height);
  }, [imageSize, containerSize]);

  const activeScale = useMemo(() => baseScale * zoomScale, [baseScale, zoomScale]);

  const pendingZoomRectRef = useRef(null);

  const zoomToRect = useCallback(
    (rect, force = false) => {
      const node = containerRef.current;
      const cw = containerSize.width || node?.clientWidth || 0;
      const ch = containerSize.height || node?.clientHeight || 0;
      if (!rect) return;
      if (!force && !autoZoomRef.current) return;
      if (!imageSize.width || !imageSize.height || !cw || !ch) {
        pendingZoomRectRef.current = rect;
        return;
      }
      const cx = (rect.x1 + rect.x2) / 2;
      const cy = (rect.y1 + rect.y2) / 2;
      const ox = cx - imageSize.width / 2;
      const oy = cy - imageSize.height / 2;
      const mw = Math.max(50, cw - 16);
      const mh = Math.max(50, ch - 16);
      const bScale = Math.min(mw / imageSize.width, mh / imageSize.height) * 2;
      const dx = Math.round(-ox * bScale);
      const dy = Math.round(-oy * bScale);
      setZoomScale(2);
      setPanPos({ x: dx, y: dy });
      transformRef.current = { scale: 2, pos: { x: dx, y: dy } };
      pendingZoomRectRef.current = null;
    },
    [imageSize, containerSize, setZoomScale, setPanPos],
  );

  useEffect(() => {
    if (zoomTargetRect) {
      zoomToRect(zoomTargetRect, true);
      setZoomTargetRect(null);
    }
  }, [zoomTargetRect, zoomToRect, setZoomTargetRect]);

  // Quando a imagem terminar de carregar e tiver dimensões válidas, executa o zoom pendente
  useEffect(() => {
    if (pendingZoomRectRef.current && imageSize.width > 0 && imageSize.height > 0) {
      zoomToRect(pendingZoomRectRef.current, true);
    }
  }, [imageSize, zoomToRect]);

  const handleWheelZoom = useCallback(
    (e) => {
      const node = containerRef.current;
      if (!node) return;
      const rect = node.getBoundingClientRect();
      const cw = node.clientWidth || rect.width || containerSize.width;
      const ch = node.clientHeight || rect.height || containerSize.height;
      const iw = imageSize.width;
      const ih = imageSize.height;
      if (!iw || !ih || !cw || !ch) return;
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const centerX = cw / 2;
      const centerY = ch / 2;
      const mw = Math.max(50, cw - 16);
      const mh = Math.max(50, ch - 16);
      const bScale = Math.min(mw / iw, mh / ih);
      const zoomFactor = 1.12;
      const currentScale = transformRef.current.scale;
      const currentPos = transformRef.current.pos;
      const actScale = bScale * currentScale;
      const imgX = (mouseX - centerX - currentPos.x) / actScale;
      const imgY = (mouseY - centerY - currentPos.y) / actScale;
      let newScale = e.deltaY < 0 ? currentScale * zoomFactor : currentScale / zoomFactor;
      newScale = Math.max(0.2, Math.min(newScale, 8));
      const newActiveScale = bScale * newScale;
      const newPos = {
        x: Math.round(mouseX - centerX - imgX * newActiveScale),
        y: Math.round(mouseY - centerY - imgY * newActiveScale),
      };
      setIsFullscreen(true);
      if (zoomTimeoutRef.current) clearTimeout(zoomTimeoutRef.current);
      zoomTimeoutRef.current = setTimeout(() => {
        setIsFullscreen(false);
      }, 120);
      setZoomScale(newScale);
      setPanPos(newPos);
      transformRef.current = { scale: newScale, pos: newPos };
    },
    [imageSize, containerSize, setZoomScale, setPanPos],
  );

  const handleWheelZoomRef = useRef(handleWheelZoom);
  useEffect(() => {
    handleWheelZoomRef.current = handleWheelZoom;
  }, [handleWheelZoom]);

  useEffect(() => {
    if (!containerNode) return;
    const wheelHandler = (e) => {
      e.preventDefault();
      e.stopPropagation();
      handleWheelZoomRef.current?.(e);
    };
    containerNode.addEventListener("wheel", wheelHandler, { passive: false });
    return () => {
      containerNode.removeEventListener("wheel", wheelHandler);
    };
  }, [containerNode]);

  const handlePanStart = useCallback(
    (e) => {
      if (e.button !== 0 && e.button !== 1) return;
      dragStartPos.current = { x: e.clientX, y: e.clientY };
      lastPanPos.current = { ...transformRef.current.pos };
      isDragging.current = false;

      const onMouseMove = (ev) => {
        const dx = ev.clientX - dragStartPos.current.x;
        const dy = ev.clientY - dragStartPos.current.y;
        if (!isDragging.current && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
          isDragging.current = true;
          setIsPanning(true);
        }
        if (isDragging.current) {
          const newPos = {
            x: Math.round(lastPanPos.current.x + dx),
            y: Math.round(lastPanPos.current.y + dy),
          };
          setPanPos(newPos);
          transformRef.current.pos = newPos;
        }
      };

      const onMouseUp = () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
        setIsPanning(false);
        setTimeout(() => {
          isDragging.current = false;
        }, 50);
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [setPanPos, setIsPanning],
  );

  return {
    setContainerRef,
    activeScale,
    panPos,
    isPanning,
    isFullscreen,
    isReady,
    setIsReady,
    hasValidDimensions,
    allowTransition,
    isDragging,
    handlePanStart,
    zoomToRect,
  };
}
