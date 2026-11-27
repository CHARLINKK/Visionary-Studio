import React, { useRef, useLayoutEffect, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Zap,
  MessageSquare,
  Maximize2,
  Minimize2,
  Square,
  Hexagon,
  Trash2,
  RotateCcw,
  Link2,
  Unlink,
  PenTool,
  Wand2,
  ListOrdered,
  Maximize,
  Crosshair,
  Undo2,
  Redo2,
} from 'lucide-react';
import {
  hasBubbleMoved,
  isBubbleSfx,
  getBubbleGroupId,
} from '../../utils/bubbleNormalizer';
import './CanvasContextMenu.css';

/**
 * Menu de Contexto (Botão Direito) no Canvas do Visionary Studio.
 * Exibe ferramentas contextuais para o balão selecionado ou atalhos rápidos do canvas.
 */
export function CanvasContextMenu({
  isOpen,
  x,
  y,
  targetBubble = null,
  boxes = [],
  onClose,
  actions,
  setActiveTool,
  setBubbleEditMode,
  setBubbleContourMode,
  bubbleContourMode = 'polygon',
  autoZoom = false,
  toggleAutoZoom,
  fitToScreen,
  history,
  handleAutoSort,
  addToast,
  pageIndex = 0,
  totalPages = 1,
}) {
  const menuRef = useRef(null);
  const [pos, setPos] = useState({ x: x + 2, y: y + 2 });

  // Reposicionamento inteligente na viewport com inversão ao tocar bordas (portal)
  useLayoutEffect(() => {
    if (!menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    const margin = 8;
    let nextX = x + 2;
    let nextY = y + 2;

    // Se ultrapassar a margem direita da janela, inverte para a esquerda do cursor
    if (nextX + rect.width > window.innerWidth - margin) {
      nextX = Math.max(margin, x - rect.width - 2);
    }
    // Se ultrapassar a margem inferior da janela, inverte para cima do cursor
    if (nextY + rect.height > window.innerHeight - margin) {
      nextY = Math.max(margin, y - rect.height - 2);
    }

    setPos({ x: nextX, y: nextY });
  }, [x, y]);

  // Fechamento automático ao clicar fora, teclar Esc ou rolar scroll
  useEffect(() => {
    const handleMouseDown = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose?.();
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose?.();
      }
    };
    const handleWheel = () => {
      onClose?.();
    };

    window.addEventListener('mousedown', handleMouseDown, true);
    window.addEventListener('keydown', handleKeyDown, true);
    window.addEventListener('wheel', handleWheel, { passive: true, capture: true });

    return () => {
      window.removeEventListener('mousedown', handleMouseDown, true);
      window.removeEventListener('keydown', handleKeyDown, true);
      window.removeEventListener('wheel', handleWheel, true);
    };
  }, [onClose]);

  if (!isOpen) return null;

  const bubbleIndex = targetBubble
    ? boxes.findIndex((b) => b.id === targetBubble.id)
    : -1;
  const isSfx = targetBubble ? isBubbleSfx(targetBubble) : false;
  const targetGroupId = targetBubble ? getBubbleGroupId(targetBubble) : null;
  const hasMoved = targetBubble ? hasBubbleMoved(targetBubble) : false;
  const boxW = targetBubble ? Math.round(Math.abs((targetBubble.x2 || 0) - (targetBubble.x1 || 0))) : 0;
  const boxH = targetBubble ? Math.round(Math.abs((targetBubble.y2 || 0) - (targetBubble.y1 || 0))) : 0;

  const menuContent = (
    <div
      ref={menuRef}
      className="canvas-context-menu"
      style={{ left: `${pos.x}px`, top: `${pos.y}px` }}
      role="menu"
      aria-label="Menu de ferramentas do canvas"
      onContextMenu={(e) => e.preventDefault()}
    >
      {targetBubble ? (
        <>
          {/* Cabeçalho do Balão */}
          <div className="ctx-header">
            <span className="ctx-header-title">
              #{bubbleIndex >= 0 ? bubbleIndex + 1 : '—'} • {isSfx ? 'Efeito Sonoro (SFX)' : 'Balão de Diálogo'}
            </span>
            <span className="ctx-header-meta">{boxW}×{boxH}px</span>
          </div>

          <div className="ctx-divider" />

          {/* Alternar SFX / Fala */}
          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              actions?.toggleSfx?.(targetBubble.id);
              addToast?.(isSfx ? 'Convertido para Fala Comum!' : 'Convertido para Efeito Sonoro (SFX)!', 'info');
              onClose?.();
            }}
          >
            {isSfx ? <MessageSquare size={13} className="ctx-icon" /> : <Zap size={13} className="ctx-icon icon-sfx" />}
            <span>{isSfx ? 'Converter em Fala' : 'Converter em SFX'}</span>
            <span className="ctx-shortcut">S</span>
          </button>

          {/* Margem OCR */}
          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              actions?.inflateMargin?.(targetBubble.id, 6);
              addToast?.('Margem expandida em +6px!', 'info');
              onClose?.();
            }}
          >
            <Maximize2 size={13} className="ctx-icon" />
            <span>Expandir Margem (+6px)</span>
          </button>

          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              actions?.inflateMargin?.(targetBubble.id, -6);
              addToast?.('Margem reduzida em -6px!', 'info');
              onClose?.();
            }}
          >
            <Minimize2 size={13} className="ctx-icon" />
            <span>Encolher Margem (-6px)</span>
          </button>

          {/* Ajuste de Vértices */}
          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              actions?.select?.(targetBubble.id);
              setBubbleEditMode?.('nodes');
              addToast?.('Modo Vértices ativado (Esc para sair)', 'info');
              onClose?.();
            }}
          >
            <Square size={13} className="ctx-icon" />
            <span>Editar Nós do Polígono</span>
            <span className="ctx-shortcut">2x Clique</span>
          </button>

          {/* Alternar Contorno / Caixa */}
          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              const nextMode = bubbleContourMode === 'polygon' ? 'rect' : 'polygon';
              setBubbleContourMode?.(nextMode);
              onClose?.();
            }}
          >
            <Hexagon size={13} className="ctx-icon" />
            <span>{bubbleContourMode === 'polygon' ? 'Mudar para Caixa Retangular' : 'Mudar para Contorno Orgânico'}</span>
          </button>

          <div className="ctx-divider" />

          {/* Vínculo de Grupos */}
          {targetGroupId ? (
            <button
              type="button"
              className="ctx-item"
              onClick={() => {
                actions?.unlink?.(targetBubble.id, targetGroupId);
                addToast?.('Balão desvinculado do grupo!', 'info');
                onClose?.();
              }}
            >
              <Unlink size={13} className="ctx-icon" />
              <span>Desvincular Grupo</span>
            </button>
          ) : (
            <button
              type="button"
              className="ctx-item"
              onClick={() => {
                setActiveTool?.('link');
                actions?.link?.(targetBubble.id);
                addToast?.('Selecione outro balão para unir', 'info');
                onClose?.();
              }}
            >
              <Link2 size={13} className="ctx-icon" />
              <span>Vincular a Outro Balão...</span>
              <span className="ctx-shortcut">L</span>
            </button>
          )}

          {/* Restaurar Posição */}
          <button
            type="button"
            className="ctx-item"
            disabled={!hasMoved}
            onClick={() => {
              actions?.resetPosition?.(targetBubble.id);
              addToast?.('Posição original restaurada!', 'info');
              onClose?.();
            }}
          >
            <RotateCcw size={13} className="ctx-icon" />
            <span>Restaurar Posição Original</span>
          </button>

          <div className="ctx-divider" />

          {/* Exclusão */}
          <button
            type="button"
            className="ctx-item danger"
            onClick={() => {
              actions?.delete?.(targetBubble.id);
              addToast?.('Balão excluído!', 'info');
              onClose?.();
            }}
          >
            <Trash2 size={13} className="ctx-icon" />
            <span>Excluir Balão</span>
            <span className="ctx-shortcut">Del</span>
          </button>
        </>
      ) : (
        <>
          {/* Cabeçalho do Canvas */}
          <div className="ctx-header">
            <span className="ctx-header-title">Canvas • Pág. {(pageIndex ?? 0) + 1} / {totalPages || 1}</span>
            <span className="ctx-header-meta">{boxes.length} {boxes.length === 1 ? 'balão' : 'balões'}</span>
          </div>

          <div className="ctx-divider" />

          {/* Ferramentas de Desenho */}
          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              setActiveTool?.('rect');
              onClose?.();
            }}
          >
            <Square size={13} className="ctx-icon" />
            <span>Criar Balão Retangular</span>
            <span className="ctx-shortcut">B</span>
          </button>

          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              setActiveTool?.('pen');
              onClose?.();
            }}
          >
            <PenTool size={13} className="ctx-icon" />
            <span>Desenhar com Caneta (Polígono)</span>
            <span className="ctx-shortcut">P</span>
          </button>

          <div className="ctx-divider" />

          {/* Ordenação */}
          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              handleAutoSort?.();
              onClose?.();
            }}
          >
            <Wand2 size={13} className="ctx-icon" />
            <span>Auto-Ordenar Mangá (D ➔ E)</span>
          </button>

          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              setActiveTool?.('sequence');
              onClose?.();
            }}
          >
            <ListOrdered size={13} className="ctx-icon" />
            <span>Marcar Ordem 1-a-1</span>
          </button>

          <div className="ctx-divider" />

          {/* Câmera e Visão */}
          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              fitToScreen?.();
              onClose?.();
            }}
          >
            <Maximize size={13} className="ctx-icon" />
            <span>Enquadrar Página na Tela</span>
            <span className="ctx-shortcut">F</span>
          </button>

          <button
            type="button"
            className="ctx-item"
            onClick={() => {
              toggleAutoZoom?.();
              onClose?.();
            }}
          >
            <Crosshair size={13} className="ctx-icon" />
            <span>{autoZoom ? 'Desativar Auto-Zoom' : 'Ativar Auto-Zoom'}</span>
            <span className="ctx-shortcut">Z</span>
          </button>

          <div className="ctx-divider" />

          {/* Histórico Desfazer / Refazer */}
          <button
            type="button"
            className="ctx-item"
            disabled={!history?.canUndo}
            onClick={() => {
              history?.undo?.();
              onClose?.();
            }}
          >
            <Undo2 size={13} className="ctx-icon" />
            <span>Desfazer</span>
            <span className="ctx-shortcut">Ctrl+Z</span>
          </button>

          <button
            type="button"
            className="ctx-item"
            disabled={!history?.canRedo}
            onClick={() => {
              history?.redo?.();
              onClose?.();
            }}
          >
            <Redo2 size={13} className="ctx-icon" />
            <span>Refazer</span>
            <span className="ctx-shortcut">Ctrl+Y</span>
          </button>
        </>
      )}
    </div>
  );

  if (typeof document !== 'undefined' && document.body) {
    return createPortal(menuContent, document.body);
  }

  return menuContent;
}
