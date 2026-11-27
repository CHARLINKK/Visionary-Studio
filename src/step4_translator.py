import os
import json
import time
import urllib.request
import re
import traceback

from src.config import Config
from src.translation_engine.context_optimizer import calculate_optimal_num_ctx
from src.translation_engine.ollama_client import translate_bubbles, bubble_needs_translation

class OllamaTranslator:
    def __init__(self, model=None, preset="neutral", custom_instructions=""):
        if not model:
            raise ValueError("OllamaTranslator requer o nome do modelo LLM obrigatório.")
        self.model = model
        self.preset = preset
        self.custom_instructions = custom_instructions
                
    def process_directory(self, input_dir: str, output_dir: str, overwrite: bool = False, target_bases: list = None, prog_base: float = 0.0, prog_weight: float = 0.0, progress_emitter=None):
        json_files = [
            os.path.join(input_dir, f)
            for f in (os.listdir(input_dir) if os.path.isdir(input_dir) else [])
            if f.endswith("_map.json")
        ]

        context = []
        valid_files = []

        def _natural_sort_key(s):
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', os.path.basename(s))]

        target_bases_set = set(target_bases) if target_bases is not None else None
        for jpath in sorted(json_files, key=_natural_sort_key):
            base_name = os.path.basename(jpath).replace("_map.json", "")
            if target_bases_set is not None and base_name not in target_bases_set:
                continue
            valid_files.append((jpath, base_name))
            
        total_files = len(valid_files)
        if total_files == 0: return
        
        optimal_ctx = calculate_optimal_num_ctx([f[0] for f in valid_files], self.custom_instructions, model=self.model)
        print(f" [Tradutor] Pre-Scan Adaptativo: Contexto otimizado para {optimal_ctx} tokens (economiza VRAM).")
        
        slice_per_file = prog_weight / total_files
        from src.batch_pipeline.session import get_current_session, backup_file
        session = get_current_session()
        
        from src.domain.page_store import PageStore
        from src.utils.json_utils import dump_compact_map
        from src.utils.file_resilience import resilient_read_json

        for idx, (jpath, base_name) in enumerate(valid_files):
            if session.cancel_event.is_set():
                print(" Tradução cancelada pelo usuário.")
                break
                
            file_prog_base = prog_base + (idx * slice_per_file)
            out_path = os.path.join(output_dir, f"{base_name}_map.json")
            
            if not overwrite and os.path.exists(out_path):
                try:
                    raw_existing = resilient_read_json(out_path)
                    existing_bubbles = PageStore.extract_boxes(raw_existing) if raw_existing is not None else []
                        
                    needs_translation = any(bubble_needs_translation(b, self.model) for b in existing_bubbles)
                            
                    if existing_bubbles and not needs_translation:
                        model_str = f" por {self.model}" if self.model else ""
                        print(f" [TRADUÇÃO] Pág {idx+1:02d}/{total_files:02d} ({base_name}) ── Pulado (já 100% traduzido{model_str})")
                        payload_data = [
                            {
                                "id": b.get("id"), 
                                "text": (b.get("model_translations") or {}).get(self.model) or b.get("translated_text", "")
                            } 
                            for b in existing_bubbles
                        ]
                        context.append(payload_data)
                        if len(context) > 6:
                            context = context[-6:]
                        if progress_emitter:
                            progress_emitter.emit_progress(file_prog_base + slice_per_file)
                        elif prog_weight > 0:
                            print(f"[PROGRESS:{int(file_prog_base + slice_per_file)}]", flush=True)
                        continue
                except Exception:
                    pass
                
            if progress_emitter:
                progress_emitter.emit_step("TRADUÇÃO", f"Traduzindo ({idx+1}/{total_files}) {base_name}...")
            print(f" [TRADUÇÃO] ({idx+1}/{total_files}) Traduzindo balões de {base_name} via {self.model}...")
            t_page_start = time.time()
            try:
                read_source = out_path if (not overwrite and os.path.exists(out_path)) else jpath
                raw_source = resilient_read_json(read_source)
                if raw_source is None:
                    raise FileNotFoundError(f"Arquivo não encontrado ou vazio: {read_source}")
                bubbles = PageStore.extract_boxes(raw_source)
                if overwrite:
                    for b in bubbles:
                        b["translated_text"] = ""
                        b["ai_translated_text"] = ""
                        if isinstance(b.get("model_translations"), dict):
                            b["model_translations"].pop(self.model, None)
            except Exception as e:
                print(f" [ERRO] Erro ao ler {read_source}: {e}")
                continue
                
            try:
                translated_bubbles, context = translate_bubbles(
                    bubbles, 
                    context=context, 
                    model=self.model, 
                    preset=self.preset,
                    custom_instructions=self.custom_instructions,
                    num_ctx=optimal_ctx,
                    prog_base=file_prog_base,
                    prog_slice=slice_per_file,
                    progress_emitter=progress_emitter,
                )
                if len(context) > 6:
                    context = context[-6:]
                
                backup_file(out_path)
                PageStore.save_boxes(out_path, translated_bubbles, target_map_path=out_path, dump_fn=dump_compact_map)

                elapsed_sec = time.time() - t_page_start
                print(f" [TRADUÇÃO] Pág {idx+1:02d}/{total_files:02d} ({base_name}) ── Concluído em {elapsed_sec:.1f}s [SUCCESS]")
                if progress_emitter:
                    progress_emitter.emit_progress(file_prog_base + slice_per_file)
                elif prog_weight > 0:
                    print(f"[PROGRESS:{int(file_prog_base + slice_per_file)}]", flush=True)
            except Exception as page_err:
                print(f" [ERRO] Falha ao traduzir balões da página {base_name}: {page_err}")
                if "cancelada pelo usuário" in str(page_err) or session.cancel_event.is_set():
                    print(" [Tradutor] Abortando lote de páginas devido a cancelamento.")
                    break
                traceback.print_exc()
                
        try:
            from src.utils.txt_sync import sync_chapter_txt
            sync_chapter_txt(input_dir)
        except Exception:
            pass

        try:
            print(f" [Tradutor] Descarregando o modelo {self.model} da VRAM...")
            from src.utils.gpu_utils import unload_ollama_models
            unload_ollama_models(self.model)
        except Exception as e:
            print(f" [Tradutor] Aviso ao descarregar modelo: {e}")

if __name__ == "__main__":
    pass
