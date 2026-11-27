"""
Módulo TXT Sync.
Engine contínua e idempotente para sincronização de roteiros de tradução (.txt).
Ele varre ativamente os mapeamentos JSON de todo o capítulo, aplica ordenação natural às páginas e balões, 
e produz um roteiro bilíngue unificado. Este parsing bidirecional de .txt em coordenação com os JSONs
permite manter o React em sync constante e garante uma única "Fonte de Verdade" para as falas.
"""

import os
import json
import re
import threading
from datetime import datetime
from src.utils.json_utils import atomic_write_text
from src.utils.fs_security import sanitize_filename
from src.utils.file_resilience import resilient_read_json

# Global threading lock to eliminate concurrent write races on Windows
_sync_lock = threading.Lock()

def _natural_sort_key(s):
    """Sort strings containing numbers in natural human order (e.g. 1, 2, 10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def format_script_multiline(text: str, fallback: str = "") -> str:
    """
    Higieniza e normaliza texto de balão preservando quebras de linha legítimas.
    Evita o achatamento forçado de diálogos e pensamentos, limpando espaços supérfluos
    no início/fim de cada linha e colapsando sequências de mais de uma linha em branco.
    """
    if not text or not str(text).strip():
        return fallback

    # Normaliza CRLF e CR para LF
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = [l.strip() for l in normalized.split("\n")]

    # Remove linhas vazias no início e no fim
    while raw_lines and not raw_lines[0]:
        raw_lines.pop(0)
    while raw_lines and not raw_lines[-1]:
        raw_lines.pop()

    if not raw_lines:
        return fallback

    # Compacta mais de uma linha vazia consecutiva para no máximo uma (parágrafo limpo)
    clean_lines = []
    consecutive_empty = 0
    for l in raw_lines:
        if not l:
            consecutive_empty += 1
            if consecutive_empty <= 1:
                clean_lines.append("")
        else:
            consecutive_empty = 0
            clean_lines.append(l)

    return "\n".join(clean_lines)

def sync_chapter_txt(chapter_dir: str, chapter_name: str = None, target_lib_dir: str = None) -> dict:
    """
    Realiza o parsing bidirecional de JSONs e .txt para construir e sincronizar o script.
    
    Arquitetura de funcionamento:
    1. Varredura: Identifica os mapas JSON do capítulo.
    2. Ordenação Natural: Classifica as páginas e blocos sequencialmente.
    3. Filtragem: Ignora balões de deleção explícitos ou de efeitos sonoros marcados para exclusão.
    4. Geração: Compila o roteiro .txt no Modo Revisão (Bilingue - EN/BR).
    5. Escrita Atômica: Salva o roteiro com lock na thread e resiliência ao sistema de arquivos do Windows.
    
    Retorna estatísticas operacionais de sucesso e progresso.
    """
    with _sync_lock:
        try:
            if not chapter_dir or not os.path.exists(chapter_dir):
                return {"success": False, "error": f"Diretório inválido: {chapter_dir}"}

            norm_dir = os.path.normpath(os.path.abspath(chapter_dir))
            # Se for passado um arquivo de imagem ou map diretamente
            if os.path.isfile(norm_dir):
                norm_dir = os.path.dirname(norm_dir)
            # Se for passada a pasta 'output' interna
            if os.path.basename(norm_dir).lower() == "output":
                norm_dir = os.path.dirname(norm_dir)

            if not chapter_name:
                chapter_name = os.path.basename(norm_dir)
                if not chapter_name or chapter_name == ".":
                    chapter_name = "Chapter"
            chapter_name = sanitize_filename(chapter_name, fallback="Chapter")

            out_dir = os.path.join(norm_dir, "output")
            img_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.avif')
            
            try:
                entries = os.listdir(norm_dir)
            except Exception as e:
                return {"success": False, "error": str(e)}

            image_files = sorted([f for f in entries if f.lower().endswith(img_exts)], key=_natural_sort_key)
            if not image_files:
                # Check if directory only has JSONs
                json_bases = [os.path.splitext(f)[0].replace('_map', '').replace('_translated', '') 
                              for f in entries if f.lower().endswith('.json') and not f.startswith('.')]
                unique_bases = sorted(dict.fromkeys(json_bases), key=_natural_sort_key)
                image_files = [f"{b}.png" for b in unique_bases]

            pages_data = []
            total_balloons = 0
            translated_balloons = 0
            json_suffixes = ['_map.json', '_map_translated.json', '_map_clean.json', '_map_ocr.json', '.json']

            for p_idx, img_name in enumerate(image_files, 1):
                base = os.path.splitext(img_name)[0]
                j_path = None

                search_dirs = [out_dir, norm_dir] if os.path.exists(out_dir) else [norm_dir]
                for s_dir in search_dirs:
                    for suffix in json_suffixes:
                        cand = os.path.join(s_dir, base + suffix)
                        if os.path.exists(cand):
                            j_path = cand
                            break
                    if j_path:
                        break

                blocks = []
                if j_path:
                    try:
                        from src.domain.page_store import PageStore
                        blocks = PageStore.load_boxes_from_source(j_path)
                    except Exception:
                        blocks = []

                page_balloons = []
                if blocks:
                    # Garante que os balões sejam exportados rigorosamente pela ordem de leitura ('order')
                    ordered_blocks = sorted(blocks, key=lambda x: x.get("order", 9999) if isinstance(x, dict) and x.get("order") is not None else 9999)
                    for b in ordered_blocks:
                        if not isinstance(b, dict):
                            continue
                        if b.get("is_sfx", False):
                            continue

                        en_text = (b.get("text") or b.get("original") or b.get("text_clean") or "").strip()
                        br_text = (b.get("translated_text") or b.get("text_ptbr") or b.get("translated") or b.get("ptbr") or "").strip()

                        # Balões marcados explicitamente para deleção são ignorados
                        if en_text == "[DELETE]" or br_text == "[DELETE]":
                            continue

                        total_balloons += 1
                        if br_text and br_text != "[PENDENTE]":
                            translated_balloons += 1

                        # Normaliza texto preservando quebras de linha e parágrafos legítimos
                        clean_en = format_script_multiline(en_text, fallback="[Sem texto original detectado]")
                        clean_br = format_script_multiline(br_text, fallback="[PENDENTE]")

                        balloon_type = b.get("type", "").lower()
                        type_tag = ""
                        if balloon_type in ("thought", "pensamento"):
                            type_tag = " (PENSAMENTO)"
                        elif balloon_type in ("narration", "narracao", "narrador"):
                            type_tag = " (NARRAÇÃO)"

                        b_id = b.get("id")
                        if b_id is None:
                            b_id = b.get("order")

                        page_balloons.append({
                            "id": b_id,
                            "en": clean_en,
                            "br": clean_br,
                            "type_tag": type_tag
                        })

                # Preserva rigorosamente todas as páginas do mangá na ordem física natural,
                # impedindo que páginas silenciosas (sem falas ou splash pages) sejam puladas
                pages_data.append({
                    "page_number": p_idx,
                    "image": img_name,
                    "balloons": page_balloons
                })

            # Build formatted script (Modo Revisão - Bilíngue com EN e BR)
            now_str = datetime.now().strftime("%d/%m/%Y - %H:%M")
            pct = round((translated_balloons / total_balloons) * 100) if total_balloons > 0 else 0
            total_pages_count = len(image_files) if image_files else len(pages_data)

            lines = [
                "# " + "=" * 58,
                f"# VISIONARY STUDIO - ROTEIRO DE TRADUCAO (MODO REVISAO)",
                f"# CAPITULO: {chapter_name}",
                f"# ATUALIZADO EM: {now_str}",
                f"# PROGRESSO: {len(pages_data)}/{total_pages_count} Paginas | {translated_balloons}/{total_balloons} Baloes ({pct}%)",
                "# " + "=" * 58,
                ""
            ]

            if not pages_data:
                lines.append("# Nenhum balao de dialogo detectado ou configurado nas paginas deste capitulo.")
                lines.append("")
            else:
                for page in pages_data:
                    p_idx = page["page_number"]
                    sep = "=" * 50
                    lines.append(sep)
                    lines.append(f"PAGINA {p_idx}: {page['image'].upper()}")
                    lines.append(sep)
                    lines.append("")

                    if not page["balloons"]:
                        lines.append("# [Página sem falas / Sem texto detectado]")
                        lines.append("")
                    else:
                        for b_idx, b in enumerate(page["balloons"], 1):
                            bid = b.get("id")
                            if bid is not None:
                                lines.append(f"# [id: {bid}]")
                            lines.append(f"[EN]: {b['en']}")
                            lines.append(f"[BR]{b['type_tag']}: {b['br']}")
                            lines.append("")

                    lines.append("")

            lines.append("=" * 50)
            lines.append("# FIM DO CAPITULO")
            lines.append("=" * 50)
            lines.append("")

            content_str = "\n".join(lines)

            # 1. Salva atomicamente na pasta do capítulo (Fonte Única da Verdade)
            local_txt = os.path.join(norm_dir, f"{chapter_name}.txt")
            write_success = atomic_write_text(local_txt, content_str, encoding="utf-8")

            if not write_success:
                import sys
                print(f"[txt_sync] AVISO: Falha ao salvar roteiro atomicamente em '{local_txt}'", file=sys.stderr)

            # Remove arquivo _letrista.txt obsoleto se existir na pasta para não poluir
            old_letrista = os.path.join(norm_dir, f"{chapter_name}_letrista.txt")
            if os.path.exists(old_letrista):
                try:
                    os.remove(old_letrista)
                except Exception:
                    pass

            # 2. Se target_lib_dir foi explicitamente fornecido, salva lá também
            if target_lib_dir and os.path.isdir(target_lib_dir):
                target_file = os.path.join(target_lib_dir, f"{chapter_name}.txt")
                atomic_write_text(target_file, content_str, encoding="utf-8")

            return {
                "success": write_success or os.path.exists(local_txt),
                "path": local_txt,
                "library_path": local_txt,
                "pages_count": len(pages_data),
                "balloons_count": total_balloons,
                "translated_count": translated_balloons
            }

        except Exception as e:
            import traceback
            return {"success": False, "error": str(e), "trace": traceback.format_exc()}
