import io
import sys
import re
import json
import datetime
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, List


class PipelineEmitter:
    """
    Emissor estruturado de eventos de progresso, status e logs para jobs do pipeline.
    Substitui a raspagem frágil de strings mágicas no sys.stdout global por eventos tipados.
    """
    def __init__(self, job_id: str, service=None):
        self.job_id = job_id
        self.service = service
        self._flush_lock = threading.Lock()
        self._buffer: List[Dict[str, Any]] = []

    def emit_progress(self, progress: Optional[float] = None, step_label: Optional[str] = None) -> None:
        """Atualiza o progresso numérico (0-100) e/ou o rótulo da etapa no backend e no WebSocket."""
        if self.service:
            with self.service._jobs_lock:
                if self.job_id in self.service._active_jobs:
                    if progress is not None and progress >= 0:
                        self.service._active_jobs[self.job_id]["progress"] = round(min(100.0, max(0.0, float(progress))), 1)
                    if step_label:
                        self.service._active_jobs[self.job_id]["step_label"] = step_label

        try:
            from src.server import broadcast_log_sync
            extra = {"job_id": self.job_id}
            if step_label:
                extra["step_label"] = step_label
            broadcast_log_sync(
                "job_progress",
                "",
                progress=round(min(100.0, max(0.0, float(progress))), 1) if progress is not None else -1.0,
                extra=extra
            )
        except Exception:
            pass

    def emit_step(self, step_name: str, step_label: str) -> None:
        """
        Notifica uma mudança de etapa (ex: OCR, Layout, Tradução) e dispara refresh no X-Ray
        de forma tipada, sem depender de parsing de texto bruto.
        """
        self.emit_progress(progress=None, step_label=step_label)
        try:
            from src.utils.event_bus import event_bus
            event_bus.publish('visionary:xray-refresh')
        except Exception:
            pass

    def emit_vram_state(self, vram_state: Dict[str, Any]) -> None:
        """Atualiza o progresso de carregamento de modelo VRAM diretamente via WebSocket/Store."""
        if not vram_state or not self.service:
            return
        with self.service._jobs_lock:
            if self.job_id in self.service._active_jobs:
                self.service._active_jobs[self.job_id]["vramState"] = vram_state

        try:
            from src.server import broadcast_log_sync
            broadcast_log_sync("job_status", "", extra={"job_id": self.job_id, "updates": {"vramState": vram_state}})
        except Exception:
            pass

    def emit_vram_realtime(self, vram_realtime: Dict[str, Any]) -> None:
        """Atualiza o consumo de VRAM em tempo real."""
        if not vram_realtime or not self.service:
            return
        with self.service._jobs_lock:
            if self.job_id in self.service._active_jobs:
                self.service._active_jobs[self.job_id]["vramRealtime"] = vram_realtime

        try:
            from src.server import broadcast_log_sync
            broadcast_log_sync("job_status", "", extra={"job_id": self.job_id, "updates": {"vramRealtime": vram_realtime}})
        except Exception:
            pass

    def emit_log(self, text: str, is_replace: bool = False, replace_prefix: Optional[str] = None) -> None:
        """Registra uma linha de log no job e transmite para o WebSocket da interface."""
        if text is None:
            return
        clean_text = str(text).strip()
        if not clean_text:
            return

        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        final_line_no_prefix = f"[{now_str}] {clean_text}"
        final_line_with_prefix = f"[{now_str}] {clean_text}"

        with self._flush_lock:
            self._buffer.append({
                "with_prefix": final_line_with_prefix,
                "no_prefix": final_line_no_prefix,
                "is_replace": is_replace,
                "replace_prefix": replace_prefix
            })
            self._flush_buffer_unlocked()

    def _flush_buffer_unlocked(self) -> None:
        if not self._buffer or not self.service:
            return
        items = list(self._buffer)
        self._buffer.clear()

        logs_for_js = []
        with self.service._jobs_lock:
            for item in items:
                logs_for_js.append(item["with_prefix"])
                if self.job_id in self.service._active_jobs:
                    master_logs = self.service._active_jobs[self.job_id]["logs"]
                    if item["is_replace"] and item["replace_prefix"]:
                        found = False
                        for i in range(len(master_logs) - 1, max(-1, len(master_logs) - 30), -1):
                            if item["replace_prefix"] in master_logs[i]:
                                master_logs[i] = item["no_prefix"]
                                found = True
                                break
                        if not found:
                            master_logs.append(item["no_prefix"])
                    else:
                        master_logs.append(item["no_prefix"])

                    # Proteção contra vazamento de memória: retém no máximo as últimas 2000 linhas
                    if len(master_logs) > 2000:
                        del master_logs[:len(master_logs) - 2000]

        try:
            from src.server import broadcast_log_sync
            broadcast_log_sync("job_log", "", extra={"job_id": self.job_id, "logs": logs_for_js})
        except Exception:
            pass


class ThreadScopedStdout:
    """
    Proxy de stdout thread-safe que direciona saídas impressas apenas da thread
    ativa do job para o seu respectivo PipelineEmitter.
    Todas as outras threads do processo continuam escrevendo diretamente no stdout original,
    eliminando a contaminação cruzada de logs e parsing frágil de strings.
    """
    _instance: Optional["ThreadScopedStdout"] = None
    _lock = threading.Lock()

    def __init__(self, original_stdout):
        self.original = original_stdout
        self._thread_emitters: Dict[int, PipelineEmitter] = {}
        self._thread_lock = threading.Lock()

    @classmethod
    def get_or_install(cls) -> "ThreadScopedStdout":
        with cls._lock:
            if not isinstance(sys.stdout, cls):
                proxy = cls(sys.stdout)
                sys.stdout = proxy
            return sys.stdout

    def register_thread(self, thread_id: int, emitter: PipelineEmitter) -> None:
        with self._thread_lock:
            self._thread_emitters[thread_id] = emitter

    def get_emitter_for_thread(self, thread_id: int) -> Optional[PipelineEmitter]:
        with self._thread_lock:
            return self._thread_emitters.get(thread_id)

    def unregister_thread(self, thread_id: int) -> None:
        with self._thread_lock:
            self._thread_emitters.pop(thread_id, None)
            if not self._thread_emitters:
                self.uninstall()

    def uninstall(self) -> None:
        with self._lock:
            if sys.stdout is self:
                sys.stdout = self.original

    def write(self, text: Any) -> None:
        if text is None:
            return
        if not isinstance(text, str):
            text = str(text)

        # Suprime eco bruto de tags internas de telemetria no console
        is_internal_telemetry = (
            "[VRAM_REALTIME:" in text or
            "[VRAM_PROGRESS:" in text or
            "[PROGRESS:" in text
        )

        # 1. Escreve no stdout original do console se não for tag de telemetria interna
        if not is_internal_telemetry:
            try:
                self.original.write(text)
            except UnicodeEncodeError:
                enc = getattr(self.original, 'encoding', None) or 'utf-8'
                try:
                    self.original.write(text.encode(enc, errors='replace').decode(enc))
                except Exception:
                    pass
            except Exception:
                pass

        # 2. Isolamento de thread: verifica se a thread atual pertence a um job registrado
        tid = threading.get_ident()
        with self._thread_lock:
            emitter = self._thread_emitters.get(tid)

        # Se for uma thread externa (FastAPI, VRAM loop, watchdog), NÃO intercepta nem contamina logs!
        if emitter is None:
            return

        clean = text.strip()
        if not clean:
            return

        # Compatibilidade com tags legadas caso bibliotecas antigas ainda façam print
        if "[PROGRESS:" in text:
            m = re.search(r'\[PROGRESS:(\d+)\]', text)
            if m:
                emitter.emit_progress(int(m.group(1)))
            return

        if "[VRAM_PROGRESS:" in text:
            m_vram = re.search(r'\[VRAM_PROGRESS:\s*([^:]+):\s*([0-9.]+|DONE)\s*/\s*([0-9.]+|DONE).*\]', text)
            if m_vram:
                model_name = m_vram.group(1).strip()
                raw_loaded = m_vram.group(2)
                raw_total = m_vram.group(3)
                if raw_loaded == "DONE":
                    vstate = {"model": model_name, "loaded": 1, "total": 1, "progress": 100, "done": True}
                else:
                    try:
                        l = float(raw_loaded)
                        t = float(raw_total)
                        pct = min(100, max(0, int((l / t) * 100))) if t > 0 else 0
                        vstate = {"model": model_name, "loaded": l, "total": t, "progress": pct, "done": False}
                    except Exception:
                        vstate = None
                if vstate:
                    emitter.emit_vram_state(vstate)
            return

        if "[VRAM_REALTIME:" in text:
            try:
                s = text.index("[VRAM_REALTIME:") + len("[VRAM_REALTIME:")
                e = text.rindex("]")
                vram_rt = json.loads(text[s:e])
                emitter.emit_vram_realtime(vram_rt)
            except Exception:
                pass
            return

        # Identificação de etapas legadas
        if "[OCR]" in clean or "Extraindo textos" in clean:
            emitter.emit_step("OCR", "Extraindo Textos (OCR)...")
        elif "[LAYOUT]" in clean or "detectando bal" in clean or "Mapeando" in clean:
            emitter.emit_step("LAYOUT", "Mapeando Layout (YOLO)...")
        elif "Cascade Validator" in clean or "Florence-2" in clean or "VALIDAÇÃO" in clean:
            emitter.emit_step("VALIDAÇÃO", "Validação Profunda...")
        elif "[TRADUÇÃO]" in clean or "Traduzindo" in clean:
            emitter.emit_step("TRADUÇÃO", "Traduzindo...")
        elif "[LIMPEZA]" in clean or "Limpando" in clean:
            emitter.emit_step("LIMPEZA", "Limpando Textos...")

        # Substituição de linha (prefixo dinâmico de log)
        m_rep = re.search(r'\[REPLACE_LAST_LOG_PREFIX:(.+?)\]', clean)
        if m_rep:
            is_replace = True
            replace_prefix = m_rep.group(1)
            clean_text_no_prefix = clean.replace(m_rep.group(0), "").strip()
        else:
            is_replace = False
            replace_prefix = None
            clean_text_no_prefix = clean

        emitter.emit_log(clean_text_no_prefix, is_replace=is_replace, replace_prefix=replace_prefix)

    def flush(self) -> None:
        try:
            if hasattr(self.original, 'flush'):
                self.original.flush()
        except Exception:
            pass

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def isatty(self) -> bool:
        try:
            return bool(self.original.isatty())
        except Exception:
            return False

    def fileno(self) -> int:
        try:
            return self.original.fileno()
        except Exception:
            raise io.UnsupportedOperation("fileno not supported on stdout proxy")

    def readable(self) -> bool:
        return getattr(self.original, "readable", lambda: False)()

    def writable(self) -> bool:
        return getattr(self.original, "writable", lambda: True)()

    def seekable(self) -> bool:
        return getattr(self.original, "seekable", lambda: False)()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.original, name)


def get_current_thread_emitter() -> Optional[PipelineEmitter]:
    """Retorna o PipelineEmitter associado à thread atual, se houver um job ativo em escopo."""
    stdout_obj = sys.stdout
    if isinstance(stdout_obj, ThreadScopedStdout):
        return stdout_obj.get_emitter_for_thread(threading.get_ident())
    return None


@contextmanager
def scoped_job_stdout(emitter: PipelineEmitter):
    """
    Context manager seguro que associa a thread atual ao PipelineEmitter.
    Garante limpeza no finally e zero contaminação de stdout global.
    """
    proxy = ThreadScopedStdout.get_or_install()
    tid = threading.get_ident()
    proxy.register_thread(tid, emitter)
    try:
        yield emitter
    finally:
        proxy.unregister_thread(tid)
