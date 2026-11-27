"""
Pacote de roteadores modulares do FastAPI para o backend do Visionary Studio.
"""

from src.routers.system_router import system_router
from src.routers.models_router import models_router
from src.routers.pipeline_router import pipeline_router
from src.routers.rpc_router import rpc_router

__all__ = [
    "system_router",
    "models_router",
    "pipeline_router",
    "rpc_router",
]
