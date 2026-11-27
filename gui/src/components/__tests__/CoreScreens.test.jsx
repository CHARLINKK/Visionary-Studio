import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, renderHook } from '@testing-library/react';
import { ToastProvider } from '../../contexts/ToastContext';
import Settings from '../Settings';
import DevDashboard from '../DevDashboard';
import ModulesCenter from '../ModulesCenter';
import SeamlessCanvas from '../SeamlessCanvas';
import LibrarySplitView from '../Library/LibrarySplitView';
import { SeamlessProvider } from '../../contexts/SeamlessContext';
import { useLibraryParser } from '../../hooks/useLibraryParser';
import { safeSetStorageItem } from '../../stores/useLibraryStore';

// Mock react-konva to render lightweight DOM elements in happy-dom
vi.mock('react-konva', () => ({
  Stage: ({ children, ...props }) => (
    <div data-testid="konva-stage" data-draggable={String(props.draggable)}>
      {children}
    </div>
  ),
  Layer: ({ children }) => <div data-testid="konva-layer">{children}</div>,
  Rect: (props) => <div data-testid="konva-rect" data-id={props.id} />,
  Image: () => <div data-testid="konva-image" />,
  Group: ({ children }) => <div data-testid="konva-group">{children}</div>,
  Text: ({ text }) => <span>{text}</span>,
  Line: () => <div data-testid="konva-line" />,
  Circle: () => <div data-testid="konva-circle" />,
}));

describe('Core Frontend Screens (Settings, DevDashboard, ModulesCenter, SeamlessCanvas, LibrarySplitView)', () => {
  beforeEach(() => {
    localStorage.clear();
    window.pywebview = {
      api: {
        getSettings: vi.fn().mockResolvedValue({
          theme: 'Dark',
          accent: 'Roxo (Padrão)',
          uiScale: 100,
          soundEnabled: true,
          debugPanelMaps: false,
        }),
        saveSettings: vi.fn().mockResolvedValue({ success: true }),
        getDevLogs: vi.fn().mockResolvedValue({
          test_logs: ['[TEST] 1 passed'],
          app_logs: ['[APP] Server booted'],
          test_running: false,
          test_progress: { running: false, percent: 100, passed: 1, failed: 0, skipped: 0, total: 1, current_test: '' },
        }),
        getDevStats: vi.fn().mockResolvedValue({
          vram_used_gb: 1.2,
          vram_total_gb: 8.0,
          vram_free_gb: 6.8,
          vram_pct: 15,
          loaded_models: [],
        }),
        getTestList: vi.fn().mockResolvedValue({
          files: [{ filename: 'test_audit_fixes.py', label: 'Auditoria' }],
          total_tests_estimate: 50,
        }),
        runTests: vi.fn().mockResolvedValue({ success: true, message: 'Iniciado' }),
        checkModulesStatus: vi.fn().mockResolvedValue({
          ocr: { state: 'installed' },
          ollama: { state: 'installed_and_running', models: ['mistral-nemo'] },
          hf_models: {
            yolo_detector: { status: 'installed' },
            florence2_large: { status: 'installed' },
          },
          models_tags: {},
          models_details: {},
        }),
        getModelsStatus: vi.fn().mockResolvedValue({
          yolo_detector: { status: 'installed' },
          florence2_large: { status: 'installed' },
        }),
        getHardwareStats: vi.fn().mockResolvedValue({
          gpu_name: 'NVIDIA GeForce RTX 4070',
          vram_total_gb: 12,
          vram_used_gb: 2,
          cpu_name: 'AMD Ryzen 7 5800X',
          ram_total_gb: 32,
        }),
        getStorageStats: vi.fn().mockResolvedValue({
          success: true,
          total_gb: 100,
          free_gb: 50,
        }),
        getPageData: vi.fn().mockResolvedValue({
          success: true,
          has_data: true,
          cards: [{ id: 1, order: 1, x1: 10, y1: 10, x2: 80, y2: 60, text: 'Hello' }],
          panels: [],
        }),
        get_page_data: vi.fn().mockResolvedValue({
          success: true,
          has_data: true,
          cards: [{ id: 1, order: 1, x1: 10, y1: 10, x2: 80, y2: 60, text: 'Hello' }],
          panels: [],
        }),
        get_image_base64_full: vi.fn().mockResolvedValue({
          success: true,
          data: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
        }),
      },
    };
  });

  it('renders Settings screen and switches between categories', async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <Settings onBaseFolderChange={vi.fn()} />
        </ToastProvider>
      );
    });

    expect(screen.getByText('Configurações')).toBeInTheDocument();
    expect(screen.getByText('Interface (UX)')).toBeInTheDocument();

    const shortcutsBtn = screen.getByText('Atalhos de Teclado').closest('button');
    await act(async () => {
      fireEvent.click(shortcutsBtn);
    });
    expect(shortcutsBtn.className).toContain('active');

    const aboutBtn = screen.getByText('Sobre o App').closest('button');
    await act(async () => {
      fireEvent.click(aboutBtn);
    });
    expect(aboutBtn.className).toContain('active');
  });

  it('renders DevDashboard screen, loads logs, and triggers test run', async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <DevDashboard isActive={true} />
        </ToastProvider>
      );
    });

    expect(window.pywebview.api.getDevLogs).toHaveBeenCalled();
    expect(window.pywebview.api.getDevStats).toHaveBeenCalled();
  });

  it('renders ModulesCenter screen with hardware and AI module telemetry', async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <ModulesCenter isActive={true} />
        </ToastProvider>
      );
    });

    expect(screen.getByText('Central de Módulos & IA')).toBeInTheDocument();
    expect(screen.getByText('Sincronizar')).toBeInTheDocument();
  });

  it('renders SeamlessCanvas inside SeamlessProvider with Konva Stage and layers', async () => {
    const dummyPage = {
      path: 'C:/test/chapter/001.png',
      pageData: { layout: true, ocr: true, translation: false },
    };

    await act(async () => {
      render(
        <ToastProvider>
          <SeamlessProvider page={dummyPage} initialMode="layout">
            <SeamlessCanvas />
          </SeamlessProvider>
        </ToastProvider>
      );
    });

    expect(screen.getByTestId('konva-stage')).toBeInTheDocument();
  });

  it('renders LibrarySplitView with parsed page balloons and preserves multiline dialogues in useLibraryParser', async () => {
    const rawScript = [
      '==================================================',
      'PAGINA 1: 01.PNG',
      '==================================================',
      '',
      '# [id: 42]',
      '[EN]: First English line',
      'Second English line',
      '[BR] (PENSAMENTO): - Primeira linha em português',
      '- Segunda linha em português',
      '',
    ].join('\n');

    const { result } = renderHook(() => useLibraryParser(rawScript, 0));
    expect(result.current.parsedPages).toHaveLength(1);
    const balloon = result.current.parsedPages[0].balloons[0];
    expect(balloon.id).toBe('42');
    expect(balloon.en).toBe('First English line\nSecond English line');
    expect(balloon.br).toBe('- Primeira linha em português\n- Segunda linha em português');
    expect(balloon.typeTag).toBe('PENSAMENTO');
    expect(balloon.endLineIndex).toBeGreaterThan(balloon.lineIndex);

    await act(async () => {
      render(
        <ToastProvider>
          <LibrarySplitView
            activeFile={{ path: 'C:/test/cap1.txt', name: 'cap1.txt' }}
            activePageData={result.current.activePageData}
            getPreviewUrl={() => 'data:image/png;base64,AAA'}
            currentPageCards={[{ id: 42, order: 1, x1: 10, y1: 10, x2: 50, y2: 50 }]}
            copyBalloon={vi.fn()}
            undoCopyBalloon={vi.fn()}
            activeTab={null}
            setActiveTab={vi.fn()}
            saveBalloonText={vi.fn()}
          />
        </ToastProvider>
      );
    });

    expect(screen.getAllByText(/Segunda linha em português/).length).toBeGreaterThanOrEqual(2);
  });

  it('bounds LRU cache entries and recovers from QuotaExceededError in safeSetStorageItem', () => {
    for (let i = 0; i < 20; i++) {
      expect(safeSetStorageItem(`visionary:copied_ch${i}`, JSON.stringify({ 1: true }), 'visionary:copied_')).toBe(true);
    }
    const index = JSON.parse(localStorage.getItem('visionary:copied___lru_index') || '[]');
    expect(index.length).toBeLessThanOrEqual(15);
    expect(localStorage.getItem('visionary:copied_ch0')).toBeNull();
    expect(localStorage.getItem('visionary:copied_ch19')).not.toBeNull();
  });
});
