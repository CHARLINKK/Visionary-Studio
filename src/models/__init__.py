"""
Módulo de Modelos Canônicos de Dados do Visionary (Pydantic v2).
Centraliza schemas tipados para validação, serialização e contratos de API.
"""

from src.models.bubble import BubbleModel, PageDataModel

__all__ = ["BubbleModel", "PageDataModel"]
