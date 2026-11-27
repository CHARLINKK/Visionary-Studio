"""
Árbitro central de VRAM entre PyTorch (YOLO / Florence-2) e o Ollama.

Impede que os dois processos disputem a mesma placa simultaneamente e acionem o
"Shared GPU Memory Fallback" do Windows (que joga pesos na RAM pela PCIe e derruba
o throughput em 10x), além de prevenir OOM em GPUs de entrada (<= 6 GB).
"""

import os
import sys
import threading
from enum import Enum
from typing import Dict, Any, Tuple, Optional
from src.utils.gpu_utils import cleanup_gpu_memory, unload_ollama_models


class GpuTier(str, Enum):
    LOW = "low"     # <= 6144 MB (ex: GTX 1650/1660, RTX 2060, RTX 3050 Laptop, RTX 4050 6GB)
    MID = "mid"     # 6145 MB - 11000 MB (ex: RTX 3060 8GB, RTX 3070, RTX 4060)
    HIGH = "high"   # > 11000 MB (ex: RTX 3060 12GB, RTX 3080, RTX 4070/4080/4090)
    CPU = "cpu"     # Sem aceleração CUDA ativa


class VramPhase(str, Enum):
    IDLE = "idle"
    LAYOUT = "layout"           # YOLO detecção de balões e quadros (~500MB)
    OCR = "ocr"                 # Florence-2 tensores FP16 (~1200MB - 2800MB)
    TRANSLATION = "translation" # Ollama LLMs (~2000MB - 5500MB)


VRAMPhase = VramPhase


class VramArbiter:
    """
    Árbitro thread-safe para gerenciamento orquestrado de VRAM.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VramArbiter, cls).__new__(cls)
                cls._instance._current_phase = VramPhase.IDLE
                cls._instance._arbiter_lock = threading.RLock()
                cls._instance._static_device_name = None
            return cls._instance

    @classmethod
    def get_instance(cls) -> "VramArbiter":
        return cls()

    def get_gpu_info(self) -> Dict[str, Any]:
        """Obtém dados de memória da GPU atual de forma segura e defensiva."""
        try:
            torch = sys.modules.get("torch")
            if torch is None:
                try:
                    import torch
                except ImportError:
                    torch = None
            if torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available():
                dev_idx = torch.cuda.current_device() if hasattr(torch.cuda, "current_device") else 0
                if getattr(self, "_static_device_name", None) is None:
                    try:
                        self._static_device_name = torch.cuda.get_device_name(dev_idx)
                    except Exception:
                        self._static_device_name = "NVIDIA CUDA Device"

                free_bytes, total_bytes = torch.cuda.mem_get_info(dev_idx)
                alloc_bytes = torch.cuda.memory_allocated(dev_idx)
                res_bytes = torch.cuda.memory_reserved(dev_idx)
                mb = 1024 * 1024
                return {
                    "available": True,
                    "device_name": getattr(self, "_static_device_name", None) or "NVIDIA CUDA Device",
                    "total_mb": round(total_bytes / mb, 1),
                    "free_mb": round(free_bytes / mb, 1),
                    "allocated_mb": round(alloc_bytes / mb, 1),
                    "reserved_mb": round(res_bytes / mb, 1)
                }
        except Exception:
            pass

        return {
            "available": False,
            "device_name": "CPU",
            "total_mb": 0.0,
            "free_mb": 0.0,
            "allocated_mb": 0.0,
            "reserved_mb": 0.0
        }

    def get_tier(self) -> GpuTier:
        """Determina o tier de hardware com base na VRAM física total."""
        info = self.get_gpu_info()
        if not info["available"]:
            return GpuTier.CPU

        total = info["total_mb"]
        if total <= 6800.0:    # Margem segura para GPUs de 6GB
            return GpuTier.LOW
        elif total <= 11200.0:  # Margem para GPUs de 8GB
            return GpuTier.MID
        else:
            return GpuTier.HIGH

    @property
    def current_phase(self) -> VramPhase:
        with self._arbiter_lock:
            return self._current_phase

    def prepare_phase(self, target_phase: VramPhase, force_clean: bool = False) -> Dict[str, Any]:
        """
        Prepara a VRAM para a próxima fase do pipeline.
        Em tiers LOW e MID, descarrega preventivamente modelos conflitantes para evitar
        que PyTorch e Ollama disputem o mesmo pool e acionem shared memory do Windows.
        """
        with self._arbiter_lock:
            tier = self.get_tier()
            actions_taken = []

            if target_phase == VramPhase.OCR:
                # Na fase de OCR, descarrega Ollama se o tier for baixo ou médio
                if tier in (GpuTier.LOW, GpuTier.MID) or force_clean:
                    unload_ollama_models()
                    cleanup_gpu_memory(force_ipc=True)
                    actions_taken.append("unloaded_ollama")
                    actions_taken.append("cleaned_torch_cache")

            elif target_phase == VramPhase.TRANSLATION:
                # Na fase de tradução, limpa resíduos de tensores do PyTorch (Florence-2 / YOLO)
                cleanup_gpu_memory(force_ipc=True)
                actions_taken.append("cleaned_torch_cache")

            elif target_phase == VramPhase.IDLE:
                cleanup_gpu_memory(force_ipc=False)
                actions_taken.append("cleaned_torch_cache")

            self._current_phase = target_phase
            return {
                "phase": target_phase.value,
                "tier": tier.value,
                "actions": actions_taken,
                "gpu_info": self.get_gpu_info()
            }

    prepare_for_phase = prepare_phase

    def get_recommended_ocr_batch_size(self) -> int:
        """
        Calcula o batch_size ideal para o Florence-2 durante a extração de OCR.
        Evita picos na alocação de beam search que causam OOM em GPUs de entrada.
        """
        tier = self.get_tier()
        if tier == GpuTier.LOW:
            return 4
        elif tier == GpuTier.MID:
            return 8
        elif tier == GpuTier.HIGH:
            return 16
        else:
            return 2

    def cap_context_for_tier(self, optimal_ctx: int) -> int:
        """
        Limita a janela de contexto de tradução (num_ctx) de acordo com o tier de GPU,
        evitando que o KV-cache do LLM sature a VRAM restante em placas <= 6GB.
        """
        tier = self.get_tier()
        if tier == GpuTier.LOW:
            return min(optimal_ctx, 2048)
        elif tier == GpuTier.MID:
            return min(optimal_ctx, 4096)
        return optimal_ctx

    def ensure_headroom_mb(self, required_mb: float) -> Tuple[bool, float]:
        """
        Verifica se há VRAM livre suficiente; se não houver, executa limpeza progressiva.
        Retorna (sucesso, vram_livre_mb).
        """
        info = self.get_gpu_info()
        if not info["available"]:
            return True, 0.0

        if info["free_mb"] >= required_mb:
            return True, info["free_mb"]

        # Tentativa 1: Limpar cache do PyTorch
        cleanup_gpu_memory(force_ipc=True)
        info = self.get_gpu_info()
        if info["free_mb"] >= required_mb:
            return True, info["free_mb"]

        # Tentativa 2: Descarregar modelos Ollama residentes
        unload_ollama_models()
        cleanup_gpu_memory(force_ipc=True)
        info = self.get_gpu_info()
        return (info["free_mb"] >= required_mb), info["free_mb"]


vram_arbiter = VramArbiter.get_instance()
