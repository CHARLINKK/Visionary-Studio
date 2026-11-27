import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import Lightbox from '../Lightbox';

const mockAddToast = vi.fn();
vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({ addToast: mockAddToast })
}));

const mockBumpExplorerRevision = vi.fn();
const mockNavigateToStudioPage = vi.fn();
vi.mock('../../stores/useWorkspaceStore', () => ({
  useWorkspaceStore: (selector) => selector({
    bumpExplorerRevision: mockBumpExplorerRevision,
    navigateToStudioPage: mockNavigateToStudioPage
  })
}));

const mockListDirectory = vi.fn();
const mockReorderPages = vi.fn();
const mockMergePages = vi.fn();
const mockSplitPage = vi.fn();
const mockDeletePage = vi.fn();

vi.mock('../../api/bridge', () => ({
  getServerUrl: () => 'http://127.0.0.1:5000',
  clientApi: {
    listDirectory: (...args) => mockListDirectory(...args),
    reorder_pages: (...args) => mockReorderPages(...args),
    merge_pages: (...args) => mockMergePages(...args),
    split_page: (...args) => mockSplitPage(...args),
    delete_page: (...args) => mockDeletePage(...args),
  }
}));

describe('Lightbox component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders guided empty state when activeChapterPath is null', () => {
    render(<Lightbox activeChapterPath={null} />);

    expect(screen.getByText('Nenhum capítulo selecionado')).toBeInTheDocument();
    expect(screen.getByText('Selecione o Capítulo')).toBeInTheDocument();
    expect(screen.getByText('Ajuste na Lightbox')).toBeInTheDocument();
    expect(screen.getByText('Traduza no Estúdio')).toBeInTheDocument();
  });

  it('renders images and header bar with chapter information', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [
        { name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true },
        { name: '02.png', path: 'C:/Manga/Cap_01/02.png', isImage: true }
      ]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    expect(screen.getByText('Cap_01')).toBeInTheDocument();
    expect(screen.getByText('2 págs')).toBeInTheDocument();
    expect(screen.getByText('02.png')).toBeInTheDocument();
    const cardImg = screen.getByAltText('01.png');
    expect(cardImg.getAttribute('src')).toContain('&thumb=360');
  });

  it('toggles the help popover when clicking the tips button', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [{ name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true }]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    // Initial state: help popover is closed
    expect(screen.queryByText('Guia Rápido da Lightbox')).not.toBeInTheDocument();

    // Click to open popover
    const helpBtn = screen.getByTitle('Dicas de uso da Lightbox');
    fireEvent.click(helpBtn);

    expect(screen.getByText('Guia Rápido da Lightbox')).toBeInTheDocument();
    expect(screen.getByText(/Reordena páginas/)).toBeInTheDocument();

    // Click close button inside popover
    const closeBtn = screen.getByTitle('Fechar guia');
    fireEvent.click(closeBtn);

    expect(screen.queryByText('Guia Rápido da Lightbox')).not.toBeInTheDocument();
  });

  it('allows selecting pages and enables contextual action buttons', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [
        { name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true },
        { name: '02.png', path: 'C:/Manga/Cap_01/02.png', isImage: true }
      ]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    // Click "Tudo"
    const selectAllBtn = screen.getByTitle('Selecionar todas as páginas do capítulo');
    fireEvent.click(selectAllBtn);

    expect(screen.getByText('2 selecionadas')).toBeInTheDocument();
    expect(screen.getByText('Unir Páginas (2)')).toBeInTheDocument();

    // Click "Limpar"
    const clearBtn = screen.getByTitle('Limpar seleção atual');
    fireEvent.click(clearBtn);

    expect(screen.queryByText('2 selecionadas')).not.toBeInTheDocument();
  });

  it('does not trigger navigation to studio when double-clicking the select checkbox rapidly', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [{ name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true }]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    const selectChip = screen.getByTitle('Selecionar página');
    
    // Rapid clicking / double click on selection chip
    fireEvent.click(selectChip);
    fireEvent.doubleClick(selectChip);
    fireEvent.click(selectChip);

    // Should NOT navigate to Studio
    expect(mockNavigateToStudioPage).not.toHaveBeenCalled();
    expect(mockAddToast).not.toHaveBeenCalledWith(expect.stringContaining('Estúdio'), 'info');
  });

  it('allows changing grid columns via zoom buttons and indicator click', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [{ name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true }]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    // Initial default is 4 col
    expect(screen.getByText('4 col')).toBeInTheDocument();

    // Click ZoomOut (more columns / smaller cards)
    const zoomOutBtn = screen.getByTitle('Mais colunas por linha (cards menores)');
    fireEvent.click(zoomOutBtn);
    expect(screen.getByText('5 col')).toBeInTheDocument();
    expect(localStorage.getItem('visionary:lightbox_columns')).toBe('5');

    // Click ZoomIn (fewer columns / larger cards)
    const zoomInBtn = screen.getByTitle('Menos colunas por linha (cards maiores)');
    fireEvent.click(zoomInBtn);
    expect(screen.getByText('4 col')).toBeInTheDocument();
    expect(localStorage.getItem('visionary:lightbox_columns')).toBe('4');

    // Click zoom indicator directly to cycle
    const indicator = screen.getByText('4 col');
    fireEvent.click(indicator);
    expect(screen.getByText('2 col')).toBeInTheDocument();
    expect(localStorage.getItem('visionary:lightbox_columns')).toBe('2');
  });

  it('supports Shift+Click range selection across pages', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [
        { name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true },
        { name: '02.png', path: 'C:/Manga/Cap_01/02.png', isImage: true },
        { name: '03.png', path: 'C:/Manga/Cap_01/03.png', isImage: true },
        { name: '04.png', path: 'C:/Manga/Cap_01/04.png', isImage: true },
      ]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    const card1 = screen.getByText('01.png').closest('.lightbox-card');
    const card3 = screen.getByText('03.png').closest('.lightbox-card');

    // Click page 1
    fireEvent.click(card1);
    expect(screen.getByText('1 selecionada')).toBeInTheDocument();

    // Shift + Click page 3
    fireEvent.click(card3, { shiftKey: true });
    expect(screen.getByText('3 selecionadas')).toBeInTheDocument();
  });

  it('opens context menu on right click with actions', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [
        { name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true },
        { name: '02.png', path: 'C:/Manga/Cap_01/02.png', isImage: true },
      ]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    const card1 = screen.getByText('01.png').closest('.lightbox-card');

    // Context menu starts closed
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();

    // Right click on card 1
    fireEvent.contextMenu(card1, { clientX: 200, clientY: 300 });

    const menu = screen.getByRole('menu');
    expect(menu).toBeInTheDocument();
    expect(screen.getByText('Copiar Caminho do Arquivo')).toBeInTheDocument();

    // Click Abrir no Estúdio from context menu
    const openBtn = within(menu).getByText('Abrir no Estúdio');
    fireEvent.click(openBtn);

    expect(mockNavigateToStudioPage).toHaveBeenCalledWith({
      folderPath: 'C:/Manga/Cap_01',
      pageName: '01.png',
    });
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('responds to keyboard shortcuts: Ctrl+A, Escape, and Zoom keys', async () => {
    mockListDirectory.mockResolvedValue({
      items: [
        { name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true },
        { name: '02.png', path: 'C:/Manga/Cap_01/02.png', isImage: true },
      ]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    // Press Ctrl+A -> Select all
    fireEvent.keyDown(window, { key: 'a', ctrlKey: true });
    expect(screen.getByText('2 selecionadas')).toBeInTheDocument();

    // Press Escape -> Clear selection
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByText('2 selecionadas')).not.toBeInTheDocument();

    // Press + -> Zoom in (fewer columns)
    expect(screen.getByText('4 col')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: '+' });
    expect(screen.getByText('3 col')).toBeInTheDocument();

    // Press - -> Zoom out (more columns)
    fireEvent.keyDown(window, { key: '-' });
    expect(screen.getByText('4 col')).toBeInTheDocument();
  });

  it('renders pipeline status indicators on card when pageData is present', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [
        { 
          name: '01.png', 
          path: 'C:/Manga/Cap_01/01.png', 
          isImage: true,
          pageData: { layout: true, ocr: true, translation: false }
        }
      ]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    const statusPill = screen.getByTitle(/Status: Layout ✓ • OCR ✓ • Tradução ✗/);
    expect(statusPill).toBeInTheDocument();
  });

  it('opens and closes Quick Look modal when pressing Space bar', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [
        { name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true },
        { name: '02.png', path: 'C:/Manga/Cap_01/02.png', isImage: true }
      ]
    });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    // Press Space bar -> Quick Look opens
    fireEvent.keyDown(window, { code: 'Space' });

    expect(screen.getByRole('dialog', { name: 'Pré-visualização da página' })).toBeInTheDocument();
    expect(screen.getByText('#01 de 2')).toBeInTheDocument();

    // Navigate with Right arrow -> page 2
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(screen.getByText('#02 de 2')).toBeInTheDocument();

    // Press Escape -> Closes
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Pré-visualização da página' })).not.toBeInTheDocument();
  });

  it('opens thematic ConfirmModal on delete and calls delete API on confirmation', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [
        { name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true },
      ]
    });
    mockDeletePage.mockResolvedValueOnce({ success: true });

    render(<Lightbox activeChapterPath="C:/Manga/Cap_01" />);

    await waitFor(() => {
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });

    const card = screen.getByText('01.png').closest('.lightbox-card');
    fireEvent.click(card);

    // Click Excluir
    const delBtn = screen.getByTitle('Excluir páginas selecionadas permanentemente da pasta');
    fireEvent.click(delBtn);

    // Confirm modal opens (replaces window.confirm)
    expect(screen.getByRole('dialog', { name: /Excluir 1 Página/ })).toBeInTheDocument();

    // Confirm deletion
    const confirmBtn = screen.getByRole('button', { name: 'Excluir Definitivamente' });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockDeletePage).toHaveBeenCalledWith('C:/Manga/Cap_01/01.png');
    });
  });

  it('defers listDirectory RPC while tab is inactive and loads immediately on activation', async () => {
    mockListDirectory.mockResolvedValueOnce({
      items: [{ name: '01.png', path: 'C:/Manga/Cap_01/01.png', isImage: true }],
    });

    const { rerender } = render(<Lightbox activeChapterPath="C:/Manga/Cap_01" isActive={false} />);
    expect(mockListDirectory).not.toHaveBeenCalled();

    rerender(<Lightbox activeChapterPath="C:/Manga/Cap_01" isActive={true} />);
    await waitFor(() => {
      expect(mockListDirectory).toHaveBeenCalledWith('C:/Manga/Cap_01');
      expect(screen.getByText('01.png')).toBeInTheDocument();
    });
  });
});
