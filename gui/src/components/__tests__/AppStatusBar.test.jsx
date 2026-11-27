import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AppTabs } from '../App/AppTabs';
import * as ToastContextModule from '../../contexts/ToastContext';
import * as WorkspaceStoreModule from '../../stores/useWorkspaceStore';
import { clientApi } from '../../api/bridge';

vi.mock('../../api/bridge', () => ({
  clientApi: {
    openFileInExplorer: vi.fn(),
  },
}));

describe('AppTabs top status actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders CUDA indicator and tabs nav when selectedFolder is null', () => {
    vi.spyOn(ToastContextModule, 'useToast').mockReturnValue({ statusFlash: null });
    vi.spyOn(WorkspaceStoreModule, 'useWorkspaceStore').mockImplementation((selector) => {
      return selector({ jobQueue: [] });
    });

    render(
      <AppTabs 
        activeTab="processamento" 
        handleTabChange={vi.fn()} 
        isSidebarOpen={true} 
        setIsSidebarOpen={vi.fn()} 
        selectedFolder={null} 
      />
    );

    expect(screen.getByText('Estúdio')).toBeInTheDocument();
    expect(screen.getByText('CUDA')).toBeInTheDocument();
  });

  it('renders formatted chapter folder pill in the top bar and opens explorer on click', () => {
    vi.spyOn(ToastContextModule, 'useToast').mockReturnValue({ statusFlash: null });
    vi.spyOn(WorkspaceStoreModule, 'useWorkspaceStore').mockImplementation((selector) => {
      return selector({ jobQueue: [] });
    });

    render(
      <AppTabs 
        activeTab="processamento" 
        handleTabChange={vi.fn()} 
        isSidebarOpen={true} 
        setIsSidebarOpen={vi.fn()} 
        selectedFolder={{ path: 'C:/Mangas/RAW/Chapter 001 The Brazen Boxer', name: 'Chapter 001 The Brazen Boxer' }} 
      />
    );

    const folderBtn = screen.getByText('RAW / Chapter 001 The Brazen Boxer');
    expect(folderBtn).toBeInTheDocument();

    fireEvent.click(folderBtn);
    expect(clientApi.openFileInExplorer).toHaveBeenCalledWith('C:/Mangas/RAW/Chapter 001 The Brazen Boxer');
  });

  it('renders statusFlash message in the top bar when active', () => {
    vi.spyOn(ToastContextModule, 'useToast').mockReturnValue({
      statusFlash: { text: 'Abrindo 002.jpg no Estúdio...', type: 'info' }
    });
    vi.spyOn(WorkspaceStoreModule, 'useWorkspaceStore').mockImplementation((selector) => {
      return selector({ jobQueue: [] });
    });

    render(
      <AppTabs 
        activeTab="lightbox" 
        handleTabChange={vi.fn()} 
        isSidebarOpen={true} 
        setIsSidebarOpen={vi.fn()} 
        selectedFolder={{ path: 'C:/Mangas/RAW/Chapter 001', name: 'Chapter 001' }} 
      />
    );

    expect(screen.getByText('Abrindo 002.jpg no Estúdio...')).toBeInTheDocument();
  });

  it('renders running pipeline job progress and step label in the top bar', () => {
    vi.spyOn(ToastContextModule, 'useToast').mockReturnValue({ statusFlash: null });
    vi.spyOn(WorkspaceStoreModule, 'useWorkspaceStore').mockImplementation((selector) => {
      return selector({
        jobQueue: [
          { id: 'job_1', status: 'running', currentStepLabel: 'OCR 4/18', progress: 45 }
        ]
      });
    });

    render(
      <AppTabs 
        activeTab="processamento" 
        handleTabChange={vi.fn()} 
        isSidebarOpen={true} 
        setIsSidebarOpen={vi.fn()} 
        selectedFolder={{ path: 'C:/Mangas/RAW/Chapter 001', name: 'Chapter 001' }} 
      />
    );

    expect(screen.getByText(/OCR 4\/18/)).toBeInTheDocument();
    expect(screen.getByText(/45%/)).toBeInTheDocument();
    expect(document.querySelector('.tab-status-pill.pill-pipeline')).toBeInTheDocument();
  });
});
