import React from 'react';
import { Layer, Line, Circle, Group, Rect, Text } from 'react-konva';

const LINK_COLORS = [
  "#f59e0b",
  "#06b6d4",
  "#ec4899",
  "#8b5cf6",
  "#10b981",
];

const DEBUG_PANEL_PALETTE = [
  { fill: 'rgba(59, 130, 246, 0.25)', stroke: '#22c55e' }, // P1: Azul
  { fill: 'rgba(239, 68, 68, 0.25)', stroke: '#22c55e' }, // P2: Vermelho
  { fill: 'rgba(16, 185, 129, 0.25)', stroke: '#22c55e' }, // P3: Verde
  { fill: 'rgba(245, 158, 11, 0.25)', stroke: '#22c55e' }, // P4: Âmbar
  { fill: 'rgba(168, 85, 247, 0.25)', stroke: '#22c55e' }, // P5: Roxo
  { fill: 'rgba(236, 72, 153, 0.25)', stroke: '#22c55e' }, // P6: Rosa
  { fill: 'rgba(6, 182, 212, 0.25)', stroke: '#22c55e' }, // P7: Ciano
  { fill: 'rgba(249, 115, 22, 0.25)', stroke: '#22c55e' }, // P8: Laranja
];

/**
 * @typedef {Object} CanvasGuidesLayerProps
 * @property {string} viewMode Modo de visualização ativo ('view'|'layout'|'typeset')
 * @property {Array<Object>} [boxes] Lista de caixas/balões com coordenadas e group_id
 * @property {Array<Object>} [panels] Painéis detectados pelo detector de layout
 * @property {string} [activeTool] Ferramenta selecionada no momento
 * @property {string|number|null} [rectStartPos] ID do balão de origem durante link
 * @property {{ x: number, y: number }|null} [mousePos] Coordenadas atuais do cursor
 * @property {number} [scale] Fator de zoom atual do canvas
 * @property {boolean} [showOcrDebug] Flag indicando se bounding boxes de OCR devem ser exibidas
 */

/**
 * Camada de guias, nós de conexão entre balões e caixas de depuração de OCR.
 * Suporta contornos poligonais inclinados refinados via OpenCV e caixas ortogonais legadas.
 * @type {React.FC<CanvasGuidesLayerProps>}
 */
export const CanvasGuidesLayer = React.memo(function CanvasGuidesLayer({
  viewMode,
  boxes = [],
  panels = [],
  activeTool,
  rectStartPos,
  mousePos,
  scale = 1,
  showOcrDebug = false,
}) {
  if (viewMode === 'view' && !showOcrDebug) {
    return null;
  }

  const nodes = [];

  if (viewMode !== 'view') {
    const groups = {};
    boxes.forEach((b) => {
      if (b.group_id) {
        groups[b.group_id] = groups[b.group_id] || [];
        groups[b.group_id].push(b);
      }
    });

    Object.keys(groups).forEach((key, i) => {
      const gBoxes = groups[key];
      if (gBoxes.length < 2) return;
      const c = LINK_COLORS[i % LINK_COLORS.length];
      for (let j = 0; j < gBoxes.length - 1; j++) {
        const b1 = gBoxes[j];
        const b2 = gBoxes[j + 1];
        const x1 = (b1.x1 + b1.x2) / 2;
        const y1 = (b1.y1 + b1.y2) / 2;
        const x2 = (b2.x1 + b2.x2) / 2;
        const y2 = (b2.y1 + b2.y2) / 2;

        nodes.push(
          <Line
            key={`link-bg-${b1.id}-${b2.id}`}
            points={[x1, y1, x2, y2]}
            stroke={c}
            strokeWidth={8 / scale}
            opacity={0.2}
            lineCap="round"
            tension={0.3}
          />,
          <Line
            key={`link-fg-${b1.id}-${b2.id}`}
            points={[x1, y1, x2, y2]}
            stroke={c}
            strokeWidth={2.5 / scale}
            opacity={0.9}
            lineCap="round"
            tension={0.3}
          />,
          <Circle
            key={`link-node1-${b1.id}`}
            x={x1}
            y={y1}
            radius={5 / scale}
            fill={c}
            opacity={0.95}
          />,
          <Circle
            key={`link-node2-${b2.id}`}
            x={x2}
            y={y2}
            radius={5 / scale}
            fill={c}
            opacity={0.95}
          />,
        );
      }
    });

    if (activeTool === 'link' && rectStartPos !== null && mousePos) {
      const b = boxes.find((e) => e.id === rectStartPos);
      if (b) {
        const bx = (b.x1 + b.x2) / 2;
        const by = (b.y1 + b.y2) / 2;
        if (Math.hypot(mousePos.x - bx, mousePos.y - by) > 20 / scale) {
          nodes.push(
            <Line
              key="link-preview-bg"
              points={[bx, by, mousePos.x, mousePos.y]}
              stroke="#ffffff"
              strokeWidth={6 / scale}
              opacity={0.12}
              lineCap="round"
              tension={0.3}
            />,
            <Line
              key="link-preview-fg"
              points={[bx, by, mousePos.x, mousePos.y]}
              stroke="#f59e0b"
              strokeWidth={2 / scale}
              dash={[8 / scale, 6 / scale]}
              opacity={0.85}
              lineCap="round"
              tension={0.3}
            />,
            <Circle
              key="link-preview-node"
              x={bx}
              y={by}
              radius={5 / scale}
              fill="#f59e0b"
              opacity={0.9}
            />,
          );
        }
      }
    }
  }

  return (
    <Layer id="guides-layer" listening={false}>
      {nodes}
      {showOcrDebug &&
        panels.map((e, t) => {
          const boxCoords =
            Array.isArray(e?.box) && e.box.length >= 4
              ? e.box
              : [e?.x1 || 0, e?.y1 || 0, e?.x2 || 0, e?.y2 || 0];
          const [x, y, w, h] = boxCoords;

          const poly = e?.polygon;
          let flatPoints = null;
          if (Array.isArray(poly) && poly.length >= 3) {
            if (typeof poly[0] === 'number') {
              flatPoints = poly;
            } else if (Array.isArray(poly[0]) || (typeof poly[0] === 'object' && poly[0] !== null)) {
              flatPoints = poly.flatMap((pt) => [
                Number(Array.isArray(pt) ? pt[0] : pt.x ?? 0),
                Number(Array.isArray(pt) ? pt[1] : pt.y ?? 0),
              ]);
            }
          }

          const hasValidPolygon = Array.isArray(flatPoints) && flatPoints.length >= 6;

          let badgeX = x;
          let badgeY = y;

          if (hasValidPolygon) {
            let minX = Infinity;
            let minY = Infinity;
            for (let i = 0; i < flatPoints.length; i += 2) {
              if (flatPoints[i] < minX) minX = flatPoints[i];
              if (flatPoints[i + 1] < minY) minY = flatPoints[i + 1];
            }
            if (minX !== Infinity && minY !== Infinity) {
              badgeX = minX;
              badgeY = minY;
            }
          }

          const colorStyle = DEBUG_PANEL_PALETTE[t % DEBUG_PANEL_PALETTE.length];
          const panelNum = e?.order || e?.id || (t + 1);
          const label = `P${panelNum}`;
          const badgeWidth = label.length > 2 ? 68 : 52;
          const badgeHeight = 30;

          // Posiciona o badge dentro do canto superior esquerdo com margem de 12px
          const badgePosX = badgeX + 12;
          const badgePosY = badgeY + 12;

          return (
            <Group key={`ocr-debug-${t}`}>
              {hasValidPolygon ? (
                <Line
                  points={flatPoints}
                  closed
                  stroke={colorStyle.stroke}
                  strokeWidth={3.5}
                  fill={colorStyle.fill}
                  listening={false}
                />
              ) : (
                <Rect
                  x={x}
                  y={y}
                  width={w - x}
                  height={h - y}
                  stroke={colorStyle.stroke}
                  strokeWidth={3.5}
                  fill={colorStyle.fill}
                  listening={false}
                />
              )}
              {/* Badge Px em cápsula escura de alto contraste com borda verde e texto branco */}
              <Rect
                x={badgePosX}
                y={badgePosY}
                width={badgeWidth}
                height={badgeHeight}
                fill="rgba(15, 23, 42, 0.92)"
                stroke="#22c55e"
                strokeWidth={2}
                cornerRadius={6}
                shadowColor="rgba(0, 0, 0, 0.6)"
                shadowBlur={6}
                shadowOffsetX={0}
                shadowOffsetY={2}
                shadowOpacity={0.8}
                listening={false}
              />
              <Text
                x={badgePosX}
                y={badgePosY + 6}
                width={badgeWidth}
                align="center"
                text={label}
                fontSize={18}
                fill="#ffffff"
                fontStyle="bold"
                listening={false}
              />
            </Group>
          );
        })}
    </Layer>
  );
});
