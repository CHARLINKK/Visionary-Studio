"""
Divisão de quadros gigantes (split_oversized_panels), limpeza de invasões e resgate de painéis omitidos.
"""

import math
from typing import List, Dict, Optional, Any
import numpy as np
import cv2
from PIL import Image

from src.geometry.panels.lines import _y_on_line, is_point_in_panel
from src.geometry.panels.gutters import (
    _has_gutter_or_frame_band,
    _find_full_span_lines,
    _outer_frame_edge,
    _measure_rectified_white_gutter,
    _find_orthogonal_horizontal_gutter,
    _find_vertical_gutter_in_poly,
    _gutter_offset_below_edge,
)


def split_oversized_panels(
    image: Image.Image,
    panels: List[Dict[str, Any]],
    min_area_ratio: float = 0.40,
    max_depth: int = 3,
    min_strength: float = 45.0,
    min_slant_deg: float = 5.0,
    bubbles: Optional[List[Dict[str, Any]]] = None,
    gray_image: Optional[np.ndarray] = None,
) -> List[Dict[str, Any]]:
    """
    Divide painéis que o YOLO fundiu em um só, guiado e confirmado pelos balões (quando disponíveis):
      1. Calhas brancas horizontais ortogonais ladeadas por moldura (waku-sen).
      2. Calhas brancas verticais (ortogonais ou levemente inclinadas) que separam colunas de balões.
      3. Calhas brancas inclinadas ou molduras diagonais duplas (ex.: pág. 032 e pág. 014).
    """
    if not panels:
        return panels
    if bubbles is not None and len(bubbles) <= 1:
        return panels

    gray_np = gray_image if gray_image is not None else np.array(image.convert("L"))
    img_h, img_w = gray_np.shape[:2]
    page_area = float(img_w * img_h)
    min_thick = max(80, int(img_h * 0.05))
    min_thick_x = max(80, int(img_w * 0.06))

    def _ipt(x: float, y: float) -> List[int]:
        return [int(round(max(0, min(img_w, x)))), int(round(max(0, min(img_h, y))))]

    def _make(panel: Dict[str, Any], sub_poly: List[List[int]], source: str) -> Dict[str, Any]:
        xs = [pt[0] for pt in sub_poly]
        ys = [pt[1] for pt in sub_poly]
        new_box = [min(xs), min(ys), max(xs), max(ys)]
        item = dict(panel)
        item["polygon"] = sub_poly
        item["box"] = new_box
        item["area"] = (new_box[2] - new_box[0]) * (new_box[3] - new_box[1])
        item["source"] = source
        return item

    def _bubbles_in(sub_poly: List[List[int]]) -> List[Dict[str, Any]]:
        if not bubbles:
            return []
        temp_p = {
            "polygon": sub_poly,
            "box": [
                min(pt[0] for pt in sub_poly),
                min(pt[1] for pt in sub_poly),
                max(pt[0] for pt in sub_poly),
                max(pt[1] for pt in sub_poly),
            ],
        }
        found = []
        for b in bubbles:
            cx = 0.5 * (b["x1"] + b["x2"])
            cy = 0.5 * (b["y1"] + b["y2"])
            if is_point_in_panel((cx, cy), temp_p, tolerance_px=15.0):
                found.append(b)
        return found

    def _confirm_split(poly_a: List[List[int]], poly_b: List[List[int]], allow_single_side_action: bool = True) -> bool:
        if not bubbles:
            return True
        ba = _bubbles_in(poly_a)
        bb = _bubbles_in(poly_b)
        if len(ba) >= 1 and len(bb) >= 1:
            return True
        if allow_single_side_action and (len(ba) + len(bb)) >= 1:
            area_a = float(cv2.contourArea(np.array(poly_a, dtype=np.float32)))
            area_b = float(cv2.contourArea(np.array(poly_b, dtype=np.float32)))
            if min(area_a, area_b) >= page_area * 0.10:
                return True
        return False

    def _split(panel: Dict[str, Any], depth: int) -> List[Dict[str, Any]]:
        poly = panel.get("polygon")
        box = panel.get("box", [0, 0, 0, 0])
        bx1, by1, bx2, by2 = box
        if depth >= max_depth or not poly or len(poly) != 4:
            return [panel]
        panel_area = (bx2 - bx1) * (by2 - by1)
        if panel_area < page_area * 0.08:
            return [panel]

        def _xl(y: float) -> float:
            dy = poly[3][1] - poly[0][1]
            return float(poly[0][0]) if abs(dy) < 1e-4 else poly[0][0] + (poly[3][0] - poly[0][0]) * ((y - poly[0][1]) / float(dy))

        def _xr(y: float) -> float:
            dy = poly[2][1] - poly[1][1]
            return float(poly[1][0]) if abs(dy) < 1e-4 else poly[1][0] + (poly[2][0] - poly[1][0]) * ((y - poly[1][1]) / float(dy))

        def _yt(x: float) -> float:
            dx = poly[1][0] - poly[0][0]
            return float(poly[0][1]) if abs(dx) < 1e-4 else poly[0][1] + (poly[1][1] - poly[0][1]) * ((x - poly[0][0]) / float(dx))

        def _yb(x: float) -> float:
            dx = poly[2][0] - poly[3][0]
            return float(poly[3][1]) if abs(dx) < 1e-4 else poly[3][1] + (poly[2][1] - poly[3][1]) * ((x - poly[3][0]) / float(dx))

        src = panel.get("source", "yolo")
        p_bubbles = _bubbles_in(poly)

        # 1. Tenta corte ortogonal por calha branca horizontal real
        ortho_gutter = _find_orthogonal_horizontal_gutter(gray_np, poly, min_thick)
        if ortho_gutter is not None:
            y_g1, y_g2 = ortho_gutter
            u_y = float(y_g1 - 2)
            l_y = float(y_g2 + 2)
            upper_poly = [list(poly[0]), list(poly[1]), _ipt(_xr(u_y), u_y), _ipt(_xl(u_y), u_y)]
            lower_poly = [_ipt(_xl(l_y), l_y), _ipt(_xr(l_y), l_y), list(poly[2]), list(poly[3])]
            if _confirm_split(upper_poly, lower_poly, allow_single_side_action=True):
                return _split(_make(panel, upper_poly, src), depth + 1) + _split(_make(panel, lower_poly, src), depth + 1)

        # 2. Tenta corte por calha branca vertical
        if (bx2 - bx1) >= img_w * 0.38:
            v_gutter = _find_vertical_gutter_in_poly(gray_np, poly, min_thick_x, panel_bubbles=p_bubbles)
            if v_gutter is not None:
                xt_l, xb_l, xt_r, xb_r = v_gutter
                left_poly = [list(poly[0]), _ipt(xt_l, _yt(xt_l)), _ipt(xb_l, _yb(xb_l)), list(poly[3])]
                right_poly = [_ipt(xt_r, _yt(xt_r)), list(poly[1]), list(poly[2]), _ipt(xb_r, _yb(xb_r))]
                if _confirm_split(left_poly, right_poly, allow_single_side_action=False):
                    return _split(_make(panel, right_poly, src), depth + 1) + _split(_make(panel, left_poly, src), depth + 1)

        # 3. Corte diagonal (calha branca inclinada real ou moldura dupla de espelho)
        if panel_area < page_area * min_area_ratio:
            return [panel]

        px1 = (poly[0][0] + poly[3][0]) / 2.0
        px2 = (poly[1][0] + poly[2][0]) / 2.0
        top_l, top_r = poly[0][1], poly[1][1]
        bot_l, bot_r = poly[3][1], poly[2][1]

        cands = _find_full_span_lines(
            gray_np, int(px1), int(min(top_l, top_r)), int(px2), int(max(bot_l, bot_r)),
            min_strength=min_strength,
        )
        valid = []
        for c in cands:
            if abs(c["angle"]) < min_slant_deg:
                continue
            yl, yr = c["yl"], c["yr"]
            if (yl - top_l >= min_thick and yr - top_r >= min_thick
                    and bot_l - yl >= min_thick and bot_r - yr >= min_thick):
                valid.append(c)

        # 3a. Verifica se algum candidato inclinado é uma calha de papel branco real ladeada por waku-sen
        for cand in valid:
            rect = _measure_rectified_white_gutter(gray_np, cand["yl"], cand["yr"], int(px1), int(px2))
            if rect is not None:
                d1, d2 = rect
                u_yl, u_yr = cand["yl"] + d1 - 2, cand["yr"] + d1 - 2
                l_yl, l_yr = cand["yl"] + d2 + 2, cand["yr"] + d2 + 2
                upper_poly = [list(poly[0]), list(poly[1]), _ipt(_xr(u_yr), u_yr), _ipt(_xl(u_yl), u_yl)]
                lower_poly = [_ipt(_xl(l_yl), l_yl), _ipt(_xr(l_yr), l_yr), list(poly[2]), list(poly[3])]
                if _confirm_split(upper_poly, lower_poly, allow_single_side_action=True):
                    return _split(_make(panel, upper_poly, src), depth + 1) + _split(_make(panel, lower_poly, src), depth + 1)

        # 3a-partial: Se um elemento gráfico (buchi-nuki) interrompe um terço da calha diagonal
        if (px2 - px1) >= img_w * 0.75:
            allow_single_action = panel_area >= page_area * 0.58
            partial_spans = [
                (int(px1 + 0.35 * (px2 - px1)), int(px2)),
                (int(px1), int(px1 + 0.65 * (px2 - px1))),
            ]
            for sub_x1, sub_x2 in partial_spans:
                cands_p = _find_full_span_lines(
                    gray_np, sub_x1, int(min(top_l, top_r)), sub_x2, int(max(bot_l, bot_r)),
                    min_strength=70.0,
                )
                for cr in cands_p:
                    if abs(cr["angle"]) < min_slant_deg:
                        continue
                    slope = (cr["yr"] - cr["yl"]) / float(max(1, sub_x2 - sub_x1))
                    yl_full = cr["yl"] - slope * (sub_x1 - px1)
                    yr_full = cr["yr"] + slope * (px2 - sub_x2)
                    if not (yl_full - top_l >= min_thick and yr_full - top_r >= min_thick
                            and bot_l - yl_full >= min_thick and bot_r - yr_full >= min_thick):
                        continue
                    rect = _measure_rectified_white_gutter(gray_np, cr["yl"], cr["yr"], sub_x1, sub_x2)
                    if rect is not None:
                        d1, d2 = rect
                        u_yl, u_yr = yl_full + d1 - 2, yr_full + d1 - 2
                        l_yl, l_yr = yl_full + d2 + 2, yr_full + d2 + 2
                        upper_poly = [list(poly[0]), list(poly[1]), _ipt(_xr(u_yr), u_yr), _ipt(_xl(u_yl), u_yl)]
                        lower_poly = [_ipt(_xl(l_yl), l_yl), _ipt(_xr(l_yr), l_yr), list(poly[2]), list(poly[3])]
                        if _confirm_split(upper_poly, lower_poly, allow_single_side_action=allow_single_action):
                            return _split(_make(panel, upper_poly, src), depth + 1) + _split(_make(panel, lower_poly, src), depth + 1)

        if not valid:
            return [panel]

        # 3b. Moldura dupla acompanhada de base inclinada
        best_cand = max(valid, key=lambda c: c["strength"])
        line = _outer_frame_edge(gray_np, best_cand, int(px1), int(px2))
        yl_line, yr_line = line["yl"], line["yr"]
        has_double_molding = abs(yl_line - best_cand["yl"]) >= 10.0

        new_bot_l, new_bot_r = bot_l, bot_r
        below = _find_full_span_lines(
            gray_np, int(px1), int(min(yl_line, yr_line)), int(px2),
            int(min(img_h, max(bot_l, bot_r) + 90)),
            min_strength=min_strength,
        )
        below = [
            c for c in below
            if c["yl"] - yl_line >= min_thick and c["yr"] - yr_line >= min_thick
            and max(c["yl"], c["yr"]) >= max(bot_l, bot_r) - 65
            and (c["yl"] + c["yr"]) / 2.0 <= max(bot_l, bot_r) + 90
        ]
        has_slanted_bottom_companion = False
        if below:
            nxt = min(below, key=lambda c: c["yl"] + c["yr"])
            has_bot_gutter, _ = _has_gutter_or_frame_band(gray_np, nxt["yl"], nxt["yr"], int(px1), int(px2))
            if has_bot_gutter or abs(nxt["angle"]) >= 4.0:
                new_bot_l, new_bot_r = nxt["yl"], nxt["yr"]
                has_slanted_bottom_companion = True

        if not (has_double_molding and has_slanted_bottom_companion):
            return [panel]

        upper_poly = [
            list(poly[0]), list(poly[1]),
            _ipt(poly[1][0], yr_line - 2), _ipt(poly[0][0], yl_line - 2),
        ]
        lower_poly = [
            _ipt(poly[0][0], yl_line + 2), _ipt(poly[1][0], yr_line + 2),
            _ipt(poly[2][0], new_bot_r), _ipt(poly[3][0], new_bot_l),
        ]
        if not _confirm_split(upper_poly, lower_poly, allow_single_side_action=True):
            return [panel]

        return _split(_make(panel, upper_poly, "frame_split"), depth + 1) + _split(_make(panel, lower_poly, "frame_split"), depth + 1)

    result: List[Dict[str, Any]] = []
    for p in panels:
        result.extend(_split(p, 0))
    return result


def _clear_panel_invasions(
    image: Image.Image,
    panels: List[Dict[str, Any]],
    gray_image: Optional[np.ndarray] = None,
) -> List[Dict[str, Any]]:
    """
    Garante que a borda superior de um painel não invada a área do painel que está
    acima dele quando este possui base inclinada: a borda superior do painel de baixo
    passa a seguir a base inclinada do painel de cima, acrescida da calha medida.
    """
    gray_np = gray_image if gray_image is not None else np.array(image.convert("L"))
    n = len(panels)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            up = panels[i].get("polygon")
            lo = panels[j].get("polygon")
            if not up or not lo or len(up) != 4 or len(lo) != 4:
                continue

            up_cy = sum(pt[1] for pt in up) / 4.0
            lo_cy = sum(pt[1] for pt in lo) / 4.0
            if up_cy >= lo_cy:
                continue

            u_x1 = (up[0][0] + up[3][0]) / 2.0
            u_x2 = (up[1][0] + up[2][0]) / 2.0
            l_x1 = (lo[0][0] + lo[3][0]) / 2.0
            l_x2 = (lo[1][0] + lo[2][0]) / 2.0
            u_w = max(1.0, u_x2 - u_x1)
            l_w = max(1.0, l_x2 - l_x1)
            ov_x1 = max(u_x1, l_x1)
            ov_x2 = min(u_x2, l_x2)
            ov_x = ov_x2 - ov_x1
            # Exige que pertençam à mesma coluna vertical
            if ov_x < 30 or ov_x / min(u_w, l_w) < 0.50:
                continue

            u_yl, u_yr = float(up[3][1]), float(up[2][1])  # base do painel de cima (BL, BR)
            if abs(u_yr - u_yl) < 25.0:
                continue
            if min(lo[0][1], lo[1][1]) < min(u_yl, u_yr) - 60:
                continue

            invaded = False
            for idx in (0, 1):
                vx, vy = lo[idx]
                if u_x1 - 15 <= vx <= u_x2 + 15 and _y_on_line(u_yl, u_yr, u_x1, u_x2, vx) + 2 > vy:
                    invaded = True
            if not invaded:
                continue

            d = _gutter_offset_below_edge(gray_np, u_yl, u_yr, u_x1, u_x2, ov_x1, ov_x2)
            lo_bottom = min(lo[2][1], lo[3][1])
            for idx in (0, 1):
                vx = max(u_x1, min(u_x2, lo[idx][0]))
                new_y = int(round(_y_on_line(u_yl, u_yr, u_x1, u_x2, vx) + d))
                if new_y < lo_bottom - 120:
                    lo[idx][1] = new_y
            xs = [pt[0] for pt in lo]
            ys = [pt[1] for pt in lo]
            panels[j]["box"] = [min(xs), min(ys), max(xs), max(ys)]
    return panels


def _fit_trapezoid_to_component_mask(
    mask: np.ndarray,
    img_w: int,
    img_h: int,
    allow_slant: bool = True,
) -> Optional[List[List[int]]]:
    """
    Ajusta um polígono de 4 vértices [TL, TR, BR, BL] à máscara binária de um quadro
    resgatado, preservando bordas superior/inferior inclinadas quando `allow_slant=True`.
    """
    ys_all, xs_all = np.nonzero(mask)
    if len(xs_all) < 50:
        return None

    col_counts = np.count_nonzero(mask, axis=0)
    max_c = int(np.max(col_counts)) if col_counts.size > 0 else 0
    valid_cols_mask = np.where(col_counts >= max(30, int(max_c * 0.45)))[0]
    if len(valid_cols_mask) < 30:
        return None
    x1 = int(valid_cols_mask[0])
    x2 = int(valid_cols_mask[-1])
    w = x2 - x1
    if w < 30:
        return None

    if not allow_slant:
        y1, y2 = int(ys_all.min()), int(ys_all.max())
        return [
            [max(0, min(img_w, x1)), max(0, min(img_h, y1))],
            [max(0, min(img_w, x2)), max(0, min(img_h, y1))],
            [max(0, min(img_w, x2)), max(0, min(img_h, y2))],
            [max(0, min(img_w, x1)), max(0, min(img_h, y2))],
        ]

    margin_x = max(4, int(w * 0.10))
    sample_cols = np.arange(x1 + margin_x, x2 - margin_x + 1, max(1, (w - 2 * margin_x) // 30))
    if len(sample_cols) < 4:
        sample_cols = np.arange(x1, x2 + 1)

    top_ys = []
    bot_ys = []
    valid_cols = []
    for cx in sample_cols:
        col_y = np.nonzero(mask[:, cx])[0]
        if len(col_y) >= 10:
            valid_cols.append(float(cx))
            top_ys.append(float(col_y[0]))
            bot_ys.append(float(col_y[-1]))

    if len(valid_cols) < 4:
        y1, y2 = int(ys_all.min()), int(ys_all.max())
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    vc = np.array(valid_cols, dtype=np.float64)
    m_top, b_top = np.polyfit(vc, np.array(top_ys, dtype=np.float64), 1)
    m_bot, b_bot = np.polyfit(vc, np.array(bot_ys, dtype=np.float64), 1)

    if abs(math.degrees(math.atan(m_top))) < 2.0:
        tl_y = tr_y = int(round(float(np.median(top_ys))))
    else:
        tl_y = int(round(m_top * x1 + b_top))
        tr_y = int(round(m_top * x2 + b_top))

    if abs(math.degrees(math.atan(m_bot))) < 2.0:
        bl_y = br_y = int(round(float(np.median(bot_ys))))
    else:
        bl_y = int(round(m_bot * x1 + b_bot))
        br_y = int(round(m_bot * x2 + b_bot))

    poly = [
        [max(0, min(img_w, x1)), max(0, min(img_h, tl_y))],
        [max(0, min(img_w, x2)), max(0, min(img_h, tr_y))],
        [max(0, min(img_w, x2)), max(0, min(img_h, br_y))],
        [max(0, min(img_w, x1)), max(0, min(img_h, bl_y))],
    ]
    return poly


def rescue_uncovered_panels(
    image: Image.Image,
    panels: List[Dict[str, Any]],
    min_area_ratio: float = 0.026,
    min_ink_ratio: float = 0.12,
    bubbles: Optional[List[Dict[str, Any]]] = None,
    gray_image: Optional[np.ndarray] = None,
) -> List[Dict[str, Any]]:
    """
    Resgata quadros que o YOLO não detectou: regiões grandes, sólidas e com tinta dentro
    do envelope dos painéis que nenhum polígono cobre.
    """
    if not panels:
        return panels

    gray_np = gray_image if gray_image is not None else np.array(image.convert("L"))
    img_h, img_w = gray_np.shape[:2]
    polys = [p["polygon"] for p in panels if p.get("polygon") and len(p["polygon"]) >= 3]
    if not polys:
        return panels

    has_frame_split = any(p.get("source") == "frame_split" for p in panels)

    # Identifica balões órfãos (centro não contido em nenhum painel existente)
    orphan_bubbles: List[Dict[str, Any]] = []
    if bubbles is not None and len(bubbles) > 0:
        for b in bubbles:
            bcx = 0.5 * float(b.get("x1", 0) + b.get("x2", 0))
            bcy = 0.5 * float(b.get("y1", 0) + b.get("y2", 0))
            if not any(is_point_in_panel((bcx, bcy), p, tolerance_px=15.0) for p in panels):
                orphan_bubbles.append(b)
        if not orphan_bubbles and not has_frame_split:
            return panels

    all_pts = np.array([pt for poly in polys for pt in poly], dtype=np.int32)
    env_x1, env_y1 = int(all_pts[:, 0].min()), int(all_pts[:, 1].min())
    env_x2, env_y2 = int(all_pts[:, 0].max()), int(all_pts[:, 1].max())
    if orphan_bubbles:
        for ob in orphan_bubbles:
            env_x1 = min(env_x1, max(0, int(ob.get("x1", 0)) - 120))
            env_y1 = min(env_y1, max(0, int(ob.get("y1", 0)) - 160))
            env_x2 = max(env_x2, min(img_w - 1, int(ob.get("x2", 0)) + 120))
            env_y2 = max(env_y2, min(img_h - 1, int(ob.get("y2", 0)) + 160))
        if env_y1 <= int(img_h * 0.28):
            env_y1 = 0
        if env_y2 >= int(img_h * 0.72):
            env_y2 = img_h - 1
    env_y2 = max(env_y2, img_h - 1) if env_y2 >= img_h - 20 else env_y2

    cover = np.zeros((img_h, img_w), dtype=np.uint8)
    for poly in polys:
        cv2.fillPoly(cover, [np.array(poly, dtype=np.int32).reshape((-1, 1, 2))], 255)

    cover_buffered = cv2.dilate(cover, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    cover_buffered = cv2.morphologyEx(cover_buffered, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (45, 15)))
    for poly in polys:
        pxs = [pt[0] for pt in poly]
        pys = [pt[1] for pt in poly]
        px1, px2 = min(pxs), max(pxs)
        py1, py2 = max(0, min(pys) - 7), min(img_h, max(pys) + 7)
        if px1 <= int(img_w * 0.08):
            cover_buffered[py1:py2, 0:px1] = 255
        if px2 >= int(img_w * 0.92):
            cover_buffered[py1:py2, px2:img_w] = 255

    free = np.zeros((img_h, img_w), dtype=np.uint8)
    free[env_y1:env_y2, env_x1:env_x2] = 255
    free[cover_buffered > 0] = 0

    k_size = min(65, max(31, int(min(img_w, img_h) * 0.042)))
    if k_size % 2 == 0:
        k_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
    opened = cv2.morphologyEx(free, cv2.MORPH_OPEN, kernel)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    page_area = float(img_w * img_h)
    new_panels: List[Dict[str, Any]] = []

    for lbl in range(1, n_labels):
        x, y, w, h, area = stats[lbl]
        solidity = float(area) / float(max(1, w * h))
        if area < page_area * min_area_ratio or w < img_w * 0.15 or h < img_h * 0.12:
            continue

        if bubbles is not None and len(bubbles) > 0 and not has_frame_split:
            has_orphan = any(
                (x - 25) <= 0.5 * (ob.get("x1", 0) + ob.get("x2", 0)) <= (x + w + 25)
                and (y - 25) <= 0.5 * (ob.get("y1", 0) + ob.get("y2", 0)) <= (y + h + 25)
                for ob in orphan_bubbles
            )
            if not has_orphan:
                continue

        if solidity < 0.68:
            continue

        mask = (labels == lbl)
        ink_ratio = float(np.count_nonzero(gray_np[mask] < 220)) / float(area)
        if ink_ratio < min_ink_ratio:
            continue

        poly = _fit_trapezoid_to_component_mask(mask, img_w, img_h, allow_slant=has_frame_split)
        if not poly:
            continue

        for p_exist in panels:
            ep = p_exist.get("polygon")
            if not ep or len(ep) != 4:
                continue
            ey1 = min(ep[0][1], ep[1][1])
            ey2 = max(ep[2][1], ep[3][1])
            ex1 = min(ep[0][0], ep[3][0])
            ex2 = max(ep[1][0], ep[2][0])

            r_y1 = min(poly[0][1], poly[1][1])
            r_y2 = max(poly[2][1], poly[3][1])
            r_x1 = min(poly[0][0], poly[3][0])
            r_x2 = max(poly[1][0], poly[2][0])

            y_overlap = min(r_y2, ey2) - max(r_y1, ey1)
            x_overlap = min(r_x2, ex2) - max(r_x1, ex1)

            if y_overlap >= 80:
                e_left_top, e_left_bot = ep[0][0], ep[3][0]
                e_right_top, e_right_bot = ep[1][0], ep[2][0]
                if r_x1 < max(e_right_top, e_right_bot) + 16 and r_x2 > max(e_right_top, e_right_bot) + 80:
                    poly[0][0] = max(poly[0][0], e_right_top + 16)
                    poly[3][0] = max(poly[3][0], e_right_bot + 16)
                elif r_x2 > min(e_left_top, e_left_bot) - 16 and r_x1 < min(e_left_top, e_left_bot) - 80:
                    poly[1][0] = min(poly[1][0], e_left_top - 16)
                    poly[2][0] = min(poly[2][0], e_left_bot - 16)

            r_x1 = min(poly[0][0], poly[3][0])
            r_x2 = max(poly[1][0], poly[2][0])
            x_overlap = min(r_x2, ex2) - max(r_x1, ex1)

            if x_overlap >= 80 and y_overlap < 50:
                e_top_l, e_top_r = ep[0][1], ep[1][1]
                e_bot_l, e_bot_r = ep[3][1], ep[2][1]
                if r_y1 < max(e_bot_l, e_bot_r) + 16 and r_y2 > max(e_bot_l, e_bot_r) + 80:
                    poly[0][1] = max(poly[0][1], e_bot_l + 16)
                    poly[1][1] = max(poly[1][1], e_bot_r + 16)
                elif r_y2 > min(e_top_l, e_top_r) - 16 and r_y1 < min(e_top_l, e_top_r) - 80:
                    poly[2][1] = min(poly[2][1], e_top_r - 16)
                    poly[3][1] = min(poly[3][1], e_top_l - 16)

        poly_xs = [pt[0] for pt in poly]
        poly_ys = [pt[1] for pt in poly]
        if max(poly_xs) - min(poly_xs) < img_w * 0.12 or max(poly_ys) - min(poly_ys) < img_h * 0.10:
            continue

        poly_mask = np.zeros((img_h, img_w), dtype=np.uint8)
        cv2.fillPoly(poly_mask, [np.array(poly, dtype=np.int32).reshape((-1, 1, 2))], 255)
        poly_px = max(1, np.count_nonzero(poly_mask))
        overlap_px = np.count_nonzero((poly_mask > 0) & (cover > 0))
        if overlap_px / float(poly_px) > 0.05:
            continue

        xs = [pt[0] for pt in poly]
        ys = [pt[1] for pt in poly]
        new_panels.append({
            "box": [min(xs), min(ys), max(xs), max(ys)],
            "area": int(area),
            "conf": 0.5,
            "polygon": [[int(px), int(py)] for px, py in poly],
            "source": "uncovered_rescue",
        })

    return panels + new_panels
