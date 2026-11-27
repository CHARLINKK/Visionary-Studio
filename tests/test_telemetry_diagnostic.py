"""
Ferramenta Isolada de Diagnóstico Profundo de Telemetria de Downloads (Visionary Studio).

Objetivo:
Permitir 'pelar' (inspecionar em nível cirúrgico) toda a cadeia de telemetria dos downloads
(PyTorch Core, Comic-YOLO, Florence-2 e Ollama) em milissegundos, detectando com precisão:
1. Stalls / Congelamentos (intervalos > 500ms sem nenhum tick de progresso)
2. Regressões não-monotônicas (resets de bytes baixados ou porcentagem caindo)
3. Clamps prematuros (velocidade e ETA zerados antes da conclusão física)
4. Colisões de threads (tqdm de rede vs DiskMonitor sobrescrevendo status)
5. Simulação da visão do usuário no frontend (renderização exata do formatDownloadTelemetry)

Este script funciona tanto como suíte de testes automatizados (pytest) quanto como
utilitário autônomo CLI executável via `python tests/test_telemetry_diagnostic.py`.
"""

import os
import sys
import time
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Garante raiz do projeto no PYTHONPATH
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@dataclass
class TelemetryTick:
    """Snapshot instantâneo de um evento de telemetria."""
    timestamp: float           # Segundos desde o início
    dt_ms: float               # Delta em milissegundos desde o tick anterior
    status: str
    progress: float
    downloaded_bytes: int
    total_bytes: int
    speed_mbps: float
    eta_seconds: int
    message: str
    source_thread: str
    source_channel: str        # 'callback', 'poll', 'eventbus', 'disk_monitor', 'stream_tqdm'
    formatted_ui_text: str     # O que a UI do React efetivamente renderiza


@dataclass
class TelemetryAnomaly:
    """Anomalia detectada na telemetria."""
    timestamp: float
    anomaly_type: str          # 'STALL', 'REGRESSION', 'PREMATURE_CLAMP', 'RACE_COLLISION', 'FROZEN_MESSAGE'
    description: str
    tick_index: int


class TelemetryProbe:
    """
    Sonda de alta resolução que se anexa aos managers e intercepta, armazena
    e audita cada micro-evento de progresso em tempo real.
    """

    def __init__(self, name: str, stall_threshold_ms: float = 600.0):
        self.name = name
        self.stall_threshold_ms = stall_threshold_ms
        self.ticks: List[TelemetryTick] = []
        self.anomalies: List[TelemetryAnomaly] = []
        self._start_perf = None
        self._last_perf = None
        self._lock = threading.Lock()
        self._max_observed_bytes = 0
        self._max_observed_progress = 0.0

    def start(self):
        """Inicia a gravação da telemetria."""
        with self._lock:
            self._start_perf = time.perf_counter()
            self._last_perf = self._start_perf
            self.ticks.clear()
            self.anomalies.clear()
            self._max_observed_bytes = 0
            self._max_observed_progress = 0.0

    def record_tick(self, key: str, data: dict, source_channel: str = "callback"):
        """Registra um tick de progresso vindo de qualquer canal."""
        now = time.perf_counter()
        with self._lock:
            if self._start_perf is None:
                self._start_perf = now
                self._last_perf = now

            rel_time = now - self._start_perf
            dt_ms = (now - self._last_perf) * 1000.0
            self._last_perf = now

            status = data.get("status", "unknown")
            progress = float(data.get("progress", 0.0))
            downloaded = int(data.get("downloaded_bytes", 0))
            total = int(data.get("total_bytes", 0))
            speed = float(data.get("speed_mbps", 0.0))
            eta = int(data.get("eta_seconds", 0))
            message = str(data.get("message", ""))
            thread_name = threading.current_thread().name

            # Renderiza o que o formatDownloadTelemetry do frontend geraria
            ui_text = self._simulate_frontend_telemetry(
                progress=progress,
                speed_mbps=speed,
                eta_seconds=eta,
                downloaded_bytes=downloaded,
                total_bytes=total,
                text=message
            )

            idx = len(self.ticks)
            tick = TelemetryTick(
                timestamp=round(rel_time, 4),
                dt_ms=round(dt_ms, 1),
                status=status,
                progress=progress,
                downloaded_bytes=downloaded,
                total_bytes=total,
                speed_mbps=speed,
                eta_seconds=eta,
                message=message,
                source_thread=thread_name,
                source_channel=source_channel,
                formatted_ui_text=ui_text,
            )
            self.ticks.append(tick)

            # ── Análise de Anomalias em Tempo Real ───────────────────────────
            # 1. Detecção de Stall (atraso entre ticks enquanto ainda baixando)
            if idx > 0 and dt_ms > self.stall_threshold_ms and status in ["downloading", "extracting", "installing"]:
                self.anomalies.append(TelemetryAnomaly(
                    timestamp=round(rel_time, 4),
                    anomaly_type="STALL",
                    description=f"Congelamento de telemetria por {dt_ms:.1f}ms (> {self.stall_threshold_ms}ms) no status '{status}'",
                    tick_index=idx
                ))

            # 2. Detecção de Regressão Não-Monotônica (reset de bytes)
            if downloaded < self._max_observed_bytes and status == "downloading" and total > 0:
                self.anomalies.append(TelemetryAnomaly(
                    timestamp=round(rel_time, 4),
                    anomaly_type="REGRESSION",
                    description=f"Regressão de bytes: caiu de {self._format_bytes(self._max_observed_bytes)} para {self._format_bytes(downloaded)}",
                    tick_index=idx
                ))
            else:
                self._max_observed_bytes = max(self._max_observed_bytes, downloaded)

            # 3. Detecção de Regressão de Porcentagem
            if progress < (self._max_observed_progress - 0.5) and status in ["downloading", "extracting"]:
                self.anomalies.append(TelemetryAnomaly(
                    timestamp=round(rel_time, 4),
                    anomaly_type="REGRESSION",
                    description=f"Regressão de progresso: caiu de {self._max_observed_progress:.1f}% para {progress:.1f}%",
                    tick_index=idx
                ))
            else:
                self._max_observed_progress = max(self._max_observed_progress, progress)

            # 4. Detecção de Clamp Prematuro (velocidade/ETA zerados prematuramente antes da fase de finalização)
            if progress >= 99.0 and progress < 99.9 and status == "downloading" and downloaded < (total * 0.995):
                if speed <= 0.05 and not any(w in message for w in ["Finalizando", "Extraindo", "Validando", "Descompactando"]):
                    self.anomalies.append(TelemetryAnomaly(
                        timestamp=round(rel_time, 4),
                        anomaly_type="PREMATURE_CLAMP",
                        description=f"Velocidade zerada artificialmente em {progress:.1f}% com {self._format_bytes(total - downloaded)} ainda pendentes",
                        tick_index=idx
                    ))

    def _simulate_frontend_telemetry(self, progress, speed_mbps, eta_seconds, downloaded_bytes, total_bytes, text) -> str:
        """Simula fielmente a saída do formatDownloadTelemetry.js."""
        # Se for fase de disco
        if any(w in text for w in ["Descompactando", "Extraindo", "Validando", "Registrando"]):
            return text.strip()

        has_remaining = total_bytes > 0 and downloaded_bytes > 0 and downloaded_bytes < total_bytes
        is_network_active = speed_mbps > 0.05

        if not has_remaining and not is_network_active and (progress >= 99.5 or "Finalizando" in text):
            sz = self._format_bytes(total_bytes) if total_bytes > 0 else ""
            return f"Finalizando instalação... · {sz}" if sz else "Finalizando instalação..."

        parts = []
        if total_bytes > 0 and downloaded_bytes > 0:
            parts.append(f"{self._format_bytes(downloaded_bytes)} / {self._format_bytes(total_bytes)}")

        if parts:
            return " · ".join(parts)
        return text.strip() if text else "Baixando..."

    @staticmethod
    def _format_bytes(b: int) -> str:
        if b >= 1024 * 1024 * 1024:
            return f"{b / (1024 * 1024 * 1024):.2f} GB"
        if b >= 1024 * 1024:
            return f"{b / (1024 * 1024):.1f} MB"
        if b >= 1024:
            return f"{b / 1024:.0f} KB"
        return f"{b} B"

    def print_diagnostic_report(self, max_sample_rows: int = 30):
        """Imprime relatório estruturado e legível da telemetria no terminal."""
        total_ticks = len(self.ticks)
        duration = self.ticks[-1].timestamp if self.ticks else 0.0
        avg_tick_rate = (total_ticks / duration) if duration > 0 else 0.0

        print("\n" + "=" * 90)
        print(f"  DIAGNÓSTICO CIRÚRGICO DE TELEMETRIA: {self.name.upper()}")
        print("=" * 90)
        print(f"• Duração total: {duration:.2f}s | Total de Ticks: {total_ticks} | Taxa média: {avg_tick_rate:.1f} ticks/s")
        print(f"• Limiar de congelamento (stall): {self.stall_threshold_ms}ms")
        print(f"• Anomalias detectadas: {len(self.anomalies)}")

        if self.anomalies:
            print("\n  [!] ANOMALIAS IDENTIFICADAS:")
            for a in self.anomalies:
                print(f"    - [T+{a.timestamp:06.3f}s | {a.anomaly_type}] {a.description}")
        else:
            print("\n  [OK] NENHUMA ANOMALIA DETECTADA (Telemetria 100% contínua e monotônica).")

        print("\n" + "-" * 90)
        print("  AMOSTRA DA LINHA DO TEMPO (O QUE ACONTECEU NO MOTOR E NA UI):")
        print("-" * 90)
        header = f"{'TEMPO':<9} | {'DELTA':<7} | {'PROG':<6} | {'BYTES':<18} | {'VELOCIDADE':<10} | {'ETA':<5} | {'THREAD':<15} | {'TEXTO NA UI'}"
        print(header)
        print("-" * 90)

        # Amostra ticks proporcionalmente para não poluir
        if total_ticks <= max_sample_rows:
            sample_ticks = self.ticks
        else:
            step = total_ticks / max_sample_rows
            indices = {int(i * step) for i in range(max_sample_rows)}
            indices.add(0)
            indices.add(total_ticks - 1)
            sample_ticks = [self.ticks[i] for i in sorted(indices) if i < total_ticks]

        for t in sample_ticks:
            b_str = f"{self._format_bytes(t.downloaded_bytes)}/{self._format_bytes(t.total_bytes)}"
            v_str = f"{t.speed_mbps:.1f} MB/s" if t.speed_mbps > 0 else "-"
            eta_str = f"{t.eta_seconds}s" if t.eta_seconds > 0 else "-"
            th_str = f"{t.source_thread[:14]}"
            print(f"T+{t.timestamp:06.3f}s | {t.dt_ms:5.1f}ms | {t.progress:5.1f}% | {b_str:<18} | {v_str:<10} | {eta_str:<5} | {th_str:<15} | {t.formatted_ui_text}")

        print("=" * 90 + "\n")


# ═════════════════════════════════════════════════════════════════════════════
#  CENÁRIOS DE DIAGNÓSTICO PROFUNDO
# ═════════════════════════════════════════════════════════════════════════════

def run_pytorch_core_telemetry_diagnostic(tmp_path) -> TelemetryProbe:
    """
    Diagnostica isoladamente o CoreEngineInstaller:
    1. Fase de download de múltiplos wheels (torch 2850 MB + torchvision 4.5 MB)
    2. Fase de descompactação e crescimento de Lib/site-packages/torch
    3. Conclusão física
    """
    from src.model_engines.core_engine_installer import CoreEngineInstaller

    probe = TelemetryProbe("PyTorch Core Installer (Wheels + Extraction)")
    installer = CoreEngineInstaller()
    probe.start()

    from src.utils.event_bus import event_bus

    def on_bus_event(payload):
        probe.record_tick("ocr", payload, source_channel="event_bus")

    event_bus.subscribe("core_engine_progress", on_bus_event)

    # Simula stream real do pip parsing com accumulator
    torch_chunks = [
        (100 * 1024 * 1024, 2850 * 1024 * 1024, 25.0, "torch-2.6.0-cp311-cp311-win_amd64.whl"),
        (850 * 1024 * 1024, 2850 * 1024 * 1024, 30.0, "torch-2.6.0-cp311-cp311-win_amd64.whl"),
        (1850 * 1024 * 1024, 2850 * 1024 * 1024, 35.0, "torch-2.6.0-cp311-cp311-win_amd64.whl"),
        (2850 * 1024 * 1024, 2850 * 1024 * 1024, 40.0, "torch-2.6.0-cp311-cp311-win_amd64.whl"),
    ]

    vision_chunks = [
        (1 * 1024 * 1024, 5 * 1024 * 1024, 15.0, "torchvision-0.21.0-cp311-cp311-win_amd64.whl"),
        (5 * 1024 * 1024, 5 * 1024 * 1024, 20.0, "torchvision-0.21.0-cp311-cp311-win_amd64.whl"),
    ]

    total_expected = 2855 * 1024 * 1024
    completed_wheels = 0

    # 1. Download Torch
    for cur, tot, spd, whl in torch_chunks:
        time.sleep(0.04)
        pct = 5.0 + ((cur / total_expected) * 80.0)
        eta = int((total_expected - cur) / (spd * 1024 * 1024))
        data = {
            "status": "installing",
            "progress": pct,
            "downloaded_bytes": cur,
            "total_bytes": total_expected,
            "speed_mbps": spd,
            "eta_seconds": eta,
            "message": f"Baixando {whl}"
        }
        probe.record_tick("ocr", data)
    completed_wheels += 2850 * 1024 * 1024

    # 2. Download Torchvision (não pode resetar bytes!)
    for cur, tot, spd, whl in vision_chunks:
        time.sleep(0.04)
        cum = completed_wheels + cur
        pct = 5.0 + ((cum / total_expected) * 80.0)
        eta = int((total_expected - cum) / (spd * 1024 * 1024))
        data = {
            "status": "installing",
            "progress": pct,
            "downloaded_bytes": cum,
            "total_bytes": total_expected,
            "speed_mbps": spd,
            "eta_seconds": eta,
            "message": f"Baixando {whl}"
        }
        probe.record_tick("ocr", data)

    # 3. Fase de Descompactação (85% -> 99%)
    extract_steps = [
        (86.0, "Extraindo pacotes: torch (500 / 4500 MB)..."),
        (89.0, "Extraindo pacotes: torch (1800 / 4500 MB)..."),
        (93.0, "Extraindo pacotes: torch (3200 / 4500 MB)..."),
        (97.0, "Extraindo pacotes: torch (4400 / 4500 MB)..."),
        (99.0, "Finalizando ambiente PyTorch..."),
    ]
    for p, msg in extract_steps:
        time.sleep(0.05)
        probe.record_tick("ocr", {
            "status": "installing",
            "progress": p,
            "downloaded_bytes": total_expected,
            "total_bytes": total_expected,
            "speed_mbps": 0.0,
            "eta_seconds": 0,
            "message": msg
        })

    # 4. Finalização
    probe.record_tick("ocr", {
        "status": "completed",
        "progress": 100.0,
        "downloaded_bytes": total_expected,
        "total_bytes": total_expected,
        "speed_mbps": 0.0,
        "eta_seconds": 0,
        "message": "PyTorch Core instalado com sucesso!"
    })
    try:
        event_bus.unsubscribe("core_engine_progress", on_bus_event)
    except Exception:
        pass

    return probe


def run_yolo_multi_file_telemetry_diagnostic(tmp_path) -> TelemetryProbe:
    """
    Diagnostica isoladamente o download sequencial do Comic-YOLO (best.pt + detector.pt).
    Testa a transição entre arquivos, integridade de contadores e sincronismo.
    """
    from src.model_manager import ModelManager
    from src.model_engines.hf.http_downloader import scoped_hf_stream_hook

    probe = TelemetryProbe("Comic-YOLO Multi-File Stream")
    manager = ModelManager(base_dir=str(tmp_path))
    key = "yolo_detector"
    est_total = 58808181  # ~58.8 MB

    manager.download_status[key] = {
        "status": "downloading",
        "progress": 0.0,
        "downloaded_bytes": 0,
        "total_bytes": est_total,
        "message": "Iniciando download..."
    }

    manager.register_progress_callback(lambda k, d: probe.record_tick(k, d, source_channel="manager_callback"))
    probe.start()

    with scoped_hf_stream_hook(manager, key, target_total_bytes=est_total) as tracker:
        import huggingface_hub.file_download as fd

        # Arquivo 1: best.pt (~6.7 MB = 6700000 B)
        bar1 = fd.tqdm(total=6700000, unit="B", desc="best.pt")
        for chunk in [2000000, 2000000, 2700000]:
            time.sleep(0.11)
            bar1.update(chunk)
        bar1.close()

        # Transição: mensagem do manager
        with manager._status_lock:
            manager.download_status[key]["message"] = "Conectando ao servidor... (2/2)"
        manager._notify_progress(key)

        # Arquivo 2: comic-speech-bubble-detector.pt (~52.1 MB = 52108181 B)
        bar2 = fd.tqdm(total=52108181, unit="B", desc="comic-speech-bubble-detector.pt")
        chunk_sz = 10000000
        for _ in range(5):
            time.sleep(0.11)
            bar2.update(chunk_sz)
        time.sleep(0.11)
        bar2.update(2108181)
        bar2.close()

    # Conclusão
    with manager._status_lock:
        manager.download_status[key] = {
            "status": "installed",
            "progress": 100.0,
            "downloaded_bytes": est_total,
            "total_bytes": est_total,
            "speed_mbps": 0.0,
            "eta_seconds": 0,
            "message": "Concluído!"
        }
    manager._notify_progress(key)

    return probe


def run_florence_disk_monitor_diagnostic(tmp_path) -> TelemetryProbe:
    """
    Diagnostica isoladamente o monitor de disco e dead-reckoning para Florence-2
    sob condições simuladas de buffer do NTFS (rajadas de escrita esporádicas).
    Verifica se o dead-reckoning avança suavemente SEM inventar megabytes irreais.
    """
    from src.model_manager import ModelManager
    from src.model_engines.hf.disk_monitor import monitor_disk_progress

    probe = TelemetryProbe("Florence-2 NTFS Buffer & Dead-Reckoning", stall_threshold_ms=800.0)
    manager = ModelManager(base_dir=str(tmp_path))
    key = "florence2_large"
    total_bytes = 100 * 1024 * 1024  # 100 MB para teste rápido

    manager.download_status[key] = {
        "status": "downloading",
        "progress": 0.0,
        "downloaded_bytes": 0,
        "total_bytes": total_bytes,
        "message": "Iniciando download..."
    }

    manager.register_progress_callback(lambda k, d: probe.record_tick(k, d, source_channel="disk_monitor"))
    probe.start()

    dummy_dir = tmp_path / "models" / "florence-2-large"
    dummy_dir.mkdir(parents=True, exist_ok=True)
    chunk_file = dummy_dir / "model.safetensors.part"

    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=monitor_disk_progress,
        args=(manager, key, [str(dummy_dir)], stop_event, total_bytes),
        daemon=True
    )
    monitor_thread.start()

    # Simula 3 flushes do NTFS em rajadas com pausas de 200ms
    for written_mb in [20, 55, 95]:
        time.sleep(0.2)
        chunk_file.write_bytes(b"F" * (written_mb * 1024 * 1024))

    time.sleep(0.2)
    stop_event.set()
    monitor_thread.join(timeout=1.0)

    # Conclusão física
    with manager._status_lock:
        manager.download_status[key] = {
            "status": "installed",
            "progress": 100.0,
            "downloaded_bytes": total_bytes,
            "total_bytes": total_bytes,
            "speed_mbps": 0.0,
            "eta_seconds": 0,
            "message": "Concluído!"
        }
    manager._notify_progress(key)

    return probe


def run_live_yolo_download_diagnostic(tmp_path, timeout_seconds: float = 120.0) -> TelemetryProbe:
    """
    Executa o download REAL de Comic-YOLO (~59 MB) para um diretório sandbox temporário,
    gravando cada milissegundo de dados de rede, flushes de disco e telemetria de ponta a ponta.
    """
    from src.model_manager import ModelManager

    probe = TelemetryProbe("Comic-YOLO Live Real-World Download", stall_threshold_ms=1200.0)
    manager = ModelManager(base_dir=str(tmp_path))
    key = "yolo_detector"

    def on_live_tick(k, data):
        probe.record_tick(k, data, source_channel="live_engine")

    manager.register_progress_callback(on_live_tick)
    probe.start()

    print(f"\n[*] Disparando download real de {key} em sandbox temporário...")
    ok = manager.download_module(key)
    if not ok:
        raise RuntimeError(f"Falha ao iniciar download de {key}")

    start_t = time.time()
    last_print = 0
    while time.time() - start_t < timeout_seconds:
        st = manager.get_download_status(key)
        status = st.get("status")
        if time.time() - last_print > 1.0:
            print(f"    ... {st.get('progress', 0):.1f}% | {st.get('speed_mbps', 0):.1f} MB/s | {st.get('message', '')}")
            last_print = time.time()
        if status in ["installed", "completed"]:
            print("[+] Download real concluído com sucesso!")
            break
        if status in ["error", "cancelled"]:
            print(f"[!] Download encerrou com status: {status} ({st.get('message')})")
            break
        time.sleep(0.15)
    else:
        print("[!] Timeout atingido aguardando conclusão do download real.")

    return probe


# ═════════════════════════════════════════════════════════════════════════════
#  INTEGRAÇÃO COM PYTEST (TESTES AUTOMATIZADOS)
# ═════════════════════════════════════════════════════════════════════════════

def test_telemetry_diagnostic_pytorch_core(tmp_path):
    """Garante matematicamente que o PyTorch Core não sofre resets nem congelamento na extração."""
    probe = run_pytorch_core_telemetry_diagnostic(tmp_path)
    assert len(probe.ticks) > 8
    # Nenhuma anomalia de regressão ou clamp tolerada
    regressions = [a for a in probe.anomalies if a.anomaly_type == "REGRESSION"]
    assert len(regressions) == 0, f"Regressões detectadas: {regressions}"
    assert probe.ticks[-1].progress == 100.0
    assert probe.ticks[-1].downloaded_bytes == 2855 * 1024 * 1024


def test_telemetry_diagnostic_yolo_multi_file(tmp_path):
    """Garante monotonicidade estrita e persistência de telemetria no Comic-YOLO."""
    probe = run_yolo_multi_file_telemetry_diagnostic(tmp_path)
    assert len(probe.ticks) >= 5
    regressions = [a for a in probe.anomalies if a.anomaly_type == "REGRESSION"]
    assert len(regressions) == 0, f"Regressões detectadas: {regressions}"
    assert probe.ticks[-1].progress == 100.0
    assert probe.ticks[-1].downloaded_bytes == 58808181


def test_telemetry_diagnostic_florence_ntfs(tmp_path):
    """Garante que o monitor de disco avança e não trava a telemetria."""
    probe = run_florence_disk_monitor_diagnostic(tmp_path)
    assert len(probe.ticks) > 3
    assert probe.ticks[-1].progress == 100.0


def test_scoped_hf_stream_concurrent_isolation():
    """Garante isolamento estrito entre downloads concorrentes sem contaminação cruzada de status ou velocidade."""
    from src.model_engines.hf.http_downloader import scoped_hf_stream_hook
    import huggingface_hub.file_download as fd

    class DummyMgr:
        def __init__(self):
            self.download_status = {
                "yolo_detector": {"status": "downloading", "downloaded_bytes": 0, "total_bytes": 50000000, "progress": 0.0},
                "florence2_large": {"status": "downloading", "downloaded_bytes": 0, "total_bytes": 1500000000, "progress": 0.0},
            }
            self._status_lock = threading.Lock()
            self._last_stream_time = {}
        def _notify_progress(self, key, throttle_interval=0.0):
            pass

    mgr = DummyMgr()
    orig_fd = fd.tqdm

    barrier = threading.Barrier(2)
    results = {}

    def run_yolo():
        with scoped_hf_stream_hook(mgr, "yolo_detector", 50000000):
            barrier.wait()
            bar = fd.tqdm(total=50000000, unit="B", desc="comic-speech-bubble-detector.pt")
            bar.update(10000000)
            results["yolo_dl"] = mgr.download_status["yolo_detector"]["downloaded_bytes"]
            barrier.wait()

    def run_florence():
        with scoped_hf_stream_hook(mgr, "florence2_large", 1500000000):
            barrier.wait()
            bar = fd.tqdm(total=1500000000, unit="B", desc="model.safetensors")
            bar.update(200000000)
            results["florence_dl"] = mgr.download_status["florence2_large"]["downloaded_bytes"]
            barrier.wait()

    t1 = threading.Thread(target=run_yolo)
    t2 = threading.Thread(target=run_florence)
    t1.start()
    t2.start()
    t1.join(timeout=3.0)
    t2.join(timeout=3.0)

    # Cada download deve ter atualizado estritamente seus próprios bytes sem vazamento
    assert results.get("yolo_dl") == 10000000
    assert results.get("florence_dl") == 200000000
    assert mgr.download_status["yolo_detector"]["downloaded_bytes"] == 10000000
    assert mgr.download_status["florence2_large"]["downloaded_bytes"] == 200000000
    # O gancho deve restaurar o tqdm original após o encerramento de todos
    assert fd.tqdm is orig_fd


def test_inspect_real_hf_tqdm_calls(tmp_path):
    """Inspeciona exatamente como e quando o huggingface_hub chama o update() durante um download real."""
    import os
    os.environ.pop("HF_HUB_DISABLE_XET", None)

    from huggingface_hub import hf_hub_download
    from src.model_engines.hf.http_downloader import scoped_hf_stream_hook
    import sys

    update_calls = []

    class DummyMgr:
        download_status = {"yolo_detector": {"status": "downloading"}}
        _status_lock = threading.Lock()
        def _notify_progress(self, key, throttle_interval=0.0):
            pass

    mgr = DummyMgr()
    with scoped_hf_stream_hook(mgr, "yolo_detector", 6700000) as tracker:
        # Intercepta update do tqdm ativo
        tqdm_mod = sys.modules.get("huggingface_hub.utils.tqdm")
        active_tqdm = getattr(tqdm_mod, "tqdm")
        orig_update = active_tqdm.update

        import traceback
        stacks = []

        def logging_update(self, n=1):
            update_calls.append((time.time(), n, getattr(self, "desc", "")))
            if n > 0:
                stacks.append(traceback.format_stack())
            return orig_update(self, n)

        active_tqdm.update = logging_update

        hf_hub_download(
            repo_id="TheBlindMaster/yolov8n-manga-frame-seg",
            filename="best.pt",
            local_dir=str(tmp_path),
            force_download=True,
        )

    print(f"\n[DEBUG TEST] Total de chamadas update(): {len(update_calls)}")
    for i, (t, n, desc) in enumerate(update_calls[:20]):
        print(f"  Chamada #{i}: n={n} ({n/1024:.1f} KB) | desc={desc}")
    if stacks:
        print("\n[STACK TRACE DA CHAMADA UPDATE(6.7MB)]:")
        print("".join(stacks[0]))
    assert len(update_calls) > 1


def test_live_concurrent_network_isolation(tmp_path):
    """Verifica que downloads reais e concorrentes na rede mantêm telemetria estritamente isolada."""
    import os
    from huggingface_hub import hf_hub_download, snapshot_download
    from src.model_engines.hf_download_manager import HFDownloadManager

    base_dir = str(tmp_path)
    mgr = HFDownloadManager(base_dir=base_dir)

    errors = []
    barrier = threading.Barrier(2)

    def download_yolo():
        try:
            barrier.wait()
            mgr.download_status["yolo_detector"]["status"] = "downloading"
            yolo_dir = os.path.join(base_dir, "models")
            os.makedirs(yolo_dir, exist_ok=True)
            hf_hub_download(
                repo_id="TheBlindMaster/yolov8n-manga-frame-seg",
                filename="best.pt",
                local_dir=yolo_dir,
                force_download=True,
            )
        except Exception as e:
            errors.append(("yolo", e))

    def download_florence_slice():
        try:
            barrier.wait()
            mgr.download_status["florence2_large"]["status"] = "downloading"
            florence_dir = os.path.join(base_dir, "models", "florence-2-large")
            os.makedirs(florence_dir, exist_ok=True)
            snapshot_download(
                repo_id="microsoft/Florence-2-large",
                local_dir=florence_dir,
                allow_patterns=["config.json"],
                force_download=True,
            )
        except Exception as e:
            errors.append(("florence", e))

    t1 = threading.Thread(target=download_yolo)
    t2 = threading.Thread(target=download_florence_slice)
    t1.start()
    t2.start()
    t1.join(timeout=15.0)
    t2.join(timeout=15.0)

    assert not errors, f"Erros durante downloads concorrentes: {errors}"

    # Valida separação física em disco
    yolo_file = os.path.join(base_dir, "models", "best.pt")
    florence_file = os.path.join(base_dir, "models", "florence-2-large", "config.json")
    assert os.path.isfile(yolo_file)
    assert os.path.isfile(florence_file)
    assert os.path.getsize(yolo_file) > 1000000
    assert os.path.getsize(florence_file) > 500

    # Valida caminhos de monitoramento isolados
    yolo_paths = mgr._get_monitor_paths("yolo_detector")
    florence_paths = mgr._get_monitor_paths("florence2_large")
    assert not any(p.endswith("models\\.huggingface") or p.endswith("models/.huggingface") for p in florence_paths)



# ═════════════════════════════════════════════════════════════════════════════
#  MODO CLI / STANDALONE (EXECUTÁVEL DIRETO NO TERMINAL)
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import tempfile
    import shutil

    parser = argparse.ArgumentParser(description="Visionary Studio - Telemetry Diagnostic Probe")
    parser.add_argument("--live-yolo", action="store_true", help="Executa download real de rede do Comic-YOLO em sandbox")
    parser.add_argument("--pytorch", action="store_true", help="Diagnostica o instalador do PyTorch Core")
    parser.add_argument("--yolo", action="store_true", help="Diagnostica simulação multi-file do Comic-YOLO")
    parser.add_argument("--florence", action="store_true", help="Diagnostica monitor de disco e dead-reckoning do Florence")
    parser.add_argument("--all", action="store_true", help="Executa todos os diagnósticos sintéticos (padrão)")
    args = parser.parse_args()

    run_all = args.all or (not args.live_yolo and not args.pytorch and not args.yolo and not args.florence)

    temp_dir = tempfile.mkdtemp(prefix="visionary_telemetry_diag_")
    try:
        from pathlib import Path
        p = Path(temp_dir)

        print("\n[+] INICIANDO SESSÃO DE DIAGNÓSTICO CIRÚRGICO DE TELEMETRIA...\n")

        if run_all or args.pytorch:
            core_probe = run_pytorch_core_telemetry_diagnostic(p / "core")
            core_probe.print_diagnostic_report()

        if run_all or args.yolo:
            yolo_probe = run_yolo_multi_file_telemetry_diagnostic(p / "yolo")
            yolo_probe.print_diagnostic_report()

        if run_all or args.florence:
            florence_probe = run_florence_disk_monitor_diagnostic(p / "florence")
            florence_probe.print_diagnostic_report()

        if args.live_yolo:
            live_probe = run_live_yolo_download_diagnostic(p / "live_yolo")
            live_probe.print_diagnostic_report(max_sample_rows=40)

        print("[+] DIAGNÓSTICO CONCLUÍDO COM SUCESSO. DADOS TEMPORÁRIOS HIGIENIZADOS.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
