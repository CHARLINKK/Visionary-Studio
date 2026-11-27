import React from 'react';
import { ArrowRight } from 'lucide-react';

/**
 * Painel de seleção de perfis de modelos (Studio 32B vs Ágil 7B) do Onboarding.
 */
export default function OnboardingProfileSelect({
  profile,
  setProfile,
  isElite,
  runInBackground,
  setRunInBackground,
  handleStartInstallation,
  isDebugPreview,
  onClose
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%', gap: '16px' }}>
      <div>
        <div className="onboarding-right-header">
          <h2 className="onboarding-right-title">Escolha o Perfil de Trabalho</h2>
          <div className="onboarding-header-meta">
            <span className="onboarding-step-tag">Etapa 1 de 2</span>
            {isDebugPreview && (
              <button 
                type="button" 
                className="onboarding-debug-close-btn"
                onClick={onClose}
                title="Fechar Preview (Modo Debug - ESC)"
              >
                Fechar Preview ✕
              </button>
            )}
          </div>
        </div>

        <div className="onboarding-cards-stack">
          {/* CARD 1: STUDIO (RECOMENDADO) */}
          <div 
            className={`onboarding-profile-card ${profile === 'elite' ? 'selected' : ''}`}
            onClick={() => setProfile('elite')}
          >
            <div className="onboarding-card-row-top">
              <div className="onboarding-card-identity">
                <div className="onboarding-radio-circle">
                  <div className="onboarding-radio-dot" />
                </div>
                <span className="onboarding-card-name">Perfil Studio Literário</span>
              </div>
              <span className="onboarding-badge-pill recommended">Recomendado</span>
            </div>

            <p className="onboarding-card-body-desc">
              Tradução refinada de alta densidade para mangás e webtoons. Compreende gírias, jogos de palavras e contexto cultural complexo.
            </p>

            <div className="onboarding-card-chips-row">
              <div className="onboarding-chips-group">
                <span className="onboarding-chip-item highlight">Amadeus Verbo 32B</span>
                <span className="onboarding-chip-item">Florence-2 Large</span>
                <span className="onboarding-chip-item">Comic-YOLO</span>
              </div>
              <div className="onboarding-card-metrics">
                <span className="onboarding-metric-tag" title="Espaço de armazenamento em disco">
                  <span className="onboarding-metric-dim">Download:</span> ~22.9 GB
                </span>
                <span className="onboarding-metric-divider">•</span>
                <span className="onboarding-metric-tag" title="Consumo projetado em execução">
                  <span className="onboarding-metric-dim">Execução:</span> ~8 GB VRAM + 14 GB RAM
                </span>
              </div>
            </div>
          </div>

          {/* CARD 2: ÁGIL */}
          <div 
            className={`onboarding-profile-card ${profile === 'fast' ? 'selected' : ''}`}
            onClick={() => setProfile('fast')}
          >
            <div className="onboarding-card-row-top">
              <div className="onboarding-card-identity">
                <div className="onboarding-radio-circle">
                  <div className="onboarding-radio-dot" />
                </div>
                <span className="onboarding-card-name">Perfil Ágil & Econômico</span>
              </div>
              <span className="onboarding-badge-pill fast">Ultraleve</span>
            </div>

            <p className="onboarding-card-body-desc">
              Inferência ultraveloz contida 100% na memória dedicada da placa de vídeo. Ideal para grandes volumes de texto direto.
            </p>

            <div className="onboarding-card-chips-row">
              <div className="onboarding-chips-group">
                <span className="onboarding-chip-item highlight">Amadeus Verbo 7B</span>
                <span className="onboarding-chip-item">Florence-2 Base</span>
                <span className="onboarding-chip-item">Comic-YOLO</span>
              </div>
              <div className="onboarding-card-metrics">
                <span className="onboarding-metric-tag" title="Espaço de armazenamento em disco">
                  <span className="onboarding-metric-dim">Download:</span> ~5.8 GB
                </span>
                <span className="onboarding-metric-divider">•</span>
                <span className="onboarding-metric-tag" title="Consumo projetado em execução">
                  <span className="onboarding-metric-dim">Execução:</span> ~5.5 GB VRAM (100% GPU)
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Ações Inferiores */}
      <div className="onboarding-bottom-actions">
        <label className="onboarding-bg-checkbox">
          <input 
            type="checkbox" 
            checked={runInBackground} 
            onChange={(e) => setRunInBackground(e.target.checked)} 
          />
          <span>Executar download em segundo plano</span>
        </label>

        <button 
          type="button" 
          className="onboarding-btn-primary" 
          onClick={handleStartInstallation}
        >
          <span>Instalar Perfil {isElite ? 'Studio (22.9 GB)' : 'Ágil (5.8 GB)'}</span>
          <ArrowRight size={15} />
        </button>
      </div>
    </div>
  );
}
