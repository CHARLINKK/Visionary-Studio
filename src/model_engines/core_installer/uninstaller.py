import os
import queue
import subprocess
import sys
import threading
import time

from src.model_engines.core_installer.dependency_probe import _cache_lock


def run_pip_uninstall_worker(installer):
    """
    Worker executado em thread desacoplada para desinstalação segura do PyTorch e módulos CUDA.
    
    DESAFIOS TÉCNICOS ESPECÍFICOS DO WINDOWS:
    1. Travamento de DLLs em RAM (File Locking): O Windows não permite deletar arquivos binários (.dll)
       que estejam carregados na memória do processo ou referenciados por contextos CUDA ativos.
    2. Sequenciamento Defensivo:
       a) Força liberação de memória VRAM e tensores na GPU via driver NVIDIA.
       b) Coleta de lixo CPython (gc.collect()) para destruir referências circulares.
       c) Medição inicial de footprint físico no disco via sensor de bytes.
       d) Subprocesso isolado do pip com captura assíncrona de streams.
       e) Limpeza manual de diretórios residuais 'fantasmas' (~orch*) deixados pelo pip.
       f) Validação se o módulo C nativo (torch._C) foi inicializado antes de limpar sys.modules.
    """
    try:
        # Passo 1: Liberação proativa de contextos CUDA e tensores na placa de vídeo
        try:
            from src.model_engines.hf_download_manager import cleanup_gpu_memory

            cleanup_gpu_memory(force_ipc=True)
        except Exception:
            pass
        import gc

        gc.collect()

        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["percent"] = 15.0
            prog["message"] = "Liberando tensores da GPU..."
            if "torch" in sys.modules:
                prog["log"] += "[Aviso] PyTorch carregado na memória. No Windows, reinicie o Visionary se DLLs estiverem travadas.\n"
        installer.notify_progress(throttle_interval=0.0)

        # Determina o executável Python do runtime embarcado (engine/python.exe)
        exe = sys.executable
        exe_dir = os.path.dirname(exe)
        python_exe = os.path.join(exe_dir, "python.exe")
        if not os.path.isfile(python_exe):
            python_exe = exe

        from src.config import is_test_environment

        # Passo 2: Medição prévia do volume em disco (em bytes) para cálculo de progresso real
        site_dirs_uninst = []
        initial_torch_bytes = 0
        if not is_test_environment():
            try:
                import site

                site_dirs_uninst = list(site.getsitepackages())
                local_sp = os.path.join(exe_dir, "Lib", "site-packages")
                if os.path.isdir(local_sp) and local_sp not in site_dirs_uninst:
                    site_dirs_uninst.append(local_sp)
                initial_torch_bytes = installer._measure_torch_footprint_bytes(site_dirs_uninst)
            except Exception:
                initial_torch_bytes = 0

        # Configuração de variáveis de ambiente para desativar buffer de I/O no subprocesso pip
        uninst_env = os.environ.copy()
        uninst_env["PYTHONUNBUFFERED"] = "1"
        uninst_env["PYTHONIOENCODING"] = "utf-8"

        # Passo 3: Disparo do subprocesso pip uninstall
        # Flag '0x08000000' (CREATE_NO_WINDOW) impede a abertura de janelas pretas no Windows
        cmd = [python_exe, "-u", "-m", "pip", "uninstall", "-y", "torch", "torchvision", "torchaudio"]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=uninst_env,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )

        out_q = queue.Queue()

        # Thread leitora assíncrona: evita deadlocks caso o buffer do pipe do sistema operacional encha
        def _reader():
            try:
                if hasattr(proc.stdout, "readline"):
                    for line in iter(proc.stdout.readline, ""):
                        out_q.put(line)
                else:
                    for line in proc.stdout:
                        out_q.put(line)
            except Exception:
                pass

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()

        current_pct = 20.0
        last_disk_scan = 0.0
        prev_freed_bytes = 0
        prev_scan_ts = time.monotonic()
        del_speed_ema = 0.0

        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["percent"] = current_pct
            prog["message"] = "Removendo ambiente PyTorch..."
        installer.notify_progress(throttle_interval=0.0)

        # Loop principal de monitoramento: combina telemetria de texto do pip com medição real do disco
        while reader_thread.is_alive() or not out_q.empty():
            while not out_q.empty():
                try:
                    line = out_q.get_nowait()
                except queue.Empty:
                    break
                with installer._get_lock():
                    prog = installer._get_install_progress()
                    prog["log"] += line
                    l_lower = line.lower()
                    # Mapeia mensagens do pip para saltos de fase na barra de progresso da UI
                    if "found existing installation" in l_lower:
                        if "torchvision" in l_lower:
                            current_pct = max(current_pct, 74.0)
                            prog["message"] = "Removendo torchvision..."
                        elif "torchaudio" in l_lower:
                            current_pct = max(current_pct, 84.0)
                            prog["message"] = "Removendo torchaudio..."
                        elif "torch" in l_lower:
                            current_pct = max(current_pct, 26.0)
                            prog["message"] = "Removendo pacotes PyTorch..."
                    elif "uninstalling torch-" in l_lower or "uninstalling torch:" in l_lower:
                        current_pct = max(current_pct, 35.0)
                        prog["message"] = "Removendo binários CUDA..."
                    elif "successfully uninstalled torch-" in l_lower or l_lower.strip().endswith(
                        "successfully uninstalled torch"
                    ):
                        current_pct = max(current_pct, 72.0)
                        prog["message"] = "Removendo pacotes auxiliares..."
                    elif "uninstalling torchvision" in l_lower:
                        current_pct = max(current_pct, 78.0)
                        prog["message"] = "Removendo módulo torchvision..."
                    elif "successfully uninstalled torchvision" in l_lower:
                        current_pct = max(current_pct, 86.0)
                        prog["message"] = "Removendo pacotes finais..."
                    elif "uninstalling torchaudio" in l_lower or "skipping torchaudio" in l_lower:
                        current_pct = max(current_pct, 88.0)
                        prog["message"] = "Removendo módulo torchaudio..."
                    prog["percent"] = round(current_pct, 1)

            # Sensor de disco ativo: roda a cada ~300ms para medir bytes físicos liberados
            if reader_thread.is_alive():
                now_m = time.monotonic()
                used_disk_sensor = False
                if initial_torch_bytes > 0 and (now_m - last_disk_scan) >= 0.30:
                    last_disk_scan = now_m
                    rem_bytes = installer._measure_torch_footprint_bytes(site_dirs_uninst)
                    freed_bytes = max(0, initial_torch_bytes - rem_bytes)
                    dt = max(0.05, now_m - prev_scan_ts)
                    if freed_bytes > prev_freed_bytes:
                        # Média móvel exponencial (EMA) para suavizar oscilações na taxa de exclusão (MB/s)
                        inst_mbps = ((freed_bytes - prev_freed_bytes) / (1024 * 1024)) / dt
                        del_speed_ema = inst_mbps if del_speed_ema <= 0 else (0.35 * inst_mbps + 0.65 * del_speed_ema)
                    prev_freed_bytes = freed_bytes
                    prev_scan_ts = now_m

                    if freed_bytes > 0:
                        used_disk_sensor = True
                        freed_ratio = min(1.0, freed_bytes / float(initial_torch_bytes))
                        target_disk_pct = 26.0 + (freed_ratio * 62.5)
                        capped_disk_pct = (
                            min(target_disk_pct, current_pct + 5.5)
                            if rem_bytes == 0 and current_pct < 70.0
                            else target_disk_pct
                        )
                        current_pct = min(88.5, max(current_pct, round(capped_disk_pct, 1)))
                        if initial_torch_bytes >= 1073741824:
                            freed_gb = freed_bytes / 1073741824.0
                            tot_gb = initial_torch_bytes / 1073741824.0
                            msg_disk = f"Removendo · {freed_gb:.2f}/{tot_gb:.2f} GB"
                        else:
                            freed_mb = freed_bytes / 1048576.0
                            tot_mb = initial_torch_bytes / 1048576.0
                            msg_disk = f"Removendo · {freed_mb:.0f}/{tot_mb:.0f} MB"
                        with installer._get_lock():
                            prog = installer._get_install_progress()
                            prog["percent"] = round(current_pct, 1)
                            prog["message"] = msg_disk
                            prog["speed_mbps"] = (
                                round(del_speed_mbps, 1) if (del_speed_mbps := del_speed_ema) > 0.5 else 0.0
                            )

                # Fallback de interpolação caso o sensor de disco não tenha bytes de referência (ex: mock em testes)
                if not used_disk_sensor:
                    if 20.0 <= current_pct < 34.0:
                        current_pct = min(34.0, round(current_pct + 0.6, 1))
                    elif 35.0 <= current_pct < 71.5:
                        current_pct = min(71.5, round(current_pct + 0.7, 1))
                    elif 72.0 <= current_pct < 88.5:
                        current_pct = min(88.5, round(current_pct + 0.5, 1))
                    with installer._get_lock():
                        prog = installer._get_install_progress()
                        prog["percent"] = round(current_pct, 1)

            # Notificação com controle de frequência para não saturar a thread principal da GUI
            installer.notify_progress(throttle_interval=0.15)
            time.sleep(0.15)

        proc.wait()
        reader_thread.join(timeout=1.0)

        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["speed_mbps"] = 0.0
            prog["percent"] = max(float(prog.get("percent", 90.0)), 92.0)
            prog["message"] = "Limpando cache residual..."
        installer.notify_progress(throttle_interval=0.0)

        # Passo 4: Limpeza profunda de resíduos em site-packages
        # Remove pastas residuais que o pip no Windows renomeia para '~orch' quando não consegue excluir de imediato
        try:
            import site
            from src.model_manager import safe_remove_path

            site_dirs = list(site.getsitepackages())
            local_sp = os.path.join(exe_dir, "Lib", "site-packages")
            if os.path.isdir(local_sp) and local_sp not in site_dirs:
                site_dirs.append(local_sp)
            for p in site_dirs:
                if not os.path.isdir(p):
                    continue
                # Remove pastas órfãs que não possuem __init__.py ou version.py válidos
                for pkg in ["torch", "torchvision", "torchaudio"]:
                    td = os.path.join(p, pkg)
                    if os.path.isdir(td) and (
                        not os.path.exists(os.path.join(td, "__init__.py"))
                        or (pkg == "torch" and not os.path.exists(os.path.join(td, "version.py")))
                    ):
                        safe_remove_path(td)
                # Remove todas as pastas '~orch*' (arquivos temporários de rollback do pip)
                try:
                    for entry in os.listdir(p):
                        if entry.startswith("~orch"):
                            safe_remove_path(os.path.join(p, entry))
                except Exception:
                    pass
        except Exception:
            pass

        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["percent"] = max(float(prog.get("percent", 96.0)), 96.0)
            prog["message"] = "Validando ambiente limpo..."
        installer.notify_progress(throttle_interval=0.0)

        # Passo 5: Verificação pós-desinstalação
        ai_deps = installer.check_ai_dependencies()
        is_torch_gone = not ai_deps.get("has_torch", False)

        with _cache_lock:
            import importlib

            # REGRA CRÍTICA DE SEGURANÇA CPYTHON:
            # Se 'torch._C' foi carregado pelo interpretador nesta sessão, chamar sys.modules.pop()
            # em ponteiros de C++ compilados corrompe a tabela de símbolos e causa CRASH FATAL (Access Violation).
            # Só realizamos o pop se a extensão C nativa NÃO tiver sido inicializada.
            has_loaded_c_ext = "torch._C" in sys.modules
            if is_torch_gone and not has_loaded_c_ext:
                for mod_name in list(sys.modules.keys()):
                    if (
                        mod_name == "torch"
                        or mod_name.startswith("torch.")
                        or mod_name in ("functorch", "torchvision", "torchaudio")
                    ):
                        sys.modules.pop(mod_name, None)
            sys.path_importer_cache.clear()
            importlib.invalidate_caches()

        # Passo 6: Diagnóstico de erros de bloqueio de DLL (Windows WinError 5)
        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["speed_mbps"] = 0.0
            prog["eta_seconds"] = 0
            log_lower = prog["log"].lower()
            has_dll_lock_error = any(
                kw in log_lower
                for kw in [
                    "access is denied",
                    "permissionerror",
                    "winerror 5",
                    "em uso por outro processo",
                ]
            )
            if proc.returncode == 0 or (is_torch_gone and not has_dll_lock_error):
                prog["status"] = "completed"
                prog["percent"] = 100.0
                prog["log"] += "\nPyTorch desinstalado com sucesso."
                prog["message"] = "PyTorch desinstalado com sucesso."
            else:
                prog["status"] = "error"
                prog["log"] += f"\nErro ao desinstalar (Código {proc.returncode})."
                if has_dll_lock_error:
                    prog["message"] = (
                        "DLLs do PyTorch bloqueadas na RAM pelo Windows. Feche e reabra o Visionary para desinstalar."
                    )
                else:
                    prog["message"] = f"Erro na desinstalação (Código {proc.returncode}). Verifique os logs."
        installer.notify_progress(throttle_interval=0.0)
    except Exception as e:
        with installer._get_lock():
            prog = installer._get_install_progress()
            prog["status"] = "error"
            prog["speed_mbps"] = 0.0
            prog["eta_seconds"] = 0
            prog["log"] += f"\nErro fatal: {str(e)}"
            prog["message"] = f"Erro fatal: {str(e)}"
        installer.notify_progress(throttle_interval=0.0)
