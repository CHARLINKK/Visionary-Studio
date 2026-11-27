"""
Módulo de Contratos e Normalização Canônica de Balões e Nomenclatura.
Centraliza as transformações de dados entre o frontend (React / camelCase)
e a camada de persistência / serviços (Python / snake_case).
"""

import re
from typing import Dict, Any, Optional, List
from src.models.bubble import BubbleModel


def safe_coord(val: Any, default: int = 0) -> int:
    """
    Higieniza e converte coordenadas para inteiros de forma segura.
    Trata None, floats e representações em string com arredondamento seguro.
    """
    try:
        if val is None:
            return default
        return int(round(float(val)))
    except (ValueError, TypeError):
        return default


def to_snake_case(name: str) -> str:
    """
    Converte um identificador camelCase ou PascalCase em snake_case.
    Ex: 'getPageData' -> 'get_page_data'
        'autoSortBoxes' -> 'auto_sort_boxes'
        'syncChapterTxt' -> 'sync_chapter_txt'
        'clearVRAM' -> 'clear_vram'
    """
    if not name:
        return ""
    # Trata sequências como clearVRAM -> clear_vram
    s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()


def to_camel_case(name: str) -> str:
    """
    Converte um identificador snake_case em camelCase (com a primeira letra minúscula).
    Ex: 'get_page_data' -> 'getPageData'
        'auto_sort_boxes' -> 'autoSortBoxes'
    """
    if not name:
        return ""
    parts = name.split('_')
    if not parts:
        return ""
    return parts[0].lower() + ''.join(word.capitalize() for word in parts[1:])


def normalize_bubble_for_gui(b: Dict[str, Any], index: Optional[int] = None) -> Dict[str, Any]:
    """
    Normaliza um balão para entrega à interface React.
    Garante simetria total: expõe tanto chaves camelCase quanto snake_case
    para que qualquer componente frontend funcione sem regressão ou campos indefinidos.
    """
    if not isinstance(b, dict):
        return {}

    # Resolução de texto original
    orig_text = (
        b.get("original")
        or b.get("text")
        or b.get("ocr_raw")
        or ""
    )
    if isinstance(orig_text, dict):
        orig_text = orig_text.get("text", "")
    orig_text = str(orig_text or "")

    # Resolução de tradução atual
    trans_text = (
        b.get("translated_text")
        or b.get("translated")
        or b.get("text_ptbr")
        or b.get("ptbr")
        or ""
    )
    if isinstance(trans_text, dict):
        trans_text = trans_text.get("text", "")
    trans_text = str(trans_text or "")

    # Resolução de tradução gerada pela IA
    ai_trans_text = (
        b.get("ai_translated_text")
        or b.get("ai_translated")
        or ""
    )
    if isinstance(ai_trans_text, dict):
        ai_trans_text = ai_trans_text.get("text", "")
    ai_trans_text = str(ai_trans_text or "")

    # Resolução de edição do usuário
    user_edited_raw = b.get("user_edited")
    if user_edited_raw is not None:
        user_edited = bool(user_edited_raw)
    elif ai_trans_text and trans_text and trans_text.strip() != ai_trans_text.strip():
        user_edited = True
    else:
        user_edited = False

    # Resolução da flag de SFX (Efeito Sonoro)
    is_sfx_val = bool(
        b.get("is_sfx")
        or b.get("isSfx")
        or (b.get("label") == "text_free")
        or False
    )

    # Identificador e ordem
    order_val = b.get("order")
    if order_val is None and index is not None and not is_sfx_val:
        order_val = index + 1

    id_val = b.get("id")
    if id_val is None:
        id_val = order_val

    # Coordenadas e polígono
    x1 = b.get("x1", b.get("xmin", 10))
    y1 = b.get("y1", b.get("ymin", 10))
    x2 = b.get("x2", b.get("xmax", 50))
    y2 = b.get("y2", b.get("ymax", 50))
    polygon = b.get("polygon", [])

    label_val = b.get("label", "text_bubble")
    is_bubble_val = b.get("is_bubble", label_val == "text_bubble")

    res = {
        "id": id_val,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "polygon": polygon,
        # Chaves canônicas e sinônimos transparentes para o Frontend
        "original": orig_text,
        "text": orig_text,
        "translated": trans_text,
        "translated_text": trans_text,
        "ai_translated": ai_trans_text,
        "ai_translated_text": ai_trans_text,
        "user_edited": user_edited,
        "is_sfx": is_sfx_val,
        "isSfx": is_sfx_val,
        "label": label_val,
        "order": order_val,
        "group_id": b.get("group_id"),
        "confidence": b.get("confidence"),
        "panel_id": b.get("panel_id"),
        "area": b.get("area"),
        "ocr_raw": b.get("ocr_raw") or orig_text,
        "is_bubble": is_bubble_val,
        "bg_type": b.get("bg_type", "unknown"),
        "initial_box": b.get("initial_box") if (isinstance(b.get("initial_box"), list) and len(b.get("initial_box")) == 4) else [x1, y1, x2, y2],
        "initial_polygon": b.get("initial_polygon") if (isinstance(b.get("initial_polygon"), list) and len(b.get("initial_polygon")) > 0) else polygon
    }

    if isinstance(b.get("model_translations"), dict) and b["model_translations"]:
        res["model_translations"] = dict(b["model_translations"])

    return res


def normalize_bubble_for_storage(
    b: Dict[str, Any],
    index: int,
    existing_box: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Normaliza um balão vindo da interface para persistência segura em disco (_map.json).
    Garante integridade canônica:
    - Nunca descarta 'is_sfx' se o frontend tiver enviado 'isSfx'.
    - Salva as chaves canônicas esperadas por txt_sync.py e pipeline de inferência.
    """
    if not isinstance(b, dict):
        return {}

    # Resolução de texto original
    orig_text = (
        b.get("text")
        or b.get("original")
        or (existing_box.get("original") if existing_box else None)
        or (existing_box.get("text") if existing_box else None)
        or ""
    )
    if isinstance(orig_text, dict):
        orig_text = orig_text.get("text", "")
    orig_text = str(orig_text or "")

    # Resolução de tradução
    new_trans = (
        b.get("translated")
        or b.get("translated_text")
        or b.get("text_ptbr")
        or b.get("ptbr")
        or ""
    )
    if isinstance(new_trans, dict):
        new_trans = new_trans.get("text", "")
    new_trans = str(new_trans or "")

    # Resolução de tradução da IA
    ai_trans = (
        b.get("ai_translated_text")
        or b.get("ai_translated")
        or ""
    )
    if isinstance(ai_trans, dict):
        ai_trans = ai_trans.get("text", "")
    ai_trans = str(ai_trans or "")

    # Recupera de existing_box se não estiver explicitada
    if not ai_trans and existing_box:
        eb_ai = (
            existing_box.get("ai_translated_text")
            or existing_box.get("ai_translated")
        )
        if not eb_ai and (existing_box.get("translated_text") or existing_box.get("translated")) and not existing_box.get("user_edited"):
            eb_ai = existing_box.get("translated_text") or existing_box.get("translated")
        if eb_ai:
            ai_trans = str(eb_ai)

    is_user_edited = b.get("user_edited")
    if not ai_trans and new_trans and not is_user_edited:
        ai_trans = new_trans

    # Determinação do flag de edição
    if is_user_edited is not None:
        user_edited_final = bool(is_user_edited)
    elif ai_trans and new_trans and new_trans.strip() != ai_trans.strip():
        user_edited_final = True
    elif ai_trans and new_trans.strip() == ai_trans.strip():
        user_edited_final = False
    else:
        user_edited_final = False

    # Detecção segura de SFX (aceita tanto is_sfx quanto isSfx)
    is_sfx_val = bool(
        b.get("is_sfx")
        or b.get("isSfx")
        or (b.get("label") == "text_free")
        or False
    )

    box_data: Dict[str, Any] = {
        "x1": safe_coord(b.get("x1", 0)),
        "y1": safe_coord(b.get("y1", 0)),
        "x2": safe_coord(b.get("x2", 0)),
        "y2": safe_coord(b.get("y2", 0)),
        "original": orig_text,
        "text": orig_text,
        "translated_text": new_trans,
        "ai_translated_text": ai_trans,
        "user_edited": user_edited_final,
        "is_sfx": is_sfx_val,
        "order": int(b["order"]) if b.get("order") is not None else (None if is_sfx_val else index + 1)
    }

    if b.get("polygon") and len(b["polygon"]) > 0:
        box_data["polygon"] = b["polygon"]
    if b.get("group_id"):
        box_data["group_id"] = b["group_id"]
    if b.get("confidence") is not None:
        box_data["confidence"] = b["confidence"]
    if b.get("panel_id") is not None:
        box_data["panel_id"] = b["panel_id"]
    if b.get("area") is not None:
        box_data["area"] = b["area"]
    if b.get("ocr_raw"):
        box_data["ocr_raw"] = b["ocr_raw"]
    if b.get("is_bubble") is not None:
        box_data["is_bubble"] = bool(b["is_bubble"])
    if b.get("label"):
        box_data["label"] = b["label"]
    if b.get("bg_type"):
        box_data["bg_type"] = b["bg_type"]

    model_translations_dict = {}
    if existing_box and isinstance(existing_box.get("model_translations"), dict):
        model_translations_dict.update(existing_box["model_translations"])
    if isinstance(b.get("model_translations"), dict):
        model_translations_dict.update(b["model_translations"])
    if model_translations_dict:
        box_data["model_translations"] = model_translations_dict

    init_box = b.get("initial_box") or (existing_box.get("initial_box") if existing_box else None)
    if isinstance(init_box, list) and len(init_box) == 4:
        box_data["initial_box"] = [safe_coord(v) for v in init_box]
    init_poly = b.get("initial_polygon") or (existing_box.get("initial_polygon") if existing_box else None)
    if isinstance(init_poly, list) and len(init_poly) > 0:
        box_data["initial_polygon"] = init_poly

    return box_data


def reconcile_and_normalize_bubbles(
    boxes: List[Dict[str, Any]],
    existing_boxes: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Reconcilia, higieniza e normaliza uma lista de balões para persistência canônica em _map.json.
    - Higieniza coordenadas com safe_coord (float/string -> int arredondado).
    - Preserva ou recupera 'ai_translated_text' (por ID ou proximidade espacial <= 30px).
    - Infere e mantém 'user_edited' se o texto traduzido diferir da tradução de IA.
    - Preserva campos estruturais (polygon, group_id, is_sfx/isSfx, confidence, panel_id, area, ocr_raw, is_bubble, label, bg_type).
    - Garante numeração canônica sequencial de 'order' e preservação de 'id'.
    """
    if not isinstance(boxes, list):
        return []

    existing_boxes = existing_boxes or []
    existing_ai_map: Dict[str, str] = {}
    existing_by_id: Dict[str, Dict[str, Any]] = {}

    for eb in existing_boxes:
        if not isinstance(eb, dict):
            continue
        eb_id = eb.get("id")
        if eb_id is not None:
            existing_by_id[str(eb_id)] = eb
        ai_val = eb.get("ai_translated_text") or eb.get("ai_translated")
        if not ai_val and (eb.get("translated_text") or eb.get("translated")) and not eb.get("user_edited"):
            ai_val = eb.get("translated_text") or eb.get("translated")
        if ai_val and eb_id is not None:
            existing_ai_map[str(eb_id)] = str(ai_val)

    formatted_boxes: List[Dict[str, Any]] = []
    for i, b in enumerate(boxes):
        if not isinstance(b, dict):
            continue

        raw_id = b.get("id")
        box_id = raw_id if (raw_id is not None and str(raw_id).strip() != "") else (i + 1)
        box_id_str = str(box_id)

        matching_eb = existing_by_id.get(box_id_str)

        x1 = safe_coord(b.get("x1"), matching_eb.get("x1", 0) if matching_eb else 0)
        y1 = safe_coord(b.get("y1"), matching_eb.get("y1", 0) if matching_eb else 0)
        x2 = safe_coord(b.get("x2"), matching_eb.get("x2", 0) if matching_eb else 0)
        y2 = safe_coord(b.get("y2"), matching_eb.get("y2", 0) if matching_eb else 0)

        # Resolução de texto original / OCR
        if "text" in b and b["text"] is not None:
            orig_text = str(b["text"])
        elif "original" in b and b["original"] is not None:
            orig_text = str(b["original"])
        elif matching_eb and ("text" in matching_eb or "original" in matching_eb):
            orig_text = str(matching_eb.get("text") if matching_eb.get("text") is not None else matching_eb.get("original", ""))
        else:
            orig_text = ""

        # Resolução de texto traduzido
        if b.get("translated") is not None:
            new_trans = str(b.get("translated"))
        elif b.get("text_ptbr") is not None:
            new_trans = str(b.get("text_ptbr"))
        elif b.get("translated_text") is not None:
            new_trans = str(b.get("translated_text"))
        elif matching_eb:
            new_trans = str(matching_eb.get("translated_text") or matching_eb.get("translated") or matching_eb.get("text_ptbr") or "")
        else:
            new_trans = ""

        # Resolução de tradução gerada pela IA
        ai_trans = b.get("ai_translated_text") or b.get("ai_translated") or existing_ai_map.get(box_id_str) or ""

        # Busca por proximidade espacial caso o ID tenha mudado
        if not ai_trans and existing_boxes:
            for eb in existing_boxes:
                if not isinstance(eb, dict):
                    continue
                eb_x1 = safe_coord(eb.get("x1", 0))
                eb_y1 = safe_coord(eb.get("y1", 0))
                if abs(eb_x1 - x1) < 30 and abs(eb_y1 - y1) < 30:
                    eb_ai = eb.get("ai_translated_text") or eb.get("ai_translated")
                    if not eb_ai and (eb.get("translated_text") or eb.get("translated")) and not eb.get("user_edited"):
                        eb_ai = eb.get("translated_text") or eb.get("translated")
                    if eb_ai:
                        ai_trans = str(eb_ai)
                        break

        # Preserva ou define tradução da IA
        explicit_user_edited = b.get("user_edited")
        eb_user_edited = matching_eb.get("user_edited") if matching_eb else None
        has_trans_in_b = (b.get("translated") is not None or b.get("text_ptbr") is not None or b.get("translated_text") is not None)

        if not ai_trans and new_trans and not explicit_user_edited and not eb_user_edited:
            ai_trans = new_trans

        # Determinação do flag de edição
        if explicit_user_edited is not None:
            user_edited_final = bool(explicit_user_edited)
        elif not has_trans_in_b and eb_user_edited is not None:
            user_edited_final = bool(eb_user_edited)
        elif ai_trans and new_trans and new_trans.strip() != ai_trans.strip():
            user_edited_final = True
        elif ai_trans and new_trans.strip() == ai_trans.strip():
            user_edited_final = False
        elif eb_user_edited is not None:
            user_edited_final = bool(eb_user_edited)
        else:
            user_edited_final = False

        box_data = {
            "id": box_id,
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "label": b.get("label") or (matching_eb.get("label") if matching_eb else None) or "text_bubble",
            "bg_type": b.get("bg_type") or (matching_eb.get("bg_type") if matching_eb else None) or "unknown",
            "text": orig_text,
            "original": orig_text,
            "translated_text": new_trans,
            "ai_translated_text": ai_trans,
            "user_edited": user_edited_final,
            "order": len(formatted_boxes) + 1
        }

        # Campos opcionais estruturais
        polygon = b.get("polygon") if b.get("polygon") is not None else (matching_eb.get("polygon") if matching_eb else None)
        if polygon and len(polygon) > 0:
            box_data["polygon"] = polygon

        group_id = b.get("group_id") or b.get("groupId")
        if group_id:
            box_data["group_id"] = group_id

        if "is_sfx" in b or "isSfx" in b:
            is_sfx_val = bool(b.get("is_sfx") or b.get("isSfx"))
        elif b.get("label") is not None:
            is_sfx_val = (b.get("label") == "text_free")
        elif matching_eb:
            is_sfx_val = bool(matching_eb.get("is_sfx") or matching_eb.get("isSfx") or matching_eb.get("label") == "text_free")
        else:
            is_sfx_val = False

        if is_sfx_val:
            box_data["is_sfx"] = True
            box_data["label"] = "text_free"
            box_data["is_bubble"] = False
        else:
            if box_data.get("label") == "text_free":
                box_data["label"] = "text_bubble"

        for k in ["confidence", "panel_id", "area", "ocr_raw"]:
            val = b.get(k) if b.get(k) is not None else (matching_eb.get(k) if matching_eb else None)
            if val is not None:
                box_data[k] = val

        is_bubble_val = b.get("is_bubble") if b.get("is_bubble") is not None else (matching_eb.get("is_bubble") if matching_eb else None)
        if is_bubble_val is not None:
            box_data["is_bubble"] = bool(is_bubble_val)

        model_translations_dict = {}
        if matching_eb and isinstance(matching_eb.get("model_translations"), dict):
            model_translations_dict.update(matching_eb["model_translations"])
        if isinstance(b.get("model_translations"), dict):
            model_translations_dict.update(b["model_translations"])
        if model_translations_dict:
            box_data["model_translations"] = model_translations_dict

        init_box = b.get("initial_box") if b.get("initial_box") is not None else (matching_eb.get("initial_box") if matching_eb else None)
        if isinstance(init_box, list) and len(init_box) == 4:
            box_data["initial_box"] = [safe_coord(v) for v in init_box]
        init_poly = b.get("initial_polygon") if b.get("initial_polygon") is not None else (matching_eb.get("initial_polygon") if matching_eb else None)
        if isinstance(init_poly, list) and len(init_poly) > 0:
            box_data["initial_polygon"] = init_poly

        formatted_boxes.append(box_data)

    return formatted_boxes
