import json
import re


def _extract_list_from_parsed(data) -> list[dict]:
    """Extrai uma lista padronizada de dicts [{"id": ..., "text": ...}] de diferentes formatos de dados JSON."""
    if isinstance(data, list):
        items = []
        for item in data:
            if isinstance(item, dict) and "id" in item:
                items.append(item)
            elif isinstance(item, dict) and "text" in item:
                items.append(item)
        return items if items else data

    if isinstance(data, dict):
        # Caso padrão: {"translations": [...]} ou {"bubbles": [...]} ou qualquer chave com lista
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v

        # Caso chave-valor simples: {"1": "texto", "2": "texto"}
        if all(isinstance(k, (int, str)) and isinstance(v, str) for k, v in data.items()):
            return [{"id": k, "text": v} for k, v in data.items()]

        # Caso objeto único: {"id": 1, "text": "..."}
        if "id" in data or "text" in data:
            return [data]

    return []


def _strip_trailing_commas(s: str) -> str:
    """Remove vírgulas soltas antes de fechamentos de chaves ou colchetes."""
    return re.sub(r',\s*([}\]])', r'\1', s)


def _repair_truncated_json(raw_str: str) -> str:
    """
    Auto-repara JSON truncado por limite de tokens usando rastreamento de pilha LIFO.
    Fecha strings pendentes e desempilha chaves e colchetes na ordem exata de aninhamento.
    """
    repaired = raw_str.rstrip()
    repaired = re.sub(r',\s*$', '', repaired)
    
    # Rastreia pilha LIFO ignorando caracteres dentro de strings
    stack = []
    in_string = False
    escape = False

    for char in repaired:
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char in ('{', '['):
                stack.append(char)
            elif char == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif char == ']' and stack and stack[-1] == '[':
                stack.pop()

    if in_string:
        repaired += '"'

    # Uma vírgula pendente antes de fechar o container quebraria o json.loads
    repaired = re.sub(r',\s*$', '', repaired)

    while stack:
        opener = stack.pop()
        if opener == '{':
            repaired += '}'
        elif opener == '[':
            repaired += ']'

    return _strip_trailing_commas(repaired)


def strip_reasoning_traces(s: str) -> str:
    """
    Remove blocos de raciocínio de modelos de reasoning (<think> ... </think>),
    garantindo que rascunhos internos não contaminem o parser do payload JSON.
    """
    if not s or not isinstance(s, str):
        return ""
    # 1. Remove blocos completos <think>...</think> (case-insensitive)
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', s, flags=re.IGNORECASE)
    # 2. Se houver tag de fechamento solta (caso de início cortado), pega o que está depois
    if '</think>' in cleaned.lower():
        idx = cleaned.lower().rfind('</think>')
        cleaned = cleaned[idx + len('</think>'):]
    # 3. Se houver tag de abertura não fechada (caso de corte no final do pensamento)
    elif '<think>' in cleaned.lower():
        idx = cleaned.lower().find('<think>')
        cleaned = cleaned[:idx]
    return cleaned.strip()


def parse_or_heal_translation_json(raw_str: str) -> list[dict]:
    """Parse altamente tolerante a falhas sintáticas de LLMs (aspas internas não escapadas, quebras de linha literais, trailing commas e truncamentos)."""
    if not raw_str or not isinstance(raw_str, str):
        return []

    # Blindagem para modelos de reasoning: elimina rastros de <think>...</think> antes de qualquer extração
    raw_str = strip_reasoning_traces(raw_str)
    raw_str = raw_str.strip()
    
    # 0. Extração de bloco markdown se houver preâmbulos ou conclusões na resposta
    code_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_str)
    if code_match:
        inner = code_match.group(1).strip()
        if inner:
            raw_str = inner
    elif raw_str.startswith("```json"): raw_str = raw_str[7:]
    elif raw_str.startswith("```"): raw_str = raw_str[3:]
    if raw_str.endswith("```"): raw_str = raw_str[:-3]
    raw_str = raw_str.strip()
    
    # 1. Tentar json.loads padrão com strict=False (aceita quebras de linha literais dentro de strings)
    try:
        data = json.loads(raw_str, strict=False)
        extracted = _extract_list_from_parsed(data)
        if extracted:
            return extracted
    except Exception:
        pass

    # 1.05 Limpeza de trailing commas antes de desistir do parser nativo
    try:
        cleaned_commas = _strip_trailing_commas(raw_str)
        data = json.loads(cleaned_commas, strict=False)
        extracted = _extract_list_from_parsed(data)
        if extracted:
            return extracted
    except Exception:
        pass

    # 1.1 Localizar o início do envelope JSON ignorando preâmbulos de texto conversacional
    start_pos = -1
    for idx_char, ch in enumerate(raw_str):
        if ch in ('[', '{'):
            start_pos = idx_char
            break

    payload_candidate = raw_str[start_pos:] if start_pos != -1 else raw_str

    # 1.2 Tentar auto-reparar JSON truncado via pilha LIFO no payload completo
    try:
        repaired = _repair_truncated_json(payload_candidate)
        data = json.loads(repaired, strict=False)
        extracted = _extract_list_from_parsed(data)
        if extracted:
            return extracted
    except Exception:
        pass

    # 1.3 Tentar extrair envelope JSON se houver blocos fechados específicos
    json_envelope = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', raw_str)
    if json_envelope:
        candidate = json_envelope.group(1).strip()
        try:
            candidate = _strip_trailing_commas(candidate)
            data = json.loads(candidate, strict=False)
            extracted = _extract_list_from_parsed(data)
            if extracted:
                return extracted
        except Exception:
            pass

    # 2. Heurística Regex Avançada: extrair blocos { "id": ..., "text": ... } mesmo com aspas internas não escapadas
    items = []
    # Captura cada bloco de objeto {}
    blocks = re.findall(r'\{[^{}]*\}', raw_str)
    for blk in blocks:
        id_match = re.search(r'["\']?id["\']?\s*:\s*["\']?([a-zA-Z0-9_\-]+)["\']?', blk)
        if id_match:
            b_id = id_match.group(1)
            # Tenta capturar o campo 'text'
            # Padrão: "text"\s*:\s*" ... " onde o texto pode conter aspas internas sem quebrar
            text_match = re.search(r'["\']?text["\']?\s*:\s*"(.*)"\s*\}?$', blk.strip(), re.DOTALL)
            if not text_match:
                # Fallback sem aspa externa estrita
                text_match = re.search(r'["\']?text["\']?\s*:\s*["\']?(.*)', blk, re.DOTALL)

            if text_match:
                raw_text = text_match.group(1).strip()
                # Remove aspas de fechamento de objeto e chaves residuais no final
                raw_text = re.sub(r'["\']?\s*\}\s*$', '', raw_text).strip()
                if raw_text.startswith('"') and raw_text.endswith('"'):
                    raw_text = raw_text[1:-1]
                elif raw_text.startswith("'") and raw_text.endswith("'"):
                    raw_text = raw_text[1:-1]
                # Desescapa eventuais caracteres escapados
                raw_text = raw_text.replace('\\"', '"').replace('\\n', '\n')
                items.append({"id": b_id, "text": raw_text})

    return items
