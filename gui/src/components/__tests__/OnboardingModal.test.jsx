import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act, screen, fireEvent } from '@testing-library/react';
import OnboardingModal from '../OnboardingModal';
import { clientApi, eventBus } from '../../api/bridge';

vi.mock('../../api/bridge', () => {
  const subscribers = new Set();
  let connected = false;
  return {
    clientApi: {
      getHardwareStats: vi.fn().mockResolvedValue({
        gpu_name: 'RTX 4090',
        vram_reserved_gb: 24.0,
        ram_total_gb: 64.0,
      }),
      getDownloadsProgress: vi.fn().mockResolvedValue({
        success: true,
        ollama: { 'amadeus:32b': { progress: 50, status: 'downloading' } },
        hf: { florence2_large: { progress: 80, status: 'downloading' } },
      }),
      ensureOllamaRunning: vi.fn().mockResolvedValue({ success: true }),
      pullOllamaModel: vi.fn().mockResolvedValue({ success: true }),
      downloadHuggingFaceModel: vi.fn().mockResolvedValue({ success: true }),
      getSettings: vi.fn().mockResolvedValue({}),
      saveSettings: vi.fn().mockResolvedValue({ success: true }),
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

describe('OnboardingModal — EventBus Integration & Polling Suppression', () => {
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

    const { unmount } = render(
      <OnboardingModal
        isOpen={true}
        initialView="downloading"
        onClose={vi.fn()}
      />
    );

    // Initial hardware fetch
    await act(async () => {
      await Promise.resolve();
    });

    expect(clientApi.getDownloadsProgress).not.toHaveBeenCalled();

    // Advance timers through multiple 800ms intervals
    await act(async () => {
      vi.advanceTimersByTime(2500);
      await Promise.resolve();
    });

    // When connected to WebSocket, HTTP polling must be suppressed
    expect(clientApi.getDownloadsProgress).toHaveBeenCalledTimes(0);

    unmount();
  });

  it('falls back to HTTP getDownloadsProgress when eventBus is not connected', async () => {
    eventBus.setConnected(false);

    const { unmount } = render(
      <OnboardingModal
        isOpen={true}
        initialView="downloading"
        onClose={vi.fn()}
      />
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(clientApi.getDownloadsProgress).not.toHaveBeenCalled();

    // Advance past one 800ms interval
    await act(async () => {
      vi.advanceTimersByTime(850);
      await Promise.resolve();
    });

    // Offline fallback calls getDownloadsProgress
    expect(clientApi.getDownloadsProgress).toHaveBeenCalled();

    unmount();
  });

  it('subscribes to EventBus while downloading and processes download events in real time', async () => {
    eventBus.setConnected(true);

    const onStartBackground = vi.fn();
    const { unmount } = render(
      <OnboardingModal
        isOpen={true}
        initialView="downloading"
        onClose={vi.fn()}
        onStartBackground={onStartBackground}
      />
    );

    expect(eventBus.subscribersCount()).toBe(1);

    // Simulate backend EventBus push
    act(() => {
      eventBus.emit({
        type: 'custom_event',
        event_name: 'downloads_progress',
        payload: {
          success: true,
          ollama: {
            'amadeus:32b': { progress: 90, status: 'downloading', speed_mbps: 45.0 },
          },
          hf: {
            florence2_large: { progress: 100, status: 'installed' },
            yolo_detector: { progress: 100, status: 'installed' },
          },
        },
      });
    });

    // Should notify background handler without HTTP polling
    expect(onStartBackground).toHaveBeenCalledWith(
      expect.objectContaining({
        model: 'amadeus:32b',
        speedMb: 45.0,
      })
    );
    expect(clientApi.getDownloadsProgress).toHaveBeenCalledTimes(0);

    unmount();
    expect(eventBus.subscribersCount()).toBe(0);
  });

  it('displays Amadeus Verbo label and exposes retry banner when ensureOllamaRunning fails', async () => {
    clientApi.ensureOllamaRunning.mockResolvedValueOnce({
      success: false,
      error: 'Falha ao iniciar o daemon Ollama local.',
    });

    const { unmount } = render(
      <OnboardingModal
        isOpen={true}
        initialView="selection"
        onClose={vi.fn()}
      />
    );

    const startBtn = screen.getByRole('button', { name: /Instalar Perfil Studio/i });
    await act(async () => {
      fireEvent.click(startBtn);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText(/Amadeus Verbo 32B/i)).toBeInTheDocument();
    expect(screen.queryByText(/Qwen 2\.5/i)).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Falha ao iniciar o daemon Ollama local.');

    const retryBtn = screen.getByRole('button', { name: /Tentar Novamente/i });
    await act(async () => {
      fireEvent.click(retryBtn);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(clientApi.ensureOllamaRunning).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    unmount();
  });
});
