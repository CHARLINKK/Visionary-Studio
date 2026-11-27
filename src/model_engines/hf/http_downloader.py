"""
Cliente de download HTTP multi-conexão (Parallel Range 206) com retomada contígua sem buracos.
Os rastreadores de stream e ganchos tqdm residem em `src.model_engines.hf.stream_tracker` e
são re-exportados aqui para compatibilidade integral com contratos existentes.
"""

import os
import time
import requests
import threading
import contextlib
import concurrent.futures
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from src.model_engines.hf.integrity_checker import verify_file_integrity
from src.model_engines.hf.stream_tracker import (
    DownloadStreamTracker,
    build_scoped_tqdm_class,
    _active_stream_threads,
    _active_stream_keys,
    _registry_lock,
    _get_active_stream_binding,
    _GlobalStreamTqdm,
    _resolve_binding_for_http_get,
    _make_hooked_http_get,
    scoped_hf_stream_hook,
)


def _should_trust_env() -> bool:
    """
    Evita que o `requests` consulte o registro de proxy do Windows (WinHTTP/Registry)
    em cada requisição quando não há proxy explícito configurado em variáveis de ambiente.
    """
    for env_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        if os.environ.get(env_key):
            return True
    return False


def parallel_range_stream_to_writer(
    url: str,
    write_fn,
    total_size: int,
    start_byte: int = 0,
    flush_fn=None,
    progress_factory=None,
    on_chunk=None,
    cancel_event: threading.Event = None,
    headers: dict = None,
    proxies: dict = None,
    max_workers: int = 16,
    trust_env: bool | None = None,
    min_parallel_bytes: int = 2 * 1024 * 1024,
) -> bool:
    """
    Motor de transferência HTTP/1.1 Range paralelo (estilo aria2c/hf_transfer) em Python puro.
    
    ARQUITETURA E DECISÕES NÃO-ÓBVIAS:
    1. Gravação Estritamente Sequencial (Contígua):
       Diferente de downloaders ingênuos que usam f.seek() aleatório e criam 'sparse files' cheios de
       buracos de bytes nulos em caso de cancelamento, este motor utiliza uma janela de commit ordenada.
       Os segmentos baixados fora de ordem aguardam em memória até que o segmento imediatamente anterior
       seja gravado no disco. Se o usuário cancelar, o arquivo .part em disco é 100% contíguo e íntegro,
       permitindo retomar de onde parou sem corrupção.
    2. Sonda Inicial (Probe 206):
       O primeiro segmento (seg0) é disparado como teste. Se o servidor responder HTTP 200 em vez de 206,
       significa que o servidor/CDN ignora requisições Range; abortamos o modo paralelo imediatamente e
       retornamos False para que o fallback de stream simples assuma sem corromper o arquivo.
    3. Tratamento de Redirecionamento Cross-Origin:
       O Hugging Face redireciona para CDNs (Cloudflare / AWS S3 presigned URLs).
       Ao mudar de domínio, cabeçalhos sensíveis como 'Authorization: Bearer ...' são removidos para evitar
       que o S3 rejeite a requisição com '400 Bad Request: Only one auth mechanism allowed'.
    """
    if not url or not total_size or total_size <= 0:
        return False

    start_byte = max(0, int(start_byte or 0))
    remaining = int(total_size) - start_byte
    # Arquivos pequenos (< 2 MB) não justificam o overhead de múltiplas conexões TCP
    if remaining < min_parallel_bytes:
        return False

    # Dimensionamento adaptativo de segmento conforme o tamanho do arquivo
    if remaining < 16 * 1024 * 1024:
        seg_size = 1 * 1024 * 1024
    elif remaining < 128 * 1024 * 1024:
        seg_size = 2 * 1024 * 1024
    elif remaining < 256 * 1024 * 1024:
        seg_size = 4 * 1024 * 1024
    else:
        seg_size = 8 * 1024 * 1024

    total_segments = (remaining + seg_size - 1) // seg_size
    if total_segments <= 1:
        return False

    workers = max(2, min(int(max_workers), total_segments))
    session = requests.Session()
    session.trust_env = _should_trust_env() if trust_env is None else bool(trust_env)
    # Pool de conexões HTTP persistentes reutilizando Keep-Alive na CDN
    adapter = HTTPAdapter(pool_connections=workers + 4, pool_maxsize=workers + 4, max_retries=0)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Dispara o segmento 0 como teste de compatibilidade HTTP 206
    seg0_start = start_byte
    seg0_end = min(int(total_size) - 1, seg0_start + seg_size - 1)
    seg0_expected = seg0_end - seg0_start + 1

    probe_headers = dict(headers or {})
    probe_headers["Range"] = f"bytes={seg0_start}-{seg0_end}"

    probe_resp = None
    try:
        probe_resp = session.get(
            url,
            headers=probe_headers,
            stream=True,
            allow_redirects=True,
            proxies=proxies,
            timeout=(10, 25),
        )
    except Exception:
        try:
            session.close()
        except Exception:
            pass
        return False

    try:
        status_code = getattr(probe_resp, "status_code", None)
        # Se a CDN não aceitar 'Range' ou responder HTTP 200 integral, aborta e recorre ao modo sequencial
        if status_code != 206:
            probe_resp.close()
            session.close()
            return False

        cl_header = probe_resp.headers.get("Content-Length") or probe_resp.headers.get("content-length")
        if cl_header is not None:
            try:
                if int(cl_header) != seg0_expected:
                    probe_resp.close()
                    session.close()
                    return False
            except (ValueError, TypeError):
                pass
    except Exception:
        try:
            if probe_resp is not None:
                probe_resp.close()
            session.close()
        except Exception:
            pass
        return False

    # Captura a URL final resolvida após eventuais redirects 301/302 da CDN
    resolved_url = getattr(probe_resp, "url", None)
    if not isinstance(resolved_url, str) or not resolved_url.startswith("http"):
        resolved_url = url

    worker_headers = {}
    cross_origin = urlparse(resolved_url).netloc.lower() != urlparse(url).netloc.lower()
    for hk, hv in (headers or {}).items():
        lk = hk.lower()
        if lk == "range":
            continue
        # Remove Authorization em caso de redirect cross-origin para buckets S3 pré-assinados
        if cross_origin and lk == "authorization":
            continue
        worker_headers[hk] = hv

    # Variáveis de sincronização da janela de commit sequencial
    window_cond = threading.Condition()
    next_assign_idx = 1
    next_commit_idx = 0
    completed_segments = {}
    commit_flushing = False
    first_error = [None]
    abort_event = threading.Event()
    progress_lock = threading.Lock()
    # Limita o número de segmentos na RAM para evitar consumo excessivo de memória em conexões ultra-rápidas
    max_window = max(workers * 2, 8)
    probe_holder = [probe_resp]

    progress_cm = progress_factory() if callable(progress_factory) else contextlib.nullcontext(None)

    def _trigger_abort(err):
        with window_cond:
            if first_error[0] is None:
                first_error[0] = err
            abort_event.set()
            window_cond.notify_all()
        try:
            session.close()
        except Exception:
            pass

    def _commit_segment(seg_idx: int, data: bytes):
        nonlocal next_commit_idx, commit_flushing
        with window_cond:
            if abort_event.is_set():
                return
            completed_segments[seg_idx] = data
            if not commit_flushing:
                commit_flushing = True
                do_flush = True
            else:
                do_flush = False

        if do_flush:
            try:
                while True:
                    with window_cond:
                        if abort_event.is_set() or next_commit_idx not in completed_segments:
                            commit_flushing = False
                            window_cond.notify_all()
                            break
                        buf_to_write = completed_segments.pop(next_commit_idx)
                        next_commit_idx += 1
                        window_cond.notify_all()
                    write_fn(buf_to_write)
            except BaseException as exc:
                with window_cond:
                    commit_flushing = False
                _trigger_abort(exc)
                raise

    try:
        with progress_cm as prog_bar:
            def _emit_bytes(nb: int):
                if prog_bar is not None:
                    prog_bar.update(nb)
                if on_chunk is not None:
                    on_chunk(nb)

            def _download_one_segment(seg_idx: int, use_probe: bool = False):
                seg_start = start_byte + seg_idx * seg_size
                seg_end = min(int(total_size) - 1, seg_start + seg_size - 1)
                expected_len = seg_end - seg_start + 1
                buf = bytearray()

                for attempt in range(4):
                    if abort_event.is_set() or (cancel_event is not None and cancel_event.is_set()):
                        raise InterruptedError("Download cancelado pelo usuário.")

                    cur_start = seg_start + len(buf)
                    if cur_start > seg_end:
                        break

                    resp = None
                    try:
                        if use_probe and attempt == 0 and len(buf) == 0 and probe_holder[0] is not None:
                            resp = probe_holder[0]
                            probe_holder[0] = None
                        else:
                            req_h = dict(worker_headers)
                            req_h["Range"] = f"bytes={cur_start}-{seg_end}"
                            resp = session.get(
                                resolved_url,
                                headers=req_h,
                                stream=True,
                                allow_redirects=True,
                                proxies=proxies,
                                timeout=(10, 25),
                            )
                            if resp.status_code != 206:
                                raise RuntimeError(
                                    f"Servidor retornou HTTP {resp.status_code} para Range {cur_start}-{seg_end}"
                                )

                        for chunk in resp.iter_content(chunk_size=512 * 1024):
                            if abort_event.is_set() or (cancel_event is not None and cancel_event.is_set()):
                                raise InterruptedError("Download cancelado pelo usuário.")
                            if not chunk:
                                continue
                            needed = expected_len - len(buf)
                            if len(chunk) > needed:
                                chunk = chunk[:needed]
                            buf.extend(chunk)
                            with progress_lock:
                                _emit_bytes(len(chunk))
                            if len(buf) >= expected_len:
                                break

                        if len(buf) == expected_len:
                            _commit_segment(seg_idx, bytes(buf))
                            return

                        if attempt == 3:
                            raise IOError(f"Segmento {seg_idx} incompleto ({len(buf)}/{expected_len} bytes)")
                    except InterruptedError as ie:
                        _trigger_abort(ie)
                        raise
                    except Exception as err:
                        if abort_event.is_set() or (cancel_event is not None and cancel_event.is_set()):
                            ie = InterruptedError("Download cancelado pelo usuário.")
                            _trigger_abort(ie)
                            raise ie
                        if attempt == 3:
                            _trigger_abort(err)
                            raise
                        time.sleep(0.25 * (attempt + 1))
                    finally:
                        if resp is not None:
                            try:
                                resp.close()
                            except Exception:
                                pass

            def _worker_loop(worker_id: int):
                nonlocal next_assign_idx
                try:
                    if worker_id == 0:
                        _download_one_segment(0, use_probe=True)
                    while not abort_event.is_set():
                        with window_cond:
                            while (
                                not abort_event.is_set()
                                and next_assign_idx < total_segments
                                and (next_assign_idx - next_commit_idx) >= max_window
                            ):
                                if cancel_event is not None and cancel_event.is_set():
                                    abort_event.set()
                                    window_cond.notify_all()
                                    break
                                window_cond.wait(timeout=0.2)
                            if abort_event.is_set() or next_assign_idx >= total_segments:
                                return
                            seg_idx = next_assign_idx
                            next_assign_idx += 1
                        _download_one_segment(seg_idx, use_probe=False)
                except BaseException as exc:
                    _trigger_abort(exc)
                    raise

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=workers, thread_name_prefix="HFParallelRange"
            ) as pool:
                futures = [pool.submit(_worker_loop, wid) for wid in range(workers)]
                for fut in concurrent.futures.as_completed(futures):
                    fut.result()

            if first_error[0] is not None:
                raise first_error[0]

            if next_commit_idx != total_segments:
                raise IOError(f"Commit paralelo incompleto ({next_commit_idx}/{total_segments} segmentos)")

            if callable(flush_fn):
                flush_fn()
        return True
    finally:
        if probe_holder[0] is not None:
            try:
                probe_holder[0].close()
            except Exception:
                pass
            probe_holder[0] = None
        try:
            session.close()
        except Exception:
            pass


def download_single_file_http(
    manager,
    key: str,
    info: dict,
    target_path: str,
    cancel_event: threading.Event,
    est_size: int
):
    """
    Executa o download de arquivo único via HTTP com suporte a Resume (Range 206)
    e validação de integridade física.
    
    ESTRATÉGIAS DEFENSIVAS:
    1. Sufixo '.part': Gravação temporária para blindar o runtime de IA contra modelos corrompidos/truncados.
    2. HTTP 416 (Range Not Satisfiable): Se o arquivo já estiver 100% gravado no .part mas não renomeado,
       o servidor responde 416. Tratamos isso como sucesso e seguimos para validação de SHA256.
    3. Renomeação Atômica no Windows com Retry: O Windows Defender frequentemente trava arquivos recém-gravados
       para varredura em tempo real. Um loop de retry de 3 tentativas com sleep(0.15) absorve essa pegadinha.
    """
    filename = info.get("filename", "model.pt")
    file_target = os.path.join(target_path, filename)
    part_file = file_target + ".part"
    url = info.get("url")
    expected_sha = info.get("sha256")
    min_size = info.get("min_size_bytes", 50 * 1024 * 1024)

    existing_bytes = 0
    if os.path.exists(part_file):
        try:
            existing_bytes = os.path.getsize(part_file)
        except Exception:
            existing_bytes = 0

    headers = {}
    if existing_bytes > 0:
        headers["Range"] = f"bytes={existing_bytes}-"

    session = requests.Session()
    session.trust_env = False

    with session.get(url, headers=headers, stream=True, timeout=60) as r:
        if r.status_code == 416:
            # Caso 416: O arquivo parcial já contém todos os bytes do arquivo remoto
            downloaded = existing_bytes
            total_length = existing_bytes
        else:
            if r.status_code == 206:
                write_mode = "ab"
                downloaded = existing_bytes
                cr = r.headers.get("content-range", "")
                if "/" in cr:
                    try:
                        total_length = int(cr.split("/")[-1])
                    except Exception:
                        total_length = existing_bytes + int(r.headers.get("content-length", est_size))
                else:
                    total_length = existing_bytes + int(r.headers.get("content-length", est_size))
            else:
                r.raise_for_status()
                write_mode = "wb"
                downloaded = 0
                total_length = int(r.headers.get("content-length", est_size))

            with manager._status_lock:
                manager.download_status[key]["total_bytes"] = total_length
                manager.download_status[key]["downloaded_bytes"] = downloaded
                manager.download_status[key]["speed_mbps"] = 0.0
                manager.download_status[key]["eta_seconds"] = 0

            last_time = time.time()
            last_downloaded = downloaded
            speed_mb = 0.0
            eta_s = 0

            from src.config import is_test_environment
            used_parallel_single = False
            if (
                not is_test_environment()
                and r.status_code in (200, 206)
                and total_length - downloaded >= 4 * 1024 * 1024
            ):
                resolved_single_url = getattr(r, "url", None) or url
                r.close()
                tracker_single = DownloadStreamTracker(key, target_total_bytes=total_length, initial_bytes=downloaded)

                def _on_single_chunk(nb: int):
                    nonlocal downloaded
                    with tracker_single.lock:
                        now_c = time.time()
                        tracker_single.record_chunk_locked(nb, now_c)
                        downloaded = tracker_single.downloaded_bytes
                        cur_spd = tracker_single.speed_mbps
                        cur_eta = tracker_single.eta_seconds
                    with manager._status_lock:
                        pct = min(99.9, round((downloaded / total_length) * 100, 1)) if total_length > 0 else 0
                        manager.download_status[key]["downloaded_bytes"] = max(
                            int(manager.download_status[key].get("downloaded_bytes", 0)), downloaded
                        )
                        manager.download_status[key]["total_bytes"] = total_length
                        manager.download_status[key]["progress"] = max(
                            float(manager.download_status[key].get("progress", 0.0)), pct
                        )
                        manager.download_status[key]["speed_mbps"] = cur_spd
                        manager.download_status[key]["eta_seconds"] = max(0, cur_eta)
                        mb = downloaded / (1024 * 1024)
                        tot_mb = total_length / (1024 * 1024)
                        manager.download_status[key]["message"] = (
                            f"Baixando {filename}... ({mb:.1f}/{tot_mb:.1f} MB - {pct}%)"
                        )
                    manager._notify_progress(key, throttle_interval=0.1)

                with open(part_file, write_mode) as f:
                    try:
                        used_parallel_single = parallel_range_stream_to_writer(
                            url=resolved_single_url,
                            write_fn=f.write,
                            total_size=total_length,
                            start_byte=downloaded,
                            flush_fn=f.flush,
                            on_chunk=_on_single_chunk,
                            cancel_event=cancel_event,
                            max_workers=16,
                            trust_env=False,
                        )
                    except InterruptedError:
                        used_parallel_single = True

            if not used_parallel_single:
                def _stream_single(resp_obj, mode_str):
                    nonlocal downloaded, last_time, last_downloaded, speed_mb, eta_s
                    with open(part_file, mode_str) as f:
                        for chunk in resp_obj.iter_content(chunk_size=1024 * 1024):
                            if cancel_event.is_set():
                                break
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                now = time.time()
                                dt = now - last_time
                                if dt >= 0.3:
                                    speed_mb = ((downloaded - last_downloaded) / (1024 * 1024)) / dt if dt > 0 else 0
                                    remaining_bytes = max(0, total_length - downloaded)
                                    eta_s = int(remaining_bytes / (speed_mb * 1024 * 1024)) if speed_mb > 0.05 else 0
                                    last_time = now
                                    last_downloaded = downloaded

                                with manager._status_lock:
                                    pct = min(99.9, round((downloaded / total_length) * 100, 1)) if total_length > 0 else 0
                                    manager.download_status[key]["downloaded_bytes"] = downloaded
                                    manager.download_status[key]["total_bytes"] = total_length
                                    manager.download_status[key]["progress"] = pct
                                    manager.download_status[key]["speed_mbps"] = round(speed_mb, 1)
                                    manager.download_status[key]["eta_seconds"] = max(0, eta_s)
                                    mb = downloaded / (1024 * 1024)
                                    tot_mb = total_length / (1024 * 1024)
                                    manager.download_status[key]["message"] = (
                                        f"Baixando {filename}... ({mb:.1f}/{tot_mb:.1f} MB - {pct}%)"
                                    )

                if getattr(r, "raw", None) is not None and not getattr(r.raw, "closed", False):
                    _stream_single(r, write_mode)
                elif not cancel_event.is_set():
                    retry_h = {"Range": f"bytes={downloaded}-"} if downloaded > 0 else {}
                    with session.get(url, headers=retry_h, stream=True, timeout=60) as r2:
                        r2.raise_for_status()
                        _stream_single(r2, "ab" if downloaded > 0 and r2.status_code == 206 else "wb")

    if not cancel_event.is_set():
        with manager._status_lock:
            manager.download_status[key]["message"] = "Validando integridade do arquivo..."

        if not verify_file_integrity(part_file, expected_sha256=expected_sha, min_size_bytes=min_size):
            try:
                os.remove(part_file)
            except Exception:
                pass
            raise RuntimeError(f"Falha na validação de integridade de {filename}. Arquivo corrompido ou incompleto.")

        for attempt in range(3):
            try:
                if os.path.exists(file_target):
                    try:
                        os.remove(file_target)
                    except Exception:
                        pass
                os.replace(part_file, file_target)
                break
            except (PermissionError, OSError) as pe:
                if attempt == 2:
                    raise pe
                time.sleep(0.15)

        with manager._status_lock:
            manager.download_status[key] = {
                "status": "installed",
                "progress": 100.0,
                "downloaded_bytes": max(downloaded, est_size),
                "total_bytes": max(downloaded, est_size),
                "speed_mbps": 0.0,
                "eta_seconds": 0,
                "message": "Concluído e validado!"
            }
