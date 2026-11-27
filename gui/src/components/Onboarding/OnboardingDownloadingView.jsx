import React from 'react';
import { ChevronRight, Check, Info, AlertTriangle, RotateCcw } from 'lucide-react';

/**
 * Painel de progresso de download não bloqueante do Onboarding.
 */
export default function OnboardingDownloadingView({
  dlStatus,
  isElite,
  isDebugPreview,
  downloadError,
  onRetry,
  onBackToSelection,
  onClose,
  handleCompleteOrSkip
}) {
  return (
    <div className="onboarding-download-workspace">
      <div>
        <div className="onboarding-right-header">
          <h2 className="onboarding-right-title">Instalando Modelos Locais</h2>
          <div className="onboarding-header-meta">
            <span className="onboarding-step-tag">Etapa 2 de 2</span>
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

        <div className="onboarding-progress-card" style={{ marginTop: '16px' }}>
          <div className="onboarding-dl-headline">
            <span className="onboarding-dl-title">
              {dlStatus.percent >= 100 ? 'Provisionamento Concluído' : 'Baixando componentes neurais...'}
            </span>
            <span className="onboarding-dl-eta">
              {dlStatus.etaSec > 0 ? `Restante: ~${Math.ceil(dlStatus.etaSec / 60)} min` : `${dlStatus.percent}%`}
            </span>
          </div>

          <div className="onboarding-dl-track">
            <div 
              className="onboarding-dl-bar" 
              style={{ width: `${Math.max(5, dlStatus.percent)}%` }} 
            />
          </div>

          <div className="onboarding-dl-stats">
            <span>
              {dlStatus.speedMb > 0 ? `Taxa: ~${dlStatus.speedMb.toFixed(1)} MB/s` : 'Conectando ao daemon local'}
            </span>
            <span>{dlStatus.bytesDownloadedStr}</span>
          </div>
        </div>

        <div className="onboarding-timeline-steps" style={{ marginTop: '14px' }}>
          <div className={`onboarding-timeline-row ${dlStatus.yoloDone ? '' : 'active'}`}>
            {dlStatus.yoloDone ? (
              <div className="onboarding-dot-done">
                <Check size={11} strokeWidth={3} />
              </div>
            ) : (
              <div className="onboarding-dot-spin" />
            )}
            <span>
              Comic-YOLO v8x (Detecção de Balões & Quadros) —{' '}
              {dlStatus.yoloDone ? 'Validado no cache' : 'Sincronizando pesos neurais (70 MB)...'}
            </span>
          </div>

          <div className={`onboarding-timeline-row ${dlStatus.florenceDone ? '' : 'active'}`}>
            {dlStatus.florenceDone ? (
              <div className="onboarding-dot-done">
                <Check size={11} strokeWidth={3} />
              </div>
            ) : (
              <div className="onboarding-dot-spin" />
            )}
            <span>
              {isElite ? 'Florence-2 Large' : 'Florence-2 Base'} (Visão & OCR) —{' '}
              {dlStatus.florenceDone ? 'Validado no cache' : 'Sincronizando com HuggingFace...'}
            </span>
          </div>

          <div className={`onboarding-timeline-row ${dlStatus.ollamaDone ? '' : 'active'}`}>
            {dlStatus.ollamaDone ? (
              <div className="onboarding-dot-done">
                <Check size={11} strokeWidth={3} />
              </div>
            ) : (
              <div className="onboarding-dot-spin" />
            )}
            <span>
              {isElite ? 'Amadeus Verbo 32B' : 'Amadeus Verbo 7B'} (Tradução Neural) —{' '}
              {dlStatus.ollamaDone ? 'Modelo pronto na memória' : 'Baixando camadas via Ollama...'}
            </span>
          </div>
        </div>

        {downloadError && (
          <div className="onboarding-error-banner" role="alert">
            <div className="onboarding-error-head">
              <AlertTriangle size={15} style={{ flexShrink: 0 }} />
              <span>{downloadError}</span>
            </div>
            <div className="onboarding-error-actions">
              {typeof onRetry === 'function' && (
                <button type="button" className="onboarding-btn-secondary" onClick={onRetry}>
                  <RotateCcw size={13} />
                  <span>Tentar Novamente</span>
                </button>
              )}
              {typeof onBackToSelection === 'function' && (
                <button type="button" className="onboarding-btn-secondary" onClick={onBackToSelection}>
                  <span>Voltar</span>
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="onboarding-bg-banner">
        <Info size={16} style={{ flexShrink: 0 }} />
        <span>
          O download continua ativo em segundo plano. Você pode usar normalmente todas as ferramentas do estúdio.
        </span>
      </div>

      <div className="onboarding-bottom-actions">
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          Progresso monitorado na barra de título
        </span>

        <button 
          type="button" 
          className="onboarding-btn-primary" 
          onClick={handleCompleteOrSkip}
        >
          <span>Abrir Área de Trabalho</span>
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  );
}
