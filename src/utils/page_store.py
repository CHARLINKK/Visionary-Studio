"""
Fachada de retrocompatibilidade para src.domain.page_store.
Mantém 100% dos imports legados e alvos de monkeypatch funcionando sem quebra.
"""

import sys
import src.domain.page_store as _domain_mod
from src.domain.page_store import (  # noqa: F401
    PageStore,
    LEGACY_STAGE_SUFFIXES,
    SATELLITE_SUFFIXES,
    _UNSET,
)

sys.modules[__name__] = _domain_mod
