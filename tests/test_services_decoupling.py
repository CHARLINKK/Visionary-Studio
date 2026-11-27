import os
import sys
import unittest
import threading
import time


from src.utils.event_bus import EventBus, event_bus
from src.api_bridge import ApiBridge
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


class TestDecoupledServices(unittest.TestCase):
    def test_01_event_bus_pub_sub(self):
        """Valida que o EventBus funciona de forma desacoplada, multi-thread e sem deadlock."""
        received_events = []
        lock = threading.Lock()

        def on_event(payload):
            with lock:
                received_events.append(payload)

        bus = EventBus.get_instance()
        bus.subscribe("test:channel", on_event)

        # Dispara eventos de 5 threads concorrentes
        threads = []
        for i in range(5):
            t = threading.Thread(target=bus.publish, args=("test:channel", {"thread_id": i}))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(received_events), 5)
        bus.unsubscribe("test:channel", on_event)
        
        # Teste pós unsubscribe
        bus.publish("test:channel", {"after": True})
        self.assertEqual(len(received_events), 5)

    def test_02_standalone_services_without_bridge(self):
        """Valida que todos os serviços funcionam perfeitamente mesmo sem ApiBridge (Headless/CLI)."""
        win_svc = WindowService(api_bridge=None)
        self.assertFalse(win_svc.toggle_maximize())
        self.assertFalse(win_svc.start_tear_off_drag(0.5, 500, 300))
        self.assertFalse(win_svc.show_system_menu(500, 300))

        hw_svc = HardwareService(api_bridge=None)
        stats = hw_svc.getHardwareStats()
        self.assertIn("cpu_percent", stats)
        self.assertIn("ram_percent", stats)

        settings_svc = SettingsService(api_bridge=None)
        settings = settings_svc.getSettings()
        self.assertIsInstance(settings, dict)
        app_stats = settings_svc.getStats()
        self.assertIn("pagesProcessed", app_stats)

        lib_svc = LibraryService(api_bridge=None)
        lib_res = lib_svc.listLibraryFiles()
        self.assertTrue(lib_res["success"])

        img_svc = ImageService(api_bridge=None)
        img_res = img_svc.get_image_base64("arquivo_inexistente.png")
        self.assertFalse(img_res["success"])

        studio_svc = StudioService(api_bridge=None)
        studio_res = studio_svc.get_page_data("arquivo_inexistente.png")
        self.assertFalse(studio_res["success"])

        fs_svc = FileSystemService(api_bridge=None)
        drives_res = fs_svc.list_directory("MEU COMPUTADOR")
        self.assertTrue(drives_res["success"])
        self.assertGreater(len(drives_res["items"]), 0)

        model_svc = ModelService(api_bridge=None)
        mod_status = model_svc.checkModulesStatus()
        self.assertIn("ollama", mod_status)
        self.assertIn("ocr", mod_status)

        dev_svc = DevService(bridge=None)
        dev_stats = dev_svc.getDevStats()
        self.assertIn("torch_version", dev_stats)

    def test_03_apibridge_facade_delegation(self):
        """Valida que o ApiBridge atua perfeitamente como Facade para a interface webview."""
        bridge = ApiBridge()
        
        # Testes de chamadas de métodos delegados
        hw = bridge.getHardwareStats()
        self.assertIn("cpu_percent", hw)
        self.assertIn("cpu_name", hw)
        self.assertIn("cpu_cores", hw)
        self.assertIn("cpu_threads", hw)

        st = bridge.getSettings()
        self.assertIsInstance(st, dict)

        drives = bridge.get_drives()
        self.assertIsInstance(drives, list)

        modules = bridge.checkModulesStatus()
        self.assertIn("ollama", modules)

        progress = bridge.getInstallProgress()
        self.assertIn("status", progress)

        downloads = bridge.getDownloadsProgress()
        self.assertTrue(downloads["success"])

    def test_04_thread_safety_concurrency(self):
        """Testa 20 chamadas simultâneas de múltiplas threads no ApiBridge para garantir ausência de deadlocks."""
        bridge = ApiBridge()
        errors = []

        def worker(idx):
            try:
                bridge.getHardwareStats()
                bridge.getSettings()
                bridge.checkModulesStatus()
                bridge.getDownloadsProgress()
            except Exception as e:
                errors.append((idx, e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(len(errors), 0, f"Erros encontrados na concorrência: {errors}")





if __name__ == "__main__":
    unittest.main()
