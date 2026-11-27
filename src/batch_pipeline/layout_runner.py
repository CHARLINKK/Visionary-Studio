import os
import json
import re
from typing import Dict, List, Any, Tuple, Optional, Callable
from PIL import Image
import numpy as np

from src.batch_pipeline.geometry import extract_perspective_crop
from src.batch_pipeline.session import _cancel_event, backup_file
from src.domain.page_store import PageStore
from src.utils.json_utils import dump_compact_map
from src.utils.gpu_utils import cleanup_gpu_memory
from src.utils.image_prefetcher import SafeImagePrefetcher


def load_existing_layout(
    images_to_process: List[str],
    output_dir: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Carrega balões e quadros pré-existentes dos arquivos JSON de mapeamento (_map.json),
    utilizado quando resume_from_layout=True.
    """
    all_phase1_boxes: Dict[str, Any] = {}
    all_phase1_panels: Dict[str, Any] = {}
    loaded_pages = 0
    total_loaded_balloons = 0
    missing_pages = 0

    for img_path in images_to_process:
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        map_path = os.path.join(output_dir, f"{base_name}_map.json")
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                raw_map = json.load(f)
                boxes = PageStore.extract_boxes(raw_map)
                panels = PageStore.extract_panels(raw_map)
                all_phase1_boxes[img_path] = boxes
                if panels:
                    all_phase1_panels[img_path] = panels
                loaded_pages += 1
                total_loaded_balloons += len(boxes) if isinstance(boxes, list) else 0
        except (FileNotFoundError, json.JSONDecodeError):
            missing_pages += 1

    if missing_pages > 0:
        print(f" [SISTEMA] Mapeamento prévio carregado: {loaded_pages} páginas sincronizadas ({total_loaded_balloons} balões) | {missing_pages} pendente(s).")
    else:
        print(f" [SISTEMA] Mapeamento prévio carregado: {loaded_pages} páginas sincronizadas com sucesso ({total_loaded_balloons} balões).")

    return all_phase1_boxes, all_phase1_panels


def run_layout_detection(
    images_to_process: List[str],
    output_dir: str,
    phase1_weight: float,
    only_layout: bool = False,
    deep_validation: bool = False,
    pause_callback: Optional[Callable] = None,
    debug: bool = False,
    progress_callback: Optional[Callable[[float, Optional[str]], None]] = None,
    step_callback: Optional[Callable[[str, str], None]] = None,
    cancel_event: Optional[Any] = None,
    direction: str = "rtl",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Executa a Fase 1A: Detecção YOLO de balões e quadros, correção de perspectiva manual
    e persistência de layout quando em modo exclusivo.
    """
    if cancel_event is None:
        cancel_event = _cancel_event

    total_pages = len(images_to_process)
    all_phase1_boxes: Dict[str, Any] = {}
    all_phase1_panels: Dict[str, Any] = {}

    yolo_weight_ratio = 1.0 if only_layout else 0.30
    yolo_page_weight = (phase1_weight * yolo_weight_ratio) / total_pages if total_pages > 0 else 0.0

    print(" [LAYOUT] Inicializando detector de balões e quadros (YOLO)...", flush=True)
    from src.model_engines.yolo_layout_engine import YoloMapeador
    step1_layout_detector = YoloMapeador()
    step1_layout_detector.load_bubble_detector()
    step1_layout_detector.load_panel_detector()
    print(f" [LAYOUT] Modelos YOLO prontos na GPU. Iniciando mapeamento de {total_pages} página(s)...", flush=True)

    prefetcher_layout = SafeImagePrefetcher(images_to_process, cancel_event=cancel_event)
    try:
        for idx, img_path in enumerate(images_to_process):
            if cancel_event.is_set():
                print(" [INFO] Processamento cancelado pelo usuário.")
                break

            page_base_prog = 5.0 + (idx * yolo_page_weight)
            if progress_callback:
                progress_callback(page_base_prog, None)

            base_name = os.path.splitext(os.path.basename(img_path))[0]
            if step_callback:
                step_callback("LAYOUT", f"Mapeando Layout (YOLO) ({idx+1}/{total_pages})...")
            print(f" [LAYOUT] ({idx+1}/{total_pages}) Detectando balões e quadros em {base_name}...")

            try:
                try:
                    next_path = images_to_process[idx + 1] if idx + 1 < total_pages else None
                    img = prefetcher_layout.get_image(img_path, next_path=next_path)
                except Exception as e:
                    print(f" [AVISO] Falha ao abrir {base_name}: {e}. Pulando.")
                    continue

                if progress_callback:
                    progress_callback(page_base_prog + yolo_page_weight * 0.1, None)
                full_gray = np.array(img.convert("L"))
                yolo_boxes = step1_layout_detector.detect_bubbles(img, gray_image=full_gray)
                if progress_callback:
                    progress_callback(page_base_prog + yolo_page_weight * 0.4, None)

                # Processa polígonos de 4 pontos (perspectiva manual)
                for box in yolo_boxes:
                    if "polygon" in box and len(box["polygon"]) == 4:
                        crop_img, x1, y1, x2, y2 = extract_perspective_crop(img, box["polygon"])
                        if crop_img is not None:
                            box["crop_img"] = crop_img
                            box["x1"] = x1
                            box["y1"] = y1
                            box["x2"] = x2
                            box["y2"] = y2
                            box["label"] = "text_bubble"
                            box["manual_perspective"] = True

                if pause_callback and not only_layout:
                    yolo_boxes = pause_callback(img_path, yolo_boxes)

                _pre_panels, yolo_boxes = step1_layout_detector.detect_panels_and_sort(img, yolo_boxes, gray_image=full_gray, direction=direction)
                yolo_boxes = step1_layout_detector.add_polygons(img, yolo_boxes, gray_image=full_gray)
                all_phase1_panels[img_path] = _pre_panels

                if debug:
                    step1_layout_detector.draw_map(img, _pre_panels, yolo_boxes, output_dir, base_name, debug=debug)

                if progress_callback:
                    progress_callback(page_base_prog + yolo_page_weight * 0.9, None)

                if only_layout and not deep_validation:
                    out_layout = os.path.join(output_dir, f"{base_name}_map.json")
                    backup_file(out_layout)
                    PageStore.save_page_record(
                        out_layout,
                        boxes=yolo_boxes,
                        panels=_pre_panels,
                        target_map_path=out_layout,
                        dump_fn=dump_compact_map,
                    )

                all_phase1_boxes[img_path] = yolo_boxes

                print(f" [LAYOUT] Pág {idx+1:02d}/{total_pages:02d} ({base_name}) ── {len(yolo_boxes)} balões, {len(_pre_panels)} quadros")
                if progress_callback:
                    progress_callback(page_base_prog + yolo_page_weight, None)

            except Exception as e:
                import traceback
                print(f" [ERRO] Falha na página {base_name}: {e}")
                traceback.print_exc()
                continue

    finally:
        prefetcher_layout.stop()
        step1_layout_detector.unload_bubble_detector()
        step1_layout_detector.unload_panel_detector()
        cleanup_gpu_memory()
        print(" [Pipeline] YOLO descarregado da VRAM e Caching Allocator limpo.")

    return all_phase1_boxes, all_phase1_panels


def run_deep_validation(
    images_to_process: List[str],
    output_dir: str,
    all_phase1_boxes: Dict[str, Any],
    all_phase1_panels: Dict[str, Any],
    only_layout: bool = False,
    cancel_event: Optional[Any] = None,
    direction: str = "rtl",
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """
    Executa a Validação Profunda opcional via Florence-2 em lotes, filtrando
    ruídos, onomatopeias espúrias e artefatos numéricos. Retorna as caixas refinadas
    e a instância ativa do FlorenceReader (se não for only_layout) para reuso na Fase 1B.
    """
    if cancel_event is None:
        cancel_event = _cancel_event

    if not all_phase1_boxes or cancel_event.is_set():
        return all_phase1_boxes, None

    print(" [VALIDAÇÃO] Carregando Florence-2 na VRAM (isolado do YOLO) para validação profunda...", flush=True)
    from src.model_engines.florence_ocr_engine import FlorenceReader
    shared_florence_reader = FlorenceReader()
    shared_florence_reader.load()
    print(" [VALIDAÇÃO] Florence-2 pronto para validação profunda.", flush=True)

    try:
        for img_path in images_to_process:
            if cancel_event.is_set():
                break
            if img_path not in all_phase1_boxes:
                continue
            base_name = os.path.splitext(os.path.basename(img_path))[0]
            yolo_boxes = all_phase1_boxes[img_path]
            try:
                with Image.open(img_path) as raw_img:
                    img = raw_img.convert("RGB")
                valid_boxes = []
                val_crops = []
                for b in yolo_boxes:
                    cx1 = max(0, b["x1"])
                    cy1 = max(0, b["y1"])
                    cx2 = min(img.width, b["x2"])
                    cy2 = min(img.height, b["y2"])
                    crop_val = img.crop((cx1, cy1, cx2, cy2))
                    target_w = min(512, crop_val.width * 2)
                    target_h = min(512, crop_val.height * 2)
                    crop_val = crop_val.resize((max(32, target_w), max(32, target_h)), Image.Resampling.BILINEAR)
                    val_crops.append(crop_val)

                val_results = []
                val_batch_size = 24
                for v_idx in range(0, len(val_crops), val_batch_size):
                    if cancel_event.is_set():
                        break
                    chunk_crops = val_crops[v_idx:v_idx+val_batch_size]
                    val_results.extend(shared_florence_reader.validate_crops_batch(chunk_crops))

                if cancel_event.is_set():
                    break

                excluded_snippets = []
                for b, text_raw in zip(yolo_boxes, val_results):
                    text = text_raw.strip() if text_raw else ""
                    clean_text = re.sub(r"<[^>]+>", "", text).strip()
                    has_alpha = bool(re.search(r"[a-zA-Z0-9぀-ゟ゠-ヿ一-龯]", clean_text))
                    is_garbage = len(clean_text) <= 1
                    is_numeric = clean_text.isdigit()
                    is_sfx = b.get("label") == "text_free" and len(clean_text.split()) <= 2

                    if clean_text and has_alpha and not is_sfx and not is_garbage and not is_numeric:
                        valid_boxes.append(b)
                    else:
                        snip = clean_text[:18] if clean_text else "Vazio"
                        excluded_snippets.append(f"'{snip}'")

                speech_order = 1
                for b in valid_boxes:
                    if not b.get("is_sfx"):
                        b["order"] = speech_order
                        speech_order += 1
                    else:
                        b["order"] = None



                all_phase1_boxes[img_path] = valid_boxes

                if only_layout:
                    out_layout = os.path.join(output_dir, f"{base_name}_map.json")
                    backup_file(out_layout)
                    PageStore.save_page_record(
                        out_layout,
                        boxes=valid_boxes,
                        panels=all_phase1_panels.get(img_path),
                        target_map_path=out_layout,
                        dump_fn=dump_compact_map,
                    )

                if excluded_snippets:
                    print(f" [VALIDAÇÃO] {base_name}: {len(excluded_snippets)} filtrado(s): {', '.join(excluded_snippets)}")
            except Exception as e:
                print(f" [AVISO] Falha na validação profunda de {base_name}: {e}")

    finally:
        if only_layout or cancel_event.is_set():
            shared_florence_reader.unload()
            shared_florence_reader = None
            cleanup_gpu_memory()
            print(" [Pipeline] Florence-2 (Validation) descarregado da VRAM.")

    return all_phase1_boxes, shared_florence_reader
