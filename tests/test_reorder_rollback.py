import os
import json
import pytest
from unittest.mock import patch
from src.api_services.fs_service import FileSystemService
from src.domain.reorder_transaction import (
    execute_reorder,
    recover_reorder_if_needed,
    plan_reorder,
    write_journal,
    JOURNAL_FILENAME,
    safe_rename,
    _get_folder_lock,
)


@pytest.fixture
def fs():
    return FileSystemService()


def test_reorder_full_success_with_all_associated(fs, tmp_path):
    """
    Test a complete, successful reorder of pages with associated files in:
    - Root (.json)
    - output/
    - output/crops/
    """
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    out_dir = chapter / "output"
    out_dir.mkdir()
    crops_dir = out_dir / "crops"
    crops_dir.mkdir()

    # Original files for Page 10
    (chapter / "10.jpg").write_text("img10")
    (chapter / "10_map.json").write_text("map10")
    (chapter / "10.json").write_text("json10")
    (out_dir / "10.png").write_text("out10")
    (crops_dir / "10_balao_1.png").write_text("crop10")

    # Original files for Page 20
    (chapter / "20.jpg").write_text("img20")
    (chapter / "20_map.json").write_text("map20")
    (out_dir / "20.png").write_text("out20")

    # Script file that must NEVER be renamed
    script_txt = chapter / "chapter_script.txt"
    script_txt.write_text("roteiro de texto original")

    # Desired order: 20 becomes 001, 10 becomes 002
    files = [
        {"name": "20.jpg", "path": str(chapter / "20.jpg")},
        {"name": "10.jpg", "path": str(chapter / "10.jpg")}
    ]

    res = fs.reorder_pages(str(chapter), files)
    assert res["success"] is True

    # Journal must be deleted
    assert not (chapter / JOURNAL_FILENAME).exists()

    # Page 20 -> 001
    assert (chapter / "001.jpg").read_text() == "img20"
    assert (chapter / "001_map.json").read_text() == "map20"
    assert (out_dir / "001.png").read_text() == "out20"

    # Page 10 -> 002
    assert (chapter / "002.jpg").read_text() == "img10"
    assert (chapter / "002_map.json").read_text() == "map10"
    assert (chapter / "002.json").read_text() == "json10"
    assert (out_dir / "002.png").read_text() == "out10"
    assert (crops_dir / "002_balao_1.png").read_text() == "crop10"

    # Script remains untouched
    assert script_txt.exists()


def test_reorder_swap_collision_free(fs, tmp_path):
    """
    Test direct swap: 001 -> 002 and 002 -> 001 where targets coincide with original names.
    """
    chapter = tmp_path / "chapter_swap"
    chapter.mkdir()

    (chapter / "001.jpg").write_text("alpha")
    (chapter / "002.jpg").write_text("beta")

    files = [
        {"name": "002.jpg", "path": str(chapter / "002.jpg")},
        {"name": "001.jpg", "path": str(chapter / "001.jpg")}
    ]

    res = fs.reorder_pages(str(chapter), files)
    assert res["success"] is True

    assert (chapter / "001.jpg").read_text() == "beta"
    assert (chapter / "002.jpg").read_text() == "alpha"
    assert not (chapter / JOURNAL_FILENAME).exists()


def test_reorder_foreign_file_collision_rejection(fs, tmp_path):
    """
    Pre-flight safety check: if an unexpected foreign file occupies a target path,
    the operation is rejected before renaming any file.
    """
    chapter = tmp_path / "chapter_foreign"
    chapter.mkdir()

    (chapter / "pageA.jpg").write_text("A")
    # Foreign file that is not in the reorder list
    (chapter / "001.jpg").write_text("FOREIGN_EXISTING_FILE")

    files = [
        {"name": "pageA.jpg", "path": str(chapter / "pageA.jpg")}
    ]

    res = fs.reorder_pages(str(chapter), files)
    assert res["success"] is False
    assert "já existe e não faz parte da reordenação" in res["error"]

    # Files must be untouched
    assert (chapter / "pageA.jpg").read_text() == "A"
    assert (chapter / "001.jpg").read_text() == "FOREIGN_EXISTING_FILE"
    assert not (chapter / JOURNAL_FILENAME).exists()


def test_reorder_rollback_on_phase1_failure(fs, tmp_path):
    """
    Simulate an error during Phase 1 (Original -> Temp).
    All files already moved to temp must be restored to original names.
    """
    chapter = tmp_path / "chapter_fail_p1"
    chapter.mkdir()

    (chapter / "10.jpg").write_text("content10")
    (chapter / "10_map.json").write_text("map10")
    (chapter / "20.jpg").write_text("content20")
    (chapter / "30.jpg").write_text("content30")

    files = [
        {"name": "10.jpg", "path": str(chapter / "10.jpg")},
        {"name": "20.jpg", "path": str(chapter / "20.jpg")},
        {"name": "30.jpg", "path": str(chapter / "30.jpg")}
    ]

    original_safe_rename = safe_rename
    call_count = 0

    def mock_safe_rename(src, dst):
        nonlocal call_count
        call_count += 1
        # Fail when trying to move the 2nd page (20.jpg)
        if "20.jpg" in src:
            raise PermissionError("Simulated disk lock on 20.jpg")
        return original_safe_rename(src, dst)

    with patch("src.domain.reorder_transaction.safe_rename", side_effect=mock_safe_rename):
        res = fs.reorder_pages(str(chapter), files)

    assert res["success"] is False
    assert "Simulated disk lock" in res["error"]

    # Rollback must restore 10.jpg and its map, and leave 20.jpg and 30.jpg intact
    assert (chapter / "10.jpg").exists()
    assert (chapter / "10.jpg").read_text() == "content10"
    assert (chapter / "10_map.json").exists()
    assert (chapter / "10_map.json").read_text() == "map10"
    assert (chapter / "20.jpg").exists()
    assert (chapter / "30.jpg").exists()

    # No leftover temp files or journal
    assert not any(f.startswith("__temp_visionary") for f in os.listdir(chapter))
    assert not (chapter / JOURNAL_FILENAME).exists()


def test_reorder_rollback_on_phase2_failure(fs, tmp_path):
    """
    Simulate an error during Phase 2 (Temp -> Final).
    Some files reached final, some are still at temp.
    Rollback must return ALL files back to their original names.
    """
    chapter = tmp_path / "chapter_fail_p2"
    chapter.mkdir()

    (chapter / "A.jpg").write_text("contentA")
    (chapter / "A_map.json").write_text("mapA")
    (chapter / "B.jpg").write_text("contentB")
    (chapter / "C.jpg").write_text("contentC")

    files = [
        {"name": "A.jpg", "path": str(chapter / "A.jpg")},
        {"name": "B.jpg", "path": str(chapter / "B.jpg")},
        {"name": "C.jpg", "path": str(chapter / "C.jpg")}
    ]

    original_safe_rename = safe_rename

    def mock_safe_rename(src, dst):
        # Detect start of Phase 2: source starts with __temp_visionary and dst is sequential (001.jpg)
        if "__temp_visionary" in src and "002.jpg" in dst:
            raise OSError("Simulated I/O failure during Phase 2 on file 002")
        return original_safe_rename(src, dst)

    with patch("src.domain.reorder_transaction.safe_rename", side_effect=mock_safe_rename):
        res = fs.reorder_pages(str(chapter), files)

    assert res["success"] is False
    assert "Simulated I/O failure" in res["error"]

    # Rollback must restore original files
    assert (chapter / "A.jpg").exists()
    assert (chapter / "A.jpg").read_text() == "contentA"
    assert (chapter / "A_map.json").exists()
    assert (chapter / "A_map.json").read_text() == "mapA"
    assert (chapter / "B.jpg").exists()
    assert (chapter / "B.jpg").read_text() == "contentB"
    assert (chapter / "C.jpg").exists()
    assert (chapter / "C.jpg").read_text() == "contentC"

    # No temp files, no partial 001 files, no journal
    assert not (chapter / "001.jpg").exists()
    assert not any(f.startswith("__temp_visionary") for f in os.listdir(chapter))
    assert not (chapter / JOURNAL_FILENAME).exists()


def test_crash_recovery_during_phase1(fs, tmp_path):
    """
    Simulate app crash / SIGKILL midway through Phase 1:
    - Plan and journal are on disk.
    - File 1 was renamed to temp.
    - File 2 is still at original path.
    Calling recover_reorder_if_needed (or list_directory) must rollback to original.
    """
    chapter = tmp_path / "chapter_crash_p1"
    chapter.mkdir()

    (chapter / "01.jpg").write_text("one")
    (chapter / "02.jpg").write_text("two")

    files = [
        {"name": "01.jpg", "path": str(chapter / "01.jpg")},
        {"name": "02.jpg", "path": str(chapter / "02.jpg")}
    ]

    plan = plan_reorder(str(chapter), files)
    write_journal(str(chapter), plan)

    # Simulate crash: only entry 0 was moved to temp
    entry0 = plan["entries"][0]
    safe_rename(entry0["original"], entry0["temp"])

    assert os.path.exists(entry0["temp"])
    assert not os.path.exists(entry0["original"])
    assert (chapter / JOURNAL_FILENAME).exists()

    # App restarts, user opens directory
    res = fs.list_directory(str(chapter))
    assert res["success"] is True

    # Both files must be back at original paths
    assert (chapter / "01.jpg").read_text() == "one"
    assert (chapter / "02.jpg").read_text() == "two"
    assert not (chapter / JOURNAL_FILENAME).exists()


def test_crash_recovery_during_phase2(fs, tmp_path):
    """
    Simulate app crash / SIGKILL midway through Phase 2:
    - Phase 1 completed (all files at temp).
    - Entry 0 moved to final.
    - Entry 1 is still at temp.
    Calling recover_reorder_if_needed must rollback all files to original.
    """
    chapter = tmp_path / "chapter_crash_p2"
    chapter.mkdir()

    (chapter / "origA.jpg").write_text("dataA")
    (chapter / "origB.jpg").write_text("dataB")

    files = [
        {"name": "origA.jpg", "path": str(chapter / "origA.jpg")},
        {"name": "origB.jpg", "path": str(chapter / "origB.jpg")}
    ]

    plan = plan_reorder(str(chapter), files)
    write_journal(str(chapter), plan)

    # Move both to temp (Phase 1)
    for e in plan["entries"]:
        safe_rename(e["original"], e["temp"])

    # Move only entry 0 to final (mid-Phase 2 crash)
    safe_rename(plan["entries"][0]["temp"], plan["entries"][0]["final"])

    assert os.path.exists(plan["entries"][0]["final"])
    assert os.path.exists(plan["entries"][1]["temp"])
    assert (chapter / JOURNAL_FILENAME).exists()

    # Recovery
    recovery_res = recover_reorder_if_needed(str(chapter))
    assert recovery_res["recovered"] is True
    assert recovery_res["action"] == "rolled_back"

    assert (chapter / "origA.jpg").read_text() == "dataA"
    assert (chapter / "origB.jpg").read_text() == "dataB"
    assert not (chapter / "001.jpg").exists()
    assert not (chapter / JOURNAL_FILENAME).exists()


def test_crash_recovery_after_phase2_completed(fs, tmp_path):
    """
    Simulate app crash after all files reached final, but before journal was removed:
    Recovery detects all files are at final and finalizes without rolling back.
    """
    chapter = tmp_path / "chapter_crash_done"
    chapter.mkdir()

    (chapter / "page1.jpg").write_text("one")
    (chapter / "page2.jpg").write_text("two")

    files = [
        {"name": "page1.jpg", "path": str(chapter / "page1.jpg")},
        {"name": "page2.jpg", "path": str(chapter / "page2.jpg")}
    ]

    plan = plan_reorder(str(chapter), files)
    write_journal(str(chapter), plan)

    # Move to temp and then directly to final
    for e in plan["entries"]:
        safe_rename(e["original"], e["temp"])
        safe_rename(e["temp"], e["final"])

    assert (chapter / JOURNAL_FILENAME).exists()
    assert (chapter / "001.jpg").exists()
    assert (chapter / "002.jpg").exists()

    recovery_res = recover_reorder_if_needed(str(chapter))
    assert recovery_res["recovered"] is True
    assert recovery_res["action"] == "finalized"

    # Journal cleaned, final files preserved
    assert not (chapter / JOURNAL_FILENAME).exists()
    assert (chapter / "001.jpg").read_text() == "one"
    assert (chapter / "002.jpg").read_text() == "two"


def test_reorder_prefix_disambiguation_1_and_1_A(fs, tmp_path):
    """
    Ensure files for page '1_A' are not incorrectly captured by page '1'.
    """
    chapter = tmp_path / "chapter_disambig"
    chapter.mkdir()
    out_dir = chapter / "output"
    out_dir.mkdir()

    # Page 1
    (chapter / "1.jpg").write_text("page1")
    (chapter / "1_map.json").write_text("map1")
    (out_dir / "1.png").write_text("out1")

    # Page 1_A (split page)
    (chapter / "1_A.jpg").write_text("page1_A")
    (chapter / "1_A_map.json").write_text("map1_A")
    (out_dir / "1_A.png").write_text("out1_A")

    # Order: put 1_A first (001), and 1 second (002)
    files = [
        {"name": "1_A.jpg", "path": str(chapter / "1_A.jpg")},
        {"name": "1.jpg", "path": str(chapter / "1.jpg")}
    ]

    res = fs.reorder_pages(str(chapter), files)
    assert res["success"] is True

    # 001 must have 1_A contents
    assert (chapter / "001.jpg").read_text() == "page1_A"
    assert (chapter / "001_map.json").read_text() == "map1_A"
    assert (out_dir / "001.png").read_text() == "out1_A"

    # 002 must have 1 contents
    assert (chapter / "002.jpg").read_text() == "page1"
    assert (chapter / "002_map.json").read_text() == "map1"
    assert (out_dir / "002.png").read_text() == "out1"


def test_safe_rename_retry_on_transient_error(tmp_path):
    """
    Verify that safe_rename retries on transient PermissionError and succeeds when lock releases.
    """
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hello")

    attempts = 0
    orig_replace = os.replace

    def flaky_replace(s, d):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("Transient lock")
        return orig_replace(s, d)

    with patch("os.replace", side_effect=flaky_replace):
        safe_rename(str(src), str(dst), max_retries=5, retry_delay=0.01)

    assert dst.read_text() == "hello"
    assert attempts == 3


def test_reorder_cross_folder_boundary_rejection(fs, tmp_path):
    """
    Ensure files outside folder_path are strictly rejected.
    """
    chapter = tmp_path / "chapter_main"
    chapter.mkdir()
    other_folder = tmp_path / "chapter_other"
    other_folder.mkdir()

    (other_folder / "rogue.jpg").write_text("rogue")

    files = [
        {"name": "rogue.jpg", "path": str(other_folder / "rogue.jpg")}
    ]

    res = fs.reorder_pages(str(chapter), files)
    assert res["success"] is False
    assert "não pertence à pasta do capítulo" in res["error"]


def test_reorder_windows_case_insensitivity(fs, tmp_path):
    """
    Ensure case variations on Windows paths do not trigger false positive collision errors.
    """
    chapter = tmp_path / "chapter_case"
    chapter.mkdir()

    (chapter / "001.JPG").write_text("one")
    (chapter / "002.JPG").write_text("two")

    # Pass paths with lowercase extension
    files = [
        {"name": "002.jpg", "path": str(chapter / "002.JPG")},
        {"name": "001.jpg", "path": str(chapter / "001.JPG")}
    ]

    res = fs.reorder_pages(str(chapter), files)
    assert res["success"] is True


def test_reorder_concurrent_call_lock(fs, tmp_path):
    """
    Verify that concurrent calls on the same chapter folder are safely rejected with an error.
    """
    chapter = tmp_path / "chapter_concurrent"
    chapter.mkdir()
    (chapter / "01.jpg").write_text("1")

    files = [{"name": "01.jpg", "path": str(chapter / "01.jpg")}]

    lock = _get_folder_lock(str(chapter))
    lock.acquire()
    try:
        res = fs.reorder_pages(str(chapter), files)
        assert res["success"] is False
        assert "Uma reordenação já está em andamento" in res["error"]
    finally:
        lock.release()


def test_safe_rename_readonly_attribute(tmp_path):
    """
    Verify that safe_rename can handle and strip Windows ReadOnly file attributes.
    """
    import stat
    src = tmp_path / "readonly_src.txt"
    dst = tmp_path / "readonly_dst.txt"
    src.write_text("locked")

    # Set Read-Only
    os.chmod(str(src), stat.S_IREAD)

    safe_rename(str(src), str(dst))
    assert dst.read_text() == "locked"
    assert not src.exists()
