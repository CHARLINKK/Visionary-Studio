import os
import json
import hashlib
import threading
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from src.step2_ocr_extractor import (
    _resolve_hf_snapshot_path,
    _suppress_flash_attn_check,
    FlorenceReader,
)
from src.model_engines.hf_download_manager import (
    safe_remove_path,
    is_hf_model_cached,
    verify_file_integrity,
    HFDownloadManager,
    MODELS_REGISTRY,
    _build_scoped_tqdm_class,
)
from src.batch_pipeline.reading_order import (
    recursive_xy_cut,
    _bubble_xy_cut,
    sort_bubbles_reading_order,
)
from src.api_services.ollama_lifecycle_manager import OllamaLifecycleManager


@pytest.fixture(autouse=True)
def isolated_user_data(tmp_path, monkeypatch):
    user_data = tmp_path / "user_data"
    user_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VISIONARY_USER_DATA", str(user_data))
    from src.config import Config
    Config._cache = None
    Config._cache_mtime = 0.0
    yield user_data


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Testes para src/step2_ocr_extractor.py
# ═══════════════════════════════════════════════════════════════════════════════

def test_resolve_hf_snapshot_path_valid_and_empty(tmp_path):
    cache_dir = tmp_path / "hf_cache"
    assert _resolve_hf_snapshot_path(str(cache_dir), "microsoft/Florence-2-large") is None

    snap_dir = cache_dir / "models--microsoft--Florence-2-large" / "snapshots" / "abc1234"
    snap_dir.mkdir(parents=True)
    # Lock files only -> returns None
    (snap_dir / "temp.lock").write_bytes(b"lock")
    assert _resolve_hf_snapshot_path(str(cache_dir), "microsoft/Florence-2-large") is None

    # Real weight file -> returns snapshot path
    (snap_dir / "model.safetensors").write_bytes(b"real_weights")
    resolved = _resolve_hf_snapshot_path(str(cache_dir), "microsoft/Florence-2-large")
    assert resolved == str(snap_dir)


def test_suppress_flash_attn_check_restores_originals():
    import transformers.dynamic_module_utils as dmu
    orig_get = getattr(dmu, "get_imports", None)
    orig_check = getattr(dmu, "check_imports", None)

    with patch.object(dmu, "get_imports", side_effect=lambda f: ["torch", "flash_attn", "PIL"]):
        with _suppress_flash_attn_check():
            filtered = dmu.get_imports("dummy.py")
            assert "flash_attn" not in filtered
            assert "torch" in filtered

    assert getattr(dmu, "get_imports", None) == orig_get
    assert getattr(dmu, "check_imports", None) == orig_check


def test_florence_reader_load_read_batch_caption_fullpage_and_map(tmp_path, monkeypatch):
    models_dir = tmp_path / "user_data" / "models" / "florence-2-large"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "config.json").write_text("{}", encoding="utf-8")

    mock_processor = MagicMock()
    mock_inputs = MagicMock()
    mock_inputs.to.return_value = {"input_ids": "ids", "pixel_values": MagicMock()}
    mock_processor.return_value = mock_inputs
    mock_processor.batch_decode.return_value = ["decoded_output"]

    def fake_post_process(text, task, image_size):
        if task == "<OCR_WITH_REGION>":
            return {
                "<OCR_WITH_REGION>": {
                    "labels": ["Hello- </s>", "world\n"],
                    "quad_boxes": [[10, 20, 50, 20, 50, 40, 10, 40], [60, 25, 90, 25, 90, 45, 60, 45]],
                }
            }
        if task == "<OCR>":
            return {"<OCR>": "  Valid crop text \n"}
        if task == "<MORE_DETAILED_CAPTION>":
            return {"<MORE_DETAILED_CAPTION>": "Manga page showing a hero."}
        return {}

    mock_processor.post_process_generation.side_effect = fake_post_process

    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.generate.return_value = ["gen_ids"]

    with patch("src.step2_ocr_extractor.AutoProcessor.from_pretrained", return_value=mock_processor), \
         patch("src.step2_ocr_extractor.AutoModelForCausalLM.from_pretrained", return_value=mock_model), \
         patch("src.step2_ocr_extractor.cleanup_gpu_memory") as mock_cleanup:

        reader = FlorenceReader()
        reader.device = "cpu"
        reader.load()
        assert reader.model is mock_model
        assert reader.processor is mock_processor

        img = Image.new("RGB", (100, 100), color="white")

        # 1. read_text
        res = reader.read_text(img)
        assert res["text"] == "Helloworld"
        assert len(res["regions"]) == 2

        # 2. read_text_batch
        assert reader.read_text_batch([]) == []
        batch_res = reader.read_text_batch([img])
        assert len(batch_res) == 1
        assert batch_res[0]["text"] == "Helloworld"

        # 3. validate_crops_batch
        assert reader.validate_crops_batch([]) == []
        val_res = reader.validate_crops_batch([img])
        assert val_res == ["Valid crop text"]

        # 4. generate_image_caption
        cap = reader.generate_image_caption(img)
        assert cap == "Manga page showing a hero."

        # 5. read_full_page
        full_res = reader.read_full_page(img)
        assert len(full_res) == 2
        assert full_res[0]["x1"] == 10 and full_res[0]["y1"] == 20
        assert full_res[0]["x2"] == 50 and full_res[0]["y2"] == 40
        assert full_res[0]["label"] == "florence_text"

        # 6. process_map
        crops_dir = tmp_path / "crops"
        crops_dir.mkdir()
        crop_img_path = crops_dir / "001_balao_001.jpg"
        img.save(crop_img_path)

        map_path = tmp_path / "001_map.json"
        map_path.write_text(json.dumps([{"id": 1, "x1": 0, "y1": 0, "x2": 10, "y2": 10}]), encoding="utf-8")

        processed = reader.process_map(str(map_path), str(crops_dir))
        assert len(processed) == 1
        assert processed[0]["text"] == "Helloworld"

        # 7. unload
        reader.unload()
        assert reader.model is None
        assert reader.processor is None
        mock_cleanup.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Testes para src/model_engines/hf_download_manager.py
# ═══════════════════════════════════════════════════════════════════════════════

def test_safe_remove_path_and_is_hf_model_cached(tmp_path):
    assert safe_remove_path(str(tmp_path / "nonexistent")) is True

    f = tmp_path / "readonly.txt"
    f.write_text("data", encoding="utf-8")
    assert safe_remove_path(str(f)) is True
    assert not f.exists()

    model_dir = tmp_path / "hf_model"
    model_dir.mkdir()
    assert is_hf_model_cached(str(model_dir)) is False

    (model_dir / ".lock").write_text("lock", encoding="utf-8")
    assert is_hf_model_cached(str(model_dir)) is False

    snap = model_dir / "snapshots" / "s1"
    snap.mkdir(parents=True)
    (snap / "weights.bin").write_bytes(b"12345")
    assert is_hf_model_cached(str(model_dir)) is True

    assert safe_remove_path(str(model_dir)) is True
    assert not model_dir.exists()


def test_verify_file_integrity(tmp_path):
    assert verify_file_integrity(str(tmp_path / "missing.pt")) is False

    bad_pt = tmp_path / "bad.pt"
    bad_pt.write_bytes(b"HTML_404_NOT_FOUND" * 100)
    assert verify_file_integrity(str(bad_pt), min_size_bytes=10) is False

    good_pt = tmp_path / "good.pt"
    payload = b"PK\x03\x04" + (b"\x00" * 1024)
    good_pt.write_bytes(payload)
    expected_sha = hashlib.sha256(payload).hexdigest()

    assert verify_file_integrity(str(good_pt), expected_sha256=expected_sha, min_size_bytes=100) is True
    assert verify_file_integrity(str(good_pt), expected_sha256="0" * 64, min_size_bytes=100) is False


def test_hf_download_manager_status_and_downloads(tmp_path):
    mgr = HFDownloadManager(base_dir=str(tmp_path))
    events = []
    mgr.register_progress_callback(lambda k, st: events.append((k, st["status"])))

    unknown = mgr.get_download_status("invalid_key")
    assert unknown["status"] == "unknown"
    assert mgr.download_module("invalid_key") is False
    assert mgr.remove_module("invalid_key") is False

    # Scoped tqdm class test
    tqdm_cls = _build_scoped_tqdm_class(mgr, "florence2", base_pct=10.0, weight_pct=50.0)
    assert tqdm_cls is not None

    # Test huggingface_cache synchronous _run_download_thread
    with patch("huggingface_hub.snapshot_download") as mock_snap:
        def fake_snap(**kwargs):
            local_d = kwargs["local_dir"]
            os.makedirs(local_d, exist_ok=True)
            with open(os.path.join(local_d, "model.bin"), "wb") as fh:
                fh.write(b"x" * 2048)

        mock_snap.side_effect = fake_snap
        mgr._run_download_thread("florence2", MODELS_REGISTRY["florence2"])
        st = mgr.get_download_status("florence2")
        assert st["status"] == "installed"
        assert st["progress"] == 100.0
        assert any(k == "florence2" and s == "installed" for k, s in events)

    # Remove module
    assert mgr.remove_module("florence2") is True
    assert mgr.get_download_status("florence2")["status"] == "missing"

    # Test single_file with HTTP 206 resume
    single_info = {
        "type": "single_file",
        "target_dir": "models",
        "filename": "custom.pt",
        "url": "http://127.0.0.1/custom.pt",
        "estimated_size_bytes": 1024,
        "min_size_bytes": 10,
    }
    models_sub = tmp_path / "models"
    models_sub.mkdir(exist_ok=True)
    part_path = models_sub / "custom.pt.part"
    part_path.write_bytes(b"PK\x03\x04")

    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.status_code = 206
    mock_resp.headers = {"content-range": "bytes 4-103/104"}
    mock_resp.iter_content.return_value = [b"\x00" * 100]

    with patch("src.model_engines.hf_download_manager.requests.Session") as mock_sess_cls:
        mock_sess_cls.return_value.get.return_value = mock_resp
        mgr._run_download_thread("florence2", single_info)
        assert (models_sub / "custom.pt").exists()
        assert mgr.download_status["florence2"]["status"] == "installed"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Testes para src/batch_pipeline/reading_order.py
# ═══════════════════════════════════════════════════════════════════════════════

def test_reading_order_recursive_xy_cut_and_bubbles():
    assert sort_bubbles_reading_order([]) == []
    assert recursive_xy_cut([]) == []
    assert _bubble_xy_cut([]) == []

    # Two columns of bubbles without panels: right column should come before left column (RTL)
    bubbles = [
        {"id": 1, "x1": 50, "y1": 50, "x2": 150, "y2": 120, "text": "Left Top"},
        {"id": 2, "x1": 500, "y1": 50, "x2": 600, "y2": 120, "text": "Right Top"},
        {"id": 3, "x1": 500, "y1": 200, "x2": 600, "y2": 280, "text": "Right Bottom"},
        {"id": 4, "x1": 50, "y1": 200, "x2": 150, "y2": 280, "text": "Left Bottom"},
    ]
    sorted_no_panels = sort_bubbles_reading_order(bubbles, panels=None)
    texts = [b["text"] for b in sorted_no_panels]
    assert texts == ["Right Top", "Right Bottom", "Left Top", "Left Bottom"]
    assert all(b["panel_id"] == -1 for b in sorted_no_panels)
    assert [b["order"] for b in sorted_no_panels] == [1, 2, 3, 4]

    # With panels + orphan bubble assigned to nearest panel
    panels = [
        {"box": [400, 0, 800, 400]},  # Right panel
        {"box": [0, 0, 350, 400]},    # Left panel
    ]
    bubbles_with_orphan = [
        {"x1": 100, "y1": 100, "x2": 200, "y2": 180, "text": "Inside Left"},
        {"x1": 500, "y1": 80, "x2": 600, "y2": 150, "text": "Inside Right"},
        {"x1": 500, "y1": 420, "x2": 600, "y2": 460},  # Orphan just below Right panel, no text key
    ]
    ordered = sort_bubbles_reading_order(bubbles_with_orphan, panels=panels)
    assert len(ordered) == 3
    assert ordered[0]["text"] == "Inside Right"
    assert ordered[1]["text"] == ""  # Orphan assigned to right panel, lower Y
    assert ordered[2]["text"] == "Inside Left"

    # Dense overlapping cluster fallback in _bubble_xy_cut
    overlapping = [
        {"x1": 100, "y1": 100, "x2": 200, "y2": 200, "text": "A"},
        {"x1": 110, "y1": 110, "x2": 210, "y2": 210, "text": "B"},
    ]
    cluster_res = _bubble_xy_cut(overlapping)
    assert len(cluster_res) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Testes para src/api_services/ollama_lifecycle_manager.py
# ═══════════════════════════════════════════════════════════════════════════════

def test_ollama_lifecycle_manager_operations(monkeypatch):
    mock_mm = MagicMock()
    mock_mm.start_ollama_server.return_value = {"success": True, "status": "started"}
    mgr = OllamaLifecycleManager(model_manager=mock_mm)

    # 1. start_server / stop_server / open_site
    assert mgr.start_server()["success"] is True
    with patch("src.api_services.ollama_lifecycle_manager.ModelManager.terminate_ollama") as mock_term:
        assert mgr.stop_server()["success"] is True
        mock_term.assert_called_once()
    with patch("src.api_services.ollama_lifecycle_manager.webbrowser.open") as mock_wb:
        assert mgr.open_site()["success"] is True
        mock_wb.assert_called_once_with("https://ollama.com/download")

    # 2. _get_ollama_tags_cached & check_ollama_state & is_running
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [{"name": "mistral-nemo:latest", "size": 5 * (1024 ** 3)}]
    }
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.get.return_value = mock_resp
    mock_session.delete.return_value = MagicMock(status_code=200)

    with patch("src.api_services.ollama_lifecycle_manager.requests.Session", return_value=mock_session), \
         patch("src.model_engines.ollama_manifest_scanner.get_installed_ollama_models_list", return_value=["qwen2.5:32b"]), \
         patch("src.model_engines.ollama_manifest_scanner.scan_local_manifests", return_value=[{"name": "qwen2.5:32b", "size": 10 * (1024 ** 3)}]), \
         patch("socket.create_connection"):

        assert mgr.is_running() is True
        state, models = mgr.check_ollama_state()
        assert state == "installed_and_running"
        assert "mistral-nemo:latest" in models
        assert "qwen2.5:32b" in models

        # Storage & details
        details = mgr.get_ollama_models_details()
        assert "mistral-nemo:latest" in details
        assert "qwen2.5:32b" in details
        assert mgr.get_ollama_storage_bytes() == 15 * (1024 ** 3)

        # ensure_running when already running
        ens = mgr.ensure_running()
        assert ens["status"] == "already_running"

        # delete_model validation & execution
        assert mgr.delete_model("")["success"] is False
        assert mgr.delete_model("mistral-nemo:latest")["success"] is True

    # 3. test_translation
    assert mgr.test_translation("")["success"] is False
    trans_resp = MagicMock()
    trans_resp.status_code = 200
    trans_resp.json.return_value = {
        "response": "Segure firme!",
        "eval_count": 20,
        "eval_duration": 500_000_000,  # 0.5s -> 40 tok/s
    }
    mock_session.post.return_value = trans_resp
    with patch("src.api_services.ollama_lifecycle_manager.requests.Session", return_value=mock_session):
        tres = mgr.test_translation("mistral-nemo")
        assert tres["success"] is True
        assert tres["translation"] == "Segure firme!"
        assert tres["tokens_per_second"] == 40.0

    # 4. cancel_download
    assert mgr.cancel_download("nonexistent")["success"] is False
    ev = threading.Event()
    mgr._cancel_events["mistral-nemo"] = ev
    mgr._downloads["mistral-nemo"] = {"progress": 50}
    assert mgr.cancel_download("mistral-nemo")["success"] is True
    assert ev.is_set()
    assert "mistral-nemo" not in mgr._downloads
