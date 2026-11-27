import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LibraryHeader from '../Library/LibraryHeader';

describe('LibraryHeader component', () => {
  const defaultProps = {
    activeFile: { name: 'Capitulo_01.txt', path: 'C:/Manga/Capitulo_01.txt' },
    parsedPages: [{ pageNumber: 1, balloons: [{ id: 1 }] }, { pageNumber: 2, balloons: [] }],
    totalBalloons: 10,
    copiedBalloons: 4,
    progressPercentage: 40,
    activePageIndex: 0,
    activePageData: { pageNumber: 1, balloons: [{ id: 1 }], pageName: '01.png' },
    sidebarCollapsed: false,
    toggleSidebar: vi.fn(),
    resetProgress: vi.fn(),
    jumpToNextPending: vi.fn(),
    openInExplorer: vi.fn(),
    isTypographyRulesOpen: false,
    setIsTypographyRulesOpen: vi.fn(),
    typographyRules: { travessao: true, reticencias: false, caixaAlta: false },
    updateTypographyRules: vi.fn(),
    isExportMenuOpen: false,
    setIsExportMenuOpen: vi.fn(),
    exportScript: vi.fn(),
    syncChapterTxt: vi.fn(),
    isSyncing: false,
    collapsedPages: {},
    setCollapsedPages: vi.fn(),
    copyRawContent: vi.fn(),
    isRawCopied: false,
    viewMode: 'script',
    changeViewMode: vi.fn(),
    goToPage: vi.fn(),
    autoResumePending: false,
    toggleAutoResume: vi.fn(),
    searchInputRef: { current: null },
    activeSearchQuery: '',
    setActiveSearchQuery: vi.fn(),
    searchMatches: [],
    currentMatchIndex: 0,
    handlePrevSearchMatch: vi.fn(),
    handleNextSearchMatch: vi.fn(),
    clearSearch: vi.fn(),
    copyFullPage: vi.fn(),
    openInStudio: vi.fn(),
  };

  it('renders chapter title, page count and balloon progress correctly', () => {
    render(<LibraryHeader {...defaultProps} />);

    expect(screen.getByText('Capitulo_01')).toBeInTheDocument();
    expect(screen.getByText('2 Págs')).toBeInTheDocument();
    expect(screen.getByText('4/10 (40%)')).toBeInTheDocument();
  });

  it('triggers jumpToNextPending when clicking on the pending jump button', () => {
    const jumpToNextPending = vi.fn();
    render(<LibraryHeader {...defaultProps} viewMode="split" jumpToNextPending={jumpToNextPending} />);

    fireEvent.click(screen.getByText('Próxima Pendente'));
    expect(jumpToNextPending).toHaveBeenCalledTimes(1);
  });

  it('triggers changeViewMode when clicking on view mode tabs', () => {
    const changeViewMode = vi.fn();
    render(<LibraryHeader {...defaultProps} changeViewMode={changeViewMode} />);

    fireEvent.click(screen.getByText('Lado a Lado'));
    expect(changeViewMode).toHaveBeenCalledWith('split');

    fireEvent.click(screen.getByText('Texto Puro'));
    expect(changeViewMode).toHaveBeenCalledWith('raw');
  });

  it('triggers copyRawContent when clicking the main copy button', () => {
    const copyRawContent = vi.fn();
    render(<LibraryHeader {...defaultProps} copyRawContent={copyRawContent} />);

    fireEvent.click(screen.getByText('Copiar Tudo'));
    expect(copyRawContent).toHaveBeenCalledTimes(1);
  });

  it('triggers syncChapterTxt when clicking the Sincronizar .TXT button', () => {
    const syncChapterTxt = vi.fn();
    render(<LibraryHeader {...defaultProps} syncChapterTxt={syncChapterTxt} />);

    fireEvent.click(screen.getByText('Sincronizar .TXT'));
    expect(syncChapterTxt).toHaveBeenCalledTimes(1);
  });

  it('displays typography dropdown when isTypographyRulesOpen is true and allows toggling rule', () => {
    const updateTypographyRules = vi.fn();
    render(
      <LibraryHeader
        {...defaultProps}
        isTypographyRulesOpen={true}
        updateTypographyRules={updateTypographyRules}
      />
    );

    expect(screen.getByText('Formatação ao Copiar')).toBeInTheDocument();
    const reticenciasCheckbox = screen.getByText('Reticências tipográficas (…)').previousSibling;
    fireEvent.click(reticenciasCheckbox);
    expect(updateTypographyRules).toHaveBeenCalledWith({ reticencias: true });
  });

  it('navigates pages forward and backward', () => {
    const goToPage = vi.fn();
    render(<LibraryHeader {...defaultProps} viewMode="split" activePageIndex={0} goToPage={goToPage} />);

    // Pág. 01 / 02 label should be present
    expect(screen.getByText('Pág. 01 / 02')).toBeInTheDocument();
  });

  it('renders cleanly when using controller prop decoupling', () => {
    const mockController = {
      ...defaultProps,
      activeFile: { name: 'Capitulo_Decoupled.txt' },
      parsedPages: [{ pageNumber: 1, balloons: [] }],
    };

    render(<LibraryHeader controller={mockController} />);

    expect(screen.getByText('Capitulo_Decoupled')).toBeInTheDocument();
    expect(screen.getByText('1 Págs')).toBeInTheDocument();
  });
});
