import unittest
from unittest.mock import MagicMock, patch
import io
import json
import socket
import http.client

from src.translation_engine.ollama_client import call_ollama
from src.step1_layout_detector import YoloMapeador


class TestOllamaClientResilience(unittest.TestCase):
    def setUp(self):
        from src.translation_engine.ollama_client import _invalidate_ollama_base_cache
        _invalidate_ollama_base_cache()
    @patch("src.config.Config.get")
    @patch("urllib.request.urlopen")
    @patch("http.client.HTTPConnection")
    def test_call_ollama_normalizes_localhost_and_closes_conn(self, mock_http_conn_cls, mock_urlopen, mock_config_get):
        mock_config_get.return_value = "http://localhost:11435/api"
        mock_urlopen.side_effect = Exception("offline")
        
        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.side_effect = [
            b'{"message": {"content": "ok"}}\n',
            b''
        ]
        mock_conn.getresponse.return_value = mock_resp
        mock_http_conn_cls.return_value = mock_conn

        with patch("src.model_manager.ModelManager.ensure_ollama_running"):
            res = call_ollama("prompt", "user", model="test_model")

        # 1. Valida que o host foi normalizado para 127.0.0.1 (evita IPv6 ::1 no Windows)
        mock_http_conn_cls.assert_called_with("127.0.0.1", 11435, timeout=1.0)
        # 2. Valida que a conexão foi fechada (sem leak)
        mock_conn.close.assert_called()
        self.assertEqual(res, "ok")

    @patch("src.config.Config.get")
    @patch("urllib.request.urlopen")
    @patch("http.client.HTTPConnection")
    def test_call_ollama_closes_conn_on_exception(self, mock_http_conn_cls, mock_urlopen, mock_config_get):
        mock_config_get.return_value = "http://127.0.0.1:11435/api"
        mock_urlopen.side_effect = Exception("offline")

        mock_conn = MagicMock()
        mock_conn.getresponse.side_effect = OSError("Connection aborted")
        mock_http_conn_cls.return_value = mock_conn

        with patch("src.model_manager.ModelManager.ensure_ollama_running"):
            res = call_ollama("prompt", "user", model="test_model")

        # Deve fechar a conexão mesmo se houver OSError
        mock_conn.close.assert_called()
        self.assertEqual(res, "")

    @patch("src.config.Config.get")
    @patch("urllib.request.urlopen")
    @patch("http.client.HTTPConnection")
    def test_call_ollama_multibyte_utf8_split_resilience(self, mock_http_conn_cls, mock_urlopen, mock_config_get):
        mock_config_get.return_value = "http://127.0.0.1:11435/api"
        mock_urlopen.side_effect = Exception("offline")

        raw_json_line = json.dumps({"message": {"content": "日本語 ✨"}}, ensure_ascii=False).encode("utf-8") + b"\n"
        split_pos = 25
        chunk1 = raw_json_line[:split_pos]
        chunk2 = raw_json_line[split_pos:]

        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.side_effect = [chunk1, chunk2, b""]
        mock_conn.getresponse.return_value = mock_resp
        mock_http_conn_cls.return_value = mock_conn

        with patch("src.model_manager.ModelManager.ensure_ollama_running"):
            res = call_ollama("prompt", "user", model="test_model")

        self.assertEqual(res, "日本語 ✨")
        mock_conn.close.assert_called()


    @patch("src.config.Config.get")
    @patch("urllib.request.urlopen")
    @patch("http.client.HTTPConnection")
    def test_call_ollama_caches_endpoint_discovery(self, mock_http_conn_cls, mock_urlopen, mock_config_get):
        mock_config_get.return_value = "http://127.0.0.1:11435/api"
        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.side_effect = [b'{"message": {"content": "1"}}\n', b'', b'{"message": {"content": "2"}}\n', b'']
        mock_conn.getresponse.return_value = mock_resp
        mock_http_conn_cls.return_value = mock_conn

        with patch("src.model_manager.ModelManager.ensure_ollama_running"):
            # Primeira chamada: executa probe em /tags
            res1 = call_ollama("prompt", "user", model="test_model")
            # Segunda chamada logo em seguida: utiliza cache TTL e NAO chama urlopen de novo
            res2 = call_ollama("prompt", "user", model="test_model")

        self.assertEqual(res1, "1")
        self.assertEqual(res2, "2")
        self.assertEqual(mock_urlopen.call_count, 1)


class TestStep1LayoutResilience(unittest.TestCase):
    @patch("os.path.isfile", return_value=False)
    @patch("huggingface_hub.hf_hub_download", side_effect=RuntimeError("No internet connection"))
    def test_load_panel_detector_offline_fallback(self, mock_hf, mock_isfile):
        mapper = YoloMapeador()
        # Não deve lançar exceção mesmo se offline e sem arquivo pré-existente
        mapper.load_panel_detector()
        self.assertIsNone(mapper._panel_model)

        # Valida que detect_panels_and_sort degrada graciosamente sem o modelo
        bubbles = [{"x1": 10, "y1": 10, "x2": 50, "y2": 50}]
        mock_img = MagicMock()
        panels, sorted_bubbles = mapper.detect_panels_and_sort(mock_img, bubbles)
        self.assertEqual(panels, [])
        self.assertEqual(len(sorted_bubbles), 1)
