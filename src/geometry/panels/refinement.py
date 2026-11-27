"""
Refinamento poligonal individual, reconciliação bidirecional de calhas entre vizinhos
e pipeline completo de refinamento de quadros (refine_panels_to_polygons).
"""

from typing import List, Dict, Optional, Any
import numpy as np
import cv2
from PIL import Image

from src.geometry.panels.lines import (
    _intersect_lines,
    _detect_boundary_line,
    _y_on_line,
)
from src.geometry.panels.gutters import (
    detect_slanted_gutter_in_corridor,
    find_horizontal_gutter_row,
)
from src.geometry.panels.splitting_and_rescue import (
    split_oversized_panels,
    _clear_panel_invasions,
    rescue_uncovered_panels,
)


def refine_panel_polygon(
    image: Image.Image,
    box: List[int],
    margin_bleed_px: int = 15,
    gray_image: Optional[np.ndarray] = None,
) -> List[List[int]]:
    """
    Refina a caixa delimitadora ortogonal [x1, y1, x2, y2] de um único painel,
    ajustando seus 4 lados para as linhas pretas (waku-sen) ou calhas da página.
    Retorna uma lista de 4 vértices ordenados: [Top-Left, Top-Right, Bottom-Right, Bottom-Left].
    """
    img_w, img_h = image.width, image.height
    bx1, by1, bx2, by2 = box
    bw = bx2 - bx1
    bh = by2 - by1

    default_poly = [[bx1, by1], [bx2, by1], [bx2, by2], [bx1, by2]]
    if bw < 20 or bh < 20:
        return default_poly

    gray_np = gray_image if gray_image is not None else np.array(image.convert("L"))

    pad_inward_y = min(32, max(15, int(bh * 0.05)))
    pad_inward_x = min(40, max(20, int(bw * 0.05)))

    # 1. Linha SUPERIOR (Top)
    if by1 <= margin_bleed_px:
        line_top = (0.0, 1.0, 0.0)  # y = 0
    else:
        y_search_top = (max(0, by1 - max(50, pad_inward_y)), min(img_h, by1 + pad_inward_y))
        detected = _detect_boundary_line(
            gray_np,
            x_range=(bx1, bx2),
            y_range=y_search_top,
            side="top",
            max_angle_deg=10.0,
        )
        line_top = detected if detected else (0.0, 1.0, -float(by1))

    # 2. Linha INFERIOR (Bottom)
    if by2 >= img_h - margin_bleed_px:
        line_bottom = (0.0, 1.0, -float(img_h))  # y = img_h
    else:
        y_search_bottom = (max(0, by2 - pad_inward_y), min(img_h, by2 + max(60, pad_inward_y)))
        detected = _detect_boundary_line(
            gray_np,
            x_range=(bx1, bx2),
            y_range=y_search_bottom,
            side="bottom",
            max_angle_deg=10.0,
        )
        line_bottom = detected if detected else (0.0, 1.0, -float(by2))

    # 3. Linha ESQUERDA (Left)
    if bx1 <= margin_bleed_px:
        line_left = (1.0, 0.0, 0.0)  # x = 0
    else:
        x_search_left = (max(0, bx1 - 35), min(img_w, bx1 + max(50, pad_inward_x)))
        detected = _detect_boundary_line(
            gray_np,
            x_range=x_search_left,
            y_range=(by1, by2),
            side="left",
            max_angle_deg=22.0,
        )
        line_left = detected if detected else (1.0, 0.0, -float(bx1))

    # 4. Linha DIREITA (Right)
    if bx2 >= img_w - margin_bleed_px:
        line_right = (1.0, 0.0, -float(img_w))  # x = img_w
    else:
        x_search_right = (max(0, bx2 - max(50, pad_inward_x)), min(img_w, bx2 + 35))
        detected = _detect_boundary_line(
            gray_np,
            x_range=x_search_right,
            y_range=(by1, by2),
            side="right",
            max_angle_deg=22.0,
        )
        line_right = detected if detected else (1.0, 0.0, -float(bx2))

    # Calcula as 4 interseções
    pt_tl = _intersect_lines(line_top, line_left)
    pt_tr = _intersect_lines(line_top, line_right)
    pt_br = _intersect_lines(line_bottom, line_right)
    pt_bl = _intersect_lines(line_bottom, line_left)

    if not (pt_tl and pt_tr and pt_br and pt_bl):
        return default_poly

    candidate_poly = [
        [max(0, min(img_w, pt_tl[0])), max(0, min(img_h, pt_tl[1]))],
        [max(0, min(img_w, pt_tr[0])), max(0, min(img_h, pt_tr[1]))],
        [max(0, min(img_w, pt_br[0])), max(0, min(img_h, pt_br[1]))],
        [max(0, min(img_w, pt_bl[0])), max(0, min(img_h, pt_bl[1]))],
    ]

    cnt = np.array(candidate_poly, dtype=np.int32).reshape((-1, 1, 2))
    if not cv2.isContourConvex(cnt):
        return default_poly

    orig_area = float(bw * bh)
    poly_area = cv2.contourArea(cnt)
    if poly_area < orig_area * 0.60 or poly_area > orig_area * 1.40:
        return default_poly

    return candidate_poly


def _reconcile_panel_gutters(
    panels: List[Dict[str, Any]],
    image: Optional[Image.Image] = None,
    gray_image: Optional[np.ndarray] = None,
) -> List[Dict[str, Any]]:
    """
    Reconciliação estrutural e não-destrutiva de calhas entre painéis vizinhos:
    1. Agrupa painéis em Tiers horizontais estritos (mesma faixa vertical e sem sobreposição X).
    2. Identifica e ajusta calhas diagonais/inclinadas entre painéis adjacentes lado a lado.
    3. Impede invasões espúrias entre Tiers adjacentes mantendo a calha limpa.
    """
    if not panels:
        return []

    if gray_image is not None:
        gray_np = gray_image
    elif image is not None:
        gray_np = np.array(image.convert("L"))
    else:
        gray_np = None
    h_img = gray_np.shape[0] if gray_np is not None else (max(p["box"][3] for p in panels) if panels else 1000)
    w_img = gray_np.shape[1] if gray_np is not None else (max(p["box"][2] for p in panels) if panels else 1000)

    # 1. Agrupamento estrito em Tiers horizontais
    sorted_p = sorted(panels, key=lambda p: (p["box"][1], p["box"][0]))
    tiers = []
    used = [False] * len(sorted_p)

    for i, p in enumerate(sorted_p):
        if used[i]:
            continue
        tier = [p]
        used[i] = True

        for j in range(i + 1, len(sorted_p)):
            if used[j]:
                continue
            b_j = sorted_p[j]["box"]
            w_j = max(1, b_j[2] - b_j[0])
            h_j = max(1, b_j[3] - b_j[1])

            can_join = True
            for member in tier:
                b_m = member["box"]
                w_m = max(1, b_m[2] - b_m[0])
                h_m = max(1, b_m[3] - b_m[1])
                overlap_y = max(0, min(b_m[3], b_j[3]) - max(b_m[1], b_j[1]))
                overlap_x = max(0, min(b_m[2], b_j[2]) - max(b_m[0], b_j[0]))
                if overlap_y / float(max(h_m, h_j)) <= 0.55 or overlap_x / float(min(w_m, w_j)) >= 0.25:
                    can_join = False
                    break

            if can_join:
                tier.append(sorted_p[j])
                used[j] = True
        tiers.append(tier)

    # 2. Refinamento de calhas dentro de cada Tier
    for tier in tiers:
        tier_boxes = [p["box"] for p in tier]
        tier.sort(key=lambda p: p["box"][0])

        raw_top = min(b[1] for b in tier_boxes)
        raw_bot = max(b[3] for b in tier_boxes)
        min_x = min(b[0] for b in tier_boxes)
        max_x = max(b[2] for b in tier_boxes)

        if gray_np is not None:
            tier_top = 0 if raw_top <= 20 else find_horizontal_gutter_row(gray_np, raw_top, min_x, max_x, search_radius=40)
            tier_bot = h_img if raw_bot >= h_img - 20 else find_horizontal_gutter_row(gray_np, raw_bot, min_x, max_x, search_radius=60)
        else:
            tier_top = raw_top
            tier_bot = raw_bot

        for p in tier:
            poly = p.get("polygon")
            if poly and len(poly) == 4:
                if abs(poly[0][1] - tier_top) < 80:
                    poly[0][1] = tier_top
                if abs(poly[1][1] - tier_top) < 80:
                    poly[1][1] = tier_top
                if abs(tier_bot - poly[2][1]) < 95:
                    poly[2][1] = tier_bot
                if abs(tier_bot - poly[3][1]) < 95:
                    poly[3][1] = tier_bot

        if len(tier) > 1 and gray_np is not None:
            for k in range(len(tier) - 1):
                p_left = tier[k]
                p_right = tier[k + 1]

                if p_left["box"][2] > p_right["box"][0] + 140:
                    continue

                left_edge = min(p_left["box"][2], p_right["box"][0])
                right_edge = max(p_left["box"][2], p_right["box"][0])
                if right_edge - left_edge > 160:
                    continue

                mid = (left_edge + right_edge) / 2.0
                half_span = min(75.0, max(40.0, (right_edge - left_edge) / 2.0 + 35.0))
                cx1 = max(0, mid - half_span)
                cx2 = min(w_img, mid + half_span)

                gutter = detect_slanted_gutter_in_corridor(gray_np, cx1, cx2, tier_top, tier_bot)
                if gutter:
                    top_x, bot_x, _ = gutter
                    gutter_w = 16
                    half_w = gutter_w / 2.0

                    poly_l = p_left.get("polygon")
                    poly_r = p_right.get("polygon")
                    if poly_l and len(poly_l) == 4 and poly_r and len(poly_r) == 4:
                        new_l_tr = int(round(top_x - half_w))
                        new_l_br = int(round(bot_x - half_w))
                        new_r_tl = int(round(top_x + half_w))
                        new_r_bl = int(round(bot_x + half_w))
                        if (new_l_tr - poly_l[0][0] >= 80 and new_l_br - poly_l[3][0] >= 80
                                and poly_r[1][0] - new_r_tl >= 80 and poly_r[2][0] - new_r_bl >= 80):
                            poly_l[1][0] = new_l_tr
                            poly_l[2][0] = new_l_br
                            poly_r[0][0] = new_r_tl
                            poly_r[3][0] = new_r_bl
                else:
                    poly_l = p_left.get("polygon")
                    poly_r = p_right.get("polygon")
                    if poly_l and len(poly_l) == 4 and poly_r and len(poly_r) == 4:
                        if poly_l[1][0] >= poly_r[0][0] - 12 and (poly_r[0][0] - 20 - poly_l[0][0]) >= 80:
                            poly_l[1][0] = poly_r[0][0] - 20
                        if poly_l[2][0] >= poly_r[3][0] - 12 and (poly_r[3][0] - 20 - poly_l[3][0]) >= 80:
                            poly_l[2][0] = poly_r[3][0] - 20

    # 3. Reconciliação lateral entre colunas de alturas diferentes
    n = len(panels)
    if gray_np is not None:
        for i in range(n):
            for j in range(i + 1, n):
                p_l, p_r = panels[i], panels[j]
                b_l, b_r = p_l["box"], p_r["box"]
                if (b_l[0] + b_l[2]) / 2.0 > (b_r[0] + b_r[2]) / 2.0:
                    p_l, p_r = p_r, p_l
                    b_l, b_r = b_r, b_l

                poly_l = p_l.get("polygon")
                poly_r = p_r.get("polygon")
                if not poly_l or not poly_r or len(poly_l) != 4 or len(poly_r) != 4:
                    continue

                h_l = max(1, b_l[3] - b_l[1])
                h_r = max(1, b_r[3] - b_r[1])
                sy1 = max(b_l[1], b_r[1])
                sy2 = min(b_l[3], b_r[3])
                ov_y = sy2 - sy1
                if ov_y < 120 or ov_y / float(min(h_l, h_r)) < 0.65:
                    continue
                if b_l[0] >= b_r[0] - 80 or b_r[2] <= b_l[2] + 80:
                    continue
                if abs(b_l[2] - b_r[0]) > 220:
                    continue

                mid = 0.5 * (b_l[2] + b_r[0])
                half_span = min(120.0, max(50.0, abs(b_l[2] - b_r[0]) * 0.6 + 40.0))
                cx1 = max(0.0, mid - half_span)
                cx2 = min(float(w_img), mid + half_span)

                gutter = detect_slanted_gutter_in_corridor(gray_np, cx1, cx2, sy1, sy2)
                if gutter:
                    top_x, bot_x, _ = gutter
                    half_w = 8.0
                    if abs(poly_l[1][1] - sy1) <= 50 and int(round(top_x - half_w)) - poly_l[0][0] >= 80:
                        poly_l[1][0] = int(round(top_x - half_w))
                    if abs(poly_l[2][1] - sy2) <= 50 and int(round(bot_x - half_w)) - poly_l[3][0] >= 80:
                        poly_l[2][0] = int(round(bot_x - half_w))
                    if abs(poly_r[0][1] - sy1) <= 50 and poly_r[1][0] - int(round(top_x + half_w)) >= 80:
                        poly_r[0][0] = int(round(top_x + half_w))
                    if abs(poly_r[3][1] - sy2) <= 50 and poly_r[2][0] - int(round(bot_x + half_w)) >= 80:
                        poly_r[3][0] = int(round(bot_x + half_w))
                else:
                    if abs(poly_l[1][1] - sy1) <= 50 and abs(poly_r[0][1] - sy1) <= 50 and poly_l[1][0] > poly_r[0][0] - 12:
                        if poly_r[0][0] - 16 - poly_l[0][0] >= 80:
                            poly_l[1][0] = poly_r[0][0] - 16
                    if abs(poly_l[2][1] - sy2) <= 50 and abs(poly_r[3][1] - sy2) <= 50 and poly_l[2][0] > poly_r[3][0] - 12:
                        if poly_r[3][0] - 16 - poly_l[3][0] >= 80:
                            poly_l[2][0] = poly_r[3][0] - 16

    # 4. Reconciliação vertical entre Tiers/Painéis empilhados adjacentes
    for i in range(n):
        for j in range(i + 1, n):
            pa, pb = panels[i], panels[j]
            if pa["box"][1] > pb["box"][1]:
                pa, pb = pb, pa
            poly_a = pa.get("polygon")
            poly_b = pb.get("polygon")
            if not poly_a or not poly_b or len(poly_a) != 4 or len(poly_b) != 4:
                continue

            box_a = pa["box"]
            box_b = pb["box"]
            w_a = max(1, box_a[2] - box_a[0])
            w_b = max(1, box_b[2] - box_b[0])
            x_overlap = max(0, min(box_a[2], box_b[2]) - max(box_a[0], box_b[0]))

            if (gray_np is not None and x_overlap / float(min(w_a, w_b)) >= 0.65
                    and box_a[1] < box_b[1] - 180 and box_b[3] > box_a[3] + 180
                    and 40 <= box_a[3] - box_b[1] <= 280):
                gx1 = max(box_a[0], box_b[0])
                gx2 = min(box_a[2], box_b[2])
                gy1 = max(0, box_b[1] - 30)
                gy2 = min(h_img, box_a[3] + 30)
                h_gutter = detect_slanted_gutter_in_corridor(gray_np.T, gy1, gy2, gx1, gx2)
                if h_gutter:
                    yl_g, yr_g, _ = h_gutter
                    half_w = 8.0
                    a_x1, a_x2 = poly_a[3][0], poly_a[2][0]
                    b_x1, b_x2 = poly_b[0][0], poly_b[1][0]
                    new_a_bl = int(round(_y_on_line(yl_g, yr_g, gx1, gx2, a_x1) - half_w))
                    new_a_br = int(round(_y_on_line(yl_g, yr_g, gx1, gx2, a_x2) - half_w))
                    new_b_tl = int(round(_y_on_line(yl_g, yr_g, gx1, gx2, b_x1) + half_w))
                    new_b_tr = int(round(_y_on_line(yl_g, yr_g, gx1, gx2, b_x2) + half_w))
                    if (new_a_bl - poly_a[0][1] >= 80 and new_a_br - poly_a[1][1] >= 80
                            and poly_b[3][1] - new_b_tl >= 80 and poly_b[2][1] - new_b_tr >= 80):
                        poly_a[3][1] = new_a_bl
                        poly_a[2][1] = new_a_br
                        poly_b[0][1] = new_b_tl
                        poly_b[1][1] = new_b_tr
                        pa["box"] = [min(pt[0] for pt in poly_a), min(pt[1] for pt in poly_a), max(pt[0] for pt in poly_a), max(pt[1] for pt in poly_a)]
                        pb["box"] = [min(pt[0] for pt in poly_b), min(pt[1] for pt in poly_b), max(pt[0] for pt in poly_b), max(pt[1] for pt in poly_b)]
                        continue

            if x_overlap > 40 and box_a[1] < box_b[1] - 120 and box_a[3] <= box_b[1] + 95 and box_b[3] > box_a[3] + 120:
                a_bot = max(poly_a[2][1], poly_a[3][1])
                b_top = min(poly_b[0][1], poly_b[1][1])
                has_horiz_gutter = False
                if gray_np is not None:
                    gx1, gx2 = max(0, max(box_a[0], box_b[0])), min(w_img, min(box_a[2], box_b[2]))
                    gy1, gy2 = max(0, a_bot - 8), min(h_img, a_bot + 28)
                    if gx2 - gx1 >= 40 and gy2 > gy1:
                        band = gray_np[gy1:gy2, gx1:gx2]
                        has_horiz_gutter = bool(np.max(np.mean(band, axis=1)) >= 210.0)
                if abs(poly_a[2][1] - poly_a[3][1]) <= 15 and b_top < a_bot - 15 and has_horiz_gutter:
                    new_b_top = a_bot + 18
                    if box_b[3] - new_b_top >= 120:
                        poly_b[0][1] = max(poly_b[0][1], new_b_top)
                        poly_b[1][1] = max(poly_b[1][1], new_b_top)
                        pb["box"] = [
                            min(pt[0] for pt in poly_b),
                            min(pt[1] for pt in poly_b),
                            max(pt[0] for pt in poly_b),
                            max(pt[1] for pt in poly_b),
                        ]
                elif box_a[3] <= box_b[1] + 45:
                    for idx_a in (2, 3):  # BR, BL de A
                        for idx_b in (0, 1):  # TL, TR de B
                            if poly_a[idx_a][1] > poly_b[idx_b][1] - 12:
                                mid_y = int((poly_a[idx_a][1] + poly_b[idx_b][1]) / 2)
                                poly_a[idx_a][1] = min(poly_a[idx_a][1], mid_y - 8)
                                poly_b[idx_b][1] = max(poly_b[idx_b][1], mid_y + 8)

    # 5. Alinhamento colinear de quadros empilhados contra vizinho de página inteira com borda inclinada
    for i in range(n):
        p_tall = panels[i]
        poly_t = p_tall.get("polygon")
        if not poly_t or len(poly_t) != 4:
            continue
        t_y1 = min(poly_t[0][1], poly_t[1][1])
        t_y2 = max(poly_t[2][1], poly_t[3][1])
        if t_y2 - t_y1 < h_img * 0.75:
            continue
        rx_top, ry_top = float(poly_t[1][0]), float(poly_t[1][1])
        rx_bot, ry_bot = float(poly_t[2][0]), float(poly_t[2][1])
        if abs(rx_bot - rx_top) < 25.0 or ry_bot - ry_top < 200.0 or max(rx_top, rx_bot) > w_img * 0.80:
            continue

        def _x_right_tall(y_val: float) -> float:
            return rx_top + (rx_bot - rx_top) * ((y_val - ry_top) / float(ry_bot - ry_top))

        for j in range(n):
            if i == j:
                continue
            p_sub = panels[j]
            poly_s = p_sub.get("polygon")
            if not poly_s or len(poly_s) != 4:
                continue
            s_y1, s_y2 = float(poly_s[0][1]), float(poly_s[3][1])
            if s_y2 - s_y1 >= (t_y2 - t_y1) * 0.85:
                continue
            exp_tl_x = _x_right_tall(s_y1) + 16.0
            exp_bl_x = _x_right_tall(s_y2) + 16.0
            if (abs(poly_s[0][0] - exp_tl_x) <= 180.0
                    and abs(poly_s[3][0] - exp_bl_x) <= 180.0
                    and poly_s[1][0] - exp_tl_x >= 120.0
                    and poly_s[2][0] - exp_bl_x >= 120.0):
                poly_s[0][0] = int(round(exp_tl_x))
                poly_s[3][0] = int(round(exp_bl_x))
                p_sub["box"] = [
                    min(pt[0] for pt in poly_s),
                    min(pt[1] for pt in poly_s),
                    max(pt[0] for pt in poly_s),
                    max(pt[1] for pt in poly_s),
                ]

    # Atualiza bounding boxes dos polígonos reconciliados
    for p in panels:
        poly = p.get("polygon")
        if poly and len(poly) == 4:
            p["box"] = [
                min(pt[0] for pt in poly),
                min(pt[1] for pt in poly),
                max(pt[0] for pt in poly),
                max(pt[1] for pt in poly),
            ]

    return panels


def refine_panels_to_polygons(
    image: Image.Image,
    panels: List[Dict[str, Any]],
    bubbles: Optional[List[Dict[str, Any]]] = None,
    gray_image: Optional[np.ndarray] = None,
) -> List[Dict[str, Any]]:
    """
    Processa a lista de painéis detectados, calculando o polígono exato para cada um.
    Preserva todos os metadados existentes e injeta o campo 'polygon'.
    """
    if not panels:
        return []

    gray_np = gray_image if gray_image is not None else np.array(image.convert("L"))

    refined = []
    for p in panels:
        p_copy = dict(p)
        box = p.get("box", [0, 0, 0, 0])
        if "polygon" in p_copy and len(p_copy["polygon"]) > 4:
            refined.append(p_copy)
            continue

        poly = refine_panel_polygon(image, box, gray_image=gray_np)
        p_copy["polygon"] = poly
        refined.append(p_copy)

    # Reconciliação estrutural e calhas entre vizinhos
    refined = _reconcile_panel_gutters(refined, image=image, gray_image=gray_np)

    # Pós-processamento estrutural (divisão, invasões e resgate de quadros órfãos)
    try:
        refined = split_oversized_panels(image, refined, bubbles=bubbles, gray_image=gray_np)
        refined = _clear_panel_invasions(image, refined, gray_image=gray_np)
        before_rescue = len(refined)
        refined = rescue_uncovered_panels(image, refined, bubbles=bubbles, gray_image=gray_np)
        if len(refined) > before_rescue:
            refined = split_oversized_panels(image, refined, min_area_ratio=0.08, bubbles=bubbles, gray_image=gray_np)
    except Exception:
        # Falha no pós-processamento nunca deve derrubar o pipeline de layout
        pass
    return refined
