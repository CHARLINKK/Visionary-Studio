import json
import codecs
import urllib.request
import urllib.error
import urllib.parse
import http.client
import socket
import re
import time
import psutil

from src.config import Config
from src.translation_engine.prompt_builder import build_system_prompt, EXCLAMATION_CACHE, resolve_fast_path_exclamation
from src.translation_engine.nlp_heuristics import auto_link_speech_bubbles, semantic_split_text, safe_bubble_sort_key
from src.translation_engine.json_healer import parse_or_heal_translation_json
from src.translation_engine.few_shot_retriever import retrieve_relevant_few_shots
from src.translation_engine.translation_sanitizer import (
    _extract_proper_nouns_from_instructions,
    sanitize_translated_text,
    sync_trailing_punctuation,
    TRANSLATION_SCHEMA,
)
from src.batch_pipeline.session import get_current_session

_PUNCTUATION_OR_DIGITS_RE = re.compile(
    r'^[\s!?.,…—~\-_:;・！？～。、「」“”‘’"\'ー〜\(\)\[\]{}]+$|^\d+$'
)

_MODEL_FALLBACK_ALIASES = {
    "amadeus:7b": "hf.co/mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-GGUF:Q4_K_M",
    "amadeus:14b": "hf.co/mradermacher/Amadeus-Verbo-FI-Qwen2.5-14B-PT-BR-Instruct-GGUF:Q4_K_M",
    "amadeus:32b": "hf.co/mradermacher/AV-BI-Qwen2.5-32B-PT-BR-Instruct-GGUF:Q4_K_M",
}


def _clean_ocr_noise(text: str) -> str:
    """
    Higieniza ruídos óticos frequentes em texto de mangá antes de enviar ao LLM:
    - Des-hifeniza palavras quebradas por quebras de linha em balões estreitos (ex: 'DETERMI-\\nNATION' -> 'DETERMINATION').
    - Preserva rigorosamente gagueiras e hesitações canônicas de mangá (ex: 'N-NO', 'W-WHAT', 'I-IS THAT').
    - Normaliza quebras de linha e múltiplos espaços.
    """
    if not text or not isinstance(text, str):
        return ""
    # Quebras em balões estreitos partem palavras com hífen ("DETERMI-\nNATION").
    # Exigimos >=2 letras antes e depois (ou minúsculas após espaço) para não juntar gagueiras ("N-NO!").
    cleaned = re.sub(r'(\b[A-Za-z]{2,})-\s*\n+\s*([A-Za-z]{2,}\b)', r'\1\2', text)
    cleaned = re.sub(r'(\b[A-Za-z]{3,})-\s+([a-z]{2,}\b)', r'\1\2', cleaned)
    cleaned = re.sub(r'[ \t]*\n+[ \t]*', ' ', cleaned)
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
    return cleaned.strip()

_cached_ollama_base = None
_cached_ollama_base_time = 0.0


def _invalidate_ollama_base_cache():
    global _cached_ollama_base, _cached_ollama_base_time
    _cached_ollama_base = None
    _cached_ollama_base_time = 0.0


def _resolve_ollama_base_url() -> str:
    """Resolve a URL base do Ollama priorizando a porta configurada e aplicando cache com TTL."""
    global _cached_ollama_base, _cached_ollama_base_time
    now = time.time()
    if _cached_ollama_base and (now - _cached_ollama_base_time) < 15.0:
        return _cached_ollama_base

    cfg_base = str(Config.get("ollama_url", "http://127.0.0.1:11435/api")).replace("localhost", "127.0.0.1")
    candidates = [cfg_base]
    if "11434" not in cfg_base:
        candidates.append("http://127.0.0.1:11434/api")

    for cand in candidates:
        try:
            with urllib.request.urlopen(cand.rstrip("/") + "/tags", timeout=1.0):
                _cached_ollama_base = cand
                _cached_ollama_base_time = now
                return cand
        except Exception:
            pass

    _cached_ollama_base = cfg_base
    _cached_ollama_base_time = now
    return cfg_base


def _is_cancelled(session=None) -> bool:
    """Verifica interrupção cooperativa da sessão ativa do lote ou fallback legado."""
    active_session = session or get_current_session()
    if active_session and active_session.cancel_event.is_set():
        return True
    try:
        import src.run_batch as rb
        if hasattr(rb, "_cancel_event") and rb._cancel_event.is_set():
            return True
    except Exception:
        pass
    return False


def is_reasoning_model(model: str = None) -> bool:
    """Identifica se o modelo pertence à classe de reasoning (DeepSeek-R1, QwQ, Marco-o1, etc)."""
    if not model:
        return False
    m = str(model).lower().strip()
    reasoning_keywords = ("r1", "deepseek-r1", "qwq", "marco-o1", "reasoning", "reasoner")
    return any(k in m for k in reasoning_keywords)


def call_ollama(system_prompt: str, user_prompt: str, model: str, num_ctx: int = 2048, expected_chars: int = 500, prog_base: float = 0.0, prog_slice: float = 0.0, total_ids: int = 1, progress_emitter=None) -> str:
    """Faz a chamada HTTP para o Ollama com hyperparameters ajustados, num_predict dinâmico e stop tokens."""
    session = get_current_session()
    active_emitter = progress_emitter
    if active_emitter is None:
        try:
            from src.utils.pipeline_emitter import get_current_thread_emitter
            active_emitter = get_current_thread_emitter()
        except Exception:
            active_emitter = None
    
    physical_cores = psutil.cpu_count(logical=False) or 4
    num_threads = max(1, physical_cores)
    syntax_tokens = max(32, total_ids * 16)
    content_tokens = int(expected_chars * 0.45)
    base_predict = content_tokens + syntax_tokens + 48
    
    is_reasoning = is_reasoning_model(model)
    is_amadeus = "amadeus" in str(model).lower() or "av-bi" in str(model).lower()
    if is_reasoning:
        # Headroom de 1536 tokens dedicado ao rastro de pensamento do modelo (<think>...</think>)
        calc_predict = min(4096, max(1024, base_predict + 1536))
    else:
        calc_predict = min(4096, max(64, base_predict))
    
    if is_amadeus and not is_reasoning:
        # Amadeus 14B / 7B / 32B sweet-spot: fluidez de dublagem sem alucinação sintática
        temp = 0.40
        top_p = 0.90
        top_k = 40
        rep_pen = 1.08
    elif is_reasoning:
        temp = 0.55
        top_p = 0.85
        top_k = 30
        rep_pen = 1.05
    else:
        temp = 0.35
        top_p = 0.85
        top_k = 30
        rep_pen = 1.05

    ollama_options = {
        "temperature": temp,
        "num_ctx": num_ctx,
        "num_predict": calc_predict,
        "num_thread": num_threads,
        "top_k": top_k,
        "top_p": top_p,
        "repeat_penalty": rep_pen,
        "stop": ["<|im_end|>", "<|im_start|>", "<|endoftext|>", "<|END_OF_TURN_TOKEN|>", "<|START_OF_TURN_TOKEN|>", "</s>"]
    }
    
    num_gpu = Config.get("ollama_num_gpu", None)
    if num_gpu is not None:
        try:
            ollama_options["num_gpu"] = int(num_gpu)
        except (ValueError, TypeError):
            pass
    
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": True,
        "keep_alive": "30m",
        "options": ollama_options
    }
    # Para modelos tradicionais, aplica o esquema estrito de gramática.
    # Para modelos de reasoning, omite 'format' para permitir o fluxo natural de <think>...</think>.
    if not is_reasoning:
        data["format"] = TRANSLATION_SCHEMA
    
    ollama_base = _resolve_ollama_base_url()
    ollama_url = ollama_base.rstrip("/") + "/chat"
    
    try:
        from src.model_manager import ModelManager
        ModelManager().ensure_ollama_running()

        parsed_url = urllib.parse.urlparse(ollama_url)
        host = parsed_url.hostname or "127.0.0.1"
        if host == "localhost":
            host = "127.0.0.1"
        port = parsed_url.port or 11435
        path = parsed_url.path or "/api/chat"

        conn = http.client.HTTPConnection(host, port, timeout=1.0)
        payload_bytes = json.dumps(data).encode("utf-8")

        try:
            from src.utils.gpu_utils import ModelLoadTracker
            with ModelLoadTracker(model, is_ollama=True, progress_emitter=active_emitter):
                conn.request("POST", path, body=payload_bytes, headers={"Content-Type": "application/json"})

                # Aguarda o início da resposta do Ollama verificando cancelamento cooperativo a cada 1.0s
                start_time = time.time()
                response = None
                while not response:
                    if _is_cancelled(session):
                        print(" [Tradutor] Requisição interrompida pelo usuário antes da resposta.")
                        return ""
                    if time.time() - start_time > 300:
                        print("\n[Ollama Error] Timeout de 300s aguardando início da resposta do Ollama.")
                        return ""
                    try:
                        response = conn.getresponse()
                    except socket.timeout:
                        continue
                    except (http.client.HTTPException, OSError) as e:
                        if _is_cancelled(session):
                            return ""
                        raise e

                if response.status != 200:
                    err_msg = response.read().decode("utf-8", errors="replace")
                    if response.status == 404:
                        print(f"\n[Ollama Error] Modelo '{model}' não encontrado no Ollama (404 Not Found).")
                    else:
                        print(f"\n[Ollama Error] Erro HTTP {response.status}: {err_msg}")
                    return ""

                full_text = ""
                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                text_buffer = ""
                id_pattern = re.compile(r'"id"\s*:\s*["\']?(\d+)["\']?')
                last_reported = -1
                thinking_notified = False
                thought_done_notified = False

                while True:
                    if _is_cancelled(session):
                        print(" [Tradutor] Requisição interrompida pelo usuário.")
                        return ""

                    try:
                        chunk = response.read(1024)
                        if not chunk:
                            text_buffer += decoder.decode(b"", final=True)
                            remaining_line = text_buffer.strip()
                            if remaining_line:
                                try:
                                    chunk_data = json.loads(remaining_line)
                                    content = chunk_data.get("message", {}).get("content", "")
                                    full_text += content
                                except Exception:
                                    pass
                            break

                        text_chunk = decoder.decode(chunk, final=False)
                        text_buffer += text_chunk

                        while "\n" in text_buffer:
                            line, text_buffer = text_buffer.split("\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                chunk_data = json.loads(line)
                                content = chunk_data.get("message", {}).get("content", "")
                                full_text += content

                                if is_reasoning:
                                    if not thinking_notified and "<think>" in full_text:
                                        print(" [Tradutor] Modelo em deliberação cognitiva profunda (<think>)...", flush=True)
                                        thinking_notified = True
                                    elif thinking_notified and not thought_done_notified and "</think>" in full_text:
                                        print(" [Tradutor] Deliberação concluída (</think>). Gerando localização final...", flush=True)
                                        thought_done_notified = True

                                if prog_slice > 0 and total_ids > 0:
                                    eval_text = full_text
                                    if is_reasoning:
                                        if "</think>" in full_text:
                                            eval_text = full_text.split("</think>", 1)[-1]
                                        else:
                                            eval_text = ""
                                    matches = len(id_pattern.findall(eval_text))
                                    matches = min(matches, total_ids)
                                    current_prog = int(prog_base + (prog_slice * (matches / total_ids)))

                                    if current_prog > last_reported:
                                        if active_emitter is not None:
                                            active_emitter.emit_progress(current_prog)
                                        else:
                                            print(f"[PROGRESS:{current_prog}]", flush=True)
                                        last_reported = current_prog
                            except Exception:
                                pass
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if _is_cancelled(session):
                            return ""
                        raise e

                return full_text.strip()
        finally:
            try:
                conn.close()
            except Exception:
                pass
            
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"\n[Ollama Error] Modelo '{model}' não encontrado no Ollama (404 Not Found).")
        else:
            print(f"\n[Ollama Error] Erro HTTP {e.code}: {e.reason}")
        return ""
    except Exception as e:
        _invalidate_ollama_base_cache()
        print(f"\n[Ollama Error] Falha na requisição: {e}")
        return ""


def bubble_needs_translation(bubble: dict, model: str = None) -> bool:
    """
    Determina se um balão precisa de tradução para um determinado modelo LLM.
    
    Regras:
    - Balões vazios, marcados como [DELETE] ou SFX nunca precisam de tradução.
    - Se não possui nenhuma tradução (`translated_text` vazio), precisa de tradução.
    - Se um `model` for fornecido e o balão já possui `model_translations`:
      - Se este modelo específico ainda não tiver tradução registrada ou estiver em branco,
        precisa ser traduzido pelo novo modelo (mesmo que outro modelo ou edição humana já existam).
      - Se este modelo específico já traduziu o balão, NÃO precisa ser traduzido.
    - Se o balão já possui `translated_text` mas não tem `model_translations` (formato legado),
      preserva a tradução existente a menos que 'overwrite' seja forçado externamente.
    """
    if not isinstance(bubble, dict):
        return False
        
    txt = bubble.get("text", "")
    if not isinstance(txt, str) or not txt.strip() or txt.strip() == "[DELETE]" or bubble.get("is_sfx", False):
        return False
        
    translated_text = bubble.get("translated_text", "")
    has_any_trans = bool(isinstance(translated_text, str) and translated_text.strip())
    
    if not has_any_trans:
        return True
        
    if model:
        model_tr = bubble.get("model_translations")
        if isinstance(model_tr, dict) and model_tr:
            model_val = model_tr.get(model, "")
            return not bool(isinstance(model_val, str) and model_val.strip())
            
    return False


def translate_bubbles(bubbles: list[dict], context: list[dict] = None, model: str = None, preset: str = "boxing", custom_instructions: str = "", num_ctx: int = 2048, pause_callback=None, prog_base: float = 0.0, prog_slice: float = 0.0, progress_emitter=None) -> tuple[list[dict], list[dict]]:
    if not bubbles:
        return [], context or []
        
    if not model:
        raise ValueError("ERRO: Nenhum modelo de IA (LLM) foi fornecido para a tradução. Selecione um modelo.")
        
    bubbles = auto_link_speech_bubbles(bubbles)
    
    for b in bubbles:
        if bubble_needs_translation(b, model) and not b.get("group_id"):
            txt = b.get("text", "").strip()
            fast_trad = resolve_fast_path_exclamation(txt)
            if fast_trad:
                cached_text = fast_trad
                if "model_translations" not in b or not isinstance(b.get("model_translations"), dict):
                    b["model_translations"] = {}
                if model:
                    b["model_translations"][model] = cached_text
                if not b.get("user_edited"):
                    b["translated_text"] = cached_text
                    b["ai_translated_text"] = cached_text
                    b["user_edited"] = False
            elif _PUNCTUATION_OR_DIGITS_RE.match(txt):
                cached_text = txt
                if "model_translations" not in b or not isinstance(b.get("model_translations"), dict):
                    b["model_translations"] = {}
                if model:
                    b["model_translations"][model] = cached_text
                if not b.get("user_edited"):
                    b["translated_text"] = cached_text
                    b["ai_translated_text"] = cached_text
                    b["user_edited"] = False
    
    grouped_bubbles_by_gid = {}
    standalone_bubbles = []
    
    for b in bubbles:
        if bubble_needs_translation(b, model):
            gid = b.get("group_id")
            if gid:
                if gid not in grouped_bubbles_by_gid:
                    grouped_bubbles_by_gid[gid] = []
                grouped_bubbles_by_gid[gid].append(b)
            else:
                standalone_bubbles.append(b)
                
    payload_data = []
    group_lookup = {}
    _numeric_group_id_map = {}
    # Grupos mesclam múltiplos balões numa única fala com marcador `[CORTE]`.
    # Usamos IDs numéricos altos (90001+) no payload porque o schema JSON exige 'id' numérico
    # e IDs pequenos poderiam colidir com os balões individuais da página.
    _group_numeric_counter = 90001

    for b in standalone_bubbles:
        payload_data.append({
            "id": b.get("id"),
            "text": _clean_ocr_noise(b.get("text", ""))
        })

    for gid, group_list in grouped_bubbles_by_gid.items():
        group_list.sort(key=safe_bubble_sort_key)
        group_key = f"group_{gid}"
        group_lookup[group_key] = group_list

        combined_text = " [CORTE] ".join(_clean_ocr_noise(b.get("text", "")) for b in group_list)

        numeric_id = _group_numeric_counter
        _group_numeric_counter += 1
        _numeric_group_id_map[str(numeric_id)] = group_key

        payload_data.append({
            "id": numeric_id,
            "text": combined_text
        })
            
    if not payload_data:
        new_context = list(context) if context else []
        full_page_context = [{"id": b.get("id"), "text": b.get("translated_text", "")} for b in bubbles if b.get("translated_text")]
        if full_page_context:
            new_context.append(full_page_context)
        if len(new_context) > 6:
            new_context = new_context[-6:]
        return bubbles, new_context
        
    system_prompt = build_system_prompt(preset=preset, custom_instructions=custom_instructions, model=model)

    context_str = ""
    if context:
        context_str = "## Contexto Narrativo das Páginas Anteriores\n"
        for page_idx, page_ctx in enumerate(context[-2:], 1):
            context_str += f"### Página Recente {page_idx}:\n"
            for item in page_ctx:
                txt = item.get('text', '').replace('\n', ' ')
                if txt.strip():
                    context_str += f"- Fala: \"{txt}\"\n"
                    
    batch_size = 100
    batches = [payload_data[i:i + batch_size] for i in range(0, len(payload_data), batch_size)]
    total_ids = len(payload_data)
    
    page_chars = sum(len(b.get("text", "")) for b in payload_data)
    is_reasoning = is_reasoning_model(model)
    reasoning_est = 1024 if is_reasoning else 0
    est_page_tokens = 950 + int(page_chars / 1.8) + (len(context_str) // 4 if context_str else 0) + 120 + reasoning_est
    print(f" [Tradutor] Balões: {len(payload_data)} | Contexto usado: ~{est_page_tokens} / {num_ctx} tokens alocados")
    
    raw_trad_dict = {}
    session = get_current_session()
    
    for i, batch in enumerate(batches):
        if len(batches) > 1:
            print(f" [Tradutor] Processando lote {i+1}/{len(batches)} ({len(batch)} itens)...")
            
        batch_prog_slice = prog_slice * (len(batch) / total_ids)
        batch_prog_base = prog_base + (prog_slice * (sum(len(b) for b in batches[:i]) / total_ids))
        
        user_payload = json.dumps(batch, ensure_ascii=False)
        user_prompt = ""
        if context_str:
            user_prompt += context_str + "\n\n"

        # Injeta exemplos few-shot do glossário que tenham termos em comum com este lote
        batch_texts = [item.get("text", "") for item in batch]
        relevant_examples = retrieve_relevant_few_shots(batch_texts)
        if relevant_examples:
            user_prompt += "## Exemplos de Referência de Tom e Localização\n"
            for ex in relevant_examples:
                user_prompt += f'- Inglês: "{ex.get("en", "")}" → PT-BR: "{ex.get("pt", "")}"\n'
            user_prompt += "\n"

        user_prompt += "## Balões da Página Atual para Traduzir\n"
        user_prompt += "Substitua o campo 'text' pela melhor localização em PT-BR mantendo o mesmo 'id':\n"
        user_prompt += user_payload
        
        batch_chars = sum(len(item.get("text", "")) for item in batch)
        has_groups_in_batch = any(str(item.get("id", "")) in _numeric_group_id_map for item in batch)
        if has_groups_in_batch:
            batch_chars = int(batch_chars * 1.4) 

        max_retries = 3
        batch_success = False
        
        for attempt in range(max_retries):
            if _is_cancelled(session):
                break
                
            translated_json_str = call_ollama(
                system_prompt, 
                user_prompt, 
                model,
                num_ctx=num_ctx,
                expected_chars=batch_chars,
                prog_base=batch_prog_base, 
                prog_slice=batch_prog_slice, 
                total_ids=len(batch),
                progress_emitter=progress_emitter,
            )
            
            if _is_cancelled(session):
                print(" [Tradutor] Cancelamento detectado. Abortando tentativa de tradução.")
                break
                
            if not translated_json_str:
                print(f" [Tradutor] Falha na comunicação no lote {i+1}. Tentativa {attempt+1}/{max_retries}.")
                time.sleep(2)
                continue
                
            translated_data = parse_or_heal_translation_json(translated_json_str)
            
            if translated_data:
                for trad in translated_data:
                    if isinstance(trad, dict) and trad.get("id") is not None:
                        text_val = trad.get("text", "")
                        if text_val and text_val.strip() != "":
                            raw_id = str(trad.get("id"))
                            actual_id = _numeric_group_id_map.get(raw_id, raw_id)
                            raw_trad_dict[actual_id] = text_val
                            
                expected_keys = [_numeric_group_id_map.get(str(item.get("id")), str(item.get("id"))) for item in batch]
                received_keys = [k for k in expected_keys if k in raw_trad_dict and raw_trad_dict[k].strip()]
                
                if len(received_keys) >= len(expected_keys):
                    batch_success = True
                    break
                elif len(received_keys) > 0:
                    if attempt < max_retries - 1:
                        print(f" [Tradutor] Lote {i+1}: Retorno parcial ({len(received_keys)}/{len(expected_keys)} itens traduzidos). Tentando novamente ({attempt+1}/{max_retries})...")
                        time.sleep(2)
                        continue
                    else:
                        print(f" [Tradutor] Lote {i+1}: Retorno parcial aceito na tentativa final ({len(received_keys)}/{len(expected_keys)} itens).")
                        batch_success = True
                        break
                else:
                    print(f" [Tradutor] Falha ao extrair objetos correspondentes aos IDs do lote {i+1}. Tentativa {attempt+1}/{max_retries}.")
                    time.sleep(2)
            else:
                print(f" [Tradutor] Falha ao extrair objetos do JSON no lote {i+1}. Tentativa {attempt+1}/{max_retries}.")
                time.sleep(2)
                
        if _is_cancelled(session):
            print(" [Tradutor] Cancelamento confirmado. Abortando a tradução da página.")
            raise RuntimeError("Tradução cancelada pelo usuário")
            
        if not batch_success:
            print(f" [Tradutor] Falha final no lote {i+1} após {max_retries} tentativas. Mantendo originais para este lote.")
            
    final_trad_dict = {}
    preserve_terms = _extract_proper_nouns_from_instructions(custom_instructions)
    
    for orig in standalone_bubbles:
        orig_id = str(orig.get("id"))
        if orig_id in raw_trad_dict:
            raw_text = raw_trad_dict[orig_id].replace("[CORTE]", " ")
            sanitized = sanitize_translated_text(raw_text, preserve_terms=preserve_terms)
            final_trad_dict[orig_id] = sync_trailing_punctuation(orig.get("text", ""), sanitized)
            
    for group_key, group_list in group_lookup.items():
        if group_key in raw_trad_dict:
            full_translated = raw_trad_dict[group_key]
            orig_lens = [len(b.get("text", "")) for b in group_list]
            split_parts = semantic_split_text(full_translated, len(group_list), orig_lens)
            
            for b, part in zip(group_list, split_parts):
                sanitized = sanitize_translated_text(part, preserve_terms=preserve_terms)
                final_trad_dict[str(b.get("id"))] = sync_trailing_punctuation(b.get("text", ""), sanitized)
                
    for orig in bubbles:
        orig_id = str(orig.get("id"))
        if orig_id in final_trad_dict:
            trad_val = sanitize_translated_text(final_trad_dict[orig_id], preserve_terms=preserve_terms)
            if "model_translations" not in orig or not isinstance(orig.get("model_translations"), dict):
                orig["model_translations"] = {}
            if model:
                orig["model_translations"][model] = trad_val

            if not orig.get("user_edited"):
                orig["translated_text"] = trad_val
                orig["ai_translated_text"] = trad_val
                orig["user_edited"] = False
        elif not orig.get("translated_text"):
            orig["translated_text"] = ""

        if orig.get("translated_text") and not orig.get("ai_translated_text") and not orig.get("user_edited"):
            orig["ai_translated_text"] = orig["translated_text"]
            
    new_context = list(context) if context else []
    full_page_context = [{"id": b.get("id"), "text": b.get("translated_text", "")} for b in bubbles if b.get("translated_text")]
    new_context.append(full_page_context) 
    if len(new_context) > 6:
        new_context = new_context[-6:]
    
    return bubbles, new_context
