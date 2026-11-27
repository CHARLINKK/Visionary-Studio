import os
from src.domain.page_store import PageStore


class StudioBackupManager:
    """
    Gerenciador especializado em ciclo de vida de backups de páginas e mapas de edição.
    Opera sobre o snapshot `backup` embutido no envelope v2 (`{base}_map.json`) via `PageStore`,
    absorvendo e limpando arquivos satélites legados (`_map_backup.json` e `.bak.json`).
    """

    @staticmethod
    def resolve_map_and_backup_paths(target: str):
        dir_path = os.path.dirname(target)
        base_name = os.path.splitext(os.path.basename(target))[0]
        out_dir = os.path.join(dir_path, 'output')

        map_path = PageStore.resolve_map_path(target, prefer_existing=True)

        backup_candidates = [
            os.path.join(out_dir, base_name + '_map_backup.json'),
            os.path.join(out_dir, base_name + '_map.bak.json'),
            os.path.join(dir_path, base_name + '_map_backup.json'),
            os.path.join(dir_path, base_name + '_map.bak.json'),
        ]
        backup_path = None
        for cand in backup_candidates:
            if os.path.isfile(cand):
                backup_path = cand
                break
        if not backup_path:
            backup_dir = out_dir if os.path.exists(out_dir) else dir_path
            backup_path = os.path.join(backup_dir, base_name + '_map_backup.json')

        return map_path, backup_path, dir_path

    def check_page_backup(self, image_path: str, resolve_target_fn):
        try:
            target = resolve_target_fn(image_path)
            if not target:
                return {"success": False, "error": f"Caminho inválido: {image_path}"}
            return {"success": True, "exists": PageStore.check_backup(target)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_page_backup(self, image_path: str, boxes, resolve_target_fn, save_layout_fn):
        try:
            target = resolve_target_fn(image_path)
            if not target:
                return {"success": False, "error": f"Caminho inválido: {image_path}"}
            if boxes is not None and isinstance(boxes, list):
                save_layout_fn(image_path, boxes)
            if PageStore.create_backup(target):
                return {"success": True}
            return {"success": False, "error": "Map file not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restore_page_backup(self, image_path: str, resolve_target_fn):
        try:
            target = resolve_target_fn(image_path)
            if not target:
                return {"success": False, "error": f"Caminho inválido: {image_path}"}
            dir_path = os.path.dirname(target)
            restored = PageStore.restore_backup(target)
            if restored is not None:
                try:
                    from src.utils.txt_sync import sync_chapter_txt
                    sync_chapter_txt(dir_path)
                except Exception:
                    pass
                return {"success": True}
            return {"success": False, "error": "Backup file not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_page_backup(self, image_path: str, resolve_target_fn):
        try:
            target = resolve_target_fn(image_path)
            if not target:
                return {"success": False, "error": f"Caminho inválido: {image_path}"}
            had_backup = PageStore.check_backup(target)
            _, _, dir_path = self.resolve_map_and_backup_paths(target)
            base_name = os.path.splitext(os.path.basename(target))[0]
            out_dir = os.path.join(dir_path, 'output')
            for cand in [
                os.path.join(out_dir, base_name + '_map.bak.json'),
                os.path.join(dir_path, base_name + '_map.bak.json'),
            ]:
                if os.path.isfile(cand):
                    try:
                        os.remove(cand)
                        had_backup = True
                    except Exception:
                        pass
            if PageStore.delete_backup(target) and had_backup:
                return {"success": True}
            return {"success": False, "error": "Backup not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
