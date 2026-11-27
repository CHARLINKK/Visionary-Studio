"""
Fachada de retrocompatibilidade para src.domain.bubble_contract.
Mantém 100% dos imports legados e alvos de monkeypatch funcionando sem quebra.
"""

import sys
import src.domain.bubble_contract as _domain_mod
from src.domain.bubble_contract import (  # noqa: F401
    safe_coord,
    to_snake_case,
    to_camel_case,
    normalize_bubble_for_gui,
    normalize_bubble_for_storage,
    reconcile_and_normalize_bubbles,
)

sys.modules[__name__] = _domain_mod
