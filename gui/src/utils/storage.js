/**
 * Centralized, quota-safe and LRU-bounded localStorage utility.
 * Prevents QuotaExceededError and unbounded storage growth in browser/Electron.
 */

export const DEFAULT_MAX_LRU_ENTRIES = 15;

export const LRU_PREFIX_LIMITS = {
  'visionary:cached_pages:': 15,
  'visionary:cached_lib_content:': 15,
  'visionary:last_index:': 20,
  'visionary:copied_': 10,
};

export const TRANSIENT_CACHE_PREFIXES = [
  'visionary:cached_pages:',
  'visionary:cached_lib_content:',
  'visionary:cached_explorer_entries',
  'visionary:cached_module_status',
  'visionary:cached_ollama_models',
  'visionary:cached_ollama_info',
  'visionary:cached_storage_stats',
  'visionary_seamless_viewport_',
  'visionary:copied_',
];

/**
 * Maintains an LRU index for a given prefix in localStorage.
 * Evicts oldest entries exceeding the limit.
 */
function maintainLruIndex(prefix, currentKey, limit) {
  const indexKey = `${prefix}__lru_index`;
  let order = [];
  try {
    const raw = localStorage.getItem(indexKey);
    order = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(order)) order = [];
  } catch {
    order = [];
  }

  order = order.filter((k) => k !== currentKey);
  order.push(currentKey);

  while (order.length > limit) {
    const evicted = order.shift();
    if (evicted) {
      try {
        localStorage.removeItem(evicted);
      } catch {
        // Ignored
      }
    }
  }

  try {
    localStorage.setItem(indexKey, JSON.stringify(order));
  } catch {
    // Ignored
  }
}

/**
 * QuotaExceededError recovery: purges transient caches and retries once.
 */
function handleQuotaExceededRecovery(key, value, lruPrefix) {
  try {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k !== key && TRANSIENT_CACHE_PREFIXES.some((prefix) => k.startsWith(prefix))) {
        keysToRemove.push(k);
      }
    }

    keysToRemove.forEach((k) => {
      try {
        localStorage.removeItem(k);
      } catch {
        // Ignored
      }
    });

    Object.keys(LRU_PREFIX_LIMITS).forEach((prefix) => {
      try {
        localStorage.removeItem(`${prefix}__lru_index`);
      } catch {
        // Ignored
      }
    });

    localStorage.setItem(key, value);
    if (lruPrefix) {
      try {
        localStorage.setItem(`${lruPrefix}__lru_index`, JSON.stringify([key]));
      } catch {
        // Ignored
      }
    }
    return true;
  } catch (retryErr) {
    console.warn(`[Storage] Impossível persistir "${key}" no localStorage (cota excedida):`, retryErr);
    return false;
  }
}

/**
 * Quota-resilient setter with automatic or explicit LRU bounding.
 * 
 * @param {string} key Storage key
 * @param {string} value String value to persist
 * @param {string|null} [lruPrefix] Explicit LRU prefix; if null, attempts auto-detection
 * @param {number|null} [maxEntries] Max entries for the LRU pool
 * @returns {boolean} True if persisted successfully, false otherwise
 */
export function safeSetStorageItem(key, value, lruPrefix = null, maxEntries = null) {
  if (typeof window === 'undefined' || !window.localStorage) return false;

  let resolvedPrefix = lruPrefix;
  let resolvedLimit = maxEntries;

  if (!resolvedPrefix) {
    for (const prefix of Object.keys(LRU_PREFIX_LIMITS)) {
      if (key.startsWith(prefix)) {
        resolvedPrefix = prefix;
        resolvedLimit = resolvedLimit || LRU_PREFIX_LIMITS[prefix];
        break;
      }
    }
  }
  resolvedLimit = resolvedLimit || DEFAULT_MAX_LRU_ENTRIES;

  try {
    if (resolvedPrefix) {
      maintainLruIndex(resolvedPrefix, key, resolvedLimit);
    }
    localStorage.setItem(key, value);
    return true;
  } catch {
    return handleQuotaExceededRecovery(key, value, resolvedPrefix);
  }
}

/**
 * Safe getter that catches potential storage access exceptions.
 */
export function safeGetStorageItem(key, fallback = null) {
  if (typeof window === 'undefined' || !window.localStorage) return fallback;
  try {
    const val = localStorage.getItem(key);
    return val !== null ? val : fallback;
  } catch {
    return fallback;
  }
}

/**
 * Safe JSON parser for localStorage items.
 */
export function safeGetStorageJSON(key, fallback = null) {
  const raw = safeGetStorageItem(key, null);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

/**
 * Safe remover catching exceptions.
 */
export function safeRemoveStorageItem(key) {
  if (typeof window === 'undefined' || !window.localStorage) return;
  try {
    localStorage.removeItem(key);
  } catch {
    // Ignored
  }
}
