import cv2
import numpy as np
from PIL import Image


def _iou(boxA, boxB):
    """Calcula Intersection over Union (IoU) entre duas caixas no formato [x1, y1, x2, y2]."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0:
        return 0.0

    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    return interArea / float(boxAArea + boxBArea - interArea)


def _merge_bubbles(
    boxes: list[dict],
    iou_threshold=0.10,
    containment_threshold=0.40,
    image: Image.Image = None,
    gray_image: np.ndarray = None,
) -> list[dict]:
    """
    Funde iterativamente caixas de balões sobrepostas ou contidas.
    Caixas fundidas assumem o bounding box de união.
    """
    if gray_image is not None:
        gray_np = gray_image
    elif image is not None:
        gray_np = np.array(image.convert("L"))
    else:
        gray_np = None
    changed = True
    while changed:
        changed = False
        merged_boxes = []
        used = [False] * len(boxes)

        # Caixas mais confiantes ancoram a fusão para não herdar rótulo de detecção ruidosa
        boxes = sorted(boxes, key=lambda b: b.get("confidence", 0), reverse=True)

        for i, a in enumerate(boxes):
            if used[i]:
                continue
            current = dict(a)

            for j, b in enumerate(boxes):
                if i == j or used[j]:
                    continue

                ax1, ay1, ax2, ay2 = current["x1"], current["y1"], current["x2"], current["y2"]
                bx1, by1, bx2, by2 = b["x1"], b["y1"], b["x2"], b["y2"]

                ix1, iy1 = max(ax1, bx1), max(ay1, by1)
                ix2, iy2 = min(ax2, bx2), min(ay2, by2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)

                area_a = (ax2 - ax1) * (ay2 - ay1)
                area_b = (bx2 - bx1) * (by2 - by1)

                should_merge = False
                if inter > 0:
                    union = area_a + area_b - inter
                    iou = inter / union if union > 0 else 0
                    containment = inter / min(area_a, area_b) if min(area_a, area_b) > 0 else 0
                    if iou > iou_threshold or containment > containment_threshold:
                        should_merge = True

                # Balão em "amendoim" (dois lóbulos da mesma fala ligados por um pescoço aberto)
                # costuma vir partido pelo YOLO com fresta vertical minúscula (<= 6px).
                # Antes de fundir, checamos a faixa da costura (±28px): se houver passagem branca
                # contínua atravessando a fresta (bridge_cols >= 0.35), é um único balão; se houver
                # parede escura separando as bordas (dark_wall_ratio >= 0.65), são dois balões empilhados.
                if not should_merge and a.get("label") == "text_bubble" and b.get("label") == "text_bubble":
                    x_overlap = max(0, min(ax2, bx2) - max(ax1, bx1))
                    min_w = min(ax2 - ax1, bx2 - bx1)
                    y_gap = max(0, max(ay1, by1) - min(ay2, by2))
                    if min_w > 0 and (x_overlap / float(min_w)) >= 0.60 and y_gap <= 6:
                        has_white_neck = True
                        if gray_np is not None:
                            h_img, w_img = gray_np.shape[:2]
                            seam_y = int(round(0.5 * (min(ay2, by2) + max(ay1, by1))))
                            sy1 = max(0, seam_y - 28)
                            sy2 = min(h_img, seam_y + 29)
                            pad_x = max(8, int(min_w * 0.16))
                            sx1 = max(0, max(ax1, bx1) + pad_x)
                            sx2 = min(w_img, min(ax2, bx2) - pad_x)
                            if sy2 > sy1 and sx2 - sx1 >= 12:
                                seam_band = gray_np[sy1:sy2, sx1:sx2]
                                min_row_white = float(np.min(np.mean(seam_band >= 230, axis=1)))
                                min_row_mean = float(np.min(np.mean(seam_band, axis=1)))
                                col_min = np.min(seam_band, axis=0)
                                dark_wall_ratio = float(np.mean(col_min <= 175))
                                w_er = cv2.erode((seam_band >= 210).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
                                _, cc_map = cv2.connectedComponents(w_er)
                                top_ids = set(cc_map[0, cc_map[0, :] > 0].tolist())
                                bot_ids = set(cc_map[-1, cc_map[-1, :] > 0].tolist())
                                bridge_ids = top_ids & bot_ids
                                bridge_cols = (
                                    float(np.mean(np.isin(cc_map, list(bridge_ids)).any(axis=0)))
                                    if bridge_ids
                                    else 0.0
                                )
                                if (
                                    min_row_white < 0.35
                                    or min_row_mean < 175.0
                                    or dark_wall_ratio >= 0.65
                                    or bridge_cols < 0.35
                                ):
                                    has_white_neck = False
                        if has_white_neck:
                            should_merge = True

                if should_merge:
                    current["x1"] = min(ax1, bx1)
                    current["y1"] = min(ay1, by1)
                    current["x2"] = max(ax2, bx2)
                    current["y2"] = max(ay2, by2)
                    current["confidence"] = max(current.get("confidence", 0), b.get("confidence", 0))

                    # Quando um recorte `text_bubble` sobrepõe um `text_free` na mesma fala, o balão vence
                    # para que o texto não seja descartado por engano como onomatopeia.
                    if b.get("label") == "text_bubble" or current.get("label") == "text_bubble":
                        current["label"] = "text_bubble"
                        current["is_bubble"] = True
                        current["is_sfx"] = False
                        if current.get("bg_type") == "sfx":
                            current["bg_type"] = b.get("bg_type", "white") if b.get("label") == "text_bubble" else "complex"
                    current["area"] = (current["x2"] - current["x1"]) * (current["y2"] - current["y1"])

                    used[j] = True
                    changed = True
                    continue

            merged_boxes.append(current)

        boxes = merged_boxes

    return boxes


def _merge_panels(boxes: list[dict], iou_threshold=0.15, containment_threshold=0.50) -> list[dict]:
    """
    Funde iterativamente caixas de painéis/quadros sobrepostas ou contidas até estabilização.
    """
    changed = True
    while changed:
        changed = False
        merged_boxes = []
        used = [False] * len(boxes)

        # Ordena por confiança decrescente para manter detecções mais fortes
        boxes = sorted(boxes, key=lambda b: b.get("conf", b.get("confidence", 0.0)), reverse=True)

        for i, a in enumerate(boxes):
            if used[i]:
                continue
            current = dict(a)
            current["box"] = list(a["box"])

            for j, b in enumerate(boxes):
                if i == j or used[j]:
                    continue

                ax1, ay1, ax2, ay2 = current["box"]
                bx1, by1, bx2, by2 = b["box"]

                ix1, iy1 = max(ax1, bx1), max(ay1, by1)
                ix2, iy2 = min(ax2, bx2), min(ay2, by2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)

                area_a = (ax2 - ax1) * (ay2 - ay1)
                area_b = (bx2 - bx1) * (by2 - by1)

                if inter > 0:
                    union = area_a + area_b - inter
                    iou = inter / union if union > 0 else 0
                    containment = inter / min(area_a, area_b) if min(area_a, area_b) > 0 else 0

                    if iou > iou_threshold or containment > containment_threshold:
                        current["box"][0] = min(ax1, bx1)
                        current["box"][1] = min(ay1, by1)
                        current["box"][2] = max(ax2, bx2)
                        current["box"][3] = max(ay2, by2)
                        current["conf"] = max(current.get("conf", current.get("confidence", 0.0)), b.get("conf", b.get("confidence", 0.0)))
                        current["area"] = (current["box"][2] - current["box"][0]) * (current["box"][3] - current["box"][1])
                        used[j] = True
                        changed = True
                        continue

            merged_boxes.append(current)

        boxes = merged_boxes

    return boxes


def _detect_panels_opencv(image: Image.Image, min_area_ratio=0.02) -> list[dict]:
    """
    Localiza bordas de quadros via thresholding adaptativo e detecção de contornos do OpenCV.
    """
    cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    thresh = cv2.adaptiveThreshold(cv_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_area = image.width * image.height
    min_area = img_area * min_area_ratio

    raw = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        if area > min_area:
            raw.append({"box": [x, y, x + w, y + h], "area": area, "conf": 0.99})

    if not raw:
        return []

    merged = _merge_panels(raw, iou_threshold=0.15, containment_threshold=0.50)
    return merged


def _refine_bubble_box(image: Image.Image, x1: int, y1: int, x2: int, y2: int, label: str, pad: int = 0):
    """
    Ajusta e limita coordenadas de bounding box aos limites estritos da imagem fornecida.
    """
    img_width, img_height = image.width, image.height

    rx1 = max(0, x1 - pad)
    ry1 = max(0, y1 - pad)
    rx2 = min(img_width, x2 + pad)
    ry2 = min(img_height, y2 + pad)

    return int(rx1), int(ry1), int(rx2), int(ry2)


def _validate_bubble_morphology(gray_crop: np.ndarray, label: str) -> bool:
    """
    Filtro morfológico ultrarrápido (OpenCV) para validar balões e descartar ruídos/balões vazios em <1ms.
    - Balões vazios: Se não houver caracteres ou traços de texto dentro do balão, descarta.
    - Ruídos na arte: Se o recorte for uma mancha/gradiente sem caracteres tipográficos, descarta.
    - Suporta dupla polaridade: texto escuro em fundo claro e texto claro em fundo escuro (balões invertidos).
    - Exclui manchas contínuas maciças (pele/sombras/reflexos) que não formam glifos tipográficos.
    """
    h, w = gray_crop.shape[:2]
    if h < 14 or w < 14:
        return False

    crop_area = float(w * h)
    max_area_glyph = max(2000, int(crop_area * 0.12))
    max_dim_w = max(120, int(w * 0.85))
    max_dim_h = max(120, int(h * 0.85))

    def _analyze_polarity(binary_img: np.ndarray):
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_img)
        glyphs = 0
        core_glyphs = 0
        total_glyph_area = 0
        core_heights = []
        core_widths = []
        cx_min, cx_max = w * 0.20, w * 0.80
        cy_min, cy_max = h * 0.18, h * 0.82
        for i in range(1, num_labels):
            sx = stats[i, cv2.CC_STAT_LEFT]
            sy = stats[i, cv2.CC_STAT_TOP]
            sw = stats[i, cv2.CC_STAT_WIDTH]
            sh = stats[i, cv2.CC_STAT_HEIGHT]
            sarea = stats[i, cv2.CC_STAT_AREA]
            # Ignora traços de moldura colados na borda extrema do recorte
            if sx <= 0 or sy <= 0 or (sx + sw) >= w or (sy + sh) >= h:
                continue
            # Desconsidera poeira (< 10px) e manchas sólidas massivas (> max_area_glyph)
            if 10 <= sarea <= max_area_glyph and 3 <= sw <= max_dim_w and 4 <= sh <= max_dim_h:
                glyphs += 1
                total_glyph_area += sarea
                cx, cy = centroids[i]
                if cx_min <= cx <= cx_max and cy_min <= cy <= cy_max:
                    core_glyphs += 1
                    core_heights.append(sh)
                    core_widths.append(sw)
        # Rejeita texturas de micro-impressão de jornal no miolo (ex.: pág. 032)
        if core_glyphs >= 15 and core_heights and core_widths:
            if float(np.median(core_heights)) <= 10.0 and float(np.median(core_widths)) <= 5.5:
                return 0, 0, 0.0
        density = total_glyph_area / crop_area if crop_area > 0 else 0
        return glyphs, core_glyphs, density

    dark_bg_ratio = np.count_nonzero(gray_crop < 100) / crop_area if crop_area > 0 else 0.0

    # Polaridade normal: letras escuras em fundo claro
    _, binary_dark = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    glyphs_dark, core_dark, density_dark = _analyze_polarity(binary_dark)

    # Polaridade invertida: SOMENTE avaliada quando o fundo é genuinamente escuro (evita contar frestas brancas de hachura)
    if dark_bg_ratio >= 0.35:
        _, binary_light = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        glyphs_light, core_light, density_light = _analyze_polarity(binary_light)
    else:
        glyphs_light, core_light, density_light = 0, 0, 0.0

    letter_glyphs = max(glyphs_dark, glyphs_light)
    core_glyphs = max(core_dark, core_light)
    glyph_density = max(density_dark, density_light)

    # Validação para balões de fala (deve ter caracteres no miolo central e densidade mínima de texto estruturado)
    if label == "text_bubble":
        white_fraction = np.count_nonzero(gray_crop >= 210) / crop_area if crop_area > 0 else 0.0
        min_density = 0.0012 if (white_fraction >= 0.65 and core_glyphs >= 2) else 0.005
        if letter_glyphs < 2 or core_glyphs < 2 or glyph_density < min_density:
            return False

    # Validação para texto livre / solto na arte (descarta ruídos e texturas que não são texto)
    if label == "text_free":
        # Se for um recorte largo de texto de impacto (> 25.000px) com caracteres detectados no miolo, aceita
        if crop_area > 25000 and core_glyphs >= 2 and glyph_density >= 0.002:
            return True
        if letter_glyphs < 2 or core_glyphs < 2 or glyph_density < 0.012:
            return False

    return True


def _has_multiline_typeset_structure(
    gray_crop: np.ndarray,
    min_lines: int = 2,
    min_glyphs: int = 7,
) -> bool:
    """
    Verifica se um recorte de baixa confiança contém múltiplas linhas horizontais de
    caracteres tipográficos uniformes (ex.: blocos de narração sem moldura no clímax),
    rejeitando onomatopeias (SFX), logotipos isolados em roupas e texturas de cenário.
    """
    if gray_crop is None or gray_crop.size == 0:
        return False
    h, w = gray_crop.shape[:2]
    if h < 28 or w < 28:
        return False

    max_h = min(65, int(h * 0.42))
    max_w = min(65, int(w * 0.42))
    dark_bg_ratio = np.count_nonzero(gray_crop < 100) / float(gray_crop.size)
    thresh_flags = [cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU]
    if dark_bg_ratio >= 0.35:
        thresh_flags.append(cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    for thresh_flag in thresh_flags:
        _, binary = cv2.threshold(gray_crop, 0, 255, thresh_flag)
        num_labels, _, stats, centroids = cv2.connectedComponentsWithStats(binary)
        cands = []
        for i in range(1, num_labels):
            sx = stats[i, cv2.CC_STAT_LEFT]
            sy = stats[i, cv2.CC_STAT_TOP]
            sw = stats[i, cv2.CC_STAT_WIDTH]
            sh = stats[i, cv2.CC_STAT_HEIGHT]
            sarea = stats[i, cv2.CC_STAT_AREA]
            if sx <= 1 or sy <= 1 or (sx + sw) >= w - 1 or (sy + sh) >= h - 1:
                continue
            if 8 <= sh <= max_h and 2 <= sw <= max_w and 12 <= sarea <= (sw * sh * 0.90):
                aspect = sw / float(sh)
                if 0.12 <= aspect <= 2.4:
                    cx, cy = centroids[i]
                    cands.append((cx, cy, sw, sh))

        if len(cands) < min_glyphs:
            continue

        heights = np.array([c[3] for c in cands], dtype=np.float32)
        widths = np.array([c[2] for c in cands], dtype=np.float32)
        med_h = float(np.median(heights))
        med_w = float(np.median(widths))
        if med_h < 9.5 or med_w < 5.0:
            continue
        uniform = [c for c in cands if (0.58 * med_h) <= c[3] <= (1.48 * med_h)]
        if len(uniform) < min_glyphs:
            continue

        # Agrupa por linhas horizontais de texto (ordenadas por cy)
        uniform.sort(key=lambda c: c[1])
        rows = []
        for c in uniform:
            placed = False
            for r in rows:
                mean_y = sum(item[1] for item in r) / float(len(r))
                if abs(c[1] - mean_y) <= 0.58 * med_h:
                    r.append(c)
                    placed = True
                    break
            if not placed:
                rows.append([c])

        valid_rows = [
            r for r in rows
            if len(r) >= 2 and (max(item[0] for item in r) - min(item[0] for item in r)) >= 1.2 * med_h
        ]
        if len(valid_rows) >= min_lines and sum(len(r) for r in valid_rows) >= min_glyphs:
            return True

    return False


def is_clean_white_bubble(gray_crop: np.ndarray, threshold: int = 210, min_white_ratio: float = 0.60) -> bool:
    """
    Avalia se um recorte é um balão de fala clássico de fundo estritamente branco limpo.
    Critérios:
    1. Proporção substancial de pixels claros (>= threshold, padrão 210) de pelo menos 60%.
    2. Presença de traços escuros (< 120) de pelo menos 0.8% para certificar que contém texto tipográfico.
    """
    if gray_crop is None or gray_crop.size == 0:
        return False
    h, w = gray_crop.shape[:2]
    if h < 14 or w < 14:
        return False

    white_ratio = np.count_nonzero(gray_crop >= threshold) / float(gray_crop.size)
    if white_ratio < min_white_ratio:
        return False

    dark_ratio = np.count_nonzero(gray_crop < 120) / float(gray_crop.size)
    if dark_ratio < 0.008:
        return False

    return True


def is_sfx_morphology(
    gray_crop: np.ndarray,
    label: str = "text_free",
    is_clean: bool = None,
    has_multiline: bool = None,
) -> bool:
    """
    Avalia se um recorte de texto corresponde a um efeito sonoro (SFX / onomatopeia) ou ruído.

    Regras de Segurança (Zero Falso Positivo):
    - Balões fechados de fundo limpo (is_clean_white_bubble) NUNCA são considerados SFX.
    - Textos multilinha estruturados (_has_multiline_typeset_structure) NUNCA são considerados SFX.
    - Se for rotulado como text_free e não contiver estrutura de balão limpo, confirma como SFX.
    """
    if gray_crop is None or gray_crop.size == 0:
        return True

    # Balões clássicos com fundo branco são sagrados
    clean = is_clean if is_clean is not None else is_clean_white_bubble(gray_crop)
    if clean:
        return False

    # Texto tipográfico estruturado multilinha é diálogo/narração
    multiline = has_multiline if has_multiline is not None else _has_multiline_typeset_structure(gray_crop, min_lines=2, min_glyphs=7)
    if multiline:
        return False

    if label == "text_free":
        return True

    # Para text_bubble com fundo complexo ou ruído:
    # Se o fundo for excessivamente ruidoso e com baixa presença de branco, classifica como SFX.
    # Short-circuit: calcula desvio padrão somente se a taxa de branco for baixa (< 25%).
    white_ratio = np.count_nonzero(gray_crop >= 200) / float(gray_crop.size)
    if white_ratio < 0.25:
        crop_std = float(np.std(gray_crop))
        if crop_std > 55.0:
            return True

    return False


def _extract_single_bubble_polygon(b: dict, img_gray: np.ndarray) -> dict:
    """Extrai o contorno curvo de um único balão de forma thread-safe."""
    if "polygon" in b and len(b["polygon"]) > 4:
        return b  # Já tem polígono complexo
    x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
    # SFX não possuem bordas curvas de balão; preserva bounding box direto e economiza floodFill
    if b.get("is_sfx", False) or not b.get("is_bubble", True):
        b["polygon"] = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        if "initial_box" not in b:
            b["initial_box"] = [x1, y1, x2, y2]
        if "initial_polygon" not in b and "polygon" in b:
            b["initial_polygon"] = [list(pt) for pt in b["polygon"]]
        return b

    gray = img_gray[y1:y2, x1:x2]
    if gray.size == 0:
        return b
    h, w = gray.shape[:2]
    thresh_val = 210
    if not b.get("is_bubble", True) or np.count_nonzero(gray >= 210) / gray.size < 0.40:
        thresh_val = 185
    _, white_mask = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
    interior = np.zeros((h, w), dtype=np.uint8)
    ff_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    for fy in [0.2, 0.35, 0.5, 0.65, 0.8]:
        for fx in [0.2, 0.35, 0.5, 0.65, 0.8]:
            sx = max(0, min(int(w * fx), w - 1))
            sy = max(0, min(int(h * fy), h - 1))
            # Pula sementes que já fazem parte de uma região inundada em iteração anterior
            if white_mask[sy, sx] > 0 and interior[sy, sx] == 0:
                temp = white_mask.copy()
                ff_mask.fill(0)
                cv2.floodFill(temp, ff_mask, (sx, sy), 128)
                region = ((temp == 128).astype(np.uint8)) * 255
                interior = cv2.bitwise_or(interior, region)
    contours, _ = cv2.findContours(interior, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        center_x, center_y = w / 2.0, h / 2.0
        best = max(contours, key=lambda c: cv2.pointPolygonTest(c, (center_x, center_y), True))
        epsilon = 0.005 * cv2.arcLength(best, True)
        approx = cv2.approxPolyDP(best, epsilon, True)
        b["polygon"] = [[int(pt[0][0] + x1), int(pt[0][1] + y1)] for pt in approx]
    else:
        b["polygon"] = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    if "initial_box" not in b:
        b["initial_box"] = [x1, y1, x2, y2]
    if "initial_polygon" not in b and "polygon" in b:
        b["initial_polygon"] = [list(pt) for pt in b["polygon"]]
    return b


def extract_bubble_polygons(
    image: Image.Image,
    bubbles: list[dict],
    gray_image: np.ndarray = None,
) -> list[dict]:
    """Extrai o contorno curvo exato (polígono) da área interna de cada balão."""
    if not bubbles:
        return []
    img_gray = gray_image if gray_image is not None else np.array(image.convert("L"))
    if len(bubbles) >= 4:
        from concurrent.futures import ThreadPoolExecutor
        workers = min(6, len(bubbles))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(lambda b: _extract_single_bubble_polygon(b, img_gray), bubbles))
    else:
        for b in bubbles:
            _extract_single_bubble_polygon(b, img_gray)
    return bubbles
