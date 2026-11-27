import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor, cleanup } from '@testing-library/react';
import { useBatchQueue, calculateLogStats, filterLogs } from '../useBatchQueue';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';

describe('useBatchQueue — pure utilities', () => {
  describe('calculateLogStats', () => {
    it('returns default metrics when logs are empty or invalid', () => {
      const emptyResult = calculateLogStats([]);
      expect(emptyResult.errorCount).toBe(0);
      expect(emptyResult.warningCount).toBe(0);
      expect(emptyResult.timeElapsed).toBe('00:00');
      expect(emptyResult.stagesSeen.size).toBe(0);

      const nullResult = calculateLogStats(null);
      expect(nullResult.errorCount).toBe(0);
      expect(nullResult.timeElapsed).toBe('00:00');
    });

    it('accurately counts error and warning variations', () => {
      const logs = [
        '[12:00:00] Início do processo',
        '[12:00:01] [AVISO] Modelo operando em modo fallback',
        '[12:00:02] warning: taxa de transferência reduzida',
        '[12:00:03] [ERRO] Falha ao alocar buffer',
        '[12:00:04] Unhandled exception occurred',
        '[12:00:05] Traceback (most recent call last):',
        '[12:00:06] Fatal Error in worker thread',
      ];

      const stats = calculateLogStats(logs);
      expect(stats.warningCount).toBe(2);
      expect(stats.errorCount).toBe(4);
    });

    it('identifies pipeline stages seen from tags and keywords', () => {
      const logs = [
        '[10:00:00] [LAYOUT] Segmentando caixas de texto',
        '[10:00:01] Executando detecção via YOLOv8',
        '[10:00:02] [OCR] Lendo texto na imagem',
        '[10:00:03] Florence extração de caracteres',
        '[10:00:04] [TRADUÇÃO] Enviando para Qwen LLM',
      ];

      const stats = calculateLogStats(logs);
      expect(stats.stagesSeen.has('layout')).toBe(true);
      expect(stats.stagesSeen.has('ocr')).toBe(true);
      expect(stats.stagesSeen.has('translate')).toBe(true);
    });

    it('calculates elapsed time from initial to final timestamp', () => {
      const logs = [
        '[10:15:10] Início',
        'Log sem timestamp no meio',
        '[10:17:45] Finalizado',
      ];

      const stats = calculateLogStats(logs);
      // 10:15:10 to 10:17:45 = 2 minutes and 35 seconds
      expect(stats.timeElapsed).toBe('02:35');
    });
  });

  describe('filterLogs', () => {
    const sampleLogs = [
      '[10:00:00] === INICIANDO PIPELINE ===',
      '[10:00:01] [LAYOUT] Análise de balões',
      '[10:00:02] [AVISO] Baixo contraste detectado',
      '[10:00:03] [ERRO] Timeout na inferência',
      '[10:00:04] [OCR] Concluído',
      '[10:00:05] [TRADUÇÃO] Concluída com sucesso',
    ];

    it('returns all logs for "all" filter without query', () => {
      const result = filterLogs(sampleLogs, 'all', '');
      expect(result.length).toBe(6);
    });

    it('filters only errors for "errors" filter', () => {
      const result = filterLogs(sampleLogs, 'errors', '');
      expect(result).toEqual(['[10:00:03] [ERRO] Timeout na inferência']);
    });

    it('filters only warnings for "warnings" filter', () => {
      const result = filterLogs(sampleLogs, 'warnings', '');
      expect(result).toEqual(['[10:00:02] [AVISO] Baixo contraste detectado']);
    });

    it('filters pipeline milestone events for "pipeline" filter', () => {
      const result = filterLogs(sampleLogs, 'pipeline', '');
      expect(result.length).toBe(4);
      expect(result).toContain('[10:00:00] === INICIANDO PIPELINE ===');
      expect(result).toContain('[10:00:01] [LAYOUT] Análise de balões');
      expect(result).toContain('[10:00:04] [OCR] Concluído');
      expect(result).toContain('[10:00:05] [TRADUÇÃO] Concluída com sucesso');
    });

    it('applies search query case-insensitively', () => {
      const result = filterLogs(sampleLogs, 'all', 'INFERÊNCIA');
      expect(result).toEqual(['[10:00:03] [ERRO] Timeout na inferência']);
    });

    it('combines category filter with search query', () => {
      const result = filterLogs(sampleLogs, 'pipeline', 'ocr');
      expect(result).toEqual(['[10:00:04] [OCR] Concluído']);
    });
  });
});

describe('useBatchQueue — hook integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();

    window.pywebview = {
      api: {
        cancelJob: vi.fn().mockResolvedValue({ success: true }),
        getPipelineStatus: vi.fn().mockResolvedValue({ success: true, jobs: {} }),
        clearCompletedJobs: vi.fn().mockResolvedValue({ success: true }),
        clearJobLogs: vi.fn().mockResolvedValue({ success: true }),
      },
    };

    useWorkspaceStore.setState({
      jobQueue: [
        {
          id: 'job-1',
          page: '001.png',
          status: 'idle',
          progress: 0,
          currentStepLabel: 'Aguardando...',
          logs: [
            '[10:00:00] [LAYOUT] Iniciado',
            '[10:00:15] [OCR] Extraindo texto',
          ],
        },
        {
          id: 'job-2',
          page: '002.png',
          status: 'completed',
          progress: 100,
          currentStepLabel: 'Concluído',
          logs: ['[10:00:00] Concluído'],
        },
      ],
    });
  });

  afterEach(() => {
    cleanup();
    delete window.pywebview;
    useWorkspaceStore.setState({ jobQueue: [] });
    vi.clearAllTimers();
  });

  it('provides partitioned running and completed jobs', async () => {
    useWorkspaceStore.setState({
      jobQueue: [
        { id: 'job-1', page: '001.png', status: 'running' },
        { id: 'job-2', page: '002.png', status: 'pending' },
        { id: 'job-3', page: '003.png', status: 'completed' },
        { id: 'job-4', page: '004.png', status: 'failed' },
        { id: 'job-5', page: '005.png', status: 'cancelled' },
      ],
    });

    let result;
    await act(async () => {
      ({ result } = renderHook(() => useBatchQueue()));
      await Promise.resolve();
    });

    expect(result.current.runningJobs.map(j => j.id)).toEqual(['job-1', 'job-2']);
    expect(result.current.completedJobs.map(j => j.id)).toEqual(['job-3', 'job-4', 'job-5']);
  });

  it('opens and closes log drawer modal, updating logModalJob and stats', async () => {
    let result;
    await act(async () => {
      ({ result } = renderHook(() => useBatchQueue()));
      await Promise.resolve();
    });

    expect(result.current.logModalJobId).toBeNull();
    expect(result.current.logModalJob).toBeNull();

    await act(async () => {
      result.current.setLogModalJobId('job-1');
      await Promise.resolve();
    });

    expect(result.current.logModalJobId).toBe('job-1');
    expect(result.current.logModalJob.page).toBe('001.png');
    expect(result.current.stats.stagesSeen.has('layout')).toBe(true);
    expect(result.current.stats.stagesSeen.has('ocr')).toBe(true);

    await act(async () => {
      result.current.setLogModalJobId(null);
      await Promise.resolve();
    });

    expect(result.current.logModalJobId).toBeNull();
    expect(result.current.logModalJob).toBeNull();
  });

  it('cancels job by calling clientApi and updating workspace store status', async () => {
    let result;
    await act(async () => {
      ({ result } = renderHook(() => useBatchQueue()));
      await Promise.resolve();
    });

    await act(async () => {
      result.current.handleCancelJob('job-1', false);
      await Promise.resolve();
    });

    expect(window.pywebview.api.cancelJob).toHaveBeenCalledWith('job-1', false);

    const updatedJob = useWorkspaceStore.getState().jobQueue.find(j => j.id === 'job-1');
    expect(updatedJob.status).toBe('cancelled');
    expect(updatedJob.currentStepLabel).toBe('Cancelado');
  });

  it('closes log drawer on Escape keydown event', async () => {
    let result;
    await act(async () => {
      ({ result } = renderHook(() => useBatchQueue()));
      await Promise.resolve();
    });

    await act(async () => {
      result.current.setLogModalJobId('job-1');
      await Promise.resolve();
    });
    expect(result.current.logModalJobId).toBe('job-1');

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      await Promise.resolve();
    });

    expect(result.current.logModalJobId).toBeNull();
  });

  it('updates autoScroll based on scroll container position in handleLogScroll', async () => {
    let result;
    await act(async () => {
      ({ result } = renderHook(() => useBatchQueue()));
      await Promise.resolve();
    });

    // Scrolled to bottom: scrollHeight=1000, scrollTop=700, clientHeight=300 (diff = 0 < 40)
    await act(async () => {
      result.current.handleLogScroll({
        target: { scrollHeight: 1000, scrollTop: 700, clientHeight: 300 },
      });
    });
    expect(result.current.autoScroll).toBe(true);

    // Scrolled up: scrollHeight=1000, scrollTop=400, clientHeight=300 (diff = 300 >= 40)
    await act(async () => {
      result.current.handleLogScroll({
        target: { scrollHeight: 1000, scrollTop: 400, clientHeight: 300 },
      });
    });
    expect(result.current.autoScroll).toBe(false);
  });

  it('copies logs to clipboard and sets temporary feedback in handleCopyLogs', async () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: writeTextSpy },
      configurable: true,
      writable: true,
    });

    let result;
    await act(async () => {
      ({ result } = renderHook(() => useBatchQueue()));
      await Promise.resolve();
    });

    await act(async () => {
      result.current.setLogModalJobId('job-1');
      await Promise.resolve();
    });

    await act(async () => {
      result.current.handleCopyLogs({ stopPropagation: vi.fn() });
    });

    expect(writeTextSpy).toHaveBeenCalledWith('[10:00:00] [LAYOUT] Iniciado\n[10:00:15] [OCR] Extraindo texto');
    expect(result.current.copied).toBe(true);
  });

  it('clears logs using clearJobLogs on store in handleClearLogs', async () => {
    let result;
    await act(async () => {
      ({ result } = renderHook(() => useBatchQueue()));
      await Promise.resolve();
    });

    await act(async () => {
      result.current.setLogModalJobId('job-1');
      await Promise.resolve();
    });

    await act(async () => {
      result.current.handleClearLogs({ stopPropagation: vi.fn() });
      await Promise.resolve();
    });

    const job = useWorkspaceStore.getState().jobQueue.find(j => j.id === 'job-1');
    expect(job.logs).toEqual([]);
  });

  it('clears completed jobs via clearCompletedJobs', async () => {
    let result;
    await act(async () => {
      ({ result } = renderHook(() => useBatchQueue()));
      await Promise.resolve();
    });

    expect(result.current.completedJobs.length).toBe(1);

    await act(async () => {
      result.current.clearCompletedJobs();
      await Promise.resolve();
    });

    expect(useWorkspaceStore.getState().jobQueue.map(j => j.id)).toEqual(['job-1']);
  });

  it('syncs pipeline status from backend periodically when jobs are running', async () => {
    useWorkspaceStore.setState({
      jobQueue: [
        {
          id: 'job-1',
          page: '001.png',
          status: 'running',
          progress: 45,
          currentStepLabel: 'Processando OCR...',
          logs: [
            '[10:00:00] [LAYOUT] Iniciado',
          ],
        },
      ],
    });

    window.pywebview.api.getPipelineStatus.mockResolvedValueOnce({
      success: true,
      jobs: {
        'job-1': {
          progress: 80,
          step_label: 'Traduzindo...',
          status: 'running',
          logs: [
            '[10:00:00] [LAYOUT] Iniciado',
            '[10:00:15] [OCR] Extraindo texto',
            '[10:00:30] [TRADUÇÃO] Em andamento',
          ],
        },
      },
    });

    await act(async () => {
      renderHook(() => useBatchQueue());
      await Promise.resolve();
    });

    await waitFor(() => {
      const updatedJob = useWorkspaceStore.getState().jobQueue.find(j => j.id === 'job-1');
      expect(updatedJob?.progress).toBe(80);
      expect(updatedJob?.currentStepLabel).toBe('Traduzindo...');
      expect(updatedJob?.logs?.length).toBe(3);
    });
  });

  it('reconciles orphaned running jobs as failed when backend restarts and returns empty jobs map', async () => {
    useWorkspaceStore.setState({
      jobQueue: [
        {
          id: 'job-orphan-1',
          page: '005.png',
          status: 'running',
          progress: 60,
          startedAt: Date.now() - 10000, // Criado há 10s (> 4s de graça)
          currentStepLabel: 'Traduzindo...',
          logs: ['[10:00:00] Em execução'],
        },
      ],
    });

    window.pywebview.api.getPipelineStatus.mockResolvedValueOnce({
      success: true,
      jobs: {},
    });

    await act(async () => {
      renderHook(() => useBatchQueue());
      await Promise.resolve();
    });

    await waitFor(() => {
      const reconciled = useWorkspaceStore.getState().jobQueue.find(j => j.id === 'job-orphan-1');
      expect(reconciled?.status).toBe('failed');
      expect(reconciled?.currentStepLabel).toContain('Motor reiniciado');
    });
  });
});
