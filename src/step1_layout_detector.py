"""
Fachada de retrocompatibilidade para `src.step1_layout_detector`.
A implementação canônica reside em `src.model_engines.yolo_layout_engine`.
"""

import sys
import src.model_engines.yolo_layout_engine as _yolo_mod
from src.model_engines.yolo_layout_engine import (  # noqa: F401
    YoloMapeador,
    _detect_panels_blind_master,
    _iou,
    _merge_bubbles,
    _merge_panels,
    _detect_panels_opencv,
    _refine_bubble_box,
    _validate_bubble_morphology,
    _has_multiline_typeset_structure,
    is_clean_white_bubble,
    is_sfx_morphology,
    extract_bubble_polygons,
    refine_panels_to_polygons,
)

sys.modules[__name__] = _yolo_mod
