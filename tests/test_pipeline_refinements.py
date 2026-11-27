import os
import json
import time
from unittest.mock import patch, MagicMock
from src.batch_pipeline.scanner import filter_cached_images
from src.translation_engine.ollama_client import translate_bubbles
from src.run_batch import run_batch_pipeline, request_cancel


def test_filter_cached_images_splash_page_skipped(tmp_path):
    img_path = tmp_path / "page_01.png"
    img_path.write_bytes(b"dummy_img")
    
    map_path = tmp_path / "page_01_map.json"
    map_path.write_text(json.dumps({"boxes": []}), encoding="utf-8")
    
    # Ensure map_path is newer than img_path
    now = time.time()
    os.utime(str(img_path), (now - 100, now - 100))
    os.utime(str(map_path), (now, now))
    
    res = filter_cached_images([str(img_path)], str(tmp_path))
    assert res == []


def test_filter_cached_images_modified_image_reprocessed(tmp_path):
    img_path = tmp_path / "page_02.png"
    img_path.write_bytes(b"dummy_img_new")
    
    map_path = tmp_path / "page_02_map.json"
    map_path.write_text(json.dumps({"boxes": []}), encoding="utf-8")
    
    # Image is newer than map
    now = time.time()
    os.utime(str(map_path), (now - 100, now - 100))
    os.utime(str(img_path), (now, now))
    
    res = filter_cached_images([str(img_path)], str(tmp_path))
    assert res == [str(img_path)]


def test_translation_context_sliding_window():
    # Simulate 10 pages in context
    old_context = [[{"id": f"p{p}_b{b}", "text": f"text {p}"}] for p in range(10) for b in range(1)]
    bubbles = [{"id": "new_1", "text": "HELLO", "translated_text": "olá"}]
    
    # Call translate_bubbles when bubbles already have translated_text or empty payload
    res_bubbles, new_ctx = translate_bubbles(bubbles, context=old_context, model="test_model")
    assert len(new_ctx) <= 6


@patch("src.step1_layout_detector.YoloMapeador")
@patch("src.step2_ocr_extractor.FlorenceReader")
@patch("src.step4_translator.OllamaTranslator")
@patch("src.api_services.dev_service.DevService")
@patch("src.utils.txt_sync.sync_chapter_txt")
def test_sync_chapter_txt_on_cancel(mock_sync, mock_dev, mock_trans, mock_flo, mock_yolo, tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    img = in_dir / "01.png"
    img.write_text("fake")

    import src.run_batch
    src.run_batch._cancel_event.set()
    src.run_batch._rollback_flag = False

    run_batch_pipeline(str(in_dir), str(out_dir))
    
    # Assert sync_chapter_txt was called even on cancel
    assert mock_sync.called
