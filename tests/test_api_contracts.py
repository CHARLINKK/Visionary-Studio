"""
Testes de Blindagem da Dívida #2: Contratos de Dados, Tipagem, Assimetria e Nomenclatura Híbrida.
Garante que métodos RPC sejam acessíveis bidirecionalmente (camelCase <-> snake_case)
e que balões (cards/boxes) não sofram perda de flags como isSfx/is_sfx.
"""

import os
import json
import pytest
from fastapi.testclient import TestClient
from src.api_bridge import ApiBridge
from src.domain.bubble_contract import (
    to_snake_case,
    to_camel_case,
    normalize_bubble_for_gui,
    normalize_bubble_for_storage,
    reconcile_and_normalize_bubbles,
)
from src.api_services.studio_service import StudioService
from src.server import app


@pytest.fixture
def isolated_user_data(tmp_path, monkeypatch):
    """Garante isolamento completo contra gravação de dados reais do usuário."""
    fake_app_data = tmp_path / "visionary_test_data"
    fake_app_data.mkdir()
    monkeypatch.setenv("VISIONARY_USER_DATA", str(fake_app_data))
    return fake_app_data


def test_casing_converters():
    """Valida conversão precisa entre camelCase e snake_case."""
    assert to_snake_case("getPageData") == "get_page_data"
    assert to_snake_case("autoSortBoxes") == "auto_sort_boxes"
    assert to_snake_case("syncChapterTxt") == "sync_chapter_txt"
    assert to_snake_case("clearVRAM") == "clear_vram"
    assert to_snake_case("") == ""

    assert to_camel_case("get_page_data") == "getPageData"
    assert to_camel_case("auto_sort_boxes") == "autoSortBoxes"
    assert to_camel_case("sync_chapter_txt") == "syncChapterTxt"
    assert to_camel_case("") == ""


def test_api_bridge_bidirectional_casing_resolution():
    """
    Testa se o ApiBridge resolve transparentemente qualquer método em
    camelCase ou snake_case.
    """
    bridge = ApiBridge()

    # Métodos registrados em snake_case que devem responder em camelCase
    assert hasattr(bridge, "get_page_data")
    assert hasattr(bridge, "getPageData")
    assert callable(bridge.getPageData)

    assert hasattr(bridge, "save_page_layout")
    assert hasattr(bridge, "savePageLayout")
    assert callable(bridge.savePageLayout)

    assert hasattr(bridge, "detect_page_bubbles")
    assert hasattr(bridge, "detectPageBubbles")

    assert hasattr(bridge, "reorder_pages")
    assert hasattr(bridge, "reorderPages")

    assert hasattr(bridge, "create_page_backup")
    assert hasattr(bridge, "createPageBackup")

    # Métodos registrados em camelCase que devem responder em snake_case
    assert hasattr(bridge, "autoSortBoxes")
    assert hasattr(bridge, "auto_sort_boxes")
    assert callable(bridge.auto_sort_boxes)

    assert hasattr(bridge, "clearVRAM")
    assert hasattr(bridge, "clear_vram")

    assert hasattr(bridge, "getSettings")
    assert hasattr(bridge, "get_settings")

    assert hasattr(bridge, "getPipelineStatus")
    assert hasattr(bridge, "get_pipeline_status")

    # Atributos inexistentes (públicos e privados) não devem ser acessíveis
    assert not hasattr(bridge, "_non_existent_private")
    assert not hasattr(bridge, "non_existent_method_12345")
    with pytest.raises(AttributeError):
        _ = bridge.non_existent_method_12345


def test_bubble_contract_gui_normalization():
    """
    Testa se o normalizador de balões para o Frontend expõe simultaneamente
    as chaves snake_case e camelCase, prevenindo 'undefined' no React.
    """
    raw_box = {
        "x1": 10,
        "y1": 20,
        "x2": 100,
        "y2": 150,
        "text": "Hello world",
        "translated_text": "Olá mundo",
        "is_sfx": True,
        "user_edited": True
    }

    gui_box = normalize_bubble_for_gui(raw_box, index=0)

    # Simetria de texto original e traduzido
    assert gui_box["original"] == "Hello world"
    assert gui_box["text"] == "Hello world"
    assert gui_box["translated"] == "Olá mundo"
    assert gui_box["translated_text"] == "Olá mundo"

    # Simetria de flag SFX
    assert gui_box["is_sfx"] is True
    assert gui_box["isSfx"] is True
    assert gui_box["initial_box"] == [10, 20, 100, 150]
    assert gui_box["initial_polygon"] == []

    # Suporte a entrada já em camelCase (estilo React)
    react_box = {
        "x1": 5, "y1": 5, "x2": 50, "y2": 50,
        "original": "Boom!",
        "translated": "Cabum!",
        "isSfx": True
    }
    gui_box2 = normalize_bubble_for_gui(react_box, index=1)
    assert gui_box2["is_sfx"] is True
    assert gui_box2["isSfx"] is True
    assert gui_box2["text"] == "Boom!"


def test_bubble_contract_storage_normalization():
    """
    Testa se balões vindos do React com chaves camelCase (isSfx) são
    salvos canonicamente com 'is_sfx' sem descarte da flag.
    """
    frontend_box = {
        "x1": 15, "y1": 25, "x2": 80, "y2": 90,
        "text": "Kaboom",
        "translated": "Cabum",
        "isSfx": True,
        "polygon": [[15, 25], [80, 25], [80, 90], [15, 90]]
    }

    storage_box = normalize_bubble_for_storage(frontend_box, index=0)
    assert storage_box["is_sfx"] is True
    assert storage_box["translated_text"] == "Cabum"
    assert storage_box["original"] == "Kaboom"
    assert storage_box["polygon"] == [[15, 25], [80, 25], [80, 90], [15, 90]]
    assert storage_box.get("initial_box") is None

    # Preserva quando initial_box estiver presente
    box_with_init = {**frontend_box, "initial_box": [10, 20, 75, 85]}
    storage_with_init = normalize_bubble_for_storage(box_with_init, index=0)
    assert storage_with_init["initial_box"] == [10, 20, 75, 85]


def test_reconcile_and_normalize_bubbles_deduplication():
    """
    Testa a função canônica unificada de reconciliação de balões do StudioService:
    1. Higienização de coordenadas (None/float/string -> int).
    2. Recuperação de ai_translated_text por proximidade espacial quando o ID mudar.
    3. Inferência correta de flag user_edited.
    4. Preservação de atributos estruturais e metadados.
    """
    existing_boxes = [
        {
            "id": 1,
            "x1": 100, "y1": 100, "x2": 200, "y2": 200,
            "text": "Hello",
            "translated_text": "Olá",
            "ai_translated_text": "Olá",
            "user_edited": False
        },
        {
            "id": 2,
            "x1": 300, "y1": 300, "x2": 400, "y2": 400,
            "text": "Original speech",
            "translated_text": "Fala original",
            "ai_translated_text": "Fala original IA",
            "user_edited": False
        }
    ]

    new_boxes = [
        # Balão 1: Coordenadas sujas, ID novo (mas coordenadas próximas <= 30px), tradução inalterada
        {
            "id": 999,  # ID mudou
            "x1": "105.4", "y1": None, "x2": 200.1, "y2": 198,
            "translated": "Olá",  # Deve herdar ai_translated_text de ID 1 por proximidade
        },
        # Balão 2: Mesma ID 2, tradução alterada pelo usuário
        {
            "id": 2,
            "x1": 300, "y1": 300, "x2": 400, "y2": 400,
            "translated_text": "Fala customizada pelo letrista",
            "group_id": "group_zeta",
            "isSfx": True
        }
    ]

    reconciled = reconcile_and_normalize_bubbles(new_boxes, existing_boxes=existing_boxes)

    assert len(reconciled) == 2

    # Validação do Balão 1 (proximidade espacial)
    assert reconciled[0]["id"] == 999
    assert reconciled[0]["x1"] == 105
    assert reconciled[0]["y1"] == 0
    assert reconciled[0]["x2"] == 200
    assert reconciled[0]["y2"] == 198
    assert reconciled[0]["ai_translated_text"] == "Olá"
    assert reconciled[0]["translated_text"] == "Olá"
    assert reconciled[0]["user_edited"] is False
    assert reconciled[0]["order"] == 1

    # Validação do Balão 2 (edição de usuário com ID preservado)
    assert reconciled[1]["id"] == 2
    assert reconciled[1]["ai_translated_text"] == "Fala original IA"
    assert reconciled[1]["translated_text"] == "Fala customizada pelo letrista"
    assert reconciled[1]["user_edited"] is True
    assert reconciled[1]["group_id"] == "group_zeta"
    assert reconciled[1]["is_sfx"] is True
    assert reconciled[1]["order"] == 2


def test_reconcile_and_normalize_bubbles_unlinking_and_sfx_toggle_persistence():
    """
    Garante que desvincular um grupo (remover group_id) ou converter SFX em fala comum
    NUNCA ressuscita group_id ou is_sfx do existing_boxes no salvamento do layout.
    """
    existing_boxes = [
        {
            "id": 1,
            "x1": 100, "y1": 100, "x2": 200, "y2": 200,
            "text": "Fala 1",
            "group_id": "group_alpha",
            "is_sfx": True,
            "label": "text_free"
        },
        {
            "id": 2,
            "x1": 250, "y1": 250, "x2": 350, "y2": 350,
            "text": "Fala 2",
            "group_id": "group_alpha",
            "is_sfx": False,
            "label": "text_bubble"
        }
    ]

    updated_boxes_from_gui = [
        {
            "id": 1,
            "x1": 100, "y1": 100, "x2": 200, "y2": 200,
            "text": "Fala 1",
            "is_sfx": False,
            "label": "text_bubble"
        },
        {
            "id": 2,
            "x1": 250, "y1": 250, "x2": 350, "y2": 350,
            "text": "Fala 2",
        }
    ]

    reconciled = reconcile_and_normalize_bubbles(updated_boxes_from_gui, existing_boxes=existing_boxes)

    assert len(reconciled) == 2
    assert "group_id" not in reconciled[0]
    assert reconciled[0].get("is_sfx") is not True
    assert reconciled[0]["label"] == "text_bubble"
    assert "group_id" not in reconciled[1]


def test_studio_service_roundtrip_preserves_sfx_and_exposes_boxes_and_cards(tmp_path, isolated_user_data):
    """
    Simula o ciclo completo do estúdio:
    1. Salva um layout com caixas contendo isSfx (enviado pelo React).
    2. Lê os dados com get_page_data().
    3. Garante que get_page_data() retorne tanto 'cards' quanto 'boxes' com isSfx e is_sfx intactos.
    """
    chapter_dir = tmp_path / "TestChapter"
    chapter_dir.mkdir()
    page_img = chapter_dir / "001.png"
    page_img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimage")

    studio = StudioService(default_path=str(chapter_dir))

    # React envia balões usando convenção mista / camelCase
    boxes_from_react = [
        {
            "id": 1,
            "x1": 10, "y1": 10, "x2": 50, "y2": 50,
            "text": "Speech balloon",
            "translated": "Balão de fala",
            "isSfx": False,
        },
        {
            "id": 2,
            "x1": 60, "y1": 60, "x2": 120, "y2": 120,
            "original": "SFX BANG",
            "translated": "SFX BANG",
            "isSfx": True,  # React enviando isSfx!
        }
    ]

    save_res = studio.save_page_layout(str(page_img), boxes_from_react)
    assert save_res.get("success") is True

    # Verifica arquivo físico salvo em disco (Envelope v2)
    map_path = chapter_dir / "output" / "001_map.json"
    assert map_path.exists()
    with open(map_path, "r", encoding="utf-8") as f:
        disk_envelope = json.load(f)

    assert disk_envelope.get("version") == 2
    disk_boxes = disk_envelope["boxes"]
    assert len(disk_boxes) == 2
    # O segundo balão DEVE ter 'is_sfx': True gravado fisicamente
    assert disk_boxes[1].get("is_sfx") is True

    # Agora faz a leitura via get_page_data
    page_data = studio.get_page_data(str(page_img))
    assert page_data.get("success") is True
    # Contrato simétrico: 'cards' e 'boxes' devem estar presentes e serem idênticos
    assert "cards" in page_data
    assert "boxes" in page_data
    assert len(page_data["cards"]) == 2
    assert len(page_data["boxes"]) == 2

    # Verifica integridade das propriedades do balão SFX lido
    sfx_box = page_data["cards"][1]
    assert sfx_box.get("is_sfx") is True
    assert sfx_box.get("isSfx") is True


def test_fastapi_rpc_casing_and_defensive_payloads(isolated_user_data):
    """
    Testa o roteador RPC (/api/rpc/{method_name}) sob chamadas em
    camelCase, snake_case, payloads malformados e rotas proibidas.
    """
    client = TestClient(app)

    # 1. Chamada em camelCase para método originalmente snake_case
    resp1 = client.post("/api/rpc/checkPageBackup", json={"args": ["non_existent_path.png"], "kwargs": {}})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1.get("success") is True

    # 2. Chamada em snake_case para método originalmente camelCase
    resp2 = client.post("/api/rpc/auto_sort_boxes", json={"args": ["test.png", []], "kwargs": {}})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2.get("success") is True
    assert data2.get("result", {}).get("boxes") == []

    # 3. Payload malformado (body vazio ou null) não deve gerar crash 500
    resp3 = client.post("/api/rpc/getSettings", json=None)
    assert resp3.status_code == 200

    # 4. Método não existente deve retornar 404
    resp4 = client.post("/api/rpc/invalidMethodNameFooBar123", json={})
    assert resp4.status_code == 404

    # 5. Tentativa de invocar dunder ou método privado deve ser bloqueada (403)
    resp5 = client.post("/api/rpc/_secretMethod", json={})
    assert resp5.status_code == 403
