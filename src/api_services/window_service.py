import threading
import ctypes

try:
    from ctypes import wintypes
    user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
    if user32:
        user32.IsZoomed.argtypes = [wintypes.HWND]
        user32.IsZoomed.restype = wintypes.BOOL
except Exception:
    user32 = None


class WindowService:
    """
    Window state compatibility service for Visionary Studio.
    In production desktop execution, Electron IPC (electron/ipcHandlers.js) manages
    native BrowserWindow framing directly. This service provides fallback/headless
    compatibility for ApiBridge RPC and standalone test execution.
    """

    def __init__(self, api_bridge=None):
        self.api = api_bridge
        self._window = None
        self._window_title = None
        self._is_maximized = False
        self._lock = threading.Lock()

    def set_window(self, window):
        """Called to associate a window instance if provided."""
        self._window = window
        self._window_title = getattr(window, "title", None)

    def setup_native_frame(self):
        """No-op: native window framing is managed by Electron main process."""
        pass

    def _get_hwnd(self):
        """Find the native window handle (HWND) by title."""
        try:
            if not user32 or not self._window_title:
                return None
            hwnd = user32.FindWindowW(None, self._window_title)
            return hwnd if hwnd and hwnd != 0 else None
        except Exception:
            return None

    def _get_window(self):
        return self._window

    # ── Public API (exposed to JS via ApiBridge) ──
    def minimize(self):
        """Minimize the window."""
        try:
            w = self._get_window()
            if w:
                w.minimize()
                return True
        except Exception as e:
            print(f"[WindowService] minimize error: {e}")
        return False

    def toggle_maximize(self):
        """Toggle between maximized and restored."""
        try:
            with self._lock:
                w = self._get_window()
                if not w:
                    return False
                hwnd = self._get_hwnd()
                is_zoomed = bool(user32.IsZoomed(hwnd)) if (user32 and hwnd) else self._is_maximized
                if is_zoomed:
                    w.restore()
                    self._is_maximized = False
                else:
                    w.maximize()
                    self._is_maximized = True
                return self._is_maximized
        except Exception as e:
            print(f"[WindowService] toggle_maximize error: {e}")
        return False

    def get_is_maximized(self):
        """Return current maximized state for the frontend."""
        hwnd = self._get_hwnd()
        if user32 and hwnd:
            return bool(user32.IsZoomed(hwnd))
        return self._is_maximized

    def start_tear_off_drag(self, percent_x, screen_x, screen_y):
        """No-op in native window mode."""
        hwnd = self._get_hwnd()
        return bool(hwnd)

    def show_system_menu(self, screen_x, screen_y):
        """No-op in native window mode."""
        hwnd = self._get_hwnd()
        return bool(hwnd)

    def close(self):
        """Close / destroy the window."""
        try:
            w = self._get_window()
            if w:
                w.destroy()
                return True
        except Exception as e:
            print(f"[WindowService] close error: {e}")
        return False
