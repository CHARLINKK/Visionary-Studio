"""
Servidor HTTP/WebSocket local (FastAPI) consumido pelo shell Electron e pela interface React.
"""

import os
import sys
import asyncio
from typing import Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from PIL import ImageFile

# Permite leitura de imagens truncadas sem exceção não-tratada
ImageFile.LOAD_TRUNCATED_IMAGES = True

src_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(src_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from src.model_manager import ModelManager, MODELS_REGISTRY
from src.config import Config
from src.utils import session_auth
from src.utils.websocket_manager import (
    ConnectionManager,
    manager,
    broadcast_log_sync,
    set_main_loop,
    get_main_loop,
)
from src.routers.system_router import system_router, perform_graceful_shutdown
from src.routers.models_router import models_router
from src.routers.pipeline_router import pipeline_router, PRESETS
from src.routers.rpc_router import rpc_router, api_bridge, RpcPayload, RpcResponse


def run_batch_pipeline(*args, **kwargs):
    """Carregamento tardio do pipeline em lote para evitar importar numpy/cv2 no boot da API."""
    from src.run_batch import run_batch_pipeline as _impl
    return _impl(*args, **kwargs)

_main_loop = None
model_manager = api_bridge.model_manager
base_project_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        loop = asyncio.get_running_loop()
        set_main_loop(loop)
    except Exception:
        set_main_loop(None)
    try:
        from src.utils.win32_job import setup_job_object_kill_on_close
        setup_job_object_kill_on_close()
    except Exception:
        pass
    try:
        import threading
        def _background_warmup():
            try:
                if hasattr(api_bridge, "_hardware_service"):
                    api_bridge._hardware_service.getHardwareStats()
                if hasattr(api_bridge, "checkModulesStatus"):
                    api_bridge.checkModulesStatus()
            except Exception:
                pass
        if Config.is_test_environment():
            threading.Thread(target=_background_warmup, daemon=True, name="WarmupServiceThread").start()
        else:
            # Atrasa warmup pesado para não disputar disco/GIL com getSettings e a primeira página do Estúdio
            warmup_timer = threading.Timer(1.2, _background_warmup)
            warmup_timer.daemon = True
            warmup_timer.name = "WarmupServiceTimer"
            warmup_timer.start()
    except Exception:
        pass
    yield
    try:
        perform_graceful_shutdown(reason="fastapi_lifespan_exit", exit_process=False, reset_after=True)
    except Exception:
        try:
            ModelManager.terminate_ollama()
        except Exception:
            pass


app = FastAPI(title="Visionary Studio API", version="1.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost",
    "http://127.0.0.1",
    "app://.",
    "file://",
    "null",
]

# Autenticação por token de sessão (HTTP + WebSocket)
app.add_middleware(session_auth.SessionTokenMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Inclusão de APIRouters Especializados ──
app.include_router(system_router)
app.include_router(models_router)
app.include_router(pipeline_router)
app.include_router(rpc_router)


# ── WebSocket Endpoint para Logs em Tempo Real ──
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    set_main_loop(asyncio.get_running_loop())
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        await manager.disconnect(websocket)


# ── Servir Arquivos Estáticos da UI ──
gui_dist_dir = os.path.join(base_project_dir, "gui", "dist")
gui_dir = gui_dist_dir if os.path.exists(gui_dist_dir) else os.path.join(base_project_dir, "gui")
if os.path.isdir(gui_dir):
    app.mount("/static", StaticFiles(directory=gui_dir), name="static")
assets_dir = os.path.join(gui_dir, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
def read_root(tab: Optional[str] = None, view: Optional[str] = None):
    """Entrega o index.html da interface do usuário."""
    index_file = os.path.join(gui_dir, "index.html")
    if os.path.exists(index_file):
        if tab or view:
            safe_view = "".join(c for c in view if c.isalnum() or c in ("-", "_")) if view else ""
            safe_tab = "".join(c for c in tab if c.isalnum() or c in ("-", "_"))
            from fastapi.responses import HTMLResponse
            with open(index_file, "r", encoding="utf-8") as f:
                content = f.read()
            inject = f"""<script>
window.addEventListener('DOMContentLoaded', () => {{
    if ("{safe_view}") {{
        try {{ localStorage.setItem("visionary:library_view_mode", "{safe_view}"); }} catch (e) {{}}
    }}
    let attempts = 0;
    const activate = () => {{
        const btn = document.querySelector('.tab-btn[data-tab="{safe_tab}"]');
        if (btn) {{
            btn.click();
        }} else if (attempts++ < 30) {{
            setTimeout(activate, 100);
        }}
    }};
    setTimeout(activate, 150);
}});
</script></body>"""
            return HTMLResponse(content.replace("</body>", inject))
        return FileResponse(index_file)
    return JSONResponse({"message": "Visionary Studio API running. GUI index.html not found in gui/ folder."})


def start_watchdog(parent_pid: int):
    """Monitora o processo pai (Electron) e encerra o backend se o pai fechar."""
    if not parent_pid or not isinstance(parent_pid, int) or parent_pid <= 0:
        return

    def _cleanup_on_parent_exit(reason: str):
        try:
            perform_graceful_shutdown(
                reason=reason,
                exit_process=False,
                reset_after=Config.is_test_environment(),
            )
        except Exception:
            try:
                ModelManager.terminate_ollama()
            except Exception:
                pass
            try:
                torch_mod = sys.modules.get("torch")
                if torch_mod is not None and torch_mod.cuda.is_available():
                    torch_mod.cuda.empty_cache()
            except Exception:
                pass
        os._exit(0)

    def _run():
        if sys.platform == 'win32':
            try:
                import ctypes
                SYNCHRONIZE = 0x00100000
                INFINITE = 0xFFFFFFFF
                handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, parent_pid)
                if handle:
                    try:
                        ctypes.windll.kernel32.WaitForSingleObject(handle, INFINITE)
                    finally:
                        ctypes.windll.kernel32.CloseHandle(handle)
                    print(f"[Watchdog] Processo pai PID {parent_pid} encerrou instantaneamente. Liberando recursos...")
                    _cleanup_on_parent_exit("parent_pid_exit_win32")
                    return
            except Exception as e:
                print(f"[Watchdog] Aviso: fallback para psutil ({e})")

        import time
        import psutil
        while True:
            time.sleep(1.5)
            if not psutil.pid_exists(parent_pid):
                print(f"[Watchdog] Processo pai PID {parent_pid} encerrou. Finalizando servidor...")
                _cleanup_on_parent_exit("parent_pid_exit_psutil")
                return

    import threading
    t = threading.Thread(target=_run, daemon=True, name="ParentWatchdog")
    t.start()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Visionary Studio Backend Server")
    parser.add_argument("--port", type=int, default=Config.get("flask_port", 5000), help="Port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address to bind")
    parser.add_argument("--parent-pid", type=int, default=None, help="Parent Process ID for Watchdog cleanup")
    args = parser.parse_args()

    session_auth.configure_from_environment()
    _auth_mode = session_auth.auth_mode()
    if _auth_mode == session_auth.MODE_OPEN:
        print("[Auth] ATENÇÃO: VISIONARY_DEV_NO_AUTH=1 - API sem autenticação (somente desenvolvimento).")
    elif _auth_mode == session_auth.MODE_LOCKED:
        print(
            "[Auth] ATENÇÃO: nenhum token de sessão válido recebido em VISIONARY_AUTH_TOKEN. "
            "Todas as rotas protegidas responderão 503."
        )
    else:
        print("[Auth] Token de sessão ativo.")

    if args.parent_pid:
        start_watchdog(args.parent_pid)

    print(f"\n [ON] Visionary Studio Backend API Server Started on http://{args.host}:{args.port}\n")
    try:
        access_log = os.environ.get("VISIONARY_ACCESS_LOG") == "1"
        uvicorn.run(app, host=args.host, port=args.port, reload=False, access_log=access_log)
    except OSError as e:
        print(f"\n[ERRO CRÍTICO] Falha ao vincular porta {args.port} em {args.host}: {e}\n")
        sys.exit(1)
