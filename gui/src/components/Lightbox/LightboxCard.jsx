import React, { memo } from 'react';
import { Check, ExternalLink } from 'lucide-react';

export const LightboxCard = memo(function LightboxCard({
  img,
  index,
  isSelected,
  isDragging,
  isDragOver,
  onToggleSelection,
  onDoubleClick,
  onContextMenu,
  onDragStart,
  onDragEnter,
  onDragOver,
  onDrop,
  onDragEnd,
}) {
  const handleCardClick = (e) => {
    if (e.target.closest('.card-select-chip')) return;
    onToggleSelection(img.path, index, e);
  };

  const handleCardDoubleClick = (e) => {
    if (e.target.closest('.card-select-chip') || e.target.closest('.card-badge-chip')) {
      e.stopPropagation();
      return;
    }
    onDoubleClick?.(img);
  };

  const handleSelectChipClick = (e) => {
    e.stopPropagation();
    onToggleSelection(img.path, index, e);
  };

  const handleSelectChipDoubleClick = (e) => {
    e.stopPropagation();
    e.preventDefault();
  };

  const handleSelectChipMouseDown = (e) => {
    e.stopPropagation();
  };

  const handleCardContextMenu = (e) => {
    e.preventDefault();
    onContextMenu?.(e, img, index);
  };

  const hasPipelineData = Boolean(img.pageData);

  return (
    <div 
      className={`lightbox-card ${isSelected ? 'selected' : ''} ${isDragging ? 'dragging' : ''} ${isDragOver ? 'drag-over' : ''}`}
      onClick={handleCardClick}
      onDoubleClick={handleCardDoubleClick}
      onContextMenu={handleCardContextMenu}
      draggable
      onDragStart={(e) => onDragStart(e, index)}
      onDragEnter={(e) => onDragEnter(e, index)}
      onDragOver={onDragOver}
      onDrop={(e) => onDrop(e, index)}
      onDragEnd={onDragEnd}
      title={`${img.name} (Duplo clique para abrir no Estúdio • Espaço para pré-visualização • Botão direito para opções)`}
    >
      <div className="card-badge-chip">
        #{String(index + 1).padStart(2, '0')}
      </div>

      <button 
        type="button"
        className={`card-select-chip ${isSelected ? 'checked' : ''}`} 
        title={isSelected ? "Desmarcar página" : "Selecionar página"}
        onClick={handleSelectChipClick}
        onDoubleClick={handleSelectChipDoubleClick}
        onMouseDown={handleSelectChipMouseDown}
        aria-label={isSelected ? `Desmarcar página ${index + 1}` : `Selecionar página ${index + 1}`}
      >
        {isSelected && <Check size={12} strokeWidth={3} />}
      </button>

      <div className="card-img-wrap">
        <img 
          src={img.thumbSrc || img.src} 
          alt={img.name} 
          loading={index < 16 ? "eager" : "lazy"} 
          fetchPriority={index < 8 ? "high" : "auto"}
          decoding="async" 
        />
        <div className="card-hover-action">
          <ExternalLink size={11} />
          <span>Abrir no Estúdio</span>
        </div>
      </div>

      <div className="card-footer-info">
        <span className="card-filename" title={img.name}>
          {img.name}
        </span>
        {hasPipelineData && (
          <div 
            className="card-pipeline-dots" 
            title={`Status: Layout ${img.pageData.layout ? '✓' : '✗'} • OCR ${img.pageData.ocr ? '✓' : '✗'} • Tradução ${img.pageData.translation ? '✓' : '✗'}`}
          >
            <span className={`pipe-dot lay ${img.pageData.layout ? 'active' : ''}`} title="Layout" />
            <span className={`pipe-dot ocr ${img.pageData.ocr ? 'active' : ''}`} title="OCR" />
            <span className={`pipe-dot tr ${img.pageData.translation ? 'active' : ''}`} title="Tradução" />
          </div>
        )}
      </div>
    </div>
  );
});

export default LightboxCard;
