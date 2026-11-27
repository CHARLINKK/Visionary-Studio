import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CanvasBottomFilmstrip } from '../canvas/CanvasBottomFilmstrip';
import * as SeamlessContextModule from '../../contexts/SeamlessContext';

vi.mock('../../contexts/SeamlessContext', () => ({
  useSeamlessDoc: vi.fn(),
  useSeamlessViewport: vi.fn(),
  useSeamlessUi: vi.fn(),
}));

describe('CanvasBottomFilmstrip Component', () => {
  let mockDoc;
  let mockViewport;
  let mockUi;

  const defaultBoxes = [
    { id: 'b1', order: 1, text: 'Hello World', is_sfx: false },
    { id: 'b2', order: 2, text: 'BOOM!', is_sfx: true, bg_type: 'sfx' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();

    mockDoc = {
      viewMode: 'layout',
      ocrData: { boxes: [...defaultBoxes] },
      setOcrData: vi.fn(),
      history: { pushHistory: vi.fn() },
      activeBubbleId: null,
      setActiveBubbleId: vi.fn(),
    };

    mockViewport = {
      zoom: {
        zoomToSpecificBubble: vi.fn(),
      },
    };

    mockUi = {
      addToast: vi.fn(),
    };

    vi.spyOn(SeamlessContextModule, 'useSeamlessDoc').mockImplementation(() => mockDoc);
    vi.spyOn(SeamlessContextModule, 'useSeamlessViewport').mockImplementation(() => mockViewport);
    vi.spyOn(SeamlessContextModule, 'useSeamlessUi').mockImplementation(() => mockUi);
  });

  it('returns null when viewMode is not layout', () => {
    mockDoc.viewMode = 'view';
    const { container } = render(<CanvasBottomFilmstrip />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null when boxes array is empty', () => {
    mockDoc.ocrData = { boxes: [] };
    const { container } = render(<CanvasBottomFilmstrip />);
    expect(container.firstChild).toBeNull();
  });

  it('renders filmstrip with all bubble chips in layout mode', () => {
    render(<CanvasBottomFilmstrip />);

    expect(screen.getByRole('region')).toBeInTheDocument();
    expect(screen.getByText('Ordem')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();
    expect(screen.getByText('Hello World')).toBeInTheDocument();
    expect(screen.getByText('BOOM!')).toBeInTheDocument();
  });

  it('selects bubble and triggers zoom on chip click', () => {
    render(<CanvasBottomFilmstrip />);

    const chip1 = screen.getByText('#1').closest('.filmstrip-chip');
    fireEvent.click(chip1);

    expect(mockDoc.setActiveBubbleId).toHaveBeenCalledWith('b1');
    expect(mockViewport.zoom.zoomToSpecificBubble).toHaveBeenCalledWith('b1');
  });

  it('navigates through bubbles using next and prev arrow buttons', () => {
    mockDoc.activeBubbleId = 'b1';
    render(<CanvasBottomFilmstrip />);

    const nextBtn = screen.getByTitle(/Próximo balão/i);
    fireEvent.click(nextBtn);

    expect(mockDoc.setActiveBubbleId).toHaveBeenCalledWith('b2');
  });

  it('toggles SFX state on badge click', () => {
    render(<CanvasBottomFilmstrip />);

    const sfxBadge = screen.getByText('SFX').closest('button');
    fireEvent.click(sfxBadge);

    expect(mockDoc.setOcrData).toHaveBeenCalled();
  });

  it('collapses and expands filmstrip on toggle button click', () => {
    render(<CanvasBottomFilmstrip />);

    const collapseBtn = screen.getByTitle(/Minimizar fita de balões/i);
    fireEvent.click(collapseBtn);

    expect(screen.getByText(/Fila de Balões \(2\)/i)).toBeInTheDocument();

    const expandBtn = screen.getByText(/Fila de Balões \(2\)/i).closest('button');
    fireEvent.click(expandBtn);

    expect(screen.getByText('Ordem')).toBeInTheDocument();
  });
});
