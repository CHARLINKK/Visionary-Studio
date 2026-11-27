import os
import sys
import json
import re
from concurrent.futures import ThreadPoolExecutor
from src.utils.fs_security import sanitize_filename, send_to_trash

_NATURAL_SPLIT_REGEX = re.compile(r'(\d+)')

def natural_sort_key(s):
    """Chave de ordenação natural humana (ex: '01.jpg', '2.jpg', '10.jpg')."""
    return [int(text) if text.isdigit() else text.lower() for text in _NATURAL_SPLIT_REGEX.split(str(s))]

_IGNORED_PROGRESS_JSON_SUFFIXES = ('.bak.json', '_backup.json', '.bak', '_panels.json', '_strokes.json')


def _detect_folder_output_progress(folder_path: str, candidate_files: list, valid_basenames: set = None, limit: int = 3) -> tuple:
    """
    Inspeciona arquivos JSON de uma pasta para determinar (has_output, has_progress).
    Se valid_basenames for fornecido, apenas arquivos cujo prefixo corresponda a uma imagem válida serão considerados.
    """
    has_output = False
    has_progress = False
    checked_summaries = 0

    valid_files = []
    for f in candidate_files:
        f_lower = f.lower()
        if not f_lower.endswith('.json') or f_lower.endswith(_IGNORED_PROGRESS_JSON_SUFFIXES):
            continue
        if valid_basenames is not None:
            b_name = f.split('_')[0] if '_' in f else os.path.splitext(f)[0]
            if b_name not in valid_basenames:
                continue
        valid_files.append(f)

    if not valid_files:
        return has_output, has_progress

    has_progress = True
    for f in valid_files:
        f_lower = f.lower()
        if '_translated' in f_lower or '_ptbr' in f_lower:
            has_output = True
            return has_output, has_progress

        if checked_summaries < limit:
            checked_summaries += 1
            try:
                from src.domain.page_store import PageStore
                summary = PageStore.get_page_summary(os.path.join(folder_path, f))
                if summary.get("block_count", 0) > 0 and summary.get("has_translation"):
                    has_output = True
                    return has_output, has_progress
            except Exception:
                pass

    return has_output, has_progress


def _inspect_subdirectory(target_path: str, entry: str, img_exts: tuple) -> dict:
    full_path = os.path.join(target_path, entry)
    status = ""
    img_count = 0
    try:
        subfiles = os.listdir(full_path)
        imgs = [f for f in subfiles if f.lower().endswith(img_exts)]
        img_count = len(imgs)
        img_basenames = {os.path.splitext(f)[0] for f in imgs}
        has_output = False
        has_progress = False

        out_path = os.path.join(full_path, 'output')
        if 'output' in subfiles and os.path.isdir(out_path):
            try:
                out_files = os.listdir(out_path)
                has_output, has_progress = _detect_folder_output_progress(out_path, out_files, valid_basenames=None, limit=3)
            except Exception:
                pass

        if not has_output:
            sub_has_output, sub_has_progress = _detect_folder_output_progress(full_path, subfiles, valid_basenames=img_basenames, limit=3)
            if sub_has_output:
                has_output = True
            if sub_has_progress:
                has_progress = True

        if img_count > 0 and has_output:
            status = "green"
        elif img_count > 0:
            status = "progress" if has_progress else "yellow"
        else:
            status = "blue"
    except Exception:
        status = ""

    return {
        "name": entry,
        "path": full_path,
        "isDir": True,
        "isChapter": img_count > 0,
        "status": status,
        "imgCount": img_count,
        "hasImages": img_count > 0
    }

class FileSystemService:
    def __init__(self, workspace_context=None, api_bridge=None, default_path="MEU COMPUTADOR"):
        from src.utils.workspace_context import WorkspaceContext
        self.context, self.api = WorkspaceContext.resolve_service_binding(
            workspace_context, api_bridge, default_path
        )

    @property
    def current_path(self):
        return self.context.current_path

    @current_path.setter
    def current_path(self, val):
        self.context.current_path = val

    def get_drives(self):
        drives = []
        if sys.platform == 'win32':
            try:
                import string
                from ctypes import windll
                bitmask = windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drive_path = f"{letter}:\\"
                        drives.append({
                            "name": drive_path,
                            "path": drive_path,
                            "isDir": True,
                            "isDrive": True,
                            "status": ""
                        })
                    bitmask >>= 1
            except Exception:
                drives.append({
                    "name": "C:\\",
                    "path": "C:\\",
                    "isDir": True,
                    "isDrive": True,
                    "status": ""
                })
        else:
            drives.append({
                "name": "/",
                "path": "/",
                "isDir": True,
                "isDrive": True,
                "status": ""
            })
        return drives


    def list_directory(self, target_path=""):
        try:
            if not target_path or target_path == "MEU COMPUTADOR":
                return {
                    "success": True,
                    "current_path": "MEU COMPUTADOR",
                    "items": self.get_drives()
                }

            if not os.path.exists(target_path):
                return {
                    "success": False,
                    "error": f"Diretório não encontrado: {target_path}"
                }

            self.context.current_path = target_path
            if self.api and hasattr(self.api, "current_path"):
                self.api.current_path = target_path
            parent_dir = os.path.dirname(target_path)
            if parent_dir == target_path:
                parent_dir = "MEU COMPUTADOR"

            items = [
                {
                    "name": f".. (Voltar para {parent_dir})",
                    "isBack": True,
                    "isDir": True,
                    "targetPath": parent_dir,
                    "path": parent_dir
                }
            ]

            # Blindagem: recuperar qualquer reordenação interrompida antes de listar
            self.recover_reorder_if_needed(target_path)
            try:
                from src.utils.file_resilience import cleanup_orphaned_tmp_files
                cleanup_orphaned_tmp_files(target_path, max_age_seconds=300.0)
                _out = os.path.join(target_path, "output")
                if os.path.isdir(_out):
                    cleanup_orphaned_tmp_files(_out, max_age_seconds=300.0)
            except Exception:
                pass

            img_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.avif')
            entries = sorted(os.listdir(target_path), key=natural_sort_key)
            target_root_files = set(entries)

            target_output_dir = os.path.join(target_path, 'output')
            target_output_exists = os.path.isdir(target_output_dir)
            target_output_files = set(os.listdir(target_output_dir)) if target_output_exists else set()

            dir_candidates = []
            file_items = []

            for entry in entries:
                if entry.startswith('.') or entry.lower() in ('__pycache__', 'thumbs.db'):
                    continue
                full_path = os.path.join(target_path, entry)
                if os.path.isdir(full_path):
                    dir_candidates.append(entry)
                else:
                    is_img = entry.lower().endswith(img_exts)
                    if is_img:
                        base = os.path.splitext(entry)[0]
                        block_count = 0
                        status = "pending"
                        
                        has_layout = False
                        has_ocr = False
                        has_trans = False

                        # Fast lookup in pre-scanned sets (O(1) memory check)
                        suffixes = ['_map.json', '_map_translated.json', '_ptbr.json', '_map_clean.json', '_ocr.json', '_map_layout.json', '.json']
                        target_jpath = None

                        for suffix in suffixes:
                            fname = base + suffix
                            if fname in target_output_files:
                                target_jpath = os.path.join(target_output_dir, fname)
                                break
                            elif fname in target_root_files:
                                target_jpath = os.path.join(target_path, fname)
                                break

                        if target_jpath:
                            status = "ready"
                            has_layout = True
                            try:
                                from src.domain.page_store import PageStore
                                summary = PageStore.get_page_summary(target_jpath)
                                block_count = summary.get("block_count", 0)
                                has_ocr = bool(summary.get("has_ocr"))
                                has_trans = bool(summary.get("has_translation"))
                            except Exception:
                                pass

                        file_items.append({
                            "name": entry,
                            "path": full_path,
                            "isDir": False,
                            "isImage": True,
                            "status": status,
                            "blockCount": block_count,
                            "pageData": {
                                "layout": has_layout,
                                "ocr": has_ocr,
                                "translation": has_trans,
                                "has_backup": False
                            }
                        })

            if len(dir_candidates) > 2:
                with ThreadPoolExecutor(max_workers=min(16, (os.cpu_count() or 4) * 2)) as executor:
                    dir_items = list(executor.map(lambda e: _inspect_subdirectory(target_path, e, img_exts), dir_candidates))
            else:
                dir_items = [_inspect_subdirectory(target_path, e, img_exts) for e in dir_candidates]

            items.extend(dir_items)
            items.extend(file_items)

            # Sandbox de /api/image: a pasta que o usuário abriu e que contém páginas passa a ser uma
            # raiz autorizada (inclui output/ e output/crops por serem subpastas).
            if any(item.get("isImage") for item in file_items):
                from src.utils.path_sandbox import register_root
                register_root(target_path)

            return {
                "success": True,
                "current_path": target_path,
                "items": items
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


    def select_folder(self, initial_dir=""):
        # No Visionary Studio com Electron, o diálogo nativo de seleção de pasta
        # é gerenciado pelo processo principal via IPC (window.electronAPI.selectFolder).
        return {
            "success": False,
            "error": "Diálogo nativo de pasta indisponível no backend. Utilize window.electronAPI.selectFolder via frontend."
        }


    def selectFolder(self, initial_dir=""):
        return self.select_folder(initial_dir)


    def listDrives(self):
        return self.get_drives()
        

    def listDirectory(self, path):
        return self.list_directory(path)
        

    def getParentPath(self, path):
        return os.path.dirname(path) if path else ""

    def recover_reorder_if_needed(self, folder_path):
        """
        Verifica e recupera qualquer transação de reordenação interrompida por queda ou erro.
        """
        try:
            from src.domain.reorder_transaction import recover_reorder_if_needed
            return recover_reorder_if_needed(folder_path)
        except Exception as e:
            return {"recovered": False, "error": str(e)}

    def reorder_pages(self, folder_path, files):
        """
        Rename all files to match a new ordered sequence (001.jpg, 002.jpg).
        files: List of file objects [{"name": "04.jpg", "path": "..."}, ...] in the newly desired order.
        Executa com rollback transacional completo e journal de recuperação pós-crash.
        """
        from src.domain.reorder_transaction import execute_reorder
        return execute_reorder(folder_path, files)

    def merge_pages(self, folder_path, file_paths, direction="rtl"):
        """
        Merge 2+ images horizontally.
        direction: 'rtl' (Manga, right-to-left) or 'ltr' (Comic, left-to-right).
        """
        images = []
        resized_images = []
        merged = None
        try:
            from PIL import Image
            if not file_paths or len(file_paths) < 2:
                return {"success": False, "error": "É necessário selecionar pelo menos 2 imagens para mesclar"}

            try:
                for p in file_paths:
                    images.append(Image.open(p))

                max_height = max(img.height for img in images)

                for img in images:
                    if img.height != max_height:
                        w = int((max_height / img.height) * img.width)
                        resized_images.append(img.resize((w, max_height), Image.Resampling.LANCZOS))
                    else:
                        resized_images.append(img)

                if direction == "rtl":
                    resized_images.reverse()

                total_width = sum(img.width for img in resized_images)

                merged = Image.new('RGB', (total_width, max_height))
                x_offset = 0
                for img in resized_images:
                    merged.paste(img, (x_offset, 0))
                    x_offset += img.width

                first_file = file_paths[0]
                base_name, ext = os.path.splitext(os.path.basename(first_file))
                clean_base = sanitize_filename(base_name, fallback="spread")
                new_name = f"{clean_base}_spread{ext}"
                new_path = os.path.join(folder_path, new_name)

                counter = 1
                candidate_path = new_path
                while os.path.exists(candidate_path):
                    candidate_name = f"{clean_base}_spread_{counter}{ext}"
                    candidate_path = os.path.join(folder_path, candidate_name)
                    counter += 1
                new_path = candidate_path

                merged.save(new_path, quality=95)
            finally:
                if merged is not None:
                    try: merged.close()
                    except Exception: pass
                for r_img in resized_images:
                    if r_img not in images:
                        try: r_img.close()
                        except Exception: pass
                for img in images:
                    try: img.close()
                    except Exception: pass

            if not os.path.exists(new_path) or os.path.getsize(new_path) == 0:
                return {"success": False, "error": "Falha ao gravar imagem mesclada no disco"}

            for p in file_paths:
                self.delete_page(p, sync_txt=False)

            try:
                from src.utils.txt_sync import sync_chapter_txt
                sync_chapter_txt(folder_path)
            except Exception:
                pass

            return {"success": True, "newPath": new_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def split_page(self, file_path, direction="rtl"):
        """Split a spread image vertically in half into two images.
        
        Args:
            file_path: Path to the image file to split.
            direction: Reading direction ('rtl' for Manga, 'ltr' for Western comics).
        """
        if not file_path or not isinstance(file_path, str) or not os.path.exists(file_path):
            return {"success": False, "error": "Arquivo não encontrado ou inválido"}
        img = None
        left_img = None
        right_img = None
        try:
            from PIL import Image
            folder = os.path.dirname(file_path)
            base_name, ext = os.path.splitext(os.path.basename(file_path))
            clean_base = sanitize_filename(base_name, fallback="split")
            try:
                img = Image.open(file_path)
                width, height = img.size
                if width < 10:
                    return {"success": False, "error": "Imagem muito estreita para divisão"}
                mid = width // 2

                left_img = img.crop((0, 0, mid, height))
                right_img = img.crop((mid, 0, width, height))

                # In Manga (RTL), right half is read first (part A), left half is read second (part B)
                # In Western/Webtoon (LTR), left half is read first (part A), right half is read second (part B)
                is_ltr = str(direction).strip().lower() == "ltr"
                part_a_img = left_img if is_ltr else right_img
                part_b_img = right_img if is_ltr else left_img

                part_a_path = os.path.join(folder, f"{clean_base}_A{ext}")
                part_b_path = os.path.join(folder, f"{clean_base}_B{ext}")

                part_a_img.save(part_a_path, quality=95)
                part_b_img.save(part_b_path, quality=95)

                if is_ltr:
                    left_path = part_a_path
                    right_path = part_b_path
                else:
                    right_path = part_a_path
                    left_path = part_b_path
            finally:
                if left_img is not None:
                    try: left_img.close()
                    except Exception: pass
                if right_img is not None:
                    try: right_img.close()
                    except Exception: pass
                if img is not None:
                    try: img.close()
                    except Exception: pass

            if not (os.path.exists(part_a_path) and os.path.getsize(part_a_path) > 0 and
                    os.path.exists(part_b_path) and os.path.getsize(part_b_path) > 0):
                if os.path.exists(part_a_path):
                    try: os.remove(part_a_path)
                    except Exception: pass
                if os.path.exists(part_b_path):
                    try: os.remove(part_b_path)
                    except Exception: pass
                return {"success": False, "error": "Falha ao gravar metades da página dividida"}

            self.delete_page(file_path, sync_txt=False)
            try:
                from src.utils.txt_sync import sync_chapter_txt
                sync_chapter_txt(folder)
            except Exception:
                pass

            return {
                "success": True,
                "partAPath": part_a_path,
                "partBPath": part_b_path,
                "rightPath": right_path,
                "leftPath": left_path
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_page(self, file_path, sync_txt=True):
        try:
            if not file_path or not isinstance(file_path, str) or not os.path.basename(file_path):
                return {"success": False, "error": "Caminho de arquivo inválido"}
            if os.path.exists(file_path):
                send_to_trash(file_path)
            
            # Blindagem: Apagar também os arquivos órfãos de output para não corromper o projeto
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            folder = os.path.dirname(file_path)
            
            known_json_suffixes = [
                '_map.json', '_map_translated.json', '_ptbr.json', '_map_clean.json',
                '_ocr.json', '_map_ocr.json', '_map_layout.json', '_panels.json',
                '_strokes.json', '_map_backup.json', '_map.bak.json', '.json'
            ]
            # Limpar JSONs no root
            for suffix in known_json_suffixes:
                p = os.path.join(folder, base_name + suffix)
                if os.path.exists(p): os.remove(p)
            
            # Limpar Output (apenas artefatos exatos desta página, sem afetar _A, _B ou _spread)
            out_dir = os.path.join(folder, 'output')
            if os.path.exists(out_dir):
                for suffix in known_json_suffixes:
                    p = os.path.join(out_dir, base_name + suffix)
                    if os.path.exists(p) and os.path.isfile(p):
                        os.remove(p)
                crops_dir = os.path.join(out_dir, 'crops')
                if os.path.exists(crops_dir):
                    crop_prefix = f"{base_name}_balao_"
                    for cf in os.listdir(crops_dir):
                        if cf.startswith(crop_prefix):
                            cp = os.path.join(crops_dir, cf)
                            if os.path.isfile(cp):
                                os.remove(cp)

            try:
                from src.domain.page_store import PageStore
                PageStore.invalidate_cache(file_path)
            except Exception:
                pass

            if sync_txt:
                try:
                    from src.utils.txt_sync import sync_chapter_txt
                    sync_chapter_txt(folder)
                except Exception:
                    pass

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
