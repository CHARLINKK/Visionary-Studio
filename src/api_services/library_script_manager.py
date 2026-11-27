"""
Gerenciador Especializado de Roteiros, Sincronização Bidirecional e Exportação.
Responsável pela manipulação de arquivos .txt, propagação atômica de edições para arquivos
_map.json, sincronização reversa e exportação formatada (Clean TXT e Microsoft Word RTF).
"""

import os
import re
from typing import Any
from src.utils.json_utils import atomic_write_text, dump_compact_map
from src.utils.fs_security import sanitize_filename
from src.utils.file_resilience import resilient_read_json, resilient_read_text
from src.api_services.library_scanner import LibraryScanner


class LibraryScriptManager:
    """
    Controlador isolado para leitura, escrita, reconciliação bidirecional e exportação de roteiros.
    """

    VALID_IMAGE_EXTS = LibraryScanner.VALID_IMAGE_EXTS

    def __init__(self, scanner=None):
        self.scanner = scanner or LibraryScanner()

    def _resolve_dir(self, script_path: str, custom_fn=None) -> str:
        if custom_fn:
            return custom_fn(script_path)
        resolved = self.scanner.resolve_chapter_dir(script_path)
        if resolved:
            return resolved
        clean = os.path.normpath(str(script_path))
        return os.path.dirname(clean) if (os.path.isfile(clean) or clean.lower().endswith(".txt")) else clean

    def read_library_file(self, path: str, resolve_chapter_dir_fn=None) -> dict:
        """Lê o roteiro de um capítulo, verificando preventivamente se há páginas mudas sem cabeçalho."""
        try:
            clean_path = os.path.normpath(str(path))
            target_chapter_dir = self._resolve_dir(clean_path, resolve_chapter_dir_fn)

            content = resilient_read_text(clean_path, encoding="utf-8", errors="replace")

            if target_chapter_dir and os.path.isfile(clean_path):
                try:
                    headers = re.findall(r'^[=\-#\s]*(?:P[ÁAáa\ufffd\?]?GINA|PAGE)\s*\d+', content, re.MULTILINE | re.IGNORECASE)
                    imgs_in_chapter = [f for f in os.listdir(target_chapter_dir) if f.lower().endswith(self.VALID_IMAGE_EXTS) and not f.startswith('.')]
                    if len(headers) < len(imgs_in_chapter):
                        from src.utils.txt_sync import sync_chapter_txt
                        script_name = os.path.splitext(os.path.basename(clean_path))[0]
                        sync_chapter_txt(
                            target_chapter_dir,
                            chapter_name=script_name,
                            target_lib_dir=os.path.dirname(clean_path) if "library" in os.path.dirname(clean_path).lower() else None
                        )
                        content = resilient_read_text(clean_path, encoding="utf-8", errors="replace")
                except Exception as sync_check_err:
                    print(f"[LibraryService] Auto-sync silent pages check notice: {sync_check_err}")

            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_library_file(self, path: str) -> dict:
        """Remove o arquivo de roteiro especificado."""
        try:
            # Suporta argumento como dict {"path": ...} ou string direta
            raw_path = path.get("path") if isinstance(path, dict) else str(path)
            if not raw_path or not raw_path.strip():
                return {"success": False, "error": "Caminho não especificado"}
            clean_path = os.path.normpath(os.path.abspath(raw_path.strip()))
            if not clean_path.lower().endswith(".txt"):
                return {"success": False, "error": "Apenas arquivos de roteiro (.txt) podem ser excluídos."}
            from src.utils.path_sandbox import is_too_broad
            if is_too_broad(os.path.normcase(clean_path)):
                return {"success": False, "error": "Caminho não autorizado."}
            if os.path.exists(clean_path):
                os.remove(clean_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_page_map_balloon(self, chapter_dir: str, page_name: str, balloon_index: int, new_text: str, original_text: str = None, balloon_id: Any = None) -> dict:
        """
        Atualiza cirurgicamente a tradução de um balão no arquivo _map.json correspondente da página.
        Localiza o balão prioritariamente por ID determinístico, seguido por texto original ou índice numérico.
        """
        try:
            balloon_index = int(balloon_index)
        except (ValueError, TypeError):
            return {"success": False, "error": f"Índice de balão inválido: {balloon_index}"}

        base_name = os.path.splitext(page_name)[0]
        candidate_paths = [
            os.path.join(chapter_dir, 'output', f"{base_name}_map.json"),
            os.path.join(chapter_dir, f"{base_name}_map.json"),
            os.path.join(chapter_dir, 'output', f"{base_name}_map_translated.json"),
            os.path.join(chapter_dir, f"{base_name}_map_translated.json"),
            os.path.join(chapter_dir, 'output', f"{base_name}.json"),
            os.path.join(chapter_dir, f"{base_name}.json"),
        ]

        map_path = None
        for cand in candidate_paths:
            if os.path.exists(cand):
                map_path = cand
                break

        if not map_path:
            out_dir = os.path.join(chapter_dir, 'output')
            os.makedirs(out_dir, exist_ok=True)
            map_path = os.path.join(out_dir, f"{base_name}_map.json")
            if not os.path.exists(map_path):
                return {"success": False, "error": f"Arquivo _map.json não encontrado para {page_name}"}

        from src.domain.page_store import PageStore
        try:
            raw_payload = resilient_read_json(map_path, encoding='utf-8')
        except Exception as e:
            return {"success": False, "error": f"Erro ao ler {map_path}: {e}"}

        if isinstance(raw_payload, list):
            blocks = raw_payload
        elif isinstance(raw_payload, dict) and isinstance(raw_payload.get("boxes"), list):
            blocks = raw_payload["boxes"]
        else:
            return {"success": False, "error": f"Formato inválido em {map_path}"}

        # Filtra blocos de diálogo (mesmo filtro usado em txt_sync.py)
        dialogue_blocks = [
            b for b in blocks
            if isinstance(b, dict)
            and not b.get("is_sfx", False)
            and (b.get("text") != "[DELETE]")
            and (b.get("translated_text") != "[DELETE]")
        ]
        dialogue_blocks.sort(key=lambda x: x.get("order", 9999) if x.get("order") is not None else 9999)

        target_block = None
        # 1. Prioridade máxima: correspondência determinística por ID
        if balloon_id is not None:
            bid_str = str(balloon_id).strip()
            for db in dialogue_blocks:
                if str(db.get("id", "")).strip() == bid_str:
                    target_block = db
                    break

        # 2. Correspondência por texto original
        if target_block is None and original_text and str(original_text).strip() and str(original_text).strip() != "[Sem texto original detectado]":
            norm_orig = " ".join(str(original_text).strip().split()).lower()
            for db in dialogue_blocks:
                cand_orig = (db.get("text") or db.get("original") or db.get("text_clean") or db.get("ocr_raw") or "").strip()
                if " ".join(cand_orig.split()).lower() == norm_orig:
                    target_block = db
                    break

        # 3. Fallback sequencial por índice ordinal
        if target_block is None and 0 <= balloon_index < len(dialogue_blocks):
            target_block = dialogue_blocks[balloon_index]

        if target_block is None:
            return {"success": False, "error": f"Balão #{balloon_index + 1} não encontrado em {page_name}"}

        clean_new = str(new_text).strip() if new_text is not None else ""
        if clean_new == "[PENDENTE]":
            clean_new = ""

        target_block["translated_text"] = clean_new
        target_block["translated"] = clean_new
        if "text_ptbr" in target_block:
            target_block["text_ptbr"] = clean_new
        if "ptbr" in target_block:
            target_block["ptbr"] = clean_new

        if clean_new:
            target_block["user_edited"] = True
            if not target_block.get("ai_translated_text"):
                target_block["ai_translated_text"] = target_block.get("ai_translated", "")
        else:
            target_block["user_edited"] = False

        canonical_map = map_path if map_path.lower().endswith("_map.json") else os.path.join(chapter_dir, "output", f"{base_name}_map.json")
        PageStore.save_boxes(map_path, blocks, target_map_path=canonical_map, dump_fn=dump_compact_map)
        return {"success": True, "map_path": canonical_map, "new_text": clean_new}

    def update_balloon_text(self, script_path: str, page_name: str, balloon_index: int, new_text: str, original_text: str = None, resolve_chapter_dir_fn=None, update_map_fn=None, balloon_id: Any = None) -> dict:
        """Atualiza a tradução de um balão específico tanto no _map.json quanto no roteiro de capítulo."""
        try:
            target_chapter_dir = self._resolve_dir(script_path, resolve_chapter_dir_fn)
            clean_path = os.path.normpath(str(script_path))
            if not target_chapter_dir:
                target_chapter_dir = os.path.dirname(clean_path) if os.path.isfile(clean_path) else clean_path

            # 1. Atualiza _map.json
            updater = update_map_fn or self.update_page_map_balloon
            try:
                update_res = updater(target_chapter_dir, page_name, int(balloon_index), str(new_text), original_text=original_text, balloon_id=balloon_id)
            except TypeError:
                update_res = updater(target_chapter_dir, page_name, int(balloon_index), str(new_text), original_text=original_text)
            if not update_res.get("success"):
                return update_res

            # 2. Re-sincroniza roteiro .txt do capítulo
            from src.utils.txt_sync import sync_chapter_txt
            script_name = os.path.splitext(os.path.basename(clean_path))[0]
            sync_res = sync_chapter_txt(
                target_chapter_dir,
                chapter_name=script_name,
                target_lib_dir=os.path.dirname(clean_path) if "library" in os.path.dirname(clean_path).lower() else None
            )

            # 3. Lê o conteúdo sincronizado atualizado
            updated_content = ""
            txt_target = clean_path if os.path.isfile(clean_path) else os.path.join(target_chapter_dir, f"{script_name}.txt")
            if os.path.exists(txt_target):
                try:
                    updated_content = resilient_read_text(txt_target, encoding="utf-8", errors="replace")
                except Exception:
                    pass

            return {
                "success": True,
                "map_path": update_res.get("map_path"),
                "page_name": page_name,
                "balloon_index": balloon_index,
                "new_text": update_res.get("new_text"),
                "content": updated_content,
                "sync": sync_res
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def parse_script_to_blocks(self, content: str) -> list[dict]:
        """Faz a análise sintática de um roteiro .txt e retorna a lista de páginas estruturadas."""
        lines = content.splitlines()
        pages = []
        curr_page = None
        curr_en = ""
        curr_id = None
        active_field = None
        pending_newlines = 0

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                if active_field:
                    pending_newlines += 1
                continue

            if trimmed.startswith(('===', '---')) and not re.search(r'(?:P[ÁAáa\ufffd\?]?GINA|PAGE)\s*\d+', trimmed, re.IGNORECASE):
                active_field = None
                pending_newlines = 0
                continue

            # Detecta âncora de ID antes do balão (ex: # [id: 1], # [b: 1], <!-- id: 1 -->)
            id_match = re.match(r'^(?:#\s*\[(?:id|b):?\s*([^\]]+)\]|<!--\s*id:\s*([^>]+)\s*-->)', trimmed, re.IGNORECASE)
            if id_match:
                curr_id = (id_match.group(1) or id_match.group(2)).strip()
                active_field = None
                pending_newlines = 0
                continue

            # Comentários que não são âncoras de ID são ignorados
            if trimmed.startswith('#') and not re.search(r'(?:P[ÁAáa\ufffd\?]?GINA|PAGE)\s*\d+', trimmed, re.IGNORECASE):
                active_field = None
                pending_newlines = 0
                continue

            clean_header = re.sub(r'^[\s=\-#]+|[\s=\-#]+$', '', trimmed).strip()
            p_match = re.match(r'^(?:P[ÁAáa\ufffd\?]?GINA|PAGE)\s*(\d+)(?:[:\s-]+(.*))?$', clean_header, re.IGNORECASE)
            if p_match:
                if curr_page:
                    pages.append(curr_page)
                curr_page = {
                    "num": int(p_match.group(1)),
                    "image": p_match.group(2).strip() if p_match.group(2) else f"Página {p_match.group(1)}",
                    "balloons": []
                }
                curr_en = ""
                curr_id = None
                active_field = None
                pending_newlines = 0
                continue

            if not curr_page:
                continue

            if trimmed.startswith(('[EN]:', '[EN]')):
                curr_en = re.sub(r'^\[EN\]:?\s*', '', trimmed, flags=re.IGNORECASE).strip()
                active_field = "en"
                pending_newlines = 0
            elif trimmed.startswith(('[BR]', '[PT]')):
                br_match = re.match(r'^\[(?:BR|PT)\](?:\s*\(([^)]+)\))?:\s*(.*)$', trimmed, re.IGNORECASE)
                br_text = br_match.group(2).strip() if br_match else re.sub(r'^\[(?:BR|PT)\]:?\s*', '', trimmed, flags=re.IGNORECASE).strip()
                curr_page["balloons"].append({
                    "id": curr_id,
                    "en": curr_en,
                    "br": br_text
                })
                curr_en = ""
                curr_id = None
                active_field = "br"
                pending_newlines = 0
            elif re.match(r'^\[\d+\]:?\s*(.*)$', trimmed):
                num_match = re.match(r'^\[\d+\]:?\s*(.*)$', trimmed)
                raw_text = num_match.group(1).strip() if num_match else trimmed
                tag_match = re.match(r'^\(([^)]+)\)\s*(.*)$', raw_text)
                txt = tag_match.group(2).strip() if tag_match else raw_text
                curr_page["balloons"].append({
                    "id": curr_id,
                    "en": curr_en,
                    "br": txt
                })
                curr_en = ""
                curr_id = None
                active_field = "br"
                pending_newlines = 0
            else:
                sep = "\n\n" if pending_newlines > 0 else "\n"
                pending_newlines = 0
                if active_field == "br" and curr_page["balloons"]:
                    prev_br = curr_page["balloons"][-1]["br"]
                    curr_page["balloons"][-1]["br"] = f"{prev_br}{sep}{trimmed}".strip() if prev_br else trimmed
                elif active_field == "en":
                    curr_en = f"{curr_en}{sep}{trimmed}".strip() if curr_en else trimmed

        if curr_page:
            pages.append(curr_page)

        return pages

    def sync_json_from_script(self, script_path: str, content: str, resolve_chapter_dir_fn=None):
        """Faz a análise completa do roteiro e propaga edições manuais de volta para os _map.json."""
        target_chapter_dir = self._resolve_dir(script_path, resolve_chapter_dir_fn)
        if not target_chapter_dir or not os.path.exists(target_chapter_dir):
            return

        pages = self.parse_script_to_blocks(content)
        if not pages:
            return

        from src.domain.page_store import PageStore
        for page in pages:
            img_name = page["image"]
            base_name = os.path.splitext(img_name)[0]
            cand_paths = [
                os.path.join(target_chapter_dir, 'output', f"{base_name}_map.json"),
                os.path.join(target_chapter_dir, f"{base_name}_map.json"),
            ]
            map_path = None
            for cp in cand_paths:
                if os.path.exists(cp):
                    map_path = cp
                    break
            if not map_path:
                continue

            try:
                raw_payload = resilient_read_json(map_path, encoding='utf-8')
            except Exception:
                continue

            if isinstance(raw_payload, list):
                blocks = raw_payload
            elif isinstance(raw_payload, dict) and isinstance(raw_payload.get("boxes"), list):
                blocks = raw_payload["boxes"]
            else:
                continue

            dialogue_blocks = [
                b for b in blocks
                if isinstance(b, dict)
                and not b.get("is_sfx", False)
                and (b.get("text") != "[DELETE]")
                and (b.get("translated_text") != "[DELETE]")
            ]
            dialogue_blocks.sort(key=lambda x: x.get("order", 9999) if x.get("order") is not None else 9999)

            # Índice de busca determinístico por ID canônico
            blocks_by_id = {}
            for db in dialogue_blocks:
                b_id_val = db.get("id")
                if b_id_val is not None:
                    blocks_by_id[str(b_id_val).strip()] = db

            modified = False
            for b_idx, s_b in enumerate(page["balloons"]):
                s_br = s_b["br"]
                if not s_br or s_br == "[PENDENTE]":
                    continue

                target_block = None
                s_id = s_b.get("id")
                # 1. Prioridade máxima: correspondência determinística por ID ancorado
                if s_id is not None and str(s_id).strip() in blocks_by_id:
                    target_block = blocks_by_id[str(s_id).strip()]

                # 2. Fallback heurístico por texto original (se não tiver ID ou ID for desconhecido)
                if target_block is None:
                    s_en = s_b["en"]
                    if s_en and s_en != "[Sem texto original detectado]":
                        norm_en = " ".join(s_en.strip().split()).lower()
                        for db in dialogue_blocks:
                            cand_orig = (db.get("text") or db.get("original") or db.get("text_clean") or db.get("ocr_raw") or "").strip()
                            if " ".join(cand_orig.split()).lower() == norm_en:
                                target_block = db
                                break

                # 3. Fallback sequencial por índice ordinal
                if target_block is None and b_idx < len(dialogue_blocks):
                    target_block = dialogue_blocks[b_idx]

                if target_block:
                    curr_trans = (target_block.get("translated_text") or target_block.get("translated") or "").strip()
                    if curr_trans != s_br:
                        target_block["translated_text"] = s_br
                        target_block["translated"] = s_br
                        if "text_ptbr" in target_block:
                            target_block["text_ptbr"] = s_br
                        if "ptbr" in target_block:
                            target_block["ptbr"] = s_br
                        target_block["user_edited"] = True
                        if not target_block.get("ai_translated_text"):
                            target_block["ai_translated_text"] = target_block.get("ai_translated", "")
                        modified = True

            if modified:
                PageStore.save_boxes(map_path, blocks, target_map_path=map_path, dump_fn=dump_compact_map)

    def save_library_file(self, path: str, content: str, resolve_chapter_dir_fn=None, sync_json_fn=None) -> dict:
        """Salva o conteúdo atualizado no arquivo .txt atomicamente e propaga para _map.json."""
        try:
            if not path or not isinstance(path, str) or not path.strip():
                return {"success": False, "error": "Caminho não especificado"}
            clean_path = os.path.normpath(os.path.abspath(path.strip()))
            if not clean_path.lower().endswith(".txt"):
                return {"success": False, "error": "Apenas arquivos de roteiro (.txt) podem ser salvos."}
            from src.utils.path_sandbox import is_too_broad
            if is_too_broad(os.path.normcase(clean_path)):
                return {"success": False, "error": "Caminho não autorizado."}

            parent = os.path.dirname(clean_path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)

            if not atomic_write_text(clean_path, content, encoding="utf-8"):
                return {"success": False, "error": f"Falha ao salvar arquivo atomicamente: {clean_path}"}

            stat = os.stat(clean_path)

            # Reconciliação bidirecional: sincroniza para o _map.json
            try:
                syncer = sync_json_fn or self.sync_json_from_script
                syncer(clean_path, content, resolve_chapter_dir_fn=resolve_chapter_dir_fn)
            except Exception as j_err:
                print(f"[LibraryService] Warning syncing json from script: {j_err}")

            return {
                "success": True,
                "path": clean_path,
                "mtime": stat.st_mtime * 1000,
                "size": stat.st_size
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_script(self, path: str, export_format: str = "clean_txt") -> dict:
        """Exporta o roteiro em formato texto puro ou documento Microsoft Word RTF com estilos."""
        try:
            clean_path = os.path.normpath(str(path))
            if not os.path.exists(clean_path):
                return {"success": False, "error": f"Arquivo não encontrado: {clean_path}"}

            content = resilient_read_text(clean_path, encoding="utf-8")
            base_name = os.path.splitext(os.path.basename(clean_path))[0]

            from src.api_services.script_exporter import export_script_to_format
            return export_script_to_format(content, base_name, export_format)
        except Exception as e:
            return {"success": False, "error": str(e)}
