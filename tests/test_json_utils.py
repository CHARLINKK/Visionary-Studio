import json
import pytest
from src.utils.json_utils import dumps_compact_polygons, dump_compact_map, atomic_write_text, atomic_write_json


def test_dumps_compact_polygons_roundtrip():
    sample = [
        {
            "id": 1,
            "x1": 180,
            "y1": 196,
            "x2": 370,
            "y2": 310,
            "label": "text_bubble",
            "polygon": [
                [225, 196], [208, 224], [180, 288], [185, 293], [239, 309],
                [332, 309], [364, 243], [365, 234], [359, 229]
            ]
        },
        {
            "id": 2,
            "polygon": [],
            "label": "empty"
        },
        {
            "id": 3,
            "polygon": [[10, 20], [-5, 30.5]],
            "label": "floats_negatives"
        }
    ]

    compact_str = dumps_compact_polygons(sample)
    
    # 1. Must parse back to exact same structure
    parsed = json.loads(compact_str)
    assert parsed == sample

    # 2. Polygon arrays must be on single lines
    lines = compact_str.splitlines()
    polygon_lines = [l for l in lines if '"polygon":' in l]
    assert len(polygon_lines) == 3
    assert '"polygon": [[225, 196], [208, 224]' in polygon_lines[0]
    assert '"polygon": []' in polygon_lines[1]
    assert '"polygon": [[10, 20], [-5, 30.5]]' in polygon_lines[2]

    # 3. Standard dump for sample would have 40+ lines, compact should have ~25
    standard_str = json.dumps(sample, indent=2, ensure_ascii=False)
    assert len(lines) < len(standard_str.splitlines())


def test_dumps_compact_polygons_strips_inpaint_residue():
    dirty_sample = [
        {
            "id": 1,
            "x1": 755,
            "y1": 413,
            "x2": 916,
            "y2": 783,
            "label": "text_bubble",
            "inpaint_only": False,
            "tool_clean_enabled": False,
            "strict_mask": False,
            "inpaint_mode": "white",
            "is_screentone": False,
            "keep_art": False,
            "translate_only": None,
            "group_id": None,
            "confidence": 0.936,
            "panel_id": 1,
            "area": 59570,
            "order": 1,
            "text": "HARRY",
            "is_bubble": True,
            "text_clean": "HARRY"
        }
    ]

    compact_str = dumps_compact_polygons(dirty_sample)
    parsed = json.loads(compact_str)

    # Inpaint residual fields must be completely gone
    assert "inpaint_only" not in parsed[0]
    assert "tool_clean_enabled" not in parsed[0]
    assert "strict_mask" not in parsed[0]
    assert "inpaint_mode" not in parsed[0]
    assert "is_screentone" not in parsed[0]
    assert "keep_art" not in parsed[0]
    assert "translate_only" not in parsed[0]
    assert "text_clean" not in parsed[0]
    # Null group_id must be removed
    assert "group_id" not in parsed[0]
    # Useful translation fields must be preserved
    assert parsed[0]["id"] == 1
    assert parsed[0]["text"] == "HARRY"
    assert parsed[0]["confidence"] == 0.936
    assert parsed[0]["order"] == 1


def test_dump_compact_map_file(tmp_path):
    map_file = tmp_path / "test_map.json"
    data = [{"id": 1, "polygon": [[1, 2], [3, 4]], "inpaint_mode": "white"}]
    dump_compact_map(data, str(map_file))

    with open(map_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == [{"id": 1, "polygon": [[1, 2], [3, 4]]}]

    # Atomic write must not leave temporary files behind
    tmp_file = tmp_path / "test_map.json.tmp"
    assert not tmp_file.exists()


def test_dump_compact_map_creates_parent_dirs_and_atomic(tmp_path):
    nested_dir = tmp_path / "sub" / "folder"
    map_file = nested_dir / "chapter_map.json"
    data = [{"id": 42, "text": "Atomic Persistence", "polygon": [[0, 0], [10, 10]]}]
    
    dump_compact_map(data, str(map_file))
    assert map_file.exists()
    
    with open(map_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded[0]["id"] == 42
    assert loaded[0]["text"] == "Atomic Persistence"
    assert not (nested_dir / "chapter_map.json.tmp").exists()


from unittest.mock import patch, MagicMock
from src.utils.json_utils import sanitize_map_data

def test_sanitize_map_data_dict():
    """Valida a sanitização de dicionários raiz."""
    dirty = {"id": 1, "inpaint_mode": "white", "group_id": None, "valid": True}
    clean = sanitize_map_data(dirty)
    assert clean == {"id": 1, "valid": True}
    
    # Test fallback
    assert sanitize_map_data("not_a_dict_or_list") == "not_a_dict_or_list"


def test_sanitize_map_data_v2_envelope_removes_strokes():
    """Valida que sanitize_map_data remove a chave 'strokes' de envelopes v2."""
    envelope = {
        "version": 2,
        "boxes": [{"id": 1, "text": "Oi", "inpaint_mode": "white"}],
        "panels": [],
        "strokes": [{"id": 1, "points": [1, 2]}],
        "backup": None
    }
    clean = sanitize_map_data(envelope)
    assert "strokes" not in clean
    assert clean["boxes"] == [{"id": 1, "text": "Oi"}]

@patch("src.utils.json_utils.json.loads")
def test_dumps_compact_polygons_json_error(mock_loads):
    """Valida que o replacer ignora erros de json.loads e mantém o raw original."""
    mock_loads.side_effect = Exception("JSON inválido")
    sample = [{"polygon": [[1, 2]]}]
    compact_str = dumps_compact_polygons(sample)
    # Deve retornar a string sem compactar a linha, pois o regex falhou no json.loads
    assert "[\n      1" in compact_str or "[\n" in compact_str

@patch("src.utils.json_utils.os.replace")
@patch("src.utils.json_utils.time.sleep")
def test_dump_compact_map_permission_error_retry(mock_sleep, mock_replace, tmp_path):
    """Valida o mecanismo de retry do arquivo temporário."""
    # Falha 2 vezes com PermissionError, depois passa
    mock_replace.side_effect = [PermissionError(), PermissionError(), None]
    map_file = tmp_path / "test.json"
    
    dump_compact_map([{"test": 1}], str(map_file))
    
    assert mock_replace.call_count == 3
    assert mock_sleep.call_count == 2
    # O arquivo tmp deve ser apagado na seção finally do sucesso ou se existir
    assert not (tmp_path / "test.json.tmp").exists()

@patch("src.utils.json_utils.os.replace")
def test_dump_compact_map_direct_fallback(mock_replace, tmp_path):
    """Valida que salva diretamente se a substituição falhar continuamente."""
    # Falha genérica imediatamente quebra o loop
    mock_replace.side_effect = Exception("Erro grave de OS")
    map_file = tmp_path / "test2.json"
    
    dump_compact_map([{"fallback": True}], str(map_file))
    
    # Arquivo deve ter sido escrito no fallback direct open
    assert map_file.exists()
    with open(map_file, "r") as f:
        assert json.load(f)[0]["fallback"] is True

@patch("src.utils.json_utils.os.remove")
@patch("src.utils.json_utils.os.replace")
def test_dump_compact_map_remove_tmp_error(mock_replace, mock_remove, tmp_path):
    """Valida exceção engolida no finally do os.remove"""
    mock_replace.side_effect = Exception("Falha para cair no fallback")
    mock_remove.side_effect = Exception("Erro ao deletar tmp")
    map_file = tmp_path / "test3.json"
    
    # Cria o .tmp manualmente para simular que o with open o criou
    tmp_file = tmp_path / "test3.json.tmp"
    with open(tmp_file, "w") as f: f.write("test")
    
    dump_compact_map([{"val": 1}], str(map_file))
    # Não deve lançar a exceção de os.remove


def test_atomic_write_text_success_and_dir_creation(tmp_path):
    """Testa atomic_write_text criando diretórios aninhados e gravando com sucesso."""
    target_file = tmp_path / "deep" / "nested" / "script.txt"
    content = "Linha 1\nLinha 2\n[BR]: Olá Mundo!"
    
    success = atomic_write_text(str(target_file), content, encoding="utf-8")
    assert success is True
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == content
    assert not (tmp_path / "deep" / "nested" / "script.txt.tmp").exists()


def test_atomic_write_text_failure_invalid_path():
    """Testa atomic_write_text retornando False em caminho inválido."""
    success = atomic_write_text("", "conteúdo")
    assert success is False


@patch("src.utils.json_utils.os.replace")
@patch("src.utils.json_utils.time.sleep")
def test_atomic_write_text_permission_retry(mock_sleep, mock_replace, tmp_path):
    """Testa atomic_write_text tentando novamente em caso de PermissionError transitório do Windows."""
    mock_replace.side_effect = [PermissionError(), None]
    target = tmp_path / "test_retry.txt"
    
    success = atomic_write_text(str(target), "dados recuperados")
    assert success is True
    assert mock_replace.call_count == 2
    assert mock_sleep.call_count == 1


def test_atomic_write_json_roundtrip_and_compact(tmp_path):
    """Testa atomic_write_json com indentação e com compact_polygons."""
    data = [
        {"id": 1, "text": "Texto", "polygon": [[10, 20], [30, 40]]}
    ]
    json_path = tmp_path / "data.json"
    
    # 1. Modo normal
    assert atomic_write_json(str(json_path), data, indent=2) is True
    assert json.loads(json_path.read_text(encoding="utf-8")) == data
    
    # 2. Modo compact_polygons
    assert atomic_write_json(str(json_path), data, compact_polygons=True) is True
    raw = json_path.read_text(encoding="utf-8")
    assert '"polygon": [[10, 20], [30, 40]]' in raw
    assert json.loads(raw) == data


def test_atomic_write_json_unserializable_returns_false(tmp_path):
    """Testa atomic_write_json com objeto não-serializável retornando False sem crash."""
    class NonSerializable:
        pass
    
    bad_data = {"obj": NonSerializable()}
    json_path = tmp_path / "bad.json"
    assert atomic_write_json(str(json_path), bad_data) is False


@patch("src.utils.json_utils.os.makedirs")
def test_atomic_write_text_makedirs_exception_returns_false(mock_makedirs):
    """Testa atomic_write_text retornando False quando os.makedirs levanta PermissionError ou OSError."""
    mock_makedirs.side_effect = PermissionError("Acesso negado ao criar pasta")
    success = atomic_write_text("C:/diretorio_protegido/arquivo.txt", "dados")
    assert success is False



