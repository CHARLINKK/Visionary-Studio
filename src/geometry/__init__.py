"""
Visionary Studio — Computational Geometry Package.
Morfologia de balões, cálculo de IoU, fusão de caixas e refinamento poligonal de painéis.
"""

from src.geometry.bubble_geometry import (
    _detect_panels_opencv,
    _extract_single_bubble_polygon,
    _has_multiline_typeset_structure,
    _iou,
    _merge_bubbles,
    _merge_panels,
    _refine_bubble_box,
    _validate_bubble_morphology,
    extract_bubble_polygons,
    is_clean_white_bubble,
    is_sfx_morphology,
)
from src.geometry.panels import (
    detect_slanted_gutter_in_corridor,
    find_horizontal_gutter_row,
    is_point_in_panel,
    refine_panel_polygon,
    refine_panels_to_polygons,
    rescue_uncovered_panels,
    split_oversized_panels,
)

__all__ = [
    "_iou",
    "_merge_bubbles",
    "_merge_panels",
    "_detect_panels_opencv",
    "_refine_bubble_box",
    "_validate_bubble_morphology",
    "_has_multiline_typeset_structure",
    "is_clean_white_bubble",
    "is_sfx_morphology",
    "_extract_single_bubble_polygon",
    "extract_bubble_polygons",
    "is_point_in_panel",
    "detect_slanted_gutter_in_corridor",
    "find_horizontal_gutter_row",
    "split_oversized_panels",
    "rescue_uncovered_panels",
    "refine_panel_polygon",
    "refine_panels_to_polygons",
]
