import React from "react";
import {
  MousePointer2,
  Square,
  Hexagon,
  RotateCcw,
  Plus,
  Minus,
  Target,
  X,
  Sparkles,
  MessageSquare,
  Trash2,
  ListOrdered,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { hasBubbleMoved, isBubbleSfx } from "../../utils/bubbleNormalizer";

/**
 * Painel da Aba 2 do Inspetor de Layout:
 * Propriedades detalhadas do balão selecionado (Modo de Edição, Margem OCR, SFX, Exclusão e Preview).
 */
const LayoutBubblePropertiesPane = React.memo(function LayoutBubblePropertiesPane({
  boxes = [],
  activeBubbleId,
  setActiveBubbleId,
  activeBoxIndex = -1,
  bubbleContourMode = "polygon",
  bubbleEditMode = "box",
  setBubbleEditMode,
  setActiveTab,
  handleNavBubble,
  handleInflateMargin,
  handleResetPosition,
  handleToggleSfx,
  handleDeleteActiveBubble,
  addToast,
}) {
  return (
    <div className="layout-tab-pane properties-pane">
      {activeBubbleId ? (
        (() => {
          const activeBox = boxes[activeBoxIndex];
          if (!activeBox) return null;

          const isSfx = isBubbleSfx(activeBox);
          const hasMoved = hasBubbleMoved(activeBox);
          const hasPolygon = Boolean(
            activeBox.polygon &&
              Array.isArray(activeBox.polygon) &&
              activeBox.polygon.length >= 3
          );
          const boxWidth = Math.round(Math.abs(activeBox.x2 - activeBox.x1));
          const boxHeight = Math.round(Math.abs(activeBox.y2 - activeBox.y1));

          return (
            <div className="layout-active-bubble-card">
              {/* Header de Navegação do Balão */}
              <div className="active-bubble-card-header">
                <div className="active-bubble-badge-group">
                  <button
                    type="button"
                    className="btn-bubble-nav-step"
                    onClick={() => handleNavBubble(-1)}
                    title="Balão anterior (A ou ←)"
                  >
                    <ChevronLeft size={13} />
                  </button>
                  <span className="active-bubble-index">#{activeBoxIndex + 1}</span>
                  <button
                    type="button"
                    className="btn-bubble-nav-step"
                    onClick={() => handleNavBubble(1)}
                    title="Próximo balão (D ou →)"
                  >
                    <ChevronRight size={13} />
                  </button>

                  <span
                    className={`active-bubble-kind-pill ${isSfx ? "sfx" : "bubble"}`}
                  >
                    {isSfx ? "SFX" : "Balão"}
                  </span>
                  <span className="active-bubble-meta-dim">
                    {boxWidth}×{boxHeight}px
                  </span>
                </div>

                <button
                  type="button"
                  className="btn-deselect-bubble"
                  onClick={() => setActiveBubbleId(null)}
                  title="Desmarcar balão (Esc)"
                >
                  <X size={13} />
                </button>
              </div>

              {/* Modo de Edição Segmentado */}
              {hasPolygon && bubbleContourMode === "polygon" && (
                <div className="active-bubble-section">
                  <div className="active-bubble-section-header">
                    <span>Modo de Edição</span>
                  </div>
                  <div
                    className="layout-segmented-track"
                    role="group"
                    aria-label="Modo de edição do balão"
                  >
                    <button
                      type="button"
                      className={`btn-segmented-pill ${!bubbleEditMode || bubbleEditMode === "box" ? "active" : ""}`}
                      onClick={() => {
                        if (setBubbleEditMode) setBubbleEditMode("box");
                        if (addToast) {
                          addToast("Modo Borda & Caixa: use as 8 alças elásticas", "info");
                        }
                      }}
                      title="Modo Borda & Caixa (8 Alças): Redimensione as bordas com deformação elástica natural"
                    >
                      <Square size={12} />
                      <span>Bordas (8)</span>
                    </button>
                    <button
                      type="button"
                      className={`btn-segmented-pill ${bubbleEditMode === "nodes" ? "active" : ""}`}
                      onClick={() => {
                        if (setBubbleEditMode) setBubbleEditMode("nodes");
                        if (addToast) {
                          addToast(
                            "Modo Vértices: arraste os nós mestres do contorno (Esc para sair)",
                            "info"
                          );
                        }
                      }}
                      title="Modo Vértices Mestres (6-8 Nós): Ajuste cirúrgico dos nós do contorno"
                    >
                      <Hexagon size={12} />
                      <span>Vértices</span>
                    </button>
                    <button
                      type="button"
                      className={`btn-segmented-pill ${bubbleEditMode === "raw" ? "active" : ""}`}
                      onClick={() => {
                        if (setBubbleEditMode) setBubbleEditMode("raw");
                        if (addToast) {
                          addToast("Modo Contorno Bruto: todos os pontos OpenCV visíveis", "info");
                        }
                      }}
                      title="Modo Contorno Bruto: Exibe todos os pontos OpenCV originais"
                    >
                      <Target size={12} />
                      <span>Todos Nós</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Margem OCR Rápida */}
              <div className="active-bubble-section">
                <div className="active-bubble-section-header">
                  <span>Margem OCR</span>
                </div>
                <div className="active-bubble-stepper-row">
                  <button
                    type="button"
                    className="btn-stepper-pill expand"
                    onClick={() => handleInflateMargin(activeBubbleId, 6)}
                    title="Expandir margem em +6px para cobrir pontuações e textos cortados"
                  >
                    <Plus size={13} />
                    <span>+6px Margem</span>
                  </button>
                  <button
                    type="button"
                    className="btn-stepper-pill shrink"
                    onClick={() => handleInflateMargin(activeBubbleId, -6)}
                    title="Reduzir margem em -6px para afastar da arte ao redor"
                  >
                    <Minus size={13} />
                    <span>-6px Margem</span>
                  </button>
                </div>
              </div>

              {/* Ações Rápidas (Restaurar, SFX e Deletar) */}
              <div className="active-bubble-actions-row">
                {hasMoved && (
                  <button
                    type="button"
                    className="btn-action-full restore layout-restore-pos-btn"
                    onClick={() => handleResetPosition(activeBubbleId)}
                    title="Voltar o balão para as coordenadas e contorno de detecção originais"
                  >
                    <RotateCcw size={13} />
                    <span>Voltar ao Local Inicial</span>
                  </button>
                )}

                <div className="active-bubble-dual-actions">
                  <button
                    type="button"
                    className={`btn-action-cell sfx ${isSfx ? "restore" : "convert"} layout-toggle-sfx-btn`}
                    onClick={() => handleToggleSfx(activeBubbleId)}
                    title={
                      isSfx
                        ? "Restaurar como balão de fala narrativo"
                        : "Marcar como efeito sonoro / onomatopeia (ignorado no OCR)"
                    }
                  >
                    {isSfx ? (
                      <>
                        <MessageSquare size={13} />
                        <span>Restaurar Balão</span>
                      </>
                    ) : (
                      <>
                        <Sparkles size={13} />
                        <span>Virar SFX</span>
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    className="btn-action-cell delete layout-delete-selected-btn"
                    onClick={handleDeleteActiveBubble}
                    title="Excluir balão da página (Del)"
                  >
                    <Trash2 size={13} />
                    <span>Excluir (Del)</span>
                  </button>
                </div>
              </div>

              {/* Preview de Texto OCR Detectado */}
              {activeBox.text && (
                <div className="active-bubble-section">
                  <div className="active-bubble-section-header">
                    <span>Texto OCR Original</span>
                  </div>
                  <div className="active-bubble-text-preview">
                    <p>{activeBox.text}</p>
                  </div>
                </div>
              )}

              {/* Botão para Retornar à Lista Completa */}
              <button
                type="button"
                className="btn-return-to-list"
                onClick={() => setActiveTab("list")}
              >
                <ListOrdered size={13} />
                <span>Ver Todos os Balões ({boxes.length})</span>
              </button>
            </div>
          );
        })()
      ) : (
        <div className="layout-idle-card full">
          <MousePointer2 size={16} className="layout-idle-icon" />
          <span className="layout-idle-title">Nenhum balão selecionado</span>
          <p className="layout-idle-desc">
            Selecione um balão no canvas ou na lista de leitura para inspecionar contorno, margem OCR e propriedades.
          </p>
          <button
            type="button"
            className="btn-return-to-list"
            onClick={() => setActiveTab("list")}
          >
            <ListOrdered size={13} />
            <span>Ir para Lista de Balões ({boxes.length})</span>
          </button>
        </div>
      )}
    </div>
  );
});

LayoutBubblePropertiesPane.displayName = "LayoutBubblePropertiesPane";

export default LayoutBubblePropertiesPane;
