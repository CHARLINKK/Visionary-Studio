import unittest
from unittest.mock import patch, MagicMock
import os
from src.utils.gpu_utils import setup_cuda_env, cleanup_gpu_memory, ModelLoadTracker

class TestGpuUtils(unittest.TestCase):
    def test_setup_cuda_env(self):
        """Valida que o ambiente CUDA é configurado corretamente para expandir segmentos ou mitigar fragmentação."""
        import sys
        # Limpa caso exista
        if "PYTORCH_CUDA_ALLOC_CONF" in os.environ:
            del os.environ["PYTORCH_CUDA_ALLOC_CONF"]
            
        setup_cuda_env()
        expected = "max_split_size_mb:128" if sys.platform == "win32" else "expandable_segments:True"
        self.assertEqual(os.environ["PYTORCH_CUDA_ALLOC_CONF"], expected)

    @patch("src.utils.gpu_utils.gc.collect")
    def test_cleanup_gpu_memory_no_torch(self, mock_gc):
        """Valida que o cleanup é resiliente se o PyTorch não estiver instalado."""
        # Simula ImportError ao importar torch
        with patch.dict('sys.modules', {'torch': None}):
            cleanup_gpu_memory()
            
        mock_gc.assert_called_once()

    @patch("src.utils.gpu_utils.gc.collect")
    def test_cleanup_gpu_memory_does_not_import_torch_if_absent(self, mock_gc):
        """Valida que o cleanup não força o import do PyTorch se ele não estiver carregado."""
        import sys
        modules_copy = dict(sys.modules)
        modules_copy.pop("torch", None)
        with patch.dict(sys.modules, modules_copy, clear=True):
            orig_import = __import__
            def guarded_import(name, *args, **kwargs):
                if name == "torch":
                    raise AssertionError("torch should not be eagerly imported by cleanup_gpu_memory!")
                return orig_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=guarded_import):
                cleanup_gpu_memory()
                mock_gc.assert_called_once()

    @patch("src.utils.gpu_utils.gc.collect")
    def test_cleanup_gpu_memory_with_torch_ipc_error(self, mock_gc):
        """Valida fallback se ipc_collect falhar em ambientes não suportados (ex: Windows)."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.ipc_collect.side_effect = Exception("IPC não suportado")
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            cleanup_gpu_memory()
            
        mock_torch.cuda.empty_cache.assert_called_once()
        mock_torch.cuda.ipc_collect.assert_called_once()

    @patch("builtins.print")
    def test_safe_print_unicode_error(self, mock_print):
        """Valida fallback de codificação ASCII em terminais que não suportam UTF-8."""
        tracker = ModelLoadTracker("test")
        
        # Simula que o print normal deu erro de Unicode
        mock_print.side_effect = [UnicodeEncodeError("ascii", "", 0, 1, "test"), None]
        tracker._safe_print("test character á")
        
        # O segundo print deve ter sido chamado com a string em ascii replace
        self.assertEqual(mock_print.call_count, 2)

    @patch("src.utils.gpu_utils.requests.get")
    @patch("src.utils.gpu_utils.time.sleep")
    def test_poll_ollama_vram(self, mock_sleep, mock_get):
        """Valida a polling da VRAM de modelos Ollama via API REST."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3", "size_vram": 2048 * 1024 * 1024, "size": 4096 * 1024 * 1024}]
        }
        mock_get.return_value = mock_response
        
        # Mata o loop na primeira iteração simulando a Thread parando
        def side_effect(*args):
            tracker.running = False
        mock_sleep.side_effect = side_effect
        
        tracker = ModelLoadTracker("llama3", is_ollama=True)
        tracker.running = True
        
        with patch.object(tracker, "_safe_print") as mock_safe_print:
            tracker._poll_ollama_vram()
            
            # Deve ter printado o progresso
            mock_safe_print.assert_called()
            
    @patch("src.utils.gpu_utils.requests.get")
    @patch("src.utils.gpu_utils.time.sleep")
    def test_poll_ollama_vram_model_not_found(self, mock_sleep, mock_get):
        """Valida o fallback de polling quando o modelo ainda não subiu."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        mock_get.return_value = mock_response
        
        def side_effect(*args):
            tracker.running = False
        mock_sleep.side_effect = side_effect
        
        tracker = ModelLoadTracker("llama3", is_ollama=True)
        tracker.running = True
        # Força o start time retroativo para engatilhar o print do fallback (timeout de 0.5s)
        import time
        with patch("src.utils.gpu_utils.time.time", side_effect=[time.time(), time.time() + 1.0]):
            with patch.object(tracker, "_safe_print") as mock_safe_print:
                tracker._poll_ollama_vram()
                mock_safe_print.assert_called_with("[VRAM_PROGRESS:llama3:0/100.0MB]")

    def test_model_load_tracker_context_manager_pytorch(self):
        """Valida o ciclo de vida completo do Context Manager para modelos PyTorch."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.memory_allocated.side_effect = [1024 * 1024 * 500, 1024 * 1024 * 1500] # 500MB -> 1.5GB
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            with patch("src.utils.vram_monitor.set_pytorch_attribution") as mock_attr:
                with patch("src.utils.gpu_utils.threading.Thread") as mock_thread:
                    with ModelLoadTracker("yolov8") as tracker:
                        self.assertTrue(tracker.running)
                        self.assertEqual(tracker._vram_before_mb, 500.0)
                        
                    # Ao sair do context manager
                    self.assertFalse(tracker.running)
                    mock_attr.assert_called_once_with("yolov8", 1000.0)
                    
    def test_model_load_tracker_import_error(self):
        """Valida context manager sendo resiliente sem torch instalado."""
        with patch.dict('sys.modules', {'torch': None}):
            with patch("src.utils.gpu_utils.threading.Thread") as mock_thread:
                with ModelLoadTracker("dummy") as tracker:
                    pass
            # Sem crash

    @patch("src.utils.gpu_utils.time.sleep")
    def test_poll_pytorch_vram(self, mock_sleep):
        """Valida o loop de monitoramento da VRAM do PyTorch."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        
        # Simula o consumo crescendo: 500MB -> 550MB -> 600MB
        MB = 1024 * 1024
        mock_torch.cuda.memory_allocated.side_effect = [500 * MB, 550 * MB, 600 * MB]
        
        tracker = ModelLoadTracker("yolov8", total_size_mb=100.0)
        
        # Interrompe o loop na segunda iteração
        def side_effect(*args):
            if mock_sleep.call_count >= 2:
                tracker.running = False
        mock_sleep.side_effect = side_effect
        
        tracker.running = True
        with patch.dict('sys.modules', {'torch': mock_torch}):
            with patch.object(tracker, "_safe_print") as mock_safe_print:
                tracker._poll_pytorch_vram()
                
                # Deve ter printado o progresso
                self.assertTrue(mock_safe_print.called)
                mock_safe_print.assert_any_call("[VRAM_PROGRESS:yolov8:50.0/100.0MB]")
                mock_safe_print.assert_any_call("[VRAM_PROGRESS:yolov8:100.0/100.0MB]")

    @patch("src.utils.gpu_utils.requests.get")
    def test_model_load_tracker_ollama_skips_when_already_loaded(self, mock_get):
        """Valida que se o modelo Ollama já estiver residente na VRAM, nenhum log redundante é impresso."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "qwen2.5:7b", "size_vram": 1024 * 1024 * 4500}]
        }
        mock_get.return_value = mock_response

        with patch("src.utils.gpu_utils.threading.Thread") as mock_thread:
            with patch("src.utils.gpu_utils.print") as mock_print:
                with ModelLoadTracker("qwen2.5:7b", is_ollama=True) as tracker:
                    self.assertTrue(tracker._already_loaded)
                    mock_thread.assert_not_called()
                    mock_print.assert_not_called()
