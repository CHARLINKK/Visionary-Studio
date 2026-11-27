import React from 'react';
import {
  MousePointer2,
  Square,
  PenTool,
  EyeOff,
  ListOrdered,
  Link,
  Sparkles,
  Wand2,
  Hexagon,
} from 'lucide-react';
import {
  useSeamlessDoc,
  useSeamlessToolsState,
  useSeamlessUi,
} from '../../contexts/SeamlessContext';
import { clientApi } from '../../api/bridge';
import { reindexBubbleOrders } from '../../utils/bubbleNormalizer';

/**
 * Barra de ferramentas vertical flutuante no canto esquerdo do Canvas (Conceito 3 - Padrão Ouro).
 * Inspirada em ferramentas profissionais como Clip Studio Paint e Photoshop.
 * Ocupa apenas 44px de largura na margem esquerda, eliminando qualquer risco de estourar a largura da tela.
 */
export const CanvasLayoutToolbar = React.memo(function CanvasLayoutToolbar() {
  const {
    viewMode,
    page,
    ocrData,
    setOcrData,
    history,
    bubbleContourMode,
    setBubbleContourMode,
    setActiveBubbleId,
  } = useSeamlessDoc();

  const { tools } = useSeamlessToolsState();
  const { addToast } = useSeamlessUi();

  if (viewMode !== 'layout') return null;

  const {
    activeTool,
    setActiveTool,
    setDragStartPos,
    setDrawingRect,
    setPenPoints,
    bubbles,
    setBubbles,
    setRectStartPos,
  } = tools;

  const boxes = ocrData?.boxes || [];
  const pushHistory = history?.pushHistory;

  const handleAutoSort = () => {
    if (!boxes.length) return;
    clientApi
      .autoSortBoxes(page?.path, boxes)
      .then((res) => {
        if (res && res.success && res.boxes) {
          setOcrData((data) => {
            if (pushHistory) pushHistory(data);
            const next = { ...data };
            const sortedBoxes = res.boxes.map((b) => ({
              ...(next.boxes?.find((x) => x.id === b.id) || b),
            }));
            next.boxes = reindexBubbleOrders(sortedBoxes);
            if (res.panels && res.panels.length > 0) {
              next.panels = res.panels;
            }
            return next;
          });
          addToast('Ordem de leitura auto-organizada!', 'success');
        } else {
          addToast('Erro ao ordenar: ' + (res?.error || 'Desconhecido'), 'error');
        }
      })
      .catch((err) => addToast('Erro na requisição: ' + err.message, 'error'));
  };

  const handleApplySequence = () => {
    if (!bubbles.length) return;
    setOcrData((data) => {
      if (pushHistory) pushHistory(data);
      const next = { ...data };
      const currBoxes = [...(next.boxes || [])];
      const seqBoxes = bubbles
        .map((id) => currBoxes.find((x) => x.id === id))
        .filter(Boolean);
      const remBoxes = currBoxes.filter((x) => !bubbles.includes(x.id));
      next.boxes = reindexBubbleOrders([...seqBoxes, ...remBoxes]);
      return next;
    });
    setBubbles([]);
    addToast('Sequência aplicada com sucesso!', 'success');
  };

  return (
    <div
      className="canvas-layout-toolbar vertical"
      onMouseDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      role="toolbar"
      aria-label="Ferramentas de Layout do Canvas"
    >
      {/* Grupo 1: Criação & Seleção */}
      <div className="canvas-toolbar-group vertical">
        <button
          type="button"
          className={`canvas-tool-btn ${activeTool === 'select' ? 'active' : ''}`}
          onClick={() => {
            setActiveTool('select');
            setDragStartPos(null);
          }}
          title="Selecionar, Mover e Redimensionar Balões (V)"
        >
          <MousePointer2 size={16} />
          <span className="tool-label">Seleção</span>
          <span className="tool-shortcut-badge">V</span>
        </button>

        <button
          type="button"
          className={`canvas-tool-btn ${activeTool === 'rect' ? 'active' : ''}`}
          onClick={() => {
            setActiveTool('rect');
            setDragStartPos(null);
            setActiveBubbleId(null);
            setDrawingRect(null);
          }}
          title="Desenhar Caixa Retangular (B)"
        >
          <Square size={16} />
          <span className="tool-label">Retângulo</span>
          <span className="tool-shortcut-badge">B</span>
        </button>

        <button
          type="button"
          className={`canvas-tool-btn ${activeTool === 'pen' ? 'active' : ''}`}
          onClick={() => {
            setActiveTool('pen');
            setDragStartPos(null);
            setActiveBubbleId(null);
            setPenPoints([]);
          }}
          title="Desenhar Balão Manual por 4 Pontos de Perspectiva (P)"
        >
          <PenTool size={16} />
          <span className="tool-label">Caneta</span>
          <span className="tool-shortcut-badge">P</span>
        </button>
      </div>

      <div className="canvas-toolbar-divider horizontal" />

      {/* Grupo 2: Ordem de Leitura & Sequência */}
      <div className="canvas-toolbar-group vertical">
        <button
          type="button"
          className={`canvas-tool-btn ${activeTool === 'reorder' ? 'active' : ''}`}
          onClick={() => {
            setActiveTool('reorder');
            setActiveBubbleId(null);
            setDragStartPos(null);
            setBubbles([]);
          }}
          title="Reordenar Balão no Fluxo de Leitura (R)"
        >
          <EyeOff size={16} />
          <span className="tool-label">Reordenar</span>
          <span className="tool-shortcut-badge">R</span>
        </button>

        <button
          type="button"
          className={`canvas-tool-btn ${activeTool === 'sequence' ? 'active' : ''}`}
          onClick={() => {
            setActiveTool('sequence');
            setActiveBubbleId(null);
            setDragStartPos(null);
            if (setRectStartPos) setRectStartPos(null);
            setBubbles([]);
          }}
          title="Modo Sequência: Clique nos balões na ordem desejada"
        >
          <ListOrdered size={16} />
          <span className="tool-label">Sequência</span>
        </button>

        <button
          type="button"
          className="canvas-tool-btn auto-sort"
          onClick={handleAutoSort}
          title="Auto-organizar Ordem de Leitura Mangá (Direita para Esquerda / Topo para Base)"
        >
          <Wand2 size={16} className="auto-sort-icon" />
          <span className="tool-label">Auto-Ordenar</span>
        </button>
      </div>

      {/* Sequência ativa: Popover chip flutuante à direita da barra vertical */}
      {activeTool === 'sequence' && bubbles.length > 0 && (
        <div className="canvas-vertical-sequence-popover">
          <span>{bubbles.length} na fila</span>
          <button
            type="button"
            className="btn-sequence-apply"
            onClick={handleApplySequence}
          >
            Aplicar
          </button>
        </div>
      )}

      <div className="canvas-toolbar-divider horizontal" />

      {/* Grupo 3: Agrupamento & SFX */}
      <div className="canvas-toolbar-group vertical">
        <button
          type="button"
          className={`canvas-tool-btn ${activeTool === 'link' ? 'active' : ''}`}
          onClick={() => {
            setActiveTool('link');
            setActiveBubbleId(null);
            setDragStartPos(null);
            if (setRectStartPos) setRectStartPos(null);
            setBubbles([]);
          }}
          title="Vincular Balões em Família Contínua (L)"
        >
          <Link size={16} />
          <span className="tool-label">Vincular</span>
          <span className="tool-shortcut-badge">L</span>
        </button>

        <button
          type="button"
          className={`canvas-tool-btn ${activeTool === 'sfx' ? 'active' : ''}`}
          onClick={() => {
            setActiveTool('sfx');
            setActiveBubbleId(null);
            setDragStartPos(null);
            if (setRectStartPos) setRectStartPos(null);
            setBubbles([]);
          }}
          title="Alternar Balão / SFX com 1 clique no canvas (S)"
        >
          <Sparkles size={16} />
          <span className="tool-label">SFX</span>
          <span className="tool-shortcut-badge">S</span>
        </button>
      </div>

      <div className="canvas-toolbar-divider horizontal" />

      {/* Grupo 4: Modo de Contorno Global */}
      <div className="canvas-contour-segmented vertical" role="group" aria-label="Modo de contorno">
        <button
          type="button"
          className={`canvas-contour-pill ${bubbleContourMode === 'polygon' ? 'active' : ''}`}
          onClick={() => {
            if (setBubbleContourMode && bubbleContourMode !== 'polygon') {
              setBubbleContourMode('polygon');
              addToast('Contorno Orgânico ativado', 'info');
            }
          }}
          title="Contorno Orgânico (OpenCV): segue as curvas anatômicas do balão"
        >
          <Hexagon size={14} />
          <span className="contour-pill-text">Orgânico</span>
        </button>
        <button
          type="button"
          className={`canvas-contour-pill ${bubbleContourMode === 'rect' ? 'active' : ''}`}
          onClick={() => {
            if (setBubbleContourMode && bubbleContourMode !== 'rect') {
              setBubbleContourMode('rect');
              addToast('Caixa Retangular (BBox) ativada', 'info');
            }
          }}
          title="Caixa Retangular (BBox): bounding box padrão para recorte"
        >
          <Square size={14} />
          <span className="contour-pill-text">BBox</span>
        </button>
      </div>
    </div>
  );
});

CanvasLayoutToolbar.displayName = 'CanvasLayoutToolbar';
