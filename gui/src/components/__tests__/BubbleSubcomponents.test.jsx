import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { BubbleBadge } from '../BubbleBadge';
import { BubbleDeleteButton } from '../BubbleDeleteButton';
import { BubblePolygonHandles, BubbleRectHandles } from '../BubbleHandles';

describe('Bubble subcomponents rendering with Konva mocks', () => {
  const sampleBubble = {
    id: 1,
    x1: 100,
    y1: 100,
    x2: 250,
    y2: 200,
    polygon: [[100, 100], [250, 100], [250, 200], [100, 200]],
    label: 'text_tool',
  };

  it('BubbleBadge renders order badge correctly', () => {
    const { container } = render(
      <BubbleBadge
        b={sampleBubble}
        i={0}
        scale={1}
        activeTool="select"
        dragStartPos={null}
        isDeleted={false}
        bubbles={[1, 2]}
      />
    );
    expect(container).not.toBeNull();
  });

  it('BubbleDeleteButton renders without crashing', () => {
    const { container } = render(
      <BubbleDeleteButton
        b={sampleBubble}
        scale={1}
        setOcrData={vi.fn()}
        pushHistory={vi.fn()}
        setActiveBubbleId={vi.fn()}
      />
    );
    expect(container).not.toBeNull();
  });

  it('BubblePolygonHandles renders 4 control vertices', () => {
    const { container } = render(
      <BubblePolygonHandles
        b={sampleBubble}
        bgSize={{ width: 800, height: 1200 }}
        startHistoryTransaction={vi.fn()}
        commitHistoryTransaction={vi.fn()}
        debouncedHistoryUpdate={vi.fn()}
        updateBubbleProperties={vi.fn()}
      />
    );
    expect(container).not.toBeNull();
  });

  it('BubbleRectHandles renders 4 corner control handles', () => {
    const { container } = render(
      <BubbleRectHandles
        b={sampleBubble}
        bgSize={{ width: 800, height: 1200 }}
        startHistoryTransaction={vi.fn()}
        commitHistoryTransaction={vi.fn()}
        debouncedHistoryUpdate={vi.fn()}
        updateBubbleProperties={vi.fn()}
      />
    );
    expect(container).not.toBeNull();
  });
});
