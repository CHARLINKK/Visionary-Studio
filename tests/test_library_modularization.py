import os
import pytest
from unittest.mock import MagicMock

from src.api_services.library_scanner import LibraryScanner
from src.api_services.library_script_manager import LibraryScriptManager
from src.api_services.library_service import LibraryService


def test_library_scanner_filters_and_stats(tmp_path):
    """Valida filtros de scripts válidos e cálculo de estatísticas pelo LibraryScanner."""
    # 1. Filtros
    assert LibraryScanner.is_valid_script_txt("Capitulo 01.txt") is True
    assert LibraryScanner.is_valid_script_txt("Capitulo 01_letrista.txt") is False
    assert LibraryScanner.is_valid_script_txt("requirements.txt") is False
    assert LibraryScanner.is_valid_script_txt("_map_teste.txt") is False

    # 2. Estatísticas de balões
    test_file = tmp_path / "chapter.txt"
    test_file.write_text(
        "PAGINA 1: 01.png\n"
        "[1]: Olá mundo\n"
        "[2]: [PENDENTE]\n"
        "[PT]: Segunda página\n",
        encoding="utf-8"
    )
    stats = LibraryScanner.inspect_file_stats(str(test_file))
    assert stats["balloonCount"] == 3
    assert stats["pendingCount"] == 1
    assert stats["status"] == "pending"


def test_library_script_manager_export_formats(tmp_path):
    """Valida a exportação em TXT limpo e Word RTF pelo LibraryScriptManager."""
    mgr = LibraryScriptManager()
    script_file = tmp_path / "Capitulo_10.txt"
    script_file.write_text(
        "PAGINA 1: 01.png\n"
        "[BR] (Grito): Pare agora!\n"
        "[BR]: [PENDENTE]\n",
        encoding="utf-8"
    )

    # 1. Export Clean TXT
    res_txt = mgr.export_script(str(script_file), export_format="clean_txt")
    assert res_txt["success"] is True
    assert "Capitulo_10_limpo.txt" in res_txt["filename"]
    assert "ROTEIRO DE TRADUÇÃO: Capitulo_10" in res_txt["content"]
    assert "--- PÁGINA 1: 01.png ---" in res_txt["content"]
    assert "[1] (Grito) Pare agora!" in res_txt["content"]
    assert "[2] [TRADUÇÃO PENDENTE]" in res_txt["content"]

    # 2. Export RTF
    res_rtf = mgr.export_script(str(script_file), export_format="rtf")
    assert res_rtf["success"] is True
    assert "Capitulo_10_revisao.rtf" in res_rtf["filename"]
    assert r"{\rtf1" in res_rtf["content"]
    assert "Capitulo_10" in res_rtf["content"]


def test_library_service_facade_delegation(tmp_path):
    """Valida que a fachada LibraryService delega corretamente para Scanner e ScriptManager."""
    mock_scanner = MagicMock()
    mock_scanner.list_library_files.return_value = {"success": True, "files": []}
    mock_scanner.resolve_chapter_dir.return_value = str(tmp_path)

    mock_script_mgr = MagicMock()
    mock_script_mgr.read_library_file.return_value = {"success": True, "content": "Roteiro"}

    service = LibraryService(api_bridge=None, scanner=mock_scanner, script_manager=mock_script_mgr)

    # listLibraryFiles
    res_list = service.listLibraryFiles()
    assert res_list["success"] is True
    mock_scanner.list_library_files.assert_called_once()

    # readLibraryFile
    res_read = service.readLibraryFile(str(tmp_path / "c1.txt"))
    assert res_read["success"] is True
    assert res_read["content"] == "Roteiro"
    mock_script_mgr.read_library_file.assert_called_once()


def test_library_script_manager_delegation(tmp_path):
    """Valida a delegação canônica de resolução de diretório e reuso de VALID_IMAGE_EXTS."""
    assert LibraryScriptManager.VALID_IMAGE_EXTS == LibraryScanner.VALID_IMAGE_EXTS

    mock_scanner = MagicMock()
    mock_scanner.resolve_chapter_dir.return_value = "/canonical/chapter/dir"

    mgr = LibraryScriptManager(scanner=mock_scanner)
    resolved = mgr._resolve_dir("/some/path/cap1.txt")
    assert resolved == "/canonical/chapter/dir"
    mock_scanner.resolve_chapter_dir.assert_called_once_with("/some/path/cap1.txt")

    # Custom override function takes precedence
    custom_resolved = mgr._resolve_dir("/some/path/cap1.txt", custom_fn=lambda p: "/custom/dir")
    assert custom_resolved == "/custom/dir"

