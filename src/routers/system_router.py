"""
Router de Sistema: Health check, Shutdown, entrega segura de imagens locais e raiz da UI.
"""

import os
import sys
import time
import threading
from collections import OrderedDict
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response
from src.model_manager import ModelManager
from src.utils.path_sandbox import INVALID_PATH, ImageReadDenied, authorize_image_read

system_router = APIRouter()

_SERVER_START_TIME = time.time()
_shutdown_lock = threading.Lock()
_is_shutting_down = False
_thumb_cache_lock = threading.Lock()
_THUMB_CACHE: "OrderedDict[tuple, tuple[bytes, str]]" = OrderedDict()
_THUMB_CACHE_MAX_ITEMS = 128


def reset_shutdown_state() -> None:
    """Restaura a flag de shutdown (utilizado em suítes de teste e lifespans isolados)."""
    global _is_shutting_down
    with _shutdown_lock:
        _is_shutting_down = False


def perform_graceful_shutdown(
    reason: str = "api_shutdown",
    exit_process: bool = True,
    reset_after: bool = False,
) -> dict:
    """
    Rotina unificada e idempotente de encerramento gracioso do backend Python:
    1. Cancela cooperativamente jobs ativos/na fila no PipelineService e aguarda
       breve janela (até 600ms) para concluir gravações atômicas em andamento.
    2. Encerra a instância do Ollama iniciada pelo Visionary (liberando VRAM e porta).
    3. Esvazia o cache CUDA se o PyTorch já estiver carregado em memória.
    4. Encerra o processo quando `exit_process=True`.
    """
    global _is_shutting_down
    with _shutdown_lock:
        if _is_shutting_down:
            return {"status": "already_shutting_down", "reason": reason}
        _is_shutting_down = True

    try:
        print(f"[Shutdown] Iniciando encerramento gracioso (motivo: {reason})...", flush=True)

        # 1. Cancelamento cooperativo de jobs em execução para evitar corrupção de arquivos
        try:
            from src.routers.rpc_router import api_bridge
            pipe_svc = getattr(api_bridge, "_pipeline_service", None)
            if pipe_svc is not None:
                pipe_svc.cancelAllJobs(hard_reset=False)
                deadline = time.time() + 0.6
                while time.time() < deadline:
                    if getattr(pipe_svc, "_current_running_job_id", None) is None:
                        break
                    time.sleep(0.05)
        except Exception as e:
            print(f"[Shutdown] Aviso ao cancelar jobs do pipeline: {e}", flush=True)

        # 2. Encerramento seguro do Ollama gerenciado pelo Visionary
        try:
            ModelManager.terminate_ollama()
        except Exception as e:
            print(f"[Shutdown] Erro ao encerrar Ollama: {e}", flush=True)

        # 3. Liberação de cache CUDA (somente se torch já foi importado na sessão)
        try:
            torch_mod = sys.modules.get("torch")
            if torch_mod is not None and hasattr(torch_mod, "cuda") and torch_mod.cuda.is_available():
                torch_mod.cuda.empty_cache()
        except Exception:
            pass

        if exit_process:
            os._exit(0)
        return {"status": "shut_down", "reason": reason}
    finally:
        if reset_after:
            with _shutdown_lock:
                _is_shutting_down = False


@system_router.get("/api/health")
def health_check(quick: bool = False):
    """
    Valida saúde do sistema.
    - `quick=True`: Heartbeat ultra-leve (< 1ms) para o Watchdog do Electron sem tocar disco/rede.
    - `quick=False`: Diagnóstico completo (escrita em disco, disponibilidade do PyTorch/CUDA e Ollama).
    """
    uptime_s = round(max(0.0, time.time() - _SERVER_START_TIME), 1)
    if quick:
        return JSONResponse(
            content={
                "status": "shutting_down" if _is_shutting_down else "ok",
                "app": "Visionary Studio",
                "quick": True,
                "pid": os.getpid(),
                "uptime_s": uptime_s,
            }
        )

    health = {
        "status": "shutting_down" if _is_shutting_down else "ok",
        "app": "Visionary Studio",
        "pid": os.getpid(),
        "uptime_s": uptime_s,
        "disk_write": False,
        "pytorch_cuda": False,
        "ollama": False
    }

    # 1. Disk Write Check
    try:
        from src.config import get_app_data_dir
        test_file = os.path.join(get_app_data_dir(), ".health_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        health["disk_write"] = True
    except Exception:
        pass

    # 2. PyTorch CUDA Check
    try:
        torch_mod = sys.modules.get("torch")
        cuda_submod = getattr(torch_mod, "cuda", None) if torch_mod is not None else None
        is_avail_fn = getattr(cuda_submod, "is_available", None) if cuda_submod is not None else None
        if callable(is_avail_fn):
            health["pytorch_cuda"] = bool(is_avail_fn())
        else:
            import importlib.util
            spec = importlib.util.find_spec("torch")
            health["pytorch_cuda"] = (
                spec is not None
                and getattr(spec, "has_location", False)
                and bool(getattr(spec, "origin", None))
                and os.path.isfile(spec.origin)
            )
    except Exception:
        health["pytorch_cuda"] = False

    # 3. Ollama Check (trust_env=False para evitar lookup de proxy no registro do Windows)
    try:
        import requests
        from src.config import Config
        ollama_url = Config.get("ollama_url", "http://127.0.0.1:11435/api").replace("localhost", "127.0.0.1").rstrip("/")
        if ollama_url.endswith("/api"):
            ollama_url = ollama_url[:-4]
        with requests.Session() as sess:
            sess.trust_env = False
            resp = sess.get(f"{ollama_url}/api/tags", timeout=0.25)
            if resp.status_code == 200:
                health["ollama"] = True
    except Exception:
        pass

    return JSONResponse(content=health)


@system_router.post("/api/shutdown")
def shutdown_server(background_tasks: BackgroundTasks):
    """
    Encerramento gracioso solicitado pelo Electron.
    Garante cancelamento de jobs ativos, encerramento do Ollama, liberação de VRAM e saída limpa.
    """
    def _graceful_exit():
        from src.config import Config
        is_test = Config.is_test_environment()
        perform_graceful_shutdown(
            reason="api_shutdown_endpoint",
            exit_process=True,
            reset_after=is_test,
        )

    background_tasks.add_task(_graceful_exit)
    return JSONResponse(content={"status": "shutting_down", "message": "Encerramento gracioso iniciado."})


def _get_or_create_thumbnail(real_path: str, max_width: int) -> Optional[tuple[bytes, str]]:
    """
    Gera miniatura leve (WebP/JPEG) em memória com cache LRU invalidado por mtime_ns + tamanho.
    Retorna None caso a imagem original já seja menor que o alvo ou não possa ser processada pelo Pillow.
    """
    clamped_w = max(64, min(1024, int(max_width)))
    try:
        st = os.stat(real_path)
        cache_key = (real_path, st.st_mtime_ns, st.st_size, clamped_w)
    except OSError:
        return None

    with _thumb_cache_lock:
        cached = _THUMB_CACHE.get(cache_key)
        if cached is not None:
            _THUMB_CACHE.move_to_end(cache_key)
            return cached

    try:
        from io import BytesIO
        from PIL import Image

        with Image.open(real_path) as im:
            orig_w, orig_h = im.size
            max_h = int(clamped_w * 1.65)
            if orig_w <= clamped_w and orig_h <= max_h:
                return None

            work = im.convert("RGB") if im.mode not in ("RGB", "L") else im.copy()
            work.thumbnail((clamped_w, max_h), Image.Resampling.BILINEAR)

            buf = BytesIO()
            try:
                work.save(buf, format="WEBP", quality=80, method=0)
                media_type = "image/webp"
            except Exception:
                buf = BytesIO()
                work.save(buf, format="JPEG", quality=82)
                media_type = "image/jpeg"

            result = (buf.getvalue(), media_type)
    except Exception:
        return None

    with _thumb_cache_lock:
        _THUMB_CACHE[cache_key] = result
        _THUMB_CACHE.move_to_end(cache_key)
        while len(_THUMB_CACHE) > _THUMB_CACHE_MAX_ITEMS:
            _THUMB_CACHE.popitem(last=False)

    return result


@system_router.get("/api/image")
def get_local_image(path: str, thumb: Optional[int] = None):
    """Endpoint para entrega segura de imagens locais (e miniaturas rápidas com ?thumb=360) à UI."""
    if not path:
        raise HTTPException(status_code=400, detail="Path parameter is required")
    try:
        real_path = authorize_image_read(path)
    except ImageReadDenied as denied:
        status_code = 400 if denied.reason == INVALID_PATH else 403
        raise HTTPException(status_code=status_code, detail=str(denied))
    if not os.path.isfile(real_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    resp_headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600, no-transform",
        "Access-Control-Allow-Origin": "*",
    }

    if thumb is not None and thumb > 0:
        thumb_res = _get_or_create_thumbnail(real_path, thumb)
        if thumb_res is not None:
            thumb_bytes, media_type = thumb_res
            return Response(content=thumb_bytes, media_type=media_type, headers=resp_headers)

    return FileResponse(real_path, headers=resp_headers)
