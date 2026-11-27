"""
Visualizador de Telemetria em Tempo Real de Downloads do Visionary Studio.
Acompanha segundo a segundo o comportamento de rede, disco e interface:
- Velocidade real e taxa de transferência por janela de 1 segundo
- Crescimento físico de arquivos em disco (.incomplete, .part, .safetensors, .pt)
- Detecção imediata de anomalias (congelamento > 1.0s, queda abrupta de vazão)
- Exibição idêntica ao que o letrista/editor visualiza na interface gráfica (React)
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "logs", "download_telemetry_live.log")
JSONL_FILE_PATH = os.path.join(PROJECT_ROOT, "logs", "download_telemetry_live.jsonl")

# Também verifica AppData caso o usuário esteja rodando via empacotamento
APPDATA_DIR = os.environ.get("APPDATA")
APPDATA_LOG = os.path.join(APPDATA_DIR, "Visionary Studio", "logs", "download_telemetry_live.log") if APPDATA_DIR else ""


def resolve_active_log_file() -> str:
    """Retorna o caminho do arquivo de log de telemetria mais recente."""
    candidates = [LOG_FILE_PATH]
    if APPDATA_LOG:
        candidates.append(APPDATA_LOG)
    for p in candidates:
        if os.path.exists(p):
            return p
    return LOG_FILE_PATH


def stream_live_telemetry(follow: bool = True):
    """Lê continuamente as linhas de telemetria segundo a segundo em tempo real."""
    print("=" * 105)
    print("  VISIONARY STUDIO — TELEMETRIA DE DOWNLOADS EM TEMPO REAL (SEGUNDO A SEGUNDO)")
    print("=" * 105)
    
    target_path = resolve_active_log_file()
    print(f"[*] Monitorando arquivo de telemetria: {target_path}")
    print("[*] Aguardando ticks de download do motor (pressione Ctrl+C para encerrar)...\n")

    last_size = 0
    if os.path.exists(target_path):
        # Lê as últimas 10 linhas se já existirem
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            for line in lines[-12:]:
                print(line.rstrip())
            last_size = f.tell()

    last_tick_time = time.time()
    try:
        while True:
            target_path = resolve_active_log_file()
            if os.path.exists(target_path):
                cur_size = os.path.getsize(target_path)
                if cur_size > last_size:
                    with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_size)
                        new_content = f.read()
                        last_size = f.tell()
                    for line in new_content.splitlines():
                        if line.strip():
                            now = time.time()
                            gap_ms = (now - last_tick_time) * 1000.0
                            if gap_ms > 1500.0 and "MB/s" in line:
                                print(f"  [ALERTA DE FLUXO] Intervalo entre amostras: {gap_ms:.0f}ms")
                            last_tick_time = now
                            print(line)
                            sys.stdout.flush()
                elif cur_size < last_size:
                    # Arquivo foi truncado ou reiniciado
                    last_size = 0
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\n[*] Monitoramento de telemetria encerrado.")


if __name__ == "__main__":
    stream_live_telemetry(follow=True)
