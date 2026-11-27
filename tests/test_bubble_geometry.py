import unittest
import numpy as np
from PIL import Image

from src.geometry.bubble_geometry import (
    _iou,
    _merge_bubbles,
    _merge_panels,
    _detect_panels_opencv,
    _refine_bubble_box,
    _validate_bubble_morphology,
    is_clean_white_bubble,
    is_sfx_morphology,
    extract_bubble_polygons,
)


class TestBubbleGeometry(unittest.TestCase):
    def test_iou_exact_and_zero(self):
        boxA = [10, 10, 50, 50]
        boxB = [10, 10, 50, 50]
        self.assertAlmostEqual(_iou(boxA, boxB), 1.0)

        boxC = [100, 100, 200, 200]
        self.assertEqual(_iou(boxA, boxC), 0.0)

    def test_merge_bubbles_and_labels(self):
        bubbles = [
            {"x1": 0, "y1": 0, "x2": 100, "y2": 100, "confidence": 0.8, "label": "text_free", "bg_type": "sfx"},
            {"x1": 5, "y1": 5, "x2": 95, "y2": 95, "confidence": 0.95, "label": "text_bubble", "bg_type": "white"},
            {"x1": 300, "y1": 300, "x2": 400, "y2": 400, "confidence": 0.9, "label": "text_bubble", "bg_type": "white"},
        ]
        merged = _merge_bubbles(bubbles, iou_threshold=0.1, containment_threshold=0.4)
        self.assertEqual(len(merged), 2)
        m0 = [b for b in merged if b["x1"] == 0][0]
        self.assertEqual(m0["x2"], 100)
        self.assertEqual(m0["y2"], 100)
        self.assertEqual(m0["label"], "text_bubble")
        self.assertTrue(m0["is_bubble"])
        self.assertFalse(m0["is_sfx"])

    def test_merge_bubbles_multilobe_peanut(self):
        """Valida fusão de lóbulos multilobados empilhados com gap <= 6px."""
        bubbles = [
            {"x1": 100, "y1": 50, "x2": 200, "y2": 100, "confidence": 0.9, "label": "text_bubble", "bg_type": "white"},
            {"x1": 98, "y1": 104, "x2": 202, "y2": 160, "confidence": 0.88, "label": "text_bubble", "bg_type": "white"},
        ]
        merged = _merge_bubbles(bubbles, iou_threshold=0.1, containment_threshold=0.4)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["x1"], 98)
        self.assertEqual(merged[0]["y1"], 50)
        self.assertEqual(merged[0]["x2"], 202)
        self.assertEqual(merged[0]["y2"], 160)

    def test_merge_bubbles_rejects_wavy_border_stack_and_morphology(self):
        """Valida que dois balões empilhados com borda ondulada não se fundem e valida reticências/bordas."""
        img_arr = np.full((300, 200, 3), 255, dtype=np.uint8)
        for x in range(20, 180):
            wy = int(148 + 10 * np.sin((x - 20) * 0.08))
            img_arr[wy - 2 : wy + 3, x] = 0
        img = Image.fromarray(img_arr)
        bubbles = [
            {"x1": 20, "y1": 20, "x2": 180, "y2": 150, "confidence": 0.95, "label": "text_bubble", "bg_type": "white"},
            {"x1": 20, "y1": 148, "x2": 180, "y2": 280, "confidence": 0.94, "label": "text_bubble", "bg_type": "white"},
        ]
        merged = _merge_bubbles(bubbles, iou_threshold=0.15, containment_threshold=0.40, image=img)
        self.assertEqual(len(merged), 2)

        ellipsis_crop = np.full((160, 90), 255, dtype=np.uint8)
        ellipsis_crop[72:77, 42:47] = 0
        ellipsis_crop[82:87, 42:47] = 0
        ellipsis_crop[92:97, 42:47] = 0
        self.assertTrue(_validate_bubble_morphology(ellipsis_crop, "text_bubble"))

        edge_only_crop = np.full((100, 200), 255, dtype=np.uint8)
        edge_only_crop[5:12, 10:18] = 0
        edge_only_crop[5:12, 22:30] = 0
        self.assertFalse(_validate_bubble_morphology(edge_only_crop, "text_bubble"))

    def test_merge_panels(self):
        panels = [
            {"box": [0, 0, 100, 100], "area": 10000, "conf": 0.9},
            {"box": [10, 10, 90, 90], "area": 6400, "conf": 0.8},
        ]
        merged = _merge_panels(panels, iou_threshold=0.15, containment_threshold=0.5)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["box"], [0, 0, 100, 100])

    def test_refine_bubble_box_bounds(self):
        img = Image.new("RGB", (500, 600), color="white")
        rx1, ry1, rx2, ry2 = _refine_bubble_box(img, -20, -10, 520, 650, "text_bubble", pad=0)
        self.assertEqual((rx1, ry1, rx2, ry2), (0, 0, 500, 600))

    def test_validate_bubble_morphology(self):
        # Empty image should fail
        empty_crop = np.zeros((10, 10), dtype=np.uint8)
        self.assertFalse(_validate_bubble_morphology(empty_crop, "text_bubble"))

        # Small image below 14x14 should fail
        small_crop = np.full((12, 12), 255, dtype=np.uint8)
        self.assertFalse(_validate_bubble_morphology(small_crop, "text_bubble"))

    def test_clean_white_bubble(self):
        crop = np.full((100, 100), 255, dtype=np.uint8)
        crop[30:50, 30:50] = 0  # text strokes
        self.assertTrue(is_clean_white_bubble(crop))

        blank = np.full((100, 100), 255, dtype=np.uint8)
        self.assertFalse(is_clean_white_bubble(blank))

    def test_extract_bubble_polygons(self):
        img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        bubbles = [
            {"x1": 10, "y1": 10, "x2": 80, "y2": 80, "is_bubble": True}
        ]
        res = extract_bubble_polygons(img, bubbles)
        self.assertIn("polygon", res[0])
        self.assertGreaterEqual(len(res[0]["polygon"]), 4)


    def test_is_sfx_morphology_protection_and_detection(self):
        # 1. Balão limpo branco NUNCA é SFX
        clean_bubble = np.full((100, 100), 255, dtype=np.uint8)
        clean_bubble[30:50, 30:50] = 0
        self.assertFalse(is_sfx_morphology(clean_bubble, "text_bubble"))
        self.assertFalse(is_sfx_morphology(clean_bubble, "text_free"))

        # 2. Texto livre sobre arte ruidosa sem fundo branco é confirmado como SFX
        noisy_art = np.random.randint(40, 180, (100, 100), dtype=np.uint8)
        self.assertTrue(is_sfx_morphology(noisy_art, "text_free"))

    def test_reading_order_sfx_dissociation(self):
        from src.batch_pipeline.reading_order import sort_bubbles_reading_order
        panels = [{"box": [0, 0, 1000, 1000], "polygon": [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]}]
        bubbles = [
            {"x1": 800, "y1": 100, "x2": 900, "y2": 200, "label": "text_bubble", "is_bubble": True, "is_sfx": False},
            {"x1": 500, "y1": 300, "x2": 600, "y2": 400, "label": "text_free", "is_bubble": False, "is_sfx": True, "bg_type": "sfx"},
            {"x1": 200, "y1": 500, "x2": 300, "y2": 600, "label": "text_bubble", "is_bubble": True, "is_sfx": False},
        ]
        res = sort_bubbles_reading_order(bubbles, panels=panels)
        self.assertEqual(len(res), 3)

        # Diálogos devem ter ordem sequencial contínua 1, 2
        dialogues = [b for b in res if not b.get("is_sfx")]
        self.assertEqual(len(dialogues), 2)
        self.assertEqual(dialogues[0]["order"], 1)
        self.assertEqual(dialogues[1]["order"], 2)

        # SFX deve estar dissociado da ordem de fala (order = None)
        sfx_items = [b for b in res if b.get("is_sfx")]
        self.assertEqual(len(sfx_items), 1)
        self.assertIsNone(sfx_items[0]["order"])
        self.assertTrue(sfx_items[0]["is_sfx"])
        self.assertEqual(sfx_items[0]["panel_id"], 1)

    def test_reading_order_ltr_vs_rtl(self):
        from src.batch_pipeline.reading_order import sort_bubbles_reading_order, recursive_xy_cut

        # 1. Test panel sorting in LTR vs RTL
        p_left = {"id": "left", "box": [0, 0, 400, 500]}
        p_right = {"id": "right", "box": [600, 0, 1000, 500]}

        panels_rtl = recursive_xy_cut([p_left, p_right], direction="rtl")
        self.assertEqual([p["id"] for p in panels_rtl], ["right", "left"])

        panels_ltr = recursive_xy_cut([p_left, p_right], direction="ltr")
        self.assertEqual([p["id"] for p in panels_ltr], ["left", "right"])

        # 2. Test bubble sorting in LTR vs RTL
        b_left = {"x1": 100, "y1": 100, "x2": 200, "y2": 150, "label": "text_bubble", "is_bubble": True}
        b_right = {"x1": 800, "y1": 100, "x2": 900, "y2": 150, "label": "text_bubble", "is_bubble": True}

        res_rtl = sort_bubbles_reading_order([b_left, b_right], panels=None, direction="rtl")
        self.assertEqual(res_rtl[0]["x1"], 800)  # Right bubble first in Manga (RTL)
        self.assertEqual(res_rtl[1]["x1"], 100)

        res_ltr = sort_bubbles_reading_order([b_left, b_right], panels=None, direction="ltr")
        self.assertEqual(res_ltr[0]["x1"], 100)  # Left bubble first in Western Comics (LTR)
        self.assertEqual(res_ltr[1]["x1"], 800)


if __name__ == "__main__":
    unittest.main()
