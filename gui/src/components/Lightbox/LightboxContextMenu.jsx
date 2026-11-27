import React, { useRef, useLayoutEffect, useEffect, useState } from 'react';
import { 
  ExternalLink, 
  Scissors, 
  Columns, 
  CheckSquare, 
  RotateCcw, 
  Copy, 
  Trash2 
} from 'lucide-react';
import './LightboxContextMenu.css';

/**
 * Menu de contexto (botão direito) para os cards da Lightbox.
 */
export default function LightboxContextMenu({
  isOpen,
  x,
  y,
  targetImg,
  selectedCount = 0,
  onClose,
  onOpenInStudio,
  onMerge,
  onSplit,
  onDelete,
  onSelectAll,
  onInvertSelection,
  addToast,
}) {
  const menuRef = useRef(null);
  const [pos, setPos] = useState({ x: x + 2, y: y + 2 });

  // Reposicionamento inteligente na viewport para nunca vazar da tela
  useLayoutEffect(() => {
    if (!menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    const margin = 8;
    let nextX = x + 2;
    let nextY = y + 2;

    if (nextX + rect.width > window.innerWidth - margin) {
      nextX = Math.max(margin, x - rect.width - 2);
    }
    if (nextY + rect.height > window.innerHeight - margin) {
      nextY = Math.max(margin, y - rect.height - 2);
    }

    setPos({ x: nextX, y: nextY });
  }, [x, y]);

  // Fechamento automático ao clicar fora, teclar Esc ou rolar
  useEffect(() => {
    if (!isOpen) return;

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
  }, [isOpen, onClose]);

  if (!isOpen || !targetImg) return null;

  const handleCopyPath = async () => {
    try {
      await navigator.clipboard.writeText(targetImg.path);
      addToast?.('Caminho copiado para a área de transferência!', 'info');
    } catch (_) {
      addToast?.('Falha ao copiar caminho.', 'error');
    }
    onClose?.();
  };

  return (
    <div
      ref={menuRef}
      className="lightbox-context-menu"
      style={{ left: `${pos.x}px`, top: `${pos.y}px` }}
      role="menu"
      aria-label="Menu de ações da página"
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="lightbox-ctx-header">
        <span className="lightbox-ctx-title" title={targetImg.name}>
          {targetImg.name}
        </span>
        {selectedCount > 1 && (
          <span className="lightbox-ctx-badge">{selectedCount} selecionadas</span>
        )}
      </div>

      <div className="lightbox-ctx-divider" />

      {/* Abrir no Estúdio */}
      <button
        type="button"
        className="lightbox-ctx-item primary"
        onClick={() => {
          onOpenInStudio?.(targetImg);
          onClose?.();
        }}
      >
        <ExternalLink size={13} className="lightbox-ctx-icon" />
        <span>Abrir no Estúdio</span>
        <span className="lightbox-ctx-shortcut">2x Clique</span>
      </button>

      {/* Dividir Página Dupla */}
      <button
        type="button"
        className="lightbox-ctx-item"
        disabled={selectedCount > 1}
        onClick={() => {
          onSplit?.();
          onClose?.();
        }}
      >
        <Scissors size={13} className="lightbox-ctx-icon" />
        <span>Dividir Página Dupla</span>
      </button>

      {/* Unir Páginas */}
      <button
        type="button"
        className="lightbox-ctx-item"
        disabled={selectedCount < 2}
        onClick={() => {
          onMerge?.();
          onClose?.();
        }}
      >
        <Columns size={13} className="lightbox-ctx-icon" />
        <span>Unir Páginas Selecionadas ({selectedCount})</span>
      </button>

      <div className="lightbox-ctx-divider" />

      {/* Seleção */}
      <button
        type="button"
        className="lightbox-ctx-item"
        onClick={() => {
          onSelectAll?.();
          onClose?.();
        }}
      >
        <CheckSquare size={13} className="lightbox-ctx-icon" />
        <span>Selecionar Todas</span>
        <span className="lightbox-ctx-shortcut">Ctrl+A</span>
      </button>

      <button
        type="button"
        className="lightbox-ctx-item"
        onClick={() => {
          onInvertSelection?.();
          onClose?.();
        }}
      >
        <RotateCcw size={13} className="lightbox-ctx-icon" />
        <span>Inverter Seleção</span>
      </button>

      <button
        type="button"
        className="lightbox-ctx-item"
        onClick={handleCopyPath}
      >
        <Copy size={13} className="lightbox-ctx-icon" />
        <span>Copiar Caminho do Arquivo</span>
      </button>

      <div className="lightbox-ctx-divider" />

      {/* Excluir */}
      <button
        type="button"
        className="lightbox-ctx-item danger"
        onClick={() => {
          onDelete?.();
          onClose?.();
        }}
      >
        <Trash2 size={13} className="lightbox-ctx-icon" />
        <span>Excluir {selectedCount > 1 ? `${selectedCount} Páginas` : 'Página'}</span>
        <span className="lightbox-ctx-shortcut">Del</span>
      </button>
    </div>
  );
}
