import os
import threading
import pytest
from unittest.mock import MagicMock, patch

from src.model_engines.ollama_process_manager import OllamaProcessManager
from src.model_engines.hf_download_manager import HFDownloadManager, MODELS_REGISTRY, safe_remove_path, verify_file_integrity, is_hf_model_cached
from src.model_manager import ModelManager


def test_ollama_process_manager_isolation(tmp_path):
    """Valida o ciclo de vida e salvamento de PID isolado no OllamaProcessManager."""
    mgr = OllamaProcessManager(base_dir=str(tmp_path))
    assert mgr.base_dir == str(tmp_path)
    
    # PID Lifecycle
    with patch("src.config.get_app_data_dir", return_value=str(tmp_path)):
        OllamaProcessManager._save_ollama_pid(12345)
        pid_file = tmp_path / ".ollama_visionary.pid"
        assert pid_file.exists()
        assert pid_file.read_text().strip() == "12345"

        OllamaProcessManager._remove_ollama_pid_file()
        assert not pid_file.exists()


def test_hf_download_manager_registry_and_monitor_paths(tmp_path):
    """Valida que o HFDownloadManager gera caminhos de monitoramento isolados e estrutura de status."""
    dl_mgr = HFDownloadManager(base_dir=str(tmp_path))
    assert dl_mgr.base_dir == str(tmp_path)

    # Verifica que todos os modelos do registry foram inicializados como 'idle'
    for key in MODELS_REGISTRY:
        assert key in dl_mgr.download_status
        st = dl_mgr.get_download_status(key)
        assert st["status"] == "idle"

    # Verifica caminhos de monitoramento para tipos diferentes
    hf_paths = dl_mgr._get_monitor_paths("florence2")
    assert any("florence-2-base" in p for p in hf_paths)

    yolo_paths = dl_mgr._get_monitor_paths("yolo_detector")
    assert any("best.pt" in p for p in yolo_paths)


def test_model_manager_facade_delegation(tmp_path):
    """Valida que a Facade ModelManager delega perfeitamente para os managers especializados."""
    facade = ModelManager(base_dir=str(tmp_path))
    assert facade.base_dir == str(tmp_path)
    assert isinstance(facade._ollama_mgr, OllamaProcessManager)
    assert isinstance(facade._hf_mgr, HFDownloadManager)

    # 1. Metaclass de sincronização de processo Ollama
    fake_proc = MagicMock()
    fake_proc.pid = 54321
    ModelManager._ollama_process = fake_proc
    ModelManager._ollama_pid = fake_proc.pid
    assert OllamaProcessManager._ollama_process == fake_proc
    assert OllamaProcessManager._ollama_pid == 54321
    assert facade._ollama_process == fake_proc
    assert facade._ollama_pid == 54321

    # Limpeza
    ModelManager._ollama_process = None
    ModelManager._ollama_pid = None

    # 2. Delegação de download status
    assert "florence2" in facade.download_status
    st = facade.get_download_status("florence2")
    assert st["status"] == "idle"

    # 3. Delegação de get_all_status
    with patch.object(facade._ollama_mgr, "get_ollama_models", return_value={"mistral-nemo"}):
        all_st = facade.get_all_status()
        assert "florence2" in all_st
        assert "mistral_nemo" in all_st
        assert all_st["mistral_nemo"]["status"] == "installed"


def test_model_manager_reexports():
    """Valida que a Facade re-exporta símbolos públicos e utilitários essenciais."""
    from src.model_manager import (
        MODELS_REGISTRY as REG,
        safe_remove_path as srp,
        is_hf_model_cached as is_cached,
        verify_file_integrity as vfi,
    )
    assert REG is MODELS_REGISTRY
    assert callable(srp)
    assert callable(is_cached)
    assert callable(vfi)
    assert ModelManager._safe_remove_path is srp
    assert ModelManager.safe_remove_path is srp
