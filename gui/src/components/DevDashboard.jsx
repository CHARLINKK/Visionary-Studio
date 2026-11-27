import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Terminal, Sparkles, Download, Image as ImageIcon, Zap 
} from 'lucide-react';
import { useToast } from '../contexts/ToastContext';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { clientApi, eventBus } from '../api/bridge';
import DevHardwareCard from './DevDashboard/DevHardwareCard';
import DevTestRunner from './DevDashboard/DevTestRunner';
import DevConsoleViewer from './DevDashboard/DevConsoleViewer';
import './DevDashboard.css';

const DEFAULT_TEST_FILES = [
  { filename: 'all', label: '🧪 Executar Todos (Suíte Completa)' },
  { filename: 'test_audit_fixes.py', label: 'Auditoria, Endpoints & RPC' },
  { filename: 'test_config_and_resilience.py', label: 'Configurações & Resiliência JSON' },
  { filename: 'test_desktop_lifecycle.py', label: 'Ciclo de Vida Desktop & Watchdog' },
  { filename: 'test_dev_service.py', label: 'Serviço de Diagnóstico & Telemetria' },
  { filename: 'test_fresh_pc_simulation.py', label: 'Simulação de PC Limpo & Cold Start' },
  { filename: 'test_fs_explorer.py', label: 'Explorador de Arquivos & Unidades' },
  { filename: 'test_json_utils.py', label: 'Utilitários de JSON & Autocura' },
  { filename: 'test_layout_detector.py', label: 'Detecção de Layout & YOLO Bubbles' },
  { filename: 'test_library_features.py', label: 'Biblioteca & Exportação de Roteiros' },
  { filename: 'test_model_service_expansion.py', label: 'Model Manager, Telemetria & PyTorch' },
  { filename: 'test_pipeline_lifecycle.py', label: 'Ciclo de Vida do Pipeline & Fila' },
  { filename: 'test_pipeline_regressions.py', label: 'Regressões Críticas do Pipeline (M1-M5)' },
  { filename: 'test_services_decoupling.py', label: 'Desacoplamento & EventBus Pub/Sub' },
  { filename: 'test_studio_and_backup.py', label: 'Studio Workspace & SSOT de Página' },
  { filename: 'test_text_cleaner_and_translator.py', label: 'Limpeza Semântica & Tradução AI' },
  { filename: 'test_txt_sync.py', label: 'Sincronização TXT & Studio Live Edit' }
];

/**
 * DevDashboard Component
 * 
 * Painel de Testes Unitários e Telemetria para Desenvolvimento.
 * @warning Componente apenas para Debug. Em produção fica oculto do menu.
 */
export default function DevDashboard({ isActive = true }) {
  const [testLogs, setTestLogs] = useState([]);
  const [appLogs, setAppLogs] = useState([]);
  const [events, setEvents] = useState([]);
  const [activeConsole, setActiveConsole] = useState('app'); // 'app' | 'test' | 'events'
  const [isRunningTest, setIsRunningTest] = useState(false);
  const [devStats, setDevStats] = useState(null);
  const [testFiles, setTestFiles] = useState(DEFAULT_TEST_FILES);
  const [selectedTest, setSelectedTest] = useState('all');
  const [autoScroll, setAutoScroll] = useState(true);
  
  // ── Filtros e Busca do Console ──
  const [logSearch, setLogSearch] = useState('');
  const [logFilter, setLogFilter] = useState('all'); // 'all' | 'error' | 'warning' | 'success'
  
  // ── Telemetria dos Testes em Tempo Real ──
  const [testProgress, setTestProgress] = useState({
    running: false,
    percent: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    total: 0,
    current_test: ''
  });

  const { addToast } = useToast();
  const consoleRef = useRef(null);

  // ── Opções de Diagnóstico e Pipeline (Modo Dev) ──
  const [debugPanelMaps, setDebugPanelMaps] = useState(false);

  useEffect(() => {
    clientApi.getSettings().then(settings => {
      if (settings) {
        setDebugPanelMaps(Boolean(settings.debugPanelMaps));
      }
    }).catch(() => {});
  }, []);

  const handleToggleDebugPanelMaps = async () => {
    const nextVal = !debugPanelMaps;
    setDebugPanelMaps(nextVal);
    try {
      const current = await clientApi.getSettings() || {};
      await clientApi.saveSettings({ ...current, debugPanelMaps: nextVal });
      addToast(nextVal ? "Mapas Visuais de Painéis ATIVADOS (Gera JPGs de debug no lote)" : "Mapas Visuais de Painéis DESATIVADOS", "info");
    } catch (e) {
      console.error(e);
    }
  };

  const handleOpenOnboardingPreview = (view = 'selection') => {
    useWorkspaceStore.getState().openOnboarding({ view, isDebugPreview: true });
    addToast(
      view === 'selection' 
        ? "Preview Setup Wizard (Seleção de Perfil) aberto em modo Debug" 
        : "Preview Setup Wizard (Download & Telemetria) aberto em modo Debug",
      "info"
    );
  };

  const fetchLogs = async () => {
    try {
      const res = await clientApi.getDevLogs();
      if (res) {
        setTestLogs(res.test_logs || []);
        setAppLogs(res.app_logs || []);
        setIsRunningTest(res.test_running);
        if (res.test_progress) {
          setTestProgress(res.test_progress);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await clientApi.getDevStats();
      if (res) setDevStats(res);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchTestFiles = async () => {
    try {
      const res = await clientApi.getTestList();
      if (res?.files?.length > 0) {
        const totalLabel = res.total_tests_estimate ? `${res.total_tests_estimate} Testes - Suíte Completa` : 'Suíte Completa';
        setTestFiles([
          { filename: 'all', label: `🧪 Executar Todos (${totalLabel})` },
          ...res.files
        ]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunTests = async () => {
    try {
      const res = await clientApi.runTests(selectedTest === 'all' ? null : selectedTest);
      if (res.success) {
        addToast(res.message, "info");
        setActiveConsole('test');
        setIsRunningTest(true);
        setTestLogs([]);
        setTestProgress({
          running: true,
          percent: 0,
          passed: 0,
          failed: 0,
          skipped: 0,
          total: selectedTest === 'all' ? (res.total_tests_estimate || testProgress.total || 0) : 0,
          current_test: 'Iniciando testes...'
        });
      } else {
        addToast(res.error, "error");
      }
    } catch {
      addToast("Erro ao comunicar com a API", "error");
    }
  };

  const handleCancelTests = async () => {
    try {
      const res = await clientApi.cancelTests();
      if (res?.success) {
        addToast("Cancelamento solicitado...", "info");
      } else {
        addToast(res?.error || "Erro ao cancelar testes", "error");
      }
    } catch {
      addToast("Erro ao contatar backend para cancelamento", "error");
    }
  };

  const handleClearVRAM = async () => {
    addToast("Limpando VRAM e esvaziando cache...", "info");
    const res = await clientApi.clearVRAM();
    if (res?.success) {
      addToast("VRAM e Garbage Collector liberados.", "success");
      fetchStats();
    }
  };

  const handleUnloadModel = async (modelKey) => {
    addToast(`Descarregando ${modelKey} da GPU...`, "info");
    try {
      const res = await clientApi.unloadDevModel(modelKey);
      if (res?.success) {
        addToast(res.message || "Modelo descarregado com sucesso.", "success");
        fetchStats();
      }
    } catch {
      addToast("Falha ao descarregar modelo.", "error");
    }
  };

  const handleCopyLogs = () => {
    if (activeConsole === 'events') {
      navigator.clipboard.writeText(JSON.stringify(events, null, 2));
      addToast("Eventos copiados em formato JSON!", "success");
      return;
    }
    const logs = activeConsole === 'test' ? testLogs : appLogs;
    navigator.clipboard.writeText(logs.join('\n'));
    addToast("Logs copiados com sucesso!", "success");
  };

  const handleClearCurrentLogs = () => {
    if (activeConsole === 'test') setTestLogs([]);
    else if (activeConsole === 'app') setAppLogs([]);
    else if (activeConsole === 'events') setEvents([]);
    addToast("Logs limpos na visualização local.", "info");
  };

  // ── Monitor de Eventos em Tempo Real (EventBus Spy & Pub/Sub Reativo) ──
  useEffect(() => {
    const unsubscribe = eventBus.subscribe((payload) => {
      if (!payload) return;
      const evtName = payload.type || payload.event_name || 'event';
      const evtData = payload.payload !== undefined ? payload.payload : payload;

      if (evtName === 'dev:log' && evtData?.line) {
        if (evtData.stream === 'test') {
          setTestLogs(prev => [...prev.slice(-1999), evtData.line]);
        } else {
          setAppLogs(prev => [...prev.slice(-1999), evtData.line]);
        }
        return;
      }

      if (evtName === 'dev:test_progress' && evtData) {
        setTestProgress(evtData);
        setIsRunningTest(Boolean(evtData.running));
        return;
      }

      if ((evtName === 'vram:realtime' || evtName === 'hardware:stats') && evtData) {
        setDevStats(prev => {
          if (!prev) return prev;
          const usedGb = evtData.vram_used_gb ?? prev.vram_used_gb ?? 0;
          const totalGb = evtData.vram_total_gb || prev.vram_total_gb || 0;
          const freeGb = totalGb > 0 ? Math.max(0, Number((totalGb - usedGb).toFixed(2))) : prev.vram_free_gb;
          const pct = totalGb > 0 ? Math.min(100, Math.max(0, Math.round((usedGb / totalGb) * 100))) : prev.vram_pct;
          return {
            ...prev,
            vram_used_gb: usedGb,
            vram_total_gb: totalGb || prev.vram_total_gb,
            vram_free_gb: freeGb,
            vram_pct: pct,
          };
        });
      }

      const newEvent = {
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString(),
        name: evtName,
        payload: evtData
      };
      setEvents(prev => [newEvent, ...prev.slice(0, 199)]);
    });

    return () => {
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!isActive) return;

    fetchStats();
    fetchLogs();
    fetchTestFiles();
  }, [isActive]);

  useEffect(() => {
    if (consoleRef.current && autoScroll && activeConsole !== 'events') {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [testLogs, appLogs, activeConsole, autoScroll, logFilter, logSearch]);

  // ── Filtragem de Logs ──
  const filteredLogs = useMemo(() => {
    const sourceLogs = activeConsole === 'test' ? testLogs : appLogs;
    if (!sourceLogs) return [];

    return sourceLogs.filter(log => {
      if (logSearch.trim()) {
        if (!log.toLowerCase().includes(logSearch.toLowerCase().trim())) {
          return false;
        }
      }

      if (logFilter === 'error') {
        return log.includes('FAILED') || log.includes('ERROR') || log.includes('[ERRO]') || log.includes('FALHAS');
      }
      if (logFilter === 'warning') {
        return log.includes('WARNING') || log.includes('SKIPPED') || log.includes('[AVISO]') || log.includes('[DEV]');
      }
      if (logFilter === 'success') {
        return log.includes('PASSED') || log.includes('SUCESSO') || log.includes('OK');
      }

      return true;
    });
  }, [activeConsole, testLogs, appLogs, logSearch, logFilter]);

  return (
    <div className="dev-dashboard-container">
      <div className="dev-dashboard-header">
        <div className="header-info">
          <div className="header-icon-wrapper">
            <Terminal size={20} />
          </div>
          <div>
            <h2>Diagnóstico & Central de Telemetria</h2>
            <span className="header-subtitle">Modo Desenvolvedor // Painel Operacional do Visionary Core</span>
          </div>
        </div>

        <div className="header-quick-actions">
          <button 
            className="action-pill-btn" 
            onClick={() => handleOpenOnboardingPreview('selection')}
            title="Preview Debug: Abre o Setup Wizard na etapa 1 (seleção de perfil e medidor de memória) sem disparar downloads reais"
          >
            <Sparkles size={13} color="#a855f7" />
            <span>Wizard: Perfis (Debug)</span>
          </button>
          <button 
            className="action-pill-btn" 
            onClick={() => handleOpenOnboardingPreview('downloading')}
            title="Preview Debug: Abre o Setup Wizard na etapa 2 (tela de download e telemetria simulada) sem disparar downloads reais"
          >
            <Download size={13} color="#38bdf8" />
            <span>Wizard: Download (Debug)</span>
          </button>
          <button 
            className={`action-pill-btn ${debugPanelMaps ? 'active' : ''}`} 
            onClick={handleToggleDebugPanelMaps}
            title={debugPanelMaps ? "Mapas Visuais ATIVADOS: salva [página]_mapa.jpg com caixas azuis (painéis) e vermelhas (balões) na pasta output/ durante o lote (Clique para desativar)" : "Mapas Visuais DESATIVADOS: processamento sem gerar imagens de depuração no disco (Clique para ativar)"}
          >
            <ImageIcon size={13} />
            <span>Mapas Visuais (Debug): {debugPanelMaps ? 'ON' : 'OFF'}</span>
          </button>
          <button 
            className="action-pill-btn" 
            onClick={handleClearVRAM}
            title="Esvaziar pool de memória da GPU e Garbage Collector"
          >
            <Zap size={13} /> Limpar VRAM
          </button>
        </div>
      </div>

      <DevHardwareCard 
        devStats={devStats}
        handleClearVRAM={handleClearVRAM}
        handleUnloadModel={handleUnloadModel}
      />

      {/* ── Controles de Execução de Testes & Abas do Console ── */}
      <div className="dev-actions-row">
        <DevTestRunner
          testFiles={testFiles}
          selectedTest={selectedTest}
          setSelectedTest={setSelectedTest}
          isRunningTest={isRunningTest}
          handleRunTests={handleRunTests}
          handleCancelTests={handleCancelTests}
          testProgress={testProgress}
        />
      </div>

      <DevConsoleViewer
        activeConsole={activeConsole}
        setActiveConsole={setActiveConsole}
        isRunningTest={isRunningTest}
        events={events}
        testProgress={testProgress}
        handleCopyLogs={handleCopyLogs}
        handleClearCurrentLogs={handleClearCurrentLogs}
        logSearch={logSearch}
        setLogSearch={setLogSearch}
        logFilter={logFilter}
        setLogFilter={setLogFilter}
        filteredLogs={filteredLogs}
        consoleRef={consoleRef}
        setAutoScroll={setAutoScroll}
      />
    </div>
  );
}
