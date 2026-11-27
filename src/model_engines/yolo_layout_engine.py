"""
Detecção de quadros e balões de mangá usando YOLO, com pós-processamento OpenCV.

Por que o pós-processamento é necessário: os modelos YOLO capturam bem balões
ortogonais, mas fragmentam balões em "amendoim", ignoram balões inclinados em
cenas de ação e geram falsos positivos em hachuras/texturas. Por isso este módulo
combina inferência GPU (com fallback automático para CPU) às heurísticas puras
de `src.geometry.bubble_geometry` e `src.geometry.panels`.
"""

import os
import sys
import json
import contextlib
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np

try:
    import torch
    if not hasattr(torch, "cuda"):
        # Pacotes órfãos/namespace sem binários CUDA não podem enganar o detector
        torch = None
        for _k in list(sys.modules.keys()):
            if _k == "torch" or _k.startswith("torch."):
                sys.modules.pop(_k, None)
except Exception:
    torch = None

class _DummyYOLOModel:
    names = {0: "text_bubble", 1: "text_free", 2: "frame"}

    def predict(self, *args, **kwargs):
        return []

    def to(self, *args, **kwargs):
        return self


YOLO = None
if torch is not None:
    try:
        # Ao ser importada, a Ultralytics substitui PIL.Image.open por um wrapper próprio
        # (com patching de EXIF/retentativas) que interfere em mocks e leituras da app.
        # Salvamos e restauramos a referência original imediatamente após o import.
        from PIL import Image as _PILImage
        _orig_pil_open = _PILImage.open
        from ultralytics import YOLO
        if getattr(_PILImage.open, "__module__", "").startswith("ultralytics"):
            _PILImage.open = _orig_pil_open
    except Exception:
        YOLO = None
        try:
            from PIL import Image as _PILImage
            if "_orig_pil_open" in locals() and getattr(_PILImage.open, "__module__", "").startswith("ultralytics"):
                _PILImage.open = _orig_pil_open
        except Exception:
            pass

if YOLO is None:
    YOLO = lambda *args, **kwargs: _DummyYOLOModel()

if torch is None:
    class _TorchFallback:
        class cuda:
            @staticmethod
            def is_available():
                return False

        @staticmethod
        def no_grad():
            return contextlib.nullcontext()

    torch = _TorchFallback()
from src.utils.gpu_utils import cleanup_gpu_memory
from src.batch_pipeline.reading_order import (
    recursive_xy_cut,
    _bubble_xy_cut,
    sort_bubbles_reading_order,
)
from src.geometry.bubble_geometry import (
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
)
from src.geometry.panels import refine_panels_to_polygons

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _detect_panels_blind_master(panel_model, image: Image.Image, min_area_ratio=0.02) -> list[dict]:
    """
    Executa inferência YOLO de detecção de quadros (Manga109 / TheBlindMaster),
    filtrando estritamente a classe de painéis ('frame') e fundindo sobreposições.
    min_area_ratio: fração mínima da área da página para descartar ruídos.
    """
    img_area = image.width * image.height
    min_area = img_area * min_area_ratio
    
    device = "cuda" if (torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available()) else "cpu"
    import contextlib
    ctx = torch.no_grad() if (torch is not None and hasattr(torch, "no_grad")) else contextlib.nullcontext()
    with ctx:
        try:
            results = panel_model.predict(source=image, conf=0.30, verbose=False, device=device)
        except Exception as e:
            if "no kernel image" in str(e) or "CUDA error" in str(e) or "not implemented" in str(e) or "out of memory" in str(e).lower():
                print(" [Mapeador] AVISO: Fallback para CPU nos painéis YOLO...")
                cleanup_gpu_memory(force_ipc=True)
                if hasattr(panel_model, "to"):
                    try:
                        panel_model.to("cpu")
                    except Exception:
                        pass

                results = panel_model.predict(source=image, conf=0.30, verbose=False, device="cpu")
            else:
                raise
    
    raw = []
    for r in results:
        if r.boxes is None:
            continue
        names = getattr(r, "names", {})
        for box in r.boxes:
            if hasattr(box, "cls") and box.cls is not None and len(box.cls) > 0:
                cls_id = int(box.cls[0].item())
                cls_name = names.get(cls_id, "").lower() if isinstance(names, dict) else ""
                if cls_name and cls_name not in ("frame", "panel"):
                    continue
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            conf = float(box.conf[0].item())
            area = (x2 - x1) * (y2 - y1)
            if area < min_area:
                continue
            raw.append({"box": [x1, y1, x2, y2], "area": area, "conf": conf})
    
    if not raw:
        return []
    
    merged = _merge_panels(raw, iou_threshold=0.25, containment_threshold=0.60)
    # A fusão pode ter unido apenas fragmentos minúsculos; garante área mínima real
    merged = [p for p in merged if p["area"] >= min_area]
    
    return merged


class YoloMapeador:
    def __init__(self, bubble_conf=0.03):
        self.bubble_conf = bubble_conf
        self.bubble_model_id = os.path.join(_PROJECT_ROOT, "models", "comic-speech-bubble-detector.pt")
        self._panel_model = None
        self._bubble_model = None

    def load_panel_detector(self):
        if self._panel_model is None:
            from src.config import get_app_data_dir
            cache_dir = os.path.join(get_app_data_dir(), "models")
            
            # Prioriza o modelo Extra-Large Manga109 (v2023.12.07_x) com fallbacks seguros
            x_candidate = os.path.join(cache_dir, "v2023.12.07_x", "model.pt")
            bundled_x = os.path.join(_PROJECT_ROOT, "models", "v2023.12.07_x", "model.pt")
            local_path = os.path.join(cache_dir, "best.pt")
            bundled_path = os.path.join(_PROJECT_ROOT, "models", "best.pt")
            
            chosen_path = None
            for cand in [x_candidate, bundled_x, local_path, bundled_path]:
                min_cand_sz = 2 * 1024 * 1024 if cand.endswith("best.pt") else 10 * 1024 * 1024
                if os.path.isfile(cand) and os.path.getsize(cand) >= min_cand_sz:
                    chosen_path = cand
                    break

            if not chosen_path:
                try:
                    from huggingface_hub import hf_hub_download
                    os.makedirs(cache_dir, exist_ok=True)
                    chosen_path = hf_hub_download(
                        repo_id="deepghs/manga109_yolo",
                        filename="v2023.12.07_x/model.pt",
                        local_dir=cache_dir
                    )
                except Exception as e:
                    print(f" [Mapeador] AVISO: Não foi possível obter o modelo de quadros YOLO ({e}). Ordenação fallback ativada.")
                    chosen_path = bundled_path

            if not chosen_path or not os.path.isfile(chosen_path):
                print(f" [Mapeador] AVISO: Modelo de quadros não encontrado em '{chosen_path}'. Segmentação de quadros desativada.")
                self._panel_model = None
                return

            try:
                from src.utils.gpu_utils import ModelLoadTracker
                with ModelLoadTracker("YOLO Panels (XL)", total_size_mb=137):
                    self._panel_model = YOLO(chosen_path)
                    device = "cuda" if (torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available()) else "cpu"
                    try:
                        self._panel_model.predict(source=np.zeros((64, 64, 3), dtype=np.uint8), device=device, verbose=False)
                    except Exception:
                        pass
            except Exception as e:
                print(f" [Mapeador] AVISO: Falha ao inicializar modelo de quadros YOLO: {e}. Seguindo sem segmentação de quadros.")
                self._panel_model = None

    def unload_panel_detector(self):
        if self._panel_model is not None:
            del self._panel_model
            self._panel_model = None
            cleanup_gpu_memory()

    def load_bubble_detector(self):
        if self._bubble_model is None:
            from src.config import get_app_data_dir
            cache_dir = os.path.join(get_app_data_dir(), "models")
            local_path = os.path.join(cache_dir, "comic-speech-bubble-detector.pt")
            if not os.path.isfile(local_path):
                if os.path.isfile(self.bubble_model_id):
                    local_path = self.bubble_model_id
                else:
                    from huggingface_hub import hf_hub_download
                    os.makedirs(cache_dir, exist_ok=True)
                    try:
                        local_path = hf_hub_download(repo_id="ogkalu/comic-speech-bubble-detector-yolov8m", filename="comic-speech-bubble-detector.pt", local_dir=cache_dir)
                    except Exception:
                        local_path = self.bubble_model_id
            from src.utils.gpu_utils import ModelLoadTracker
            with ModelLoadTracker("YOLO Bubbles", total_size_mb=100):
                self._bubble_model = YOLO(local_path)
                device = "cuda" if (torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available()) else "cpu"
                try:
                    self._bubble_model.predict(source=np.zeros((64, 64, 3), dtype=np.uint8), device=device, verbose=False)
                except Exception:
                    pass

    def unload_bubble_detector(self):
        if self._bubble_model is not None:
            del self._bubble_model
            self._bubble_model = None
            cleanup_gpu_memory()

    def detect_bubbles(self, image: Image.Image, white_only: bool = False, gray_image: np.ndarray = None, **kwargs) -> list[dict]:
        self.load_bubble_detector()
        full_gray = gray_image if gray_image is not None else np.array(image.convert("L"))
        # Páginas de mangá são bem mais altas que largas; imgsz=1280 com rect=True evita
        # esmagar balões estreitos de reticências ou textos verticais no redimensionamento quadrado.
        device = "cuda" if (torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available()) else "cpu"
        import contextlib
        ctx = torch.no_grad() if (torch is not None and hasattr(torch, "no_grad")) else contextlib.nullcontext()
        with ctx:
            try:
                results = self._bubble_model.predict(
                    source=image,
                    conf=self.bubble_conf,
                    imgsz=1280,
                    rect=True,
                    iou=0.45,
                    agnostic_nms=True,
                    verbose=False,
                    device=device
                )
            except Exception as e:
                if "no kernel image" in str(e) or "CUDA error" in str(e) or "not implemented" in str(e) or "out of memory" in str(e).lower():
                    print(" [Mapeador] AVISO: Fallback para CPU nos balões YOLO...")
                    cleanup_gpu_memory(force_ipc=True)
                    if hasattr(self._bubble_model, "to"):
                        try:
                            self._bubble_model.to("cpu")
                        except Exception:
                            pass
    
                    results = self._bubble_model.predict(
                        source=image,
                        conf=self.bubble_conf,
                        imgsz=1280,
                        rect=True,
                        iou=0.45,
                        agnostic_nms=True,
                        verbose=False,
                        device="cpu"
                    )
                else:
                    raise
        
        img_area = image.width * image.height
        raw_bubbles = []
        for r in results:
            if r.boxes is None:
                continue
            names = r.names
            for box in r.boxes:
                cls_id = int(box.cls[0].item())
                label = names.get(cls_id, "unknown").lower()
                conf = float(box.conf[0].item())
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                
                # Sanity Checks
                area = (x2 - x1) * (y2 - y1)
                if area < img_area * 0.0005:
                    continue
                    
                # Filtro anti-artefatos de margem/sangria (fatias finas coladas nas bordas com baixa confiança)
                w_box = x2 - x1
                h_box = y2 - y1
                is_margin_sliver = (
                    (x1 <= 4 or x2 >= image.width - 4 or y1 <= 4 or y2 >= image.height - 4)
                    and (w_box < 50 or h_box < 50)
                    and conf < 0.35
                )
                if is_margin_sliver:
                    continue

                # Filtro anti-linha de moldura/calha (fatias extremamente finas e compridas na página)
                if min(w_box, h_box) < 60 and max(w_box, h_box) / float(max(1, min(w_box, h_box))) > 9.5:
                    continue

                # Filtro anti-ladrilho/logotipo minúsculo de fundo com baixa confiança (ex.: patrocínio no cenário)
                if label == "text_bubble" and conf < 0.35 and area < img_area * 0.0018:
                    continue

                # Filtro de cenário massivo de baixa confiança (elimina falsos positivos de água, nuvens e manchas)
                # Não descarta recortes de text_free de clímax com proporção de texto largo
                if area > 80000 and conf < 0.25 and label != "text_free":
                    continue

                # Descarta ruídos de confiança residual (< 0.09)
                if conf < 0.09:
                    continue
                
                # Refinamento e validação dos limites da imagem com smart padding contextual (4px)
                x1, y1, x2, y2 = _refine_bubble_box(image, x1, y1, x2, y2, label, pad=4)
                if x2 <= x1 or y2 <= y1:
                    continue
                
                bg_type = "white" if label == "text_bubble" else "sfx"
                gray_crop = full_gray[y1:y2, x1:x2]
                if gray_crop.size == 0:
                    continue

                is_clean = is_clean_white_bubble(gray_crop)
                dark_bg_ratio = np.count_nonzero(gray_crop < 80) / float(gray_crop.size)
                light_text_ratio = np.count_nonzero(gray_crop >= 180) / float(gray_crop.size)
                is_dark_bubble = (dark_bg_ratio >= 0.45 and light_text_ratio >= 0.008)

                # Filtro morfológico de traços de texto OpenCV (elimina ruídos e balões vazios em <1ms antes de análises tipográficas mais pesadas)
                if not _validate_bubble_morphology(gray_crop, label):
                    continue

                # Detecções de baixa confiança (< 0.35) exigem estrutura tipográfica multilinha real
                # (preserva narrações de clímax sem moldura e gritos, rejeitando SFX, luvas, roupas e janelas)
                has_multiline = None
                if conf < 0.35:
                    has_multiline = _has_multiline_typeset_structure(gray_crop, min_lines=2, min_glyphs=7)
                    if not has_multiline:
                        continue
                
                if label == "text_bubble":
                    white_ratio = np.count_nonzero(gray_crop > 180) / gray_crop.size
                    if white_ratio < 0.10 and not is_dark_bubble:
                        label = "text_free"
                elif label == "text_free":
                    if has_multiline is None:
                        has_multiline = _has_multiline_typeset_structure(gray_crop, min_lines=2, min_glyphs=7)
                    if is_clean or (is_dark_bubble and has_multiline) or has_multiline:
                        label = "text_bubble"
                    
                # Determinação inteligente do tipo de fundo e flag de SFX
                is_sfx = False
                if is_clean:
                    bg_type = "white"
                    is_sfx = False
                elif is_dark_bubble and label == "text_bubble":
                    bg_type = "dark"
                    is_sfx = False
                elif label == "text_bubble":
                    if is_sfx_morphology(gray_crop, label="text_bubble", is_clean=is_clean, has_multiline=has_multiline):
                        bg_type = "sfx"
                        is_sfx = True
                        label = "text_free"
                    else:
                        bg_type = "complex"
                        is_sfx = False
                else:
                    bg_type = "sfx"
                    is_sfx = True

                if white_only and (bg_type != "white" or is_sfx):
                    continue
                
                raw_bubbles.append({
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "confidence": round(conf, 3), "label": label,
                    "area": int(area),
                    "is_bubble": (label == "text_bubble"),
                    "is_sfx": is_sfx,
                    "bg_type": bg_type
                })

        # Passada secundária rotacionada em -25°: o detector foi treinado em textos horizontais e costuma
        # perder balões de grito inclinados em cenas de ação (ex.: pág. 024). Para não importar falsos
        # positivos do fundo girado, validamos o miolo branco cercado por borda escura antes de reprojetar.
        if image.width >= 500 and image.height >= 500:
            try:
                import math
                angle = -25.0
                rot_pil = image.rotate(angle, resample=Image.BICUBIC, expand=True)
                rw_tot, rh_tot = rot_pil.width, rot_pil.height
                rot_gray = np.array(rot_pil.convert("L"))
                rad = math.radians(angle)
                cos_r, sin_r = math.cos(rad), math.sin(rad)

                import contextlib
                rot_ctx = torch.no_grad() if (torch is not None and hasattr(torch, "no_grad")) else contextlib.nullcontext()
                with rot_ctx:
                    rot_results = self._bubble_model.predict(
                        source=rot_pil,
                        conf=max(0.20, self.bubble_conf),
                        imgsz=1280,
                        rect=True,
                        iou=0.45,
                        agnostic_nms=True,
                        verbose=False,
                        device=device,
                    )

                for rr in rot_results:
                    if getattr(rr, "boxes", None) is None:
                        continue
                    for rbox in rr.boxes:
                        rconf = float(rbox.conf[0].item())
                        if rconf < 0.20:
                            continue
                        rx1, ry1, rx2, ry2 = [int(v) for v in rbox.xyxy[0].tolist()]
                        if rx2 - rx1 < 40 or ry2 - ry1 < 40:
                            continue

                        rcx = 0.5 * (rx1 + rx2) - rw_tot / 2.0
                        rcy = 0.5 * (ry1 + ry2) - rh_tot / 2.0
                        ocx = image.width / 2.0 + rcx * cos_r - rcy * sin_r
                        ocy = image.height / 2.0 + rcx * sin_r + rcy * cos_r
                        if any(
                            (b["x1"] - 12) <= ocx <= (b["x2"] + 12) and (b["y1"] - 12) <= ocy <= (b["y2"] + 12)
                            for b in raw_bubbles
                        ):
                            continue

                        rcrop = rot_gray[ry1:ry2, rx1:rx2]
                        if rcrop.size == 0:
                            continue
                        rh, rw = rcrop.shape[:2]
                        w_ratio = np.count_nonzero(rcrop >= 200) / float(rcrop.size)
                        d_ratio = np.count_nonzero(rcrop < 115) / float(rcrop.size)
                        if w_ratio < 0.42 or d_ratio < 0.025:
                            continue
                        if not _validate_bubble_morphology(rcrop, "text_bubble"):
                            continue

                        _, wmask = cv2.threshold(rcrop, 200, 255, cv2.THRESH_BINARY)
                        wmask_closed = cv2.morphologyEx(wmask, cv2.MORPH_CLOSE, np.ones((19, 19), np.uint8))
                        wmask_er = cv2.erode(wmask_closed, np.ones((5, 5), np.uint8))
                        interior = np.zeros((rh, rw), dtype=np.uint8)
                        ff = np.zeros((rh + 2, rw + 2), dtype=np.uint8)
                        for fy in (0.3, 0.45, 0.5, 0.55, 0.7):
                            for fx in (0.3, 0.45, 0.5, 0.55, 0.7):
                                sx, sy = min(rw - 1, int(rw * fx)), min(rh - 1, int(rh * fy))
                                if wmask_er[sy, sx] > 0 and interior[sy, sx] == 0:
                                    tmp = wmask_er.copy()
                                    ff.fill(0)
                                    cv2.floodFill(tmp, ff, (sx, sy), 128)
                                    interior = cv2.bitwise_or(interior, ((tmp == 128).astype(np.uint8)) * 255)
                        interior = cv2.dilate(interior, np.ones((5, 5), np.uint8))
                        interior = cv2.bitwise_and(interior, wmask_closed)
                        if np.count_nonzero(interior) < rcrop.size * 0.25:
                            continue

                        dil_int = cv2.dilate(interior, np.ones((9, 9), np.uint8))
                        ring = cv2.bitwise_and(dil_int, cv2.bitwise_not(interior))
                        if not np.any(ring > 0) or float(np.mean(rcrop[ring > 0] <= 125)) < 0.28:
                            continue

                        cnts, _ = cv2.findContours(interior, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        if not cnts:
                            continue
                        pts_rot = np.vstack(cnts).reshape(-1, 2).astype(np.float32)
                        rdx = (pts_rot[:, 0] + rx1) - rw_tot / 2.0
                        rdy = (pts_rot[:, 1] + ry1) - rh_tot / 2.0
                        ox = image.width / 2.0 + rdx * cos_r - rdy * sin_r
                        oy = image.height / 2.0 + rdx * sin_r + rdy * cos_r

                        ox1 = max(0, int(np.percentile(ox, 1)) - 4)
                        oy1 = max(0, int(np.percentile(oy, 1)) - 4)
                        ox2 = min(image.width, int(np.percentile(ox, 99)) + 4)
                        oy2 = min(image.height, int(np.percentile(oy, 99)) + 4)
                        oarea = (ox2 - ox1) * (oy2 - oy1)
                        if oarea < img_area * 0.002 or oarea > img_area * 0.08:
                            continue

                        if any(_iou([ox1, oy1, ox2, oy2], [b["x1"], b["y1"], b["x2"], b["y2"]]) > 0.15 for b in raw_bubbles):
                            continue

                        orig_crop = full_gray[oy1:oy2, ox1:ox2]
                        bg_t = "white" if is_clean_white_bubble(orig_crop) else "complex"
                        if white_only and bg_t != "white":
                            continue

                        raw_bubbles.append({
                            "x1": ox1, "y1": oy1, "x2": ox2, "y2": oy2,
                            "confidence": round(rconf, 3), "label": "text_bubble",
                            "area": int(oarea),
                            "is_bubble": True,
                            "is_sfx": False,
                            "bg_type": bg_t,
                        })
            except Exception:
                pass

        merged_bubbles = _merge_bubbles(raw_bubbles, iou_threshold=0.15, containment_threshold=0.40, image=image, gray_image=full_gray)
        return merged_bubbles

    def detect_all_bubbles(self, image: Image.Image) -> list[dict]:
        """
        Executa a inferência YOLO na imagem fornecida e retorna uma lista completa
        de dicionários de balões de texto (Bounding Boxes).
        """
        full_gray = np.array(image.convert("L"))
        self.load_bubble_detector()
        bubbles = self.detect_bubbles(image, white_only=False, gray_image=full_gray)
        self.load_panel_detector()
        panels, sorted_bubbles = self.detect_panels_and_sort(image, bubbles, gray_image=full_gray)
        return self.add_polygons(image, sorted_bubbles, gray_image=full_gray)

    def add_polygons(self, image: Image.Image, bubbles: list[dict], gray_image: np.ndarray = None) -> list[dict]:
        """Extrai o contorno curvo exato (polígono) da área interna de cada balão."""
        return extract_bubble_polygons(image, bubbles, gray_image=gray_image)

    def detect_white_bubbles(self, image: Image.Image) -> list[dict]:
        """
        Detecta e filtra estritamente apenas balões de fala fechados de fundo branco puro,
        descartando SFX, texto livre sobre arte, balões escuros/reticulados e ruídos.
        """
        all_bubbles = self.detect_all_bubbles(image)
        return [
            b for b in all_bubbles
            if b.get("is_bubble", True)
            and not b.get("is_sfx", False)
            and b.get("bg_type", "white") == "white"
        ]

    sort_bubbles_reading_order = staticmethod(sort_bubbles_reading_order)

    @staticmethod
    def _sort_bubbles_reading_order_static(image_or_none, bubbles: list[dict], panels: list[dict] = None, direction: str = "rtl") -> list[dict]:
        return YoloMapeador.sort_bubbles_reading_order(bubbles, panels=panels, direction=direction)

    def detect_panels_and_sort(self, image: Image.Image, bubbles: list[dict], gray_image: np.ndarray = None, direction: str = "rtl") -> tuple[list[dict], list[dict]]:
        if self._panel_model is None:
            self.load_panel_detector()
            
        if self._panel_model is not None:
            panels = _detect_panels_blind_master(self._panel_model, image)
            if panels:
                panels = refine_panels_to_polygons(image, panels, bubbles=bubbles, gray_image=gray_image)
                panels = recursive_xy_cut(panels, direction=direction)
                for idx, p in enumerate(panels):
                    p["id"] = idx + 1
                    p["order"] = idx + 1
            elif hasattr(image, "width") and hasattr(image, "height") and not isinstance(image.width, (type(None), type(int))) and not hasattr(image.width, "return_value"):
                img_w = int(image.width)
                img_h = int(image.height)
                panels = [{
                    "id": 1,
                    "order": 1,
                    "box": [0, 0, img_w, img_h],
                    "conf": 1.0,
                    "polygon": [[0, 0], [img_w, 0], [img_w, img_h], [0, img_h]],
                    "description": "Full-bleed splash panel"
                }]
            else:
                panels = []
        else:
            panels = []

        final_bubbles = self.sort_bubbles_reading_order(bubbles, panels=panels, direction=direction)
        return panels, final_bubbles

    def save_crops(self, image: Image.Image, bubbles: list[dict], output_dir: str, base_name: str):
        crops_dir = os.path.join(output_dir, "crops")
        os.makedirs(crops_dir, exist_ok=True)
        
        for b in bubbles:
            x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
            pad = 0
            x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
            x2, y2 = min(image.width, x2 + pad), min(image.height, y2 + pad)
            crop = image.crop((x1, y1, x2, y2))
            crop_path = os.path.join(crops_dir, f"{base_name}_balao_{b['id']:03d}.jpg")
            crop.save(crop_path)
            
        print(f" [Mapeador] Salvos {len(bubbles)} recortes em {crops_dir}")

    def draw_map(self, image: Image.Image, panels: list[dict], bubbles: list[dict], output_dir: str, base_name: str, debug: bool = False):
        """Gera um mapa visual de depuração (`_mapa.jpg`) somente quando debug=True."""
        if not debug:
            return

        draw_img = image.copy()
        draw = ImageDraw.Draw(draw_img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except Exception:
            font = ImageFont.load_default()
            
        for i, p in enumerate(panels):
            poly = p.get("polygon")
            if poly and len(poly) >= 3:
                poly_pts = [tuple(pt) for pt in poly]
                draw.polygon(poly_pts, outline="blue", width=4)
                x1, y1 = poly[0]
            else:
                x1, y1, x2, y2 = p["box"]
                draw.rectangle([x1, y1, x2, y2], outline="blue", width=4)
            draw.text((x1 + 5, y1 + 5), f"P{i+1}", fill="blue", font=font)
            
        for i, b in enumerate(bubbles):
            x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            bubble_id = b.get('id', i + 1)
            draw.text((x1 + 5, y1 - 35), f"#{bubble_id:03d}", fill="red", font=font)
            
        map_path = os.path.join(output_dir, f"{base_name}_mapa.jpg")
        draw_img.save(map_path)
        print(f" [Mapeador] Mapa visual salvo -> {map_path}")

    def save_map(self, bubbles: list[dict], output_dir: str, base_name: str, panels: list[dict] = None) -> str:
        map_path = os.path.join(output_dir, f"{base_name}_map.json")
        from src.utils.json_utils import dump_compact_map
        from src.domain.page_store import PageStore
        PageStore.save_page_record(map_path, boxes=bubbles, panels=panels, target_map_path=map_path, dump_fn=dump_compact_map)
        return map_path
