import React, { useState, useRef, useEffect } from 'react';
import {
  ListOrdered,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  RotateCcw,
} from 'lucide-react';
import {
  useSeamlessDoc,
  useSeamlessViewport,
  useSeamlessUi,
} from '../../contexts/SeamlessContext';
import {
  resolveBubbleBadgeLabel,
  reindexBubbleOrders,
  hasBubbleMoved,
  isBubbleSfx,
  toggleBubbleSfxState,
} from '../../utils/bubbleNormalizer';

/**
 * Fita Horizontal de Navegação no Rodapé do Canvas (Conceito 3 - Padrão Ouro).
 * Desloca a fila de balões #1..#N para uma fita elegante no rodapé do canvas,
 * liberando o inspetor lateral direito 100% para propriedades do balão selecionado.
 */
export const CanvasBottomFilmstrip = React.memo(function CanvasBottomFilmstrip() {
  const {
    viewMode,
    ocrData,
    setOcrData,
    history,
    activeBubbleId,
    setActiveBubbleId,
  } = useSeamlessDoc();

  const { zoom } = useSeamlessViewport();
  const { addToast } = useSeamlessUi();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const activeChipRef = useRef(null);

  const boxes = ocrData?.boxes || [];
  const pushHistory = history?.pushHistory;

  // Auto-scroll para centralizar o chip ativo no filmstrip
  useEffect(() => {
    if (activeBubbleId && activeChipRef.current) {
      activeChipRef.current.scrollIntoView({
        behavior: 'smooth',
        inline: 'center',
        block: 'nearest',
      });
    }
  }, [activeBubbleId]);

  if (viewMode !== 'layout' || boxes.length === 0) return null;

  const activeIndex = boxes.findIndex((b) => b.id === activeBubbleId);

  const handleSelectBubble = (id) => {
    if (activeBubbleId === id) {
      setActiveBubbleId(null);
    } else {
      setActiveBubbleId(id);
      if (zoom && typeof zoom.zoomToSpecificBubble === 'function') {
        zoom.zoomToSpecificBubble(id);
      }
    }
  };

  const handleNavigateDelta = (delta) => {
    if (boxes.length === 0) return;
    let nextIdx = 0;
    if (activeIndex >= 0) {
      nextIdx = (activeIndex + delta + boxes.length) % boxes.length;
    } else {
      nextIdx = delta > 0 ? 0 : boxes.length - 1;
    }
    const target = boxes[nextIdx];
    if (target) {
      handleSelectBubble(target.id);
    }
  };

  const handleToggleSfx = (targetId) => {
    setOcrData((data) => {
      if (pushHistory) pushHistory(data);
      const next = { ...data };
      if (next.boxes) {
        const updated = next.boxes.map((b) =>
          b.id === targetId ? toggleBubbleSfxState(b) : b
        );
        next.boxes = reindexBubbleOrders(updated);
      }
      return next;
    });
  };

  const handleResetPosition = (targetId) => {
    setOcrData((data) => {
      if (!data?.boxes) return data;
      const target = data.boxes.find((x) => x.id === targetId);
      if (!target) return data;

      const ibox = Array.isArray(target.initial_box) && target.initial_box.length === 4
        ? target.initial_box
        : [target.x1, target.y1, target.x2, target.y2];

      const ipoly = Array.isArray(target.initial_polygon) && target.initial_polygon.length > 0
        ? target.initial_polygon
        : target.polygon;

      if (pushHistory) pushHistory(data);

      return {
        ...data,
        boxes: data.boxes.map((b) => {
          if (b.id !== targetId) return b;
          return {
            ...b,
            x1: ibox[0],
            y1: ibox[1],
            x2: ibox[2],
            y2: ibox[3],
            polygon: ipoly ? JSON.parse(JSON.stringify(ipoly)) : b.polygon,
          };
        }),
      };
    });
    addToast('Balão restaurado para a posição e contorno iniciais!', 'info');
  };

  if (isCollapsed) {
    return (
      <div
        className="canvas-bottom-filmstrip collapsed"
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          className="filmstrip-collapsed-pill"
          onClick={() => setIsCollapsed(false)}
          title="Expandir fila de balões (Ordem de leitura)"
        >
          <ListOrdered size={14} />
          <span>Fila de Balões ({boxes.length})</span>
          <ChevronUp size={14} />
        </button>
      </div>
    );
  }

  return (
    <div
      className="canvas-bottom-filmstrip"
      onMouseDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      role="region"
      aria-label="Fita de Navegação de Leitura dos Balões"
    >
      {/* Controles de Navegação Anterior/Próximo e Recolhimento */}
      <div className="filmstrip-controls">
        <div className="filmstrip-title-group">
          <span className="filmstrip-title">Ordem</span>
          <span className="filmstrip-count">{boxes.length}</span>
        </div>

        <div className="filmstrip-arrows">
          <button
            type="button"
            className="filmstrip-arrow-btn"
            onClick={() => handleNavigateDelta(-1)}
            title="Balão anterior (Atalho A)"
            disabled={boxes.length === 0}
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            className="filmstrip-arrow-btn"
            onClick={() => handleNavigateDelta(1)}
            title="Próximo balão (Atalho D)"
            disabled={boxes.length === 0}
          >
            <ChevronRight size={14} />
          </button>
        </div>

        <button
          type="button"
          className="filmstrip-collapse-btn"
          onClick={() => setIsCollapsed(true)}
          title="Minimizar fita de balões"
        >
          <ChevronDown size={14} />
        </button>
      </div>

      <div className="filmstrip-divider" />

      {/* Trilha Horizontal de Balões com Rolagem Suave */}
      <div className="filmstrip-track">
        {boxes.map((b, i) => {
          const isSelected = activeBubbleId === b.id;
          const isSfx = isBubbleSfx(b);
          const moved = hasBubbleMoved(b);
          const snippet = b.text ? b.text.trim() : '';

          return (
            <div
              key={b.id}
              ref={isSelected ? activeChipRef : null}
              className={`filmstrip-chip ${isSelected ? 'active' : ''}`}
              onClick={() => handleSelectBubble(b.id)}
              title={snippet ? `#${i + 1}: ${snippet}` : `#${i + 1} (${isSfx ? 'SFX' : 'Balão'})`}
            >
              <span className="filmstrip-chip-index">#{i + 1}</span>

              {snippet ? (
                <span className="filmstrip-chip-text">
                  {snippet.length > 18 ? snippet.slice(0, 18) + '…' : snippet}
                </span>
              ) : null}

              <button
                type="button"
                className={`filmstrip-chip-badge ${isSfx ? 'sfx' : 'bubble'}`}
                onClick={(e) => {
                  e.stopPropagation();
                  handleToggleSfx(b.id);
                }}
                title="Alternar entre Balão de fala e SFX"
              >
                {resolveBubbleBadgeLabel(b)}
              </button>

              {moved && (
                <button
                  type="button"
                  className="filmstrip-chip-reset"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleResetPosition(b.id);
                  }}
                  title="Restaurar posição e contorno de detecção"
                >
                  <RotateCcw size={11} />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
});

CanvasBottomFilmstrip.displayName = 'CanvasBottomFilmstrip';
