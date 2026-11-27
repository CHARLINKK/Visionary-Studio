import os
import sys
import threading
from typing import Dict, List, Optional
from src.utils.gpu_utils import cleanup_gpu_memory
from src.utils.json_utils import atomic_write_text


class BatchPipelineSession:
    """
    Controlador encapsulado de sessão transacional do pipeline de processamento em lote.
    Garante isolamento de cancelamento cooperativo, backups em memória para rollback atômico e
    serialização de execuções via lock reentrante.
    """

    def __init__(self):
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.rollback_flag = False
        self.backups: Dict[str, Optional[str]] = {}
        self.outputs: List[str] = []

    def request_cancel(self, rollback: bool = False) -> None:
        """Sinaliza interrupção imediata cooperativa e limpa recursos de GPU."""
        self.rollback_flag = rollback
        self.cancel_event.set()
        if self is _canonical_session:
            rb_mod = sys.modules.get("src.run_batch")
            if rb_mod:
                rb_mod._rollback_flag = rollback
        cleanup_gpu_memory(unload_ollama=True)

    def backup_file(self, path: str) -> None:
        """Registra uma cópia em memória do arquivo antes de qualquer modificação para rollback."""
        from src.utils.file_resilience import resilient_read_text
        rb_mod = sys.modules.get("src.run_batch")
        rb_backups = getattr(rb_mod, "_session_backups", None) if rb_mod else None
        if self is _canonical_session and rb_backups is not None and isinstance(rb_backups, dict) and rb_backups is not self.backups:
            self.backups = rb_backups

        if path not in self.backups:
            if os.path.exists(path):
                try:
                    content = resilient_read_text(path, encoding="utf-8", errors="strict")
                    self.backups[path] = content
                    if self is _canonical_session and rb_backups is not None and rb_backups is not self.backups:
                        rb_backups[path] = content
                except Exception as e:
                    print(f"[SessionBackup] Aviso: falha ao ler backup de '{path}' ({e}). Preservando arquivo no disco em caso de rollback.")
            else:
                self.backups[path] = None
                if self is _canonical_session and rb_backups is not None and rb_backups is not self.backups:
                    rb_backups[path] = None

    def execute_rollback(self) -> None:
        """Restaura todos os arquivos modificados durante a sessão ao seu estado original."""
        rb_mod = sys.modules.get("src.run_batch")
        flag = getattr(rb_mod, "_rollback_flag", self.rollback_flag) if (rb_mod and self is _canonical_session) else self.rollback_flag
        if not flag:
            return

        rb_backups = getattr(rb_mod, "_session_backups", None) if (rb_mod and self is _canonical_session) else None
        target_backups = rb_backups if (rb_backups is not None and isinstance(rb_backups, dict)) else self.backups

        for path, content in list(target_backups.items()):
            if content is None:
                if os.path.exists(path):
                    try:
                        from src.utils.file_resilience import retry_on_file_lock
                        retry_on_file_lock(os.remove, path)
                    except Exception as e:
                        print(f"[ExecuteRollback] Aviso: não foi possível remover arquivo criado na sessão '{path}': {e}")
            elif isinstance(content, str):
                try:
                    atomic_write_text(path, content)
                except Exception as e:
                    print(f"[ExecuteRollback] Aviso: não foi possível restaurar arquivo de backup '{path}': {e}")

        target_backups.clear()
        self.backups.clear()
        if rb_backups is not None and rb_backups is not self.backups:
            rb_backups.clear()

        try:
            from src.domain.page_store import PageStore
            PageStore.invalidate_cache()
        except Exception:
            pass

    def reset(self) -> None:
        """Reinicializa as flags e estruturas transacionais para uma nova execução."""
        self.cancel_event.clear()
        self.rollback_flag = False
        self.backups.clear()
        self.outputs.clear()
        if self is _canonical_session:
            rb_mod = sys.modules.get("src.run_batch")
            if rb_mod:
                rb_mod._rollback_flag = False
                if hasattr(rb_mod, "_session_backups") and isinstance(rb_mod._session_backups, dict):
                    rb_mod._session_backups.clear()
                if hasattr(rb_mod, "_session_outputs") and isinstance(rb_mod._session_outputs, list):
                    rb_mod._session_outputs.clear()


import contextvars
from contextlib import contextmanager

# ContextVar para isolamento concorrente e multitarefa de sessões
_session_context: contextvars.ContextVar[Optional[BatchPipelineSession]] = contextvars.ContextVar(
    "_session_context", default=None
)

# Instância canônica ativa de sessão (fallback global para retrocompatibilidade)
_canonical_session = BatchPipelineSession()
_current_session = _canonical_session


def get_current_session() -> BatchPipelineSession:
    """Retorna a instância gerenciada da sessão ativa no contexto da tarefa/thread, ou a canônica global."""
    ctx_sess = _session_context.get()
    if ctx_sess is not None:
        return ctx_sess
    return _canonical_session


@contextmanager
def scoped_session(session: Optional[BatchPipelineSession] = None):
    """
    Context manager transacional que ativa uma sessão isolada para o contexto atual.
    Garante que tarefas concorrentes ou isoladas tenham seus próprios eventos de cancelamento,
    backups em memória e rollback atômico, sem interferência no estado global.
    """
    if session is None:
        session = BatchPipelineSession()
    token = _session_context.set(session)
    try:
        yield session
    finally:
        _session_context.reset(token)


class SessionEventProxy(threading.Event):
    """
    Proxy dinâmico para threading.Event vinculado à sessão ativa via ContextVar.
    Permite que qualquer código ou teste preexistente que acesse `_cancel_event`
    opere de forma transparente na sessão isolada do contexto atual.
    """

    def is_set(self) -> bool:
        return get_current_session().cancel_event.is_set()

    def set(self) -> None:
        get_current_session().cancel_event.set()

    def clear(self) -> None:
        get_current_session().cancel_event.clear()

    def wait(self, timeout: Optional[float] = None) -> bool:
        return get_current_session().cancel_event.wait(timeout)

    def isSet(self) -> bool:
        return self.is_set()


# ── Pontes de compatibilidade para código e testes preexistentes ──
_cancel_event = SessionEventProxy()
_rollback_flag = _canonical_session.rollback_flag
_session_backups = _canonical_session.backups
_session_outputs = _canonical_session.outputs
_pipeline_lock = _canonical_session.lock


def request_cancel(rollback: bool = False, session: Optional[BatchPipelineSession] = None) -> None:
    target = session or get_current_session()
    target.request_cancel(rollback=rollback)


def backup_file(path: str, session: Optional[BatchPipelineSession] = None) -> None:
    target = session or get_current_session()
    target.backup_file(path)


def execute_rollback(session: Optional[BatchPipelineSession] = None) -> None:
    target = session or get_current_session()
    target.execute_rollback()


def reset_session(session: Optional[BatchPipelineSession] = None) -> None:
    target = session or get_current_session()
    target.reset()
