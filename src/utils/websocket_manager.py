"""
Gerenciador global de WebSockets e transmissão sincronizada de telemetria em tempo real.
"""

import sys
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import WebSocket


class ConnectionManager:
    """
    Controlador de conexões WebSocket ativas com suporte a thread-safety e locks assíncronos.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock: asyncio.Lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        async with self._lock:
            connections = list(self.active_connections)
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                await self.disconnect(connection)


manager = ConnectionManager()
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_loop(loop: Optional[asyncio.AbstractEventLoop]):
    global _main_loop
    _main_loop = loop
    server_mod = sys.modules.get("src.server")
    if server_mod is not None:
        setattr(server_mod, "_main_loop", loop)


def get_main_loop() -> Optional[asyncio.AbstractEventLoop]:
    server_mod = sys.modules.get("src.server")
    if server_mod is not None and hasattr(server_mod, "_main_loop"):
        return getattr(server_mod, "_main_loop")
    return _main_loop


def broadcast_log_sync(event_type: str, message: str = "", progress: float = -1.0, extra: Optional[Dict[str, Any]] = None):
    """
    Despacha uma mensagem broadcast para todos os clientes conectados ao WebSocket a partir
    de qualquer thread síncrona ou assíncrona do Python.
    """
    payload = {"type": event_type, "message": message, "progress": progress}
    if extra:
        payload.update(extra)
    try:
        loop = get_main_loop()
        if loop is None or not loop.is_running():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast(payload), loop)
    except Exception:
        pass
