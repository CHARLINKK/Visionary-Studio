import os
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from src.batch_pipeline.geometry import _calc_text_margin, deduplicate_spatial_regions, extract_perspective_crop
from src.batch_pipeline.scanner import natural_sort_key, get_natural_sorted_images, filter_cached_images
from src.batch_pipeline.glossary_builder import build_custom_instructions
from src.batch_pipeline.session import request_cancel, backup_file, execute_rollback, reset_session
import src.run_batch as rb


def test_calc_text_margin():
    box = {"x1": 10, "y1": 10, "x2": 100, "y2": 100}
    # Centro (50, 50): distância até borda é 40 (50-10 ou 100-50)
    margin = _calc_text_margin(box, 50, 50)
    assert margin == 40
    # Próximo à borda esquerda (15, 50): distância até borda é 5 (15-10)
    assert _calc_text_margin(box, 15, 50) == 5


def test_deduplicate_spatial_regions():
    # Balão 1 e Balão 2 sobrepostos
    b1 = {
        "id": 1,
        "x1": 10, "y1": 10, "x2": 50, "y2": 50,
        "text": "Hello",
        "regions": [
            {"text": "Hello", "center": (20, 20)}
        ]
    }
    b2 = {
        "id": 2,
        "x1": 40, "y1": 10, "x2": 80, "y2": 50,
        "text": "Hello World",
        "regions": [
            {"text": "Hello", "center": (20, 20)},  # Região (20, 20) está dentro de b1 (margem 10 vs fora de b2)
            {"text": "World", "center": (60, 20)}   # Região (60, 20) está dentro de b2
        ]
    }
    bubbles = [b1, b2]
    deduplicate_spatial_regions(bubbles)

    # b1 deve reter "Hello"
    assert "text" in b1
    assert "regions" not in b1  # regions são removidas após dedup
    # b2 deve perder a cópia duplicada de "Hello" e ficar só com "World"
    assert b2["text"] == "World"


def test_scanner_natural_sort_and_filter(tmp_path):
    # Cria arquivos desordenados
    (tmp_path / "page10.png").write_bytes(b"dummy")
    (tmp_path / "page2.png").write_bytes(b"dummy")
    (tmp_path / "page1.png").write_bytes(b"dummy")

    resolved_dir, sorted_images = get_natural_sorted_images(str(tmp_path))
    basenames = [os.path.basename(p) for p in sorted_images]
    assert basenames == ["page1.png", "page2.png", "page10.png"]

    # Testa smart skip com map.json existente
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    map1 = out_dir / "page1_map.json"
    map1.write_text('[{"text": "Existing OCR"}]', encoding="utf-8")

    filtered = filter_cached_images(sorted_images, str(out_dir), overwrite=False, only_layout=False)
    # page1 já tem OCR completo e map_mtime recente, deve ser pulada
    assert len(filtered) == 2
    assert os.path.basename(filtered[0]) == "page2.png"
    assert os.path.basename(filtered[1]) == "page10.png"


def test_glossary_builder(tmp_path):
    chapter_dir = tmp_path / "Manga" / "Capitulo_01"
    chapter_dir.mkdir(parents=True)
    parent_dir = chapter_dir.parent

    # Cria glossário global e de capítulo
    (parent_dir / "_glossary_global.txt").write_text("Sensei -> Mestre", encoding="utf-8")
    (chapter_dir / "_glossary_temp.txt").write_text("Jutsu -> Técnica Secreta", encoding="utf-8")

    instr = build_custom_instructions(str(chapter_dir))
    assert "Sensei -> Mestre" in instr
    assert "Jutsu -> Técnica Secreta" in instr
    assert "O usuário definiu este dicionário" in instr


def test_session_reexport_contracts(tmp_path):
    # Valida que imports via src.run_batch mantêm compatibilidade total
    test_f = tmp_path / "file.json"
    test_f.write_text('{"v": 1}', encoding="utf-8")

    rb.backup_file(str(test_f))
    test_f.write_text('{"v": 2}', encoding="utf-8")

    rb.request_cancel(rollback=True)
    assert rb._cancel_event.is_set()
    assert rb._rollback_flag is True

    rb.execute_rollback()
    assert test_f.read_text(encoding="utf-8") == '{"v": 1}'
    rb.reset_session()
