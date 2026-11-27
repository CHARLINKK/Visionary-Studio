import os
import json
import logging
from typing import List, Dict, Any, Callable, Optional
from src.utils.json_utils import dump_compact_map

logger = logging.getLogger("visionary.studio_layout")


class StudioLayoutManager:
    """
    Gerenciador especializado em análise de layout, ordenação geométrica de leitura
    e detecção visual de balões de fala sob demanda.
    Isola a lógica algorítmica pesada e visão computacional de StudioService.
    """

    @staticmethod
    def safe_coord(val: Any, default: int = 0) -> int:
        try:
            if val is None:
                return default
            return int(round(float(val)))
        except (ValueError, TypeError):
            return default

    @classmethod
    def normalize_polygon_boxes(cls, boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calcula as coordenadas de bounding box (x1, y1, x2, y2) a partir de polígonos
        arbitrários para garantir compatibilidade com o algoritmo de ordenação de leitura.
        """
        normalized_boxes = []
        for b in boxes:
            if not isinstance(b, dict):
                continue
            b_copy = dict(b)
            poly = b_copy.get('polygon', [])
            if poly and isinstance(poly, list):
                if len(poly) >= 3 and isinstance(poly[0], (list, tuple)):
                    xs = [cls.safe_coord(p[0]) for p in poly if isinstance(p, (list, tuple)) and len(p) >= 1 and p[0] is not None]
                    ys = [cls.safe_coord(p[1]) for p in poly if isinstance(p, (list, tuple)) and len(p) >= 2 and p[1] is not None]
                elif len(poly) >= 6 and isinstance(poly[0], (int, float)):
                    xs = [cls.safe_coord(poly[i]) for i in range(0, len(poly) - 1, 2) if poly[i] is not None]
                    ys = [cls.safe_coord(poly[i + 1]) for i in range(0, len(poly) - 1, 2) if poly[i + 1] is not None]
                else:
                    xs, ys = [], []

                if xs and ys:
                    b_copy['x1'] = min(xs)
                    b_copy['y1'] = min(ys)
                    b_copy['x2'] = max(xs)
                    b_copy['y2'] = max(ys)
                else:
                    b_copy['x1'] = cls.safe_coord(b_copy.get('x1'), 0)
                    b_copy['y1'] = cls.safe_coord(b_copy.get('y1'), 0)
                    b_copy['x2'] = cls.safe_coord(b_copy.get('x2'), 0)
                    b_copy['y2'] = cls.safe_coord(b_copy.get('y2'), 0)
            else:
                b_copy['x1'] = cls.safe_coord(b_copy.get('x1'), 0)
                b_copy['y1'] = cls.safe_coord(b_copy.get('y1'), 0)
                b_copy['x2'] = cls.safe_coord(b_copy.get('x2'), 0)
                b_copy['y2'] = cls.safe_coord(b_copy.get('y2'), 0)
            normalized_boxes.append(b_copy)
        return normalized_boxes

    @staticmethod
    def resolve_panels_for_image(target_path: str) -> List[Any]:
        from src.domain.page_store import PageStore
        record = PageStore.load_page_record(target_path)
        return record.get("panels", [])

    def auto_sort_boxes(
        self,
        image_path: str,
        boxes: List[Dict[str, Any]],
        resolve_target_fn: Callable[[str], str]
    ) -> Dict[str, Any]:
        """
        Reordena todas as caixas de texto na ordem de leitura de mangá (Direita para Esquerda, Topo para Base),
        respeitando os painéis e quadros identificados se disponíveis.
        Se os painéis ainda não possuem polígonos refinados com OpenCV, refina sob demanda.
        """
        try:
            if not boxes:
                return {"success": True, "boxes": [], "panels": []}

            target = resolve_target_fn(image_path)
            panels = self.resolve_panels_for_image(target)

            normalized_boxes = self.normalize_polygon_boxes(boxes)

            # Refina ou detecta painéis sob demanda com OpenCV (guiado pelos balões)
            try:
                if os.path.exists(target):
                    import numpy as np
                    from PIL import Image
                    from src.domain.page_store import PageStore
                    from src.geometry.panels import refine_panels_to_polygons

                    with Image.open(target) as src_img:
                        img = src_img.convert("RGB")
                    full_gray = np.array(img.convert("L"))

                    if not panels:
                        from src.model_engines.yolo_layout_engine import YoloMapeador
                        mapper = YoloMapeador(bubble_conf=0.15)
                        detected_panels, _ = mapper.detect_panels_and_sort(img, normalized_boxes, gray_image=full_gray)
                        if detected_panels:
                            panels = detected_panels
                            PageStore.save_page_record(
                                target,
                                panels=panels,
                                dump_fn=dump_compact_map,
                            )
                        mapper.unload_panel_detector()
                    else:
                        # Re-refina polígonos com geometria computacional, calhas e balões da página
                        panels = refine_panels_to_polygons(img, panels, bubbles=normalized_boxes, gray_image=full_gray)
                        PageStore.save_page_record(
                            target,
                            panels=panels,
                            dump_fn=dump_compact_map,
                        )
            except Exception as ex:
                logger.warning("Falha ao refinar painéis em auto_sort_boxes para %s: %s", image_path, ex)

            from src.model_engines.yolo_layout_engine import YoloMapeador
            sorted_boxes = YoloMapeador.sort_bubbles_reading_order(normalized_boxes, panels=panels)

            speech_idx = 1
            for b in sorted_boxes:
                if not b.get("is_sfx"):
                    b['order'] = speech_idx
                    speech_idx += 1
                else:
                    b['order'] = None

            return {"success": True, "boxes": sorted_boxes, "panels": panels}
        except Exception as e:
            logger.error("Erro no auto_sort_boxes para %s: %s", image_path, e)
            return {"success": False, "error": str(e)}

    def detect_page_bubbles(
        self,
        image_path: str,
        white_only: bool,
        resolve_target_fn: Callable[[str], str],
        dump_map_fn: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Executa a detecção de balões de fala e quadros na página sob demanda.
        Preserva textos OCR e traduções pré-existentes mesclando com o _map.json existente.
        Gera polígonos OpenCV para quadros de mangá.
        """
        try:
            target = resolve_target_fn(image_path)
            if not os.path.exists(target):
                return {"success": False, "error": f"Arquivo não encontrado: {target}"}

            dump_map = dump_map_fn or dump_compact_map

            import numpy as np
            from PIL import Image
            from src.model_engines.yolo_layout_engine import YoloMapeador
            from src.domain.page_store import PageStore

            with Image.open(target) as src_img:
                img = src_img.convert("RGB")
            full_gray = np.array(img.convert("L"))
            mapper = YoloMapeador(bubble_conf=0.15)

            if white_only:
                detected_boxes = mapper.detect_white_bubbles(img)
            else:
                detected_boxes = mapper.detect_all_bubbles(img)

            # Detecta e refina quadros com OpenCV
            detected_panels = []
            try:
                detected_panels, _ = mapper.detect_panels_and_sort(img, detected_boxes, gray_image=full_gray)
            except Exception as panel_err:
                logger.warning("Falha na detecção de painéis para %s: %s", image_path, panel_err)
                detected_panels = []

            formatted_boxes = []
            for i, b in enumerate(detected_boxes):
                is_sfx_val = bool(b.get("is_sfx", b.get("label") == "text_free"))
                order_val = b.get("order")
                box_item = {
                    "id": b.get("id", i + 1),
                    "x1": int(b["x1"]),
                    "y1": int(b["y1"]),
                    "x2": int(b["x2"]),
                    "y2": int(b["y2"]),
                    "polygon": b.get("polygon", []),
                    "order": order_val if not is_sfx_val else None,
                    "label": b.get("label", "text_free" if is_sfx_val else "text_bubble"),
                    "confidence": b.get("confidence", 1.0),
                    "is_bubble": b.get("is_bubble", not is_sfx_val),
                    "is_sfx": is_sfx_val,
                    "text": b.get("text", "") or b.get("original", ""),
                    "translated_text": b.get("translated_text") or b.get("translated", ""),
                    "user_edited": bool(b.get("user_edited", False))
                }
                ai_t = b.get("ai_translated_text") or b.get("ai_translated")
                if not ai_t and box_item["translated_text"] and not box_item["user_edited"]:
                    ai_t = box_item["translated_text"]
                if ai_t:
                    box_item["ai_translated_text"] = ai_t

                box_item["translated"] = box_item["translated_text"]
                box_item["ai_translated"] = box_item.get("ai_translated_text", "")
                formatted_boxes.append(box_item)

            existing = PageStore.load_boxes(target)
            if isinstance(existing, list) and len(existing) > 0:
                for nb in formatted_boxes:
                    for eb in existing:
                        if abs(eb.get('x1', 0) - nb['x1']) < 30 and abs(eb.get('y1', 0) - nb['y1']) < 30:
                            if eb.get('text'):
                                nb['text'] = eb.get('text')
                            elif eb.get('original'):
                                nb['text'] = eb.get('original')

                            trans = eb.get('translated_text') or eb.get('translated') or ''
                            ai_trans = eb.get('ai_translated_text') or eb.get('ai_translated')
                            if not ai_trans and trans and not eb.get('user_edited'):
                                ai_trans = trans

                            if trans:
                                nb['translated_text'] = trans
                                nb['translated'] = trans
                            if ai_trans:
                                nb['ai_translated_text'] = ai_trans
                                nb['ai_translated'] = ai_trans

                            nb['user_edited'] = bool(eb.get('user_edited', False))
                            break

            if detected_panels:
                PageStore.save_page_record(
                    target,
                    boxes=formatted_boxes,
                    panels=detected_panels,
                    dump_fn=dump_map,
                )
            else:
                PageStore.save_boxes(target, formatted_boxes, dump_fn=dump_map)

            mapper.unload_bubble_detector()
            mapper.unload_panel_detector()

            return {
                "success": True,
                "boxes": formatted_boxes,
                "panels": detected_panels or [],
                "count": len(formatted_boxes),
                "message": f"{len(formatted_boxes)} balão(ões) detectado(s) com sucesso."
            }
        except Exception as e:
            logger.error("Erro no detect_page_bubbles para %s: %s", image_path, e)
            return {"success": False, "error": str(e)}
