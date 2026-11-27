import React from 'react';
import { LayoutDashboard } from 'lucide-react';

export default function LightboxEmptyState() {
  return (
    <div className="lightbox-container">
      <div className="lightbox-empty-state">
        <div className="empty-icon-wrap">
          <LayoutDashboard size={40} />
        </div>
        <h2>Nenhum capítulo selecionado</h2>
        <p className="empty-subtitle">
          Selecione uma pasta de capítulo no explorador lateral para inspecionar, reordenar e preparar as páginas antes do processamento com IA.
        </p>
        <div className="empty-guide-steps">
          <div className="empty-step">
            <span className="step-num">1</span>
            <div>
              <strong>Selecione o Capítulo</strong>
              <span>Escolha a pasta com imagens no painel lateral</span>
            </div>
          </div>
          <div className="empty-step">
            <span className="step-num">2</span>
            <div>
              <strong>Ajuste na Lightbox</strong>
              <span>Reordene, una páginas duplas ou exclua capas</span>
            </div>
          </div>
          <div className="empty-step">
            <span className="step-num">3</span>
            <div>
              <strong>Traduza no Estúdio</strong>
              <span>Duplo clique em uma página para abrir e editar</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
