import React from "react";
import {
  MousePointer2,
  Square,
  PenTool,
  Link,
  Hexagon,
  Sparkles,
  ListOrdered,
  SlidersHorizontal,
} from "lucide-react";

/**
 * Barra superior de ferramentas de desenho, alternador de modo de contorno
 * e abas de navegação contextual do Inspetor de Layout.
 */
const LayoutToolsDock = React.memo(function LayoutToolsDock({
  activeTool,
  setActiveTool,
  dragStartPos = null,
  setDragStartPos,
  rectStartPos = null,
  setRectStartPos,
  bubbles = [],
  setBubbles,
  boxes = [],
  activeBubbleId,
  setActiveBubbleId,
  setDrawingRect,
  setPenPoints,
  bubbleContourMode = "polygon",
  setBubbleContourMode,
  activeTab,
  setActiveTab,
  boxesCount = 0,
  activeBoxIndex = -1,
  addToast,
}) {
  const clearTransientToolStates = () => {
    if (setDragStartPos) setDragStartPos(null);
    if (setRectStartPos) setRectStartPos(null);
    if (setBubbles) setBubbles([]);
  };

  const handleCancelActiveTool = () => {
    clearTransientToolStates();
    if (setDrawingRect) setDrawingRect(null);
    if (setPenPoints) setPenPoints([]);
    if (setActiveTool) setActiveTool("select");
  };

  let stepHint = null;
  if (activeTool === "link") {
    if (rectStartPos == null) {
      stepHint = "Unir [CORTE] · 1/2: clique no 1º balão no canvas";
    } else {
      const originIdx = boxes.findIndex((b) => b.id === rectStartPos);
      const originLabel = originIdx >= 0 ? `#${originIdx + 1}` : String(rectStartPos);
      stepHint = `Unir [CORTE] · 2/2: ${originLabel} marcado — clique no 2º balão`;
    }
  } else if (activeTool === "reorder") {
    if (dragStartPos == null) {
      stepHint = "Reordenar (R) · 1/2: clique no balão de origem";
    } else {
      const originIdx = boxes.findIndex((b) => b.id === dragStartPos);
      const originLabel = originIdx >= 0 ? `#${originIdx + 1}` : String(dragStartPos);
      stepHint = `Reordenar (R) · 2/2: movendo ${originLabel} — clique no destino`;
    }
  } else if (activeTool === "sfx") {
    stepHint = "Modo SFX · Clique nos balões para alternar Fala ⇄ SFX";
  } else if (activeTool === "sequence") {
    const queued = Array.isArray(bubbles) ? bubbles.length : 0;
    stepHint = `Sequência 1-a-1 · Clique na ordem de leitura (${queued}/${boxesCount})`;
  }

  return (
    <>
      {/* 1. Toolbar de Desenho & Contorno (Dock de Ícones Limpo - Padrão Figma) */}
      <div className="layout-tools-panel">
        <div className="layout-tools-primary-row" role="toolbar" aria-label="Ferramentas de desenho">
          <button
            type="button"
            className={`btn-layout-dock ${activeTool === "select" ? "active" : ""}`}
            onClick={() => {
              if (setActiveTool) setActiveTool("select");
              clearTransientToolStates();
            }}
            title="Seleção — Selecionar e mover balões (V)"
            aria-label="Seleção (V)"
            aria-pressed={activeTool === "select"}
          >
            <MousePointer2 size={16} />
          </button>

          <button
            type="button"
            className={`btn-layout-dock ${activeTool === "rect" ? "active" : ""}`}
            onClick={() => {
              if (setActiveTool) setActiveTool("rect");
              clearTransientToolStates();
              if (setActiveBubbleId) setActiveBubbleId(null);
              if (setDrawingRect) setDrawingRect(null);
            }}
            title="Retângulo — Desenhar caixa retangular (B)"
            aria-label="Retângulo (B)"
            aria-pressed={activeTool === "rect"}
          >
            <Square size={16} />
          </button>

          <button
            type="button"
            className={`btn-layout-dock ${activeTool === "pen" ? "active" : ""}`}
            onClick={() => {
              if (setActiveTool) setActiveTool("pen");
              clearTransientToolStates();
              if (setActiveBubbleId) setActiveBubbleId(null);
              if (setPenPoints) setPenPoints([]);
            }}
            title="Caneta — Desenhar balão livre (P)"
            aria-label="Caneta (P)"
            aria-pressed={activeTool === "pen"}
          >
            <PenTool size={16} />
          </button>

          <button
            type="button"
            className={`btn-layout-dock ${activeTool === "link" ? "active" : ""}`}
            onClick={() => {
              if (setActiveTool) setActiveTool("link");
              clearTransientToolStates();
              if (setActiveBubbleId) setActiveBubbleId(null);
            }}
            title="Unir — Vincular grupo de balões [CORTE] (L)"
            aria-label="Unir (L)"
            aria-pressed={activeTool === "link"}
          >
            <Link size={16} />
          </button>

          <button
            type="button"
            className={`btn-layout-dock ${activeTool === "sfx" ? "active" : ""}`}
            onClick={() => {
              if (setActiveTool) setActiveTool("sfx");
              clearTransientToolStates();
              if (setActiveBubbleId) setActiveBubbleId(null);
            }}
            title="SFX — Alternar Fala ⇄ SFX (S)"
            aria-label="SFX (S)"
            aria-pressed={activeTool === "sfx"}
          >
            <Sparkles size={16} />
          </button>
        </div>

        {stepHint && (
          <div className="layout-tool-step-hint" role="status" aria-live="polite">
            <span className="layout-tool-step-text">{stepHint}</span>
            <button
              type="button"
              className="btn-tool-step-cancel"
              onClick={handleCancelActiveTool}
              title="Cancelar ferramenta e voltar para Seleção (Esc)"
            >
              Esc
            </button>
          </div>
        )}

        <div
          className="layout-contour-toggle-group"
          role="group"
          aria-label="Modo de contorno do balão"
        >
          <button
            type="button"
            className={`btn-contour-toggle ${bubbleContourMode === "polygon" ? "active" : ""}`}
            onClick={() => {
              if (setBubbleContourMode && bubbleContourMode !== "polygon") {
                setBubbleContourMode("polygon");
                if (addToast) addToast("Modo Contorno Orgânico ativado", "info");
              }
            }}
            title="Modo Contorno Orgânico (OpenCV) - Segue a curvatura natural do balão"
            aria-pressed={bubbleContourMode === "polygon"}
          >
            <Hexagon size={13} className="contour-mode-icon" />
            <span>Contorno Orgânico</span>
          </button>
          <button
            type="button"
            className={`btn-contour-toggle ${bubbleContourMode === "rect" ? "active" : ""}`}
            onClick={() => {
              if (setBubbleContourMode && bubbleContourMode !== "rect") {
                setBubbleContourMode("rect");
                if (addToast) addToast("Modo Caixa Retangular (BBox) ativado", "info");
              }
            }}
            title="Modo Caixa Retangular (BBox) - Bounding box padrão para corte e edição"
            aria-pressed={bubbleContourMode === "rect"}
          >
            <Square size={13} className="contour-mode-icon" />
            <span>Caixa Retangular</span>
          </button>
        </div>
      </div>

      {/* 2. Abas de Navegação Contextual (Figma/Apple Style) */}
      <div className="layout-tabs-bar" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "list"}
          className={`btn-layout-tab ${activeTab === "list" ? "active" : ""}`}
          onClick={() => setActiveTab("list")}
        >
          <ListOrdered size={13} />
          <span>Ordem de Leitura ({boxesCount})</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "properties"}
          className={`btn-layout-tab ${activeTab === "properties" ? "active" : ""}`}
          onClick={() => setActiveTab("properties")}
        >
          <SlidersHorizontal size={13} />
          <span>{activeBubbleId ? `Balão #${activeBoxIndex + 1}` : "Propriedades"}</span>
          {activeBubbleId && <span className="tab-bubble-dot" />}
        </button>
      </div>
    </>
  );
});

LayoutToolsDock.displayName = "LayoutToolsDock";

export default LayoutToolsDock;
