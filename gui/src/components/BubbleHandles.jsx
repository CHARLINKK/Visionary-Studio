import React from "react";
import { Circle } from "react-konva";
import {
  simplifyPolygon,
  computeBboxFromPolygon,
  elasticDeformPolygon,
} from "../utils/polygonGeometry";

/**
 * Alças de manipulação de vértices de polígonos de balões (text_tool ou modo de nós).
 * Suporta modo simplificado (6 a 10 nós mestres via RDP) e modo bruto (todos os vértices).
 */
export const BubblePolygonHandles = React.memo(({
  b,
  scale = 1,
  bgSize,
  actions,
  rawPolygon = false,
  // Props legadas para compatibilidade
  startHistoryTransaction,
  commitHistoryTransaction,
  debouncedHistoryUpdate,
  updateBubbleProperties
}) => {
  // Se rawPolygon for false e o polígono for denso (>10 pontos), simplifica para âncoras mestres limpas
  const activePolygon = React.useMemo(() => {
    if (!b.polygon || !Array.isArray(b.polygon) || b.polygon.length < 3) return [];
    if (!rawPolygon && b.polygon.length > 10) {
      return simplifyPolygon(b.polygon, 0.035, 6, 10);
    }
    return b.polygon;
  }, [b.polygon, rawPolygon]);

  if (activePolygon.length < 3) return null;

  const cw = bgSize?.width || 800;
  const ch = bgSize?.height || 1200;

  const handleUpdate = actions?.update || debouncedHistoryUpdate || updateBubbleProperties;
  const handleFinalUpdate = actions?.update || updateBubbleProperties;

  return (
    <>
      {activePolygon.map((p, pIdx) => (
        <Circle
          key={pIdx}
          x={p[0]}
          y={p[1]}
          radius={6 / (scale || 1)}
          fill="#ffffff"
          stroke="#10b981"
          strokeWidth={2.5 / (scale || 1)}
          shadowColor="rgba(0, 0, 0, 0.35)"
          shadowBlur={3}
          draggable={true}
          onDragStart={(e) => {
            e.cancelBubble = true;
            if (actions?.dragStart) actions.dragStart();
            else if (startHistoryTransaction) startHistoryTransaction();
          }}
          onDragMove={(e) => {
            e.cancelBubble = true;
            const nextPoly = activePolygon.map((pt) => [...pt]);
            nextPoly[pIdx] = [
              Math.max(0, Math.min(cw, e.target.x())),
              Math.max(0, Math.min(ch, e.target.y())),
            ];
            const nextBbox = computeBboxFromPolygon(nextPoly);
            if (handleUpdate) {
              handleUpdate(b.id, {
                polygon: nextPoly,
                ...nextBbox,
              });
            }
          }}
          onDragEnd={(e) => {
            e.cancelBubble = true;
            const nextPoly = activePolygon.map((pt) => [...pt]);
            nextPoly[pIdx] = [
              Math.max(0, Math.min(cw, e.target.x())),
              Math.max(0, Math.min(ch, e.target.y())),
            ];
            const nextBbox = computeBboxFromPolygon(nextPoly);
            if (handleFinalUpdate) {
              handleFinalUpdate(b.id, {
                polygon: nextPoly,
                ...nextBbox,
              });
            }
            if (commitHistoryTransaction) commitHistoryTransaction();
          }}
          onMouseEnter={(e) => {
            const st = e.target.getStage();
            if (st) st.container().style.cursor = "crosshair";
            e.target.radius(8 / (scale || 1));
            const lyr = e.target.getLayer();
            if (lyr) lyr.batchDraw();
          }}
          onMouseLeave={(e) => {
            const st = e.target.getStage();
            if (st) st.container().style.cursor = "default";
            e.target.radius(6 / (scale || 1));
            const lyr = e.target.getLayer();
            if (lyr) lyr.batchDraw();
          }}
        />
      ))}
    </>
  );
});

BubblePolygonHandles.displayName = "BubblePolygonHandles";

/**
 * 8 Alças de redimensionamento da caixa do balão (Padrão Ouro).
 * 4 cantos diagonais + 4 bordas cardinais (topo, base, esquerda, direita).
 * Utiliza deformação elástica (elasticDeformPolygon) para esticar apenas a borda puxada,
 * mantendo as bordas opostas e caudas anatomicas estáveis sem deformar desnecessariamente o contorno.
 */
export const BubbleRectHandles = React.memo(({
  b,
  scale = 1,
  bgSize,
  actions,
  // Props legadas para compatibilidade
  startHistoryTransaction,
  commitHistoryTransaction,
  debouncedHistoryUpdate,
  updateBubbleProperties
}) => {
  const cw = bgSize?.width || 800;
  const ch = bgSize?.height || 1200;

  const handleUpdate = actions?.update || debouncedHistoryUpdate || updateBubbleProperties;
  const handleFinalUpdate = actions?.update || updateBubbleProperties;

  const dragOriginRef = React.useRef(null);

  const minX = Math.min(b.x1, b.x2);
  const maxX = Math.max(b.x1, b.x2);
  const minY = Math.min(b.y1, b.y2);
  const maxY = Math.max(b.y1, b.y2);
  const midX = (minX + maxX) / 2;
  const midY = (minY + maxY) / 2;

  const handles = [
    // 4 cantos diagonais
    { key: "tl", x: minX, y: minY, cursor: "nwse-resize", isEdge: false },
    { key: "tr", x: maxX, y: minY, cursor: "nesw-resize", isEdge: false },
    { key: "bl", x: minX, y: maxY, cursor: "nesw-resize", isEdge: false },
    { key: "br", x: maxX, y: maxY, cursor: "nwse-resize", isEdge: false },
    // 4 bordas cardinais (Padrão Ouro: estica borda específica sem alargar a oposta)
    { key: "t", x: midX, y: minY, cursor: "ns-resize", isEdge: true },
    { key: "b", x: midX, y: maxY, cursor: "ns-resize", isEdge: true },
    { key: "l", x: minX, y: midY, cursor: "ew-resize", isEdge: true },
    { key: "r", x: maxX, y: midY, cursor: "ew-resize", isEdge: true },
  ];

  return (
    <>
      {handles.map((handle) => {
        const baseRadius = (handle.isEdge ? 5 : 6) / (scale || 1);
        return (
          <Circle
            key={handle.key}
            x={handle.x}
            y={handle.y}
            radius={baseRadius}
            fill={handle.isEdge ? "#3b82f6" : "#ffffff"}
            stroke={handle.isEdge ? "#ffffff" : "#2563eb"}
            strokeWidth={(handle.isEdge ? 1.5 : 2) / (scale || 1)}
            shadowColor="rgba(0, 0, 0, 0.35)"
            shadowBlur={3}
            draggable={true}
            onDragStart={(e) => {
              e.cancelBubble = true;
              dragOriginRef.current = {
                x1: minX,
                y1: minY,
                x2: maxX,
                y2: maxY,
                polygon: b.polygon && Array.isArray(b.polygon) && b.polygon.length >= 3
                  ? b.polygon.map((pt) => [...pt])
                  : null,
              };
              if (actions?.dragStart) actions.dragStart();
              else if (startHistoryTransaction) startHistoryTransaction();
            }}
            onDragMove={(e) => {
              e.cancelBubble = true;
              if (!dragOriginRef.current) return;
              const orig = dragOriginRef.current;
              let nx = orig.x1;
              let ny = orig.y1;
              let nx2 = orig.x2;
              let ny2 = orig.y2;

              // Trava ortogonal nas alças de borda e cálculo de limites seguros
              if (handle.key === "t") {
                e.target.x(midX);
                ny = Math.max(0, Math.min(ch, e.target.y()));
              } else if (handle.key === "b") {
                e.target.x(midX);
                ny2 = Math.max(0, Math.min(ch, e.target.y()));
              } else if (handle.key === "l") {
                e.target.y(midY);
                nx = Math.max(0, Math.min(cw, e.target.x()));
              } else if (handle.key === "r") {
                e.target.y(midY);
                nx2 = Math.max(0, Math.min(cw, e.target.x()));
              } else {
                if (handle.key.includes("l")) nx = Math.max(0, Math.min(cw, e.target.x()));
                if (handle.key.includes("r")) nx2 = Math.max(0, Math.min(cw, e.target.x()));
                if (handle.key.includes("t")) ny = Math.max(0, Math.min(ch, e.target.y()));
                if (handle.key.includes("b")) ny2 = Math.max(0, Math.min(ch, e.target.y()));
              }

              const payload = {
                x1: nx,
                y1: ny,
                x2: nx2,
                y2: ny2,
              };

              if (orig.polygon) {
                payload.polygon = elasticDeformPolygon(
                  orig.polygon,
                  orig,
                  { x1: nx, y1: ny, x2: nx2, y2: ny2 }
                );
              }

              if (handleUpdate) {
                handleUpdate(b.id, payload);
              }
            }}
            onDragEnd={(e) => {
              e.cancelBubble = true;
              if (!dragOriginRef.current) return;
              const orig = dragOriginRef.current;

              let nx = orig.x1;
              let ny = orig.y1;
              let nx2 = orig.x2;
              let ny2 = orig.y2;

              if (handle.key === "t") {
                ny = Math.max(0, Math.min(ch, e.target.y()));
              } else if (handle.key === "b") {
                ny2 = Math.max(0, Math.min(ch, e.target.y()));
              } else if (handle.key === "l") {
                nx = Math.max(0, Math.min(cw, e.target.x()));
              } else if (handle.key === "r") {
                nx2 = Math.max(0, Math.min(cw, e.target.x()));
              } else {
                if (handle.key.includes("l")) nx = Math.max(0, Math.min(cw, e.target.x()));
                if (handle.key.includes("r")) nx2 = Math.max(0, Math.min(cw, e.target.x()));
                if (handle.key.includes("t")) ny = Math.max(0, Math.min(ch, e.target.y()));
                if (handle.key.includes("b")) ny2 = Math.max(0, Math.min(ch, e.target.y()));
              }

              const finalX1 = Math.min(nx, nx2);
              const finalX2 = Math.max(nx, nx2);
              const finalY1 = Math.min(ny, ny2);
              const finalY2 = Math.max(ny, ny2);

              const finalPayload = {
                x1: finalX1,
                y1: finalY1,
                x2: finalX2,
                y2: finalY2,
              };

              if (orig.polygon) {
                finalPayload.polygon = elasticDeformPolygon(
                  orig.polygon,
                  orig,
                  { x1: nx, y1: ny, x2: nx2, y2: ny2 }
                );
              }

              dragOriginRef.current = null;
              if (handleFinalUpdate) {
                handleFinalUpdate(b.id, finalPayload);
              }
              if (commitHistoryTransaction) commitHistoryTransaction();
            }}
            onMouseEnter={(e) => {
              const st = e.target.getStage();
              if (st) st.container().style.cursor = handle.cursor;
              e.target.radius((handle.isEdge ? 7 : 8) / (scale || 1));
              const lyr = e.target.getLayer();
              if (lyr) lyr.batchDraw();
            }}
            onMouseLeave={(e) => {
              const st = e.target.getStage();
              if (st) st.container().style.cursor = "default";
              e.target.radius(baseRadius);
              const lyr = e.target.getLayer();
              if (lyr) lyr.batchDraw();
            }}
          />
        );
      })}
    </>
  );
});

BubbleRectHandles.displayName = "BubbleRectHandles";
