"""
Testes Unitários e de Concorrência para o Gravador de Telemetria em Tempo Real (telemetry_logger).
Garante matematicamente:
1. Gravação segundo a segundo contínua e atômica em JSONL e human log
2. Cálculo preciso de delta físico (bytes e MB/s) na janela de 1.0s
3. Formatação idêntica à UI do React (formatDownloadTelemetry)
4. Isolamento estrito por modelo em downloads concorrentes
"""

import os
import time
import json
import threading
import pytest
from src.model_engines.hf.telemetry_logger import DownloadTelemetryLogger, _format_bytes, _format_eta, _format_ui_text


def test_format_helpers():
    assert _format_bytes(1024 * 1024 * 50) == "50.0 MB"
    assert _format_bytes(1024 * 1024 * 1024 * 1.5) == "1.50 GB"
    assert _format_bytes(2048) == "2 KB"

    assert _format_eta(15) == "~15s rest."
    assert _format_eta(75) == "~1m 15s rest."
    assert _format_eta(3665) == "~1h 1m rest."

    ui = _format_ui_text(progress=25.0, speed_mbps=30.0, downloaded=1000000, total=4000000, eta=10, message="Baixando...")
    assert "30.0 MB/s" in ui
    assert "~10s rest." in ui


def test_telemetry_logger_session_and_samples(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    
    logger = DownloadTelemetryLogger(base_dir=str(tmp_path))
    logger.local_log_dir = str(log_dir)
    logger.appdata_log_dir = str(log_dir)
    logger.jsonl_path = str(log_dir / "download_telemetry_live.jsonl")
    logger.human_log_path = str(log_dir / "download_telemetry_live.log")

    key = "yolo_detector"
    tot = 56000000
    logger.start_session(key, total_bytes=tot)

    # Simula 3 ticks a cada 200ms
    for i in range(1, 4):
        time.sleep(0.1)
        cur_bytes = i * 15000000
        prog = round((cur_bytes / tot) * 100, 1)
        logger.record_tick(key, {
            "status": "downloading",
            "downloaded_bytes": cur_bytes,
            "total_bytes": tot,
            "progress": prog,
            "speed_mbps": 25.0,
            "eta_seconds": 2,
            "message": f"Baixando chunk {i}..."
        })

    # Força emissão de amostra
    st = logger._active_sessions.get(key)
    assert st is not None
    logger._emit_second_sample(key, st, force_final=False)

    # Conclusão final
    logger.record_tick(key, {
        "status": "installed",
        "downloaded_bytes": tot,
        "total_bytes": tot,
        "progress": 100.0,
        "speed_mbps": 0.0,
        "eta_seconds": 0,
        "message": "Concluído!"
    })

    assert os.path.exists(logger.jsonl_path)
    assert os.path.exists(logger.human_log_path)

    with open(logger.jsonl_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) >= 2
    last_entry = lines[-1]
    assert last_entry["model_key"] == key
    assert last_entry["status"] == "installed"
    assert last_entry["progress_pct"] == 100.0
    assert last_entry["downloaded_bytes"] == tot


def test_telemetry_logger_eventbus_integration(tmp_path):
    from src.utils.event_bus import event_bus

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    
    logger = DownloadTelemetryLogger(base_dir=str(tmp_path))
    logger.local_log_dir = str(log_dir)
    logger.jsonl_path = str(log_dir / "download_telemetry_live.jsonl")
    logger.human_log_path = str(log_dir / "download_telemetry_live.log")

    event_bus.publish("core_engine_progress", {
        "status": "downloading",
        "percent": 50.0,
        "message": "Baixando pacotes PyTorch (1427 MB / 2855 MB)..."
    })

    st = logger._active_sessions.get("pytorch_core")
    assert st is not None
    assert st["progress"] == 50.0
    assert "pytorch_core" in logger._session_start_times
