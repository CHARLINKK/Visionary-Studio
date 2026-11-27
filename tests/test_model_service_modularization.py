import pytest
from unittest.mock import MagicMock, patch
import threading

from src.api_services.ollama_lifecycle_manager import OllamaLifecycleManager
from src.api_services.hf_download_orchestrator import HFDownloadOrchestrator
from src.model_engines.core_engine_installer import CoreEngineInstaller
from src.api_services.model_service import ModelService
from src.utils.event_bus import EventBus


def test_ollama_lifecycle_manager_direct_and_eventbus(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    bus = EventBus.get_instance()
    events_received = []

    def on_progress(payload):
        events_received.append(payload)

    bus.subscribe("downloads_progress", on_progress)
    try:
        downloads = {}
        completed = set()
        cancel_events = {}
        sessions = {}
        lock = threading.Lock()

        mgr = OllamaLifecycleManager(
            downloads=downloads,
            completed_models=completed,
            cancel_events=cancel_events,
            active_sessions=sessions,
            lock=lock,
        )

        # 1. Test is_running fallback
        with patch("socket.create_connection", side_effect=OSError("Refused")):
            assert mgr.is_running() is False

        # 2. Test get_downloads_snapshot
        downloads["test_model"] = {"progress": 45.0, "status": "downloading"}
        completed.add("done_model")
        snapshot = mgr.get_downloads_snapshot()
        assert "test_model" in snapshot
        assert snapshot["test_model"]["progress"] == 45.0
        assert "done_model" in snapshot
        assert snapshot["done_model"]["progress"] == 100.0

        # 3. Test notify_progress fires event bus
        mgr.notify_progress(throttle_interval=0.0)
        assert len(events_received) >= 1
        assert "ollama" in events_received[-1]

        # 4. Test cancel_download triggers event and clears download
        cancel_event = threading.Event()
        cancel_events["test_model"] = cancel_event
        cancel_res = mgr.cancel_download("test_model")
        assert cancel_res["success"] is True
        assert cancel_event.is_set()
        assert "test_model" not in downloads

        # 5. Test empty model validations
        assert mgr.delete_model("")["success"] is False
        assert mgr.pull_model("")["success"] is False
        assert mgr.test_translation("")["success"] is False
    finally:
        bus.unsubscribe("downloads_progress", on_progress)


def test_hf_download_orchestrator_direct_and_eventbus(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    bus = EventBus.get_instance()
    events_received = []

    def on_event(payload):
        events_received.append(payload)

    bus.subscribe("downloads_progress", on_event)
    try:
        from src.model_manager import ModelManager
        manager = ModelManager(base_dir=str(tmp_path))
        orchestrator = HFDownloadOrchestrator(model_manager=manager)

        # 1. Status checking with disk cache
        status = orchestrator.get_active_hf_status()
        assert isinstance(status, dict)

        # 2. Storage stats calculation
        stats = orchestrator.get_storage_stats(ollama_bytes=1024 * 1024)
        assert stats["success"] is True
        assert stats["ollama_bytes"] == 1024 * 1024
        assert "total_gb" in stats
        assert "total_formatted" in stats

        # 3. Notification via EventBus
        orchestrator.notify_progress("florence2", {"status": "downloading", "progress": 50.0})
        assert len(events_received) >= 1
        assert "hf" in events_received[-1]
    finally:
        bus.unsubscribe("downloads_progress", on_event)


def test_core_engine_installer_direct_and_eventbus():
    bus = EventBus.get_instance()
    events_received = []

    def on_event(payload):
        events_received.append(payload)

    bus.subscribe("core_engine_progress", on_event)
    try:
        installer = CoreEngineInstaller()

        # 1. Check AI dependencies
        deps = installer.check_ai_dependencies()
        assert "ai_state" in deps
        assert "has_torch" in deps
        assert "has_transformers" in deps
        assert "has_ultralytics" in deps
        assert "has_einops" in deps
        assert "has_timm" in deps

        # 2. Fast-path installation when packages exist
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            res = installer.install_core_engine()
            assert res["success"] is True
            assert "já está instalado" in res["message"]
            prog = installer.get_install_progress()
            assert prog["status"] == "completed"
            assert prog["percent"] == 100.0

        # 3. EventBus notification
        assert len(events_received) >= 1
        assert events_received[-1]["status"] == "completed"

        # 4. Partial dependencies (missing ultralytics) must report not_installed
        def mock_find_spec_no_ultra(name):
            if name == "ultralytics":
                return None
            mock_spec = MagicMock()
            mock_spec.has_location = True
            mock_spec.origin = "/path/to/pkg"
            return mock_spec

        with patch("importlib.util.find_spec", side_effect=mock_find_spec_no_ultra):
            deps = installer.check_ai_dependencies()
            assert deps["has_ultralytics"] is False
            assert deps["ai_state"] == "not_installed"

        # 5. Missing transformers must also report not_installed
        def mock_find_spec_no_trans(name):
            if name == "transformers":
                return None
            mock_spec = MagicMock()
            mock_spec.has_location = True
            mock_spec.origin = "/path/to/pkg"
            return mock_spec

        with patch("importlib.util.find_spec", side_effect=mock_find_spec_no_trans):
            deps = installer.check_ai_dependencies()
            assert deps["has_transformers"] is False
            assert deps["ai_state"] == "not_installed"
    finally:
        bus.unsubscribe("core_engine_progress", on_event)


def test_model_service_facade_delegation_and_properties(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    from src.model_manager import ModelManager

    mock_ollama_mgr = MagicMock()
    mock_ollama_mgr._ollama_start_lock = threading.Lock()
    mock_ollama_mgr._ollama_starting = False
    mock_ollama_mgr.check_ollama_state.return_value = ("installed_and_running", ["qwen2.5:14b"])
    mock_ollama_mgr.get_downloads_snapshot.return_value = {"qwen2.5:14b": {"progress": 100.0}}
    mock_ollama_mgr.get_ollama_storage_bytes.return_value = 5000

    mock_hf = MagicMock()
    mock_hf.get_active_hf_status.return_value = {"florence2": {"status": "installed"}}
    mock_hf.get_storage_stats.return_value = {"success": True, "total_bytes": 10000}

    mock_core = MagicMock()
    mock_core.check_ai_dependencies.return_value = {
        "ai_state": "installed",
        "has_torch": True,
        "has_transformers": True,
        "has_ultralytics": True,
    }
    mock_core.get_install_progress.return_value = {"status": "completed", "percent": 100.0}

    manager = ModelManager(base_dir=str(tmp_path))
    service = ModelService(
        api_bridge=None,
        model_manager=manager,
        ollama_manager=mock_ollama_mgr,
        hf_orchestrator=mock_hf,
        core_installer=mock_core,
    )

    # 1. Properties
    assert service._ollama_start_lock is mock_ollama_mgr._ollama_start_lock
    assert service._ollama_starting is False
    service._ollama_starting = True
    assert mock_ollama_mgr._ollama_starting is True

    # 2. checkModulesStatus combines both
    modules = service.checkModulesStatus()
    assert modules["ollama"]["state"] == "installed_and_running"
    assert modules["ocr"]["state"] == "installed"
    assert "qwen2.5:14b" in modules["ollamaModels"]
    assert "ollamaModelsDetails" in modules

    # 3. getDownloadsProgress merges both
    dls = service.getDownloadsProgress()
    assert dls["success"] is True
    assert "qwen2.5:14b" in dls["ollama"]
    assert "florence2" in dls["hf"]

    # 4. Storage stats delegation
    stats = service.getStorageStats()
    assert stats["success"] is True
    assert stats["total_bytes"] == 10000
    mock_ollama_mgr.get_ollama_storage_bytes.assert_called_once()
    mock_hf.get_storage_stats.assert_called_once_with(ollama_bytes=5000)

    # 5. Core engine progress delegation
    prog = service.getInstallProgress()
    assert prog["status"] == "completed"
    mock_core.get_install_progress.assert_called_once()


def test_resolve_torch_hub_checkpoints_dir(tmp_path, monkeypatch):
    import sys
    from src.api_services.hf_download_orchestrator import _resolve_torch_hub_checkpoints_dir

    # 1. Custom TORCH_HOME
    custom_torch = tmp_path / "custom_torch"
    custom_checkpoints = custom_torch / "hub" / "checkpoints"
    custom_checkpoints.mkdir(parents=True)
    monkeypatch.setenv("TORCH_HOME", str(custom_torch))

    resolved = _resolve_torch_hub_checkpoints_dir()
    assert resolved == str(custom_checkpoints)

    # 2. When TORCH_HOME is absent, falls back gracefully WITHOUT cold-importing torch
    monkeypatch.delenv("TORCH_HOME", raising=False)
    saved_torch = sys.modules.pop("torch", None)
    try:
        resolved_fallback = _resolve_torch_hub_checkpoints_dir()
        assert isinstance(resolved_fallback, str)
        assert "torch" not in sys.modules
    finally:
        if saved_torch is not None:
            sys.modules["torch"] = saved_torch
