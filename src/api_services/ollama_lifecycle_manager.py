import time
import socket
import threading
import urllib.parse

from src.config import Config
from src.model_manager import ModelManager


def _get_requests():
    mod = globals().get("requests")
    if mod is None:
        import requests as mod
        globals()["requests"] = mod
    return mod


def _get_webbrowser():
    mod = globals().get("webbrowser")
    if mod is None:
        import webbrowser as mod
        globals()["webbrowser"] = mod
    return mod


def __getattr__(name: str):
    if name == "requests":
        return _get_requests()
    if name == "webbrowser":
        return _get_webbrowser()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class OllamaLifecycleManager:
    """
    Gerenciador modular para o ciclo de vida do Ollama:
    - Verificação de portas e saúde do servidor (endpoints /api/tags)
    - Iniciar, parar e inicialização silenciosa em segundo plano (auto-start)
    - Emissão de telemetria em tempo real via EventBus
    - Delegação coesa para `ollama_isolated_installer` e `ollama_model_puller`.
    """

    def __init__(
        self,
        api_bridge=None,
        model_manager=None,
        downloads=None,
        completed_models=None,
        cancel_events=None,
        active_sessions=None,
        lock=None,
        get_downloads_provider=None,
    ):
        self.api = api_bridge
        self.model_manager = model_manager
        self._lock = lock if lock is not None else threading.Lock()
        self._downloads = downloads if downloads is not None else {}
        self._completed_models = completed_models if completed_models is not None else set()
        self._cancel_events = cancel_events if cancel_events is not None else {}
        self._active_sessions = active_sessions if active_sessions is not None else {}
        self._ollama_start_lock = threading.Lock()
        self._ollama_starting = False
        self._ollama_installing = False
        self._ollama_install_cancel_event = None
        self._ollama_install_progress = {
            "status": "idle",
            "percent": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_mbps": 0.0,
            "eta_seconds": 0,
            "message": "",
            "error": "",
        }
        self._downloads_provider = get_downloads_provider
        self._last_event_time = 0.0
        self._tags_cache_time = 0.0
        self._tags_cache_data = None

    def _get_lock(self):
        if self.api and hasattr(self.api, "_lock"):
            return self.api._lock
        return self._lock

    def _get_downloads(self):
        if self.api and hasattr(self.api, "_ollama_downloads"):
            return self.api._ollama_downloads
        return self._downloads

    def _get_ollama_tags_cached(self, max_age_sec: float = 2.0):
        now = time.time()
        if self._tags_cache_data is not None and (now - self._tags_cache_time) < max_age_sec:
            return self._tags_cache_data

        active_port = getattr(self, "_active_port", None)
        url_str = Config.get("ollama_url", "http://127.0.0.1:11435/api")
        ports = []
        if active_port and active_port not in ports:
            ports.append(active_port)
        try:
            parsed = urllib.parse.urlparse(url_str)
            if parsed.port and parsed.port not in ports:
                ports.append(parsed.port)
        except Exception:
            pass
        for p in (11435, 11434):
            if p not in ports:
                ports.append(p)

        for port in ports:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.15):
                    pass
            except Exception:
                continue

            try:
                with _get_requests().Session() as session:
                    session.trust_env = False
                    url = f"http://127.0.0.1:{port}/api/tags"
                    resp = session.get(url, timeout=0.8)
                    if resp.status_code == 200:
                        data = resp.json()
                        self._tags_cache_data = data
                        self._tags_cache_time = now
                        self._active_port = port
                        Config.set("ollama_url", f"http://127.0.0.1:{port}/api")
                        return data
            except Exception:
                continue
        return self._tags_cache_data

    def invalidate_tags_cache(self):
        self._tags_cache_time = 0.0
        self._tags_cache_data = None

    def notify_progress(self, throttle_interval: float = 0.0):
        """Dispara evento de telemetria via EventBus com rate limit throttled opcional."""
        now = time.time()
        if throttle_interval > 0.0 and (now - self._last_event_time) < throttle_interval:
            return
        self._last_event_time = now
        try:
            from src.utils.event_bus import event_bus
            if callable(self._downloads_provider):
                snapshot = self._downloads_provider()
            else:
                snapshot = {
                    "success": True,
                    "ollama": self.get_downloads_snapshot(),
                    "hf": {},
                }
            event_bus.publish("downloads_progress", snapshot)
        except Exception:
            pass

    def get_downloads_snapshot(self) -> dict:
        """Retorna snapshot consolidado dos downloads ativos e concluídos do Ollama."""
        with self._get_lock():
            dls = dict(self._get_downloads())
            completed_set = getattr(self, "_completed_models", set())
            for m in completed_set:
                if m not in dls:
                    dls[m] = {
                        "progress": 100.0,
                        "status": "installed",
                        "text": "Modelo pronto no Ollama",
                        "speed_mbps": 0.0,
                        "eta_seconds": 0,
                    }
        return dls

    def get_install_progress(self) -> dict:
        """Retorna o progresso atual do download/instalação do motor Ollama isolado."""
        with self._get_lock():
            return dict(self._ollama_install_progress)

    def notify_install_progress(self, throttle_interval: float = 0.0):
        """Emite evento de telemetria da instalação do motor Ollama via EventBus."""
        now = time.time()
        if throttle_interval > 0.0 and (now - self._last_event_time) < throttle_interval:
            return
        self._last_event_time = now
        try:
            from src.utils.event_bus import event_bus
            prog = self.get_install_progress()
            event_bus.publish("ollama_install_progress", prog)
        except Exception:
            pass

    def check_ollama_state(self) -> tuple[str, list]:
        """
        Verifica o estado do servidor Ollama e lista os modelos instalados.
        Utiliza o scanner físico de manifestos no SSD (< 1ms) como base determinística
        e une com os metadados do daemon HTTP quando ativo.
        """
        try:
            from src.model_engines.ollama_manifest_scanner import get_installed_ollama_models_list
            disk_models = get_installed_ollama_models_list()
        except Exception:
            disk_models = []

        if getattr(self, "_ollama_installing", False):
            return "installing", disk_models

        data = self._get_ollama_tags_cached(max_age_sec=2.0)
        if data and "models" in data:
            ollama_state = "installed_and_running"
            running_models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            combined = list(running_models)
            for dm in disk_models:
                if dm not in combined:
                    combined.append(dm)
            return ollama_state, combined
        elif getattr(self, "_ollama_starting", False):
            ollama_state = "starting"
            target = self._tags_cache_data
            running_models = [m.get("name", "") for m in target.get("models", []) if m.get("name")] if target else []
            combined = list(running_models)
            for dm in disk_models:
                if dm not in combined:
                    combined.append(dm)
            return ollama_state, combined or disk_models
        elif self.is_running():
            ollama_state = "installed_and_running"
            target = self._tags_cache_data
            running_models = [m.get("name", "") for m in target.get("models", []) if m.get("name")] if target else []
            combined = list(running_models)
            for dm in disk_models:
                if dm not in combined:
                    combined.append(dm)
            return ollama_state, combined or disk_models
        else:
            try:
                from src.model_engines.ollama_process_manager import OllamaProcessManager
                is_installed = OllamaProcessManager.is_ollama_installed()
            except Exception:
                is_installed = bool(disk_models)

            if is_installed or disk_models:
                return "installed_and_stopped", disk_models
            return "not_installed", []

    def is_running(self) -> bool:
        """Verifica de forma rápida e não-bloqueante se o serviço Ollama está ativo."""
        try:
            url_str = Config.get("ollama_url", "http://127.0.0.1:11435/api")
            parsed = urllib.parse.urlparse(url_str)
            host = parsed.hostname or "127.0.0.1"
            cfg_port = parsed.port if parsed.port else 11435

            ports_to_check = []
            active_port = getattr(self, "_active_port", None)
            if active_port and active_port not in ports_to_check:
                ports_to_check.append(active_port)
            if cfg_port not in ports_to_check:
                ports_to_check.append(cfg_port)
            for fallback in (11435, 11434):
                if fallback not in ports_to_check:
                    ports_to_check.append(fallback)

            for port in ports_to_check:
                try:
                    with socket.create_connection((host, port), timeout=0.15):
                        pass
                except Exception:
                    continue

                try:
                    with _get_requests().Session() as session:
                        session.trust_env = False
                        resp = session.get(f"http://{host}:{port}/api/tags", timeout=0.5)
                        if resp.status_code == 200:
                            data = resp.json()
                            self._tags_cache_data = data
                            self._tags_cache_time = time.time()
                            self._active_port = port
                            Config.set("ollama_url", f"http://{host}:{port}/api")
                            return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    isOllamaRunning = is_running

    def ensure_running(self, start_server_fn=None) -> dict:
        """Verifica se o Ollama está ativo. Se não, inicia silenciosamente em segundo plano."""
        if self.is_running():
            return {"success": True, "status": "already_running"}

        with self._ollama_start_lock:
            if getattr(self, "_ollama_starting", False):
                return {"success": True, "status": "already_starting"}
            self._ollama_starting = True

        def _bg_worker():
            try:
                if callable(start_server_fn):
                    start_server_fn()
                else:
                    self.start_server()
            except Exception as e:
                print(f"[OllamaAutoStart] Aviso silencioso: {e}")
            finally:
                with self._ollama_start_lock:
                    self._ollama_starting = False

        t = threading.Thread(target=_bg_worker, daemon=True, name="OllamaSilentAutoStart")
        t.start()
        return {"success": True, "status": "starting"}

    ensureOllamaRunning = ensure_running

    def start_server(self) -> dict:
        """Inicia o servidor Ollama delegando ao ModelManager."""
        try:
            mgr = self.model_manager or ModelManager()
            return mgr.start_ollama_server()
        except Exception as e:
            return {"success": False, "error": str(e)}

    startOllamaServer = start_server

    def stop_server(self) -> dict:
        """Encerra o servidor Ollama se tiver sido iniciado pelo Visionary."""
        try:
            ModelManager.terminate_ollama()
            return {"success": True, "message": "Ollama encerrado com sucesso."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    stopOllamaServer = stop_server

    def open_site(self) -> dict:
        """Abre a página oficial de download do Ollama no navegador."""
        try:
            _get_webbrowser().open("https://ollama.com/download")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    openOllamaSite = open_site

    def cancel_isolated_install(self) -> dict:
        from src.model_engines.ollama_isolated_installer import cancel_isolated_install
        return cancel_isolated_install(self)

    cancelIsolatedInstall = cancel_isolated_install

    def install_isolated_ollama(self, download_url: str = None) -> dict:
        from src.model_engines.ollama_isolated_installer import install_isolated_ollama
        return install_isolated_ollama(self, download_url=download_url, session_factory=_get_requests().Session)

    installIsolatedOllama = install_isolated_ollama
    getOllamaInstallProgress = get_install_progress

    def cancel_download(self, model_name: str) -> dict:
        from src.model_engines.ollama_model_puller import cancel_ollama_download
        return cancel_ollama_download(self, model_name)

    cancelOllamaDownload = cancel_download

    def delete_model(self, model_name: str) -> dict:
        from src.model_engines.ollama_model_puller import delete_ollama_model
        return delete_ollama_model(self, model_name, session_factory=_get_requests().Session)

    deleteOllamaModel = delete_model

    def test_translation(self, model_name: str, prompt: str = None) -> dict:
        from src.model_engines.ollama_model_puller import test_ollama_translation
        return test_ollama_translation(self, model_name, prompt=prompt, session_factory=_get_requests().Session)

    testModelTranslation = test_translation

    def get_ollama_models_details(self) -> dict:
        from src.model_engines.ollama_model_puller import get_ollama_models_details
        return get_ollama_models_details(self)

    def get_ollama_storage_bytes(self) -> int:
        self._get_ollama_tags_cached(max_age_sec=2.0)
        details = self.get_ollama_models_details()
        return sum(info.get("size", 0) for info in details.values())

    def pull_model(self, model_name: str) -> dict:
        from src.model_engines.ollama_model_puller import pull_ollama_model
        return pull_ollama_model(self, model_name, session_factory=_get_requests().Session)

    pullOllamaModel = pull_model
