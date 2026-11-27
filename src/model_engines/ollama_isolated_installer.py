"""
Instalador isolado do motor Ollama portátil para Windows (64-bit) em `%APPDATA%\\Visionary Studio\\engine\\ollama`.
"""

import os
import shutil
import threading
import time
import zipfile
import requests

from src.config import Config


def cancel_isolated_install(mgr) -> dict:
    """Cancela o download/instalação do motor Ollama isolado."""
    with mgr._get_lock():
        if not getattr(mgr, "_ollama_installing", False):
            return {"success": False, "message": "Nenhuma instalação do Ollama em andamento."}
        if mgr._ollama_install_cancel_event:
            mgr._ollama_install_cancel_event.set()
        mgr._ollama_install_progress["status"] = "cancelled"
        mgr._ollama_install_progress["message"] = "Instalação cancelada pelo usuário."
    mgr.notify_install_progress(throttle_interval=0.0)
    return {"success": True, "message": "Instalação cancelada com sucesso."}


def install_isolated_ollama(mgr, download_url: str = None, session_factory=None) -> dict:
    """
    Baixa e extrai o pacote oficial portátil do Ollama para Windows (64-bit)
    em %APPDATA%\\Visionary Studio\\engine\\ollama\\ com telemetria via EventBus.
    """
    with mgr._get_lock():
        if getattr(mgr, "_ollama_installing", False):
            return {"success": False, "message": "Instalação do Ollama já está em andamento."}
        mgr._ollama_installing = True
        mgr._ollama_install_cancel_event = threading.Event()
        mgr._ollama_install_progress = {
            "status": "downloading",
            "percent": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_mbps": 0.0,
            "eta_seconds": 0,
            "message": "Iniciando download do motor Ollama portátil...",
            "error": "",
        }
    mgr.notify_install_progress(throttle_interval=0.0)

    cancel_event = mgr._ollama_install_cancel_event
    url = download_url or Config.get(
        "ollama_windows_zip_url",
        "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip",
    )
    make_session = session_factory or requests.Session

    def _worker():
        from src.config import get_app_data_dir

        app_dir = get_app_data_dir()
        temp_dir = os.path.join(app_dir, "engine", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        zip_dest = os.path.join(temp_dir, "ollama-windows-amd64.zip")
        part_dest = zip_dest + ".part"
        target_engine_dir = os.path.join(app_dir, "engine", "ollama")

        session = make_session()
        session.trust_env = False

        try:
            with session.get(url, stream=True, timeout=45) as resp:
                resp.raise_for_status()
                total_bytes = int(resp.headers.get("content-length", 0))
                with mgr._get_lock():
                    mgr._ollama_install_progress["total_bytes"] = total_bytes
                    mgr._ollama_install_progress["message"] = "Baixando pacote portátil do Ollama..."
                mgr.notify_install_progress()

                downloaded = 0
                chunk_size = 1024 * 1024
                start_time = time.time()
                last_time = start_time
                last_downloaded = 0
                used_parallel = False

                from src.config import is_test_environment
                if (
                    session_factory is None
                    and not is_test_environment()
                    and total_bytes >= 4 * 1024 * 1024
                ):
                    from src.model_engines.hf.http_downloader import (
                        DownloadStreamTracker,
                        parallel_range_stream_to_writer,
                    )

                    resolved_zip_url = getattr(resp, "url", None) or url
                    resp.close()
                    tracker = DownloadStreamTracker("ollama_engine", target_total_bytes=total_bytes, initial_bytes=0)

                    def _on_zip_chunk(nb: int):
                        nonlocal downloaded
                        with tracker.lock:
                            now_c = time.time()
                            tracker.record_chunk_locked(nb, now_c)
                            downloaded = tracker.downloaded_bytes
                            spd = tracker.speed_mbps
                            eta = tracker.eta_seconds
                        pct = min(88.0, (downloaded / total_bytes * 88.0)) if total_bytes > 0 else 10.0
                        with mgr._get_lock():
                            mgr._ollama_install_progress.update({
                                "percent": round(pct, 1),
                                "downloaded_bytes": downloaded,
                                "speed_mbps": spd,
                                "eta_seconds": max(0, eta),
                                "message": f"Baixando motor... ({downloaded / (1024**2):.1f}/{total_bytes / (1024**2):.1f} MB)",
                            })
                        mgr.notify_install_progress(throttle_interval=0.15)

                    with open(part_dest, "wb") as f:
                        used_parallel = parallel_range_stream_to_writer(
                            url=resolved_zip_url,
                            write_fn=f.write,
                            total_size=total_bytes,
                            start_byte=0,
                            flush_fn=f.flush,
                            on_chunk=_on_zip_chunk,
                            cancel_event=cancel_event,
                            max_workers=16,
                            trust_env=False,
                        )

                if not used_parallel:
                    def _stream_zip(r_obj):
                        nonlocal downloaded, last_time, last_downloaded
                        with open(part_dest, "wb") as f:
                            for chunk in r_obj.iter_content(chunk_size=chunk_size):
                                if cancel_event.is_set():
                                    raise InterruptedError("Cancelado pelo usuário.")
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    now = time.time()
                                    dt = now - last_time
                                    if dt >= 0.4:
                                        speed = ((downloaded - last_downloaded) / dt) / (1024 * 1024) if dt > 0 else 0
                                        pct = min(88.0, (downloaded / total_bytes * 88.0)) if total_bytes > 0 else 10.0
                                        remaining = max(0, total_bytes - downloaded)
                                        eta = int(remaining / (speed * 1024 * 1024)) if speed > 0.05 else 0
                                        with mgr._get_lock():
                                            mgr._ollama_install_progress.update({
                                                "percent": round(pct, 1),
                                                "downloaded_bytes": downloaded,
                                                "speed_mbps": round(speed, 1),
                                                "eta_seconds": max(0, eta),
                                                "message": f"Baixando motor... ({downloaded / (1024**2):.1f}/{total_bytes / (1024**2):.1f} MB)",
                                            })
                                        mgr.notify_install_progress(throttle_interval=0.3)
                                        last_time = now
                                        last_downloaded = downloaded

                    if getattr(resp, "raw", None) is not None and not getattr(resp.raw, "closed", False):
                        _stream_zip(resp)
                    else:
                        with session.get(url, stream=True, timeout=45) as resp2:
                            resp2.raise_for_status()
                            _stream_zip(resp2)

            if os.path.exists(zip_dest):
                try:
                    os.remove(zip_dest)
                except Exception:
                    pass
            os.replace(part_dest, zip_dest)

            if cancel_event.is_set():
                raise InterruptedError("Cancelado pelo usuário.")

            with mgr._get_lock():
                mgr._ollama_install_progress.update({
                    "status": "extracting",
                    "percent": 90.0,
                    "speed_mbps": 0.0,
                    "eta_seconds": 0,
                    "message": "Extraindo binários e runners do Ollama...",
                })
            mgr.notify_install_progress()

            os.makedirs(target_engine_dir, exist_ok=True)
            with zipfile.ZipFile(zip_dest, "r") as zf:
                zf.extractall(target_engine_dir)

            top_exe = os.path.join(target_engine_dir, "ollama.exe")
            if not os.path.isfile(top_exe):
                for root, _, files in os.walk(target_engine_dir):
                    if "ollama.exe" in files:
                        sub_dir = root
                        for item in os.listdir(sub_dir):
                            s = os.path.join(sub_dir, item)
                            d = os.path.join(target_engine_dir, item)
                            if not os.path.exists(d):
                                shutil.move(s, d)
                        break

            try:
                if os.path.exists(zip_dest):
                    os.remove(zip_dest)
            except Exception:
                pass

            with mgr._get_lock():
                mgr._ollama_install_progress.update({
                    "status": "completed",
                    "percent": 100.0,
                    "downloaded_bytes": total_bytes,
                    "message": "Motor Ollama instalado com sucesso!",
                })
            mgr.notify_install_progress()

            try:
                mgr.start_server()
            except Exception:
                pass

        except InterruptedError:
            with mgr._get_lock():
                mgr._ollama_install_progress.update({
                    "status": "cancelled",
                    "message": "Instalação cancelada pelo usuário.",
                })
            mgr.notify_install_progress()
            try:
                if os.path.exists(part_dest):
                    os.remove(part_dest)
            except Exception:
                pass
        except Exception as e:
            with mgr._get_lock():
                mgr._ollama_install_progress.update({
                    "status": "error",
                    "error": str(e),
                    "message": f"Erro durante a instalação: {e}",
                })
            mgr.notify_install_progress()
        finally:
            with mgr._get_lock():
                mgr._ollama_installing = False

    t = threading.Thread(target=_worker, daemon=True, name="OllamaIsolatedInstallerThread")
    t.start()
    return {"success": True, "message": "Instalação do motor Ollama iniciada em segundo plano."}
