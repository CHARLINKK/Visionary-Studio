"""
Autenticação por token efêmero de sessão para a API local (HTTP e WebSocket).

Problema que resolve: o FastAPI escuta em 127.0.0.1, mas sem credencial qualquer processo local ou
página aberta no navegador (`fetch("http://127.0.0.1:5000/api/rpc/...")`) conseguia chamar o RPC
universal, `/api/shutdown`, `/api/image` e abrir o WebSocket de logs.

Modelo:
- O Electron gera um segredo aleatório (32 bytes) a cada execução e o entrega ao backend pela
  variável de ambiente `VISIONARY_AUTH_TOKEN` (não pela linha de comando, que qualquer processo do
  usuário consegue listar). O backend lê e REMOVE a variável do ambiente, para que processos filhos
  (Ollama, pytest do painel de dev) não a herdem.
- O processo main do Electron injeta o cabeçalho `X-Visionary-Token` nas requisições da janela para
  o backend (`session.webRequest`). O renderer nunca conhece o segredo, então XSS na GUI não o vaza.
- Este middleware exige o cabeçalho em todas as rotas, exceto `PUBLIC_PATHS`/`PUBLIC_PREFIXES`.

Modos (avaliados a cada requisição):
- `token`: há token configurado -> exige o cabeçalho. Tem precedência sobre qualquer outra coisa.
- `open`: sem token E `VISIONARY_DEV_NO_AUTH=1` -> sem autenticação. Só para desenvolvimento
  (ex.: Vite em :5173 sem Electron). Ignorado e bloqueado em executável empacotado ou produção.
- `locked`: sem token e sem a flag de dev -> TUDO que não é público é negado (503). Falha fechada:
  esquecer de configurar o token nunca deixa a API aberta por acidente.
"""

import hmac
import json
import os
import sys

ENV_TOKEN = "VISIONARY_AUTH_TOKEN"
ENV_DEV_NO_AUTH = "VISIONARY_DEV_NO_AUTH"
TOKEN_HEADER = b"x-visionary-token"

# Abaixo disso o segredo é considerado fraco demais e tratado como não configurado.
MIN_TOKEN_LENGTH = 32

MODE_TOKEN = "token"
MODE_OPEN = "open"
MODE_LOCKED = "locked"

# Rotas que permanecem sem token: sonda de saúde (o Electron a usa para detectar que o servidor
# subiu, antes de qualquer janela existir) e os arquivos estáticos da própria GUI (não são segredo).
PUBLIC_PATHS = frozenset({"/", "/api/health"})
PUBLIC_PREFIXES = ("/static/",)

_token = None


def configure_from_environment():
    """
    Lê o token de `VISIONARY_AUTH_TOKEN` e o REMOVE do ambiente do processo.
    Retorna True se um token válido (>= MIN_TOKEN_LENGTH) ficou configurado.
    """
    global _token
    raw = os.environ.pop(ENV_TOKEN, None)
    candidate = (raw or "").strip()
    _token = candidate if len(candidate) >= MIN_TOKEN_LENGTH else None
    return _token is not None


def auth_mode():
    if _token:
        return MODE_TOKEN
    # Blindagem de produção fail-closed: se o executável estiver empacotado (PyInstaller)
    # ou em ambiente de produção explícito, a flag de dev é estritamente ignorada.
    is_frozen = getattr(sys, "frozen", False)
    is_prod = (
        os.environ.get("VISIONARY_ENV") == "production"
        or os.environ.get("NODE_ENV") == "production"
    )
    if is_frozen or is_prod:
        return MODE_LOCKED
    if os.environ.get(ENV_DEV_NO_AUTH) == "1":
        return MODE_OPEN
    return MODE_LOCKED


def is_public_path(path):
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES) or path == "/static"


def _header_value(raw_headers, name):
    for key, value in raw_headers or ():
        if key.lower() == name:
            return value
    return None


def evaluate_request(path, raw_headers):
    """
    Decide se a requisição pode seguir. Retorna None (liberada) ou `(status_http, mensagem)`.
    `raw_headers` no formato ASGI: lista de pares de bytes `(nome, valor)`.
    """
    if is_public_path(path):
        return None
    mode = auth_mode()
    if mode == MODE_OPEN:
        return None
    if mode == MODE_LOCKED:
        return 503, "Authentication is not configured on the server"
    supplied = _header_value(raw_headers, TOKEN_HEADER)
    if supplied is None or not hmac.compare_digest(supplied, _token.encode("utf-8")):
        return 401, "Missing or invalid session token"
    return None


class SessionTokenMiddleware:
    """
    Middleware ASGI puro (não `BaseHTTPMiddleware`, que ignora WebSocket) que aplica `evaluate_request`
    a requisições HTTP e a handshakes de WebSocket.

    Deve ser adicionado ANTES do CORSMiddleware: assim o CORS fica mais externo, responde os preflights
    `OPTIONS` sem exigir token (navegadores não enviam credenciais customizadas no preflight) e ainda
    anexa os cabeçalhos CORS às respostas 401/503, o que torna o erro legível no DevTools.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope_type = scope["type"]
        if scope_type not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        denial = evaluate_request(scope.get("path", ""), scope.get("headers"))
        if denial is None:
            await self.app(scope, receive, send)
            return

        status_code, detail = denial
        if scope_type == "websocket":
            # Fechar antes de aceitar rejeita o handshake (o cliente vê HTTP 403).
            await send({"type": "websocket.close", "code": 1008, "reason": detail})
            return

        body = json.dumps({"detail": detail}).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        })
        await send({"type": "http.response.body", "body": body})
