import os
import threading
import pytest
from src.utils.workspace_context import WorkspaceContext
from src.api_services.fs_service import FileSystemService
from src.api_services.library_service import LibraryService
from src.api_services.image_service import ImageService
from src.api_services.studio_service import StudioService
from src.api_services.pipeline_service import PipelineService
from src.api_services.model_service import ModelService
from src.api_services.settings_service import SettingsService
from src.model_manager import ModelManager
from src.api_bridge import ApiBridge


def test_workspace_context_lifecycle_and_thread_safety():
    ctx = WorkspaceContext("MEU COMPUTADOR")
    assert ctx.current_path == "MEU COMPUTADOR"
    assert ctx.get_current_path() == "MEU COMPUTADOR"

    ctx.set_current_path("C:/Manga/Chapter_01")
    assert ctx.current_path == "C:/Manga/Chapter_01"

    # Concurrency test
    paths = [f"C:/Manga/Vol_{i}" for i in range(50)]
    def worker(p):
        ctx.set_current_path(p)
        _ = ctx.current_path

    threads = [threading.Thread(target=worker, args=(p,)) for p in paths]
    for t in threads: t.start()
    for t in threads: t.join()

    assert ctx.current_path in paths


def test_fs_service_isolated_with_workspace_context(tmp_path):
    ctx = WorkspaceContext(str(tmp_path))
    fs = FileSystemService(workspace_context=ctx)

    assert fs.current_path == str(tmp_path)
    drives = fs.get_drives()
    assert isinstance(drives, list)
    assert len(drives) > 0

    sub_dir = tmp_path / "SubChapter"
    sub_dir.mkdir()
    res = fs.list_directory(str(sub_dir))
    assert res["success"] is True
    assert ctx.current_path == str(sub_dir)
    assert fs.current_path == str(sub_dir)


def test_library_service_isolated_with_workspace_context(tmp_path):
    chapter_dir = tmp_path / "Chapter 99"
    chapter_dir.mkdir()
    (chapter_dir / "Chapter 99.txt").write_text("Hello World", encoding="utf-8")

    ctx = WorkspaceContext(str(chapter_dir))
    lib = LibraryService(workspace_context=ctx)

    res = lib.listLibraryFiles()
    assert res["success"] is True
    file_names = [f["name"] for f in res["files"]]
    assert "Chapter 99.txt" in file_names


def test_image_service_isolated_with_workspace_context(tmp_path):
    ctx = WorkspaceContext(str(tmp_path))
    img_svc = ImageService(workspace_context=ctx)

    resolved = img_svc._resolve_target("cover.png")
    assert resolved == os.path.normpath(str(tmp_path / "cover.png"))


def test_studio_service_isolated_with_workspace_context(tmp_path):
    ctx = WorkspaceContext(str(tmp_path))
    studio = StudioService(workspace_context=ctx)

    resolved = studio._resolve_target("page_01.png")
    assert resolved == os.path.normpath(str(tmp_path / "page_01.png"))


def test_pipeline_service_isolated_with_settings_service():
    class DummySettings:
        def getSettings(self):
            return {"translation_model": "test_model:latest"}

    pipe = PipelineService(settings_service=DummySettings())
    assert pipe.settings_service is not None
    assert pipe.settings_service.getSettings()["translation_model"] == "test_model:latest"


def test_model_service_isolated_with_model_manager():
    mm = ModelManager()
    ms = ModelService(model_manager=mm)
    assert ms.model_manager is mm
    assert hasattr(ms, "core_installer")
    assert hasattr(ms, "hf_orchestrator")
    assert hasattr(ms, "ollama_mgr")


def test_api_bridge_pure_facade_and_synchronization(tmp_path):
    bridge = ApiBridge(base_folder=str(tmp_path))

    assert bridge.current_path == str(tmp_path)
    assert bridge.workspace_context.current_path == str(tmp_path)

    # Change via FileSystemService
    sub_dir = tmp_path / "NextChapter"
    sub_dir.mkdir()
    bridge.list_directory(str(sub_dir))

    assert bridge.current_path == str(sub_dir)
    assert bridge._library_service.context.current_path == str(sub_dir)
    assert bridge._image_service.context.current_path == str(sub_dir)
    assert bridge._studio_service.context.current_path == str(sub_dir)

    # Change via bridge setter
    bridge.current_path = "C:/Direct/Assignment"
    assert bridge.workspace_context.current_path == "C:/Direct/Assignment"
    assert bridge._fs_service.current_path == "C:/Direct/Assignment"


def test_pipeline_queue_max_capacity_backpressure(tmp_path):
    pipe = PipelineService()
    # Fill queue to 100
    with pipe._jobs_lock:
        pipe._pending_tasks = [(f"job_{i}", {}, str(tmp_path), "test") for i in range(100)]

    res = pipe.queueJob({"folderPath": str(tmp_path)})
    assert res["success"] is False
    assert "Fila de tarefas cheia" in res["error"]


def test_rollback_resilience_and_execution(tmp_path):
    from src.batch_pipeline.session import backup_file, execute_rollback, reset_session, request_cancel
    reset_session()

    file_a = tmp_path / "page_01_map.json"
    file_a.write_text('{"boxes": [{"id": 1}]}', encoding="utf-8")

    # Backup existing file
    backup_file(str(file_a))

    # Overwrite
    file_a.write_text('{"boxes": [{"id": 2}]}', encoding="utf-8")

    # Brand new file created in session
    file_b = tmp_path / "page_02_map.json"
    backup_file(str(file_b)) # Not existing when backed up
    file_b.write_text('{"boxes": [{"id": 3}]}', encoding="utf-8")

    request_cancel(rollback=True)
    execute_rollback()

    assert file_a.read_text(encoding="utf-8") == '{"boxes": [{"id": 1}]}'
    assert not file_b.exists()
    reset_session()


def test_context_optimizer_and_few_shot_resilience(tmp_path):
    from src.translation_engine.context_optimizer import calculate_optimal_num_ctx
    from src.translation_engine.few_shot_retriever import load_glossary_data

    map_file = tmp_path / "test_map.json"
    map_file.write_text('{"boxes": [{"id": 1, "text": "Hello world from manga"}]}', encoding="utf-8")

    ctx = calculate_optimal_num_ctx([str(map_file)])
    assert ctx in [1536, 1792, 2048, 2560, 3072, 4096, 6144, 8192]

    # Empty glossary handling
    res = load_glossary_data(str(tmp_path / "non_existing.json"))
    assert res == {}


def test_domain_and_geometry_slicing_contracts():
    """Garante que os pacotes fatiados (src.domain, src.geometry, src.geometry.panels, src.model_engines)
    e as fachadas legadas em src.utils e src.step1/step2 apontam exatamente para os mesmos objetos em memória."""
    import src.domain.bubble_contract as domain_bc
    import src.domain.page_store as domain_ps
    import src.domain.reorder_transaction as domain_rt
    import src.geometry.bubble_geometry as geom_bg
    import src.geometry.panels as geom_panels
    from src.geometry.panels import gutters, lines, refinement, splitting_and_rescue
    import src.utils.bubble_contract as utils_bc
    import src.utils.bubble_geometry as utils_bg
    import src.utils.page_store as utils_ps
    import src.utils.panel_geometry as utils_pg
    import src.utils.reorder_transaction as utils_rt
    import src.model_engines.florence_ocr_engine as florence_mod
    import src.model_engines.yolo_layout_engine as yolo_mod
    import src.model_engines.core_engine_installer as core_installer_mod
    import src.api_services.core_engine_installer as api_core_installer_mod
    import src.step1_layout_detector as step1_mod
    import src.step2_ocr_extractor as step2_mod
    from src.model_engines import (
        CoreEngineInstaller,
        install_isolated_ollama,
        pull_ollama_model,
        delete_ollama_model,
        test_ollama_translation,
    )

    assert domain_bc is utils_bc
    assert domain_ps is utils_ps
    assert domain_rt is utils_rt
    assert geom_bg is utils_bg
    assert geom_panels is utils_pg
    assert yolo_mod is step1_mod
    assert florence_mod is step2_mod
    assert core_installer_mod is api_core_installer_mod
    assert callable(CoreEngineInstaller)

    assert geom_panels.is_point_in_panel is lines.is_point_in_panel
    assert geom_panels.detect_slanted_gutter_in_corridor is gutters.detect_slanted_gutter_in_corridor
    assert geom_panels.split_oversized_panels is splitting_and_rescue.split_oversized_panels
    assert geom_panels.refine_panels_to_polygons is refinement.refine_panels_to_polygons
    assert callable(florence_mod.FlorenceReader)
    assert callable(yolo_mod.YoloMapeador)
    assert callable(install_isolated_ollama)
    assert callable(pull_ollama_model)
    assert callable(delete_ollama_model)
    assert callable(test_ollama_translation)


def test_config_is_test_environment_centralized(monkeypatch):
    """Valida a detecção centralizada de ambiente de teste em Config.is_test_environment."""
    from src.config import Config, is_test_environment

    assert Config.is_test_environment() is True
    assert is_test_environment() is True

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("VISIONARY_TEST_ENV", raising=False)
    assert Config.is_test_environment() is False

    monkeypatch.setenv("VISIONARY_TEST_ENV", "1")
    assert Config.is_test_environment() is True


def test_workspace_context_resolve_service_binding_variants(tmp_path):
    """Valida que WorkspaceContext.resolve_service_binding suporta injeção direta e legado (api_bridge no 1º arg)."""
    ctx = WorkspaceContext(str(tmp_path))

    # 1. Injeção pura de WorkspaceContext
    r_ctx, r_api = WorkspaceContext.resolve_service_binding(ctx, None, "DEFAULT")
    assert r_ctx is ctx
    assert r_api is None

    # 2. Legado: ApiBridge passado como primeiro argumento posicional
    class DummyBridgeWithCtx:
        def __init__(self):
            self.workspace_context = ctx

    dummy_bridge = DummyBridgeWithCtx()
    r_ctx2, r_api2 = WorkspaceContext.resolve_service_binding(dummy_bridge, None, "DEFAULT")
    assert r_ctx2 is ctx
    assert r_api2 is dummy_bridge

    # 3. Fallback vazio
    r_ctx3, r_api3 = WorkspaceContext.resolve_service_binding(None, None, "FALLBACK_DIR")
    assert isinstance(r_ctx3, WorkspaceContext)
    assert r_ctx3.current_path == "FALLBACK_DIR"
    assert r_api3 is None


