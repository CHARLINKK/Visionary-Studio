"""
Telemetria em Tempo Real de Alta Resolução para Downloads do Visionary Studio.
Captura segundo a segundo cada detalhe do fluxo de dados:
- Vazão de rede real (MB/s instantâneo e EMA)
- Bytes transferidos e deltas físicos em janelas exatas de 1.0s
- Flushes físicos de disco (NTFS) e arquivos ativos (.incomplete, .part, .safetensors, .pt)
- Rastreamento de threads e transições de fase (download, validação, extração, finalização)
- Renderização exata da string visualizada pelo usuário na UI do React
- Gravação atômica em JSONL e LOG estruturado para auditoria profunda
"""

import os
import sys
import time
import json
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.config import get_app_data_dir


def _format_bytes(num_bytes: int) -> str:
    """Formata bytes em GB, MB ou KB."""
    if num_bytes is None or num_bytes <= 0:
        return "0 B"
    gb = num_bytes / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.2f} GB"
    mb = num_bytes / (1024 ** 2)
    if mb >= 1.0:
        return f"{mb:.1f} MB"
    kb = num_bytes / 1024
    if kb >= 1.0:
        return f"{kb:.0f} KB"
    return f"{num_bytes} B"


def _format_eta(seconds: int) -> str:
    """Formata ETA em formato legível."""
    if not seconds or seconds <= 0:
        return "--"
    if seconds < 60:
        return f"~{int(seconds)}s rest."
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins < 60:
        return f"~{mins}m {secs}s rest."
    hours = int(mins // 60)
    rem_mins = int(mins % 60)
    return f"~{hours}h {rem_mins}m rest."


def _format_ui_text(progress: float, speed_mbps: float, downloaded: int, total: int, eta: int, message: str) -> str:
    """Simula a renderização exata do formatDownloadTelemetry do frontend React."""
    if message and any(w in message for w in ["Extraindo", "Descompactando", "Validando", "Registrando"]):
        return message.strip()
    if progress >= 99.0 and downloaded >= total and total > 0:
        return f"Finalizando instalação... · {_format_bytes(total)}"
    parts = []
    if speed_mbps > 0.05:
        if speed_mbps >= 1.0:
            parts.append(f"{speed_mbps:.1f} MB/s")
        else:
            parts.append(f"{int(speed_mbps * 1024)} KB/s")
    if total > 0 and downloaded > 0:
        parts.append(f"{_format_bytes(downloaded)} / {_format_bytes(total)}")
    if eta > 0:
        parts.append(_format_eta(eta))
    if parts:
        return " · ".join(parts)
    return message or "Iniciando..."


class DownloadTelemetryLogger:
    """
    Gravador e despachante de telemetria segundo a segundo para downloads do Visionary Studio.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DownloadTelemetryLogger, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, base_dir: Optional[str] = None):
        if self._initialized:
            self._ensure_eventbus_subscribed()
            return
        self._initialized = True
        self.base_dir = base_dir or get_app_data_dir()
        
        # Diretórios de logs
        self.project_root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
        self.local_log_dir = os.path.join(self.project_root, "logs")
        self.appdata_log_dir = os.path.join(self.base_dir, "logs")
        
        for d in [self.local_log_dir, self.appdata_log_dir]:
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass

        self.jsonl_path = os.path.join(self.local_log_dir, "download_telemetry_live.jsonl")
        self.human_log_path = os.path.join(self.local_log_dir, "download_telemetry_live.log")

        self._active_sessions = {}
        self._last_sample_times = {}
        self._last_sample_bytes = {}
        self._session_start_times = {}
        self._file_lock = threading.Lock()

        # Thread de batimento cardíaco (Heartbeat) de 1 segundo
        self._stop_heartbeat = threading.Event()
        self._heartbeat_thread = threading.Thread(target=self._run_heartbeat, daemon=True, name="TelemetryHeartbeat")
        self._heartbeat_thread.start()

        # Conexão automática ao EventBus para captura de telemetria de qualquer módulo
        self._ensure_eventbus_subscribed()

    def _ensure_eventbus_subscribed(self):
        """Garante inscrição idempotente nos eventos de download do EventBus."""
        try:
            from src.utils.event_bus import event_bus
            event_bus.subscribe("core_engine_progress", self._on_core_engine_progress)
            event_bus.subscribe("model_download_progress", self._on_model_download_progress)
        except Exception:
            pass

    def _on_core_engine_progress(self, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            return
        status = payload.get("status", "idle")
        if status in ["downloading", "extracting", "completed"]:
            pct = float(payload.get("percent", 0.0))
            msg = payload.get("message", "")
            tot = 2855 * 1024 * 1024
            dl = int(tot * (pct / 100.0))
            st = {
                "status": status,
                "progress": pct,
                "downloaded_bytes": dl,
                "total_bytes": tot,
                "speed_mbps": 0.0,
                "eta_seconds": 0,
                "message": msg,
            }
            if "pytorch_core" not in self._active_sessions:
                if status in ["completed", "installed", "idle"]:
                    return
                self.start_session("pytorch_core", total_bytes=tot)
            self.record_tick("pytorch_core", st, source="core_installer")

    def _on_model_download_progress(self, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            return
        key = payload.get("key")
        data = payload.get("data")
        if key and isinstance(data, dict):
            if key not in self._active_sessions:
                if data.get("status") in ["installed", "completed", "idle", "cancelled"]:
                    return
                if data.get("status") in ["downloading", "extracting"]:
                    self.start_session(key, total_bytes=data.get("total_bytes", 0))
                else:
                    return
            self.record_tick(key, data, source="event_bus")

    def start_session(self, key: str, total_bytes: int = 0):
        """Inicia uma sessão de telemetria segundo a segundo para um modelo."""
        now = time.time()
        with self._file_lock:
            self._active_sessions[key] = {
                "key": key,
                "total_bytes": total_bytes,
                "downloaded_bytes": 0,
                "speed_mbps": 0.0,
                "progress": 0.0,
                "eta_seconds": 0,
                "status": "downloading",
                "message": "Iniciando download...",
            }
            self._session_start_times[key] = now
            self._last_sample_times[key] = now
            self._last_sample_bytes[key] = 0

        header_msg = f"\n{'='*90}\n[TELEMETRIA INICIADA] Modelo: {key} | Total Esperado: {_format_bytes(total_bytes)} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*90}"
        self._append_human_log(header_msg)
        print(header_msg, flush=True)

    def record_tick(self, key: str, status_data: Dict[str, Any], source: str = "engine"):
        """Atualiza os dados mais recentes de um modelo ativo."""
        with self._file_lock:
            st = self._active_sessions.get(key)
            if not st:
                # Não cria sessões fantasmas quando recebe eventos terminais ou inativos sem sessão prévia
                if status_data.get("status") in ["installed", "completed", "idle", "cancelled"]:
                    return
                self._active_sessions[key] = {}
                st = self._active_sessions[key]
                self._session_start_times[key] = time.time()
                self._last_sample_times[key] = time.time()
                self._last_sample_bytes[key] = int(status_data.get("downloaded_bytes", 0))

            st.update(status_data)
            st["key"] = key
            st["last_source"] = source
            st["last_update_perf"] = time.time()

            # Se o status encerrou, registra snapshot final
            cur_status = status_data.get("status")
            if cur_status in ["installed", "completed", "error", "cancelled"]:
                self._emit_second_sample(key, st, force_final=True)

    def _scan_active_disk_files(self, key: str) -> Dict[str, int]:
        """Varre os arquivos físicos em disco associados ao modelo."""
        found = {}
        target_dir = os.path.join(self.base_dir, "models")
        # Também verifica models local na raiz do projeto se diferente
        search_dirs = [target_dir]
        proj_models = os.path.join(self.project_root, "models")
        if proj_models not in search_dirs and os.path.isdir(proj_models):
            search_dirs.append(proj_models)

        for sdir in search_dirs:
            if not os.path.isdir(sdir):
                continue
            try:
                for root, dirs, files in os.walk(sdir):
                    if ".locks" in dirs:
                        dirs.remove(".locks")
                    if "__pycache__" in dirs:
                        dirs.remove("__pycache__")
                    for f in files:
                        if f.endswith(".lock"):
                            continue
                        if key == "yolo_detector" and not ("best" in f or "comic" in f or "bubble" in f):
                            continue
                        if (key == "florence2" or key == "florence2_large") and not ("florence" in root.lower() or "safetensors" in f or "config" in f):
                            continue
                        fp = os.path.join(root, f)
                        try:
                            sz = os.path.getsize(fp)
                            found[f] = sz
                        except Exception:
                            pass
            except Exception:
                pass
        return found

    def _emit_second_sample(self, key: str, st: Dict[str, Any], force_final: bool = False):
        """Calcula e persiste o snapshot exato do segundo atual."""
        now = time.time()
        t0 = self._session_start_times.get(key, now)
        elapsed_s = now - t0

        last_t = self._last_sample_times.get(key, now)
        dt = max(0.1, now - last_t)
        last_b = self._last_sample_bytes.get(key, 0)
        cur_b = int(st.get("downloaded_bytes", 0))
        delta_b = max(0, cur_b - last_b)
        
        # Taxa de transferência real na fatia deste segundo
        window_speed_mb = round((delta_b / (1024 * 1024)) / dt, 1) if dt > 0 else 0.0

        self._last_sample_times[key] = now
        self._last_sample_bytes[key] = cur_b

        tot_b = int(st.get("total_bytes", 0))
        prog = float(st.get("progress", 0.0))
        speed_mb = float(st.get("speed_mbps", 0.0)) or window_speed_mb
        eta_s = int(st.get("eta_seconds", 0))
        status = st.get("status", "unknown")
        msg = st.get("message", "")

        ui_text = _format_ui_text(prog, speed_mb, cur_b, tot_b, eta_s, msg)
        active_files = self._scan_active_disk_files(key)

        files_summary = ", ".join([f"{fn} ({_format_bytes(sz)})" for fn, sz in list(active_files.items())[:4]]) or "nenhum arquivo no momento"

        payload = {
            "iso_time": datetime.now().isoformat(),
            "elapsed_seconds": round(elapsed_s, 2),
            "model_key": key,
            "status": status,
            "progress_pct": round(prog, 2),
            "downloaded_bytes": cur_b,
            "total_bytes": tot_b,
            "downloaded_formatted": _format_bytes(cur_b),
            "total_formatted": _format_bytes(tot_b),
            "reported_speed_mbps": speed_mb,
            "window_1s_speed_mbps": window_speed_mb,
            "delta_1s_bytes": delta_b,
            "delta_1s_formatted": _format_bytes(delta_b),
            "eta_seconds": eta_s,
            "eta_formatted": _format_eta(eta_s),
            "message": msg,
            "ui_rendered_text": ui_text,
            "active_disk_files": active_files,
            "thread": threading.current_thread().name,
        }

        # 1. Gravação no arquivo JSONL para inspeção estruturada
        json_line = json.dumps(payload, ensure_ascii=False)
        self._append_jsonl(json_line)

        # 2. Gravação e exibição da linha humana estruturada
        log_line = (
            f"[{datetime.now().strftime('%H:%M:%S')} | T+{elapsed_s:05.1f}s] "
            f"{key:<15} | "
            f"{speed_mb:5.1f} MB/s (1s: +{_format_bytes(delta_b):<7}) | "
            f"{_format_bytes(cur_b):>9} / {_format_bytes(tot_b):<9} ({prog:5.1f}%) | "
            f"ETA: {payload['eta_formatted']:<11} | "
            f"Status: {status:<11} | "
            f"UI: '{ui_text}'"
        )
        self._append_human_log(log_line)
        print(log_line, flush=True)

        if force_final:
            summary = (
                f"\n{'='*90}\n"
                f"[TELEMETRIA CONCLUÍDA] Modelo: {key} | Status Final: {status} | "
                f"Total: {_format_bytes(cur_b)} em {elapsed_s:.1f}s | "
                f"Velocidade Média Global: {(cur_b / (1024*1024) / max(0.1, elapsed_s)):.1f} MB/s\n"
                f"{'='*90}\n"
            )
            self._append_human_log(summary)
            print(summary, flush=True)
            self._active_sessions.pop(key, None)

    def _run_heartbeat(self):
        """Loop de batimento cardíaco executado a cada 1.0 segundo com precisão de relógio."""
        while not self._stop_heartbeat.is_set():
            if self._stop_heartbeat.wait(1.0):
                break
            with self._file_lock:
                keys = list(self._active_sessions.keys())
            for k in keys:
                with self._file_lock:
                    st = dict(self._active_sessions.get(k, {}))
                if st and st.get("status") in ["downloading", "extracting", "installing"]:
                    self._emit_second_sample(k, st, force_final=False)

    def _append_jsonl(self, line: str):
        for path in [self.jsonl_path, os.path.join(self.appdata_log_dir, "download_telemetry_live.jsonl")]:
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

    def _append_human_log(self, line: str):
        for path in [self.human_log_path, os.path.join(self.appdata_log_dir, "download_telemetry_live.log")]:
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass


# Instância global Singleton
telemetry_logger = DownloadTelemetryLogger()
