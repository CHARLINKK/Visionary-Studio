import os
import re
import json
import shutil
from src.utils.json_utils import dump_compact_map, atomic_write_json
from src.domain.page_store import PageStore, LEGACY_STAGE_SUFFIXES
from src.domain.bubble_contract import (
    normalize_bubble_for_gui,
    normalize_bubble_for_storage,
    reconcile_and_normalize_bubbles,
)


def _natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


class StudioService:
    """Serviço do editor visual (Studio): leitura/gravação de layouts, backups e glossário."""

    def __init__(self, workspace_context=None, api_bridge=None, default_path="", backup_manager=None, references_manager=None, layout_manager=None):
        from src.utils.workspace_context import WorkspaceContext
        self.context, self.api = WorkspaceContext.resolve_service_binding(
            workspace_context, api_bridge, default_path
        )
        self.default_path = default_path
        from src.api_services.studio_backup_manager import StudioBackupManager
        from src.api_services.studio_references_manager import StudioReferencesManager
        from src.api_services.studio_layout_manager import StudioLayoutManager
        self._backup_manager = backup_manager or StudioBackupManager()
        self._references_manager = references_manager or StudioReferencesManager()
        self._layout_manager = layout_manager or StudioLayoutManager()

    def _resolve_target(self, path):
        if not path or not isinstance(path, str) or "\0" in path:
            return ""
        target = path.strip()
        if not target:
            return ""
        if not os.path.isabs(target):
            base = self.context.current_path if self.context else (getattr(self.api, "current_path", "") if self.api else self.default_path)
            if base and base != "MEU COMPUTADOR":
                target = os.path.join(base, target)
        try:
            resolved = os.path.normpath(os.path.abspath(target))
            from src.utils.path_sandbox import is_too_broad
            if is_too_broad(os.path.normcase(resolved)):
                return ""
            return resolved
        except (ValueError, OSError):
            return ""

    def get_page_data(self, image_path):
        try:
            target = self._resolve_target(image_path)
            if not target or not os.path.exists(target):
                return {"success": False, "error": f"Arquivo não encontrado: {image_path}"}

            dir_path = os.path.dirname(target)
            from src.utils.path_sandbox import register_root
            register_root(dir_path)

            out_dir = os.path.join(dir_path, 'output')
            os.makedirs(out_dir, exist_ok=True)

            source_path = PageStore.find_existing_source_path(target)
            record = PageStore.load_page_record(target)
            raw_boxes = record.get("boxes", [])
            has_data = bool(source_path and os.path.exists(source_path))

            cards = [
                normalize_bubble_for_gui(b, idx)
                for idx, b in enumerate(raw_boxes)
                if isinstance(b, dict)
            ]

            # Se veio de um arquivo legado (_map_translated.json, _ptbr.json, etc.), consolida em _map.json v2
            if source_path and not source_path.lower().endswith("_map.json"):
                PageStore.save_page_record(
                    target,
                    boxes=cards,
                    panels=record.get("panels", []),
                    backup=record.get("backup"),
                    dump_fn=dump_compact_map,
                )

            panels = record.get("panels", [])
            has_backup = False

            return {
                "success": True,
                "has_data": has_data,
                "has_backup": has_backup,
                "cards": cards,
                "boxes": cards,
                "panels": panels,
                "block_count": len(cards),
                "image_path": target
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _load_existing_boxes(map_path):
        return PageStore.load_boxes(map_path)

    def save_page_layout(self, image_path, boxes):
        try:
            target = self._resolve_target(image_path)
            if not target:
                return {"success": False, "error": f"Caminho inválido: {image_path}"}
            if not isinstance(boxes, list):
                return {"success": False, "error": "Parâmetro 'boxes' deve ser uma lista"}

            dir_path = os.path.dirname(target)
            base_name = os.path.splitext(os.path.basename(target))[0]
            out_dir = os.path.join(dir_path, 'output')
            os.makedirs(out_dir, exist_ok=True)

            map_path = os.path.join(out_dir, base_name + '_map.json')
            existing_boxes = self._load_existing_boxes(map_path)
            formatted_boxes = reconcile_and_normalize_bubbles(boxes, existing_boxes=existing_boxes)
            PageStore.save_boxes(target, formatted_boxes, target_map_path=map_path, dump_fn=dump_compact_map)

            sync_res = None
            try:
                from src.utils.txt_sync import sync_chapter_txt
                sync_res = sync_chapter_txt(dir_path)
            except Exception:
                pass

            return {"success": True, "message": "Layout salvo com sucesso.", "sync": sync_res}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def autoSortBoxes(self, image_path, boxes):
        """Reordena os balões na ordem de leitura do mangá (RTL, topo para base) usando os quadros da página."""
        return self._layout_manager.auto_sort_boxes(image_path, boxes, self._resolve_target)

    def detect_page_bubbles(self, image_path, white_only=False):
        """
        Executa a detecção de balões sob demanda na página aberta no Studio.
        Com `white_only=True`, mantém só balões brancos; caso contrário inclui onomatopeias.
        """
        return self._layout_manager.detect_page_bubbles(image_path, white_only, self._resolve_target, dump_map_fn=dump_compact_map)

    def clearPageData(self, image_paths, stages):
        try:
            if not isinstance(image_paths, list):
                image_paths = [image_paths]

            if isinstance(stages, str):
                stages = [stages]
            elif not isinstance(stages, (list, tuple, set)):
                stages = []

            has_translate = "translate" in stages or "translation" in stages
            suffixes_to_delete = []
            if "layout" in stages:
                suffixes_to_delete.extend(['_map.json', '_map_layout.json', '_map_clean.json', '_map_ocr.json', '_map_translated.json', '_ptbr.json', '_panels.json'])
            elif "ocr" in stages:
                suffixes_to_delete.extend(['_map_clean.json', '_map_ocr.json', '_map_translated.json', '_ptbr.json'])
            elif has_translate:
                suffixes_to_delete.extend(['_map_translated.json', '_ptbr.json'])

            affected_dirs = set()
            for img_p in image_paths:
                target = self._resolve_target(img_p)
                if not target:
                    continue
                dir_p = os.path.dirname(target)
                if not dir_p:
                    continue
                affected_dirs.add(dir_p)
                base = os.path.splitext(os.path.basename(target))[0]

                if "backup" in stages:
                    backup_p = os.path.join(dir_p, 'output', base + '_map_backup.json')
                    if os.path.exists(backup_p):
                        try:
                            os.remove(backup_p)
                        except Exception:
                            pass

                for s in suffixes_to_delete:
                    for folder in [os.path.join(dir_p, 'output'), dir_p]:
                        f_path = os.path.join(folder, base + s)
                        if os.path.exists(f_path):
                            try:
                                os.remove(f_path)
                            except Exception:
                                pass

                # Quando `layout` é preservado, apagamos só as chaves de texto para manter caixas e polígonos intactos
                if "layout" not in stages:
                    for folder in [os.path.join(dir_p, 'output'), dir_p]:
                        p = os.path.join(folder, base + '_map.json')
                        if os.path.exists(p):
                            try:
                                record = PageStore.load_page_record(p)
                                data = record.get("boxes", [])
                                modified = False
                                for b in data:
                                    if has_translate or "ocr" in stages:
                                        for key in ["translated", "translated_text", "text_ptbr", "ai_translated_text", "ai_translated", "user_edited"]:
                                            if key in b:
                                                del b[key]
                                                modified = True
                                    if "ocr" in stages:
                                        for key in ["text", "original", "text_clean", "ocr_raw", "is_sfx", "isSfx"]:
                                            if key in b:
                                                del b[key]
                                                modified = True
                                if modified:
                                    PageStore.save_boxes(p, data, target_map_path=p, dump_fn=dump_compact_map)
                            except Exception:
                                pass

                PageStore.invalidate_cache(target)

            if affected_dirs and any(s in stages for s in ("layout", "ocr", "translate", "translation")):
                try:
                    from src.utils.txt_sync import sync_chapter_txt
                    for d in affected_dirs:
                        if os.path.isdir(d):
                            sync_chapter_txt(d)
                except Exception:
                    pass

            return {"success": True, "message": "Dados limpos com sucesso!"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def loadStudioData(self, folderPath, isEditorMode=False):
        try:
            target_folder = self._resolve_target(folderPath)
            if not target_folder or not os.path.exists(target_folder):
                return {"success": False, "error": f"Diretório não encontrado: {folderPath}"}

            img_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.avif')

            all_files = sorted(os.listdir(target_folder), key=_natural_sort_key)
            images = [f for f in all_files if f.lower().endswith(img_exts)]

            data = []
            for img in images:
                img_full_path = os.path.join(target_folder, img)
                j_path = PageStore.find_existing_source_path(img_full_path)

                img_data = {
                    "image": img,
                    "has_layout": False,
                    "has_ocr": False,
                    "has_translated": False,
                    "boxes": []
                }

                if j_path and os.path.exists(j_path):
                    try:
                        record = PageStore.load_page_record(img_full_path)
                        blocks = record.get("boxes", [])
                        img_data["has_layout"] = True
                        normalized_blocks = [
                            normalize_bubble_for_gui(b, b_idx)
                            for b_idx, b in enumerate(blocks)
                            if isinstance(b, dict)
                        ]
                        img_data["boxes"] = normalized_blocks
                        img_data["cards"] = normalized_blocks

                        has_txt = any((b.get('text') or b.get('text_clean') or b.get('original') or '').strip() for b in blocks if isinstance(b, dict))
                        has_tr = any((b.get('translated_text') or b.get('text_ptbr') or b.get('translated') or b.get('ptbr') or '').strip() for b in blocks if isinstance(b, dict))

                        img_data["has_ocr"] = has_txt
                        img_data["has_translated"] = has_tr
                    except Exception:
                        pass
                data.append(img_data)

            return {"success": True, "pages": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def saveStudioData(self, folderPath, studioData):
        try:
            target_folder = self._resolve_target(folderPath)
            if not target_folder:
                return {"success": False, "error": f"Diretório inválido: {folderPath}"}
            if not isinstance(studioData, dict):
                return {"success": False, "error": "Parâmetro 'studioData' deve ser um dicionário"}

            out_dir = os.path.join(target_folder, 'output')
            os.makedirs(out_dir, exist_ok=True)

            for page in studioData.get('pages', []):
                if not isinstance(page, dict):
                    continue
                img_name = page.get('image')
                if not img_name:
                    continue

                base = os.path.splitext(img_name)[0]
                j_path = os.path.join(out_dir, base + '_map.json')

                if 'boxes' in page and isinstance(page['boxes'], list):
                    existing_boxes = self._load_existing_boxes(j_path)
                    new_data = reconcile_and_normalize_bubbles(page['boxes'], existing_boxes=existing_boxes)
                    PageStore.save_boxes(j_path, new_data, target_map_path=j_path, dump_fn=dump_compact_map)

            try:
                from src.utils.txt_sync import sync_chapter_txt
                sync_chapter_txt(target_folder)
            except Exception:
                pass

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _resolve_map_and_backup_paths(self, target):
        return self._backup_manager.resolve_map_and_backup_paths(target)

    def check_page_backup(self, image_path):
        return self._backup_manager.check_page_backup(image_path, self._resolve_target)

    def create_page_backup(self, image_path, boxes=None):
        return self._backup_manager.create_page_backup(image_path, boxes, self._resolve_target, self.save_page_layout)

    def restore_page_backup(self, image_path):
        return self._backup_manager.restore_page_backup(image_path, self._resolve_target)

    def delete_page_backup(self, image_path):
        return self._backup_manager.delete_page_backup(image_path, self._resolve_target)

    def _atomic_write_json(self, file_path, data):
        return atomic_write_json(file_path, data, indent=2)

    def _resolve_folder_dir(self, folder_path):
        return self._references_manager.resolve_folder_dir(folder_path, self._resolve_target)

    def get_references(self, folder_path=None):
        return self._references_manager.get_references(folder_path, self._resolve_target)

    def save_references(self, folder_path, data):
        return self._references_manager.save_references(folder_path, data, self._resolve_target)

    def get_global_dictionary(self, folder_path=None):
        return self._references_manager.get_global_dictionary(folder_path, self._resolve_target)

    def save_global_dictionary(self, folder_path, data):
        return self._references_manager.save_global_dictionary(folder_path, data, self._resolve_target)

    def scan_user_edits(self, folder_path, analysis_model=None):
        return self._references_manager.scan_user_edits(folder_path, analysis_model, self._resolve_target)
