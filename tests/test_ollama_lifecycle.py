import unittest
from unittest.mock import MagicMock, patch
import sys
import subprocess

from src.model_manager import ModelManager
from src.api_services.model_service import ModelService


class TestOllamaLifecycle(unittest.TestCase):
    def setUp(self):
        ModelManager._ollama_process = None
        ModelManager._ollama_pid = None

    def tearDown(self):
        ModelManager._ollama_process = None
        ModelManager._ollama_pid = None

    def test_terminate_ollama_noop_when_not_started_by_us(self):
        # Se o Visionary não iniciou o processo (ex: usuário já tinha o Ollama rodando externamente),
        # terminate_ollama não deve tentar matar nenhum processo.
        with patch("subprocess.run") as mock_run:
            ModelManager.terminate_ollama()
            mock_run.assert_not_called()

    def test_terminate_ollama_kills_tracked_process_and_resets(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 4321
        ModelManager._ollama_process = mock_proc
        ModelManager._ollama_pid = 4321

        with patch("subprocess.run") as mock_run:
            ModelManager.terminate_ollama()
            
            if sys.platform == 'win32':
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                self.assertIn("taskkill", args[0])
                self.assertIn("4321", args[0])
                self.assertIn("/t", args[0])
                self.assertIn("/f", args[0])

            self.assertIsNone(ModelManager._ollama_process)
            self.assertIsNone(ModelManager._ollama_pid)

    def test_ensure_ollama_running_tracks_process_handle(self):
        mock_proc = MagicMock()
        mock_proc.pid = 7777
        mock_proc.poll.return_value = None
        
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_session
        mock_session.get.side_effect = OSError("Not running")

        manager = ModelManager()
        with patch.object(manager, "check_ollama_running", side_effect=[False, True]), \
             patch.object(manager._ollama_mgr, "check_ollama_running", side_effect=[False, True]), \
             patch("src.model_engines.ollama_process_manager.requests.Session", return_value=mock_session), \
             patch("requests.Session", return_value=mock_session), \
             patch("os.path.isfile", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            res = manager.ensure_ollama_running()
            self.assertTrue(res)
            self.assertEqual(ModelManager._ollama_pid, 7777)
            self.assertEqual(ModelManager._ollama_process, mock_proc)

    def test_model_service_stop_ollama_server(self):
        service = ModelService(MagicMock())
        with patch.object(ModelManager, "terminate_ollama") as mock_term:
            res = service.stopOllamaServer()
            self.assertTrue(res.get("success"))
            mock_term.assert_called_once()
