"""
Álgebra linear analítica, retas de moldura (waku-sen), interseções e teste ponto-no-painel.
"""

import math
from typing import Dict, Tuple, Optional, Any
import numpy as np
import cv2


def _line_from_points(p1: Tuple[float, float], p2: Tuple[float, float]) -> Tuple[float, float, float]:
    """
    Retorna os coeficientes da reta Ax + By + C = 0 passando por p1 e p2.
    Normalizado de forma que A^2 + B^2 = 1.
    """
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    A = -dy
    B = dx
    norm = math.hypot(A, B)
    if norm < 1e-7:
        return (1.0, 0.0, -x1)
    A /= norm
    B /= norm
    C = -(A * x1 + B * y1)
    return (A, B, C)


def _intersect_lines(l1: Tuple[float, float, float], l2: Tuple[float, float, float]) -> Optional[Tuple[int, int]]:
    """Calcula a interseção entre duas retas Ax + By + C = 0."""
    A1, B1, C1 = l1
    A2, B2, C2 = l2
    det = A1 * B2 - A2 * B1
    if abs(det) < 1e-5:
        return None  # Retas paralelas
    x = (B1 * C2 - B2 * C1) / det
    y = (A2 * C1 - A1 * C2) / det
    return int(round(x)), int(round(y))


def _y_on_line(yl: float, yr: float, x1: float, x2: float, x: float) -> float:
    """Altura (y) no ponto x de uma reta definida por yl (em x1) e yr (em x2)."""
    if x2 == x1:
        return yl
    return yl + (yr - yl) * ((x - x1) / float(x2 - x1))


def _evaluate_line_contrast(
    gray_img: np.ndarray,
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    side: str,
    offset_dist: int = 8,
) -> Tuple[float, float]:
    """
    Avalia a polaridade e o contraste de um segmento de moldura.
    Garante que o lado de fora (calha) seja papel branco/claro e que a linha seja escura.
    Retorna (outside_brightness, contrast_against_line).
    """
    h_img, w_img = gray_img.shape[:2]
    x1, y1 = p1
    x2, y2 = p2

    num_samples = 10
    ts = np.linspace(0.1, 0.9, num_samples)
    xs = x1 + ts * (x2 - x1)
    ys = y1 + ts * (y2 - y1)

    line_vals = []
    outside_vals = []

    for px, py in zip(xs, ys):
        ix = int(round(px))
        iy = int(round(py))
        if 0 <= ix < w_img and 0 <= iy < h_img:
            line_vals.append(float(gray_img[iy, ix]))

            if side == "top":
                ox, oy = ix, iy - offset_dist
            elif side == "bottom":
                ox, oy = ix, iy + offset_dist
            elif side == "left":
                ox, oy = ix - offset_dist, iy
            elif side == "right":
                ox, oy = ix + offset_dist, iy
            else:
                ox, oy = ix, iy

            if 0 <= ox < w_img and 0 <= oy < h_img:
                outside_vals.append(float(gray_img[oy, ox]))

    if not line_vals or not outside_vals:
        return 0.0, 0.0

    mean_line = sum(line_vals) / len(line_vals)
    mean_outside = sum(outside_vals) / len(outside_vals)
    contrast = mean_outside - mean_line
    return mean_outside, contrast


def _detect_boundary_line(
    gray_img: np.ndarray,
    x_range: Tuple[int, int],
    y_range: Tuple[int, int],
    side: str = "vertical",
    min_length_ratio: float = 0.25,
    max_angle_deg: Optional[float] = None,
    orientation: Optional[str] = None,
) -> Optional[Tuple[float, float, float]]:
    """
    Busca uma reta dominante (waku-sen ou calha de papel branco) em uma zona de busca delimitada.
    Valida o contraste, polaridade direcional e suporte ao longo da reta extrapolada para evitar
    falsos positivos inclinados dentro da arte.
    side: 'top', 'bottom', 'left', 'right', ou legado 'vertical'/'horizontal'.
    """
    if orientation is not None:
        side = orientation
    is_vertical = side in ("vertical", "left", "right")

    if max_angle_deg is None:
        max_angle_deg = 22.0 if is_vertical else 10.0
    elif is_vertical:
        max_angle_deg = min(float(max_angle_deg), 22.0)

    h_img, w_img = gray_img.shape[:2]
    x1, x2 = max(0, x_range[0]), min(w_img, x_range[1])
    y1, y2 = max(0, y_range[0]), min(h_img, y_range[1])

    roi_w = x2 - x1
    roi_h = y2 - y1
    if roi_w < 5 or roi_h < 5:
        return None

    roi = gray_img[y1:y2, x1:x2]
    expected_len = roi_h if is_vertical else roi_w
    min_len = max(20, int(expected_len * min_length_ratio))

    # Combina bordas de Canny em escala de cinza e em máscara de branco (calhas de papel puro)
    edges_gray = cv2.Canny(roi, 50, 150)
    white_mask = (roi > 195).astype(np.uint8) * 255
    edges_white = cv2.Canny(white_mask, 100, 200)
    edges = cv2.bitwise_or(edges_gray, edges_white)

    lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi / 180, threshold=25, minLineLength=min_len, maxLineGap=25)

    if lines is None or len(lines) == 0:
        return None

    lines = lines.reshape(-1, 4)
    valid_candidates = []
    max_tan = math.tan(math.radians(max_angle_deg))

    for lx1, ly1, lx2, ly2 in lines:
        dx = lx2 - lx1
        dy = ly2 - ly1
        length = math.hypot(dx, dy)
        if length < min_len:
            continue

        p1_global = (lx1 + x1, ly1 + y1)
        p2_global = (lx2 + x1, ly2 + y1)

        if is_vertical:
            if abs(dy) < 1e-4 or abs(dx / dy) > max_tan:
                continue
            angle_deg = abs(math.degrees(math.atan2(dx, dy)))
            m_inv = dx / float(dy)
            ext_x1 = p1_global[0] + (y1 - p1_global[1]) * m_inv
            ext_x2 = p1_global[0] + (y2 - p1_global[1]) * m_inv
            # Impede extrapolação diagonal selvagem para fora da zona de busca
            if angle_deg > 2.5:
                max_drift = max(70, int(roi_w * 1.8))
                if (ext_x1 < x1 - max_drift or ext_x1 > x2 + max_drift or
                        ext_x2 < x1 - max_drift or ext_x2 > x2 + max_drift):
                    continue
                if length < expected_len * 0.40:
                    continue
            ext_p1 = (int(round(ext_x1)), y1)
            ext_p2 = (int(round(ext_x2)), y2)
        else:
            if abs(dx) < 1e-4 or abs(dy / dx) > max_tan:
                continue
            angle_deg = abs(math.degrees(math.atan2(dy, dx)))
            m = dy / float(dx)
            ext_y1 = p1_global[1] + (x1 - p1_global[0]) * m
            ext_y2 = p1_global[1] + (x2 - p1_global[0]) * m
            if angle_deg > 2.5 and length < expected_len * 0.40:
                continue
            ext_p1 = (x1, int(round(ext_y1)))
            ext_p2 = (x2, int(round(ext_y2)))

        # Avaliação de contraste e brilho na reta (tanto no segmento quanto extrapolada)
        outside_val, contrast = _evaluate_line_contrast(gray_img, p1_global, p2_global, side)
        ext_outside_val, ext_contrast = _evaluate_line_contrast(gray_img, ext_p1, ext_p2, side)

        if angle_deg > 2.5 and side in ("top", "bottom", "left", "right"):
            # Retas inclinadas exigem calha clara real e contraste ao longo de toda a extensão
            if ext_outside_val < 180 or ext_contrast < 20:
                continue

        # Se o lado de fora é calha de papel branco puro (> 180), alta pontuação
        if outside_val > 180 or (outside_val >= 140 and contrast >= 15):
            score = length + (max(0, contrast) * 2.0) + (outside_val * 0.5)
        else:
            score = length * 0.4

        # Bônus de prioridade para molduras ortogonais clássicas
        if angle_deg <= 2.5:
            score *= 1.35

        valid_candidates.append((p1_global, p2_global, score))

    if not valid_candidates:
        return None

    valid_candidates.sort(key=lambda s: s[2], reverse=True)
    best_p1, best_p2, _ = valid_candidates[0]
    return _line_from_points(best_p1, best_p2)


def is_point_in_panel(point: Tuple[float, float], panel: Dict[str, Any], tolerance_px: float = 10.0) -> bool:
    """
    Verifica se um ponto (cx, cy) reside no interior do painel.
    Se o painel possuir 'polygon', realiza teste ponto-polígono com precisão subpixel.
    Caso contrário, avalia os limites do bounding box retangular.
    """
    cx, cy = point
    poly = panel.get("polygon")
    if poly and len(poly) >= 3:
        try:
            cnt = np.array(poly, dtype=np.float32).reshape((-1, 1, 2))
            dist = cv2.pointPolygonTest(cnt, (float(cx), float(cy)), measureDist=True)
            return dist >= -tolerance_px
        except Exception:
            pass

    try:
        bx1, by1, bx2, by2 = panel.get("box", [0, 0, 0, 0])
        return (bx1 - tolerance_px) <= cx <= (bx2 + tolerance_px) and (by1 - tolerance_px) <= cy <= (by2 + tolerance_px)
    except Exception:
        return False
