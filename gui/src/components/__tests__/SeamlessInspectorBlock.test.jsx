import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SeamlessInspectorBlock from '../SeamlessEditor/SeamlessInspectorBlock';

describe('SeamlessInspectorBlock component', () => {
  const defaultBubble = {
    id: 'block_1',
    text: 'Japanese original',
    translated: 'Português traduzido',
    x1: 50,
    y1: 50,
    x2: 150,
    y2: 150,
    initial_box: [50, 50, 150, 150],
    polygon: [[50, 50], [150, 50], [150, 150], [50, 150]],
    initial_polygon: [[50, 50], [150, 50], [150, 150], [50, 150]],
  };

  const defaultProps = {
    b: defaultBubble,
    i: 0,
    ocrData: { boxes: [defaultBubble] },
    setOcrData: vi.fn(),
    activeBubbleId: null,
    setActiveBubbleId: vi.fn(),
    viewMode: 'layout',
    previewSrc: null,
    setPreviewSrc: vi.fn(),
    zoomToSpecificBubble: vi.fn(),
    debouncedHistoryUpdate: vi.fn(),
    pushHistory: vi.fn(),
    startHistoryTransaction: vi.fn(),
    commitHistoryTransaction: vi.fn(),
  };

  it('does NOT render restore position button when bubble is at initial coordinates', () => {
    render(<SeamlessInspectorBlock {...defaultProps} />);
    expect(screen.queryByText('Voltar ao local inicial')).toBeNull();
  });

  it('renders restore position button when bubble has moved and triggers restore', () => {
    const movedBubble = {
      ...defaultBubble,
      x1: 90, // moved from 50
    };
    render(<SeamlessInspectorBlock {...defaultProps} b={movedBubble} />);

    const restoreBtn = screen.getByText('Voltar ao local inicial');
    expect(restoreBtn).toBeInTheDocument();

    fireEvent.click(restoreBtn);

    expect(defaultProps.pushHistory).toHaveBeenCalled();
    expect(defaultProps.debouncedHistoryUpdate).toHaveBeenCalledWith(
      'block_1',
      expect.objectContaining({
        x1: 50,
        y1: 50,
        x2: 150,
        y2: 150,
      })
    );
  });
});
