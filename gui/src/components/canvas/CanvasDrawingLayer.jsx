import React from 'react';
import { Layer, Group, Circle, Line, Rect } from 'react-konva';

/**
 * @typedef {Object} CanvasDrawingLayerProps
 * @property {string} viewMode Modo de visualização ativo ('view'|'layout'|'typeset')
 * @property {string} activeTool Ferramenta ativa selecionada
 * @property {Array<Array<number>>} [penPoints] Lista de coordenadas dos pontos do polígono
 * @property {{ startX: number, startY: number, endX: number, endY: number }|null} [drawingRect] Coordenadas do retângulo em desenho
 * @property {{ x: number, y: number }|null} [mousePos] Posição do cursor do mouse
 * @property {number} [scale] Escala de zoom do canvas
 */

/**
 * Camada Konva de desenho temporário vetorial (caneta e retângulos).
 * @type {React.FC<CanvasDrawingLayerProps>}
 */
export const CanvasDrawingLayer = React.memo(function CanvasDrawingLayer({
  viewMode,
  activeTool,
  penPoints = [],
  drawingRect = null,
  mousePos = null,
  scale = 1,
}) {
  if (viewMode !== 'layout') return null;
  const hasPenPoints = activeTool === 'pen' && penPoints.length > 0;
  const hasDrawingRect = activeTool === 'rect' && drawingRect !== null;

  if (!hasPenPoints && !hasDrawingRect) return null;

  return (
    <Layer id="drawing-preview-layer" listening={false}>
      {hasPenPoints && (
        <Group>
          {penPoints.map((p, idx) => (
            <Circle
              key={idx}
              x={p[0]}
              y={p[1]}
              radius={5 / scale}
              fill="#22ff64"
              stroke="#000000"
              strokeWidth={1.5 / scale}
            />
          ))}
          {mousePos && (
            <Line
              points={[
                ...penPoints.flat(),
                mousePos.x,
                mousePos.y,
              ]}
              stroke="#22ff64"
              strokeWidth={2 / scale}
              dash={[5, 5]}
              fill="rgba(34, 255, 100, 0.2)"
              closed={penPoints.length === 3}
            />
          )}
        </Group>
      )}
      {hasDrawingRect && (
        <Rect
          x={Math.min(drawingRect.startX, drawingRect.endX)}
          y={Math.min(drawingRect.startY, drawingRect.endY)}
          width={Math.abs(drawingRect.endX - drawingRect.startX)}
          height={Math.abs(drawingRect.endY - drawingRect.startY)}
          stroke="#22ff64"
          strokeWidth={2 / scale}
          dash={[5, 5]}
          fill="rgba(34, 255, 100, 0.2)"
        />
      )}
    </Layer>
  );
});
