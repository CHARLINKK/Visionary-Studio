import React from "react";
import {
  RotateCcw,
  Wand2,
  ListOrdered,
  SlidersHorizontal,
  Zap,
} from "lucide-react";
import {
  reindexBubbleOrders,
  hasBubbleMoved,
  isBubbleSfx,
} from "../../utils/bubbleNormalizer";

/**
 * Painel da Aba 1 do Inspetor de Layout:
 * Lista completa da Ordem de Leitura com Drag & Drop, Auto-Ordenação Mangá e Mini-Map SVG.
 */
const LayoutReadingOrderPane = React.memo(function LayoutReadingOrderPane({
  boxes = [],
  pageIndex = 0,
  totalPages = 1,
  activeTool,
  setActiveTool,
  activeBubbleId,
  setActiveBubbleId,
  bubbles,
  setBubbles,
  setOcrData,
  pushHistory,
  zoomToSpecificBubble,
  setActiveTab,
  draggedId,
  setDraggedId,
  dragOverId,
  setDragOverId,
  realPageW = 800,
  realPageH = 1200,
  getBubbleLocationTag,
  handleAutoSort,
  handleToggleSfx,
  handleResetPosition,
  addToast,
}) {
  return (
    <div className="layout-tab-pane list-pane">
      <div className="layout-nav-header">
        <div className="layout-nav-title-row">
          <div className="layout-nav-heading-group">
            <span className="layout-nav-title">Ordem dos Balões</span>
            <span className="layout-nav-count-badge">{boxes.length}</span>
          </div>
          <span
            className="layout-nav-subtitle"
            title={`Página ${(pageIndex ?? 0) + 1} de ${totalPages || 1}`}
          >
            Pág. {(pageIndex ?? 0) + 1} / {totalPages || 1}
          </span>
        </div>

        <div className="layout-flow-buttons">
          <button
            type="button"
            className="btn-flow auto"
            onClick={handleAutoSort}
            title="Auto-organizar Ordem de Leitura Mangá (Direita para Esquerda / Topo para Base)"
          >
            <Wand2 size={12} className="flow-icon" />
            <span>Auto-Ordenar Mangá</span>
          </button>

          <button
            type="button"
            className={`btn-flow ${activeTool === "sequence" ? "active" : ""}`}
            onClick={() => {
              if (setActiveTool) {
                const nextTool = activeTool === "sequence" ? "select" : "sequence";
                setActiveTool(nextTool);
                if (setActiveBubbleId) setActiveBubbleId(null);
                if (setBubbles) setBubbles([]);
              }
            }}
            title="Modo Sequência: clique nos balões no canvas na ordem desejada"
          >
            <ListOrdered size={12} />
            <span>Marcar 1-a-1</span>
          </button>
        </div>

        {activeTool === "sequence" && bubbles && bubbles.length > 0 && (
          <div className="layout-sequence-queue-banner">
            <span>{bubbles.length} balões na fila</span>
            <button
              type="button"
              className="btn-apply-sequence"
              onClick={() => {
                setOcrData((data) => {
                  if (pushHistory) pushHistory(data);
                  const next = { ...data };
                  const currBoxes = [...(next.boxes || [])];
                  const seqBoxes = bubbles
                    .map((id) => currBoxes.find((x) => x.id === id))
                    .filter(Boolean);
                  const remBoxes = currBoxes.filter(
                    (x) => !bubbles.includes(x.id)
                  );
                  next.boxes = reindexBubbleOrders([...seqBoxes, ...remBoxes]);
                  return next;
                });
                if (setBubbles) setBubbles([]);
                if (addToast) addToast("Sequência aplicada!", "success");
              }}
            >
              Aplicar
            </button>
          </div>
        )}
      </div>

      {/* Lista de Balões com Arrastar e Soltar (Drag & Drop) */}
      <div className="layout-nav-list">
        {boxes.map((b, i) => {
          const isSelected = activeBubbleId === b.id;
          const isSfx = isBubbleSfx(b);
          const moved = hasBubbleMoved(b);
          const snippet = b.text ? b.text.trim() : "";
          const boxWidth = Math.round(Math.abs((b.x2 || 0) - (b.x1 || 0)));
          const boxHeight = Math.round(Math.abs((b.y2 || 0) - (b.y1 || 0)));
          const isDragging = draggedId === b.id;
          const isDragOver = dragOverId === b.id;
          const locTag = getBubbleLocationTag(b);

          return (
            <div
              key={b.id}
              id={`panel-block-${b.id}`}
              className={`balloon-nav-card ${isSelected ? "active" : ""} ${isDragging ? "dragging" : ""} ${isDragOver ? "drag-over" : ""}`}
              draggable={true}
              onDragStart={(e) => {
                setDraggedId(b.id);
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", b.id);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                if (dragOverId !== b.id) {
                  setDragOverId(b.id);
                }
              }}
              onDragLeave={() => {
                if (dragOverId === b.id) {
                  setDragOverId(null);
                }
              }}
              onDrop={(e) => {
                e.preventDefault();
                if (draggedId && draggedId !== b.id) {
                  setOcrData((data) => {
                    if (pushHistory) pushHistory(data);
                    const next = { ...data };
                    if (next.boxes) {
                      const arr = [...next.boxes];
                      const fromIdx = arr.findIndex((x) => x.id === draggedId);
                      const toIdx = arr.findIndex((x) => x.id === b.id);
                      if (fromIdx > -1 && toIdx > -1) {
                        const [movedItem] = arr.splice(fromIdx, 1);
                        arr.splice(toIdx, 0, movedItem);
                      }
                      next.boxes = reindexBubbleOrders(arr);
                    }
                    return next;
                  });
                  if (addToast) addToast("Ordem de leitura atualizada!", "info");
                }
                setDraggedId(null);
                setDragOverId(null);
              }}
              onDragEnd={() => {
                setDraggedId(null);
                setDragOverId(null);
              }}
              onClick={() => {
                setActiveBubbleId(b.id);
                if (zoomToSpecificBubble) zoomToSpecificBubble(b.id);
              }}
              onDoubleClick={() => {
                setActiveBubbleId(b.id);
                setActiveTab("properties");
                if (zoomToSpecificBubble) zoomToSpecificBubble(b.id);
              }}
            >
              {/* Mini-Map Vetorial da Página com Posição Real e Contorno Exato */}
              <div
                className="mini-page-map"
                title={`Posição real na página: ${locTag} (X: ${Math.round(b.x1 || 0)}, Y: ${Math.round(b.y1 || 0)})`}
              >
                <svg
                  className="mini-page-map-svg"
                  viewBox={`0 0 ${realPageW} ${realPageH}`}
                  preserveAspectRatio="xMidYMid meet"
                >
                  {/* Fundo da folha */}
                  <rect
                    x="0"
                    y="0"
                    width={realPageW}
                    height={realPageH}
                    fill="rgba(0, 0, 0, 0.45)"
                  />

                  {/* Exibe estritamente apenas o balão deste bloco com sua posição e contorno real */}
                  {b.polygon && Array.isArray(b.polygon) && b.polygon.length >= 3 ? (
                    <polygon
                      points={b.polygon.map(([px, py]) => `${px},${py}`).join(" ")}
                      fill={isSfx ? "#f59e0b" : "#6366f1"}
                      stroke={isSfx ? "#fbbf24" : "#a5b4fc"}
                      strokeWidth={realPageW * 0.035}
                    />
                  ) : (
                    <rect
                      x={Math.min(b.x1 || 0, b.x2 || 0)}
                      y={Math.min(b.y1 || 0, b.y2 || 0)}
                      width={boxWidth}
                      height={boxHeight}
                      fill={isSfx ? "#f59e0b" : "#6366f1"}
                      stroke={isSfx ? "#fbbf24" : "#a5b4fc"}
                      strokeWidth={realPageW * 0.035}
                      rx={realPageW * 0.015}
                    />
                  )}
                </svg>
              </div>

              <div className="card-v1-info">
                <div className="card-v1-top-row">
                  <span
                    className={`card-v1-title ${!snippet ? "fallback-label" : ""}`}
                    title={
                      snippet ||
                      (isSfx ? `Efeito Sonoro #${i + 1}` : `Balão de Diálogo #${i + 1}`)
                    }
                  >
                    {snippet
                      ? snippet
                      : isSfx
                        ? "Efeito Sonoro (SFX)"
                        : "Balão de Diálogo"}
                  </span>
                  <span className="card-v1-rank">
                    #{String(i + 1).padStart(2, "0")}
                  </span>
                </div>

                <div className="card-v1-bot-row">
                  <div className="card-v1-meta-left">
                    <span className={`card-v1-loc ${isSfx ? "sfx" : ""}`}>
                      {locTag}
                    </span>
                    <span className="card-v1-dim">
                      {boxWidth} × {boxHeight} px
                    </span>
                  </div>

                  <div className="balloon-nav-actions">
                    {isSfx ? (
                      <button
                        type="button"
                        className="balloon-sfx-badge"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleSfx(b.id);
                        }}
                        title="Efeito Sonoro detectado. Clique para converter em Balão de Fala."
                      >
                        <Zap size={10} className="sfx-tag-icon" />
                        <span>SFX</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="balloon-hover-action-btn toggle-sfx"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleSfx(b.id);
                        }}
                        title="Converter em SFX (Efeito Sonoro)"
                      >
                        <Zap size={11} />
                      </button>
                    )}

                    {moved && (
                      <button
                        type="button"
                        className="balloon-hover-action-btn reset-pos"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleResetPosition(b.id);
                        }}
                        title="Restaurar posição e contorno iniciais deste balão"
                      >
                        <RotateCcw size={11} />
                      </button>
                    )}

                    <button
                      type="button"
                      className="balloon-hover-action-btn edit-props"
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveBubbleId(b.id);
                        setActiveTab("properties");
                        if (zoomToSpecificBubble) zoomToSpecificBubble(b.id);
                      }}
                      title="Ajustar propriedades e contorno (ou clique duplo)"
                    >
                      <SlidersHorizontal size={11} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});

LayoutReadingOrderPane.displayName = "LayoutReadingOrderPane";

export default LayoutReadingOrderPane;
