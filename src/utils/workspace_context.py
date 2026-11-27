import threading
from typing import Optional


class WorkspaceContext:
    """
    Contexto de Workspace e Sessão Ativa do Visionary Studio.
    
    Centraliza o estado de navegação e diretório ativo de forma thread-safe,
    eliminando a necessidade de serviços de domínio acessarem ou mutarem o ApiBridge
    através de dependências circulares (weakref).
    """

    def __init__(self, base_folder: str = "MEU COMPUTADOR"):
        self._lock = threading.RLock()
        self._current_path = base_folder or "MEU COMPUTADOR"

    @property
    def current_path(self) -> str:
        """Retorna o caminho atual ativo de forma segura entre threads."""
        with self._lock:
            return self._current_path

    @current_path.setter
    def current_path(self, path: Optional[str]):
        """Atualiza o caminho atual ativo de forma segura entre threads."""
        with self._lock:
            self._current_path = (path or "").strip() or "MEU COMPUTADOR"

    def set_current_path(self, path: Optional[str]) -> str:
        """Método explícito de conveniência para atualizar o caminho ativo."""
        with self._lock:
            self._current_path = (path or "").strip() or "MEU COMPUTADOR"
            return self._current_path

    def get_current_path(self) -> str:
        """Método explícito de conveniência para leitura do caminho ativo."""
        with self._lock:
            return self._current_path

    @classmethod
    def resolve_service_binding(
        cls,
        workspace_context=None,
        api_bridge=None,
        default_path: str = "MEU COMPUTADOR",
    ) -> tuple["WorkspaceContext", object]:
        """
        Resolve de forma canônica a injeção de dependência de (WorkspaceContext, api_bridge),
        mantendo retrocompatibilidade caso um caller legado passe `api_bridge` no primeiro argumento.
        """
        if isinstance(workspace_context, cls):
            return workspace_context, api_bridge
        bridge = workspace_context if workspace_context is not None else api_bridge
        if bridge is not None:
            existing_ctx = getattr(bridge, "workspace_context", None)
            if isinstance(existing_ctx, cls):
                return existing_ctx, bridge
            return cls(getattr(bridge, "current_path", default_path)), bridge
        return cls(default_path), None
