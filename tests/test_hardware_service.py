import os
import sys
from unittest.mock import MagicMock, patch
import pytest

from src.api_services.hardware_service import HardwareService


class TestHardwareService:
    def test_getHardwareStats_structure(self):
        service = HardwareService()
        stats = service.getHardwareStats()

        expected_keys = {
            "cpu_name",
            "cpu_cores",
            "cpu_threads",
            "cpu_percent",
            "ram_percent",
            "ram_used_gb",
            "ram_total_gb",
            "vram_allocated_gb",
            "vram_reserved_gb",
            "gpu_name",
            "gpu_temp",
            "cuda_version",
            "gpu_tier",
            "cuda_available",
            "cuda_driver_version",
            "cuda_runtime_version",
            "cuda_device_capability",
            "cuda_recommendation",
        }
        assert set(stats.keys()) == expected_keys
        assert isinstance(stats["cpu_name"], str)
        assert isinstance(stats["cpu_cores"], int)
        assert isinstance(stats["cpu_threads"], int)
        assert isinstance(stats["cpu_percent"], (int, float))
        assert isinstance(stats["ram_percent"], (int, float))
        assert isinstance(stats["ram_used_gb"], (int, float))
        assert isinstance(stats["ram_total_gb"], (int, float))
        assert isinstance(stats["cuda_available"], bool)
        assert isinstance(stats["cuda_recommendation"], dict)
        assert "status" in stats["cuda_recommendation"]

    def test_static_cpu_info_caching(self):
        service = HardwareService()
        name1, cores1, threads1 = service._get_static_cpu_info()
        assert service._cpu_name is not None

        # Directly alter internal cache to verify subsequent call hits cache
        service._cpu_name = "Mocked CPU"
        name2, cores2, threads2 = service._get_static_cpu_info()
        assert name2 == "Mocked CPU"

    def test_getHardwareStats_with_mocked_torch_cuda(self):
        service = HardwareService()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 4080"
        mock_torch.cuda.get_device_capability.return_value = (8, 9)
        mock_torch.version.cuda = "12.4"
        # 4GB free, 16GB total
        mock_torch.cuda.mem_get_info.return_value = (4 * (1024**3), 16 * (1024**3))

        with patch.dict(sys.modules, {"torch": mock_torch}):
            stats = service.getHardwareStats()
            assert stats["gpu_name"] == "NVIDIA GeForce RTX 4080"
            assert stats["cuda_version"] == "12.4"
            assert stats["cuda_available"] is True
            assert stats["cuda_runtime_version"] == "12.4"
            assert stats["cuda_device_capability"] == "8.9"
            assert stats["cuda_recommendation"]["status"] == "ok"
            assert stats["vram_reserved_gb"] == 16.0
            assert stats["vram_allocated_gb"] == 12.0

    def test_cuda_recommendation_cpu_only_torch(self):
        service = HardwareService()
        service._nvml_failed = True

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.version.cuda = None

        mock_pynvml = MagicMock()
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        mock_pynvml.nvmlSystemGetCudaDriverVersion.return_value = 12040
        h = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = h
        mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA GeForce RTX 3060"
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 45
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = MagicMock(total=12 * 1024**3, used=2 * 1024**3)

        with patch.dict(sys.modules, {"torch": mock_torch, "pynvml": mock_pynvml}):
            service._nvml_failed = False
            service._nvml_initialized = False
            stats = service.getHardwareStats()
            assert stats["cuda_available"] is False
            assert stats["cuda_version"] is None
            assert stats["cuda_recommendation"]["status"] == "cpu_only"
            assert "Central de Módulos" in stats["cuda_recommendation"]["action"]

    def test_cuda_recommendation_outdated_driver(self):
        service = HardwareService()
        rec = service._evaluate_cuda_status(
            cuda_driver_ver="10.2",
            cuda_runtime_ver=None,
            cuda_avail=False,
            gpu_name="NVIDIA GeForce GTX 960",
            compute_cap=(5, 2),
            has_torch=False
        )
        assert rec["status"] == "driver_outdated"
        assert "CUDA >= 11.8" in rec["message"]

    def test_nvml_failure_flags_and_recovers_gracefully(self):
        service = HardwareService()

        mock_pynvml = MagicMock()
        mock_pynvml.nvmlInit.side_effect = RuntimeError("NVML driver error")

        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            stats = service.getHardwareStats()
            assert service._nvml_failed is True
            # Further call should not call nvmlInit again
            mock_pynvml.nvmlInit.reset_mock()
            stats2 = service.getHardwareStats()
            mock_pynvml.nvmlInit.assert_not_called()

    def test_multi_gpu_selects_discrete_with_highest_vram(self):
        service = HardwareService()
        service._nvml_failed = True

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.device_count.return_value = 2
        mock_torch.version.cuda = "12.8"

        def _dev_name(idx):
            return "Intel(R) UHD Graphics 770" if idx == 0 else "NVIDIA GeForce RTX 4070 Laptop GPU"

        def _mem_info(idx):
            # GPU 0 (integrated) pretends 8GB shared, GPU 1 (discrete) has 12GB dedicated
            if idx == 0:
                return (7 * (1024**3), 8 * (1024**3))
            return (9 * (1024**3), 12 * (1024**3))

        mock_torch.cuda.get_device_name.side_effect = _dev_name
        mock_torch.cuda.mem_get_info.side_effect = _mem_info

        with patch.dict(sys.modules, {"torch": mock_torch}):
            stats = service.getHardwareStats()
            assert stats["gpu_name"] == "NVIDIA GeForce RTX 4070 Laptop GPU"
            assert stats["vram_reserved_gb"] == 12.0
            assert stats["vram_allocated_gb"] == 3.0

    def test_core_engine_installer_cpu_fallback_when_no_nvidia_gpu(self, tmp_path, monkeypatch):
        from src.model_engines.core_engine_installer import CoreEngineInstaller

        monkeypatch.setenv("VISIONARY_FORCE_CPU_TORCH", "1")
        req_file = tmp_path / "requirements-ai.txt"
        req_file.write_text(
            "--extra-index-url https://download.pytorch.org/whl/cu128\n"
            "torch==2.11.0+cu128\n"
            "torchvision==0.26.0+cu128\n"
            "transformers==4.40.0\n",
            encoding="utf-8",
        )

        installer = CoreEngineInstaller()
        assert installer._has_nvidia_gpu() is False

        cmd, tmp_req = installer._build_pip_install_args("python.exe", str(req_file))
        try:
            assert tmp_req is not None
            assert os.path.exists(tmp_req)
            with open(tmp_req, "r", encoding="utf-8") as f:
                adapted = f.read()
            assert "https://download.pytorch.org/whl/cpu" in adapted
            assert "torch==2.11.0\n" in adapted
            assert "+cu128" not in adapted
        finally:
            if tmp_req and os.path.exists(tmp_req):
                os.remove(tmp_req)

    def test_image_service_full_cache_and_adjacent_prefetch(self, tmp_path, monkeypatch):
        from PIL import Image
        import src.api_services.image_service as img_svc_mod
        from src.api_services.image_service import ImageService
        from src.utils.path_sandbox import register_root

        register_root(str(tmp_path))
        p1 = tmp_path / "page_1.png"
        p2 = tmp_path / "page_2.png"
        p10 = tmp_path / "page_10.png"
        Image.new("RGB", (32, 32), color="red").save(p1)
        Image.new("RGB", (32, 32), color="blue").save(p2)
        Image.new("RGB", (32, 32), color="green").save(p10)

        svc = ImageService(max_full_cache_entries=3)
        try:
            # Verify natural sort picks page_2.png after page_1.png, NOT page_10.png
            assert svc._find_next_sibling_image(str(p1)) == str(p2)

            res1 = svc.get_image_base64_full(str(p1))
            assert res1["success"] is True
            assert svc._prefetcher is not None

            # Wait for background full-cache prefetch of p2 to finish
            if svc._full_prefetch_thread is not None:
                svc._full_prefetch_thread.join(timeout=2.0)

            # Poison resilient_read_bytes so any synchronous disk read of p2 would fail
            orig_read_bytes = img_svc_mod.resilient_read_bytes
            def _forbid_p2_disk_read(path, *a, **kw):
                if os.path.normpath(path) == os.path.normpath(str(p2)):
                    raise RuntimeError("p2 should have been served from prefetched RAM cache!")
                return orig_read_bytes(path, *a, **kw)

            monkeypatch.setattr(img_svc_mod, "resilient_read_bytes", _forbid_p2_disk_read)

            res2 = svc.get_image_base64_full(str(p2))
            assert res2["success"] is True
            assert res2["data_url"].startswith("data:image/png;base64,")

            # Loading p2 triggered SafeImagePrefetcher on p10; verify get_image_base64(p10) consumes RAM PIL image without Image.open
            if svc._prefetcher._worker_thread is not None:
                svc._prefetcher._worker_thread.join(timeout=2.0)
            monkeypatch.setattr(Image, "open", lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("Should not touch disk")))
            res10_thumb = svc.get_image_base64(str(p10))
            assert res10_thumb["success"] is True
            assert res10_thumb["data_url"].startswith("data:image/jpeg;base64,")
        finally:
            svc.clear_cache()
            assert len(svc._full_cache) == 0
            assert svc._prefetcher is None

    def test_intel_arc_classified_as_discrete_gpu(self):
        assert HardwareService._is_integrated_gpu_name("Intel(R) Arc(TM) A770 Graphics") is False
        assert HardwareService._is_integrated_gpu_name("Intel Arc B580") is False
        assert HardwareService._is_integrated_gpu_name("Intel(R) UHD Graphics 770") is True
        assert HardwareService._is_integrated_gpu_name("Intel(R) Iris(R) Xe Graphics") is True

    def test_dev_service_publishes_logs_and_progress_to_event_bus_and_selects_best_gpu(self):
        from src.api_services.dev_service import DevService
        from src.utils.event_bus import event_bus

        received = []
        cb_log = lambda payload: received.append(("dev:log", payload))
        cb_prog = lambda payload: received.append(("dev:test_progress", payload))
        event_bus.subscribe("dev:log", cb_log)
        event_bus.subscribe("dev:test_progress", cb_prog)
        try:
            svc = DevService()
            svc._append_app_log("app log line 1")
            svc._append_test_log("test log line 1")
            svc._finish_test_run(return_code=0)

            log_events = [p for ev, p in received if ev == "dev:log"]
            prog_events = [p for ev, p in received if ev == "dev:test_progress"]
            assert any(p.get("stream") == "app" and p.get("line") == "app log line 1" for p in log_events)
            assert any(p.get("stream") == "test" and p.get("line") == "test log line 1" for p in log_events)
            assert any(p.get("running") is False and p.get("percent") == 100 for p in prog_events)

            mock_torch = MagicMock()
            mock_torch.__version__ = "2.11.0"
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.device_count.return_value = 2
            mock_torch.cuda.get_device_name.side_effect = lambda idx: (
                "AMD Radeon(TM) Graphics" if idx == 0 else "NVIDIA GeForce RTX 4080"
            )
            mock_torch.cuda.mem_get_info.side_effect = lambda idx: (
                (1 * 1024**3, 2 * 1024**3) if idx == 0 else (12 * 1024**3, 16 * 1024**3)
            )
            props0 = MagicMock(total_memory=2 * 1024**3)
            props1 = MagicMock(total_memory=16 * 1024**3)
            mock_torch.cuda.get_device_properties.side_effect = lambda idx: props0 if idx == 0 else props1
            mock_torch.cuda.memory_allocated.side_effect = lambda idx: 0 if idx == 0 else 512 * 1024**2
            mock_torch.cuda.memory_reserved.side_effect = lambda idx: 0 if idx == 0 else 1024 * 1024**2

            with patch.dict("sys.modules", {"torch": mock_torch}):
                stats = svc.getDevStats()
                assert stats["device_name"] == "NVIDIA GeForce RTX 4080"
                assert stats["vram_total_gb"] == 16.0
                assert stats["vram_allocated_pytorch"] == 512.0
        finally:
            event_bus.unsubscribe("dev:log", cb_log)
            event_bus.unsubscribe("dev:test_progress", cb_prog)

    def test_export_script_preserves_dash_prefixed_multiline_dialogue(self, tmp_path):
        from src.api_services.library_script_manager import LibraryScriptManager

        script_file = tmp_path / "dash_chapter.txt"
        script_file.write_text(
            "==================================================\n"
            "PAGINA 1: 01.PNG\n"
            "==================================================\n\n"
            "# [id: 1]\n"
            "[EN]: - Hello there!\n"
            "- General Kenobi!\n"
            "[BR]: - Olá!\n"
            "- General Kenobi!\n\n",
            encoding="utf-8",
        )
        mgr = LibraryScriptManager()
        res = mgr.export_script(str(script_file), export_format="clean_txt")
        assert res["success"] is True
        assert "- Olá!\n- General Kenobi!" in res["content"]

    def test_core_engine_installer_heterogeneous_cuda_detection(self, tmp_path, monkeypatch):
        from src.model_engines.core_engine_installer import CoreEngineInstaller

        installer = CoreEngineInstaller()

        # 1. Override explícito via VISIONARY_CUDA_VERSION
        monkeypatch.setenv("VISIONARY_CUDA_VERSION", "cu124")
        assert installer._detect_cuda_target() == "cu124"

        # 2. Respeito ao VISIONARY_FORCE_CPU_TORCH mesmo com CUDA_VERSION
        monkeypatch.setenv("VISIONARY_FORCE_CPU_TORCH", "1")
        assert installer._detect_cuda_target() == "cpu"
        monkeypatch.delenv("VISIONARY_FORCE_CPU_TORCH", raising=False)
        monkeypatch.delenv("VISIONARY_CUDA_VERSION", raising=False)

        # 3. Simulação de NVML reportando CUDA 12.4 (12040)
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        mock_pynvml.nvmlSystemGetCudaDriverVersion.return_value = 12040

        with patch.dict("sys.modules", {"pynvml": mock_pynvml}):
            assert installer._detect_cuda_target() == "cu124"

            # Gera manifesto adaptado para cu124
            req_file = tmp_path / "req_cu124.txt"
            req_file.write_text(
                "--extra-index-url https://download.pytorch.org/whl/cu128\n"
                "torch==2.11.0+cu128\n"
                "torchvision==0.26.0+cu128\n",
                encoding="utf-8",
            )
            cmd, tmp_req = installer._build_pip_install_args("python.exe", str(req_file))
            try:
                assert tmp_req is not None
                with open(tmp_req, "r", encoding="utf-8") as f:
                    content = f.read()
                assert "https://download.pytorch.org/whl/cu124" in content
                assert "torch==2.11.0+cu124" in content
                assert "torchvision==0.26.0+cu124" in content
            finally:
                if tmp_req and os.path.exists(tmp_req):
                    os.remove(tmp_req)

        # 4. Simulação de NVML reportando CUDA 12.1 (12010)
        mock_pynvml.nvmlSystemGetCudaDriverVersion.return_value = 12010
        with patch.dict("sys.modules", {"pynvml": mock_pynvml}):
            assert installer._detect_cuda_target() == "cu121"

        # 5. Simulação de NVML reportando CUDA 11.8 (11080)
        mock_pynvml.nvmlSystemGetCudaDriverVersion.return_value = 11080
        with patch.dict("sys.modules", {"pynvml": mock_pynvml}):
            assert installer._detect_cuda_target() == "cu118"

    def test_model_service_cuda_status_decoupling(self):
        from src.api_services.model_service import ModelService

        mock_installer = MagicMock()
        mock_installer.check_ai_dependencies.return_value = {
            "ai_state": "installed",
            "has_torch": True,
            "has_cuda_torch": False,
            "torch_cuda_version": None,
        }
        mock_installer._has_nvidia_gpu.return_value = True
        mock_installer.get_cuda_recommendation.return_value = {
            "has_gpu": True,
            "target": "cu124",
            "message": "Recomenda-se reinstalar para ativar a GPU.",
        }

        mock_ollama = MagicMock()
        mock_ollama.check_ollama_state.return_value = ("installed_and_running", ["qwen2.5:7b"])
        mock_ollama.get_install_progress.return_value = {}

        svc = ModelService(core_installer=mock_installer, ollama_manager=mock_ollama)
        status = svc.checkModulesStatus()

        assert status["ocr"]["state"] == "installed"
        assert status["cuda"]["state"] == "cpu_only"
        assert status["cuda"]["torch_cuda"] is False
        assert status["cuda"]["has_nvidia_gpu"] is True

    def test_hardware_stats_purges_stale_namespace_torch_after_uninstall(self):
        import types
        import importlib.machinery

        service = HardwareService()
        stale_torch = types.ModuleType("torch")
        stale_torch.__file__ = None
        stale_torch.__spec__ = importlib.machinery.ModuleSpec(name="torch", loader=None, origin=None)

        mock_pynvml = MagicMock()
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        mock_pynvml.nvmlSystemGetCudaDriverVersion.return_value = 12080
        h = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = h
        mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA GeForce RTX 2060 SUPER"
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 50
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = MagicMock(total=8 * 1024**3, used=2 * 1024**3)

        with patch.dict("sys.modules", {"torch": stale_torch, "pynvml": mock_pynvml}):
            with patch("importlib.util.find_spec", return_value=stale_torch.__spec__):
                stats = service.getHardwareStats()
                assert stats["cuda_recommendation"]["status"] == "ready_for_install"
                assert "modo CPU" not in stats["cuda_recommendation"]["message"]

    def test_hardware_stats_respects_is_busy_during_install(self):
        mock_api = MagicMock()
        mock_api._install_progress = {"status": "installing", "percent": 45.0}
        service = HardwareService(api_bridge=mock_api)

        mock_pynvml = MagicMock()
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        mock_pynvml.nvmlSystemGetCudaDriverVersion.return_value = 12080
        h = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = h
        mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA GeForce RTX 2060 SUPER"
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 50
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = MagicMock(total=8 * 1024**3, used=2 * 1024**3)

        with patch.dict("sys.modules", {"pynvml": mock_pynvml}):
            stats = service.getHardwareStats()
            assert stats["cuda_recommendation"]["status"] == "ready_for_install"

    def test_hardware_stats_and_core_installer_detect_cuda_on_disk_without_importing_torch(self, tmp_path):
        import importlib.machinery
        from src.model_engines.core_engine_installer import CoreEngineInstaller

        fake_torch_dir = tmp_path / "torch"
        fake_torch_dir.mkdir(parents=True, exist_ok=True)
        init_file = fake_torch_dir / "__init__.py"
        init_file.write_text("# fake torch init\n", encoding="utf-8")
        version_file = fake_torch_dir / "version.py"
        version_file.write_text("__version__ = '2.11.0+cu128'\ncuda = '12.8'\n", encoding="utf-8")

        fake_spec = importlib.machinery.ModuleSpec(name="torch", loader=None, origin=str(init_file))
        fake_spec.has_location = True

        mock_pynvml = MagicMock()
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        mock_pynvml.nvmlSystemGetCudaDriverVersion.return_value = 12080
        h = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = h
        mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA GeForce RTX 2060 SUPER"
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 52
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = MagicMock(total=8 * 1024**3, used=2 * 1024**3)

        def _fake_find_spec(name, *args, **kwargs):
            if name in ("torch", "transformers", "ultralytics", "einops", "timm"):
                return fake_spec
            return None

        saved_torch_mods = {
            k: sys.modules.pop(k)
            for k in list(sys.modules.keys())
            if k == "torch" or k.startswith("torch.")
        }
        try:
            with patch.dict("sys.modules", {"pynvml": mock_pynvml}), \
                 patch("importlib.util.find_spec", side_effect=_fake_find_spec):
                service = HardwareService()
                stats = service.getHardwareStats()
                assert "torch" not in sys.modules
                assert stats["cuda_available"] is True
                assert stats["cuda_runtime_version"] == "12.8"
                assert stats["cuda_recommendation"]["status"] == "ok"

                installer = CoreEngineInstaller()
                deps = installer.check_ai_dependencies()
                assert "torch" not in sys.modules
                assert deps["ai_state"] == "installed"
                assert deps["has_cuda_torch"] is True
                assert deps["torch_cuda_version"] == "12.8"
        finally:
            sys.modules.update(saved_torch_mods)

    def test_core_engine_installer_cached_wheel_and_unpacking_smooth_progression(self, tmp_path):
        import io
        import time
        from src.model_engines.core_engine_installer import CoreEngineInstaller

        installer = CoreEngineInstaller()
        fake_deps = {
            "ai_state": "not_installed",
            "has_torch": False,
            "has_transformers": False,
            "has_ultralytics": False,
        }

        pip_stdout = io.StringIO(
            "Collecting torch==2.11.0+cu128\n"
            "  Using cached torch-2.11.0%2Bcu128-cp311-cp311-win_amd64.whl\n"
            "Collecting torchvision==0.26.0+cu128\n"
            "  Using cached torchvision-0.26.0%2Bcu128-cp311-cp311-win_amd64.whl (24.0 MB)\n"
            "Installing collected packages: torch, torchvision\n"
            "Successfully installed torch-2.11.0+cu128 torchvision-0.26.0+cu128\n"
        )

        mock_proc = MagicMock()
        mock_proc.stdout = pip_stdout
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        observed_percents = []
        orig_notify = installer.notify_progress

        def _spy_notify(*args, **kwargs):
            p = installer.get_install_progress()
            observed_percents.append(p.get("percent", 0.0))
            return orig_notify(*args, **kwargs)

        with patch.object(installer, "check_ai_dependencies", return_value=fake_deps), \
             patch.object(installer, "_detect_cuda_target", return_value="cu128"), \
             patch.object(installer, "notify_progress", side_effect=_spy_notify), \
             patch("sys.executable", str(tmp_path / "python.exe")), \
             patch("subprocess.Popen", return_value=mock_proc):
            res = installer.install_core_engine()
            assert res["success"] is True
            for _ in range(40):
                st = installer.get_install_progress()
                if st["status"] in ("completed", "error"):
                    break
                time.sleep(0.03)

        final_prog = installer.get_install_progress()
        assert final_prog["status"] == "completed"
        assert final_prog["percent"] == 100.0
        assert final_prog["downloaded_bytes"] >= 2550 * 1024 * 1024
        # Garante progressão estritamente monotônica (sem regressões)
        for i in range(1, len(observed_percents)):
            assert observed_percents[i] >= observed_percents[i - 1]

    def test_core_engine_installer_unbuffered_pipe_and_live_disk_extraction_75_to_99(self, tmp_path):
        import io
        import time
        import threading
        from src.model_engines.core_engine_installer import CoreEngineInstaller

        installer = CoreEngineInstaller()
        cmd, _ = installer._build_pip_install_args("python.exe", str(tmp_path / "req.txt"))
        assert "-u" in cmd

        fake_py_dir = tmp_path / "engine"
        fake_sp = fake_py_dir / "Lib" / "site-packages"
        fake_sp.mkdir(parents=True, exist_ok=True)
        fake_py = fake_py_dir / "python.exe"
        fake_py.write_bytes(b"MZ")

        fake_deps = {
            "ai_state": "not_installed",
            "has_torch": False,
            "has_transformers": False,
            "has_ultralytics": False,
        }

        # Real OS pipe (< 128 bytes written before silence!) reproducing exact Windows pipe behavior
        r_fd, w_fd = os.pipe()
        pipe_reader = io.TextIOWrapper(os.fdopen(r_fd, "rb", buffering=4096), encoding="utf-8", line_buffering=True)

        mock_proc = MagicMock()
        mock_proc.stdout = pipe_reader
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        mid_extraction_snapshots = []

        def _simulate_pip_child():
            # 1. Emit short 'Installing collected packages' (< 60 bytes, without closing pipe!)
            os.write(w_fd, b"Installing collected packages: numpy\n")
            # 2. Simulate disk extraction in site-packages/numpy (~60 MB of weights/binaries + .py/.pyc)
            np_dir = fake_sp / "numpy"
            np_dir.mkdir(parents=True, exist_ok=True)
            (np_dir / "core.dll").write_bytes(b"\x00" * (60 * 1024 * 1024))
            for idx in range(60):
                (np_dir / f"mod_{idx}.py").write_text("x = 1\n", encoding="utf-8")
            time.sleep(0.95)
            mid_extraction_snapshots.append(installer.get_install_progress())
            # 3. Simulate .pyc compilation phase
            pycache = np_dir / "__pycache__"
            pycache.mkdir(exist_ok=True)
            for idx in range(55):
                (pycache / f"mod_{idx}.cpython-311.pyc").write_bytes(b"\x00" * 128)
            time.sleep(0.95)
            mid_extraction_snapshots.append(installer.get_install_progress())
            # 4. Finish installation and close stdout pipe
            os.write(w_fd, b"Successfully installed numpy-2.4.6\n")
            os.close(w_fd)

        popen_kwargs_captured = {}

        def _fake_popen(*args, **kwargs):
            popen_kwargs_captured.update(kwargs)
            threading.Thread(target=_simulate_pip_child, daemon=True).start()
            return mock_proc

        with patch.object(installer, "check_ai_dependencies", return_value=fake_deps), \
             patch.object(installer, "_detect_cuda_target", return_value="cpu"), \
             patch("sys.executable", str(fake_py)), \
             patch("subprocess.Popen", side_effect=_fake_popen):
            res = installer.install_core_engine()
            assert res["success"] is True
            for _ in range(80):
                st = installer.get_install_progress()
                if st["status"] in ("completed", "error"):
                    break
                time.sleep(0.05)
            pipe_reader.close()

        assert popen_kwargs_captured.get("env", {}).get("PYTHONUNBUFFERED") == "1"
        assert len(mid_extraction_snapshots) == 2
        # Must have advanced well past 75% BEFORE 'Successfully installed' was emitted!
        assert mid_extraction_snapshots[0]["percent"] > 80.0
        assert "Descompactando" in mid_extraction_snapshots[0]["message"] or "Compilando" in mid_extraction_snapshots[0]["message"]
        assert mid_extraction_snapshots[1]["percent"] > mid_extraction_snapshots[0]["percent"]
        assert installer.get_install_progress()["status"] == "completed"
        assert installer.get_install_progress()["percent"] == 100.0

    def test_hardware_stats_cuda_handshake_debouncing_prevents_transient_flash(self):
        service = HardwareService()
        service._nvml_failed = False
        service._nvml_initialized = True

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.version.cuda = "12.8"
        mock_torch.__file__ = r"C:\fake\site-packages\torch\__init__.py"

        mock_pynvml = MagicMock()
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        mock_pynvml.nvmlSystemGetCudaDriverVersion.return_value = 12080
        h = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = h
        mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA GeForce RTX 2060 SUPER"
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 50
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = MagicMock(total=8 * 1024**3, used=2 * 1024**3)

        with patch.dict("sys.modules", {"torch": mock_torch, "pynvml": mock_pynvml}), \
             patch("os.path.isfile", return_value=True):
            # Tick 1: cold start / DLL handshake delay (< 3 ticks)
            stats1 = service.getHardwareStats()
            assert stats1["cuda_available"] is True
            assert stats1["cuda_runtime_version"] == "12.8"
            assert stats1["cuda_recommendation"]["status"] == "ok"
            assert service._consecutive_cuda_failures == 1

            # Tick 2: still initializing (< 3 ticks)
            stats2 = service.getHardwareStats()
            assert stats2["cuda_available"] is True
            assert stats2["cuda_recommendation"]["status"] == "ok"
            assert service._consecutive_cuda_failures == 2

            # Tick 3: persistent failure (>= 3 ticks) triggers legitimate driver_mismatch
            stats3 = service.getHardwareStats()
            assert stats3["cuda_available"] is False
            assert stats3["cuda_recommendation"]["status"] == "driver_mismatch"
            assert "PyTorch possui binários CUDA 12.8, mas o subsistema CUDA não respondeu" in stats3["cuda_recommendation"]["message"]
            assert service._consecutive_cuda_failures == 3

            # Tick 4: CUDA handshake completes and succeeds -> instant recovery
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 2060 SUPER"
            mock_torch.cuda.get_device_capability.return_value = (7, 5)
            mock_torch.cuda.mem_get_info.return_value = (6 * 1024**3, 8 * 1024**3)
            stats4 = service.getHardwareStats()
            assert stats4["cuda_available"] is True
            assert stats4["cuda_recommendation"]["status"] == "ok"
            assert service._consecutive_cuda_failures == 0
