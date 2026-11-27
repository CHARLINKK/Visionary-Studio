import os
import sys
from PIL import ImageFile

# Proteção ativa contra crash de pipeline por imagens truncadas ou corrompidas
ImageFile.LOAD_TRUNCATED_IMAGES = True

src_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(src_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from src.config import Config
from src.utils.gpu_utils import cleanup_gpu_memory
from src.utils.json_utils import dump_compact_map, atomic_write_text

# Reexportação de contratos transacionais e sincronização para compatibilidade retroativa absoluta
from src.batch_pipeline.session import (
    _cancel_event,
    _rollback_flag,
    _session_backups,
    _session_outputs,
    _pipeline_lock,
    request_cancel,
    backup_file,
    execute_rollback,
    reset_session,
    get_current_session,
    scoped_session,
    BatchPipelineSession,
)
from src.batch_pipeline.geometry import (
    _calc_text_margin,
    extract_perspective_crop,
    deduplicate_spatial_regions,
)
from src.batch_pipeline.scanner import (
    VALID_EXTENSIONS,
    natural_sort_key,
    get_natural_sorted_images,
    filter_cached_images,
)
from src.batch_pipeline.glossary_builder import (
    build_custom_instructions,
)
from src.batch_pipeline.layout_runner import (
    load_existing_layout,
    run_layout_detection,
    run_deep_validation,
)
from src.batch_pipeline.ocr_runner import (
    run_ocr_phase,
)
from src.batch_pipeline.translation_runner import (
    run_translation_phase,
)
from src.utils.vram_arbiter import vram_arbiter, VramPhase, VRAMPhase


def run_batch_pipeline(
    input_dir: str,
    output_dir: str,
    preset="neutral",
    model=None,
    debug=False,
    overwrite=False,
    skip_ocr=False,
    skip_translate=False,
    pause_callback=None,
    only_layout=False,
    resume_from_layout=False,
    files_list=None,
    deep_validation=False,
    progress_emitter=None,
    session=None,
    direction="rtl",
):
    """Orquestrador principal do pipeline em lote:
    - Fase 1A: Detecção YOLO (Balões e Quadros)
    - Validação Profunda (Opcional) com Florence-2
    - Fase 1B: OCR de Alta Resolução com Florence-2
    - Fase 2: Tradução Automatizada com Ollama e Injeção de Glossários
    - Garantia estrita de isolamento de VRAM entre modelos."""

    def _report_prog(val: float, lbl: str = None):
        if progress_emitter:
            progress_emitter.emit_progress(val, lbl)
        else:
            if lbl:
                print(f"[{lbl}]", flush=True)
            print(f"[PROGRESS:{int(val)}]", flush=True)

    def _report_step(name: str, lbl: str):
        if progress_emitter:
            progress_emitter.emit_step(name, lbl)
        else:
            print(f"[{name}] {lbl}", flush=True)

    def _log(msg: str):
        is_stdout_scoped = False
        try:
            from src.utils.pipeline_emitter import ThreadScopedStdout
            if hasattr(sys.stdout, "_thread_emitters"):
                import threading
                tid = threading.get_ident()
                with sys.stdout._thread_lock:
                    is_stdout_scoped = tid in sys.stdout._thread_emitters
        except Exception:
            pass

        if progress_emitter and hasattr(progress_emitter, "emit_log") and not is_stdout_scoped:
            progress_emitter.emit_log(msg)
        print(msg, flush=True)

    active_session = session or get_current_session()
    active_session.reset()

    # Se rodamos Fase 1 (YOLO/Florence) que usa GPU, prepara a VRAM via árbitro central
    if not resume_from_layout and not skip_ocr:
        _log(" [Pipeline] Esvaziando VRAM residual (Ollama/PyTorch) via VramArbiter...")
        try:
            vram_arbiter.prepare_phase(VramPhase.LAYOUT, force_clean=True)
        except Exception:
            pass

    _report_prog(0, "Iniciando Pipeline de Lote...")
    _log(" [SISTEMA] Iniciando Pipeline de Lote...")

    os.makedirs(output_dir, exist_ok=True)
    input_dir, image_paths = get_natural_sorted_images(input_dir, files_list=files_list)

    if not image_paths:
        _log(f"Nenhuma imagem válida encontrada em {input_dir}")
        return None

    _log(f"Encontradas {len(image_paths)} imagens na fila para processamento.")

    images_to_process = list(image_paths)
    progress_available = 95.0

    if skip_ocr and not skip_translate:
        phase1_weight = 0.0
        phase2_weight = progress_available
    elif only_layout or skip_translate:
        phase1_weight = progress_available
        phase2_weight = 0.0
    else:
        phase1_weight = progress_available * 0.65
        phase2_weight = progress_available * 0.35

    # ==========================================
    # ETAPAS 1 & 2: DETECÇÃO HÍBRIDA & OCR
    # ==========================================
    if not skip_ocr:
        print("\n Iniciando Processamento em Lote...")
        print(f" Imagens encontradas: {len(image_paths)}")
        _report_prog(5, "Iniciando Processamento em Lote...")

        try:
            images_to_process = filter_cached_images(
                image_paths,
                output_dir,
                overwrite=overwrite,
                only_layout=only_layout,
                resume_from_layout=resume_from_layout,
            )

            if not images_to_process:
                print(" Nenhuma imagem nova para processar encontrada. Seguindo para os próximos passos...")
            else:
                total_pages = len(images_to_process)
                shared_florence_reader = None

                if not resume_from_layout:
                    all_phase1_boxes, all_phase1_panels = run_layout_detection(
                        images_to_process,
                        output_dir,
                        phase1_weight=phase1_weight,
                        only_layout=only_layout,
                        deep_validation=deep_validation,
                        pause_callback=pause_callback,
                        debug=debug,
                        progress_callback=_report_prog,
                        step_callback=_report_step,
                        cancel_event=active_session.cancel_event,
                        direction=direction,
                    )

                    if deep_validation and not active_session.cancel_event.is_set() and all_phase1_boxes:
                        all_phase1_boxes, shared_florence_reader = run_deep_validation(
                            images_to_process,
                            output_dir,
                            all_phase1_boxes=all_phase1_boxes,
                            all_phase1_panels=all_phase1_panels,
                            only_layout=only_layout,
                            cancel_event=active_session.cancel_event,
                            direction=direction,
                        )
                else:
                    all_phase1_boxes, all_phase1_panels = load_existing_layout(images_to_process, output_dir)

                if not only_layout and not active_session.cancel_event.is_set():
                    yolo_done_weight = phase1_weight * (0.30 if not resume_from_layout else 0.0)
                    ocr_total_weight = phase1_weight - yolo_done_weight
                    ocr_page_weight = ocr_total_weight / total_pages if total_pages > 0 else 0.0
                    ocr_base_prog = 5.0 + yolo_done_weight

                    run_ocr_phase(
                        images_to_process,
                        output_dir,
                        input_dir,
                        all_phase1_boxes=all_phase1_boxes,
                        all_phase1_panels=all_phase1_panels,
                        ocr_base_prog=ocr_base_prog,
                        ocr_page_weight=ocr_page_weight,
                        shared_florence_reader=shared_florence_reader,
                        overwrite=overwrite,
                        progress_callback=_report_prog,
                        step_callback=_report_step,
                        cancel_event=active_session.cancel_event,
                    )

        except Exception as e:
            import traceback
            print(f" Erro inesperado no pipeline de detecção/OCR: {e}")
            traceback.print_exc()
            if "CUDA out of memory" in str(e) or "OutOfMemoryError" in type(e).__name__:
                raise
            return False
        finally:
            shared_florence_reader = None
            cleanup_gpu_memory(force_ipc=True)

        if only_layout:
            if active_session.cancel_event.is_set():
                if active_session.rollback_flag:
                    print("\n Executando Rollback Cirúrgico...")
                    active_session.execute_rollback()
                    print(" Arquivos restaurados ao estado anterior.")
                try:
                    from src.utils.txt_sync import sync_chapter_txt
                    sync_chapter_txt(input_dir)
                except Exception:
                    pass
                return False
            if images_to_process and not all_phase1_boxes:
                print(" [ERRO] Nenhuma página teve o layout processado com sucesso.")
                return False
            return True

    # ==========================================
    # ETAPA 3: TRADUÇÃO OLLAMA
    # ==========================================
    # Liberação Preventiva de VRAM: Visão (PyTorch/Florence) -> LLM (Ollama)
    cleanup_gpu_memory(force_ipc=True)

    if not skip_translate and not active_session.cancel_event.is_set():
        prog_base = 5.0 + phase1_weight
        success = run_translation_phase(
            input_dir=input_dir,
            output_dir=output_dir,
            image_paths=image_paths,
            model=model,
            preset=preset,
            overwrite=overwrite,
            prog_base=prog_base,
            phase2_weight=phase2_weight,
            progress_emitter=progress_emitter,
            progress_callback=_report_prog,
            step_callback=_report_step,
            cancel_event=active_session.cancel_event,
        )
        if not success:
            return False

    if active_session.cancel_event.is_set():
        if active_session.rollback_flag:
            print("\n Executando Rollback Cirúrgico...")
            active_session.execute_rollback()
            print(" Arquivos restaurados ao estado anterior.")
        try:
            from src.utils.txt_sync import sync_chapter_txt
            sync_chapter_txt(input_dir)
        except Exception:
            pass
        return False

    _log("\n PROCESSAMENTO CONCLUÍDO COM SUCESSO! ")
    _report_prog(100, "Concluído")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python src/run_batch.py <input_folder_path> <output_folder_path> [preset] [model] [--overwrite] [--only-layout] [--resume-from-layout] [--direction rtl|ltr]")
        sys.exit(1)

    in_dir = sys.argv[1]
    out_dir = sys.argv[2]

    preset_arg = "neutral"
    model_arg = None
    overwrite_arg = False
    skip_ocr_arg = False
    skip_translate_arg = False
    only_layout_arg = False
    resume_from_layout_arg = False
    direction_arg = "rtl"

    args = sys.argv[3:]
    if "--overwrite" in args:
        overwrite_arg = True
        args.remove("--overwrite")
    if "--only-layout" in args:
        only_layout_arg = True
        args.remove("--only-layout")
    if "--resume-from-layout" in args:
        resume_from_layout_arg = True
        args.remove("--resume-from-layout")
    if "--skip-ocr" in args:
        skip_ocr_arg = True
        args.remove("--skip-ocr")
    if "--skip-translate" in args:
        skip_translate_arg = True
        args.remove("--skip-translate")
    if "--ltr" in args:
        direction_arg = "ltr"
        args.remove("--ltr")
    elif "--rtl" in args:
        direction_arg = "rtl"
        args.remove("--rtl")
    elif "--direction" in args:
        d_idx = args.index("--direction")
        if d_idx + 1 < len(args):
            direction_arg = args[d_idx + 1]
            args.pop(d_idx + 1)
        args.pop(d_idx)

    if len(args) > 0:
        preset_arg = args[0]
    if len(args) > 1:
        model_arg = args[1]

    run_batch_pipeline(
        in_dir,
        out_dir,
        preset=preset_arg,
        model=model_arg,
        overwrite=overwrite_arg,
        skip_ocr=skip_ocr_arg,
        skip_translate=skip_translate_arg,
        only_layout=only_layout_arg,
        resume_from_layout=resume_from_layout_arg,
        direction=direction_arg,
    )
