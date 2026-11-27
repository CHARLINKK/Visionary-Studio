import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from src.domain.page_store import PageStore


class TestPageStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_page_store_")
        self.output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.img_path = os.path.join(self.temp_dir, "001.png")
        with open(self.img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        PageStore.invalidate_cache()

    def tearDown(self):
        PageStore.invalidate_cache()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_v2_envelope_consolidates_boxes_panels_and_backup(self):
        """Valida que boxes, panels e backup residem em um único 001_map.json v2."""
        boxes = [
            {
                "id": 1,
                "x1": 10,
                "y1": 20,
                "x2": 100,
                "y2": 80,
                "polygon": [[10, 20], [100, 20], [100, 80], [10, 80]],
                "text": "Hello",
                "translated_text": "Olá",
            }
        ]
        panels = [{"box": [0, 0, 500, 500]}]

        PageStore.save_page_record(self.img_path, boxes=boxes, panels=panels)
        self.assertTrue(PageStore.create_backup(self.img_path))

        map_path = os.path.join(self.output_dir, "001_map.json")
        self.assertTrue(os.path.isfile(map_path))
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "001_panels.json")))
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "001_map_backup.json")))

        with open(map_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        self.assertIn('"polygon": [[10, 20], [100, 20], [100, 80], [10, 80]]', raw_text)

        raw = json.loads(raw_text)
        self.assertEqual(raw["version"], 2)
        self.assertEqual(len(raw["boxes"]), 1)
        self.assertEqual(raw["panels"], panels)
        self.assertNotIn("strokes", raw)
        self.assertEqual(len(raw["backup"]), 1)
        self.assertEqual(raw["backup"][0]["text"], "Hello")

    def test_legacy_v1_and_satellites_auto_migration_and_cleanup(self):
        """Valida que arquivos legados v1 (lista) e satélites (_panels, _map_backup) são absorvidos e qualquer satélite legado (incluindo _strokes) é limpo."""
        map_path = os.path.join(self.output_dir, "001_map.json")
        panels_path = os.path.join(self.output_dir, "001_panels.json")
        strokes_path = os.path.join(self.output_dir, "001_strokes.json")
        backup_path = os.path.join(self.output_dir, "001_map_backup.json")

        with open(map_path, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "text": "Legacy V1", "translated_text": "Legado V1"}], f)
        with open(panels_path, "w", encoding="utf-8") as f:
            json.dump([{"box": [10, 10, 200, 200]}], f)
        with open(strokes_path, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "points": [5.0, 6.0], "size": 16, "color": "#000000", "mode": "erase"}], f)
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "text": "Original Snapshot"}], f)

        record = PageStore.load_page_record(self.img_path)
        self.assertEqual(record["version"], 2)
        self.assertEqual(record["boxes"][0]["text"], "Legacy V1")
        self.assertEqual(len(record["panels"]), 1)
        self.assertNotIn("strokes", record)
        self.assertEqual(record["backup"][0]["text"], "Original Snapshot")

        # Ao salvar, os satélites legados devem ser consolidados no _map.json e removidos do disco
        PageStore.save_boxes(self.img_path, record["boxes"])
        self.assertTrue(os.path.isfile(map_path))
        self.assertFalse(os.path.exists(panels_path))
        self.assertFalse(os.path.exists(strokes_path))
        self.assertFalse(os.path.exists(backup_path))

        with open(map_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["version"], 2)
        self.assertEqual(len(saved["panels"]), 1)
        self.assertNotIn("strokes", saved)
        self.assertEqual(saved["backup"][0]["text"], "Original Snapshot")

    def test_mtime_ram_cache_hit_and_invalidation(self):
        """Valida que get_page_summary usa o cache em RAM sem reexecutar json.load quando mtime/size não mudam."""
        PageStore.save_boxes(
            self.img_path,
            [{"id": 1, "text": "Cached OCR", "translated_text": "Cached PTBR"}],
        )

        # Primeira chamada já está em cache após save_boxes; segunda chamada não deve chamar json.load
        with patch("json.load", side_effect=AssertionError("json.load should not be called on cache hit")):
            summary = PageStore.get_page_summary(self.img_path)

        self.assertTrue(summary["has_layout"])
        self.assertTrue(summary["has_ocr"])
        self.assertTrue(summary["has_translation"])
        self.assertEqual(summary["block_count"], 1)
        self.assertFalse(summary["has_backup"])

        # Modificação externa no arquivo em disco altera size/mtime e invalida automaticamente a entrada
        map_path = os.path.join(self.output_dir, "001_map.json")
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "boxes": [], "panels": [], "backup": [{"id": 99}]}, f)

        summary_after = PageStore.get_page_summary(self.img_path)
        self.assertEqual(summary_after["block_count"], 0)
        self.assertTrue(summary_after["has_ocr"])
        self.assertTrue(summary_after["has_translation"])
        self.assertTrue(summary_after["has_backup"])

    def test_v1_list_of_bubbles_does_not_duplicate_into_panels(self):
        """Valida que balões de fala v1 ([{label: text_bubble, ...}]) NUNCA são duplicados em panels."""
        v1_bubbles = [
            {
                "id": 1,
                "label": "text_bubble",
                "is_bubble": True,
                "text": "Hello world",
                "translated_text": "Olá mundo",
                "ocr_raw": "Hello world"
            }
        ]
        record = PageStore.normalize_record(v1_bubbles)
        self.assertEqual(len(record["boxes"]), 1)
        self.assertEqual(record["boxes"][0]["text"], "Hello world")
        self.assertEqual(record["panels"], [], "Panels must NOT contain duplicated text bubbles!")

        # Valida que se um v2 já vier com balões indevidamente em panels, extract_panels os expurga
        corrupted_v2 = {
            "version": 2,
            "boxes": v1_bubbles,
            "panels": v1_bubbles,
            "backup": None
        }
        cleansed = PageStore.normalize_record(corrupted_v2)
        self.assertEqual(cleansed["panels"], [])

    def test_record_cache_o1_hit_defensive_copy_and_lru_bound(self):
        """Valida que load_page_record/load_boxes servem em O(1) da RAM com cópia defensiva e respeitam MAX_CACHE_ENTRIES."""
        PageStore.save_boxes(
            self.img_path,
            [{"id": 1, "text": "Immutable Cache", "translated_text": "Cache Imutável"}],
        )

        with patch("src.domain.page_store.resilient_read_json", side_effect=AssertionError("disk read must not occur on cache hit")):
            boxes_first = PageStore.load_boxes(self.img_path)
            self.assertEqual(boxes_first[0]["translated_text"], "Cache Imutável")
            # Mutar o dicionário retornado NÃO pode corromper o cache interno
            boxes_first[0]["translated_text"] = "Mutado pelo chamador"

            boxes_second = PageStore.load_boxes(self.img_path)
            self.assertEqual(boxes_second[0]["translated_text"], "Cache Imutável")

        # Verifica limite máximo de entradas (evita vazamento de memória em sessões longas)
        orig_max = PageStore.MAX_CACHE_ENTRIES
        try:
            PageStore.MAX_CACHE_ENTRIES = 3
            PageStore.invalidate_cache()
            for idx in range(5):
                p_img = os.path.join(self.temp_dir, f"lru_{idx:03d}.png")
                with open(p_img, "wb") as f:
                    f.write(b"dummy")
                PageStore.save_boxes(p_img, [{"id": idx, "text": f"T{idx}"}])
            self.assertLessEqual(len(PageStore._record_cache), 3)
            self.assertLessEqual(len(PageStore._summary_cache), 3)
        finally:
            PageStore.MAX_CACHE_ENTRIES = orig_max


if __name__ == "__main__":
    unittest.main()
