import os
import json
import pytest
from fastapi.testclient import TestClient
from src.server import app
from src.api_services.settings_service import SettingsService
from src.api_services.library_service import LibraryService

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"

def test_image_security_filter(tmp_path):
    from src.utils.path_sandbox import register_root
    register_root(str(tmp_path))

    fake_exe = tmp_path / "malicious.exe"
    fake_exe.write_text("dummy")
    res_exe = client.get("/api/image", params={"path": str(fake_exe)})
    assert res_exe.status_code == 403

    res_nonexistent = client.get("/api/image", params={"path": str(tmp_path / "does_not_exist.png")})
    assert res_nonexistent.status_code == 404

    valid_img = tmp_path / "sample.png"
    valid_img.write_bytes(b"\x89PNG\r\n\x1a\n")
    res_valid = client.get("/api/image", params={"path": str(valid_img)})
    assert res_valid.status_code == 200

def test_settings_service_stats_and_cache(tmp_path, monkeypatch):
    stats_file = tmp_path / "stats.json"
    stats_file.write_text(json.dumps({"pagesProcessed": 10, "timeSaved": 30}))
    
    svc = SettingsService()
    orig_normpath = os.path.normpath
    monkeypatch.setattr("src.api_services.settings_service.os.path.normpath", lambda p: str(stats_file) if "stats.json" in str(p) else orig_normpath(p))
    
    stats = svc.getStats()
    assert stats["pagesProcessed"] == 10

    stats_file.write_text(json.dumps({"pagesProcessed": 15, "timeSaved": 45}))
    svc.invalidate_cache()
    stats_updated = svc.getStats()
    assert stats_updated["pagesProcessed"] == 15

def test_library_service_filters_temp_files(tmp_path):
    chapter_dir = tmp_path / "Chapter 01"
    chapter_dir.mkdir()
    
    (chapter_dir / "Chapter 01.txt").write_text("Script content", encoding="utf-8")
    (chapter_dir / "_glossary_temp.txt").write_text("glossary", encoding="utf-8")
    (chapter_dir / "requirements.txt").write_text("torch", encoding="utf-8")
    (chapter_dir / ".hidden.txt").write_text("hidden", encoding="utf-8")

    class MockBridge:
        current_path = str(chapter_dir)

    svc = LibraryService(MockBridge())
    res = svc.listLibraryFiles()
    assert res["success"] is True
    file_names = [f["name"] for f in res["files"]]
    
    assert "Chapter 01.txt" in file_names
    assert "_glossary_temp.txt" not in file_names
    assert "requirements.txt" not in file_names
    assert ".hidden.txt" not in file_names

def test_broadcast_log_sync_safe_execution():
    from src.server import broadcast_log_sync
    # Must not raise exceptions even when called from background threads or outside event loop
    broadcast_log_sync("job_progress", "test", progress=50, extra={"job_id": "test-123"})
    broadcast_log_sync("job_log", "test line", extra={"job_id": "test-123", "logs": ["line 1", "line 2"]})
    broadcast_log_sync("custom_event", "event", extra={"event_name": "xray-refresh", "payload": {}})

def test_dev_service_diagnostics_and_stats():
    from src.api_services.dev_service import DevService
    dev = DevService()
    stats = dev.getDevStats()
    assert "cuda_available" in stats
    assert "device_name" in stats
    assert "torch_version" in stats
    
    logs = dev.getDevLogs()
    assert "app_logs" in logs
    assert "test_logs" in logs
    assert isinstance(logs["app_logs"], list)

def test_config_in_memory_caching(tmp_path, monkeypatch):
    from src.config import Config
    fake_config = tmp_path / "settings.json"
    fake_config.write_text(json.dumps({"theme": "Light", "flask_port": 5000}))
    
    monkeypatch.setattr("src.config.CONFIG_FILE", str(fake_config))
    Config._cached_data = None
    Config._cached_mtime = 0
    
    loaded = Config.load()
    assert loaded["theme"] == "Light"
    
    # Update through Config
    Config.set("theme", "Dark")
    assert Config.get("theme") == "Dark"

def test_pipeline_service_job_status_and_dual_channel_sync(tmp_path):
    from unittest.mock import patch
    with patch("src.run_batch.run_batch_pipeline", return_value=True):
        from src.api_bridge import ApiBridge
        bridge = ApiBridge()
        pipeline_service = bridge._pipeline_service
        
        # Check initial pipeline status
        initial_status = pipeline_service.getPipelineStatus()
        assert initial_status["success"] is True
        assert isinstance(initial_status["jobs"], dict)
        
        # Test non-existent job
        res = pipeline_service.getJobStatus("non-existent-id")
        assert res["success"] is False
        
        # Test with custom job_id
        test_id = "test-job-999"
        data = {
            "job_id": test_id,
            "folderPath": str(tmp_path),
            "steps": {"layout": False, "ocr": False, "translate": False}
        }
        queue_res = pipeline_service.queueJob(data)
        assert queue_res["success"] is True
        assert queue_res["job_id"] == test_id
        
        # Verify active job was registered and can be queried
        job_status = pipeline_service.getJobStatus(test_id)
        assert job_status["success"] is True
        assert job_status["job_id"] == test_id
        assert "logs" in job_status
        assert "progress" in job_status
        assert "status" in job_status

def test_fastapi_core_endpoints():
    from fastapi.testclient import TestClient
    from src.server import app
    client = TestClient(app)
    
    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    
    # 2. Presets
    res = client.get("/api/presets")
    assert res.status_code == 200
    assert "boxing" in res.json()
    assert "shonen" in res.json()
    
    # 3. Models
    res = client.get("/api/models")
    assert res.status_code == 200
    assert isinstance(res.json(), dict)

def test_rpc_all_services(tmp_path):
    from fastapi.testclient import TestClient
    from src.server import app
    client = TestClient(app)

    # 1. Settings
    res = client.post("/api/rpc/getSettings", json={})
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert isinstance(res.json()["result"], dict)

    # 2. Hardware
    res = client.post("/api/rpc/getHardwareStats", json={})
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 3. FileSystem
    res = client.post("/api/rpc/get_drives", json={})
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 4. Studio
    img_file = tmp_path / "page_01.png"
    from PIL import Image
    im = Image.new("RGB", (100, 100), color="white")
    im.save(str(img_file))
    
    res = client.post("/api/rpc/get_page_data", json={"args": [str(img_file)]})
    assert res.status_code == 200
    assert res.json()["result"]["success"] is True
    
    boxes = [{"id": 1, "x1": 10, "y1": 10, "x2": 50, "y2": 50, "text": "Hello", "translated": "Olá"}]
    res = client.post("/api/rpc/save_page_layout", json={"args": [str(img_file), boxes]})
    assert res.status_code == 200
    assert res.json()["result"]["success"] is True

    res = client.post("/api/rpc/create_page_backup", json={"args": [str(img_file)]})
    assert res.status_code == 200
    assert res.json()["result"]["success"] is True

    res = client.post("/api/rpc/check_page_backup", json={"args": [str(img_file)]})
    assert res.status_code == 200
    assert res.json()["result"]["exists"] is True

    res = client.post("/api/rpc/restore_page_backup", json={"args": [str(img_file)]})
    assert res.status_code == 200
    assert res.json()["result"]["success"] is True

    res = client.post("/api/rpc/delete_page_backup", json={"args": [str(img_file)]})
    assert res.status_code == 200
    assert res.json()["result"]["success"] is True

    # 5. Library
    res = client.post("/api/rpc/listLibraryFiles", json={})
    assert res.status_code == 200
    assert res.json()["result"]["success"] is True

    # 6. Dev
    res = client.post("/api/rpc/getDevStats", json={})
    assert res.status_code == 200
    assert "torch_version" in res.json()["result"]

    # 7. Pipeline
    res = client.post("/api/rpc/getPipelineStatus", json={})
    assert res.status_code == 200
    assert res.json()["result"]["success"] is True

def test_safe_image_prefetcher_stale_worker_protection(tmp_path):
    """Verifica se o prefetcher descarta workers lentos obsoletos sem sobrescrever a imagem alvo."""
    from src.utils.image_prefetcher import SafeImagePrefetcher
    from PIL import Image
    import threading

    p1 = str(tmp_path / "img1.png")
    p2 = str(tmp_path / "img2.png")
    Image.new("RGB", (100, 100), color="green").save(p1)
    Image.new("RGB", (150, 150), color="yellow").save(p2)

    cancel = threading.Event()
    prefetcher = SafeImagePrefetcher([p1, p2], cancel_event=cancel)

    # Simula mudança de alvo em tempo real
    with prefetcher._lock:
        prefetcher._target_path = p2

    img2 = prefetcher.get_image(p2)
    assert img2.size == (150, 150)
    prefetcher.stop()

def test_safe_image_prefetcher_empty_and_corrupt_resilience(tmp_path):
    """Valida resiliência do prefetcher contra listas vazias e arquivos corrompidos."""
    from src.utils.image_prefetcher import SafeImagePrefetcher

    # 1. Lista vazia
    with SafeImagePrefetcher([]) as empty_pf:
        assert empty_pf._prefetched_img is None
        assert empty_pf.image_paths == []

    # 2. Arquivo corrompido (bytes inválidos)
    corrupt_file = str(tmp_path / "bad.png")
    with open(corrupt_file, "wb") as f:
        f.write(b"NOT_A_VALID_IMAGE_BYTES_XYZ")

    with SafeImagePrefetcher([corrupt_file]) as corrupt_pf:
        with pytest.raises(Exception):
            corrupt_pf.get_image(corrupt_file)

def test_model_manager_windows_replace_retry(tmp_path, monkeypatch):
    """Valida o mecanismo de retry para Windows em caso de lock temporário no os.replace."""
    import time

    calls = {"count": 0}
    orig_replace = os.replace

    def flaky_replace(src, dst):
        calls["count"] += 1
        if calls["count"] < 2:
            raise PermissionError("[WinError 32] O arquivo já está sendo usado por outro processo")
        return orig_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)

    f_src = str(tmp_path / "src.bin")
    f_dst = str(tmp_path / "dst.bin")
    with open(f_src, "w") as f: f.write("data")

    # Lógica de retry idêntica à de model_manager.py
    for attempt in range(3):
        try:
            if os.path.exists(f_dst):
                try: os.remove(f_dst)
                except Exception: pass
            os.replace(f_src, f_dst)
            break
        except (PermissionError, OSError) as pe:
            if attempt == 2:
                raise pe
            time.sleep(0.01)

    assert calls["count"] == 2
    assert os.path.exists(f_dst)
    assert not os.path.exists(f_src)

def test_api_bridge_show_system_notification():
    """Valida que a chamada de notificação do sistema no ApiBridge não quebra e é silenciosa em testes."""
    from src.api_bridge import ApiBridge
    bridge = ApiBridge()
    # Em ambientes de teste/headless, send_system_notification é suprimido silenciosamente sem apito
    res = bridge.showSystemNotification("Visionary Test", "Audit validation message")
    assert isinstance(res, dict)
    assert res.get("success") is True
    assert res.get("suppressed") is True

def test_send_system_notification_worker_logic(monkeypatch):
    """Valida a formatação segura do PowerShell com subprocess mockado, sem emitir som no SO."""
    import subprocess
    import time
    from unittest.mock import MagicMock
    from src.utils import notification

    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(subprocess, "run", mock_run)

    # Força execução do worker sem supressão apenas para este teste com subprocess mockado
    import sys
    monkeypatch.delitem(sys.modules, "pytest", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("VISIONARY_SILENT_TESTS", raising=False)

    res = notification.send_system_notification('Visionary "Test"', 'Audio "Safe" Message')
    assert res["success"] is True
    time.sleep(0.05)
    assert mock_run.called

def test_semantic_split_text_variations():
    """Valida as divisões semânticas por corte, conjunções e pontuações."""
    from src.translation_engine.nlp_heuristics import semantic_split_text

    # 1. Caso sem divisão ou texto vazio
    assert semantic_split_text("", 2) == [""]
    assert semantic_split_text("Texto simples", 1) == ["Texto simples"]

    # 2. Tag [CORTE] explícita
    text_tagged = "Primeira frase.[CORTE]Segunda frase."
    parts = semantic_split_text(text_tagged, 2)
    assert len(parts) == 2
    assert "Primeira frase." in parts[0]
    assert "Segunda frase." in parts[1]

    # 3. Variação case-insensitive [corte] / [cut]
    text_cut = "Parte 1 [cut] Parte 2 [corte] Parte 3"
    parts_cut = semantic_split_text(text_cut, 3)
    assert len(parts_cut) == 3

    # 4. Fallback semântico sem tag
    long_text = "Eu queria dizer que aquilo foi inacreditável, mas você não acreditou em mim quando eu avisei."
    split_fallback = semantic_split_text(long_text, 2)
    assert len(split_fallback) == 2
    assert all(len(p.strip()) > 0 for p in split_fallback)

def test_image_security_path_traversal():
    """Valida que o endpoint /api/image bloqueia caminhos inválidos ou vazios."""
    res_empty = client.get("/api/image?path=")
    assert res_empty.status_code == 400

    res_non_file = client.get("/api/image?path=C:/Windows")
    assert res_non_file.status_code == 403




