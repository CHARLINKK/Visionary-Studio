import React, { useEffect } from 'react';
import { X, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import './LightboxQuickLook.css';

/**
 * Modal de Pré-visualização Rápida (Quick Look) da Lightbox.
 * Acionado ao pressionar 'Espaço' em um card da grade.
 */
export default function LightboxQuickLook({
  isOpen,
  images = [],
  currentIndex = 0,
  onClose,
  onNavigate,
  onOpenInStudio,
}) {
  const currentImg = images[currentIndex] || null;

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' || e.code === 'Space') {
        e.preventDefault();
        onClose?.();
        return;
      }
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (currentIndex > 0) {
          onNavigate?.(currentIndex - 1);
        }
        return;
      }
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (currentIndex < images.length - 1) {
          onNavigate?.(currentIndex + 1);
        }
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        if (currentImg) {
          onOpenInStudio?.(currentImg);
          onClose?.();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentIndex, images.length, currentImg, onClose, onNavigate, onOpenInStudio]);

  if (!isOpen || !currentImg) return null;

  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < images.length - 1;

  return (
    <div 
      className="lightbox-quicklook-overlay" 
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Pré-visualização da página"
    >
      <div 
        className="lightbox-quicklook-modal" 
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header com Metadados e Ações */}
        <div className="quicklook-header">
          <div className="quicklook-meta">
            <span className="quicklook-badge">
              #{String(currentIndex + 1).padStart(2, '0')} de {images.length}
            </span>
            <span className="quicklook-filename" title={currentImg.name}>
              {currentImg.name}
            </span>
            {currentImg.pageData && (
              <div className="quicklook-status-pills">
                <span className={`ql-status ${currentImg.pageData.layout ? 'done' : ''}`}>
                  Layout
                </span>
                <span className={`ql-status ${currentImg.pageData.ocr ? 'done' : ''}`}>
                  OCR
                </span>
                <span className={`ql-status ${currentImg.pageData.translation ? 'done' : ''}`}>
                  Tradução
                </span>
              </div>
            )}
          </div>

          <div className="quicklook-actions">
            <button
              type="button"
              className="quicklook-btn-studio"
              onClick={() => {
                onOpenInStudio?.(currentImg);
                onClose?.();
              }}
              title="Abrir no Estúdio para edição (Enter)"
            >
              <ExternalLink size={13} />
              <span>Abrir no Estúdio</span>
              <kbd className="quicklook-kbd">Enter</kbd>
            </button>

            <button
              type="button"
              className="quicklook-btn-close"
              onClick={onClose}
              title="Fechar pré-visualização (Espaço ou Esc)"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Viewport Central da Imagem com Controles Laterais */}
        <div className="quicklook-body">
          {hasPrev && (
            <button
              type="button"
              className="quicklook-nav-btn prev"
              onClick={() => onNavigate?.(currentIndex - 1)}
              title="Página anterior (←)"
              aria-label="Página anterior"
            >
              <ChevronLeft size={24} />
            </button>
          )}

          <div className="quicklook-img-wrapper">
            <img
              src={currentImg.src}
              alt={currentImg.name}
              className="quicklook-img"
              decoding="async"
            />
          </div>

          {hasNext && (
            <button
              type="button"
              className="quicklook-nav-btn next"
              onClick={() => onNavigate?.(currentIndex + 1)}
              title="Próxima página (→)"
              aria-label="Próxima página"
            >
              <ChevronRight size={24} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
