import os
from typing import List, Optional, Callable, Any

from src.batch_pipeline.session import _cancel_event
from src.batch_pipeline.glossary_builder import build_custom_instructions
from src.utils.vram_arbiter import vram_arbiter, VramPhase


def run_translation_phase(
    input_dir: str,
    output_dir: str,
    image_paths: List[str],
    model: Optional[str],
    preset: str = "neutral",
    overwrite: bool = False,
    prog_base: float = 0.0,
    phase2_weight: float = 35.0,
    progress_emitter: Optional[Any] = None,
    progress_callback: Optional[Callable[[float, Optional[str]], None]] = None,
    step_callback: Optional[Callable[[str, str], None]] = None,
    cancel_event: Optional[Any] = None,
) -> bool:
    """
    Executa a Fase 2: Tradução Automatizada com Ollama, injeção contextual
    de glossários e sincronização de TXT de capítulo.
    """
    if cancel_event is None:
        cancel_event = _cancel_event

    if cancel_event.is_set():
        return False

    if not model:
        print("[Batch] ERRO: Nenhum modelo de IA (LLM) foi fornecido. Impossível traduzir.")
        return False

    print("\n=== INICIANDO TRADUÇÃO ===")
    print(f"[Batch] Traduzindo páginas com {model}...")
    if progress_callback:
        progress_callback(prog_base, "Traduzindo páginas...")
    if step_callback:
        step_callback("TRADUÇÃO", f"Traduzindo páginas com {model}...")

    custom_instr = build_custom_instructions(input_dir)

    # Prepara a VRAM para a fase de tradução e limpa resíduos de visão
    vram_arbiter.prepare_phase(VramPhase.TRANSLATION)
    try:
        from src.step4_translator import OllamaTranslator
        step4_translator = OllamaTranslator(model=model, preset=preset, custom_instructions=custom_instr)
        target_bases = [os.path.splitext(os.path.basename(p))[0] for p in image_paths]

        step4_translator.process_directory(
            output_dir,
            output_dir,
            overwrite=overwrite,
            target_bases=target_bases,
            prog_base=prog_base,
            prog_weight=phase2_weight,
            progress_emitter=progress_emitter,
        )

        if not cancel_event.is_set():
            try:
                from src.utils.txt_sync import sync_chapter_txt
                sync_chapter_txt(input_dir)
            except Exception:
                pass

        return True
    finally:
        vram_arbiter.prepare_phase(VramPhase.IDLE)
