"""
Testes de acurácia determinística de porcentagem (%) na Central de Módulos:
- Florence-2 e Comic-YOLO (ledger por arquivo, zero dupla contagem em retry/resume, isolamento concorrente por manifesto)
- PyTorch Core (resolução dry-run JSON, download exato por wheel com SHA-256, extração ZIP exata em profundidade total,
  e proteção contra salto prematuro de 74.8% no fallback do pip)
"""

import hashlib
import io
import json
import os
import threading
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from src.model_engines.core_engine_installer import CoreEngineInstaller
from src.model_engines.core_installer.pip_runner import run_pip_install_worker
from src.model_engines.core_installer.wheelhouse_plan import (
    download_wheelhouse_plan,
    inspect_wheels_unpacked_manifest,
    measure_site_packages_entries_bytes,
    resolve_pip_install_plan,
)
from src.model_engines.hf.stream_tracker import DownloadStreamTracker, scoped_hf_stream_hook
from src.model_manager import ModelManager


def _make_valid_wheel_bytes(pkg_name: str, files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in files.items():
            zf.writestr(rel_path, content)
        zf.writestr(f"{pkg_name}-1.0.0.dist-info/METADATA", f"Name: {pkg_name}\nVersion: 1.0.0\n".encode("utf-8"))
        zf.writestr(f"{pkg_name}-1.0.0.dist-info/WHEEL", b"Wheel-Version: 1.0\n")
    return buf.getvalue()


# ═════════════════════════════════════════════════════════════════════════════
# 1. Florence-2 & Comic-YOLO — Ledger Determinístico por Arquivo
# ═════════════════════════════════════════════════════════════════════════════


def test_hf_stream_tracker_retry_does_not_double_count_bytes(tmp_path):
    """Se um arquivo falhar na metade e reabrir a barra tqdm do zero, os bytes nunca são somados duas vezes."""
    import huggingface_hub.file_download as fd

    manager = ModelManager(base_dir=str(tmp_path))
    manager.download_status["florence2_large"] = {
        "status": "downloading",
        "progress": 0.0,
        "downloaded_bytes": 0,
        "total_bytes": 10000,
        "message": "",
    }
    manifest_files = {
        "model.safetensors": {"size": 8000, "local_path": str(tmp_path / "model.safetensors"), "pre_bytes": 0, "completed": False},
        "config.json": {"size": 2000, "local_path": str(tmp_path / "config.json"), "pre_bytes": 0, "completed": False},
    }

    with scoped_hf_stream_hook(
        manager,
        "florence2_large",
        target_total_bytes=10000,
        initial_bytes=0,
        manifest_files=manifest_files,
    ):
        # Tentativa 1: baixa 4000 de 8000 (40% do total) e cai a conexão
        bar_try1 = fd.tqdm(total=8000, unit="B", desc="model.safetensors")
        bar_try1.update(4000)
        bar_try1.close()
        st1 = manager.get_download_status("florence2_large")
        assert st1["downloaded_bytes"] == 4000
        assert st1["progress"] == 40.0

        # Tentativa 2 (retry do zero para o MESMO arquivo): baixa 4000 novamente -> NÃO pode virar 8000 (80%)!
        bar_try2 = fd.tqdm(total=8000, unit="B", desc="model.safetensors")
        bar_try2.update(4000)
        st2 = manager.get_download_status("florence2_large")
        assert st2["downloaded_bytes"] == 4000
        assert st2["progress"] == 40.0

        # Continua até concluir o arquivo (8000) -> 80% exato
        bar_try2.update(4000)
        bar_try2.close()
        st3 = manager.get_download_status("florence2_large")
        assert st3["downloaded_bytes"] == 8000
        assert st3["progress"] == 80.0

        # Segundo arquivo (2000) -> 10000 / 10000 (cap de 99.0% até validação final)
        bar_cfg = fd.tqdm(total=2000, unit="B", desc="config.json")
        bar_cfg.update(2000)
        bar_cfg.close()
        st4 = manager.get_download_status("florence2_large")
        assert st4["downloaded_bytes"] == 10000
        assert st4["progress"] == 99.0


def test_hf_stream_tracker_redownload_of_precompleted_file_avoids_overcounting(tmp_path):
    """Se um arquivo pré-existente no manifesto for rebaixado pelo HF (ex: etag mudou), desconta da base uma vez."""
    import huggingface_hub.file_download as fd

    manager = ModelManager(base_dir=str(tmp_path))
    manager.download_status["florence2"] = {
        "status": "downloading",
        "progress": 50.0,
        "downloaded_bytes": 5000,
        "total_bytes": 10000,
        "message": "",
    }
    manifest_files = {
        "config.json": {"size": 5000, "local_path": str(tmp_path / "config.json"), "pre_bytes": 5000, "completed": True},
        "model.safetensors": {"size": 5000, "local_path": str(tmp_path / "model.safetensors"), "pre_bytes": 0, "completed": False},
    }

    with scoped_hf_stream_hook(
        manager,
        "florence2",
        target_total_bytes=10000,
        initial_bytes=5000,
        manifest_files=manifest_files,
    ) as tracker:
        # HF decide rebaixar config.json do zero: base cai de 5000 para 0 e file_progress["config.json"] vai a 5000
        bar_cfg = fd.tqdm(total=5000, unit="B", desc="config.json")
        bar_cfg.update(5000)
        bar_cfg.close()
        assert tracker.downloaded_bytes == 5000

        # Agora baixa metade de model.safetensors (2500) -> total exato 7500 / 10000 = 75.0%
        bar_st = fd.tqdm(total=5000, unit="B", desc="model.safetensors")
        bar_st.update(2500)
        bar_st.close()
        assert tracker.downloaded_bytes == 7500
        st = manager.get_download_status("florence2")
        assert st["progress"] == 75.0


def test_hf_concurrent_manifest_matching_handles_generic_filenames(tmp_path):
    """Arquivos genéricos (ex: README.md) são roteados ao modelo correto pelo manifesto mesmo com downloads concorrentes."""
    import huggingface_hub.file_download as fd

    manager = ModelManager(base_dir=str(tmp_path))
    manager.download_status["yolo_detector"] = {
        "status": "downloading", "progress": 0.0, "downloaded_bytes": 0, "total_bytes": 1000, "message": "",
    }
    manager.download_status["florence2_large"] = {
        "status": "downloading", "progress": 0.0, "downloaded_bytes": 0, "total_bytes": 4000, "message": "",
    }
    yolo_manifest = {
        "best.pt": {"size": 1000, "local_path": str(tmp_path / "models" / "best.pt"), "pre_bytes": 0, "completed": False},
    }
    florence_manifest = {
        "README.md": {"size": 1000, "local_path": str(tmp_path / "models" / "florence-2-large" / "README.md"), "pre_bytes": 0, "completed": False},
        "model.safetensors": {"size": 3000, "local_path": str(tmp_path / "models" / "florence-2-large" / "model.safetensors"), "pre_bytes": 0, "completed": False},
    }

    barrier = threading.Barrier(2)
    errors = []

    def worker_yolo():
        try:
            with scoped_hf_stream_hook(manager, "yolo_detector", 1000, manifest_files=yolo_manifest):
                barrier.wait()
                bar = fd.tqdm(total=1000, unit="B", desc="best.pt")
                bar.update(500)
                bar.close()
                barrier.wait()
        except Exception as exc:
            errors.append(exc)

    def worker_florence():
        try:
            with scoped_hf_stream_hook(manager, "florence2_large", 4000, manifest_files=florence_manifest):
                barrier.wait()
                # Simula worker filho de ThreadPoolExecutor (thread ID diferente da thread que abriu o hook!)
                def child_fn():
                    bar = fd.tqdm(total=1000, unit="B", desc="README.md")
                    bar.update(1000)
                    bar.close()
                ct = threading.Thread(target=child_fn)
                ct.start()
                ct.join(timeout=2.0)
                barrier.wait()
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=worker_yolo)
    t2 = threading.Thread(target=worker_florence)
    t1.start()
    t2.start()
    t1.join(timeout=3.0)
    t2.join(timeout=3.0)

    assert not errors
    assert manager.download_status["yolo_detector"]["downloaded_bytes"] == 500
    assert manager.download_status["florence2_large"]["downloaded_bytes"] == 1000
    assert manager.download_status["florence2_large"]["progress"] == 25.0


# ═════════════════════════════════════════════════════════════════════════════
# 2. PyTorch Core — Wheelhouse Determinístico + Fallback Blindado
# ═════════════════════════════════════════════════════════════════════════════


def test_resolve_pip_install_plan_parses_report_and_probes_exact_sizes(tmp_path):
    """Valida resolução de JSON do pip --dry-run --report, HEAD/Range 0-0 e fallback limpo em sdist."""
    report_payload = {
        "version": "1",
        "install": [
            {
                "metadata": {"name": "torch", "version": "2.11.0+cu128"},
                "download_info": {
                    "url": "https://download.pytorch.org/whl/cu128/torch-2.11.0%2Bcu128-cp311-cp311-win_amd64.whl",
                    "archive_info": {"hashes": {"sha256": "a" * 64}},
                },
            },
            {
                "metadata": {"name": "einops", "version": "0.8.2"},
                "download_info": {
                    "url": "https://files.pythonhosted.org/packages/einops-0.8.2-py3-none-any.whl",
                    "archive_info": {"hash": "sha256=" + ("b" * 64)},
                },
            },
        ],
    }

    def fake_subprocess_run(cmd, **kwargs):
        rep_idx = cmd.index("--report") + 1
        with open(cmd[rep_idx], "w", encoding="utf-8") as fh:
            json.dump(report_payload, fh)
        return MagicMock(returncode=0, stdout="", stderr="")

    class FakeSession:
        def head(self, url, **kwargs):
            if "torch-" in url:
                return MagicMock(status_code=200, headers={"Content-Length": "2000000000"})
            # Simula servidor sem Content-Length no HEAD para testar fallback Range 0-0
            return MagicMock(status_code=200, headers={})

        def get(self, url, **kwargs):
            cm = MagicMock()
            resp = MagicMock(status_code=206, headers={"Content-Range": "bytes 0-0/50000"})
            cm.__enter__.return_value = resp
            return cm

        def close(self):
            pass

    with patch("src.model_engines.core_installer.wheelhouse_plan.subprocess.run", side_effect=fake_subprocess_run), \
         patch("src.model_engines.core_installer.wheelhouse_plan.requests.Session", return_value=FakeSession()):
        plan = resolve_pip_install_plan(
            "python.exe",
            ["python.exe", "-u", "-m", "pip", "install", "--prefer-binary", "-r", "requirements-ai.txt"],
        )

    assert plan is not None
    assert plan["all_satisfied"] is False
    assert plan["total_download_bytes"] == 2000050000
    assert len(plan["items"]) == 2
    assert plan["items"][0]["filename"] == "torch-2.11.0+cu128-cp311-cp311-win_amd64.whl"
    assert plan["items"][0]["sha256"] == "a" * 64
    assert plan["items"][1]["size_bytes"] == 50000
    assert plan["items"][1]["sha256"] == "b" * 64

    # Se houver um sdist (.tar.gz), deve retornar None para ativar o fallback seguro do pip
    sdist_report = {
        "install": [
            {
                "metadata": {"name": "legacy_pkg", "version": "1.0"},
                "download_info": {"url": "https://files.pythonhosted.org/legacy_pkg-1.0.tar.gz"},
            }
        ]
    }

    def fake_sdist_run(cmd, **kwargs):
        rep_idx = cmd.index("--report") + 1
        with open(cmd[rep_idx], "w", encoding="utf-8") as fh:
            json.dump(sdist_report, fh)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("src.model_engines.core_installer.wheelhouse_plan.subprocess.run", side_effect=fake_sdist_run):
        assert resolve_pip_install_plan("python.exe", ["python.exe", "-m", "pip", "install", "legacy_pkg"]) is None


def test_download_wheelhouse_plan_and_unpacked_zip_measurement(tmp_path):
    """Valida download com resume .part, validação SHA-256, leitura ZIP exata e varredura em profundidade total."""
    w1_bytes = _make_valid_wheel_bytes(
        "torch",
        {
            "torch/__init__.py": b"x" * 1000,
            "torch/sub/deep/level4/kernel.bin": b"K" * 5000,  # depth >= 4 (antes ignorado por depth < 2!)
        },
    )
    w2_bytes = _make_valid_wheel_bytes(
        "einops",
        {
            "einops/__init__.py": b"e" * 2000,
        },
    )
    w1_sha = hashlib.sha256(w1_bytes).hexdigest()
    w2_sha = hashlib.sha256(w2_bytes).hexdigest()

    wheelhouse_dir = tmp_path / "wheelhouse"
    wheelhouse_dir.mkdir()
    # Simula resume parcial (.part já com os primeiros 400 bytes de w1)
    (wheelhouse_dir / "torch-1.0.0-py3-none-any.whl.part").write_bytes(w1_bytes[:400])

    plan_items = [
        {
            "name": "torch",
            "version": "1.0.0",
            "url": "https://cdn.example/torch-1.0.0-py3-none-any.whl",
            "filename": "torch-1.0.0-py3-none-any.whl",
            "size_bytes": len(w1_bytes),
            "sha256": w1_sha,
            "is_local": False,
            "local_path": None,
        },
        {
            "name": "einops",
            "version": "1.0.0",
            "url": "https://cdn.example/einops-1.0.0-py3-none-any.whl",
            "filename": "einops-1.0.0-py3-none-any.whl",
            "size_bytes": len(w2_bytes),
            "sha256": w2_sha,
            "is_local": False,
            "local_path": None,
        },
    ]

    class FakeHttpSession:
        def get(self, url, headers=None, **kwargs):
            payload = w1_bytes if "torch-" in url else w2_bytes
            rng = (headers or {}).get("Range", "")
            cm = MagicMock()
            if rng.startswith("bytes="):
                start = int(rng.replace("bytes=", "").split("-")[0])
                body = payload[start:]
                resp = MagicMock(status_code=206)
                resp.raise_for_status = MagicMock()
                resp.iter_content.return_value = [body[:256], body[256:]]
            else:
                resp = MagicMock(status_code=200)
                resp.raise_for_status = MagicMock()
                resp.iter_content.return_value = [payload[:256], payload[256:]]
            cm.__enter__.return_value = resp
            return cm

        def close(self):
            pass

    observed_progress = []

    # Validação via streaming SHA-256 não deve reler o arquivo inteiro em disco após finalizar
    with patch("src.model_engines.core_installer.wheelhouse_plan.requests.Session", return_value=FakeHttpSession()), \
         patch("src.model_engines.core_installer.wheelhouse_plan._file_sha256", side_effect=AssertionError("Não deveria reler disco após stream SHA-256")):
        wheel_paths, net_bytes = download_wheelhouse_plan(
            plan_items,
            str(wheelhouse_dir),
            on_progress=lambda cur, tot, pkg: observed_progress.append((cur, tot, pkg)),
        )

    assert len(wheel_paths) == 2
    assert net_bytes == len(w1_bytes) + len(w2_bytes)
    # Monotonicidade e nunca excede o total exato
    assert observed_progress[-1][0] == net_bytes
    assert all(cur <= tot for cur, tot, _ in observed_progress)

    # Verifica leitura do Central Directory ZIP
    exact_unpacked, top_entries = inspect_wheels_unpacked_manifest(wheel_paths)
    assert "torch" in top_entries
    assert "einops" in top_entries
    assert exact_unpacked >= 1000 + 5000 + 2000

    # Descompacta ambos os wheels em um site-packages falso e verifica medição EXATA (incluindo depth >= 4)
    fake_sp = tmp_path / "site-packages"
    fake_sp.mkdir()
    for wp in wheel_paths:
        with zipfile.ZipFile(wp, "r") as zf:
            zf.extractall(fake_sp)
    # __pycache__ deve ser ignorado na medição
    pycache = fake_sp / "torch" / "__pycache__"
    pycache.mkdir()
    (pycache / "__init__.cpython-311.pyc").write_bytes(b"P" * 99999)

    measured_bytes, _ = measure_site_packages_entries_bytes(str(fake_sp), top_entries)
    assert measured_bytes == exact_unpacked


def test_pip_fallback_does_not_jump_to_75_percent_on_small_wheel(tmp_path, monkeypatch):
    """Regressão crítica: 100% de um wheel pequeno (ex: einops 50 kB) NUNCA pode jogar o PyTorch para 74.8%."""
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    monkeypatch.delenv("VISIONARY_ENABLE_WHEELHOUSE_IN_TESTS", raising=False)

    installer = CoreEngineInstaller()
    installer._install_progress["status"] = "installing"
    observed_percents = []

    orig_notify = installer.notify_progress

    def capture_notify(throttle_interval=0.0):
        with installer._get_lock():
            observed_percents.append((
                installer._get_install_progress().get("percent", 0.0),
                installer._get_install_progress().get("message", ""),
            ))
        orig_notify(throttle_interval=0.0)

    installer.notify_progress = capture_notify

    fake_lines = [
        "Collecting einops==0.8.2\n",
        "Downloading einops-0.8.2-py3-none-any.whl (45 kB)\n",
        "100%\n",  # <- Este padrão antes disparava o bug elif pct_match and not mb_match -> 74.8%!
        "Progress 45000 of 45000\n",
        "Collecting torch==2.11.0+cu128\n",
        "Downloading torch-2.11.0%2Bcu128-cp311-cp311-win_amd64.whl (2.5 GB)\n",
        "Progress 500000000 of 2684354560\n",
    ]

    class FakeProc:
        def __init__(self):
            self.stdout = io.StringIO("".join(fake_lines))
            self.returncode = 0

        def wait(self):
            return 0

    with patch.object(installer, "_build_pip_install_args", return_value=(["python", "-m", "pip", "install", "-r", "req.txt"], None)), \
         patch.object(installer, "_detect_cuda_target", return_value="cu128"), \
         patch("src.model_engines.core_installer.pip_runner.subprocess.Popen", return_value=FakeProc()):
        run_pip_install_worker(installer)

    # Durante o download do einops (antes do torch completar), a % NÃO pode ter saltado acima de 5%!
    einops_ticks = [pct for pct, msg in observed_percents if "einops" in msg.lower()]
    assert einops_ticks, f"Esperava ticks do einops, recebeu: {observed_percents}"
    assert max(einops_ticks) < 5.0, f"Bug de salto prematuro detectado no einops: {observed_percents}"

    # No meio do download do torch (500 MB / ~2.85 GB), deve estar por volta de ~15% (nunca 74.8%)
    torch_ticks = [pct for pct, msg in observed_percents if "torch" in msg.lower() and pct < 100.0]
    assert torch_ticks
    assert max(torch_ticks) < 25.0
    assert installer.get_install_progress()["percent"] == 100.0
    assert installer.get_install_progress()["status"] == "completed"


def test_run_pip_install_worker_deterministic_wheelhouse_end_to_end(tmp_path, monkeypatch):
    """Valida fluxo completo do wheelhouse determinístico (resolve -> download -> extract ZIP -> 100%)."""
    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    monkeypatch.setenv("VISIONARY_ENABLE_WHEELHOUSE_IN_TESTS", "1")

    fake_sp = tmp_path / "Lib" / "site-packages"
    fake_sp.mkdir(parents=True)
    fake_py = tmp_path / "python.exe"
    fake_py.write_bytes(b"MZ")

    whl_bytes = _make_valid_wheel_bytes("torch", {"torch/__init__.py": b"T" * 4096, "torch/lib/core.dll": b"D" * 8192})
    local_whl = tmp_path / "src_wheels" / "torch-2.11.0-cp311-cp311-win_amd64.whl"
    local_whl.parent.mkdir(parents=True)
    local_whl.write_bytes(whl_bytes)

    plan = {
        "all_satisfied": False,
        "items": [
            {
                "name": "torch",
                "version": "2.11.0",
                "url": local_whl.as_uri(),
                "filename": local_whl.name,
                "size_bytes": len(whl_bytes),
                "sha256": hashlib.sha256(whl_bytes).hexdigest(),
                "is_local": True,
                "local_path": str(local_whl),
            }
        ],
        "total_download_bytes": 0,
    }

    installer = CoreEngineInstaller()
    installer._install_progress["status"] = "installing"
    history = []

    orig_notify = installer.notify_progress

    def capture_notify(throttle_interval=0.0):
        with installer._get_lock():
            history.append(installer._get_install_progress().get("percent", 0.0))
        orig_notify(throttle_interval=0.0)

    installer.notify_progress = capture_notify

    class FakeOfflinePipProc:
        def __init__(self, cmd, **kwargs):
            assert "--no-index" in cmd
            assert "--no-deps" in cmd
            with zipfile.ZipFile(local_whl, "r") as zf:
                zf.extractall(fake_sp)
            self.stdout = io.StringIO("Successfully installed torch-2.11.0\n")
            self.returncode = 0

        def wait(self):
            return 0

    with patch("src.model_engines.core_installer.pip_runner.sys.executable", str(fake_py)), \
         patch.object(installer, "_build_pip_install_args", return_value=([str(fake_py), "-m", "pip", "install", "-r", "req.txt"], None)), \
         patch.object(installer, "_detect_cuda_target", return_value="cu128"), \
         patch("src.model_engines.core_installer.pip_runner.resolve_pip_install_plan", return_value=plan), \
         patch("src.model_engines.core_installer.pip_runner.subprocess.Popen", side_effect=FakeOfflinePipProc):
        run_pip_install_worker(installer)

    prog = installer.get_install_progress()
    assert prog["status"] == "completed"
    assert prog["percent"] == 100.0
    # Monotonicidade estrita em toda a linha do tempo
    assert history == sorted(history)
    assert (fake_sp / "torch" / "lib" / "core.dll").is_file()
