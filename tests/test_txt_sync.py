import os
import json
import tempfile
import shutil
import pytest
from src.utils.txt_sync import sync_chapter_txt

@pytest.fixture
def temp_chapter():
    temp_dir = tempfile.mkdtemp(prefix="test_chapter_")
    out_dir = os.path.join(temp_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    yield temp_dir, out_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_first_ocr_genesis(temp_chapter):
    """Test that .txt is born immediately on 1st OCR with [EN] and [BR]: [PENDENTE]."""
    temp_dir, out_dir = temp_chapter
    
    # Simulate page 1 with raw OCR
    with open(os.path.join(temp_dir, "001.png"), "wb") as f:
        f.write(b"dummy")

    map_p1 = [
        {"id": 1, "text_clean": "Hey Harima-kun, watch out!", "is_sfx": False},
        {"id": 2, "text_clean": "What is that?", "is_sfx": False}
    ]
    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump(map_p1, f)

    res = sync_chapter_txt(temp_dir, "Chapter_01")
    assert res["success"] is True
    assert res["pages_count"] == 1
    assert res["balloons_count"] == 2
    assert res["translated_count"] == 0

    local_txt = os.path.join(temp_dir, "Chapter_01.txt")
    assert os.path.exists(local_txt)

    with open(local_txt, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PAGINA 1: 001.PNG" in content
    assert "[EN]: Hey Harima-kun, watch out!" in content
    assert "[BR]: [PENDENTE]" in content

def test_incremental_auto_merge_across_pages(temp_chapter):
    """Test incremental merge: adding page 2 later preserves order and consolidates."""
    temp_dir, out_dir = temp_chapter
    
    # Create page 1 and page 2
    for p in ["001.png", "002.png"]:
        with open(os.path.join(temp_dir, p), "wb") as f:
            f.write(b"dummy")

    # Page 1 has OCR and translation
    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text_clean": "Hello!", "translated_text": "Olá!", "is_sfx": False}], f)

    # Page 2 has only OCR for now
    with open(os.path.join(out_dir, "002_map.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text_clean": "Good morning!", "is_sfx": False}], f)

    res = sync_chapter_txt(temp_dir, "Chapter_02")
    assert res["success"] is True
    assert res["pages_count"] == 2
    assert res["balloons_count"] == 2
    assert res["translated_count"] == 1

    local_txt = os.path.join(temp_dir, "Chapter_02.txt")
    with open(local_txt, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify natural page ordering
    p1_pos = content.find("PAGINA 1: 001.PNG")
    p2_pos = content.find("PAGINA 2: 002.PNG")
    assert p1_pos != -1 and p2_pos != -1
    assert p1_pos < p2_pos
    assert "[BR]: Olá!" in content
    assert "[BR]: [PENDENTE]" in content

def test_studio_live_edit_updates_txt(temp_chapter):
    """Test that changing text in JSON immediately reflects in the synced .txt."""
    temp_dir, out_dir = temp_chapter

    with open(os.path.join(temp_dir, "001.png"), "wb") as f:
        f.write(b"dummy")

    json_path = os.path.join(out_dir, "001_map.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text_clean": "Old Text", "translated_text": "Texto Velho", "is_sfx": False}], f)

    sync_chapter_txt(temp_dir, "Chapter_03")

    # Simulate user editing text in Studio
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text_clean": "Edited Original", "translated_text": "Tradução Perfeita", "is_sfx": False}], f)

    sync_chapter_txt(temp_dir, "Chapter_03")

    local_txt = os.path.join(temp_dir, "Chapter_03.txt")
    with open(local_txt, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Edited Original" in content
    assert "Tradução Perfeita" in content
    assert "Texto Velho" not in content

def test_sfx_exclusion(temp_chapter):
    """Test that pure sound effects are excluded from dialogue script."""
    temp_dir, out_dir = temp_chapter

    with open(os.path.join(temp_dir, "001.png"), "wb") as f:
        f.write(b"dummy")

    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump([
            {"id": 1, "text_clean": "Dialogue", "translated_text": "Diálogo", "is_sfx": False},
            {"id": 2, "text_clean": "*BOOM*", "translated_text": "*CABUM*", "is_sfx": True}
        ], f)

    sync_chapter_txt(temp_dir, "Chapter_04")

    local_txt = os.path.join(temp_dir, "Chapter_04.txt")
    with open(local_txt, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Diálogo" in content
    assert "*BOOM*" not in content

def test_library_service_scans_active_chapter_and_portable_folder(temp_chapter):
    """Test that LibraryService detects .txt files directly in the active chapter folder."""
    temp_dir, out_dir = temp_chapter
    from src.api_services.library_service import LibraryService

    # Create dummy chapter .txt in the active folder
    local_txt = os.path.join(temp_dir, "My_Manga_Cap01.txt")
    with open(local_txt, "w", encoding="utf-8") as f:
        f.write("# VISIONARY STUDIO - TEST ROTEIRO\nPAGINA 1: 001.PNG\n[EN]: Hello\n[BR]: Olá")

    # Sibling chapter in the parent directory
    parent_dir = os.path.dirname(temp_dir)
    sibling_dir = os.path.join(parent_dir, "Chapter_02")
    os.makedirs(sibling_dir, exist_ok=True)
    sibling_txt = os.path.join(sibling_dir, "Chapter_02.txt")
    with open(sibling_txt, "w", encoding="utf-8") as f:
        f.write("# Sibling chapter")

    # Obsolete letrista txt that should be ignored
    letrista_txt = os.path.join(temp_dir, "My_Manga_Cap01_letrista.txt")
    with open(letrista_txt, "w", encoding="utf-8") as f:
        f.write("# Obsolete letrista")

    class MockBridge:
        def __init__(self, path):
            self.current_path = path

    mock_bridge = MockBridge(temp_dir)
    service = LibraryService(api_bridge=mock_bridge)

    result = service.listLibraryFiles()
    assert result["success"] is True
    files = result["files"]
    names = [f["name"] for f in files]
    
    # Should find local and sibling chapters, while ignoring _letrista.txt
    assert "My_Manga_Cap01.txt" in names
    assert "Chapter_02.txt" in names
    assert "My_Manga_Cap01_letrista.txt" not in names

    found = [f for f in files if f["name"] == "My_Manga_Cap01.txt"]
    assert len(found) == 1
    assert found[0]["path"] == local_txt

    # Test reading content
    read_res = service.readLibraryFile(found[0]["path"])
    assert read_res["success"] is True
    assert "Olá" in read_res["content"]

def test_single_consolidated_script_generation(temp_chapter):
    """Valida a geração de apenas 1 roteiro consolidado {chapter}.txt e limpeza de _letrista.txt."""
    temp_dir, out_dir = temp_chapter

    with open(os.path.join(temp_dir, "001.png"), "wb") as f:
        f.write(b"dummy")

    map_p1 = [
        {"id": 1, "text_clean": "Watch out!", "translated_text": "Cuidado!", "is_sfx": False},
        {"id": 2, "text_clean": "He's fast...", "translated_text": "Ele é rápido...", "type": "thought", "is_sfx": False}
    ]
    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump(map_p1, f)

    # Simular a presença de um arquivo antigo _letrista.txt
    old_let_path = os.path.join(temp_dir, "Capitulo_10_letrista.txt")
    with open(old_let_path, "w", encoding="utf-8") as f:
        f.write("antigo letrista obsoleto")
    assert os.path.exists(old_let_path)

    res = sync_chapter_txt(temp_dir, "Capitulo_10")
    assert res["success"] is True

    # 1. Arquivo único consolidado
    rev_path = os.path.join(temp_dir, "Capitulo_10.txt")
    assert os.path.exists(rev_path)
    with open(rev_path, "r", encoding="utf-8") as f:
        rev_content = f.read()
    assert "[EN]: Watch out!" in rev_content
    assert "[BR]: Cuidado!" in rev_content
    assert "[BR] (PENSAMENTO): Ele é rápido..." in rev_content

    # 2. Arquivo letrista deve ter sido excluído/limpo
    assert not os.path.exists(old_let_path)
    assert "letrista_txt" not in res or res.get("letrista_txt") is None

def test_empty_ocr_balloons_preserved(temp_chapter):
    """Test that balloons detected by YOLO with no text are preserved as [PENDENTE] and not dropped."""
    temp_dir, out_dir = temp_chapter

    for p in ["001.png", "002.png"]:
        with open(os.path.join(temp_dir, p), "wb") as f:
            f.write(b"dummy")

    # Page 1 has 2 balloons with empty text (only bounding boxes from YOLO)
    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump([
            {"id": 1, "x1": 10, "y1": 10, "x2": 50, "y2": 50, "text": "", "translated_text": ""},
            {"id": 2, "x1": 60, "y1": 10, "x2": 90, "y2": 50, "text": "", "translated_text": ""}
        ], f)

    # Page 2 has 1 balloon with translated text
    with open(os.path.join(out_dir, "002_map.json"), "w", encoding="utf-8") as f:
        json.dump([
            {"id": 1, "text": "Hi", "translated_text": "Oi", "is_sfx": False}
        ], f)

    res = sync_chapter_txt(temp_dir, "Chapter_Empty_Preserve")
    assert res["success"] is True
    assert res["pages_count"] == 2
    assert res["balloons_count"] == 3
    assert res["translated_count"] == 1

    local_txt = os.path.join(temp_dir, "Chapter_Empty_Preserve.txt")
    assert os.path.exists(local_txt)
    with open(local_txt, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PAGINA 1: 001.PNG" in content
    assert "PAGINA 2: 002.PNG" in content
    assert "[Sem texto original detectado]" in content
    assert "[BR]: [PENDENTE]" in content
    assert "[BR]: Oi" in content

def test_path_normalization_image_and_output(temp_chapter):
    """Test that passing an image file path or the 'output' directory works seamlessly."""
    temp_dir, out_dir = temp_chapter

    img_file = os.path.join(temp_dir, "001.png")
    with open(img_file, "wb") as f:
        f.write(b"dummy")

    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text": "Hello", "translated_text": "Olá"}], f)

    # Pass image file path directly
    res1 = sync_chapter_txt(img_file)
    assert res1["success"] is True
    assert res1["balloons_count"] == 1

    # Pass output folder directly
    res2 = sync_chapter_txt(out_dir)
    assert res2["success"] is True
    assert res2["balloons_count"] == 1

def test_concurrent_sync_lock(temp_chapter):
    """Test that concurrent writes from multiple threads do not crash or corrupt the .txt file."""
    import concurrent.futures
    temp_dir, out_dir = temp_chapter

    with open(os.path.join(temp_dir, "001.png"), "wb") as f:
        f.write(b"dummy")

    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text": "Concur", "translated_text": "Concorrente"}], f)

    def worker():
        return sync_chapter_txt(temp_dir, "Chapter_Concurrent")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker) for _ in range(20)]
        results = [f.result() for f in futures]

    for r in results:
        assert r["success"] is True
        assert r["balloons_count"] == 1

    local_txt = os.path.join(temp_dir, "Chapter_Concurrent.txt")
    assert os.path.exists(local_txt)
    with open(local_txt, "r", encoding="utf-8") as f:
        content = f.read()
    assert "[BR]: Concorrente" in content

def test_silent_pages_without_balloons_are_preserved_in_exact_order(temp_chapter):
    """Test that pages without balloons (silent scenes, double spreads) are never skipped and preserve exact 1:1 numbering."""
    temp_dir, out_dir = temp_chapter

    # Create 3 pages: 001.png, 002.png (silent / empty map), 003.png
    for p in ["001.png", "002.png", "003.png"]:
        with open(os.path.join(temp_dir, p), "wb") as f:
            f.write(b"dummy")

    # Page 1 has balloons
    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text_clean": "First page text", "translated_text": "Texto pagina 1", "is_sfx": False}], f)

    # Page 2 has empty json (silent page)
    with open(os.path.join(out_dir, "002_map.json"), "w", encoding="utf-8") as f:
        json.dump([], f)

    # Page 3 has balloons
    with open(os.path.join(out_dir, "003_map.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text_clean": "Third page text", "translated_text": "Texto pagina 3", "is_sfx": False}], f)

    res = sync_chapter_txt(temp_dir, "Chapter_Silent")
    assert res["success"] is True
    assert res["pages_count"] == 3
    assert res["balloons_count"] == 2

    local_txt = os.path.join(temp_dir, "Chapter_Silent.txt")
    assert os.path.exists(local_txt)
    with open(local_txt, "r", encoding="utf-8") as f:
        content = f.read()

    # All three pages must exist in exact order
    assert "PAGINA 1: 001.PNG" in content
    assert "PAGINA 2: 002.PNG" in content
    assert "PAGINA 3: 003.PNG" in content

    p1_pos = content.find("PAGINA 1: 001.PNG")
    p2_pos = content.find("PAGINA 2: 002.PNG")
    p3_pos = content.find("PAGINA 3: 003.PNG")
    assert p1_pos < p2_pos < p3_pos

    # Silent page contains clear indicator
    assert "[Página sem falas / Sem texto detectado]" in content

def test_library_service_auto_sync_on_missing_pages(temp_chapter):
    """Test that readLibraryFile auto-resyncs when it detects fewer pages in script than images in directory."""
    from src.api_services.library_service import LibraryService

    temp_dir, out_dir = temp_chapter

    for p in ["001.png", "002.png"]:
        with open(os.path.join(temp_dir, p), "wb") as f:
            f.write(b"dummy")

    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text_clean": "Page 1", "translated_text": "Pagina 1"}], f)
    with open(os.path.join(out_dir, "002_map.json"), "w", encoding="utf-8") as f:
        json.dump([], f)

    # Simulate an outdated script that only contains Page 1
    script_path = os.path.join(temp_dir, "Chapter_Test.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("PAGINA 1: 001.PNG\n[BR]: Pagina 1\n")

    svc = LibraryService()
    read_res = svc.readLibraryFile(script_path)
    assert read_res["success"] is True
    # Auto-sync should have refreshed the file to include PAGINA 2
    assert "PAGINA 1: 001.PNG" in read_res["content"]
    assert "PAGINA 2: 002.PNG" in read_res["content"]


def test_txt_sync_with_illegal_windows_filename(temp_chapter):
    """Test that chapter names with illegal Windows characters (: ? * etc.) are safely sanitized without OSError."""
    temp_dir, out_dir = temp_chapter

    img_file = os.path.join(temp_dir, "001.png")
    with open(img_file, "wb") as f:
        f.write(b"dummy")

    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text": "Hi", "translated_text": "Oi"}], f)

    res = sync_chapter_txt(temp_dir, chapter_name="Capítulo 01: O Início? (Especial*)")
    assert res["success"] is True
    assert os.path.exists(res["path"])
    base = os.path.basename(res["path"])
    assert ":" not in base
    assert "?" not in base
    assert "*" not in base


def test_deterministic_id_anchoring_in_script_emission(temp_chapter):
    """Testa se o sync_chapter_txt gera âncoras # [id: <id>] para cada balão de diálogo."""
    temp_dir, out_dir = temp_chapter

    img_file = os.path.join(temp_dir, "001.png")
    with open(img_file, "wb") as f:
        f.write(b"dummy")

    map_data = [
        {"id": "b_101", "text": "Primeira fala", "translated_text": "Primeira tradução", "is_sfx": False},
        {"id": "b_102", "text": "Segunda fala", "translated_text": "Segunda tradução", "is_sfx": False}
    ]
    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    res = sync_chapter_txt(temp_dir, "Cap_Anchors")
    assert res["success"] is True

    with open(res["path"], "r", encoding="utf-8") as f:
        content = f.read()

    assert "# [id: b_101]" in content
    assert "# [id: b_102]" in content
    assert "[EN]: Primeira fala" in content
    assert "[BR]: Primeira tradução" in content


def test_two_way_sync_preserves_duplicate_texts_and_reordered_blocks(temp_chapter):
    """
    Testa se a sincronização bidirecional do script TXT para o JSON de mapa
    reconcilia perfeitamente balões com textos idênticos e blocos reordenados
    através de âncoras de ID determinísticas.
    """
    from src.api_services.library_service import LibraryService

    temp_dir, out_dir = temp_chapter

    img_file = os.path.join(temp_dir, "001.png")
    with open(img_file, "wb") as f:
        f.write(b"dummy")

    # Dois balões com o mesmo texto original "..."
    map_data = [
        {"id": "box_first", "text": "...", "translated_text": "Tradução 1", "is_sfx": False},
        {"id": "box_second", "text": "...", "translated_text": "Tradução 2", "is_sfx": False}
    ]
    map_file = os.path.join(out_dir, "001_map.json")
    with open(map_file, "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    script_path = os.path.join(temp_dir, "Cap_Dup.txt")
    # Simula edição manual externa onde a ordem dos blocos foi invertida no Bloco de Notas:
    # O box_second aparece antes do box_first e os textos foram alterados
    inverted_content = (
        "==================================================\n"
        "PAGINA 1: 001.PNG\n"
        "==================================================\n\n"
        "# [id: box_second]\n"
        "[EN]: ...\n"
        "[BR]: Novo texto do segundo balão\n\n"
        "# [id: box_first]\n"
        "[EN]: ...\n"
        "[BR]: Novo texto do primeiro balão\n\n"
    )

    class MockBridge:
        def __init__(self, path):
            self.current_path = path

    svc = LibraryService(api_bridge=MockBridge(temp_dir))
    save_res = svc.saveLibraryFile(script_path, inverted_content)
    assert save_res["success"] is True

    from src.domain.page_store import PageStore
    # Valida que o _map.json recebeu as traduções corretas por ID, sem contaminação cruzada
    with open(map_file, "r", encoding="utf-8") as f:
        saved_boxes = PageStore.extract_boxes(json.load(f))

    b_first = next(b for b in saved_boxes if b["id"] == "box_first")
    b_second = next(b for b in saved_boxes if b["id"] == "box_second")

    assert b_first["translated_text"] == "Novo texto do primeiro balão"
    assert b_second["translated_text"] == "Novo texto do segundo balão"


def test_update_page_map_balloon_with_explicit_id(temp_chapter):
    """Valida update_page_map_balloon localizando exatamente o balão pelo balloon_id."""
    from src.api_services.library_service import LibraryService
    from src.domain.page_store import PageStore

    temp_dir, out_dir = temp_chapter

    img_file = os.path.join(temp_dir, "001.png")
    with open(img_file, "wb") as f:
        f.write(b"dummy")

    map_data = [
        {"id": "b_alpha", "text": "Same text", "translated_text": "Old 1", "is_sfx": False},
        {"id": "b_beta", "text": "Same text", "translated_text": "Old 2", "is_sfx": False}
    ]
    map_file = os.path.join(out_dir, "001_map.json")
    with open(map_file, "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    svc = LibraryService()
    # Atualiza especificamente b_beta pelo ID
    res = svc._update_page_map_balloon(temp_dir, "001.png", balloon_index=0, new_text="Updated Beta", original_text="Same text", balloon_id="b_beta")
    assert res["success"] is True

    with open(map_file, "r", encoding="utf-8") as f:
        saved_boxes = PageStore.extract_boxes(json.load(f))

    b_alpha = next(b for b in saved_boxes if b["id"] == "b_alpha")
    b_beta = next(b for b in saved_boxes if b["id"] == "b_beta")

    # b_alpha deve estar intacto, b_beta deve ter sido atualizado
    assert b_alpha["translated_text"] == "Old 1"
    assert b_beta["translated_text"] == "Updated Beta"


def test_format_script_multiline_behavior():
    """Valida o normalizador format_script_multiline em cenários de quebras e parágrafos."""
    from src.utils.txt_sync import format_script_multiline

    # 1. Fallback em texto vazio ou None
    assert format_script_multiline(None, fallback="[PENDENTE]") == "[PENDENTE]"
    assert format_script_multiline("", fallback="[PENDENTE]") == "[PENDENTE]"
    assert format_script_multiline("   \n\n  ", fallback="[PENDENTE]") == "[PENDENTE]"

    # 2. Preservação de quebras de linha com limpeza de espaços nas extremidades
    raw = "  Primeira linha de diálogo   \r\n   Segunda linha de diálogo  "
    assert format_script_multiline(raw) == "Primeira linha de diálogo\nSegunda linha de diálogo"

    # 3. Compactação de múltiplas linhas vazias para 1 parágrafo limpo
    paragraphs = "Parágrafo um\n\n\n\n\nParágrafo dois"
    assert format_script_multiline(paragraphs) == "Parágrafo um\n\nParágrafo dois"

    # 4. Trimming de quebras vazias nas bordas
    bordered = "\n\nFala central\n\n"
    assert format_script_multiline(bordered) == "Fala central"


def test_sync_chapter_txt_preserves_multiline_dialogues(temp_chapter):
    """Valida que sync_chapter_txt não achata quebras de linha legítimas com espaço simples."""
    temp_dir, out_dir = temp_chapter

    img_file = os.path.join(temp_dir, "001.png")
    with open(img_file, "wb") as f:
        f.write(b"dummy")

    map_data = [
        {
            "id": "b_multi",
            "text": "First line of original.\nSecond line of original.",
            "translated_text": "Primeira linha de fala.\nSegunda linha de fala.",
            "is_sfx": False
        }
    ]
    with open(os.path.join(out_dir, "001_map.json"), "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    res = sync_chapter_txt(temp_dir, "Cap_Multi")
    assert res["success"] is True

    with open(res["path"], "r", encoding="utf-8") as f:
        content = f.read()

    # Não deve ter sido achatado em "Primeira linha de fala. Segunda linha de fala."
    assert "Primeira linha de fala.\nSegunda linha de fala." in content
    assert "First line of original.\nSecond line of original." in content


def test_sync_json_from_script_preserves_multiline_and_paragraphs(temp_chapter):
    """Valida que sync_json_from_script reconcilia falas com quebras de linha e parágrafos sem descartar texto."""
    from src.api_services.library_service import LibraryService
    from src.domain.page_store import PageStore

    temp_dir, out_dir = temp_chapter

    img_file = os.path.join(temp_dir, "001.png")
    with open(img_file, "wb") as f:
        f.write(b"dummy")

    map_data = [
        {
            "id": "b_para",
            "text": "Speech",
            "translated_text": "Texto antigo",
            "is_sfx": False
        }
    ]
    map_file = os.path.join(out_dir, "001_map.json")
    with open(map_file, "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    script_path = os.path.join(temp_dir, "Cap_Para.txt")
    # Roteiro manual com 2 parágrafos separados por linha em branco
    script_content = (
        "==================================================\n"
        "PAGINA 1: 001.PNG\n"
        "==================================================\n\n"
        "# [id: b_para]\n"
        "[EN]: Speech\n"
        "[BR]: Primeiro parágrafo da fala.\n"
        "\n"
        "Segundo parágrafo da fala após linha vazia.\n\n"
    )

    class MockBridge:
        def __init__(self, path):
            self.current_path = path

    svc = LibraryService(api_bridge=MockBridge(temp_dir))
    save_res = svc.saveLibraryFile(script_path, script_content)
    assert save_res["success"] is True

    with open(map_file, "r", encoding="utf-8") as f:
        saved_boxes = PageStore.extract_boxes(json.load(f))

    b_res = next(b for b in saved_boxes if b["id"] == "b_para")
    expected_text = "Primeiro parágrafo da fala.\n\nSegundo parágrafo da fala após linha vazia."
    assert b_res["translated_text"] == expected_text


def test_idempotent_multiline_round_trip(temp_chapter):
    """Valida que o ciclo bidirecional (JSON -> TXT -> JSON -> TXT) é 100% determinístico e idempotente."""
    from src.api_services.library_service import LibraryService

    temp_dir, out_dir = temp_chapter

    img_file = os.path.join(temp_dir, "001.png")
    with open(img_file, "wb") as f:
        f.write(b"dummy")

    original_dialogue = "Linha um do balão\nLinha dois do balão\n\nLinha três em novo parágrafo"
    map_data = [
        {
            "id": "b_cycle",
            "text": "Original text",
            "translated_text": original_dialogue,
            "is_sfx": False
        }
    ]
    map_file = os.path.join(out_dir, "001_map.json")
    with open(map_file, "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    # 1. Primeira geração de script
    res1 = sync_chapter_txt(temp_dir, "Cap_Idempotent")
    assert res1["success"] is True
    with open(res1["path"], "r", encoding="utf-8") as f:
        txt1 = f.read()

    assert original_dialogue in txt1

    # 2. Salva o mesmo script de volta no sistema
    class MockBridge:
        def __init__(self, path):
            self.current_path = path

    svc = LibraryService(api_bridge=MockBridge(temp_dir))
    save_res = svc.saveLibraryFile(res1["path"], txt1)
    assert save_res["success"] is True

    # 3. Segunda geração de script a partir dos dados reconciliados
    res2 = sync_chapter_txt(temp_dir, "Cap_Idempotent")
    assert res2["success"] is True
    with open(res2["path"], "r", encoding="utf-8") as f:
        txt2 = f.read()

    # O conteúdo do roteiro deve ser estritamente idempotente (sem duplicar newlines ou alterar espaçamento)
    # Ignora timestamp do cabeçalho que pode mudar
    txt1_body = txt1.split("# " + "=" * 58)[-1]
    txt2_body = txt2.split("# " + "=" * 58)[-1]
    assert txt1_body == txt2_body


def test_sync_chapter_txt_uses_pagestore_ram_cache_for_unchanged_pages(temp_chapter):
    """Valida que páginas inalteradas são lidas em O(1) do PageStore sem reler JSON do disco a cada auto-save."""
    from unittest.mock import patch
    from src.domain.page_store import PageStore

    temp_dir, _ = temp_chapter
    PageStore.invalidate_cache()

    for idx in range(1, 5):
        img_p = os.path.join(temp_dir, f"{idx:03d}.png")
        with open(img_p, "wb") as f:
            f.write(b"dummy")
        PageStore.save_boxes(
            img_p,
            [{"id": 1, "text": f"Hello {idx}", "translated_text": f"Olá {idx}", "is_sfx": False}],
        )

    # Como save_boxes já aqueceu o _record_cache, sync_chapter_txt não deve tocar resilient_read_json nenhuma vez
    with patch("src.domain.page_store.resilient_read_json", side_effect=AssertionError("Should hit RAM cache")) as mock_read:
        res = sync_chapter_txt(temp_dir, "Cap_Cache_O1")
        assert res["success"] is True
        assert res["pages_count"] == 4
        assert res["translated_count"] == 4
        assert mock_read.call_count == 0

    # Edita apenas a página 2 via PageStore e ressincroniza: 0 leituras de disco
    PageStore.save_boxes(
        os.path.join(temp_dir, "002.png"),
        [{"id": 1, "text": "Hello 2", "translated_text": "Olá 2 Editado", "is_sfx": False}],
    )
    with patch("src.domain.page_store.resilient_read_json", side_effect=AssertionError("Should hit RAM cache")):
        res2 = sync_chapter_txt(temp_dir, "Cap_Cache_O1")
        assert res2["success"] is True

    with open(res2["path"], "r", encoding="utf-8") as f:
        txt_after = f.read()
    assert "Olá 2 Editado" in txt_after
    assert "Olá 4" in txt_after

