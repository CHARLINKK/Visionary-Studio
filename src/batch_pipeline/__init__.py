"""Pacote de componentes modulares do pipeline de processamento em lote."""

from .session import (
    _cancel_event,
    _rollback_flag,
    _session_backups,
    _session_outputs,
    _pipeline_lock,
    request_cancel,
    backup_file,
    execute_rollback,
)
from .geometry import (
    _calc_text_margin,
    extract_perspective_crop,
    deduplicate_spatial_regions,
)
from .scanner import (
    get_natural_sorted_images,
    filter_cached_images,
)
from .glossary_builder import (
    build_custom_instructions,
)
from .layout_runner import (
    load_existing_layout,
    run_layout_detection,
    run_deep_validation,
)
from .ocr_runner import (
    run_ocr_phase,
)
from .translation_runner import (
    run_translation_phase,
)

__all__ = [
    "_cancel_event",
    "_rollback_flag",
    "_session_backups",
    "_session_outputs",
    "_pipeline_lock",
    "request_cancel",
    "backup_file",
    "execute_rollback",
    "_calc_text_margin",
    "extract_perspective_crop",
    "deduplicate_spatial_regions",
    "get_natural_sorted_images",
    "filter_cached_images",
    "build_custom_instructions",
    "load_existing_layout",
    "run_layout_detection",
    "run_deep_validation",
    "run_ocr_phase",
    "run_translation_phase",
]
