import os
import json
import pytest
from src.batch_pipeline.glossary_builder import (
    _extract_terms_from_dict_file,
    _extract_characters_from_ref_file,
    build_custom_instructions,
)


def test_extract_terms_from_dict_file(tmp_path):
    dict_file = tmp_path / "global_dictionary.json"
    data = {
        "terms": [
            {"original": "Bankai", "translation": "Bankai", "notes": "Habilidade shinigami"},
            {"en": "Straw Hat", "pt": "Chapéu de Palha"},
            {"invalid": "entry"}
        ]
    }
    with open(dict_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    rules = _extract_terms_from_dict_file(str(dict_file))
    assert len(rules) == 2
    assert '- "Bankai" → "Bankai" (Habilidade shinigami)' in rules
    assert '- "Straw Hat" → "Chapéu de Palha"' in rules


def test_extract_terms_from_key_value_dict(tmp_path):
    dict_file = tmp_path / "global_dictionary.json"
    data = {
        "Kamehameha": "Kamehameha",
        "Senshi": "Guerreiro"
    }
    with open(dict_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    rules = _extract_terms_from_dict_file(str(dict_file))
    assert len(rules) == 2
    assert any("Kamehameha" in r for r in rules)
    assert any("Senshi" in r for r in rules)


def test_extract_characters_from_ref_file(tmp_path):
    ref_file = tmp_path / "references.json"
    data = {
        "characters": [
            {"name": "Luffy", "gender": "male", "role": "Capitão", "notes": "Gosta de carne"},
            {"name": "Nami", "gender": "female", "role": "Navegadora"},
            {"name": "Chopper"}
        ]
    }
    with open(ref_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    rules = _extract_characters_from_ref_file(str(ref_file))
    assert len(rules) == 3
    assert '- Personagem "Luffy": gênero masculino (usar concordância masculina, ele/dele); papel: Capitão; notas: Gosta de carne.' in rules
    assert '- Personagem "Nami": gênero feminino (usar concordância feminina, ela/dela); papel: Navegadora.' in rules
    assert '- Personagem "Chopper": preservar nome exato e concordância natural.' in rules


def test_build_custom_instructions_combines_all_sources(tmp_path, monkeypatch):
    # Mock do appdata_dir para não tocar o sistema real
    fake_appdata = tmp_path / "appdata"
    fake_appdata.mkdir()
    monkeypatch.setattr("src.config.get_app_data_dir", lambda: str(fake_appdata))

    # 1. Global dictionary no appdata
    with open(fake_appdata / "global_dictionary.json", "w", encoding="utf-8") as f:
        json.dump({"terms": [{"original": "GlobalTerm", "translation": "TermoGlobal"}]}, f)

    # 2. Obra/Capítulo
    work_dir = tmp_path / "MangaWork"
    chapter_dir = work_dir / "Chapter_01"
    chapter_dir.mkdir(parents=True)

    with open(work_dir / "references.json", "w", encoding="utf-8") as f:
        json.dump({"characters": [{"name": "Zoro", "gender": "male"}]}, f)

    with open(chapter_dir / "_glossary_temp.txt", "w", encoding="utf-8") as f:
        f.write("Ataque Especial = Golpe Fatal")

    instructions = build_custom_instructions(str(chapter_dir))
    assert "O usuário definiu este dicionário" in instructions
    assert '"GlobalTerm" → "TermoGlobal"' in instructions
    assert 'Personagem "Zoro"' in instructions
    assert "Ataque Especial = Golpe Fatal" in instructions


def test_build_custom_instructions_empty_when_no_glossaries(tmp_path, monkeypatch):
    fake_appdata = tmp_path / "empty_appdata"
    fake_appdata.mkdir()
    monkeypatch.setattr("src.config.get_app_data_dir", lambda: str(fake_appdata))

    empty_dir = tmp_path / "EmptyChapter"
    empty_dir.mkdir()

    instructions = build_custom_instructions(str(empty_dir))
    assert instructions == ""
