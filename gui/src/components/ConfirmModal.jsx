import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, X } from 'lucide-react';

/**
 * ConfirmModal Component
 * 
 * Modal global reutilizável para confirmações destrutivas (ex: exclusão de páginas, limpeza de dados).
 * Intercepta 'Escape' para fechar e 'Enter' para confirmar.
 */
export default function ConfirmModal({
  isOpen,
  title = "Limpar Dados?",
  message,
  confirmText = "Limpar",
  cancelText = "Cancelar",
  icon: CustomIcon,
  onConfirm,
  onClose
}) {
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        onConfirm();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onConfirm, onClose]);

  if (!isOpen) return null;

  const IconComponent = CustomIcon || AlertTriangle;

  const modalContent = (
    <div className="visionary-dialog-overlay" onClick={onClose}>
      <div 
        className="visionary-dialog-modal" 
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="visionary-dialog-header">
          <div className="visionary-dialog-icon-orb">
            <IconComponent size={18} />
          </div>
          <h3 style={{ flex: 1 }}>{title}</h3>
          <button 
            type="button" 
            className="visionary-dialog-close" 
            onClick={onClose}
            title="Fechar (Esc)"
          >
            <X size={15} />
          </button>
        </div>

        {message && <div className="visionary-dialog-body">{message}</div>}

        <div className="visionary-dialog-actions">
          <button 
            type="button" 
            className="visionary-dialog-btn" 
            onClick={onClose}
          >
            {cancelText}
          </button>
          <button 
            type="button" 
            className="visionary-dialog-btn confirm" 
            onClick={onConfirm}
            autoFocus
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );

  if (typeof document !== 'undefined' && document.body) {
    return createPortal(modalContent, document.body);
  }

  return modalContent;
}
