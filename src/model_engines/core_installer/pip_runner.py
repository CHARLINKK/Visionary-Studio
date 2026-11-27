import codecs
import os
import re
import shutil
import subprocess
import sys
import threading
import time

from src.config import get_app_data_dir, is_test_environment
from src.model_engines.core_installer.dependency_probe import _cache_lock
from src.model_engines.core_installer.wheelhouse_plan import (
    download_wheelhouse_plan,
    inspect_wheels_unpacked_manifest,
    measure_site_packages_entries_bytes,
    resolve_pip_install_plan,
)

MONITORED_DIRS = [
    "torch",
    "torchvision",
    "transformers",
    "ultralytics",
    "scipy",
    "cv2",
    "numpy",
    "sympy",
    "PIL",
    "timm",
    "tokenizers",
    "safetensors",
    "huggingface_hub",
    "accelerate",
    "einops",
    "networkx",
    "fsspec",
]


def _read_lines_or_cr(stream):
    """
    Gerador que divide o stream de stdout do pip tanto por quebras de linha (\\n) quanto por Carriage Return (\\r).
    """
    buf = ""
    raw_buf = getattr(stream, "buffer", None)
    has_read1 = raw_buf is not None and hasattr(raw_buf, "read1")
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace") if has_read1 else None
    while True:
        if has_read1:
            raw_chunk = raw_buf.read1(4096)
            chunk = decoder.decode(raw_chunk, final=not raw_chunk) if raw_chunk else decoder.decode(b"", final=True)
        else:
            raw_chunk = None
            chunk = stream.read(1) if hasattr(stream, "read") else ""
        if not chunk and (not has_read1 or not raw_chunk):
            if buf.strip():
                yield buf.strip()
            break
        buf += chunk
        while "\r" in buf or "\n" in buf:
            ir = buf.find("\r")
            in_ = buf.find("\n")
            if ir != -1 and (in_ == -1 or ir < in_):
                l = buf[:ir]
                buf = buf[ir + 1 :]
                if buf.startswith("\n"):
                    buf = buf[1:]
                if l.strip():
                    yield l.strip()
            else:
                l = buf[:in_]
                buf = buf[in_ + 1 :]
                if l.strip():
                    yield l.strip()


def _scan_extraction_metrics(
    sp_dir: str,
    target_pkgs: list[str],
    stop_monitor: threading.Event,
) -> tuple[int, int, int, int, str]:
    """
    Varre a pasta site-packages em profundidade total (sem truncar `depth < 2`)
    medindo os bytes físicos realmente gravados durante o `pip install` no modo fallback.
    """
    total_b = 0
    py_cnt = 0
    pyc_cnt = 0
    done_pkgs = 0
    newest_pkg = ""
    newest_mtime = 0.0
    if not os.path.isdir(sp_dir):
        return 0, 0, 0, 0, ""

    stack = []
    seen_roots = set()
    norm_targets = {re.sub(r"[-_.]+", "_", p.lower()) for p in (target_pkgs or [])}

    for d_name in MONITORED_DIRS:
        d_full = os.path.join(sp_dir, d_name)
        if os.path.isdir(d_full):
            norm_p = os.path.normcase(os.path.abspath(d_full))
            if norm_p not in seen_roots:
                seen_roots.add(norm_p)
                stack.append(d_full)
            try:
                mt = os.stat(d_full).st_mtime
                if mt > newest_mtime:
                    newest_mtime = mt
                    newest_pkg = d_name
            except OSError:
                pass

    try:
        with os.scandir(sp_dir) as top_it:
            for entry in top_it:
                if entry.is_dir(follow_symlinks=False):
                    en = entry.name
                    if en.endswith(".libs") or (norm_targets and re.sub(r"[-_.]+", "_", en.lower()) in norm_targets):
                        norm_p = os.path.normcase(os.path.abspath(entry.path))
                        if norm_p not in seen_roots:
                            seen_roots.add(norm_p)
                            stack.append(entry.path)
                    elif norm_targets and en.endswith(".dist-info"):
                        prefix = re.sub(r"[-_.]+", "_", en.split("-")[0].lower())
                        if prefix in norm_targets and os.path.isfile(os.path.join(entry.path, "RECORD")):
                            done_pkgs += 1
    except OSError:
        pass

    while stack:
        if stop_monitor.is_set():
            break
        cur_dir = stack.pop()
        in_pycache = os.path.basename(cur_dir) == "__pycache__"
        try:
            with os.scandir(cur_dir) as it:
                for entry in it:
                    try:
                        ename = entry.name
                        if entry.is_dir(follow_symlinks=False):
                            if ename in ("include", "share", "test", "tests"):
                                continue
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            if ename.endswith(".pyc"):
                                pyc_cnt += 1
                            elif not in_pycache:
                                total_b += entry.stat(follow_symlinks=False).st_size
                                if ename.endswith(".py"):
                                    py_cnt += 1
                    except OSError:
                        pass
        except OSError:
            pass

    return total_b, py_cnt, pyc_cnt, done_pkgs, newest_pkg


def _estimate_wheel_bytes(wheel_name: str, is_cuda: bool) -> int:
    w_lower = (wheel_name or "").lower()
    if w_lower.startswith("torch-") or w_lower.startswith("torch_"):
        return int((2550 if is_cuda else 180) * 1024 * 1024)
    if "torchvision" in w_lower:
        return int(24 * 1024 * 1024)
    if "opencv" in w_lower:
        return int(62 * 1024 * 1024)
    if "scipy" in w_lower:
        return int(42 * 1024 * 1024)
    if "numpy" in w_lower:
        return int(16 * 1024 * 1024)
    if "transformers" in w_lower:
        return int(11 * 1024 * 1024)
    if "sympy" in w_lower:
        return int(6 * 1024 * 1024)
    if "pillow" in w_lower:
        return int(5 * 1024 * 1024)
    if "ultralytics" in w_lower or "timm" in w_lower or "tokenizers" in w_lower:
        return int(4 * 1024 * 1024)
    return int(3 * 1024 * 1024)


def _estimate_unpacked_mb(pkg_list: list[str], is_cuda: bool, default_extract_mb: float) -> float:
    if not pkg_list:
        return default_extract_mb
    est = 0.0
    for pkg in pkg_list:
        pl = pkg.lower()
        if pl == "torch":
            est += 4850.0 if is_cuda else 450.0
        elif pl == "torchvision":
            est += 65.0
        elif "opencv" in pl:
            est += 140.0
        elif pl == "scipy":
            est += 130.0
        elif pl == "transformers":
            est += 55.0
        elif pl == "numpy":
            est += 45.0
        elif pl == "sympy":
            est += 68.0
        elif pl in ("ultralytics", "timm", "pillow", "accelerate", "huggingface-hub", "huggingface_hub"):
            est += 18.0
        else:
            est += 5.0
    return max(120.0, est)


def _short_pkg_name(raw_name: str) -> str:
    if not raw_name:
        return "PyTorch"
    base = raw_name.split("-")[0].replace("_", "-")
    return base[:14]


def _fmt_size_pair(cur_mb: float, tot_mb: float) -> str:
    if tot_mb >= 1024.0:
        return f"{cur_mb / 1024.0:.2f}/{tot_mb / 1024.0:.2f} GB"
    return f"{cur_mb:.0f}/{tot_mb:.0f} MB"


def _compile_hot_packages_pyc(installer, site_packages_dir: str, start_pct: float = 95.0, end_pct: float = 99.5):
    """Compila `.pyc` em paralelo com progresso exato (done_py / total_py)."""
    try:
        import concurrent.futures
        import importlib.util
        import py_compile

        hot_pkgs = (
            "torch",
            "torchvision",
            "transformers",
            "ultralytics",
            "timm",
            "einops",
            "accelerate",
            "huggingface_hub",
        )
        skip_dirs = {"__pycache__", "include", "share", "test", "tests", "testing", "codegen"}

        pending_py = []
        if os.path.isdir(site_packages_dir) and not is_test_environment():
            for hp in hot_pkgs:
                hp_root = os.path.join(site_packages_dir, hp)
                if not os.path.isdir(hp_root):
                    continue
                for r_dir, sub_dirs, f_names in os.walk(hp_root):
                    sub_dirs[:] = [d for d in sub_dirs if d not in skip_dirs]
                    for fn in f_names:
                        if fn.endswith(".py"):
                            py_p = os.path.join(r_dir, fn)
                            try:
                                pyc_p = importlib.util.cache_from_source(py_p)
                                if not os.path.isfile(pyc_p):
                                    pending_py.append(py_p)
                            except Exception:
                                pending_py.append(py_p)

        total_py = len(pending_py)
        if total_py > 0:
            workers = min(8, max(2, os.cpu_count() or 4))

            def _compile_one(fp: str) -> bool:
                try:
                    py_compile.compile(fp, doraise=False, optimize=0)
                    return True
                except Exception:
                    return False

            done_py = 0
            span = max(0.5, end_pct - start_pct)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                for _ in pool.map(_compile_one, pending_py, chunksize=16):
                    done_py += 1
                    if done_py % 32 == 0 or done_py == total_py:
                        comp_pct = round(start_pct + (done_py / total_py) * span, 1)
                        with installer._get_lock():
                            prog = installer._get_install_progress()
                            prog["percent"] = min(end_pct, max(float(prog.get("percent", start_pct)), comp_pct))
                            prog["message"] = f"Compilando · {done_py}/{total_py} mód."
                        installer.notify_progress(throttle_interval=0.12)
    except Exception:
        pass


def _invalidate_ai_module_caches():
    with _cache_lock:
        import importlib

        has_loaded_c_ext = "torch._C" in sys.modules
        for mod_name in list(sys.modules.keys()):
            if not has_loaded_c_ext and (mod_name == "torch" or mod_name.startswith("torch.")):
                sys.modules.pop(mod_name, None)
            elif mod_name in ("transformers", "ultralytics", "einops", "timm"):
                sys.modules.pop(mod_name, None)
        sys.path_importer_cache.clear()
        importlib.invalidate_caches()
        for eng_mod_name in (
            "src.model_engines.florence_ocr_engine",
            "src.model_engines.yolo_layout_engine",
        ):
            eng_mod = sys.modules.get(eng_mod_name)
            if eng_mod is not None and type(getattr(eng_mod, "torch", None)).__name__ == "_TorchFallback":
                try:
                    importlib.reload(eng_mod)
                except Exception:
                    pass


def _run_deterministic_wheelhouse_install(
    installer,
    python_exe: str,
    pip_cmd: list[str],
    pip_env: dict,
    site_packages_dir: str,
    is_cuda: bool,
    stop_monitor: threading.Event,
) -> tuple[bool, int | None, str | None]:
    """
    Executa instalação determinística em 3 fases exatas:
    1. Resolução via `pip install --dry-run --report <json>` + `HEAD` paralelo (0% -> 3%)
    2. Download exato por wheel com Parallel Range 206 + SHA-256 (3% -> 75%)
    3. Extração offline (`--no-index --no-deps`) medida contra tamanho descompactado exato dos ZIPs (75% -> 95%)

    Retorna `(used_wheelhouse, returncode, wheelhouse_dir)`.
    Se `used_wheelhouse` for False, o caller deve executar o fallback padrão do pip (podendo reutilizar `wheelhouse_dir`).
    """
    with installer._get_lock():
        prog = installer._get_install_progress()
        prog["message"] = "Resolvendo pacotes PyTorch..."
    installer.notify_progress(throttle_interval=0.0)

    plan = resolve_pip_install_plan(python_exe, pip_cmd, env=pip_env, timeout=90)
    if plan is None:
        return False, None, None

    if plan.get("all_satisfied"):
        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["percent"] = 95.0
            prog["message"] = "Dependências já presentes. Otimizando..."
        installer.notify_progress(throttle_interval=0.0)
        return True, 0, None

    items = plan.get("items") or []
    total_dl_bytes = int(plan.get("total_download_bytes", 0) or 0)

    wheelhouse_dir = os.path.join(get_app_data_dir(), "cache", "pip_wheelhouse")
    os.makedirs(wheelhouse_dir, exist_ok=True)

    with installer._get_lock():
        prog = installer._get_install_progress()
        prog["percent"] = max(float(prog.get("percent", 0.0)), 3.0)
        prog["downloaded_bytes"] = 0
        prog["total_bytes"] = total_dl_bytes
        prog["speed_mbps"] = 0.0
        prog["eta_seconds"] = 0
        prog["log"] += f"Plano determinístico resolvido: {len(items)} wheels ({total_dl_bytes / (1024 * 1024):.1f} MB).\n"
        prog["message"] = f"Baixando {len(items)} pacotes..."
    installer.notify_progress(throttle_interval=0.0)

    def _on_wheel_progress(cur_bytes: int, tot_bytes: int, active_pkg: str):
        ratio = min(1.0, cur_bytes / tot_bytes) if tot_bytes > 0 else 1.0
        calc_pct = round(3.0 + (ratio * 72.0), 1)
        with installer._get_lock():
            p = installer._get_install_progress()
            if p.get("status") != "installing":
                return
            p["downloaded_bytes"] = max(int(p.get("downloaded_bytes", 0)), cur_bytes)
            p["total_bytes"] = tot_bytes
            p["percent"] = max(float(p.get("percent", 3.0)), min(75.0, calc_pct))
            p["speed_mbps"] = 0.0
            p["eta_seconds"] = 0
            p["message"] = f"Baixando {_short_pkg_name(active_pkg)}..."
        installer.notify_progress(throttle_interval=0.1)

    try:
        wheel_paths, network_bytes = download_wheelhouse_plan(
            items,
            wheelhouse_dir=wheelhouse_dir,
            on_progress=_on_wheel_progress,
        )
    except Exception as dl_err:
        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["log"] += f"\n[Fallback] Download direto interrompido ({dl_err}); retomando via pip...\n"
        return False, None, wheelhouse_dir

    # Fase 2: Lê o Central Directory ZIP de cada wheel para saber o tamanho EXATO descompactado
    exact_unpacked_bytes, top_entries = inspect_wheels_unpacked_manifest(wheel_paths)
    extract_start_pct = 75.0 if network_bytes > 0 else 5.0
    extract_end_pct = 95.0
    accel_tag = "CUDA" if is_cuda else "CPU"

    base_extract_bytes, _ = measure_site_packages_entries_bytes(site_packages_dir, top_entries, stop_monitor)

    with installer._get_lock():
        prog = installer._get_install_progress()
        prog["percent"] = max(float(prog.get("percent", 0.0)), extract_start_pct)
        if total_dl_bytes > 0:
            prog["downloaded_bytes"] = total_dl_bytes
        prog["speed_mbps"] = 0.0
        prog["eta_seconds"] = 0
        prog["message"] = f"Descompactando pacotes {accel_tag}..."
    installer.notify_progress(throttle_interval=0.0)

    offline_cmd = [
        python_exe,
        "-u",
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        "--disable-pip-version-check",
        "--find-links",
        wheelhouse_dir,
        *wheel_paths,
    ]

    ext_stop = threading.Event()

    def _extract_monitor():
        tot_mb = exact_unpacked_bytes / (1024 * 1024) if exact_unpacked_bytes > 0 else 0.0
        span = max(1.0, extract_end_pct - extract_start_pct)
        while not ext_stop.is_set() and not stop_monitor.is_set():
            cur_b, active_pkg = measure_site_packages_entries_bytes(site_packages_dir, top_entries, ext_stop)
            delta_b = max(0, cur_b - base_extract_bytes)
            if exact_unpacked_bytes > 0:
                ratio = min(1.0, delta_b / exact_unpacked_bytes)
                calc_pct = round(extract_start_pct + (ratio * span), 1)
            else:
                calc_pct = extract_start_pct

            with installer._get_lock():
                p = installer._get_install_progress()
                if p.get("status") != "installing":
                    break
                new_pct = min(extract_end_pct, max(float(p.get("percent", extract_start_pct)), calc_pct))
                p["percent"] = new_pct
                p["speed_mbps"] = 0.0
                p["eta_seconds"] = 0
                delta_mb = delta_b / (1024 * 1024)
                if tot_mb > 0 and delta_mb >= 1.0:
                    pkg_hint = active_pkg[:12] if active_pkg else accel_tag
                    p["message"] = f"Descompactando {pkg_hint} · {_fmt_size_pair(min(delta_mb, tot_mb), tot_mb)}"
            installer.notify_progress(throttle_interval=0.15)
            if ext_stop.wait(0.35):
                break

    ext_thread = threading.Thread(target=_extract_monitor, daemon=True)
    ext_thread.start()

    try:
        proc = subprocess.Popen(
            offline_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            universal_newlines=True,
            env=pip_env,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        for line_str in _read_lines_or_cr(proc.stdout):
            with installer._get_lock():
                prog = installer._get_install_progress()
                prog["log"] += line_str + "\n"
        proc.wait()
        rc = proc.returncode
    finally:
        ext_stop.set()
        ext_thread.join(timeout=0.6)

    if rc == 0:
        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["percent"] = max(float(prog.get("percent", 0.0)), extract_end_pct)
            prog["message"] = "Otimizando módulos neurais..."
        installer.notify_progress(throttle_interval=0.0)
        # Limpa wheels do cache temporário após instalação bem-sucedida para não desperdiçar espaço
        try:
            shutil.rmtree(wheelhouse_dir, ignore_errors=True)
        except Exception:
            pass
        return True, 0, None

    # Se o modo offline falhou por alguma peculiaridade de ambiente, deixa o caller cair no fallback usando wheelhouse
    with installer._get_lock():
        prog = installer._get_install_progress()
        prog["log"] += f"\n[Fallback] Instalação offline retornou código {rc}; tentando fluxo padrão do pip...\n"
    return False, rc, wheelhouse_dir


def run_pip_install_worker(installer):
    """
    Worker assíncrono executado em thread dedicada para instalação do motor de IA (PyTorch Core).

    ESTRATÉGIA PADRÃO OURO DE ACURÁCIA DE PORCENTAGEM:
    1. Caminho Primário Determinístico (Wheelhouse):
       Resolve o grafo exato via `pip --dry-run --report`, mede o tamanho exato de cada `.whl`,
       baixa com contabilidade exata por arquivo (3% -> 75%) e extrai offline medindo bytes reais
       contra o tamanho descompactado exato dos ZIPs (75% -> 95%), seguido de compilação `.pyc` (95% -> 99.5%).
    2. Fallback Compatível (Pip Stream Corrigido):
       Caso o ambiente tenha sdists ou bloqueie `--dry-run`, usa `pip install` com `PIP_PROGRESS_BAR=raw`,
       sem drift temporal artificial e sem o bug de salto imediato por wheel pequeno.
    """
    base_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
    req_path = os.path.join(base_dir, "requirements-ai.txt")
    if not os.path.isfile(req_path):
        req_path = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "requirements-ai.txt")
        )

    exe = sys.executable
    exe_dir = os.path.dirname(exe)
    python_exe = os.path.join(exe_dir, "python.exe")
    if not os.path.isfile(python_exe):
        python_exe = exe

    tmp_req_file = None
    stop_monitor = threading.Event()
    monitor_thread = None
    try:
        pip_cmd, tmp_req_file = installer._build_pip_install_args(python_exe, req_path)
        mode_label = "CPU / Compatibilidade" if tmp_req_file else "GPU CUDA"
        with installer._get_lock():
            progress = installer._get_install_progress()
            progress["log"] += f"\nBaixando PyTorch ({mode_label}) e demais módulos de IA (Florence, YOLO)..."
            progress["log"] += "\nPor favor aguarde, o pacote pode demorar vários minutos...\n\n"
            progress["percent"] = 0.0
            progress["speed_mbps"] = 0.0
            progress["eta_seconds"] = 0
            progress["message"] = "Resolvendo pacotes PyTorch..."
        installer.notify_progress(throttle_interval=0.0)

        cuda_target = installer._detect_cuda_target()
        is_cuda = cuda_target != "cpu"
        total_expected_dl = int(2850 * 1024 * 1024) if is_cuda else int(235 * 1024 * 1024)
        default_extract_mb = 5050.0 if is_cuda else 620.0

        site_packages_dir = os.path.join(exe_dir, "Lib", "site-packages")
        if not os.path.isdir(site_packages_dir):
            alt_sp = os.path.join(os.path.dirname(exe_dir), "Lib", "site-packages")
            if os.path.isdir(alt_sp):
                site_packages_dir = alt_sp

        pip_env = os.environ.copy()
        pip_env["PYTHONUNBUFFERED"] = "1"
        pip_env["PYTHONIOENCODING"] = "utf-8"
        pip_env["PIP_PROGRESS_BAR"] = "raw"
        pip_env["PIP_NO_COMPILE"] = "1"

        use_wheelhouse = (not is_test_environment()) or (
            os.environ.get("VISIONARY_ENABLE_WHEELHOUSE_IN_TESTS") == "1"
        )
        fallback_find_links = None
        if use_wheelhouse:
            used_wh, wh_rc, fallback_find_links = _run_deterministic_wheelhouse_install(
                installer=installer,
                python_exe=python_exe,
                pip_cmd=pip_cmd,
                pip_env=pip_env,
                site_packages_dir=site_packages_dir,
                is_cuda=is_cuda,
                stop_monitor=stop_monitor,
            )
            if used_wh and wh_rc == 0:
                _compile_hot_packages_pyc(installer, site_packages_dir, start_pct=95.0, end_pct=99.5)
                _invalidate_ai_module_caches()
                with installer._get_lock():
                    prog = installer._get_install_progress()
                    prog["status"] = "completed"
                    prog["percent"] = 100.0
                    if prog.get("total_bytes", 0) > 0:
                        prog["downloaded_bytes"] = prog["total_bytes"]
                    prog["speed_mbps"] = 0.0
                    prog["eta_seconds"] = 0
                    prog["log"] += "\nInstalação concluída com sucesso! Você já pode usar a Inteligência Artificial."
                    prog["message"] = "Instalação concluída com sucesso!"
                installer.notify_progress(throttle_interval=0.0)
                return

        # ── Fallback Compatível (Pip Stream sem drift artificial e sem bug de salto) ──
        base_bytes, base_py, base_pyc, _, _ = _scan_extraction_metrics(site_packages_dir, [], stop_monitor)

        effective_pip_cmd = list(pip_cmd)
        if fallback_find_links and os.path.isdir(fallback_find_links):
            try:
                inst_idx = effective_pip_cmd.index("install")
                effective_pip_cmd[inst_idx + 1 : inst_idx + 1] = ["--find-links", fallback_find_links]
            except ValueError:
                pass

        process = subprocess.Popen(
            effective_pip_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            universal_newlines=True,
            env=pip_env,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )

        state_meta = {
            "stage": "init",
            "pct": 0.0,
            "wheel_name": None,
            "packages_to_install": [],
            "expected_extract_mb": default_extract_mb,
            "target_dl_bytes": 0,
        }
        completed_wheels: dict[str, int] = {}
        wheel_totals: dict[str, int] = {}

        def _progress_monitor_worker():
            last_scan_ts = 0.0
            delta_mb = 0.0
            done_pkgs = 0
            active_pkg = ""

            while not stop_monitor.is_set():
                now_ts = time.time()
                cur_stage = state_meta["stage"]

                should_scan_disk = cur_stage == "installing" and (now_ts - last_scan_ts >= 0.5)
                if should_scan_disk:
                    last_scan_ts = now_ts
                    cur_b, cur_py, cur_pyc, cur_done, cur_pkg = _scan_extraction_metrics(
                        site_packages_dir, state_meta["packages_to_install"], stop_monitor
                    )
                    delta_mb = max(0.0, (cur_b - base_bytes) / (1024 * 1024))
                    delta_py = max(0, cur_py - base_py)
                    delta_pyc = max(0, cur_pyc - base_pyc)
                    done_pkgs = cur_done
                    if cur_pkg:
                        active_pkg = cur_pkg

                    with installer._get_lock():
                        p = installer._get_install_progress()
                        if p.get("status") != "installing":
                            break
                        cur_pct = float(p.get("percent", 75.0))
                        exp_mb = max(120.0, float(state_meta["expected_extract_mb"]))
                        eff_tot_mb = max(exp_mb, delta_mb)
                        unpack_ratio = min(1.0, delta_mb / eff_tot_mb) if eff_tot_mb > 0 else 0.0
                        pyc_ratio = min(1.0, delta_pyc / max(50, delta_py)) if delta_py >= 50 else 0.0
                        pkg_total = len(state_meta["packages_to_install"])
                        pkg_ratio = min(1.0, done_pkgs / pkg_total) if pkg_total > 0 else 0.0

                        # 100% baseado em bytes físicos reais + .pyc reais + pacotes concluídos (ZERO drift artificial!)
                        physical_pct = round(75.0 + (unpack_ratio * 16.0) + (pyc_ratio * 2.0) + (pkg_ratio * 2.0), 1)
                        new_pct = min(95.0, max(cur_pct, physical_pct))
                        p["percent"] = new_pct
                        state_meta["pct"] = new_pct
                        p["speed_mbps"] = 0.0
                        p["eta_seconds"] = 0

                        accel_tag = "CUDA" if is_cuda else "CPU"
                        pkg_hint = active_pkg[:12] if active_pkg else accel_tag
                        if delta_pyc > 0 and pyc_ratio < 0.98:
                            tot_files = max(delta_pyc, delta_py)
                            p["message"] = f"Compilando · {delta_pyc}/{tot_files} mód."
                        elif delta_mb >= 4.0 and new_pct < 94.5:
                            sz_str = _fmt_size_pair(min(delta_mb, eff_tot_mb), eff_tot_mb)
                            p["message"] = f"Descompactando {pkg_hint} · {sz_str}"
                        elif pkg_total > 0 and done_pkgs > 0:
                            p["message"] = f"Registrando · {min(done_pkgs, pkg_total)}/{pkg_total} pacotes"

                    installer.notify_progress(throttle_interval=0.2)

                if stop_monitor.wait(0.25):
                    break

        monitor_thread = threading.Thread(target=_progress_monitor_worker, daemon=True)
        monitor_thread.start()

        for line_str in _read_lines_or_cr(process.stdout):
            with installer._get_lock():
                prog = installer._get_install_progress()
                prog["log"] += line_str + "\n"
                current_pct = float(prog.get("percent", state_meta["pct"]))

                if "Collecting " in line_str:
                    pkg_part = line_str.split("Collecting")[-1].strip().split()[0]
                    if state_meta["stage"] in ("init", "collecting"):
                        state_meta["stage"] = "collecting"
                    prog["message"] = f"Verificando dependência: {pkg_part[:18]}"

                dl_match = re.search(
                    r"Downloading\s+.*?([a-zA-Z0-9_\-\.%]+?-(?:\d+[\.\d]*).*?\.whl)(?:\s*\(([\d\.]+)\s*(GB|MB|kB)\))?",
                    line_str,
                    re.IGNORECASE,
                )
                if dl_match:
                    raw_dl_name = dl_match.group(1).replace("%2B", "+")
                    state_meta["wheel_name"] = raw_dl_name
                    state_meta["stage"] = "downloading"
                    if dl_match.group(2) and dl_match.group(3):
                        d_val = float(dl_match.group(2))
                        d_unit = dl_match.group(3).upper()
                        d_mul = 1024 * 1024 * 1024 if d_unit == "GB" else (1024 if d_unit == "KB" else 1024 * 1024)
                        wheel_totals[raw_dl_name] = max(wheel_totals.get(raw_dl_name, 0), int(d_val * d_mul))

                cached_match = re.search(
                    r"Using cached\s+.*?([a-zA-Z0-9_\-\.%]+?-(?:\d+[\.\d]*).*?\.whl)(?:\s*\(([\d\.]+)\s*(MB|GB|kB)\))?",
                    line_str,
                    re.IGNORECASE,
                )
                if cached_match:
                    raw_name = cached_match.group(1).replace("%2B", "+")
                    state_meta["wheel_name"] = raw_name
                    state_meta["stage"] = "cached_extracting"
                    if cached_match.group(2) and cached_match.group(3):
                        c_val = float(cached_match.group(2))
                        c_unit = cached_match.group(3).upper()
                        c_mul = 1024 * 1024 * 1024 if c_unit == "GB" else (1024 if c_unit == "KB" else 1024 * 1024)
                        c_bytes = int(c_val * c_mul)
                    else:
                        c_bytes = _estimate_wheel_bytes(raw_name, is_cuda)

                    wheel_totals[raw_name] = max(wheel_totals.get(raw_name, 0), c_bytes)
                    completed_wheels[raw_name] = max(completed_wheels.get(raw_name, 0), c_bytes)
                    total_dl = sum(completed_wheels.values())
                    known_tot = max(total_expected_dl, sum(wheel_totals.values()), total_dl)
                    state_meta["target_dl_bytes"] = total_dl
                    prog["total_bytes"] = known_tot
                    prog["downloaded_bytes"] = max(int(prog.get("downloaded_bytes", 0)), total_dl)
                    dl_ratio = min(1.0, total_dl / known_tot) if known_tot > 0 else 0.0
                    current_pct = max(current_pct, round(3.0 + (dl_ratio * 72.0), 1))
                    prog["speed_mbps"] = 0.0
                    prog["eta_seconds"] = 0
                    prog["message"] = f"Carregando cache · {_short_pkg_name(raw_name)}"

                raw_prog_match = re.search(r"Progress\s+(\d+)\s+of\s+(\d+)", line_str)
                mb_match = re.search(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\s*(GB|MB|kB)", line_str, re.IGNORECASE)

                if raw_prog_match:
                    state_meta["stage"] = "downloading"
                    cur_bytes = int(raw_prog_match.group(1))
                    tot_bytes = int(raw_prog_match.group(2))
                    wheel_key = state_meta["wheel_name"] or f"wheel_{len(completed_wheels)}"
                    wheel_totals[wheel_key] = max(wheel_totals.get(wheel_key, 0), tot_bytes)
                    completed_wheels[wheel_key] = min(
                        wheel_totals[wheel_key],
                        max(completed_wheels.get(wheel_key, 0), cur_bytes),
                    )
                    total_dl = sum(completed_wheels.values())
                    known_tot = max(total_expected_dl, sum(wheel_totals.values()), total_dl)
                    state_meta["target_dl_bytes"] = max(state_meta["target_dl_bytes"], total_dl)
                    prog["downloaded_bytes"] = max(int(prog.get("downloaded_bytes", 0)), total_dl)
                    prog["total_bytes"] = known_tot
                    prog["speed_mbps"] = 0.0
                    prog["eta_seconds"] = 0
                    dl_ratio = min(1.0, prog["downloaded_bytes"] / known_tot) if known_tot > 0 else 0.0
                    current_pct = max(current_pct, round(3.0 + (dl_ratio * 72.0), 1))

                elif mb_match:
                    state_meta["stage"] = "downloading"
                    cur_val = float(mb_match.group(1))
                    tot_val = float(mb_match.group(2))
                    unit = mb_match.group(3).upper()
                    mul = 1024 * 1024 * 1024 if unit == "GB" else (1024 if unit == "KB" else 1024 * 1024)
                    cur_bytes = int(cur_val * mul)
                    tot_bytes = int(tot_val * mul)

                    wheel_key = state_meta["wheel_name"] or f"wheel_{len(completed_wheels)}"
                    wheel_totals[wheel_key] = max(wheel_totals.get(wheel_key, 0), tot_bytes)
                    completed_wheels[wheel_key] = min(
                        wheel_totals[wheel_key],
                        max(completed_wheels.get(wheel_key, 0), cur_bytes),
                    )
                    total_dl = sum(completed_wheels.values())
                    known_tot = max(total_expected_dl, sum(wheel_totals.values()), total_dl)
                    state_meta["target_dl_bytes"] = max(state_meta["target_dl_bytes"], total_dl)
                    prog["downloaded_bytes"] = max(int(prog.get("downloaded_bytes", 0)), total_dl)
                    prog["total_bytes"] = known_tot
                    prog["speed_mbps"] = 0.0
                    prog["eta_seconds"] = 0
                    dl_ratio = min(1.0, prog["downloaded_bytes"] / known_tot) if known_tot > 0 else 0.0
                    current_pct = max(current_pct, round(3.0 + (dl_ratio * 72.0), 1))

                if "Downloading" in line_str:
                    state_meta["stage"] = "downloading"
                    if state_meta["wheel_name"]:
                        prog["message"] = f"Baixando {_short_pkg_name(state_meta['wheel_name'])}..."
                elif "Installing collected packages" in line_str:
                    raw_pkgs = line_str.split("Installing collected packages:")[-1]
                    pkg_list = [p.strip() for p in raw_pkgs.split(",") if p.strip()]
                    state_meta["packages_to_install"] = pkg_list
                    state_meta["expected_extract_mb"] = _estimate_unpacked_mb(pkg_list, is_cuda, default_extract_mb)
                    state_meta["stage"] = "installing"
                    current_pct = max(current_pct, 75.0)
                    if state_meta["target_dl_bytes"] > 0:
                        prog["downloaded_bytes"] = max(
                            int(prog.get("downloaded_bytes", 0)), state_meta["target_dl_bytes"]
                        )
                    prog["speed_mbps"] = 0.0
                    prog["eta_seconds"] = 0
                    accel_tag = "CUDA" if is_cuda else "CPU"
                    prog["message"] = f"Descompactando pacotes {accel_tag}..."
                elif "Successfully installed" in line_str:
                    state_meta["stage"] = "finalizing"
                    current_pct = max(current_pct, 95.0)
                    prog["speed_mbps"] = 0.0
                    prog["eta_seconds"] = 0
                    prog["message"] = "Otimizando módulos neurais..."

                prog["percent"] = min(99.0, current_pct)
                state_meta["pct"] = prog["percent"]
                if (
                    state_meta["stage"] not in ("installing", "finalizing")
                    and "Installing collected packages" not in line_str
                    and "Successfully installed" not in line_str
                ):
                    if "Using cached" in line_str and state_meta["wheel_name"]:
                        prog["message"] = f"Carregando cache · {_short_pkg_name(state_meta['wheel_name'])}"
                    elif "Downloading" in line_str and state_meta["wheel_name"]:
                        prog["message"] = f"Baixando {_short_pkg_name(state_meta['wheel_name'])}..."
                    elif "Collecting" in line_str:
                        pkg_part = line_str.split("Collecting")[-1].strip().split()[0]
                        prog["message"] = f"Verificando dependência: {pkg_part[:18]}"
                    elif "Requirement already satisfied" in line_str:
                        req_part = line_str.split("Requirement already satisfied:")[-1].strip().split()[0]
                        prog["message"] = f"Dependência já presente: {req_part[:16]}"
            installer.notify_progress(throttle_interval=0.1)

        process.wait()
        stop_monitor.set()
        monitor_thread.join(timeout=0.5)
        if process.returncode == 0:
            _compile_hot_packages_pyc(installer, site_packages_dir, start_pct=95.0, end_pct=99.5)
            _invalidate_ai_module_caches()
            if fallback_find_links and os.path.isdir(fallback_find_links):
                try:
                    shutil.rmtree(fallback_find_links, ignore_errors=True)
                except Exception:
                    pass
            with installer._get_lock():
                prog = installer._get_install_progress()
                prog["status"] = "completed"
                prog["percent"] = 100.0
                if prog.get("total_bytes", 0) > 0:
                    prog["downloaded_bytes"] = prog["total_bytes"]
                prog["speed_mbps"] = 0.0
                prog["eta_seconds"] = 0
                prog["log"] += "\nInstalação concluída com sucesso! Você já pode usar a Inteligência Artificial."
                prog["message"] = "Instalação concluída com sucesso!"
        else:
            with installer._get_lock():
                prog = installer._get_install_progress()
                prog["status"] = "error"
                prog["speed_mbps"] = 0.0
                prog["eta_seconds"] = 0
                prog["log"] += f"\nErro na instalação (Código {process.returncode}). Verifique os logs."
                prog["message"] = f"Erro na instalação (Código {process.returncode})."
                log_tail = prog["log"][-3000:]
            try:
                from src.utils.logger import get_logger

                get_logger("crash").error(f"[installCoreEngine] pip returncode={process.returncode}\n{log_tail}")
            except Exception:
                pass
        installer.notify_progress(throttle_interval=0.0)
    except Exception as e:
        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["status"] = "error"
            prog["speed_mbps"] = 0.0
            prog["eta_seconds"] = 0
            prog["log"] += f"\nErro fatal: {str(e)}"
            prog["message"] = f"Erro fatal: {str(e)}"
        try:
            import traceback
            from src.utils.logger import get_logger

            get_logger("crash").error(f"[installCoreEngine] Exception: {str(e)}\n{traceback.format_exc()}")
        except Exception:
            pass
        installer.notify_progress(throttle_interval=0.0)
    finally:
        stop_monitor.set()
        if monitor_thread is not None and monitor_thread.is_alive():
            monitor_thread.join(timeout=0.5)
        if tmp_req_file and os.path.exists(tmp_req_file):
            try:
                os.remove(tmp_req_file)
            except Exception:
                pass
