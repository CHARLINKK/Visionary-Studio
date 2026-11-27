import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLibraryClipboard } from '../useLibraryClipboard';
import { useLibraryStore } from '../../stores/useLibraryStore';

// Mock audio and clipboard utilities
vi.mock('../../utils/clipboard', () => ({
  copyTextToClipboard: vi.fn().mockResolvedValue(true),
}));

vi.mock('../../utils/sound', () => ({
  playCopySound: vi.fn(),
}));

import { copyTextToClipboard } from '../../utils/clipboard';
import { playCopySound } from '../../utils/sound';

describe('useLibraryClipboard', () => {
  beforeEach(() => {
    localStorage.clear();
    useLibraryStore.setState({
      copiedBlocks: {},
      activeCopiedId: null,
    });
    vi.clearAllMocks();
  });

  const activeFile = { path: 'Capitulo-01.txt' };

  it('copies Portuguese balloon text, marks as copied, and triggers sound feedback', async () => {
    const addToast = vi.fn();
    const applyTypographyRules = vi.fn((text) => `— ${text}`);

    const { result } = renderHook(() =>
      useLibraryClipboard({
        activeFile,
        applyTypographyRules,
        addToast,
      })
    );

    await act(async () => {
      await result.current.copyBalloon('1-0', { br: 'Olá Mundo', en: 'Hello World' });
    });

    expect(applyTypographyRules).toHaveBeenCalledWith('Olá Mundo');
    expect(copyTextToClipboard).toHaveBeenCalledWith('— Olá Mundo');
    expect(useLibraryStore.getState().copiedBlocks['1-0']).toBe(true);
    expect(result.current.lastCopiedId).toBe('1-0');
    expect(playCopySound).toHaveBeenCalled();
    expect(addToast).toHaveBeenCalledWith('Balão copiado para o Photoshop!', 'success');
  });

  it('falls back to English text when Portuguese translation is still pending', async () => {
    const addToast = vi.fn();
    const { result } = renderHook(() =>
      useLibraryClipboard({
        activeFile,
        applyTypographyRules: (t) => t,
        addToast,
      })
    );

    await act(async () => {
      await result.current.copyBalloon('1-1', { br: '[PENDENTE]', en: 'Warning danger' });
    });

    expect(copyTextToClipboard).toHaveBeenCalledWith('Warning danger');
    expect(addToast).toHaveBeenCalledWith(
      'Texto original (EN) copiado para o Photoshop!',
      'info'
    );
  });

  it('shows warning and avoids clipboard operation when text is completely empty', async () => {
    const addToast = vi.fn();
    const { result } = renderHook(() =>
      useLibraryClipboard({
        activeFile,
        addToast,
      })
    );

    await act(async () => {
      await result.current.copyBalloon('1-2', { br: '', en: '' });
    });

    expect(copyTextToClipboard).not.toHaveBeenCalled();
    expect(addToast).toHaveBeenCalledWith(
      'Balão sem texto disponível para copiar.',
      'warning'
    );
  });

  it('undoes copied state for a specific balloon in undoCopyBalloon', async () => {
    const addToast = vi.fn();
    useLibraryStore.setState({ copiedBlocks: { '1-0': true, '1-1': true } });

    const { result } = renderHook(() =>
      useLibraryClipboard({
        activeFile,
        addToast,
      })
    );

    act(() => {
      result.current.undoCopyBalloon('1-0');
    });

    expect(useLibraryStore.getState().copiedBlocks['1-0']).toBeUndefined();
    expect(useLibraryStore.getState().copiedBlocks['1-1']).toBe(true);
    expect(addToast).toHaveBeenCalledWith('Status de colado desfeito!', 'info');
  });

  it('copies all valid texts of an entire page at once in copyFullPage', async () => {
    const addToast = vi.fn();
    const { result } = renderHook(() =>
      useLibraryClipboard({
        activeFile,
        applyTypographyRules: (t) => t,
        addToast,
      })
    );

    const page = {
      pageNumber: 5,
      balloons: [
        { br: 'Primeira fala' },
        { br: '[PENDENTE]', en: 'Second dialogue' },
        { br: '' }, // empty
      ],
    };

    await act(async () => {
      await result.current.copyFullPage(page);
    });

    expect(copyTextToClipboard).toHaveBeenCalledWith('Primeira fala\n\nSecond dialogue');
    expect(useLibraryStore.getState().copiedBlocks['5-0']).toBe(true);
    expect(useLibraryStore.getState().copiedBlocks['5-1']).toBe(true);
    expect(addToast).toHaveBeenCalledWith(
      expect.stringContaining('Página 5 copiada (2 balões)!'),
      'success'
    );
  });

  it('handles 2-step confirmation for resetProgress safely without blocking window.confirm', () => {
    const addToast = vi.fn();
    useLibraryStore.setState({ copiedBlocks: { '1-0': true, '1-1': true } });
    localStorage.setItem(`visionary:copied_${activeFile.path}`, JSON.stringify({ '1-0': true }));

    const { result } = renderHook(() =>
      useLibraryClipboard({
        activeFile,
        addToast,
      })
    );

    // First click: prompts confirmation
    act(() => {
      result.current.resetProgress();
    });
    expect(useLibraryStore.getState().copiedBlocks['1-0']).toBe(true);
    expect(addToast).toHaveBeenCalledWith(
      'Clique novamente para confirmar a redefinição do progresso.',
      'warning'
    );

    // Second click: resets progress
    act(() => {
      result.current.resetProgress();
    });
    expect(useLibraryStore.getState().copiedBlocks).toEqual({});
    expect(localStorage.getItem(`visionary:copied_${activeFile.path}`)).toBeNull();
    expect(addToast).toHaveBeenCalledWith(
      'Progresso redefinido com sucesso!',
      'info'
    );
  });

  it('allows forced immediate reset when force=true', () => {
    const addToast = vi.fn();
    useLibraryStore.setState({ copiedBlocks: { '2-0': true } });

    const { result } = renderHook(() =>
      useLibraryClipboard({
        activeFile,
        addToast,
      })
    );

    act(() => {
      result.current.resetProgress(true);
    });
    expect(useLibraryStore.getState().copiedBlocks).toEqual({});
    expect(addToast).toHaveBeenCalledWith(
      'Progresso redefinido com sucesso!',
      'info'
    );
  });
});
