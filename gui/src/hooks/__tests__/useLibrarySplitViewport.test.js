import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLibrarySplitViewport } from '../useLibrarySplitViewport';

describe('useLibrarySplitViewport Hook', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it('keeps isReady and allowTransition false until valid dimensions exist, avoiding zoom-out flicker', () => {
    const { result, rerender } = renderHook(
      ({ imageSize, activePageName }) =>
        useLibrarySplitViewport({
          activePageName,
          imageSize,
          zoomScale: 1,
          setZoomScale: vi.fn(),
          panPos: { x: 0, y: 0 },
          setPanPos: vi.fn(),
          setIsPanning: vi.fn(),
          isPanning: false,
          autoZoomEnabled: false,
          zoomTargetRect: null,
          setZoomTargetRect: vi.fn(),
        }),
      {
        initialProps: {
          imageSize: { width: 0, height: 0 },
          activePageName: '001.JPG',
        },
      }
    );

    // Initial state before dimensions: not ready, no transition allowed
    expect(result.current.hasValidDimensions).toBe(false);
    expect(result.current.isReady).toBe(false);
    expect(result.current.allowTransition).toBe(false);

    // Mock container node with real dimensions
    const fakeNode = {
      clientWidth: 600,
      clientHeight: 800,
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 600, height: 800 }),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };

    act(() => {
      result.current.setContainerRef(fakeNode);
    });

    // Provide valid image dimensions
    rerender({
      imageSize: { width: 1000, height: 1400 },
      activePageName: '001.JPG',
    });

    expect(result.current.hasValidDimensions).toBe(true);
    expect(result.current.isReady).toBe(true);
    // allowTransition must stay false during initial render to prevent zoom-out animation
    expect(result.current.allowTransition).toBe(false);

    // After settle timeout, transition is allowed for user interactions
    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(result.current.allowTransition).toBe(true);

    // Switching page immediately resets allowTransition and isReady
    rerender({
      imageSize: { width: 0, height: 0 },
      activePageName: '002.JPG',
    });

    expect(result.current.isReady).toBe(false);
    expect(result.current.allowTransition).toBe(false);
  });
});
