"""
Pacote de Motores de IA e Gerenciamento Especializado de Modelos.
"""

import importlib

from src.model_engines.core_engine_installer import CoreEngineInstaller, _cache_lock
from src.model_engines.ollama_process_manager import OllamaProcessManager
from src.model_engines.hf_download_manager import (
    HFDownloadManager,
    MODELS_REGISTRY,
    safe_remove_path,
    is_hf_model_cached,
    verify_file_integrity,
    setup_hf_tqdm_hook,
)

_LAZY_EXPORTS = {
    "install_isolated_ollama": ("src.model_engines.ollama_isolated_installer", "install_isolated_ollama"),
    "cancel_isolated_install": ("src.model_engines.ollama_isolated_installer", "cancel_isolated_install"),
    "pull_ollama_model": ("src.model_engines.ollama_model_puller", "pull_ollama_model"),
    "cancel_ollama_download": ("src.model_engines.ollama_model_puller", "cancel_ollama_download"),
    "delete_ollama_model": ("src.model_engines.ollama_model_puller", "delete_ollama_model"),
    "test_ollama_translation": ("src.model_engines.ollama_model_puller", "test_ollama_translation"),
    "get_ollama_models_details": ("src.model_engines.ollama_model_puller", "get_ollama_models_details"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod_name, attr_name = target
    mod = importlib.import_module(mod_name)
    val = getattr(mod, attr_name)
    globals()[name] = val
    return val

__all__ = [
    "CoreEngineInstaller",
    "_cache_lock",
    "OllamaProcessManager",
    "install_isolated_ollama",
    "cancel_isolated_install",
    "pull_ollama_model",
    "cancel_ollama_download",
    "delete_ollama_model",
    "test_ollama_translation",
    "get_ollama_models_details",
    "HFDownloadManager",
    "MODELS_REGISTRY",
    "safe_remove_path",
    "is_hf_model_cached",
    "verify_file_integrity",
    "setup_hf_tqdm_hook",
]
