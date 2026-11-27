import sys

class HardwareService:
    def __init__(self, api_bridge=None):
        self.api = api_bridge
        self._cpu_name = None
        self._cpu_cores = None
        self._cpu_threads = None
        self._nvml_initialized = False
        self._nvml_failed = False
        self._consecutive_cuda_failures = 0

    def _get_static_cpu_info(self):
        if self._cpu_name is not None:
            return self._cpu_name, self._cpu_cores, self._cpu_threads

        cpu_name = "Processador / CPU"
        cpu_cores = 0
        cpu_threads = 0

        try:
            import psutil
            cpu_cores = psutil.cpu_count(logical=False) or 0
            cpu_threads = psutil.cpu_count(logical=True) or 0
        except Exception:
            pass

        try:
            if sys.platform == "win32":
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                    raw_name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
                    cpu_name = raw_name.replace("(R)", "").replace("(TM)", "").replace("  ", " ").strip()
            elif sys.platform == "darwin":
                import subprocess
                cpu_name = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
            else:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if "model name" in line:
                            cpu_name = line.split(":", 1)[1].strip()
                            break
        except Exception:
            try:
                import platform
                cpu_name = platform.processor() or "Processador / CPU"
            except Exception:
                pass

        self._cpu_name = cpu_name
        self._cpu_cores = cpu_cores
        self._cpu_threads = cpu_threads
        return cpu_name, cpu_cores, cpu_threads

    @staticmethod
    def _is_integrated_gpu_name(name: str) -> bool:
        low = (name or "").lower()
        if "arc" in low and "integrated" not in low:
            return False
        return any(
            kw in low
            for kw in ("intel", "uhd", "iris", "hd graphics", "radeon(tm) graphics", "microsoft basic", "vega ")
        )

    @classmethod
    def _select_best_torch_device(cls, torch) -> int:
        try:
            count = torch.cuda.device_count()
            if not isinstance(count, int) or count <= 1:
                return 0
            best_idx = 0
            best_key = (-1, -1)
            for idx in range(count):
                name = str(torch.cuda.get_device_name(idx) or "")
                try:
                    _free, total = torch.cuda.mem_get_info(idx)
                except Exception:
                    props = torch.cuda.get_device_properties(idx)
                    total = getattr(props, "total_memory", 0)
                is_discrete = 0 if cls._is_integrated_gpu_name(name) else 1
                cand_key = (is_discrete, int(total))
                if cand_key > best_key:
                    best_key = cand_key
                    best_idx = idx
            return best_idx
        except Exception:
            return 0

    @classmethod
    def _select_best_nvml_handle(cls, pynvml):
        try:
            count = pynvml.nvmlDeviceGetCount()
            if not isinstance(count, int) or count <= 1:
                return pynvml.nvmlDeviceGetHandleByIndex(0)
            best_handle = None
            best_key = (-1, -1)
            for idx in range(count):
                h = pynvml.nvmlDeviceGetHandleByIndex(idx)
                raw_name = pynvml.nvmlDeviceGetName(h)
                name = raw_name.decode("utf-8", errors="ignore") if isinstance(raw_name, bytes) else str(raw_name)
                meminfo = pynvml.nvmlDeviceGetMemoryInfo(h)
                is_discrete = 0 if cls._is_integrated_gpu_name(name) else 1
                cand_key = (is_discrete, int(getattr(meminfo, "total", 0)))
                if cand_key > best_key:
                    best_key = cand_key
                    best_handle = h
            return best_handle if best_handle is not None else pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            return pynvml.nvmlDeviceGetHandleByIndex(0)

    @staticmethod
    def _evaluate_cuda_status(
        cuda_driver_ver: str | None,
        cuda_runtime_ver: str | None,
        cuda_avail: bool,
        gpu_name: str,
        compute_cap: tuple[int, int] | None,
        has_torch: bool,
        is_busy: bool = False
    ) -> dict:
        is_cpu_only_gpu = (gpu_name or "").lower().startswith("nenhum") or "cpu" in (gpu_name or "").lower()
        if is_cpu_only_gpu and not cuda_driver_ver:
            return {
                "status": "no_gpu",
                "message": "Nenhuma GPU NVIDIA detectada no sistema.",
                "action": None,
                "recommended_target": "cpu"
            }

        driver_major = 0
        driver_minor = 0
        if cuda_driver_ver:
            try:
                parts = cuda_driver_ver.split(".")
                driver_major = int(parts[0])
                driver_minor = int(parts[1]) if len(parts) > 1 else 0
            except Exception:
                pass

        if is_busy:
            rec = "cu128" if (driver_major, driver_minor) >= (12, 8) else ("cu124" if (driver_major, driver_minor) >= (12, 4) else "cu121")
            return {
                "status": "ready_for_install",
                "message": f"Configurando motor neural para GPU {gpu_name}...",
                "action": None,
                "recommended_target": rec
            }

        if cuda_driver_ver and (driver_major < 11 or (driver_major == 11 and driver_minor < 8)):
            return {
                "status": "driver_outdated",
                "message": f"Driver NVIDIA desatualizado (suporta apenas CUDA {cuda_driver_ver}). O Visionary requer driver compatível com CUDA >= 11.8.",
                "action": "Atualize o driver da sua GPU NVIDIA no site oficial da NVIDIA.",
                "recommended_target": "cpu"
            }

        if cuda_avail:
            if compute_cap and compute_cap < (7, 0):
                cap_str = f"{compute_cap[0]}.{compute_cap[1]}"
                return {
                    "status": "limited_architecture",
                    "message": f"GPU {gpu_name} (CC {cap_str}) possui suporte FP16 limitado. Inferência operará com aceleração reduzida.",
                    "action": "Recomenda-se GPU Turing/Ampere/Ada (GTX 16xx / RTX 20xx+) para desempenho total FP16.",
                    "recommended_target": "cu121"
                }
            return {
                "status": "ok",
                "message": f"Aceleração neural ativa na GPU {gpu_name} (CUDA {cuda_runtime_ver or cuda_driver_ver}).",
                "action": None,
                "recommended_target": None
            }

        # Se não há cuda_avail ativo:
        if has_torch:
            if cuda_runtime_ver is None:
                rec = "cu128" if (driver_major, driver_minor) >= (12, 8) else ("cu124" if (driver_major, driver_minor) >= (12, 4) else "cu121")
                return {
                    "status": "cpu_only",
                    "message": f"GPU {gpu_name} detectada, mas o PyTorch instalado opera em modo CPU (sem binários CUDA).",
                    "action": "Reinstale o Motor Central de IA na Central de Módulos para ativar a aceleração por GPU.",
                    "recommended_target": rec
                }
            else:
                return {
                    "status": "driver_mismatch",
                    "message": f"PyTorch possui binários CUDA {cuda_runtime_ver}, mas o subsistema CUDA não respondeu para a GPU {gpu_name}.",
                    "action": "Verifique a integridade do driver de vídeo ou reinstale o driver NVIDIA.",
                    "recommended_target": "cu121"
                }

        # PyTorch ainda não instalado
        rec = "cu128" if (driver_major, driver_minor) >= (12, 8) else ("cu124" if (driver_major, driver_minor) >= (12, 4) else "cu121")
        return {
            "status": "ready_for_install",
            "message": f"GPU {gpu_name} compatível com CUDA {cuda_driver_ver or '12.x'}. Pronta para receber aceleração neural.",
            "action": "Instale o Motor Central de IA para ativar a GPU.",
            "recommended_target": rec
        }

    def getHardwareStats(self):
        try:
            import psutil
            # Leitura instantânea não-bloqueante (0ms de latência)
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            ram_pct = mem.percent
            ram_used = mem.used / (1024 ** 3)
            ram_total = mem.total / (1024 ** 3)
        except Exception:
            cpu_pct, ram_pct, ram_used, ram_total = 0, 0, 0, 0

        vram_alloc, vram_res = 0, 0
        gpu_temp = None
        gpu_name = "Nenhum / CPU"
        cuda_version = None
        cuda_driver_version = None
        cuda_runtime_version = None
        cuda_available = False
        cuda_device_capability = None

        is_busy = False
        if self.api and hasattr(self.api, "_install_progress"):
            try:
                prog = getattr(self.api, "_install_progress", {})
                is_busy = prog.get("status") in ("installing", "uninstalling")
            except Exception:
                pass

        # 1. Tenta identificar métricas via PyTorch se torch já estiver carregado em memória (zero-latency)
        if "torch" in sys.modules and sys.modules["torch"] is not None:
            torch_mod = sys.modules["torch"]
            mod_file = getattr(torch_mod, "__file__", None)
            mod_spec = getattr(torch_mod, "__spec__", None)
            is_stale_real_module = False
            if isinstance(mod_file, str) and not mod_file.startswith("/path/to/"):
                import os
                if not os.path.isfile(mod_file):
                    is_stale_real_module = True
            elif mod_file is None and mod_spec is not None and getattr(mod_spec, "origin", None) is None:
                # PEP 420 namespace package (ex: pasta residual site-packages/torch/lib sem __init__.py)
                is_stale_real_module = True
            if not hasattr(torch_mod, "cuda") and not hasattr(torch_mod, "version"):
                is_stale_real_module = True
            if is_stale_real_module:
                for k in list(sys.modules.keys()):
                    if k == "torch" or k.startswith("torch."):
                        sys.modules.pop(k, None)

        if "torch" in sys.modules and sys.modules["torch"] is not None and not is_busy:
            try:
                torch = sys.modules["torch"]
                if hasattr(torch, "cuda") and torch.cuda.is_available():
                    cuda_available = True
                    self._consecutive_cuda_failures = 0
                    dev_idx = self._select_best_torch_device(torch)
                    gpu_name = torch.cuda.get_device_name(dev_idx)
                    cuda_runtime_version = getattr(torch.version, "cuda", None)
                    cuda_version = cuda_runtime_version
                    try:
                        cap = torch.cuda.get_device_capability(dev_idx)
                        cuda_device_capability = f"{cap[0]}.{cap[1]}"
                    except Exception:
                        pass
                    free, total = torch.cuda.mem_get_info(dev_idx)
                    vram_res = total / (1024 ** 3)
                    vram_alloc = (total - free) / (1024 ** 3)
                else:
                    cuda_runtime_version = getattr(getattr(torch, "version", None), "cuda", None)
            except Exception:
                pass

        # 2. Identifica temperatura, nome, VRAM e versão CUDA via pynvml (ultra-rápido, ~1ms, sem carregar DLLs do PyTorch)
        if not self._nvml_failed:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=FutureWarning)
                    import pynvml

                if not self._nvml_initialized:
                    pynvml.nvmlInit()
                    self._nvml_initialized = True

                handle = self._select_best_nvml_handle(pynvml)
                try:
                    gpu_temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except Exception:
                    gpu_temp = None

                if gpu_name == "Nenhum / CPU":
                    raw_gpu = pynvml.nvmlDeviceGetName(handle)
                    gpu_name = raw_gpu.decode("utf-8", errors="ignore") if isinstance(raw_gpu, bytes) else str(raw_gpu)

                try:
                    driver_ver = pynvml.nvmlSystemGetCudaDriverVersion()
                    if driver_ver:
                        major = driver_ver // 1000
                        minor = (driver_ver % 1000) // 10
                        cuda_driver_version = f"{major}.{minor}"
                except Exception:
                    pass

                if not cuda_device_capability:
                    try:
                        if hasattr(pynvml, "nvmlDeviceGetCudaComputeCapability"):
                            cap = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                            if cap and isinstance(cap, (tuple, list)) and len(cap) == 2:
                                cuda_device_capability = f"{cap[0]}.{cap[1]}"
                    except Exception:
                        pass

                if vram_res == 0:
                    meminfo = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    vram_res = meminfo.total / (1024 ** 3)
                    vram_alloc = meminfo.used / (1024 ** 3)
            except Exception:
                self._nvml_failed = True

        # 3. Checagem leve de presença do Torch sem carregamento pesado (zero DLL lock no Windows)
        has_torch = "torch" in sys.modules and sys.modules["torch"] is not None and not is_busy
        if not has_torch and not is_busy:
            try:
                import importlib
                import importlib.util
                import os
                import re
                importlib.invalidate_caches()
                spec = importlib.util.find_spec("torch")
                if spec is not None and getattr(spec, "has_location", False):
                    origin = getattr(spec, "origin", "") or ""
                    if os.path.isfile(origin):
                        v_path = os.path.join(os.path.dirname(origin), "version.py")
                        if os.path.isfile(v_path):
                            has_torch = True
                            if cuda_runtime_version is None:
                                try:
                                    with open(v_path, "r", encoding="utf-8", errors="ignore") as vf:
                                        m = re.search(r"cuda\s*(?::\s*[^=]+)?=\s*['\"]([^'\"]+)['\"]", vf.read())
                                        if m:
                                            cuda_runtime_version = m.group(1)
                                except Exception:
                                    pass
                        else:
                            has_torch = True
            except Exception:
                pass

        # 4.1 Validação do subsistema CUDA sem forçar import de C-extensions no processo principal da API
        if has_torch and not is_busy:
            torch_loaded = "torch" in sys.modules and sys.modules["torch"] is not None
            if not cuda_available and torch_loaded:
                try:
                    torch = sys.modules["torch"]
                    if hasattr(torch, "cuda") and torch.cuda.is_available():
                        cuda_available = True
                        self._consecutive_cuda_failures = 0
                        if not cuda_runtime_version:
                            cuda_runtime_version = getattr(getattr(torch, "version", None), "cuda", None)
                        if gpu_name == "Nenhum / CPU":
                            dev_idx = self._select_best_torch_device(torch)
                            gpu_name = torch.cuda.get_device_name(dev_idx)
                        if vram_res == 0:
                            try:
                                dev_idx = self._select_best_torch_device(torch)
                                free, total = torch.cuda.mem_get_info(dev_idx)
                                vram_res = total / (1024 ** 3)
                                vram_alloc = (total - free) / (1024 ** 3)
                            except Exception:
                                pass
                        if not cuda_device_capability:
                            try:
                                dev_idx = self._select_best_torch_device(torch)
                                cap = torch.cuda.get_device_capability(dev_idx)
                                cuda_device_capability = f"{cap[0]}.{cap[1]}"
                            except Exception:
                                pass
                except Exception:
                    if "torch" in sys.modules and not hasattr(sys.modules["torch"], "cuda"):
                        sys.modules.pop("torch", None)

            if not cuda_available and cuda_runtime_version and gpu_name != "Nenhum / CPU":
                driver_ok = True
                if cuda_driver_version:
                    try:
                        d_parts = cuda_driver_version.split(".")
                        d_maj = int(d_parts[0])
                        d_min = int(d_parts[1]) if len(d_parts) > 1 else 0
                        driver_ok = (d_maj, d_min) >= (11, 8)
                    except Exception:
                        pass
                if driver_ok:
                    if not torch_loaded:
                        # PyTorch em disco, não importado no processo da API: assume compatibilidade com base nos binários e driver
                        cuda_available = True
                        self._consecutive_cuda_failures = 0
                    else:
                        # PyTorch carregado em memória, mas CUDA ainda não respondeu (aquecimento/handshake de DLLs a frio no Windows)
                        self._consecutive_cuda_failures += 1
                        if self._consecutive_cuda_failures < 3:
                            # Janela de debouncing/graça (até 3 segundos) para evitar flash de aviso falso
                            cuda_available = True
                        else:
                            # Falha persistente após 3 tentativas consecutivas: subsistema CUDA realmente não respondeu
                            cuda_available = False
            elif cuda_available:
                self._consecutive_cuda_failures = 0
        elif not has_torch:
            self._consecutive_cuda_failures = 0

        # 5. Ajuste de compatibilidade para cuda_version
        if cuda_available:
            cuda_version = cuda_runtime_version or cuda_driver_version
        else:
            if has_torch and (cuda_runtime_version is None):
                cuda_version = None
            else:
                cuda_version = cuda_driver_version or cuda_runtime_version

        # 6. Avaliação da recomendação técnica de CUDA
        parsed_cap = None
        if cuda_device_capability:
            try:
                cparts = cuda_device_capability.split(".")
                parsed_cap = (int(cparts[0]), int(cparts[1]))
            except Exception:
                pass

        cuda_recommendation = self._evaluate_cuda_status(
            cuda_driver_ver=cuda_driver_version,
            cuda_runtime_ver=cuda_runtime_version,
            cuda_avail=cuda_available,
            gpu_name=gpu_name,
            compute_cap=parsed_cap,
            has_torch=has_torch,
            is_busy=is_busy,
        )

        # 7. Informações estáticas do processador (em cache, com context manager para evitar vazamento de handles)
        cpu_name, cpu_cores, cpu_threads = self._get_static_cpu_info()

        gpu_tier = "cpu"
        if vram_res > 0:
            total_mb = vram_res * 1024
            if total_mb <= 6800.0:
                gpu_tier = "low"
            elif total_mb <= 11200.0:
                gpu_tier = "mid"
            else:
                gpu_tier = "high"
        elif "torch" in sys.modules and sys.modules["torch"] is not None and not is_busy:
            try:
                from src.utils.vram_arbiter import vram_arbiter
                gpu_tier = vram_arbiter.get_tier().value
            except Exception:
                pass

        return {
            "cpu_name": cpu_name,
            "cpu_cores": cpu_cores,
            "cpu_threads": cpu_threads,
            "cpu_percent": cpu_pct,
            "ram_percent": ram_pct,
            "ram_used_gb": round(ram_used, 1),
            "ram_total_gb": round(ram_total, 1),
            "vram_allocated_gb": round(vram_alloc, 2),
            "vram_reserved_gb": round(vram_res, 2),
            "gpu_name": gpu_name,
            "gpu_temp": gpu_temp,
            "cuda_version": cuda_version,
            "gpu_tier": gpu_tier,
            "cuda_available": cuda_available,
            "cuda_driver_version": cuda_driver_version,
            "cuda_runtime_version": cuda_runtime_version,
            "cuda_device_capability": cuda_device_capability,
            "cuda_recommendation": cuda_recommendation,
        }
