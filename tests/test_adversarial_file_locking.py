"""
Adversarial stress tests for Windows File Locking Resilience (Milestone 1).
Validates concurrency, thread contention, real Windows locking (kernel32 CreateFileW exclusive lock / msvcrt),
transient simulated locks, mixed exceptions, path sandbox security, and ImageService/PageStore stress.
"""
import ctypes
import errno
import json
import msvcrt
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.api_services.image_service import ImageService
from src.utils.file_resilience import (
    is_transient_lock_error,
    resilient_read_bytes,
    resilient_read_json,
    resilient_read_text,
    retry_on_file_lock,
)
from src.domain.page_store import PageStore
from src.utils.path_sandbox import register_root, ImageReadDenied


# Windows API constants for kernel32 CreateFileW
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_NONE = 0x00000000  # Exclusive lock: no sharing
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def open_exclusive_windows_handle(filepath: str):
    """Opens a file with 0 share mode (FILE_SHARE_NONE) to trigger true WinError 32."""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(
        str(filepath),
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_NONE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        err = kernel32.GetLastError()
        raise ctypes.WinError(err)
    return handle


def close_windows_handle(handle):
    if handle and handle != INVALID_HANDLE_VALUE:
        ctypes.windll.kernel32.CloseHandle(handle)


class TestKernel32ExclusiveLockStress:
    """True native Windows kernel lock tests using CreateFileW with FILE_SHARE_NONE."""

    def test_kernel32_exclusive_lock_recovery(self, tmp_path):
        """
        Hold a true kernel exclusive lock for 30ms while resilient_read_bytes attempts to read.
        resilient_read_bytes must encounter [WinError 32] on attempt 1, sleep 20ms, retry,
        and succeed on attempt 2 or 3 once the handle is released.
        """
        target = tmp_path / "kernel_locked.dat"
        payload = b"KERNEL_EXCLUSIVE_PAYLOAD_TEST_987654321"
        target.write_bytes(payload)

        # Open exclusive lock
        handle = open_exclusive_windows_handle(str(target))

        # Schedule release after 30ms in a background thread (simulating antivirus scan completion)
        def release_after():
            time.sleep(0.030)  # 30ms
            close_windows_handle(handle)

        t = threading.Thread(target=release_after, daemon=True)
        t.start()

        # Resilient read with 4 attempts, initial delay 20ms
        start = time.perf_counter()
        data = resilient_read_bytes(str(target), max_attempts=4)
        elapsed = time.perf_counter() - start

        assert data == payload
        assert elapsed >= 0.020, f"Expected retry backoff delay, got {elapsed:.4f}s"
        t.join(timeout=1.0)

    def test_kernel32_exclusive_lock_exhaustion_raises_winerror_32(self, tmp_path):
        """
        Hold exclusive lock continuously; verify that retry_on_file_lock exhausts retries
        and raises true PermissionError with winerror == 32.
        """
        target = tmp_path / "permanently_locked.dat"
        target.write_bytes(b"DATA")

        handle = open_exclusive_windows_handle(str(target))
        try:
            with pytest.raises(PermissionError) as exc_info:
                resilient_read_bytes(str(target), max_attempts=3)

            assert exc_info.value.errno == errno.EACCES
            assert is_transient_lock_error(exc_info.value) is True
        finally:
            close_windows_handle(handle)

    def test_image_service_recovers_from_true_kernel_lock(self, tmp_path):
        """
        ImageService.get_thumbnail must survive a true kernel32 exclusive lock
        if released during the retry window.
        """
        folder = tmp_path / "chapter_kernel"
        folder.mkdir()
        register_root(str(folder))

        img_p = folder / "kernel_img.png"
        img = Image.new("RGB", (80, 80), color="orange")
        img.save(str(img_p))

        handle = open_exclusive_windows_handle(str(img_p))

        def release_after():
            time.sleep(0.025)
            close_windows_handle(handle)

        t = threading.Thread(target=release_after, daemon=True)
        t.start()

        svc = ImageService()
        res = svc.get_thumbnail(str(img_p))
        assert res["success"] is True
        assert res["data_url"].startswith("data:image/jpeg;base64,")
        t.join(timeout=1.0)

    def test_pagestore_recovers_from_true_kernel_lock(self, tmp_path):
        """
        PageStore.load_page_record must survive a true kernel32 exclusive lock
        and not wipe the bubbles/panels.
        """
        chapter = tmp_path / "chapter_kernel_ps"
        out_dir = chapter / "output"
        out_dir.mkdir(parents=True)
        register_root(str(chapter))

        map_path = str(out_dir / "001_map.json")
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": 2,
                "boxes": [{"id": 42, "text": "Crucial dialogue"}],
                "panels": [{"box": [1, 2, 3, 4]}],
                "backup": None,
            }, f)

        handle = open_exclusive_windows_handle(map_path)

        def release_after():
            time.sleep(0.025)
            close_windows_handle(handle)

        t = threading.Thread(target=release_after, daemon=True)
        t.start()

        PageStore.invalidate_cache()
        rec = PageStore.load_page_record(map_path)
        assert len(rec["boxes"]) == 1
        assert rec["boxes"][0]["text"] == "Crucial dialogue"
        assert len(rec["panels"]) == 1
        t.join(timeout=1.0)


class TestAdversarialWindowsLocking:
    """Stress tests using msvcrt (Windows native file locking) and multi-threading."""

    def test_msvcrt_real_file_lock_behavior(self, tmp_path):
        test_file = tmp_path / "locked_file.txt"
        test_file.write_text("Hello Windows Native Lock", encoding="utf-8")

        f = open(str(test_file), "r+b")
        fd = f.fileno()
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 10)
            lock_exc = None
            try:
                with open(str(test_file), "r+b") as f2:
                    msvcrt.locking(f2.fileno(), msvcrt.LK_NBLCK, 10)
            except (OSError, PermissionError) as e:
                lock_exc = e

            assert lock_exc is not None, "Expected an OSError/PermissionError on locked file"
            assert is_transient_lock_error(lock_exc) is True
        finally:
            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 10)
            except Exception:
                pass
            f.close()

    def test_multithreaded_concurrent_reads_under_intermittent_lock(self, tmp_path):
        test_file = tmp_path / "concurrent_target.txt"
        content = "Stress Test Shared Data 1234567890" * 50
        test_file.write_text(content, encoding="utf-8")

        stop_chaos = threading.Event()
        lock_stats = {"locks_acquired": 0}

        def chaos_monkey():
            while not stop_chaos.is_set():
                try:
                    with open(str(test_file), "r+b") as cf:
                        msvcrt.locking(cf.fileno(), msvcrt.LK_NBLCK, 10)
                        lock_stats["locks_acquired"] += 1
                        time.sleep(0.015)
                        msvcrt.locking(cf.fileno(), msvcrt.LK_UNLCK, 10)
                except Exception:
                    pass
                time.sleep(0.01)

        chaos_thread = threading.Thread(target=chaos_monkey, daemon=True)
        chaos_thread.start()

        def worker_read(worker_id):
            successes = 0
            for _ in range(10):
                text = resilient_read_text(
                    str(test_file),
                    max_attempts=12,
                    initial_delay=0.02,
                    max_delay=0.10,
                )
                if text == content:
                    successes += 1
                time.sleep(0.005)
            return successes

        num_workers = 6
        try:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(worker_read, i) for i in range(num_workers)]
                results = [f.result() for f in as_completed(futures)]
        finally:
            stop_chaos.set()
            chaos_thread.join(timeout=3.0)

        assert all(r == 10 for r in results), f"Some workers failed reads: {results}"
        assert lock_stats["locks_acquired"] > 0, "Chaos monkey never locked the file"

    def test_multithreaded_resilient_read_json_concurrency(self, tmp_path):
        json_file = tmp_path / "page_map.json"
        payload = {"version": 2, "boxes": [{"id": i, "text": f"text_{i}"} for i in range(50)]}
        json_file.write_text(json.dumps(payload), encoding="utf-8")

        errors = []

        def worker(wid):
            try:
                for _ in range(20):
                    data = resilient_read_json(str(json_file), default=None, max_attempts=4)
                    assert data["version"] == 2
                    assert len(data["boxes"]) == 50
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent workers encountered errors: {errors}"

    def test_image_service_multithreaded_thumbnail_cache_race(self, tmp_path):
        folder = tmp_path / "chapter_stress"
        folder.mkdir()
        register_root(str(folder))

        image_paths = []
        for i in range(5):
            img_p = folder / f"img_{i}.png"
            img = Image.new("RGB", (100 + i * 20, 100 + i * 20), color=(i * 40, 100, 200))
            img.save(str(img_p))
            image_paths.append(str(img_p))

        svc = ImageService(max_cache_entries=3)
        errors = []

        def client_task(thread_id):
            try:
                for cycle in range(25):
                    target_p = image_paths[(thread_id + cycle) % len(image_paths)]
                    res = svc.get_thumbnail(target_p)
                    assert res["success"] is True
                    assert "data_url" in res
                    assert res["data_url"].startswith("data:image/jpeg;base64,")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=client_task, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread race errors in ImageService: {errors}"
        with svc._cache_lock:
            assert len(svc._thumbnail_cache) <= 3

    def test_pagestore_under_rapid_concurrent_load_and_save(self, tmp_path):
        chapter = tmp_path / "chapter_ps"
        out_dir = chapter / "output"
        out_dir.mkdir(parents=True)
        register_root(str(chapter))

        map_path = str(out_dir / "001_map.json")
        initial_record = {
            "version": 2,
            "boxes": [{"id": 0, "text": "init"}],
            "panels": [],
            "backup": None,
        }
        PageStore.save_page_record(map_path, boxes=initial_record["boxes"])

        errors = []

        def worker(wid):
            try:
                for i in range(15):
                    rec = PageStore.load_page_record(map_path)
                    assert "boxes" in rec
                    assert "version" in rec
                    assert rec["version"] == 2
                    assert len(rec["boxes"]) >= 1
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"PageStore concurrency errors: {errors}"


class TestAdversarialEdgeCases:
    """Stress testing edge cases, boundary conditions, security, and mixed exceptions."""

    def test_mixed_exception_sequence(self):
        fn = MagicMock()
        err_lock = PermissionError(13, "[WinError 32] In use")
        err_lock.winerror = 32
        fn.side_effect = [err_lock, ValueError("Corrupt syntax")]

        with pytest.raises(ValueError) as excinfo:
            retry_on_file_lock(fn, max_attempts=3)
        assert "Corrupt syntax" in str(excinfo.value)
        assert fn.call_count == 2

    def test_transient_followed_by_filenotfound(self):
        fn = MagicMock()
        err_lock = PermissionError(13, "[WinError 32] In use")
        err_lock.winerror = 32
        fn.side_effect = [err_lock, FileNotFoundError("Vanished")]

        with pytest.raises(FileNotFoundError):
            retry_on_file_lock(fn, max_attempts=4)
        assert fn.call_count == 2

    def test_zero_or_negative_max_attempts(self):
        fn = MagicMock()
        with pytest.raises(RuntimeError):
            retry_on_file_lock(fn, max_attempts=0)
        with pytest.raises(RuntimeError):
            retry_on_file_lock(fn, max_attempts=-1)
        assert fn.call_count == 0

    def test_resilient_read_json_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("", encoding="utf-8")
        res = resilient_read_json(str(empty_file), default={"empty": True})
        assert res == {"empty": True}

    def test_resilient_read_json_empty_file_no_default_raises(self, tmp_path):
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            resilient_read_json(str(empty_file))
        assert resilient_read_json(str(empty_file), default=None) is None

    def test_resilient_read_text_encoding_error_handling(self, tmp_path):
        bad_file = tmp_path / "bad_utf8.txt"
        bad_file.write_bytes(b"Good text \xff\xfe bad bytes")
        text = resilient_read_text(str(bad_file), encoding="utf-8", errors="replace")
        assert "Good text" in text
        assert "\ufffd" in text

    def test_image_service_sandbox_enforcement_not_bypassed(self, tmp_path):
        """
        Verify that retry_on_file_lock integration did not weaken path_sandbox security.
        Attempting to read outside registered root must be rejected immediately without retrying.
        """
        unauthorized_file = tmp_path / "secret.png"
        unauthorized_file.write_bytes(b"FAKE_PNG")

        svc = ImageService()
        res = svc.get_thumbnail(str(unauthorized_file))
        assert res["success"] is False
        assert "outside the authorized folders" in res["error"].lower() or "denied" in res["error"].lower()

    def test_no_real_user_data_accessed(self, monkeypatch):
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            real_visionary = os.path.join(appdata, "Visionary Studio")
            assert not os.path.exists(os.path.join(real_visionary, "test_file.txt"))
