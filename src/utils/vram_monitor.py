"""
VramRealtimeMonitor — Monitor de VRAM em tempo real com atribuição por componente.

Fontes de dados (em ordem de precisão):
  - torch.cuda.mem_get_info()  → total do sistema, identico ao Task Manager
  - torch.cuda.memory_allocated() → tensores PyTorch ativos agora
  - torch.cuda.memory_reserved()  → tudo que o PyTorch reservou (inclui cache)
  - /api/ps (Ollama)              → VRAM por modelo Ollama, exato
  - _pytorch_attribution          → delta de alocação no carregamento de cada modelo
"""

import threading

# Atribuições de VRAM no carregamento dos modelos PyTorch
_pytorch_attribution = {}   # { "Florence-2": 453.0, "YOLO": 320.0 }
_attribution_lock = threading.Lock()


def set_pytorch_attribution(model_name: str, mb: float):
    """Registra o delta de VRAM alocada quando um modelo termina de carregar."""
    with _attribution_lock:
        _pytorch_attribution[model_name] = mb


def clear_pytorch_attribution(model_name: str):
    with _attribution_lock:
        _pytorch_attribution.pop(model_name, None)


def _get_torch_info():
    """
    Retorna:
        system_used_mb  — VRAM total usada no sistema (= Task Manager). Usa mem_get_info.
        allocated_mb    — tensores PyTorch ativos neste processo agora.
        reserved_mb     — memória que o PyTorch reservou do CUDA (inclui cache).
        total_mb        — capacidade total da GPU.
    """
    try:
        import torch
        if not torch.cuda.is_available():
            return 0.0, 0.0, 0.0, 8192.0
        free, total = torch.cuda.mem_get_info(0)
        allocated = torch.cuda.memory_allocated(0)
        reserved  = torch.cuda.memory_reserved(0)
        system_used = total - free
        MB = 1024 ** 2
        return (
            system_used / MB,
            allocated   / MB,
            reserved    / MB,
            total       / MB,
        )
    except Exception:
        return 0.0, 0.0, 0.0, 8192.0


def _get_ollama_breakdown():
    """Retorna {display_name: vram_mb} para modelos ativos no Ollama."""
    try:
        import requests
        from src.config import Config
        base_api = Config.get("ollama_url", "http://127.0.0.1:11435/api").replace("localhost", "127.0.0.1").rstrip("/")
        res = requests.get(f"{base_api}/ps", timeout=0.5)
        if res.status_code == 200:
            result = {}
            for m in res.json().get("models", []):
                vram_mb = m.get("size_vram", 0) / (1024 ** 2)
                if vram_mb < 10:
                    continue
                raw = m.get("name", "").split(":")[0].split("/")[-1]
                # Limpa sufixos verbosos
                display = raw.replace("-instruct", "").replace("-chat", "")[:20]
                result[display] = round(vram_mb, 1)
            return result
    except Exception:
        pass
    return {}


def get_vram_snapshot() -> dict:
    """
    Retorna:
    {
        "total_gpu":    8192.0,   # Capacidade total (MB)
        "system_used":  6600.0,   # Uso real (= Task Manager, MB)
        "used_mb":      6600.0,   # Alias de system_used para compatibilidade
        "allocated_mb": 1200.0,   # Tensores PyTorch ativos
        "breakdown": {
            "Florence-2":  1200.0,
            "Cache GPU":    400.0,
            "qwen2.5":     4800.0,
            "Outros":       200.0,
        }
    }
    """
    system_used, allocated, reserved, total_gpu = _get_torch_info()
    ollama = _get_ollama_breakdown()
    ollama_total = sum(ollama.values())

    breakdown = {}

    # Ollama: atribuição exata via API /api/ps
    breakdown.update(ollama)

    # PyTorch: modelos com delta de carregamento já medido
    with _attribution_lock:
        pytorch_known = dict(_pytorch_attribution)

    pytorch_tracked_total = 0.0
    for name, weight_mb in sorted(pytorch_known.items(), key=lambda x: -x[1]):
        if weight_mb < 10:
            continue
        breakdown[name] = round(weight_mb, 1)
        pytorch_tracked_total += weight_mb
        
    # Se a VRAM alocada caiu abaixo de 80% do esperado, o modelo foi descarregado fora do tracker
    if allocated < pytorch_tracked_total * 0.8:
        with _attribution_lock:
            _pytorch_attribution.clear()
        pytorch_known = {}
        for k in list(breakdown.keys()):
            if k not in ollama:
                del breakdown[k]
        pytorch_tracked_total = 0.0

    # Ativações PyTorch (memória de inferência além dos pesos estáticos)
    activations = max(0.0, allocated - pytorch_tracked_total)
    if activations > 30:
        if pytorch_known:
            top_model = max(pytorch_known, key=pytorch_known.get)
            breakdown[top_model] = round(breakdown.get(top_model, 0) + activations, 1)
        else:
            breakdown["PyTorch"] = round(allocated, 1)

    # Cache alocado pelo PyTorch junto ao driver CUDA mas livre para reuso interno
    cache = max(0.0, reserved - allocated)
    if cache > 50:
        breakdown["Cache GPU"] = round(cache, 1)

    # Consumo restante na GPU (Electron, compositor do Windows, outros apps)
    pytorch_system_footprint = reserved
    other = max(0.0, system_used - pytorch_system_footprint - ollama_total)
    if other > 100:
        breakdown["Outros"] = round(other, 1)

    return {
        "total_gpu":    round(total_gpu,    1),
        "system_used":  round(system_used,  1),
        "used_mb":      round(system_used,  1),   # alias para a UI
        "allocated_mb": round(allocated,    1),
        "breakdown":    breakdown,
    }
