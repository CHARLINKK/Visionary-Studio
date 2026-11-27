"""
Monitor de disco e varredura de progresso de arquivos em download para modelos Hugging Face.
"""

import os
import time
import threading
from typing import List


def scan_disk_downloaded_bytes(paths: List[str]) -> int:
    """
    Varre os caminhos fornecidos e acumula o tamanho em bytes dos arquivos reais baixados,
    ignorando lockfiles do Hugging Face (.locks), temporários e deduplicando arquivos
    físicos reais para evitar contagem duplicada em diretórios aninhados ou symlinks.
    """
    total = 0
    seen_files = set()
    for p in paths:
        if not os.path.exists(p):
            continue
        if os.path.isfile(p):
            try:
                norm = os.path.normcase(os.path.realpath(p))
                if norm not in seen_files:
                    seen_files.add(norm)
                    total += os.path.getsize(p)
            except Exception:
                pass
            continue
        try:
            for root, dirs, files in os.walk(p):
                if ".locks" in dirs:
                    dirs.remove(".locks")
                if "__pycache__" in dirs:
                    dirs.remove("__pycache__")
                for f in files:
                    if f.endswith(".lock") or f.endswith(".metadata") or f.startswith(".git"):
                        continue
                    fp = os.path.join(root, f)
                    try:
                        norm = os.path.normcase(os.path.realpath(fp))
                        if norm not in seen_files:
                            seen_files.add(norm)
                            total += os.path.getsize(fp)
                    except (FileNotFoundError, PermissionError, OSError):
                        pass
        except Exception:
            pass
    return total


def monitor_disk_progress(manager, key: str, monitor_paths: List[str], stop_event: threading.Event, est_total: int = 0):
    """
    Thread de monitoramento físico de disco (fallback sem dead-reckoning artificial).
    Reporta estritamente os bytes físicos confirmados no sistema de arquivos quando o gancho
    de rede não está ativo, garantindo 100% de honestidade na porcentagem sem projetar bytes fictícios.
    """
    start_time = time.time()
    initial_bytes = scan_disk_downloaded_bytes(monitor_paths)
    last_real_bytes = initial_bytes
    last_real_sync_time = start_time
    smoothed_speed_mb = 0.0

    while not stop_event.is_set():
        real_bytes = scan_disk_downloaded_bytes(monitor_paths)
        now = time.time()

        # 1. Detecta novos bytes físicos realmente gravados em disco
        if real_bytes > last_real_bytes:
            flush_dt = max(0.2, now - last_real_sync_time)
            delta_bytes = real_bytes - last_real_bytes
            instant_speed = min(500.0, (delta_bytes / (1024 * 1024)) / flush_dt)

            if instant_speed > 0.0:
                if smoothed_speed_mb > 0.0:
                    smoothed_speed_mb = round(0.35 * instant_speed + 0.65 * smoothed_speed_mb, 1)
                else:
                    smoothed_speed_mb = round(instant_speed, 1)

            last_real_bytes = real_bytes
            last_real_sync_time = now

        # 2. Interage de forma thread-safe com o status do manager
        with manager._status_lock:
            current_st = manager.download_status.get(key)
            if not current_st or current_st.get("status") != "downloading":
                break

            stream_dl = int(current_st.get("downloaded_bytes", 0) or 0)

            # Se o gancho de stream de rede estiver ativo (< 2.0s), ele é a fonte de verdade
            # exata por arquivo; o monitor de disco não interfere nem sobrescreve.
            last_stream_time = getattr(manager, "_last_stream_time", {}).get(key, 0.0)
            stream_active = (now - last_stream_time) < 2.0 and stream_dl > 0
            if stream_active:
                last_real_bytes = max(last_real_bytes, stream_dl)
                stop_event.wait(0.2)
                continue

            tot = max(int(current_st.get("total_bytes") or est_total or 0), real_bytes, stream_dl)
            # Sem dead-reckoning: usa estritamente bytes físicos confirmados ou já reportados pelo stream
            cur_dl_int = max(real_bytes, stream_dl)
            if tot > 0:
                # Trava de segurança antes da verificação estrutural final
                cur_dl_int = min(cur_dl_int, tot)
                pct = min(99.0, round((cur_dl_int / tot) * 100, 1))
            else:
                pct = 0.0

            current_st["downloaded_bytes"] = max(int(current_st.get("downloaded_bytes", 0) or 0), cur_dl_int)
            current_st["total_bytes"] = tot
            current_st["progress"] = max(float(current_st.get("progress", 0.0) or 0.0), pct)
            current_st["speed_mbps"] = 0.0 if pct >= 99.0 else smoothed_speed_mb
            current_st["eta_seconds"] = 0

            tot_mb = tot / (1024 * 1024) if tot > 0 else 0.0
            if pct >= 99.0:
                current_st["message"] = f"Finalizando instalação... ({tot_mb:.1f} MB)"
            elif cur_dl_int > 0:
                mb = cur_dl_int / (1024 * 1024)
                if tot_mb > 0:
                    current_st["message"] = f"Baixando... ({mb:.1f}/{tot_mb:.1f} MB · {pct}%)"
                else:
                    current_st["message"] = f"Baixando... ({mb:.1f} MB)"

        manager._notify_progress(key, throttle_interval=0.15)
        stop_event.wait(0.2)
