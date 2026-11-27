import os
import threading
from src.model_manager import ModelManager
from src.domain.bubble_contract import to_snake_case, to_camel_case
from src.utils.workspace_context import WorkspaceContext

from src.api_services.window_service import WindowService
from src.api_services.hardware_service import HardwareService
from src.api_services.settings_service import SettingsService
from src.api_services.library_service import LibraryService
from src.api_services.image_service import ImageService
from src.api_services.studio_service import StudioService
from src.api_services.pipeline_service import PipelineService
from src.api_services.model_service import ModelService
from src.api_services.fs_service import FileSystemService
from src.api_services.dev_service import DevService


class ApiBridge:
    """
    Ponto de entrada único das chamadas RPC vindas do frontend (`/api/rpc/{method}`).
    Instancia e delega para cada serviço especializado mantendo um `WorkspaceContext` compartilhado.
    """

    def __init__(self, base_folder="MEU COMPUTADOR"):
        # Contexto compartilhado entre serviços para evitar divergência de pasta ativa
        self.workspace_context = WorkspaceContext(base_folder)

        self.pipeline_event = threading.Event()
        self.edited_boxes = []
        self._settings_cache = None
        self._stats_cache = None
        self._lock = threading.Lock()
        self._install_progress = {"log": "", "status": "idle", "percent": 0.0, "message": ""}
        self._ollama_downloads = {}
        self.model_manager = ModelManager()

        self._window_service = WindowService()
        self._hardware_service = HardwareService(api_bridge=self)
        self._settings_service = SettingsService()
        self._library_service = LibraryService(workspace_context=self.workspace_context)
        self._image_service = ImageService(workspace_context=self.workspace_context)
        self._studio_service = StudioService(workspace_context=self.workspace_context)
        self._pipeline_service = PipelineService(settings_service=self._settings_service)
        self._model_service = ModelService(model_manager=self.model_manager, api_bridge=self)
        self._fs_service = FileSystemService(workspace_context=self.workspace_context)
        self._dev_service = DevService()
        self._all_services = [
            self._window_service, self._hardware_service, self._settings_service,
            self._library_service, self._image_service, self._studio_service,
            self._pipeline_service, self._model_service, self._fs_service, self._dev_service
        ]

    @property
    def current_path(self):
        return self.workspace_context.current_path

    @current_path.setter
    def current_path(self, val):
        self.workspace_context.current_path = val

    def set_window(self, window): return self._window_service.set_window(window)
    def minimize(self): return self._window_service.minimize()
    def toggle_maximize(self): return self._window_service.toggle_maximize()
    def get_is_maximized(self): return self._window_service.get_is_maximized()
    def start_tear_off_drag(self, *args, **kwargs): return self._window_service.start_tear_off_drag(*args, **kwargs)
    def show_system_menu(self, *args, **kwargs): return self._window_service.show_system_menu(*args, **kwargs)
    def close(self): return self._window_service.close()

    def getHardwareStats(self, *args, **kwargs): return self._hardware_service.getHardwareStats(*args, **kwargs)

    def getSettings(self, *args, **kwargs): return self._settings_service.getSettings(*args, **kwargs)
    def saveSettings(self, *args, **kwargs): return self._settings_service.saveSettings(*args, **kwargs)
    def getStats(self, *args, **kwargs): return self._settings_service.getStats(*args, **kwargs)
    def updateStats(self, *args, **kwargs): return self._settings_service.updateStats(*args, **kwargs)

    def listLibraryFiles(self, *args, **kwargs): return self._library_service.listLibraryFiles(*args, **kwargs)
    def readLibraryFile(self, *args, **kwargs): return self._library_service.readLibraryFile(*args, **kwargs)
    def saveLibraryFile(self, *args, **kwargs): return self._library_service.saveLibraryFile(*args, **kwargs)
    def exportScript(self, *args, **kwargs): return self._library_service.exportScript(*args, **kwargs)
    def deleteLibraryFile(self, *args, **kwargs): return self._library_service.deleteLibraryFile(*args, **kwargs)
    def openFileInExplorer(self, *args, **kwargs): return self._library_service.openFileInExplorer(*args, **kwargs)
    def openLibraryFolder(self, *args, **kwargs): return self._library_service.openLibraryFolder(*args, **kwargs)
    def syncChapterTxt(self, *args, **kwargs): return self._library_service.syncChapterTxt(*args, **kwargs)
    def force_sync_chapter_txt(self, *args, **kwargs): return self._library_service.syncChapterTxt(*args, **kwargs)
    def open_folder(self, *args, **kwargs): return self._library_service.openFileInExplorer(*args, **kwargs)
    def updateBalloonText(self, *args, **kwargs): return self._library_service.updateBalloonText(*args, **kwargs)

    def copyToClipboard(self, text: str):
        try:
            import subprocess
            p = subprocess.Popen(['clip'], stdin=subprocess.PIPE, close_fds=True)
            p.communicate(input=str(text).encode('utf-16le'))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def showSystemNotification(self, title: str, message: str):
        try:
            from src.utils.notification import send_system_notification
        except ImportError:
            from utils.notification import send_system_notification
        return send_system_notification(str(title), str(message))

    def get_image_base64(self, *args, **kwargs): return self._image_service.get_image_base64(*args, **kwargs)
    def get_image_base64_full(self, *args, **kwargs): return self._image_service.get_image_base64_full(*args, **kwargs)

    def get_page_data(self, *args, **kwargs): return self._studio_service.get_page_data(*args, **kwargs)
    def clearPageData(self, *args, **kwargs): return self._studio_service.clearPageData(*args, **kwargs)
    def loadStudioData(self, *args, **kwargs): return self._studio_service.loadStudioData(*args, **kwargs)
    def saveStudioData(self, *args, **kwargs): return self._studio_service.saveStudioData(*args, **kwargs)
    def save_page_layout(self, *args, **kwargs): return self._studio_service.save_page_layout(*args, **kwargs)
    def autoSortBoxes(self, *args, **kwargs): return self._studio_service.autoSortBoxes(*args, **kwargs)
    def detect_page_bubbles(self, *args, **kwargs): return self._studio_service.detect_page_bubbles(*args, **kwargs)
    def create_page_backup(self, *args, **kwargs): return self._studio_service.create_page_backup(*args, **kwargs)
    def check_page_backup(self, *args, **kwargs): return self._studio_service.check_page_backup(*args, **kwargs)
    def restore_page_backup(self, *args, **kwargs): return self._studio_service.restore_page_backup(*args, **kwargs)
    def delete_page_backup(self, *args, **kwargs): return self._studio_service.delete_page_backup(*args, **kwargs)
    def get_global_dictionary(self, *args, **kwargs): return self._studio_service.get_global_dictionary(*args, **kwargs)
    def save_global_dictionary(self, *args, **kwargs): return self._studio_service.save_global_dictionary(*args, **kwargs)
    def get_references(self, *args, **kwargs): return self._studio_service.get_references(*args, **kwargs)
    def save_references(self, *args, **kwargs): return self._studio_service.save_references(*args, **kwargs)
    def scan_user_edits(self, *args, **kwargs): return self._studio_service.scan_user_edits(*args, **kwargs)

    def logDebug(self, message):
        try:
            from src.utils.logger import get_logger
            get_logger("teleport").info(f"[API Bridge] {message}")
            return {"success": True}
        except Exception:
            return {"success": False}

    def clearTeleportLogs(self, *args, **kwargs):
        try:
            from src.config import get_app_data_dir
            logs_dir = os.path.join(get_app_data_dir(), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_path = os.path.join(logs_dir, "teleport_debug.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("--- Teleport Tracker Log Reiniciado ---\n")
            return {"success": True}
        except Exception:
            return {"success": False}

    def clearDebugLog(self, *args, **kwargs):
        return self.clearTeleportLogs(*args, **kwargs)

    def openExternal(self, url: str, *args, **kwargs):
        try:
            import webbrowser
            import urllib.parse
            if urllib.parse.urlparse(str(url)).scheme in ("http", "https"):
                webbrowser.open(url)
            else:
                return {"success": False, "error": "Protocolo inválido"}
            return {"success": True}
        except Exception:
            return {"success": False}

    def queueJob(self, *args, **kwargs): return self._pipeline_service.queueJob(*args, **kwargs)
    def cancelJob(self, *args, **kwargs): return self._pipeline_service.cancelJob(*args, **kwargs)
    def cancelAllJobs(self, *args, **kwargs): return self._pipeline_service.cancelAllJobs(*args, **kwargs)
    def getJobStatus(self, *args, **kwargs): return self._pipeline_service.getJobStatus(*args, **kwargs)
    def getPipelineStatus(self, *args, **kwargs): return self._pipeline_service.getPipelineStatus(*args, **kwargs)
    def clearCompletedJobs(self, *args, **kwargs): return self._pipeline_service.clearCompletedJobs(*args, **kwargs)
    def clearJobLogs(self, *args, **kwargs): return self._pipeline_service.clearJobLogs(*args, **kwargs)
    def finalizePipeline(self, *args, **kwargs): return self._pipeline_service.finalizePipeline(*args, **kwargs)

    def checkModulesStatus(self, *args, **kwargs): return self._model_service.checkModulesStatus(*args, **kwargs)
    def installCoreEngine(self, *args, **kwargs): return self._model_service.installCoreEngine(*args, **kwargs)
    def uninstallCoreEngine(self, *args, **kwargs): return self._model_service.uninstallCoreEngine(*args, **kwargs)
    def getInstallProgress(self, *args, **kwargs): return self._model_service.getInstallProgress(*args, **kwargs)
    def getModelsStatus(self, *args, **kwargs): return self._model_service.getModelsStatus(*args, **kwargs)
    def getDownloadsProgress(self, *args, **kwargs): return self._model_service.getDownloadsProgress(*args, **kwargs)
    def downloadHuggingFaceModel(self, *args, **kwargs): return self._model_service.downloadHuggingFaceModel(*args, **kwargs)
    def cancelHuggingFaceModel(self, *args, **kwargs): return self._model_service.cancelHuggingFaceModel(*args, **kwargs)
    def cancelModelDownload(self, *args, **kwargs): return self._model_service.cancelModelDownload(*args, **kwargs)
    def deleteHuggingFaceModel(self, *args, **kwargs): return self._model_service.deleteHuggingFaceModel(*args, **kwargs)
    def pullOllamaModel(self, *args, **kwargs): return self._model_service.pullOllamaModel(*args, **kwargs)
    def cancelOllamaDownload(self, *args, **kwargs): return self._model_service.cancelOllamaDownload(*args, **kwargs)
    def deleteOllamaModel(self, *args, **kwargs): return self._model_service.deleteOllamaModel(*args, **kwargs)
    def startOllamaServer(self, *args, **kwargs): return self._model_service.startOllamaServer(*args, **kwargs)
    def stopOllamaServer(self, *args, **kwargs): return self._model_service.stopOllamaServer(*args, **kwargs)
    def ensureOllamaRunning(self, *args, **kwargs): return self._model_service.ensureOllamaRunning(*args, **kwargs)
    def isOllamaRunning(self, *args, **kwargs): return self._model_service.isOllamaRunning(*args, **kwargs)
    def installIsolatedOllama(self, *args, **kwargs): return self._model_service.installIsolatedOllama(*args, **kwargs)
    def cancelIsolatedOllamaInstall(self, *args, **kwargs): return self._model_service.cancelIsolatedOllamaInstall(*args, **kwargs)
    def getOllamaInstallProgress(self, *args, **kwargs): return self._model_service.getOllamaInstallProgress(*args, **kwargs)
    def openOllamaSite(self, *args, **kwargs): return self._model_service.openOllamaSite(*args, **kwargs)
    def testModelTranslation(self, *args, **kwargs): return self._model_service.testModelTranslation(*args, **kwargs)
    def getStorageStats(self, *args, **kwargs): return self._model_service.getStorageStats(*args, **kwargs)

    def get_drives(self, *args, **kwargs): return self._fs_service.get_drives(*args, **kwargs)
    def list_directory(self, *args, **kwargs): return self._fs_service.list_directory(*args, **kwargs)
    def select_folder(self, *args, **kwargs): return self._fs_service.select_folder(*args, **kwargs)
    def selectFolder(self, *args, **kwargs): return self._fs_service.selectFolder(*args, **kwargs)
    def listDrives(self, *args, **kwargs): return self._fs_service.listDrives(*args, **kwargs)
    def listDirectory(self, *args, **kwargs): return self._fs_service.listDirectory(*args, **kwargs)
    def getParentPath(self, *args, **kwargs): return self._fs_service.getParentPath(*args, **kwargs)
    def reorder_pages(self, *args, **kwargs): return self._fs_service.reorder_pages(*args, **kwargs)
    def merge_pages(self, *args, **kwargs): return self._fs_service.merge_pages(*args, **kwargs)
    def split_page(self, *args, **kwargs): return self._fs_service.split_page(*args, **kwargs)
    def delete_page(self, *args, **kwargs): return self._fs_service.delete_page(*args, **kwargs)

    def runTests(self, *args, **kwargs): return self._dev_service.runTests(*args, **kwargs)
    def cancelTests(self, *args, **kwargs): return self._dev_service.cancelTests(*args, **kwargs)
    def stopTests(self, *args, **kwargs): return self._dev_service.stopTests(*args, **kwargs)
    def getDevLogs(self, *args, **kwargs): return self._dev_service.getDevLogs(*args, **kwargs)
    def getDevStats(self, *args, **kwargs): return self._dev_service.getDevStats(*args, **kwargs)
    def clearVRAM(self, *args, **kwargs): return self._dev_service.clearVRAM(*args, **kwargs)
    def unloadDevModel(self, *args, **kwargs): return self._dev_service.unloadDevModel(*args, **kwargs)
    def getTestList(self, *args, **kwargs): return self._dev_service.getTestList(*args, **kwargs)

    def __getattr__(self, name: str):
        """Fallback de resolução para variantes de sigla que fogem do camelCase/snake_case padrão (ex.: clear_vram -> clearVRAM)."""
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        class_methods = {
            m for m in dir(self.__class__)
            if not m.startswith("_") and callable(getattr(self.__class__, m, None))
        }

        snake_name = to_snake_case(name)
        if snake_name in class_methods:
            return getattr(self, snake_name)

        camel_name = to_camel_case(name)
        if camel_name in class_methods:
            return getattr(self, camel_name)

        target_norm = name.lower().replace("_", "")
        for method_name in class_methods:
            if method_name.lower().replace("_", "") == target_norm:
                return getattr(self, method_name)

        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


def _bind_explicit_bidirectional_rpc_aliases(cls):
    """
    Registra explicitamente no dicionário da classe ApiBridge os aliases
    bidirecionais (camelCase <-> snake_case) de todos os métodos públicos.
    Garante que dir(ApiBridge), inspect e o catálogo /api/rpc/contract exponham
    100% da superfície RPC sem depender de fallback invisível em __getattr__.
    """
    public_methods = [
        name for name, attr in list(cls.__dict__.items())
        if not name.startswith("_") and callable(attr)
    ]
    for method_name in public_methods:
        fn = cls.__dict__[method_name]
        for alias in (to_snake_case(method_name), to_camel_case(method_name)):
            if alias and not alias.startswith("_") and alias not in cls.__dict__:
                setattr(cls, alias, fn)


_bind_explicit_bidirectional_rpc_aliases(ApiBridge)
