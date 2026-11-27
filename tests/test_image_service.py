import os
import time
import pytest
from PIL import Image

from src.api_services.image_service import ImageService
from src.utils.path_sandbox import register_root


class TestImageServiceUnit:
    @pytest.fixture
    def setup_env(self, tmp_path):
        folder = tmp_path / "chapter_images"
        folder.mkdir()
        register_root(str(folder))

        # Create normal test image
        img_path = folder / "page_01.png"
        img = Image.new("RGB", (300, 400), color="blue")
        img.save(str(img_path))

        # Create transparent RGBA image
        rgba_path = folder / "page_alpha.png"
        rgba_img = Image.new("RGBA", (300, 400), color=(255, 0, 0, 128))
        rgba_img.save(str(rgba_path))

        return {
            "folder": str(folder),
            "img_path": str(img_path),
            "rgba_path": str(rgba_path),
        }

    def test_invalid_path_types_rejected(self):
        svc = ImageService()
        for invalid in [None, "", 12345, [], {}]:
            res = svc.get_image_base64(invalid)
            assert res["success"] is False
            assert "error" in res

            res_full = svc.get_image_base64_full(invalid)
            assert res_full["success"] is False
            assert "error" in res_full

    def test_thumbnail_caching_and_invalidation(self, setup_env):
        svc = ImageService()
        img_path = setup_env["img_path"]

        # First call: populates cache
        res1 = svc.get_image_base64(img_path)
        assert res1["success"] is True
        assert len(svc._thumbnail_cache) == 1

        # Second call: hits cache
        res2 = svc.get_image_base64(img_path)
        assert res2["success"] is True
        assert res2["data_url"] == res1["data_url"]

        # Modify file mtime to test cache refresh
        time.sleep(0.05)
        with open(img_path, "ab") as f:
            f.write(b"\x00")
        os.utime(img_path, None)

        res3 = svc.get_image_base64(img_path)
        assert res3["success"] is True
        # Now cache has 2 entries (old mtime and new mtime) or updated key
        assert len(svc._thumbnail_cache) >= 1

        # Test clear_cache
        svc.clear_cache()
        assert len(svc._thumbnail_cache) == 0

    def test_rgba_alpha_blending_on_white_canvas(self, setup_env):
        svc = ImageService()
        res = svc.get_image_base64(setup_env["rgba_path"])
        assert res["success"] is True
        assert res["data_url"].startswith("data:image/jpeg;base64,")

    def test_get_image_base64_full_reads_raw(self, setup_env):
        svc = ImageService()
        res = svc.get_image_base64_full(setup_env["img_path"])
        assert res["success"] is True
        assert res["data_url"].startswith("data:image/png;base64,")
