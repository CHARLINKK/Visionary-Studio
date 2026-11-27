import os
import pytest
from src.utils.fs_security import sanitize_filename, is_safe_filename, safe_join


def test_sanitize_filename_illegal_characters():
    assert sanitize_filename("Capítulo 01: O Início") == "Capítulo 01_ O Início"
    assert sanitize_filename('Nome com "aspas" e <tags>') == "Nome com _aspas_ e _tags_"
    assert sanitize_filename("Arquivo|Com|Barras/E\\Backslash") == "Arquivo_Com_Barras_E_Backslash"
    assert sanitize_filename("Pergunta? Asterisco*") == "Pergunta_ Asterisco_"


def test_sanitize_filename_trailing_dots_and_spaces():
    assert sanitize_filename("Capítulo 1. ") == "Capítulo 1"
    assert sanitize_filename("Capítulo 1...") == "Capítulo 1"
    assert sanitize_filename("   Espaços no início e fim   ") == "Espaços no início e fim"


def test_sanitize_filename_reserved_windows_names():
    assert sanitize_filename("CON") == "_CON_"
    assert sanitize_filename("con.txt") == "_con_.txt"
    assert sanitize_filename("aux.json") == "_aux_.json"
    assert sanitize_filename("NUL") == "_NUL_"
    assert sanitize_filename("com1.png") == "_com1_.png"
    assert sanitize_filename("lpt1.txt") == "_lpt1_.txt"


def test_sanitize_filename_max_length_preserves_extension():
    long_name = "A" * 300 + ".txt"
    sanitized = sanitize_filename(long_name, max_length=255)
    assert len(sanitized) <= 255
    assert sanitized.endswith(".txt")


def test_sanitize_filename_empty_or_invalid_fallback():
    assert sanitize_filename("") == "unnamed"
    assert sanitize_filename("   ") == "unnamed"
    assert sanitize_filename(None) == "unnamed"
    assert sanitize_filename("???", replacement="_") == "unnamed"
    assert sanitize_filename("???", fallback="capitulo") == "capitulo"


def test_is_safe_filename():
    assert is_safe_filename("Capítulo_01.txt") is True
    assert is_safe_filename("image.png") is True
    assert is_safe_filename("Capítulo: 01.txt") is False
    assert is_safe_filename("arquivo?.png") is False
    assert is_safe_filename("trailing. ") is False
    assert is_safe_filename("CON.txt") is False
    assert is_safe_filename("A" * 300) is False


def test_safe_join_within_boundary(tmp_path):
    base = str(tmp_path)
    res = safe_join(base, "capitulo_1", "pagina_01.png")
    assert res is not None
    assert res.startswith(base)


def test_safe_join_prevents_directory_traversal(tmp_path):
    base = str(tmp_path / "subfolder")
    os.makedirs(base, exist_ok=True)

    # Attempting to escape the base folder
    res = safe_join(base, "..", "secret.txt")
    assert res is None

    res2 = safe_join(base, "foo", "..", "..", "escape.png")
    assert res2 is None


def test_send_to_trash_removes_existing_file(tmp_path):
    from src.utils.fs_security import send_to_trash
    dummy = tmp_path / "page_to_delete.png"
    dummy.write_text("dummy image data")
    assert dummy.exists()

    success = send_to_trash(str(dummy))
    assert success is True
    assert not dummy.exists()


def test_send_to_trash_handles_non_existent_file(tmp_path):
    from src.utils.fs_security import send_to_trash
    ghost = tmp_path / "does_not_exist.png"
    assert send_to_trash(str(ghost)) is False


def test_send_to_trash_never_permanently_deletes_on_failure(tmp_path, monkeypatch):
    import ctypes
    from unittest.mock import MagicMock
    from src.utils.fs_security import send_to_trash

    protected_file = tmp_path / "important_page.png"
    protected_file.write_text("do not permanently delete", encoding="utf-8")

    # Simulate failure of both send2trash and Win32 SHFileOperationW (return code 124)
    monkeypatch.setitem(__import__("sys").modules, "send2trash", None)
    if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "shell32"):
        monkeypatch.setattr(ctypes.windll.shell32, "SHFileOperationW", MagicMock(return_value=124))

    with pytest.raises(RuntimeError, match="Exclusão física permanente bloqueada"):
        send_to_trash(str(protected_file))

    # File MUST still exist on disk!
    assert protected_file.exists()


def test_sync_json_from_script_preserves_multiline_dialogue(tmp_path):
    import json
    from src.api_services.library_script_manager import LibraryScriptManager

    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True)
    map_file = out_dir / "001_map.json"
    map_file.write_text(
        json.dumps([{"id": 1, "order": 1, "text": "Line one\nLine two", "translated_text": "Velho"}]),
        encoding="utf-8",
    )

    script_content = (
        "==================================================\n"
        "PAGINA 1: 001.PNG\n"
        "==================================================\n"
        "# [id: 1]\n"
        "[EN]: Line one\n"
        "Line two\n"
        "[BR]: Primeira linha da fala\n"
        "Segunda linha da fala\n"
        "Terceira linha!\n"
    )

    mgr = LibraryScriptManager()
    mgr.sync_json_from_script(str(tmp_path / "Cap01.txt"), script_content)

    updated = json.loads(map_file.read_text(encoding="utf-8"))
    boxes = updated["boxes"] if isinstance(updated, dict) else updated
    assert boxes[0]["translated_text"] == "Primeira linha da fala\nSegunda linha da fala\nTerceira linha!"


