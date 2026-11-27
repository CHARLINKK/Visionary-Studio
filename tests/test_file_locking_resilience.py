"""
Unit tests validating Windows File Locking Resilience (PermissionError [WinError 32] / EBUSY)
using unittest.mock without touching real user data.
"""
import errno
import json
import os
import time
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from src.utils.file_resilience import (
    is_transient_lock_error,
    retry_on_file_lock,
    resilient_read_bytes,
    resilient_read_text,
    resilient_read_json,
    to_extended_length_path,
)
from src.api_services.image_service import ImageService
from src.domain.page_store import PageStore
from src.utils.path_sandbox import register_root


class TestIsTransientLockError:
    def test_winerror_codes(self):
        # WinError 32 (Sharing violation)
        pe32 = PermissionError(13, "[WinError 32] The process cannot access the file")
        pe32.winerror = 32
        assert is_transient_lock_error(pe32) is True

        # WinError 33 (Lock violation)
        pe33 = PermissionError(13, "[WinError 33] The process cannot access the file")
        pe33.winerror = 33
        assert is_transient_lock_error(pe33) is True

        # WinError 5 (Access denied)
        pe5 = PermissionError(13, "[WinError 5] Access is denied")
        pe5.winerror = 5
        assert is_transient_lock_error(pe5) is True

    def test_errno_codes(self):
        # OSError EBUSY
        ebusy = OSError(errno.EBUSY, "Device or resource busy")
        assert is_transient_lock_error(ebusy) is True

        # PermissionError with errno.EACCES
        eacces = PermissionError(errno.EACCES, "Permission denied")
        assert is_transient_lock_error(eacces) is True

    def test_string_fallback(self):
        err1 = OSError("[WinError 32] O arquivo já está sendo usado por outro processo")
        assert is_transient_lock_error(err1) is True

        err2 = OSError("System error: EBUSY resource locked")
        assert is_transient_lock_error(err2) is True

        err3 = OSError("[WinError 5] Access denied")
        assert is_transient_lock_error(err3) is True

        err4 = OSError("[WinError 33] Lock violation")
        assert is_transient_lock_error(err4) is True

        # Unrelated non-IO exceptions containing lock substrings must NOT be classified as transient
        val_err = ValueError("Invalid parameter containing [WinError 32]")
        assert is_transient_lock_error(val_err) is False

        val_ebusy = ValueError("Config parameter EBUSY is invalid")
        assert is_transient_lock_error(val_ebusy) is False

        gen_exc = Exception("[WinError 5] Access denied")
        assert is_transient_lock_error(gen_exc) is False

    def test_non_transient_errors(self):
        fnf = FileNotFoundError("Missing file")
        assert is_transient_lock_error(fnf) is False

        dir_err = IsADirectoryError("Target is a directory")
        assert is_transient_lock_error(dir_err) is False

        val_err = ValueError("Invalid format")
        assert is_transient_lock_error(val_err) is False

        gen_err = RuntimeError("General runtime failure")
        assert is_transient_lock_error(gen_err) is False


class TestRetryOnFileLock:
    def test_immediate_success(self):
        mock_fn = MagicMock(return_value="ok")
        res = retry_on_file_lock(mock_fn)
        assert res == "ok"
        assert mock_fn.call_count == 1

    @patch("src.utils.file_resilience.time.sleep")
    def test_recovery_after_transient_failures(self, mock_sleep):
        mock_fn = MagicMock()
        err = PermissionError(13, "[WinError 32] Locked by search indexer")
        err.winerror = 32
        mock_fn.side_effect = [err, err, "success_result"]

        res = retry_on_file_lock(mock_fn, max_attempts=3, initial_delay=0.02, max_delay=0.05)
        assert res == "success_result"
        assert mock_fn.call_count == 3
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 0.02
        assert mock_sleep.call_args_list[1][0][0] >= 0.03

    @patch("src.utils.file_resilience.time.sleep")
    def test_non_transient_error_aborts_immediately(self, mock_sleep):
        mock_fn = MagicMock(side_effect=ValueError("Syntax problem"))
        with pytest.raises(ValueError):
            retry_on_file_lock(mock_fn, max_attempts=3)
        assert mock_fn.call_count == 1
        assert mock_sleep.call_count == 0

    @patch("src.utils.file_resilience.time.sleep")
    def test_filenotfound_error_aborts_immediately(self, mock_sleep):
        mock_fn = MagicMock(side_effect=FileNotFoundError("Target absent"))
        with pytest.raises(FileNotFoundError):
            retry_on_file_lock(mock_fn, max_attempts=3)
        assert mock_fn.call_count == 1
        assert mock_sleep.call_count == 0

    @patch("src.utils.file_resilience.time.sleep")
    def test_exhausted_attempts_raises(self, mock_sleep):
        mock_fn = MagicMock()
        err = PermissionError(13, "[WinError 32] Persistent sharing violation")
        err.winerror = 32
        mock_fn.side_effect = err

        with pytest.raises(PermissionError):
            retry_on_file_lock(mock_fn, max_attempts=3)
        assert mock_fn.call_count == 3
        assert mock_sleep.call_count == 2


class TestResilientFileOperations:
    @patch("src.utils.file_resilience.time.sleep")
    def test_resilient_read_bytes_recovery(self, mock_sleep, tmp_path):
        test_file = tmp_path / "sample.bin"
        payload = b"\x89PNG\r\n\x1a\nPayloadData"
        test_file.write_bytes(payload)

        real_open = open
        call_counter = {"count": 0}

        def flaky_open(file, mode="r", *args, **kwargs):
            if str(file) == str(test_file):
                call_counter["count"] += 1
                if call_counter["count"] < 2:
                    pe = PermissionError(13, "[WinError 32] Locked by AV")
                    pe.winerror = 32
                    raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=flaky_open):
            data = resilient_read_bytes(str(test_file))
            assert data == payload
            assert call_counter["count"] == 2
            assert mock_sleep.call_count == 1

    @patch("src.utils.file_resilience.time.sleep")
    def test_resilient_read_text_recovery(self, mock_sleep, tmp_path):
        test_file = tmp_path / "sample.txt"
        test_file.write_text("Olá Mundo UTF-8", encoding="utf-8")

        real_open = open
        call_counter = {"count": 0}

        def flaky_open(file, mode="r", *args, **kwargs):
            if str(file) == str(test_file):
                call_counter["count"] += 1
                if call_counter["count"] < 2:
                    pe = PermissionError(13, "[WinError 32] Search indexer locked")
                    pe.winerror = 32
                    raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=flaky_open):
            text = resilient_read_text(str(test_file))
            assert text == "Olá Mundo UTF-8"
            assert call_counter["count"] == 2
            assert mock_sleep.call_count == 1

    def test_resilient_read_json_nonexistent_returns_default(self, tmp_path):
        missing = tmp_path / "does_not_exist.json"
        assert resilient_read_json(str(missing), default=[]) == []
        assert resilient_read_json("", default={"a": 1}) == {"a": 1}
        assert resilient_read_json(None, default="fallback") == "fallback"

    @patch("src.utils.file_resilience.time.sleep")
    def test_resilient_read_json_recovery(self, mock_sleep, tmp_path):
        test_file = tmp_path / "map.json"
        test_file.write_text('{"version": 2, "boxes": [{"id": 1, "text": "Hi"}]}', encoding="utf-8")

        real_open = open
        call_counter = {"count": 0}

        def flaky_open(file, mode="r", *args, **kwargs):
            if str(file) == str(test_file):
                call_counter["count"] += 1
                if call_counter["count"] < 3:
                    pe = PermissionError(13, "[WinError 32] Defender scan")
                    pe.winerror = 32
                    raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=flaky_open):
            data = resilient_read_json(str(test_file))
            assert data["version"] == 2
            assert len(data["boxes"]) == 1
            assert data["boxes"][0]["text"] == "Hi"
            assert call_counter["count"] == 3
            assert mock_sleep.call_count == 2

    def test_resilient_read_json_corrupted_returns_default(self, tmp_path):
        test_file = tmp_path / "corrupted.json"
        test_file.write_text("{broken json format", encoding="utf-8")
        res = resilient_read_json(str(test_file), default={"recovery": True})
        assert res == {"recovery": True}

        # default=None must return None on corrupted JSON
        res_none = resilient_read_json(str(test_file), default=None)
        assert res_none is None

        # when default is not provided, it must raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            resilient_read_json(str(test_file))


class TestImageServiceResilience:
    @patch("src.utils.file_resilience.time.sleep")
    def test_image_service_get_thumbnail_and_pil_recovery(self, mock_sleep, tmp_path):
        folder = tmp_path / "chapter"
        folder.mkdir()
        register_root(str(folder))

        img_path = folder / "001.png"
        img = Image.new("RGB", (120, 120), color="blue")
        img.save(str(img_path))

        svc = ImageService()
        real_open = Image.open
        call_counter = {"count": 0}

        def flaky_pil_open(fp, *args, **kwargs):
            call_counter["count"] += 1
            if call_counter["count"] == 1:
                pe = PermissionError(13, "[WinError 32] Antivirus lock")
                pe.winerror = 32
                raise pe
            return real_open(fp, *args, **kwargs)

        with patch("PIL.Image.open", side_effect=flaky_pil_open):
            # Test get_thumbnail alias as well as get_image_base64
            res = svc.get_thumbnail(str(img_path))
            assert res["success"] is True
            assert res["data_url"].startswith("data:image/jpeg;base64,")
            assert call_counter["count"] == 2
            assert mock_sleep.call_count == 1

    @patch("src.utils.file_resilience.time.sleep")
    def test_image_service_mtime_recovery(self, mock_sleep, tmp_path):
        folder = tmp_path / "chapter_mtime"
        folder.mkdir()
        register_root(str(folder))

        img_path = folder / "002.png"
        img = Image.new("RGB", (60, 60), color="green")
        img.save(str(img_path))

        real_mtime = os.path.getmtime
        svc = ImageService()
        target_calls = []

        def flaky_getmtime(path):
            if os.path.normpath(str(path)) == os.path.normpath(str(img_path)):
                target_calls.append(path)
                if len(target_calls) == 1:
                    pe = PermissionError(13, "[WinError 32] Transient indexer lock")
                    pe.winerror = 32
                    raise pe
            return real_mtime(path)

        with patch("os.path.getmtime", side_effect=flaky_getmtime):
            res = svc.get_thumbnail(str(img_path))
            assert res["success"] is True
            assert len(target_calls) == 2
            assert mock_sleep.call_count == 1
            with svc._cache_lock:
                assert len(svc._thumbnail_cache) == 1

    @patch("src.utils.file_resilience.time.sleep")
    def test_image_service_get_image_base64_full_resilience(self, mock_sleep, tmp_path):
        folder = tmp_path / "chapter_full"
        folder.mkdir()
        register_root(str(folder))

        img_path = folder / "003.png"
        img = Image.new("RGB", (80, 80), color="purple")
        img.save(str(img_path))

        svc = ImageService()
        real_open = open
        call_counter = {"count": 0}

        def flaky_open(file, mode="r", *args, **kwargs):
            if str(file) == str(img_path):
                call_counter["count"] += 1
                if call_counter["count"] == 1:
                    pe = PermissionError(13, "[WinError 32] Lock on full read")
                    pe.winerror = 32
                    raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=flaky_open):
            res = svc.get_image_base64_full(str(img_path))
            assert res["success"] is True
            assert res["data_url"].startswith("data:image/png;base64,")
            assert call_counter["count"] == 2
            assert mock_sleep.call_count == 1


class TestPageStoreResilience:
    @patch("src.utils.file_resilience.time.sleep")
    def test_load_page_record_recovers_from_transient_lock(self, mock_sleep, tmp_path):
        chapter = tmp_path / "chapter"
        out_dir = chapter / "output"
        out_dir.mkdir(parents=True)

        map_path = out_dir / "001_map.json"
        map_path.write_text(
            json.dumps({
                "version": 2,
                "boxes": [{"id": 1, "text": "Essential text"}],
                "panels": [{"box": [0, 0, 100, 100]}],
                "backup": None,
            }),
            encoding="utf-8"
        )

        real_open = open
        call_counter = {"count": 0}

        def flaky_open(file, mode="r", *args, **kwargs):
            if str(file) == str(map_path):
                call_counter["count"] += 1
                if call_counter["count"] < 3:
                    pe = PermissionError(13, "[WinError 32] Sharing lock on map")
                    pe.winerror = 32
                    raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=flaky_open):
            PageStore.invalidate_cache()
            record = PageStore.load_page_record(str(map_path))
            # Critical verification: bubbles/panels must NOT be wiped
            assert len(record["boxes"]) == 1
            assert record["boxes"][0]["text"] == "Essential text"
            assert len(record["panels"]) == 1
            assert call_counter["count"] == 3
            assert mock_sleep.call_count == 2

    @patch("src.utils.file_resilience.time.sleep")
    def test_read_satellite_list_recovers_from_transient_lock(self, mock_sleep, tmp_path):
        chapter = tmp_path / "chapter_sat"
        out_dir = chapter / "output"
        out_dir.mkdir(parents=True)

        sat_path = out_dir / "001_panels.json"
        sat_path.write_text(
            json.dumps([{"box": [10, 20, 30, 40]}]),
            encoding="utf-8"
        )

        real_open = open
        call_counter = {"count": 0}

        def flaky_open(file, mode="r", *args, **kwargs):
            if str(file) == str(sat_path):
                call_counter["count"] += 1
                if call_counter["count"] == 1:
                    pe = PermissionError(13, "[WinError 32] Antivirus lock on satellite")
                    pe.winerror = 32
                    raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=flaky_open):
            panels = PageStore._read_satellite_list(str(chapter), "001", "_panels.json")
            assert panels is not None
            assert len(panels) == 1
            assert panels[0]["box"] == [10, 20, 30, 40]
            assert call_counter["count"] == 2
            assert mock_sleep.call_count == 1


class TestConfigAndTxtSyncResilience:
    @patch("src.utils.file_resilience.time.sleep")
    def test_config_load_recovers_from_transient_lock_without_wiping_settings(self, mock_sleep, tmp_path, monkeypatch):
        from src.config import Config
        cfg_file = tmp_path / "settings.json"
        cfg_file.write_text(json.dumps({"theme": "Light", "soundVolume": 42}), encoding="utf-8")
        monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
        Config._cached_data = None
        Config._cached_mtime = 0

        real_open = open
        call_counter = {"count": 0}

        def flaky_open(file, mode="r", *args, **kwargs):
            if str(file) == str(cfg_file) and "r" in mode:
                call_counter["count"] += 1
                if call_counter["count"] < 3:
                    pe = PermissionError(13, "[WinError 32] Sharing violation on settings.json")
                    pe.winerror = 32
                    raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=flaky_open):
            loaded = Config.load()
            assert loaded["theme"] == "Light"
            assert loaded["soundVolume"] == 42
            assert call_counter["count"] == 3

        # Even if all retry attempts fail with a persistent lock, settings.json on disk must NOT be overwritten
        Config._cached_data = None
        Config._cached_mtime = 0

        def persistent_lock_open(file, mode="r", *args, **kwargs):
            if str(file) == str(cfg_file) and "r" in mode:
                pe = PermissionError(13, "[WinError 32] Persistent lock on settings.json")
                pe.winerror = 32
                raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=persistent_lock_open):
            fallback_data = Config.load()
            assert isinstance(fallback_data, dict)

        disk_after = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert disk_after["theme"] == "Light"
        assert disk_after["soundVolume"] == 42


class TestExtendedLengthPath:
    def test_handles_empty_or_non_string(self):
        assert to_extended_length_path(None) is None
        assert to_extended_length_path("") == ""

    def test_leaves_short_path_unchanged(self):
        short_path = "C:\\Short\\Path\\file.txt"
        assert to_extended_length_path(short_path) == short_path

    def test_leaves_already_prefixed_path_unchanged(self):
        prefixed = "\\\\?\\C:\\Very\\Long\\Path"
        assert to_extended_length_path(prefixed) == prefixed

    def test_prefixes_long_windows_path(self):
        long_dir = "C:\\" + ("a" * 250) + "\\file.json"
        res = to_extended_length_path(long_dir)
        if os.name == "nt":
            assert res.startswith("\\\\?\\C:\\")
        else:
            assert res == long_dir




class TestCleanupOrphanedTmpFiles:
    def test_cleanup_ignores_nonexistent_or_empty_dir(self):
        from src.utils.file_resilience import cleanup_orphaned_tmp_files
        assert cleanup_orphaned_tmp_files(None) == 0
        assert cleanup_orphaned_tmp_files("C:\\caminho\\que\\nao\\existe_xyz") == 0

    def test_cleanup_removes_only_old_tmp_files(self, tmp_path):
        from src.utils.file_resilience import cleanup_orphaned_tmp_files
        old_tmp = tmp_path / "page_001_map.json.tmp"
        old_tmp.write_text("temp data", encoding="utf-8")

        recent_tmp = tmp_path / "page_002_map.json.tmp"
        recent_tmp.write_text("active data", encoding="utf-8")

        real_json = tmp_path / "page_001_map.json"
        real_json.write_text('{"version": 2}', encoding="utf-8")

        past_time = time.time() - 600
        os.utime(str(old_tmp), (past_time, past_time))

        removed = cleanup_orphaned_tmp_files(str(tmp_path), max_age_seconds=300.0)
        assert removed == 1
        assert not old_tmp.exists()
        assert recent_tmp.exists()
        assert real_json.exists()
