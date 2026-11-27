import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import Library from '../Library';
import { ToastProvider } from '../../contexts/ToastContext';
import { useLibraryStore } from '../../stores/useLibraryStore';

vi.mock('../../api/bridge', () => ({
  clientApi: {
    listLibraryFiles: vi.fn().mockResolvedValue({ success: true, files: [] }),
    readLibraryFile: vi.fn().mockResolvedValue({ success: true, content: '' }),
    get_page_data: vi.fn().mockResolvedValue({ success: true, cards: [] }),
    exportScript: vi.fn().mockResolvedValue({ success: true, content: 'Exported' }),
  },
  getServerUrl: () => 'http://127.0.0.1:5000',
}));

describe('Library Screen Component', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    useLibraryStore.setState({
      activeFile: null,
      fileContent: '',
      libraryFiles: [],
    });
  });

  it('renders empty state when no chapter file is selected', async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <Library isActive={true} />
        </ToastProvider>
      );
    });

    expect(screen.getByText(/Selecione um capítulo na lista para visualizar o roteiro/)).toBeInTheDocument();
    expect(screen.getByText(/Abrir Pasta dos Capítulos/)).toBeInTheDocument();
  });

  it('renders chapter header and formatted text when activeFile is present', async () => {
    const { clientApi } = await import('../../api/bridge');
    const fakeFile = { name: 'capitulo_01.txt', path: 'C:/manga/ch01/capitulo_01.txt' };
    const fakeContent = [
      '==================================================',
      'PAGINA 1: 01.PNG',
      '==================================================',
      '',
      '# [id: 1]',
      '[EN]: Hello world!',
      '[BR]: Olá mundo!',
    ].join('\n');

    clientApi.listLibraryFiles.mockResolvedValue({ success: true, files: [fakeFile] });
    clientApi.readLibraryFile.mockResolvedValue({ success: true, content: fakeContent });

    useLibraryStore.setState({
      activeFile: fakeFile,
      fileContent: fakeContent,
      libraryFiles: [fakeFile],
    });

    await act(async () => {
      render(
        <ToastProvider>
          <Library isActive={true} />
        </ToastProvider>
      );
    });

    expect(screen.getByText(/Olá mundo!/)).toBeInTheDocument();
  });
});
