"""
Fachada de retrocompatibilidade para `src.api_services.core_engine_installer`.
A implementação canônica agora vive em `src.model_engines.core_engine_installer`.
"""
import sys
import src.model_engines.core_engine_installer as _core_engine_mod
from src.model_engines.core_engine_installer import (
    CoreEngineInstaller,
    _cache_lock,
)

__all__ = [
    "CoreEngineInstaller",
    "_cache_lock",
]

sys.modules[__name__] = _core_engine_mod
