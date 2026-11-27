"""
Router de Motores e Modelos de IA: Catálogo, downloads e remoção.
"""

from fastapi import APIRouter, HTTPException
from src.model_manager import ModelManager, MODELS_REGISTRY
from src.routers.rpc_router import api_bridge

models_router = APIRouter()
_model_manager = getattr(api_bridge, "model_manager", None) or ModelManager()


def get_model_manager_instance():
    import sys
    server_mod = sys.modules.get("src.server")
    if server_mod and hasattr(server_mod, "model_manager"):
        return server_mod.model_manager
    return _model_manager


@models_router.get("/api/models")
def get_models_status():
    """Retorna o status consolidado de todos os modelos de IA registrados."""
    return get_model_manager_instance().get_all_status()


@models_router.post("/api/models/{model_key}/download")
def download_model(model_key: str):
    """Inicia o download assíncrono de um modelo especificado."""
    if model_key not in MODELS_REGISTRY:
        raise HTTPException(status_code=404, detail="Model module key not registered")
    mgr = get_model_manager_instance()
    started = mgr.download_module(model_key)
    return {"success": started, "status": mgr.get_all_status().get(model_key)}


@models_router.post("/api/models/{model_key}/cancel")
def cancel_model_download(model_key: str):
    """Cancela cooperativamente o download ativo de um modelo especificado."""
    if model_key not in MODELS_REGISTRY:
        raise HTTPException(status_code=404, detail="Model module key not registered")
    mgr = get_model_manager_instance()
    cancelled = mgr.cancel_module(model_key)
    return {"success": cancelled, "status": mgr.get_all_status().get(model_key)}


@models_router.delete("/api/models/{model_key}")
def remove_model(model_key: str):
    """Remove com segurança os arquivos físicos de um modelo de IA do disco."""
    mgr = get_model_manager_instance()
    success = mgr.remove_module(model_key)
    return {"success": success, "status": mgr.get_all_status().get(model_key)}
