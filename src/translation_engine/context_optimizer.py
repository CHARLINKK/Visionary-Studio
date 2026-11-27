import os
import json


def calculate_optimal_num_ctx(json_files: list[str], custom_instructions: str = "", model: str = None) -> int:
    """
    Realiza o Pre-Scan Adaptativo de Contexto do capítulo e imprime o relatório de tokens no console.
    Calcula a quantidade ideal de tokens de contexto (num_ctx) para a pior página do lote,
    arredondando para múltiplos seguros (1536, 1792, 2048, 2560, 3072, 4096).
    Se o modelo pertencer à classe de reasoning (DeepSeek-R1, QwQ), aloca margem de rastro de pensamento.
    """
    from src.translation_engine.prompt_builder import is_reasoning_model
    is_reasoning = is_reasoning_model(model)
    reasoning_headroom = 1024 if is_reasoning else 0

    base_prompt_tokens = 1150 + (len(custom_instructions) // 4 if custom_instructions else 0)
    max_page_tokens = 0
    total_page_tokens_sum = 0
    valid_pages_count = 0
    max_page_name = ""
    
    from src.domain.page_store import PageStore
    from src.utils.file_resilience import resilient_read_json
    for jpath in json_files:
        try:
            raw = resilient_read_json(jpath)
            if raw is None:
                continue
            bubbles = PageStore.extract_boxes(raw)
            total_chars = sum(len(b.get("text", "")) for b in bubbles if b.get("text"))
            page_tokens = int(total_chars / 1.8) + 200
            if total_chars > 0:
                valid_pages_count += 1
                total_page_tokens_sum += page_tokens
            if page_tokens > max_page_tokens:
                max_page_tokens = page_tokens
                max_page_name = os.path.basename(jpath).replace("_map.json", "")
        except Exception:
            continue
            
    history_tokens = 350
    total_peak = base_prompt_tokens + max_page_tokens + history_tokens + reasoning_headroom
    total_needed = int(total_peak * 1.25)
    
    optimal_ctx = 8192
    for threshold in [1536, 1792, 2048, 2560, 3072, 4096, 6144, 8192]:
        if total_needed <= threshold:
            optimal_ctx = threshold
            break

    from src.utils.vram_arbiter import vram_arbiter
    optimal_ctx = vram_arbiter.cap_context_for_tier(optimal_ctx)

    avg_page_tokens = (total_page_tokens_sum // valid_pages_count) if valid_pages_count > 0 else 0
    vram_saved_mb = max(0, (4096 - optimal_ctx) * 0.45)

    print("\n" + "═" * 68)
    print(" 📊 [VISIONARY] PRE-SCAN DE TOKENS & CONTEXTO DA PIPELINE")
    print("═" * 68)
    print(f"   • Prompt do Sistema & Diretrizes:   ~{base_prompt_tokens} tokens")
    if is_reasoning:
        print(f"   • Buffer de Raciocínio (<think>):   ~{reasoning_headroom} tokens (Reasoning Mode)")
    print(f"   • Histórico Narrativo Recente:      ~{history_tokens} tokens")
    print(f"   • Média por Página (Entrada/Saída): ~{avg_page_tokens} tokens")
    if max_page_name:
        print(f"   • Pico Máximo Estimado ({max_page_name}):     ~{total_peak} tokens (Página mais densa)")
    else:
        print(f"   • Pico Máximo Estimado do Lote:     ~{total_peak} tokens")
    print(f"   • Margem de Segurança Alocada:      +25%")
    print("   " + "─" * 64)
    print(f"   🎯 Janela de Contexto Definida:     {optimal_ctx} tokens (num_ctx)")
    if vram_saved_mb > 0:
        print(f"   ⚡ VRAM Economizada na GPU:         ~{vram_saved_mb:.1f} MB (vs padrão 4096)")
    print("═" * 68 + "\n")
    
    return optimal_ctx
