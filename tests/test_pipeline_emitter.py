import threading
import time
import pytest
from unittest.mock import MagicMock, patch
from src.utils.pipeline_emitter import (
    PipelineEmitter,
    ThreadScopedStdout,
    scoped_job_stdout
)


class MockPipelineService:
    def __init__(self):
        self._jobs_lock = threading.Lock()
        self._active_jobs = {
            "job-test-1": {
                "logs": [],
                "progress": 0,
                "status": "running",
                "step_label": "",
                "vramState": None,
                "vramRealtime": None,
            }
        }


def test_emitter_direct_progress_and_step():
    service = MockPipelineService()
    emitter = PipelineEmitter("job-test-1", service=service)

    with patch("src.server.broadcast_log_sync") as mock_broadcast:
        with patch("src.utils.event_bus.event_bus.publish") as mock_event_bus:
            # Emit progress
            emitter.emit_progress(25, "Mapeando balões...")
            assert service._active_jobs["job-test-1"]["progress"] == 25
            assert service._active_jobs["job-test-1"]["step_label"] == "Mapeando balões..."
            mock_broadcast.assert_called_with(
                "job_progress",
                "",
                progress=25,
                extra={"job_id": "job-test-1", "step_label": "Mapeando balões..."}
            )

            # Emit step
            emitter.emit_step("LAYOUT", "Layout concluído")
            assert service._active_jobs["job-test-1"]["step_label"] == "Layout concluído"
            mock_event_bus.assert_called_with("visionary:xray-refresh")


def test_emitter_vram_and_logs():
    service = MockPipelineService()
    emitter = PipelineEmitter("job-test-1", service=service)

    with patch("src.server.broadcast_log_sync"):
        # VRAM State
        vstate = {"model": "florence", "progress": 100, "done": True}
        emitter.emit_vram_state(vstate)
        assert service._active_jobs["job-test-1"]["vramState"] == vstate

        # VRAM Realtime
        vrt = {"used_mb": 4096, "total_mb": 8192}
        emitter.emit_vram_realtime(vrt)
        assert service._active_jobs["job-test-1"]["vramRealtime"] == vrt

        # Logs
        emitter.emit_log("Linha 1 do processamento")
        logs = service._active_jobs["job-test-1"]["logs"]
        assert len(logs) == 1
        assert "Linha 1 do processamento" in logs[0]

        # Log replacement
        emitter.emit_log("Linha 2 [versao inicial]")
        assert len(logs) == 2
        emitter.emit_log("Linha 2 [versao final]", is_replace=True, replace_prefix="Linha 2")
        assert len(logs) == 2
        assert "Linha 2 [versao final]" in logs[1]


def test_thread_scoped_stdout_isolation():
    """
    Verifica que apenas a thread registrada no scoped_job_stdout tem seus prints
    capturados para o job. Outras threads do processo escrevem livremente sem poluir o job.
    """
    service = MockPipelineService()
    emitter = PipelineEmitter("job-test-1", service=service)

    external_thread_ran = threading.Event()
    job_thread_ran = threading.Event()

    def external_thread_work():
        # Simula uma requisição HTTP do FastAPI acontecendo em paralelo
        print("Mensagem de outra thread externa que NAO deve ir para o job")
        external_thread_ran.set()

    def job_thread_work():
        with scoped_job_stdout(emitter):
            # Esta saída pertence ao job e deve ser capturada
            print("Mensagem legítima da thread do job de IA")
            # Dispara thread externa simultaneamente
            t_ext = threading.Thread(target=external_thread_work)
            t_ext.start()
            t_ext.join()
        job_thread_ran.set()

    t_job = threading.Thread(target=job_thread_work)
    t_job.start()
    t_job.join()

    assert job_thread_ran.is_set()
    assert external_thread_ran.is_set()

    logs = service._active_jobs["job-test-1"]["logs"]
    logs_str = " ".join(logs)

    # Mensagem do job deve estar presente
    assert "Mensagem legítima da thread do job de IA" in logs_str
    # Mensagem da thread externa NUNCA pode ter sido capturada pelo job!
    assert "Mensagem de outra thread externa" not in logs_str


def test_scoped_job_stdout_exception_safety():
    """
    Garante que se uma exceção ocorrer dentro do bloco scoped_job_stdout,
    a thread é desregistrada no finally e prints subsequentes não caem no emitter.
    """
    service = MockPipelineService()
    emitter = PipelineEmitter("job-test-1", service=service)

    try:
        with scoped_job_stdout(emitter):
            print("Mensagem antes do erro")
            raise RuntimeError("Falha intencional na GPU")
    except RuntimeError:
        pass

    # Print fora do bloco
    print("Mensagem apos o erro fora do escopo")

    logs = service._active_jobs["job-test-1"]["logs"]
    logs_str = " ".join(logs)

    assert "Mensagem antes do erro" in logs_str
    assert "Mensagem apos o erro fora do escopo" not in logs_str


def test_thread_scoped_stdout_full_textio_compliance():
    """
    Verifica que o proxy ThreadScopedStdout implementa todos os métodos e atributos
    esperados de um TextIOBase (isatty, writable, encoding, writelines) via delegação transparente,
    prevenindo exceções de AttributeError em Uvicorn, ASGI loggers ou C extensions.
    """
    import sys
    orig_stdout = sys.stdout
    service = MockPipelineService()
    emitter = PipelineEmitter("job-test-1", service=service)

    with scoped_job_stdout(emitter):
        proxy = sys.stdout
        # Conformidade com atributos padrão
        assert hasattr(proxy, "encoding")
        assert hasattr(proxy, "isatty")
        assert isinstance(proxy.isatty(), bool)
        assert proxy.writable() == getattr(orig_stdout, "writable", lambda: True)()
        assert proxy.readable() == getattr(orig_stdout, "readable", lambda: False)()
        assert proxy.seekable() == getattr(orig_stdout, "seekable", lambda: False)()

        # writelines funciona e é capturado para o job
        proxy.writelines(["Linha via writelines 1\n", "Linha via writelines 2\n"])

    # Após o bloco, stdout deve ser restaurado ao objeto original
    assert sys.stdout is orig_stdout

    logs = service._active_jobs["job-test-1"]["logs"]
    logs_str = " ".join(logs)
    assert "Linha via writelines 1" in logs_str
    assert "Linha via writelines 2" in logs_str


def test_call_ollama_emits_typed_progress_without_stdout_scraping():
    """Garante que o streaming do Ollama usa PipelineEmitter diretamente sem imprimir [PROGRESS:XX] no stdout."""
    from src.translation_engine.ollama_client import call_ollama, _invalidate_ollama_base_cache

    _invalidate_ollama_base_cache()
    service = MockPipelineService()
    emitter = PipelineEmitter("job-test-1", service=service)

    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.side_effect = [
        b'{"message": {"content": "{\\"translations\\": [{\\"id\\": 1, \\"text\\": \\"Oi\\"},"}} \n',
        b'{"message": {"content": "{\\"id\\": 2, \\"text\\": \\"Tudo bem\\"}]}"}}\n',
        b"",
    ]
    mock_conn.getresponse.return_value = mock_resp

    with patch("src.server.broadcast_log_sync"):
        with patch("src.config.Config.get", return_value="http://127.0.0.1:11435/api"):
            with patch("urllib.request.urlopen", side_effect=Exception("offline")):
                with patch("http.client.HTTPConnection", return_value=mock_conn):
                    with patch("src.model_manager.ModelManager.ensure_ollama_running"):
                        with patch("builtins.print") as mock_print:
                            res = call_ollama(
                                "sys",
                                "usr",
                                model="qwen2.5:7b",
                                prog_base=20.0,
                                prog_slice=40.0,
                                total_ids=2,
                                progress_emitter=emitter,
                            )

    assert '"id": 2' in res
    assert service._active_jobs["job-test-1"]["progress"] == 60.0
    printed_args = " ".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
    assert "[PROGRESS:" not in printed_args


def test_model_load_tracker_child_thread_emits_vram_state_to_job_emitter():
    """Garante que a thread filha do ModelLoadTracker herda o PipelineEmitter da thread do job."""
    import itertools
    from src.utils.gpu_utils import ModelLoadTracker

    service = MockPipelineService()
    emitter = PipelineEmitter("job-test-1", service=service)
    polled_event = threading.Event()
    intermediate_states = []

    orig_emit_vram = emitter.emit_vram_state
    def spy_emit_vram(vstate):
        orig_emit_vram(vstate)
        if not vstate.get("done"):
            intermediate_states.append(vstate)
            polled_event.set()
    emitter.emit_vram_state = spy_emit_vram

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    MB = 1024 * 1024
    mock_torch.cuda.memory_allocated.side_effect = itertools.chain(
        [100 * MB, 100 * MB, 160 * MB],
        itertools.repeat(200 * MB),
    )

    with patch("src.server.broadcast_log_sync"):
        with patch.dict("sys.modules", {"torch": mock_torch}):
            with patch("src.utils.vram_monitor.set_pytorch_attribution"):
                with scoped_job_stdout(emitter):
                    with ModelLoadTracker("Florence-2", total_size_mb=100, poll_interval=0.005) as tracker:
                        assert tracker._emitter is emitter
                        assert polled_event.wait(timeout=1.0)

    assert len(intermediate_states) >= 1
    assert intermediate_states[0]["model"] == "Florence-2"
    assert intermediate_states[0]["progress"] == 60

    vstate = service._active_jobs["job-test-1"]["vramState"]
    assert vstate is not None
    assert vstate["model"] == "Florence-2"
    assert vstate["done"] is True
    assert vstate["progress"] == 100
