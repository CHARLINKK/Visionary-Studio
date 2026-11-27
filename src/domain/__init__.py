"""
Visionary Studio — Core Domain Package.
Reúne contratos de dados, persistência de páginas (PageStore) e transações atômicas de capítulo.
"""

from src.domain.bubble_contract import (
    safe_coord,
    to_snake_case,
    to_camel_case,
    normalize_bubble_for_gui,
    normalize_bubble_for_storage,
    reconcile_and_normalize_bubbles,
)
from src.domain.page_store import PageStore, LEGACY_STAGE_SUFFIXES, SATELLITE_SUFFIXES
from src.domain.reorder_transaction import (
    JOURNAL_FILENAME,
    safe_rename,
    plan_reorder,
    write_journal,
    rollback_transaction,
    recover_reorder_if_needed,
    execute_reorder,
)

__all__ = [
    "safe_coord",
    "to_snake_case",
    "to_camel_case",
    "normalize_bubble_for_gui",
    "normalize_bubble_for_storage",
    "reconcile_and_normalize_bubbles",
    "PageStore",
    "LEGACY_STAGE_SUFFIXES",
    "SATELLITE_SUFFIXES",
    "JOURNAL_FILENAME",
    "safe_rename",
    "plan_reorder",
    "write_journal",
    "rollback_transaction",
    "recover_reorder_if_needed",
    "execute_reorder",
]
