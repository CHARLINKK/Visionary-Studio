"""
Gerenciador Especializado de Downloads e Armazenamento de Modelos de IA.
Responsável por orquestrar downloads Hugging Face (snapshot & multi-single), downloads HTTP com resume (Range 206),
monitoramento de progresso em disco, validação de integridade física/hash SHA-256 e remoção segura.
O catálogo, resolução de raízes, manifesto e limpeza física residem em `src.model_engines.hf.cache_locator`.
"""

import os
import threading
import time

# Desativação de binários nativos de transferência (Rust):
# O 'hf_transfer' e o 'hf_xet' assumem o controle direto dos sockets em código C/Rust e
# NÃO emitem callbacks granulares de progresso para o Python, deixando a barra da UI congelada.
# Forçar o uso do pipeline HTTP puro do Python permite que nossos ganchos de stream e Range Paralelo
# calculem a taxa real de transferência (MB/s) e tempo restante (ETA) com precisão a cada 100ms.
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

from src.config import Config, get_app_data_dir
from src.model_engines.hf.integrity_checker import (
    safe_remove_path,
    is_hf_model_cached,
    verify_file_integrity,
    verify_safetensors_header,
)
from src.model_engines.hf.disk_monitor import (
    scan_disk_downloaded_bytes,
    monitor_disk_progress,
)
from src.model_engines.hf.cache_locator import (
    MODELS_REGISTRY,
    get_candidate_roots,
    get_monitor_paths,
    probe_hf_manifest,
    probe_hf_manifest_detailed,
    remove_model_artifacts,
    resolve_all_models_status,
)
from src.model_engines.hf.telemetry_logger import telemetry_logger


_LAZY_HTTP_EXPORTS = {
    "build_scoped_tqdm_class": "build_scoped_tqdm_class",
    "_build_scoped_tqdm_class": "build_scoped_tqdm_class",
    "download_single_file_http": "download_single_file_http",
    "DownloadStreamTracker": "DownloadStreamTracker",
    "scoped_hf_stream_hook": "scoped_hf_stream_hook",
}


def __getattr__(name: str):
    if name == "requests":
        import requests as _requests
        globals()["requests"] = _requests
        return _requests
    target = _LAZY_HTTP_EXPORTS.get(name)
    if target is not None:
        from src.model_engines.hf import http_downloader as _http_dl
        val = getattr(_http_dl, target)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def setup_hf_tqdm_hook():
    """Mantido por compatibilidade de importação; o progresso agora utiliza tqdm_class isolado por download."""
    return None


class HFDownloadManager:
    """
    Gerenciador dedicado de downloads e armazenamento local de modelos (Hugging Face, PyTorch e Ollama pull).
    """

    def __init__(self, base_dir=None, ollama_manager=None):
        self.base_dir = base_dir or get_app_data_dir()
        self.ollama_manager = ollama_manager
        self._status_lock = threading.Lock()
        self.download_status = {
            k: {
                "status": "idle",
                "progress": 0.0,
                "downloaded_bytes": 0,
                "total_bytes": MODELS_REGISTRY[k].get("estimated_size_bytes", 0),
                "message": ""
            } for k in MODELS_REGISTRY
        }
        self._download_threads = {}
        self._stop_events = {}
        self._cancel_events = {}
        self._progress_callbacks = []
        self._last_notify_time = {}
        self._last_stream_time = {}
        self.register_progress_callback(lambda k, st: telemetry_logger.record_tick(k, st, source="hf_mgr"))

    def register_progress_callback(self, callback):
        """Registra uma função callback(key: str, status: dict) chamada quando houver progresso."""
        if callable(callback) and callback not in self._progress_callbacks:
            self._progress_callbacks.append(callback)

    def _notify_progress(self, key: str, throttle_interval: float = 0.0):
        """Notifica callbacks registrados de forma thread-safe com throttle opcional."""
        if not self._progress_callbacks:
            return

        now = time.time()
        if throttle_interval > 0.0:
            last = self._last_notify_time.get(key, 0.0)
            if now - last < throttle_interval:
                return
        self._last_notify_time[key] = now

        with self._status_lock:
            status_copy = dict(self.download_status.get(key, {}))

        for cb in self._progress_callbacks:
            try:
                cb(key, status_copy)
            except Exception:
                pass

    def is_hf_model_cached(self, target_path: str) -> bool:
        """Verifica se o diretório de cache do HuggingFace contém arquivos reais do modelo/snapshots."""
        return is_hf_model_cached(target_path)

    def _get_candidate_roots(self) -> list[str]:
        """Retorna a lista ordenada de diretórios raiz candidatos para busca de modelos (base_dir, projectRoot, etc.)."""
        return get_candidate_roots(self.base_dir)

    def _get_monitor_paths(self, key: str) -> list[str]:
        return get_monitor_paths(self.base_dir, key, MODELS_REGISTRY)

    def get_download_status(self, key: str) -> dict:
        if key not in MODELS_REGISTRY:
            return {
                "status": "unknown",
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "progress": 0.0,
                "speed_mbps": 0.0,
                "eta_seconds": 0,
                "message": "Modelo desconhecido"
            }
        with self._status_lock:
            st = self.download_status.get(key, {}).copy()

        info = MODELS_REGISTRY[key]
        est_size = info.get("estimated_size_bytes", 0)
        tot = st.get("total_bytes") or est_size
        dl = st.get("downloaded_bytes", 0)

        if st.get("status") in ["downloading", "extracting"]:
            last_stream_ts = self._last_stream_time.get(key, 0.0)
            stream_authoritative = (time.time() - last_stream_ts) < 5.0 and dl > 0
            if not stream_authoritative:
                monitor_paths = self._get_monitor_paths(key)
                if monitor_paths:
                    disk_bytes = self._scan_disk_downloaded_bytes(monitor_paths)
                    if tot > 0:
                        disk_bytes = min(disk_bytes, tot)
                    dl = max(dl, disk_bytes)

        prog = st.get("progress", 0.0)
        if tot > 0 and dl > 0:
            calc_prog = round((dl / tot) * 100, 1)
            if st.get("status") in ["downloading", "extracting"]:
                calc_prog = min(99.0, calc_prog)
            prog = max(prog, calc_prog)

        return {
            "status": st.get("status", "idle"),
            "downloaded_bytes": dl,
            "total_bytes": tot,
            "progress": min(prog, 100.0),
            "speed_mbps": st.get("speed_mbps", 0.0),
            "eta_seconds": st.get("eta_seconds", 0),
            "message": st.get("message", "")
        }

    def _scan_disk_downloaded_bytes(self, paths: list[str]) -> int:
        return scan_disk_downloaded_bytes(paths)

    def _monitor_disk_progress(self, key: str, monitor_paths: list[str], stop_event: threading.Event):
        info = MODELS_REGISTRY.get(key, {})
        est_total = info.get("estimated_size_bytes", 0)
        monitor_disk_progress(self, key, monitor_paths, stop_event, est_total=est_total)

    def download_module(self, key: str) -> bool:
        if key not in MODELS_REGISTRY:
            return False

        with self._status_lock:
            existing_thread = self._download_threads.get(key)
            if existing_thread and existing_thread.is_alive():
                if self.download_status[key]["status"] == "downloading" and not self._cancel_events.get(key, threading.Event()).is_set():
                    return True

                if key in self._stop_events:
                    self._stop_events[key].set()
                if key in self._cancel_events:
                    self._cancel_events[key].set()

        if existing_thread and existing_thread.is_alive():
            existing_thread.join(timeout=0.2)

        thread = threading.Thread(target=self._run_download_thread, args=(key, MODELS_REGISTRY[key]), daemon=True)
        with self._status_lock:
            self._download_threads[key] = thread
            thread.start()
        return True

    def _probe_hf_manifest(self, info: dict, target_path: str) -> tuple[int, int, int]:
        return probe_hf_manifest(self.base_dir, info, target_path)

    def _probe_hf_manifest_detailed(self, info: dict, target_path: str) -> dict:
        return probe_hf_manifest_detailed(self.base_dir, info, target_path)

    def _run_download_thread(self, key: str, info: dict):
        target_path = os.path.join(self.base_dir, info.get("target_dir", "models"))
        os.makedirs(target_path, exist_ok=True)
        est_size = info.get("estimated_size_bytes", 0)

        stop_monitor = threading.Event()
        cancel_event = threading.Event()

        with self._status_lock:
            self._stop_events[key] = stop_monitor
            self._cancel_events[key] = cancel_event
            self.download_status[key] = {
                "status": "downloading",
                "progress": 0.0,
                "downloaded_bytes": 0,
                "total_bytes": est_size,
                "speed_mbps": 0.0,
                "eta_seconds": 0,
                "message": "Sincronizando manifesto HF..."
            }
        self._notify_progress(key, throttle_interval=0.0)
        telemetry_logger.start_session(key, total_bytes=est_size)

        monitor_paths = self._get_monitor_paths(key)

        monitor_thread = threading.Thread(
            target=self._monitor_disk_progress,
            args=(key, monitor_paths, stop_monitor),
            name=f"DiskMonitor-{key}",
            daemon=True
        )
        monitor_thread.start()

        try:
            if info["type"] == "huggingface_cache":
                manifest = self._probe_hf_manifest_detailed(info, target_path)
                exact_total = int(manifest.get("total_bytes", 0) or 0)
                pre_bytes = int(manifest.get("pre_bytes", 0) or 0)
                f_cnt = int(manifest.get("file_count", 0) or 0)
                manifest_files = manifest.get("files") or {}
                effective_total = exact_total or est_size
                init_pct = min(95.0, round((pre_bytes / effective_total) * 100, 1)) if effective_total > 0 and pre_bytes > 0 else 0.0
                with self._status_lock:
                    if not cancel_event.is_set():
                        self.download_status[key]["total_bytes"] = effective_total
                        self.download_status[key]["downloaded_bytes"] = pre_bytes
                        self.download_status[key]["progress"] = max(self.download_status[key].get("progress", 0.0), init_pct)
                        self.download_status[key]["message"] = (
                            f"Sincronizando · {f_cnt} artefatos..." if f_cnt > 0 else "Conectando ao Hugging Face..."
                        )
                self._notify_progress(key, throttle_interval=0.0)

                from huggingface_hub import snapshot_download
                local_dir = os.path.join(target_path, info.get("cache_folder", "florence-2-base"))
                dl_kwargs = {
                    "repo_id": info["repo_id"],
                    "local_dir": local_dir,
                    "max_workers": 8,
                }
                if info.get("ignore_patterns"):
                    dl_kwargs["ignore_patterns"] = info["ignore_patterns"]

                from src.model_engines.hf.http_downloader import scoped_hf_stream_hook
                with scoped_hf_stream_hook(
                    self,
                    key,
                    target_total_bytes=effective_total,
                    initial_bytes=pre_bytes,
                    manifest_files=manifest_files,
                ):
                    snapshot_download(**dl_kwargs)

                with self._status_lock:
                    if not cancel_event.is_set() and self.download_status.get(key, {}).get("status") == "downloading":
                        self.download_status[key]["progress"] = max(self.download_status[key].get("progress", 0.0), 98.8)
                        self.download_status[key]["message"] = "Verificando cabeçalho Safetensors..."
                        self.download_status[key]["speed_mbps"] = 0.0
                        self.download_status[key]["eta_seconds"] = 0
                self._notify_progress(key, throttle_interval=0.0)

                # Validação estrutural de cabeçalho Safetensors:
                # Previne que modelos corrompidos por cortes de conexão sejam carregados pela IA.
                # O safetensors armazena um cabeçalho JSON de tamanho variável nos primeiros 8 bytes;
                # se o arquivo for truncado, a leitura falha imediatamente com erro claro antes de causar crash em C++.
                if not cancel_event.is_set() and os.path.isdir(local_dir):
                    for fn in os.listdir(local_dir):
                        if fn.endswith(".safetensors"):
                            sf_path = os.path.join(local_dir, fn)
                            if os.path.isfile(sf_path) and os.path.getsize(sf_path) >= 4096:
                                if not verify_safetensors_header(sf_path, strict=True):
                                    raise RuntimeError(f"Cabeçalho Safetensors corrompido ou truncado em {fn}.")
                    if not Config.is_test_environment() and "florence" in key.lower():
                        from src.utils.hf_snapshot_resolver import is_valid_florence_dir
                        if not is_valid_florence_dir(local_dir):
                            raise RuntimeError("Arquivos estruturais do Florence-2 incompletos após download.")

                final_bytes = self._scan_disk_downloaded_bytes(monitor_paths) or effective_total

                with self._status_lock:
                    if not cancel_event.is_set() and self.download_status.get(key, {}).get("status") == "downloading":
                        self.download_status[key]["progress"] = max(self.download_status[key].get("progress", 0.0), 99.5)
                        self.download_status[key]["message"] = "Registrando OCR no pipeline..."
                self._notify_progress(key, throttle_interval=0.0)
                stop_monitor.wait(0.1)

                with self._status_lock:
                    if not cancel_event.is_set() and self.download_status.get(key, {}).get("status") == "downloading":
                        self.download_status[key] = {
                            "status": "installed",
                            "progress": 100.0,
                            "downloaded_bytes": max(final_bytes, effective_total),
                            "total_bytes": max(final_bytes, effective_total),
                            "speed_mbps": 0.0,
                            "eta_seconds": 0,
                            "message": "Concluído!"
                        }
                self._notify_progress(key, throttle_interval=0.0)

            elif info["type"] == "huggingface_multi_single":
                from huggingface_hub import hf_hub_download
                import concurrent.futures
                from src.model_engines.hf.http_downloader import _registry_lock, _active_stream_threads

                files = info.get("files", [])
                total_files = len(files)
                manifest = self._probe_hf_manifest_detailed(info, target_path)
                exact_total = int(manifest.get("total_bytes", 0) or 0)
                pre_bytes = int(manifest.get("pre_bytes", 0) or 0)
                manifest_files = manifest.get("files") or {}
                effective_total = exact_total or est_size
                init_pct = min(95.0, round((pre_bytes / effective_total) * 100, 1)) if effective_total > 0 and pre_bytes > 0 else 0.0

                with self._status_lock:
                    if not cancel_event.is_set():
                        self.download_status[key]["total_bytes"] = effective_total
                        self.download_status[key]["downloaded_bytes"] = pre_bytes
                        self.download_status[key]["progress"] = max(self.download_status[key].get("progress", 0.0), init_pct)
                        self.download_status[key]["message"] = f"Baixando detectores · 0/{total_files}"
                self._notify_progress(key, throttle_interval=0.0)

                from src.model_engines.hf.http_downloader import scoped_hf_stream_hook
                with scoped_hf_stream_hook(
                    self,
                    key,
                    target_total_bytes=effective_total,
                    initial_bytes=pre_bytes,
                    manifest_files=manifest_files,
                ) as tracker:
                    completed_count = 0
                    files_lock = threading.Lock()

                    def _download_file(f):
                        nonlocal completed_count
                        if cancel_event.is_set():
                            return
                        sub_target = os.path.join(self.base_dir, f.get("target_dir", "models"))
                        os.makedirs(sub_target, exist_ok=True)
                        dl_kwargs = {
                            "repo_id": f["repo_id"],
                            "filename": f["filename"],
                            "local_dir": sub_target,
                        }
                        w_ident = threading.get_ident()
                        with _registry_lock:
                            _active_stream_threads[w_ident] = (self, key, tracker)
                        try:
                            hf_hub_download(**dl_kwargs)
                            with files_lock:
                                completed_count += 1
                                if not cancel_event.is_set():
                                    with self._status_lock:
                                        if completed_count < total_files:
                                            self.download_status[key]["message"] = f"Detectores · {completed_count}/{total_files} baixado"
                                        else:
                                            self.download_status[key]["message"] = "Validando pesos YOLO..."
                                    self._notify_progress(key, throttle_interval=0.0)
                        finally:
                            with _registry_lock:
                                _active_stream_threads.pop(w_ident, None)

                    self._last_stream_time[key] = time.time()
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, max(1, total_files))) as executor:
                        futures = [executor.submit(_download_file, f) for f in files]
                        for fut in concurrent.futures.as_completed(futures):
                            fut.result()

                with self._status_lock:
                    if not cancel_event.is_set() and self.download_status.get(key, {}).get("status") == "downloading":
                        self.download_status[key]["progress"] = max(self.download_status[key].get("progress", 0.0), 98.8)
                        self.download_status[key]["message"] = "Validando pesos TorchScript..."
                        self.download_status[key]["speed_mbps"] = 0.0
                        self.download_status[key]["eta_seconds"] = 0
                self._notify_progress(key, throttle_interval=0.0)

                for f in info.get("files", []):
                    p = os.path.join(self.base_dir, f.get("target_dir", "models"), f["filename"])
                    min_sz = f.get("min_size_bytes", 1024 * 1024) if not Config.is_test_environment() else 1024 * 1024
                    if not os.path.exists(p) or os.path.getsize(p) < 1024 * 1024:
                        raise RuntimeError(f"O modelo {f['filename']} não foi baixado corretamente ou está truncado.")
                    if not Config.is_test_environment() and not verify_file_integrity(p, min_size_bytes=min_sz):
                        raise RuntimeError(f"Cabeçalho binário inválido em {f['filename']}.")

                final_bytes = self._scan_disk_downloaded_bytes(monitor_paths) or effective_total

                with self._status_lock:
                    if not cancel_event.is_set() and self.download_status.get(key, {}).get("status") == "downloading":
                        self.download_status[key]["progress"] = max(self.download_status[key].get("progress", 0.0), 99.5)
                        self.download_status[key]["message"] = "Registrando detectores..."
                self._notify_progress(key, throttle_interval=0.0)
                stop_monitor.wait(0.1)

                with self._status_lock:
                    if not cancel_event.is_set() and self.download_status.get(key, {}).get("status") == "downloading":
                        self.download_status[key] = {
                            "status": "installed",
                            "progress": 100.0,
                            "downloaded_bytes": max(final_bytes, effective_total),
                            "total_bytes": max(final_bytes, effective_total),
                            "speed_mbps": 0.0,
                            "eta_seconds": 0,
                            "message": "Concluído!"
                        }
                self._notify_progress(key, throttle_interval=0.0)

            elif info["type"] == "single_file":
                from src.model_engines.hf.http_downloader import download_single_file_http
                download_single_file_http(
                    self,
                    key=key,
                    info=info,
                    target_path=target_path,
                    cancel_event=cancel_event,
                    est_size=est_size
                )

            elif info["type"] == "ollama":
                ollama_ok = False
                if self.ollama_manager:
                    ollama_ok = self.ollama_manager.check_ollama_running() or self.ollama_manager.ensure_ollama_running()

                if not ollama_ok:
                    raise RuntimeError("O serviço do Ollama não está em execução. Inicie o Ollama primeiro.")

                with self._status_lock:
                    self.download_status[key]["message"] = f"Baixando {info['model_name']} via Ollama..."

                self.ollama_manager.pull_model(info["model_name"])

                with self._status_lock:
                    self.download_status[key] = {
                        "status": "installed",
                        "progress": 100.0,
                        "downloaded_bytes": est_size,
                        "total_bytes": est_size,
                        "message": "Concluído!"
                    }
        except Exception as e:
            with self._status_lock:
                if not cancel_event.is_set():
                    self.download_status[key] = {
                        "status": "error",
                        "progress": 0.0,
                        "downloaded_bytes": 0,
                        "total_bytes": est_size,
                        "message": f"Erro: {str(e)}"
                    }
                else:
                    self.download_status[key] = {
                        "status": "cancelled",
                        "progress": 0.0,
                        "downloaded_bytes": 0,
                        "total_bytes": est_size,
                        "message": "Download cancelado pelo usuário"
                    }
        finally:
            stop_monitor.set()
            monitor_thread.join(timeout=1.0)
            self._notify_progress(key, throttle_interval=0.0)

    def cancel_module(self, key: str) -> bool:
        """Cancela cooperativamente um download ativo e atualiza o status para 'cancelled'."""
        if key not in MODELS_REGISTRY:
            return False

        with self._status_lock:
            if key in self._cancel_events:
                self._cancel_events[key].set()
            if key in self._stop_events:
                self._stop_events[key].set()

            st = self.download_status.get(key)
            if st and st.get("status") == "downloading":
                self.download_status[key] = {
                    "status": "cancelled",
                    "progress": 0.0,
                    "downloaded_bytes": 0,
                    "total_bytes": MODELS_REGISTRY[key].get("estimated_size_bytes", 0),
                    "message": "Download cancelado pelo usuário"
                }

        self._notify_progress(key, throttle_interval=0.0)
        return True

    cancel_download = cancel_module

    def remove_module(self, key: str) -> bool:
        """Remove o modelo especificado do disco de forma thread-safe em todas as raízes candidatas e caches."""
        return remove_model_artifacts(self, key, MODELS_REGISTRY)

    def get_all_status(self, ollama_models: set = None) -> dict:
        """Retorna o dicionário consolidado de status de todos os modelos no registry."""
        return resolve_all_models_status(self, ollama_models=ollama_models, registry=MODELS_REGISTRY)
