import React from 'react';

/**
 * Visualizador dinâmico de consumo projetado de VRAM e RAM para o Onboarding.
 */
export default function OnboardingMemoryVisualizer({
  isElite,
  hw,
  targetVramGb,
  targetRamGb,
  vramPercent,
  ramPercent
}) {
  return (
    <div className="onboarding-memory-visualizer">
      <div className="onboarding-mem-header">
        <div className="onboarding-mem-header-top">
          <span className="onboarding-mem-pill">PREVISÃO DE CONSUMO</span>
          <span className="onboarding-mem-profile-tag">
            {isElite ? 'Studio (32B)' : 'Ágil (7B)'}
          </span>
        </div>
        <div className="onboarding-mem-hw-row">
          <span className="onboarding-mem-hw-label">GPU:</span>
          <span className="onboarding-mem-hw-name" title={hw.gpuName}>
            {hw.gpuName}
          </span>
        </div>
      </div>

      <div className="onboarding-mem-bar-group">
        <div className="onboarding-mem-label-row">
          <span className="onboarding-mem-label-name">VRAM (GPU)</span>
          <span className="onboarding-mem-label-val">
            {targetVramGb.toFixed(1)} / {hw.vramTotal.toFixed(1)} GB ({vramPercent}%)
          </span>
        </div>
        <div className="onboarding-mem-track">
          <div 
            className="onboarding-mem-fill vram" 
            style={{ width: `${vramPercent}%` }}
          />
        </div>
      </div>

      <div className="onboarding-mem-bar-group">
        <div className="onboarding-mem-label-row">
          <span className="onboarding-mem-label-name">RAM do Sistema</span>
          <span className="onboarding-mem-label-val">
            {targetRamGb.toFixed(1)} / {hw.ramTotal.toFixed(1)} GB ({ramPercent}%)
          </span>
        </div>
        <div className="onboarding-mem-track">
          <div 
            className="onboarding-mem-fill ram" 
            style={{ width: `${ramPercent}%` }}
          />
        </div>
      </div>

      <div className={`onboarding-mem-diagnostic ${isElite ? 'hybrid' : 'direct'}`}>
        <div className="onboarding-mem-diag-header">
          <span className="onboarding-mem-diag-icon">{isElite ? '💡' : '⚡'}</span>
          <span className="onboarding-mem-diag-title">
            {isElite ? 'Modo Híbrido (GPU + RAM)' : '100% VRAM (Direto)'}
          </span>
        </div>
        <p className="onboarding-mem-diag-desc">
          {isElite
            ? `Preenche a VRAM (${hw.vramTotal.toFixed(0)} GB) e transfere camadas para a RAM do PC (~${targetRamGb.toFixed(0)} GB) para tradução de alta fidelidade.`
            : `Inferência contida integralmente na placa de vídeo (${targetVramGb.toFixed(1)} de ${hw.vramTotal.toFixed(0)} GB) com velocidade máxima.`}
        </p>
      </div>
    </div>
  );
}
