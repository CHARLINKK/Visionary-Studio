import React, { useState } from "react";
import { Group, Circle, Path } from "react-konva";

/**
 * Botão flutuante para restaurar o balão para as coordenadas e contorno de detecção iniciais.
 */
export const BubbleResetPositionButton = React.memo(({
  b,
  scale,
  actions,
  onReset,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  const handleReset = (e) => {
    if (e && e.cancelBubble !== undefined) e.cancelBubble = true;
    const st = typeof e?.target?.getStage === "function" ? e.target.getStage() : null;
    if (st) {
      st.container().style.cursor = "default";
      st.container().title = "";
    }

    if (onReset) {
      onReset();
      return;
    }

    if (actions?.resetPosition) {
      actions.resetPosition(b.id);
    }
  };

  return (
    <Group
      id={`btn-reset-${b.id}`}
      x={b.x2 + 14 / scale + 4 / scale}
      y={b.y1 + 14 / scale + 6 / scale}
      onClick={handleReset}
      onMouseEnter={(e) => {
        setIsHovered(true);
        const st = typeof e?.target?.getStage === "function" ? e.target.getStage() : null;
        if (st) {
          st.container().style.cursor = "pointer";
          st.container().title = "Voltar ao local inicial";
        }
      }}
      onMouseLeave={(e) => {
        setIsHovered(false);
        const st = typeof e?.target?.getStage === "function" ? e.target.getStage() : null;
        if (st) {
          st.container().style.cursor = "default";
          st.container().title = "";
        }
      }}
    >
      <Circle
        radius={12 / scale}
        fill={isHovered ? "#0284c7" : "#0369a1"}
        stroke="#ffffff"
        strokeWidth={1.2 / scale}
        shadowColor="rgba(0,0,0,0.5)"
        shadowBlur={isHovered ? 6 / scale : 4 / scale}
        shadowOffset={{ x: 0, y: 2 / scale }}
      />
      <Path
        data="M -9,0 a 9,9 0 1,0 9,-9 a 9.75,9.75 0 0,0 -6.74,2.74 L -9,-4 M -9,-9 L -9,-4 L -4,-4"
        fillEnabled={false}
        fill="transparent"
        stroke="#ffffff"
        strokeWidth={2.4}
        scaleX={0.55 / scale}
        scaleY={0.55 / scale}
        lineCap="round"
        lineJoin="round"
      />
    </Group>
  );
});

BubbleResetPositionButton.displayName = "BubbleResetPositionButton";
