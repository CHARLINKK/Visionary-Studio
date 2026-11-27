"""
Módulo de Configuração (Config).
Gerencia o mapeamento de diretórios de dados (App Data) e as configurações (settings locais) do Visionary Studio.
A arquitetura de salvamento garante atomicidade para evitar corrupção de arquivos, com estratégias de fallback de diretórios 
(Modo Portátil -> Electron User Data -> Local Relativo -> AppData Windows). 
Implementa locks re-entrantes (RLock) para blindar as configurações contra condições de corrida durante o acesso assíncrono.
"""

import sys
import os
import json
import threading
from PIL import ImageFile

# Permite que imagens com EOF quebrado ou download truncado sejam lidas com segurança
ImageFile.LOAD_TRUNCATED_IMAGES = True

# O HuggingFace usa symlinks por padrão, o que dispara OSError [Errno 22] no Windows sem Developer Mode ativo.
# O HuggingFace usa symlinks de snapshot que falham no Windows sem Developer Mode
# ativo. Forçar cópia física dos arquivos garante estabilidade absoluta em qualquer
# máquina de usuário final, independente de permissões do sistema.
# setdefault respeita variáveis já definidas pelo usuário ou ambiente de CI.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
# Garante que o huggingface_hub não tente criar tokens ou home directories
# no perfil do usuário quando operando com cache_dir explícito do projeto.
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
# Evita fragmentação do pool de VRAM durante alternância entre modelos (YOLO, Florence-2).
# No Windows, expandable_segments não é suportado pelo backend PyTorch CUDA e emite UserWarning contínuo.
if sys.platform == "win32":
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:128")
else:
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

def is_test_environment() -> bool:
    """
    Detecta se o processo atual está executando sob suíte de testes automatizados
    ou modo de teste isolado (garantindo que testes nunca toquem dados reais do host,
    caches globais ~/.cache ou emitam notificações nativas do SO).
    """
    return bool(
        os.environ.get("PYTEST_CURRENT_TEST")
        or os.environ.get("VISIONARY_TEST_ENV") == "1"
    )


def get_app_data_dir() -> str:
    """
    Retorna o diretório de dados do Visionary Studio seguindo uma hierarquia estrita:
    1. Precedência Soberana: VISIONARY_USER_DATA (injetada pelo Electron ou testes isolados)
    2. Modo Portátil: se existir .portable na raiz do executável/projeto, isola em pasta 'data/'
    3. Produção / Desenvolvimento Windows: %APPDATA%\\Visionary Studio (evita poluir a árvore git)
    4. Fallback Local Isolado: subpasta 'data/' dentro do diretório local
    """
    user_data = os.environ.get("VISIONARY_USER_DATA")
    if user_data:
        try:
            clean = os.path.normpath(user_data)
            os.makedirs(clean, exist_ok=True)
            return clean
        except Exception:
            pass

    local_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

    # 2. Modo Portátil explícito (.portable na raiz do executável/projeto)
    is_portable = (
        os.path.exists(os.path.join(local_path, ".portable"))
        or os.path.exists(os.path.join(os.path.dirname(local_path), ".portable"))
    )
    if is_portable:
        portable_data = os.path.join(local_path, "data")
        try:
            os.makedirs(portable_data, exist_ok=True)
            return portable_data
        except Exception:
            return local_path

    # 3. Diretório padrão de dados do usuário no Windows (%APPDATA%\Visionary Studio)
    appdata = os.environ.get("APPDATA")
    if appdata:
        prod_dir = os.path.join(appdata, "Visionary Studio")
        try:
            os.makedirs(prod_dir, exist_ok=True)
            return prod_dir
        except Exception:
            pass

    # 4. Fallback isolado em subpasta 'data/' sem sujar a raiz do repositório
    fallback_data = os.path.join(local_path, "data")
    try:
        os.makedirs(fallback_data, exist_ok=True)
        return fallback_data
    except Exception:
        return local_path

def _get_config_path() -> str:
    return os.path.join(get_app_data_dir(), "settings.json")

CONFIG_FILE = _get_config_path()
_last_dynamic_path = CONFIG_FILE

# RLock (reentrante) protege operações read-modify-write em settings.json; um Lock simples daria deadlock em update().
# em settings.json. Re-entrante porque update() chama load() + save() internamente
# — com um Lock simples, isso causaria deadlock na mesma thread.
_config_lock = threading.RLock()

class Config:
    """
    Gerenciador thread-safe do arquivo `settings.json`.
    Utiliza estratégias de read-modify-write isoladas por RLock, escritas atômicas com arquivos temporários e
    flush/fsync a nível de sistema operacional (Windows) para evitar que crashes resultem em arquivos de 0-bytes.
    """
    _defaults = {
        "ollama_url": "http://127.0.0.1:11435/api",
        "flask_port": 5000,
        "theme": "Dark",
        "accent": "Roxo (Padrão)",
        "sidebarWidth": 250,
        "rememberZoom": False,
        "last_opened_folder": "",
        "baseFolder": "",
        "pipeline_steps": {"layout": True, "ocr": True, "translate": True},
        "translation_tone": "neutral",
        "selected_models": {},
        "systemNotifications": True,
        "notifyOnlyInBackground": True,
        "debugPanelMaps": False,
        "autoUpdate": True,
        "enableVLM": True,
        "uiDensity": "comfortable",
        "soundFeedback": True,
        "soundStyle": "harmonic",
        "soundVolume": 80,
        "reduceMotion": False,
        "acrylicBlur": True,
        "fontFamily": "modern",
        "uiScale": "100%",
        "showPagePills": True,
        "showStatusDots": True,
        "autoResumePending": True,
        "autoTurnPage": False,
        "autoZoomLibrary": False,
        "quickSymbols": False,
        "first_run_completed": False,
        "close_action": "smart",
        "preserve_translation_case": False,
    }
    _cached_data = None
    _cached_mtime = 0
    _cached_file = ""

    @staticmethod
    def is_test_environment() -> bool:
        """Retorna True quando executando sob pytest ou ambiente de teste isolado."""
        return is_test_environment()

    @classmethod
    def get_config_path(cls) -> str:
        """Resolve dinamicamente o caminho de settings.json respeitando patches em CONFIG_FILE."""
        import sys
        mod = sys.modules.get("src.config")
        current_global = getattr(mod, "CONFIG_FILE", None) if mod else None
        dynamic_path = _get_config_path()
        last_dyn = getattr(mod, "_last_dynamic_path", None) if mod else None

        # Se CONFIG_FILE foi explicitamente modificado para um caminho customizado diferente do dynamic_path anterior
        if current_global and last_dyn and current_global != last_dyn and current_global != dynamic_path:
            return current_global

        if mod:
            mod._last_dynamic_path = dynamic_path
            mod.CONFIG_FILE = dynamic_path
        return dynamic_path

    @classmethod
    def update(cls, new_data):
        if not isinstance(new_data, dict):
            return cls.load()
        with _config_lock:
            data = cls.load()
            data.update(new_data)
            cls.save(data)
            return data

    @classmethod
    def load(cls):
        with _config_lock:
            config_file = cls.get_config_path()
            if cls._cached_file != config_file:
                cls._cached_data = None
                cls._cached_mtime = 0
                cls._cached_file = config_file

            if not os.path.exists(config_file):
                cls.save(cls._defaults)
                return dict(cls._defaults)
            
            try:
                from src.utils.file_resilience import resilient_read_json, retry_on_file_lock
                mtime = retry_on_file_lock(lambda: os.path.getmtime(config_file))
                if cls._cached_data is not None and mtime == cls._cached_mtime:
                    return dict(cls._cached_data)

                data = resilient_read_json(config_file, encoding="utf-8")
                    
                # Se o arquivo contiver JSON válido mas não for um dicionário (ex: array []), restaura defaults
                if not isinstance(data, dict):
                    data = dict(cls._defaults)
                    cls.save(data)
                    return data

                # Preenche chaves novas adicionadas em versões recentes preservando escolhas do usuário
                updated = False
                for k, v in cls._defaults.items():
                    if k not in data:
                        data[k] = v
                        updated = True
                
                if updated:
                    cls.save(data)
                else:
                    cls._cached_data = dict(data)
                    cls._cached_mtime = mtime
                    
                return data
            except Exception as e:
                from src.utils.file_resilience import is_transient_lock_error
                if is_transient_lock_error(e):
                    return dict(cls._cached_data if cls._cached_data is not None else cls._defaults)
                # Recuperação automática de corrupção (arquivo vazio ou malformado)
                try:
                    if os.path.exists(config_file) and os.path.getsize(config_file) > 0:
                        bak_file = f"{config_file}.bak"
                        import shutil
                        shutil.copy2(config_file, bak_file)
                    cls.save(cls._defaults)
                except Exception:
                    pass
                return dict(cls._defaults)
            
    @classmethod
    def save(cls, data):
        with _config_lock:
            try:
                from src.utils.json_utils import atomic_write_json
                config_file = cls.get_config_path()
                cls._cached_file = config_file
                target_dir = os.path.dirname(config_file)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)

                if atomic_write_json(config_file, data, indent=2):
                    cls._cached_data = dict(data)
                    try:
                        cls._cached_mtime = os.path.getmtime(config_file)
                    except Exception:
                        pass
                else:
                    print(f"[Config] Warning: atomic_write_json failed for {config_file}")
            except Exception as e:
                print(f"[Config] Error saving config: {e}")

    @classmethod
    def get(cls, key, fallback=None):
        with _config_lock:
            data = cls.load()
            return data.get(key, fallback)

    @classmethod
    def set(cls, key, value):
        with _config_lock:
            data = cls.load()
            data[key] = value
            cls.save(data)

