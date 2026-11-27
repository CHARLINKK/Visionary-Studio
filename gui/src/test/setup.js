import '@testing-library/jest-dom';
import { beforeEach, vi } from 'vitest';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { useLibraryStore } from '../stores/useLibraryStore';
import { useLibraryViewerStore } from '../stores/useLibraryViewerStore';

// ── In-Memory LocalStorage Mock ──
const createLocalStorageMock = () => {
  let store = {};
  return {
    getItem: vi.fn((key) => (key in store ? store[key] : null)),
    setItem: vi.fn((key, value) => {
      store[key] = String(value);
    }),
    removeItem: vi.fn((key) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((i) => Object.keys(store)[i] || null),
  };
};

const mockLocalStorage = createLocalStorageMock();
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
});

// ── Electron & Web API Mocks ──
window.electronAPI = {
  minimize: vi.fn(),
  toggleMaximize: vi.fn(),
  isMaximized: vi.fn(() => false),
  close: vi.fn(),
  showNotification: vi.fn(async () => ({ success: true })),
  focusWindow: vi.fn(),
};

window.pywebview = {
  api: {
    showSystemNotification: vi.fn(async () => true),
  },
};

// ── DOM Browser Feature Mocks ──
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverMock;

window.matchMedia = vi.fn().mockImplementation((query) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}));

// Snapshot original initial states of Zustand stores
const initialWorkspaceState = useWorkspaceStore.getState();
const initialLibraryState = useLibraryStore.getState();
const initialViewerState = useLibraryViewerStore.getState();

beforeEach(() => {
  mockLocalStorage.clear();
  vi.clearAllMocks();

  // Reset Zustand singleton stores atomically before every test
  useWorkspaceStore.setState(initialWorkspaceState, true);
  useLibraryStore.setState(initialLibraryState, true);
  useLibraryViewerStore.setState(initialViewerState, true);
});
