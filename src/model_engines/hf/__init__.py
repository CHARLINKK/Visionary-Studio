"""
Subpacote de infraestrutura e gerenciamento de modelos Hugging Face do Visionary Studio.
"""

import importlib

from src.model_engines.hf.integrity_checker import (
    safe_remove_path,
    is_hf_model_cached,
    verify_file_integrity,
)
from src.model_engines.hf.disk_monitor import (
    scan_disk_downloaded_bytes,
    monitor_disk_progress,
)

_LAZY_EXPORTS = {
    "build_scoped_tqdm_class": ("src.model_engines.hf.http_downloader", "build_scoped_tqdm_class"),
    "download_single_file_http": ("src.model_engines.hf.http_downloader", "download_single_file_http"),
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
    "safe_remove_path",
    "is_hf_model_cached",
    "verify_file_integrity",
    "scan_disk_downloaded_bytes",
    "monitor_disk_progress",
    "build_scoped_tqdm_class",
    "download_single_file_http",
]
