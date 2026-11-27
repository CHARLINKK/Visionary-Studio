import os
import unittest
from unittest.mock import patch, MagicMock
from src.api_services.studio_layout_manager import StudioLayoutManager


class TestStudioLayoutManager(unittest.TestCase):
    def setUp(self):
        self.mgr = StudioLayoutManager()

    def test_safe_coord(self):
        self.assertEqual(StudioLayoutManager.safe_coord(10), 10)
        self.assertEqual(StudioLayoutManager.safe_coord("15.7"), 16)
        self.assertEqual(StudioLayoutManager.safe_coord(None, default=42), 42)
        self.assertEqual(StudioLayoutManager.safe_coord("invalid", default=-1), -1)

    def test_normalize_polygon_boxes(self):
        boxes = [
            {
                "id": 1,
                "polygon": [[10, 20], [50, 20], [50, 80], [10, 80]]
            },
            {
                "id": 2,
                "x1": 100, "y1": 100, "x2": 200, "y2": 200
            }
        ]
        norm = StudioLayoutManager.normalize_polygon_boxes(boxes)
        self.assertEqual(len(norm), 2)
        # Box 1 polygon bounding box
        self.assertEqual(norm[0]["x1"], 10)
        self.assertEqual(norm[0]["y1"], 20)
        self.assertEqual(norm[0]["x2"], 50)
        self.assertEqual(norm[0]["y2"], 80)
        # Box 2 preserved
        self.assertEqual(norm[1]["x1"], 100)
        self.assertEqual(norm[1]["y1"], 100)

    def test_auto_sort_boxes_rtl(self):
        boxes = [
            {"id": "left", "x1": 10, "y1": 50, "x2": 40, "y2": 90},
            {"id": "right", "x1": 200, "y1": 50, "x2": 250, "y2": 90}
        ]
        res = self.mgr.auto_sort_boxes(
            "C:/fake/01.jpg",
            boxes,
            resolve_target_fn=lambda p: p
        )
        self.assertTrue(res["success"])
        # Manga reading order (RTL): right comes before left
        self.assertEqual(res["boxes"][0]["id"], "right")
        self.assertEqual(res["boxes"][0]["order"], 1)
        self.assertEqual(res["boxes"][1]["id"], "left")
        self.assertEqual(res["boxes"][1]["order"], 2)
        self.assertIn("panels", res)

    def test_auto_sort_boxes_empty(self):
        res = self.mgr.auto_sort_boxes(
            "C:/fake/01.jpg",
            [],
            resolve_target_fn=lambda p: p
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["boxes"], [])

    def test_detect_page_bubbles_not_found(self):
        res = self.mgr.detect_page_bubbles(
            "C:/nonexistent/fake_image.png",
            white_only=False,
            resolve_target_fn=lambda p: p
        )
        self.assertFalse(res["success"])
        self.assertIn("não encontrado", res["error"])

    @patch("src.model_engines.yolo_layout_engine.YoloMapeador")
    @patch("src.domain.page_store.PageStore.save_page_record")
    @patch("src.domain.page_store.PageStore.load_boxes", return_value=[])
    @patch("PIL.Image.open")
    @patch("os.path.exists", return_value=True)
    def test_detect_page_bubbles_with_panels(self, mock_exists, mock_img_open, mock_load, mock_save_rec, mock_yolo):
        mock_mapper = MagicMock()
        mock_yolo.return_value = mock_mapper
        mock_mapper.detect_all_bubbles.return_value = [
            {"id": 1, "x1": 10, "y1": 20, "x2": 50, "y2": 60, "label": "text_bubble", "confidence": 0.9}
        ]
        mock_mapper.detect_panels_and_sort.return_value = (
            [{"id": 1, "box": [0, 0, 100, 100], "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]}],
            [{"id": 1, "x1": 10, "y1": 20, "x2": 50, "y2": 60}]
        )

        res = self.mgr.detect_page_bubbles(
            "C:/fake/page.jpg",
            white_only=False,
            resolve_target_fn=lambda p: p
        )
        self.assertTrue(res["success"])
        self.assertEqual(len(res["boxes"]), 1)
        self.assertEqual(len(res["panels"]), 1)
        self.assertEqual(len(res["panels"][0]["polygon"]), 4)
        mock_save_rec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
