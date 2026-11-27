import gc
import os

def setup_cuda_env():
    """
    Configura alocador PyTorch para evitar fragmentação de memória em GPUs com 6-8GB de VRAM.
    Deve ser chamado no início da execução da aplicação antes de carregar modelos CUDA.
    No Windows, expandable_segments não é suportado pelo backend PyTorch CUDA e emite
    UserWarning contínuo; usamos max_split_size_mb:128 para mitigar fragmentação física.
    """
    import sys
    if sys.platform == "win32":
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:128")
    else:
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

def unload_ollama_models(model_name: str = None):
    """
    Descarrega modelo(s) do Ollama da VRAM enviando keep_alive: 0.
    Verifica tanto a porta configurada (ex: 11435) quanto a porta padrão do Ollama (11434).
    """
    try:
        import requests
        from src.config import Config
        cfg_url = Config.get("ollama_url", "http://127.0.0.1:11435/api")
        candidates = [cfg_url.replace("/api", "").rstrip("/"), "http://127.0.0.1:11434"]
        
        seen = set()
        unique_candidates = [c for c in candidates if not (c in seen or seen.add(c))]

        for base_url in unique_candidates:
            try:
                if model_name:
                    requests.post(
                        f"{base_url}/api/generate",
                        json={"model": model_name, "keep_alive": 0},
                        timeout=1.5
                    )
                else:
                    resp = requests.get(f"{base_url}/api/ps", timeout=0.8)
                    if resp.status_code == 200:
                        models = resp.json().get('models', [])
                        for m in models:
                            m_name = m.get('name')
                            if m_name:
                                requests.post(
                                    f"{base_url}/api/generate",
                                    json={"model": m_name, "keep_alive": 0},
                                    timeout=1.0
                                )
            except Exception:
                pass
    except Exception:
        pass

def cleanup_gpu_memory(force_ipc: bool = True, unload_ollama: bool = False):
    """
    Força coleta de lixo do Python e esvazia o pool de cache do PyTorch CUDA.
    Se unload_ollama=True, descarrega também os modelos LLM residentes na VRAM do Ollama.
    Executa de forma segura mesmo em ambientes sem CUDA / CPU-only.
    """
    gc.collect()
    import sys
    if "torch" in sys.modules and sys.modules["torch"] is not None:
        try:
            torch = sys.modules["torch"]
            if hasattr(torch, "cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()
                if force_ipc:
                    try:
                        torch.cuda.ipc_collect()
                    except Exception:
                        pass
        except Exception:
            pass

    if unload_ollama:
        unload_ollama_models()

import threading
import time
import requests

class ModelLoadTracker:
    """
    Context manager to track and print VRAM loading progress for AI models.
    Supports PyTorch models via torch.cuda and Ollama models via its API.
    """
    def __init__(self, model_name: str, total_size_mb: int = None, poll_interval: float = 0.1, is_ollama: bool = False, progress_emitter=None):
        self.model_name = model_name
        self.total_size_mb = total_size_mb
        self.poll_interval = poll_interval
        self.is_ollama = is_ollama
        self.progress_emitter = progress_emitter
        self._emitter = progress_emitter
        self.thread = None

    def _safe_print(self, text, flush=True):
        try:
            print(text, flush=flush)
        except UnicodeEncodeError:
            print(text.encode('ascii', 'replace').decode('ascii'), flush=flush)

    def _emit_vram_progress(self, loaded_mb: float, total_mb: float, done: bool = False):
        if self._emitter is not None:
            if done:
                vstate = {"model": self.model_name, "loaded": 1, "total": 1, "progress": 100, "done": True}
            else:
                pct = min(100, max(0, int((loaded_mb / total_mb) * 100))) if total_mb > 0 else 0
                vstate = {
                    "model": self.model_name,
                    "loaded": round(float(loaded_mb), 1),
                    "total": round(float(total_mb), 1),
                    "progress": pct,
                    "done": False,
                }
            self._emitter.emit_vram_state(vstate)
            return

        if done:
            self._safe_print(f"[VRAM_PROGRESS:{self.model_name}:DONE/DONEMB]")
        elif loaded_mb == 0:
            self._safe_print(f"[VRAM_PROGRESS:{self.model_name}:0/{total_mb:.1f}MB]")
        else:
            self._safe_print(f"[VRAM_PROGRESS:{self.model_name}:{loaded_mb:.1f}/{total_mb:.1f}MB]")

    def _poll_pytorch_vram(self):
        try:
            import torch
            if not hasattr(torch, "cuda") or not torch.cuda.is_available():
                return
        except ImportError:
            return
            
        initial_vram = torch.cuda.memory_allocated() / (1024 * 1024)
        last_mb = 0
        start_time = time.time()
        last_print_time = start_time
        
        while self.running:
            current_vram = torch.cuda.memory_allocated() / (1024 * 1024)
            loaded_mb = max(0, current_vram - initial_vram)
            now = time.time()
            
            # Atualiza UI se subir 20MB OU a cada 0.5s
            if loaded_mb > last_mb + 20 or (now - last_print_time > 0.5):
                if loaded_mb > last_mb + 20:
                    last_mb = loaded_mb
                last_print_time = now
                
                total = self.total_size_mb if self.total_size_mb and self.total_size_mb > 0 else loaded_mb + 100
                self._emit_vram_progress(loaded_mb, total, done=False)
                
            time.sleep(self.poll_interval)
            
    def _poll_ollama_vram(self):
        last_mb = 0
        start_time = time.time()
        last_print_time = start_time
        
        from src.config import Config
        ollama_url = Config.get("ollama_url", "http://127.0.0.1:11435/api")
        base_url = ollama_url.replace("/api", "")
        ps_url = f"{base_url}/api/ps"
        
        while self.running:
            now = time.time()
            try:
                res = requests.get(ps_url, timeout=0.2)
                if res.status_code == 200:
                    data = res.json()
                    model_found = False
                    for model in data.get("models", []):
                        if self.model_name.lower() in model.get("name", "").lower():
                            model_found = True
                            loaded_mb = model.get("size_vram", 0) / (1024 * 1024)
                            if loaded_mb > last_mb + 50 or (now - last_print_time > 0.5):
                                if loaded_mb > last_mb + 50:
                                    last_mb = loaded_mb
                                last_print_time = now
                                total = self.total_size_mb or (model.get("size", 0) / (1024 * 1024))
                                total = total if total > 0 else loaded_mb + 100
                                self._emit_vram_progress(loaded_mb, total, done=False)
                                    
                    if not model_found and (now - last_print_time > 0.5):
                        last_print_time = now
                        total = self.total_size_mb or 100
                        self._emit_vram_progress(0, total, done=False)
            except Exception:
                pass
                
            time.sleep(self.poll_interval)
            
    def __enter__(self):
        self.running = True
        self._already_loaded = False
        self._start_time = time.time()
        if self._emitter is None:
            try:
                from src.utils.pipeline_emitter import get_current_thread_emitter
                self._emitter = get_current_thread_emitter()
            except Exception:
                self._emitter = None
        # Snapshot de VRAM antes do carregamento para calcular atribuição depois
        self._vram_before_mb = 0.0
        if not self.is_ollama:
            try:
                import torch
                if torch.cuda.is_available():
                    self._vram_before_mb = torch.cuda.memory_allocated() / (1024 ** 2)
            except Exception:
                pass
        else:
            try:
                from src.config import Config
                ollama_url = Config.get("ollama_url", "http://127.0.0.1:11435/api")
                base_url = ollama_url.replace("/api", "")
                ps_url = f"{base_url}/api/ps"
                res = requests.get(ps_url, timeout=0.2)
                if res.status_code == 200:
                    data = res.json()
                    for model in data.get("models", []):
                        if self.model_name.lower() in model.get("name", "").lower() and model.get("size_vram", 0) > 0:
                            self._already_loaded = True
                            break
            except Exception:
                pass

        if not self._already_loaded:
            self._safe_print(f"[SISTEMA] Iniciando ativação do modelo {self.model_name} na VRAM...")
            target = self._poll_ollama_vram if self.is_ollama else self._poll_pytorch_vram
            self.thread = threading.Thread(target=target, daemon=True)
            self.thread.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if getattr(self, "_already_loaded", False):
            return
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        
        # Registra atribuição de VRAM para este modelo no monitor global
        if not self.is_ollama:
            try:
                import torch
                from src.utils.vram_monitor import set_pytorch_attribution
                if torch.cuda.is_available():
                    vram_after = torch.cuda.memory_allocated() / (1024 ** 2)
                    attributed_mb = max(0.0, vram_after - self._vram_before_mb)
                    if attributed_mb > 10:
                        set_pytorch_attribution(self.model_name, attributed_mb)
            except Exception:
                pass
        
        # Notifica a UI que o carregamento terminou
        duration = time.time() - self._start_time if getattr(self, "_start_time", 0.0) else 0.0
        dur_str = f" ({duration:.1f}s)" if duration > 1.0 else ""
        self._emit_vram_progress(1, 1, done=True)
        self._safe_print(f"[SISTEMA] Modelo {self.model_name} ativado e pronto para inferência{dur_str}.")
