import threading
import json
from typing import Callable, Any, Dict, List

# ===============================================================================
#  Visionary Studio - Decoupled Event Bus (Pub/Sub)
# ===============================================================================

class EventBus:
    """
    Barramento de eventos thread-safe para comunicação desacoplada entre
    serviços de backend, pipelines de IA e interface gráfica (Electron / WebSocket).
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance._subscribers: Dict[str, List[Callable[[Any], None]]] = {}
                cls._instance._sub_lock = threading.RLock()
            return cls._instance

    @classmethod
    def get_instance(cls) -> "EventBus":
        return cls()

    def subscribe(self, event_name: str, callback: Callable[[Any], None]) -> None:
        """Registra um ouvinte para um evento específico."""
        with self._sub_lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[[Any], None]) -> None:
        """Remove um ouvinte de um evento."""
        with self._sub_lock:
            if event_name in self._subscribers and callback in self._subscribers[event_name]:
                self._subscribers[event_name].remove(callback)

    def publish(self, event_name: str, payload: Any = None) -> None:
        """
        Dispara um evento para todos os ouvintes registrados e emite o evento
        correspondente via WebSocket para os clientes conectados.
        """
        with self._sub_lock:
            callbacks = list(self._subscribers.get(event_name, []))

        for cb in callbacks:
            try:
                cb(payload)
            except Exception as e:
                import traceback
                print(f"[EventBus] Erro ao executar callback para '{event_name}': {e}")
                traceback.print_exc()

        # Emite evento para a interface gráfica via WebSocket em tempo real
        self._emit_to_clients(event_name, payload)

    def _emit_to_clients(self, event_name: str, payload: Any = None) -> None:
        try:
            from src.server import broadcast_log_sync
            broadcast_log_sync("custom_event", "", extra={"event_name": event_name, "payload": payload})
        except Exception:
            pass


# Instância global padrão para importação direta
event_bus = EventBus.get_instance()
