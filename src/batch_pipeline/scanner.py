import os
import re
import json

VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".avif"}


def natural_sort_key(s: str):
    """Gera chave de ordenação alfanumérica natural para nomes de arquivos (ex: 1, 2, 10)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', os.path.basename(s))]


def get_natural_sorted_images(input_dir: str, files_list=None):
    """Resolve o diretório de entrada e retorna a lista de imagens suportadas
    ordenadas pelo padrão alfanumérico natural."""
    resolved_input_dir = input_dir
    if files_list:
        image_paths = [f for f in files_list if os.path.isfile(f) and os.path.splitext(f)[1].lower() in VALID_EXTENSIONS]
    elif os.path.isfile(input_dir):
        image_paths = [input_dir]
        resolved_input_dir = os.path.dirname(input_dir)
    elif os.path.isdir(input_dir):
        image_paths = []
        for file in os.listdir(input_dir):
            if os.path.splitext(file)[1].lower() in VALID_EXTENSIONS:
                image_paths.append(os.path.join(input_dir, file))
    else:
        image_paths = []

    image_paths.sort(key=natural_sort_key)
    return resolved_input_dir, image_paths


def filter_cached_images(image_paths: list, output_dir: str, overwrite=False, only_layout=False, resume_from_layout=False):
    """Aplica o algoritmo de Smart Skip: checa mtime da imagem vs map.json e
    avalia o status de layout, OCR e tradução para evitar retrabalho de processamento."""
    if overwrite:
        return list(image_paths)

    images_to_process = []
    for img_path in image_paths:
        base = os.path.splitext(os.path.basename(img_path))[0]
        map_path = os.path.join(output_dir, base + "_map.json")

        if os.path.exists(map_path):
            try:
                img_mtime = os.path.getmtime(img_path)
                map_mtime = os.path.getmtime(map_path)
                if img_mtime > map_mtime:
                    print(f" [CACHE] Página {base}: imagem original foi modificada recentemente. Reprocessando...")
                    images_to_process.append(img_path)
                    continue
            except Exception:
                pass

            try:
                from src.domain.page_store import PageStore
                with open(map_path, 'r', encoding='utf-8') as f:
                    raw_json = json.load(f)
                    data = PageStore.extract_boxes(raw_json)
                    has_boxes = len(data) > 0
                    has_ocr = any(b.get('text', '').strip() for b in data) if has_boxes else False
                    has_trans = any(b.get('translated_text', '').strip() for b in data) if has_boxes else False

                    if only_layout:
                        print(f" [CACHE] Página {base}: layout já existente e atualizado (pulando).")
                        continue
                    elif resume_from_layout:
                        if has_ocr or has_trans:
                            print(f" [CACHE] Página {base}: já processada com OCR/Tradução (pulando).")
                            continue
                        if not has_boxes:
                            print(f" [INFO] Página {base}: sem balões de fala mapeados (pulando etapa).")
                            continue
                    else:
                        if has_ocr or has_trans or not has_boxes:
                            print(f" [CACHE] Página {base}: já processada e atualizada (pulando).")
                            continue
            except Exception:
                pass
        else:
            if resume_from_layout:
                print(f" [AVISO] Página {base}: arquivo de layout não encontrado (pulando).")
                continue

        images_to_process.append(img_path)

    return images_to_process
