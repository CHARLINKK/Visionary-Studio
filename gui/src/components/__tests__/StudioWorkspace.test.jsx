import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import StudioWorkspace from '../StudioWorkspace';
import { ToastProvider } from '../../contexts/ToastContext';

// Mock dependencies
vi.mock('../SeamlessEditor', () => ({
  default: ({ pageIndex, totalPages }) => (
    <div data-testid="seamless-editor">
      Editor Page {pageIndex + 1} of {totalPages}
    </div>
  ),
}));

vi.mock('../StudioBatchSidebar', () => ({
  default: () => <div data-testid="studio-batch-sidebar">Batch Sidebar</div>,
}));

vi.mock('../../api/bridge', () => ({
  clientApi: {
    listDirectory: vi.fn(),
    getSettings: vi.fn().mockResolvedValue({
      pipeline_steps: { layout: true, ocr: true, translate: true },
      translation_tone: 'neutral',
    }),
    saveSettings: vi.fn().mockResolvedValue({ success: true }),
  },
  getServerUrl: () => 'http://127.0.0.1:5000',
}));

describe('StudioWorkspace Component', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders onboarding welcome view when no folderPath is selected', async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <StudioWorkspace folderPath={null} folderName={null} isActive={true} />
        </ToastProvider>
      );
    });

    expect(screen.getByText('Bem-vindo ao Visionary Studio')).toBeInTheDocument();
    expect(screen.getByText('Escolha a pasta RAW na barra lateral')).toBeInTheDocument();
    expect(screen.getByTestId('studio-batch-sidebar')).toBeInTheDocument();
  });

  it('renders empty chapter notice when folder contains no image files', async () => {
    const { clientApi } = await import('../../api/bridge');
    clientApi.listDirectory.mockResolvedValue({
      success: true,
      items: [{ name: 'notes.txt', isImage: false, isDir: false }],
    });

    await act(async () => {
      render(
        <ToastProvider>
          <StudioWorkspace folderPath="C:/manga/ch01" folderName="ch01" isActive={true} />
        </ToastProvider>
      );
    });

    expect(screen.getByText('Nenhuma imagem encontrada neste capítulo.')).toBeInTheDocument();
  });

  it('renders SeamlessEditor when valid images are found in the chapter', async () => {
    const { clientApi } = await import('../../api/bridge');
    clientApi.listDirectory.mockResolvedValue({
      success: true,
      items: [
        { name: '01.png', path: 'C:/manga/ch01/01.png', isImage: true },
        { name: '02.png', path: 'C:/manga/ch01/02.png', isImage: true },
      ],
    });

    await act(async () => {
      render(
        <ToastProvider>
          <StudioWorkspace folderPath="C:/manga/ch01" folderName="ch01" isActive={true} />
        </ToastProvider>
      );
    });

    expect(screen.getByTestId('seamless-editor')).toBeInTheDocument();
    expect(screen.getByText(/Editor Page 1 of 2/)).toBeInTheDocument();
  });
});
