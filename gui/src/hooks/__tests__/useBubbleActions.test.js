import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useBubbleActions } from '../useBubbleActions';

describe('useBubbleActions Hook', () => {
  it('selects and deselects a bubble', () => {
    let activeId = null;
    const setActiveBubbleId = vi.fn((updater) => {
      activeId = typeof updater === 'function' ? updater(activeId) : updater;
    });

    const { result } = renderHook(() =>
      useBubbleActions({ setActiveBubbleId })
    );

    act(() => {
      result.current.select('box_1');
    });
    expect(activeId).toBe('box_1');

    act(() => {
      result.current.select('box_1');
    });
    expect(activeId).toBeNull();
  });

  it('updates bubble properties', () => {
    let ocrData = {
      boxes: [
        { id: 'b1', text: 'Old', x1: 10, y1: 10 },
        { id: 'b2', text: 'Untouched', x1: 50, y1: 50 },
      ],
    };
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });

    const { result } = renderHook(() =>
      useBubbleActions({ setOcrData })
    );

    act(() => {
      result.current.update('b1', { text: 'New Text', x1: 20 });
    });

    expect(ocrData.boxes[0].text).toBe('New Text');
    expect(ocrData.boxes[0].x1).toBe(20);
    expect(ocrData.boxes[1].text).toBe('Untouched');
  });

  it('deletes bubble, cleans up orphan groups, and re-indexes orders', () => {
    let ocrData = {
      boxes: [
        { id: 'b1', group_id: 'g1', order: 1 },
        { id: 'b2', group_id: 'g1', order: 2 },
        { id: 'b3', group_id: null, order: 3 },
      ],
    };
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });
    const pushHistory = vi.fn();
    const setActiveBubbleId = vi.fn();

    const { result } = renderHook(() =>
      useBubbleActions({ setOcrData, pushHistory, setActiveBubbleId })
    );

    act(() => {
      result.current.delete('b1');
    });

    expect(pushHistory).toHaveBeenCalled();
    expect(ocrData.boxes).toHaveLength(2);
    // b2 was the only remaining bubble in g1, so its group_id should be removed
    expect(ocrData.boxes[0].id).toBe('b2');
    expect(ocrData.boxes[0].group_id).toBeUndefined();
    expect(ocrData.boxes[0].order).toBe(1);
    expect(ocrData.boxes[1].id).toBe('b3');
    expect(ocrData.boxes[1].order).toBe(2);
  });

  it('reorders bubbles in two-step selection', () => {
    let ocrData = {
      boxes: [
        { id: 'b1', order: 1 },
        { id: 'b2', order: 2 },
        { id: 'b3', order: 3 },
      ],
    };
    const setDragStartPos = vi.fn();
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });
    const pushHistory = vi.fn();

    const { result, rerender } = renderHook(
      ({ currentDragPos }) =>
        useBubbleActions({
          setOcrData,
          pushHistory,
          tools: { dragStartPos: currentDragPos, setDragStartPos },
        }),
      { initialProps: { currentDragPos: null } }
    );

    // Step 1: select source bubble
    act(() => {
      result.current.reorder('b1');
    });
    expect(setDragStartPos).toHaveBeenCalledWith('b1');

    // Step 2: click target bubble with dragStartPos active
    rerender({ currentDragPos: 'b1' });
    act(() => {
      result.current.reorder('b3');
    });

    expect(pushHistory).toHaveBeenCalled();
    // b1 was moved to index of b3
    expect(ocrData.boxes.map((x) => x.id)).toEqual(['b2', 'b3', 'b1']);
    expect(ocrData.boxes.map((x) => x.order)).toEqual([1, 2, 3]);
  });

  it('sequences bubbles when all are selected', () => {
    let ocrData = {
      boxes: [
        { id: 'b1', order: 1 },
        { id: 'b2', order: 2 },
      ],
    };
    const setBubbles = vi.fn();
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });
    const pushHistory = vi.fn();

    const { result, rerender } = renderHook(
      ({ currentQueue }) =>
        useBubbleActions({
          setOcrData,
          pushHistory,
          tools: { bubbles: currentQueue, setBubbles },
        }),
      { initialProps: { currentQueue: [] } }
    );

    // Click b2 first (out of 2 bubbles total)
    act(() => {
      result.current.sequence('b2', 2);
    });
    expect(setBubbles).toHaveBeenCalledWith(['b2']);

    // Now queue has ['b2']
    rerender({ currentQueue: ['b2'] });

    // Click b1 (completes sequence of 2)
    act(() => {
      result.current.sequence('b1', 2);
    });

    expect(pushHistory).toHaveBeenCalled();
    expect(ocrData.boxes.map((x) => x.id)).toEqual(['b2', 'b1']);
    expect(ocrData.boxes.map((x) => x.order)).toEqual([1, 2]);
  });

  it('links two bubbles with group_id', () => {
    let ocrData = {
      boxes: [
        { id: 'b1', order: 1 },
        { id: 'b2', order: 2 },
      ],
    };
    const setRectStartPos = vi.fn();
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });
    const pushHistory = vi.fn();

    const { result, rerender } = renderHook(
      ({ currentRectPos }) =>
        useBubbleActions({
          setOcrData,
          pushHistory,
          tools: { rectStartPos: currentRectPos, setRectStartPos },
        }),
      { initialProps: { currentRectPos: null } }
    );

    // Step 1: select link origin
    act(() => {
      result.current.link('b1');
    });
    expect(setRectStartPos).toHaveBeenCalledWith('b1');

    // Step 2: click target
    rerender({ currentRectPos: 'b1' });
    act(() => {
      result.current.link('b2');
    });

    expect(pushHistory).toHaveBeenCalled();
    expect(ocrData.boxes[0].group_id).toBe('b1');
    expect(ocrData.boxes[1].group_id).toBe('b1');
  });

  it('unlinks a bubble and cleans remaining group if only one left', () => {
    let ocrData = {
      boxes: [
        { id: 'b1', group_id: 'group_X' },
        { id: 'b2', group_id: 'group_X' },
      ],
    };
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });
    const pushHistory = vi.fn();
    const setRectStartPos = vi.fn();

    const { result } = renderHook(() =>
      useBubbleActions({
        setOcrData,
        pushHistory,
        tools: { setRectStartPos },
      })
    );

    act(() => {
      result.current.unlink('b1', 'group_X');
    });

    expect(pushHistory).toHaveBeenCalled();
    // b1 is unlinked, leaving only b2 in group_X -> b2 should also have group_id removed
    expect(ocrData.boxes[0].group_id).toBeUndefined();
    expect(ocrData.boxes[1].group_id).toBeUndefined();
  });

  it('unlinks without explicit groupId by inferring from target bubble', () => {
    let ocrData = {
      boxes: [
        { id: 'b1', group_id: 'group_Y' },
        { id: 'b2', group_id: 'group_Y' },
      ],
    };
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });
    const pushHistory = vi.fn();
    const setRectStartPos = vi.fn();

    const { result } = renderHook(() =>
      useBubbleActions({
        setOcrData,
        pushHistory,
        tools: { setRectStartPos },
      })
    );

    act(() => {
      result.current.unlink('b1');
    });

    expect(pushHistory).toHaveBeenCalled();
    expect(ocrData.boxes[0].group_id).toBeUndefined();
    expect(ocrData.boxes[1].group_id).toBeUndefined();
  });

  it('toggles link off when linking two bubbles already in the same group', () => {
    let ocrData = {
      boxes: [
        { id: 'b1', group_id: 'group_shared' },
        { id: 'b2', group_id: 'group_shared' },
      ],
    };
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });
    const pushHistory = vi.fn();
    let currentRectPos = null;
    const setRectStartPos = vi.fn((val) => {
      currentRectPos = val;
    });

    const { result } = renderHook(() =>
      useBubbleActions({
        setOcrData,
        pushHistory,
        tools: { rectStartPos: currentRectPos, setRectStartPos },
      })
    );

    act(() => {
      result.current.link('b1');
    });
    expect(setRectStartPos).toHaveBeenCalledWith('b1');

    const { result: rerenderedResult } = renderHook(() =>
      useBubbleActions({
        setOcrData,
        pushHistory,
        tools: { rectStartPos: 'b1', setRectStartPos },
      })
    );

    act(() => {
      rerenderedResult.current.link('b2');
    });

    expect(pushHistory).toHaveBeenCalled();
    expect(ocrData.boxes[0].group_id).toBeUndefined();
    expect(ocrData.boxes[1].group_id).toBeUndefined();
  });

  it('manages dragStart and dragEnd with bounding box constraints', () => {
    const startHistoryTransaction = vi.fn();
    const commitHistoryTransaction = vi.fn();
    let ocrData = {
      boxes: [
        { id: 'b1', x1: 100, y1: 100, x2: 200, y2: 200 },
      ],
    };
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });

    const { result } = renderHook(() =>
      useBubbleActions({
        setOcrData,
        startHistoryTransaction,
        commitHistoryTransaction,
        bgSize: { width: 500, height: 500 },
      })
    );

    act(() => {
      result.current.dragStart();
    });
    expect(startHistoryTransaction).toHaveBeenCalled();

    // Drag delta: dx = 50, dy = 50
    act(() => {
      result.current.dragEnd(ocrData.boxes[0], 50, 50);
    });

    expect(ocrData.boxes[0].x1).toBe(150);
    expect(ocrData.boxes[0].y1).toBe(150);
    expect(ocrData.boxes[0].x2).toBe(250);
    expect(ocrData.boxes[0].y2).toBe(250);
    expect(commitHistoryTransaction).toHaveBeenCalled();
  });

  it('ignores micro-jitter movements under 4px threshold in dragEnd', () => {
    const commitHistoryTransaction = vi.fn();
    let ocrData = {
      boxes: [
        { id: 'b1', x1: 100, y1: 100, x2: 200, y2: 200 },
      ],
    };
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });

    const { result } = renderHook(() =>
      useBubbleActions({
        setOcrData,
        commitHistoryTransaction,
        bgSize: { width: 500, height: 500 },
      })
    );

    // Jitter of dx = 2, dy = 1 (hypot is 2.23 < 4)
    act(() => {
      result.current.dragEnd(ocrData.boxes[0], 2, 1);
    });

    // Coordinates should remain untouched
    expect(ocrData.boxes[0].x1).toBe(100);
    expect(ocrData.boxes[0].y1).toBe(100);
    expect(commitHistoryTransaction).toHaveBeenCalled();
  });

  it('toggles bubble to SFX and back, adjusting flags and reindexing orders', () => {
    let ocrData = {
      boxes: [
        { id: 'b1', order: 1, is_bubble: true, is_sfx: false, label: 'text_bubble' },
        { id: 'b2', order: 2, is_bubble: true, is_sfx: false, label: 'text_bubble' },
        { id: 'b3', order: 3, is_bubble: true, is_sfx: false, label: 'text_bubble' },
      ],
    };
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });
    const pushHistory = vi.fn();

    const { result } = renderHook(() =>
      useBubbleActions({ setOcrData, pushHistory })
    );

    // Turn b2 into SFX
    act(() => {
      result.current.toggleSfx('b2');
    });

    expect(pushHistory).toHaveBeenCalled();
    expect(ocrData.boxes[1].is_sfx).toBe(true);
    expect(ocrData.boxes[1].isSfx).toBe(true);
    expect(ocrData.boxes[1].is_bubble).toBe(false);
    expect(ocrData.boxes[1].order).toBeNull();
    // b3 should now be reindexed to order 2
    expect(ocrData.boxes[0].order).toBe(1);
    expect(ocrData.boxes[2].order).toBe(2);

    // Toggle b2 back to speech bubble
    act(() => {
      result.current.toggleSfx('b2');
    });

    expect(ocrData.boxes[1].is_sfx).toBe(false);
    expect(ocrData.boxes[1].is_bubble).toBe(true);
    expect(ocrData.boxes[1].order).toBe(2);
    expect(ocrData.boxes[2].order).toBe(3);
  });

  it('resets moved bubble back to its initial_box and initial_polygon', () => {
    let ocrData = {
      boxes: [
        {
          id: 'b1',
          x1: 250,
          y1: 300,
          x2: 450,
          y2: 500,
          polygon: [[250, 300], [450, 300], [450, 500], [250, 500]],
          initial_box: [100, 100, 200, 200],
          initial_polygon: [[100, 100], [200, 100], [200, 200], [100, 200]],
        },
      ],
    };
    const setOcrData = vi.fn((updater) => {
      ocrData = typeof updater === 'function' ? updater(ocrData) : updater;
    });
    const pushHistory = vi.fn();

    const { result } = renderHook(() =>
      useBubbleActions({ setOcrData, pushHistory })
    );

    act(() => {
      result.current.resetPosition('b1');
    });

    expect(pushHistory).toHaveBeenCalled();
    expect(ocrData.boxes[0].x1).toBe(100);
    expect(ocrData.boxes[0].y1).toBe(100);
    expect(ocrData.boxes[0].x2).toBe(200);
    expect(ocrData.boxes[0].y2).toBe(200);
    expect(ocrData.boxes[0].polygon).toEqual([[100, 100], [200, 100], [200, 200], [100, 200]]);
  });
});
