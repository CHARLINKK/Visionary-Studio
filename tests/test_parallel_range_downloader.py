import io
import threading
import time
from unittest.mock import patch

import pytest

from src.model_engines.hf.http_downloader import (
    DownloadStreamTracker,
    _make_hooked_http_get,
    parallel_range_stream_to_writer,
    scoped_hf_stream_hook,
)


class _FakeRangeResponse:
    def __init__(self, body: bytes, status_code: int = 206, url: str = "https://cdn.example.com/model.safetensors", headers=None, fail_after_bytes: int = None, delay: float = 0.0):
        self._body = body
        self.status_code = status_code
        self.url = url
        base_headers = {"Content-Length": str(len(body))}
        if headers:
            base_headers.update(headers)
        self.headers = base_headers
        self._fail_after = fail_after_bytes
        self._delay = delay
        self.closed = False

    def iter_content(self, chunk_size: int = 262144):
        if self._delay > 0:
            time.sleep(self._delay)
        sent = 0
        for offset in range(0, len(self._body), chunk_size):
            if self.closed:
                raise IOError("Socket closed")
            piece = self._body[offset : offset + chunk_size]
            if self._fail_after is not None and sent + len(piece) > self._fail_after:
                partial = piece[: max(0, self._fail_after - sent)]
                if partial:
                    yield partial
                raise ConnectionError("Simulated mid-segment TCP reset")
            sent += len(piece)
            yield piece

    def close(self):
        self.closed = True


def test_parallel_range_out_of_order_commits_strictly_sequential():
    """Garante reconstrução byte-a-byte idêntica mesmo quando workers terminam fora de ordem."""
    total_size = 6 * 1024 * 1024  # 6 MB -> 6 segmentos de 1 MB
    source_data = bytes((i * 31 + 7) % 256 for i in range(total_size))
    seen_headers = []
    seen_lock = threading.Lock()

    class FakeSession:
        def __init__(self):
            self.trust_env = True

        def mount(self, prefix, adapter):
            pass

        def get(self, url, headers=None, stream=True, allow_redirects=True, proxies=None, timeout=None):
            with seen_lock:
                seen_headers.append((url, dict(headers or {})))
            rng = (headers or {}).get("Range", "")
            assert rng.startswith("bytes=")
            start_s, end_s = rng.replace("bytes=", "").split("-")
            start_i, end_i = int(start_s), int(end_s)
            slice_bytes = source_data[start_i : end_i + 1]
            # Atraso inverso: primeiros segmentos demoram mais para forçar chegadas fora de ordem
            seg_idx = start_i // (1024 * 1024)
            delay = max(0.0, (5 - seg_idx) * 0.015)
            resolved = "https://cdn-edge.example.org/blob/model.safetensors"
            return _FakeRangeResponse(slice_bytes, status_code=206, url=resolved, delay=delay)

        def close(self):
            pass

    output = io.BytesIO()
    counted_bytes = []

    with patch("src.model_engines.hf.http_downloader.requests.Session", FakeSession):
        ok = parallel_range_stream_to_writer(
            url="https://huggingface.co/org/repo/resolve/main/model.safetensors",
            write_fn=output.write,
            total_size=total_size,
            start_byte=0,
            flush_fn=output.flush,
            on_chunk=lambda nb: counted_bytes.append(nb),
            headers={"Authorization": "Bearer hf_secret_token", "User-Agent": "VisionaryTest"},
            max_workers=6,
        )

    assert ok is True
    assert output.getvalue() == source_data
    assert sum(counted_bytes) == total_size

    # Probe inicial vai para huggingface.co com Authorization; segmentos subsequentes vão direto para CDN sem Authorization
    cdn_calls = [(u, h) for u, h in seen_headers if "cdn-edge.example.org" in u]
    assert len(cdn_calls) == 5
    for _, hdrs in cdn_calls:
        assert "Authorization" not in hdrs
        assert "authorization" not in hdrs
        assert hdrs.get("User-Agent") == "VisionaryTest"


def test_parallel_range_mid_segment_retry_without_double_counting():
    """Verifica retomada de sub-range dentro de um segmento com falha parcial sem duplicar progresso."""
    total_size = 4 * 1024 * 1024
    source_data = bytes((i * 17 + 3) % 256 for i in range(total_size))
    seg1_failed_once = {"done": False}
    lock = threading.Lock()

    class FlakySession:
        def __init__(self):
            self.trust_env = True

        def mount(self, prefix, adapter):
            pass

        def get(self, url, headers=None, **kwargs):
            start_s, end_s = headers["Range"].replace("bytes=", "").split("-")
            start_i, end_i = int(start_s), int(end_s)
            slice_bytes = source_data[start_i : end_i + 1]
            with lock:
                if start_i == 1024 * 1024 and not seg1_failed_once["done"]:
                    seg1_failed_once["done"] = True
                    return _FakeRangeResponse(slice_bytes, status_code=206, url=url, fail_after_bytes=300 * 1024)
            return _FakeRangeResponse(slice_bytes, status_code=206, url=url)

        def close(self):
            pass

    output = io.BytesIO()
    total_reported = [0]

    with patch("src.model_engines.hf.http_downloader.requests.Session", FlakySession):
        ok = parallel_range_stream_to_writer(
            url="https://cdn.example.com/weights.pt",
            write_fn=output.write,
            total_size=total_size,
            on_chunk=lambda nb: total_reported.__setitem__(0, total_reported[0] + nb),
            max_workers=4,
        )

    assert ok is True
    assert seg1_failed_once["done"] is True
    assert output.getvalue() == source_data
    assert total_reported[0] == total_size


def test_parallel_range_fallback_when_server_returns_200():
    """Garante fallback limpo e sem efeitos colaterais se o servidor não suportar Range 206."""
    class NonRangeSession:
        def __init__(self):
            self.trust_env = True

        def mount(self, prefix, adapter):
            pass

        def get(self, url, headers=None, **kwargs):
            return _FakeRangeResponse(b"x" * 1024, status_code=200, url=url)

        def close(self):
            pass

    fallback_called = []

    def fake_orig_http_get(url, temp_file, *, proxies=None, resume_size=0, headers=None, expected_size=None, displayed_filename=None, _nb_retries=5, _tqdm_bar=None):
        fallback_called.append((url, expected_size))
        temp_file.write(b"fallback-ok")

    class DummyFdMod:
        tqdm = None

    hooked = _make_hooked_http_get(fake_orig_http_get, DummyFdMod)
    buf = io.BytesIO()

    with patch("src.model_engines.hf.http_downloader.requests.Session", NonRangeSession):
        hooked("https://example.com/file.bin", buf, expected_size=5 * 1024 * 1024)

    assert len(fallback_called) == 1
    assert buf.getvalue() == b"fallback-ok"


def test_global_stream_tqdm_propagates_cancel_interrupted_error():
    """Garante que cancel_event interrompe imediatamente o tqdm sem engolir InterruptedError."""
    import huggingface_hub.file_download as fd

    cancel_ev = threading.Event()
    cancel_ev.set()

    class DummyMgr:
        def __init__(self):
            self.download_status = {"yolo_detector": {"status": "downloading", "downloaded_bytes": 0, "total_bytes": 10000000}}
            self._status_lock = threading.Lock()
            self._cancel_events = {"yolo_detector": cancel_ev}
            self._last_stream_time = {}

        def _notify_progress(self, key, throttle_interval=0.0):
            pass

    mgr = DummyMgr()
    with scoped_hf_stream_hook(mgr, "yolo_detector", target_total_bytes=10000000):
        bar = fd.tqdm(total=10000000, unit="B", desc="best.pt")
        with pytest.raises(InterruptedError):
            bar.update(262144)


def test_stream_tracker_first_byte_anchor_avoids_handshake_dilution():
    """Verifica que latência prévia de DNS/TLS não dilui a velocidade inicial reportada."""
    trk = DownloadStreamTracker("florence2_large", target_total_bytes=100 * 1024 * 1024)
    t_handshake_done = time.time() + 5.0  # Simula 5s de resolução de manifesto/TLS antes do 1º byte
    with trk.lock:
        trk.record_chunk_locked(2 * 1024 * 1024, t_handshake_done)
        trk.record_chunk_locked(8 * 1024 * 1024, t_handshake_done + 0.2)
    # 8 MB em 0.2s = ~40 MB/s (não 10 MB / 5.2s = 1.9 MB/s)
    assert trk.speed_mbps >= 35.0
