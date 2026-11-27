import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import StudioBatchSidebar from '../StudioBatchSidebar';

vi.mock('../Queue', () => ({
  default: () => <div data-testid="batch-queue">Queue</div>,
}));

describe('StudioBatchSidebar component', () => {
  const defaultProps = {
    pages: [
      { name: '001.jpg', path: 'C:/manga/001.jpg', pageData: { translation: true, layout: true, ocr: true } },
      { name: '002.jpg', path: 'C:/manga/002.jpg', pageData: { ocr: true, layout: true } },
    ],
    selectedPages: new Set([0]),
    currentIndex: 0,
    setCurrentIndex: vi.fn(),
    handleSelectAll: vi.fn(),
    handleTogglePage: vi.fn(),
    requestClear: vi.fn(),
    isClearing: false,
    canRunOcr: true,
    canRunTranslate: true,
    isSubmitting: false,
    setSteps: vi.fn(),
    handleProcess: vi.fn(),
    deepValidation: false,
    setDeepValidation: vi.fn(),
    overwrite: false,
    setOverwrite: vi.fn(),
  };

  it('renders correctly with studio-sidebar structure, micro-tracks and pipeline dock', () => {
    const { container } = render(<StudioBatchSidebar {...defaultProps} />);

    expect(container.querySelector('.studio-sidebar.batch-sidebar')).not.toBeNull();
    expect(screen.getByText('Processamento em Lote')).toBeInTheDocument();
    expect(screen.getByText('Páginas (1/2)')).toBeInTheDocument();
    expect(screen.getByText('Todas')).toBeInTheDocument();
    expect(screen.getByText('001.jpg')).toBeInTheDocument();
    expect(screen.getByText('002.jpg')).toBeInTheDocument();

    // Micro-tracks for both pages
    expect(container.querySelectorAll('.vs-micro-track').length).toBe(2);

    // Vertical pipeline stages
    expect(screen.getByText('1. Layout')).toBeInTheDocument();
    expect(screen.getByText('2. OCR')).toBeInTheDocument();
    expect(screen.getByText('3. Tradução')).toBeInTheDocument();
    expect(screen.getByText('Filtro SFX')).toBeInTheDocument();
    expect(screen.getByText('Sobrescrever dados existentes')).toBeInTheDocument();
    expect(screen.getByText('Executar Pipeline Completa (1 Página)')).toBeInTheDocument();
  });

  it('handles page selection and select all actions', () => {
    render(<StudioBatchSidebar {...defaultProps} />);

    fireEvent.click(screen.getByText('Todas'));
    expect(defaultProps.handleSelectAll).toHaveBeenCalledTimes(1);

    const checkboxes = screen.getAllByRole('generic').filter(el => el.classList.contains('checkbox-wrapper'));
    if (checkboxes.length > 0) {
      fireEvent.click(checkboxes[1]);
      expect(defaultProps.handleTogglePage).toHaveBeenCalledWith(1);
    }
  });

  it('triggers clear requests for translation, ocr and all', () => {
    render(<StudioBatchSidebar {...defaultProps} />);

    const clearTrBtn = screen.getByTitle('Apagar apenas traduções');
    fireEvent.click(clearTrBtn);
    expect(defaultProps.requestClear).toHaveBeenCalledWith(['translate']);

    const clearOcrBtn = screen.getByTitle('Apagar OCR e Traduções');
    fireEvent.click(clearOcrBtn);
    expect(defaultProps.requestClear).toHaveBeenCalledWith(['ocr', 'translate']);

    const clearAllBtn = screen.getByTitle('Apagar balões, OCR e traduções');
    fireEvent.click(clearAllBtn);
    expect(defaultProps.requestClear).toHaveBeenCalledWith(['layout', 'ocr', 'translate']);
  });

  it('triggers individual pipeline step execution', () => {
    render(<StudioBatchSidebar {...defaultProps} />);

    const layoutBtn = screen.getByTitle('Executar apenas Layout nas páginas selecionadas');
    fireEvent.click(layoutBtn);
    expect(defaultProps.setSteps).toHaveBeenCalledWith({ layout: true, ocr: false, translate: false });
    expect(defaultProps.handleProcess).toHaveBeenCalledWith({ layout: true, ocr: false, translate: false });

    const ocrBtn = screen.getByTitle('Executar apenas OCR nas páginas selecionadas');
    fireEvent.click(ocrBtn);
    expect(defaultProps.setSteps).toHaveBeenCalledWith({ layout: false, ocr: true, translate: false });
    expect(defaultProps.handleProcess).toHaveBeenCalledWith({ layout: false, ocr: true, translate: false });

    const transBtn = screen.getByTitle('Executar apenas Tradução nas páginas selecionadas');
    fireEvent.click(transBtn);
    expect(defaultProps.setSteps).toHaveBeenCalledWith({ layout: false, ocr: false, translate: true });
    expect(defaultProps.handleProcess).toHaveBeenCalledWith({ layout: false, ocr: false, translate: true });
  });

  it('triggers unified pipeline execution with the master button', () => {
    render(<StudioBatchSidebar {...defaultProps} />);

    const masterBtn = screen.getByText('Executar Pipeline Completa (1 Página)');
    fireEvent.click(masterBtn);
    expect(defaultProps.setSteps).toHaveBeenCalledWith({ layout: true, ocr: true, translate: true });
    expect(defaultProps.handleProcess).toHaveBeenCalledWith({ layout: true, ocr: true, translate: true });
  });

  it('toggles deep validation and overwrite', () => {
    render(<StudioBatchSidebar {...defaultProps} />);

    const sfxPill = screen.getByText('Filtro SFX');
    fireEvent.click(sfxPill);
    expect(defaultProps.setDeepValidation).toHaveBeenCalledWith(true);

    const overwriteCheckbox = screen.getByRole('checkbox', { name: /sobrescrever dados existentes/i });
    fireEvent.click(overwriteCheckbox);
    expect(defaultProps.setOverwrite).toHaveBeenCalledWith(true);
  });

  it('displays informative status pills and hints when no pages are selected or requirements are missing', () => {
    // Zero pages selected: clean layout without redundant pills
    const { rerender } = render(<StudioBatchSidebar {...defaultProps} selectedPages={new Set()} />);
    
    expect(screen.queryByText('0 selecionadas')).toBeNull();
    expect(screen.getByText(/Marque páginas na lista acima/i)).toBeInTheDocument();
    expect(screen.getByText('Selecione Páginas')).toBeInTheDocument();

    // 1 page selected without layout or OCR
    rerender(
      <StudioBatchSidebar
        {...defaultProps}
        selectedPages={new Set([0])}
        pages={[
          { name: '001.jpg', path: 'C:/manga/001.jpg', pageData: {} },
        ]}
        canRunOcr={false}
        canRunTranslate={false}
      />
    );

    expect(screen.getByText('Requer Layout (1)')).toBeInTheDocument();
    expect(screen.getByText('Requer OCR (1)')).toBeInTheDocument();
  });
});
