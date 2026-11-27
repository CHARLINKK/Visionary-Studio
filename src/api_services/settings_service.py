import os
from src.config import Config

class SettingsService:
    def __init__(self, api_bridge=None):
        self.api = api_bridge
        self._stats_cache = None

    def getSettings(self):
        return Config.load()

    def saveSettings(self, settings):
        if not isinstance(settings, dict):
            return {"success": False, "error": "Settings must be a dictionary"}
        try:
            clean = dict(settings)
            if "flask_port" in clean:
                try:
                    clean["flask_port"] = max(1024, min(65535, int(clean["flask_port"])))
                except (ValueError, TypeError):
                    clean.pop("flask_port", None)

            if "soundVolume" in clean:
                try:
                    clean["soundVolume"] = max(0, min(100, int(clean["soundVolume"])))
                except (ValueError, TypeError):
                    clean.pop("soundVolume", None)

            if "sidebarWidth" in clean:
                try:
                    clean["sidebarWidth"] = max(150, min(800, int(clean["sidebarWidth"])))
                except (ValueError, TypeError):
                    clean.pop("sidebarWidth", None)

            if "close_action" in clean and clean["close_action"] not in ("smart", "tray", "quit"):
                clean["close_action"] = "smart"

            Config.update(clean)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def invalidate_cache(self):
        self._stats_cache = None

    def _get_stats_path(self):
        from src.config import get_app_data_dir
        app_data_stats = os.path.normpath(os.path.join(get_app_data_dir(), 'stats.json'))
        repo_stats = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'stats.json'))
        if os.path.exists(app_data_stats) or not os.path.exists(repo_stats):
            return app_data_stats
        return repo_stats

    def getStats(self):
        stats_path = self._get_stats_path()
        default_stats = {"pagesProcessed": 0, "timeSaved": 0}
        try:
            if os.path.exists(stats_path):
                from src.utils.file_resilience import resilient_read_json
                saved = resilient_read_json(stats_path, default=None)
                if isinstance(saved, dict):
                    self._stats_cache = {**default_stats, **saved}
                    return self._stats_cache
        except Exception:
            pass
        self._stats_cache = default_stats
        return self._stats_cache

    def updateStats(self, pages_processed: int = 0, time_saved: int = 0):
        try:
            from src.utils.json_utils import atomic_write_json
            current = self.getStats()
            updated = {
                "pagesProcessed": max(0, int(current.get("pagesProcessed", 0)) + int(pages_processed)),
                "timeSaved": max(0, int(current.get("timeSaved", 0)) + int(time_saved))
            }
            stats_path = self._get_stats_path()
            target_dir = os.path.dirname(stats_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            if atomic_write_json(stats_path, updated, indent=2):
                self._stats_cache = dict(updated)
                return {"success": True, "stats": updated}
            return {"success": False, "error": "atomic_write_json failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
