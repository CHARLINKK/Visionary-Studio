import { useState, useEffect } from 'react';
import { RefreshCw, Download, CheckCircle2 } from 'lucide-react';
import pkg from '../../../package.json';
import logoPng from '../../assets/logo3d.png';

function resolveHardwareAccelLabel() {
  try {
    const raw = localStorage.getItem('visionary:cached_hardware_stats');
    if (raw) {
      const hw = JSON.parse(raw);
      const gpuName = typeof hw?.gpu_name === 'string' ? hw.gpu_name.trim() : '';
      if (gpuName && !/identificando/i.test(gpuName)) {
        if (/cpu|nenhum/i.test(gpuName) || hw?.cuda_available === false) {
          return 'CPU (Modo Local)';
        }
        const shortGpu = gpuName
          .replace(/^(NVIDIA\s+GeForce|NVIDIA|GeForce)\s+/i, '')
          .trim() || gpuName;
        return `${shortGpu} · CUDA 12.8`;
      }
    }
  } catch {
    // Fallback neutro caso não haja telemetria em cache
  }
  return 'CUDA 12.8 · PyTorch';
}

export function SettingsAbout() {
  const hardwareAccelLabel = resolveHardwareAccelLabel();
  const [updater, setUpdater] = useState({ state: 'idle', message: null, progress: 0, latestVersion: null });

  useEffect(() => {
    const api = typeof window !== 'undefined' ? window.electronAPI : null;
    if (!api) return;
    if (typeof api.getUpdaterStatus === 'function') {
      api.getUpdaterStatus().then((st) => {
        if (st) setUpdater((prev) => ({ ...prev, ...st }));
      }).catch(() => {});
    }
    if (typeof api.onUpdaterStatus === 'function') {
      return api.onUpdaterStatus((st) => {
        if (st) setUpdater((prev) => ({ ...prev, ...st }));
      });
    }
  }, []);

  const handleCheckUpdates = async () => {
    const api = typeof window !== 'undefined' ? window.electronAPI : null;
    if (api?.checkForUpdates) {
      const res = await api.checkForUpdates();
      if (res) setUpdater((prev) => ({ ...prev, ...res }));
    }
  };

  const handleDownloadUpdate = async () => {
    const api = typeof window !== 'undefined' ? window.electronAPI : null;
    if (api?.downloadUpdate) {
      const res = await api.downloadUpdate();
      if (res) setUpdater((prev) => ({ ...prev, ...res }));
    }
  };

  const handleInstallUpdate = async () => {
    const api = typeof window !== 'undefined' ? window.electronAPI : null;
    if (api?.installUpdate) {
      await api.installUpdate();
    }
  };

  return (
    <div className="settings-section about-section">
      <div className="about-studio-card">
        <div className="about-studio-left">
          <div className="about-studio-brand">
            <img src={logoPng} alt="Visionary Studio" className="about-studio-logo" />
            <div className="about-studio-titles">
              <h2 className="about-studio-name">Visionary Studio</h2>
              <div className="about-studio-badge-row">
                <span className="about-mono-ver">v{pkg.version || '1.0.0'}</span>
                <span className="about-dot-sep">·</span>
                <span className="about-build-lbl">Release Estável (64-bit)</span>
              </div>
              <div className="about-team-credit">
                Desenvolvido e mantido por <strong>Trevo</strong>
              </div>
            </div>
          </div>

          <p className="about-studio-manifest">
            Ambiente neural integrado de alto desempenho para segmentação de páginas, 
            reconhecimento de texto (OCR) e tradução assistida de quadrinhos com processamento 100% local.
          </p>

          <div className="about-system-telemetry">
            <div className="telemetry-item">
              <span className="telemetry-dot active" />
              <span className="telemetry-key">Aceleração Neural</span>
              <span className="telemetry-val">{hardwareAccelLabel}</span>
            </div>
            <div className="telemetry-item">
              <span className="telemetry-dot active" />
              <span className="telemetry-key">Modo de Operação</span>
              <span className="telemetry-val">100% Offline / Privado</span>
            </div>
            <div className="telemetry-item">
              <span className="telemetry-dot active" />
              <span className="telemetry-key">Arquitetura</span>
              <span className="telemetry-val">x86_64 Local Runtime</span>
            </div>
          </div>

          <div className="about-studio-copyright" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {typeof window !== 'undefined' && window.electronAPI?.checkForUpdates && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', padding: '7px 10px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle, rgba(255,255,255,0.07))' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary, #cbd5e1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {updater.state === 'checking' && 'Verificando GitHub Releases...'}
                  {updater.state === 'available' && `Nova versão v${updater.latestVersion} disponível`}
                  {updater.state === 'downloading' && `Baixando v${updater.latestVersion} (${updater.progress || 0}%)...`}
                  {updater.state === 'downloaded' && `v${updater.latestVersion} pronta para instalar`}
                  {updater.state === 'up-to-date' && 'Versão atualizada (GitHub Releases)'}
                  {updater.state === 'error' && (updater.message || 'Falha ao consultar GitHub')}
                  {updater.state === 'idle' && 'Canal de atualização: GitHub Releases'}
                </span>
                {updater.state === 'available' && updater.downloadUrl ? (
                  <button
                    type="button"
                    onClick={handleDownloadUpdate}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '4px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '5px', border: 'none', background: 'var(--brand-primary, #6366f1)', color: '#fff', cursor: 'pointer', flexShrink: 0 }}
                  >
                    <Download size={12} /> Baixar
                  </button>
                ) : updater.state === 'downloaded' ? (
                  <button
                    type="button"
                    onClick={handleInstallUpdate}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '4px 9px', fontSize: '11px', fontWeight: 600, borderRadius: '5px', border: 'none', background: '#10b981', color: '#fff', cursor: 'pointer', flexShrink: 0 }}
                  >
                    <CheckCircle2 size={12} /> Reiniciar e Aplicar
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleCheckUpdates}
                    disabled={updater.state === 'checking' || updater.state === 'downloading'}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '4px 9px', fontSize: '11px', fontWeight: 500, borderRadius: '5px', border: '1px solid var(--border-subtle, rgba(255,255,255,0.12))', background: 'rgba(255,255,255,0.04)', color: 'var(--text-main, #f8fafc)', cursor: 'pointer', flexShrink: 0 }}
                  >
                    <RefreshCw size={11} className={updater.state === 'checking' ? 'spin' : ''} /> Verificar
                  </button>
                )}
              </div>
            )}
            <div>© 2026 Trevo. Todos os direitos reservados.</div>
          </div>
        </div>

        <div className="about-studio-right">
          <div className="about-right-section">
            <div className="about-section-header">
              <span className="about-section-title">Pipeline Neural de Processamento</span>
              <span className="about-section-sub">4 Etapas de Pipeline Local</span>
            </div>

            <div className="about-pipeline-flow">
              <div className="pipeline-step-item">
                <span className="pipeline-step-num">01</span>
                <div className="pipeline-step-info">
                  <span className="pipeline-step-name">Detecção e Segmentação</span>
                  <span className="pipeline-step-desc">Mapeamento poligonal de balões (Fala / SFX) e quadros</span>
                </div>
                <span className="pipeline-step-engine">YOLOv8</span>
              </div>

              <div className="pipeline-step-item">
                <span className="pipeline-step-num">02</span>
                <div className="pipeline-step-info">
                  <span className="pipeline-step-name">Ordenação de Leitura</span>
                  <span className="pipeline-step-desc">Sequenciamento espacial configurável (Mangá RTL / HQ LTR)</span>
                </div>
                <span className="pipeline-step-engine">Heurística Espacial</span>
              </div>

              <div className="pipeline-step-item">
                <span className="pipeline-step-num">03</span>
                <div className="pipeline-step-info">
                  <span className="pipeline-step-name">Extração Textual (OCR)</span>
                  <span className="pipeline-step-desc">Leitura óptica de diálogos em inglês (FP16)</span>
                </div>
                <span className="pipeline-step-engine">Florence-2</span>
              </div>

              <div className="pipeline-step-item">
                <span className="pipeline-step-num">04</span>
                <div className="pipeline-step-info">
                  <span className="pipeline-step-name">Tradução Contextual</span>
                  <span className="pipeline-step-desc">Adaptação semântica de diálogos com preservação de tom</span>
                </div>
                <span className="pipeline-step-engine">LLMs Locais · Ollama</span>
              </div>
            </div>
          </div>

          <div className="about-right-divider" />

          <div className="about-right-section">
            <div className="about-section-header">
              <span className="about-section-title">Especificações do Ambiente</span>
            </div>

            <div className="about-env-grid">
              <div className="env-grid-item">
                <span className="env-key">Engine de IA</span>
                <span className="env-val">PyTorch 2.11 · CUDA 12.8</span>
              </div>
              <div className="env-grid-item">
                <span className="env-key">Ambiente Local</span>
                <span className="env-val">Python 3.11 (64-bit)</span>
              </div>
              <div className="env-grid-item">
                <span className="env-key">Shell & Interface</span>
                <span className="env-val">Electron & React 19 · Vite</span>
              </div>
              <div className="env-grid-item">
                <span className="env-key">Privacidade</span>
                <span className="env-val">Zero Telemetria Externa</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
