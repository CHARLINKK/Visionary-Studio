import React from "react";
import { Group, Rect, Line, Text as KonvaText } from "react-konva";
import { BubblePolygonHandles, BubbleRectHandles } from "./BubbleHandles";
import { BubbleBadge } from "./BubbleBadge";
import { BubbleDeleteButton } from "./BubbleDeleteButton";
import { BubbleResetPositionButton } from "./BubbleResetPositionButton";
import {
  hasBubbleMoved,
  isBubbleSfx as checkBubbleSfx,
  getBubbleGroupId,
  getBubbleText,
  getBubbleTranslation,
} from "../utils/bubbleNormalizer";
import { useBubbleActions } from "../hooks/useBubbleActions";

/**
 * @typedef {import('../types/bubble').Bubble} Bubble
 */

/**
 * Componente Konva para renderização interativa de um balão individual.
 * Suporta contornos orgânicos vetoriais (polígonos OpenCV) e caixas retangulares (BBox YOLO).
 * Otimizado com React.memo para evitar re-renderizações em cascata quando
 * a seleção ou ferramentas globais são alteradas.
 */
export const BubbleShape = React.memo(({
  b,
  i,
  scale,
  bgSize,
  totalBubbles = 0,
  viewMode = "layout",
  activeTool = "select",
  // Novas props atômicas e controller
  isSelected: isSelectedProp,
  isReorderSource: isReorderSourceProp,
  isLinkSource: isLinkSourceProp,
  sequenceIndex: sequenceIndexProp,
  actions: actionsProp,
  bubbleContourMode = "polygon",
  bubbleEditMode = "box",
  setBubbleEditMode,
  // Props legadas para compatibilidade
  activeBubbleId,
  setActiveBubbleId,
  dragStartPos,
  setDragStartPos,
  pushHistory,
  startHistoryTransaction,
  commitHistoryTransaction,
  debouncedHistoryUpdate,
  bubbles,
  setBubbles,
  rectStartPos,
  setRectStartPos,
  updateBubbleProperties,
  setOcrData,
}) => {
  // Cria adapter fallback com useBubbleActions caso actions não tenha sido injetado
  const fallbackActions = useBubbleActions(
    actionsProp
      ? undefined
      : {
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
        }
  );

  const actions = actionsProp || fallbackActions;

  const isSelected = isSelectedProp !== undefined
    ? isSelectedProp
    : (activeBubbleId === b.id);

  const isReorderSource = isReorderSourceProp !== undefined
    ? isReorderSourceProp
    : (activeTool === "reorder" && dragStartPos === b.id);

  const isLinkSource = isLinkSourceProp !== undefined
    ? isLinkSourceProp
    : (activeTool === "link" && rectStartPos === b.id);

  const sequenceIndex = sequenceIndexProp !== undefined
    ? sequenceIndexProp
    : (Array.isArray(bubbles) ? bubbles.indexOf(b.id) : -1);

  const [internalEditingNodes, setInternalEditingNodes] = React.useState(false);

  // Se setBubbleEditMode estiver conectado via Context, sincroniza com o inspetor;
  // senão faz fallback para o estado local (testes unitários isolados).
  const isEditingNodes = isSelected && (
    setBubbleEditMode
      ? (bubbleEditMode === "nodes" || bubbleEditMode === "raw")
      : internalEditingNodes
  );

  const isRawNodes = isSelected && (
    setBubbleEditMode
      ? bubbleEditMode === "raw"
      : false
  );

  const toggleNodeEditing = React.useCallback(() => {
    if (setBubbleEditMode) {
      setBubbleEditMode((prev) => (prev === "box" ? "nodes" : "box"));
    } else {
      setInternalEditingNodes((prev) => !prev);
    }
  }, [setBubbleEditMode]);

  const exitNodeEditing = React.useCallback(() => {
    if (setBubbleEditMode) {
      setBubbleEditMode("box");
    } else {
      setInternalEditingNodes(false);
    }
  }, [setBubbleEditMode]);

  React.useEffect(() => {
    if (!isSelected) {
      setInternalEditingNodes(false);
    }
  }, [isSelected]);

  React.useEffect(() => {
    if (!isEditingNodes) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape" || e.key === "Enter") {
        exitNodeEditing();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isEditingNodes, exitNodeEditing]);

  const t = getBubbleText(b);
  const tr = getBubbleTranslation(b);
  const isDeleted = t === "[DELETE]" || tr === "[DELETE]" || checkBubbleSfx(b);

  const handleClick = (e) => {
    e.cancelBubble = true;
    if (viewMode !== "layout") {
      actions.select(b.id);
      return;
    }
    if (activeTool === "select") {
      actions.select(b.id);
    } else if (activeTool === "reorder") {
      actions.reorder(b.id);
    } else if (activeTool === "sequence") {
      actions.sequence(b.id, totalBubbles);
    } else if (activeTool === "link") {
      actions.link(b.id);
    } else if (activeTool === "sfx") {
      actions.toggleSfx(b.id);
    }
  };

  const handleDblClick = (e) => {
    e.cancelBubble = true;
    if (viewMode === "layout" && activeTool === "select" && hasPolygon) {
      toggleNodeEditing();
    }
  };

  const handleContextMenu = (e) => {
    e?.evt?.preventDefault?.();
    e?.preventDefault?.();
    if (e) e.cancelBubble = true;
    const bubbleGroupId = getBubbleGroupId(b);
    if (viewMode === "layout" && activeTool === "link" && bubbleGroupId) {
      actions?.unlink?.(b.id, bubbleGroupId);
      return;
    }
    if (actions?.openContextMenu) {
      if (!isSelected && actions.select) {
        actions.select(b.id);
      }
      actions.openContextMenu({
        x: e.evt.clientX,
        y: e.evt.clientY,
        targetBubble: b,
      });
      return;
    }
  };

  const handleDragStart = (e) => {
    if (viewMode !== "layout") return;
    if (e.target !== e.currentTarget) return;
    e.cancelBubble = true;
    actions.dragStart();
  };

  const handleDragEnd = (e) => {
    if (viewMode !== "layout") return;
    if (e.target !== e.currentTarget) return;
    const dx = e.target.x();
    const dy = e.target.y();
    e.target.x(0);
    e.target.y(0);
    if (Math.hypot(dx, dy) < 4) {
      if (commitHistoryTransaction) commitHistoryTransaction();
      return;
    }
    actions.dragEnd(b, dx, dy);
  };

  const hasPolygon = Boolean(b.polygon && Array.isArray(b.polygon) && b.polygon.length >= 3);
  const isPolygonTextTool = hasPolygon && b.polygon.length === 4 && b.label === "text_tool";
  const isOrganicPolygon = bubbleContourMode === "polygon" && hasPolygon;
  const isPolygon = isPolygonTextTool || isOrganicPolygon;
  const isBubbleSfx = checkBubbleSfx(b);

  return (
    <Group
      key={b.id}
      id={`box-${b.id}`}
      x={0}
      y={0}
      draggable={viewMode === "layout" && activeTool === "select" && isSelected && !isEditingNodes}
      onClick={handleClick}
      onDblClick={handleDblClick}
      onContextMenu={handleContextMenu}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      {viewMode === "layout" &&
        (isPolygon ? (
          <>
            <Line
              points={b.polygon.flat()}
              fill={
                isReorderSource || isLinkSource
                  ? "rgba(245, 158, 11, 0.4)"
                  : isBubbleSfx
                    ? "rgba(168, 85, 247, 0.18)"
                    : isDeleted
                      ? "rgba(239, 68, 68, 0.15)"
                      : isSelected
                        ? "rgba(16, 185, 129, 0.22)"
                        : "rgba(16, 185, 129, 0.08)"
              }
              stroke={
                isEditingNodes
                  ? "#10b981"
                  : isReorderSource || isLinkSource
                    ? "#f59e0b"
                    : isBubbleSfx
                      ? "#a855f7"
                      : isDeleted
                        ? "#ef4444"
                        : isSelected
                          ? "#10b981"
                          : "rgba(16, 185, 129, 0.75)"
              }
              dash={
                isBubbleSfx || isDeleted
                  ? [6 / scale, 4 / scale]
                  : undefined
              }
              strokeWidth={
                (isEditingNodes ? 2.8 : isReorderSource || isLinkSource ? 4 : isSelected ? 2.5 : 1.5) / scale
              }
              closed={true}
            />
            {isSelected && !isPolygonTextTool && !isEditingNodes && (
              <Rect
                x={Math.min(b.x1, b.x2)}
                y={Math.min(b.y1, b.y2)}
                width={Math.abs(b.x2 - b.x1)}
                height={Math.abs(b.y2 - b.y1)}
                fill="transparent"
                stroke="#38bdf8"
                strokeWidth={1.5 / scale}
                dash={[6 / scale, 4 / scale]}
                listening={false}
              />
            )}
            {isSelected && isEditingNodes && (
              <Group
                x={Math.max(0, Math.min(b.x1, b.x2))}
                y={Math.max(0, Math.min(b.y1, b.y2) - 28 / scale)}
                onClick={(e) => {
                  e.cancelBubble = true;
                  exitNodeEditing();
                }}
              >
                <Rect
                  x={0}
                  y={0}
                  width={220 / scale}
                  height={22 / scale}
                  fill="#064e3b"
                  stroke="#10b981"
                  strokeWidth={1.2 / scale}
                  cornerRadius={4 / scale}
                  shadowColor="rgba(0, 0, 0, 0.4)"
                  shadowBlur={4}
                />
                <KonvaText
                  x={8 / scale}
                  y={5 / scale}
                  text={isRawNodes ? "✺ Vértices Brutos • [ Esc ] Concluir" : "⬡ Modo de Vértices • [ Esc ] Concluir"}
                  fontSize={11 / scale}
                  fontFamily="sans-serif"
                  fontStyle="bold"
                  fill="#ecfdf5"
                  listening={false}
                />
              </Group>
            )}
            {isSelected && activeTool === "select" && (
              (isPolygonTextTool || isEditingNodes) ? (
                <BubblePolygonHandles
                  b={b}
                  scale={scale}
                  bgSize={bgSize}
                  actions={actions}
                  rawPolygon={isRawNodes}
                  startHistoryTransaction={startHistoryTransaction}
                  commitHistoryTransaction={commitHistoryTransaction}
                  debouncedHistoryUpdate={debouncedHistoryUpdate}
                  updateBubbleProperties={updateBubbleProperties}
                />
              ) : (
                <BubbleRectHandles
                  b={b}
                  scale={scale}
                  bgSize={bgSize}
                  actions={actions}
                  startHistoryTransaction={startHistoryTransaction}
                  commitHistoryTransaction={commitHistoryTransaction}
                  debouncedHistoryUpdate={debouncedHistoryUpdate}
                  updateBubbleProperties={updateBubbleProperties}
                />
              )
            )}
          </>
        ) : (
          <>
            <Rect
              x={Math.min(b.x1, b.x2)}
              y={Math.min(b.y1, b.y2)}
              width={Math.abs(b.x2 - b.x1)}
              height={Math.abs(b.y2 - b.y1)}
              fill={
                isReorderSource || isLinkSource
                  ? "rgba(245, 158, 11, 0.35)"
                  : isBubbleSfx
                    ? "rgba(168, 85, 247, 0.18)"
                    : isDeleted
                      ? "rgba(239, 68, 68, 0.15)"
                      : isSelected
                        ? "rgba(37, 99, 235, 0.18)"
                        : "rgba(37, 99, 235, 0.08)"
              }
              stroke={
                isReorderSource || isLinkSource
                  ? "#f59e0b"
                  : isBubbleSfx
                    ? "#a855f7"
                    : isDeleted
                      ? "#ef4444"
                      : isSelected
                        ? "#2563eb"
                        : "rgba(37, 99, 235, 0.85)"
              }
              dash={
                isBubbleSfx || isDeleted
                  ? [6 / scale, 4 / scale]
                  : undefined
              }
              strokeWidth={
                (isReorderSource || isLinkSource
                  ? 4
                  : isSelected
                    ? 2.5
                    : 1.8) / scale
              }
              cornerRadius={isSelected ? 3 / scale : 0}
            />
            {isSelected && activeTool === "select" && (
              <BubbleRectHandles
                b={b}
                scale={scale}
                bgSize={bgSize}
                actions={actions}
                startHistoryTransaction={startHistoryTransaction}
                commitHistoryTransaction={commitHistoryTransaction}
                debouncedHistoryUpdate={debouncedHistoryUpdate}
                updateBubbleProperties={updateBubbleProperties}
              />
            )}
          </>
        ))}

      <BubbleBadge
        b={b}
        i={i}
        scale={scale}
        activeTool={activeTool}
        dragStartPos={dragStartPos}
        isDeleted={isDeleted}
        bubbles={bubbles}
        isReorderSource={isReorderSource}
        sequenceIndex={sequenceIndex}
        bubbleContourMode={bubbleContourMode}
      />

      {viewMode !== "layout" && (
        <Group>
          <Rect
            x={Math.min(b.x1, b.x2)}
            y={Math.min(b.y1, b.y2)}
            width={Math.abs(b.x2 - b.x1)}
            height={Math.abs(b.y2 - b.y1)}
            fill="rgba(0, 0, 0, 0.01)"
            stroke={
              isSelected
                ? "#ff2222"
                : isDeleted
                  ? "rgba(245, 158, 11, 0.85)"
                  : "rgba(255, 255, 255, 0.2)"
            }
            strokeWidth={isSelected ? 3 : isDeleted ? 2 : 1}
            dash={
              isDeleted && !isSelected
                ? [
                    4 / Math.max(scale || 1, 0.001),
                    3 / Math.max(scale || 1, 0.001),
                  ]
                : []
            }
            dashEnabled={isDeleted && !isSelected}
            cornerRadius={3}
          />
        </Group>
      )}

      {viewMode === "layout" &&
        activeTool === "select" &&
        isSelected && (
          <>
            {hasBubbleMoved(b) && (
              <BubbleResetPositionButton
                b={b}
                scale={scale}
                actions={actions}
                onReset={() => actions?.resetPosition ? actions.resetPosition(b.id) : undefined}
              />
            )}
            <BubbleDeleteButton
              b={b}
              scale={scale}
              actions={actions}
              onDelete={() => actions.delete(b.id, b.group_id)}
              setOcrData={setOcrData}
              pushHistory={pushHistory}
              setActiveBubbleId={setActiveBubbleId}
            />
          </>
        )}
    </Group>
  );
});

BubbleShape.displayName = "BubbleShape";
