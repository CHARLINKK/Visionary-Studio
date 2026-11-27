"""
Módulo Construtor de Glossário e Referências para Tradução por IA.

Varre, consolida e compila as diretrizes terminológicas de múltiplas fontes:
1. Dicionário Global da Máquina (%APPDATA%/global_dictionary.json)
2. Dicionário do Projeto/Capítulo (global_dictionary.json no input_dir ou output/)
3. Referências de Personagens (references.json no input_dir, output/ ou pasta-pai)
4. Arquivos legados de texto (_glossary_global.txt e _glossary_temp.txt)

Gera um bloco de instruções de prioridade máxima para injeção no prompt do LLM.
"""

import os
import json
from typing import List


def _extract_terms_from_dict_file(filepath: str) -> List[str]:
    """Lê um arquivo global_dictionary.json e extrai regras formatadas para o prompt."""
    rules = []
    if not filepath or not os.path.exists(filepath):
        return rules
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        terms = []
        if isinstance(data, dict):
            if "terms" in data and isinstance(data["terms"], list):
                terms = data["terms"]
            else:
                for k, v in data.items():
                    if isinstance(v, str) and v.strip() and k.strip():
                        terms.append({"original": k, "translation": v})
        elif isinstance(data, list):
            terms = data

        for item in terms:
            if not isinstance(item, dict):
                continue
            orig = (item.get("original") or item.get("en") or item.get("term") or "").strip()
            trans = (item.get("translation") or item.get("pt") or item.get("target") or "").strip()
            notes = (item.get("notes") or "").strip()
            if orig and trans:
                line = f'- "{orig}" → "{trans}"'
                if notes:
                    line += f" ({notes})"
                rules.append(line)
    except Exception:
        pass
    return rules


def _extract_characters_from_ref_file(filepath: str) -> List[str]:
    """Lê um arquivo references.json e extrai regras de contexto e pronomes de personagens."""
    rules = []
    if not filepath or not os.path.exists(filepath):
        return rules
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        chars = []
        if isinstance(data, dict) and "characters" in data and isinstance(data["characters"], list):
            chars = data["characters"]
        elif isinstance(data, list):
            chars = data

        for c in chars:
            if not isinstance(c, dict):
                continue
            name = (c.get("name") or "").strip()
            if not name:
                continue
            gender = (c.get("gender") or "").strip().lower()
            role = (c.get("role") or "").strip()
            notes = (c.get("notes") or "").strip()

            desc_parts = []
            if gender in ("male", "m", "masculino", "homem"):
                desc_parts.append("gênero masculino (usar concordância masculina, ele/dele)")
            elif gender in ("female", "f", "feminino", "mulher"):
                desc_parts.append("gênero feminino (usar concordância feminina, ela/dela)")
            elif gender:
                desc_parts.append(f"gênero: {gender}")

            if role:
                desc_parts.append(f"papel: {role}")
            if notes:
                desc_parts.append(f"notas: {notes}")

            desc = "; ".join(desc_parts)
            if desc:
                rules.append(f'- Personagem "{name}": {desc}.')
            else:
                rules.append(f'- Personagem "{name}": preservar nome exato e concordância natural.')
    except Exception:
        pass
    return rules


def build_custom_instructions(input_dir: str) -> str:
    """Varre e compila diretrizes terminológicas consolidadas para injeção no prompt do LLM."""
    if not input_dir:
        return ""

    norm_input = os.path.normpath(os.path.abspath(input_dir))
    parent_dir = os.path.dirname(norm_input)
    instr_parts = []
    seen_terms = set()

    # 1. Dicionário Global da Máquina (Config / AppData)
    try:
        from src.config import get_app_data_dir
        appdata_dict = os.path.join(get_app_data_dir(), "global_dictionary.json")
        global_terms = _extract_terms_from_dict_file(appdata_dict)
        if global_terms:
            unique_terms = []
            for t in global_terms:
                if t not in seen_terms:
                    seen_terms.add(t)
                    unique_terms.append(t)
            if unique_terms:
                instr_parts.append("Dicionário Global do Usuário (regras terminológicas fixas):\n" + "\n".join(unique_terms))
    except Exception:
        pass

    # 2. Dicionário Específico da Obra ou do Capítulo
    chapter_dict_candidates = [
        os.path.join(parent_dir, "global_dictionary.json"),
        os.path.join(norm_input, "global_dictionary.json"),
        os.path.join(norm_input, "output", "global_dictionary.json"),
    ]
    chapter_terms = []
    for cand in chapter_dict_candidates:
        terms = _extract_terms_from_dict_file(cand)
        for t in terms:
            if t not in seen_terms:
                seen_terms.add(t)
                chapter_terms.append(t)
    if chapter_terms:
        instr_parts.append("Termos Fixos desta Obra/Capítulo:\n" + "\n".join(chapter_terms))

    # 3. Referências de Personagens (Gênero e Concordância)
    ref_candidates = [
        os.path.join(parent_dir, "references.json"),
        os.path.join(norm_input, "references.json"),
        os.path.join(norm_input, "output", "references.json"),
    ]
    char_rules = []
    seen_chars = set()
    for cand in ref_candidates:
        rules = _extract_characters_from_ref_file(cand)
        for r in rules:
            if r not in seen_chars:
                seen_chars.add(r)
                char_rules.append(r)
    if char_rules:
        instr_parts.append("Referências de Personagens (preserve nomes e concordância de gênero estritamente):\n" + "\n".join(char_rules))

    # 4. Arquivos legados de texto (_glossary_global.txt e _glossary_temp.txt)
    legacy_global = os.path.join(parent_dir, '_glossary_global.txt')
    if os.path.exists(legacy_global):
        try:
            with open(legacy_global, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    instr_parts.append(f"Instruções terminológicas globais em texto:\n{content}")
        except Exception:
            pass

    legacy_temp = os.path.join(norm_input, '_glossary_temp.txt')
    if os.path.exists(legacy_temp):
        try:
            with open(legacy_temp, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    instr_parts.append(f"Instruções terminológicas deste capítulo em texto:\n{content}")
        except Exception:
            pass

    if instr_parts:
        return "O usuário definiu este dicionário. DEVE respeitar RIGOROSAMENTE estas traduções:\n\n" + "\n\n".join(instr_parts)

    return ""
