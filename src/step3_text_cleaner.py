"""
Limpeza determinística do texto bruto devolvido pelo Florence-2 (Etapa 3 do pipeline).

Corrige alucinações comuns do OCR em inglês (reticências lidas como zeros, exclamações
lidas como '1' ou 'I', contrações partidas por espaço), normaliza pontuação de mangá e
marca efeitos sonoros puros para exclusão (`[DELETE]`) antes da tradução. Tudo roda
em memória e persiste no envelope v2 (`_map.json`) via `PageStore`.
"""

import os
import sys
import json
import re

# Carregado em runtime a partir de global_dictionary.json e references.json para evitar
# que nomes próprios ou siglas curtas (ex.: "K.O.") sejam confundidos com onomatopeias.
PROTECTED_STRINGS = set()

COMMON_NON_SFX = {
    'tv', 'pc', 'dr', 'mr', 'mrs', 'ms', 'jr', 'sr', 'st', 'vs', 'ft',
    'cd', 'dvd', 'dj', 'id', 'pr', 'vip', 'fbi', 'cia', 'kg', 'km', 'cm', 'mm', 'am', 'pm'
}


def clean_ocr_hallucinations(text: str) -> str:
    original = text.strip()

    # Descarta tokens especiais residuais emitidos pelo decoder do Florence-2
    text = re.sub(r'</?s>|<pad>|\|endoftext\||<[^>]+>', '', text)

    # Normaliza pontuação unicode para ASCII antes das regras de espaçamento
    text = text.replace("…", "...").replace("—", " -- ").replace("–", "-")
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("`", "'")

    # Florence-2 frequentemente lê reticências isoladas ("...") como sequência de zeros ou 'O'
    if re.fullmatch(r'[0oO\s\.]+', original) and len(original.replace(' ', '')) >= 2:
        return '...'

    # Exclamações estilizadas/pontiagudas de mangá costumam ser lidas como "1", "l", "I" ou "1.1.0.1"
    if original.strip() in ("I", "1"):
        pass
    elif re.fullmatch(r'[1lI0\.\s!]+', original) and original.count('.') >= 1 and not re.fullmatch(r'\d+\.\d{1,2}', original):
        return '!'
    elif re.fullmatch(r'[1lI\s]+', original):
        return '!' * len(original.replace(' ', ''))

    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    text = re.sub(r'[^\x00-\x7FÀ-ÿ♪♫♡♥★☆]+', '', text)

    # Junta contrações quebradas pelo OCR ("DIDN ' T" -> "DIDN'T") sem engolir gírias finais ("SOMETHIN' NEW")
    text = re.sub(r"\b([A-Za-z]+)\s*'\s*(t|s|m|d|ll|ve|re)\b", r"\1'\2", text, flags=re.IGNORECASE)

    # Normaliza reticências quebradas (". . .", "..", "....") para "..."
    text = re.sub(r'(?:\.\s*){3,}', '...', text)
    text = re.sub(r'\.\s*\.\s*\.', '...', text)
    text = re.sub(r'(?<!\.)\.\.(?!\.)', '...', text)
    text = re.sub(r'\.{4,}', '...', text)

    # "1" repetido colado ao fim de fala gritada ("STOP 11" -> "STOP!!") sem afetar "ROUND 1"
    text = re.sub(r'(?<=[A-Za-z])\s+1{2,}(?=\s*$|[!?])', lambda m: '!' * m.group().count('1'), text)

    # Tipografia de mangá: cola reticências e pontuação na palavra anterior, garantindo espaço depois
    text = re.sub(r'([A-Za-zÀ-ÿ0-9"\'\)\]])\s+\.\.\.', r'\1...', text)
    text = re.sub(r'\.\.\.(?=[A-Za-zÀ-ÿ0-9"\'\(\[])', '... ', text)
    text = re.sub(r'([A-Za-zÀ-ÿ0-9"\'\)\]])\s+([,;:!?])', r'\1\2', text)
    text = re.sub(r'([A-Za-zÀ-ÿ0-9"\'\)\]])\s+\.(?!\.)', r'\1.', text)
    text = re.sub(r'\.\.\.\s+([!?])', r'...\1', text)
    text = re.sub(r'([!?])\s+(?=[!?])', r'\1', text)

    # Espaço após pontuação seguida de palavra, sem quebrar números ("$1,000,000", "12:30")
    text = re.sub(r'(?<!\d)([,;:])(?=\d)|([,;:])(?=[A-Za-zÀ-ÿ"\'\(\[])', lambda m: (m.group(1) or m.group(2)) + ' ', text)
    text = re.sub(r'(?<!\.)\.(?!\.)(?=[A-Za-zÀ-ÿ"\'\(\[])', '. ', text)

    text = re.sub(r'([A-Za-z]+)-\s+([A-Za-z]+)', r'\1-\2', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    text = re.sub(r'\[\s+', '[', text)
    text = re.sub(r'\s+\]', ']', text)
    text = re.sub(r'"\s+([^"]+?)\s+"', r'"\1"', text)

    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def is_sfx_heuristic(text: str) -> bool:
    clean_text = re.sub(r'[^a-zA-Z\s]', '', text).strip().lower()
    if not clean_text:
        return False
    words = clean_text.split()
    if len(words) > 2:
        return False

    if any(w in COMMON_NON_SFX for w in words):
        return False

    # Palavras curtas sem nenhuma vogal ("TCH", "TSK", "BRRR", "ZZZ", "PFFT") são efeitos sonoros
    if all(not re.search(r'[aeiouy]', w) for w in words):
        return True

    return False


def is_narrative_heuristic(text: str) -> bool:
    """Identifica textos soltos fora de balão que são frases de narração (e não SFX)."""
    clean_text = re.sub(r'[^a-zA-Z\s]', '', text).strip().lower()
    words = clean_text.split()
    if len(words) > 2:
        return True
    stop_words = {'the', 'a', 'an', 'is', 'was', 'in', 'on', 'at', 'he', 'she', 'they', 'but', 'and', 'or', 'of', 'to'}
    if any(w in stop_words for w in words):
        return True
    return False


def _extract_terms_into_set(filepath: str, target_set: set):
    if not filepath or not os.path.isfile(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            if "terms" in data and isinstance(data["terms"], list):
                for item in data["terms"]:
                    if isinstance(item, dict):
                        orig = (item.get("original") or item.get("en") or item.get("term") or "").strip()
                        if orig and len(orig.split()) <= 3:
                            target_set.add(orig.upper())
            elif "characters" in data and isinstance(data["characters"], list):
                for char in data["characters"]:
                    if isinstance(char, dict):
                        name = (char.get("name") or "").strip()
                        if name:
                            target_set.add(name.upper())
                        for alias in char.get("aliases", []):
                            if isinstance(alias, str) and alias.strip():
                                target_set.add(alias.strip().upper())
            else:
                for key in data:
                    if key == "few_shot_examples":
                        continue
                    if isinstance(key, str) and key.strip() and len(key.split()) <= 3:
                        target_set.add(key.strip().upper())
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    orig = (item.get("original") or item.get("en") or item.get("term") or item.get("name") or "").strip()
                    if orig and len(orig.split()) <= 3:
                        target_set.add(orig.upper())
    except Exception:
        pass


def load_protected_terms(glossary_path: str = None) -> set:
    """
    Carrega termos protegidos (nomes de personagens e termos fixos) a partir do
    dicionário global (`global_dictionary.json`) e das referências do capítulo ativo.
    """
    protected = set(PROTECTED_STRINGS)

    try:
        from src.config import get_app_data_dir
        appdata_dict = os.path.join(get_app_data_dir(), "global_dictionary.json")
        _extract_terms_into_set(appdata_dict, protected)
    except Exception:
        pass

    try:
        root_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        root_dict = os.path.join(root_dir, "global_dictionary.json")
        _extract_terms_into_set(root_dict, protected)
    except Exception:
        pass

    if glossary_path:
        norm = os.path.normpath(glossary_path)
        if os.path.isfile(norm):
            _extract_terms_into_set(norm, protected)
        elif os.path.isdir(norm):
            for fname in ("global_dictionary.json", "references.json"):
                candidates = [
                    os.path.join(norm, fname),
                    os.path.join(norm, "output", fname),
                    os.path.join(os.path.dirname(norm), fname),
                ]
                for cand in candidates:
                    if os.path.isfile(cand):
                        _extract_terms_into_set(cand, protected)

    return protected


def clean_bubbles_list(bubbles: list[dict] | dict, glossary_path: str = None) -> list[dict] | dict:
    """
    Higieniza em memória o texto extraído pelo OCR (sem I/O de disco), atualizando
    a chave canônica `text` em listas v1 ou envelopes v2.
    """
    is_envelope = isinstance(bubbles, dict) and "boxes" in bubbles
    box_list = bubbles["boxes"] if is_envelope else bubbles
    if not isinstance(box_list, list):
        return bubbles

    protected = load_protected_terms(glossary_path)

    for b in box_list:
        if not isinstance(b, dict):
            continue
        # Remove resíduo legado de versões que duplicavam 'text' em 'text_clean'
        b.pop("text_clean", None)

        raw_val = b.get("text")
        raw = (raw_val if raw_val is not None else "").strip()
        is_bbl = b.get("is_bubble", b.get("label") == "text_bubble")

        if "ocr_raw" not in b and raw and raw != "[DELETE]":
            b["ocr_raw"] = raw

        norm_term = re.sub(r'[^a-zA-Z0-9\s]', '', raw).strip().upper()

        if norm_term not in protected and is_sfx_heuristic(raw):
            b["ocr_raw"] = b.get("ocr_raw") or raw
            b["text"] = "[DELETE]"
            b["is_sfx"] = True
            continue

        # Texto livre fora de balão com estrutura de frase é promovido para fala/narração
        if not is_bbl and is_narrative_heuristic(raw):
            b["is_sfx"] = False
            b["is_bubble"] = True
            b["label"] = "text_bubble"
            b["text"] = clean_ocr_hallucinations(raw)
            continue

        b["text"] = clean_ocr_hallucinations(raw)

    return bubbles


def process_ocr_map(json_path: str, model_name: str = None, glossary_path: str = None):
    from src.domain.page_store import PageStore
    from src.utils.json_utils import dump_compact_map

    boxes = PageStore.load_boxes(json_path)
    cleaned = clean_bubbles_list(boxes, glossary_path=glossary_path)
    PageStore.save_boxes(json_path, cleaned, target_map_path=json_path, dump_fn=dump_compact_map)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/step3_text_cleaner.py <path_to_ocr_json>")
        sys.exit(1)
    map_file = sys.argv[1]
    process_ocr_map(map_file)
