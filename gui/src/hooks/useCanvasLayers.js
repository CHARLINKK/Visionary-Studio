import { useCallback, useMemo, useState } from 'react';
import {
  useSeamlessDoc,
  useSeamlessViewport,
  useSeamlessToolsState,
  useSeamlessUi,
} from '../contexts/SeamlessContext';
import { useBubbleActions } from './useBubbleActions';
import { reindexBubbleOrders } from '../utils/bubbleNormalizer';
import { clientApi } from '../api/bridge';

/**
 * Consolida estado do documento, viewport e ferramentas do SeamlessContext para alimentar
 * as camadas do Konva Stage e os callbacks de interação no canvas.
 */
export function useCanvasLayers() {
  const {
    viewMode,
    ocrData,
    setOcrData,
    showOcrDebug,
    activeBubbleId,
    setActiveBubbleId,
    bubbleContourMode,
    setBubbleContourMode,
    bubbleEditMode,
    setBubbleEditMode,
    history,
    overlayVisibility = "all",
    page,
    pageIndex = 0,
    totalPages = 1,
  } = useSeamlessDoc();

  const {
    containerRef,
    stageSize,
    bgImage,
    bgSize,
    zoom,
  } = useSeamlessViewport();

  const {
    tools,
    mousePosRef,
  } = useSeamlessToolsState();

  const { addToast } = useSeamlessUi();

  const {
    scale,
    stagePos,
    setStagePos,
    handleCanvasWheelZoom,
    zoomStateRef,
    hasUserAdjustedZoomRef,
  } = zoom;

  const {
    activeTool,
    drawingRect,
    setDrawingRect,
    penPoints,
    bubbles,
    setBubbles,
    mousePos,
    setMousePos,
    dragStartPos,
    setDragStartPos,
    rectStartPos,
    setRectStartPos,
    addPenPoint,
  } = tools;

  const {
    pushHistory,
    startHistoryTransaction,
    commitHistoryTransaction,
  } = history;

  // Estado do Menu de Contexto (botão direito no canvas/balão)
  const [contextMenu, setContextMenu] = useState(null);

  const openContextMenu = useCallback(({ x, y, targetBubble = null }) => {
    setContextMenu({ x, y, targetBubble });
  }, []);

  const closeContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

  // Controlador centralizado de ações de balão
  const bubbleActions = useBubbleActions({
    setOcrData,
    setActiveBubbleId,
    pushHistory,
    startHistoryTransaction,
    commitHistoryTransaction,
    bgSize,
    tools: {
      dragStartPos,
      setDragStartPos,
      rectStartPos,
      setRectStartPos,
      bubbles,
      setBubbles,
    },
    openContextMenu,
  });

  // Sincroniza a posição final do Stage após pan manual para não resetar no próximo render
  const handleStageDragEnd = useCallback((e) => {
    try {
      if (e.target === e.target.getStage()) {
        const p = { x: e.target.x(), y: e.target.y() };
        if (zoomStateRef && zoomStateRef.current) {
          zoomStateRef.current.position = p;
        }
        if (hasUserAdjustedZoomRef) {
          hasUserAdjustedZoomRef.current = true;
        }
        setStagePos(p);
      }
    } catch (err) {
      console.error('Error in onDragEnd:', err);
    }
  }, [zoomStateRef, hasUserAdjustedZoomRef, setStagePos]);

  const handleStageMouseDown = useCallback((e) => {
    if (contextMenu) {
      closeContextMenu();
    }
    if (mousePosRef) {
      mousePosRef.current = { x: e.evt.clientX, y: e.evt.clientY };
    }
    if (activeTool === 'pen') {
      addPenPoint(e);
    } else if (activeTool === 'rect') {
      const rp = e.target.getStage().getRelativePointerPosition();
      if (rp) {
        setDrawingRect({
          startX: rp.x,
          startY: rp.y,
          endX: rp.x,
          endY: rp.y,
        });
      }
    }
  }, [contextMenu, closeContextMenu, mousePosRef, activeTool, addPenPoint, setDrawingRect]);

  // Ignora cliques após movimento > 5px para não desmarcar o balão ao terminar um pan no canvas
  const handleStageClick = useCallback((e) => {
    const dx = Math.abs(e.evt.clientX - (mousePosRef?.current?.x || 0));
    const dy = Math.abs(e.evt.clientY - (mousePosRef?.current?.y || 0));
    if (dx > 5 || dy > 5) return;
    const t = e.target;
    if (
      t === t.getStage() ||
      t.name?.() === 'bg-image' ||
      t.attrs?.id === 'bg-layer-rect'
    ) {
      setActiveBubbleId(null);
    }
  }, [mousePosRef, setActiveBubbleId]);

  // Handler de clique direito no Stage (área vazia do Canvas)
  const handleStageContextMenu = useCallback((e) => {
    e.evt?.preventDefault();
    if (!e.evt) return;

    const dx = Math.abs((e.evt.clientX || 0) - (mousePosRef?.current?.x || 0));
    const dy = Math.abs((e.evt.clientY || 0) - (mousePosRef?.current?.y || 0));
    if (dx > 6 || dy > 6) return;

    const t = e.target;
    const isStageOrBg =
      !t ||
      t === t.getStage?.() ||
      t.name?.() === 'bg-image' ||
      t.attrs?.id === 'bg-layer-rect' ||
      t.attrs?.id === 'bg-layer' ||
      t.attrs?.id === 'guides-layer';

    if (isStageOrBg) {
      openContextMenu({
        x: e.evt.clientX,
        y: e.evt.clientY,
        targetBubble: null,
      });
    }
  }, [mousePosRef, openContextMenu]);

  // Handler de mouse move para ferramentas de desenho e linking
  const handleStageMouseMove = useCallback((e) => {
    if (
      activeTool !== 'pen' &&
      !(activeTool === 'link' && rectStartPos !== null) &&
      !(activeTool === 'rect' && drawingRect)
    ) {
      return;
    }
    const rp = e.target.getStage().getRelativePointerPosition();
    if (rp) {
      if (
        activeTool === 'pen' ||
        (activeTool === 'link' && rectStartPos !== null)
      ) {
        setMousePos(rp);
      } else if (activeTool === 'rect' && drawingRect) {
        setDrawingRect((prev) =>
          prev ? { ...prev, endX: rp.x, endY: rp.y } : null
        );
      }
    }
  }, [activeTool, rectStartPos, drawingRect, setMousePos, setDrawingRect]);

  // Handler de mouse up para confirmação de nova caixa OCR
  const handleStageMouseUp = useCallback(() => {
    if (activeTool === 'rect' && drawingRect) {
      const x1 = Math.min(drawingRect.startX, drawingRect.endX);
      const x2 = Math.max(drawingRect.startX, drawingRect.endX);
      const y1 = Math.min(drawingRect.startY, drawingRect.endY);
      const y2 = Math.max(drawingRect.startY, drawingRect.endY);
      if (x2 - x1 > 5 && y2 - y1 > 5) {
        setOcrData((data) => {
          if (pushHistory) pushHistory(data);
          const next = { ...data };
          const nextId =
            next.boxes && next.boxes.length > 0
              ? Math.max(
                  ...next.boxes.map((b) =>
                    isNaN(parseInt(b.id, 10)) ? 0 : parseInt(b.id, 10)
                  )
                ) + 1
              : 1;
          const newBox = {
            id: nextId,
            order: null,
            x1: Math.round(x1),
            y1: Math.round(y1),
            x2: Math.round(x2),
            y2: Math.round(y2),
            is_bubble: true,
            label: 'text_tool',
          };
          next.boxes = reindexBubbleOrders([...(next.boxes || []), newBox]);
          return next;
        });
      }
      setDrawingRect(null);
    }
  }, [activeTool, drawingRect, setOcrData, pushHistory, setDrawingRect]);

  // Ação rápida de auto-ordenação de mangá do canvas
  const handleAutoSort = useCallback(() => {
    const rawBoxes = ocrData?.boxes || [];
    if (!rawBoxes.length) return;
    clientApi
      .autoSortBoxes(page?.path, rawBoxes)
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
          addToast?.('Ordem de leitura auto-organizada!', 'success');
        } else {
          addToast?.('Erro ao ordenar: ' + (res?.error || 'Desconhecido'), 'error');
        }
      })
      .catch((err) => addToast?.('Erro na requisição: ' + err.message, 'error'));
  }, [ocrData?.boxes, page?.path, setOcrData, pushHistory, addToast]);

  // Prop bundle do Stage Konva
  const stageProps = useMemo(() => ({
    width: stageSize.width,
    height: stageSize.height,
    onWheel: (e) => {
      closeContextMenu();
      handleCanvasWheelZoom(e);
    },
    scaleX: scale,
    scaleY: scale,
    x: stagePos.x,
    y: stagePos.y,
    draggable: activeTool !== 'pen' && activeTool !== 'rect',
    onDragEnd: handleStageDragEnd,
    onMouseDown: handleStageMouseDown,
    onClick: handleStageClick,
    onTap: handleStageClick,
    onMouseMove: handleStageMouseMove,
    onMouseUp: handleStageMouseUp,
    onContextMenu: handleStageContextMenu,
  }), [
    stageSize.width,
    stageSize.height,
    handleCanvasWheelZoom,
    closeContextMenu,
    scale,
    stagePos.x,
    stagePos.y,
    activeTool,
    handleStageDragEnd,
    handleStageMouseDown,
    handleStageClick,
    handleStageMouseMove,
    handleStageMouseUp,
    handleStageContextMenu,
  ]);

  // Estilo do wrapper de transição do canvas
  const stageWrapperStyle = useMemo(() => ({
    width: '100%',
    height: '100%',
    opacity: 1,
    pointerEvents: 'auto',
  }), []);

  // Bundles limpos para cada camada
  const backgroundProps = useMemo(() => ({
    bgImage,
    bgSize,
  }), [bgImage, bgSize]);

  const filteredBoxes = useMemo(() => {
    const rawBoxes = ocrData?.boxes || [];
    if (overlayVisibility === "clean") return [];
    if (overlayVisibility === "dialogue") return rawBoxes.filter((b) => !b.is_sfx);
    if (overlayVisibility === "sfx") return rawBoxes.filter((b) => b.is_sfx);
    return rawBoxes;
  }, [ocrData?.boxes, overlayVisibility]);

  const guidesProps = useMemo(() => ({
    viewMode,
    boxes: filteredBoxes,
    panels: ocrData?.panels || [],
    activeTool,
    rectStartPos,
    mousePos,
    scale,
    showOcrDebug,
  }), [
    viewMode,
    filteredBoxes,
    ocrData?.panels,
    activeTool,
    rectStartPos,
    mousePos,
    scale,
    showOcrDebug,
  ]);

  const bubblesProps = useMemo(() => ({
    boxes: filteredBoxes,
    scale,
    bgSize,
    viewMode,
    activeTool,
    activeBubbleId,
    dragStartPos,
    rectStartPos,
    bubbles,
    actions: bubbleActions,
    bubbleContourMode,
    bubbleEditMode,
    setBubbleEditMode,
  }), [
    filteredBoxes,
    scale,
    bgSize,
    viewMode,
    activeTool,
    activeBubbleId,
    dragStartPos,
    rectStartPos,
    bubbles,
    bubbleActions,
    bubbleContourMode,
    bubbleEditMode,
    setBubbleEditMode,
  ]);

  const drawingProps = useMemo(() => ({
    viewMode,
    activeTool,
    penPoints,
    drawingRect,
    mousePos,
    scale,
  }), [
    viewMode,
    activeTool,
    penPoints,
    drawingRect,
    mousePos,
    scale,
  ]);

  const contextMenuProps = useMemo(() => {
    if (!contextMenu) return null;
    return {
      isOpen: true,
      x: contextMenu.x,
      y: contextMenu.y,
      targetBubble: contextMenu.targetBubble,
      boxes: ocrData?.boxes || [],
      onClose: closeContextMenu,
      actions: bubbleActions,
      setActiveTool: tools.setActiveTool,
      setBubbleEditMode,
      setBubbleContourMode,
      bubbleContourMode,
      autoZoom: zoom.autoZoom,
      toggleAutoZoom: zoom.toggleAutoZoom,
      fitToScreen: zoom.fitToScreen,
      history,
      handleAutoSort,
      addToast,
      pageIndex,
      totalPages,
    };
  }, [
    contextMenu,
    ocrData?.boxes,
    closeContextMenu,
    bubbleActions,
    tools.setActiveTool,
    setBubbleEditMode,
    setBubbleContourMode,
    bubbleContourMode,
    zoom.autoZoom,
    zoom.toggleAutoZoom,
    zoom.fitToScreen,
    history,
    handleAutoSort,
    addToast,
    pageIndex,
    totalPages,
  ]);

  return {
    containerRef,
    stageWrapperStyle,
    stageProps,
    backgroundProps,
    guidesProps,
    bubblesProps,
    drawingProps,
    contextMenuProps,
  };
}
