import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from src.server import app, ConnectionManager, broadcast_log_sync
import asyncio
import os

client = TestClient(app)

def test_health_check_success():
    """Valida o endpoint /api/health retornando status ok"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

@patch("src.config.get_app_data_dir")
@patch("requests.get")
def test_health_check_failures(mock_get, mock_app_data):
    """Valida que falhas isoladas nos checadores não quebram o endpoint de health."""
    mock_app_data.side_effect = Exception("Disk Write Fail")
    mock_get.side_effect = Exception("Ollama Connect Fail")
    
    # We also need to patch the local imports correctly.
    # Since torch is imported locally, we must patch sys.modules if we want to simulate ImportError
    with patch.dict('sys.modules', {'torch': MagicMock(cuda=MagicMock(is_available=MagicMock(side_effect=Exception("Torch Import Fail")))), 'requests': None}):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["disk_write"] is False
        assert data["pytorch_cuda"] is False
        assert data["ollama"] is False

def test_health_check_partial_torch_import():
    """Valida que um modulo torch parcialmente inicializado em sys.modules (race condition no boot) nao gera falso negativo."""
    import types
    partial_torch = types.ModuleType("torch")  # Sem atributo .cuda ainda anexado
    with patch.dict("sys.modules", {"torch": partial_torch}):
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            response = client.get("/api/health")
            assert response.status_code == 200
            assert response.json()["pytorch_cuda"] is True

def test_get_models_status():
    response = client.get("/api/models")
    assert response.status_code == 200
    assert "florence2" in response.json()

@patch("src.server.model_manager.download_module")
def test_download_model_success(mock_download):
    mock_download.return_value = True
    response = client.post("/api/models/florence2/download")
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_download_model_not_found():
    response = client.post("/api/models/inexistente/download")
    assert response.status_code == 404

@patch("src.server.model_manager.remove_module")
def test_remove_model(mock_remove):
    mock_remove.return_value = True
    response = client.delete("/api/models/florence2")
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_get_presets():
    response = client.get("/api/presets")
    assert response.status_code == 200
    assert "boxing" in response.json()

def test_get_local_image(tmp_path):
    from src.utils.path_sandbox import register_root
    assert register_root(str(tmp_path)) is True
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image data")
    
    response = client.get("/api/image", params={"path": str(img_path)})
    assert response.status_code == 200
    assert response.content == b"fake image data"

    from PIL import Image
    big_path = tmp_path / "big_page.png"
    Image.new("RGB", (1200, 1800), color=(240, 240, 240)).save(str(big_path), format="PNG")
    thumb_resp = client.get("/api/image", params={"path": str(big_path), "thumb": 360})
    assert thumb_resp.status_code == 200
    assert thumb_resp.headers.get("content-type") in ("image/webp", "image/jpeg")
    assert len(thumb_resp.content) < big_path.stat().st_size

def test_get_local_image_forbidden_ext(tmp_path):
    from src.utils.path_sandbox import register_root
    register_root(str(tmp_path))
    img_path = tmp_path / "test.exe"
    img_path.write_bytes(b"mz")
    response = client.get("/api/image", params={"path": str(img_path)})
    assert response.status_code == 403

def test_get_local_image_not_found(tmp_path):
    """Dentro de uma raiz autorizada, arquivo inexistente continua sendo 404."""
    from src.utils.path_sandbox import register_root
    register_root(str(tmp_path))
    response = client.get("/api/image", params={"path": str(tmp_path / "inexistente.png")})
    assert response.status_code == 404

def test_get_local_image_not_found_outside_roots_is_forbidden():
    """Fora de qualquer raiz a resposta é 403 mesmo para arquivo inexistente (o 404 não pode vazar existência)."""
    response = client.get("/api/image?path=/inexistente.png")
    assert response.status_code == 403

def test_get_local_image_no_path():
    response = client.get("/api/image")
    assert response.status_code == 422 # FastAPI validation for required query param

def test_read_root_fallback():
    """Valida o fallback quando index.html não existe no dir do GUI."""
    with patch("src.server.os.path.exists", return_value=False):
        response = client.get("/")
        assert response.status_code == 200
        assert "not found" in response.json()["message"]

@patch("src.server.broadcast_log_sync")
@patch("src.server.run_batch_pipeline")
def test_trigger_pipeline_success(mock_run, mock_broadcast, tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    response = client.post("/api/pipeline/run", json={"input_dir": str(in_dir)})
    assert response.status_code == 200
    assert response.json()["success"] is True
    # Verify the background task executed mock_run
    mock_run.assert_called_once()

@patch("src.server.broadcast_log_sync")
@patch("src.server.run_batch_pipeline")
def test_trigger_pipeline_exception(mock_run, mock_broadcast, tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    mock_run.side_effect = Exception("Erro forçado no pipeline")
    response = client.post("/api/pipeline/run", json={"input_dir": str(in_dir)})
    assert response.status_code == 200
    # O pipeline em background falha e chama o broadcast
    mock_broadcast.assert_called()

def test_trigger_pipeline_missing_dir():
    response = client.post("/api/pipeline/run", json={"input_dir": "/nao/existe"})
    assert response.status_code == 400

@patch("src.server.api_bridge")
def test_rpc_not_callable(mock_bridge):
    """Testa RPC quando o método existe mas não é chamável"""
    mock_bridge.not_a_func = "string"
    response = client.post("/api/rpc/not_a_func", json={})
    assert response.status_code == 400

def test_rpc_private_method_forbidden():
    """Valida que métodos privados, protegidos e dunders são bloqueados com 403."""
    response = client.post("/api/rpc/__init__", json={})
    assert response.status_code == 403
    assert "forbidden" in response.json()["detail"].lower()

    response2 = client.post("/api/rpc/_private_helper", json={})
    assert response2.status_code == 403

def test_cors_local_origin():
    """Valida que origens locais são permitidas pelo CORS."""
    response = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

@patch("src.server.api_bridge")
def test_rpc_exception(mock_bridge):
    """Testa retorno seguro do RPC quando o método lança exceção"""
    def explode(*args, **kwargs):
        raise ValueError("Boom")
    mock_bridge.explode_method = explode
    
    response = client.post("/api/rpc/explode_method", json={})
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "Boom" in response.json()["error"]

def test_websocket_broadcast():
    """Valida a proteção e isolamento do ConnectionManager"""
    cm = ConnectionManager()
    mock_ws = AsyncMock()
    
    async def run_test():
        await cm.connect(mock_ws)
        assert len(cm.active_connections) == 1
        
        # Simula um cliente que desconectou abruta
        mock_ws.send_json.side_effect = Exception("Connection lost")
        await cm.broadcast({"msg": "hi"})
        
        # O manager deve ter removido o socket com erro silenciosamente
        assert len(cm.active_connections) == 0

    asyncio.run(run_test())

def test_broadcast_log_sync():
    """Valida disparo de logs via bridge síncrona."""
    with patch("src.server._main_loop") as mock_loop:
        mock_loop.is_running.return_value = True
        with patch("src.server.asyncio.run_coroutine_threadsafe") as mock_run:
            broadcast_log_sync("test", "msg")
            mock_run.assert_called_once()
            # Fecha a coroutine criada por manager.broadcast para evitar aviso do GC
            coro = mock_run.call_args[0][0]
            coro.close()

def test_websocket_endpoint_ping_pong():
    """Valida o endpoint real do websocket, garantindo que ele aceita conexões e responde pings."""
    with client.websocket_connect("/ws/logs") as websocket:
        websocket.send_text("ping")
        data = websocket.receive_text()
        assert data == "pong"
        
        # Simula envio de mensagem qualquer (ignorado ou causa disconnect)
        websocket.send_text("hello")


def test_rpc_contract_discovery():
    """Valida o endpoint de descoberta de contratos RPC /api/rpc/contract."""
    response = client.get("/api/rpc/contract")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "methods" in data
    methods = data["methods"]
    assert "getHardwareStats" in methods
    assert "getSettings" in methods
    assert isinstance(methods["getHardwareStats"]["parameters"], list)


def test_rpc_schema_contract_violation():
    """Valida que parâmetros incorretos disparam erro de contrato RPC antecipadamente."""
    # get_page_data requer image_path obrigatoriamente
    response = client.post("/api/rpc/get_page_data", json={"args": []})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Contrato RPC violado" in data["error"]


def test_rpc_valid_contract_execution():
    """Valida execução limpa com payload fortemente tipado via Pydantic."""
    response = client.post("/api/rpc/getSettings", json={"args": [], "kwargs": {}})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["result"], dict)


def test_health_check_does_not_import_torch_on_cold_start(monkeypatch, tmp_path):
    """Garante que o polling de /api/health no boot não força import pesado do PyTorch em sys.modules."""
    import sys
    import importlib.util

    monkeypatch.setenv("VISIONARY_USER_DATA", str(tmp_path))
    saved_torch = sys.modules.pop("torch", None)
    try:
        with patch.object(importlib.util, "find_spec", return_value=MagicMock()) as mock_spec, \
             patch("requests.get", side_effect=OSError("Offline")):
            response = client.get("/api/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["pytorch_cuda"] is True
            mock_spec.assert_called_once_with("torch")
            assert "torch" not in sys.modules
    finally:
        if saved_torch is not None:
            sys.modules["torch"] = saved_torch


def test_cold_import_defers_heavy_cv2_numpy_and_wheelhouse():
    """Garante que importar src.server no boot não puxa cv2, numpy, src.run_batch nem wheelhouse_plan."""
    import subprocess
    import sys

    probe_code = (
        "import sys; import src.server; "
        "loaded = [m for m in ('cv2', 'numpy', 'torch', 'psutil', 'requests', 'webbrowser', 'src.run_batch', "
        "'src.model_engines.core_installer.wheelhouse_plan') if m in sys.modules]; "
        "print('|'.join(loaded)); "
        "assert not loaded, f'Modulos pesados carregados no boot: {loaded}'"
    )
    res = subprocess.run(
        [sys.executable, "-c", probe_code],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert res.returncode == 0, f"Boot pesado detectado: {res.stdout} {res.stderr}"



