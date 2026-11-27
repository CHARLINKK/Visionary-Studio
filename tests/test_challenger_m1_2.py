"""
tests/test_challenger_m1_2.py
Empirical stress tests by Challenger 2 for Milestone 1.
Validates:
1. Boundary values of retry_on_file_lock (max_attempts <= 0, 1, delay bounds, backoff clamping).
2. Max retries exceeded behavior (raising original exception, resilient_read_json behavior).
3. Exception classification is_transient_lock_error across winerror 32, 33, 5, errno EBUSY/EACCES,
   EPERM, FileNotFoundError, Directory errors, and string markers.
4. ImageService get_thumbnail vs get_image_base64 exact consistency across formats, cache hits,
   PIL errors, and sandbox violations.
5. PageStore resilience during batch reads with mixed locks, satellites, and concurrent threads.
Strictly isolated using tmp_path and mocks; zero access to real user data.
"""
import concurrent.futures
import errno
import io
import json
import os
import time
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from src.utils.file_resilience import (
    is_transient_lock_error,
    retry_on_file_lock,
    resilient_read_bytes,
    resilient_read_text,
    resilient_read_json,
    TRANSIENT_WINERRORS,
)
from src.api_services.image_service import ImageService
from src.domain.page_store import PageStore
from src.utils.path_sandbox import register_root, ImageReadDenied


# =====================================================================
# 1. Boundary Values & Parameter Stress
# =====================================================================
class TestBoundaryValuesStress:
    def test_max_attempts_zero_raises_runtime_error(self):
        """When max_attempts is 0, the retry loop does not run and raises RuntimeError."""
        mock_fn = MagicMock()
        with pytest.raises(RuntimeError, match="retry_on_file_lock completed without result or exception"):
            retry_on_file_lock(mock_fn, max_attempts=0)
        assert mock_fn.call_count == 0

    def test_max_attempts_negative_raises_runtime_error(self):
        """Negative max_attempts behaves identically to 0 (no iterations)."""
        mock_fn = MagicMock()
        with pytest.raises(RuntimeError, match="retry_on_file_lock completed without result or exception"):
            retry_on_file_lock(mock_fn, max_attempts=-5)
        assert mock_fn.call_count == 0

    def test_max_attempts_one_no_retries_on_failure(self):
        """max_attempts=1 executes exactly once; if transient error occurs, it raises immediately."""
        mock_fn = MagicMock()
        pe = PermissionError(13, "[WinError 32] Exclusive lock")
        pe.winerror = 32
        mock_fn.side_effect = pe

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(PermissionError):
                retry_on_file_lock(mock_fn, max_attempts=1)
            assert mock_fn.call_count == 1
            assert mock_sleep.call_count == 0

    def test_max_attempts_one_returns_on_success(self):
        """max_attempts=1 returns successful result on first run."""
        mock_fn = MagicMock(return_value="single_shot")
        res = retry_on_file_lock(mock_fn, max_attempts=1)
        assert res == "single_shot"
        assert mock_fn.call_count == 1

    @patch("time.sleep")
    def test_delay_clamping_at_max_delay(self, mock_sleep):
        """Backoff delay must not exceed max_delay."""
        mock_fn = MagicMock()
        pe = PermissionError(13, "[WinError 32] Lock")
        pe.winerror = 32
        mock_fn.side_effect = [pe, pe, pe, pe, "success"]

        res = retry_on_file_lock(
            mock_fn,
            max_attempts=5,
            initial_delay=0.02,
            max_delay=0.04,
            backoff_factor=2.0,
        )
        assert res == "success"
        assert mock_fn.call_count == 5
        assert mock_sleep.call_count == 4

        # Delays should be: 0.02, then min(0.04, 0.04)=0.04, then min(0.08, 0.04)=0.04, then min(0.08, 0.04)=0.04
        sleep_args = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_args[0] == 0.02
        for delay in sleep_args[1:]:
            assert delay <= 0.04 + 1e-9


# =====================================================================
# 2. Max Retries Exceeded & Exception Transparency
# =====================================================================
class TestMaxRetriesExceeded:
    @patch("time.sleep")
    def test_exact_original_exception_propagates_intact(self, mock_sleep):
        """When retries are exhausted, the exact original exception instance must be raised."""
        custom_exc = PermissionError(13, "[WinError 32] Specific lock detail")
        custom_exc.winerror = 32
        custom_exc.custom_attr = "audit_marker_123"

        mock_fn = MagicMock(side_effect=custom_exc)
        with pytest.raises(PermissionError) as exc_info:
            retry_on_file_lock(mock_fn, max_attempts=3)

        assert exc_info.value is custom_exc
        assert getattr(exc_info.value, "custom_attr", None) == "audit_marker_123"
        assert mock_fn.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    def test_resilient_read_json_raises_on_exhausted_transient_lock(self, mock_sleep, tmp_path):
        """resilient_read_json must NOT mask persistent lock with default fallback; it must raise!"""
        test_file = tmp_path / "persistent_lock.json"
        test_file.write_text('{"important": "data"}', encoding="utf-8")

        def always_locked(*args, **kwargs):
            pe = PermissionError(13, "[WinError 32] Held indefinitely")
            pe.winerror = 32
            raise pe

        with patch("builtins.open", side_effect=always_locked):
            with pytest.raises(PermissionError):
                resilient_read_json(str(test_file), default={"fallback": True}, max_attempts=3)

    @patch("time.sleep")
    def test_resilient_read_bytes_and_text_raise_on_exhausted_lock(self, mock_sleep, tmp_path):
        """resilient_read_bytes and resilient_read_text propagate lock exception on exhaustion."""
        test_file = tmp_path / "test.dat"
        test_file.write_text("content", encoding="utf-8")

        def locked_open(*args, **kwargs):
            pe = PermissionError(errno.EBUSY, "EBUSY file locked")
            raise pe

        with patch("builtins.open", side_effect=locked_open):
            with pytest.raises(PermissionError):
                resilient_read_bytes(str(test_file), max_attempts=3)
            with pytest.raises(PermissionError):
                resilient_read_text(str(test_file), max_attempts=3)


# =====================================================================
# 3. Exception Classification Stress (is_transient_lock_error)
# =====================================================================
class TestExceptionClassificationStress:
    def test_all_transient_winerrors(self):
        """Check all defined TRANSIENT_WINERRORS {32, 33, 5}."""
        assert TRANSIENT_WINERRORS == {32, 33, 5}
        for code in (32, 33, 5):
            exc = OSError()
            exc.winerror = code
            assert is_transient_lock_error(exc) is True

    def test_non_transient_winerrors(self):
        """Non-locking winerrors (e.g. 2 File Not Found, 3 Path Not Found) return False."""
        for code in (2, 3, 15, 21):
            exc = OSError(code, "Other OS Error")
            exc.winerror = code
            assert is_transient_lock_error(exc) is False

    def test_permission_error_eacces_without_winerror(self):
        """PermissionError with errno.EACCES (13) and winerror=None is recognized as transient."""
        pe = PermissionError(errno.EACCES, "Permission denied")
        pe.winerror = None
        assert is_transient_lock_error(pe) is True

    def test_permission_error_eperm_without_winerror_is_not_transient(self):
        """PermissionError with errno.EPERM (1) and no winerror/string marker is NOT transient."""
        pe = PermissionError(errno.EPERM, "Operation not permitted")
        pe.winerror = None
        assert is_transient_lock_error(pe) is False

    def test_oserror_ebusy_recognized(self):
        """OSError with errno.EBUSY (16) is recognized as transient."""
        err = OSError(errno.EBUSY, "Resource busy")
        assert is_transient_lock_error(err) is True

    def test_file_not_found_variants_never_transient(self):
        """FileNotFoundError is never transient even if it contains misleading text."""
        fnf1 = FileNotFoundError(2, "No such file or directory")
        assert is_transient_lock_error(fnf1) is False

        # Even if string mentions [WinError 32]
        fnf2 = FileNotFoundError("[WinError 32] File not found")
        assert is_transient_lock_error(fnf2) is False

    def test_directory_errors_never_transient(self):
        """IsADirectoryError and NotADirectoryError are never transient."""
        assert is_transient_lock_error(IsADirectoryError("[WinError 32] Dir")) is False
        assert is_transient_lock_error(NotADirectoryError("EBUSY not a dir")) is False

    def test_string_markers_case_insensitivity_and_variants(self):
        """String inspection identifies WinError 32, 33, 5 and EBUSY on OSError instances."""
        assert is_transient_lock_error(OSError("Failed: [WinError 32] sharing violation")) is True
        assert is_transient_lock_error(OSError("Failed: [WinError 5] access denied")) is True
        assert is_transient_lock_error(OSError("Failed: [WinError 33] lock violation")) is True
        assert is_transient_lock_error(OSError("IO error: EBUSY locked by another thread")) is True
        assert is_transient_lock_error(OSError("Random disk error without codes")) is False
        # Non-OSError exceptions containing lock markers must NOT be classified as transient
        assert is_transient_lock_error(Exception("Failed: [WinError 32] sharing violation")) is False
        assert is_transient_lock_error(ValueError("Failed: [WinError 5] access denied")) is False


# =====================================================================
# 4. ImageService: get_thumbnail vs get_image_base64 Consistency
# =====================================================================
class TestImageServiceConsistency:
    @pytest.fixture
    def setup_image_env(self, tmp_path):
        img_dir = tmp_path / "manga_chapter"
        img_dir.mkdir(parents=True)
        register_root(str(img_dir))

        # 1. Standard PNG
        png_path = img_dir / "page_01.png"
        img_png = Image.new("RGB", (200, 300), color=(100, 150, 200))
        img_png.save(str(png_path), format="PNG")

        # 2. Transparent RGBA PNG
        rgba_path = img_dir / "page_02_alpha.png"
        img_rgba = Image.new("RGBA", (150, 150), color=(255, 0, 0, 128))
        img_rgba.save(str(rgba_path), format="PNG")

        # 3. JPEG
        jpg_path = img_dir / "page_03.jpg"
        img_jpg = Image.new("RGB", (300, 400), color=(50, 50, 50))
        img_jpg.save(str(jpg_path), format="JPEG")

        svc = ImageService(default_path=str(img_dir))
        return {
            "dir": img_dir,
            "png": str(png_path),
            "rgba": str(rgba_path),
            "jpg": str(jpg_path),
            "svc": svc,
        }

    def test_thumbnail_and_get_image_base64_identical_output(self, setup_image_env):
        """get_thumbnail and get_image_base64 must return identical data structures."""
        svc = setup_image_env["svc"]
        for key in ("png", "rgba", "jpg"):
            path = setup_image_env[key]
            svc.clear_cache()
            res_thumb = svc.get_thumbnail(path)
            svc.clear_cache()
            res_base64 = svc.get_image_base64(path)

            assert res_thumb["success"] is True
            assert res_base64["success"] is True
            assert res_thumb["data_url"] == res_base64["data_url"]
            assert res_thumb["data_url"].startswith("data:image/jpeg;base64,")

    def test_cache_cross_sharing_between_thumbnail_and_base64(self, setup_image_env):
        """A thumbnail generated via get_thumbnail must be returned from cache by get_image_base64 and vice versa."""
        svc = setup_image_env["svc"]
        path = setup_image_env["png"]
        svc.clear_cache()

        # Prime with get_thumbnail
        res1 = svc.get_thumbnail(path)
        assert res1["success"] is True

        # Intercept PIL to ensure cache hit
        with patch("PIL.Image.open", side_effect=RuntimeError("PIL should not be called on cache hit")):
            res2 = svc.get_image_base64(path)
            assert res2["success"] is True
            assert res2["data_url"] == res1["data_url"]

        # Now clear and prime with get_image_base64
        svc.clear_cache()
        res3 = svc.get_image_base64(path)
        with patch("PIL.Image.open", side_effect=RuntimeError("PIL should not be called on cache hit")):
            res4 = svc.get_thumbnail(path)
            assert res4["success"] is True
            assert res4["data_url"] == res3["data_url"]

    def test_consistency_on_nonexistent_and_unauthorized_paths(self, setup_image_env, tmp_path):
        """Both methods return identical error structures on missing or unauthorized files."""
        svc = setup_image_env["svc"]

        # Missing file
        missing_path = os.path.join(str(setup_image_env["dir"]), "does_not_exist.png")
        err1 = svc.get_thumbnail(missing_path)
        err2 = svc.get_image_base64(missing_path)
        assert err1["success"] is False
        assert err2["success"] is False
        assert err1 == err2

        # Unauthorized path (outside registered root)
        outside_dir = tmp_path / "outside_dir"
        outside_dir.mkdir()
        outside_file = outside_dir / "secret.png"
        outside_file.write_bytes(b"dummy")

        err3 = svc.get_thumbnail(str(outside_file))
        err4 = svc.get_image_base64(str(outside_file))
        assert err3["success"] is False
        assert err4["success"] is False
        assert err3 == err4

    @patch("time.sleep")
    def test_fallback_to_resilient_read_bytes_when_pil_fails(self, mock_sleep, setup_image_env):
        """When PIL crashes (e.g. invalid format), both methods fall back to resilient_read_bytes."""
        svc = setup_image_env["svc"]
        path = setup_image_env["png"]
        svc.clear_cache()

        call_counter = {"count": 0}
        real_read_bytes = resilient_read_bytes

        def flaky_resilient_read(filepath, max_attempts=3):
            call_counter["count"] += 1
            return real_read_bytes(filepath, max_attempts=max_attempts)

        with patch("PIL.Image.open", side_effect=Exception("Corrupted PIL stream")):
            with patch("src.api_services.image_service.resilient_read_bytes", side_effect=flaky_resilient_read):
                res = svc.get_thumbnail(path)
                assert res["success"] is True
                assert res["data_url"].startswith("data:image/png;base64,")
                assert call_counter["count"] == 1


# =====================================================================
# 5. PageStore: Resilience During Batch Reads & Satellite Recovery
# =====================================================================
class TestPageStoreBatchResilience:
    @pytest.fixture
    def setup_batch_chapter(self, tmp_path):
        chapter = tmp_path / "vol01_ch01"
        out_dir = chapter / "output"
        out_dir.mkdir(parents=True)

        pages = []
        for i in range(1, 11):
            page_name = f"{i:03d}"
            map_file = out_dir / f"{page_name}_map.json"
            map_data = {
                "version": 2,
                "boxes": [{"id": i, "text": f"Dialog for page {page_name}"}],
                "panels": [{"box": [0, 0, 100, 100]}],
                "backup": None,
            }
            map_file.write_text(json.dumps(map_data), encoding="utf-8")

            # Page 3 and 7 also have legacy satellite files
            if i in (3, 7):
                panel_file = out_dir / f"{page_name}_panels.json"
                panel_file.write_text(json.dumps([{"box": [10, 10, 50, 50]}]), encoding="utf-8")

            pages.append({
                "page_name": page_name,
                "map_path": str(map_file),
                "expected_text": f"Dialog for page {page_name}",
            })

        return {"chapter": chapter, "pages": pages}

    @patch("time.sleep")
    def test_batch_page_loads_with_random_transient_locks(self, mock_sleep, setup_batch_chapter):
        """Simulate a batch load of 10 pages where even pages experience WinError 32 locks."""
        pages = setup_batch_chapter["pages"]
        locked_counter = {}

        real_open = open

        def intermittent_lock_open(file, mode="r", *args, **kwargs):
            file_str = str(file)
            for page in pages:
                if page["map_path"] == file_str:
                    num = int(page["page_name"])
                    if num % 2 == 0:  # Even pages lock once or twice
                        locked_counter[file_str] = locked_counter.get(file_str, 0) + 1
                        if locked_counter[file_str] <= 2:
                            pe = PermissionError(13, f"[WinError 32] Intermittent lock on {file_str}")
                            pe.winerror = 32
                            raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=intermittent_lock_open):
            PageStore.invalidate_cache()
            loaded_records = []
            for page in pages:
                rec = PageStore.load_page_record(page["map_path"])
                loaded_records.append(rec)

            # Verification: All 10 pages must be completely intact!
            assert len(loaded_records) == 10
            for idx, rec in enumerate(loaded_records):
                expected = pages[idx]["expected_text"]
                assert len(rec["boxes"]) == 1, f"Data lost for page index {idx}"
                assert rec["boxes"][0]["text"] == expected

            # Verify that locks occurred and retries recovered them
            assert len(locked_counter) > 0
            assert mock_sleep.call_count > 0

    @patch("time.sleep")
    def test_concurrent_batch_page_loads_under_transient_locks(self, mock_sleep, setup_batch_chapter):
        """Multi-threaded batch reading of pages under transient lock conditions."""
        pages = setup_batch_chapter["pages"]
        real_open = open
        lock_stats = {"count": 0}

        def concurrent_flaky_open(file, mode="r", *args, **kwargs):
            file_str = str(file)
            if "_map.json" in file_str:
                lock_stats["count"] += 1
                if lock_stats["count"] % 3 == 0:
                    pe = PermissionError(13, "[WinError 32] Concurrent lock")
                    pe.winerror = 32
                    raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=concurrent_flaky_open):
            PageStore.invalidate_cache()
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(PageStore.load_page_record, p["map_path"]): p
                    for p in pages
                }
                results = []
                for fut in concurrent.futures.as_completed(futures):
                    p = futures[fut]
                    record = fut.result()
                    results.append((p, record))

            assert len(results) == 10
            for p, record in results:
                assert len(record["boxes"]) == 1
                assert record["boxes"][0]["text"] == p["expected_text"]

    @patch("time.sleep")
    def test_page_record_satellite_resilience_when_map_backup_is_locked(self, mock_sleep, setup_batch_chapter):
        """
        When satellite file (_panels.json) suffers transient locks and envelope v2 has empty panels,
        PageStore recovers via resilient_read_json and absorbs the satellite panels.
        """
        pages = setup_batch_chapter["pages"]
        page3 = pages[2]  # page 003
        chapter = setup_batch_chapter["chapter"]

        # Re-write 003_map.json with empty panels to trigger satellite absorption
        map_path = page3["map_path"]
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": 2,
                "boxes": [{"id": 3, "text": "Dialog for page 003"}],
                "panels": [],
                "backup": None,
            }, f)

        sat_path = os.path.join(str(chapter), "output", "003_panels.json")
        assert os.path.exists(sat_path)

        sat_lock_counter = {"count": 0}
        real_open = open

        def satellite_lock_open(file, mode="r", *args, **kwargs):
            if os.path.normpath(str(file)) == os.path.normpath(sat_path):
                sat_lock_counter["count"] += 1
                if sat_lock_counter["count"] < 2:
                    pe = PermissionError(13, "[WinError 32] Sat lock")
                    pe.winerror = 32
                    raise pe
            return real_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=satellite_lock_open):
            PageStore.invalidate_cache()
            rec = PageStore.load_page_record(page3["map_path"])
            assert len(rec["boxes"]) == 1
            # Satellite panels were successfully loaded after recovering from transient lock
            assert len(rec["panels"]) == 1
            assert rec["panels"][0]["box"] == [10, 10, 50, 50]
            assert sat_lock_counter["count"] == 2
            assert mock_sleep.call_count == 1

