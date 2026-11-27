"""
Detecção e medição de calhas (gutters) ortogonais, inclinadas (slanted) e perfis de cisalhamento.
"""

import math
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import cv2

from src.geometry.panels.lines import _y_on_line


def detect_slanted_gutter_in_corridor(
    gray_img: np.ndarray,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> Optional[Tuple[float, float, float]]:
    """
    Detecta uma calha inclinada (diagonal) no corredor entre dois painéis adjacentes.
    Filtra ruídos dentro da arte exigindo que a calha seja composta por papel branco
    contínuo ao longo de toda a altura compartilhada.
    Retorna (x_top, x_bottom, angle_deg) ou None.
    """
    h_img, w_img = gray_img.shape[:2]
    x1, x2 = max(0, int(round(x_min))), min(w_img, int(round(x_max)))
    y1, y2 = max(0, int(round(y_min))), min(h_img, int(round(y_max)))
    if x2 - x1 < 10 or y2 - y1 < 60:
        return None

    roi = gray_img[y1:y2, x1:x2]
    white_mask = (roi > 195).astype(np.uint8) * 255
    edges_w = cv2.Canny(white_mask, 100, 200)
    edges_g = cv2.Canny(roi, 50, 150)
    edges = cv2.bitwise_or(edges_w, edges_g)

    min_len = int((y2 - y1) * 0.45)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 30, minLineLength=min_len, maxLineGap=30)
    if lines is None:
        return None

    candidates = []
    mid_corr = (x1 + x2) / 2.0

    for lx1, ly1, lx2, ly2 in lines.reshape(-1, 4):
        dx = lx2 - lx1
        dy = ly2 - ly1
        if abs(dy) < 40:
            continue
        angle = math.degrees(math.atan2(dx, dy))
        if abs(angle) > 25:
            continue

        m = dx / dy
        gx1 = lx1 + x1
        gy1 = ly1 + y1
        xt = gx1 + (y1 - gy1) * m
        xb = gx1 + (y2 - gy1) * m

        # A reta extrapolada não pode sair do corredor de busca entre os dois painéis
        if xt < x1 - 15 or xt > x2 + 15 or xb < x1 - 15 or xb > x2 + 15:
            continue

        # Valida brilho na vizinhança da calha (rejeita traços escuros de arte/desenho)
        num_pts = 20
        ts = np.linspace(0.05, 0.95, num_pts)
        xs = xt + ts * (xb - xt)
        ys = y1 + ts * (y2 - y1)
        bright_samples = 0
        for px, py in zip(xs, ys):
            ix, iy = int(round(px)), int(round(py))
            wx1 = max(0, ix - 6)
            wx2 = min(w_img, ix + 7)
            if wx2 > wx1 and 0 <= iy < h_img:
                if np.max(gray_img[iy, wx1:wx2]) > 200:
                    bright_samples += 1

        whiteness_ratio = bright_samples / float(num_pts)
        if whiteness_ratio < 0.80:
            continue

        length = math.hypot(dx, dy)
        dist_from_mid = abs(((xt + xb) / 2.0) - mid_corr)
        score = length + (whiteness_ratio * 100.0) - (dist_from_mid * 0.5)
        candidates.append((xt, xb, angle, score))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c[3], reverse=True)
    return candidates[0][0], candidates[0][1], candidates[0][2]


def find_horizontal_gutter_row(
    gray_img: np.ndarray,
    y_target: int,
    x_min: int,
    x_max: int,
    search_radius: int = 50,
) -> int:
    """
    Localiza a calha horizontal de papel branco mais brilhante na vizinhança de y_target.
    """
    h_img, w_img = gray_img.shape[:2]
    y_start = max(0, int(y_target - search_radius))
    y_end = min(h_img, int(y_target + search_radius))
    x1 = max(0, int(x_min))
    x2 = min(w_img, int(x_max))
    if x2 - x1 < 20 or y_end - y_start < 5:
        return y_target

    best_y = y_target
    max_brightness = 0.0
    for y in range(y_start, y_end):
        mean_val = float(np.mean(gray_img[y, x1:x2]))
        if mean_val > max_brightness:
            max_brightness = mean_val
            best_y = y

    if max_brightness > 195:
        return best_y
    return y_target


def _shear_profile(
    grad: np.ndarray,
    slope: float,
) -> Tuple[np.ndarray, int]:
    """
    Projeção tipo Radon: cisalha o gradiente vertical `grad` de modo que retas com
    inclinação `slope` (dy/dx) virem horizontais e devolve a média do gradiente
    assinado por linha, mais o índice da primeira linha válida (`lo`).
    """
    h, w = grad.shape
    cols = np.arange(w, dtype=np.float32)
    drift = slope * (w - 1)
    lo = int(math.ceil(max(0.0, -drift)))
    hi = int(math.floor(h - max(0.0, drift))) - 1
    if hi <= lo:
        return np.zeros(h, dtype=np.float32), lo
    ys = np.arange(lo, hi, dtype=np.float32)
    map_x = np.tile(cols, (len(ys), 1))
    map_y = ys[:, None] + slope * cols[None, :]
    sheared = cv2.remap(grad, map_x, map_y.astype(np.float32), cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REPLICATE)
    prof = np.zeros(h, dtype=np.float32)
    row_means = sheared.mean(axis=1)

    # Validação de continuidade horizontal em 8 segmentos (impede falsos picos de sombras/barras parciais)
    n_segs = 8
    if w >= n_segs * 8:
        seg_w = w // n_segs
        trimmed = sheared[:, :seg_w * n_segs].reshape(len(ys), n_segs, seg_w)
        seg_means = trimmed.mean(axis=2)
        same_sign = (seg_means * row_means[:, None] > 0) & (np.abs(seg_means) >= 8.0)
        valid_rows = same_sign.sum(axis=1) >= 7
        row_means = np.where(valid_rows, row_means, 0.0)

    prof[lo:hi] = row_means
    return prof, lo


def _has_gutter_or_frame_band(
    gray_img: np.ndarray,
    yl: float,
    yr: float,
    x1: int,
    x2: int,
    band_half_px: int = 24,
) -> Tuple[bool, float]:
    """
    Verifica se ao longo da reta (yl em x1 -> yr em x2) existe uma calha clara contínua
    (papel branco > 200 em >= 82% das colunas) ou uma linha de moldura escura contínua.
    Retorna (has_white_gutter, white_col_ratio).
    """
    h_img, w_img = gray_img.shape[:2]
    x1, x2 = max(0, int(x1)), min(w_img, int(x2))
    if x2 - x1 < 60:
        return False, 0.0

    xs = np.linspace(x1 + 4, x2 - 5, 60)
    white_cols = 0
    for x in xs:
        yc = int(round(_y_on_line(yl, yr, x1, x2, x)))
        ya = max(0, yc - band_half_px)
        yb = min(h_img, yc + band_half_px + 1)
        if yb > ya:
            col_slice = gray_img[ya:yb, int(x)]
            if np.max(col_slice) >= 202 and np.min(col_slice) <= 135:
                white_cols += 1

    ratio = white_cols / float(len(xs))
    return ratio >= 0.82, ratio


def _find_full_span_lines(
    gray_img: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    max_angle_deg: float = 20.0,
    angle_step: float = 0.75,
    min_strength: float = 45.0,
    scale: float = 0.5,
) -> List[Dict[str, float]]:
    """
    Localiza molduras/calhas quase horizontais (mesmo inclinadas) que atravessam a
    região [x1, x2] de ponta a ponta, via projeção de gradiente cisalhado.
    """
    h_img, w_img = gray_img.shape[:2]
    x1, x2 = max(0, int(x1)), min(w_img, int(x2))
    y1, y2 = max(0, int(y1)), min(h_img, int(y2))
    if x2 - x1 < 100 or y2 - y1 < 60:
        return []

    roi = gray_img[y1:y2, x1:x2].astype(np.float32)
    roi = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    roi = cv2.GaussianBlur(roi, (0, 0), 1.5)
    k = 3
    grad = np.zeros_like(roi)
    grad[k:-k] = roi[2 * k:] - roi[:-2 * k]
    sw = grad.shape[1]

    peaks: List[Tuple[float, float, float, int]] = []
    for ang in np.arange(-max_angle_deg, max_angle_deg + 1e-6, angle_step):
        slope = math.tan(math.radians(ang))
        prof, lo = _shear_profile(grad, slope)
        order = np.argsort(-np.abs(prof))[:3]
        for yy in order:
            if abs(prof[yy]) >= min_strength:
                peaks.append((abs(float(prof[yy])), float(prof[yy]), float(ang), int(yy)))

    peaks.sort(reverse=True)
    found: List[Dict[str, float]] = []
    for strength, signed, ang, yy in peaks:
        slope = math.tan(math.radians(ang))
        yl = yy / scale + y1
        yr = (yy + slope * (sw - 1)) / scale + y1
        if all(abs(yl - f["yl"]) >= 25 or abs(yr - f["yr"]) >= 25 for f in found):
            found.append({
                "yl": yl, "yr": yr, "angle": ang,
                "strength": strength, "signed": signed,
            })
    return found


def _outer_frame_edge(
    gray_img: np.ndarray,
    line: Dict[str, float],
    x1: int,
    x2: int,
    max_thickness: int = 60,
    min_thickness: int = 12,
) -> Dict[str, float]:
    """
    Molduras grossas (madeira entalhada, caixilhos) produzem dois picos de gradiente
    de mesma polaridade: a borda interna (a mais forte) e a externa, que é o limite
    real do painel.
    """
    h_img, w_img = gray_img.shape[:2]
    x1, x2 = max(0, int(x1)), min(w_img, int(x2))
    yl, yr = line["yl"], line["yr"]
    top = int(max(0, min(yl, yr) - max_thickness - 10))
    bot = int(min(h_img, max(yl, yr) + 10))
    if bot - top < 40 or x2 - x1 < 100:
        return line

    sc = 0.5
    roi = cv2.resize(gray_img[top:bot, x1:x2].astype(np.float32), None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
    roi = cv2.GaussianBlur(roi, (0, 0), 1.5)
    grad = np.zeros_like(roi)
    grad[3:-3] = roi[6:] - roi[:-6]

    slope = (yr - yl) / float(x2 - x1)
    prof, _ = _shear_profile(grad, slope)
    inner_row = (yl - top) * sc
    best_row, best_val = None, 0.0
    for d in range(int(min_thickness * sc), int(max_thickness * sc)):
        r = int(round(inner_row - d))
        if 0 <= r < len(prof) and prof[r] * line["signed"] > 0 and abs(prof[r]) > best_val:
            best_row, best_val = r, abs(float(prof[r]))
    if best_row is None or best_val < 0.6 * line["strength"]:
        return line

    outer_yl = best_row / sc + top
    shift = outer_yl - yl
    return {**line, "yl": outer_yl, "yr": yr + shift, "strength": best_val}


def _measure_rectified_white_gutter(
    gray_img: np.ndarray,
    yl: float,
    yr: float,
    x1: int,
    x2: int,
    half_window: int = 36,
) -> Optional[Tuple[int, int]]:
    """
    Retifica uma faixa paralela à reta (yl em x1 -> yr em x2) e verifica se existe
    uma calha contínua de papel branco (espessura 4..45px) ladeada acima e abaixo
    por linhas escuras de moldura (waku-sen).
    Retorna (d_top, d_bot) em pixels relativos à reta, ou None.
    """
    h_img, w_img = gray_img.shape[:2]
    x1, x2 = max(0, int(x1)), min(w_img, int(x2))
    if x2 - x1 < 80:
        return None

    xs = np.linspace(x1 + 10, x2 - 10, 80)
    n_rows = 2 * half_window + 1
    strip = np.full((n_rows, len(xs)), 128.0, dtype=np.float32)

    for col_idx, x in enumerate(xs):
        yc = int(round(_y_on_line(yl, yr, x1, x2, x)))
        ix = int(round(x))
        for d in range(-half_window, half_window + 1):
            yy = yc + d
            if 0 <= yy < h_img and 0 <= ix < w_img:
                strip[d + half_window, col_idx] = float(gray_img[yy, ix])

    is_white = np.zeros(n_rows, dtype=bool)
    for r in range(n_rows):
        row = strip[r]
        if float(np.mean(row)) >= 224.0 and float(np.mean(row >= 215)) >= 0.74:
            is_white[r] = True

    runs: List[Tuple[int, int]] = []
    r = 0
    while r < n_rows:
        if is_white[r]:
            r1 = r
            while r < n_rows and is_white[r]:
                r += 1
            r2 = r - 1
            if 4 <= (r2 - r1 + 1) <= 48:
                runs.append((r1, r2))
        else:
            r += 1

    best_run: Optional[Tuple[int, int]] = None
    best_score = -1.0
    for r1, r2 in runs:
        up_band = strip[max(0, r1 - 14):min(n_rows, r1 + 2), :]
        lo_band = strip[max(0, r2 - 1):min(n_rows, r2 + 15), :]
        if up_band.size == 0 or lo_band.size == 0:
            continue
        up_dark = float(np.mean(np.min(up_band, axis=0) <= 145))
        lo_dark = float(np.mean(np.min(lo_band, axis=0) <= 145))
        if up_dark < 0.55 or lo_dark < 0.55:
            continue
        score = (up_dark + lo_dark) * 100.0 + (r2 - r1 + 1) - abs(0.5 * (r1 + r2) - half_window) * 0.5
        if score > best_score:
            best_score = score
            best_run = (r1 - half_window, r2 - half_window)

    if best_run is not None:
        return best_run

    # Fallback para calha inclinada de moldura dupla (hachura/retícula cinza, ex.: pág. 024)
    row_dark = np.zeros(n_rows, dtype=np.float32)
    row_mean = np.mean(strip, axis=1)
    for r in range(n_rows):
        band = strip[max(0, r - 1):min(n_rows, r + 2), :]
        row_dark[r] = float(np.mean(np.min(band, axis=0) <= 135))

    best_dw: Optional[Tuple[int, int]] = None
    best_dw_score = -1.0
    for r1 in range(2, n_rows - 12):
        if row_dark[r1] < 0.68:
            continue
        for r2 in range(r1 + 10, min(n_rows - 1, r1 + 42)):
            if row_dark[r2] < 0.68:
                continue
            mid_strip = strip[r1 + 2:r2 - 1, :]
            if mid_strip.shape[0] < 4:
                continue
            mid_peak = float(np.max(np.mean(mid_strip, axis=1)))
            mid_mean = float(np.mean(mid_strip))
            edges_mean = 0.5 * float(row_mean[r1] + row_mean[r2])
            col_bright = float(np.mean(np.max(mid_strip, axis=0) >= 155))
            if (mid_peak >= 175.0 and (mid_peak - edges_mean) >= 45.0
                    and (mid_mean - edges_mean) >= 32.0 and col_bright >= 0.85):
                sc = float(row_dark[r1] + row_dark[r2]) * 100.0 + (mid_peak - edges_mean)
                if sc > best_dw_score:
                    best_dw_score = sc
                    best_dw = (r1 + 1 - half_window, r2 - 1 - half_window)
    return best_dw


def _find_orthogonal_horizontal_gutter(
    gray_img: np.ndarray,
    poly: List[List[int]],
    min_thick: int,
) -> Optional[Tuple[int, int]]:
    """
    Procura uma calha horizontal ortogonal de papel branco dentro do polígono `poly`,
    ladeada acima e abaixo por linhas de moldura escuras (waku-sen).
    """
    h_img, w_img = gray_img.shape[:2]
    top_y = int(max(poly[0][1], poly[1][1]) + min_thick)
    bot_y = int(min(poly[2][1], poly[3][1]) - min_thick)
    if bot_y - top_y < 20:
        return None

    def _xl(y: float) -> float:
        dy = poly[3][1] - poly[0][1]
        if abs(dy) < 1e-4:
            return float(poly[0][0])
        return poly[0][0] + (poly[3][0] - poly[0][0]) * ((y - poly[0][1]) / float(dy))

    def _xr(y: float) -> float:
        dy = poly[2][1] - poly[1][1]
        if abs(dy) < 1e-4:
            return float(poly[1][0])
        return poly[1][0] + (poly[2][0] - poly[1][0]) * ((y - poly[1][1]) / float(dy))

    is_white = np.zeros(h_img, dtype=bool)
    for y in range(max(0, top_y), min(h_img, bot_y)):
        xl = max(0, int(round(_xl(y))) + 6)
        xr = min(w_img, int(round(_xr(y))) - 6)
        if xr - xl < 80:
            continue
        row = gray_img[y, xl:xr]
        if float(np.mean(row)) >= 228.0 and float(np.mean(row >= 218)) >= 0.85:
            is_white[y] = True

    runs: List[Tuple[int, int]] = []
    y = max(0, top_y)
    while y < min(h_img, bot_y):
        if is_white[y]:
            y1 = y
            while y < min(h_img, bot_y) and is_white[y]:
                y += 1
            y2 = y - 1
            if 5 <= (y2 - y1 + 1) <= 70:
                runs.append((y1, y2))
        else:
            y += 1

    best_run: Optional[Tuple[int, int]] = None
    best_score = -1.0
    for y1, y2 in runs:
        ym = 0.5 * (y1 + y2)
        xl = max(0, int(round(_xl(ym))) + 8)
        xr = min(w_img, int(round(_xr(ym))) - 8)
        if xr - xl < 80:
            continue

        up_band = gray_img[max(0, y1 - 14):min(h_img, y1 + 2), xl:xr]
        lo_band = gray_img[max(0, y2 - 1):min(h_img, y2 + 15), xl:xr]
        if up_band.size == 0 or lo_band.size == 0:
            continue

        up_dark_ratio = float(np.mean(np.min(up_band, axis=0) <= 145))
        lo_dark_ratio = float(np.mean(np.min(lo_band, axis=0) <= 145))
        if up_dark_ratio < 0.58 or lo_dark_ratio < 0.58:
            continue

        score = (up_dark_ratio + lo_dark_ratio) * 100.0 + (y2 - y1 + 1)
        if score > best_score:
            best_score = score
            best_run = (y1, y2)

    if best_run is not None:
        return best_run

    # Fallback para calha horizontal de moldura dupla (flashback/hachura cinza, ex.: pág. 017)
    y_lo = max(0, top_y)
    y_hi = min(h_img, bot_y)
    if y_hi - y_lo >= 20:
        row_dark: Dict[int, float] = {}
        row_dark_l: Dict[int, float] = {}
        row_dark_r: Dict[int, float] = {}
        row_mean: Dict[int, float] = {}
        for y in range(y_lo, y_hi):
            xl = max(0, int(round(_xl(y))) + 8)
            xr = min(w_img, int(round(_xr(y))) - 8)
            if xr - xl < 120:
                continue
            band = gray_img[max(0, y - 1):min(h_img, y + 2), xl:xr]
            if band.size == 0:
                continue
            col_min = np.min(band, axis=0)
            xm = (xl + xr) // 2 - xl
            row_dark[y] = float(np.mean(col_min <= 135))
            row_dark_l[y] = float(np.mean(col_min[:xm] <= 135)) if xm > 10 else 0.0
            row_dark_r[y] = float(np.mean(col_min[xm:] <= 135)) if (xr - xl - xm) > 10 else 0.0
            row_mean[y] = float(np.mean(band))

        best_hw_pair: Optional[Tuple[int, int]] = None
        best_hw_score = -1.0
        for y1 in range(y_lo, y_hi - 10):
            if row_dark.get(y1, 0.0) < 0.68 or row_dark_l.get(y1, 0.0) < 0.60 or row_dark_r.get(y1, 0.0) < 0.55:
                continue
            for y2 in range(y1 + 10, min(y_hi, y1 + 44)):
                if row_dark.get(y2, 0.0) < 0.68 or row_dark_l.get(y2, 0.0) < 0.60 or row_dark_r.get(y2, 0.0) < 0.55:
                    continue
                ym = 0.5 * (y1 + y2)
                xl = max(0, int(round(_xl(ym))) + 8)
                xr = min(w_img, int(round(_xr(ym))) - 8)
                mid_strip = gray_img[y1 + 2:y2 - 1, xl:xr]
                if mid_strip.size == 0 or mid_strip.shape[0] < 4:
                    continue
                row_means = np.mean(mid_strip, axis=1)
                mid_peak = float(np.max(row_means))
                mid_mean = float(np.mean(mid_strip))
                edges_mean = 0.5 * (row_mean[y1] + row_mean[y2])
                col_bright_ratio = float(np.mean(np.max(mid_strip, axis=0) >= 155))
                if (mid_peak >= 175.0 and (mid_peak - edges_mean) >= 45.0
                        and (mid_mean - edges_mean) >= 32.0 and col_bright_ratio >= 0.88):
                    sc = (row_dark[y1] + row_dark[y2]) * 100.0 + (mid_peak - edges_mean)
                    if sc > best_hw_score:
                        best_hw_score = sc
                        best_hw_pair = (y1 + 1, y2 - 1)
        if best_hw_pair is not None:
            return best_hw_pair

    return None


def _find_vertical_gutter_in_poly(
    gray_img: np.ndarray,
    poly: List[List[int]],
    min_thick_x: int,
    panel_bubbles: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Tuple[float, float, float, float]]:
    """
    Procura uma calha vertical (ortogonal ou levemente inclinada) dentro do polígono `poly`,
    ladeada à esquerda e à direita por linhas de moldura escuras (waku-sen).
    Retorna (xt_left, xb_left, xt_right, xb_right) nas bordas superior e inferior de `poly`, ou None.
    """
    h_img, w_img = gray_img.shape[:2]
    left_x = int(max(poly[0][0], poly[3][0]) + min_thick_x)
    right_x = int(min(poly[1][0], poly[2][0]) - min_thick_x)
    if right_x - left_x < 20:
        return None

    def _yt(x: float) -> float:
        dx = poly[1][0] - poly[0][0]
        return float(poly[0][1]) if abs(dx) < 1e-4 else poly[0][1] + (poly[1][1] - poly[0][1]) * ((x - poly[0][0]) / float(dx))

    def _yb(x: float) -> float:
        dx = poly[2][0] - poly[3][0]
        return float(poly[3][1]) if abs(dx) < 1e-4 else poly[3][1] + (poly[2][1] - poly[3][1]) * ((x - poly[3][0]) / float(dx))

    # 1. Busca ortogonal rápida
    is_white = np.zeros(w_img, dtype=bool)
    for x in range(max(0, left_x), min(w_img, right_x)):
        yt = max(0, int(round(_yt(x))) + 6)
        yb = min(h_img, int(round(_yb(x))) - 6)
        if yb - yt < 80:
            continue
        col = gray_img[yt:yb, x]
        if float(np.mean(col)) >= 228.0 and float(np.mean(col >= 218)) >= 0.84:
            is_white[x] = True

    runs: List[Tuple[int, int]] = []
    x = max(0, left_x)
    while x < min(w_img, right_x):
        if is_white[x]:
            x1 = x
            while x < min(w_img, right_x) and is_white[x]:
                x += 1
            x2 = x - 1
            if 5 <= (x2 - x1 + 1) <= 65:
                runs.append((x1, x2))
        else:
            x += 1

    best_run: Optional[Tuple[int, int]] = None
    best_score = -1.0
    for x1, x2 in runs:
        xm = 0.5 * (x1 + x2)
        yt = max(0, int(round(_yt(xm))) + 8)
        yb = min(h_img, int(round(_yb(xm))) - 8)
        if yb - yt < 80:
            continue
        l_band = gray_img[yt:yb, max(0, x1 - 14):min(w_img, x1 + 2)]
        r_band = gray_img[yt:yb, max(0, x2 - 1):min(w_img, x2 + 15)]
        if l_band.size == 0 or r_band.size == 0:
            continue
        l_dark = float(np.mean(np.min(l_band, axis=1) <= 145))
        r_dark = float(np.mean(np.min(r_band, axis=1) <= 145))
        if l_dark < 0.58 or r_dark < 0.58:
            continue
        score = (l_dark + r_dark) * 100.0 + (x2 - x1 + 1)
        if score > best_score:
            best_score = score
            best_run = (x1, x2)

    if best_run is not None:
        x1, x2 = best_run
        return float(x1 - 2), float(x1 - 2), float(x2 + 2), float(x2 + 2)

    # 2. Se houver balões separados por corredor X dentro do painel, busca calha vertical
    if panel_bubbles and len(panel_bubbles) >= 2:
        x_int = sorted((b["x1"], b["x2"]) for b in panel_bubbles)
        gaps = []
        max_end = x_int[0][1]
        for cur_s, cur_e in x_int[1:]:
            if cur_s > max_end + 12:
                g1, g2 = max(left_x, max_end), min(right_x, cur_s)
                if g2 > g1:
                    gaps.append((g2 - g1, g1, g2))
            max_end = max(max_end, cur_e)
        for _, gx1, gx2 in sorted(gaps, key=lambda g: g[0], reverse=True):
            xm = 0.5 * (gx1 + gx2)
            yt = max(0, int(round(_yt(xm))) + 8)
            yb = min(h_img, int(round(_yb(xm))) - 8)
            if yb - yt < 100:
                continue

            # 2a. Calha vertical ortogonal de moldura dupla
            sx1 = max(left_x - 20, int(gx1) - 16)
            sx2 = min(right_x + 20, int(gx2) + 16)
            if sx2 - sx1 >= 10:
                wall_dark = {}
                wall_dark_t = {}
                wall_dark_b = {}
                wall_mean = {}
                ymid = (yt + yb) // 2 - yt
                for x in range(sx1, sx2 + 1):
                    band = gray_img[yt:yb, max(0, x - 1):min(w_img, x + 2)]
                    if band.size > 0:
                        rmin = np.min(band, axis=1)
                        wall_dark[x] = float(np.mean(rmin <= 135))
                        wall_dark_t[x] = float(np.mean(rmin[:ymid] <= 135)) if ymid > 10 else 0.0
                        wall_dark_b[x] = float(np.mean(rmin[ymid:] <= 135)) if (yb - yt - ymid) > 10 else 0.0
                        wall_mean[x] = float(np.mean(band))
                best_pair: Optional[Tuple[int, int]] = None
                best_pair_score = -1.0
                for xl in range(sx1, sx2 - 7):
                    if (wall_dark.get(xl, 0.0) < 0.65
                            or wall_dark_t.get(xl, 0.0) < 0.55
                            or wall_dark_b.get(xl, 0.0) < 0.55):
                        continue
                    for xr in range(xl + 8, min(sx2 + 1, xl + 45)):
                        if (wall_dark.get(xr, 0.0) < 0.65
                                or wall_dark_t.get(xr, 0.0) < 0.55
                                or wall_dark_b.get(xr, 0.0) < 0.55):
                            continue
                        mid_strip = gray_img[yt:yb, xl + 2:xr - 1]
                        if mid_strip.size == 0 or mid_strip.shape[1] < 2:
                            continue
                        mid_peak = float(np.max(np.mean(mid_strip, axis=0)))
                        mid_mean = float(np.mean(mid_strip))
                        edges_mean = 0.5 * (wall_mean[xl] + wall_mean[xr])
                        if (mid_peak >= 145.0 and (mid_peak - edges_mean) >= 35.0
                                and (mid_mean - edges_mean) >= 18.0):
                            sc = (wall_dark[xl] + wall_dark[xr]) * 100.0 + (mid_peak - edges_mean)
                            if sc > best_pair_score:
                                best_pair_score = sc
                                best_pair = (xl, xr)
                if best_pair is not None:
                    xl, xr = best_pair
                    return float(xl - 2), float(xl - 2), float(xr + 2), float(xr + 2)

            # 2b. Calha vertical inclinada de papel branco
            cx1 = max(left_x - 30, gx1 - 45)
            cx2 = min(right_x + 30, gx2 + 45)
            sg = detect_slanted_gutter_in_corridor(gray_img, cx1, cx2, yt, yb)
            if sg is not None:
                xt, xb, _ = sg
                rect = _measure_rectified_white_gutter(gray_img.T, xt, xb, yt, yb, half_window=24)
                if rect is not None:
                    d1, d2 = rect
                    return float(xt + d1 - 2), float(xb + d1 - 2), float(xt + d2 + 2), float(xb + d2 + 2)

            # 2c. Calha vertical inclinada de moldura dupla
            sx1_v = max(left_x - 40, int(gx1) - 85)
            sx2_v = min(right_x + 40, int(gx2) + 85)
            if sx2_v - sx1_v >= 28:
                v_cands = _find_full_span_lines(
                    gray_img.T, yt, sx1_v, yb, sx2_v, max_angle_deg=18.0, min_strength=35.0
                )
                for vc in v_cands:
                    xt, xb = vc["yl"], vc["yr"]
                    rect = _measure_rectified_white_gutter(gray_img.T, xt, xb, yt, yb, half_window=36)
                    if rect is not None:
                        d1, d2 = rect
                        return float(xt + d1 - 2), float(xb + d1 - 2), float(xt + d2 + 2), float(xb + d2 + 2)

    return None


def _gutter_offset_below_edge(
    gray_img: np.ndarray,
    yl: float,
    yr: float,
    x1: float,
    x2: float,
    sample_x1: float,
    sample_x2: float,
    default: int = 16,
) -> int:
    """
    Mede quantos pixels abaixo de uma borda inclinada (yl em x1, yr em x2) termina
    a calha clara e começa a arte do painel vizinho. Retorna `default` se o perfil
    de brilho não for conclusivo.
    """
    h_img, w_img = gray_img.shape[:2]
    xs = np.linspace(max(0, sample_x1), min(w_img - 1, sample_x2), 40)
    max_d = 60
    profile = np.zeros(max_d, dtype=np.float32)
    for d in range(max_d):
        vals = []
        for x in xs:
            y = int(round(_y_on_line(yl, yr, x1, x2, x))) + d
            if 0 <= y < h_img:
                vals.append(float(gray_img[y, int(x)]))
        profile[d] = sum(vals) / len(vals) if vals else 0.0

    smooth = np.convolve(profile, np.ones(5) / 5.0, mode="same")
    peak_d = int(np.argmax(smooth[:45]))
    peak_v = float(smooth[peak_d])
    tail = smooth[peak_d:]
    if tail.size < 6:
        return default
    dark_v = float(np.min(tail))
    if peak_v - dark_v < 25:
        return default
    thr = (peak_v + dark_v) / 2.0
    for d in range(peak_d, max_d):
        if smooth[d] < thr:
            return int(max(12, min(42, d)))
    return default
