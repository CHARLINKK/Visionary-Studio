import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  safeSetStorageItem,
  safeGetStorageItem,
  safeGetStorageJSON,
  safeRemoveStorageItem,
  DEFAULT_MAX_LRU_ENTRIES,
  LRU_PREFIX_LIMITS,
} from '../storage';

describe('gui/src/utils/storage.js', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('safely sets, gets and removes basic storage values', () => {
    expect(DEFAULT_MAX_LRU_ENTRIES).toBe(15);
    expect(safeSetStorageItem('test_key', 'test_val')).toBe(true);
    expect(safeGetStorageItem('test_key')).toBe('test_val');
    expect(safeGetStorageItem('non_existent', 'fallback_val')).toBe('fallback_val');

    safeRemoveStorageItem('test_key');
    expect(safeGetStorageItem('test_key')).toBeNull();
  });

  it('safely parses JSON values with fallback on corruption', () => {
    safeSetStorageItem('json_valid', JSON.stringify({ a: 1, b: 'two' }));
    expect(safeGetStorageJSON('json_valid')).toEqual({ a: 1, b: 'two' });

    // Corrupted JSON in localStorage
    localStorage.setItem('json_corrupt', '{invalid_json');
    expect(safeGetStorageJSON('json_corrupt', { default: true })).toEqual({ default: true });
    expect(safeGetStorageJSON('json_missing', null)).toBeNull();
  });

  it('auto-detects known LRU prefixes and bounds cache size', () => {
    const limit = LRU_PREFIX_LIMITS['visionary:cached_pages:'];
    expect(limit).toBeGreaterThan(0);

    // Insert limit + 3 items
    for (let i = 0; i <= limit + 2; i++) {
      safeSetStorageItem(`visionary:cached_pages:chapter_${i}`, `data_${i}`);
    }

    // The first 3 should be evicted
    expect(safeGetStorageItem('visionary:cached_pages:chapter_0')).toBeNull();
    expect(safeGetStorageItem('visionary:cached_pages:chapter_1')).toBeNull();
    expect(safeGetStorageItem('visionary:cached_pages:chapter_2')).toBeNull();

    // The most recent ones must be intact
    expect(safeGetStorageItem(`visionary:cached_pages:chapter_${limit + 2}`)).toBe(`data_${limit + 2}`);
  });

  it('evicts oldest items according to custom maxEntries and updates index', () => {
    const prefix = 'visionary:custom_lru:';
    const max = 3;

    for (let i = 1; i <= 5; i++) {
      safeSetStorageItem(`${prefix}item_${i}`, `v_${i}`, prefix, max);
    }

    expect(safeGetStorageItem(`${prefix}item_1`)).toBeNull();
    expect(safeGetStorageItem(`${prefix}item_2`)).toBeNull();
    expect(safeGetStorageItem(`${prefix}item_3`)).toBe('v_3');
    expect(safeGetStorageItem(`${prefix}item_4`)).toBe('v_4');
    expect(safeGetStorageItem(`${prefix}item_5`)).toBe('v_5');

    const indexRaw = safeGetStorageJSON(`${prefix}__lru_index`);
    expect(indexRaw).toEqual([
      `${prefix}item_3`,
      `${prefix}item_4`,
      `${prefix}item_5`,
    ]);
  });

  it('recovers from QuotaExceededError by clearing transient caches and retrying', () => {
    // Populate some transient caches
    safeSetStorageItem('visionary:cached_pages:old1', 'big_pages_data');
    safeSetStorageItem('visionary:cached_explorer_entries', 'big_explorer_data');
    safeSetStorageItem('visionary:cached_module_status', 'status_data');

    // Simulate QuotaExceededError on first setItem attempt
    vi.spyOn(localStorage, 'setItem').mockImplementationOnce(() => {
      const err = new Error('QuotaExceededError');
      err.name = 'QuotaExceededError';
      throw err;
    });

    const result = safeSetStorageItem('new_target_key', 'saved_payload');
    expect(result).toBe(true);
    expect(safeGetStorageItem('new_target_key')).toBe('saved_payload');

    // Transient caches should have been cleared in recovery
    expect(safeGetStorageItem('visionary:cached_pages:old1')).toBeNull();
    expect(safeGetStorageItem('visionary:cached_explorer_entries')).toBeNull();
  });

  it('returns false and logs warning gracefully if retry also fails', () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      const err = new Error('Persistent QuotaExceededError');
      err.name = 'QuotaExceededError';
      throw err;
    });

    const result = safeSetStorageItem('unpersistable_key', 'impossible_val');
    expect(result).toBe(false);
    expect(consoleWarnSpy).toHaveBeenCalled();
  });
});
