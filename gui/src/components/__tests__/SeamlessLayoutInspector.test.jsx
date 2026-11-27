import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SeamlessLayoutInspector from '../SeamlessEditor/SeamlessLayoutInspector';
import { ToastProvider } from '../../contexts/ToastContext';

describe('SeamlessLayoutInspector component', () => {
  const defaultBubble = {
    id: 'b1',
    text: 'Hello',
    x1: 50,
    y1: 50,
    x2: 150,
    y2: 150,
    initial_box: [50, 50, 150, 150],
    polygon: [[50, 50], [150, 50], [150, 150], [50, 150]],
    initial_polygon: [[50, 50], [150, 50], [150, 150], [50, 150]],
  };

  const defaultProps = {
    activeTool: 'select',
    setActiveTool: vi.fn(),
    setDragStartPos: vi.fn(),
    activeBubbleId: 'b1',
    setActiveBubbleId: vi.fn(),
    setDrawingRect: vi.fn(),
    setPenPoints: vi.fn(),
    bubbles: [],
    setBubbles: vi.fn(),
    setOcrData: vi.fn(),
    pushHistory: vi.fn(),
    page: { path: '/path/p1.png' },
    ocrData: { boxes: [defaultBubble] },
    zoomToSpecificBubble: vi.fn(),
    setRectStartPos: vi.fn(),
    bubbleContourMode: 'polygon',
    setBubbleContourMode: vi.fn(),
  };

  const renderWithToast = (ui) => render(<ToastProvider>{ui}</ToastProvider>);

  it('does NOT render restore position button when active bubble is unmoved', () => {
    renderWithToast(<SeamlessLayoutInspector {...defaultProps} />);
    expect(screen.queryByText('Voltar ao Local Inicial')).toBeNull();
  });

  it('renders restore position button in active actions and in nav list when bubble has moved', () => {
    const movedBubble = {
      ...defaultBubble,
      x1: 120, // moved
    };

    const setOcrData = vi.fn((updater) => {
      if (typeof updater === 'function') updater({ boxes: [movedBubble] });
    });
    const pushHistory = vi.fn();

    renderWithToast(
      <SeamlessLayoutInspector
        {...defaultProps}
        setOcrData={setOcrData}
        pushHistory={pushHistory}
        ocrData={{ boxes: [movedBubble] }}
      />
    );

    const restoreBtn = screen.getByText('Voltar ao Local Inicial');
    expect(restoreBtn).toBeInTheDocument();

    fireEvent.click(restoreBtn);
    expect(pushHistory).toHaveBeenCalled();
    expect(setOcrData).toHaveBeenCalled();
  });

  it('renders contour mode segmented control with active organic mode', () => {
    const setBubbleContourMode = vi.fn();
    renderWithToast(
      <SeamlessLayoutInspector
        {...defaultProps}
        bubbleContourMode="polygon"
        setBubbleContourMode={setBubbleContourMode}
      />
    );

    const organicBtn = screen.getByText('Contorno Orgânico').closest('button');
    const rectBtn = screen.getByText('Caixa Retangular').closest('button');

    expect(organicBtn).toHaveClass('active');
    expect(organicBtn).toHaveAttribute('aria-pressed', 'true');
    expect(rectBtn).not.toHaveClass('active');
    expect(rectBtn).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(rectBtn);
    expect(setBubbleContourMode).toHaveBeenCalledWith('rect');
  });

  it('renders contour mode segmented control with active rectangular mode', () => {
    const setBubbleContourMode = vi.fn();
    renderWithToast(
      <SeamlessLayoutInspector
        {...defaultProps}
        bubbleContourMode="rect"
        setBubbleContourMode={setBubbleContourMode}
      />
    );

    const organicBtn = screen.getByText('Contorno Orgânico').closest('button');
    const rectBtn = screen.getByText('Caixa Retangular').closest('button');

    expect(organicBtn).not.toHaveClass('active');
    expect(organicBtn).toHaveAttribute('aria-pressed', 'false');
    expect(rectBtn).toHaveClass('active');
    expect(rectBtn).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(organicBtn);
    expect(setBubbleContourMode).toHaveBeenCalledWith('polygon');
  });

  it('renders bubble edit mode segmented control and triggers setBubbleEditMode', () => {
    const setBubbleEditMode = vi.fn();
    renderWithToast(
      <SeamlessLayoutInspector
        {...defaultProps}
        bubbleEditMode="box"
        setBubbleEditMode={setBubbleEditMode}
      />
    );

    const boxBtn = screen.getByText('Bordas (8)').closest('button');
    const nodesBtn = screen.getByText('Vértices').closest('button');
    const rawBtn = screen.getByText('Todos Nós').closest('button');

    expect(boxBtn).toHaveClass('active');
    expect(nodesBtn).not.toHaveClass('active');
    expect(rawBtn).not.toHaveClass('active');

    fireEvent.click(nodesBtn);
    expect(setBubbleEditMode).toHaveBeenCalledWith('nodes');

    fireEvent.click(rawBtn);
    expect(setBubbleEditMode).toHaveBeenCalledWith('raw');
  });

  it('triggers quick OCR margin inflation (+6px and -6px)', () => {
    const pushHistory = vi.fn();
    const setOcrData = vi.fn((updater) => {
      if (typeof updater === 'function') updater({ boxes: [defaultBubble] });
    });

    renderWithToast(
      <SeamlessLayoutInspector
        {...defaultProps}
        setOcrData={setOcrData}
        pushHistory={pushHistory}
      />
    );

    const plusBtn = screen.getByText('+6px Margem').closest('button');
    const minusBtn = screen.getByText('-6px Margem').closest('button');

    fireEvent.click(plusBtn);
    expect(pushHistory).toHaveBeenCalled();
    expect(setOcrData).toHaveBeenCalled();

    fireEvent.click(minusBtn);
    expect(pushHistory).toHaveBeenCalledTimes(2);
  });

  it('renders idle placeholder when no bubble is selected in properties tab', () => {
    renderWithToast(
      <SeamlessLayoutInspector
        {...defaultProps}
        activeBubbleId={null}
      />
    );

    const propsTab = screen.getByRole('tab', { name: /propriedades/i });
    fireEvent.click(propsTab);

    expect(screen.getByText('Nenhum balão selecionado')).toBeInTheDocument();
    expect(screen.queryByText('Modo de Edição')).toBeNull();
  });

  it('reorders balloons via drag and drop of blocks in reading order list', () => {
    const bubble1 = { ...defaultBubble, id: 'b1', text: 'Balloon 1' };
    const bubble2 = { ...defaultBubble, id: 'b2', text: 'Balloon 2' };
    const setOcrData = vi.fn((updater) => {
      if (typeof updater === 'function') updater({ boxes: [bubble1, bubble2] });
    });
    const pushHistory = vi.fn();

    renderWithToast(
      <SeamlessLayoutInspector
        {...defaultProps}
        activeBubbleId={null}
        ocrData={{ boxes: [bubble1, bubble2] }}
        setOcrData={setOcrData}
        pushHistory={pushHistory}
      />
    );

    const card1 = document.getElementById('panel-block-b1');
    const card2 = document.getElementById('panel-block-b2');
    expect(card1).toBeInTheDocument();
    expect(card2).toBeInTheDocument();

    const dataTransfer = {
      effectAllowed: '',
      dropEffect: '',
      setData: vi.fn(),
      getData: vi.fn(() => 'b1'),
    };

    fireEvent.dragStart(card1, { dataTransfer });
    fireEvent.dragOver(card2, { dataTransfer });
    fireEvent.drop(card2, { dataTransfer });

    expect(pushHistory).toHaveBeenCalled();
    expect(setOcrData).toHaveBeenCalled();
  });

  it('renders mini page map showing strictly only the balloon of that specific block', () => {
    const bubble1 = { ...defaultBubble, id: 'b1', text: 'Balloon 1' };
    const bubble2 = { ...defaultBubble, id: 'b2', text: 'Balloon 2', x1: 200, y1: 200, x2: 300, y2: 300, polygon: null };

    renderWithToast(
      <SeamlessLayoutInspector
        {...defaultProps}
        activeBubbleId={null}
        ocrData={{ boxes: [bubble1, bubble2] }}
      />
    );

    const card1 = document.getElementById('panel-block-b1');
    expect(card1).toBeInTheDocument();

    const card1Svg = card1.querySelector('.mini-page-map-svg');
    expect(card1Svg).toBeInTheDocument();

    // Contains 1 background rect and 1 polygon for b1 (and no ghost bubbles for b2)
    const polys = card1Svg.querySelectorAll('polygon');
    const rects = card1Svg.querySelectorAll('rect');
    expect(polys.length).toBe(1);
    expect(rects.length).toBe(1); // Only page background rect
  });

  it('renders accessible Unir (L) and SFX (S) icon dock buttons and shows contextual 2-step guidance', () => {
    const setActiveTool = vi.fn();
    const setRectStartPos = vi.fn();
    const setDragStartPos = vi.fn();

    const { rerender } = renderWithToast(
      <SeamlessLayoutInspector
        {...defaultProps}
        activeTool="link"
        rectStartPos={null}
        setActiveTool={setActiveTool}
        setRectStartPos={setRectStartPos}
        setDragStartPos={setDragStartPos}
      />
    );

    expect(screen.getByRole('button', { name: 'Unir (L)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'SFX (S)' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/1\/2: clique no 1º balão/i);

    rerender(
      <ToastProvider>
        <SeamlessLayoutInspector
          {...defaultProps}
          activeTool="link"
          rectStartPos="b1"
          setActiveTool={setActiveTool}
          setRectStartPos={setRectStartPos}
          setDragStartPos={setDragStartPos}
        />
      </ToastProvider>
    );

    expect(screen.getByRole('status')).toHaveTextContent(/2\/2: #1 marcado/i);

    const cancelBtn = screen.getByTitle(/Cancelar ferramenta/i);
    fireEvent.click(cancelBtn);
    expect(setRectStartPos).toHaveBeenCalledWith(null);
    expect(setActiveTool).toHaveBeenCalledWith('select');
  });
});
