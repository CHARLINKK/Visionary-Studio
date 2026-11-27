import os
import json
import re
from functools import lru_cache

@lru_cache(maxsize=16)
def load_glossary_data(json_path: str) -> dict:
    """Carrega e armazena em cache o JSON de glossário/few-shot."""
    if not json_path or not os.path.isfile(json_path):
        return {}
    try:
        from src.utils.file_resilience import resilient_read_json
        data = resilient_read_json(json_path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def retrieve_relevant_few_shots(
    batch_texts: list[str],
    glossary_path: str = None,
    max_examples: int = 2
) -> list[dict]:
    """
    Localiza os exemplos few-shot mais semanticamente relevantes para o lote atual de balões
    usando correspondência de vocabulário (Token Overlap).
    Retorna no máximo `max_examples` pares (en -> pt) para manter o consumo de contexto <100 tokens.
    """
    if not batch_texts:
        return []

    if not glossary_path:
        base_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        glossary_path = os.path.join(base_dir, "models", "glossaries", "genikasuri.json")

    data = load_glossary_data(glossary_path)
    few_shots = data.get("few_shot_examples", [])
    if not few_shots:
        return []

    # Extrai conjunto de palavras-chave do lote atual (letras >= 3 caracteres, sem stopwords triviais)
    batch_blob = " ".join(batch_texts).lower()
    batch_words = set(re.findall(r'\b[a-z]{3,}\b', batch_blob))

    stopwords = {
        "the", "and", "that", "this", "what", "with", "for", "you", "your",
        "are", "have", "can", "not", "all", "get", "got", "just", "now", "see",
        "think", "want", "like", "make", "know", "say", "tell", "give", "take",
        "good", "bad", "day", "days", "time", "here", "there", "from", "about",
        "into", "some", "them", "their", "him", "her", "his", "was", "were",
        "been", "will", "would", "could", "should", "did", "does", "done", "doing",
        "why", "who", "how", "when", "where", "which", "out", "off", "over",
        "under", "again", "then", "once", "any", "both", "each", "few", "more"
    }
    query_words = batch_words - stopwords
    if not query_words:
        return []

    scored = []
    for ex in few_shots:
        en_text = ex.get("en", "").lower()
        ex_words = set(re.findall(r'\b[a-z]{3,}\b', en_text)) - stopwords
        overlap = len(query_words & ex_words)
        if overlap >= 2 or (overlap == 1 and any(len(w) >= 5 for w in (query_words & ex_words))):
            scored.append((overlap, ex))

    # Ordena por maior overlap de palavras-chave
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:max_examples]]
