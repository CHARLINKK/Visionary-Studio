import os
import re
from typing import Dict, List, Any, Optional, Callable
from PIL import Image

from src.batch_pipeline.geometry import deduplicate_spatial_regions
from src.batch_pipeline.session import _cancel_event, backup_file
from src.domain.page_store import PageStore
from src.utils.json_utils import dump_compact_map
from src.utils.image_prefetcher import SafeImagePrefetcher
from src.utils.vram_arbiter import vram_arbiter, VramPhase


def run_ocr_phase(
    images_to_process: List[str],
    output_dir: str,
    input_dir: str,
    all_phase1_boxes: Dict[str, Any],
    all_phase1_panels: Dict[str, Any],
    ocr_base_prog: float,
    ocr_page_weight: float,
    shared_florence_reader: Optional[Any] = None,
    overwrite: bool = False,
    progress_callback: Optional[Callable[[float, Optional[str]], None]] = None,
    step_callback: Optional[Callable[[str, str], None]] = None,
    cancel_event: Optional[Any] = None,
) -> List[str]:
    """
    Executa a Fase 1B: Extração de OCR de alta resolução com Florence-2,
    redimensionamento bilinear, deduplicação espacial e persistência transacional.
    """
    if cancel_event is None:
        cancel_event = _cancel_event

    total_pages = len(images_to_process)
    json_paths: List[str] = []

    vram_arbiter.prepare_phase(VramPhase.OCR)

    from src.model_engines.florence_ocr_engine import FlorenceReader
    from src.step3_text_cleaner import clean_bubbles_list

    if shared_florence_reader is not None:
        florence_reader = shared_florence_reader
    else:
        florence_reader = FlorenceReader()
        florence_reader.load()

    prefetcher_ocr = SafeImagePrefetcher(images_to_process, cancel_event=cancel_event)
    try:
        for idx, img_path in enumerate(images_to_process):
            if cancel_event.is_set():
                print(" Processamento cancelado pelo usuário.")
                break

            if img_path not in all_phase1_boxes:
                continue

            page_base_prog = ocr_base_prog + (idx * ocr_page_weight)
            if progress_callback:
                progress_callback(page_base_prog, None)

            base_name = os.path.splitext(os.path.basename(img_path))[0]
            if step_callback:
                step_callback("OCR", f"Extraindo Textos (OCR) ({idx+1}/{total_pages})...")
            print(f" [OCR] ({idx+1}/{total_pages}) Extraindo texto dos balões em {base_name}...")

            try:
                try:
                    next_path = images_to_process[idx + 1] if idx + 1 < total_pages else None
                    img = prefetcher_ocr.get_image(img_path, next_path=next_path)
                except Exception as e:
                    print(f" [AVISO] Não foi possível abrir a imagem {img_path}: {e}. Pulando.")
                    continue

                yolo_boxes = all_phase1_boxes[img_path]
                if progress_callback:
                    progress_callback(page_base_prog + ocr_page_weight * 0.1, None)

                hybrid_bubbles = []
                boxes_with_crops = []

                for yolo_b in yolo_boxes:
                    x1 = max(0, yolo_b.get("x1", 0))
                    y1 = max(0, yolo_b.get("y1", 0))
                    x2 = min(img.width, yolo_b.get("x2", 0))
                    y2 = min(img.height, yolo_b.get("y2", 0))
                    crop = yolo_b.pop("crop_img", None)

                    is_sfx = bool(
                        yolo_b.get("is_sfx")
                        or yolo_b.get("isSfx")
                        or (yolo_b.get("label") == "text_free")
                        or (yolo_b.get("bg_type") == "sfx")
                    )
                    if is_sfx:
                        if not yolo_b.get("text"):
                            yolo_b["text"] = ""
                        hybrid_bubbles.append(yolo_b)
                        continue

                    if not overwrite and yolo_b.get("text") and str(yolo_b["text"]).strip():
                        hybrid_bubbles.append(yolo_b)
                        continue

                    if crop is None:
                        crop = img.crop((x1, y1, x2, y2))

                    orig_w, orig_h = crop.width, crop.height
                    target_w = orig_w * 2
                    target_h = orig_h * 2
                    max_dim = 1536
                    if max(target_w, target_h) > max_dim:
                        scale = max_dim / float(max(target_w, target_h))
                        target_w = max(32, int(target_w * scale))
                        target_h = max(32, int(target_h * scale))

                    scale_x = target_w / float(orig_w) if orig_w > 0 else 1.0
                    scale_y = target_h / float(orig_h) if orig_h > 0 else 1.0

                    crop = crop.resize((target_w, target_h), Image.Resampling.BILINEAR)
                    boxes_with_crops.append((yolo_b, crop, x1, y1, scale_x, scale_y))

                base_batch_size = vram_arbiter.get_recommended_ocr_batch_size()
                total_boxes = len(boxes_with_crops)
                b_idx = 0

                while b_idx < total_boxes:
                    if cancel_event.is_set():
                        print(" [INFO] Cancelamento detectado durante OCR dos balões.")
                        break
                    current_ocr_prog = page_base_prog + (ocr_page_weight * 0.1) + (ocr_page_weight * 0.80 * (b_idx / total_boxes)) if total_boxes > 0 else page_base_prog + ocr_page_weight * 0.1
                    if progress_callback:
                        progress_callback(current_ocr_prog, None)

                    # Dynamic batch size adjustment based on VRAM headroom
                    current_batch_size = base_batch_size
                    has_headroom, _ = vram_arbiter.ensure_headroom_mb(500.0)
                    if not has_headroom and current_batch_size > 1:
                        current_batch_size = max(1, current_batch_size // 2)

                    chunk = boxes_with_crops[b_idx:b_idx+current_batch_size]
                    crops = [c[1] for c in chunk]

                    try:
                        batch_results = florence_reader.read_text_batch(crops)
                    except Exception as e:
                        err_str = str(e).lower()
                        if ("out of memory" in err_str or "cuda" in err_str or "allocation" in err_str) and len(crops) > 1:
                            vram_arbiter.ensure_headroom_mb(0.0)
                            batch_results = []
                            for single_crop in crops:
                                single_res = florence_reader.read_text_batch([single_crop])
                                batch_results.extend(single_res)
                        else:
                            raise

                    for (yolo_b, crop, x1, y1, scale_x, scale_y), text_data in zip(chunk, batch_results):
                        text = text_data.get("text", "")
                        regions = text_data.get("regions", [])

                        global_regions = []
                        for r in regions:
                            q = r["quad"]
                            g_q = []
                            for j in range(0, 8, 2):
                                g_q.append((q[j] / scale_x) + x1)
                                g_q.append((q[j+1] / scale_y) + y1)
                            global_regions.append({
                                "text": r["text"],
                                "quad": g_q,
                                "center": (
                                    (g_q[0] + g_q[2] + g_q[4] + g_q[6]) / 4,
                                    (g_q[1] + g_q[3] + g_q[5] + g_q[7]) / 4
                                )
                            })
                        yolo_b["regions"] = global_regions

                        text = text.replace('\n', ' ')
                        text = re.sub(r'\.\.\.\s*[Il]$', '...!', text)
                        text = text.replace("THEYL'LL", "THEY'LL")

                        yolo_b["text"] = text
                        yolo_b["ocr_raw"] = text
                        yolo_b["is_bubble"] = True
                        hybrid_bubbles.append(yolo_b)

                    b_idx += len(chunk)

                if cancel_event.is_set():
                    break

                # Deduplicação Espacial de Texto
                deduplicate_spatial_regions(hybrid_bubbles)

                # Preserva a ordenação de leitura definida na Fase 1A
                sorted_bubbles = []
                next_order = 1
                for b_order, b in enumerate(hybrid_bubbles):
                    b["id"] = b_order + 1
                    is_b_sfx = bool(
                        b.get("is_sfx")
                        or b.get("isSfx")
                        or (b.get("label") == "text_free")
                        or (b.get("bg_type") == "sfx")
                    )
                    if is_b_sfx:
                        b["order"] = None
                        b["is_sfx"] = True
                        b["is_bubble"] = False
                    else:
                        b["order"] = next_order
                        next_order += 1
                        b["is_sfx"] = False
                        b["is_bubble"] = True
                    sorted_bubbles.append(b)

                # Text Cleaner / Anti-Hallucination em memória
                try:
                    sorted_bubbles = clean_bubbles_list(sorted_bubbles, glossary_path=input_dir)
                except Exception:
                    pass

                out_ocr = os.path.join(output_dir, f"{base_name}_map.json")
                backup_file(out_ocr)
                PageStore.save_page_record(
                    out_ocr,
                    boxes=sorted_bubbles,
                    panels=all_phase1_panels.get(img_path),
                    target_map_path=out_ocr,
                    dump_fn=dump_compact_map,
                )

                # Auto-sync do .txt na 1ª página ou a cada 5 páginas
                if idx == 0 or (idx + 1) % 5 == 0 or (idx + 1) == total_pages:
                    try:
                        from src.utils.txt_sync import sync_chapter_txt
                        sync_chapter_txt(input_dir)
                    except Exception:
                        pass

                print(f" [OCR] Pág {idx+1:02d}/{total_pages:02d} ({base_name}) ── {len(sorted_bubbles)} balões extraídos [SUCCESS]")
                json_paths.append(out_ocr)
                if progress_callback:
                    progress_callback(page_base_prog + ocr_page_weight, None)

            except Exception as e:
                import traceback
                print(f" [ERRO] Falha na página {base_name}: {e}")
                traceback.print_exc()
                if "CUDA out of memory" in str(e) or "OutOfMemoryError" in type(e).__name__:
                    raise
                continue

    finally:
        prefetcher_ocr.stop()
        try:
            from src.utils.txt_sync import sync_chapter_txt
            sync_chapter_txt(input_dir)
        except Exception:
            pass

        florence_reader.unload()
        vram_arbiter.prepare_phase(VramPhase.IDLE)
        print(" [Pipeline] Florence-2 descarregado da VRAM e Caching Allocator limpo.")

    return json_paths
