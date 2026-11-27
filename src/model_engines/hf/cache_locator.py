"""
Catálogo de Modelos (MODELS_REGISTRY), Localizador de Caches, Sondagem de Manifesto Remoto (HfApi)
e Limpeza/Auditoria de Artefatos Físicos do Hugging Face e Ollama.
"""

import os
import gc
import threading
from src.config import Config
from src.model_engines.hf.integrity_checker import (
    safe_remove_path,
    verify_file_integrity,
)


MODELS_REGISTRY = {
    "florence2": {
        "name": "Módulo de Visão & OCR (Florence-2-base)",
        "type": "huggingface_cache",
        "repo_id": "microsoft/Florence-2-base",
        "size_str": "~465 MB",
        "estimated_size_bytes": 465000000,
        "description": "Responsável por ler textos difíceis, balões inclinados e detectar elementos de arte no mangá.",
        "target_dir": "models",
        "cache_folder": "florence-2-base",
        "ignore_patterns": ["*.bin", "*.pt", "*.bin.index.json"],
    },
    "florence2_large": {
        "name": "Módulo de Visão & OCR de Alta Fidelidade (Florence-2-large)",
        "type": "huggingface_cache",
        "repo_id": "microsoft/Florence-2-large",
        "size_str": "~1.56 GB",
        "estimated_size_bytes": 1560000000,
        "description": "Modelo 3x maior (0.77B). Máxima acurácia para fontes estilizadas, balões pequenos e arte complexa de mangá.",
        "target_dir": "models",
        "cache_folder": "florence-2-large",
        "ignore_patterns": ["*.bin", "*.pt", "*.bin.index.json"],
    },
    "yolo_detector": {
        "name": "Detectores Espaciais de Balões e Painéis (YOLO)",
        "type": "huggingface_multi_single",
        "size_str": "~59 MB",
        "estimated_size_bytes": 58808181,
        "description": "Mapeia as coordenadas XY de cada balão de fala, quadros e garante a ordem de leitura da direita para a esquerda.",
        "files": [
            {"repo_id": "TheBlindMaster/yolov8n-manga-frame-seg", "filename": "best.pt", "target_dir": "models", "min_size_bytes": 3000000},
            {"repo_id": "ogkalu/comic-speech-bubble-detector-yolov8m", "filename": "comic-speech-bubble-detector.pt", "target_dir": "models", "min_size_bytes": 40000000}
        ]
    },
    "mistral_nemo": {
        "name": "Tradutor Especialista & Contextual (Mistral Nemo 12B)",
        "type": "ollama",
        "model_name": "mistral-nemo",
        "size_str": "~4.7 GB",
        "description": "Responsável pela tradução PT-BR mantendo a consistência do universo e personalidade."
    },
    "qwen_32b": {
        "name": "Tradutor Literário de Elite (Qwen 2.5 32B)",
        "type": "ollama",
        "model_name": "qwen2.5:32b",
        "size_str": "~19.8 GB",
        "description": "Tradução de altíssima qualidade em PT-BR com nuances literárias, gírias e contexto consistente."
    }
}


def get_candidate_roots(base_dir: str) -> list[str]:
    """
    Retorna a lista ordenada de diretórios raiz candidatos para busca de modelos.
    
    POR QUE MÚLTIPLAS RAÍZES:
    No ambiente desktop empacotado (Electron + Python sidecar), o 'base_dir' pode apontar para
    a pasta de recursos descompactados temporários ou para o diretório de instalação do app.
    Também checamos 'VISIONARY_PROJECT_ROOT' para que desenvolvedores possam rodar a aplicação
    compartilhando pesos de IA já baixados na raiz do repositório, sem duplicar gigabytes em disco.
    """
    roots = [base_dir]
    if not Config.is_test_environment():
        project_root = os.environ.get("VISIONARY_PROJECT_ROOT")
        if not project_root:
            project_root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
        if project_root and project_root not in roots and os.path.isdir(project_root):
            roots.append(project_root)
    return roots


def get_monitor_paths(base_dir: str, key: str, registry: dict = None) -> list[str]:
    """
    Retorna todos os caminhos físicos em disco monitorados durante o download de um modelo.
    
    MOTIVAÇÃO:
    Downloads do Hugging Face e PyTorch salvam dados em múltiplos locais intermediários:
    - Arquivos temporários parciais (.incomplete, .part, .tmp)
    - Pastas internas de snapshot (.cache/huggingface/hub/models--...)
    O sensor de telemetria precisa monitorar todas essas pastas para calcular o volume
    parcial baixado mesmo antes da consolidação do arquivo final.
    """
    reg = registry if registry is not None else MODELS_REGISTRY
    if key not in reg:
        return []
    info = reg[key]
    target_path = os.path.join(base_dir, info.get("target_dir", "models"))
    monitor_paths = []
    if info.get("type") == "huggingface_cache":
        cache_folder = info.get("cache_folder", "")
        if cache_folder:
            target_folder = os.path.join(target_path, cache_folder)
            monitor_paths.append(target_folder)
            monitor_paths.append(os.path.join(target_folder, "xet"))
            monitor_paths.append(os.path.join(target_folder, ".huggingface"))
            monitor_paths.append(os.path.join(target_folder, ".cache"))
        else:
            monitor_paths.append(target_path)
            monitor_paths.append(os.path.join(target_path, "xet"))
            monitor_paths.append(os.path.join(target_path, ".huggingface"))
        repo_id = info.get("repo_id")
        if repo_id:
            repo_folder = "models--" + repo_id.replace("/", "--")
            monitor_paths.append(os.path.join(target_path, ".cache", "huggingface", "hub", repo_folder))
            monitor_paths.append(os.path.join(base_dir, ".cache", "huggingface", "hub", repo_folder))
    elif info.get("type") == "huggingface_multi_single":
        for f in info.get("files", []):
            sub_target = os.path.join(base_dir, f.get("target_dir", "models"))
            monitor_paths.append(os.path.join(sub_target, f["filename"]))
            monitor_paths.append(os.path.join(sub_target, f"{f['filename']}.incomplete"))
            monitor_paths.append(os.path.join(sub_target, f"{f['filename']}.part"))
            monitor_paths.append(os.path.join(sub_target, f"{f['filename']}.tmp"))
            monitor_paths.append(os.path.join(sub_target, ".huggingface"))
            monitor_paths.append(os.path.join(sub_target, ".cache"))
            repo_folder = "models--" + f["repo_id"].replace("/", "--")
            monitor_paths.append(os.path.join(sub_target, ".cache", "huggingface", "hub", repo_folder))
    elif info.get("type") == "single_file":
        fn = os.path.join(target_path, info.get("filename", "model.pt"))
        monitor_paths.append(fn)
        monitor_paths.append(fn + ".part")
        monitor_paths.append(fn + ".incomplete")
        monitor_paths.append(fn + ".tmp")
    return monitor_paths


def probe_hf_manifest_detailed(base_dir: str, info: dict, target_path: str) -> dict:
    """
    Inspeciona o manifesto real do Hugging Face antes do download e retorna o mapa completo
    de arquivos esperados com seus tamanhos exatos em bytes e bytes já completos em disco.

    Retorna:
        {
            "total_bytes": int,
            "pre_bytes": int,
            "file_count": int,
            "files": {
                rfilename: {
                    "size": int,
                    "local_path": str,
                    "pre_bytes": int,
                    "completed": bool,
                }
            },
        }
    """
    est_size = int(info.get("estimated_size_bytes", 0) or 0)
    fallback = {
        "total_bytes": est_size,
        "pre_bytes": 0,
        "file_count": 0,
        "files": {},
    }
    if Config.is_test_environment():
        return fallback
    try:
        import fnmatch
        from huggingface_hub import HfApi

        api = HfApi()
        if info.get("type") == "huggingface_cache":
            repo_id = info.get("repo_id")
            if not repo_id:
                return fallback
            local_dir = os.path.join(target_path, info.get("cache_folder", "florence-2-base"))
            ignore_pats = info.get("ignore_patterns") or []
            # Consulta os metadados do repositório remoto sem baixar os pesos binários
            m_info = api.model_info(repo_id=repo_id, files_metadata=True)
            siblings = getattr(m_info, "siblings", None) or []
            exact_tot = 0
            pre_bytes = 0
            f_cnt = 0
            files_map = {}
            for sib in siblings:
                rfn = getattr(sib, "rfilename", "") or ""
                # Ignora arquivos desnecessários conforme regex do registro (ex: *.bin se safetensors for usado)
                if not rfn or any(fnmatch.fnmatch(rfn, pat) for pat in ignore_pats):
                    continue
                f_cnt += 1
                sz = int(getattr(sib, "size", 0) or 0)
                if sz > 0:
                    exact_tot += sz
                    lp = os.path.join(local_dir, *rfn.split("/"))
                    f_pre = 0
                    completed = False
                    try:
                        # Se o arquivo já existe no disco com o tamanho idêntico, conta como já baixado
                        if os.path.isfile(lp) and os.path.getsize(lp) == sz:
                            f_pre = sz
                            completed = True
                            pre_bytes += sz
                    except OSError:
                        pass
                    files_map[rfn] = {
                        "size": sz,
                        "local_path": lp,
                        "pre_bytes": f_pre,
                        "completed": completed,
                    }
            if exact_tot > 0:
                return {
                    "total_bytes": exact_tot,
                    "pre_bytes": min(pre_bytes, exact_tot),
                    "file_count": f_cnt,
                    "files": files_map,
                }
        elif info.get("type") == "huggingface_multi_single":
            import concurrent.futures

            files = info.get("files") or []
            exact_tot = 0
            pre_bytes = 0
            files_map = {}

            # Sondagem paralela para múltiplos pesos (ex: 2 modelos YOLO em repositórios diferentes)
            def _probe_single(f_entry):
                repo_id = f_entry.get("repo_id")
                fn = f_entry.get("filename")
                if not repo_id or not fn:
                    return fn, 0, 0, ""
                m_info = api.model_info(repo_id=repo_id, files_metadata=True)
                for sib in (getattr(m_info, "siblings", None) or []):
                    if getattr(sib, "rfilename", "") == fn:
                        sz = int(getattr(sib, "size", 0) or 0)
                        if sz > 0:
                            lp = os.path.join(base_dir, f_entry.get("target_dir", "models"), fn)
                            try:
                                if os.path.isfile(lp) and os.path.getsize(lp) == sz:
                                    return fn, sz, sz, lp
                            except OSError:
                                pass
                            return fn, sz, 0, lp
                        break
                return fn, 0, 0, ""

            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(4, len(files)))) as ex:
                for fn, f_sz, f_pre, lp in ex.map(_probe_single, files):
                    if fn and f_sz > 0:
                        exact_tot += f_sz
                        pre_bytes += f_pre
                        files_map[fn] = {
                            "size": f_sz,
                            "local_path": lp,
                            "pre_bytes": f_pre,
                            "completed": f_pre == f_sz,
                        }

            if exact_tot > 0:
                return {
                    "total_bytes": exact_tot,
                    "pre_bytes": min(pre_bytes, exact_tot),
                    "file_count": len(files),
                    "files": files_map,
                }
    except Exception:
        pass
    return fallback


def probe_hf_manifest(base_dir: str, info: dict, target_path: str) -> tuple[int, int, int]:
    """
    Inspeciona o manifesto real do Hugging Face antes do download.
    Delega para `probe_hf_manifest_detailed` mantendo assinatura legada `(exact_total, pre_bytes, file_count)`.
    """
    manifest = probe_hf_manifest_detailed(base_dir, info, target_path)
    return (
        int(manifest.get("total_bytes", 0)),
        int(manifest.get("pre_bytes", 0)),
        int(manifest.get("file_count", 0)),
    )


def remove_model_artifacts(manager, key: str, registry: dict = None) -> bool:
    """
    Remove o modelo especificado do disco de forma thread-safe em todas as raízes candidatas e caches.
    
    CUIDADOS CRÍTICOS NO WINDOWS:
    1. Liberação de Memória GPU antes da Exclusão:
       Pesos de modelos carregados na VRAM geram locks do kernel do Windows nos arquivos (.safetensors/.pt).
       Chamar 'cleanup_gpu_memory(force_ipc=True)' descarrega os pesos da placa de vídeo antes de tentar deletar.
    2. Sinalização de Cancelamento e Join Cooperativo:
       Se uma thread de download estiver ativa, acionamos 'cancel_events' e aguardamos até 2 segundos
       para que ela feche seus sockets de rede antes de remover os diretórios parciais.
    3. Limpeza de Caches Globais do Hugging Face (~/.cache/huggingface/hub):
       O HF armazena dados em blobs globais e cria links locais. Remover apenas a pasta do projeto
       deixaria gigabytes de blobs órfãos no disco do usuário; varremos e limpamos ambas as localizações.
    4. Remoção em Modelos Ollama via API REST:
       Se for um modelo LLM (tipo 'ollama'), invocamos o endpoint '/api/delete' do servidor Ollama local.
    """
    reg = registry if registry is not None else MODELS_REGISTRY
    if key not in reg:
        return False

    gc.collect()
    try:
        from src.utils.gpu_utils import cleanup_gpu_memory
        cleanup_gpu_memory(force_ipc=True, unload_ollama=False)
    except Exception:
        pass

    info = reg[key]
    try:
        with manager._status_lock:
            dl_thread = manager._download_threads.get(key)
            if key in manager._stop_events:
                manager._stop_events[key].set()
            if key in manager._cancel_events:
                manager._cancel_events[key].set()

            manager.download_status[key] = {
                "status": "missing",
                "progress": 0.0,
                "downloaded_bytes": 0,
                "total_bytes": info.get("estimated_size_bytes", 0),
                "message": "Removido do sistema"
            }

            if key in ["florence2", "florence2_large"]:
                other_k = "florence2_large" if key == "florence2" else "florence2"
                other_info = reg.get(other_k, {})
                manager.download_status[other_k] = {
                    "status": "missing",
                    "progress": 0.0,
                    "downloaded_bytes": 0,
                    "total_bytes": other_info.get("estimated_size_bytes", 0),
                    "message": "Removido do sistema"
                }

        manager._notify_progress(key, throttle_interval=0.0)
        if key in ["florence2", "florence2_large"]:
            manager._notify_progress("florence2_large" if key == "florence2" else "florence2", throttle_interval=0.0)

        # Aguarda término cooperativo de thread de download ativa
        if dl_thread is not None and dl_thread.is_alive() and dl_thread is not threading.current_thread():
            dl_thread.join(timeout=2.0)

        candidate_roots = manager._get_candidate_roots()

        hf_hub_dirs = []
        if not Config.is_test_environment():
            hf_hub_dirs.append(os.path.expanduser("~/.cache/huggingface/hub"))
            if os.environ.get("HF_HOME"):
                hf_hub_dirs.append(os.path.join(os.environ["HF_HOME"], "hub"))
                hf_hub_dirs.append(os.environ["HF_HOME"])

        if key in ["florence2", "florence2_large"]:
            florence_folders = [
                "florence-2-base",
                "florence-2-large",
                "models--microsoft--Florence-2-base",
                "models--microsoft--Florence-2-large",
            ]
            for cr in candidate_roots:
                m_dir = os.path.join(cr, "models")
                for ff in florence_folders:
                    safe_remove_path(os.path.join(m_dir, ff))
                    safe_remove_path(os.path.join(m_dir, ".locks", ff))
            for hf_dir in hf_hub_dirs:
                for ff in florence_folders:
                    safe_remove_path(os.path.join(hf_dir, ff))
                    safe_remove_path(os.path.join(hf_dir, ".locks", ff))

        elif info["type"] == "huggingface_cache":
            cache_folder = info.get("cache_folder", "")
            repo_folder = "models--" + info["repo_id"].replace("/", "--")
            target_sub = info.get("target_dir", "models")

            for cr in candidate_roots:
                m_dir = os.path.join(cr, target_sub)
                if cache_folder:
                    safe_remove_path(os.path.join(m_dir, cache_folder))
                safe_remove_path(os.path.join(m_dir, repo_folder))
                safe_remove_path(os.path.join(m_dir, ".locks", repo_folder))

            for hf_dir in hf_hub_dirs:
                safe_remove_path(os.path.join(hf_dir, repo_folder))
                if cache_folder:
                    safe_remove_path(os.path.join(hf_dir, cache_folder))
                safe_remove_path(os.path.join(hf_dir, ".locks", repo_folder))

        elif info["type"] == "huggingface_multi_single":
            for f in info.get("files", []):
                fn = f["filename"]
                target_sub = f.get("target_dir", "models")
                repo_folder = "models--" + f["repo_id"].replace("/", "--")

                for cr in candidate_roots:
                    sub_target = os.path.join(cr, target_sub)
                    target_file = os.path.join(sub_target, fn)
                    safe_remove_path(target_file)
                    safe_remove_path(target_file + ".part")
                    safe_remove_path(target_file + ".tmp")

                    repo_cache = os.path.join(sub_target, ".cache", "huggingface", "hub", repo_folder)
                    safe_remove_path(repo_cache)
                    safe_remove_path(os.path.join(sub_target, ".locks", repo_folder))

                    dl_cache_dir = os.path.join(sub_target, ".cache", "huggingface", "download")
                    if os.path.isdir(dl_cache_dir):
                        try:
                            for cached_item in os.listdir(dl_cache_dir):
                                if cached_item.startswith(fn):
                                    safe_remove_path(os.path.join(dl_cache_dir, cached_item))
                            if not os.listdir(dl_cache_dir):
                                safe_remove_path(dl_cache_dir)
                        except OSError:
                            pass

                    hub_dir = os.path.join(sub_target, ".cache", "huggingface", "hub")
                    if os.path.exists(hub_dir) and not os.listdir(hub_dir):
                        safe_remove_path(hub_dir)
                    hf_dir = os.path.join(sub_target, ".cache", "huggingface")
                    if os.path.exists(hf_dir) and not os.listdir(hf_dir):
                        safe_remove_path(hf_dir)
                    dot_cache = os.path.join(sub_target, ".cache")
                    if os.path.exists(dot_cache) and not os.listdir(dot_cache):
                        safe_remove_path(dot_cache)

                for hf_dir in hf_hub_dirs:
                    safe_remove_path(os.path.join(hf_dir, repo_folder))
                    safe_remove_path(os.path.join(hf_dir, ".locks", repo_folder))

        elif info["type"] == "single_file":
            target_sub = info.get("target_dir", "models")
            fn = info.get("filename", "")
            for cr in candidate_roots:
                target_file = os.path.join(cr, target_sub, fn)
                safe_remove_path(target_file)
                safe_remove_path(target_file + ".part")
                safe_remove_path(target_file + ".tmp")

            hub_file = os.path.join(os.path.expanduser("~"), ".cache", "torch", "hub", "checkpoints", fn)
            safe_remove_path(hub_file)

        elif info["type"] == "ollama":
            ollama_ok = manager.ollama_manager.check_ollama_running() if manager.ollama_manager else False
            if ollama_ok:
                import requests
                candidates = [Config.get("ollama_url", "http://127.0.0.1:11435/api"), "http://127.0.0.1:11434/api"]
                session = requests.Session()
                session.trust_env = False
                for base in candidates:
                    try:
                        url = base.replace("localhost", "127.0.0.1").rstrip("/") + "/delete"
                        session.delete(url, json={"name": info["model_name"]}, timeout=5.0)
                        break
                    except Exception:
                        continue

        gc.collect()

        is_still_cached = False
        for cr in candidate_roots:
            if info["type"] == "huggingface_cache":
                cache_folder = info.get("cache_folder", "")
                if cache_folder and os.path.exists(os.path.join(cr, "models", cache_folder)):
                    is_still_cached = True
            elif info["type"] == "huggingface_multi_single":
                for f in info.get("files", []):
                    if os.path.exists(os.path.join(cr, f.get("target_dir", "models"), f["filename"])):
                        is_still_cached = True

        if is_still_cached:
            print(f"[ModelManager] Aviso: Alguns arquivos de {key} ainda persistem no disco após tentativa de remoção.")
            return False

        return True
    except Exception as e:
        print(f"[ModelManager] Failed to remove {key}: {e}")
        return False


def resolve_all_models_status(manager, ollama_models: set = None, registry: dict = None) -> dict:
    """Retorna o dicionário consolidado de status de todos os modelos no registry."""
    reg = registry if registry is not None else MODELS_REGISTRY
    if ollama_models is None and manager.ollama_manager:
        ollama_models = manager.ollama_manager.get_ollama_models()
    ollama_models = ollama_models or set()

    status_dict = {}

    for key, info in reg.items():
        current_dl = manager.get_download_status(key)
        if current_dl["status"] in ["downloading", "extracting", "error"]:
            status_dict[key] = {
                **info,
                "status": current_dl["status"],
                "progress": current_dl["progress"],
                "downloaded_bytes": current_dl["downloaded_bytes"],
                "total_bytes": current_dl["total_bytes"],
                "speed_mbps": current_dl.get("speed_mbps", 0.0),
                "eta_seconds": current_dl.get("eta_seconds", 0),
                "message": current_dl["message"]
            }
            continue

        if info["type"] == "huggingface_cache":
            repo_folder = "models--" + info["repo_id"].replace("/", "--")
            cache_folder = info.get("cache_folder", "")
            target_sub = info.get("target_dir", "models")

            candidate_paths = []
            for cr in manager._get_candidate_roots():
                m_dir = os.path.join(cr, target_sub)
                if cache_folder:
                    candidate_paths.append(os.path.join(m_dir, cache_folder))
                candidate_paths.append(os.path.join(m_dir, repo_folder))

            hf_hub_dirs = []
            if not Config.is_test_environment():
                hf_hub_dirs.append(os.path.expanduser("~/.cache/huggingface/hub"))
                if os.environ.get("HF_HOME"):
                    hf_hub_dirs.append(os.path.join(os.environ["HF_HOME"], "hub"))
                    hf_hub_dirs.append(os.environ["HF_HOME"])
            for hf_dir in hf_hub_dirs:
                candidate_paths.append(os.path.join(hf_dir, repo_folder))
                if cache_folder:
                    candidate_paths.append(os.path.join(hf_dir, cache_folder))

            is_installed = any(manager.is_hf_model_cached(cp) for cp in candidate_paths)
        elif info["type"] == "huggingface_multi_single":
            is_installed = True
            for f in info["files"]:
                fn = f["filename"]
                target_sub = f.get("target_dir", "models")
                min_sz = f.get("min_size_bytes", 1024 * 1024)
                if Config.is_test_environment():
                    min_sz = min(min_sz, 100)

                file_found = False
                for cr in manager._get_candidate_roots():
                    p = os.path.join(cr, target_sub, fn)
                    if verify_file_integrity(p, min_size_bytes=min_sz):
                        file_found = True
                        break
                if not file_found:
                    repo_folder = "models--" + f["repo_id"].replace("/", "--")
                    hf_dirs = []
                    if not Config.is_test_environment():
                        hf_dirs.append(os.path.expanduser("~/.cache/huggingface/hub"))
                        if os.environ.get("HF_HOME"):
                            hf_dirs.append(os.path.join(os.environ["HF_HOME"], "hub"))
                            hf_dirs.append(os.environ["HF_HOME"])
                    for hf_dir in hf_dirs:
                        snap_dir = os.path.join(hf_dir, repo_folder, "snapshots")
                        if os.path.isdir(snap_dir):
                            for root, _, files in os.walk(snap_dir):
                                if fn in files:
                                    fp = os.path.join(root, fn)
                                    if verify_file_integrity(fp, min_size_bytes=min_sz):
                                        file_found = True
                                        break
                            if file_found:
                                break
                if not file_found:
                    is_installed = False
                    break
        elif info["type"] == "ollama":
            is_installed = info["model_name"] in ollama_models or info["model_name"].split(":")[0] in ollama_models
        elif info["type"] == "single_file":
            min_sz = info.get("min_size_bytes", 100 * 1024 * 1024)
            hub_file = os.path.join(os.path.expanduser("~"), ".cache", "torch", "hub", "checkpoints", info["filename"])
            is_installed = (not Config.is_test_environment()) and os.path.exists(hub_file) and os.path.getsize(hub_file) >= min_sz
            if not is_installed:
                for cr in manager._get_candidate_roots():
                    target_file = os.path.join(cr, info["target_dir"], info["filename"])
                    if os.path.exists(target_file) and os.path.getsize(target_file) >= min_sz:
                        is_installed = True
                        break
        else:
            is_installed = False

        status_dict[key] = {
            **info,
            "status": "installed" if is_installed else "missing",
            "progress": 100.0 if is_installed else 0.0,
            "downloaded_bytes": info.get("estimated_size_bytes", 0) if is_installed else 0,
            "total_bytes": info.get("estimated_size_bytes", 0),
            "message": "Pronto para uso" if is_installed else "Não instalado no sistema"
        }

    return status_dict
