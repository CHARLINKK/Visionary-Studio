import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLibrarySearch } from '../useLibrarySearch';

describe('useLibrarySearch', () => {
  const sampleBalloons = [
    { key: '1-0', balloon: { br: 'Olá Mundo', en: 'Hello World' } },
    { key: '1-1', balloon: { br: 'Cuidado com o dragão', en: 'Beware of the dragon' } },
    { key: '2-0', balloon: { br: 'Vamos em frente', en: 'Let us move forward' } },
    { key: '2-1', balloon: { br: 'O dragão está dormindo', en: 'The dragon is asleep' } },
  ];

  const parsedPages = [
    { pageNumber: 1, balloons: [{ br: 'Olá Mundo' }, { br: 'Cuidado com o dragão' }] },
    { pageNumber: 2, balloons: [{ br: 'Vamos em frente' }, { br: 'O dragão está dormindo' }] },
  ];

  it('initializes with empty search state', () => {
    const { result } = renderHook(() =>
      useLibrarySearch({
        allBalloonsList: sampleBalloons,
        parsedPages,
      })
    );

    expect(result.current.activeSearchQuery).toBe('');
    expect(result.current.searchMatches).toEqual([]);
    expect(result.current.currentMatchIndex).toBe(0);
    expect(result.current.activeMatchKey).toBeNull();
  });

  it('finds matches in Portuguese and English case-insensitively', () => {
    const { result } = renderHook(() =>
      useLibrarySearch({
        allBalloonsList: sampleBalloons,
        parsedPages,
      })
    );

    act(() => {
      result.current.setActiveSearchQuery('DRAGÃO');
    });

    expect(result.current.searchMatches).toEqual(['1-1', '2-1']);
    expect(result.current.currentMatchIndex).toBe(0);
    expect(result.current.activeMatchKey).toBe('1-1');

    act(() => {
      result.current.setActiveSearchQuery('world');
    });

    expect(result.current.searchMatches).toEqual(['1-0']);
    expect(result.current.activeMatchKey).toBe('1-0');
  });

  it('cycles through search matches circularly using next and prev methods', () => {
    const { result } = renderHook(() =>
      useLibrarySearch({
        allBalloonsList: sampleBalloons,
        parsedPages,
      })
    );

    act(() => {
      result.current.setActiveSearchQuery('dragão');
    });

    expect(result.current.currentMatchIndex).toBe(0);
    expect(result.current.activeMatchKey).toBe('1-1');

    // Next match
    act(() => {
      result.current.handleNextSearchMatch();
    });
    expect(result.current.currentMatchIndex).toBe(1);
    expect(result.current.activeMatchKey).toBe('2-1');

    // Circular next wrap-around to 0
    act(() => {
      result.current.handleNextSearchMatch();
    });
    expect(result.current.currentMatchIndex).toBe(0);
    expect(result.current.activeMatchKey).toBe('1-1');

    // Previous match wrap-around to 1
    act(() => {
      result.current.handlePrevSearchMatch();
    });
    expect(result.current.currentMatchIndex).toBe(1);
    expect(result.current.activeMatchKey).toBe('2-1');
  });

  it('clears query and matches cleanly via clearSearch', () => {
    const { result } = renderHook(() =>
      useLibrarySearch({
        allBalloonsList: sampleBalloons,
        parsedPages,
      })
    );

    act(() => {
      result.current.setActiveSearchQuery('dragão');
    });
    expect(result.current.searchMatches.length).toBe(2);

    act(() => {
      result.current.clearSearch();
    });
    expect(result.current.activeSearchQuery).toBe('');
    expect(result.current.searchMatches).toEqual([]);
    expect(result.current.activeMatchKey).toBeNull();
  });
});
