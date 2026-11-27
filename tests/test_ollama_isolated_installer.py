import os
import io
import time
import zipfile
from unittest.mock import MagicMock, patch

from src.model_engines.ollama_process_manager import OllamaProcessManager
from src.api_services.ollama_lifecycle_manager import OllamaLifecycleManager
from src.api_services.model_service import ModelService
from src.api_bridge import ApiBridge


def test_find_ollama_executable_and_is_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    monkeypatch.setattr("sys.executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(os, "getcwd", lambda: str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path / "home" / "fake.exe"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "empty_local"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "empty_pf"))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "empty_pf86"))

    # 1. Sem executável em nenhum diretório
    assert OllamaProcessManager.find_ollama_executable(base_dir=str(tmp_path)) is None
    assert OllamaProcessManager.is_ollama_installed(base_dir=str(tmp_path)) is False

    # 2. Com executável isolado criado em engine/ollama/ollama.exe
    isolated_dir = tmp_path / "engine" / "ollama"
    isolated_dir.mkdir(parents=True, exist_ok=True)
    fake_exe = isolated_dir / "ollama.exe"
    fake_exe.write_text("dummy binary", encoding="utf-8")

    found = OllamaProcessManager.find_ollama_executable(base_dir=str(tmp_path))
    assert found is not None
    assert os.path.samefile(found, str(fake_exe))
    assert OllamaProcessManager.is_ollama_installed(base_dir=str(tmp_path)) is True


def test_check_ollama_state_transitions(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    monkeypatch.setattr("sys.executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(os, "getcwd", lambda: str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path / "home" / "fake.exe"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "empty_local"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "empty_pf"))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "empty_pf86"))

    mgr = OllamaLifecycleManager()
    with patch.object(mgr, "_get_ollama_tags_cached", return_value=None), \
         patch.object(mgr, "is_running", return_value=False):

        # A. Not installed
        state, models = mgr.check_ollama_state()
        assert state == "not_installed"
        assert models == []

        # B. Installing
        mgr._ollama_installing = True
        state, models = mgr.check_ollama_state()
        assert state == "installing"
        mgr._ollama_installing = False

        # C. Installed and stopped
        isolated_dir = tmp_path / "engine" / "ollama"
        isolated_dir.mkdir(parents=True, exist_ok=True)
        (isolated_dir / "ollama.exe").write_text("dummy", encoding="utf-8")

        state, models = mgr.check_ollama_state()
        assert state == "installed_and_stopped"

        # D. Installed and running
        with patch.object(mgr, "_get_ollama_tags_cached", return_value={"models": [{"name": "qwen2.5:7b"}]}):
            state, models = mgr.check_ollama_state()
            assert state == "installed_and_running"
            assert "qwen2.5:7b" in models


def test_install_isolated_ollama_download_and_extract(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda _: None)

    # Cria pacote zip em memória contendo ollama.exe
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("ollama.exe", b"fake-ollama-executable")
        zf.writestr("lib/ollama/cuda.dll", b"fake-cuda-dll")
    zip_bytes = zip_buffer.getvalue()

    # Mock da resposta HTTP de streaming
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.headers = {"content-length": str(len(zip_bytes))}
    mock_response.iter_content.return_value = [zip_bytes[:50], zip_bytes[50:]]

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    mgr = OllamaLifecycleManager()
    events_published = []

    def mock_publish(channel, data):
        events_published.append((channel, data))

    with patch("requests.Session", return_value=mock_session), \
         patch("src.utils.event_bus.event_bus.publish", side_effect=mock_publish), \
         patch.object(mgr, "start_server", return_value={"success": True}):

        res = mgr.install_isolated_ollama(download_url="https://mock.ollama/ollama.zip")
        assert res["success"] is True

        # Aguarda thread em segundo plano finalizar
        for _ in range(50):
            prog = mgr.get_install_progress()
            if prog.get("status") in ["completed", "error"]:
                break
            time.sleep(0.05)

        final_prog = mgr.get_install_progress()
        assert final_prog["status"] == "completed"
        assert final_prog["percent"] == 100.0

        # Verifica se o arquivo foi descompactado no diretório isolado do usuário
        extracted_exe = tmp_path / "engine" / "ollama" / "ollama.exe"
        assert extracted_exe.is_file()
        assert extracted_exe.read_bytes() == b"fake-ollama-executable"


def test_cancel_isolated_install(tmp_path, monkeypatch):
    mgr = OllamaLifecycleManager()
    mgr._ollama_installing = True
    mgr._ollama_install_cancel_event = MagicMock()

    res = mgr.cancel_isolated_install()
    assert res["success"] is True
    mgr._ollama_install_cancel_event.set.assert_called_once()
    assert mgr.get_install_progress()["status"] == "cancelled"


def test_model_service_and_api_bridge_integration(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))

    bridge = ApiBridge()
    # Verifica resolução e deleção transparente de métodos
    assert hasattr(bridge, "installIsolatedOllama")
    assert hasattr(bridge, "cancelIsolatedOllamaInstall")
    assert hasattr(bridge, "getOllamaInstallProgress")

    prog = bridge.getOllamaInstallProgress()
    assert isinstance(prog, dict)
    assert "status" in prog
