import os
import tempfile
import shutil
import pytest
from src.api_services.library_service import LibraryService

@pytest.fixture
def temp_lib_env():
    temp_dir = tempfile.mkdtemp(prefix="test_lib_")
    chapter_dir = os.path.join(temp_dir, "Chapter_01")
    os.makedirs(chapter_dir, exist_ok=True)
    yield temp_dir, chapter_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_list_library_files_metadata_and_status(temp_lib_env, monkeypatch):
    """Valida a extração automática de metadados de balões e status (complete vs pending)."""
    from src.config import Config
    monkeypatch.setattr(Config, "get", lambda k, default="": "" if k == "baseFolder" else default)
    temp_dir, chapter_dir = temp_lib_env

    # 1. Script com tradução pendente
    txt_pending = os.path.join(chapter_dir, "Chapter_01.txt")
    with open(txt_pending, "w", encoding="utf-8") as f:
        f.write(
            "# VISIONARY ROTEIRO\n"
            "PAGINA 1: 001.PNG\n"
            "[EN]: Hello\n"
            "[BR]: Olá\n"
            "[EN]: Look out\n"
            "[BR]: [PENDENTE]\n"
        )

    class MockBridge:
        def __init__(self, path):
            self.current_path = path

    service = LibraryService(api_bridge=MockBridge(chapter_dir))
    res = service.listLibraryFiles()
    assert res["success"] is True
    files = res["files"]
    file_meta = next((f for f in files if f["name"] == "Chapter_01.txt"), None)
    assert file_meta is not None
    assert file_meta["balloonCount"] == 2
    assert file_meta["pendingCount"] == 1
    assert file_meta["status"] == "pending"

    # 2. Atualizar para 100% completo
    with open(txt_pending, "w", encoding="utf-8") as f:
        f.write(
            "# VISIONARY ROTEIRO\n"
            "PAGINA 1: 001.PNG\n"
            "[EN]: Hello\n"
            "[BR]: Olá\n"
            "[EN]: Look out\n"
            "[BR]: Cuidado!\n"
        )

    res2 = service.listLibraryFiles()
    file_meta2 = next((f for f in res2["files"] if f["name"] == "Chapter_01.txt"), None)
    assert file_meta2 is not None
    assert file_meta2["balloonCount"] == 2
    assert file_meta2["pendingCount"] == 0
    assert file_meta2["status"] == "complete"

def test_save_library_file(temp_lib_env):
    """Valida o salvamento em disco com codificação UTF-8."""
    temp_dir, chapter_dir = temp_lib_env
    txt_path = os.path.join(chapter_dir, "Chapter_01.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Versão antiga")

    service = LibraryService(api_bridge=None)
    new_content = "Versão nova com caracteres especiais: Olá — mundo… [100%]"
    res = service.saveLibraryFile(txt_path, new_content)

    assert res["success"] is True
    assert res["path"] == os.path.normpath(txt_path)
    assert res["size"] > 0

    read_res = service.readLibraryFile(txt_path)
    assert read_res["success"] is True
    assert read_res["content"] == new_content

def test_export_script_clean_txt_and_rtf(temp_lib_env):
    """Valida a exportação nos formatos clean_txt e rtf compatível com Microsoft Word."""
    temp_dir, chapter_dir = temp_lib_env
    txt_path = os.path.join(chapter_dir, "Chapter_01.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(
            "# VISIONARY ROTEIRO\n"
            "PAGINA 1: 001.PNG\n"
            "[EN]: Watch out!\n"
            "[BR] (GRITO): Cuidado!\n"
            "PAGINA 2: 002.PNG\n"
            "[EN]: Are you okay?\n"
            "[BR]: Você está bem?\n"
        )

    service = LibraryService(api_bridge=None)

    # 1. Export Clean TXT
    res_txt = service.exportScript(txt_path, "clean_txt")
    assert res_txt["success"] is True
    assert res_txt["filename"] == "Chapter_01_limpo.txt"
    assert "ROTEIRO DE TRADUÇÃO: Chapter_01" in res_txt["content"]
    assert "--- PÁGINA 1: 001.PNG ---" in res_txt["content"]
    assert "[1] (GRITO) Cuidado!" in res_txt["content"]
    assert "--- PÁGINA 2: 002.PNG ---" in res_txt["content"]
    assert "[1] Você está bem?" in res_txt["content"]

    # 2. Export RTF
    res_rtf = service.exportScript(txt_path, "rtf")
    assert res_rtf["success"] is True
    assert res_rtf["filename"] == "Chapter_01_revisao.rtf"
    assert r"{\rtf1" in res_rtf["content"]
    assert r"\fs32 Chapter_01" in res_rtf["content"]
    assert "001.PNG" in res_rtf["content"]
    assert "Cuidado!" in res_rtf["content"]

def test_open_file_and_library_folder_in_explorer(temp_lib_env, monkeypatch):
    """Valida a abertura de arquivos e pastas no Explorer pelo LibraryService."""
    temp_dir, chapter_dir = temp_lib_env
    txt_path = os.path.join(chapter_dir, "Chapter_01.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("test")

    opened_commands = []
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: opened_commands.append(cmd))
    if hasattr(os, 'startfile'):
        monkeypatch.setattr(os, "startfile", lambda p: opened_commands.append(["startfile", p]))

    class MockBridge:
        def __init__(self, path):
            self.current_path = path

    service = LibraryService(api_bridge=MockBridge(chapter_dir))

    # 1. Abrir pasta de capítulo existente (diretório direto)
    res_dir = service.openFileInExplorer(chapter_dir)
    assert res_dir["success"] is True
    assert len(opened_commands) == 1

    # 2. Abrir arquivo existente (select)
    res_file = service.openFileInExplorer(txt_path)
    assert res_file["success"] is True
    assert len(opened_commands) == 2

    # 3. Abrir arquivo que não existe na pasta (deve cair na pasta pai)
    missing_file = os.path.join(chapter_dir, "nonexistent.png")
    res_missing = service.openFileInExplorer(missing_file)
    assert res_missing["success"] is True
    assert len(opened_commands) == 3

    # 4. Abrir pasta padrão da biblioteca
    res_lib = service.openLibraryFolder()
    assert res_lib["success"] is True
    assert len(opened_commands) == 4

def test_update_balloon_text_updates_json_and_txt(temp_lib_env):
    """Valida que updateBalloonText atualiza simultaneamente o _map.json da página e o arquivo .txt do capítulo."""
    import json
    from src.utils.txt_sync import sync_chapter_txt

    temp_dir, chapter_dir = temp_lib_env
    out_dir = os.path.join(chapter_dir, "output")
    os.makedirs(out_dir, exist_ok=True)

    # Imagem física
    with open(os.path.join(chapter_dir, "001.png"), "wb") as f:
        f.write(b"dummy")

    # Map com SFX e 2 balões
    map_data = [
        {"id": 1, "is_sfx": True, "text": "BOOM", "translated_text": "CABUM"},
        {"id": 2, "is_sfx": False, "order": 1, "text": "Hey there", "translated_text": "E aí"},
        {"id": 3, "is_sfx": False, "order": 2, "text": "How are you?", "translated_text": "Como vai?"}
    ]
    map_path = os.path.join(out_dir, "001_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    sync_chapter_txt(chapter_dir, "Chapter_01")
    txt_path = os.path.join(chapter_dir, "Chapter_01.txt")
    assert os.path.exists(txt_path)

    service = LibraryService(api_bridge=None)

    # Atualiza o segundo balão de diálogo (index 1 = "How are you?")
    res = service.updateBalloonText(
        script_path=txt_path,
        page_name="001.png",
        balloon_index=1,
        new_text="Como você está, meu amigo?",
        original_text="How are you?"
    )

    assert res["success"] is True

    # 1. Verifica se o _map.json foi atualizado (Envelope v2)
    with open(map_path, "r", encoding="utf-8") as f:
        updated_envelope = json.load(f)
    assert updated_envelope["version"] == 2
    updated_map = updated_envelope["boxes"]

    box2 = next(b for b in updated_map if b.get("id") == 2)
    box3 = next(b for b in updated_map if b.get("id") == 3)
    sfx = next(b for b in updated_map if b.get("id") == 1)

    assert sfx["translated_text"] == "CABUM"
    assert box2["translated_text"] == "E aí"
    assert box3["translated_text"] == "Como você está, meu amigo?"
    assert box3["user_edited"] is True

    # 2. Verifica se o .txt foi resincronizado
    with open(txt_path, "r", encoding="utf-8") as f:
        txt_content = f.read()

    assert "[BR]: E aí" in txt_content
    assert "[BR]: Como você está, meu amigo?" in txt_content

def test_save_library_file_two_way_syncs_to_json(temp_lib_env):
    """Valida que salvar o roteiro completo via saveLibraryFile também atualiza os arquivos _map.json."""
    import json
    from src.utils.txt_sync import sync_chapter_txt

    temp_dir, chapter_dir = temp_lib_env
    out_dir = os.path.join(chapter_dir, "output")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(chapter_dir, "001.png"), "wb") as f:
        f.write(b"dummy")

    map_data = [
        {"id": 1, "is_sfx": False, "order": 1, "text": "Original speech", "translated_text": "Tradução velha"}
    ]
    map_path = os.path.join(out_dir, "001_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    sync_chapter_txt(chapter_dir, "Chapter_01")
    txt_path = os.path.join(chapter_dir, "Chapter_01.txt")

    service = LibraryService(api_bridge=None)

    # Simula edição manual e salvamento do script
    new_script = (
        "PAGINA 1: 001.PNG\n"
        "[EN]: Original speech\n"
        "[BR]: Nova tradução magnífica!\n"
    )
    res = service.saveLibraryFile(txt_path, new_script)
    assert res["success"] is True

    # Verifica se o _map.json recebeu a nova tradução (Envelope v2)
    with open(map_path, "r", encoding="utf-8") as f:
        updated_envelope = json.load(f)
    assert updated_envelope["version"] == 2
    updated_map = updated_envelope["boxes"]

    assert updated_map[0]["translated_text"] == "Nova tradução magnífica!"
    assert updated_map[0]["user_edited"] is True


def test_page_header_regex_variations_and_export():
    """Valida o parser de cabeçalhos de página com formatos flexíveis (com ou sem nome de imagem, com ou sem separador)."""
    from src.api_services.library_script_manager import LibraryScriptManager
    from src.api_services.script_exporter import parse_script_into_pages, export_script_to_format

    content = (
        "=== PÁGINA 1 ===\n"
        "[EN]: Hello\n"
        "[BR]: Olá\n\n"
        "PAGINA 2\n"
        "[EN]: Second page\n"
        "[BR]: Segunda página\n\n"
        "--- PÁGINA 3: 003.png ---\n"
        "[EN]: Third page\n"
        "[BR]: Terceira página\n\n"
        "PAGE 4 - 004.jpg\n"
        "[EN]: Fourth page\n"
        "[BR]: Quarta página\n"
    )

    # 1. Teste no LibraryScriptManager
    mgr = LibraryScriptManager()
    pages = mgr.parse_script_to_blocks(content)
    assert len(pages) == 4
    assert pages[0]["num"] == 1
    assert pages[0]["image"] == "Página 1"
    assert pages[0]["balloons"][0]["br"] == "Olá"

    assert pages[1]["num"] == 2
    assert pages[1]["image"] == "Página 2"
    assert pages[1]["balloons"][0]["br"] == "Segunda página"

    assert pages[2]["num"] == 3
    assert pages[2]["image"] == "003.png"
    assert pages[2]["balloons"][0]["br"] == "Terceira página"

    assert pages[3]["num"] == 4
    assert pages[3]["image"] == "004.jpg"
    assert pages[3]["balloons"][0]["br"] == "Quarta página"

    # 2. Teste no script_exporter
    exp_pages = parse_script_into_pages(content)
    assert len(exp_pages) == 4
    assert exp_pages[0]["num"] == "1"
    assert exp_pages[0]["name"] == "Página 1"
    assert exp_pages[2]["name"] == "003.png"

    # 3. Export RTF e Clean TXT
    rtf_res = export_script_to_format(content, "Capitulo_01", export_format="rtf")
    assert rtf_res["success"] is True
    assert "P\\u193?GINA 1" in rtf_res["content"] or "PÁGINA 1" in rtf_res["content"]

    txt_res = export_script_to_format(content, "Capitulo_01", export_format="clean_txt")
    assert txt_res["success"] is True
    assert "PÁGINA 1" in txt_res["content"]

    # 4. Teste de páginas silenciosas e quebra de linha multiline com \line no RTF
    multiline_content = "=== PÁGINA 1: 001.png ===\n[EN]: Hello\nworld\n[BR]: Olá\nmundo\n\n=== PÁGINA 2: 002.png ===\n"
    rtf_multi = export_script_to_format(multiline_content, "Capitulo_Multi", export_format="rtf")
    assert rtf_multi["success"] is True
    assert r"\line " in rtf_multi["content"]
    assert "P\\u225?gina sem falas / Arte pura" in rtf_multi["content"] or "Página sem falas / Arte pura" in rtf_multi["content"]

    txt_multi = export_script_to_format(multiline_content, "Capitulo_Multi", export_format="clean_txt")
    assert txt_multi["success"] is True
    assert "Página sem falas / Arte pura" in txt_multi["content"]


def test_inspect_file_stats_with_tagged_balloons(temp_lib_env):
    """Valida se balões com anotações de estilo (ex: [1] (PENSAMENTO): [PENDENTE]) são contados como pendentes."""
    from src.api_services.library_scanner import LibraryScanner
    temp_dir, chapter_dir = temp_lib_env
    txt_path = os.path.join(chapter_dir, "Chapter_Tagged.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(
            "PAGINA 1: 001.PNG\n"
            "[1] (PENSAMENTO): [PENDENTE]\n"
            "[2] (NARRAÇÃO): [PENDENTE]\n"
            "[3] (GRITO): Socorro!\n"
            "[BR] (SUSSURRO): [PENDENTE]\n"
            "[BR]: Olá mundo\n"
        )

    stats = LibraryScanner.inspect_file_stats(txt_path)
    assert stats["balloonCount"] == 5
    assert stats["pendingCount"] == 3
    assert stats["status"] == "pending"

