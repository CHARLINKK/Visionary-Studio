import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChevronRight } from 'lucide-react';
import { clientApi, eventBus } from '../api/bridge';
import OnboardingMemoryVisualizer from './Onboarding/OnboardingMemoryVisualizer';
import OnboardingProfileSelect from './Onboarding/OnboardingProfileSelect';
import OnboardingDownloadingView from './Onboarding/OnboardingDownloadingView';
import './OnboardingModal.css';

/**
 * OnboardingModal Component
 * 
 * Wizard de Primeiro Início (First-Run AI Setup) do Visionary Studio.
 * Layout Widescreen Split-Studio (900px, Minimalista e Sóbrio).
 * 
 * @param {boolean} isOpen - Controla se o modal está visível
 * @param {Function} onClose - Callback chamado ao fechar/pular o wizard
 * @param {Function} onStartBackground - Callback chamado para notificar o App sobre download em segundo plano
 * @param {string} initialView - 'selection' ou 'downloading'
 */
export default function OnboardingModal({
  isOpen,
  onClose,
  onStartBackground,
  initialView = 'selection',
  isDebugPreview = false
}) {
  const [profile, setProfile] = useState('elite'); // 'elite' (Studio 32B) | 'fast' (Ágil 7B)
  const [viewState, setViewState] = useState(initialView); // 'selection' | 'downloading'
  const [runInBackground, setRunInBackground] = useState(true);
  const [downloadError, setDownloadError] = useState(null);

  // Sincroniza viewState com initialView ao abrir
  useEffect(() => {
    if (isOpen) {
      setViewState(initialView);
      setDownloadError(null);
    }
  }, [isOpen, initialView]);

  // Hardware Real
  const [hw, setHw] = useState({
    gpuName: 'NVIDIA GeForce RTX',
    vramTotal: 8.0,
    ramTotal: 32.0,
    isLoaded: false
  });

  // Progresso do Download
  const [dlStatus, setDlStatus] = useState({
    percent: 0,
    speedMb: 0,
    etaSec: 0,
    bytesDownloadedStr: '0 GB / 22.9 GB',
    statusText: 'Iniciando serviços locais...',
    ollamaDone: false,
    florenceDone: false,
    yoloDone: false
  });

  const pollIntervalRef = useRef(null);

  // Carrega hardware real do sistema
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    const fetchHw = async () => {
      try {
        const res = await clientApi.getHardwareStats();
        if (res && isMounted) {
          setHw({
            gpuName: res.gpu_name || 'NVIDIA GeForce RTX',
            vramTotal: res.vram_reserved_gb > 0 ? res.vram_reserved_gb : 8.0,
            ramTotal: res.ram_total_gb > 0 ? res.ram_total_gb : 32.0,
            isLoaded: true
          });
        }
      } catch (e) {
        console.warn('[Onboarding] Fallback para specs padrão de hardware:', e);
      }
    };
    fetchHw();

    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  // Limpa polling ao desmontar
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Cálculos dinâmicos de memória baseados no perfil selecionado
  const isElite = profile === 'elite';
  const targetVramGb = isElite ? 8.0 : 5.5;
  const targetRamGb = isElite ? 14.0 : 3.0;

  const vramPercent = Math.min(100, Math.round((targetVramGb / (hw.vramTotal || 8.0)) * 100));
  const ramPercent = Math.min(100, Math.round((targetRamGb / (hw.ramTotal || 32.0)) * 100));

  // Simulação de telemetria visual quando em Modo Debug
  useEffect(() => {
    if (!isOpen || !isDebugPreview) return;
    if (viewState === 'downloading') {
      const totGb = isElite ? 22.9 : 5.8;
      setDlStatus({
        percent: 42,
        speedMb: 68.5,
        etaSec: 195,
        bytesDownloadedStr: `${((42 / 100) * totGb).toFixed(1)} GB / ${totGb} GB (42%)`,
        statusText: 'Baixando camadas neurais (Simulação Visual)...',
        ollamaDone: false,
        florenceDone: true,
        yoloDone: true
      });
      const timer = setInterval(() => {
        setDlStatus(prev => {
          const nextPct = prev.percent >= 98 ? 32 : prev.percent + 3;
          return {
            ...prev,
            percent: nextPct,
            speedMb: +(62 + Math.random() * 12).toFixed(1),
            etaSec: Math.max(10, Math.round((100 - nextPct) * 3)),
            bytesDownloadedStr: `${((nextPct / 100) * totGb).toFixed(1)} GB / ${totGb} GB (${nextPct}%)`
          };
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [isOpen, isDebugPreview, viewState, isElite]);

  // Tecla ESC para fechar em modo de preview
  useEffect(() => {
    if (!isOpen || !isDebugPreview) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isDebugPreview, onClose]);

  const processProgress = useCallback((res, ollamaModelName, hfModelKey, totalSizeStr) => {
    if (!res || !res.success) return;
    const ollamaDl = res.ollama?.[ollamaModelName];
    const hfDl = res.hf?.[hfModelKey];
    const yoloDl = res.hf?.['yolo_detector'];

    const errMsg =
      (ollamaDl?.status === 'error' && (ollamaDl?.error || ollamaDl?.text)) ||
      (hfDl?.status === 'error' && (hfDl?.error || hfDl?.message)) ||
      (yoloDl?.status === 'error' && (yoloDl?.error || yoloDl?.message)) ||
      null;
    if (errMsg) {
      setDownloadError(String(errMsg));
    }

    let updatedStatus = null;
    setDlStatus((prev) => {
      const yoloDone = prev.yoloDone || 
        (yoloDl?.progress >= 100) || 
        (yoloDl?.status === 'installed') || 
        (yoloDl?.status === 'ready') ||
        (yoloDl?.status === 'completed');

      const florenceDone = prev.florenceDone || 
        (hfDl?.progress >= 100) || 
        (hfDl?.status === 'installed') || 
        (hfDl?.status === 'ready') ||
        (hfDl?.status === 'completed');

      const ollamaDone = prev.ollamaDone || 
        (ollamaDl?.progress >= 100) || 
        (ollamaDl?.status === 'success') || 
        (ollamaDl?.status === 'installed');

      const rawOllamaPct = typeof ollamaDl?.progress === 'number' ? ollamaDl.progress : 0;
      const rawHfPct = typeof hfDl?.progress === 'number' ? hfDl.progress : 0;
      const rawYoloPct = typeof yoloDl?.progress === 'number' ? yoloDl.progress : 0;

      const ollamaPct = ollamaDone ? 100 : Math.max(prev.ollamaPct || 0, rawOllamaPct);
      const hfPct = florenceDone ? 100 : Math.max(prev.hfPct || 0, rawHfPct);
      const yoloPct = yoloDone ? 100 : Math.max(prev.yoloPct || 0, rawYoloPct);

      const isDone = ollamaDone && florenceDone && yoloDone;

      // Média ponderada real: YOLO ~5% (70MB), Florence ~15% (1.4-3.1GB), Qwen ~80% (5.8-20GB)
      const calcOverall = Math.round((yoloPct * 0.05) + (hfPct * 0.15) + (ollamaPct * 0.80));
      const overallPct = isDone ? 100 : Math.max(prev.percent || 0, calcOverall);

      const speed = ollamaDl?.speed_mbps || 0;
      const eta = isDone ? 0 : (ollamaDl?.eta_seconds || 0);

      updatedStatus = {
        percent: overallPct,
        speedMb: speed,
        etaSec: eta,
        bytesDownloadedStr: `${((overallPct / 100) * (isElite ? 22.9 : 5.8)).toFixed(1)} GB / ${totalSizeStr} (${overallPct}%)`,
        statusText: isDone 
          ? 'Provisionamento concluído com sucesso!' 
          : (ollamaDl?.text || (!yoloDone ? 'Baixando detectores YOLO (70 MB)...' : !florenceDone ? 'Sincronizando visão computacional...' : 'Finalizando camadas do modelo neural...')),
        ollamaDone,
        florenceDone,
        yoloDone,
        ollamaPct,
        hfPct,
        yoloPct
      };

      if (isDone && pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }

      return updatedStatus;
    });

    if (updatedStatus && runInBackground && typeof onStartBackground === 'function') {
      onStartBackground({
        model: ollamaModelName,
        profile,
        progress: updatedStatus.percent,
        speedMb: updatedStatus.speedMb,
        text: updatedStatus.percent >= 100 ? 'Modelos prontos' : `Baixando IA (${updatedStatus.percent}%)`
      });
    }
  }, [isElite, onStartBackground, profile, runInBackground]);

  const startProgressPolling = useCallback((ollamaModelName, hfModelKey, totalSizeStr) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(async () => {
      if (eventBus.isConnected()) return;
      try {
        const res = await clientApi.getDownloadsProgress();
        processProgress(res, ollamaModelName, hfModelKey, totalSizeStr);
      } catch {
        // Erro silencioso no polling
      }
    }, 800);
  }, [processProgress]);

  // Escuta telemetria do WebSocket via EventBus e atualiza progresso em tempo real
  useEffect(() => {
    if (!isOpen || viewState !== 'downloading' || isDebugPreview) return;

    const ollamaModelName = isElite ? 'amadeus:32b' : 'amadeus:7b';
    const hfModelKey = isElite ? 'florence2_large' : 'florence2';
    const totalSizeStr = isElite ? '22.9 GB' : '5.8 GB';

    const unsub = eventBus.subscribe((payload) => {
      if (payload?.type === 'custom_event' && payload.event_name === 'downloads_progress' && payload.payload) {
        processProgress(payload.payload, ollamaModelName, hfModelKey, totalSizeStr);
      }
    });

    return () => unsub();
  }, [isOpen, viewState, isDebugPreview, isElite, processProgress]);

  // Retoma o polling automaticamente se o usuário reabrir o modal a partir da pílula da Titlebar
  useEffect(() => {
    if (isOpen && viewState === 'downloading' && !isDebugPreview && !pollIntervalRef.current) {
      const ollamaModelName = isElite ? 'amadeus:32b' : 'amadeus:7b';
      const hfModelKey = isElite ? 'florence2_large' : 'florence2';
      const totalSizeStr = isElite ? '22.9 GB' : '5.8 GB';
      startProgressPolling(ollamaModelName, hfModelKey, totalSizeStr);
    }
  }, [isOpen, viewState, isDebugPreview, isElite, startProgressPolling]);

  // Iniciar Provisionamento
  const handleStartInstallation = async () => {
    setDownloadError(null);
    setViewState('downloading');

    if (isDebugPreview) {
      return;
    }

    const ollamaModelName = isElite ? 'amadeus:32b' : 'amadeus:7b';
    const hfModelKey = isElite ? 'florence2_large' : 'florence2';
    const totalSizeStr = isElite ? '22.9 GB' : '5.8 GB';

    setDlStatus({
      percent: 0,
      speedMb: 0,
      etaSec: 0,
      bytesDownloadedStr: `0 GB / ${totalSizeStr}`,
      statusText: 'Iniciando serviços locais...',
      ollamaDone: false,
      florenceDone: false,
      yoloDone: false,
    });

    if (runInBackground && typeof onStartBackground === 'function') {
      onStartBackground({
        model: ollamaModelName,
        profile,
        progress: 0,
        text: `Baixando IA (${ollamaModelName})`
      });
    }

    try {
      const ollamaRes = await clientApi.ensureOllamaRunning();
      if (ollamaRes && ollamaRes.success === false) {
        throw new Error(ollamaRes.error || ollamaRes.message || 'Não foi possível iniciar o serviço local Ollama.');
      }

      startProgressPolling(ollamaModelName, hfModelKey, totalSizeStr);

      const results = await Promise.allSettled([
        Promise.resolve(clientApi.pullOllamaModel(ollamaModelName)),
        Promise.resolve(clientApi.downloadHuggingFaceModel(hfModelKey)),
        Promise.resolve(clientApi.downloadHuggingFaceModel('yolo_detector')),
      ]);

      const rejected = results.find((r) => r.status === 'rejected');
      if (rejected) {
        throw rejected.reason;
      }

      const hardFailure = results.find(
        (r) =>
          r.status === 'fulfilled' &&
          r.value &&
          r.value.success === false &&
          !String(r.value.message || '').includes('Já está baixando')
      );
      if (hardFailure) {
        throw new Error(hardFailure.value.error || hardFailure.value.message || 'Falha ao iniciar o download dos modelos de IA.');
      }
    } catch (err) {
      console.error('[Onboarding] Erro ao disparar download:', err);
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      setDownloadError(err?.message || 'Falha ao iniciar os serviços locais de IA.');
    }
  };

  const handleBackToSelection = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setDownloadError(null);
    setViewState('selection');
  };

  // Pular ou finalizar
  const handleCompleteOrSkip = async () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    if (isDebugPreview) {
      onClose();
      return;
    }

    try {
      const targetOllamaModel = isElite ? 'amadeus:32b' : 'amadeus:7b';
      let currentSelected = {};
      try {
        const existing = await clientApi.getSettings();
        if (existing?.selected_models && typeof existing.selected_models === 'object') {
          currentSelected = existing.selected_models;
        }
      } catch (_) {}
      await clientApi.saveSettings({
        first_run_completed: true,
        selected_profile: profile,
        selected_models: {
          ...currentSelected,
          transPol: currentSelected.transPol || targetOllamaModel
        }
      });
    } catch (e) {
      console.error('[Onboarding] Falha ao salvar flag de primeiro boot:', e);
    }

    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="onboarding-overlay" onClick={(e) => e.stopPropagation()}>
      <div className="onboarding-window" role="dialog" aria-modal="true">
        
        {/* COLUNA ESQUERDA: Identidade & Medidor Gráfico Dinâmico */}
        <div className="onboarding-left-panel">
          <div className="onboarding-brand-group">
            <div className="onboarding-brand-badge">
              <span className="onboarding-brand-gem"></span>
              <span>Visionary Studio</span>
              {isDebugPreview && (
                <span className="onboarding-debug-badge">PREVIEW DEBUG</span>
              )}
            </div>

            <h1 className="onboarding-left-title">Configuração do Motor de IA</h1>

            <p className="onboarding-left-desc">
              O Visionary executa visão computacional e modelos neurais localmente para máxima privacidade e operação 100% offline.
            </p>

            <OnboardingMemoryVisualizer
              isElite={isElite}
              hw={hw}
              targetVramGb={targetVramGb}
              targetRamGb={targetRamGb}
              vramPercent={vramPercent}
              ramPercent={ramPercent}
            />
          </div>

          <div className="onboarding-left-footer">
            <button 
              type="button" 
              className="onboarding-skip-link" 
              onClick={handleCompleteOrSkip}
            >
              <span>Pular calibração e abrir estúdio</span>
              <ChevronRight size={13} />
            </button>
          </div>
        </div>

        {/* COLUNA DIREITA: Seleção Espaçosa ou Download */}
        <div className="onboarding-right-panel">
          {viewState === 'selection' ? (
            <OnboardingProfileSelect
              profile={profile}
              setProfile={setProfile}
              isElite={isElite}
              runInBackground={runInBackground}
              setRunInBackground={setRunInBackground}
              handleStartInstallation={handleStartInstallation}
              isDebugPreview={isDebugPreview}
              onClose={onClose}
            />
          ) : (
            <OnboardingDownloadingView
              dlStatus={dlStatus}
              isElite={isElite}
              isDebugPreview={isDebugPreview}
              downloadError={downloadError}
              onRetry={handleStartInstallation}
              onBackToSelection={handleBackToSelection}
              onClose={onClose}
              handleCompleteOrSkip={handleCompleteOrSkip}
            />
          )}
        </div>

      </div>
    </div>
  );
}
