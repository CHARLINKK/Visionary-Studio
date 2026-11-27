import os
from src.utils.json_utils import atomic_write_json
from src.utils.file_resilience import resilient_read_json


class StudioReferencesManager:
    """
    Gerenciador especializado em referências de personagens, dicionário global de termos
    e varredura de edições humanas (glossário).
    Desacopla as operações de vocabulário e referências da lógica de layout do StudioService.
    """

    @staticmethod
    def resolve_folder_dir(folder_path: str, resolve_target_fn):
        if not folder_path:
            from src.config import get_app_data_dir
            return get_app_data_dir()
        target = resolve_target_fn(folder_path)
        if os.path.isfile(target):
            target = os.path.dirname(target)
        return target

    def get_references(self, folder_path, resolve_target_fn):
        try:
            target_dir = self.resolve_folder_dir(folder_path, resolve_target_fn)
            for cand in [
                os.path.join(target_dir, "output", "references.json"),
                os.path.join(target_dir, "references.json"),
            ]:
                if os.path.exists(cand):
                    data = resilient_read_json(cand, default=None)
                    if isinstance(data, dict):
                        return {"success": True, "data": data}
            return {"success": True, "data": {"characters": []}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_references(self, folder_path, data, resolve_target_fn):
        try:
            target_dir = self.resolve_folder_dir(folder_path, resolve_target_fn)
            out_dir = os.path.join(target_dir, "output")
            os.makedirs(out_dir, exist_ok=True)
            ref_path = os.path.join(out_dir, "references.json")
            payload = data if isinstance(data, dict) else {"characters": []}
            atomic_write_json(ref_path, payload, indent=2)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_global_dictionary(self, folder_path, resolve_target_fn):
        try:
            from src.config import get_app_data_dir
            candidates = []
            if folder_path:
                target_dir = self.resolve_folder_dir(folder_path, resolve_target_fn)
                candidates.extend([
                    os.path.join(target_dir, "output", "global_dictionary.json"),
                    os.path.join(target_dir, "global_dictionary.json"),
                ])
            candidates.append(os.path.join(get_app_data_dir(), "global_dictionary.json"))

            for cand in candidates:
                if os.path.exists(cand):
                    data = resilient_read_json(cand, default=None)
                    if isinstance(data, dict):
                        return {"success": True, "data": data}
            return {"success": True, "data": {"terms": []}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_global_dictionary(self, folder_path, data, resolve_target_fn):
        try:
            from src.config import get_app_data_dir
            payload = data if isinstance(data, dict) else {"terms": []}
            global_dir = get_app_data_dir()
            os.makedirs(global_dir, exist_ok=True)
            atomic_write_json(os.path.join(global_dir, "global_dictionary.json"), payload, indent=2)

            if folder_path:
                target_dir = self.resolve_folder_dir(folder_path, resolve_target_fn)
                out_dir = os.path.join(target_dir, "output")
                os.makedirs(out_dir, exist_ok=True)
                atomic_write_json(os.path.join(out_dir, "global_dictionary.json"), payload, indent=2)

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def scan_user_edits(self, folder_path, analysis_model, resolve_target_fn):
        try:
            target_dir = self.resolve_folder_dir(folder_path, resolve_target_fn)
            search_dirs = [os.path.join(target_dir, "output"), target_dir]
            diffs = []
            seen_pairs = set()

            for sdir in search_dirs:
                if not os.path.isdir(sdir):
                    continue
                for fname in sorted(os.listdir(sdir)):
                    if not fname.endswith("_map.json"):
                        continue
                    fpath = os.path.join(sdir, fname)
                    try:
                        from src.domain.page_store import PageStore
                        boxes = PageStore.extract_boxes(resilient_read_json(fpath, default=[]))
                        if not boxes:
                            continue
                        for b in boxes:
                            if not isinstance(b, dict):
                                continue
                            ai_txt = (b.get("ai_translated_text") or b.get("ai_translated") or "").strip()
                            user_txt = (b.get("translated_text") or b.get("translated") or "").strip()
                            if ai_txt and user_txt and ai_txt != user_txt and user_txt != "[DELETE]":
                                pair_key = (ai_txt, user_txt)
                                if pair_key not in seen_pairs:
                                    seen_pairs.add(pair_key)
                                    diffs.append({
                                        "id": f"{fname}_{b.get('id', len(diffs) + 1)}",
                                        "original": ai_txt,
                                        "suggestion": user_txt,
                                    })
                    except Exception:
                        pass

            return {"success": True, "diffs": diffs}
        except Exception as e:
            return {"success": False, "error": str(e)}
