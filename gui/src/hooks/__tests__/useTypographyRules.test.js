import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTypographyRules } from '../useTypographyRules';
import { useLibraryStore } from '../../stores/useLibraryStore';

describe('useTypographyRules', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    useLibraryStore.getState().initializeTypographyRules();
  });

  it('initializes with default typography rules when localStorage is empty', () => {
    const { result } = renderHook(() => useTypographyRules());

    expect(result.current.typographyRules).toEqual({
      travessao: true,
      reticencias: true,
      caixaAlta: false,
    });
  });

  it('loads existing typography rules from localStorage', () => {
    localStorage.setItem(
      'visionary:typography_rules',
      JSON.stringify({ travessao: false, reticencias: true, caixaAlta: true })
    );

    const { result } = renderHook(() => useTypographyRules());

    expect(result.current.typographyRules).toEqual({
      travessao: false,
      reticencias: true,
      caixaAlta: true,
    });
  });

  it('updates rules and persists them to localStorage', () => {
    const { result } = renderHook(() => useTypographyRules());

    act(() => {
      result.current.updateTypographyRules({ caixaAlta: true, travessao: false });
    });

    expect(result.current.typographyRules.caixaAlta).toBe(true);
    expect(result.current.typographyRules.travessao).toBe(false);

    const stored = JSON.parse(localStorage.getItem('visionary:typography_rules') || '{}');
    expect(stored.caixaAlta).toBe(true);
    expect(stored.travessao).toBe(false);
  });

  it('applies ellipsis and em-dash transformations correctly', () => {
    const { result } = renderHook(() => useTypographyRules());

    const formatted = result.current.applyTypographyRules('- Olá... Você viu isso?');
    expect(formatted).toBe('— Olá… Você viu isso?');
    expect(result.current.applyTypographyRules('-- Cuidado...')).toBe('— Cuidado…');
    expect(result.current.applyTypographyRules('--- Espere!')).toBe('— Espere!');
  });

  it('converts text to uppercase when caixaAlta is enabled', () => {
    const { result } = renderHook(() => useTypographyRules());

    act(() => {
      result.current.updateTypographyRules({ caixaAlta: true });
    });

    const formatted = result.current.applyTypographyRules('- socorro... corram!');
    expect(formatted).toBe('— SOCORRO… CORRAM!');
  });

  it('safely handles empty or pending placeholder text without modifying it', () => {
    const { result } = renderHook(() => useTypographyRules());

    expect(result.current.applyTypographyRules('')).toBe('');
    expect(result.current.applyTypographyRules(null)).toBe(null);
    expect(result.current.applyTypographyRules('[PENDENTE]')).toBe('[PENDENTE]');
  });
});
