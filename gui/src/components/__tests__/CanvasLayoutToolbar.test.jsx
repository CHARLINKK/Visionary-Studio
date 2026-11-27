import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CanvasLayoutToolbar } from '../canvas/CanvasLayoutToolbar';
import * as SeamlessContextModule from '../../contexts/SeamlessContext';

vi.mock('../../contexts/SeamlessContext', () => ({
  useSeamlessDoc: vi.fn(),
  useSeamlessToolsState: vi.fn(),
  useSeamlessUi: vi.fn(),
}));

describe('CanvasLayoutToolbar Component', () => {
  let mockDoc;
  let mockTools;
  let mockUi;

  beforeEach(() => {
    vi.clearAllMocks();

    mockDoc = {
      viewMode: 'layout',
      page: { path: '/test/p1.png' },
      ocrData: {
        boxes: [
          { id: 'b1', order: 1, text: 'One' },
          { id: 'b2', order: 2, text: 'Two' },
        ],
      },
      setOcrData: vi.fn(),
      history: { pushHistory: vi.fn() },
      bubbleContourMode: 'polygon',
      setBubbleContourMode: vi.fn(),
      setActiveBubbleId: vi.fn(),
    };

    mockTools = {
      tools: {
        activeTool: 'select',
        setActiveTool: vi.fn(),
        setDragStartPos: vi.fn(),
        setDrawingRect: vi.fn(),
        setPenPoints: vi.fn(),
        bubbles: [],
        setBubbles: vi.fn(),
        setRectStartPos: vi.fn(),
      },
    };

    mockUi = {
      addToast: vi.fn(),
    };

    vi.spyOn(SeamlessContextModule, 'useSeamlessDoc').mockImplementation(() => mockDoc);
    vi.spyOn(SeamlessContextModule, 'useSeamlessToolsState').mockImplementation(() => mockTools);
    vi.spyOn(SeamlessContextModule, 'useSeamlessUi').mockImplementation(() => mockUi);
  });

  it('returns null when viewMode is not layout', () => {
    mockDoc.viewMode = 'view';
    const { container } = render(<CanvasLayoutToolbar />);
    expect(container.firstChild).toBeNull();
  });

  it('renders all layout tools and contour mode in layout mode', () => {
    render(<CanvasLayoutToolbar />);

    expect(screen.getByRole('toolbar')).toBeInTheDocument();
    expect(screen.getByTitle(/Selecionar, Mover/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Desenhar Caixa Retangular/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Desenhar Balão Manual/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Reordenar Balão no Fluxo/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Modo Sequência/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Auto-organizar Ordem/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Vincular Balões em Família/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Alternar Balão \/ SFX/i)).toBeInTheDocument();

    expect(screen.getByText('Orgânico')).toBeInTheDocument();
    expect(screen.getByText('BBox')).toBeInTheDocument();
  });

  it('activates tool on click and resets drawing states', () => {
    render(<CanvasLayoutToolbar />);

    const rectBtn = screen.getByTitle(/Desenhar Caixa Retangular/i);
    fireEvent.click(rectBtn);

    expect(mockTools.tools.setActiveTool).toHaveBeenCalledWith('rect');
    expect(mockDoc.setActiveBubbleId).toHaveBeenCalledWith(null);
    expect(mockTools.tools.setDrawingRect).toHaveBeenCalledWith(null);

    const penBtn = screen.getByTitle(/Desenhar Balão Manual/i);
    fireEvent.click(penBtn);

    expect(mockTools.tools.setActiveTool).toHaveBeenCalledWith('pen');
    expect(mockTools.tools.setPenPoints).toHaveBeenCalledWith([]);
  });

  it('switches global contour mode on click', () => {
    render(<CanvasLayoutToolbar />);

    const bboxBtn = screen.getByText('BBox').closest('button');
    fireEvent.click(bboxBtn);

    expect(mockDoc.setBubbleContourMode).toHaveBeenCalledWith('rect');
    expect(mockUi.addToast).toHaveBeenCalledWith(expect.stringContaining('Caixa Retangular'), 'info');
  });

  it('renders sequence queue badge and applies sequence order', () => {
    mockTools.tools.activeTool = 'sequence';
    mockTools.tools.bubbles = ['b2', 'b1'];

    render(<CanvasLayoutToolbar />);

    expect(screen.getByText('2 na fila')).toBeInTheDocument();
    const applyBtn = screen.getByText('Aplicar');

    fireEvent.click(applyBtn);

    expect(mockDoc.setOcrData).toHaveBeenCalled();
    expect(mockTools.tools.setBubbles).toHaveBeenCalledWith([]);
    expect(mockUi.addToast).toHaveBeenCalledWith(expect.stringContaining('Sequência aplicada'), 'success');
  });
});
