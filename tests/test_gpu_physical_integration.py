import pytest
import sys
try:
    import torch
except ImportError:
    torch = None
from src.utils.gpu_utils import setup_cuda_env, cleanup_gpu_memory
from src.utils.vram_arbiter import vram_arbiter, GpuTier, VramPhase
from src.api_services.hardware_service import HardwareService

pytestmark = pytest.mark.skipif(
    not (torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available()),
    reason="Physical NVIDIA CUDA GPU is not available on this host",
)


class TestGpuPhysicalIntegration:
    """
    Testes de integração física com a GPU NVIDIA real e subsistema CUDA.
    Verifica alocação física de tensores, resolução de memória, transições
    de fase do VRAM Arbiter e serviço de telemetria de hardware.
    """

    def test_physical_cuda_device_properties(self):
        setup_cuda_env()
        assert torch.cuda.device_count() >= 1
        dev_name = torch.cuda.get_device_name(0)
        assert isinstance(dev_name, str) and len(dev_name) > 0
        props = torch.cuda.get_device_properties(0)
        assert props.total_memory > 1024 * 1024 * 1024  # Pelo menos 1GB
        assert props.major >= 5  # Arquitetura Maxwell ou superior

    def test_physical_cuda_tensor_allocation_and_cleanup(self):
        cleanup_gpu_memory(force_ipc=True)
        initial_alloc = torch.cuda.memory_allocated(0)

        # Aloca tensor de ~64MB na GDDR física
        tensor = torch.zeros((1024, 1024, 16), dtype=torch.float32, device="cuda:0")
        allocated_with_tensor = torch.cuda.memory_allocated(0)
        assert allocated_with_tensor > initial_alloc

        del tensor
        cleanup_gpu_memory(force_ipc=True)
        final_alloc = torch.cuda.memory_allocated(0)
        # Permite pequena variação de bookkeeping do PyTorch CUDA context (< 2MB)
        assert final_alloc <= initial_alloc + 2 * 1024 * 1024

    def test_vram_arbiter_physical_detection_and_phases(self):
        info = vram_arbiter.get_gpu_info()
        assert info["available"] is True
        assert info["total_mb"] > 2048.0
        assert info["free_mb"] > 0.0
        assert isinstance(info["device_name"], str)

        tier = vram_arbiter.get_tier()
        assert tier in (GpuTier.LOW, GpuTier.MID, GpuTier.HIGH)

        # Executa ciclo completo de transição de fases no hardware físico
        vram_arbiter.prepare_phase(VramPhase.LAYOUT)
        assert vram_arbiter.current_phase == VramPhase.LAYOUT

        vram_arbiter.prepare_phase(VramPhase.OCR)
        assert vram_arbiter.current_phase == VramPhase.OCR

        vram_arbiter.prepare_phase(VramPhase.TRANSLATION)
        assert vram_arbiter.current_phase == VramPhase.TRANSLATION

        vram_arbiter.prepare_phase(VramPhase.IDLE)
        assert vram_arbiter.current_phase == VramPhase.IDLE

        # Headroom de 500MB em GPU física
        success, free_mb = vram_arbiter.ensure_headroom_mb(500.0)
        assert success is True
        assert free_mb >= 500.0

    def test_hardware_service_physical_stats(self):
        service = HardwareService()
        stats = service.getHardwareStats()

        assert stats["gpu_name"] != "Nenhum / CPU"
        assert stats["vram_reserved_gb"] > 0
        assert stats["gpu_tier"] in ("low", "mid", "high")
        assert stats["cuda_version"] is not None
        assert isinstance(stats["cuda_version"], str)
