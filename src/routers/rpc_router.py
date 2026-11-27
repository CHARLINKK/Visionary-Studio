"""
Router Universal de RPC (Remote Procedure Call): Despacha chamadas dinâmicas do JavaScript para o ApiBridge.
"""

import sys
import inspect
import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Body
from src.api_bridge import ApiBridge

rpc_router = APIRouter()
api_bridge = ApiBridge()


def _get_active_bridge():
    server_mod = sys.modules.get("src.server")
    if server_mod is not None and hasattr(server_mod, "api_bridge"):
        return getattr(server_mod, "api_bridge")
    return api_bridge


class RpcPayload(BaseModel):
    model_config = {"extra": "ignore"}
    args: Optional[object] = Field(default_factory=list, description="Lista de argumentos posicionais do método RPC")
    kwargs: Optional[object] = Field(default_factory=dict, description="Dicionário de argumentos nomeados do método RPC")


class RpcResponse(BaseModel):
    success: bool = Field(..., description="Status de sucesso da chamada RPC")
    result: Optional[object] = Field(default=None, description="Resultado retornado pelo método RPC")
    error: Optional[str] = Field(default=None, description="Mensagem de erro em caso de falha")


@rpc_router.post("/api/rpc/{method_name}", response_model=RpcResponse)
async def call_rpc(method_name: str, payload: RpcPayload = Body(default_factory=RpcPayload)):
    """Despacha uma chamada RPC para o método correspondente no ApiBridge."""
    if not method_name or method_name.startswith("_"):
        raise HTTPException(status_code=403, detail="Access to private or internal RPC methods is strictly forbidden")

    bridge = _get_active_bridge()
    if not hasattr(bridge, method_name):
        raise HTTPException(status_code=404, detail=f"RPC method '{method_name}' not found on ApiBridge")
    
    target_func = getattr(bridge, method_name)
    if not callable(target_func):
        raise HTTPException(status_code=400, detail=f"'{method_name}' is not callable")

    if isinstance(payload.args, (list, tuple)):
        args = list(payload.args)
    elif payload.args is not None:
        args = list(payload.args) if isinstance(payload.args, (str, bytes)) else [payload.args]
    else:
        args = []
    kwargs = payload.kwargs if isinstance(payload.kwargs, dict) else {}

    eval_func = target_func
    for svc in getattr(bridge, "_all_services", []):
        if hasattr(svc, method_name) and callable(getattr(svc, method_name)):
            eval_func = getattr(svc, method_name)
            break

    try:
        sig = inspect.signature(eval_func)
        sig.bind(*args, **kwargs)
    except TypeError as bind_err:
        return {"success": False, "error": f"Contrato RPC violado em '{method_name}': {str(bind_err)}"}
    except (ValueError, TypeError):
        pass

    try:
        res = await asyncio.to_thread(target_func, *args, **kwargs)
        return {"success": True, "result": res}
    except TypeError as e:
        return {"success": False, "error": f"Contrato RPC violado em '{method_name}': {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@rpc_router.get("/api/rpc/contract")
def get_rpc_contract():
    """
    Retorna o catálogo completo de métodos RPC expostos pelo ApiBridge,
    suas assinaturas, parâmetros e docstrings.
    """
    catalog = {}
    bridge = _get_active_bridge()
    for attr_name in sorted(dir(bridge)):
        if attr_name.startswith("_"):
            continue
        attr = getattr(bridge, attr_name)
        if callable(attr):
            eval_func = attr
            for svc in getattr(bridge, "_all_services", []):
                if hasattr(svc, attr_name) and callable(getattr(svc, attr_name)):
                    eval_func = getattr(svc, attr_name)
                    break
            try:
                sig = inspect.signature(eval_func)
                params = []
                for p_name, p in sig.parameters.items():
                    params.append({
                        "name": p_name,
                        "kind": str(p.kind),
                        "default": None if p.default is inspect.Parameter.empty else str(p.default),
                        "required": p.default is inspect.Parameter.empty and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                    })
                catalog[attr_name] = {
                    "parameters": params,
                    "doc": inspect.getdoc(eval_func) or inspect.getdoc(attr) or ""
                }
            except (ValueError, TypeError):
                catalog[attr_name] = {"parameters": [], "doc": inspect.getdoc(attr) or ""}
    return {"success": True, "methods": catalog}
