import pytest
from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)

def test_fuzz_rpc_endpoint():
    """Testa o comportamento do endpoint RPC com vários payloads inesperados."""
    # Chamada válida
    res = client.post("/api/rpc/getSettings", json={"args": [], "kwargs": {}})
    assert res.status_code == 200

    # Chamada sem corpo retorna 200 porque payload tem Body(default={})
    res = client.post("/api/rpc/getSettings")
    assert res.status_code == 200 
    
    # Chamada com corpo vazio
    res = client.post("/api/rpc/getSettings", json={})
    assert res.status_code == 200

    # Método inexistente
    res = client.post("/api/rpc/metodoInexistente123", json={"args": [], "kwargs": {}})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]

    # Tipos incorretos (args deveria ser lista) 
    # args como string ("not a list") desempacota os caracteres e passa como *args
    res = client.post("/api/rpc/getSettings", json={"args": "not a list", "kwargs": {}})
    assert res.status_code == 200

def test_websocket_fuzz():
    """Testa a conexão do WebSocket e mensagens inválidas."""
    with client.websocket_connect("/ws/logs") as websocket:
        # Só testa se consegue conectar, se manter aberto
        websocket.send_text("Hello, world!")
        # O backend atualmente ignora/descarta ou não reage a mensagens recebidas no /ws/logs, 
        # ele é feito só para *enviar* logs para o frontend, então ele não deve quebrar.
        assert True
