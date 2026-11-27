"""
Rastreador de Fluxo (DownloadStreamTracker) e Ganchos Isolados de Progresso (tqdm / http_get)
para downloads concorrentes do Hugging Face Hub.
"""

import os
import time
import inspect
import threading
import contextlib
from collections import deque
from urllib.parse import urlparse


def _should_trust_env_proxies() -> bool:
    for env_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        if os.environ.get(env_key):
            return True
    return False


class DownloadStreamTracker:
    """
    Rastreador determinístico de progresso por arquivo (ledger) compartilhado entre workers de download.

    ARQUITETURA DE ACURÁCIA DE PORCENTAGEM:
    1. Contabilidade Determinística por Arquivo (`file_progress` / `file_totals`):
       Em vez de somar `+= n` cegamente num acumulador global (que infla a % em retries, fallbacks ou
       resumes duplicados), cada arquivo tem sua posição absoluta limitada a `[0, file_total]`.
       `downloaded_bytes = base_completed_bytes + sum(file_progress.values()) + unkeyed_bytes`.
    2. Prevenção de Dupla Contagem com Manifesto Prévio:
       Se um arquivo já contabilizado em `base_completed_bytes` precisar ser rebaixado (ex: hash divergente),
       seu tamanho prévio é automaticamente descontado uma única vez antes de contabilizar o novo stream.
    3. Compatibilidade Total:
       Mantém `record_chunk_locked(n, now)` e métricas de janela deslizante para retrocompatibilidade com testes.
    """

    def __init__(
        self,
        key: str,
        target_total_bytes: int = 0,
        initial_bytes: int = 0,
        manifest_files: dict = None,
    ):
        self.key = key
        # Lock de proteção: múltiplos chunks de threads paralelas Range atualizam este objeto simultaneamente
        self.lock = threading.Lock()
        self.target_total = max(0, int(target_total_bytes or 0))
        self.base_completed_bytes = max(0, int(initial_bytes or 0))
        self.downloaded_bytes = self.base_completed_bytes
        self.unkeyed_bytes = 0
        self.last_bytes = self.downloaded_bytes
        now = time.time()
        self.last_speed_time = now
        self.last_active_time = now
        self._first_byte_time = None
        self.speed_samples = deque()
        self._last_sample_push = now
        self.speed_mbps = 0.0
        self.peak_speed_mbps = 0.0
        self.eta_seconds = 0
        self.registered_initials = set()

        # Ledger determinístico por arquivo
        self.file_totals: dict[str, int] = {}
        self.file_progress: dict[str, int] = {}
        self._completed_manifest_pre: dict[str, int] = {}
        self.expected_filenames: set[str] = set()
        self.expected_local_dirs: set[str] = set()

        if isinstance(manifest_files, dict):
            for rfn, meta in manifest_files.items():
                if not rfn or not isinstance(meta, dict):
                    continue
                norm_key = self.normalize_file_key(rfn)
                sz = max(0, int(meta.get("size", 0) or 0))
                if sz > 0:
                    self.file_totals[norm_key] = sz
                self.expected_filenames.add(norm_key)
                self.expected_filenames.add(rfn.lower())
                lp = meta.get("local_path") or ""
                if lp:
                    import os
                    self.expected_local_dirs.add(os.path.normcase(os.path.dirname(os.path.abspath(lp))))
                if meta.get("completed") and int(meta.get("pre_bytes", 0) or 0) > 0:
                    self._completed_manifest_pre[norm_key] = int(meta["pre_bytes"])

    @staticmethod
    def normalize_file_key(raw_name: str) -> str:
        """Normaliza desc/filename para chave estável de arquivo (basename em minúsculas)."""
        if not raw_name:
            return ""
        clean = str(raw_name).strip().replace("\\", "/")
        if "/" in clean:
            clean = clean.rsplit("/", 1)[-1]
        return clean.strip().lower()

    def _recompute_downloaded_locked(self) -> int:
        total_dl = self.base_completed_bytes + sum(self.file_progress.values()) + self.unkeyed_bytes
        if self.target_total > 0:
            # Se temos totais individuais que superam uma estimativa desatualizada, ajusta o teto
            known_files_sum = self.base_completed_bytes + sum(
                max(self.file_totals.get(fk, 0), fv) for fk, fv in self.file_progress.items()
            )
            if known_files_sum > self.target_total:
                self.target_total = known_files_sum
            total_dl = min(total_dl, self.target_total)
        self.downloaded_bytes = max(0, int(total_dl))
        return self.downloaded_bytes

    def _update_rate_metrics_locked(self, delta_n: int, now: float, prev_bytes: int) -> None:
        self.last_active_time = now
        if self._first_byte_time is None and delta_n > 0:
            self._first_byte_time = now
            self.last_speed_time = now
            self.last_bytes = prev_bytes
            self.speed_samples.clear()
            self.speed_samples.append((now, prev_bytes))
            self._last_sample_push = now

        if (now - self._last_sample_push) >= 0.05 or len(self.speed_samples) < 2:
            self.speed_samples.append((now, self.downloaded_bytes))
            self._last_sample_push = now
        else:
            self.speed_samples[-1] = (now, self.downloaded_bytes)

        while len(self.speed_samples) > 2 and (now - self.speed_samples[0][0]) > 3.0:
            self.speed_samples.popleft()

        dt = now - self.last_speed_time
        if dt >= 0.1 and len(self.speed_samples) >= 2:
            win_dt = now - self.speed_samples[0][0]
            win_delta = self.downloaded_bytes - self.speed_samples[0][1]
            if win_dt > 0.02 and win_delta >= 0:
                window_spd = (win_delta / (1024 * 1024)) / win_dt
            else:
                delta = self.downloaded_bytes - self.last_bytes
                window_spd = (delta / (1024 * 1024)) / dt if dt > 0 else 0.0

            if self.speed_mbps > 0.0:
                alpha = 0.75 if window_spd > self.speed_mbps * 1.25 else 0.45
                self.speed_mbps = round(alpha * window_spd + (1.0 - alpha) * self.speed_mbps, 1)
            else:
                self.speed_mbps = round(window_spd, 1)

            if self.speed_mbps > self.peak_speed_mbps:
                self.peak_speed_mbps = self.speed_mbps

            self.last_speed_time = now
            self.last_bytes = self.downloaded_bytes

            active_elapsed = (now - self._first_byte_time) if self._first_byte_time is not None else 0.0
            if self.target_total > self.downloaded_bytes and active_elapsed >= 0.35:
                rem = self.target_total - self.downloaded_bytes
                calc_spd = (
                    max(self.speed_mbps, 0.45 * self.peak_speed_mbps)
                    if self.peak_speed_mbps > 1.0
                    else self.speed_mbps
                )
                if calc_spd > 0.1 and rem > 0:
                    raw_eta = int(rem / (calc_spd * 1024 * 1024))
                    if self.eta_seconds > 0:
                        eta_alpha = 0.65 if raw_eta < self.eta_seconds else 0.35
                        self.eta_seconds = int(eta_alpha * raw_eta + (1.0 - eta_alpha) * self.eta_seconds)
                    else:
                        self.eta_seconds = raw_eta
                else:
                    self.eta_seconds = 0
            else:
                self.eta_seconds = 0

    def register_file_initial_locked(self, file_id: str, initial_n: int, file_total: int, now: float) -> None:
        """
        Registra o estado inicial (resume) de um arquivo no ledger sem dupla contagem.
        ATENÇÃO: Requer que o chamador já esteja segurando 'self.lock'.
        """
        fkey = self.normalize_file_key(file_id) or file_id
        # Se este arquivo constava como pré-completo no manifesto mas o HF decidiu rebaixá-lo,
        # desconta da base uma única vez para não somar duas vezes.
        if fkey in self._completed_manifest_pre:
            pre_sz = self._completed_manifest_pre.pop(fkey)
            self.base_completed_bytes = max(0, self.base_completed_bytes - pre_sz)

        if file_total > 0:
            self.file_totals[fkey] = max(self.file_totals.get(fkey, 0), int(file_total))
        cap = self.file_totals.get(fkey, 0)
        clamped_init = max(0, int(initial_n or 0))
        if cap > 0:
            clamped_init = min(clamped_init, cap)
        # Mantém o maior progresso já observado (sem somar de novo se a barra reabrir!)
        self.file_progress[fkey] = max(self.file_progress.get(fkey, 0), clamped_init)
        self.registered_initials.add(fkey)
        self._recompute_downloaded_locked()
        self.last_bytes = self.downloaded_bytes
        self.speed_samples.clear()
        self.speed_samples.append((now, self.downloaded_bytes))
        self._last_sample_push = now

    def set_file_progress_locked(self, file_id: str, abs_bytes: int, file_total: int, now: float) -> None:
        """
        Define a posição absoluta de bytes baixados de um arquivo específico no ledger.
        Imune a dupla contagem em retries, fallbacks ou múltiplos updates repetidos.
        ATENÇÃO: Requer que o chamador já esteja segurando 'self.lock'.
        """
        fkey = self.normalize_file_key(file_id) or file_id
        if fkey in self._completed_manifest_pre:
            pre_sz = self._completed_manifest_pre.pop(fkey)
            self.base_completed_bytes = max(0, self.base_completed_bytes - pre_sz)

        if file_total > 0:
            self.file_totals[fkey] = max(self.file_totals.get(fkey, 0), int(file_total))
        cap = self.file_totals.get(fkey, 0)
        clamped = max(0, int(abs_bytes or 0))
        if cap > 0:
            clamped = min(clamped, cap)

        prev_total = self.downloaded_bytes
        # Em caso de retry onde o arquivo recomeça do zero, mantém o pico já validado
        # até a nova tentativa ultrapassar o ponto anterior (evita regressão visual E evita dupla soma).
        self.file_progress[fkey] = max(self.file_progress.get(fkey, 0), clamped)
        new_total = self._recompute_downloaded_locked()
        delta_n = max(0, new_total - prev_total)
        self._update_rate_metrics_locked(delta_n, now, prev_total)

    def record_chunk_locked(self, n: int, now: float) -> None:
        """
        Atualiza bytes acumulados sem chave de arquivo (modo legado / single-file).
        ATENÇÃO: Requer que o chamador já esteja segurando 'self.lock'.
        """
        prev_bytes = self.downloaded_bytes
        inc = max(0, int(n or 0))
        self.unkeyed_bytes += inc
        self._recompute_downloaded_locked()
        self._update_rate_metrics_locked(inc, now, prev_bytes)


def build_scoped_tqdm_class(
    manager,
    key: str,
    total_expected_bytes: int = 0,
    base_pct: float = 0.0,
    weight_pct: float = 100.0,
    tracker: DownloadStreamTracker = None,
):
    """
    Cria uma subclasse dinâmica de tqdm isolada por modelo para o huggingface_hub.
    
    POR QUE USAR UMA SUBCLASSE DINÂMICA:
    O SDK do Hugging Face dispara instâncias internas de tqdm para imprimir na tela (sys.stderr).
    Subclassificando o tqdm base:
    1. Interceptamos o método 'update(n)' onde 'n' é o número de bytes do chunk HTTP que acabou de chegar.
    2. Suportamos cancelamento em tempo real: Se o usuário clicou em 'Cancelar' na interface,
       detectamos 'cancel_ev.is_set()' e levantamos 'InterruptedError', abortando o socket TCP imediatamente.
    3. Ignoramos contadores de arquivos: Algumas chamadas internas do HF usam tqdm para contar '1 de 5 arquivos'.
       Filtramos esses contadores para que a barra mostre apenas o progresso em BYTES, sem saltos estranhos.
    """
    try:
        from tqdm.auto import tqdm as base_tqdm

        if tracker is None:
            est = total_expected_bytes
            if est <= 0 and hasattr(manager, "download_status") and key in manager.download_status:
                est = manager.download_status[key].get("total_bytes", 0)
            stream_tracker = DownloadStreamTracker(key, target_total_bytes=est)
        else:
            stream_tracker = tracker

        class _ScopedHFTqdm(base_tqdm):
            def __init__(self, *args, **kwargs):
                init_arg = int(kwargs.get("initial", 0) or 0)
                if "disable" in kwargs:
                    kwargs["disable"] = False
                super().__init__(*args, **kwargs)
                self.disable = False
                self._file_id = (getattr(self, "desc", "") or "").strip() or f"scoped_{id(self)}"
                if hasattr(manager, "_last_stream_time"):
                    manager._last_stream_time[key] = time.time()
                unit = getattr(self, "unit", "")
                tot_val = int(getattr(self, "total", 0) or 0)
                is_byte_stream = unit == "B" or getattr(self, "unit_scale", False) or tot_val > 10000
                if is_byte_stream:
                    with stream_tracker.lock:
                        if stream_tracker.target_total <= 0 and tot_val > 0:
                            stream_tracker.target_total = tot_val
                        init_n = max(init_arg, int(getattr(self, "n", 0) or 0))
                        if init_n > 0:
                            stream_tracker.register_file_initial_locked(self._file_id, init_n, tot_val, time.time())

            def update(self, n=1):
                # Verificação atômica de cancelamento disparado pelo usuário
                cancel_ev = getattr(manager, "_cancel_events", {}).get(key)
                if cancel_ev and cancel_ev.is_set():
                    raise InterruptedError("Download cancelado pelo usuário.")
                res = super().update(n)
                try:
                    unit = getattr(self, "unit", "")
                    tot_bar = int(getattr(self, "total", 0) or 0)
                    # Ignora barras que contam número de arquivos em vez de volume de dados (bytes)
                    is_file_counter = tot_bar < 100 and unit != "B" and not getattr(self, "unit_scale", False)
                    if is_file_counter:
                        return res

                    with stream_tracker.lock:
                        now = time.time()
                        if hasattr(manager, "_last_stream_time"):
                            manager._last_stream_time[key] = now
                        cur_bar_n = int(getattr(self, "n", 0) or 0)
                        stream_tracker.set_file_progress_locked(self._file_id, cur_bar_n, tot_bar, now)

                        cur_dl = stream_tracker.downloaded_bytes
                        tot = max(stream_tracker.target_total, cur_dl)
                        pct = min(99.9, round((cur_dl / tot) * 100, 1)) if tot > 0 else 0.0

                        with manager._status_lock:
                            st = manager.download_status.get(key)
                            if st and st.get("status") == "downloading":
                                # Garante contagem monotônica (bytes baixados nunca diminuem)
                                monotonic_dl = max(int(st.get("downloaded_bytes", 0)), cur_dl)
                                tot = max(tot, monotonic_dl)
                                st["downloaded_bytes"] = monotonic_dl
                                st["total_bytes"] = tot
                                st["progress"] = max(st.get("progress", 0.0), pct)
                                is_done_dl = pct >= 99.0 and monotonic_dl >= tot
                                if is_done_dl:
                                    st["speed_mbps"] = 0.0
                                    st["eta_seconds"] = 0
                                    st["message"] = f"Finalizando instalação... ({tot / (1024 * 1024):.1f} MB)"
                                else:
                                    st["speed_mbps"] = stream_tracker.speed_mbps
                                    st["eta_seconds"] = stream_tracker.eta_seconds
                                    last_msg_t = getattr(stream_tracker, "_last_msg_format_t", 0.0)
                                    if (now - last_msg_t) >= 0.09 or not st.get("message"):
                                        stream_tracker._last_msg_format_t = now
                                        tot_mb = tot / (1024 * 1024)
                                        mb = monotonic_dl / (1024 * 1024)
                                        desc = getattr(self, "desc", "") or ""
                                        if desc and not desc.startswith("Fetching"):
                                            clean_desc = desc.split("/")[-1].strip()
                                            if len(clean_desc) > 22:
                                                clean_desc = clean_desc[:19] + "..."
                                            st["message"] = f"Baixando {clean_desc} ({mb:.1f}/{tot_mb:.1f} MB · {pct}%)"
                                        else:
                                            st["message"] = f"Baixando... ({mb:.1f}/{tot_mb:.1f} MB · {pct}%)"

                    # Throttle de 100ms para emissão de progresso via WebSocket/EventBus
                    manager._notify_progress(key, throttle_interval=0.1)
                except InterruptedError:
                    raise
                except Exception:
                    pass
                return res

        return _ScopedHFTqdm
    except Exception:
        return None


_patch_lock = threading.Lock()
_patch_refcount = 0
_orig_fd_tqdm = None
_orig_fd_hf_tqdm = None
_orig_fd_http_get = None
_orig_hf_tqdm = None
_orig_hf_utils_mod_tqdm = None
_orig_sd_hf_tqdm = None
_orig_sd_base_tqdm = None
_orig_chunk_size = 10 * 1024 * 1024

_active_stream_threads = {}
_active_stream_keys = {}
_registry_lock = threading.Lock()


def _get_active_stream_binding(desc: str = ""):
    """Retorna (manager, key, tracker) isolado para a thread/arquivo atual sem colisão entre modelos."""
    ident = threading.get_ident()
    with _registry_lock:
        if ident in _active_stream_threads:
            return _active_stream_threads[ident]
        if desc:
            clean_desc = desc.lower()
            norm_base = DownloadStreamTracker.normalize_file_key(desc)
            # 1. Correspondência determinística pelo manifesto exato de arquivos esperados e diretórios
            for _k, val in _active_stream_keys.items():
                trk = val[2]
                expected_fns = getattr(trk, "expected_filenames", None)
                if expected_fns and (norm_base in expected_fns or clean_desc in expected_fns):
                    return val
                expected_dirs = getattr(trk, "expected_local_dirs", None)
                if expected_dirs:
                    for exp_dir in expected_dirs:
                        if exp_dir and exp_dir in clean_desc:
                            return val
            # 2. Fallback por assinatura de modelo/repositório
            if "florence-2-large" in clean_desc and "florence2_large" in _active_stream_keys:
                return _active_stream_keys["florence2_large"]
            if "florence-2-base" in clean_desc and "florence2" in _active_stream_keys:
                return _active_stream_keys["florence2"]
            for k, val in _active_stream_keys.items():
                if k in clean_desc:
                    return val
                if k == "yolo_detector" and any(
                    w in clean_desc for w in ["best.pt", "comic", "bubble", "detector", "yolo", "manga-frame"]
                ):
                    return val
                if k in ("florence2", "florence2_large") and any(
                    w in clean_desc
                    for w in [
                        "florence",
                        "safetensors",
                        "config",
                        "vocab",
                        "tokenizer",
                        "generation_config",
                        "preprocessor",
                        "modeling",
                        "processing",
                        "merges",
                        "special_tokens",
                        "added_tokens",
                    ]
                ):
                    return val
        if len(_active_stream_keys) == 1:
            return next(iter(_active_stream_keys.values()))
    return None


class _GlobalStreamTqdm:
    """Implementação unificada e thread-safe de tqdm com ledger determinístico por arquivo."""

    def __init__(self, *args, **kwargs):
        init_arg = int(kwargs.get("initial", 0) or 0)
        if "disable" in kwargs:
            kwargs["disable"] = False
        super().__init__(*args, **kwargs)
        self.disable = False
        desc = getattr(self, "desc", "") or ""
        self._file_id = desc.strip() if desc.strip() else f"obj_{id(self)}"
        self._binding = _get_active_stream_binding(desc)
        if self._binding:
            mgr, k, trk = self._binding
            if hasattr(mgr, "_last_stream_time"):
                mgr._last_stream_time[k] = time.time()
            unit = getattr(self, "unit", "")
            tot_val = int(getattr(self, "total", 0) or 0)
            is_bytes = unit == "B" or getattr(self, "unit_scale", False) or tot_val > 10000
            if is_bytes:
                with trk.lock:
                    if trk.target_total <= 0 and tot_val > 0:
                        trk.target_total = tot_val
                    init_n = max(init_arg, int(getattr(self, "n", 0) or 0))
                    if init_n > 0 or tot_val > 0:
                        trk.register_file_initial_locked(self._file_id, init_n, tot_val, time.time())

    def update(self, n=1):
        res = super().update(n) if hasattr(super(), "update") else None
        try:
            if not getattr(self, "_binding", None):
                desc = getattr(self, "desc", "") or ""
                self._binding = _get_active_stream_binding(desc)
            if not getattr(self, "_binding", None):
                return res

            mgr, key, tracker = self._binding
            cancel_ev = getattr(mgr, "_cancel_events", {}).get(key)
            if cancel_ev and cancel_ev.is_set():
                raise InterruptedError("Download cancelado pelo usuário.")

            unit = getattr(self, "unit", "")
            tot = int(getattr(self, "total", 0) or 0)
            is_file_counter = tot < 100 and unit != "B" and not getattr(self, "unit_scale", False)
            if is_file_counter:
                if tot > 0 and tracker.downloaded_bytes == 0:
                    cur_f = min(int(getattr(self, "n", 0) or 0), int(tot))
                    with mgr._status_lock:
                        st = mgr.download_status.get(key)
                        if st and st.get("status") == "downloading":
                            st["message"] = f"Sincronizando · {cur_f}/{int(tot)} arq."
                    mgr._notify_progress(key, throttle_interval=0.1)
                return res

            with tracker.lock:
                now = time.time()
                if hasattr(mgr, "_last_stream_time"):
                    mgr._last_stream_time[key] = now
                cur_bar_n = int(getattr(self, "n", 0) or 0)
                file_id = getattr(self, "_file_id", "") or (getattr(self, "desc", "") or f"obj_{id(self)}")
                tracker.set_file_progress_locked(file_id, cur_bar_n, tot, now)

                cur_dl = tracker.downloaded_bytes
                total_sz = max(tracker.target_total, cur_dl)
                pct = min(99.0, round((cur_dl / total_sz) * 100, 1)) if total_sz > 0 else 0.0

                with mgr._status_lock:
                    st = mgr.download_status.get(key)
                    if st and st.get("status") == "downloading":
                        monotonic_dl = max(int(st.get("downloaded_bytes", 0)), cur_dl)
                        total_sz = max(total_sz, monotonic_dl)
                        st["downloaded_bytes"] = monotonic_dl
                        st["total_bytes"] = total_sz
                        st["progress"] = max(st.get("progress", 0.0), pct)
                        if monotonic_dl >= total_sz and total_sz > 0:
                            st["speed_mbps"] = 0.0
                            st["eta_seconds"] = 0
                            st["message"] = f"Finalizando instalação... ({total_sz / (1024 * 1024):.1f} MB)"
                        else:
                            st["speed_mbps"] = tracker.speed_mbps
                            st["eta_seconds"] = tracker.eta_seconds
                            last_msg_t = getattr(tracker, "_last_msg_format_t", 0.0)
                            if (now - last_msg_t) >= 0.09 or not st.get("message"):
                                tracker._last_msg_format_t = now
                                tot_mb = total_sz / (1024 * 1024)
                                mb = monotonic_dl / (1024 * 1024)
                                desc = getattr(self, "desc", "") or ""
                                if desc and not desc.startswith("Fetching") and desc != "Downloading":
                                    clean_desc = desc.split("/")[-1].strip()
                                    if len(clean_desc) > 18:
                                        clean_desc = clean_desc[:15] + "..."
                                    st["message"] = f"Baixando {clean_desc} ({mb:.1f}/{tot_mb:.1f} MB)"
                                else:
                                    st["message"] = f"Baixando... ({mb:.1f}/{tot_mb:.1f} MB)"

            mgr._notify_progress(key, throttle_interval=0.1)
        except InterruptedError:
            raise
        except Exception:
            pass
        return res


def _resolve_binding_for_http_get(url: str, temp_file, displayed_filename: str = ""):
    """Identifica deterministicamente (manager, key, tracker) para um arquivo em download no huggingface_hub."""
    binding = _get_active_stream_binding(displayed_filename or "")
    if binding is not None:
        return binding
    temp_name = str(getattr(temp_file, "name", "") or "")
    hint = f"{displayed_filename or ''} {temp_name} {url or ''}"
    return _get_active_stream_binding(hint)


def _make_hooked_http_get(orig_http_get, fd_mod):
    """Cria substituto drop-in para huggingface_hub.file_download.http_get com aceleração paralela multi-stream."""
    try:
        orig_sig = inspect.signature(orig_http_get)
    except Exception:
        orig_sig = None

    def _hooked_http_get(url, temp_file, *args, **kwargs):
        if orig_sig is None:
            return orig_http_get(url, temp_file, *args, **kwargs)

        try:
            bound = orig_sig.bind(url, temp_file, *args, **kwargs)
            bound.apply_defaults()
            b_args = bound.arguments
        except Exception:
            return orig_http_get(url, temp_file, *args, **kwargs)

        expected_size = b_args.get("expected_size")
        resume_size = int(b_args.get("resume_size") or 0)
        headers = b_args.get("headers")
        proxies = b_args.get("proxies")
        displayed_filename = b_args.get("displayed_filename") or ""
        ext_tqdm_bar = b_args.get("_tqdm_bar")

        caller_ident = threading.get_ident()
        binding = _resolve_binding_for_http_get(url, temp_file, displayed_filename)
        injected_thread_binding = False
        cancel_ev = None
        active_dl_count = 1

        with _registry_lock:
            active_dl_count = max(1, len(_active_stream_keys))
            if binding is not None and caller_ident not in _active_stream_threads:
                _active_stream_threads[caller_ident] = binding
                injected_thread_binding = True

        if binding is not None:
            mgr, key, _ = binding
            cancel_ev = getattr(mgr, "_cancel_events", {}).get(key)

        try:
            if expected_size is not None and int(expected_size) - resume_size >= 2 * 1024 * 1024:
                try:
                    temp_file.flush()
                except Exception:
                    pass

                max_workers = max(8, min(20, 24 // active_dl_count))
                inferred_desc = displayed_filename
                if not inferred_desc and isinstance(url, str):
                    url_tail = urlparse(url).path.rsplit("/", 1)[-1]
                    if url_tail and "." in url_tail and len(url_tail) < 64:
                        inferred_desc = url_tail

                @contextlib.contextmanager
                def _lazy_progress_bar():
                    if ext_tqdm_bar is not None:
                        yield ext_tqdm_bar
                    else:
                        tqdm_cls = getattr(fd_mod, "tqdm", None) or getattr(fd_mod, "hf_tqdm", None)
                        if tqdm_cls is not None:
                            bar = tqdm_cls(
                                unit="B",
                                unit_scale=True,
                                total=int(expected_size),
                                initial=resume_size,
                                desc=inferred_desc or "Downloading",
                            )
                            try:
                                yield bar
                            finally:
                                try:
                                    bar.close()
                                except Exception:
                                    pass
                        else:
                            yield None

                from src.model_engines.hf.http_downloader import parallel_range_stream_to_writer
                used_parallel = parallel_range_stream_to_writer(
                    url=url,
                    write_fn=temp_file.write,
                    total_size=int(expected_size),
                    start_byte=resume_size,
                    flush_fn=getattr(temp_file, "flush", None),
                    progress_factory=_lazy_progress_bar,
                    cancel_event=cancel_ev,
                    headers=headers,
                    proxies=proxies,
                    max_workers=max_workers,
                    trust_env=_should_trust_env_proxies() if not proxies else True,
                )
                if used_parallel:
                    return None

            return orig_http_get(url, temp_file, *args, **kwargs)
        finally:
            if injected_thread_binding:
                with _registry_lock:
                    _active_stream_threads.pop(caller_ident, None)

    return _hooked_http_get


@contextlib.contextmanager
def scoped_hf_stream_hook(
    manager,
    key: str,
    target_total_bytes: int = 0,
    initial_bytes: int = 0,
    manifest_files: dict = None,
):
    """
    Context manager thread-safe que intercepta tqdm e http_get do huggingface_hub.
    
    ARQUITETURA DE INTERCEPTAÇÃO NÃO-DESTRUTIVA:
    1. Contagem de Referência (_patch_refcount): Se 2 downloads concorrentes ocorrerem,
       o patch permanece ativo enquanto houver pelo menos 1 download em andamento e só restaura
       as funções originais do Hugging Face quando o contador chegar a zero.
    2. Redução de Chunk (10 MB -> 1 MB): O Hugging Face usa 10 MB por chunk por padrão.
       Em conexões brasileiras médias (20-50 Mbps), chunks de 10 MB geram atrasos de até 4 segundos
       entre atualizações de barra. Ajustamos temporariamente para 1 MB, entregando uma telemetria fluida.
    3. Thread Binding e Manifesto Exato: Cada download registra seu (manager, key, tracker) associado
       ao thread ID e ao mapa de arquivos do manifesto, garantindo que downloads simultâneos nunca se contaminem.
    4. Restauração Estrita (finally): Todas as referências originais de tqdm e http_get são
       restauradas quando o bloco with finaliza, mesmo em caso de erro ou cancelamento.
    """
    import sys
    import huggingface_hub.file_download as fd
    import huggingface_hub.utils as hf_utils

    global _patch_refcount, _orig_fd_tqdm, _orig_fd_hf_tqdm, _orig_fd_http_get, _orig_hf_tqdm, _orig_hf_utils_mod_tqdm, _orig_sd_hf_tqdm, _orig_sd_base_tqdm, _orig_chunk_size

    est = target_total_bytes
    if est <= 0 and hasattr(manager, "download_status") and key in manager.download_status:
        est = manager.download_status[key].get("total_bytes", 0)
    tracker = DownloadStreamTracker(
        key,
        target_total_bytes=est,
        initial_bytes=initial_bytes,
        manifest_files=manifest_files,
    )

    ident = threading.get_ident()
    with _registry_lock:
        _active_stream_threads[ident] = (manager, key, tracker)
        _active_stream_keys[key] = (manager, key, tracker)

    with _patch_lock:
        _patch_refcount += 1
        # Somente aplica os ganchos na primeira thread que requisitar o patch
        if _patch_refcount == 1:
            try:
                import huggingface_hub.constants as hf_constants
                # Salva o chunk original e reduz para 1 MB para granularidade alta
                _orig_chunk_size = getattr(hf_constants, "DOWNLOAD_CHUNK_SIZE", 10 * 1024 * 1024)
                hf_constants.DOWNLOAD_CHUNK_SIZE = 1024 * 1024
            except Exception:
                pass

            # Salva os ponteiros originais do SDK para reversão futura
            _orig_fd_tqdm = getattr(fd, "tqdm", None)
            _orig_fd_hf_tqdm = getattr(fd, "hf_tqdm", None) if hasattr(fd, "hf_tqdm") else None
            _orig_fd_http_get = getattr(fd, "http_get", None)
            _orig_hf_tqdm = getattr(hf_utils, "tqdm", None)

            hf_utils_tqdm_mod = sys.modules.get("huggingface_hub.utils.tqdm")
            _orig_hf_utils_mod_tqdm = getattr(hf_utils_tqdm_mod, "tqdm", None) if hf_utils_tqdm_mod else None

            sd_mod = sys.modules.get("huggingface_hub._snapshot_download")
            if sd_mod is None:
                try:
                    import huggingface_hub._snapshot_download as sd_mod
                except Exception:
                    pass
            _orig_sd_hf_tqdm = getattr(sd_mod, "hf_tqdm", None) if sd_mod else None
            _orig_sd_base_tqdm = getattr(sd_mod, "base_tqdm", None) if sd_mod else None

            base_cls = _orig_hf_tqdm or _orig_fd_hf_tqdm or object

            # Classe herdeira que encapsula nosso listener de stream
            class _ActiveStreamTqdm(_GlobalStreamTqdm, base_cls):
                pass

            # Substituição drop-in nos módulos internos do huggingface_hub
            fd.tqdm = _ActiveStreamTqdm
            if _orig_fd_hf_tqdm is not None:
                fd.hf_tqdm = _ActiveStreamTqdm
            if callable(_orig_fd_http_get):
                fd.http_get = _make_hooked_http_get(_orig_fd_http_get, fd)
            hf_utils.tqdm = _ActiveStreamTqdm
            if hf_utils_tqdm_mod is not None:
                hf_utils_tqdm_mod.tqdm = _ActiveStreamTqdm
            if sd_mod is not None:
                sd_mod.hf_tqdm = _ActiveStreamTqdm
                sd_mod.base_tqdm = _ActiveStreamTqdm

    try:
        yield tracker
    finally:
        # Desvincula a thread atual
        with _registry_lock:
            _active_stream_threads.pop(ident, None)
            _active_stream_keys.pop(key, None)

        with _patch_lock:
            _patch_refcount -= 1
            # Quando todos os downloads finalizarem, restaura os ponteiros originais da biblioteca
            if _patch_refcount == 0:
                if _orig_fd_tqdm is not None:
                    fd.tqdm = _orig_fd_tqdm
                if _orig_fd_hf_tqdm is not None:
                    fd.hf_tqdm = _orig_fd_hf_tqdm
                if _orig_fd_http_get is not None:
                    fd.http_get = _orig_fd_http_get
                if _orig_hf_tqdm is not None:
                    hf_utils.tqdm = _orig_hf_tqdm
                hf_utils_tqdm_mod = sys.modules.get("huggingface_hub.utils.tqdm")
                if hf_utils_tqdm_mod is not None and _orig_hf_utils_mod_tqdm is not None:
                    hf_utils_tqdm_mod.tqdm = _orig_hf_utils_mod_tqdm
                sd_mod = sys.modules.get("huggingface_hub._snapshot_download")
                if sd_mod is not None:
                    if _orig_sd_hf_tqdm is not None:
                        sd_mod.hf_tqdm = _orig_sd_hf_tqdm
                    if _orig_sd_base_tqdm is not None:
                        sd_mod.base_tqdm = _orig_sd_base_tqdm
                try:
                    import huggingface_hub.constants as hf_constants
                    hf_constants.DOWNLOAD_CHUNK_SIZE = _orig_chunk_size
                except Exception:
                    pass
