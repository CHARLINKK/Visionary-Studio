import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import {
  CanvasBackgroundLayer,
  CanvasGuidesLayer,
  CanvasBubblesLayer,
  CanvasDrawingLayer,
} from '../canvas';

describe('Canvas Sublayers Architecture', () => {
  describe('CanvasBackgroundLayer', () => {
    it('renders fallback rectangle when bgImage is null', () => {
      const { container } = render(
        <CanvasBackgroundLayer bgImage={null} bgSize={{ width: 800, height: 1200 }} />
      );
      const layer = container.querySelector('#bg-layer');
      expect(layer).not.toBeNull();
      const rect = container.querySelector('#bg-layer-rect');
      expect(rect).not.toBeNull();
    });

    it('renders image when bgImage is provided', () => {
      const dummyImage = { width: 1000, height: 1500 };
      const { container } = render(
        <CanvasBackgroundLayer bgImage={dummyImage} bgSize={{ width: 1000, height: 1500 }} />
      );
      const layer = container.querySelector('#bg-layer');
      expect(layer).not.toBeNull();
    });
  });

  describe('CanvasGuidesLayer', () => {
    it('returns null in view mode without ocr debug', () => {
      const { container } = render(
        <CanvasGuidesLayer
          viewMode="view"
          boxes={[]}
          showOcrDebug={false}
        />
      );
      expect(container.firstChild).toBeNull();
    });

    it('renders links and panels in edit mode with debug info', () => {
      const boxes = [
        { id: '1', group_id: 'g1', x1: 10, y1: 10, x2: 50, y2: 50 },
        { id: '2', group_id: 'g1', x1: 60, y1: 60, x2: 100, y2: 100 },
      ];
      const panels = [
        { box: [0, 0, 200, 200] }
      ];

      const { container } = render(
        <CanvasGuidesLayer
          viewMode="layout"
          boxes={boxes}
          panels={panels}
          activeTool="select"
          rectStartPos={null}
          mousePos={null}
          scale={1}
          showOcrDebug={true}
        />
      );

      const layer = container.querySelector('#guides-layer');
      expect(layer).not.toBeNull();
    });

    it('renders refined polygon panels when polygon coordinates are present', () => {
      const panels = [
        {
          id: 1,
          box: [114, 0, 1044, 768],
          polygon: [[114, 0], [942, 0], [1044, 752], [114, 768]],
        },
      ];

      const { container } = render(
        <CanvasGuidesLayer
          viewMode="layout"
          boxes={[]}
          panels={panels}
          activeTool="select"
          rectStartPos={null}
          mousePos={null}
          scale={1}
          showOcrDebug={true}
        />
      );

      const layer = container.querySelector('#guides-layer');
      expect(layer).not.toBeNull();
    });
  });

  describe('CanvasBubblesLayer', () => {
    it('renders bubbles via BubbleShape', () => {
      const boxes = [
        { id: 'b1', x1: 10, y1: 10, x2: 50, y2: 50, text: 'Hello' }
      ];

      const { container } = render(
        <CanvasBubblesLayer
          boxes={boxes}
          scale={1}
          bgSize={{ width: 1000, height: 1500 }}
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
          bubbles={boxes}
          setBubbles={vi.fn()}
          rectStartPos={null}
          setRectStartPos={vi.fn()}
          updateBubbleProperties={vi.fn()}
        />
      );

      const layer = container.querySelector('#interactive-layer');
      expect(layer).not.toBeNull();
      const bubble = container.querySelector('#box-b1');
      expect(bubble).not.toBeNull();
    });

    it('renders bubbles with simplified props and actions controller', () => {
      const boxes = [
        { id: 'b1', x1: 10, y1: 10, x2: 50, y2: 50, text: 'Hello' }
      ];
      const mockActions = {
        select: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
      };

      const { container } = render(
        <CanvasBubblesLayer
          boxes={boxes}
          scale={1}
          bgSize={{ width: 1000, height: 1500 }}
          viewMode="layout"
          activeTool="select"
          activeBubbleId="b1"
          actions={mockActions}
        />
      );

      const layer = container.querySelector('#interactive-layer');
      expect(layer).not.toBeNull();
      const bubble = container.querySelector('#box-b1');
      expect(bubble).not.toBeNull();
    });
  });

  describe('CanvasDrawingLayer', () => {
    it('returns null if viewMode is not layout', () => {
      const { container } = render(
        <CanvasDrawingLayer
          viewMode="typeset"
          activeTool="rect"
          drawingRect={{ startX: 0, startY: 0, endX: 100, endY: 100 }}
        />
      );
      expect(container.firstChild).toBeNull();
    });

    it('renders rectangle preview when drawing with rect tool in layout mode', () => {
      const { container } = render(
        <CanvasDrawingLayer
          viewMode="layout"
          activeTool="rect"
          drawingRect={{ startX: 10, startY: 20, endX: 110, endY: 120 }}
          scale={1}
        />
      );
      const layer = container.querySelector('#drawing-preview-layer');
      expect(layer).not.toBeNull();
    });

    it('renders pen points preview when drawing with pen tool in layout mode', () => {
      const { container } = render(
        <CanvasDrawingLayer
          viewMode="layout"
          activeTool="pen"
          penPoints={[[10, 10], [50, 50]]}
          mousePos={{ x: 60, y: 60 }}
          scale={1}
        />
      );
      const layer = container.querySelector('#drawing-preview-layer');
      expect(layer).not.toBeNull();
    });
  });
});
