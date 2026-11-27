import React from "react";
import { Group, Circle, Text as KonvaText } from "react-konva";
import { isBubbleSfx } from "../utils/bubbleNormalizer";

/**
 * Badge numérico e indicador de sequência/reordenação do balão.
 */
export const BubbleBadge = React.memo(({
  b,
  i,
  scale,
  activeTool,
  dragStartPos,
  isDeleted,
  bubbles,
  // Novas props atômicas para isolamento de re-render
  isReorderSource,
  sequenceIndex,
  bubbleContourMode = "polygon",
}) => {
  const isReordering = isReorderSource !== undefined
    ? isReorderSource
    : (activeTool === "reorder" && dragStartPos === b.id);

  const seqIndex = sequenceIndex !== undefined
    ? sequenceIndex
    : (Array.isArray(bubbles) ? bubbles.indexOf(b.id) : -1);

  const isSequenceActive = activeTool === "sequence" && seqIndex >= 0;
  const isSfx = isBubbleSfx(b);
  const badgeText = isSfx ? "SFX" : String(b?.order ?? (i + 1));

  return (
    <>
      <Group listening={false}>
        <Circle
          x={b.x1 - 14 / scale - 4 / scale}
          y={b.y1 - 14 / scale - 4 / scale}
          radius={14 / scale}
          fill={
            isReordering ? "#f59e0b" : isSfx ? "#8b5cf6" : isDeleted
              ? "#f59e0b"
              : (bubbleContourMode === "polygon" ? "#10b981" : "#3b82f6")
          }
          stroke="#ffffff"
          strokeWidth={1.5 / scale}
        />
        <KonvaText
          x={b.x1 - 28 / scale - 4 / scale}
          y={b.y1 - 14 / scale - 4 / scale - 6 / scale}
          width={28 / scale}
          align="center"
          text={badgeText}
          fontSize={isSfx ? 10 / scale : 14 / scale}
          fontStyle="bold"
          fill="#ffffff"
        />
      </Group>

      {isSequenceActive && (
        <Group listening={false}>
          <Circle
            x={b.x1 - 14 / scale - 4 / scale}
            y={b.y1 - 14 / scale - 4 / scale}
            radius={14 / scale}
            fill="#a855f7"
            stroke="#ffffff"
            strokeWidth={1.5 / scale}
          />
          <KonvaText
            x={b.x1 - 28 / scale - 4 / scale}
            y={b.y1 - 14 / scale - 4 / scale - 6 / scale}
            width={28 / scale}
            align="center"
            text={`${seqIndex + 1}`}
            fontSize={isSfx ? 10 / scale : 14 / scale}
            fontStyle="bold"
            fill="#ffffff"
          />
        </Group>
      )}
    </>
  );
});

BubbleBadge.displayName = "BubbleBadge";
