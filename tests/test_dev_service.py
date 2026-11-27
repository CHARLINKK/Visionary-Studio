import unittest
from unittest.mock import patch, MagicMock
from src.api_services.dev_service import DevService, StreamInterceptor
import sys

class TestDevService(unittest.TestCase):
    def setUp(self):
        self.dev = DevService()

    def test_stream_interceptor_ignored_patterns(self):
        """Valida que mensagens de heartbeat e polling não poluem o log"""
        # A inicialização já injeta no sys.stdout
        sys.stdout.write("POST /api/rpc/getDevStats HTTP 1.1")
        # O log não deve conter essa string
        self.assertNotIn("POST /api/rpc/getDevStats HTTP 1.1", self.dev._app_logs)

        sys.stdout.write("Isso deve aparecer\n")
        self.assertIn("Isso deve aparecer", self.dev._app_logs)

    def test_getDevStats_cpu_only(self):
        """Valida estatisticas quando está rodando apenas em CPU."""
        with patch.dict("sys.modules", {"torch": None}):
            stats = self.dev.getDevStats()
            self.assertFalse(stats["cuda_available"])
            self.assertEqual(stats["vram_total"], 0)

    @patch("subprocess.run")
    def test_getDevStats_with_cuda(self, mock_run):
        """Valida estatisticas quando CUDA está ativo e nvidia-smi responde."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.__version__ = "2.0.0"
        mock_torch.cuda.get_device_name.return_value = "RTX 3060"
        
        mock_props = MagicMock()
        mock_props.total_memory = 12 * 1024 * 1024 * 1024 # 12GB
        mock_torch.cuda.get_device_properties.return_value = mock_props
        
        mock_torch.cuda.memory_allocated.return_value = 1024 * 1024 * 1024 # 1GB
        mock_torch.cuda.memory_reserved.return_value = 2 * 1024 * 1024 * 1024 # 2GB
        
        mock_result = MagicMock()
        mock_result.stdout = "4000\n" # nvidia-smi memory.used em MB
        mock_run.return_value = mock_result
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            stats = self.dev.getDevStats()
            
        self.assertTrue(stats["cuda_available"])
        self.assertEqual(stats["vram_total"], 12 * 1024)
        self.assertEqual(stats["vram_allocated_global"], 4000 / 1024)
        self.assertEqual(stats["vram_allocated_pytorch"], 1024)
        self.assertEqual(stats["vram_reserved"], 2048)
        self.assertEqual(stats["vram_total_gb"], 12.0)
        self.assertEqual(stats["vram_used_gb"], 3.91) # 4000/1024 arredondado

    @patch("src.utils.gpu_utils.cleanup_gpu_memory")
    @patch("requests.get")
    @patch("requests.post")
    def test_clearVRAM(self, mock_post, mock_get, mock_cleanup):
        """Valida a limpeza global de VRAM (Ollama + PyTorch)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
        mock_get.return_value = mock_resp
        
        with patch.dict("sys.modules", {"requests": MagicMock(get=mock_get, post=mock_post)}):
            res = self.dev.clearVRAM()
        
        self.assertTrue(res["success"])
        mock_cleanup.assert_called_once()
        mock_post.assert_called_once()
        
    @patch("src.utils.gpu_utils.cleanup_gpu_memory")
    def test_unloadDevModel(self, mock_cleanup):
        """Valida endpoint de unload via dev mode."""
        res = self.dev.unloadDevModel("yolo")
        self.assertTrue(res["success"])
        mock_cleanup.assert_called_once()

    def test_getTestList(self):
        """Valida descoberta de scripts de teste via reflexão."""
        res = self.dev.getTestList()
        self.assertTrue("files" in res)
        # O arquivo atual (test_dev_service.py) não existe no diretório alvo do sys_path real
        # mas os originais sim.
        
    @patch("src.api_services.dev_service.subprocess.Popen")
    def test_runTests_dev_mode(self, mock_popen):
        """Valida que o runTests aciona o Pytest em Thread separada."""
        # Configura o Popen mock para retornar imediatamente como se tivesse rodado
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["collected 10 items", "tests/test_1.py::test PASSED [ 50%]", ""]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        res = self.dev.runTests("test_json_utils.py")
        self.assertTrue(res["success"])
        
        # Pega a thread e espera terminar
        time_limit = 2.0
        import time
        start = time.time()
        while self.dev._is_test_running and time.time() - start < time_limit:
            time.sleep(0.01)
            
        logs = self.dev.getDevLogs()
        self.assertEqual(logs["test_progress"]["return_code"], 0)
        self.assertEqual(logs["test_progress"]["total"], 10)
        self.assertEqual(logs["test_progress"]["percent"], 100) # Finish força 100
        self.assertEqual(logs["test_progress"]["passed"], 1)

    @patch("src.api_services.dev_service.sys.frozen", True, create=True)
    def test_runTests_production_mode(self):
        """Valida que no modo release (frozen), os testes rodam via internal diagnostics."""
        res = self.dev.runTests()
        self.assertTrue(res["success"])
        
        import time
        start = time.time()
        while self.dev._is_test_running and time.time() - start < 2.0:
            time.sleep(0.01)
            
        logs = self.dev.getDevLogs()
        # Diagnostic printa info do sistema
        found = any("Sistema Operacional" in log for log in logs["test_logs"])
        self.assertTrue(found)

    def test_runTests_already_running(self):
        """Valida lock contra múltiplas execuções de teste simultâneas."""
        self.dev._is_test_running = True
        res = self.dev.runTests()
        self.assertFalse(res["success"])
        self.assertIn("andamento", res["error"])

    def test_cancelTests_lifecycle(self):
        """Valida cancelamento de testes quando em execução e quando ocioso."""
        # Quando não há testes rodando
        idle_res = self.dev.cancelTests()
        self.assertFalse(idle_res["success"])

        # Quando há processo em execução simulado
        mock_proc = MagicMock()
        self.dev._is_test_running = True
        self.dev._test_process = mock_proc
        cancel_res = self.dev.cancelTests()
        self.assertTrue(cancel_res["success"])
        mock_proc.terminate.assert_called_once()
        self.assertFalse(self.dev._is_test_running)

    def test_stream_interceptor_no_nested_wrapping(self):
        """Valida que instanciar DevService múltiplas vezes não aninha interceptors recursivamente."""
        first_stdout = sys.stdout
        dev2 = DevService()
        self.assertIs(sys.stdout, first_stdout)
        self.assertIs(dev2._stdout_interceptor, first_stdout)

    def test_all_test_files_have_descriptive_labels(self):
        """Garante que todas as suítes test_*.py em tests/ possuem rótulo amigável em TEST_LABELS."""
        from pathlib import Path
        from src.api_services.dev_service import TEST_LABELS
        tests_dir = Path(__file__).resolve().parent
        test_files = sorted(p.name for p in tests_dir.glob("test_*.py"))
        missing = [f for f in test_files if f not in TEST_LABELS]
        self.assertEqual(missing, [], f"Suítes de teste sem rótulo em TEST_LABELS: {missing}")

