import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLibraryPagination } from '../useLibraryPagination';
import { useLibraryStore } from '../../stores/useLibraryStore';

describe('useLibraryPagination', () => {
  beforeEach(() => {
    useLibraryStore.setState({
      autoResumePending: false,
      autoTurnPage: false,
    });
    vi.restoreAllMocks();
  });

  const parsedPages = [
    { pageNumber: 1, balloons: [{ br: 'F1' }, { br: 'F2' }] },
    { pageNumber: 2, balloons: [{ br: 'F3' }, { br: 'F4' }] },
    { pageNumber: 3, balloons: [{ br: 'F5' }] },
  ];

  it('clamps page index within boundary limits in goToPage', () => {
    const setActivePageIndex = vi.fn();
    const resetZoom = vi.fn();

    const { result } = renderHook(() =>
      useLibraryPagination({
        parsedPages,
        activePageIndex: 0,
        setActivePageIndex,
        resetZoom,
      })
    );

    // Negative index clamped to 0
    act(() => {
      result.current.goToPage(-5);
    });
    expect(setActivePageIndex).toHaveBeenCalledWith(0);
    expect(resetZoom).toHaveBeenCalled();

    // Out of bounds clamped to max index (2)
    act(() => {
      result.current.goToPage(10);
    });
    expect(setActivePageIndex).toHaveBeenCalledWith(2);
  });

  it('toggles autoResumePending and notifies via toast', () => {
    const addToast = vi.fn();
    const { result } = renderHook(() =>
      useLibraryPagination({
        parsedPages,
        addToast,
      })
    );

    expect(useLibraryStore.getState().autoResumePending).toBe(false);

    act(() => {
      result.current.toggleAutoResume();
    });

    expect(useLibraryStore.getState().autoResumePending).toBe(true);
    expect(addToast).toHaveBeenCalledWith(
      expect.stringContaining('Auto-Retomar ativado'),
      'info'
    );
  });

  it('navigates to the first page and balloon with pending status in jumpToNextPending', () => {
    const setActivePageIndex = vi.fn();
    const setActiveCopiedId = vi.fn();
    const addToast = vi.fn();

    // Page 1 is fully copied (1-0 and 1-1)
    const copiedBlocks = {
      '1-0': true,
      '1-1': true,
      // Page 2 has 2-0 copied, but 2-1 is pending
      '2-0': true,
    };

    const { result } = renderHook(() =>
      useLibraryPagination({
        parsedPages,
        activePageIndex: 0,
        setActivePageIndex,
        setActiveCopiedId,
        copiedBlocks,
        addToast,
      })
    );

    act(() => {
      result.current.jumpToNextPending();
    });

    // Should navigate to page index 1 (pageNumber 2)
    expect(setActivePageIndex).toHaveBeenCalledWith(1);
    expect(setActiveCopiedId).toHaveBeenCalledWith('2-1');
    expect(addToast).toHaveBeenCalledWith(
      expect.stringContaining('Saltou para a Pág. 02'),
      'info'
    );
  });

  it('informs user when all balloons in chapter are already copied', () => {
    const setActivePageIndex = vi.fn();
    const addToast = vi.fn();

    const fullyCopied = {
      '1-0': true,
      '1-1': true,
      '2-0': true,
      '2-1': true,
      '3-0': true,
    };

    const { result } = renderHook(() =>
      useLibraryPagination({
        parsedPages,
        activePageIndex: 0,
        setActivePageIndex,
        copiedBlocks: fullyCopied,
        addToast,
      })
    );

    act(() => {
      result.current.jumpToNextPending();
    });

    expect(setActivePageIndex).not.toHaveBeenCalled();
    expect(addToast).toHaveBeenCalledWith(
      'Todas as falas deste capítulo já foram copiadas!',
      'info'
    );
  });
});
