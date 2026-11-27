import os
import tempfile
from src.api_services.fs_service import FileSystemService

def test_fs_service_natural_sort_and_chapter_status():
    fs = FileSystemService()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create folders in non-alphabetical natural order
        ch1 = os.path.join(temp_dir, "Capítulo 1")
        ch2 = os.path.join(temp_dir, "Capítulo 2")
        ch10 = os.path.join(temp_dir, "Capítulo 10")
        notes = os.path.join(temp_dir, "Anotações")
        
        os.makedirs(ch1)
        os.makedirs(ch2)
        os.makedirs(ch10)
        os.makedirs(notes)

        # Ch1: RAW images (status yellow)
        for i in range(3):
            with open(os.path.join(ch1, f"page_{i}.jpg"), "wb") as f:
                f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        # Ch2: RAW images + output folder with json (status green)
        for i in range(2):
            with open(os.path.join(ch2, f"page_{i}.png"), "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        out_dir = os.path.join(ch2, "output")
        os.makedirs(out_dir)
        with open(os.path.join(out_dir, "page_0_map.json"), "w", encoding="utf-8") as f:
            f.write('[{"translated": "Texto traduzido"}]')
        with open(os.path.join(out_dir, "page_1_map.json"), "w", encoding="utf-8") as f:
            f.write('[{"translated": "Texto traduzido 2"}]')

        # Root image file (should be sorted after directories in file_items)
        with open(os.path.join(temp_dir, "cover.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        # Auxiliary non-image files (_glossary_global.txt, global_dictionary.json, README.txt) must NOT appear
        with open(os.path.join(temp_dir, "README.txt"), "w") as f:
            f.write("Hello")
        with open(os.path.join(temp_dir, "_glossary_global.txt"), "w") as f:
            f.write("Glossario")
        with open(os.path.join(temp_dir, "global_dictionary.json"), "w") as f:
            f.write("{}")

        res = fs.list_directory(temp_dir)
        items = res.get("items", [])

        # Check grouping: first 4 items must be dirs, last item must be image file
        dir_names = [item["name"] for item in items if item.get("isDir") and not item.get("isBack")]
        file_names = [item["name"] for item in items if not item.get("isDir")]

        assert file_names == ["cover.jpg"]
        assert "README.txt" not in [item["name"] for item in items]
        assert "_glossary_global.txt" not in [item["name"] for item in items]
        assert "global_dictionary.json" not in [item["name"] for item in items]
        
        # Check natural sort order: Capítulo 1, Capítulo 2, Capítulo 10 (not Capítulo 1, 10, 2)
        assert dir_names == ["Anotações", "Capítulo 1", "Capítulo 2", "Capítulo 10"]

        # Check item attributes
        ch1_meta = next(i for i in items if i["name"] == "Capítulo 1")
        assert ch1_meta["isChapter"] is True
        assert ch1_meta["imgCount"] == 3
        assert ch1_meta["status"] == "yellow"

        ch2_meta = next(i for i in items if i["name"] == "Capítulo 2")
        assert ch2_meta["isChapter"] is True
        assert ch2_meta["imgCount"] == 2
        assert ch2_meta["status"] == "green"

        notes_meta = next(i for i in items if i["name"] == "Anotações")
        assert notes_meta["isChapter"] is False
        assert notes_meta["imgCount"] == 0
        assert notes_meta["status"] == "blue"

def test_clearing_chapter_data_reverts_status_to_yellow():
    fs = FileSystemService()
    with tempfile.TemporaryDirectory() as temp_dir:
        ch = os.path.join(temp_dir, "Capítulo 1")
        os.makedirs(ch)
        with open(os.path.join(ch, "p1.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 10)
        out_dir = os.path.join(ch, "output")
        os.makedirs(out_dir)
        map_p = os.path.join(out_dir, "p1_map.json")
        with open(map_p, "w", encoding="utf-8") as f:
            f.write('[{"translated": "Texto"}]')

        # Initially green
        items = fs.list_directory(temp_dir)["items"]
        ch_meta = next(i for i in items if i["name"] == "Capítulo 1")
        assert ch_meta["status"] == "green"

        # Case 1: translation cleared (no translated keys remaining)
        with open(map_p, "w", encoding="utf-8") as f:
            f.write('[{"box": [0,0,10,10]}]')
        items = fs.list_directory(temp_dir)["items"]
        ch_meta = next(i for i in items if i["name"] == "Capítulo 1")
        assert ch_meta["status"] == "progress"

        # Case 2: only backup json left
        os.remove(map_p)
        with open(os.path.join(out_dir, "p1_map.bak.json"), "w") as f:
            f.write('[{"translated": "Texto"}]')
        items = fs.list_directory(temp_dir)["items"]
        ch_meta = next(i for i in items if i["name"] == "Capítulo 1")
        assert ch_meta["status"] == "yellow"


def test_fs_service_recognizes_modern_and_raw_image_formats():
    """Valida que formatos modernos (.avif, .bmp, .tiff) são reconhecidos no explorador de capítulos."""
    fs = FileSystemService()
    with tempfile.TemporaryDirectory() as temp_dir:
        ch = os.path.join(temp_dir, "Capítulo Moderno")
        os.makedirs(ch)
        for ext in [".avif", ".bmp", ".tiff", ".webp"]:
            with open(os.path.join(ch, f"page{ext}"), "wb") as f:
                f.write(b"\x00" * 32)
        
        items = fs.list_directory(temp_dir)["items"]
        ch_meta = next(i for i in items if i["name"] == "Capítulo Moderno")
        assert ch_meta["isChapter"] is True
        assert ch_meta["imgCount"] == 4


def test_image_service_rgba_thumbnail_generation():
    """Valida que imagens com canal alfa (RGBA) geram thumbnail JPEG sem lançar OSError."""
    from src.api_services.image_service import ImageService
    from src.utils.path_sandbox import register_root
    from PIL import Image
    import io

    with tempfile.TemporaryDirectory() as temp_dir:
        assert register_root(temp_dir) is True
        rgba_path = os.path.join(temp_dir, "transparent.png")
        img = Image.new("RGBA", (200, 200), (255, 0, 0, 128))
        img.save(rgba_path, "PNG")

        svc = ImageService()
        res = svc.get_image_base64(rgba_path)
        assert res["success"] is True
        assert res["data_url"].startswith("data:image/jpeg;base64,")
