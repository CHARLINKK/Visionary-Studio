"""
Micro-retentativas contra bloqueios transitórios de arquivo no Windows.

No Windows, o antivírus (Windows Defender) e o indexador de busca travam arquivos
recém-escritos por alguns milissegundos com `[WinError 32]` ou `EBUSY`. Este módulo
absorve essas travas curtas antes que o pipeline interprete o arquivo como ausente.
"""
import errno
import json
import logging
import os
import time
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger("visionary.file_resilience")
T = TypeVar("T")

WINERROR_SHARING_VIOLATION = 32
WINERROR_LOCK_VIOLATION = 33
WINERROR_ACCESS_DENIED = 5

TRANSIENT_WINERRORS = {
    WINERROR_SHARING_VIOLATION,
    WINERROR_LOCK_VIOLATION,
    WINERROR_ACCESS_DENIED,
}


def is_transient_lock_error(exc: BaseException) -> bool:
    """Identifica bloqueios temporários de arquivo no Windows (antivírus, indexador, handle aberto)."""
    if isinstance(exc, FileNotFoundError):
        return False
    if isinstance(exc, (IsADirectoryError, NotADirectoryError)):
        return False

    winerror = getattr(exc, "winerror", None)
    if winerror in TRANSIENT_WINERRORS:
        return True

    err_no = getattr(exc, "errno", None)
    if err_no in (errno.EBUSY, errno.EACCES):
        return True

    # Restringe fallback textual a OSError/IOError para não confundir mensagens comuns de ValueError
    if isinstance(exc, (OSError, IOError)):
        err_str = str(exc)
        if (
            "[WinError 32]" in err_str
            or "EBUSY" in err_str
            or "[WinError 5]" in err_str
            or "[WinError 33]" in err_str
        ):
            return True

    return False


def retry_on_file_lock(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    initial_delay: float = 0.02,
    max_delay: float = 0.05,
    backoff_factor: float = 1.5,
    **kwargs: Any,
) -> T:
    """Executa `func` com backoff exponencial curto (20ms-50ms) se houver lock transitório."""
    delay = initial_delay
    last_exc: Optional[BaseException] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if not is_transient_lock_error(exc) or attempt == max_attempts:
                raise
            last_exc = exc
            logger.debug(
                "Transient file lock on attempt %d/%d (%s). Retrying in %.3fs...",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            time.sleep(delay)
            delay = min(delay * backoff_factor, max_delay)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry_on_file_lock completed without result or exception")


def to_extended_length_path(path: str) -> str:
    """
    Normaliza caminhos absolutos no Windows para a sintaxe estendida (\\\\?\\)
    quando o comprimento excede MAX_PATH (260 caracteres), prevenindo falhas de I/O.
    """
    if os.name != "nt" or not path or not isinstance(path, str):
        return path
    if path.startswith("\\\\?\\") or path.startswith("//?/"):
        return path
    try:
        norm = os.path.abspath(path)
        if len(norm) >= 240 and len(norm) >= 2 and norm[1] == ":" and norm[0].isalpha():
            return f"\\\\?\\{norm}"
    except Exception:
        pass
    return path


def resilient_read_bytes(
    filepath: str,
    max_attempts: int = 3,
    initial_delay: float = 0.02,
    max_delay: float = 0.05,
) -> bytes:
    """Lê bytes brutos do arquivo com micro-retentativas contra bloqueio no Windows."""
    target_path = to_extended_length_path(filepath)

    def _read() -> bytes:
        with open(target_path, "rb") as f:
            return f.read()

    return retry_on_file_lock(
        _read,
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
    )


def resilient_read_text(
    filepath: str,
    encoding: str = "utf-8",
    errors: str = "replace",
    max_attempts: int = 3,
    initial_delay: float = 0.02,
    max_delay: float = 0.05,
) -> str:
    """Lê texto do arquivo com micro-retentativas contra bloqueio no Windows."""
    target_path = to_extended_length_path(filepath)

    def _read() -> str:
        with open(target_path, "r", encoding=encoding, errors=errors) as f:
            return f.read()

    return retry_on_file_lock(
        _read,
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
    )


_DEFAULT_NOT_SET = object()


def resilient_read_json(
    filepath: str,
    default: Any = _DEFAULT_NOT_SET,
    encoding: str = "utf-8",
    max_attempts: int = 3,
    initial_delay: float = 0.02,
    max_delay: float = 0.05,
) -> Any:
    """Lê e interpreta um JSON com micro-retentativas contra bloqueio; propaga lock persistente em vez de mascarar com `default`."""
    target_path = to_extended_length_path(filepath) if filepath else filepath
    if not target_path or not os.path.exists(target_path):
        return None if default is _DEFAULT_NOT_SET else default

    def _read() -> Any:
        with open(target_path, "r", encoding=encoding) as f:
            return json.load(f)

    try:
        return retry_on_file_lock(
            _read,
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
        )
    except Exception as exc:
        if default is not _DEFAULT_NOT_SET and not is_transient_lock_error(exc):
            return default
        raise


def cleanup_orphaned_tmp_files(directory: str, max_age_seconds: float = 300.0) -> int:
    """
    Remove arquivos `.tmp` órfãos deixados por quedas abruptas após `max_age_seconds`
    de inatividade, garantindo que nunca apague um arquivo em escrita ativa.
    """
    if not directory or not os.path.isdir(directory):
        return 0

    removed = 0
    now = time.time()
    try:
        for entry in os.scandir(directory):
            try:
                if entry.is_file() and entry.name.endswith(".tmp"):
                    st = entry.stat()
                    if (now - st.st_mtime) >= max_age_seconds:
                        try:
                            os.remove(entry.path)
                            removed += 1
                        except OSError:
                            pass
            except OSError:
                continue
    except OSError:
        pass

    return removed
