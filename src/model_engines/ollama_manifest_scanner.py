import os
import sys
import json
import time
from typing import List, Dict, Set, Optional


_CACHE_TTL = 1.0  # Cache de 1 segundo para evitar re-scans em loops ultra-rápidos
_manifests_cache: Dict[str, any] = {
    "timestamp": 0.0,
    "paths_key": "",
    "data": [],
    "sizes_parsed": False,
}


MANIFEST_ALIASES: Dict[str, str] = {
    "mradermacher/Amadeus-Verbo-FI-Qwen2.5-14B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:14b",
    "hf.co/mradermacher/Amadeus-Verbo-FI-Qwen2.5-14B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:14b",
    "mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:7b",
    "hf.co/mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:7b",
    "mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-i1-GGUF:Q4_K_M": "amadeus:7b",
    "hf.co/mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-i1-GGUF:Q4_K_M": "amadeus:7b",
    "mradermacher/AV-BI-Qwen2.5-32B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:32b",
    "hf.co/mradermacher/AV-BI-Qwen2.5-32B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:32b",
}


def invalidate_manifests_cache():
    """Invalida o cache em memória dos manifests para forçar re-scan físico imediato."""
    global _manifests_cache
    _manifests_cache["timestamp"] = 0.0
    _manifests_cache["paths_key"] = ""
    _manifests_cache["data"] = []
    _manifests_cache["sizes_parsed"] = False


def get_ollama_manifest_search_paths(custom_dir: Optional[str] = None) -> List[str]:
    """
    Retorna a lista de diretórios onde manifests do Ollama podem residir.
    Se um custom_dir for especificado explicitamente, retorna apenas ele.
    Caso contrário, busca nos caminhos padrão do sistema em ordem de prioridade:
    1. Variável de ambiente OLLAMA_MODELS
    2. Diretório padrão do usuário (~/.ollama/models ou %USERPROFILE%\\.ollama\\models)
    3. Diretório isolado do Visionary Studio (%APPDATA%\\Visionary Studio\\engine\\ollama\\models)
    4. Diretório padrão do sistema Linux (/usr/share/ollama/.ollama/models)
    """
    if custom_dir:
        return [os.path.abspath(custom_dir)]

    paths = []

    env_models = os.environ.get("OLLAMA_MODELS")
    if env_models and os.path.isdir(env_models):
        paths.append(os.path.abspath(env_models))

    # Padrão de usuário no Windows / Linux / macOS
    home = os.path.expanduser("~")
    user_ollama = os.path.join(home, ".ollama", "models")
    if os.path.isdir(user_ollama):
        paths.append(os.path.abspath(user_ollama))

    # Diretório isolado do Visionary
    try:
        from src.config import get_app_data_dir
        appdata_models = os.path.join(get_app_data_dir(), "engine", "ollama", "models")
        if os.path.isdir(appdata_models):
            paths.append(os.path.abspath(appdata_models))
    except Exception:
        pass

    # Diretório isolado do Visionary Studio no Windows Roaming (%APPDATA%\Visionary Studio)
    appdata = os.environ.get("APPDATA")
    if appdata:
        roaming_models = os.path.join(appdata, "Visionary Studio", "engine", "ollama", "models")
        if os.path.isdir(roaming_models):
            paths.append(os.path.abspath(roaming_models))

    # Padrão Linux compartilhado
    linux_sys = "/usr/share/ollama/.ollama/models"
    if os.path.isdir(linux_sys):
        paths.append(os.path.abspath(linux_sys))

    # Remove duplicatas preservando ordem
    unique_paths = []
    seen = set()
    for p in paths:
        norm = os.path.normpath(p).lower() if sys.platform == "win32" else os.path.normpath(p)
        if norm not in seen:
            seen.add(norm)
            unique_paths.append(p)

    return unique_paths


def parse_manifest_path(relpath: str) -> Optional[Dict[str, str]]:
    """
    Analisa o caminho relativo de um arquivo de manifesto e extrai model_name, tag e base_name.
    Exemplos:
      - registry.ollama.ai/library/qwen2.5/7b -> name="qwen2.5:7b", base="qwen2.5", tag="7b"
      - registry.ollama.ai/library/llama3.1/latest -> name="llama3.1:latest", base="llama3.1", tag="latest"
      - registry.ollama.ai/lly/qwen2.5-32b-instruct-iq3_m/latest -> name="lly/qwen2.5-32b-instruct-iq3_m:latest"
      - library/mistral/latest -> name="mistral:latest", base="mistral", tag="latest"
      - qwen2.5/7b -> name="qwen2.5:7b", base="qwen2.5", tag="7b"
    """
    normalized = relpath.replace("\\", "/").strip("/")
    parts = [p for p in normalized.split("/") if p and p != "."]

    if len(parts) < 2:
        return None

    tag = parts[-1]

    # Remove registry se for um domínio conhecido ou contiver ponto (ex: registry.ollama.ai)
    if len(parts) >= 4 and ("." in parts[0] or parts[0] == "registry.ollama.ai"):
        parts = parts[1:]

    # Remove namespace padrão 'library' se houver
    if len(parts) >= 3 and parts[0] == "library":
        parts = parts[1:]

    model_id = "/".join(parts[:-1])
    full_name = f"{model_id}:{tag}"

    return {
        "name": full_name,
        "base_name": model_id,
        "tag": tag,
    }


def scan_local_manifests(
    custom_dir: Optional[str] = None,
    parse_sizes: bool = False,
    force_refresh: bool = False,
) -> List[Dict]:
    """
    Realiza varredura física ultrarrápida (< 1ms) nas pastas de manifests locais.
    Retorna lista de modelos fisicamente presentes no SSD/HD.
    """
    global _manifests_cache
    now = time.time()

    search_roots = get_ollama_manifest_search_paths(custom_dir)
    paths_key = "|".join(search_roots)

    if (
        not force_refresh
        and _manifests_cache["data"]
        and _manifests_cache["paths_key"] == paths_key
        and (now - _manifests_cache["timestamp"]) < _CACHE_TTL
        and (not parse_sizes or _manifests_cache.get("sizes_parsed", False))
    ):
        return list(_manifests_cache["data"])

    discovered: Dict[str, Dict] = {}

    for root in search_roots:
        # Garante que estamos apontando para a pasta 'manifests'
        manifests_dir = root if os.path.basename(root) == "manifests" else os.path.join(root, "manifests")
        if not os.path.isdir(manifests_dir):
            continue

        try:
            for dirpath, _, filenames in os.walk(manifests_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        rel = os.path.relpath(filepath, manifests_dir)
                        parsed = parse_manifest_path(rel)
                        if not parsed:
                            continue

                        model_name = parsed["name"]
                        if model_name in discovered:
                            continue

                        mtime = os.path.getmtime(filepath)
                        total_size = 0

                        if parse_sizes:
                            try:
                                with open(filepath, "r", encoding="utf-8") as f:
                                    data = json.load(f)
                                layers = data.get("layers", [])
                                total_size = sum(l.get("size", 0) for l in layers)
                                config_size = data.get("config", {}).get("size", 0)
                                total_size += config_size
                            except Exception:
                                total_size = 0

                        discovered[model_name] = {
                            "name": model_name,
                            "base_name": parsed["base_name"],
                            "tag": parsed["tag"],
                            "size": total_size,
                            "mtime": mtime,
                            "manifest_path": filepath,
                        }
                    except Exception:
                        continue
        except Exception:
            continue

    for raw_name, friendly_name in MANIFEST_ALIASES.items():
        if raw_name in discovered and friendly_name not in discovered:
            src = discovered[raw_name]
            base = friendly_name.split(":")[0]
            tag = friendly_name.split(":")[1] if ":" in friendly_name else "latest"
            discovered[friendly_name] = {
                "name": friendly_name,
                "base_name": base,
                "tag": tag,
                "size": src.get("size", 0),
                "mtime": src.get("mtime", now),
                "manifest_path": src.get("manifest_path", ""),
            }

    result = list(discovered.values())
    result.sort(key=lambda x: x["name"])

    _manifests_cache["timestamp"] = now
    _manifests_cache["paths_key"] = paths_key
    _manifests_cache["data"] = result
    _manifests_cache["sizes_parsed"] = parse_sizes

    return list(result)


def get_installed_ollama_model_names(custom_dir: Optional[str] = None) -> Set[str]:
    """
    Retorna o conjunto de nomes de modelos instalados no Ollama,
    incluindo o nome completo com tag (ex: 'qwen2.5:7b') e o nome base (ex: 'qwen2.5').
    """
    manifests = scan_local_manifests(custom_dir=custom_dir, parse_sizes=False)
    names = set()
    for m in manifests:
        name = m.get("name")
        base = m.get("base_name")
        if name:
            names.add(name)
        if base:
            names.add(base)
    return names


def get_installed_ollama_models_list(custom_dir: Optional[str] = None) -> List[str]:
    """
    Retorna lista ordenada contendo apenas as tags completas dos modelos instalados
    (ex: ['llama3.1:latest', 'qwen2.5:32b', 'qwen2.5:7b']).
    """
    manifests = scan_local_manifests(custom_dir=custom_dir, parse_sizes=False)
    return [m["name"] for m in manifests if m.get("name")]
