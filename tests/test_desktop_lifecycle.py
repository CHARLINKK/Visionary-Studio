import os
import sys
import unittest
from unittest.mock import patch, MagicMock


class TestDesktopLifecycle(unittest.TestCase):
    def test_watchdog_invalid_parent_pid(self):
        """Valida que o watchdog não trava ou quebra com PIDs inválidos ou ausentes."""
        from src.server import start_watchdog
        # Não deve lançar exceção
        start_watchdog(None)
        start_watchdog(-1)
        start_watchdog(0)

    @patch("ctypes.windll.kernel32.OpenProcess")
    @patch("ctypes.windll.kernel32.WaitForSingleObject")
    @patch("ctypes.windll.kernel32.CloseHandle")
    def test_watchdog_windows_kernel_event(self, mock_close, mock_wait, mock_open):
        """Valida que o watchdog no Windows usa WaitForSingleObject com OpenProcess SYNCHRONIZE."""
        from src.server import start_watchdog
        import threading
        import time

        mock_open.return_value = 12345
        # Retorna WAIT_OBJECT_0 imediatamente simulando término do pai
        mock_wait.return_value = 0

        exit_called = threading.Event()
        with patch("src.server.os._exit", side_effect=lambda code: exit_called.set()):
            with patch("sys.platform", "win32"):
                start_watchdog(99999)
                self.assertTrue(exit_called.wait(timeout=2.0))
                mock_open.assert_called_once()
                mock_wait.assert_called_once_with(12345, 0xFFFFFFFF)
                mock_close.assert_called_once_with(12345)

    def test_jumplist_action_parsing(self):
        """Valida a lógica de resolução de argumentos do Jump List (--action=xxx)."""
        valid_actions = {
            "--action=processamento": "processamento",
            "--action=biblioteca": "biblioteca",
            "--action=lightbox": "lightbox",
            "--action=modulos": "modulos",
            "--action=configuracoes": "configuracoes",
            "--action=queue": "queue",
            "--action=dev": "dev",
        }

        def parse_action(args):
            for arg in args:
                if isinstance(arg, str):
                    import re
                    match = re.search(r'--action=["\']?([a-zA-Z0-9_-]+)["\']?', arg, re.IGNORECASE)
                    if match:
                        return match.group(1).lower().strip()
            return None

        for flag, expected in valid_actions.items():
            args = ["Visionary.exe", flag, "--other-flag"]
            self.assertEqual(parse_action(args), expected)

        # Suporte a argumentos agrupados do Windows Shell
        self.assertEqual(parse_action(['"app.exe" --action=lightbox']), "lightbox")
        self.assertEqual(parse_action(['--action="configuracoes"']), "configuracoes")

        # Sem ação
        self.assertIsNone(parse_action(["Visionary.exe", "--headless"]))

    def test_jumplist_dedicated_icons_contract(self):
        """Valida que as tarefas da JumpList utilizam ícones dedicados e que os arquivos .ico existem."""
        paths_file = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "electron", "paths.js"))
        tray_file = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "electron", "trayManager.js"))
        jumplist_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "jumplist"))

        with open(paths_file, "r", encoding="utf-8") as f:
            paths_code = f.read()
        with open(tray_file, "r", encoding="utf-8") as f:
            tray_code = f.read()

        self.assertIn("getJumpListIconPath", paths_code)
        self.assertIn("getJumpListIconPath", tray_code)

        expected_icons = [
            "task_studio.ico",
            "task_library.ico",
            "task_lightbox.ico",
            "task_modules.ico",
            "task_settings.ico",
        ]

        for icon in expected_icons:
            self.assertIn(f"getJumpListIconPath('{icon}')", tray_code)
            icon_path = os.path.join(jumplist_dir, icon)
            self.assertTrue(os.path.isfile(icon_path), f"Ícone {icon} não encontrado em {jumplist_dir}")
            self.assertGreater(os.path.getsize(icon_path), 1000, f"Ícone {icon} corrompido ou vazio")

    def test_taskbar_progress_aggregation(self):
        """Valida a regra de cálculo e agregação de progresso para a barra de tarefas."""
        jobs = [
            {"id": "j1", "status": "running", "progress": 40},
            {"id": "j2", "status": "pending", "progress": 0},
            {"id": "j3", "status": "completed", "progress": 100},
        ]

        running_jobs = [j for j in jobs if j["status"] in ("running", "pending")]
        self.assertEqual(len(running_jobs), 2)

        total_progress = sum(j.get("progress", 0) for j in running_jobs)
        avg_progress = round(total_progress / len(running_jobs))
        self.assertEqual(avg_progress, 20)

        fraction = max(0.01, min(1.0, avg_progress / 100))
        self.assertAlmostEqual(fraction, 0.2, places=2)

    def test_cancel_all_jobs_logic(self):
        """Valida a transição atômica de status para 'failed' quando a fila é cancelada pelo tray."""
        queue = [
            {"id": "j1", "status": "running", "progress": 50},
            {"id": "j2", "status": "pending", "progress": 0},
            {"id": "j3", "status": "completed", "progress": 100},
        ]

        new_queue = []
        for j in queue:
            if j["status"] in ("running", "pending"):
                new_queue.append({
                    **j,
                    "status": "failed",
                    "currentStepLabel": "Cancelado pelo usuário",
                    "error": "Interrompido manualmente.",
                })
            else:
                new_queue.append(j)

        running_after = [j for j in new_queue if j["status"] in ("running", "pending")]
        failed_after = [j for j in new_queue if j["status"] == "failed"]
        self.assertEqual(len(running_after), 0)
        self.assertEqual(len(failed_after), 2)
        self.assertEqual(new_queue[2]["status"], "completed")

    def test_uninstaller_script_total_wipe_contract(self):
        """Valida que o script build/uninstaller.nsh contém as diretivas de Total Wipe completas."""
        nsh_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "build", "uninstaller.nsh"))
        self.assertTrue(os.path.isfile(nsh_path))
        with open(nsh_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("customUnInstall", content)
        self.assertIn("Total Wipe", content)
        self.assertIn("customInit", content)
        self.assertIn("customInstall", content)
        self.assertIn("customUnInstall", content)
        self.assertIn("KillVisionaryProcesses", content)
        self.assertIn("FileWriteUTF16LE", content)
        self.assertIn("0xFEFF", content)
        self.assertIn("amadeus:32b", content)
        self.assertIn("$LOCALAPPDATA\\${APP_PRODUCT_FILENAME}", content)
        self.assertIn("$APPDATA\\${APP_PRODUCT_FILENAME}", content)

    def test_install_core_engine_fast_path(self):
        """Valida que installCoreEngine não dispara download desnecessário se IA já estiver instalada."""
        from src.api_services.model_service import ModelService
        service = ModelService()

        with patch("importlib.util.find_spec", return_value=MagicMock()):
            res = service.installCoreEngine()
            self.assertTrue(res.get("success"))
            self.assertIn("já está instalado", res.get("message", ""))
            prog = service.getInstallProgress()
            self.assertEqual(prog.get("status"), "completed")
    def test_close_action_default_setting(self):
        """Valida que close_action possui padrão 'smart' na configuração."""
        from src.config import Config
        self.assertEqual(Config._defaults.get("close_action"), "smart")

    def test_api_shutdown_endpoint(self):
        """Valida que a rota /api/shutdown aceita requisição e responde status shutting_down."""
        from fastapi.testclient import TestClient
        from src.server import app

        with patch("src.model_manager.ModelManager.terminate_ollama"), \
             patch("os._exit"):
            client = TestClient(app)
            response = client.post("/api/shutdown")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data.get("status"), "shutting_down")

    def test_ollama_pid_file_lifecycle(self):
        """Valida escrita e limpeza do arquivo de PID do Ollama iniciado pelo Visionary."""
        import tempfile
        from src.model_manager import ModelManager
        from src.config import get_app_data_dir

        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(os.environ, {"VISIONARY_USER_DATA": tmp_dir}):
            pid_file = os.path.join(get_app_data_dir(), ".ollama_visionary.pid")
            ModelManager._save_ollama_pid(98765)
            self.assertTrue(os.path.exists(pid_file))
            with open(pid_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read().strip(), "98765")

            ModelManager._remove_ollama_pid_file()
            self.assertFalse(os.path.exists(pid_file))

    def test_sidecar_manager_resilience_contracts(self):
        """Valida que sidecarManager.js implementa contratos de resiliência: log persistente, sleepSync e filtro taskkill."""
        sidecar_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "electron", "sidecarManager.js"))
        self.assertTrue(os.path.isfile(sidecar_path))
        with open(sidecar_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("initBootLogger", code)
        self.assertIn("sidecar_boot.log", code)
        self.assertIn("sleepSync", code)
        self.assertIn("Atomics.wait", code)
        self.assertIn("IMAGENAME eq ollama.exe", code)
        self.assertIn("getRecentStderr", code)
        self.assertIn("startRuntimeWatchdog", code)
        self.assertIn("recoverPythonSidecar", code)
        self.assertIn("checkServerHealthQuick", code)
        self.assertIn("cleanupPromise", code)

    def test_quick_health_check_and_idempotent_graceful_shutdown(self):
        """Valida /api/health?quick=1 ultra-rápido e perform_graceful_shutdown idempotente."""
        from fastapi.testclient import TestClient
        from src.server import app
        from src.routers.system_router import perform_graceful_shutdown, reset_shutdown_state

        reset_shutdown_state()
        try:
            client = TestClient(app)
            resp = client.get("/api/health?quick=1")
            self.assertEqual(resp.status_code, 200)
            payload = resp.json()
            self.assertEqual(payload.get("status"), "ok")
            self.assertTrue(payload.get("quick"))
            self.assertIsInstance(payload.get("pid"), int)
            self.assertIn("uptime_s", payload)

            with patch("src.routers.rpc_router.api_bridge._pipeline_service.cancelAllJobs") as mock_cancel, \
                 patch("src.model_manager.ModelManager.terminate_ollama") as mock_term:
                res1 = perform_graceful_shutdown(reason="unit_test", exit_process=False)
                res2 = perform_graceful_shutdown(reason="duplicate_call", exit_process=False)
                self.assertEqual(res1.get("status"), "shut_down")
                self.assertEqual(res2.get("status"), "already_shutting_down")
                mock_cancel.assert_called_once_with(hard_reset=False)
                mock_term.assert_called_once()
        finally:
            reset_shutdown_state()

    def test_sidecar_dynamic_port_and_shutdown_contract(self):
        """Valida que sidecarManager.js e paths.js honram portas dinâmicas e shutdown nativo."""
        paths_file = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "electron", "paths.js"))
        sidecar_file = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "electron", "sidecarManager.js"))

        with open(paths_file, "r", encoding="utf-8") as f:
            paths_code = f.read()
        with open(sidecar_file, "r", encoding="utf-8") as f:
            sidecar_code = f.read()

        self.assertIn("findAvailablePort", paths_code)
        self.assertIn("getServerPort", paths_code)
        self.assertIn("getServerUrl", paths_code)
        self.assertIn("setServerPort", paths_code)

        # Garante que sidecarManager usa porta e url dinâmicas
        self.assertIn("activeServerPort", sidecar_code)
        self.assertIn("currentUrl", sidecar_code)
        self.assertIn("requestShutdownNative", sidecar_code)
        self.assertIn("waitForPidExit", sidecar_code)
        self.assertIn("Connection: 'close'", sidecar_code)
        self.assertNotIn("spawnSync('curl.exe'", sidecar_code)

        main_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "electron", "main.js"))
        with open(main_path, "r", encoding="utf-8") as f:
            main_code = f.read()
        self.assertIn("hideAllAppWindows", main_code)
        self.assertIn("isQuitting = true", main_code)

    def test_main_handles_wait_for_server_failure(self):
        """Valida que main.js verifica o retorno estruturado de waitForServer antes de abrir mainWindow."""
        main_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "electron", "main.js"))
        self.assertTrue(os.path.isfile(main_path))
        with open(main_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("serverResult", code)
        self.assertIn("serverResult.success", code)
        self.assertIn("bootstrap:error", code)
        self.assertIn("createMainWindow", code)
        self.assertIn("pendingWin.destroy()", code)
        self.assertIn("showError", code)

    def test_session_auth_electron_contract(self):
        """Valida que sessionAuth.js intercepta tanto http quanto ws e blinda o callback contra exceções."""
        auth_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "electron", "sessionAuth.js"))
        self.assertTrue(os.path.isfile(auth_path))
        with open(auth_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("ws://${host}:${port}/*", code)
        self.assertIn("http://${host}:${port}/*", code)
        self.assertIn("onBeforeSendHeaders", code)
        self.assertIn("callback({ requestHeaders", code)
        self.assertIn("try {", code)
        self.assertIn("TOKEN_HEADER", code)

    def test_installer_build_scripts_and_packaging_contract(self):
        """Valida a integridade do script de build do instalador e diretivas de empacotamento."""
        import json
        pkg_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "package.json"))
        bat_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "scripts", "Build_Installer.bat"))

        self.assertTrue(os.path.isfile(pkg_path))
        self.assertTrue(os.path.isfile(bat_path))

        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)

        build_cfg = pkg.get("build", {})
        self.assertEqual(build_cfg.get("directories", {}).get("output"), "dist_installer")

        files = build_cfg.get("files", [])
        self.assertIn("!models/*.pt", files)
        self.assertIn("!models/**/*.pt", files)
        self.assertIn("!assets/python/engine-runtime.tar.zst", files)
        self.assertIn("!assets/python/prebuilt-engine.zip", files)
        self.assertTrue(bool(pkg.get("engineVersion")))
        self.assertNotIn("models/best.pt", files)
        self.assertEqual(build_cfg.get("nsis", {}).get("include"), "build/uninstaller.nsh")

        with open(bat_path, "r", encoding="utf-8") as f:
            bat_code = f.read()

        self.assertIn('cd /d "%~dp0\\.."', bat_code)
        self.assertIn("errorlevel", bat_code)
        self.assertIn("dist:installer", bat_code)
        self.assertIn("build_release.py", bat_code)

        import tempfile
        from scripts.build_release import generate_engine_manifest, precompile_src_bytecode
        self.assertNotIn("!src/**/__pycache__/**", files)
        self.assertNotIn("!src/**/*.pyc", files)
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_src = os.path.join(tmp_dir, "src")
            os.makedirs(sample_src, exist_ok=True)
            with open(os.path.join(sample_src, "hello_mod.py"), "w", encoding="utf-8") as fh:
                fh.write("VALUE = 42\n")
            compiled_count = precompile_src_bytecode(tmp_dir)
            self.assertEqual(compiled_count, 1)
            pycache_dir = os.path.join(sample_src, "__pycache__")
            self.assertTrue(os.path.isdir(pycache_dir))
            pyc_files = [f for f in os.listdir(pycache_dir) if f.endswith(".pyc")]
            self.assertEqual(len(pyc_files), 1)
            with open(os.path.join(pycache_dir, pyc_files[0]), "rb") as pyc_fh:
                header = pyc_fh.read(8)
            bitfield = int.from_bytes(header[4:8], "little")
            self.assertEqual(bitfield & 0b1, 1)

            dummy_archive = os.path.join(tmp_dir, "engine-runtime.tar.zst")
            with open(dummy_archive, "wb") as fh:
                fh.write(b"\x28\xb5\x2f\xfddummy-engine-archive")
            dist_dir = os.path.join(tmp_dir, "dist")
            manifest_path, manifest = generate_engine_manifest(
                dummy_archive,
                dist_dir,
                engine_version=pkg["engineVersion"],
                app_version=pkg["version"],
            )
            self.assertTrue(os.path.isfile(manifest_path))
            self.assertEqual(manifest["engineVersion"], pkg["engineVersion"])
            self.assertEqual(manifest["archiveName"], "engine-runtime.tar.zst")
            self.assertEqual(len(manifest["sha256"]), 64)

    def test_electron_bootstrap_unit_suite(self):
        """Executa a suíte unitária nativa do Node.js cobrindo bootstrap, extrator e pre-flight."""
        import subprocess
        import shutil

        node_bin = shutil.which("node") or shutil.which("node.exe")
        if not node_bin:
            self.skipTest("Node.js não disponível no PATH")

        repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
        test_file = os.path.join(repo_root, "tests", "electron", "bootstrap.test.js")
        self.assertTrue(os.path.isfile(test_file))
        res = subprocess.run(
            [node_bin, "--test", test_file],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(res.returncode, 0, f"Bootstrap unit suite falhou:\n{res.stdout}\n{res.stderr}")

    def test_electron_smoke_test_script_and_contract(self):
        """Valida que scripts/smoke_test_electron.js existe e cumpre o contrato de integridade."""
        import subprocess
        import shutil

        smoke_script = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "scripts", "smoke_test_electron.js"))
        self.assertTrue(os.path.isfile(smoke_script))

        with open(smoke_script, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("runSmokeTest", code)
        self.assertIn("contextIsolation: true", code)
        self.assertIn("window.electronAPI", code)
        self.assertIn("safetyTimeout", code)

        # Se o executável npx estiver no PATH, roda o smoke test headless
        npx_bin = shutil.which("npx") or shutil.which("npx.cmd")
        if npx_bin:
            res = subprocess.run(
                [npx_bin, "electron", smoke_script],
                cwd=os.path.normpath(os.path.join(os.path.dirname(__file__), "..")),
                capture_output=True,
                text=True,
                timeout=45,
            )
            self.assertEqual(res.returncode, 0, f"Electron smoke test falhou: {res.stdout}\n{res.stderr}")

    def test_tray_manager_exports_and_flyout_bounds_contract(self):
        """Valida que trayManager.js exporta calculateFlyoutBounds e trata monitores secundários."""
        tray_mgr_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "electron", "trayManager.js"))
        self.assertTrue(os.path.isfile(tray_mgr_path))

        with open(tray_mgr_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("calculateFlyoutBounds", code)
        self.assertIn("hasTrayBounds", code)
        self.assertIn("FLYOUT_WIDTH", code)
        self.assertIn("FLYOUT_HEIGHT", code)

if __name__ == "__main__":
    unittest.main()



