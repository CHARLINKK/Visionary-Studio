import unittest
from unittest.mock import patch, MagicMock
from src.api_services.studio_service import StudioService
import os
import json
import tempfile

class TestStudioService(unittest.TestCase):
    def setUp(self):
        self.api = MagicMock()
        self.ss = StudioService(self.api)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data='[{"id": 1, "text": "Oi"}]')
    @patch("os.makedirs")
    def test_get_page_data(self, mock_makedirs, mock_open, mock_exists):
        res = self.ss.get_page_data("C:/fake/01.jpg")
        print(f"GET PAGE DATA RES: {res}")
        self.assertTrue(res["success"])
        self.assertEqual(len(res["cards"]), 1)

    @patch("os.path.exists", return_value=False)
    def test_get_page_data_not_found(self, mock_exists):
        res = self.ss.get_page_data("C:/fake/01.jpg")
        self.assertFalse(res["success"])

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("src.api_services.studio_service.dump_compact_map")
    @patch("os.makedirs")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    @patch("shutil.copy2") # Mock externo para backup, em vez de mockar método interno
    def test_save_page_layout(self, mock_copy, mock_sync, mock_makedirs, mock_dump, mock_open, mock_exists):
        # Simula leitura do layout e escrita do novo dump
        mock_open.return_value.read.return_value = "[]"
        
        boxes = [{"id": 1, "x1": 0, "y1": 0, "x2": 10, "y2": 10, "text": "Oi", "translated_text": "Hi", "user_edited": True}]
        res = self.ss.save_page_layout("C:/fake/01.jpg", boxes)
        
        self.assertTrue(res["success"])
        
        # Validar asseções fortes (Payload verification no Envelope v2)
        mock_dump.assert_called()
        args, kwargs = mock_dump.call_args
        saved_envelope = args[0]
        self.assertEqual(saved_envelope["version"], 2)
        saved_boxes = saved_envelope["boxes"]
        self.assertEqual(len(saved_boxes), 1)
        self.assertEqual(saved_boxes[0]["translated_text"], "Hi")

    def test_autoSortBoxes(self):
        # Test basic sort response
        boxes = [{"x1": 100, "y1": 50}, {"x1": 10, "y1": 50}]
        res = self.ss.autoSortBoxes("C:/fake/01.jpg", boxes)
        self.assertTrue(res["success"])
        # In RTL sorting (default), higher X comes first
        self.assertEqual(res["boxes"][0]["x1"], 100)
        self.assertEqual(res["boxes"][1]["x1"], 10)

    @patch("os.path.exists", return_value=True)
    @patch("os.listdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_loadStudioData(self, mock_open, mock_listdir, mock_exists):
        mock_listdir.return_value = ["01.jpg", "02.png"]
        mock_open.return_value.read.return_value = '[{"text": "olá", "translated_text": "hello"}]'
        
        res = self.ss.loadStudioData("C:/fake")
        self.assertTrue(res["success"])
        self.assertEqual(len(res["pages"]), 2)
        self.assertTrue(res["pages"][0]["has_ocr"])
        self.assertTrue(res["pages"][0]["has_translated"])

    @patch("os.path.exists", return_value=True)
    @patch("os.makedirs")
    @patch("src.api_services.studio_service.dump_compact_map")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    @patch("os.fsync")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_saveStudioData(self, mock_open, mock_fsync, mock_sync, mock_dump, mock_makedirs, mock_exists):
        studio_data = {
            "pages": [
                {
                    "image": "01.jpg",
                    "boxes": [
                        {"id": 1, "text": "Oi", "translated_text": "Hi", "user_edited": True}
                    ]
                }
            ]
        }
        mock_open.return_value.read.return_value = "[]"
        res = self.ss.saveStudioData("C:/fake", studio_data)
        self.assertTrue(res["success"])
        
        # Validar asseções fortes (Payload verification no Envelope v2)
        mock_dump.assert_called()
        args, kwargs = mock_dump.call_args
        saved_envelope = args[0]
        self.assertEqual(saved_envelope["version"], 2)
        saved_boxes = saved_envelope["boxes"]
        self.assertEqual(len(saved_boxes), 1)
        self.assertEqual(saved_boxes[0].get("translated_text", ""), "Hi")
        self.assertTrue(saved_boxes[0]["user_edited"])
        
        mock_sync.assert_called()

    @patch("os.path.exists", return_value=True)
    @patch("os.makedirs")
    @patch("src.step1_layout_detector.YoloMapeador")
    @patch("PIL.Image.open")
    @patch("src.api_services.studio_service.dump_compact_map")
    def test_detect_page_bubbles(self, mock_dump, mock_img_open, mock_yolo, mock_makedirs, mock_exists):
        mock_yolo_inst = MagicMock()
        mock_yolo.return_value = mock_yolo_inst
        mock_yolo_inst.detect_all_bubbles.return_value = [{"x1": 0, "y1": 0, "x2": 10, "y2": 10}]
        mock_yolo.sort_bubbles_reading_order.side_effect = lambda boxes, **kwargs: boxes
        
        mock_img = MagicMock()
        mock_img.width = 100
        mock_img.height = 100
        mock_img_open.return_value.__enter__.return_value = mock_img
        
        res = self.ss.detect_page_bubbles("C:/fake/01.jpg")
        self.assertTrue(res["success"])
        self.assertEqual(len(res["boxes"]), 1)
        self.assertEqual(res["boxes"][0]["x1"], 0)
        
        mock_dump.assert_called()
        args, kwargs = mock_dump.call_args
        saved_envelope = args[0]
        self.assertEqual(saved_envelope["version"], 2)
        self.assertEqual(len(saved_envelope["boxes"]), 1)
        self.assertEqual(saved_envelope["boxes"][0]["x1"], 0)

    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    def test_clearPageData(self, mock_sync, mock_remove, mock_exists):
        res = self.ss.clearPageData("C:/fake/01.jpg", stages=["ocr", "layout"])
        self.assertTrue(res["success"])
        self.assertTrue(mock_remove.called)

    def test_check_page_backup(self):
        with patch("os.path.exists", return_value=True):
            res = self.ss.check_page_backup("C:/fake/01.jpg")
            self.assertTrue(res["success"])

    @patch("os.path.exists", return_value=True)
    @patch("os.makedirs")
    @patch("src.domain.page_store.dump_compact_map")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data='[{"id": 1, "text": "Snap"}]')
    def test_create_page_backup(self, mock_open, mock_dump, mock_makedirs, mock_exists):
        res = self.ss.create_page_backup("C:/fake/01.jpg")
        self.assertTrue(res["success"])
        mock_dump.assert_called()
        saved_env = mock_dump.call_args[0][0]
        self.assertEqual(saved_env["backup"], [{"id": 1, "text": "Snap"}])

    @patch("os.path.exists", return_value=True)
    @patch("os.makedirs")
    @patch("src.domain.page_store.dump_compact_map")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data='{"version": 2, "boxes": [], "backup": [{"id": 1, "text": "Restored"}]}')
    def test_restore_page_backup(self, mock_open, mock_sync, mock_dump, mock_makedirs, mock_exists):
        res = self.ss.restore_page_backup("C:/fake/01.jpg")
        self.assertTrue(res["success"])
        mock_dump.assert_called()
        saved_env = mock_dump.call_args[0][0]
        self.assertEqual(saved_env["boxes"], [{"id": 1, "text": "Restored"}])

    @patch("os.path.exists", return_value=True)
    @patch("os.makedirs")
    @patch("src.domain.page_store.dump_compact_map")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data='{"version": 2, "boxes": [], "backup": [{"id": 1}]}')
    def test_delete_page_backup(self, mock_open, mock_dump, mock_makedirs, mock_exists):
        res = self.ss.delete_page_backup("C:/fake/01.jpg")
        self.assertTrue(res["success"])
        mock_dump.assert_called()
        saved_env = mock_dump.call_args[0][0]
        self.assertIsNone(saved_env["backup"])


    def test_references_and_global_dictionary_and_scan_edits(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(os.environ, {"VISIONARY_USER_DATA": tmp_dir}):
            # 1. References save & load
            save_ref = self.ss.save_references(tmp_dir, {"characters": [{"id": "1", "name": "Hanabi", "pronoun": "Feminino (Ela)"}]})
            self.assertTrue(save_ref["success"])
            get_ref = self.ss.get_references(tmp_dir)
            self.assertTrue(get_ref["success"])
            self.assertEqual(len(get_ref["data"]["characters"]), 1)
            self.assertEqual(get_ref["data"]["characters"][0]["name"], "Hanabi")

            # 2. Global Dictionary save & load
            save_dict = self.ss.save_global_dictionary(tmp_dir, {"terms": [{"id": "t1", "original": "Kage", "translation": "Sombra", "category": "Termo"}]})
            self.assertTrue(save_dict["success"])
            get_dict = self.ss.get_global_dictionary(tmp_dir)
            self.assertTrue(get_dict["success"])
            self.assertEqual(len(get_dict["data"]["terms"]), 1)
            self.assertEqual(get_dict["data"]["terms"][0]["translation"], "Sombra")

            # 3. Scan user edits & eligible pages
            out_dir = os.path.join(tmp_dir, "output")
            os.makedirs(out_dir, exist_ok=True)
            img_path = os.path.join(tmp_dir, "01.png")
            import cv2
            import numpy as np
            dummy_img = np.full((60, 60, 3), 255, dtype=np.uint8)
            cv2.imwrite(img_path, dummy_img)

            map_path = os.path.join(out_dir, "01_map.json")
            with open(map_path, "w", encoding="utf-8") as f:
                json.dump([
                    {
                        "id": 1,
                        "x1": 10, "y1": 10, "x2": 30, "y2": 30,
                        "bg_type": "white",
                        "text": "Hello",
                        "ai_translated_text": "Olá",
                        "translated_text": "Oi",
                        "user_edited": True
                    }
                ], f)

            scan_res = self.ss.scan_user_edits(tmp_dir)
            self.assertTrue(scan_res["success"])
            self.assertEqual(len(scan_res["diffs"]), 1)
            self.assertEqual(scan_res["diffs"][0]["original"], "Olá")
            self.assertEqual(scan_res["diffs"][0]["suggestion"], "Oi")

    def test_input_validation_and_path_safety(self):
        # 1. Invalid or malformed paths return safe error responses
        for bad_path in [None, "", "   ", "\0bad_path"]:
            res_data = self.ss.get_page_data(bad_path)
            self.assertFalse(res_data["success"])
            self.assertIn("Arquivo não encontrado", res_data["error"])

            res_layout = self.ss.save_page_layout(bad_path, [])
            self.assertFalse(res_layout["success"])
            self.assertIn("Caminho inválido", res_layout["error"])

            res_chk_backup = self.ss.check_page_backup(bad_path)
            self.assertFalse(res_chk_backup["success"])

        # 2. Non-list payloads for boxes are rejected safely
        res_bad_boxes = self.ss.save_page_layout("dummy.png", "not_a_list")
        self.assertFalse(res_bad_boxes["success"])
        self.assertIn("deve ser uma lista", res_bad_boxes["error"])

        # 3. clearPageData safely ignores invalid path entries without crashing
        clear_res = self.ss.clearPageData([None, "", "\0invalid"], ["layout", "ocr"])
        self.assertTrue(clear_res["success"])

        # 4. clearPageData safely handles None or string stages
        self.assertTrue(self.ss.clearPageData([], None)["success"])
        self.assertTrue(self.ss.clearPageData([], "layout")["success"])

    def test_normalize_polygon_boxes_flat_and_nested(self):
        from src.api_services.studio_layout_manager import StudioLayoutManager

        # Flat array [x1, y1, x2, y2, x3, y3]
        boxes_flat = [{"polygon": [10, 20, 50, 20, 50, 80, 10, 80]}]
        norm_flat = StudioLayoutManager.normalize_polygon_boxes(boxes_flat)
        self.assertEqual(norm_flat[0]["x1"], 10)
        self.assertEqual(norm_flat[0]["y1"], 20)
        self.assertEqual(norm_flat[0]["x2"], 50)
        self.assertEqual(norm_flat[0]["y2"], 80)

        # Nested points [[x1, y1], [x2, y2], ...]
        boxes_nested = [{"polygon": [[5, 15], [60, 15], [60, 95], [5, 95]]}]
        norm_nested = StudioLayoutManager.normalize_polygon_boxes(boxes_nested)
        self.assertEqual(norm_nested[0]["x1"], 5)
        self.assertEqual(norm_nested[0]["y1"], 15)
        self.assertEqual(norm_nested[0]["x2"], 60)
        self.assertEqual(norm_nested[0]["y2"], 95)



