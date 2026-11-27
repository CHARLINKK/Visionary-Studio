import os
import re
import base64
import threading
from collections import OrderedDict

from src.utils.path_sandbox import ImageReadDenied, authorize_image_read
from src.utils.file_resilience import retry_on_file_lock, resilient_read_bytes


class ImageService:
    def __init__(self, workspace_context=None, api_bridge=None, default_path="", max_cache_entries=128, max_full_cache_entries=4):
        from src.utils.workspace_context import WorkspaceContext
        self.context, self.api = WorkspaceContext.resolve_service_binding(
            workspace_context, api_bridge, default_path
        )

        self.default_path = default_path
        self._thumbnail_cache = OrderedDict()
        self._full_cache = OrderedDict()
        self._cache_lock = threading.RLock()
        self._max_cache_entries = max_cache_entries
        self._max_full_cache_entries = max_full_cache_entries
        self._prefetcher = None
        self._prefetched_mtimes = {}
        self._full_prefetch_thread = None
        self._full_prefetch_target = None

    def clear_cache(self):
        """Limpa o cache de thumbnails e imagens completas em memória RAM."""
        with self._cache_lock:
            self._thumbnail_cache.clear()
            self._full_cache.clear()
            self._prefetched_mtimes.clear()
            self._full_prefetch_target = None
            if self._prefetcher is not None:
                try:
                    self._prefetcher.stop()
                except Exception:
                    pass
                self._prefetcher = None

    def _resolve_target(self, file_path):
        if not file_path or not isinstance(file_path, str):
            return ""
        target = file_path
        if not os.path.isabs(target):
            base = self.context.current_path if self.context else (getattr(self.api, "current_path", "") if self.api else self.default_path)
            if base and base != "MEU COMPUTADOR":
                target = os.path.join(base, file_path)
        return os.path.normpath(target)

    def _authorized_target(self, file_path):
        """
        Aplica a mesma política de leitura do endpoint `/api/image` (extensão raster + raiz autorizada,
        sobre o caminho resolvido). Sem isto, o RPC base64 seria uma segunda porta de leitura de
        qualquer imagem do disco.

        Retorna `(caminho_resolvido, None)` ou `(None, resposta_de_erro)`. A existência só é checada
        depois da autorização e a mensagem fora do sandbox não inclui o caminho, para não revelar
        quais arquivos existem.
        """
        try:
            real_path = authorize_image_read(self._resolve_target(file_path))
        except ImageReadDenied as denied:
            return None, {"success": False, "error": str(denied)}
        if not os.path.isfile(real_path):
            return None, {"success": False, "error": f"Arquivo de imagem não encontrado: {real_path}"}
        return real_path, None

    def get_thumbnail(self, file_path):
        """
        Gera miniatura base64 com micro-retries defensivos contra file-locking no Windows.
        Alias canônico para get_image_base64.
        """
        return self.get_image_base64(file_path)

    def _consume_prefetched_pil(self, target: str, mtime):
        """Retorna uma cópia da imagem PIL pré-carregada em RAM se disponível e com mtime válido."""
        with self._cache_lock:
            prefetcher = self._prefetcher
            expected_mtime = self._prefetched_mtimes.get(target)
        if prefetcher is None or expected_mtime != mtime:
            return None
        with prefetcher._lock:
            has_target = (prefetcher._target_path == target or prefetcher._prefetched_path == target)
        if not has_target:
            return None
        try:
            img = prefetcher.get_image(target)
            if img is not None:
                return img.copy()
        except Exception:
            return None
        return None

    def get_image_base64(self, file_path):
        try:
            target, error = self._authorized_target(file_path)
            if error:
                return error

            # Verificação de cache em memória com micro-retry defensivo em os.path.getmtime
            mtime = None
            try:
                mtime = retry_on_file_lock(lambda: os.path.getmtime(target), max_attempts=3)
                cache_key = (target, mtime)
                cached_thumb = None
                with self._cache_lock:
                    if cache_key in self._thumbnail_cache:
                        self._thumbnail_cache.move_to_end(cache_key)
                        cached_thumb = self._thumbnail_cache[cache_key]
                if cached_thumb is not None:
                    self._trigger_adjacent_prefetch(target)
                    return {
                        "success": True,
                        "data_url": cached_thumb
                    }
            except Exception:
                cache_key = None

            ext = os.path.splitext(target)[1].lower()
            try:
                from PIL import Image
                import io

                def _load_and_resize():
                    prefetched = self._consume_prefetched_pil(target, mtime) if mtime is not None else None
                    if prefetched is not None:
                        img = prefetched
                    else:
                        with Image.open(target) as img_raw:
                            img = img_raw.copy()
                            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                                rgba = img.convert('RGBA')
                                background = Image.new('RGB', rgba.size, (255, 255, 255))
                                background.paste(rgba, mask=rgba.split()[3])
                                img = background
                            elif img.mode != 'RGB':
                                img = img.convert('RGB')
                    img.thumbnail((720, 720), Image.Resampling.BILINEAR)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=85, optimize=False)
                    return base64.b64encode(buffer.getvalue()).decode('utf-8')

                b64_data = retry_on_file_lock(_load_and_resize, max_attempts=3)
                data_url = f"data:image/jpeg;base64,{b64_data}"

                if cache_key is not None:
                    with self._cache_lock:
                        self._thumbnail_cache[cache_key] = data_url
                        if len(self._thumbnail_cache) > self._max_cache_entries:
                            self._thumbnail_cache.popitem(last=False)

                self._trigger_adjacent_prefetch(target)
                return {
                    "success": True,
                    "data_url": data_url
                }
            except Exception:
                # Fallback se PIL falhar: leitura de bytes brutos com micro-retries
                raw_data = resilient_read_bytes(target, max_attempts=3)
                b64_data = base64.b64encode(raw_data).decode('utf-8')
                mime_ext = ext.replace('.', '')
                if mime_ext == 'jpg': mime_ext = 'jpeg'
                data_url = f"data:image/{mime_ext};base64,{b64_data}"

                if cache_key is not None:
                    with self._cache_lock:
                        self._thumbnail_cache[cache_key] = data_url
                        if len(self._thumbnail_cache) > self._max_cache_entries:
                            self._thumbnail_cache.popitem(last=False)

                self._trigger_adjacent_prefetch(target)
                return {
                    "success": True,
                    "data_url": data_url
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _natural_sort_key(path_str: str):
        name = os.path.basename(path_str)
        return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]

    def _find_next_sibling_image(self, target_path: str):
        """Encontra a próxima página de imagem no mesmo diretório usando ordenação natural."""
        try:
            parent_dir = os.path.dirname(target_path)
            if not parent_dir or not os.path.isdir(parent_dir):
                return None
            valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
            siblings = sorted(
                (
                    os.path.normpath(os.path.join(parent_dir, name))
                    for name in os.listdir(parent_dir)
                    if os.path.splitext(name)[1].lower() in valid_exts
                ),
                key=self._natural_sort_key,
            )
            norm_target = os.path.normpath(target_path)
            if norm_target in siblings:
                idx = siblings.index(norm_target)
                if idx + 1 < len(siblings):
                    return siblings[idx + 1]
        except Exception:
            pass
        return None

    def _warm_full_cache_worker(self, next_target: str):
        """Pré-carrega o data_url completo da próxima página em RAM (_full_cache)."""
        try:
            authorized, err = self._authorized_target(next_target)
            if err or not authorized:
                return
            mtime = retry_on_file_lock(lambda: os.path.getmtime(authorized), max_attempts=3)
            cache_key = (authorized, mtime)
            with self._cache_lock:
                if cache_key in self._full_cache:
                    return
            ext = os.path.splitext(authorized)[1].lower()
            raw_data = resilient_read_bytes(authorized, max_attempts=3)
            b64_data = base64.b64encode(raw_data).decode('utf-8')
            mime_ext = ext.replace('.', '')
            if mime_ext == 'jpg':
                mime_ext = 'jpeg'
            data_url = f"data:image/{mime_ext};base64,{b64_data}"
            with self._cache_lock:
                self._full_cache[cache_key] = data_url
                if len(self._full_cache) > self._max_full_cache_entries:
                    self._full_cache.popitem(last=False)
        except Exception:
            pass

    def _trigger_adjacent_prefetch(self, current_target: str):
        """Agenda o prefetch assíncrono em RAM da próxima página do capítulo usando SafeImagePrefetcher."""
        next_target = self._find_next_sibling_image(current_target)
        if not next_target:
            return
        try:
            from src.utils.image_prefetcher import SafeImagePrefetcher
            try:
                next_mtime = os.path.getmtime(next_target)
            except Exception:
                next_mtime = None
            with self._cache_lock:
                self._prefetched_mtimes[next_target] = next_mtime
                if self._prefetcher is None:
                    self._prefetcher = SafeImagePrefetcher([next_target])
                else:
                    self._prefetcher._schedule_prefetch(next_target)
                self._full_prefetch_target = next_target
                t = threading.Thread(
                    target=self._warm_full_cache_worker,
                    args=(next_target,),
                    daemon=True,
                    name=f"FullCachePrefetch-{os.path.basename(next_target)}"
                )
                self._full_prefetch_thread = t
                t.start()
        except Exception:
            pass

    def get_image_base64_full(self, file_path):
        try:
            target, error = self._authorized_target(file_path)
            if error:
                return error

            with self._cache_lock:
                pending_thread = self._full_prefetch_thread if self._full_prefetch_target == target else None
            if pending_thread is not None and pending_thread.is_alive() and pending_thread is not threading.current_thread():
                try:
                    pending_thread.join(timeout=0.5)
                except Exception:
                    pass

            try:
                mtime = retry_on_file_lock(lambda: os.path.getmtime(target), max_attempts=3)
                cache_key = (target, mtime)
                cached_url = None
                with self._cache_lock:
                    if cache_key in self._full_cache:
                        self._full_cache.move_to_end(cache_key)
                        cached_url = self._full_cache[cache_key]
                if cached_url is not None:
                    self._trigger_adjacent_prefetch(target)
                    return {
                        "success": True,
                        "data_url": cached_url
                    }
            except Exception:
                cache_key = None

            ext = os.path.splitext(target)[1].lower()
            raw_data = resilient_read_bytes(target, max_attempts=3)
            b64_data = base64.b64encode(raw_data).decode('utf-8')
            mime_ext = ext.replace('.', '')
            if mime_ext == 'jpg': mime_ext = 'jpeg'
            data_url = f"data:image/{mime_ext};base64,{b64_data}"

            if cache_key is not None:
                with self._cache_lock:
                    self._full_cache[cache_key] = data_url
                    if len(self._full_cache) > self._max_full_cache_entries:
                        self._full_cache.popitem(last=False)

            self._trigger_adjacent_prefetch(target)
            return {
                "success": True,
                "data_url": data_url
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
