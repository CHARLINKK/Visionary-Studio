# -*- coding: utf-8 -*-
"""
Módulo Image Prefetcher.
Responsável pelo carregamento antecipado de páginas de mangá de forma assíncrona, focando no desempenho da interface.
Ele garante um carregamento Safe RAM-only, impedindo alocações acidentais de VRAM, e otimiza o fluxo do usuário no React, 
antecipando a próxima imagem da fila e reduzindo engasgos perceptíveis.
"""

import os
import threading
from typing import Optional, List
from PIL import Image, ImageFile

# Permite que imagens truncadas ou com chunks web incompletos sejam decodificadas sem crash
ImageFile.LOAD_TRUNCATED_IMAGES = True

class SafeImagePrefetcher:
    """
    Prefetcher assíncrono e seguro na memória RAM para as páginas do mangá.
    
    Garantias da Arquitetura:
    1. Zero VRAM: Decodificação da imagem estritamente forçada para a CPU (RAM), evitando explosão no pool do PyTorch CUDA.
    2. Memória Limitada (Bounded): Preserva na RAM apenas a próxima imagem em cache (aproximadamente 10-15 MB), destruindo a anterior agressivamente.
    3. Cancelamento Imediato: Abandona o background worker via `cancel_event` ou locks para rápida navegação.
    4. Fallback Transparente: Se a thread não concluir a tempo, a interface retrocede naturalmente ao carregamento síncrono padrão.
    """
    def __init__(self, image_paths: List[str], cancel_event: Optional[threading.Event] = None):
        self.image_paths = list(image_paths)
        self.cancel_event = cancel_event or threading.Event()
        self._lock = threading.Lock()
        self._prefetched_path: Optional[str] = None
        self._prefetched_img: Optional[Image.Image] = None
        self._prefetch_error: Optional[Exception] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._target_path: Optional[str] = None
        self._stop_event = threading.Event()

        # Start prefetching the first page immediately if list is not empty
        if self.image_paths:
            self._schedule_prefetch(self.image_paths[0])

    def _schedule_prefetch(self, path: str):
        if self._stop_event.is_set() or self.cancel_event.is_set():
            return
        if not path or not os.path.exists(path):
            return
        with self._lock:
            prev_worker = self._worker_thread
            self._target_path = path
        if prev_worker and prev_worker.is_alive() and prev_worker is not threading.current_thread():
            try:
                prev_worker.join(timeout=0.25)
            except Exception:
                pass
            if prev_worker.is_alive():
                return
        with self._lock:
            if self._stop_event.is_set() or self.cancel_event.is_set():
                return
            self._worker_thread = threading.Thread(
                target=self._worker_load,
                args=(path,),
                daemon=True,
                name=f"SafePrefetch-{os.path.basename(path)}"
            )
            self._worker_thread.start()

    def _worker_load(self, path: str):
        if self._stop_event.is_set() or self.cancel_event.is_set():
            return
        try:
            with Image.open(path) as raw:
                if raw.mode in ('RGBA', 'LA') or (raw.mode == 'P' and 'transparency' in raw.info):
                    rgba = raw.convert('RGBA')
                    background = Image.new('RGB', rgba.size, (255, 255, 255))
                    background.paste(rgba, mask=rgba.split()[3])
                    img = background
                else:
                    img = raw.convert("RGB")
                img.load()  # Force decode pixel buffer into system RAM

            if self._stop_event.is_set() or self.cancel_event.is_set():
                del img
                return

            with self._lock:
                if self._target_path != path or self._stop_event.is_set() or self.cancel_event.is_set():
                    try:
                        img.close()
                    except Exception:
                        pass
                    del img
                    return

                if self._prefetched_img is not None:
                    try:
                        self._prefetched_img.close()
                    except Exception:
                        pass
                    del self._prefetched_img

                self._prefetched_img = img
                self._prefetched_path = path
                self._prefetch_error = None
        except Exception as e:
            with self._lock:
                if self._target_path == path:
                    self._prefetch_error = e

    def get_image(self, path: str, next_path: Optional[str] = None) -> Image.Image:
        """
        Returns the decoded image from RAM.
        If next_path is supplied, immediately triggers background prefetch of next_path.
        """
        with self._lock:
            worker = self._worker_thread if self._target_path == path else None
        if worker and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=3.0)

        img = None
        with self._lock:
            if self._prefetched_path == path and self._prefetched_img is not None:
                img = self._prefetched_img
                self._prefetched_img = None
                self._prefetched_path = None
                self._prefetch_error = None

        if next_path and not self._stop_event.is_set() and not self.cancel_event.is_set():
            self._schedule_prefetch(next_path)

        if img is not None:
            return img

        with Image.open(path) as raw:
            if raw.mode in ('RGBA', 'LA') or (raw.mode == 'P' and 'transparency' in raw.info):
                rgba = raw.convert('RGBA')
                background = Image.new('RGB', rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.split()[3])
                loaded = background
            else:
                loaded = raw.convert("RGB")
            loaded.load()
            return loaded

    def stop(self):
        """Stops worker and frees RAM immediately."""
        self._stop_event.set()
        with self._lock:
            worker = self._worker_thread
            if self._prefetched_img is not None:
                try:
                    self._prefetched_img.close()
                except Exception:
                    pass
                del self._prefetched_img
                self._prefetched_img = None
            self._prefetched_path = None
            self._prefetch_error = None

        if worker and worker.is_alive() and worker is not threading.current_thread():
            try:
                worker.join(timeout=0.2)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
