import React from "react";
import { Group, Circle, Line } from "react-konva";
import { reindexBubbleOrders } from "../utils/bubbleNormalizer";

/**
 * Botão flutuante para exclusão rápida de balão no modo layout.
 */
export const BubbleDeleteButton = React.memo(({
  b,
  scale,
  actions,
  onDelete,
  // Props legadas para compatibilidade
  setOcrData,
  pushHistory,
  setActiveBubbleId
}) => {
  const handleDelete = (e) => {
    e.cancelBubble = true;
    const st = e.target.getStage();
    if (st) st.container().style.cursor = "default";

    if (onDelete) {
      onDelete();
      return;
    }

    if (actions?.delete) {
      actions.delete(b.id, b.group_id);
      return;
    }

    // Fallback legado caso chamado isoladamente sem actions
    if (setOcrData) {
      setOcrData((data) => {
        if (pushHistory) pushHistory(data);
        const next = { ...data };
        if (next.boxes) {
          let filtered = next.boxes.filter((x) => x.id !== b.id);
          if (b.group_id) {
            const remainingInGroup = filtered.filter(
              (x) => x.group_id === b.group_id
            );
            if (remainingInGroup.length === 1) {
              filtered = filtered.map((x) => {
                if (x.group_id === b.group_id) {
                  const { group_id: _group_id, ...rest } = x;
                  return rest;
                }
                return x;
              });
            }
          }
          next.boxes = reindexBubbleOrders(filtered);



        }
        return next;
      });
    }
    if (setActiveBubbleId) {
      setActiveBubbleId(null);
    }
  };

  return (
    <Group
      x={b.x2 + 14 / scale + 4 / scale}
      y={b.y1 - 14 / scale - 4 / scale}
      onClick={handleDelete}
      onMouseEnter={(e) => {
        const st = e.target.getStage();
        if (st) st.container().style.cursor = "pointer";
      }}
      onMouseLeave={(e) => {
        const st = e.target.getStage();
        if (st) st.container().style.cursor = "default";
      }}
    >
      <Circle
        radius={12 / scale}
        fill="#ef4444"
        shadowColor="rgba(0,0,0,0.5)"
        shadowBlur={4 / scale}
        shadowOffset={{ x: 0, y: 2 / scale }}
      />
      <Line
        points={[-5 / scale, -5 / scale, 5 / scale, 5 / scale]}
        stroke="#ffffff"
        strokeWidth={2.5 / scale}
      />
      <Line
        points={[5 / scale, -5 / scale, -5 / scale, 5 / scale]}
        stroke="#ffffff"
        strokeWidth={2.5 / scale}
      />
    </Group>
  );
});

BubbleDeleteButton.displayName = "BubbleDeleteButton";
