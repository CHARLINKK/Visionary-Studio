import os


def _resolve_hf_snapshot_path(cache_dir: str, repo_id: str) -> str | None:
    """
    Resolve o caminho físico do snapshot mais recente de um modelo HuggingFace.
    Isso contorna o bug OSError [Errno 22] no Windows, onde o HF Transformers tenta
    abrir symlinks de snapshot que falham sem o Developer Mode ativo.
    Ao passar o caminho direto do snapshot, pulamos completamente a resolução de links.

    Returns:
        Caminho absoluto para a pasta do snapshot, ou None se não encontrado.
    """
    repo_folder = "models--" + repo_id.replace("/", "--")
    snapshots_dir = os.path.join(cache_dir, repo_folder, "snapshots")
    if not os.path.isdir(snapshots_dir):
        return None
    try:
        snaps = [
            d for d in os.listdir(snapshots_dir)
            if os.path.isdir(os.path.join(snapshots_dir, d))
        ]
        if not snaps:
            return None
        # Ordena por data de modificação para pegar o mais recente
        snaps.sort(
            key=lambda d: os.path.getmtime(os.path.join(snapshots_dir, d)),
            reverse=True
        )
        snapshot_path = os.path.join(snapshots_dir, snaps[0])
        # Valida que o snapshot tem arquivos reais (não apenas locks/tmp)
        for root, _, files in os.walk(snapshot_path):
            for f in files:
                if not f.endswith((".lock", ".tmp")) and not f.startswith("."):
                    fp = os.path.join(root, f)
                    if os.path.isfile(fp) and os.path.getsize(fp) > 0:
                        return snapshot_path
    except Exception:
        pass
    return None


resolve_hf_snapshot_path = _resolve_hf_snapshot_path


def is_valid_florence_dir(dir_path: str | None) -> bool:
    """
    Verifica se um diretório contém os artefatos mínimos necessários para carregar
    o modelo Florence-2 localmente sem falhas ou downloads espúrios.
    Exige config.json, código de arquitetura remota e pesos válidos.
    Protege contra downloads truncados exigindo limites mínimos realistas de tamanho.
    """
    if not dir_path or not os.path.isdir(dir_path):
        return False
    if not os.path.isfile(os.path.join(dir_path, "config.json")):
        return False
    # Florence-2 usa classes customizadas remotas no Transformers
    has_code = (
        os.path.isfile(os.path.join(dir_path, "processing_florence2.py")) or
        os.path.isfile(os.path.join(dir_path, "modeling_florence2.py"))
    )
    if not has_code:
        return False
    weight_files = (
        "model.safetensors",
        "pytorch_model.bin",
        "model.safetensors.index.json",
        "pytorch_model.bin.index.json",
    )

    from src.config import is_test_environment
    is_test = is_test_environment()
    d_lower = dir_path.lower()
    if is_test:
        min_weight_size = 1
    elif "large" in d_lower:
        min_weight_size = 500 * 1024 * 1024  # 500 MB
    elif "base" in d_lower:
        min_weight_size = 100 * 1024 * 1024  # 100 MB
    else:
        min_weight_size = 50 * 1024 * 1024   # 50 MB

    for wf in weight_files:
        fp = os.path.join(dir_path, wf)
        if os.path.isfile(fp):
            if wf.endswith(".json"):
                if os.path.getsize(fp) > 0:
                    return True
            elif os.path.getsize(fp) >= min_weight_size:
                return True

    return False
