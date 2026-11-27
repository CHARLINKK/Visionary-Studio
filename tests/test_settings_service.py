import os
import json
import pytest
from unittest.mock import patch

from src.config import Config
from src.api_services.settings_service import SettingsService


class TestSettingsService:
    def test_saveSettings_non_dict_rejected(self):
        svc = SettingsService()
        res_none = svc.saveSettings(None)
        assert res_none["success"] is False
        assert "must be a dictionary" in res_none["error"]

        res_list = svc.saveSettings(["theme", "Dark"])
        assert res_list["success"] is False

    def test_saveSettings_clamping_and_validation(self, tmp_path, monkeypatch):
        test_config = tmp_path / "settings.json"
        monkeypatch.setattr("src.config.CONFIG_FILE", str(test_config))
        monkeypatch.setattr("src.config._last_dynamic_path", str(test_config))
        monkeypatch.setattr(Config, "get_config_path", classmethod(lambda cls: str(test_config)))

        svc = SettingsService()
        res = svc.saveSettings({
            "flask_port": 90000,
            "soundVolume": 180,
            "sidebarWidth": 50,
            "close_action": "invalid_mode"
        })
        assert res["success"] is True

        saved = svc.getSettings()
        assert saved["flask_port"] == 65535
        assert saved["soundVolume"] == 100
        assert saved["sidebarWidth"] == 150
        assert saved["close_action"] == "smart"

    def test_stats_lifecycle_and_updateStats(self, tmp_path, monkeypatch):
        test_stats = tmp_path / "stats.json"
        orig_normpath = os.path.normpath
        monkeypatch.setattr(
            "src.api_services.settings_service.os.path.normpath",
            lambda p: str(test_stats) if "stats.json" in str(p) else orig_normpath(p)
        )

        svc = SettingsService()
        initial = svc.getStats()
        assert initial["pagesProcessed"] == 0
        assert initial["timeSaved"] == 0

        # Update stats
        up_res = svc.updateStats(pages_processed=5, time_saved=120)
        assert up_res["success"] is True
        assert up_res["stats"]["pagesProcessed"] == 5
        assert up_res["stats"]["timeSaved"] == 120

        # Verify on disk
        with open(test_stats, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        assert disk_data["pagesProcessed"] == 5
        assert disk_data["timeSaved"] == 120

        # Increment further
        up_res2 = svc.updateStats(pages_processed=3, time_saved=60)
        assert up_res2["stats"]["pagesProcessed"] == 8
        assert up_res2["stats"]["timeSaved"] == 180

    def test_config_self_healing_from_corrupted_json(self, tmp_path, monkeypatch):
        bad_config = tmp_path / "corrupted_settings.json"
        bad_config.write_text("{malformed_json: true, broken", encoding="utf-8")

        monkeypatch.setattr("src.config.CONFIG_FILE", str(bad_config))
        monkeypatch.setattr("src.config._last_dynamic_path", str(bad_config))
        monkeypatch.setattr(Config, "get_config_path", classmethod(lambda cls: str(bad_config)))

        Config._cached_data = None
        Config._cached_mtime = 0
        Config._cached_file = ""

        # load() should not crash, should create .bak and restore valid defaults
        loaded = Config.load()
        assert isinstance(loaded, dict)
        assert loaded.get("theme") == "Dark"
        assert os.path.exists(str(bad_config) + ".bak")

        # Config file on disk should now be valid JSON
        with open(bad_config, "r", encoding="utf-8") as f:
            repaired = json.load(f)
        assert isinstance(repaired, dict)
        assert repaired.get("flask_port") == 5000
