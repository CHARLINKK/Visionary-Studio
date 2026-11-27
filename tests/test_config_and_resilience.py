import os
import sys
import unittest
import tempfile
import json
import shutil
from unittest.mock import patch

from src.config import Config

class TestConfigAndResilience(unittest.TestCase):
    def test_config_full_ui_defaults(self):
        """Valida que todos os valores de interface, som e ergonomia possuem defaults canônicos definidos."""
        expected_keys = [
            "ollama_url", "flask_port", "theme", "accent", "sidebarWidth",
            "rememberZoom", "last_opened_folder", "baseFolder", "pipeline_steps",
            "translation_tone", "selected_models", "systemNotifications",
            "notifyOnlyInBackground", "debugPanelMaps", "autoUpdate", "enableVLM",
            "uiDensity", "soundFeedback", "soundStyle", "soundVolume",
            "reduceMotion", "acrylicBlur", "fontFamily", "uiScale",
            "showPagePills", "showStatusDots"
        ]
        defaults = Config._defaults
        for k in expected_keys:
            self.assertIn(k, defaults, f"Chave canônica ausente em Config._defaults: {k}")

        self.assertEqual(defaults["uiDensity"], "comfortable")
        self.assertEqual(defaults["soundStyle"], "harmonic")
        self.assertEqual(defaults["soundVolume"], 80)
        self.assertTrue(defaults["soundFeedback"])
        self.assertTrue(defaults["systemNotifications"])
        self.assertTrue(defaults["notifyOnlyInBackground"])
        self.assertTrue(defaults["acrylicBlur"])
        self.assertFalse(defaults["reduceMotion"])

    def test_config_atomic_save_and_no_tmp_leak(self):
        """Valida que a gravação atômica salva os dados e remove qualquer arquivo temporário .tmp."""
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(os.environ, {"VISIONARY_USER_DATA": tmp_dir}):
            cfg_path = Config.get_config_path()
            tmp_path = f"{cfg_path}.tmp"

            Config.update({"test_atomic_key": "verified_safe"})
            self.assertEqual(Config.get("test_atomic_key"), "verified_safe")
            self.assertFalse(os.path.exists(tmp_path), "Arquivo .tmp não deve persistir após gravação atômica")

    def test_truncated_image_loading_resilience(self):
        """Valida que ImageFile.LOAD_TRUNCATED_IMAGES está ativo e decodifica fluxos com EOI ausente sem crash."""
        from PIL import Image, ImageFile
        import io

        self.assertTrue(ImageFile.LOAD_TRUNCATED_IMAGES)

        # Cria uma imagem JPEG válida
        img = Image.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()

        # Remove os últimos 15 bytes (incluindo o marcador de fim de arquivo JPEG \xFF\xD9)
        # Com LOAD_TRUNCATED_IMAGES = False, isso lançaria OSError: image file is truncated
        truncated_bytes = raw_bytes[:-15]
        
        trunc_buf = io.BytesIO(truncated_bytes)
        try:
            with Image.open(trunc_buf) as loaded_img:
                loaded_img.load()
        except OSError as e:
            self.fail(f"Pillow falhou ao carregar imagem com EOF truncado: {e}")

    def test_config_save_failure_does_not_corrupt_cache(self):
        """Valida que falha na gravação atômica não atualiza cache de mtime de forma inconsistente."""
        from unittest.mock import patch
        with patch("src.utils.json_utils.atomic_write_json", return_value=False):
            Config._cached_mtime = 12345
            Config.save({"corrupted": True})
            # Não deve ter atualizado o mtime do cache
            self.assertEqual(Config._cached_mtime, 12345)

    def test_visionary_user_data_strict_priority(self):
        """Valida que VISIONARY_USER_DATA tem precedência soberana e isola settings.json no diretório temporário."""
        from src.config import get_app_data_dir, Config
        
        tmp_dir = tempfile.mkdtemp(prefix="test_portable_user_data_")
        try:
            with patch.dict(os.environ, {"VISIONARY_USER_DATA": tmp_dir}):
                resolved = get_app_data_dir()
                self.assertEqual(os.path.normpath(resolved), os.path.normpath(tmp_dir))
                
                # Salvar via Config grava exatamente no settings.json isolado
                Config.set("test_portable_sync_key", "pendrive_isolated_value")
                
                target_json = os.path.join(tmp_dir, "settings.json")
                self.assertTrue(os.path.exists(target_json))
                with open(target_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data.get("test_portable_sync_key"), "pendrive_isolated_value")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_portable_marker_creates_data_folder(self):
        """Valida que o marcador .portable isola os dados na subpasta 'data/'."""
        from src.config import get_app_data_dir
        
        tmp_root = tempfile.mkdtemp(prefix="test_root_portable_")
        try:
            portable_marker = os.path.join(tmp_root, ".portable")
            with open(portable_marker, "w") as f:
                f.write("1")
                
            fake_config_py = os.path.join(tmp_root, "src", "config.py")
            with patch.dict(os.environ, {"VISIONARY_USER_DATA": ""}):
                with patch("src.config.__file__", fake_config_py):
                    resolved = get_app_data_dir()
                    expected_data = os.path.normpath(os.path.join(tmp_root, "data"))
                    self.assertEqual(os.path.normpath(resolved), expected_data)
                    self.assertTrue(os.path.isdir(expected_data))
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
