import os
import threading
from src.config import Config
from src.model_manager import ModelManager, MODELS_REGISTRY
from src.api_services.ollama_lifecycle_manager import OllamaLifecycleManager
from src.api_services.hf_download_orchestrator import HFDownloadOrchestrator
from src.model_engines.core_engine_installer import CoreEngineInstaller, _cache_lock


class ModelService:
    """
    Fachada de modelos e instalações para o `ApiBridge`.
    Delega cada responsabilidade para `CoreEngineInstaller` (PyTorch/CUDA),
    `HFDownloadOrchestrator` (YOLO/Florence) e `OllamaLifecycleManager` (LLM local),
    compartilhando o estado de progresso com o bridge para não quebrar callers antigos.
    """

    def __init__(
        self,
        model_manager=None,
        api_bridge=None,
        ollama_manager=None,
        hf_orchestrator=None,
        core_installer=None,
    ):
        # Chamadores antigos passam `api_bridge` no 1º argumento posicional; detectamos pelo tipo/interface
        if isinstance(model_manager, ModelManager):
            self.model_manager = model_manager
            self.api = api_bridge
        elif model_manager is not None and not hasattr(model_manager, "models"):
            self.api = model_manager
            self.model_manager = getattr(self.api, "model_manager", None) or ModelManager()
        else:
            self.api = api_bridge
            self.model_manager = model_manager or (getattr(api_bridge, "model_manager", None) if api_bridge else ModelManager())

        self._lock = threading.Lock()
        self._install_progress = {"log": "", "status": "idle", "percent": 0.0, "message": ""}
        self._ollama_downloads = {}
        self._completed_ollama_models = set()
        self._ollama_cancel_events = {}
        self._ollama_active_sessions = {}

        self.core_installer = core_installer or CoreEngineInstaller(
            api_bridge=self.api,
            lock=self._get_lock(),
            install_progress=self._get_install_progress(),
        )

        self.hf_orchestrator = hf_orchestrator or HFDownloadOrchestrator(
            model_manager=self.model_manager,
            get_downloads_provider=self.getDownloadsProgress,
        )

        self.ollama_mgr = ollama_manager or OllamaLifecycleManager(
            api_bridge=self.api,
            model_manager=self.model_manager,
            downloads=self._get_ollama_downloads(),
            completed_models=self._completed_ollama_models,
            cancel_events=self._ollama_cancel_events,
            active_sessions=self._ollama_active_sessions,
            lock=self._get_lock(),
            get_downloads_provider=self.getDownloadsProgress,
        )

    def _get_lock(self):
        return getattr(self.api, "_lock", self._lock) if self.api else self._lock

    def _get_install_progress(self):
        if self.api and hasattr(self.api, "_install_progress"):
            return self.api._install_progress
        return self._install_progress

    def _get_ollama_downloads(self):
        if self.api and hasattr(self.api, "_ollama_downloads"):
            return self.api._ollama_downloads
        return self._ollama_downloads

    @property
    def _ollama_start_lock(self):
        return self.ollama_mgr._ollama_start_lock

    @property
    def _ollama_starting(self):
        return self.ollama_mgr._ollama_starting

    @_ollama_starting.setter
    def _ollama_starting(self, val):
        self.ollama_mgr._ollama_starting = val

    def checkModulesStatus(self):
        ollama_state, ollama_models = self.ollama_mgr.check_ollama_state()
        deps = self.core_installer.check_ai_dependencies()
        ai_state = deps["ai_state"]

        has_torch = deps.get("has_torch", False)
        has_cuda_torch = deps.get("has_cuda_torch", False)
        has_gpu = self.core_installer._has_nvidia_gpu()

        if ai_state == "installed":
            if has_cuda_torch and has_gpu:
                cuda_state = "installed"
            elif has_gpu and not has_cuda_torch:
                cuda_state = "cpu_only"
            elif not has_gpu:
                cuda_state = "not_supported"
            else:
                cuda_state = "installed"
        else:
            if has_gpu:
                cuda_state = "not_installed"
            else:
                cuda_state = "not_supported"

        cuda_recommendation = getattr(self.core_installer, "get_cuda_recommendation", lambda: {})()

        with self._get_lock():
            ollama_dls = dict(self._get_ollama_downloads())

        details = {}
        if hasattr(self.ollama_mgr, "get_ollama_models_details"):
            raw_details = self.ollama_mgr.get_ollama_models_details()
            if isinstance(raw_details, dict):
                details = raw_details

        return {
            "ollama": {"state": ollama_state},
            "ocr": {"state": ai_state},
            "cuda": {
                "state": cuda_state,
                "torch_cuda": has_cuda_torch,
                "torch_version": deps.get("torch_cuda_version"),
                "has_nvidia_gpu": has_gpu,
                "recommendation": cuda_recommendation,
            },
            "ollamaModels": ollama_models,
            "ollamaModelsDetails": details,
            "ollamaDownloads": ollama_dls,
            "ollamaInstall": self.ollama_mgr.get_install_progress(),
        }

    def installCoreEngine(self):
        return self.core_installer.install_core_engine()

    def uninstallCoreEngine(self):
        return self.core_installer.uninstall_core_engine()

    def getInstallProgress(self):
        return self.core_installer.get_install_progress()

    def getModelsStatus(self):
        try:
            ret = self.model_manager.get_all_status()
            ret["base_dir"] = self.model_manager.base_dir
            return ret
        except Exception as e:
            return {"error": str(e)}

    def getDownloadsProgress(self):
        try:
            if hasattr(self, "_completed_ollama_models"):
                self.ollama_mgr._completed_models = self._completed_ollama_models
            ollama_dls = self.ollama_mgr.get_downloads_snapshot()
            active_hf = self.hf_orchestrator.get_active_hf_status()
            return {
                "success": True,
                "ollama": ollama_dls,
                "hf": active_hf,
                "ollama_install": self.ollama_mgr.get_install_progress(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def downloadHuggingFaceModel(self, key):
        return self.hf_orchestrator.download_model(key)

    def cancelHuggingFaceModel(self, key):
        return self.hf_orchestrator.cancel_model(key)

    cancelModelDownload = cancelHuggingFaceModel

    def deleteHuggingFaceModel(self, key):
        return self.hf_orchestrator.delete_model(key)

    def installIsolatedOllama(self, download_url=None):
        return self.ollama_mgr.install_isolated_ollama(download_url=download_url)

    def cancelIsolatedOllamaInstall(self):
        return self.ollama_mgr.cancel_isolated_install()

    def getOllamaInstallProgress(self):
        return self.ollama_mgr.get_install_progress()

    def cancelOllamaDownload(self, model_name):
        if hasattr(self, "_ollama_cancel_events"):
            self.ollama_mgr._cancel_events = self._ollama_cancel_events
        if hasattr(self, "_ollama_active_sessions"):
            self.ollama_mgr._active_sessions = self._ollama_active_sessions
        return self.ollama_mgr.cancel_download(model_name)

    def deleteOllamaModel(self, model_name):
        if hasattr(self, "_completed_ollama_models"):
            self.ollama_mgr._completed_models = self._completed_ollama_models
        res = self.ollama_mgr.delete_model(model_name)
        if hasattr(self.hf_orchestrator, "invalidate_storage_cache"):
            self.hf_orchestrator.invalidate_storage_cache()
        return res

    def isOllamaRunning(self) -> bool:
        return self.ollama_mgr.is_running()

    def ensureOllamaRunning(self):
        return self.ollama_mgr.ensure_running(start_server_fn=self.startOllamaServer)

    def startOllamaServer(self):
        return self.ollama_mgr.start_server()

    def stopOllamaServer(self):
        return self.ollama_mgr.stop_server()

    def openOllamaSite(self):
        return self.ollama_mgr.open_site()

    def testModelTranslation(self, model_name, prompt=None):
        return self.ollama_mgr.test_translation(model_name, prompt=prompt)

    def pullOllamaModel(self, model_name):
        if hasattr(self, "_ollama_cancel_events"):
            self.ollama_mgr._cancel_events = self._ollama_cancel_events
        if hasattr(self, "_ollama_active_sessions"):
            self.ollama_mgr._active_sessions = self._ollama_active_sessions
        return self.ollama_mgr.pull_model(model_name)

    def getStorageStats(self):
        try:
            ollama_bytes = self.ollama_mgr.get_ollama_storage_bytes()
            return self.hf_orchestrator.get_storage_stats(ollama_bytes=ollama_bytes)
        except Exception as e:
            return {"success": False, "error": str(e)}
