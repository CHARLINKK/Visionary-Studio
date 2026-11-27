"""
Leitor OCR baseado em Florence-2 para os recortes de balões do pipeline.

Responsável por localizar os pesos em disco (priorizando Florence-2-large com fallback
para base e snapshot do HuggingFace), carregar em FP16 na GPU (ou CPU se faltar VRAM)
e extrair o texto preservando regiões via `<OCR_WITH_REGION>`. A persistência em
`_map.json` fica a cargo do `ocr_runner` / `PageStore`, não desta classe.
"""

import os
import sys
import json
import contextlib
from PIL import Image

try:
    import torch
    if not hasattr(torch, "cuda"):
        torch = None
        for _k in list(sys.modules.keys()):
            if _k == "torch" or _k.startswith("torch."):
                sys.modules.pop(_k, None)
except Exception:
    torch = None

try:
    from transformers import AutoProcessor, AutoModelForCausalLM
    if torch is None:
        class _AutoModelFallback:
            @classmethod
            def from_pretrained(cls, *args, **kwargs):
                raise RuntimeError("PyTorch não instalado.")
        AutoModelForCausalLM = _AutoModelFallback
except Exception:
    class _AutoFallback:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            raise RuntimeError("Transformers/PyTorch não instalado.")
    AutoProcessor = _AutoFallback
    AutoModelForCausalLM = _AutoFallback

if torch is None:
    class _TorchFallback:
        float16 = "float16"
        float32 = "float32"

        class cuda:
            @staticmethod
            def is_available():
                return False

        @staticmethod
        def no_grad():
            return contextlib.nullcontext()

        @staticmethod
        def inference_mode():
            return contextlib.nullcontext()

    torch = _TorchFallback()
from src.utils.gpu_utils import cleanup_gpu_memory

from src.config import get_app_data_dir
from src.utils.hf_snapshot_resolver import (
    _resolve_hf_snapshot_path,
    resolve_hf_snapshot_path,
    is_valid_florence_dir,
)

MODEL_ID = "microsoft/Florence-2-large"
CACHE_DIR = os.path.join(get_app_data_dir(), "models")
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


@contextlib.contextmanager
def _suppress_flash_attn_check():
    """
    Filtra temporariamente apenas a verificação de 'flash_attn' no dynamic_module_utils
    do HuggingFace Transformers (que exige compilador C++ no Windows), restaurando a
    função original imediatamente ao sair do bloco para evitar monkeypatch global.
    """
    import transformers.dynamic_module_utils as dmu
    orig_check_imports = getattr(dmu, "check_imports", None)
    orig_get_imports = getattr(dmu, "get_imports", None)

    def _filtered_get_imports(filename):
        imports = orig_get_imports(filename) if callable(orig_get_imports) else []
        return [imp for imp in imports if imp != "flash_attn"]

    def _filtered_check_imports(filename):
        if callable(orig_check_imports):
            try:
                return orig_check_imports(filename)
            except ImportError as exc:
                if "flash_attn" in str(exc):
                    return _filtered_get_imports(filename)
                raise
        return []

    if callable(orig_get_imports):
        dmu.get_imports = _filtered_get_imports
    if callable(orig_check_imports):
        dmu.check_imports = _filtered_check_imports
    try:
        yield
    finally:
        if callable(orig_get_imports):
            dmu.get_imports = orig_get_imports
        if callable(orig_check_imports):
            dmu.check_imports = orig_check_imports


class FlorenceReader:
    def __init__(self, model_id=MODEL_ID):
        self.model_id = model_id
        self.device = "cuda" if (torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available()) else "cpu"
        self.model = None
        self.processor = None

    def load(self):
        cache_dir = os.path.join(get_app_data_dir(), "models")
        os.makedirs(cache_dir, exist_ok=True)

        # Procura o modelo na pasta do usuário e na pasta do projeto antes de tentar rede,
        # pois o Florence-2 no Windows falha com OSError [Errno 22] se o caminho tiver snapshots inválidos.
        from src.config import is_test_environment
        is_test_env = is_test_environment()
        candidate_cache_dirs = [cache_dir]
        if not is_test_env:
            proj_models = os.path.join(_PROJECT_ROOT, "models")
            if proj_models not in candidate_cache_dirs and os.path.isdir(proj_models):
                candidate_cache_dirs.append(proj_models)
            if os.environ.get("VISIONARY_PROJECT_ROOT"):
                p_models = os.path.join(os.environ["VISIONARY_PROJECT_ROOT"], "models")
                if p_models not in candidate_cache_dirs and os.path.isdir(p_models):
                    candidate_cache_dirs.append(p_models)

        large_dir = None
        base_dir = None
        for cd in candidate_cache_dirs:
            ld = os.path.join(cd, "florence-2-large")
            bd = os.path.join(cd, "florence-2-base")
            if not large_dir and is_valid_florence_dir(ld):
                large_dir = ld
            if not base_dir and is_valid_florence_dir(bd):
                base_dir = bd

        # Fallback para snapshot HuggingFace se não encontrado em diretório simples
        if not is_test_env:
            if not large_dir:
                for cd in candidate_cache_dirs:
                    snap = _resolve_hf_snapshot_path(cd, "microsoft/Florence-2-large")
                    if snap and is_valid_florence_dir(snap):
                        large_dir = snap
                        break
            if not base_dir:
                for cd in candidate_cache_dirs:
                    snap = _resolve_hf_snapshot_path(cd, "microsoft/Florence-2-base")
                    if snap and is_valid_florence_dir(snap):
                        base_dir = snap
                        break

        has_large = bool(large_dir)
        has_base = bool(base_dir)

        if "large" in self.model_id.lower():
            if has_large:
                local_dir = large_dir
            elif has_base and self.model_id == MODEL_ID:
                self.model_id = "microsoft/Florence-2-base"
                local_dir = base_dir
            else:
                local_dir = large_dir or os.path.join(cache_dir, "florence-2-large")
        else:
            local_dir = base_dir if has_base else (large_dir if has_large else os.path.join(cache_dir, "florence-2-base"))

        print(f" [OCR] Carregando {self.model_id} na {self.device}...")

        # Se os arquivos estiverem íntegros na raiz local ou snapshot (baixados via model_manager)
        if is_valid_florence_dir(local_dir):
            load_path = local_dir
            load_kwargs_base = {
                "trust_remote_code": True,
                "local_files_only": True,
            }
        else:
            # Fallback (download automático se rodar via CLI sem model_manager)
            load_path = self.model_id
            load_kwargs_base = {
                "trust_remote_code": True,
                "cache_dir": cache_dir,
            }

        if self.device == "cuda":
            from src.utils.vram_arbiter import vram_arbiter
            required_mb = 2600 if "large" in self.model_id.lower() else 1200
            vram_arbiter.ensure_headroom_mb(required_mb)

        with _suppress_flash_attn_check():
            try:
                from src.utils.gpu_utils import ModelLoadTracker
                tracker_mb = 2600 if "large" in self.model_id.lower() else 1200
                with ModelLoadTracker("Florence-2", total_size_mb=tracker_mb):
                    self.processor = AutoProcessor.from_pretrained(load_path, **load_kwargs_base)
                    self.model = AutoModelForCausalLM.from_pretrained(
                        load_path,
                        # Força atenção 'eager' porque SDPA/flash_attn costumam quebrar em GPUs Turing/Windows
                        attn_implementation="eager",
                        torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                        **load_kwargs_base,
                    ).to(self.device)
                    if self.device == "cuda":
                        # Crops de balões têm resoluções muito variadas; cudnn.benchmark só gera pico de VRAM
                        torch.backends.cudnn.benchmark = False
            except Exception as e:
                is_cuda_err = (
                    self.device == "cuda" and (
                        "no kernel image" in str(e)
                        or "cuda error" in str(e).lower()
                        or "out of memory" in str(e).lower()
                        or "outofmemoryerror" in type(e).__name__.lower()
                    )
                )
                if is_cuda_err:
                    print(" [OCR] AVISO: VRAM insuficiente ou erro de GPU no Florence-2. Acionando fallback gracioso para CPU...")
                    cleanup_gpu_memory(force_ipc=True)
                    self.device = "cpu"
                print(f" [OCR] AVISO: Fallback no carregamento do modelo ({type(e).__name__}: {e}) na {self.device}...")
                from src.utils.gpu_utils import ModelLoadTracker
                with ModelLoadTracker("Florence-2 (Fallback)", total_size_mb=1200):
                    fallback_path = load_path if is_valid_florence_dir(load_path) else self.model_id
                    fallback_kwargs = load_kwargs_base.copy()
                    if not is_valid_florence_dir(load_path):
                        fallback_kwargs["cache_dir"] = CACHE_DIR
                    try:
                        self.processor = AutoProcessor.from_pretrained(fallback_path, **fallback_kwargs)
                        self.model = AutoModelForCausalLM.from_pretrained(
                            fallback_path,
                            attn_implementation="eager",
                            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                            **fallback_kwargs,
                        ).to(self.device)
                    except Exception as e2:
                        if self.device == "cuda":
                            print(f" [OCR] AVISO: Falha secundária na GPU ({e2}). Forçando execução em CPU...")
                            cleanup_gpu_memory(force_ipc=True)
                            self.device = "cpu"
                            self.processor = AutoProcessor.from_pretrained(fallback_path, **fallback_kwargs)
                            self.model = AutoModelForCausalLM.from_pretrained(
                                fallback_path,
                                attn_implementation="eager",
                                torch_dtype=torch.float32,
                                **fallback_kwargs,
                            ).to(self.device)
                        else:
                            raise e2
                    if self.device == "cuda":
                        torch.backends.cudnn.benchmark = False
                        try:
                            dummy_img = Image.new("RGB", (64, 64), color="white")
                            dummy_inp = self.processor(text=["<OCR>"], images=[dummy_img], return_tensors="pt").to(self.device)
                            dummy_inp["pixel_values"] = dummy_inp["pixel_values"].to(torch.float16)
                            with torch.inference_mode():
                                self.model.generate(input_ids=dummy_inp["input_ids"], pixel_values=dummy_inp["pixel_values"], max_new_tokens=4, num_beams=1)
                            del dummy_inp
                        except Exception:
                            pass

        print(" [OCR] Modelo carregado e pronto para uso.")

    def unload(self):
        if self.model is not None or self.processor is not None:
            del self.model
            del self.processor
            self.model = None
            self.processor = None
            cleanup_gpu_memory()
            print(" [OCR] VRAM liberada.")

    def read_text(self, image: Image.Image) -> dict:
        """Executa `<OCR_WITH_REGION>` em um único recorte, retornando texto corrido e polígonos das linhas."""
        task_prompt = "<OCR_WITH_REGION>"
        inputs = None
        generated_ids = None
        try:
            inputs = self.processor(text=task_prompt, images=image, return_tensors="pt").to(self.device)
            if self.device == "cuda":
                inputs["pixel_values"] = inputs["pixel_values"].to(torch.float16)

            with torch.inference_mode():
                generated_ids = self.model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=512,
                    do_sample=False,
                    num_beams=1,
                )

            generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed_answer = self.processor.post_process_generation(generated_text, task=task_prompt, image_size=(image.width, image.height))
            result_dict = parsed_answer.get(task_prompt, {})
            labels = result_dict.get("labels", [])
            quad_boxes = result_dict.get("quad_boxes", [])

            regions = []
            for label, quad in zip(labels, quad_boxes):
                clean_label = label.replace("</s>", "").replace("\n", " ").replace("  ", " ").strip()
                if clean_label:
                    regions.append({"text": clean_label, "quad": quad})

            spaced_text = " ".join([r["text"] for r in regions])
            spaced_text = spaced_text.replace("- ", "").strip()

            return {"text": spaced_text, "regions": regions}
        finally:
            del inputs, generated_ids

    def read_text_batch(self, images: list[Image.Image]) -> list[dict]:
        """Executa `<OCR_WITH_REGION>` em lote em uma única passada na GPU/CPU."""
        if not images:
            return []
            
        task_prompt = "<OCR_WITH_REGION>"
        task_prompts = [task_prompt] * len(images)
        inputs = None
        generated_ids = None
        generated_texts = []
        
        try:
            inputs = self.processor(text=task_prompts, images=images, return_tensors="pt", padding=True).to(self.device)
            if self.device == "cuda":
                inputs["pixel_values"] = inputs["pixel_values"].to(torch.float16)

            with torch.inference_mode():
                generated_ids = self.model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=512,
                    do_sample=False,
                    num_beams=1,
                )
            
            generated_texts = self.processor.batch_decode(generated_ids, skip_special_tokens=False)
        finally:
            del inputs, generated_ids
        
        results = []
        for i, text in enumerate(generated_texts):
            img = images[i]
            parsed_answer = self.processor.post_process_generation(text, task=task_prompt, image_size=(img.width, img.height))
            result_dict = parsed_answer.get(task_prompt, {})
            labels = result_dict.get("labels", [])
            quad_boxes = result_dict.get("quad_boxes", [])
            
            regions = []
            for label, quad in zip(labels, quad_boxes):
                clean_label = label.replace("</s>", "").replace("\n", " ").replace("  ", " ").strip()
                if clean_label:
                    regions.append({"text": clean_label, "quad": quad})
            
            spaced_text = " ".join([r["text"] for r in regions])
            spaced_text = spaced_text.replace("- ", "").strip()
            
            results.append({"text": spaced_text, "regions": regions})
            
        return results

    def validate_crops_batch(self, images: list[Image.Image]) -> list[str]:
        """Passada leve com `<OCR>` (32 tokens) apenas para checar se existe texto legível nos recortes."""
        if not images:
            return []
            
        task_prompt = "<OCR>"
        task_prompts = [task_prompt] * len(images)
        inputs = None
        generated_ids = None
        generated_texts = []
        
        try:
            inputs = self.processor(text=task_prompts, images=images, return_tensors="pt", padding=True).to(self.device)
            if self.device == "cuda":
                inputs["pixel_values"] = inputs["pixel_values"].to(torch.float16)

            with torch.inference_mode():
                generated_ids = self.model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=32,
                    do_sample=False,
                    num_beams=1,
                )
            
            generated_texts = self.processor.batch_decode(generated_ids, skip_special_tokens=False)
        finally:
            del inputs, generated_ids
        
        results = []
        for i, text in enumerate(generated_texts):
            img = images[i]
            parsed_answer = self.processor.post_process_generation(text, task=task_prompt, image_size=(img.width, img.height))
            raw_text = parsed_answer.get(task_prompt, "")
            results.append(raw_text.replace("\n", " ").strip())
            
        return results

    def generate_image_caption(self, image: Image.Image) -> str:
        """Run Florence-2 <MORE_DETAILED_CAPTION> on the entire image to get visual context."""
        task_prompt = "<MORE_DETAILED_CAPTION>"
        inputs = None
        generated_ids = None
        generated_text = ""
        
        try:
            inputs = self.processor(text=task_prompt, images=image, return_tensors="pt").to(self.device)
            if self.device == "cuda":
                inputs["pixel_values"] = inputs["pixel_values"].to(torch.float16)

            with torch.inference_mode():
                generated_ids = self.model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=1024,
                    early_stopping=False,
                    do_sample=False,
                    num_beams=1,
                )
            
            generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        finally:
            del inputs, generated_ids
        
        parsed_answer = self.processor.post_process_generation(
            generated_text, 
            task=task_prompt, 
            image_size=(image.width, image.height)
        )
        
        return parsed_answer.get(task_prompt, "")

    def read_full_page(self, image: Image.Image) -> list[dict]:
        """Run Florence-2 OCR_WITH_REGION on the entire page to find all texts and their bounding boxes."""
        task_prompt = "<OCR_WITH_REGION>"
        inputs = None
        generated_ids = None
        generated_text = ""
        
        try:
            inputs = self.processor(text=task_prompt, images=image, return_tensors="pt").to(self.device)
            if self.device == "cuda":
                inputs["pixel_values"] = inputs["pixel_values"].to(torch.float16)

            with torch.inference_mode():
                generated_ids = self.model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=1024,
                    early_stopping=False,
                    do_sample=False,
                    num_beams=1,
                )
            
            generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        finally:
            del inputs, generated_ids
        
        parsed_answer = self.processor.post_process_generation(
            generated_text, 
            task=task_prompt, 
            image_size=(image.width, image.height)
        )
        
        result_dict = parsed_answer.get(task_prompt, {})
        quad_boxes = result_dict.get("quad_boxes", [])
        labels = result_dict.get("labels", [])
        
        detected_texts = []
        for i in range(len(quad_boxes)):
            quad = quad_boxes[i]
            text = labels[i].replace("\n", " ").replace("  ", " ").strip()
            
            if not text:
                continue
                
            x_coords = [quad[0], quad[2], quad[4], quad[6]]
            y_coords = [quad[1], quad[3], quad[5], quad[7]]
            x1, y1 = int(min(x_coords)), int(min(y_coords))
            x2, y2 = int(max(x_coords)), int(max(y_coords))
            
            detected_texts.append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "text": text,
                "confidence": 1.0,
                "label": "florence_text"
            })
            
        return detected_texts

    def process_map(self, map_path: str, crops_dir: str) -> list[dict]:
        """Process all bubbles defined in the map file in batches."""
        from src.domain.page_store import PageStore
        from src.utils.file_resilience import resilient_read_json
        raw_map = resilient_read_json(map_path)
        bubbles = PageStore.extract_boxes(raw_map) if raw_map is not None else []
            
        print(f" [OCR] Processando {len(bubbles)} balões de {map_path}...")
        base_name = os.path.basename(map_path).replace("_map.json", "")
        
        valid_bubbles = []
        images = []
        
        for b in bubbles:
            crop_path = os.path.join(crops_dir, f"{base_name}_balao_{b['id']:03d}.jpg")
            if not os.path.exists(crop_path):
                print(f" [OCR] Aviso: recorte não encontrado -> {crop_path}")
                continue
                
            img_raw = Image.open(crop_path)
            img = img_raw.convert("RGB")
            images.append(img)
            valid_bubbles.append((b, img_raw))
            
        if not images:
            return bubbles

        batch_size = 16
        for i in range(0, len(images), batch_size):
            batch_imgs = images[i:i + batch_size]
            batch_results = self.read_text_batch(batch_imgs)
            
            for j, res in enumerate(batch_results):
                b, img_raw = valid_bubbles[i + j]
                text = res["text"]
                b["text"] = text
                print(f" #{b['id']:03d} -> {text}")
                img_raw.close()
            
        return bubbles


def _cli_main():
    if len(sys.argv) < 2:
        print("Usage: python src/step2_ocr_extractor.py <path_to_map_json>")
        sys.exit(1)

    map_file = sys.argv[1]
    base_dir = os.path.dirname(map_file)
    crops_folder = os.path.join(base_dir, "crops")
    
    if not os.path.exists(map_file):
        print(f"Erro: {map_file} não encontrado.")
        sys.exit(1)

    reader = FlorenceReader()
    reader.load()
    updated_bubbles = reader.process_map(map_file, crops_folder)
    reader.unload()
    
    out_file = map_file
    from src.utils.json_utils import dump_compact_map
    from src.domain.page_store import PageStore
    PageStore.save_boxes(out_file, updated_bubbles, target_map_path=out_file, dump_fn=dump_compact_map)
        
    print(f"\nConcluído! Resultados do OCR salvos em {out_file}")
