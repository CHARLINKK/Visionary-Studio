import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ExplorerSidebar } from '../App/ExplorerSidebar';

describe('ExplorerSidebar component', () => {
  const defaultProps = {
    activeTab: 'processamento',
    isSidebarOpen: true,
    setIsSidebarOpen: vi.fn(),
    sidebarWidth: 260,
    isResizing: false,
    startResize: vi.fn(),
    handleSecretClick: vi.fn(),
    handleGoUp: vi.fn(),
    isAtRoot: false,
    currentPath: 'C:\\Mangas\\One Piece',
    refreshCurrentDirectory: vi.fn(),
    searchQuery: '',
    setSearchQuery: vi.fn(),
    filteredEntries: [],
    handleEntryClick: vi.fn(),
    selectedFolder: null,
    showStatusDots: true,
    showPagePills: true,
  };

  it('renders chapter folders and organizer folders', () => {
    const entries = [
      { name: '.. (Voltar para Mangas)', path: 'C:\\Mangas', isBack: true, isDir: true },
      { name: 'Capítulo 1', path: 'C:\\Mangas\\One Piece\\Capítulo 1', isDir: true, isChapter: true, hasImages: true, imgCount: 20, status: 'green' },
      { name: 'Capítulo 2', path: 'C:\\Mangas\\One Piece\\Capítulo 2', isDir: true, isChapter: true, hasImages: true, imgCount: 18, status: 'yellow' },
      { name: 'Extras', path: 'C:\\Mangas\\One Piece\\Extras', isDir: true, isChapter: false, hasImages: false, imgCount: 0, status: 'blue' }
    ];

    render(<ExplorerSidebar {...defaultProps} filteredEntries={entries} />);

    expect(screen.getByText('.. (Voltar para Mangas)')).toBeInTheDocument();
    expect(screen.getByText('Capítulo 1')).toBeInTheDocument();
    expect(screen.getByText('Capítulo 2')).toBeInTheDocument();
    expect(screen.getByText('Extras')).toBeInTheDocument();
    expect(screen.getByText('20 págs')).toBeInTheDocument();
    expect(screen.getByText('18 págs')).toBeInTheDocument();
  });

  it('strictly hides auxiliary files such as _glossary_global.txt and global_dictionary.json', () => {
    const entries = [
      { name: 'Capítulo 1', path: 'C:\\Mangas\\One Piece\\Capítulo 1', isDir: true, isChapter: true, hasImages: true, imgCount: 20 },
      { name: '_glossary_global.txt', path: 'C:\\Mangas\\One Piece\\_glossary_global.txt', isDir: false, isImage: false },
      { name: 'global_dictionary.json', path: 'C:\\Mangas\\One Piece\\global_dictionary.json', isDir: false, isImage: false },
      { name: '01.png', path: 'C:\\Mangas\\One Piece\\01.png', isDir: false, isImage: true },
      { name: 'README.txt', path: 'C:\\Mangas\\One Piece\\README.txt', isDir: false, isImage: false },
    ];

    render(<ExplorerSidebar {...defaultProps} filteredEntries={entries} />);

    expect(screen.getByText('Capítulo 1')).toBeInTheDocument();
    expect(screen.queryByText('_glossary_global.txt')).not.toBeInTheDocument();
    expect(screen.queryByText('global_dictionary.json')).not.toBeInTheDocument();
    expect(screen.queryByText('01.png')).not.toBeInTheDocument();
    expect(screen.queryByText('README.txt')).not.toBeInTheDocument();
  });

  it('triggers handleEntryClick when a directory is clicked', () => {
    const handleEntryClick = vi.fn();
    const entries = [
      { name: 'Capítulo 1', path: 'C:\\Mangas\\One Piece\\Capítulo 1', isDir: true, isChapter: true, hasImages: true, imgCount: 15 }
    ];

    render(<ExplorerSidebar {...defaultProps} filteredEntries={entries} handleEntryClick={handleEntryClick} />);

    fireEvent.click(screen.getByText('Capítulo 1'));
    expect(handleEntryClick).toHaveBeenCalledWith(entries[0]);
  });
});
