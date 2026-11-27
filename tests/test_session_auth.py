"""
Testes da autenticação por token de sessão (src/utils/session_auth.py + middleware do server).

Os testes trocam o modo de autenticação por teste via monkeypatch; a suíte inteira roda no modo
dev explícito (VISIONARY_DEV_NO_AUTH=1, ver conftest.py). Nenhum dado real do usuário é tocado.
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.server import app
from src.utils import session_auth
from src.utils.session_auth import (
    ENV_DEV_NO_AUTH,
    ENV_TOKEN,
    MODE_LOCKED,
    MODE_OPEN,
    MODE_TOKEN,
    evaluate_request,
)

client = TestClient(app)

TOKEN = "t" * 64
AUTH = {"X-Visionary-Token": TOKEN}
UNKNOWN_RPC = "/api/rpc/metodo_que_nao_existe_xyz"


@pytest.fixture
def token_mode(monkeypatch):
    """Token configurado; a flag de dev continua ligada de propósito (o token deve ter precedência)."""
    monkeypatch.setattr(session_auth, "_token", TOKEN)
    monkeypatch.setenv(ENV_DEV_NO_AUTH, "1")


@pytest.fixture
def locked_mode(monkeypatch):
    """Sem token e sem a flag de dev."""
    monkeypatch.setattr(session_auth, "_token", None)
    monkeypatch.delenv(ENV_DEV_NO_AUTH, raising=False)


def _headers(token):
    return [(b"x-visionary-token", token.encode("utf-8"))]


# ── Configuração a partir do ambiente ─────────────────────────────────────────

def test_configure_from_environment_reads_and_removes_the_token(monkeypatch):
    monkeypatch.setattr(session_auth, "_token", None)
    monkeypatch.delenv(ENV_DEV_NO_AUTH, raising=False)
    monkeypatch.setenv(ENV_TOKEN, TOKEN)

    assert session_auth.configure_from_environment() is True
    assert session_auth.auth_mode() == MODE_TOKEN
    assert ENV_TOKEN not in os.environ, "processos filhos (Ollama etc.) não podem herdar o segredo"


@pytest.mark.parametrize("weak", ["", "   ", "curto", "x" * (session_auth.MIN_TOKEN_LENGTH - 1)])
def test_weak_or_empty_token_is_treated_as_not_configured(monkeypatch, weak):
    monkeypatch.setattr(session_auth, "_token", None)
    monkeypatch.delenv(ENV_DEV_NO_AUTH, raising=False)
    monkeypatch.setenv(ENV_TOKEN, weak)

    assert session_auth.configure_from_environment() is False
    assert session_auth.auth_mode() == MODE_LOCKED
    assert ENV_TOKEN not in os.environ


def test_missing_env_var_leaves_the_server_locked_not_open(monkeypatch):
    monkeypatch.setattr(session_auth, "_token", None)
    monkeypatch.delenv(ENV_DEV_NO_AUTH, raising=False)
    monkeypatch.delenv(ENV_TOKEN, raising=False)
    assert session_auth.configure_from_environment() is False
    assert session_auth.auth_mode() == MODE_LOCKED


def test_dev_flag_opens_the_api_only_when_no_token_is_configured(monkeypatch):
    monkeypatch.setattr(session_auth, "_token", None)
    monkeypatch.setenv(ENV_DEV_NO_AUTH, "1")
    assert session_auth.auth_mode() == MODE_OPEN

    monkeypatch.setattr(session_auth, "_token", TOKEN)
    assert session_auth.auth_mode() == MODE_TOKEN, "o token tem precedência sobre a flag de dev"


@pytest.mark.parametrize("value", ["0", "true", "yes", "", "2"])
def test_only_the_literal_1_enables_dev_mode(monkeypatch, value):
    monkeypatch.setattr(session_auth, "_token", None)
    monkeypatch.setenv(ENV_DEV_NO_AUTH, value)
    assert session_auth.auth_mode() == MODE_LOCKED


# ── Decisão por requisição (função pura) ──────────────────────────────────────

@pytest.mark.parametrize("path", ["/", "/api/health", "/static/assets/app.js", "/static"])
def test_public_paths_never_need_a_token(token_mode, path):
    assert evaluate_request(path, []) is None


@pytest.mark.parametrize("path", [
    "/api/health/", "/api/healthz", "/api/health/../rpc/x", "/staticfoo", "/static_evil/x",
    "/api/rpc/x", "/api/shutdown", "/api/image", "/ws/logs", "/docs", "/openapi.json",
])
def test_everything_else_is_protected(token_mode, path):
    assert evaluate_request(path, [])[0] == 401


def test_valid_token_is_accepted_and_header_name_is_case_insensitive(token_mode):
    assert evaluate_request("/api/rpc/x", _headers(TOKEN)) is None
    assert evaluate_request("/api/rpc/x", [(b"X-Visionary-Token", TOKEN.encode())]) is None


@pytest.mark.parametrize("wrong", [TOKEN[:-1], TOKEN + "x", "T" * 64, "", " " + TOKEN])
def test_wrong_tokens_are_rejected(token_mode, wrong):
    assert evaluate_request("/api/rpc/x", _headers(wrong))[0] == 401


def test_other_headers_do_not_substitute_the_token(token_mode):
    for headers in (
        [(b"authorization", f"Bearer {TOKEN}".encode())],
        [(b"cookie", f"x-visionary-token={TOKEN}".encode())],
    ):
        assert evaluate_request("/api/rpc/x", headers)[0] == 401


def test_query_string_token_is_not_accepted(token_mode):
    response = client.get("/api/image", params={"path": "x.png", "token": TOKEN})
    assert response.status_code == 401


def test_locked_mode_denies_with_503_even_when_a_token_is_sent(locked_mode):
    assert evaluate_request("/api/rpc/x", [])[0] == 503
    assert evaluate_request("/api/rpc/x", _headers(TOKEN))[0] == 503
    assert evaluate_request("/api/health", []) is None


# ── Integração HTTP com o app real ────────────────────────────────────────────

def test_health_stays_public_in_token_mode(token_mode):
    assert client.get("/api/health").status_code == 200


def test_rpc_requires_the_token(token_mode):
    assert client.post(UNKNOWN_RPC, json={"args": [], "kwargs": {}}).status_code == 401
    assert client.post(UNKNOWN_RPC, json={}, headers={"X-Visionary-Token": "errado"}).status_code == 401
    # Com o token correto a requisição passa pelo middleware e chega ao roteador (método inexistente = 404).
    assert client.post(UNKNOWN_RPC, json={}, headers=AUTH).status_code == 404


def test_other_protected_routes_require_the_token(token_mode):
    for method, path in (
        ("get", "/api/rpc/contract"),
        ("get", "/api/models"),
        ("get", "/api/presets"),
        ("post", "/api/pipeline/run"),
        ("post", "/api/models/florence2/download"),
        ("delete", "/api/models/florence2"),
        ("get", "/docs"),
        ("get", "/openapi.json"),
    ):
        assert getattr(client, method)(path).status_code == 401, f"{method.upper()} {path}"


def test_image_endpoint_requires_the_token_before_the_sandbox(token_mode, tmp_path):
    image = tmp_path / "x.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert client.get("/api/image", params={"path": str(image)}).status_code == 401
    # Autenticado, o sandbox de raiz continua valendo (a pasta não foi autorizada).
    assert client.get("/api/image", params={"path": str(image)}, headers=AUTH).status_code == 403


def test_shutdown_requires_the_token_and_does_not_kill_the_process_without_it(token_mode):
    with patch("src.model_manager.ModelManager.terminate_ollama") as terminate, patch("os._exit") as exit_mock:
        denied = client.post("/api/shutdown")
        assert denied.status_code == 401
        assert exit_mock.call_count == 0
        assert terminate.call_count == 0

        allowed = client.post("/api/shutdown", headers=AUTH)
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "shutting_down"


def test_locked_mode_blocks_http_but_keeps_health(locked_mode):
    assert client.get("/api/health").status_code == 200
    assert client.post(UNKNOWN_RPC, json={}).status_code == 503
    assert client.post(UNKNOWN_RPC, json={}, headers=AUTH).status_code == 503


def test_dev_mode_without_token_keeps_the_api_open(monkeypatch):
    monkeypatch.setattr(session_auth, "_token", None)
    monkeypatch.setenv(ENV_DEV_NO_AUTH, "1")
    assert client.post(UNKNOWN_RPC, json={}).status_code == 404


# ── CORS: ordem dos middlewares ───────────────────────────────────────────────

def test_cors_preflight_is_answered_without_a_token(token_mode):
    response = client.options(
        UNKNOWN_RPC,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_denied_responses_still_carry_cors_headers_so_devtools_shows_the_real_error(token_mode):
    response = client.get("/api/models", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


# ── WebSocket ─────────────────────────────────────────────────────────────────

def test_websocket_without_token_is_rejected(token_mode):
    with pytest.raises(WebSocketDisconnect) as denied:
        with client.websocket_connect("/ws/logs"):
            pass
    assert denied.value.code == 1008


def test_websocket_with_wrong_token_is_rejected(token_mode):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/logs", headers={"X-Visionary-Token": "errado"}):
            pass


def test_websocket_with_token_connects_and_answers_ping(token_mode):
    with client.websocket_connect("/ws/logs", headers=AUTH) as socket:
        socket.send_text("ping")
        assert socket.receive_text() == "pong"


def test_websocket_is_rejected_in_locked_mode(locked_mode):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/logs", headers=AUTH):
            pass


def test_websocket_disconnect_cleans_up_connection_manager(token_mode):
    from src.server import manager
    initial_count = len(manager.active_connections)
    with client.websocket_connect("/ws/logs", headers=AUTH) as socket:
        socket.send_text("ping")
        assert socket.receive_text() == "pong"
        assert len(manager.active_connections) == initial_count + 1
    assert len(manager.active_connections) == initial_count


def test_websocket_broadcast_in_token_mode(token_mode):
    from src.server import broadcast_log_sync
    with client.websocket_connect("/ws/logs", headers=AUTH) as socket:
        socket.send_text("ping")
        assert socket.receive_text() == "pong"
        broadcast_log_sync("custom_event", message="test_msg", progress=75.0)
        received = socket.receive_json()
        assert received["type"] == "custom_event"
        assert received["message"] == "test_msg"
        assert received["progress"] == 75.0



def test_frozen_binary_rejects_dev_no_auth(monkeypatch):
    """Garante que binários congelados (PyInstaller) forçam fail-closed mesmo com flag de dev."""
    monkeypatch.setattr(session_auth, "_token", None)
    monkeypatch.setenv(ENV_DEV_NO_AUTH, "1")
    monkeypatch.setattr(session_auth.sys, "frozen", True, raising=False)
    assert session_auth.auth_mode() == MODE_LOCKED


def test_production_env_rejects_dev_no_auth(monkeypatch):
    """Garante que VISIONARY_ENV=production ou NODE_ENV=production trava em fail-closed."""
    monkeypatch.setattr(session_auth, "_token", None)
    monkeypatch.setenv(ENV_DEV_NO_AUTH, "1")
    monkeypatch.setenv("VISIONARY_ENV", "production")
    assert session_auth.auth_mode() == MODE_LOCKED

    monkeypatch.delenv("VISIONARY_ENV")
    monkeypatch.setenv("NODE_ENV", "production")
    assert session_auth.auth_mode() == MODE_LOCKED
