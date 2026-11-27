import sys
import threading

# Requisições de rotina/heartbeat e tags de telemetria interna que não devem poluir o dev log
IGNORED_LOG_PATTERNS = (
    "POST /api/rpc/getDownloadsProgress",
    "POST /api/rpc/getDevLogs",
    "POST /api/rpc/getDevStats",
    "POST /api/rpc/getHardwareStats",
    "POST /api/rpc/getStorageStats",
    "POST /api/rpc/checkModulesStatus",
    "POST /api/rpc/getModelsStatus",
    "POST /api/rpc/getPipelineStatus",
    "POST /api/rpc/getVramRealtime",
    "POST /api/rpc/getVramStatus",
    "GET /api/health",
    "OPTIONS /api/",
    "WebSocket /ws/logs",
    "connection open",
    "[VRAM_REALTIME:",
    "[VRAM_PROGRESS:",
    "[PROGRESS:",
    "[REPLACE_LAST_LOG_PREFIX:",
)


class StreamInterceptor:
    def __init__(self, original_stream, buffer_list, lock):
        self.original_stream = original_stream
        self.buffer_list = buffer_list
        self.lock = lock
        self._local = threading.local()

    def write(self, data):
        try:
            self.original_stream.write(data)
        except Exception:
            pass
        if data and str(data).strip():
            text = str(data).strip()
            # Ignora ruído repetitivo de polling/heartbeat
            if any(pat in text for pat in IGNORED_LOG_PATTERNS):
                return
            with self.lock:
                # Mantém o histórico sob limite para evitar estouro de memória
                if len(self.buffer_list) > 1500:
                    del self.buffer_list[:500]
                self.buffer_list.append(text)
            if not getattr(self._local, "publishing", False):
                self._local.publishing = True
                try:
                    from src.utils.event_bus import event_bus
                    event_bus.publish("dev:log", {"stream": "app", "line": text})
                except Exception:
                    pass
                finally:
                    self._local.publishing = False

    def flush(self):
        try:
            self.original_stream.flush()
        except Exception:
            pass

    def isatty(self):
        return getattr(self.original_stream, "isatty", lambda: False)()

    def fileno(self):
        return getattr(self.original_stream, "fileno", lambda: 1)()

    def __getattr__(self, name):
        return getattr(self.original_stream, name)
