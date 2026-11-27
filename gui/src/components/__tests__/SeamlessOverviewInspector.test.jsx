import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import SeamlessOverviewInspector from '../SeamlessEditor/SeamlessOverviewInspector';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';

describe('SeamlessOverviewInspector component', () => {
  const defaultProps = {
    page: { name: 'page_001.png' },
    bgSize: { width: 1200, height: 1800 },
    canEditLayout: true,
    canEditOcr: true,
    canEditTranslation: true,
    ocrData: { boxes: [] },
    setIsRestartModalOpen: vi.fn(),
    showOcrDebug: false,
    setShowOcrDebug: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({ isDevUnlocked: false });
  });

  it('does NOT render debug panels button in standard user mode', () => {
    render(<SeamlessOverviewInspector {...defaultProps} />);

    expect(screen.getByText('Redefinir Página (Apagar Tudo)')).toBeInTheDocument();
    expect(screen.queryByText('Exibir Painéis (Debug)')).toBeNull();
    expect(screen.queryByText('Ocultar Painéis (Debug)')).toBeNull();
  });

  it('renders debug panels button when dev mode is unlocked', () => {
    useWorkspaceStore.setState({ isDevUnlocked: true });

    render(<SeamlessOverviewInspector {...defaultProps} />);

    const debugBtn = screen.getByText('Exibir Painéis (Debug)');
    expect(debugBtn).toBeInTheDocument();
    expect(screen.getByText('Redefinir Página (Apagar Tudo)')).toBeInTheDocument();

    fireEvent.click(debugBtn);
    expect(defaultProps.setShowOcrDebug).toHaveBeenCalledWith(true);
  });

  it('displays active state text when showOcrDebug is true in dev mode', () => {
    useWorkspaceStore.setState({ isDevUnlocked: true });

    render(<SeamlessOverviewInspector {...defaultProps} showOcrDebug={true} />);

    const debugBtn = screen.getByText('Ocultar Painéis (Debug)');
    expect(debugBtn).toBeInTheDocument();

    fireEvent.click(debugBtn);
    expect(defaultProps.setShowOcrDebug).toHaveBeenCalledWith(false);
  });

  it('auto-disables showOcrDebug if dev mode gets locked while debug was active', () => {
    useWorkspaceStore.setState({ isDevUnlocked: true });
    const setShowOcrDebug = vi.fn();

    const { rerender } = render(
      <SeamlessOverviewInspector
        {...defaultProps}
        showOcrDebug={true}
        setShowOcrDebug={setShowOcrDebug}
      />
    );

    expect(screen.getByText('Ocultar Painéis (Debug)')).toBeInTheDocument();

    act(() => {
      useWorkspaceStore.setState({ isDevUnlocked: false });
    });

    rerender(
      <SeamlessOverviewInspector
        {...defaultProps}
        showOcrDebug={true}
        setShowOcrDebug={setShowOcrDebug}
      />
    );

    expect(setShowOcrDebug).toHaveBeenCalledWith(false);
    expect(screen.queryByText('Ocultar Painéis (Debug)')).toBeNull();
  });

  it('renders contextual next-step action and navigates mode on click', () => {
    const setViewMode = vi.fn();

    // Com 0 balões
    const { rerender } = render(
      <SeamlessOverviewInspector
        {...defaultProps}
        setViewMode={setViewMode}
        ocrData={{ boxes: [] }}
      />
    );

    const layoutBtn = screen.getByText(/Abrir Modo Layout para Delimitar/i);
    expect(layoutBtn).toBeInTheDocument();
    fireEvent.click(layoutBtn);
    expect(setViewMode).toHaveBeenCalledWith('layout');

    // Com balões prontos para OCR
    const sampleBoxes = [
      { id: 'b1', text: 'Konnichiwa', x1: 500, y1: 100, x2: 700, y2: 300, is_sfx: false },
      { id: 'b2', text: '', x1: 100, y1: 400, x2: 250, y2: 600, is_sfx: true },
    ];

    rerender(
      <SeamlessOverviewInspector
        {...defaultProps}
        canEditOcr={true}
        canEditTranslation={false}
        setViewMode={setViewMode}
        ocrData={{ boxes: sampleBoxes }}
      />
    );

    const ocrBtn = screen.getByText(/Ir para Revisão de OCR/i);
    expect(ocrBtn).toBeInTheDocument();
    fireEvent.click(ocrBtn);
    expect(setViewMode).toHaveBeenCalledWith('ocr');
  });

  it('does NOT render visual controls and sanity audit cards', () => {
    render(<SeamlessOverviewInspector {...defaultProps} />);
    expect(screen.queryByText('Controles de Visualização')).toBeNull();
    expect(screen.queryByText('Auditoria de Sanidade')).toBeNull();
  });

  it('opens sequential script preview drawer and displays lines', () => {
    const sampleBoxes = [
      { id: 'b1', text: 'Olá mundo', translated: 'Hello world', x1: 100, y1: 100, x2: 200, y2: 200, is_sfx: false },
    ];

    render(
      <SeamlessOverviewInspector
        {...defaultProps}
        ocrData={{ boxes: sampleBoxes }}
      />
    );

    const scriptToggleBtn = screen.getByText(/Ver Roteiro da Página/i);
    expect(scriptToggleBtn).toBeInTheDocument();

    fireEvent.click(scriptToggleBtn);

    expect(screen.getByText('Roteiro Sequencial')).toBeInTheDocument();
    expect(screen.getByText('Olá mundo')).toBeInTheDocument();
    expect(screen.getByText(/Hello world/i)).toBeInTheDocument();
  });
});
