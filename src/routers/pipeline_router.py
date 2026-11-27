"""
Router de Tradução em Lote e Presets: Endpoints para disparo de processamento de mangás.
"""

import os
import sys
from fastapi import APIRouter, HTTPException, BackgroundTasks, Body
from src.config import Config
from src.utils.websocket_manager import broadcast_log_sync

pipeline_router = APIRouter()

PRESETS = {
    "neutral": {"name": "Neutro / Equilibrado", "desc": "Tradução equilibrada e natural, sem regionalismos excessivos."},
    "boxing": {"name": "Luta / Combate (Boxing)", "desc": "Gírias pesadas de confronto, agressividade e impacto físico."},
    "shonen": {"name": "Shonen (Ação)", "desc": "Gírias jovens, intensidade, gritos de golpe."},
    "seinen": {"name": "Seinen (Sério)", "desc": "Tom maduro, dramático e profundo."},
    "comedy": {"name": "Comédia / Meme", "desc": "Livre, cômico e altamente focado no humor PT-BR."}
}


@pipeline_router.get("/api/presets")
def get_presets():
    """Retorna os perfis de personalidade e instruções de tradução disponíveis."""
    return PRESETS


@pipeline_router.post("/api/pipeline/run")
def trigger_pipeline(background_tasks: BackgroundTasks, payload: dict = Body(...)):
    """Dispara a execução completa do pipeline de lote em segundo plano."""
    input_dir = payload.get("input_dir")
    base_project_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    output_dir = payload.get("output_dir", os.path.join(base_project_dir, "output_processed"))
    preset = payload.get("preset", "neutral")
    model = payload.get("model") or Config.get("translation_model") or "amadeus:7b"
    
    if not input_dir or not os.path.exists(input_dir) or not os.path.isdir(input_dir):
        raise HTTPException(status_code=400, detail="Input directory does not exist or is not a directory")
    
    output_dir = os.path.abspath(os.path.normpath(output_dir))
        
    def _run_pipeline():
        from src.run_batch import _pipeline_lock, run_batch_pipeline as _default_run_batch
        server_mod = sys.modules.get("src.server")
        broadcast_fn = getattr(server_mod, "broadcast_log_sync", broadcast_log_sync) if server_mod is not None else broadcast_log_sync
        batch_fn = getattr(server_mod, "run_batch_pipeline", _default_run_batch) if server_mod is not None else _default_run_batch

        with _pipeline_lock:
            broadcast_fn("pipeline_status", f"Iniciando pipeline no diretório: {input_dir} (Preset: {preset})...", progress=5.0)
            try:
                batch_fn(input_dir, output_dir, preset=preset, model=model)
                broadcast_fn("pipeline_status", "Tradução concluída com sucesso! Todos os mapas e textos gerados.", progress=100.0)
            except Exception as e:
                broadcast_fn("pipeline_error", f"Erro durante a execução: {str(e)}", progress=0.0)

    background_tasks.add_task(_run_pipeline)
    return {"success": True, "message": "Pipeline iniciado em plano de fundo"}
