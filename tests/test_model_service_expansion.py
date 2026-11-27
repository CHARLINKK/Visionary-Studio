import os
import pytest
from src.api_bridge import ApiBridge

def test_storage_stats():
    bridge = ApiBridge()
    res = bridge.getStorageStats()
    assert res.get("success") is True
    assert "total_bytes" in res
    assert "total_formatted" in res
    assert res["total_bytes"] >= 0

def test_ensure_ollama_running_non_blocking():
    from unittest.mock import patch
    bridge = ApiBridge()
    with patch.object(bridge._model_service, "startOllamaServer"):
        res = bridge.ensureOllamaRunning()
        assert res.get("success") is True
        assert "status" in res
        assert res["status"] in ["already_running", "starting", "already_starting"]

def test_uninstall_core_engine_api_and_progress():
    bridge = ApiBridge()
    assert hasattr(bridge, "uninstallCoreEngine")
    prog = bridge.getInstallProgress()
    assert "status" in prog
    assert "percent" in prog
    assert "log" in prog

def test_model_manager_monitor_paths_isolated(tmp_path):
    from src.model_manager import ModelManager
    manager = ModelManager(base_dir=str(tmp_path))
    # Models folder with other files
    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    # Create large dummy file that is NOT part of yolo_detector
    (models_dir / "unrelated_huge_file.bin").write_bytes(b"0" * (10 * 1024 * 1024))
    
    # Check yolo_detector monitor paths
    paths = manager._get_monitor_paths("yolo_detector")
    assert any("best.pt" in p for p in paths)
    assert any("best.pt.incomplete" in p for p in paths)
    assert any("comic-speech-bubble-detector.pt.incomplete" in p for p in paths)
    assert any(".cache" in p for p in paths)
    
    # Download status should NOT count the unrelated huge file
    st = manager.get_download_status("yolo_detector")
    assert st["downloaded_bytes"] == 0

def test_verify_file_integrity_checks(tmp_path):
    import hashlib
    from src.model_manager import verify_file_integrity

    test_file = tmp_path / "model.pt"
    # 1. Non-existent file
    assert verify_file_integrity(str(tmp_path / "missing.pt")) is False

    # 2. File too small
    test_file.write_bytes(b"PK\x03\x04" + b"x" * 50)
    assert verify_file_integrity(str(test_file), min_size_bytes=100) is False

    # 3. Invalid magic bytes for .pt file
    corrupt_pt = tmp_path / "corrupt.pt"
    corrupt_pt.write_bytes(b"INVALID_HEADER" + b"0" * 200)
    assert verify_file_integrity(str(corrupt_pt), min_size_bytes=100) is False

    # 4. Valid magic bytes and matching SHA
    valid_content = b"PK\x03\x04" + b"VALID_TORCH_DATA" * 10
    valid_pt = tmp_path / "valid.pt"
    valid_pt.write_bytes(valid_content)
    expected_hash = hashlib.sha256(valid_content).hexdigest()
    assert verify_file_integrity(str(valid_pt), expected_sha256=expected_hash, min_size_bytes=50) is True

    # 5. Mismatched SHA
    assert verify_file_integrity(str(valid_pt), expected_sha256="wronghash123", min_size_bytes=50) is False

def test_corrupt_files_marked_missing_and_part_cleanup(tmp_path, monkeypatch):
    from src.model_manager import ModelManager, MODELS_REGISTRY
    monkeypatch.setattr("os.path.expanduser", lambda x: str(tmp_path / "fake_user"))
    manager = ModelManager(base_dir=str(tmp_path))

    # Create dummy yolo file of 0 bytes (corrupt download)
    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    corrupt_file = models_dir / "best.pt"
    corrupt_file.write_bytes(b"")

    # In get_all_status, it should be recognized as 'missing', not 'installed'
    status = manager.get_all_status()
    assert status["yolo_detector"]["status"] == "missing"

    # Also test .part file cleanup on remove_module
    part_file = models_dir / "best.pt.part"
    part_file.write_bytes(b"partial content")
    assert part_file.exists()

    removed = manager.remove_module("yolo_detector")
    assert removed is True
    assert not part_file.exists()
    assert not corrupt_file.exists()


def test_get_downloads_progress_preserves_completed_and_cached(tmp_path):
    from src.model_manager import ModelManager
    from src.api_services.model_service import ModelService
    
    manager = ModelManager(base_dir=str(tmp_path))
    service = ModelService(api_bridge=None, model_manager=manager)
    
    # 1. Simula Florence-2 marcado como installed
    manager.download_status["florence2"] = {
        "status": "installed",
        "progress": 100.0,
        "downloaded_bytes": 1000,
        "total_bytes": 1000,
        "message": "Concluído!"
    }
    
    # 2. Simula Qwen marcado como completed no Ollama
    service._completed_ollama_models.add("qwen2.5:32b")
    
    res = service.getDownloadsProgress()
    assert res["success"] is True
    # Florence deve estar presente em 'hf' mesmo com status 'installed'
    assert "florence2" in res["hf"]
    assert res["hf"]["florence2"]["progress"] == 100.0
    assert res["hf"]["florence2"]["status"] == "installed"
    
    # Qwen deve estar presente em 'ollama' mesmo sem estar no dicionário efêmero
    assert "qwen2.5:32b" in res["ollama"]
    assert res["ollama"]["qwen2.5:32b"]["progress"] == 100.0
    assert res["ollama"]["qwen2.5:32b"]["status"] == "installed"


def test_safe_remove_path_handles_windows_readonly(tmp_path):
    import stat
    from src.model_manager import safe_remove_path
    
    test_dir = tmp_path / "locked_cache"
    test_dir.mkdir()
    locked_file = test_dir / "blob_readonly.bin"
    locked_file.write_bytes(b"data" * 100)
    
    # Define atributo somente leitura (simulando Windows git/hf blob)
    os.chmod(str(locked_file), stat.S_IREAD)
    
    success = safe_remove_path(str(test_dir))
    assert success is True
    assert not test_dir.exists()


def test_remove_module_huggingface_multi_single_cleans_cache_and_parts(tmp_path):
    import stat
    from src.model_manager import ModelManager
    
    manager = ModelManager(base_dir=str(tmp_path))
    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Arquivos reais do yolo_detector
    best_file = models_dir / "best.pt"
    best_file.write_bytes(b"PK\x03\x04" + b"x" * 100)
    bubble_file = models_dir / "comic-speech-bubble-detector.pt"
    bubble_file.write_bytes(b"PK\x03\x04" + b"y" * 100)
    part_file = models_dir / "best.pt.part"
    part_file.write_bytes(b"partial")
    
    # 2. Pasta interna de cache do Hugging Face Hub gerada pelo hf_hub_download
    hub_cache = models_dir / ".cache" / "huggingface" / "hub" / "models--TheBlindMaster--yolov8n-manga-frame-seg"
    hub_cache.mkdir(parents=True, exist_ok=True)
    blob_file = hub_cache / "blobs_test.bin"
    blob_file.write_bytes(b"blob data")
    os.chmod(str(blob_file), stat.S_IREAD)
    
    assert best_file.exists()
    assert hub_cache.exists()
    
    res = manager.remove_module("yolo_detector")
    assert res is True
    assert not best_file.exists()
    assert not bubble_file.exists()
    assert not part_file.exists()
    assert not hub_cache.exists()
    assert not (models_dir / ".cache" / "huggingface" / "hub" / "models--TheBlindMaster--yolov8n-manga-frame-seg").exists()


def test_cancel_ollama_download_triggers_event_and_closes_session(tmp_path):
    from unittest.mock import MagicMock, patch
    from src.model_manager import ModelManager
    from src.api_services.model_service import ModelService
    
    manager = ModelManager(base_dir=str(tmp_path))
    service = ModelService(api_bridge=None, model_manager=manager)
    
    # Inicia pull com mock de requests que simula stream contínuo
    mock_resp = MagicMock()
    mock_resp.iter_lines.return_value = [b'{"status":"downloading","completed":10,"total":100}']
    mock_session = MagicMock()
    mock_session.post.return_value.__enter__.return_value = mock_resp
    
    with patch("requests.Session", return_value=mock_session):
        res = service.pullOllamaModel("mistral-nemo")
        assert res["success"] is True
        
        # Evento de cancelamento foi registrado
        assert "mistral-nemo" in service._ollama_cancel_events
        evt = service._ollama_cancel_events["mistral-nemo"]
        assert not evt.is_set()
        
        # Cancela o download
        cancel_res = service.cancelOllamaDownload("mistral-nemo")
        assert cancel_res["success"] is True
        assert evt.is_set()
        assert "mistral-nemo" not in service._get_ollama_downloads()


def test_huggingface_model_supports_cancellation(tmp_path):
    import threading
    from src.model_manager import ModelManager
    from src.api_services.model_service import ModelService

    manager = ModelManager(base_dir=str(tmp_path))
    service = ModelService(api_bridge=None, model_manager=manager)

    manager.download_status["florence2"] = {
        "status": "downloading",
        "progress": 50.0,
        "message": "Baixando..."
    }
    manager._cancel_events["florence2"] = threading.Event()

    res = service.cancelHuggingFaceModel("florence2")
    assert res["success"] is True
    assert manager._cancel_events["florence2"].is_set()
    assert manager.download_status["florence2"]["status"] == "cancelled"


def test_uninstall_core_engine_reports_dll_lock_actionable_error(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch
    import time
    from src.model_manager import ModelManager
    from src.api_services.model_service import ModelService
    
    manager = ModelManager(base_dir=str(tmp_path))
    service = ModelService(api_bridge=None, model_manager=manager)
    
    # Simula erro típico de DLL travada no Windows durante pip uninstall
    mock_proc = MagicMock()
    mock_proc.stdout = [
        "Found existing installation: torch 2.5.0\n",
        "Uninstalling torch-2.5.0:\n",
        "PermissionError: [WinError 5] Access is denied: 'c:\\env\\lib\\site-packages\\torch\\lib\\torch_cpu.dll'\n"
    ]
    mock_proc.returncode = 1
    mock_proc.wait.return_value = 1
    
    with patch("subprocess.Popen", return_value=mock_proc):
        res = service.uninstallCoreEngine()
        assert res["success"] is True
        
        # Aguarda thread concluir
        for _ in range(50):
            prog = service.getInstallProgress()
            if prog["status"] == "error":
                break
            time.sleep(0.05)
            
        prog = service.getInstallProgress()
        assert prog["status"] == "error"
        assert "DLLs do PyTorch bloqueadas na RAM pelo Windows" in prog["message"]


def test_start_ollama_server_resolves_isolated_base_dir_without_error(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch
    from src.model_manager import ModelManager
    from src.api_services.model_service import ModelService

    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    ollama_dir = tmp_path / "engine" / "ollama"
    ollama_dir.mkdir(parents=True, exist_ok=True)
    fake_exe = ollama_dir / "ollama.exe"
    fake_exe.write_bytes(b"MZ_FAKE_OLLAMA")

    manager = ModelManager(base_dir=str(tmp_path))
    service = ModelService(api_bridge=None, model_manager=manager)

    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    # 1ª chamada: falha (não está rodando); 2ª chamada após Popen: retorna 200 OK
    resp_ok = MagicMock(status_code=200)
    resp_ok.json.return_value = {"models": [{"name": "qwen2.5:14b"}]}
    mock_session.get.side_effect = [OSError("Connection refused"), resp_ok]

    mock_proc = MagicMock()
    mock_proc.pid = 99999
    mock_proc.poll.return_value = None

    with patch("src.config.get_app_data_dir", return_value=str(tmp_path / "nonexistent_appdata")), \
         patch("sys.executable", str(tmp_path / "nonexistent_py" / "python.exe")), \
         patch("requests.Session", return_value=mock_session), \
         patch("subprocess.Popen", return_value=mock_proc) as popen_mock, \
         patch("time.sleep", return_value=None):
        res = service.startOllamaServer()
        assert res["success"] is True
        assert "qwen2.5:14b" in res.get("models", [])
        called_args = popen_mock.call_args[0][0]
        assert str(fake_exe) == called_args[0]


def test_model_service_input_validation_and_friendly_errors(tmp_path, monkeypatch):
    import requests
    from unittest.mock import MagicMock, patch
    from src.model_manager import ModelManager
    from src.api_services.model_service import ModelService

    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    manager = ModelManager(base_dir=str(tmp_path))
    service = ModelService(api_bridge=None, model_manager=manager)

    # Empty inputs
    assert service.testModelTranslation("")["success"] is False
    assert service.deleteOllamaModel("")["success"] is False
    assert service.pullOllamaModel("")["success"] is False

    # Connection error handling
    with patch("requests.Session.post", side_effect=requests.exceptions.ConnectionError("Refused")):
        res = service.testModelTranslation("qwen2.5:14b")
        assert res["success"] is False
        assert "Servidor Ollama não está acessível" in res["error"]


def test_is_ollama_running_fallback_ports(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch
    from src.model_manager import ModelManager
    from src.api_services.model_service import ModelService

    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    manager = ModelManager(base_dir=str(tmp_path))
    service = ModelService(api_bridge=None, model_manager=manager)

    # Simulates port 11435 closed, but 11434 open and returning 200 OK
    def mock_create_connection(addr, timeout=None):
        if addr[1] == 11434:
            return MagicMock()
        raise OSError("Connection refused")

    mock_resp = MagicMock(status_code=200)
    with patch("socket.create_connection", side_effect=mock_create_connection), \
         patch("requests.Session.get", return_value=mock_resp):
        assert service.isOllamaRunning() is True


def test_remove_module_florence_purges_both_variants_and_notifies(tmp_path):
    from src.model_manager import ModelManager
    from src.api_services.hf_download_orchestrator import HFDownloadOrchestrator

    manager = ModelManager(base_dir=str(tmp_path))
    orchestrator = HFDownloadOrchestrator(model_manager=manager)

    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    base_dir = models_dir / "florence-2-base"
    base_dir.mkdir()
    (base_dir / "model.safetensors").write_bytes(b"base")

    large_dir = models_dir / "florence-2-large"
    large_dir.mkdir()
    (large_dir / "model.safetensors").write_bytes(b"large")

    hub_base = models_dir / "models--microsoft--Florence-2-base"
    hub_base.mkdir()

    events = []
    manager.register_progress_callback(lambda k, st: events.append((k, st.get("status"))))

    # Deleting florence2_large should purge both base and large folders and update both statuses
    res = orchestrator.delete_model("florence2_large")
    assert res["success"] is True

    assert not base_dir.exists()
    assert not large_dir.exists()
    assert not hub_base.exists()

    st_large = manager.get_download_status("florence2_large")
    st_base = manager.get_download_status("florence2")
    assert st_large["status"] == "missing"
    assert st_base["status"] == "missing"

    active_hf = orchestrator.get_active_hf_status()
    assert active_hf.get("florence2", {}).get("status") == "missing"
    assert active_hf.get("florence2_large", {}).get("status") == "missing"


def test_scoped_tqdm_cumulative_stream_tracker(tmp_path):
    from src.model_manager import ModelManager
    from src.model_engines.hf.http_downloader import build_scoped_tqdm_class, DownloadStreamTracker

    manager = ModelManager(base_dir=str(tmp_path))
    manager.download_status["florence2_large"] = {
        "status": "downloading",
        "progress": 0.0,
        "downloaded_bytes": 0,
        "total_bytes": 1000000,
        "message": ""
    }

    tqdm_cls = build_scoped_tqdm_class(manager, "florence2_large", total_expected_bytes=1000000)
    assert tqdm_cls is not None

    # Simula 2 arquivos baixados em sequência ou chunks
    bar1 = tqdm_cls(total=500000, unit="B", desc="config.json")
    bar1.update(250000)
    st = manager.get_download_status("florence2_large")
    assert st["downloaded_bytes"] == 250000
    assert st["progress"] == 25.0
    bar1.update(250000)
    bar1.close()

    bar2 = tqdm_cls(total=500000, unit="B", desc="model.safetensors")
    bar2.update(250000)
    st = manager.get_download_status("florence2_large")
    # Deve acumular para 750000 (75%) em vez de resetar para 250000
    assert st["downloaded_bytes"] == 750000
    assert st["progress"] == 75.0
    bar2.close()


def test_scoped_hf_stream_hook_intercepts_and_restores(tmp_path):
    import huggingface_hub.file_download as fd
    import huggingface_hub.utils as hf_utils
    from src.model_manager import ModelManager
    from src.model_engines.hf.http_downloader import scoped_hf_stream_hook

    manager = ModelManager(base_dir=str(tmp_path))
    manager.download_status["florence2_large"] = {
        "status": "downloading",
        "progress": 0.0,
        "downloaded_bytes": 0,
        "total_bytes": 2000,
        "message": ""
    }

    orig_fd = fd.tqdm
    orig_ht = hf_utils.tqdm

    with scoped_hf_stream_hook(manager, "florence2_large", target_total_bytes=2000) as tracker:
        assert fd.tqdm is not orig_fd
        assert hf_utils.tqdm is not orig_ht

        # Simula instanciacao do tqdm interno do hf_hub_download
        bar = fd.tqdm(total=2000, unit="B", desc="model.safetensors")
        bar.update(500)
        st = manager.get_download_status("florence2_large")
        assert st["downloaded_bytes"] == 500
        assert st["progress"] == 25.0
        bar.update(500)
        st = manager.get_download_status("florence2_large")
        assert st["downloaded_bytes"] == 1000
        assert st["progress"] == 50.0

    # Garante que restaurou perfeitamente as classes originais apos o bloco with
    assert fd.tqdm is orig_fd
    assert hf_utils.tqdm is orig_ht


def test_disk_monitor_reports_exact_physical_bytes_without_fake_dead_reckoning(tmp_path):
    import time
    import threading
    from src.model_manager import ModelManager
    from src.model_engines.hf.disk_monitor import monitor_disk_progress

    manager = ModelManager(base_dir=str(tmp_path))
    key = "florence2_large"
    total_bytes = 100 * 1024 * 1024  # 100 MB
    
    manager.download_status[key] = {
        "status": "downloading",
        "progress": 0.0,
        "downloaded_bytes": 0,
        "total_bytes": total_bytes,
        "message": "Iniciando download..."
    }

    dummy_dir = tmp_path / "models" / "florence-2-large"
    dummy_dir.mkdir(parents=True, exist_ok=True)
    chunk_file = dummy_dir / "model.safetensors.part"
    # Escreve 10 MB iniciais
    chunk_file.write_bytes(b"x" * (10 * 1024 * 1024))

    stop_event = threading.Event()
    monitor_paths = [str(dummy_dir)]

    t = threading.Thread(
        target=monitor_disk_progress,
        args=(manager, key, monitor_paths, stop_event, total_bytes),
        daemon=True
    )
    t.start()

    time.sleep(0.25)
    st1 = manager.get_download_status(key)
    assert st1["downloaded_bytes"] == 10 * 1024 * 1024
    assert st1["progress"] == 10.0

    # Sem novos bytes no disco, NÃO pode inventar bytes fictícios
    time.sleep(0.35)
    st2 = manager.get_download_status(key)
    assert st2["downloaded_bytes"] == 10 * 1024 * 1024
    assert st2["progress"] == 10.0

    # Quando novos bytes físicos chegam ao disco (35 MB), atualiza exatamente para 35%
    chunk_file.write_bytes(b"x" * (35 * 1024 * 1024))
    time.sleep(0.3)
    st3 = manager.get_download_status(key)
    assert st3["downloaded_bytes"] == 35 * 1024 * 1024
    assert st3["progress"] == 35.0
    assert "Baixando..." in st3["message"]

    stop_event.set()
    t.join(timeout=1.0)
    assert not t.is_alive()


def test_disk_monitor_caps_at_99_percent_before_completion(tmp_path):
    import time
    import threading
    from src.model_manager import ModelManager
    from src.model_engines.hf.disk_monitor import monitor_disk_progress

    manager = ModelManager(base_dir=str(tmp_path))
    key = "florence2_large"
    total_bytes = 10 * 1024 * 1024  # 10 MB
    
    manager.download_status[key] = {
        "status": "downloading",
        "progress": 0.0,
        "downloaded_bytes": 0,
        "total_bytes": total_bytes,
        "speed_mbps": 0.0,
        "message": "Iniciando download..."
    }

    dummy_dir = tmp_path / "models" / "florence-2-large"
    dummy_dir.mkdir(parents=True, exist_ok=True)
    chunk_file = dummy_dir / "model.safetensors.part"
    chunk_file.write_bytes(b"x" * total_bytes)

    stop_event = threading.Event()
    monitor_paths = [str(dummy_dir)]

    t = threading.Thread(
        target=monitor_disk_progress,
        args=(manager, key, monitor_paths, stop_event, total_bytes),
        daemon=True
    )
    t.start()

    time.sleep(0.35)
    st = manager.get_download_status(key)

    # NUNCA pode atingir 100% antes da verificação e conclusão física
    assert st["progress"] <= 99.0
    assert st["status"] == "downloading"
    assert st["speed_mbps"] == 0.0
    assert "Finalizando instalação..." in st["message"]

    stop_event.set()
    t.join(timeout=1.0)
    assert not t.is_alive()


def test_core_engine_installer_does_not_short_circuit_on_namespace_package():
    from unittest.mock import patch, MagicMock
    from src.model_engines.core_engine_installer import CoreEngineInstaller

    installer = CoreEngineInstaller()

    # Simulate torch missing origin (namespace package or leftover folder)
    fake_deps = {
        "ai_state": "not_installed",
        "has_torch": False,
        "has_transformers": True,
        "has_ultralytics": True,
    }

    with patch.object(installer, "check_ai_dependencies", return_value=fake_deps):
        with patch("threading.Thread") as mock_thread:
            mock_t_instance = MagicMock()
            mock_thread.return_value = mock_t_instance
            res = installer.install_core_engine()
            assert res.get("success") is True
            assert res.get("message") == "Installation started"
            # It must have spawned the installer thread rather than short-circuiting!
            mock_thread.assert_called_once()
            prog = installer.get_install_progress()
            assert prog["status"] == "installing"


def test_core_engine_installer_short_circuits_only_when_fully_installed():
    from unittest.mock import patch
    from src.model_engines.core_engine_installer import CoreEngineInstaller

    installer = CoreEngineInstaller()

    fake_deps = {
        "ai_state": "installed",
        "has_torch": True,
        "has_transformers": True,
        "has_ultralytics": True,
    }

    with patch.object(installer, "check_ai_dependencies", return_value=fake_deps):
        with patch("threading.Thread") as mock_thread:
            res = installer.install_core_engine()
            assert res.get("success") is True
            assert "já está instalado" in res.get("message", "")
            mock_thread.assert_not_called()
            prog = installer.get_install_progress()
            assert prog["status"] == "completed"
            assert prog["percent"] == 100.0


def test_florence_incomplete_cache_reported_as_missing(tmp_path):
    from src.model_engines.hf_download_manager import HFDownloadManager

    models_dir = tmp_path / "models"
    florence_base = models_dir / "florence-2-base"
    florence_base.mkdir(parents=True)

    # Cria apenas model.safetensors sem config.json ou processing_florence2.py (arquivo incompleto)
    (florence_base / "model.safetensors").write_bytes(b"weights" * 100)

    manager = HFDownloadManager(base_dir=str(tmp_path))
    status = manager.get_all_status()

    # Deve reportar missing e não installed
    assert status["florence2"]["status"] == "missing"
    assert status["florence2"]["progress"] == 0.0

    # Agora cria os arquivos mínimos exigidos pela arquitetura Florence-2
    (florence_base / "config.json").write_text("{}", encoding="utf-8")
    (florence_base / "processing_florence2.py").write_text("# code", encoding="utf-8")

    status_valid = manager.get_all_status()
    assert status_valid["florence2"]["status"] == "installed"
    assert status_valid["florence2"]["progress"] == 100.0


def test_yolo_corrupt_or_truncated_file_reported_as_missing(tmp_path):
    from src.model_engines.hf_download_manager import HFDownloadManager

    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True)

    # Cria best.pt com dados corrompidos (sem header PyTorch)
    best_file = models_dir / "best.pt"
    best_file.write_bytes(b"corrupt non-pytorch data" * 10)

    manager = HFDownloadManager(base_dir=str(tmp_path))
    status = manager.get_all_status()
    # Deve ser missing porque o header é inválido
    assert status["yolo_detector"]["status"] == "missing"

    # Agora cria best.pt com header válido PK\x03\x04, mas comic-speech-bubble-detector.pt ainda não existe
    best_file.write_bytes(b"PK\x03\x04" + (b"\x00" * 200))
    status = manager.get_all_status()
    assert status["yolo_detector"]["status"] == "missing"

    # Agora cria comic-speech-bubble-detector.pt também válido
    bubble_file = models_dir / "comic-speech-bubble-detector.pt"
    bubble_file.write_bytes(b"PK\x03\x04" + (b"\x00" * 200))
    status = manager.get_all_status()
    assert status["yolo_detector"]["status"] == "installed"


def test_check_ai_dependencies_requires_timm_and_einops(monkeypatch):
    import importlib.util
    from src.model_engines.core_engine_installer import CoreEngineInstaller

    installer = CoreEngineInstaller()
    orig_find_spec = importlib.util.find_spec

    def mock_find_spec(name, *args, **kwargs):
        if name == "timm":
            return None
        return orig_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", mock_find_spec)
    deps = installer.check_ai_dependencies()
    assert deps["has_timm"] is False
    assert deps["ai_state"] == "not_installed"


def test_delete_ollama_model_invalidates_caches_and_emits_event():
    from unittest.mock import MagicMock
    from src.model_engines.ollama_model_puller import delete_ollama_model
    from src.model_engines.ollama_manifest_scanner import _manifests_cache

    mock_mgr = MagicMock()
    mock_mgr._get_lock.return_value.__enter__ = MagicMock()
    mock_mgr._get_lock.return_value.__exit__ = MagicMock()
    mock_mgr._completed_models = {"qwen2.5:7b"}
    mock_mgr._get_downloads.return_value = {"qwen2.5:7b": {"progress": 100}}

    _manifests_cache["data"] = [{"name": "qwen2.5:7b"}]
    _manifests_cache["timestamp"] = 999999.0

    class FakeResp:
        status_code = 200

    class FakeSession:
        trust_env = False
        def delete(self, url, json=None, timeout=None):
            return FakeResp()

    res = delete_ollama_model(mock_mgr, "qwen2.5:7b", session_factory=FakeSession)
    assert res.get("success") is True
    mock_mgr.invalidate_tags_cache.assert_called_once()
    assert _manifests_cache["data"] == []
    assert _manifests_cache["timestamp"] == 0.0


def test_florence_and_yolo_monitor_paths_and_deduplication(tmp_path):
    from src.model_manager import ModelManager
    from src.model_engines.hf.disk_monitor import scan_disk_downloaded_bytes

    manager = ModelManager(base_dir=str(tmp_path))
    paths = manager._get_monitor_paths("florence2_large")
    assert any("florence-2-large" in p for p in paths)
    assert any(".cache" in p for p in paths)
    assert any("xet" in p for p in paths)

    # Cria diretório base e subdiretório .cache dentro dele
    base_dir = tmp_path / "models" / "florence-2-large"
    cache_sub = base_dir / ".cache"
    cache_sub.mkdir(parents=True, exist_ok=True)

    dummy_file = cache_sub / "chunk.bin"
    dummy_file.write_bytes(b"A" * 1024 * 1024)  # 1 MB

    # Varrendo ambos os caminhos (pai e filho), o arquivo DEVE ser contabilizado apenas UMA vez
    scanned = scan_disk_downloaded_bytes([str(base_dir), str(cache_sub)])
    assert scanned == 1024 * 1024


def test_scoped_hf_stream_hook_patches_snapshot_download_and_utils(tmp_path):
    import sys
    import huggingface_hub.file_download as fd
    import huggingface_hub._snapshot_download as sd
    from src.model_manager import ModelManager
    from src.model_engines.hf.http_downloader import scoped_hf_stream_hook

    manager = ModelManager(base_dir=str(tmp_path))
    manager.download_status["florence2_large"]["status"] = "downloading"
    orig_fd = fd.tqdm
    orig_sd_hf = sd.hf_tqdm
    orig_sd_base = sd.base_tqdm

    with scoped_hf_stream_hook(manager, "florence2_large", target_total_bytes=5000) as tracker:
        assert fd.tqdm is not orig_fd
        assert sd.hf_tqdm is not orig_sd_hf
        assert sd.base_tqdm is not orig_sd_base

        # Testa se a telemetria é atualizada pelo tqdm interceptado
        bar = sd.hf_tqdm(total=5000, unit="B", desc="model.safetensors")
        bar.update(2500)
        st = manager.get_download_status("florence2_large")
        assert st["downloaded_bytes"] == 2500
        bar.close()


    # Restauração limpa
    assert fd.tqdm is orig_fd
    assert sd.hf_tqdm is orig_sd_hf
    assert sd.base_tqdm is orig_sd_base


def test_stream_hook_keeps_telemetry_alive_at_high_progress(tmp_path):
    from src.model_manager import ModelManager
    from src.model_engines.hf.http_downloader import build_scoped_tqdm_class

    manager = ModelManager(base_dir=str(tmp_path))
    manager.download_status["florence2_large"] = {
        "status": "downloading",
        "progress": 0.0,
        "downloaded_bytes": 0,
        "total_bytes": 10000000,
        "message": ""
    }

    tqdm_cls = build_scoped_tqdm_class(manager, "florence2_large", total_expected_bytes=10000000)
    bar = tqdm_cls(total=10000000, unit="B", desc="model.safetensors")
    
    # Avança para 9.92 MB (99.2%)
    bar.update(9920000)
    st = manager.get_download_status("florence2_large")
    assert st["progress"] >= 99.0
    # Telemetria NÃO pode ter sido zerada porque ainda restam 80 KB
    assert st["downloaded_bytes"] == 9920000
    assert "Baixando" in st["message"]
    bar.close()


def test_verify_safetensors_header_valid_and_corrupt(tmp_path):
    import json
    import struct
    from src.model_engines.hf.integrity_checker import verify_safetensors_header

    valid_st = tmp_path / "model.safetensors"
    header_bytes = json.dumps({
        "__metadata__": {"format": "pt"},
        "weight": {"dtype": "F16", "shape": [2, 2], "data_offsets": [0, 8]},
    }).encode("utf-8")
    valid_st.write_bytes(struct.pack("<Q", len(header_bytes)) + header_bytes + (b"\x00" * 8))
    assert verify_safetensors_header(str(valid_st), strict=True) is True

    # Cabeçalho truncado (declara 4096 bytes mas arquivo tem apenas 32 bytes)
    truncated_st = tmp_path / "truncated.safetensors"
    truncated_st.write_bytes(struct.pack("<Q", 4096) + b'{"weight":')
    assert verify_safetensors_header(str(truncated_st), strict=True) is False


def test_scoped_hf_stream_hook_resumes_initial_bytes_honestly(tmp_path):
    import huggingface_hub.file_download as fd
    from src.model_manager import ModelManager
    from src.model_engines.hf.http_downloader import scoped_hf_stream_hook

    manager = ModelManager(base_dir=str(tmp_path))
    manager.download_status["florence2_large"] = {
        "status": "downloading",
        "progress": 0.0,
        "downloaded_bytes": 1000,
        "total_bytes": 4000,
        "message": "",
    }

    with scoped_hf_stream_hook(
        manager, "florence2_large", target_total_bytes=4000, initial_bytes=1000
    ):
        bar = fd.tqdm(total=3000, initial=500, unit="B", desc="model.safetensors")
        bar.update(500)
        st = manager.get_download_status("florence2_large")
        # 1000 (arquivos prévios) + 500 (resume .incomplete) + 500 (novo chunk) = 2000 / 4000 (50%)
        assert st["downloaded_bytes"] == 2000
        assert st["progress"] == 50.0
        bar.close()


def test_hf_storage_cache_invalidation_and_torch_footprint_sensor(tmp_path):
    from src.model_manager import ModelManager
    from src.api_services.hf_download_orchestrator import HFDownloadOrchestrator
    from src.model_engines.core_engine_installer import CoreEngineInstaller

    manager = ModelManager(base_dir=str(tmp_path))
    orch = HFDownloadOrchestrator(model_manager=manager)
    orch._cached_hf_bytes = 999999
    orch._cached_hf_time = 1e12

    manager.download_status["yolo_detector"] = {
        "status": "installed",
        "progress": 100.0,
        "message": "Instalado com sucesso!",
    }
    orch.notify_progress("yolo_detector", manager.download_status["yolo_detector"])
    assert orch._cached_hf_bytes == 0
    assert orch._cached_hf_time == 0.0

    # Verifica sensor físico de pegada de disco para torch e diretórios temporários ~orch do pip no Windows
    fake_sp = tmp_path / "site-packages"
    torch_dir = fake_sp / "torch"
    stash_dir = fake_sp / "~orchvision"
    other_dir = fake_sp / "numpy"
    torch_dir.mkdir(parents=True)
    stash_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)
    (torch_dir / "torch_cuda.dll").write_bytes(b"A" * 4096)
    (stash_dir / "_C.pyd").write_bytes(b"B" * 2048)
    (other_dir / "core.py").write_bytes(b"C" * 8192)

    measured = CoreEngineInstaller._measure_torch_footprint_bytes([str(fake_sp)])
    assert measured == 4096 + 2048










