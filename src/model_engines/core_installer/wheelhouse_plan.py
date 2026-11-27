"""
Planejador e downloader determinístico de wheelhouse para o PyTorch Core.

Resolve o grafo exato de dependências via `pip install --dry-run --report <json>`,
sonda o tamanho real (Content-Length) de cada wheel, baixa com progresso exato por arquivo
(Parallel Range 206 + validação SHA-256) e mede o tamanho real descompactado lendo o
Central Directory ZIP de cada `.whl` antes da instalação offline (`pip install --no-index --no-deps`).
"""

import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import requests
from requests.adapters import HTTPAdapter

from src.model_engines.hf.http_downloader import _should_trust_env, parallel_range_stream_to_writer


def _create_fast_session(pool_size: int = 16) -> requests.Session:
    session = requests.Session()
    session.trust_env = _should_trust_env()
    if hasattr(session, "mount"):
        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size, max_retries=2)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    return session


def _hash_prefix_file(path: str, limit_bytes: int) -> hashlib.sha256:
    """Inicializa hasher SHA-256 lendo apenas os bytes já gravados de um `.part` retomado."""
    h = hashlib.sha256()
    remaining = max(0, int(limit_bytes))
    with open(path, "rb") as fh:
        while remaining > 0:
            chunk = fh.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h


def _extract_sha256(download_info: dict) -> str | None:
    archive_info = (download_info or {}).get("archive_info") or {}
    hashes = archive_info.get("hashes") or {}
    sha = hashes.get("sha256")
    if isinstance(sha, str) and len(sha.strip()) == 64:
        return sha.strip().lower()
    raw_hash = archive_info.get("hash") or ""
    if isinstance(raw_hash, str) and raw_hash.lower().startswith("sha256="):
        cand = raw_hash.split("=", 1)[1].strip().lower()
        if len(cand) == 64:
            return cand
    return None


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


def _probe_remote_wheel_size(session: requests.Session, url: str) -> int:
    """Obtém o tamanho exato em bytes de um wheel remoto via HEAD ou fallback Range 0-0."""
    try:
        resp = session.head(url, allow_redirects=True, timeout=(8, 15))
        if resp.status_code == 200:
            cl = resp.headers.get("Content-Length") or resp.headers.get("content-length")
            if cl is not None:
                sz = int(cl)
                if sz > 0:
                    return sz
    except Exception:
        pass

    try:
        with session.get(
            url,
            headers={"Range": "bytes=0-0"},
            stream=True,
            allow_redirects=True,
            timeout=(8, 15),
        ) as resp:
            if resp.status_code == 206:
                cr = resp.headers.get("Content-Range") or resp.headers.get("content-range") or ""
                if "/" in cr:
                    tot_str = cr.rsplit("/", 1)[-1].strip()
                    if tot_str.isdigit() and int(tot_str) > 0:
                        return int(tot_str)
            elif resp.status_code == 200:
                cl = resp.headers.get("Content-Length") or resp.headers.get("content-length")
                if cl is not None and int(cl) > 0:
                    return int(cl)
    except Exception:
        pass

    return 0


def _build_dry_run_command(python_exe: str, pip_install_args: list[str], report_path: str) -> list[str]:
    """Deriva comando `--dry-run --report <file>` preservando os argumentos de requisitos do pip."""
    tail_args: list[str] = []
    try:
        idx = pip_install_args.index("install")
        tail_args = list(pip_install_args[idx + 1 :])
    except ValueError:
        tail_args = list(pip_install_args)

    return [
        python_exe,
        "-m",
        "pip",
        "install",
        "--dry-run",
        "--quiet",
        "--disable-pip-version-check",
        "--report",
        report_path,
        *tail_args,
    ]


def resolve_pip_install_plan(
    python_exe: str,
    pip_install_args: list[str],
    env: dict = None,
    timeout: int = 90,
) -> dict | None:
    """
    Executa `pip install --dry-run --report <tmp_json>` para descobrir exatamente quais wheels
    precisam ser baixados/instalados e sonda o `Content-Length` exato de cada wheel.

    Retorna None se algum item não for `.whl` (ex: sdist que exige compilação) ou se o probe falhar,
    permitindo fallback seguro e transparente para o fluxo padrão do pip.
    """
    fd, report_path = tempfile.mkstemp(prefix="visionary_pip_report_", suffix=".json")
    os.close(fd)
    try:
        cmd = _build_dry_run_command(python_exe, pip_install_args, report_path)
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        if res.returncode != 0 or not os.path.isfile(report_path):
            return None

        with open(report_path, "r", encoding="utf-8") as rf:
            report = json.load(rf)
    except Exception:
        return None
    finally:
        try:
            os.remove(report_path)
        except OSError:
            pass

    install_list = report.get("install")
    if not isinstance(install_list, list):
        return None
    if len(install_list) == 0:
        return {"all_satisfied": True, "items": [], "total_download_bytes": 0}

    parsed_items = []
    for entry in install_list:
        if not isinstance(entry, dict):
            return None
        dl_info = entry.get("download_info") or {}
        url = dl_info.get("url") or ""
        if not isinstance(url, str) or not url:
            return None

        parsed_url = urlparse(url)
        scheme = (parsed_url.scheme or "").lower()
        filename = unquote(parsed_url.path.rsplit("/", 1)[-1])
        # Só assume controle do wheelhouse se todos os artefatos forem wheels pré-compilados (.whl)
        if not filename.lower().endswith(".whl"):
            return None

        meta = entry.get("metadata") or {}
        pkg_name = str(meta.get("name") or filename.split("-")[0])
        pkg_ver = str(meta.get("version") or "")
        sha256 = _extract_sha256(dl_info)

        if scheme == "file":
            local_path = url2pathname(parsed_url.path)
            if not os.path.isfile(local_path):
                return None
            sz = os.path.getsize(local_path)
            if sz <= 0:
                return None
            parsed_items.append(
                {
                    "name": pkg_name,
                    "version": pkg_ver,
                    "url": url,
                    "filename": filename,
                    "size_bytes": sz,
                    "sha256": sha256,
                    "is_local": True,
                    "local_path": local_path,
                }
            )
        elif scheme in ("http", "https"):
            parsed_items.append(
                {
                    "name": pkg_name,
                    "version": pkg_ver,
                    "url": url,
                    "filename": filename,
                    "size_bytes": 0,
                    "sha256": sha256,
                    "is_local": False,
                    "local_path": None,
                }
            )
        else:
            return None

    remote_items = [it for it in parsed_items if not it["is_local"]]
    if remote_items:
        session = _create_fast_session(pool_size=16)
        try:
            max_w = max(1, min(16, len(remote_items)))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as pool:
                fut_map = {pool.submit(_probe_remote_wheel_size, session, it["url"]): it for it in remote_items}
                for fut, item in fut_map.items():
                    sz = int(fut.result() or 0)
                    if sz <= 0:
                        return None
                    item["size_bytes"] = sz
        except Exception:
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

    total_dl = sum(it["size_bytes"] for it in parsed_items if not it["is_local"])
    return {
        "all_satisfied": False,
        "items": parsed_items,
        "total_download_bytes": total_dl,
    }


def _is_cached_wheel_valid(path: str, expected_size: int, expected_sha256: str | None) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        if expected_size > 0 and os.path.getsize(path) != expected_size:
            return False
        if expected_sha256:
            return _file_sha256(path) == expected_sha256.lower()
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def download_wheelhouse_plan(
    plan_items: list[dict],
    wheelhouse_dir: str,
    on_progress=None,
    cancel_event: threading.Event = None,
) -> tuple[list[str], int]:
    """
    Baixa todos os wheels remotos do plano para `wheelhouse_dir` com contabilidade exata por arquivo.

    Retorna:
        (wheel_paths, network_bytes_downloaded)
    """
    os.makedirs(wheelhouse_dir, exist_ok=True)
    lock = threading.Lock()
    last_emit = [0.0]

    wheel_paths: list[str] = []
    pending_remote: list[dict] = []
    wheel_done_bytes: dict[str, int] = {}

    for item in plan_items:
        if item.get("is_local") and item.get("local_path") and os.path.isfile(item["local_path"]):
            wheel_paths.append(item["local_path"])
            continue
        final_path = os.path.join(wheelhouse_dir, item["filename"])
        wheel_paths.append(final_path)
        if _is_cached_wheel_valid(final_path, item["size_bytes"], item.get("sha256")):
            continue
        pending_remote.append(item)
        wheel_done_bytes[item["filename"]] = 0

    total_network_bytes = sum(it["size_bytes"] for it in pending_remote)
    if total_network_bytes == 0:
        return wheel_paths, 0

    def _emit_progress_unlocked(active_name: str, force: bool = False):
        if not callable(on_progress):
            return
        now = time.time()
        with lock:
            if not force and (now - last_emit[0]) < 0.1:
                return
            last_emit[0] = now
            cur_total = min(total_network_bytes, sum(wheel_done_bytes.values()))
        on_progress(cur_total, total_network_bytes, active_name)

    thread_local = threading.local()
    created_sessions: list[requests.Session] = []
    sessions_lock = threading.Lock()

    def _get_worker_session() -> requests.Session:
        sess = getattr(thread_local, "session", None)
        if sess is None:
            sess = _create_fast_session(pool_size=8)
            thread_local.session = sess
            with sessions_lock:
                created_sessions.append(sess)
        return sess

    def _download_single_wheel(item: dict):
        fname = item["filename"]
        pkg_name = item["name"]
        expected_size = int(item["size_bytes"])
        expected_sha = item.get("sha256")
        final_path = os.path.join(wheelhouse_dir, fname)
        part_path = final_path + ".part"

        existing = 0
        if os.path.isfile(part_path):
            try:
                part_sz = os.path.getsize(part_path)
                if 0 < part_sz <= expected_size:
                    existing = part_sz
                else:
                    os.remove(part_path)
            except OSError:
                existing = 0

        with lock:
            wheel_done_bytes[fname] = existing
        _emit_progress_unlocked(pkg_name, force=True)

        trust_env_flag = _should_trust_env()
        stream_sha_hex = None

        if existing < expected_size:
            used_parallel = False
            remaining = expected_size - existing
            parallel_acc = existing

            def _record_progress(new_abs: int):
                should_emit = False
                cur_total = 0
                now = time.time()
                with lock:
                    clamped = max(0, min(expected_size, new_abs))
                    if clamped > wheel_done_bytes[fname]:
                        wheel_done_bytes[fname] = clamped
                    if callable(on_progress) and (now - last_emit[0]) >= 0.1:
                        last_emit[0] = now
                        cur_total = min(total_network_bytes, sum(wheel_done_bytes.values()))
                        should_emit = True
                if should_emit:
                    on_progress(cur_total, total_network_bytes, pkg_name)

            if remaining >= 4 * 1024 * 1024:
                stream_hasher = _hash_prefix_file(part_path, existing) if (expected_sha and existing > 0) else (hashlib.sha256() if expected_sha else None)

                def _write_and_hash(data: bytes):
                    fh.write(data)
                    if stream_hasher is not None:
                        stream_hasher.update(data)

                def _on_chunk(nb: int):
                    nonlocal parallel_acc
                    parallel_acc += nb
                    _record_progress(parallel_acc)

                mode = "ab" if existing > 0 else "wb"
                with open(part_path, mode) as fh:
                    used_parallel = parallel_range_stream_to_writer(
                        url=item["url"],
                        write_fn=_write_and_hash,
                        total_size=expected_size,
                        start_byte=existing,
                        flush_fn=fh.flush,
                        on_chunk=_on_chunk,
                        cancel_event=cancel_event,
                        max_workers=16 if expected_size >= 256 * 1024 * 1024 else 12,
                        trust_env=trust_env_flag,
                    )
                if used_parallel and stream_hasher is not None:
                    stream_sha_hex = stream_hasher.hexdigest().lower()

            if not used_parallel:
                seq_start = 0
                if os.path.isfile(part_path):
                    try:
                        seq_start = min(expected_size, os.path.getsize(part_path))
                    except OSError:
                        seq_start = 0

                seq_hasher = _hash_prefix_file(part_path, seq_start) if (expected_sha and seq_start > 0) else (hashlib.sha256() if expected_sha else None)
                headers = {"Range": f"bytes={seq_start}-"} if seq_start > 0 else {}
                session = _get_worker_session()
                with session.get(
                    item["url"],
                    headers=headers,
                    stream=True,
                    allow_redirects=True,
                    timeout=(10, 60),
                ) as resp:
                    if resp.status_code == 416 and seq_start == expected_size:
                        _record_progress(expected_size)
                        if seq_hasher is not None:
                            stream_sha_hex = seq_hasher.hexdigest().lower()
                    else:
                        resp.raise_for_status()
                        if resp.status_code == 206 and seq_start > 0:
                            mode = "ab"
                            cur_pos = seq_start
                        else:
                            mode = "wb"
                            cur_pos = 0
                            if seq_hasher is not None:
                                seq_hasher = hashlib.sha256()
                        with open(part_path, mode) as fh:
                            for chunk in resp.iter_content(chunk_size=512 * 1024):
                                if cancel_event is not None and cancel_event.is_set():
                                    raise InterruptedError("Instalação cancelada.")
                                if not chunk:
                                    continue
                                fh.write(chunk)
                                if seq_hasher is not None:
                                    seq_hasher.update(chunk)
                                cur_pos += len(chunk)
                                _record_progress(cur_pos)
                        if seq_hasher is not None:
                            stream_sha_hex = seq_hasher.hexdigest().lower()

        # Validação sem re-leitura de disco quando o SHA-256 já foi calculado em streaming
        if stream_sha_hex is not None and expected_sha:
            size_ok = os.path.isfile(part_path) and os.path.getsize(part_path) == expected_size
            valid = size_ok and (stream_sha_hex == expected_sha.lower())
        else:
            valid = _is_cached_wheel_valid(part_path, expected_size, expected_sha)

        if not valid:
            try:
                os.remove(part_path)
            except OSError:
                pass
            raise RuntimeError(f"Integridade inválida no wheel {fname}.")

        # Renomeação atômica com retry contra varredura instantânea do Windows Defender
        for attempt in range(3):
            try:
                if os.path.exists(final_path):
                    os.remove(final_path)
                os.replace(part_path, final_path)
                break
            except (PermissionError, OSError):
                if attempt == 2:
                    raise
                time.sleep(0.15)

        with lock:
            wheel_done_bytes[fname] = expected_size
        _emit_progress_unlocked(pkg_name, force=True)

    # Pool dedicado para wheels gigantes (>= 256 MB, ex: torch com 16 streams Range)
    # em paralelo com 4 workers Keep-Alive para liquidar os wheels médios/pequenos simultaneamente.
    giant_items = sorted(
        [it for it in pending_remote if it["size_bytes"] >= 256 * 1024 * 1024],
        key=lambda x: x["size_bytes"],
        reverse=True,
    )
    small_items = sorted(
        [it for it in pending_remote if it["size_bytes"] < 256 * 1024 * 1024],
        key=lambda x: x["size_bytes"],
        reverse=True,
    )

    try:
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as giant_pool, \
             concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(4, len(small_items) or 1))) as small_pool:
            for it in giant_items:
                futures.append(giant_pool.submit(_download_single_wheel, it))
            for it in small_items:
                futures.append(small_pool.submit(_download_single_wheel, it))
            for fut in concurrent.futures.as_completed(futures):
                fut.result()
    finally:
        for sess in created_sessions:
            try:
                sess.close()
            except Exception:
                pass

    return wheel_paths, total_network_bytes


def inspect_wheels_unpacked_manifest(wheel_paths: list[str]) -> tuple[int, set[str]]:
    """
    Lê o Central Directory ZIP de todos os wheels locais para obter:
    1. O tamanho exato total descompactado em bytes (`sum(zi.file_size)`).
    2. O conjunto exato de diretórios/arquivos raiz que serão gravados em `site-packages`.
    """
    total_unpacked = 0
    top_entries: set[str] = set()

    for whl in wheel_paths:
        if not whl or not os.path.isfile(whl):
            continue
        try:
            with zipfile.ZipFile(whl, "r") as zf:
                for zi in zf.infolist():
                    if zi.is_dir():
                        continue
                    total_unpacked += max(0, int(zi.file_size))
                    norm = zi.filename.replace("\\", "/").lstrip("/")
                    if not norm:
                        continue
                    parts = norm.split("/")
                    first = parts[0]
                    if first.endswith(".data") and len(parts) >= 3 and parts[1] in ("purelib", "platlib"):
                        top_entries.add(parts[2])
                    elif not first.endswith(".data"):
                        top_entries.add(first)
        except Exception:
            continue

    return total_unpacked, top_entries


def measure_site_packages_entries_bytes(
    site_packages_dir: str,
    top_entries: set[str],
    stop_event: threading.Event = None,
) -> tuple[int, str]:
    """
    Mede em profundidade total (sem truncar `depth < 2`) os bytes físicos reais dos pacotes
    do manifesto em `site-packages`, ignorando `__pycache__`.

    Retorna `(total_bytes, newest_pkg_name)`.
    """
    if not site_packages_dir or not os.path.isdir(site_packages_dir) or not top_entries:
        return 0, ""

    total_b = 0
    newest_pkg = ""
    newest_mtime = 0.0
    stack: list[str] = []

    for entry_name in top_entries:
        if stop_event is not None and stop_event.is_set():
            break
        full_p = os.path.join(site_packages_dir, entry_name)
        try:
            st = os.lstat(full_p)
        except OSError:
            continue
        if os.path.isdir(full_p):
            stack.append(full_p)
            if not entry_name.endswith(".dist-info") and st.st_mtime > newest_mtime:
                newest_mtime = st.st_mtime
                newest_pkg = entry_name
        else:
            total_b += st.st_size

    while stack:
        if stop_event is not None and stop_event.is_set():
            break
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name == "__pycache__":
                                continue
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total_b += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue

    return total_b, newest_pkg
