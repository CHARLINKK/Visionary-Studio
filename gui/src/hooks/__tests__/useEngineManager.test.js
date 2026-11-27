import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useEngineManager } from '../useEngineManager';
import { clientApi, eventBus } from '../../api/bridge';

vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

vi.mock('../../api/bridge', () => {
  const subscribers = new Set();
  let connected = false;
  return {
    clientApi: {
      getSettings: vi.fn().mockResolvedValue({ selected_models: { transPol: 'qwen2.5:7b' } }),
      getHardwareStats: vi.fn().mockResolvedValue({ gpu_name: 'RTX 4090', vram_reserved_gb: 24 }),
      getStorageStats: vi.fn().mockResolvedValue({ success: true, models_gb: 12 }),
      checkModulesStatus: vi.fn().mockResolvedValue({
        ocr: { state: 'installed' },
        cuda: { state: 'installed' },
        ollama: { state: 'installed_and_running' },
        ollamaModels: ['qwen2.5:7b'],
        ollamaDownloads: {},
      }),
      getModelsStatus: vi.fn().mockResolvedValue({}),
      getDownloadsProgress: vi.fn().mockResolvedValue({ success: true, ollama: {}, hf: {} }),
      saveSettings: vi.fn().mockResolvedValue({ success: true }),
      installCoreEngine: vi.fn().mockResolvedValue({ success: true }),
      getInstallProgress: vi.fn().mockResolvedValue({ status: 'installing', percent: 25, message: 'Baixando...' }),
      downloadHuggingFaceModel: vi.fn().mockResolvedValue({ success: true }),
      deleteHuggingFaceModel: vi.fn().mockResolvedValue({ success: true }),
      cancelHuggingFaceModel: vi.fn().mockResolvedValue({ success: true }),
    },
    eventBus: {
      isConnected: vi.fn(() => connected),
      setConnected: (val) => { connected = val; },
      subscribe: vi.fn((cb) => {
        subscribers.add(cb);
        return () => subscribers.delete(cb);
      }),
      emit: (payload) => {
        subscribers.forEach((cb) => cb(payload));
      },
      clearSubscribers: () => subscribers.clear(),
      subscribersCount: () => subscribers.size,
    },
  };
});

describe('useEngineManager — EventBus Integration & Polling Suppression', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    eventBus.clearSubscribers();
    eventBus.setConnected(false);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('suppresses HTTP getDownloadsProgress polling when eventBus.isConnected() is true', async () => {
    eventBus.setConnected(true);

    const { unmount } = renderHook(() => useEngineManager(true));

    // Allow initial checkModules promises to resolve
    await act(async () => {
      await Promise.resolve();
    });

    expect(clientApi.getDownloadsProgress).not.toHaveBeenCalled();

    // Advance timers across multiple polling cycles (800ms, 1600ms, 2400ms)
    await act(async () => {
      vi.advanceTimersByTime(2500);
      await Promise.resolve();
    });

    // When connected, HTTP getDownloadsProgress must be suppressed
    expect(clientApi.getDownloadsProgress).toHaveBeenCalledTimes(0);

    unmount();
  });

  it('falls back to HTTP getDownloadsProgress polling when eventBus.isConnected() is false', async () => {
    eventBus.setConnected(false);

    const { unmount } = renderHook(() => useEngineManager(true));

    await act(async () => {
      await Promise.resolve();
    });

    expect(clientApi.getDownloadsProgress).not.toHaveBeenCalled();

    // Advance past one 800ms progressInterval tick
    await act(async () => {
      vi.advanceTimersByTime(850);
      await Promise.resolve();
    });

    // Offline fallback should have fired getDownloadsProgress
    expect(clientApi.getDownloadsProgress).toHaveBeenCalled();

    unmount();
  });

  it('receives WebSocket downloads_progress event and updates model tags in real time', async () => {
    eventBus.setConnected(true);

    const { result, unmount } = renderHook(() => useEngineManager(true));

    await act(async () => {
      await Promise.resolve();
    });

    // Simulate incoming WebSocket push event from EventBus
    act(() => {
      eventBus.emit({
        type: 'custom_event',
        event_name: 'downloads_progress',
        payload: {
          success: true,
          ollama: {
            'qwen2.5:32b': { progress: 64, status: 'downloading', speed_mbps: 28.5 },
          },
          hf: {},
        },
      });
    });

    // Tag should reflect real-time WebSocket payload without any HTTP call
    expect(result.current.ollamaModelsTags['qwen2.5:32b']).toEqual(
      expect.objectContaining({
        progress: 64,
        status: 'downloading',
        speed_mbps: 28.5,
      })
    );
    expect(clientApi.getDownloadsProgress).toHaveBeenCalledTimes(0);

    unmount();
  });

  it('unsubscribes from eventBus when unmounted', async () => {
    eventBus.setConnected(true);

    const { unmount } = renderHook(() => useEngineManager(true));
    expect(eventBus.subscribersCount()).toBe(1);

    unmount();
    expect(eventBus.subscribersCount()).toBe(0);
  });

  it('prevents state oscillation when stale checkModulesStatus resolves right after installCoreEngine completes', async () => {
    eventBus.setConnected(true);
    clientApi.checkModulesStatus.mockResolvedValue({
      ocr: { state: 'not_installed' },
      cuda: { state: 'not_installed' },
      ollama: { state: 'installed_and_running' },
      ollamaModels: ['qwen2.5:7b'],
      ollamaDownloads: {},
    });

    const { result, unmount } = renderHook(() => useEngineManager(true));

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.moduleStatus.ocr.state).toBe('not_installed');

    await act(async () => {
      await result.current.installCoreEngine();
    });

    act(() => {
      eventBus.emit({
        type: 'custom_event',
        event_name: 'core_engine_progress',
        payload: { status: 'installing', percent: 60, message: 'Carregando do cache local...' },
      });
    });
    expect(result.current.ollamaModelsTags.ocr.progress).toBe(60);

    // Emit out-of-order lower progress (45%) and verify monotonic clamping preserves 60%
    act(() => {
      eventBus.emit({
        type: 'custom_event',
        event_name: 'core_engine_progress',
        payload: { status: 'installing', percent: 45, message: 'Carregando...' },
      });
    });
    expect(result.current.ollamaModelsTags.ocr.progress).toBe(60);

    // Complete installation while checkModulesStatus mock still returns stale 'not_installed'
    await act(async () => {
      eventBus.emit({
        type: 'custom_event',
        event_name: 'core_engine_progress',
        payload: { status: 'completed', percent: 100, message: 'Instalação concluída com sucesso!' },
      });
      await Promise.resolve();
    });

    // Must remain 'installed' and NOT oscillate back to 'not_installed'!
    expect(result.current.moduleStatus.ocr.state).toBe('installed');
    expect(result.current.ollamaModelsTags.ocr).toBeUndefined();

    clientApi.checkModulesStatus.mockResolvedValue({
      ocr: { state: 'installed' },
      cuda: { state: 'installed' },
      ollama: { state: 'installed_and_running' },
      ollamaModels: ['qwen2.5:7b'],
      ollamaDownloads: {},
    });
    unmount();
  });

  it('protects Comic-YOLO and Florence-2 against stale getModelsStatus polls and supports cancelHFModel', async () => {
    eventBus.setConnected(true);
    clientApi.getModelsStatus.mockResolvedValue({
      yolo_detector: { status: 'missing', progress: 0 },
      florence2_large: { status: 'missing', progress: 0 },
    });

    const { result, unmount } = renderHook(() => useEngineManager(true));

    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await result.current.downloadHFModel('florence2_large', 'Florence-2 Large');
    });
    expect(result.current.ollamaModelsInfo.florence2_large.status).toBe('downloading');

    act(() => {
      eventBus.emit({
        type: 'custom_event',
        event_name: 'model_download_progress',
        payload: {
          key: 'florence2_large',
          data: { status: 'downloading', progress: 62, speed_mbps: 45.2, eta_seconds: 12 },
        },
      });
    });
    expect(result.current.ollamaModelsInfo.florence2_large.progress).toBe(62);

    clientApi.getModelsStatus.mockResolvedValueOnce({
      yolo_detector: { status: 'missing', progress: 0 },
      florence2_large: { status: 'downloading', progress: 40 },
    });
    await act(async () => {
      await result.current.checkModules(true, true);
    });
    expect(result.current.ollamaModelsInfo.florence2_large.progress).toBe(62);

    clientApi.getModelsStatus.mockResolvedValueOnce({
      yolo_detector: { status: 'missing', progress: 0 },
      florence2_large: { status: 'downloading', progress: 98 },
    });
    await act(async () => {
      eventBus.emit({
        type: 'custom_event',
        event_name: 'model_download_progress',
        payload: {
          key: 'florence2_large',
          data: { status: 'installed', progress: 100, message: 'Instalado com sucesso!' },
        },
      });
      await Promise.resolve();
    });
    expect(result.current.ollamaModelsInfo.florence2_large.status).toBe('installed');

    await act(async () => {
      await result.current.downloadHFModel('yolo_detector', 'Comic-YOLO');
    });
    expect(result.current.ollamaModelsInfo.yolo_detector.status).toBe('downloading');

    await act(async () => {
      await result.current.cancelHFModel('yolo_detector', 'Comic-YOLO');
    });
    expect(clientApi.cancelHuggingFaceModel).toHaveBeenCalledWith('yolo_detector');
    expect(result.current.ollamaModelsInfo.yolo_detector.status).toBe('missing');

    unmount();
  });

  it('polls getHardwareStats at 1000ms intervals when isActive is true', async () => {
    const { unmount } = renderHook(() => useEngineManager(true));

    await act(async () => {
      await Promise.resolve();
    });

    const initialCalls = clientApi.getHardwareStats.mock.calls.length;
    expect(initialCalls).toBeGreaterThanOrEqual(1);

    // Advance 1050ms
    await act(async () => {
      vi.advanceTimersByTime(1050);
      await Promise.resolve();
    });

    expect(clientApi.getHardwareStats.mock.calls.length).toBe(initialCalls + 1);

    // Advance another 1000ms
    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });

    expect(clientApi.getHardwareStats.mock.calls.length).toBe(initialCalls + 2);

    unmount();

    // Advance after unmount should NOT trigger further calls
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(clientApi.getHardwareStats.mock.calls.length).toBe(initialCalls + 2);
  });
});
