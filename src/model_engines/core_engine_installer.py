import threading
import time

from src.model_engines.core_installer import (
    _cache_lock,
    build_pip_install_args,
    check_ai_dependencies,
    detect_cuda_target,
    get_cuda_recommendation,
    has_nvidia_gpu,
    measure_torch_footprint_bytes,
)


class CoreEngineInstaller:
    """
    Instalador e Desinstalador especializado para o motor de IA pesado (PyTorch, TorchVision, Transformers):
    - Verificação rápida de integridade e presença de pacotes (sem carregamento lento na memória)
    - Instalação via subprocesso pip com streaming de saída e parser regex de porcentagem / megabytes
    - Desinstalação com limpeza de diretórios residuais em site-packages
    - Detecção e tratamento resiliente de travamentos de DLL na memória no Windows (WinError 5 / Access Denied)
    - Emissão de telemetria de progresso via EventBus
    
    PADRÃO DE PROJETO:
    Atua como uma Fachada (Facade) orquestradora. A lógica pesada foi distribuída nos submódulos
    'dependency_probe.py', 'pip_runner.py' e 'uninstaller.py', mantendo este arquivo enxuto,
    100% retrocompatível com testes e focado exclusivamente no ciclo de vida e concorrência.
    """

    def __init__(self, api_bridge=None, lock=None, install_progress=None):
        self.api = api_bridge
        # Lock de concorrência: se compartilhado com o serviço pai (api_bridge), herda o lock dele;
        # caso contrário, instancia um lock de thread autônomo.
        self._lock = lock if lock is not None else threading.Lock()
        self._install_progress = (
            install_progress
            if install_progress is not None
            else {"log": "", "status": "idle", "percent": 0.0, "message": ""}
        )
        self._last_event_time = 0.0

    def _get_lock(self):
        """Retorna o lock ativo, priorizando o lock compartilhado do ApiBridge se presente."""
        if self.api and hasattr(self.api, "_lock"):
            return self.api._lock
        return self._lock

    def _get_install_progress(self):
        """Retorna o dicionário de progresso, priorizando a referência do ApiBridge."""
        if self.api and hasattr(self.api, "_install_progress"):
            return self.api._install_progress
        return self._install_progress

    def notify_progress(self, throttle_interval: float = 0.0):
        """
        Emite o progresso da instalação via EventBus com rate limiting throttled opcional.
        
        POR QUE O RATE LIMITING (THROTTLE) É CRÍTICO:
        Durante o download ou compilação pelo pip, eventos de I/O chegam a dezenas de vezes por segundo.
        Sem este controle, a camada de WebSocket/IPC seria sobrecarregada, congelando o thread de UI do React.
        """
        now = time.time()
        if throttle_interval > 0.0 and (now - self._last_event_time) < throttle_interval:
            return
        self._last_event_time = now
        try:
            from src.utils.event_bus import event_bus

            with self._get_lock():
                prog = dict(self._get_install_progress())
            event_bus.publish("core_engine_progress", prog)
        except Exception:
            pass

    def check_ai_dependencies(self) -> dict:
        """Verifica a presença das dependências pesadas de IA sem carregá-las na memória."""
        return check_ai_dependencies(self)

    def _has_nvidia_gpu(self) -> bool:
        """Detecta se o host possui GPU NVIDIA compatível antes de forçar wheels CUDA."""
        return has_nvidia_gpu()

    def _detect_cuda_target(self) -> str:
        """Detecta o flavor ideal de wheel PyTorch para o ambiente atual."""
        return detect_cuda_target(self)

    def get_cuda_recommendation(self) -> dict:
        """Retorna diagnóstico completo e recomendação para o pipeline de instalação."""
        return get_cuda_recommendation(self)

    def _build_pip_install_args(self, python_exe: str, req_path: str) -> tuple[list[str], str | None]:
        return build_pip_install_args(self, python_exe, req_path)

    def install_core_engine(self) -> dict:
        """
        Instala o PyTorch e requisitos de IA via pip em thread desacoplada.
        
        MECÂNICA DE EARLY-EXIT:
        Se os pacotes já estiverem no disco e com integridade confirmada, retorna sucesso
        imediato (percent=100%) em 10ms, sem disparar processos pip redundantes.
        """
        deps = self.check_ai_dependencies()
        if deps.get("ai_state") == "installed" and deps.get("has_torch") and deps.get("has_transformers"):
            with self._get_lock():
                progress = self._get_install_progress()
                progress["status"] = "completed"
                progress["percent"] = 100.0
                progress["speed_mbps"] = 0.0
                progress["eta_seconds"] = 0
                progress["log"] = "Motor de IA (PyTorch e Transformers) já está instalado e operacional.\n"
                progress["message"] = "Motor já instalado."
            self.notify_progress(throttle_interval=0.0)
            return {
                "success": True,
                "already_installed": True,
                "message": "Motor de IA (PyTorch e Transformers) já está instalado e operacional.",
            }

        # Impede a inicialização de múltiplas operações concorrentes de pip
        with self._get_lock():
            progress = self._get_install_progress()
            if progress.get("status") in ["installing", "uninstalling"]:
                return {"success": False, "message": "Operação já em andamento"}
            progress["status"] = "installing"
            progress["percent"] = 0.0
            progress["speed_mbps"] = 0.0
            progress["eta_seconds"] = 0
            progress["downloaded_bytes"] = 0
            progress["total_bytes"] = 0
            progress["log"] = (
                "Iniciando download e instalação do motor de IA...\n"
                "Isso pode demorar vários minutos. Por favor, aguarde...\n"
            )
            progress["message"] = "Resolvendo pacotes PyTorch..."
        self.notify_progress(throttle_interval=0.0)

        from src.model_engines.core_installer.pip_runner import run_pip_install_worker

        # Dispara o worker em thread daemon=False para garantir que downloads iniciados concluam com segurança
        threading.Thread(target=run_pip_install_worker, args=(self,), daemon=False).start()
        return {"success": True, "message": "Installation started"}

    # Aliases camelCase para compatibilidade com a bridge RPC do Electron
    installCoreEngine = install_core_engine

    @staticmethod
    def _measure_torch_footprint_bytes(site_dirs: list) -> int:
        """Mede rapidamente (via os.scandir) o tamanho físico restante de torch/torchvision/torchaudio/~orch*."""
        return measure_torch_footprint_bytes(site_dirs)

    def uninstall_core_engine(self) -> dict:
        """
        Desinstala o PyTorch e aceleradores GPU de IA em thread desacoplada.
        """
        with self._get_lock():
            progress = self._get_install_progress()
            if progress.get("status") in ["installing", "uninstalling"]:
                return {"success": False, "message": "Uma operação já está em andamento."}
            progress["status"] = "uninstalling"
            progress["percent"] = 5.0
            progress["speed_mbps"] = 0.0
            progress["eta_seconds"] = 0
            progress["log"] = "Desinstalando PyTorch e aceleradores GPU...\n"
            progress["message"] = "Desinstalando PyTorch..."
        self.notify_progress(throttle_interval=0.0)

        from src.model_engines.core_installer.uninstaller import run_pip_uninstall_worker

        threading.Thread(target=run_pip_uninstall_worker, args=(self,), daemon=False).start()
        return {"success": True, "message": "Desinstalação iniciada."}

    # Alias camelCase
    uninstallCoreEngine = uninstall_core_engine

    def get_install_progress(self) -> dict:
        """Retorna uma cópia thread-safe do estado atual da operação."""
        with self._get_lock():
            return dict(self._get_install_progress())

    # Alias camelCase
    getInstallProgress = get_install_progress


__all__ = ["CoreEngineInstaller", "_cache_lock"]
