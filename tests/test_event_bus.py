import unittest
from src.utils.event_bus import EventBus
from unittest.mock import patch, MagicMock
import io
import sys

class TestEventBus(unittest.TestCase):
    def setUp(self):
        # We want to test the EventBus specifically. Since it's a singleton,
        # we can reset its state for the test.
        self.bus = EventBus.get_instance()
        self.bus._subscribers.clear()

    def test_callback_exception_is_caught(self):
        """Valida que uma exceção em um callback não derruba o barramento."""
        def bad_callback(payload):
            raise ValueError("Erro forçado no callback")

        received = []
        def good_callback(payload):
            received.append(payload)

        self.bus.subscribe("test:error", bad_callback)
        self.bus.subscribe("test:error", good_callback)

        # Captura o stdout para verificar o traceback
        captured_output = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            self.bus.publish("test:error", {"data": 123})
        finally:
            sys.stdout = original_stdout

        # O good_callback deve ter sido executado apesar do erro no bad_callback
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], {"data": 123})
        
        # O erro deve ter sido printado (com traceback)
        output = captured_output.getvalue()
        self.assertIn("[EventBus] Erro ao executar callback", output)
        self.assertIn("Erro forçado no callback", output)

    @patch("src.utils.event_bus.json.dumps")
    def test_emit_to_webview_exception_is_silent(self, mock_dumps):
        """Valida que falhas na emissão para o webview (como objeto não serializável) não quebram o publish."""
        def good_callback(payload):
            pass
            
        self.bus.subscribe("test:webview", good_callback)
        
        # Força um TypeError ao tentar serializar o payload para o javascript
        mock_dumps.side_effect = TypeError("Not serializable")
        
        # Mock do broadcast_log_sync para também falhar e garantir que cai no except
        with patch("src.server.broadcast_log_sync", side_effect=Exception("Failed broadcast")):
            # Deve executar silenciosamente
            self.bus.publish("test:webview", {"complex_object": object()})
            
        # O teste passa se nenhuma exceção vazar.

    def test_unsubscribe_callback(self):
        """Valida que o unsubscribe remove o listener e ele não é mais chamado."""
        received = []
        def my_callback(payload):
            received.append(payload)

        self.bus.subscribe("test:unsub", my_callback)
        self.bus.publish("test:unsub", 1)
        self.assertEqual(len(received), 1)

        self.bus.unsubscribe("test:unsub", my_callback)
        self.bus.publish("test:unsub", 2)
        # O listener não deve ter recebido a segunda chamada
        self.assertEqual(len(received), 1)

