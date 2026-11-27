import os
import json
import tempfile
import shutil
import pytest
from src.api_services.studio_service import StudioService
from src.utils.txt_sync import sync_chapter_txt

class TestLayer6StudioAudit:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.test_dir = tempfile.mkdtemp(prefix="vis_layer6_test_")
        self.studio = StudioService(api_bridge=None, default_path=self.test_dir)
        yield
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_page_layout_coordinate_sanitization_and_group_id(self):
        """Valida que save_page_layout trata coordenadas nulas ou float sem falhar e preserva group_id."""
        img_path = os.path.join(self.test_dir, "page_002.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        boxes = [
            {
                "id": 1,
                "x1": None,          # Deve virar 0
                "y1": "15.7",        # Deve virar 16
                "x2": 100.4,         # Deve virar 100
                "y2": 150,
                "text": "Hello world",
                "translated": "Olá mundo",
                "group_id": "group_alpha"
            },
            {
                "id": 2,
                "x1": 120,
                "y1": 160,
                "x2": 200,
                "y2": 250,
                "text": "Part two",
                "translated": "Parte dois",
                "group_id": "group_alpha"
            }
        ]

        res = self.studio.save_page_layout(img_path, boxes)
        assert res["success"] is True

        map_file = os.path.join(self.test_dir, "output", "page_002_map.json")
        assert os.path.exists(map_file)
        with open(map_file, "r", encoding="utf-8") as f:
            envelope = json.load(f)

        assert envelope["version"] == 2
        saved = envelope["boxes"]
        assert len(saved) == 2
        assert saved[0]["x1"] == 0
        assert saved[0]["y1"] == 16
        assert saved[0]["x2"] == 100
        assert saved[0]["group_id"] == "group_alpha"
        assert saved[1]["group_id"] == "group_alpha"
        assert saved[0]["order"] == 1
        assert saved[1]["order"] == 2

    def test_autosort_boxes_resilience(self):
        """Valida que autoSortBoxes tolera polígonos imperfeitos e coordenadas ausentes sem erro."""
        img_path = os.path.join(self.test_dir, "page_003.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        boxes = [
            {
                "id": 1,
                "x1": 50, "y1": 50, "x2": 100, "y2": 100,
                "polygon": [[50, 50], [100, 50], [100, 100], [50, 100]]
            },
            {
                "id": 2,
                "x1": None, "y1": None, "x2": None, "y2": None,
                "polygon": [[None, None], [10, 20]]
            },
            {
                "id": 3,
                "x1": 200, "y1": 50, "x2": 250, "y2": 100,
                "polygon": []
            }
        ]

        res = self.studio.autoSortBoxes(img_path, boxes)
        assert res["success"] is True
        sorted_boxes = res["boxes"]
        assert len(sorted_boxes) == 3
        orders = [b["order"] for b in sorted_boxes]
        assert orders == [1, 2, 3]

    def test_clear_page_data_continuous_txt_sync(self):
        """Valida que clearPageData re-sincroniza o arquivo de roteiro .txt imediatamente."""
        img_path = os.path.join(self.test_dir, "001.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        out_dir = os.path.join(self.test_dir, "output")
        os.makedirs(out_dir, exist_ok=True)

        map_data = [
            {
                "id": 1,
                "x1": 10, "y1": 10, "x2": 50, "y2": 50,
                "text": "Original text here",
                "translated_text": "Texto traduzido inicial",
                "order": 1
            }
        ]
        map_path = os.path.join(out_dir, "001_map.json")
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(map_data, f)

        sync_res = sync_chapter_txt(self.test_dir)
        assert sync_res["success"] is True
        txt_path = os.path.join(self.test_dir, f"{os.path.basename(self.test_dir)}.txt")
        assert os.path.exists(txt_path)
        with open(txt_path, "r", encoding="utf-8") as f:
            txt_content = f.read()
        assert "Texto traduzido inicial" in txt_content

        res = self.studio.clearPageData([img_path], ["translate"])
        assert res["success"] is True

        with open(txt_path, "r", encoding="utf-8") as f:
            updated_txt = f.read()
        assert "Texto traduzido inicial" not in updated_txt
        assert "[PENDENTE]" in updated_txt
        assert "Original text here" in updated_txt
