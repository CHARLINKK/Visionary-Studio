import unittest
from unittest.mock import patch, MagicMock
from src.utils.vram_monitor import (
    get_vram_snapshot,
    set_pytorch_attribution,
    clear_pytorch_attribution,
    _get_torch_info,
    _get_ollama_breakdown,
    _pytorch_attribution
)

class TestVramMonitor(unittest.TestCase):
    def setUp(self):
        # Limpa o state global antes de cada teste
        _pytorch_attribution.clear()

    @patch("requests.get")
    def test_ollama_breakdown_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:latest", "size_vram": 2048 * 1024 * 1024},
                {"name": "qwen2-instruct:7b", "size_vram": 4096 * 1024 * 1024},
                {"name": "small_model", "size_vram": 5 * 1024 * 1024} # Ignorado por < 10MB
            ]
        }
        mock_get.return_value = mock_response

        breakdown = _get_ollama_breakdown()
        self.assertIn("llama3", breakdown)
        self.assertEqual(breakdown["llama3"], 2048.0)
        self.assertIn("qwen2", breakdown) # removeu -instruct
        self.assertEqual(breakdown["qwen2"], 4096.0)
        self.assertNotIn("small_model", breakdown)

    @patch("requests.get")
    def test_ollama_breakdown_exception(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        self.assertEqual(_get_ollama_breakdown(), {})

    def test_get_torch_info_no_cuda(self):
        with patch.dict('sys.modules', {'torch': None}):
            system, alloc, res, total = _get_torch_info()
            self.assertEqual((system, alloc, res, total), (0.0, 0.0, 0.0, 8192.0))

    def test_get_torch_info_with_cuda(self):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        # mem_get_info returns (free, total)
        MB = 1024 ** 2
        mock_torch.cuda.mem_get_info.return_value = (4000 * MB, 8000 * MB)
        mock_torch.cuda.memory_allocated.return_value = 1000 * MB
        mock_torch.cuda.memory_reserved.return_value = 2000 * MB

        with patch.dict('sys.modules', {'torch': mock_torch}):
            system, alloc, res, total = _get_torch_info()
            self.assertEqual(system, 4000.0)
            self.assertEqual(alloc, 1000.0)
            self.assertEqual(res, 2000.0)
            self.assertEqual(total, 8000.0)

    @patch("src.utils.vram_monitor._get_torch_info")
    @patch("src.utils.vram_monitor._get_ollama_breakdown")
    def test_get_vram_snapshot_complex_scenario(self, mock_ollama, mock_torch):
        """Testa o motor de inferência de distribuições (system, cache, pyTorch, Ollama)"""
        # system_used = 6000, allocated = 2500, reserved = 3500, total = 8192
        mock_torch.return_value = (6000.0, 2500.0, 3500.0, 8192.0)
        mock_ollama.return_value = {"llama3": 1000.0}

        set_pytorch_attribution("YOLO", 500.0)
        set_pytorch_attribution("Florence-2", 1500.0)

        snap = get_vram_snapshot()
        breakdown = snap["breakdown"]

        # Florence deve ter (1500 + 500 de ativação extra, pois total allocated=2500 vs tracked=2000)
        # O top_model recebe as ativações = Florence-2 = 1500 + 500 = 2000.0
        self.assertEqual(breakdown["Florence-2"], 2000.0)
        self.assertEqual(breakdown["YOLO"], 500.0)
        self.assertEqual(breakdown["llama3"], 1000.0)
        
        # Cache GPU = reserved (3500) - allocated (2500) = 1000.0
        self.assertEqual(breakdown["Cache GPU"], 1000.0)
        
        # Outros = system_used (6000) - pytorch_reserved (3500) - ollama (1000) = 1500.0
        self.assertEqual(breakdown["Outros"], 1500.0)

    @patch("src.utils.vram_monitor._get_torch_info")
    @patch("src.utils.vram_monitor._get_ollama_breakdown")
    def test_get_vram_snapshot_auto_correction(self, mock_ollama, mock_torch):
        """Testa auto-correção quando modelos sumiram silenciosamente da VRAM."""
        # allocated = 100, muito menor que os 1500 rastreados
        mock_torch.return_value = (1000.0, 100.0, 500.0, 8192.0)
        mock_ollama.return_value = {}
        
        set_pytorch_attribution("GhostModel", 1500.0)
        
        snap = get_vram_snapshot()
        breakdown = snap["breakdown"]
        
        # O modelo ghost deve ser removido do breakdown pois a VRAM não reflete ele
        self.assertNotIn("GhostModel", breakdown)
        self.assertIn("PyTorch", breakdown)
        self.assertEqual(breakdown["PyTorch"], 100.0)

    def test_clear_attribution(self):
        set_pytorch_attribution("test", 100)
        clear_pytorch_attribution("test")
        self.assertNotIn("test", _pytorch_attribution)
