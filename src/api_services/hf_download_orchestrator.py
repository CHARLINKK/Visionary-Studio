import os
import sys
import time
import threading
from src.model_manager import ModelManager, MODELS_REGISTRY


def _resolve_torch_hub_checkpoints_dir() -> str:
    """Resolve o diretório de checkpoints do PyTorch Hub sem forçar cold-import do `torch`."""
    torch_home = os.environ.get("TORCH_HOME")
    if torch_home:
        cand = os.path.join(torch_home, "hub", "checkpoints")
        if os.path.isdir(cand):
            return cand

    # Usa torch.hub apenas se o módulo torch já estiver carregado na sessão (zero cold import)
    torch_mod = sys.modules.get("torch")
    if torch_mod is not None:
        try:
            hub_dir = torch_mod.hub.get_dir()
            cand = os.path.join(hub_dir, "checkpoints")
            if os.path.isdir(cand):
                return cand
        except Exception:
            pass

    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            cand = os.path.join(local_app, "torch", "hub", "checkpoints")
            if os.path.isdir(cand):
                return cand

    unix_cand = os.path.join(os.path.expanduser("~"), ".cache", "torch", "hub", "checkpoints")
    if os.path.isdir(unix_cand):
        return unix_cand
    return ""


class HFDownloadOrchestrator:
    """
    Orquestrador modular para modelos Hugging Face:
    - Download assíncrono de modelos do registro com telemetria
    - Remoção de pesos e limpeza de caches
    - Inspeção de status ativo e verificação de integridade em disco
    - Cálculo de armazenamento ocupado por modelos de visão/OCR
    - Emissão de telemetria via EventBus
    """

    def __init__(self, model_manager=None, get_downloads_provider=None):
        self.model_manager = model_manager or ModelManager()
        self._downloads_provider = get_downloads_provider
        if hasattr(self.model_manager, "register_progress_callback"):
            try:
                self.model_manager.register_progress_callback(self.notify_progress)
            except Exception:
                pass
        elif hasattr(getattr(self.model_manager, "_hf_mgr", None), "register_progress_callback"):
            try:
                self.model_manager._hf_mgr.register_progress_callback(self.notify_progress)
            except Exception:
                pass

    def notify_progress(self, key: str = None, progress_data: dict = None):
        """Dispara evento de telemetria de downloads via EventBus."""
        try:
            if isinstance(progress_data, dict) and progress_data.get("status") in (
                "installed",
                "completed",
                "missing",
                "cancelled",
            ):
                self.invalidate_storage_cache()
            from src.utils.event_bus import event_bus
            if callable(self._downloads_provider):
                snapshot = self._downloads_provider()
            else:
                snapshot = {
                    "success": True,
                    "ollama": {},
                    "hf": self.get_active_hf_status(),
                }
            event_bus.publish("downloads_progress", snapshot)
            if key is not None and progress_data is not None:
                event_bus.publish("model_download_progress", {"key": key, "data": progress_data})
        except Exception:
            pass

    def get_active_hf_status(self) -> dict:
        """
        Consolida o status dos modelos Hugging Face delegando a verificação
        de cache e download para a engine (HFDownloadManager) e formatando
        o snapshot para consumo pela API/EventBus.
        """
        active_hf = {}
        # 1. Prioriza status em memória (downloads ativos ou concluídos na sessão atual)
        hf_status = getattr(self.model_manager, "download_status", {})
        for k, v in hf_status.items():
            st = v.get("status")
            if st in ["downloading", "extracting", "installed", "completed", "ready", "missing", "removed"]:
                active_hf[k] = v

        # 2. Complementa com status detectado da engine/disco
        if hasattr(self.model_manager, "get_all_status"):
            try:
                all_st = self.model_manager.get_all_status()
                for k, v in all_st.items():
                    if k not in active_hf and v.get("type") in ["huggingface_cache", "huggingface_multi_single"]:
                        if v.get("status") in ["installed", "ready", "downloading", "extracting"]:
                            active_hf[k] = {
                                "status": v.get("status", "idle"),
                                "progress": v.get("progress", 0.0),
                                "downloaded_bytes": v.get("downloaded_bytes", 0),
                                "total_bytes": v.get("total_bytes") or v.get("estimated_size_bytes", 0),
                                "speed_mbps": v.get("speed_mbps", 0.0),
                                "eta_seconds": v.get("eta_seconds", 0),
                                "message": v.get("message", "")
                            }
                return active_hf
            except Exception:
                pass

        # Fallback de compatibilidade caso o model_manager seja um mock simples
        for k, v in hf_status.items():
            if k not in active_hf and hasattr(self.model_manager, "is_hf_model_cached"):
                info = MODELS_REGISTRY.get(k, {})
                base_dir = getattr(self.model_manager, "base_dir", "")
                target_path = os.path.join(base_dir, info.get("target_dir", "models"), info.get("cache_folder", ""))
                if self.model_manager.is_hf_model_cached(target_path):
                    tot = v.get("total_bytes") or info.get("estimated_size_bytes", 0)
                    active_hf[k] = {
                        "status": "installed",
                        "progress": 100.0,
                        "downloaded_bytes": tot,
                        "total_bytes": tot,
                        "message": "Instalado e operacional"
                    }
        return active_hf

    def download_model(self, key: str) -> dict:
        """Inicia o download de um modelo Hugging Face pelo gerenciador com telemetria reativa via callback."""
        try:
            success = self.model_manager.download_module(key)
            if success:
                self.notify_progress(key, self.model_manager.get_download_status(key))
            return {"success": success}
        except Exception as e:
            return {"success": False, "error": str(e)}

    downloadHuggingFaceModel = download_model

    def cancel_model(self, key: str) -> dict:
        """Cancela o download ativo de um modelo Hugging Face."""
        try:
            cancel_fn = getattr(self.model_manager, "cancel_module", None) or getattr(self.model_manager, "cancel_download", None)
            success = bool(cancel_fn(key)) if callable(cancel_fn) else False
            self.notify_progress(key, {"status": "cancelled", "progress": 0.0, "message": "Download cancelado"})
            return {"success": success}
        except Exception as e:
            return {"success": False, "error": str(e)}

    cancelHuggingFaceModel = cancel_model

    def invalidate_storage_cache(self):
        """Invalida o cache local de métricas de armazenamento para forçar recontagem física."""
        self._cached_hf_bytes = 0
        self._cached_hf_time = 0.0

    def delete_model(self, key: str) -> dict:
        """Remove o modelo Hugging Face e limpa pastas de cache."""
        try:
            success = self.model_manager.remove_module(key)
            self.invalidate_storage_cache()
            if key in ["florence2", "florence2_large"]:
                self.notify_progress("florence2", {"status": "missing", "progress": 0.0})
                self.notify_progress("florence2_large", {"status": "missing", "progress": 0.0})
            else:
                self.notify_progress(key, {"status": "missing", "progress": 0.0})
            try:
                from src.utils.event_bus import event_bus
                event_bus.publish("model_inventory_changed", {"action": "delete_hf", "model": key, "success": success})
            except Exception:
                pass
            return {"success": success}
        except Exception as e:
            return {"success": False, "error": str(e)}

    deleteHuggingFaceModel = delete_model

    def get_storage_stats(self, ollama_bytes: int = 0) -> dict:
        """Calcula o uso em disco dos modelos Hugging Face somado aos bytes do Ollama com cache de 5s."""
        try:
            now = time.time()
            if hasattr(self, "_cached_hf_bytes") and (now - getattr(self, "_cached_hf_time", 0)) < 5.0:
                hf_bytes = self._cached_hf_bytes
            else:
                base_dir = getattr(self.model_manager, "base_dir", "")
                models_dir = os.path.join(base_dir, "models")
                hf_bytes = self.model_manager._scan_disk_downloaded_bytes([models_dir])

                torch_hub = _resolve_torch_hub_checkpoints_dir()
                if torch_hub and os.path.isdir(torch_hub):
                    hf_bytes += self.model_manager._scan_disk_downloaded_bytes([torch_hub])
                self._cached_hf_bytes = hf_bytes
                self._cached_hf_time = now

            total_bytes = ollama_bytes + hf_bytes
            total_gb = total_bytes / (1024 ** 3)

            return {
                "success": True,
                "ollama_bytes": ollama_bytes,
                "vision_bytes": hf_bytes,
                "total_bytes": total_bytes,
                "total_gb": round(total_gb, 1),
                "total_formatted": f"{total_gb:.1f} GB"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
