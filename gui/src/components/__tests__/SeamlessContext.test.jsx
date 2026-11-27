import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, renderHook, act } from '@testing-library/react';
import {
  SeamlessProvider,
  useSeamlessContext,
  useSeamlessDoc,
  useSeamlessViewport,
  useSeamlessToolsState,
  useSeamlessUi
} from '../../contexts/SeamlessContext';
import { ToastProvider } from '../../contexts/ToastContext';

describe('SeamlessContext and Provider', () => {
  beforeEach(() => {
    window.pywebview = {
      api: {
        get_page_data: vi.fn().mockResolvedValue({
          success: true,
          has_data: true,
          cards: [],
          panels: []
        }),
        save_page_layout: vi.fn().mockResolvedValue({ success: true }),
      }
    };
  });

  it('throws an error if useSeamlessContext is used outside SeamlessProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => {
      renderHook(() => useSeamlessContext());
    }).toThrow('useSeamlessContext must be used within a SeamlessProvider');
    spy.mockRestore();
  });

  it('renders children and provides context values without crashing', async () => {
    const dummyPage = {
      path: 'C:/test/chapter/001.png',
      pageData: { layout: true, ocr: true, translation: false },
    };

    function Consumer() {
      const ctx = useSeamlessContext();
      return (
        <div>
          <span data-testid="viewMode">{ctx.viewMode}</span>
          <span data-testid="saveStatus">{ctx.saveStatus}</span>
          <span data-testid="hasTools">{ctx.tools ? 'tools_ready' : 'no'}</span>
          <span data-testid="hasHistory">{ctx.history ? 'history_ready' : 'no'}</span>
          <span data-testid="hasBackend">{ctx.backend ? 'backend_ready' : 'no'}</span>
          <span data-testid="hasZoom">{ctx.zoom ? 'zoom_ready' : 'no'}</span>
        </div>
      );
    }

    await act(async () => {
      render(
        <ToastProvider>
          <SeamlessProvider page={dummyPage} initialMode="layout">
            <Consumer />
          </SeamlessProvider>
        </ToastProvider>
      );
    });

    expect(screen.getByTestId('viewMode').textContent).toBe('layout');
    expect(screen.getByTestId('saveStatus').textContent).toBe('saved');
    expect(screen.getByTestId('hasTools').textContent).toBe('tools_ready');
    expect(screen.getByTestId('hasHistory').textContent).toBe('history_ready');
    expect(screen.getByTestId('hasBackend').textContent).toBe('backend_ready');
    expect(screen.getByTestId('hasZoom').textContent).toBe('zoom_ready');
  });

  it('provides memoized stable object references across parent re-renders', async () => {
    const dummyPage = {
      path: 'C:/test/chapter/001.png',
      pageData: { layout: true, ocr: true, translation: false },
    };

    let capturedContexts = [];
    function ContextWatcher() {
      const ctx = useSeamlessContext();
      capturedContexts.push(ctx);
      return <div data-testid="watcher">count: {capturedContexts.length}</div>;
    }

    function TestHost({ tick }) {
      return (
        <ToastProvider>
          <SeamlessProvider page={dummyPage} initialMode="layout">
            <ContextWatcher />
            <div data-testid="tick">{tick}</div>
          </SeamlessProvider>
        </ToastProvider>
      );
    }

    let rerenderFn;
    await act(async () => {
      const { rerender } = render(<TestHost tick={1} />);
      rerenderFn = rerender;
    });

    await act(async () => {
      rerenderFn(<TestHost tick={2} />);
    });

    expect(capturedContexts.length).toBeGreaterThanOrEqual(2);
    const first = capturedContexts[0];
    const second = capturedContexts[capturedContexts.length - 1];

    // Sub-objects (backend, history, tools, zoom) should retain reference stability
    expect(first.backend.savePageLayout).toBe(second.backend.savePageLayout);
    expect(first.history.clearHistory).toBe(second.history.clearHistory);
    expect(first.tools.resetTools).toBe(second.tools.resetTools);
    expect(first.zoom.toggleAutoZoom).toBe(second.zoom.toggleAutoZoom);
  });

  it('provides isolated sliced hooks (doc, viewport, tools, ui)', async () => {
    const dummyPage = {
      path: 'C:/test/chapter/001.png',
      pageData: { layout: true, ocr: true, translation: false },
    };

    let docResult = null;
    let viewportResult = null;
    let toolsResult = null;
    let uiResult = null;

    function SlicedConsumer() {
      docResult = useSeamlessDoc();
      viewportResult = useSeamlessViewport();
      toolsResult = useSeamlessToolsState();
      uiResult = useSeamlessUi();
      return <div data-testid="sliced-done">Ready</div>;
    }

    await act(async () => {
      render(
        <ToastProvider>
          <SeamlessProvider page={dummyPage} initialMode="layout">
            <SlicedConsumer />
          </SeamlessProvider>
        </ToastProvider>
      );
    });

    expect(docResult).not.toBeNull();
    expect(docResult.viewMode).toBe('layout');
    expect(docResult.backend).toBeDefined();

    expect(viewportResult).not.toBeNull();
    expect(viewportResult.zoom).toBeDefined();
    expect(viewportResult.bgSize).toBeDefined();

    expect(toolsResult).not.toBeNull();
    expect(toolsResult.tools).toBeDefined();

    expect(uiResult).not.toBeNull();
    expect(uiResult.isRestartModalOpen).toBeDefined();
    expect(uiResult.addToast).toBeDefined();
  });
});
