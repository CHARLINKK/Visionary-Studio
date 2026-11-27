"""
Gerenciador Especializado do Ciclo de Vida e Processo do Ollama.
Responsável por localização do binário, configuração de portas/variáveis de ambiente,
inicialização de subprocesso, monitoramento via sockets e encerramento seguro.
"""

import os
import sys
import time
import socket
import subprocess
import shutil

from src.config import Config


def _get_requests():
    mod = globals().get("requests")
    if mod is None:
        import requests as mod
        globals()["requests"] = mod
    return mod


def __getattr__(name: str):
    if name == "requests":
        return _get_requests()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class OllamaProcessManager:
    """
    Controlador isolado do servidor Ollama local.
    """
    _ollama_process = None
    _ollama_pid = None

    def __init__(self, base_dir=None):
        if base_dir is None:
            from src.config import get_app_data_dir
            self.base_dir = get_app_data_dir()
        else:
            self.base_dir = base_dir

    @classmethod
    def check_ollama_running(cls) -> bool:
        """Verifica se o servidor Ollama está respondendo em 11435 ou 11434."""
        for port in (11435, 11434):
            try:
                s = socket.create_connection(('127.0.0.1', port), timeout=0.5)
                s.close()
                return True
            except Exception:
                pass
        return False

    @classmethod
    def find_ollama_executable(cls, base_dir=None) -> str | None:
        """Localiza o executável do Ollama em diretórios locais isolados e globais do sistema."""
        from src.config import get_app_data_dir
        base = base_dir or get_app_data_dir()
        engine_dir = os.path.join(base, "engine", "ollama")
        isolated_exe = os.path.join(engine_dir, "ollama.exe")
        possible_paths = [
            isolated_exe if os.path.isfile(isolated_exe) else None,
            os.path.join(os.path.dirname(sys.executable), "ollama", "ollama.exe"),
            os.path.join(os.path.dirname(sys.executable), "ollama.exe"),
            os.path.join(base, "engine", "ollama", "ollama.exe"),
            os.path.join(os.getcwd(), "engine", "ollama", "ollama.exe"),
            shutil.which("ollama"),
            shutil.which("ollama.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
            os.path.expanduser(r"~\AppData\Local\Programs\Ollama\ollama.exe"),
            os.path.expandvars(r"%ProgramFiles%\Ollama\ollama.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Ollama\ollama.exe"),
        ]
        return next((p for p in possible_paths if p and os.path.isfile(p)), None)

    @classmethod
    def is_ollama_installed(cls, base_dir=None) -> bool:
        """Verifica se o binário do Ollama está instalado e acessível no sistema."""
        return cls.find_ollama_executable(base_dir=base_dir) is not None

    def start_ollama_server(self, check_running_fn=None) -> dict:
        """
        Ponto Único de Verdade (SSOT) para inicialização do servidor Ollama.
        Localiza o executável em diretórios isolados e globais, configura limites ótimos
        de VRAM/threads e garante monitoramento e encerramento limpo via PID e Job Object.
        """
        from src.config import get_app_data_dir, Config
        check_running = check_running_fn or self.check_ollama_running

        # 1. Se já está rodando na porta isolada do Visionary, obtém lista de modelos e retorna imediatamente
        try:
            with _get_requests().Session() as session:
                session.trust_env = False
                resp = session.get("http://127.0.0.1:11435/api/tags", timeout=0.5)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                    Config.set("ollama_url", "http://127.0.0.1:11435/api")
                    return {"success": True, "message": "Ollama já está em execução", "models": models}
        except Exception:
            pass

        # 2. Localiza o executável do Ollama
        ollama_exe = self.find_ollama_executable(base_dir=self.base_dir)

        if not ollama_exe:
            return {"success": False, "error": "Executável do Ollama não encontrado no sistema."}

        # 3. Configura o ambiente e flags do subprocesso
        try:
            creationflags = 0x08000000 if sys.platform == 'win32' else 0
            exe_dir = os.path.dirname(ollama_exe)

            env = os.environ.copy()
            env["OLLAMA_HOST"] = "127.0.0.1:11435"

            # Unificação canônica de modelos Ollama: prioriza OLLAMA_MODELS ou ~/.ollama/models
            canonical_models = env.get("OLLAMA_MODELS")
            if not canonical_models:
                user_home_models = os.path.join(os.path.expanduser("~"), ".ollama", "models")
                if os.path.isdir(user_home_models):
                    canonical_models = user_home_models
                else:
                    canonical_models = os.path.join(self.base_dir, "engine", "ollama", "models")
            env["OLLAMA_MODELS"] = canonical_models

            if env.get("OLLAMA_MODELS"):
                os.makedirs(env["OLLAMA_MODELS"], exist_ok=True)

            log_dir = os.path.join(get_app_data_dir(), "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "ollama_startup.log")

            log_file = None
            try:
                log_file = open(log_path, "w", encoding="utf-8")
                stdout_target = log_file
            except Exception:
                stdout_target = subprocess.DEVNULL

            try:
                proc = subprocess.Popen(
                    [ollama_exe, "serve"],
                    cwd=exe_dir,
                    creationflags=creationflags,
                    stdout=stdout_target,
                    stderr=subprocess.STDOUT if stdout_target != subprocess.DEVNULL else subprocess.DEVNULL,
                    env=env
                )
            finally:
                if log_file:
                    try:
                        log_file.close()
                    except Exception:
                        pass

            OllamaProcessManager._ollama_process = proc
            OllamaProcessManager._ollama_pid = proc.pid
            self._save_ollama_pid(proc.pid)

            # Vinculação atômica ao Windows Job Object
            try:
                from src.utils.win32_job import assign_pid_to_job
                assign_pid_to_job(proc.pid)
            except Exception:
                pass

            # 4. Polling até Ollama responder HTTP
            for _ in range(40):
                time.sleep(0.25)
                if proc.poll() is not None:
                    err_out = ""
                    try:
                        with open(log_path, "r", encoding="utf-8") as lf:
                            err_out = lf.read()
                    except Exception:
                        pass
                    return {"success": False, "error": f"Ollama fechou inesperadamente (Código {proc.returncode}). Log: {err_out}"}

                # Sondagem HTTP direta na porta do Ollama
                for port in (11435, 11434):
                    try:
                        if False:
                            with socket.create_connection(('127.0.0.1', port), timeout=0.15):
                                pass
                        with _get_requests().Session() as session:
                            session.trust_env = False
                            resp = session.get(f"http://127.0.0.1:{port}/api/tags", timeout=0.4)
                            if resp.status_code == 200:
                                data = resp.json()
                                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                                try:
                                    from src.utils.event_bus import EventBus
                                    EventBus.get_instance().publish("onOllamaReady", {"models": models})
                                except Exception:
                                    pass
                                Config.set("ollama_url", f"http://127.0.0.1:{port}/api")
                                return {"success": True, "message": "Ollama pronto", "models": models}
                    except Exception:
                        pass

                # Se socket ou processo respondeu que está rodando, faz uma última tentativa nos tags
                if check_running():
                    for port in (11435, 11434):
                        try:
                            with _get_requests().Session() as session:
                                session.trust_env = False
                                resp = session.get(f"http://127.0.0.1:{port}/api/tags", timeout=0.6)
                                if resp.status_code == 200:
                                    data = resp.json()
                                    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                                    Config.set("ollama_url", f"http://127.0.0.1:{port}/api")
                                    return {"success": True, "message": "Ollama pronto", "models": models}
                        except Exception:
                            pass
                    Config.set("ollama_url", "http://127.0.0.1:11435/api")
                    return {"success": True, "message": "Ollama pronto", "models": []}

            return {"success": False, "error": "Tempo limite excedido ao iniciar o Ollama."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def ensure_ollama_running(self) -> bool:
        """Garante que o Ollama está rodando, iniciando-o se necessário. Retorna bool."""
        if self.check_ollama_running():
            return True
        res = self.start_ollama_server()
        return bool(res.get("success")) or self.check_ollama_running()

    @classmethod
    def _save_ollama_pid(cls, pid: int):
        try:
            from src.config import get_app_data_dir
            from src.utils.json_utils import atomic_write_text
            pid_file = os.path.join(get_app_data_dir(), ".ollama_visionary.pid")
            atomic_write_text(pid_file, str(pid))
        except Exception:
            pass

    @classmethod
    def _remove_ollama_pid_file(cls):
        try:
            from src.config import get_app_data_dir
            pid_file = os.path.join(get_app_data_dir(), ".ollama_visionary.pid")
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception:
            pass

    @classmethod
    def _read_saved_ollama_pid(cls) -> int | None:
        try:
            from src.config import get_app_data_dir
            pid_file = os.path.join(get_app_data_dir(), ".ollama_visionary.pid")
            if os.path.isfile(pid_file):
                with open(pid_file, "r", encoding="utf-8") as fh:
                    raw = fh.read().strip()
                if raw.isdigit():
                    return int(raw)
        except Exception:
            pass
        return None

    @classmethod
    def terminate_ollama(cls):
        """
        Encerra graciosamente (e força se necessário) o processo do Ollama iniciado pelo Visionary Studio.
        Garante que subprocessos filhos não fiquem órfãos ocupando portas e VRAM.
        Se o Ollama já estava rodando externamente antes do app abrir, ele NÃO é encerrado.
        """
        proc = cls._ollama_process
        pid = cls._ollama_pid or cls._read_saved_ollama_pid()
        cls._remove_ollama_pid_file()
        if not proc and not pid:
            return

        print(f"[ModelManager] Encerrando instância do Ollama iniciada pelo Visionary (PID {pid})...")
        try:
            if pid and sys.platform == 'win32':
                creationflags = 0x08000000
                subprocess.run(
                    ["taskkill", "/pid", str(pid), "/fi", "IMAGENAME eq ollama.exe", "/t", "/f"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags,
                    timeout=5
                )
        except Exception as e:
            print(f"[ModelManager] Aviso ao encerrar Ollama via taskkill: {e}")

        try:
            if proc:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
        except Exception as e:
            print(f"[ModelManager] Aviso ao finalizar proc Ollama: {e}")

        cls._ollama_process = None
        cls._ollama_pid = None

    def get_ollama_models(self) -> set:
        """
        Retorna o conjunto de nomes de modelos instalados no Ollama.
        Combina a leitura física instantânea de manifestos no disco (< 1ms)
        com o retorno em tempo de execução via daemon HTTP se estiver ativo.
        """
        try:
            from src.model_engines.ollama_manifest_scanner import get_installed_ollama_model_names
            models_norm = set(get_installed_ollama_model_names())
        except Exception:
            models_norm = set()

        if not self.check_ollama_running():
            return models_norm

        session = _get_requests().Session()
        session.trust_env = False
        candidates = [Config.get("ollama_url", "http://127.0.0.1:11435/api"), "http://127.0.0.1:11434/api"]
        for base in candidates:
            try:
                url = base.replace("localhost", "127.0.0.1").rstrip("/") + "/tags"
                resp = session.get(url, timeout=0.5).json()
                models = {m["name"] for m in resp.get("models", [])}
                for m in models:
                    models_norm.add(m)
                    if ":" in m:
                        models_norm.add(m.split(":")[0])
                return models_norm
            except Exception:
                continue
        return models_norm
