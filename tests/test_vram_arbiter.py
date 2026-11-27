import pytest
from unittest.mock import patch, MagicMock
from src.utils.vram_arbiter import VramArbiter, GpuTier, VramPhase


class TestVramArbiter:
    def test_singleton(self):
        a1 = VramArbiter.get_instance()
        a2 = VramArbiter.get_instance()
        assert a1 is a2

    def test_tier_classification_cpu(self):
        arbiter = VramArbiter()
        with patch.object(arbiter, "get_gpu_info", return_value={"available": False, "total_mb": 0, "free_mb": 0, "device_name": ""}):
            assert arbiter.get_tier() == GpuTier.CPU

    def test_tier_classification_low(self):
        arbiter = VramArbiter()
        # 4GB VRAM
        with patch.object(arbiter, "get_gpu_info", return_value={"available": True, "total_mb": 4096, "free_mb": 2048, "device_name": "GTX 1650"}):
            assert arbiter.get_tier() == GpuTier.LOW
        # 6GB VRAM exactly
        with patch.object(arbiter, "get_gpu_info", return_value={"available": True, "total_mb": 6144, "free_mb": 3000, "device_name": "RTX 3060 6GB"}):
            assert arbiter.get_tier() == GpuTier.LOW

    def test_tier_classification_mid(self):
        arbiter = VramArbiter()
        # 8GB VRAM
        with patch.object(arbiter, "get_gpu_info", return_value={"available": True, "total_mb": 8192, "free_mb": 5000, "device_name": "RTX 3070"}):
            assert arbiter.get_tier() == GpuTier.MID

    def test_tier_classification_high(self):
        arbiter = VramArbiter()
        # 16GB VRAM
        with patch.object(arbiter, "get_gpu_info", return_value={"available": True, "total_mb": 16384, "free_mb": 12000, "device_name": "RTX 4080"}):
            assert arbiter.get_tier() == GpuTier.HIGH

    def test_recommended_ocr_batch_size(self):
        arbiter = VramArbiter()
        with patch.object(arbiter, "get_tier", return_value=GpuTier.LOW):
            assert arbiter.get_recommended_ocr_batch_size() == 4
        with patch.object(arbiter, "get_tier", return_value=GpuTier.MID):
            assert arbiter.get_recommended_ocr_batch_size() == 8
        with patch.object(arbiter, "get_tier", return_value=GpuTier.HIGH):
            assert arbiter.get_recommended_ocr_batch_size() == 16
        with patch.object(arbiter, "get_tier", return_value=GpuTier.CPU):
            assert arbiter.get_recommended_ocr_batch_size() == 2

    def test_cap_context_for_tier(self):
        arbiter = VramArbiter()
        with patch.object(arbiter, "get_tier", return_value=GpuTier.LOW):
            assert arbiter.cap_context_for_tier(8192) == 2048
            assert arbiter.cap_context_for_tier(1024) == 1024
        with patch.object(arbiter, "get_tier", return_value=GpuTier.MID):
            assert arbiter.cap_context_for_tier(8192) == 4096
            assert arbiter.cap_context_for_tier(2048) == 2048
        with patch.object(arbiter, "get_tier", return_value=GpuTier.HIGH):
            assert arbiter.cap_context_for_tier(8192) == 8192

    @patch("src.utils.vram_arbiter.unload_ollama_models")
    @patch("src.utils.vram_arbiter.cleanup_gpu_memory")
    def test_prepare_for_phase_ocr_low_tier(self, mock_cleanup, mock_unload):
        arbiter = VramArbiter()
        with patch.object(arbiter, "get_tier", return_value=GpuTier.LOW):
            res = arbiter.prepare_for_phase(VramPhase.OCR)
            assert res["phase"] == "ocr"
            assert "unloaded_ollama" in res["actions"]
            assert "cleaned_torch_cache" in res["actions"]
            mock_unload.assert_called_once()
            mock_cleanup.assert_called_once_with(force_ipc=True)

    @patch("src.utils.vram_arbiter.unload_ollama_models")
    @patch("src.utils.vram_arbiter.cleanup_gpu_memory")
    def test_prepare_for_phase_ocr_high_tier(self, mock_cleanup, mock_unload):
        arbiter = VramArbiter()
        with patch.object(arbiter, "get_tier", return_value=GpuTier.HIGH):
            res = arbiter.prepare_for_phase(VramPhase.OCR)
            assert res["phase"] == "ocr"
            mock_unload.assert_not_called()
            mock_cleanup.assert_not_called()

    @patch("src.utils.vram_arbiter.cleanup_gpu_memory")
    def test_prepare_for_phase_translation(self, mock_cleanup):
        arbiter = VramArbiter()
        res = arbiter.prepare_for_phase(VramPhase.TRANSLATION)
        assert res["phase"] == "translation"
        mock_cleanup.assert_called_once_with(force_ipc=True)

    @patch("src.utils.vram_arbiter.cleanup_gpu_memory")
    def test_prepare_for_phase_idle(self, mock_cleanup):
        arbiter = VramArbiter()
        res = arbiter.prepare_for_phase(VramPhase.IDLE)
        assert res["phase"] == "idle"
        mock_cleanup.assert_called_once_with(force_ipc=False)

    @patch("src.utils.vram_arbiter.unload_ollama_models")
    @patch("src.utils.vram_arbiter.cleanup_gpu_memory")
    def test_ensure_headroom_mb_sufficient(self, mock_cleanup, mock_unload):
        arbiter = VramArbiter()
        with patch.object(arbiter, "get_gpu_info", return_value={"available": True, "free_mb": 5000, "total_mb": 8000, "device_name": "GPU"}):
            ok, free = arbiter.ensure_headroom_mb(2000)
            assert ok is True
            assert free == 5000
            mock_cleanup.assert_not_called()
            mock_unload.assert_not_called()

    @patch("src.utils.vram_arbiter.unload_ollama_models")
    @patch("src.utils.vram_arbiter.cleanup_gpu_memory")
    def test_ensure_headroom_mb_clean_torch_first(self, mock_cleanup, mock_unload):
        arbiter = VramArbiter()
        # First call: 1500 MB (insufficient for 2000 MB required)
        # Second call (after torch cleanup): 2500 MB (now sufficient)
        call_counts = [0]
        def mock_gpu_info():
            call_counts[0] += 1
            if call_counts[0] == 1:
                return {"available": True, "free_mb": 1500, "total_mb": 8000, "device_name": "GPU"}
            return {"available": True, "free_mb": 2500, "total_mb": 8000, "device_name": "GPU"}

        with patch.object(arbiter, "get_gpu_info", side_effect=mock_gpu_info):
            ok, free = arbiter.ensure_headroom_mb(2000)
            assert ok is True
            assert free == 2500
            mock_cleanup.assert_called_once_with(force_ipc=True)
            mock_unload.assert_not_called()

    @patch("src.utils.vram_arbiter.unload_ollama_models")
    @patch("src.utils.vram_arbiter.cleanup_gpu_memory")
    def test_ensure_headroom_mb_clean_ollama_second(self, mock_cleanup, mock_unload):
        arbiter = VramArbiter()
        # Call 1: 1000 MB (insufficient)
        # Call 2 (after torch cleanup): 1200 MB (still insufficient)
        # Call 3 (after ollama unload + cleanup): 3000 MB (sufficient)
        call_counts = [0]
        def mock_gpu_info():
            call_counts[0] += 1
            if call_counts[0] == 1:
                return {"available": True, "free_mb": 1000, "total_mb": 8000, "device_name": "GPU"}
            elif call_counts[0] == 2:
                return {"available": True, "free_mb": 1200, "total_mb": 8000, "device_name": "GPU"}
            return {"available": True, "free_mb": 3000, "total_mb": 8000, "device_name": "GPU"}

        with patch.object(arbiter, "get_gpu_info", side_effect=mock_gpu_info):
            ok, free = arbiter.ensure_headroom_mb(2000)
            assert ok is True
            assert free == 3000
            mock_unload.assert_called_once()
