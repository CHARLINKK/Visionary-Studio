import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCanvasLayers } from '../useCanvasLayers';
import { SeamlessProvider } from '../../contexts/SeamlessContext';
import { ToastProvider } from '../../contexts/ToastContext';

describe('useCanvasLayers Hook', () => {
  beforeEach(() => {
    window.pywebview = {
      api: {
        get_page_data: vi.fn().mockResolvedValue({
          success: true,
          has_data: true,
          cards: [],
          panels: [],
        }),
      },
    };
  });

  const dummyPage = {
    path: 'C:/test/chapter/001.png',
    pageData: { layout: true, ocr: true, translation: false },
  };

  const wrapper = ({ children }) => (
    <ToastProvider>
      <SeamlessProvider page={dummyPage}>
        {children}
      </SeamlessProvider>
    </ToastProvider>
  );

  it('provides structured prop bundles for all canvas layers', async () => {
    let hookResult;
    await act(async () => {
      hookResult = renderHook(() => useCanvasLayers(), { wrapper });
    });
    const { result } = hookResult;

    expect(result.current.containerRef).toBeDefined();
    expect(result.current.stageWrapperStyle).toBeDefined();

    // Stage props bundle
    expect(result.current.stageProps).toBeDefined();
    expect(result.current.stageProps.width).toBeGreaterThan(0);
    expect(result.current.stageProps.height).toBeGreaterThan(0);
    expect(typeof result.current.stageProps.onWheel).toBe('function');
    expect(typeof result.current.stageProps.onMouseDown).toBe('function');
    expect(typeof result.current.stageProps.onClick).toBe('function');

    // Layer bundles
    expect(result.current.backgroundProps).toBeDefined();
    expect(result.current.guidesProps).toBeDefined();
    expect(result.current.bubblesProps).toBeDefined();
    expect(result.current.bubblesProps.actions).toBeDefined();
    expect(typeof result.current.bubblesProps.actions.select).toBe('function');
    expect(result.current.drawingProps).toBeDefined();
  });
});
