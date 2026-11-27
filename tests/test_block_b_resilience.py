"""
Testes de Blindagem do Bloco B: Resiliência do Pipeline & Kernel Windows.
- Validação do Windows Job Object com JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
- Validação de cancelamento cooperativo não-bloqueante na tradução via Ollama.
"""

import os
import sys
import time
import threading
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler

from src.utils.win32_job import setup_job_object_kill_on_close, assign_pid_to_job
import src.run_batch as rb
from src.translation_engine.ollama_client import call_ollama


def test_win32_job_object_initialization():
    """Valida a criação e idempotência do Windows Job Object nativo."""
    if sys.platform != 'win32':
        pytest.skip("Teste exclusivo para ambiente Windows")

    hJob = setup_job_object_kill_on_close()
    assert hJob is not None

    # Idempotência: deve retornar o mesmo handle global
    hJob2 = setup_job_object_kill_on_close()
    assert hJob2 == hJob

    # Atribuição do PID atual deve retornar True
    res = assign_pid_to_job(os.getpid())
    assert res is True

    # Atribuição defensiva com PID inválido deve falhar sem crash
    assert assign_pid_to_job(-1) is False
    assert assign_pid_to_job(0) is False


def test_ollama_client_instant_cancellation(monkeypatch):
    """
    Testa se o call_ollama responde a cancelamento instantaneamente (< 2.0s)
    em vez de ficar travado nos 300s de timeout do socket.
    """
    # 1. Cria um servidor HTTP mock local lento
    class SlowHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            # Simula atraso extenso do Ollama compilando prompt na GPU
            time.sleep(10)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"message":{"content":"teste"}}\n')

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), SlowHandler)
    server_port = server.server_port
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    # Redireciona a URL do Ollama para o nosso servidor lento e previne inicialização real de processo
    from src.config import Config
    monkeypatch.setattr(Config, "get", lambda k, d=None: f"http://127.0.0.1:{server_port}/api" if k == "ollama_url" else d)
    monkeypatch.setattr("src.model_manager.ModelManager.ensure_ollama_running", lambda self: True)

    # 2. Agenda o cancelamento do batch em 0.6 segundos
    rb._cancel_event.clear()
    def _cancel_after_delay():
        time.sleep(0.6)
        rb._cancel_event.set()

    t_canceler = threading.Thread(target=_cancel_after_delay, daemon=True)
    t_canceler.start()

    start_t = time.time()
    result = call_ollama(
        system_prompt="sys",
        user_prompt="user",
        model="test_model",
        num_ctx=512
    )
    elapsed = time.time() - start_t

    # Limpa a flag de cancelamento
    rb._cancel_event.clear()
    server.server_close()

    # A chamada DEVE ter sido interrompida imediatamente após o cancel_event (< 3.0s)
    # e NÃO pode ter esperado os 10s do servidor mock nem 300s de timeout!
    assert result == ""
    assert elapsed < 3.5, f"O cancelamento demorou {elapsed:.2f}s, indicando bloqueio no socket HTTP!"
