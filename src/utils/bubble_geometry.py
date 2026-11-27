"""
Fachada de retrocompatibilidade para src.geometry.bubble_geometry.
Mantém 100% dos imports legados e alvos de monkeypatch funcionando sem quebra.
"""

import sys
import src.geometry.bubble_geometry as _geom_mod
from src.geometry.bubble_geometry import (  # noqa: F401
    _iou,
    _merge_bubbles,
    _merge_panels,
    _detect_panels_opencv,
    _refine_bubble_box,
    _validate_bubble_morphology,
    _has_multiline_typeset_structure,
    is_clean_white_bubble,
    is_sfx_morphology,
    _extract_single_bubble_polygon,
    extract_bubble_polygons,
)

sys.modules[__name__] = _geom_mod
