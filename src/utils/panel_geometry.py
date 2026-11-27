"""
Backwards-compatibility facade for `src.utils.panel_geometry`.
Canonical implementation lives in `src.geometry.panels` (`lines`, `gutters`, `splitting_and_rescue`, `refinement`).
"""

import sys
import src.geometry.panels as _panels_mod
from src.geometry.panels import (  # noqa: F401
    _clear_panel_invasions,
    _detect_boundary_line,
    _evaluate_line_contrast,
    _find_full_span_lines,
    _find_orthogonal_horizontal_gutter,
    _find_vertical_gutter_in_poly,
    _fit_trapezoid_to_component_mask,
    _gutter_offset_below_edge,
    _has_gutter_or_frame_band,
    _intersect_lines,
    _line_from_points,
    _measure_rectified_white_gutter,
    _outer_frame_edge,
    _reconcile_panel_gutters,
    _shear_profile,
    _y_on_line,
    detect_slanted_gutter_in_corridor,
    find_horizontal_gutter_row,
    is_point_in_panel,
    refine_panel_polygon,
    refine_panels_to_polygons,
    rescue_uncovered_panels,
    split_oversized_panels,
)

sys.modules[__name__] = _panels_mod
