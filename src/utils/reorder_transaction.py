"""
Fachada de retrocompatibilidade para src.domain.reorder_transaction.
Mantém 100% dos imports legados e alvos de monkeypatch funcionando sem quebra.
"""

import sys
import src.domain.reorder_transaction as _domain_mod
from src.domain.reorder_transaction import (  # noqa: F401
    JOURNAL_FILENAME,
    _get_folder_lock,
    safe_rename,
    _find_associated_files,
    plan_reorder,
    write_journal,
    rollback_transaction,
    recover_reorder_if_needed,
    execute_reorder,
)

sys.modules[__name__] = _domain_mod
