"""
Testes de Contrato de Dados e Validação de Esquema Pydantic (BubbleModel e PageDataModel).
Garante conformidade com dados legados e compatibilidade bidirecional com a interface.
"""

import pytest
from src.models.bubble import BubbleModel, PageDataModel


def test_bubble_model_from_clean_dict():
    raw = {
        "id": 1,
        "order": 1,
        "x1": 10,
        "y1": 20,
        "x2": 100,
        "y2": 200,
        "text": "Hello world",
        "translated_text": "Olá mundo",
        "ai_translated_text": "Olá mundo",
        "user_edited": False,
        "is_sfx": False,
        "polygon": [[10, 20], [100, 20], [100, 200], [10, 200]],
    }
    bubble = BubbleModel.model_validate(raw)
    assert bubble.id == 1
    assert bubble.text == "Hello world"
    assert bubble.translated_text == "Olá mundo"
    assert bubble.user_edited is False
    assert bubble.is_sfx is False
    assert len(bubble.polygon) == 4

    gui_data = bubble.to_gui_dict()
    assert gui_data["original"] == "Hello world"
    assert gui_data["text"] == "Hello world"
    assert gui_data["translated"] == "Olá mundo"
    assert gui_data["translated_text"] == "Olá mundo"
    assert gui_data["isSfx"] is False
    assert gui_data["is_sfx"] is False


def test_bubble_model_from_legacy_dict():
    # Dados legados com xmin/ymin, isSfx camelCase e chaves originais
    legacy = {
        "xmin": "15.4",
        "ymin": "25.8",
        "xmax": "150.2",
        "ymax": "250.9",
        "original": "Konnichiwa",
        "translated": "E aí!",
        "ai_translated": "Olá",
        "isSfx": True,
        "label": "text_free",
        "order": "3",
    }
    bubble = BubbleModel.model_validate(legacy)
    assert bubble.x1 == 15
    assert bubble.y1 == 26
    assert bubble.x2 == 150
    assert bubble.y2 == 251
    assert bubble.text == "Konnichiwa"
    assert bubble.translated_text == "E aí!"
    assert bubble.ai_translated_text == "Olá"
    # Como translated ('E aí!') difere de ai_translated ('Olá'), user_edited deve ser True automaticamente
    assert bubble.user_edited is True
    assert bubble.is_sfx is True
    assert bubble.order == 3
    assert bubble.id == 3

    storage = bubble.to_storage_dict()
    assert storage["x1"] == 15
    assert storage["translated_text"] == "E aí!"
    assert storage["user_edited"] is True
    assert storage["is_sfx"] is True


def test_bubble_model_handles_nested_text_dict():
    # Casos onde o OCR ou LLM salvou {'text': '...'} como dicionário
    corrupted = {
        "x1": 0,
        "y1": 0,
        "x2": 50,
        "y2": 50,
        "text": {"text": "Nested OCR"},
        "translated_text": {"text": "Nested Tradução"},
    }
    bubble = BubbleModel.model_validate(corrupted)
    assert bubble.text == "Nested OCR"
    assert bubble.translated_text == "Nested Tradução"


def test_page_data_model_from_legacy_list():
    raw_list = [
        {"x1": 0, "y1": 0, "x2": 10, "y2": 10, "text": "P1"},
        {"x1": 10, "y1": 10, "x2": 20, "y2": 20, "text": "P2"},
    ]
    page = PageDataModel.from_raw(raw_list)
    assert len(page.boxes) == 2
    assert page.boxes[0].text == "P1"
    assert page.boxes[1].text == "P2"

    gui_dict = page.to_gui_dict()
    assert len(gui_dict["boxes"]) == 2
    assert gui_dict["boxes"][0]["original"] == "P1"


def test_page_data_model_from_full_map_json():
    raw_map = {
        "boxes": [
            {"id": 1, "x1": 5, "y1": 5, "x2": 50, "y2": 50, "text": "Box 1"}
        ],
        "panels": [{"x1": 0, "y1": 0, "x2": 100, "y2": 100}],
        "backup": {"boxes": []}
    }
    page = PageDataModel.from_raw(raw_map)
    assert len(page.boxes) == 1
    assert len(page.panels) == 1
    assert page.backup == {"boxes": []}

    storage_dict = page.to_storage_dict()
    assert storage_dict["panels"] == [{"x1": 0, "y1": 0, "x2": 100, "y2": 100}]
