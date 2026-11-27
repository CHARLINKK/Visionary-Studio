import { useState, useEffect, useRef, useMemo } from 'react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { clientApi } from '../api/bridge';

/**
 * calculateLogStats
 * Analisa a coleção de logs de execução para apurar contagem de erros, avisos,
 * estágios percorridos na pipeline (layout, ocr, translate) e tempo decorrido total.
 */
export function calculateLogStats(logs = []) {
  if (!Array.isArray(logs) || logs.length === 0) {
    return {
      errorCount: 0,
      warningCount: 0,
      timeElapsed: '00:00',
      currentStage: 'Pronto',
      stagesSeen: new Set()
    };
  }

  let errorCount = 0;
  let warningCount = 0;
  const stagesSeen = new Set();

  logs.forEach(line => {
    if (typeof line !== 'string') return;
    const lower = line.toLowerCase();
    if (line.includes('[ERRO]') || lower.includes('error') || lower.includes('exception') || lower.includes('traceback')) {
      errorCount++;
    }
    if (line.includes('[AVISO]') || lower.includes('warning')) {
      warningCount++;
    }
    if (line.includes('[LAYOUT]') || lower.includes('yolo') || lower.includes('detecção')) {
      stagesSeen.add('layout');
    }
    if (line.includes('[OCR]') || lower.includes('florence') || lower.includes('extração')) {
      stagesSeen.add('ocr');
    }
    if (line.includes('[TRADUÇÃO]') || line.includes('[TRADUTOR]') || lower.includes('qwen') || lower.includes('llm')) {
      stagesSeen.add('translate');
    }
  });

  // Cálculo do tempo decorrido a partir dos timestamps [HH:MM:SS]
  const timeRegex = /^\[(\d{2}):(\d{2}):(\d{2})\]/;
  let startTime = null;
  let endTime = null;

  for (let i = 0; i < logs.length; i++) {
    const match = typeof logs[i] === 'string' ? logs[i].match(timeRegex) : null;
    if (match) {
      startTime = new Date();
      startTime.setHours(Number(match[1]), Number(match[2]), Number(match[3]));
      break;
    }
  }

  for (let i = logs.length - 1; i >= 0; i--) {
    const match = typeof logs[i] === 'string' ? logs[i].match(timeRegex) : null;
    if (match) {
      endTime = new Date();
      endTime.setHours(Number(match[1]), Number(match[2]), Number(match[3]));
      break;
    }
  }

  let timeElapsed = '00:00';
  if (startTime && endTime) {
    const diffSec = Math.max(0, Math.floor((endTime - startTime) / 1000));
    const m = Math.floor(diffSec / 60).toString().padStart(2, '0');
    const s = (diffSec % 60).toString().padStart(2, '0');
    timeElapsed = `${m}:${s}`;
  }

  return { errorCount, warningCount, timeElapsed, currentStage: 'Pronto', stagesSeen };
}

/**
 * filterLogs
 * Aplica filtragem de categoria (all | errors | warnings | pipeline) e busca textual (grep).
 */
export function filterLogs(logs = [], activeFilter = 'all', searchQuery = '') {
  if (!Array.isArray(logs)) return [];
  let list = logs;

  if (activeFilter === 'errors') {
    list = list.filter(l => typeof l === 'string' && (l.includes('[ERRO]') || l.toLowerCase().includes('error') || l.toLowerCase().includes('exception') || l.toLowerCase().includes('traceback')));
  } else if (activeFilter === 'warnings') {
    list = list.filter(l => typeof l === 'string' && (l.includes('[AVISO]') || l.toLowerCase().includes('warning')));
  } else if (activeFilter === 'pipeline') {
    list = list.filter(l => typeof l === 'string' && (l.includes('[LAYOUT]') || l.includes('[OCR]') || l.includes('[TRADUÇÃO]') || l.includes('[TRADUTOR]') || l.includes('===')));
  }

  if (searchQuery && typeof searchQuery === 'string' && searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    list = list.filter(l => typeof l === 'string' && l.toLowerCase().includes(q));
  }

  return list;
}

/**
 * useBatchQueue
 * Hook desacoplado de gerenciamento da fila de tarefas em lote do Visionary Studio.
 * Encapsula o estado global de fila, polling de progresso, console de telemetria,
 * autoscroll, métricas VRAM e atalhos de teclado.
 */
export function useBatchQueue() {
  const jobQueue = useWorkspaceStore(state => state.jobQueue);
  const updateJob = useWorkspaceStore(state => state.updateJob);
  const clearCompletedJobs = useWorkspaceStore(state => state.clearCompletedJobs);
  const clearJobLogs = useWorkspaceStore(state => state.clearJobLogs);

  const [logModalJobId, setLogModalJobId] = useState(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all'); // 'all' | 'errors' | 'warnings' | 'pipeline'
  const [isExpanded, setIsExpanded] = useState(false);

  const logContainerRef = useRef(null);

  /**
   * handleCancelJob
   * Força cancelamento e descarte (Kill) do processo rodando no worker do Python.
   */
  const handleCancelJob = (jobId, hardReset = false) => {
    clientApi.cancelJob(jobId, hardReset).catch(() => {});
    updateJob(jobId, { status: 'cancelled', currentStepLabel: 'Cancelado', error: 'Interrompido pelo usuário' });
  };

  const runningJobs = useMemo(
    () => (Array.isArray(jobQueue) ? jobQueue.filter(j => j.status === 'running' || j.status === 'pending') : []),
    [jobQueue]
  );

  const completedJobs = useMemo(
    () => (Array.isArray(jobQueue) ? jobQueue.filter(j => j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled') : []),
    [jobQueue]
  );

  // Sincronização periódica com o backend (Polling HTTP resiliente)
  useEffect(() => {
    let interval;
    if (runningJobs.length > 0 || logModalJobId) {
      const syncJobs = async () => {
        try {
          const res = await clientApi.getPipelineStatus();
          if (res && res.success && res.jobs) {
            const currentQueue = useWorkspaceStore.getState().jobQueue || [];
            const currentJobsMap = new Map(currentQueue.map(j => [j.id, j]));
            Object.entries(res.jobs).forEach(([jobId, backendJob]) => {
              const currentJob = currentJobsMap.get(jobId);
              const updates = {};
              // Preserva logs do WebSocket em tempo real: só atualiza se o backend tiver mais logs ou se o job finalizou
              if (backendJob.logs && (!currentJob || backendJob.logs.length >= (currentJob.logs?.length || 0))) {
                updates.logs = backendJob.logs;
              }
              if (backendJob.progress !== undefined) updates.progress = backendJob.progress;
              if (backendJob.step_label) updates.currentStepLabel = backendJob.step_label;
              if (backendJob.vramState !== undefined) updates.vramState = backendJob.vramState;
              if (backendJob.vramRealtime !== undefined) updates.vramRealtime = backendJob.vramRealtime;
              if (backendJob.status && (backendJob.status === 'completed' || backendJob.status === 'failed' || backendJob.status === 'cancelled')) {
                updates.status = backendJob.status;
                if (backendJob.error) updates.error = backendJob.error;
              }
              updateJob(jobId, updates);
            });

            // Reconciliação de jobs órfãos: se um job com startedAt (> 4s) consta como ativo na UI
            // mas não existe mais no dicionário do backend (ex: após reinício do sidecar Python),
            // marca como failed para liberar a fila, hasActiveWork e powerSaveBlocker.
            const now = Date.now();
            currentQueue.forEach((localJob) => {
              if (
                (localJob.status === 'running' || localJob.status === 'pending' || localJob.status === 'queued') &&
                !res.jobs[localJob.id] &&
                typeof localJob.startedAt === 'number' &&
                localJob.startedAt > 0 &&
                now - localJob.startedAt > 4000
              ) {
                updateJob(localJob.id, {
                  status: 'failed',
                  error: 'O motor de IA foi reiniciado durante a execução. Você pode reexecutar o lote com segurança.',
                  currentStepLabel: 'Interrompido (Motor reiniciado)',
                });
              }
            });
          }
        } catch {}
      };
      syncJobs();
      interval = setInterval(syncJobs, 2500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [runningJobs.length, logModalJobId, updateJob]);

  // Tecla ESC para fechar o Drawer
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && logModalJobId) {
        setLogModalJobId(null);
      }
    };
    if (typeof window !== 'undefined') {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [logModalJobId]);

  // Auto-scroll ao abrir ou ao chegar novos logs
  useEffect(() => {
    if (logModalJobId && logContainerRef.current && autoScroll) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [jobQueue, logModalJobId, autoScroll, searchQuery, activeFilter]);

  const handleLogScroll = (e) => {
    if (!e || !e.target) return;
    const el = e.target;
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(isAtBottom);
  };

  const logModalJob = useMemo(() => {
    if (!logModalJobId || !Array.isArray(jobQueue)) return null;
    return jobQueue.find(j => j.id === logModalJobId) || null;
  }, [jobQueue, logModalJobId]);

  const handleCopyLogs = (e) => {
    if (e && typeof e.stopPropagation === 'function') {
      e.stopPropagation();
    }
    if (logModalJob && Array.isArray(logModalJob.logs)) {
      if (typeof navigator !== 'undefined' && navigator?.clipboard?.writeText) {
        navigator.clipboard.writeText(logModalJob.logs.join('\n')).catch(() => {});
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleClearLogs = (e) => {
    if (e && typeof e.stopPropagation === 'function') {
      e.stopPropagation();
    }
    if (logModalJobId) {
      clearJobLogs(logModalJobId);
    }
  };

  // Análise estatística e de telemetria dos logs
  const stats = useMemo(() => {
    return calculateLogStats(logModalJob?.logs);
  }, [logModalJob]);

  // Filtragem dos logs
  const filteredLogs = useMemo(() => {
    return filterLogs(logModalJob?.logs, activeFilter, searchQuery);
  }, [logModalJob, activeFilter, searchQuery]);

  return {
    jobQueue,
    runningJobs,
    completedJobs,
    handleCancelJob,
    clearCompletedJobs,
    clearJobLogs,
    logModalJobId,
    setLogModalJobId,
    logModalJob,
    autoScroll,
    setAutoScroll,
    handleLogScroll,
    logContainerRef,
    copied,
    handleCopyLogs,
    handleClearLogs,
    searchQuery,
    setSearchQuery,
    activeFilter,
    setActiveFilter,
    isExpanded,
    setIsExpanded,
    stats,
    filteredLogs
  };
}

export default useBatchQueue;
