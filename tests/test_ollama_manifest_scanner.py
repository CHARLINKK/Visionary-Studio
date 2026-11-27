import os
import json
import pytest

from src.model_engines.ollama_manifest_scanner import (
    parse_manifest_path,
    get_ollama_manifest_search_paths,
    scan_local_manifests,
    get_installed_ollama_model_names,
    get_installed_ollama_models_list,
)


def test_parse_manifest_path_standard_library():
    res = parse_manifest_path(r"registry.ollama.ai\library\qwen2.5\7b")
    assert res is not None
    assert res["name"] == "qwen2.5:7b"
    assert res["base_name"] == "qwen2.5"
    assert res["tag"] == "7b"

    res_latest = parse_manifest_path("registry.ollama.ai/library/llama3.1/latest")
    assert res_latest is not None
    assert res_latest["name"] == "llama3.1:latest"
    assert res_latest["base_name"] == "llama3.1"
    assert res_latest["tag"] == "latest"


def test_parse_manifest_path_custom_namespace():
    res = parse_manifest_path("registry.ollama.ai/lly/qwen2.5-32b-instruct-iq3_m/latest")
    assert res is not None
    assert res["name"] == "lly/qwen2.5-32b-instruct-iq3_m:latest"
    assert res["base_name"] == "lly/qwen2.5-32b-instruct-iq3_m"
    assert res["tag"] == "latest"


def test_parse_manifest_path_short_and_invalid():
    # Caminho curto: library/mistral/latest
    res = parse_manifest_path("library/mistral/latest")
    assert res is not None
    assert res["name"] == "mistral:latest"
    assert res["base_name"] == "mistral"

    # Caminho direto model/tag
    res_direct = parse_manifest_path("deepseek-r1/8b")
    assert res_direct is not None
    assert res_direct["name"] == "deepseek-r1:8b"
    assert res_direct["base_name"] == "deepseek-r1"

    # Inválido (menos de 2 partes)
    assert parse_manifest_path("qwen2.5") is None
    assert parse_manifest_path("") is None


def test_get_ollama_manifest_search_paths_priority(tmp_path, monkeypatch):
    custom = tmp_path / "custom_models"
    custom.mkdir()
    env_dir = tmp_path / "env_models"
    env_dir.mkdir()

    # Quando custom_dir é passado, retorna apenas o custom
    paths_custom = get_ollama_manifest_search_paths(custom_dir=str(custom))
    assert paths_custom == [str(custom.resolve())]

    # Quando custom_dir não é passado, OLLAMA_MODELS é consultado
    monkeypatch.setenv("OLLAMA_MODELS", str(env_dir))
    paths_env = get_ollama_manifest_search_paths()
    assert str(env_dir.resolve()) in [os.path.normpath(p) for p in paths_env]


def test_scan_local_manifests_with_fake_fs(tmp_path):
    models_dir = tmp_path / "models"
    manifests_dir = models_dir / "manifests" / "registry.ollama.ai" / "library" / "qwen2.5"
    manifests_dir.mkdir(parents=True)

    manifest_file = manifests_dir / "7b"
    content = {
        "schemaVersion": 2,
        "config": {"size": 487},
        "layers": [
            {"mediaType": "application/vnd.ollama.image.model", "size": 4000000},
            {"mediaType": "application/vnd.ollama.image.license", "size": 1000},
        ],
    }
    manifest_file.write_text(json.dumps(content), encoding="utf-8")

    # 1. Scan com parse_sizes=True
    discovered = scan_local_manifests(custom_dir=str(models_dir), parse_sizes=True, force_refresh=True)
    assert len(discovered) == 1
    m = discovered[0]
    assert m["name"] == "qwen2.5:7b"
    assert m["base_name"] == "qwen2.5"
    assert m["tag"] == "7b"
    assert m["size"] == 4001487

    # 2. get_installed_ollama_model_names retorna tanto o full name quanto o base name
    names = get_installed_ollama_model_names(custom_dir=str(models_dir))
    assert "qwen2.5:7b" in names
    assert "qwen2.5" in names

    # 3. get_installed_ollama_models_list retorna a lista de tags completas
    full_list = get_installed_ollama_models_list(custom_dir=str(models_dir))
    assert full_list == ["qwen2.5:7b"]


def test_scan_local_manifests_empty_and_corrupt(tmp_path):
    empty_dir = tmp_path / "empty_models"
    empty_dir.mkdir()

    res = scan_local_manifests(custom_dir=str(empty_dir), force_refresh=True)
    assert res == []

    # Manifesto corrompido não quebra a varredura
    manifests_dir = empty_dir / "manifests" / "registry.ollama.ai" / "library" / "badmodel"
    manifests_dir.mkdir(parents=True)
    bad_file = manifests_dir / "latest"
    bad_file.write_text("NOT_A_VALID_JSON{{{", encoding="utf-8")

    res2 = scan_local_manifests(custom_dir=str(empty_dir), parse_sizes=True, force_refresh=True)
    assert len(res2) == 1
    assert res2[0]["name"] == "badmodel:latest"
    assert res2[0]["size"] == 0  # Falha silenciosa gracefully


def test_get_ollama_models_offline_uses_manifest_scanner(tmp_path, monkeypatch):
    from unittest.mock import patch
    from src.model_engines.ollama_process_manager import OllamaProcessManager

    models_dir = tmp_path / "models"
    manifests_dir = models_dir / "manifests" / "registry.ollama.ai" / "library" / "llama3.1"
    manifests_dir.mkdir(parents=True)
    (manifests_dir / "latest").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("OLLAMA_MODELS", str(models_dir))
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))

    mgr = OllamaProcessManager(base_dir=str(tmp_path))
    # Força check_ollama_running para False (daemon offline)
    with patch.object(mgr, "check_ollama_running", return_value=False):
        models = mgr.get_ollama_models()
        assert "llama3.1:latest" in models
        assert "llama3.1" in models


def test_check_ollama_state_offline_reports_installed_and_stopped(tmp_path, monkeypatch):
    from unittest.mock import patch
    from src.api_services.ollama_lifecycle_manager import OllamaLifecycleManager

    models_dir = tmp_path / "models"
    manifests_dir = models_dir / "manifests" / "registry.ollama.ai" / "library" / "qwen2.5"
    manifests_dir.mkdir(parents=True)
    (manifests_dir / "7b").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("OLLAMA_MODELS", str(models_dir))
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))

    lifecycle = OllamaLifecycleManager()
    with patch.object(lifecycle, "_get_ollama_tags_cached", return_value=None), \
         patch.object(lifecycle, "is_running", return_value=False):
        state, models = lifecycle.check_ollama_state()
        assert state == "installed_and_stopped"
        assert "qwen2.5:7b" in models


def test_scan_local_manifests_sizes_parsed_cache_invalidation(tmp_path):
    models_dir = tmp_path / "models"
    manifests_dir = models_dir / "manifests" / "registry.ollama.ai" / "library" / "m"
    manifests_dir.mkdir(parents=True)
    manifest_file = manifests_dir / "latest"
    manifest_file.write_text(json.dumps({"layers": [{"size": 5000}]}), encoding="utf-8")

    # 1ª chamada sem parse_sizes
    res_no_size = scan_local_manifests(custom_dir=str(models_dir), parse_sizes=False, force_refresh=True)
    assert res_no_size[0]["size"] == 0

    # 2ª chamada imediata com parse_sizes=True deve forçar o recálculo do tamanho
    res_with_size = scan_local_manifests(custom_dir=str(models_dir), parse_sizes=True, force_refresh=False)
    assert res_with_size[0]["size"] == 5000




