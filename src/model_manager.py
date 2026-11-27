"""
Fachada central para downloads do HuggingFace (`HFDownloadManager`) e ciclo
de vida do servidor local do Ollama (`OllamaProcessManager`).
"""

import atexit
import threading
from src.config import get_app_data_dir
from src.model_engines.ollama_process_manager import OllamaProcessManager
from src.model_engines.hf_download_manager import (
    HFDownloadManager,
    MODELS_REGISTRY,
    safe_remove_path,
    is_hf_model_cached,
    verify_file_integrity,
    setup_hf_tqdm_hook,
)


class _ModelManagerMeta(type):
    """Espelha `_ollama_process` e `_ollama_pid` como propriedades de classe para
    que callers e testes legados que leem `ModelManager._ollama_pid` enxerguem o
    estado real gerenciado em `OllamaProcessManager`."""

    @property
    def _ollama_process(cls):
        return OllamaProcessManager._ollama_process

    @_ollama_process.setter
    def _ollama_process(cls, val):
        OllamaProcessManager._ollama_process = val

    @property
    def _ollama_pid(cls):
        return OllamaProcessManager._ollama_pid

    @_ollama_pid.setter
    def _ollama_pid(cls, val):
        OllamaProcessManager._ollama_pid = val


class ModelManager(metaclass=_ModelManagerMeta):
    """Fachada para downloads de modelos e controle do processo local do Ollama."""
    _safe_remove_path = staticmethod(safe_remove_path)
    safe_remove_path = staticmethod(safe_remove_path)

    @property
    def _ollama_process(self):
        return OllamaProcessManager._ollama_process

    @_ollama_process.setter
    def _ollama_process(self, val):
        OllamaProcessManager._ollama_process = val

    @property
    def _ollama_pid(self):
        return OllamaProcessManager._ollama_pid

    @_ollama_pid.setter
    def _ollama_pid(self, val):
        OllamaProcessManager._ollama_pid = val

    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = get_app_data_dir()
        else:
            self.base_dir = base_dir
        self._ollama_mgr = OllamaProcessManager(base_dir=self.base_dir)
        self._hf_mgr = HFDownloadManager(base_dir=self.base_dir, ollama_manager=self._ollama_mgr)

    @property
    def _status_lock(self):
        return self._hf_mgr._status_lock

    @property
    def download_status(self):
        return self._hf_mgr.download_status

    @download_status.setter
    def download_status(self, val):
        self._hf_mgr.download_status = val

    @property
    def _download_threads(self):
        return self._hf_mgr._download_threads

    @property
    def _stop_events(self):
        return self._hf_mgr._stop_events

    @property
    def _cancel_events(self):
        return self._hf_mgr._cancel_events

    def is_hf_model_cached(self, target_path: str) -> bool:
        return self._hf_mgr.is_hf_model_cached(target_path)

    def _get_monitor_paths(self, key: str) -> list[str]:
        return self._hf_mgr._get_monitor_paths(key)

    def get_download_status(self, key: str) -> dict:
        return self._hf_mgr.get_download_status(key)

    def _scan_disk_downloaded_bytes(self, paths: list[str]) -> int:
        return self._hf_mgr._scan_disk_downloaded_bytes(paths)

    def _monitor_disk_progress(self, key: str, monitor_paths: list[str], stop_event: threading.Event):
        return self._hf_mgr._monitor_disk_progress(key, monitor_paths, stop_event)

    def download_module(self, key: str) -> bool:
        return self._hf_mgr.download_module(key)

    def _run_download_thread(self, key: str, info: dict):
        return self._hf_mgr._run_download_thread(key, info)

    def cancel_module(self, key: str) -> bool:
        return self._hf_mgr.cancel_module(key)

    cancel_download = cancel_module

    def remove_module(self, key: str) -> bool:
        return self._hf_mgr.remove_module(key)

    def get_all_status(self) -> dict:
        return self._hf_mgr.get_all_status(self.get_ollama_models())

    def register_progress_callback(self, callback):
        return self._hf_mgr.register_progress_callback(callback)

    def check_ollama_running(self) -> bool:
        return self._ollama_mgr.check_ollama_running()

    def start_ollama_server(self) -> dict:
        return self._ollama_mgr.start_ollama_server(check_running_fn=self.check_ollama_running)

    def ensure_ollama_running(self) -> bool:
        if self.check_ollama_running():
            return True
        res = self.start_ollama_server()
        return bool(res.get("success")) or self.check_ollama_running()

    def get_ollama_models(self) -> set:
        return self._ollama_mgr.get_ollama_models()

    @classmethod
    def _save_ollama_pid(cls, pid: int):
        OllamaProcessManager._save_ollama_pid(pid)

    @classmethod
    def _remove_ollama_pid_file(cls):
        OllamaProcessManager._remove_ollama_pid_file()

    @classmethod
    def terminate_ollama(cls):
        OllamaProcessManager.terminate_ollama()

    def __getattr__(self, name: str):
        for target in (self._hf_mgr, self._ollama_mgr):
            if hasattr(target, name):
                return getattr(target, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


# Garante encerramento do Ollama isolado mesmo quando o backend sai fora do fluxo do Electron
atexit.register(ModelManager.terminate_ollama)
