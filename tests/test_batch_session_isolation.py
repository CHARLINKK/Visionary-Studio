import os
import threading
import time
import pytest
from src.batch_pipeline.session import (
    BatchPipelineSession,
    scoped_session,
    get_current_session,
    _canonical_session,
    _cancel_event,
    request_cancel,
    backup_file,
    execute_rollback,
    reset_session,
)


def test_session_instances_are_isolated():
    """Valida que instâncias independentes de BatchPipelineSession possuem estados desacoplados."""
    sess1 = BatchPipelineSession()
    sess2 = BatchPipelineSession()

    assert not sess1.cancel_event.is_set()
    assert not sess2.cancel_event.is_set()

    sess1.request_cancel(rollback=True)
    assert sess1.cancel_event.is_set()
    assert sess1.rollback_flag is True
    assert not sess2.cancel_event.is_set()
    assert sess2.rollback_flag is False

    sess1.reset()
    assert not sess1.cancel_event.is_set()
    assert sess1.rollback_flag is False


def test_scoped_session_context_isolation():
    """Valida que o context manager scoped_session altera get_current_session() e _cancel_event dinamicamente."""
    sess_custom = BatchPipelineSession()

    # Fora do escopo: retorna a canônica global
    assert get_current_session() is _canonical_session
    _canonical_session.reset()
    assert not _cancel_event.is_set()

    with scoped_session(sess_custom):
        assert get_current_session() is sess_custom
        assert not _cancel_event.is_set()

        # Aciona o cancelamento pelo proxy legado
        _cancel_event.set()
        assert sess_custom.cancel_event.is_set()
        assert not _canonical_session.cancel_event.is_set()

    # Ao sair do escopo: restaura a sessão canônica intacta
    assert get_current_session() is _canonical_session
    assert not _canonical_session.cancel_event.is_set()
    assert not _cancel_event.is_set()


def test_parallel_threads_session_isolation():
    """Valida que duas threads com scoped_session distintos não compartilham estado de cancelamento."""
    sess_a = BatchPipelineSession()
    sess_b = BatchPipelineSession()

    results = {}

    def thread_a_worker():
        with scoped_session(sess_a):
            # Thread A aguarda sinal
            time.sleep(0.05)
            # Aciona cancelamento na sessão A
            request_cancel(rollback=False)
            results["thread_a_cancelled"] = _cancel_event.is_set()

    def thread_b_worker():
        with scoped_session(sess_b):
            # Thread B dorme um pouco para deixar Thread A cancelar sua própria sessão
            time.sleep(0.15)
            results["thread_b_cancelled"] = _cancel_event.is_set()

    t_a = threading.Thread(target=thread_a_worker)
    t_b = threading.Thread(target=thread_b_worker)

    t_a.start()
    t_b.start()
    t_a.join()
    t_b.join()

    assert results.get("thread_a_cancelled") is True
    assert results.get("thread_b_cancelled") is False
    assert not _canonical_session.cancel_event.is_set()


def test_session_backup_and_rollback_isolation(tmp_path):
    """Valida que o backup e rollback em sessões isoladas não poluem outras sessões."""
    file_a = tmp_path / "page_a.txt"
    file_b = tmp_path / "page_b.txt"

    file_a.write_text("conteúdo original A", encoding="utf-8")
    file_b.write_text("conteúdo original B", encoding="utf-8")

    sess_a = BatchPipelineSession()
    sess_b = BatchPipelineSession()

    with scoped_session(sess_a):
        backup_file(str(file_a))
        file_a.write_text("conteúdo modificado A", encoding="utf-8")

    with scoped_session(sess_b):
        backup_file(str(file_b))
        file_b.write_text("conteúdo modificado B", encoding="utf-8")

    # Apenas a sessão A executa rollback
    with scoped_session(sess_a):
        sess_a.rollback_flag = True
        execute_rollback()

    assert file_a.read_text(encoding="utf-8") == "conteúdo original A"
    # Sessão B não sofreu rollback
    assert file_b.read_text(encoding="utf-8") == "conteúdo modificado B"
