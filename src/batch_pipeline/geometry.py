import re
from PIL import Image


def _calc_text_margin(b: dict, px: float, py: float) -> float:
    """Calcula o quão 'fundo' o centro de um texto está dentro de um bounding box.
    Retorna a menor distância até qualquer borda."""
    bx1 = b.get("x1") if b.get("x1") is not None else 0
    by1 = b.get("y1") if b.get("y1") is not None else 0
    bx2 = b.get("x2") if b.get("x2") is not None else 0
    by2 = b.get("y2") if b.get("y2") is not None else 0
    return min(px - bx1, bx2 - px, py - by1, by2 - py)


def extract_perspective_crop(img, polygon_pts):
    """Converte um polígono arbitrário de 4 pontos em um crop retangular ortogonal
    utilizando cv2.warpPerspective."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None, 0, 0, 0, 0

    pts = np.array(polygon_pts, dtype=np.float32)

    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    pts = rect

    widthA = np.linalg.norm(pts[0] - pts[1])
    widthB = np.linalg.norm(pts[2] - pts[3])
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.linalg.norm(pts[0] - pts[3])
    heightB = np.linalg.norm(pts[1] - pts[2])
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array(
        [[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]],
        dtype="float32"
    )

    M = cv2.getPerspectiveTransform(pts, dst)
    warped = cv2.warpPerspective(np.array(img), M, (maxWidth, maxHeight), borderValue=(255, 255, 255))

    crop_img = Image.fromarray(warped)
    x1 = int(np.min(pts[:, 0]))
    y1 = int(np.min(pts[:, 1]))
    x2 = int(np.max(pts[:, 0]))
    y2 = int(np.max(pts[:, 1]))

    return crop_img, x1, y1, x2, y2


def deduplicate_spatial_regions(hybrid_bubbles: list):
    """Aplica NMS por margem de segurança entre regiões de texto detectadas pelo Florence
    em múltiplos balões adjacentes, eliminando vazamento de OCR entre caixas."""
    for b1 in hybrid_bubbles:
        if not b1.get("regions"):
            continue

        surviving_regions = []
        for r in b1["regions"]:
            rx, ry = r["center"]
            margin_b1 = _calc_text_margin(b1, rx, ry)

            closest_box = b1
            best_margin = margin_b1

            for b2 in hybrid_bubbles:
                if b1 == b2:
                    continue
                margin_b2 = _calc_text_margin(b2, rx, ry)
                if margin_b2 > best_margin:
                    best_margin = margin_b2
                    closest_box = b2

            if closest_box == b1:
                surviving_regions.append(r)

        if len(surviving_regions) < len(b1["regions"]):
            b1["regions"] = surviving_regions
            new_text = " ".join([r["text"] for r in surviving_regions])
            new_text = new_text.replace("- ", "")
            new_text = new_text.replace('\n', ' ')
            new_text = re.sub(r'\.\.\.\s*[Il]$', '...!', new_text)
            new_text = new_text.replace("THEYL'LL", "THEY'LL")
            b1["text"] = new_text

    for b in hybrid_bubbles:
        b.pop("regions", None)
