import os
import json
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from src.batch_pipeline.layout_runner import load_existing_layout, run_layout_detection, run_deep_validation
from src.batch_pipeline.ocr_runner import run_ocr_phase
from src.batch_pipeline.translation_runner import run_translation_phase


class TestBatchRunners:
    def test_load_existing_layout(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        map1 = out_dir / "01_map.json"
        map1.write_text(json.dumps([{"id": 1, "text": "Hello", "x1": 10, "y1": 10, "x2": 50, "y2": 50}]), encoding="utf-8")

        images = [str(tmp_path / "in" / "01.jpg"), str(tmp_path / "in" / "02.jpg")]
        boxes, panels = load_existing_layout(images, str(out_dir))

        assert str(tmp_path / "in" / "01.jpg") in boxes
        assert len(boxes[str(tmp_path / "in" / "01.jpg")]) == 1
        assert str(tmp_path / "in" / "02.jpg") not in boxes

    @patch("src.step1_layout_detector.YoloMapeador")
    def test_run_layout_detection(self, mock_yolo, tmp_path):
        in_img = tmp_path / "01.jpg"
        in_img.write_bytes(b"dummy")

        mock_inst = MagicMock()
        mock_yolo.return_value = mock_inst
        mock_inst.detect_bubbles.return_value = [{"x1": 0, "y1": 0, "x2": 20, "y2": 20}]
        mock_inst.detect_panels_and_sort.return_value = ([], [{"x1": 0, "y1": 0, "x2": 20, "y2": 20}])
        mock_inst.add_polygons.return_value = [{"x1": 0, "y1": 0, "x2": 20, "y2": 20}]

        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value = Image.new("RGB", (100, 100))
            boxes, panels = run_layout_detection([str(in_img)], str(tmp_path), phase1_weight=50.0)

            assert str(in_img) in boxes
            assert len(boxes[str(in_img)]) == 1
            mock_inst.unload_bubble_detector.assert_called_once()
            mock_inst.unload_panel_detector.assert_called_once()

    @patch("src.step2_ocr_extractor.FlorenceReader")
    def test_run_deep_validation(self, mock_flo, tmp_path):
        in_img = tmp_path / "01.jpg"
        in_img.write_bytes(b"dummy")

        mock_inst = MagicMock()
        mock_flo.return_value = mock_inst
        # Retorna um texto válido e um lixo que deve ser filtrado
        mock_inst.validate_crops_batch.return_value = ["Fala válida!", "1"]

        boxes = {
            str(in_img): [
                {"x1": 10, "y1": 10, "x2": 30, "y2": 30, "label": "text_bubble"},
                {"x1": 40, "y1": 40, "x2": 60, "y2": 60, "label": "text_bubble"}
            ]
        }

        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value = Image.new("RGB", (100, 100))
            filtered_boxes, shared_reader = run_deep_validation(
                [str(in_img)],
                str(tmp_path),
                all_phase1_boxes=boxes,
                all_phase1_panels={},
                only_layout=False
            )
            # Apenas a fala válida deve permanecer
            assert len(filtered_boxes[str(in_img)]) == 1
            assert filtered_boxes[str(in_img)][0]["order"] == 1
            assert shared_reader is mock_inst

    @patch("src.step2_ocr_extractor.FlorenceReader")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    def test_run_ocr_phase(self, mock_sync, mock_flo, tmp_path):
        in_img = tmp_path / "01.jpg"
        in_img.write_bytes(b"dummy")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        mock_inst = MagicMock()
        mock_flo.return_value = mock_inst
        mock_inst.read_text_batch.return_value = [{"text": "Texto extraído", "regions": []}]

        boxes = {
            str(in_img): [{"x1": 10, "y1": 10, "x2": 50, "y2": 50}]
        }

        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value = Image.new("RGB", (100, 100))
            json_paths = run_ocr_phase(
                images_to_process=[str(in_img)],
                output_dir=str(out_dir),
                input_dir=str(tmp_path),
                all_phase1_boxes=boxes,
                all_phase1_panels={},
                ocr_base_prog=10.0,
                ocr_page_weight=20.0,
            )
            assert len(json_paths) == 1
            assert os.path.exists(json_paths[0])
            mock_inst.unload.assert_called_once()
            mock_sync.assert_called()

    @patch("src.step2_ocr_extractor.FlorenceReader")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    def test_run_ocr_phase_skips_sfx_boxes(self, mock_sync, mock_flo, tmp_path):
        in_img = tmp_path / "01.jpg"
        in_img.write_bytes(b"dummy")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        mock_inst = MagicMock()
        mock_flo.return_value = mock_inst
        mock_inst.read_text_batch.return_value = [{"text": "Fala do balão", "regions": []}]

        boxes = {
            str(in_img): [
                {"x1": 10, "y1": 10, "x2": 50, "y2": 50, "is_sfx": True},
                {"x1": 60, "y1": 60, "x2": 90, "y2": 90, "is_sfx": False},
            ]
        }

        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value = Image.new("RGB", (100, 100))
            json_paths = run_ocr_phase(
                images_to_process=[str(in_img)],
                output_dir=str(out_dir),
                input_dir=str(tmp_path),
                all_phase1_boxes=boxes,
                all_phase1_panels={},
                ocr_base_prog=10.0,
                ocr_page_weight=20.0,
            )
            assert len(json_paths) == 1
            assert mock_inst.read_text_batch.call_count == 1
            called_crops = mock_inst.read_text_batch.call_args[0][0]
            assert len(called_crops) == 1

            with open(json_paths[0], "r", encoding="utf-8") as f:
                saved = json.load(f)
            from src.domain.page_store import PageStore
            saved_boxes = PageStore.extract_boxes(saved)
            assert len(saved_boxes) == 2
            sfx_box = [b for b in saved_boxes if b.get("is_sfx")][0]
            assert sfx_box["order"] is None
            assert sfx_box["text"] == ""
            bubble_box = [b for b in saved_boxes if not b.get("is_sfx")][0]
            assert bubble_box["order"] == 1
            assert bubble_box["text"] == "Fala do balão"

    @patch("src.step2_ocr_extractor.FlorenceReader")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    @patch("src.batch_pipeline.ocr_runner.vram_arbiter")
    def test_run_ocr_phase_throttles_batch_on_low_vram(self, mock_vram, mock_sync, mock_flo, tmp_path):
        in_img = tmp_path / "01.jpg"
        in_img.write_bytes(b"dummy")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        mock_inst = MagicMock()
        mock_flo.return_value = mock_inst
        mock_inst.read_text_batch.return_value = [{"text": "T", "regions": []}, {"text": "T", "regions": []}]

        mock_vram.get_recommended_ocr_batch_size.return_value = 4
        # Headroom constrained: ensure_headroom_mb returns (False, 200MB)
        mock_vram.ensure_headroom_mb.return_value = (False, 200.0)

        boxes = {
            str(in_img): [
                {"x1": 10, "y1": 10, "x2": 20, "y2": 20},
                {"x1": 25, "y1": 25, "x2": 35, "y2": 35},
                {"x1": 40, "y1": 40, "x2": 50, "y2": 50},
                {"x1": 55, "y1": 55, "x2": 65, "y2": 65},
            ]
        }

        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value = Image.new("RGB", (100, 100))
            json_paths = run_ocr_phase(
                images_to_process=[str(in_img)],
                output_dir=str(out_dir),
                input_dir=str(tmp_path),
                all_phase1_boxes=boxes,
                all_phase1_panels={},
                ocr_base_prog=0.0,
                ocr_page_weight=10.0,
            )
            assert len(json_paths) == 1
            # Throttled from 4 to 2, so 4 boxes split into 2 batches of 2
            assert mock_inst.read_text_batch.call_count == 2
            for call in mock_inst.read_text_batch.call_args_list:
                assert len(call[0][0]) == 2

    @patch("src.step2_ocr_extractor.FlorenceReader")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    @patch("src.batch_pipeline.ocr_runner.vram_arbiter")
    def test_run_ocr_phase_oom_fallback(self, mock_vram, mock_sync, mock_flo, tmp_path):
        in_img = tmp_path / "01.jpg"
        in_img.write_bytes(b"dummy")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        mock_inst = MagicMock()
        mock_flo.return_value = mock_inst
        mock_vram.get_recommended_ocr_batch_size.return_value = 2
        mock_vram.ensure_headroom_mb.return_value = (True, 1500.0)

        def side_effect_read(crops):
            if len(crops) > 1:
                raise RuntimeError("CUDA out of memory. Tried to allocate 512.00 MiB")
            return [{"text": "Single Fallback OK", "regions": []}]

        mock_inst.read_text_batch.side_effect = side_effect_read

        boxes = {
            str(in_img): [
                {"x1": 10, "y1": 10, "x2": 20, "y2": 20},
                {"x1": 25, "y1": 25, "x2": 35, "y2": 35},
            ]
        }

        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value = Image.new("RGB", (100, 100))
            json_paths = run_ocr_phase(
                images_to_process=[str(in_img)],
                output_dir=str(out_dir),
                input_dir=str(tmp_path),
                all_phase1_boxes=boxes,
                all_phase1_panels={},
                ocr_base_prog=0.0,
                ocr_page_weight=10.0,
            )
            assert len(json_paths) == 1
            # Initial batch of 2 failed with CUDA OOM, fallback triggered 2 single-item calls
            assert mock_inst.read_text_batch.call_count == 3
            mock_vram.ensure_headroom_mb.assert_any_call(0.0)

    @patch("src.step4_translator.OllamaTranslator")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    def test_run_translation_phase(self, mock_sync, mock_trans, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        mock_inst = MagicMock()
        mock_trans.return_value = mock_inst

        success = run_translation_phase(
            input_dir=str(in_dir),
            output_dir=str(out_dir),
            image_paths=[str(in_dir / "01.jpg")],
            model="qwen2.5:14b",
        )
        assert success is True
        mock_inst.process_directory.assert_called_once()
        mock_sync.assert_called_once()

    def test_run_translation_phase_no_model(self, tmp_path):
        success = run_translation_phase(
            input_dir=str(tmp_path),
            output_dir=str(tmp_path),
            image_paths=[],
            model=None
        )
        assert success is False
