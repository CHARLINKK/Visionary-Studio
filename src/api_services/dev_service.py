import os
import sys
import subprocess
import threading
import time
import gc
import re

from src.utils.stream_interceptor import StreamInterceptor, IGNORED_LOG_PATTERNS
from src.api_services.dev_test_runner import (
    TEST_LABELS,
    estimate_total_tests,
    get_test_files_list,
    run_pytest_process,
    run_internal_diagnostics,
)


class DevService:
    """
    Coordenador de Diagnóstico, Logs e Telemetria em Tempo Real (Dev & Release).
    Delega a interceptação de streams para StreamInterceptor e execução de testes para DevTestRunner.
    """

    def __init__(self, bridge=None):
        self.bridge = bridge
        self._test_process = None

        self._test_logs = []
        self._app_logs = []

        self._is_test_running = False
        initial_total = self._estimate_total_tests()
        self._test_progress = {
            "running": False,
            "percent": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": initial_total,
            "current_test": "",
        }

        self._lock = threading.RLock()

        # Intercept stdout and stderr de forma segura (evita aninhamento recursivo em re-instanciação)
        if not isinstance(sys.stdout, StreamInterceptor):
            self._stdout_interceptor = StreamInterceptor(sys.stdout, self._app_logs, self._lock)
            sys.stdout = self._stdout_interceptor
        else:
            self._stdout_interceptor = sys.stdout

        if not isinstance(sys.stderr, StreamInterceptor):
            self._stderr_interceptor = StreamInterceptor(sys.stderr, self._app_logs, self._lock)
            sys.stderr = self._stderr_interceptor
        else:
            self._stderr_interceptor = sys.stderr

        self._append_app_log(">>> DEV LOGGER INICIADO <<<")

    def _get_base_dir(self) -> str:
        return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

    def _estimate_total_tests(self) -> int:
        return estimate_total_tests(self._get_base_dir())

    def _append_app_log(self, text):
        with self._lock:
            if len(self._app_logs) > 2000:
                del self._app_logs[:500]
            self._app_logs.append(text)
        try:
            from src.utils.event_bus import event_bus

            event_bus.publish("dev:log", {"stream": "app", "line": text})
        except Exception:
            pass

    def _append_test_log(self, text):
        with self._lock:
            if len(self._test_logs) > 2000:
                del self._test_logs[:500]
            self._test_logs.append(text)
        try:
            from src.utils.event_bus import event_bus

            event_bus.publish("dev:log", {"stream": "test", "line": text})
        except Exception:
            pass

    def _set_test_process(self, proc):
        self._test_process = proc

    def getDevStats(self):
        cuda_avail = False
        torch_ver = "N/A"
        device_name = "CPU"
        torch_mod = None
        best_idx = 0
        try:
            import torch
            from src.api_services.hardware_service import HardwareService

            torch_mod = torch
            cuda_avail = torch.cuda.is_available()
            torch_ver = torch.__version__
            if cuda_avail:
                best_idx = HardwareService._select_best_torch_device(torch)
                device_name = torch.cuda.get_device_name(best_idx)
            else:
                device_name = "CPU"
        except Exception:
            pass

        stats = {
            "torch_version": torch_ver,
            "cuda_available": cuda_avail,
            "device_name": device_name,
            "vram_total": 0,
            "vram_allocated_global": 0,
            "vram_allocated_pytorch": 0,
            "vram_reserved": 0,
            "vram_total_gb": 0,
            "vram_used_gb": 0,
            "vram_free_gb": 0,
            "vram_pct": 0,
            "models_status": self._check_models(),
            "loaded_in_vram": {},
        }

        if cuda_avail and torch_mod:
            try:
                total_mb = torch_mod.cuda.get_device_properties(best_idx).total_memory / (1024**2)
                stats["vram_total"] = total_mb
            except Exception:
                total_mb = 0

            # Tenta pegar a VRAM GLOBAL via nvidia-smi (para não ficar 0.0 quando ociosos)
            global_vram_used = 0
            try:
                c_flags = 0x08000000 if sys.platform == "win32" else 0
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,nounits,noheader"],
                    stdout=subprocess.PIPE,
                    text=True,
                    timeout=1.5,
                    creationflags=c_flags,
                )
                if result.stdout:
                    lines = [ln.strip() for ln in result.stdout.strip().split("\n") if ln.strip()]
                    if lines:
                        idx_to_use = best_idx if best_idx < len(lines) else 0
                        global_vram_used = float(lines[idx_to_use])
            except Exception:
                pass

            if global_vram_used > 0:
                stats["vram_allocated_global"] = global_vram_used / 1024
            else:
                stats["vram_allocated_global"] = 0

            try:
                stats["vram_allocated_pytorch"] = torch_mod.cuda.memory_allocated(best_idx) / (1024**2)
                stats["vram_reserved"] = torch_mod.cuda.memory_reserved(best_idx) / (1024**2)
            except Exception:
                pass

            # Métricas calculadas para exibição no Gauge
            v_total_gb = round(stats["vram_total"] / 1024, 2) if stats["vram_total"] else 0
            v_used_gb = round(stats["vram_allocated_global"], 2)
            v_free_gb = round(max(0, v_total_gb - v_used_gb), 2) if v_total_gb > 0 else 0
            v_pct = int((v_used_gb / v_total_gb) * 100) if v_total_gb > 0 else 0

            stats["vram_total_gb"] = v_total_gb
            stats["vram_used_gb"] = v_used_gb
            stats["vram_free_gb"] = v_free_gb
            stats["vram_pct"] = min(100, max(0, v_pct))

        # Modelos ativos em memória (Live VRAM Inspector)
        loaded_models = {}
        ollama_online = False
        try:
            import socket

            with socket.create_connection(("127.0.0.1", 11435), timeout=0.2):
                ollama_online = True
        except Exception:
            ollama_online = False
        loaded_models["Ollama"] = {"active": ollama_online, "key": "ollama", "can_unload": False, "label": "Serviço LLM Local"}

        stats["loaded_in_vram"] = loaded_models
        return stats

    def _check_models(self):
        from src.config import get_app_data_dir

        base_dir = self._get_base_dir()
        app_data_dir = str(get_app_data_dir())
        model_dirs = [os.path.join(app_data_dir, "models"), os.path.join(base_dir, "models")]

        def _exists_in_models(*rel_candidates):
            for mdir in model_dirs:
                for rel in rel_candidates:
                    if os.path.exists(os.path.join(mdir, *rel)):
                        return True
            return False

        return {
            "florence2_vision": _exists_in_models(
                ("florence-2-large", "model.safetensors"),
                ("florence-2-base", "model.safetensors"),
            ),
            "yolo_layout": _exists_in_models(("best.pt",)),
            "bubble_detector": _exists_in_models(("comic-speech-bubble-detector.pt",)),
        }

    def clearVRAM(self):
        self._append_app_log("[DEV] Solicitada limpeza agressiva de VRAM...")
        from src.utils.gpu_utils import cleanup_gpu_memory

        cleanup_gpu_memory()

        # Descarrega modelos do Ollama para liberar VRAM nativa
        try:
            import requests
            from src.config import Config

            base_url = Config.get("ollama_url", "http://127.0.0.1:11435/api").replace("/api", "")
            resp = requests.get(f"{base_url}/api/ps", timeout=1.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                for m in models:
                    requests.post(
                        f"{base_url}/api/generate",
                        json={"model": m["name"], "keep_alive": 0},
                        timeout=1.0,
                    )
                if models:
                    self._append_app_log("[DEV] Modelos do Ollama descarregados da VRAM.")
        except Exception:
            pass

        self._append_app_log("[DEV] VRAM limpa com sucesso.")
        return {"success": True}

    def unloadDevModel(self, model_name="all"):
        self._append_app_log(f"[DEV] Descarregando modelo da GPU: {model_name}...")
        from src.utils.gpu_utils import cleanup_gpu_memory

        cleanup_gpu_memory()
        self._append_app_log("[DEV] Caches PyTorch esvaziados.")
        return {"success": True, "message": f"Modelo '{model_name}' descarregado com sucesso."}

    def getTestList(self):
        return {
            "total_tests_estimate": self._estimate_total_tests(),
            "files": get_test_files_list(self._get_base_dir()),
        }

    def cancelTests(self):
        with self._lock:
            if not self._is_test_running:
                return {"success": False, "error": "Nenhum teste em execução no momento."}
            proc = self._test_process
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            self._append_test_log("\n[DEV] Execução de testes cancelada pelo usuário.")
            self._finish_test_run(return_code=-9)
            return {"success": True, "message": "Execução de testes cancelada com sucesso."}

    def stopTests(self):
        return self.cancelTests()

    def runTests(self, test_name=None):
        estimated_total = self._estimate_total_tests()

        with self._lock:
            if self._is_test_running:
                return {"success": False, "error": "Os testes/diagnósticos já estão em andamento."}
            self._is_test_running = True
            self._test_logs = []
            self._test_progress = {
                "running": True,
                "percent": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": estimated_total if not test_name or test_name == "all" else 0,
                "current_test": "Iniciando suite...",
                "return_code": None,
            }
            initial_snap = dict(self._test_progress)

        try:
            from src.utils.event_bus import event_bus

            event_bus.publish("dev:test_progress", initial_snap)
        except Exception:
            pass

        if getattr(sys, "frozen", False):
            t = threading.Thread(target=self._run_internal_diagnostics, daemon=True)
            t.start()
            return {"success": True, "message": "Iniciando Diagnóstico Seguro do Sistema (Modo Cliente)..."}
        else:
            t = threading.Thread(target=self._run_tests_thread, args=(test_name,), daemon=True)
            t.start()
            suite_desc = f"suíte completa (~{estimated_total} testes)" if not test_name or test_name == "all" else test_name
            return {"success": True, "message": f"Iniciando {suite_desc} via Pytest...", "total_tests_estimate": estimated_total}

    def _run_tests_thread(self, test_name):
        run_pytest_process(
            base_dir=self._get_base_dir(),
            test_name=test_name,
            popen_fn=subprocess.Popen,
            append_log_fn=self._append_test_log,
            lock=self._lock,
            test_progress=self._test_progress,
            finish_fn=self._finish_test_run,
            set_process_fn=self._set_test_process,
        )

    def _run_internal_diagnostics(self):
        run_internal_diagnostics(
            append_log_fn=self._append_test_log,
            finish_fn=self._finish_test_run,
            check_models_fn=self._check_models,
        )

    def _finish_test_run(self, return_code=0):
        with self._lock:
            self._is_test_running = False
            self._test_process = None
            self._test_progress["running"] = False
            self._test_progress["percent"] = 100
            self._test_progress["return_code"] = return_code
            snap = dict(self._test_progress)
        try:
            from src.utils.event_bus import event_bus

            event_bus.publish("dev:test_progress", snap)
        except Exception:
            pass

    def getDevLogs(self):
        with self._lock:
            return {
                "test_running": self._is_test_running,
                "test_progress": dict(self._test_progress),
                "test_logs": list(self._test_logs),
                "app_logs": list(self._app_logs),
            }

    def getDevTestProgress(self):
        with self._lock:
            return {
                "running": self._is_test_running,
                **self._test_progress,
            }
