import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { BubbleShape } from '../BubbleShape';

describe('BubbleShape component with declarative Konva mock', () => {
  const defaultBubble = {
    id: 'bubble_42',
    text: 'Original Japanese Text',
    translated: 'Texto em Português',
    x1: 50,
    y1: 50,
    x2: 200,
    y2: 150,
    box_2d: [50, 50, 200, 150],
    center: [125, 100],
  };

  it('should render bubble group and elements without canvas C++ crashes (legacy props)', () => {
    const { container } = render(
      <BubbleShape
        b={defaultBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        setOcrData={vi.fn()}
        activeBubbleId={null}
        setActiveBubbleId={vi.fn()}
        viewMode="typeset"
        activeTool="select"
        dragStartPos={{ x: 0, y: 0 }}
        setDragStartPos={vi.fn()}
        pushHistory={vi.fn()}
        startHistoryTransaction={vi.fn()}
        commitHistoryTransaction={vi.fn()}
        debouncedHistoryUpdate={vi.fn()}
        bubbles={[defaultBubble]}
        setBubbles={vi.fn()}
        rectStartPos={null}
        setRectStartPos={vi.fn()}
        updateBubbleProperties={vi.fn()}
      />
    );

    const group = container.querySelector('#box-bubble_42');
    expect(group).not.toBeNull();
  });

  it('renders cleanly with atomic props and triggers actions on click', () => {
    const mockActions = {
      select: vi.fn(),
      reorder: vi.fn(),
      sequence: vi.fn(),
      link: vi.fn(),
      unlink: vi.fn(),
      delete: vi.fn(),
      dragStart: vi.fn(),
      dragEnd: vi.fn(),
      update: vi.fn(),
    };

    const { container } = render(
      <BubbleShape
        b={defaultBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="select"
        isSelected={false}
        isReorderSource={false}
        isLinkSource={false}
        sequenceIndex={-1}
        actions={mockActions}
      />
    );

    const group = container.querySelector('#box-bubble_42');
    expect(group).not.toBeNull();

    fireEvent.click(group);
    expect(mockActions.select).toHaveBeenCalledWith('bubble_42');
  });

  it('renders delete button when selected in layout select mode and calls delete action', () => {
    const mockActions = {
      select: vi.fn(),
      delete: vi.fn(),
      dragStart: vi.fn(),
      dragEnd: vi.fn(),
      update: vi.fn(),
    };

    const { container } = render(
      <BubbleShape
        b={defaultBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="select"
        isSelected={true}
        isReorderSource={false}
        isLinkSource={false}
        sequenceIndex={-1}
        actions={mockActions}
      />
    );

    // Group should exist
    expect(container.querySelector('#box-bubble_42')).not.toBeNull();
  });

  it('renders Line element when bubble has organic polygon in polygon contour mode', () => {
    const polygonBubble = {
      ...defaultBubble,
      id: 'bubble_poly',
      polygon: [
        [50, 50], [120, 40], [200, 50], [190, 140], [120, 150], [50, 140]
      ],
    };

    const { container } = render(
      <BubbleShape
        b={polygonBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="select"
        isSelected={false}
        bubbleContourMode="polygon"
      />
    );

    expect(container.querySelector('#box-bubble_poly')).not.toBeNull();
  });

  it('renders Rect fallback when bubbleContourMode is rect even if polygon exists', () => {
    const polygonBubble = {
      ...defaultBubble,
      id: 'bubble_rect_mode',
      polygon: [
        [50, 50], [120, 40], [200, 50], [190, 140], [120, 150], [50, 140]
      ],
    };

    const { container } = render(
      <BubbleShape
        b={polygonBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="select"
        isSelected={false}
        bubbleContourMode="rect"
      />
    );

    expect(container.querySelector('#box-bubble_rect_mode')).not.toBeNull();
  });

  it('only enables drag when selected in layout select mode (accidental drag protection)', () => {
    const { container, rerender } = render(
      <BubbleShape
        b={defaultBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="select"
        isSelected={false}
      />
    );

    const group = container.querySelector('#box-bubble_42');
    expect(group).not.toBeNull();
    // Unselected bubble should NOT be draggable to prevent accidental drag
    expect(group.getAttribute('data-draggable')).toBe('false');

    // Once selected, dragging is enabled
    rerender(
      <BubbleShape
        b={defaultBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="select"
        isSelected={true}
      />
    );
    expect(group.getAttribute('data-draggable')).toBe('true');

    // In other tools (e.g. reorder), dragging is disabled even if selected
    rerender(
      <BubbleShape
        b={defaultBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="reorder"
        isSelected={true}
      />
    );
    expect(group.getAttribute('data-draggable')).toBe('false');
  });

  it('renders BubbleResetPositionButton only when bubble has moved from initial_box and triggers resetPosition', () => {
    const mockActions = {
      select: vi.fn(),
      delete: vi.fn(),
      resetPosition: vi.fn(),
    };

    const unmovedBubble = {
      ...defaultBubble,
      initial_box: [50, 50, 200, 150],
    };

    const { container, rerender } = render(
      <BubbleShape
        b={unmovedBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="select"
        isSelected={true}
        actions={mockActions}
      />
    );

    // When unmoved, reset button should NOT exist
    expect(container.querySelector('#btn-reset-bubble_42')).toBeNull();

    // Now bubble is moved
    const movedBubble = {
      ...defaultBubble,
      x1: 120, // moved from 50 to 120
      initial_box: [50, 50, 200, 150],
    };

    rerender(
      <BubbleShape
        b={movedBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="select"
        isSelected={true}
        actions={mockActions}
      />
    );

    const resetBtn = container.querySelector('#btn-reset-bubble_42');
    expect(resetBtn).not.toBeNull();

    fireEvent.click(resetBtn);
    expect(mockActions.resetPosition).toHaveBeenCalledWith('bubble_42');
  });

  it('toggles node edit mode on double click for organic polygon and exits on Escape', () => {
    const polygonBubble = {
      ...defaultBubble,
      polygon: [
        [50, 50],
        [200, 50],
        [220, 100],
        [200, 150],
        [50, 150],
        [40, 100],
      ],
    };

    const { container } = render(
      <BubbleShape
        b={polygonBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="select"
        isSelected={true}
        bubbleContourMode="polygon"
      />
    );

    const group = container.querySelector('#box-bubble_42');
    expect(group).not.toBeNull();
    expect(group.getAttribute('data-draggable')).toBe('true');

    // Double click enters node editing: group becomes non-draggable so individual anchor circles can be dragged
    fireEvent.doubleClick(group);
    expect(group.getAttribute('data-draggable')).toBe('false');

    // Press Escape to exit node editing
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(group.getAttribute('data-draggable')).toBe('true');
  });

  it('triggers unlink on right click when in layout viewMode and link tool is active', () => {
    const mockActions = {
      select: vi.fn(),
      unlink: vi.fn(),
      openContextMenu: vi.fn(),
    };

    const linkedBubble = {
      ...defaultBubble,
      group_id: 'grp_alpha',
    };

    const { container } = render(
      <BubbleShape
        b={linkedBubble}
        i={0}
        scale={1}
        bgSize={{ width: 1000, height: 1500 }}
        totalBubbles={1}
        viewMode="layout"
        activeTool="link"
        isSelected={false}
        actions={mockActions}
      />
    );

    const group = container.querySelector('#box-bubble_42');
    expect(group).not.toBeNull();

    fireEvent.contextMenu(group);
    expect(mockActions.unlink).toHaveBeenCalledWith('bubble_42', 'grp_alpha');
    expect(mockActions.openContextMenu).not.toHaveBeenCalled();
  });
});
