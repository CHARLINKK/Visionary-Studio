import os
import sys
import tempfile
import pytest
from unittest.mock import patch

# Ensure src is in the pythonpath


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Sets up a completely isolated environment for the test suite.
    Ensures that no test touches real user data or settings.json.
    """
    # Create a temporary directory for the session
    test_data_dir = tempfile.mkdtemp(prefix="visionary_test_data_")
    
    # Set environment variables BEFORE importing src modules where possible,
    # though some might already be imported.
    os.environ["VISIONARY_USER_DATA"] = test_data_dir
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
    # Os testes existentes chamam a API via TestClient sem token: rodam no modo dev explícito.
    # Os testes de autenticação (test_session_auth.py) trocam o modo por teste via monkeypatch.
    os.environ["VISIONARY_DEV_NO_AUTH"] = "1"
    
    # Now we can safely import config
    from src.config import Config
    import src.config
    
    # Force CONFIG_FILE to point to our temp directory, 
    # just in case it was already evaluated at import time.
    fake_config_file = os.path.join(test_data_dir, "settings.json")
    
    with patch("src.config.CONFIG_FILE", fake_config_file):
        yield
        
    # Cleanup after session
    import shutil
    try:
        shutil.rmtree(test_data_dir)
    except Exception:
        pass

@pytest.fixture(autouse=True)
def reset_config_cache():
    """
    Resets the Config cache before each test to ensure no state leakage.
    """
    from src.config import Config
    Config._cached_data = None
    Config._cached_mtime = 0
    yield


@pytest.fixture(autouse=True)
def reset_path_sandbox():
    """
    Zera o registro em memória de raízes autorizadas do sandbox de /api/image.
    É estado global do processo: sem isto, um teste que registra uma pasta liberaria o acesso
    em outro teste e esconderia falhas de isolamento.
    """
    from src.utils.path_sandbox import clear_runtime_roots
    clear_runtime_roots()
    yield
    clear_runtime_roots()


@pytest.fixture(autouse=True)
def hermetic_network_guard(monkeypatch):
    """
    Prevents tests from leaking into host network (e.g. real Ollama on 11435/11434).
    Any unmocked connection to Ollama ports will raise ConnectionRefusedError.
    """
    import socket
    real_create_connection = socket.create_connection

    def _safe_create_connection(address, *args, **kwargs):
        host, port = address[0], address[1]
        if host in ("127.0.0.1", "localhost") and port in (11434, 11435):
            raise ConnectionRefusedError(f"[HermeticTestGuard] Blocked real host socket connection to {host}:{port}")
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", _safe_create_connection)
    yield
