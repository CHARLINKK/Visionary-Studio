import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json
import tempfile
import shutil



from src.step4_translator import OllamaTranslator
from src.translation_engine.prompt_builder import build_system_prompt
from src.translation_engine.json_healer import parse_or_heal_translation_json
from src.run_batch import _calc_text_margin, run_batch_pipeline

class TestLayer4PipelineAudit(unittest.TestCase):
    def tearDown(self):
        import src.run_batch as rb
        rb._cancel_event.clear()
        rb._rollback_flag = False

    def test_preset_tone_modulation(self):
        p_boxing = build_system_prompt("boxing")
        self.assertIn("Luta e Confronto", p_boxing)
        self.assertIn("peso-pena", p_boxing)

        p_shonen = build_system_prompt("shonen")
        self.assertIn("Shonen (Ação, Intensidade e Espírito Jovem)", p_shonen)
        self.assertIn("Termos Frequentes de Ação e Shonen", p_shonen)

        p_seinen = build_system_prompt("seinen")
        self.assertIn("Seinen (Maduro, Dramático e Profundo)", p_seinen)
        self.assertIn("Diretrizes Vocabulares Seinen", p_seinen)

        p_comedy = build_system_prompt("comedy")
        self.assertIn("Comédia e Humor Brasileiro", p_comedy)
        self.assertIn("Expressões Cômicas e Reações", p_comedy)

        p_neutral = build_system_prompt("neutral")
        self.assertIn("Neutro e Equilibrado", p_neutral)

        p_custom = build_system_prompt("shonen", custom_instructions="Hokage -> Líder da Vila")
        self.assertIn("Work-Specific Glossary", p_custom)
        self.assertIn("Hokage -> Líder da Vila", p_custom)

    def test_parse_or_heal_markdown_with_preamble_and_envelope(self):
        response_with_preamble = """
        Aqui está o resultado:
        ```json
        {
          "translations": [
            {"id": 1, "text": "fala um"},
            {"id": 2, "text": "fala dois"}
          ]
        }
        ```
        Espero ter ajudado!
        """
        res = parse_or_heal_translation_json(response_with_preamble)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['text'], "fala um")
        self.assertEqual(res[1]['text'], "fala dois")

        raw_envelope = 'Claro, aqui está: [{"id": 10, "text": "olá mundo"}] aproveite!'
        res2 = parse_or_heal_translation_json(raw_envelope)
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0]['text'], "olá mundo")

    def test_calc_text_margin_missing_keys_safe(self):
        b_incomplete = {"x1": 10, "y1": 10}
        margin = _calc_text_margin(b_incomplete, 20, 20)
        self.assertIsInstance(margin, (int, float))

        b_none_keys = {"x1": None, "y1": None, "x2": None, "y2": None}
        margin_none = _calc_text_margin(b_none_keys, 20, 20)
        self.assertIsInstance(margin_none, (int, float))
        self.assertEqual(margin_none, -20)

    def test_only_layout_cancellation_status_and_rollback(self):
        temp_dir = tempfile.mkdtemp(prefix="test_layout_cancel_")
        try:
            output_dir = os.path.join(temp_dir, "output")
            from PIL import Image
            img_p = os.path.join(temp_dir, "001.png")
            Image.new("RGB", (100, 100), color="white").save(img_p)
            os.makedirs(output_dir, exist_ok=True)
            map_file = os.path.join(output_dir, "001_map.json")
            with open(map_file, "w", encoding="utf-8") as f:
                json.dump([{"id": 1, "text": "Antigo"}], f)

            import src.run_batch as rb

            def mock_detect(img, *args, **kwargs):
                rb.request_cancel(rollback=True)
                return [{"id": 99, "text": "Novo Layout", "x1": 10, "y1": 10, "x2": 50, "y2": 50}]

            with patch("src.step1_layout_detector.YoloMapeador.detect_bubbles", side_effect=mock_detect):
                res = rb.run_batch_pipeline(temp_dir, output_dir, only_layout=True, overwrite=True)

            self.assertFalse(res)

            with open(map_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data[0]["text"], "Antigo")
        finally:
            rb._cancel_event.clear()
            rb._rollback_flag = False
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_only_layout_fails_when_all_pages_throw(self):
        """Valida que run_batch_pipeline retorna False quando todas as imagens falham na detecção de layout."""
        temp_dir = tempfile.mkdtemp(prefix="test_layout_all_fail_")
        try:
            output_dir = os.path.join(temp_dir, "output")
            from PIL import Image
            img_p = os.path.join(temp_dir, "001.png")
            Image.new("RGB", (100, 100), color="white").save(img_p)
            os.makedirs(output_dir, exist_ok=True)

            import src.run_batch as rb

            def mock_fail(img, *args, **kwargs):
                raise RuntimeError("Falha simulada no modelo YOLO")

            with patch("src.step1_layout_detector.YoloMapeador.detect_bubbles", side_effect=mock_fail):
                res = rb.run_batch_pipeline(temp_dir, output_dir, only_layout=True, overwrite=True)

            self.assertFalse(res)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_process_directory_page_error_isolation(self):
        temp_dir = tempfile.mkdtemp(prefix="test_iso_")
        try:
            p1 = os.path.join(temp_dir, "001_map.json")
            p2 = os.path.join(temp_dir, "002_map.json")
            with open(p1, "w", encoding="utf-8") as f:
                json.dump([{"id": 1, "text": "Page 1"}], f)
            with open(p2, "w", encoding="utf-8") as f:
                json.dump([{"id": 2, "text": "Page 2"}], f)

            translator = OllamaTranslator(model="test-model", preset="neutral")

            call_count = [0]
            def mock_translate(bubbles, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise RuntimeError("Falha simulada na pagina 1")
                return [{"id": 2, "text": "pagina dois"}], []

            with patch("src.step4_translator.translate_bubbles", side_effect=mock_translate):
                translator.process_directory(temp_dir, temp_dir, overwrite=True)

            self.assertEqual(call_count[0], 2)
            with open(p2, "r", encoding="utf-8") as f:
                data2 = json.load(f)
            self.assertEqual(data2["version"], 2)
            self.assertEqual(data2["boxes"][0]["text"], "pagina dois")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_pipeline_service_job_cancellation_status(self):
        """Valida que jobs cancelados no pipeline_service transitam para status cancelled e não completed."""
        from src.api_services.pipeline_service import PipelineService
        import time

        mock_bridge = MagicMock()
        mock_bridge.getSettings.return_value = {}
        mock_bridge.finalizePipeline.return_value = {"success": True}

        service = PipelineService(mock_bridge)
        job_data = {
            "job_id": "test_cancel_job",
            "folderPath": "dummy_path",
            "steps": {"layout": True, "ocr": False, "translate": False},
            "tone": "neutral",
            "model": "test-model"
        }

        def mock_pipeline(*args, **kwargs):
            import src.run_batch as rb
            rb._cancel_event.set()
            return False

        with patch("src.run_batch.run_batch_pipeline", side_effect=mock_pipeline):
            res = service.queueJob(job_data)
            status = None
            for _ in range(60):
                status = service.getJobStatus("test_cancel_job")
                if status and status.get("status") == "cancelled":
                    break
                time.sleep(0.05)

            self.assertEqual(status["status"], "cancelled")
            self.assertIn("Cancelado", status["step_label"])
            self.assertFalse(mock_bridge.finalizePipeline.called)

    def test_florence_reader_auto_detects_installed_base_model(self):
        import tempfile
        from src.step2_ocr_extractor import FlorenceReader

        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = os.path.join(tmp_dir, "models", "florence-2-base")
            os.makedirs(base_dir, exist_ok=True)
            with open(os.path.join(base_dir, "config.json"), "w", encoding="utf-8") as f:
                f.write("{}")
            with open(os.path.join(base_dir, "processing_florence2.py"), "w", encoding="utf-8") as f:
                f.write("# processor code")
            with open(os.path.join(base_dir, "model.safetensors"), "wb") as f:
                f.write(b"mock_weights")

            reader = FlorenceReader()
            mock_model = MagicMock()
            mock_model.to.return_value = mock_model

            with patch("src.step2_ocr_extractor.get_app_data_dir", return_value=tmp_dir), \
                 patch("src.step2_ocr_extractor.AutoProcessor.from_pretrained") as mock_proc, \
                 patch("src.step2_ocr_extractor.AutoModelForCausalLM.from_pretrained", return_value=mock_model) as mock_causal:
                reader.load()
                self.assertEqual(reader.model_id, "microsoft/Florence-2-base")
                mock_proc.assert_called_once()
                self.assertEqual(mock_proc.call_args[0][0], base_dir)
                self.assertTrue(mock_proc.call_args[1].get("local_files_only"))
                mock_causal.assert_called_once()
                self.assertEqual(mock_causal.call_args[0][0], base_dir)

