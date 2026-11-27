import React from 'react';
import { Cpu, Activity, ShieldCheck, CheckCircle, AlertCircle, Trash2, X } from 'lucide-react';

export default function DevHardwareCard({ devStats, handleClearVRAM, handleUnloadModel }) {
  if (!devStats) return null;

  const vramPct = devStats.vram_pct || 0;
  const vramUsedGb = devStats.vram_used_gb || (devStats.vram_allocated_global ? devStats.vram_allocated_global.toFixed(2) : '0.00');
  const vramTotalGb = devStats.vram_total_gb || (devStats.vram_total ? (devStats.vram_total / 1024).toFixed(2) : '0.00');
  const vramFreeGb = devStats.vram_free_gb || '0.00';

  return (
    <div className="dev-stats-grid">
      {/* Card 1: Backend do Dispositivo */}
      <div className="stat-card">
        <div className="stat-icon cpu"><Cpu size={20}/></div>
        <div className="stat-info">
          <span className="stat-label">Backend do Dispositivo</span>
          <span className="stat-value">{devStats.cuda_available ? devStats.device_name : "CPU Only"}</span>
          <span className="stat-sub">PyTorch {devStats.torch_version} • {devStats.cuda_available ? 'CUDA Acelerado' : 'Modo Seguro'}</span>
        </div>
      </div>

      {/* Card 2: Medidor de VRAM */}
      <div className="stat-card vram-card">
        <div className="stat-icon vram"><Activity size={20}/></div>
        <div className="stat-info">
          <div className="vram-header">
            <span className="stat-label">Medidor de VRAM</span>
            <span className="vram-pct-badge">{vramPct}%</span>
          </div>
          
          {/* Barra Visual de VRAM */}
          <div className="vram-bar-track">
            <div 
              className={`vram-bar-fill ${vramPct > 85 ? 'danger' : vramPct > 65 ? 'warning' : ''}`}
              style={{ width: `${Math.min(100, Math.max(4, vramPct))}%` }}
            />
          </div>

          <div className="vram-meta-row">
            <span className="vram-used-text">{vramUsedGb} GB de {vramTotalGb} GB</span>
            <span className="vram-free-text">{vramFreeGb} GB livres</span>
          </div>
        </div>
        <button className="vram-btn" onClick={handleClearVRAM} title="Forçar limpeza agressiva de VRAM">
          <Trash2 size={14}/>
        </button>
      </div>

      {/* Card 3: Modelos em VRAM e Disco */}
      <div className="stat-card models-card">
        <div className="stat-icon shield"><ShieldCheck size={20}/></div>
        <div className="stat-info">
          <div className="models-header-row">
            <span className="stat-label">Inspetor de Modelo ao Vivo</span>
          </div>

          {/* Modelos Carregados em Memória */}
          <div className="live-models-list">
            {devStats.loaded_in_vram && Object.entries(devStats.loaded_in_vram).map(([name, info]) => (
              <div key={name} className={`live-model-badge ${info.active ? 'active' : 'idle'}`}>
                <span className="live-dot" />
                <span className="model-name">{name}</span>
                <span className="model-state">{info.active ? 'EM VRAM' : 'OCIOSO'}</span>
                {info.active && info.can_unload && (
                  <button 
                    className="unload-btn" 
                    onClick={() => handleUnloadModel(info.key)} 
                    title={`Descarregar ${name} da GPU`}
                  >
                    <X size={10} />
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Integridade em Disco */}
          <div className="models-status-list">
            {Object.entries(devStats.models_status || {}).map(([key, ok]) => (
              <span key={key} className={`model-tag ${ok ? 'ok' : 'missing'}`} title={ok ? "Arquivo verificado no disco" : "Arquivo ausente"}>
                {ok ? <CheckCircle size={10}/> : <AlertCircle size={10}/>} {key}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
