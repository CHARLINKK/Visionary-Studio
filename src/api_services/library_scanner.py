"""
Gerenciador Especializado de Varredura, Indexação e Descoberta de Capítulos.
Responsável pela localização física de diretórios de capítulos no disco, filtragem de scripts
válidos (.txt), cálculo de estatísticas de balões/pendências e descoberta em múltiplos níveis.
"""

import os
import re


class LibraryScanner:
    """
    Controlador isolado para descoberta e resolução de arquivos de roteiro e pastas de capítulos.
    """

    VALID_IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.avif')

    @staticmethod
    def is_valid_script_txt(fname: str, fpath: str = None) -> bool:
        """Verifica se o nome de arquivo e caminho correspondem a um roteiro válido de capítulo."""
        lower = fname.lower()
        if not lower.endswith(".txt"):
            return False
        if lower.endswith(("_letrista.txt", "_clean.txt", "_limpo.txt")):
            return False
        if "_map_" in lower or lower.startswith(('_', '.', 'studio_test_', 'test_', 'tmp', 'temp')):
            return False
        if lower in ("requirements.txt", "license.txt", "readme.txt", "todo.txt", "output.txt"):
            return False
        if fpath:
            parts = [p.lower() for p in os.path.normpath(fpath).split(os.sep)]
            if "output" in parts or "limpos" in parts or "temp_in" in parts:
                return False
        return True

    _stats_cache = {}
    _chapter_dir_cache = {}

    @classmethod
    def _dir_has_images(cls, dir_path: str) -> bool:
        """Verifica em O(1) via os.scandir se o diretório contém ao menos uma imagem válida."""
        if not dir_path or not os.path.isdir(dir_path):
            return False
        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    if not entry.name.startswith('.') and entry.name.lower().endswith(cls.VALID_IMAGE_EXTS):
                        if entry.is_file():
                            return True
        except Exception:
            pass
        return False

    @classmethod
    def inspect_file_stats(cls, file_path: str, stat_info=None) -> dict:
        """Lê um arquivo de roteiro e extrai contagem de balões, pendências e status com cache mtime/size."""
        try:
            norm_p = os.path.normpath(file_path)
            if stat_info is None:
                stat_info = os.stat(norm_p)
            cache_key = (norm_p, stat_info.st_mtime_ns, stat_info.st_size)
            if cache_key in cls._stats_cache:
                return cls._stats_cache[cache_key]

            balloon_count = 0
            pending_count = 0
            with open(norm_p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    trimmed = line.strip()
                    if not trimmed or trimmed.startswith(('#', '=', '-')):
                        continue
                    if trimmed.startswith(('[BR]', '[PT]')):
                        balloon_count += 1
                        val = re.sub(r'^\[(?:BR|PT)\](?:\s*\([^)]+\))?:?\s*', '', trimmed, flags=re.IGNORECASE).strip()
                        if not val or val == '[PENDENTE]':
                            pending_count += 1
                    elif (trimmed.startswith('[') and ']' in trimmed and (trimmed.endswith(':') or ':' in trimmed)):
                        prefix = trimmed.split(']')[0].lstrip('[')
                        if prefix.isdigit():
                            balloon_count += 1
                            raw_val = trimmed.split(']', 1)[1].lstrip(':').strip()
                            tag_match = re.match(r'^\([^)]+\)\s*:?\s*(.*)$', raw_val)
                            val = tag_match.group(1).strip() if tag_match else raw_val
                            if not val or val == '[PENDENTE]':
                                pending_count += 1
            status = "complete" if (balloon_count > 0 and pending_count == 0) else ("pending" if pending_count > 0 else "ready")
            res = {
                "balloonCount": balloon_count,
                "pendingCount": pending_count,
                "status": status
            }
            if len(cls._stats_cache) > 1024:
                cls._stats_cache.clear()
            cls._stats_cache[cache_key] = res
            return res
        except Exception:
            return {"balloonCount": 0, "pendingCount": 0, "status": "unknown"}

    def register_file(self, file_path: str, files_map: dict, is_local: bool = False, stat_info=None):
        """Registra um arquivo no mapa de roteiros se for válido, reaproveitando stat_info do scandir."""
        try:
            name = os.path.basename(file_path)
            if not self.is_valid_script_txt(name, file_path):
                return
            stat = stat_info if stat_info is not None else os.stat(file_path)
            key = name.lower()
            if key not in files_map or is_local:
                norm_p = os.path.normpath(file_path)
                stats = self.inspect_file_stats(norm_p, stat_info=stat)
                chapter_dir = self._chapter_dir_cache.get(norm_p)
                if not chapter_dir or not os.path.isdir(chapter_dir):
                    chapter_dir = os.path.normpath(
                        self.resolve_chapter_dir(norm_p) or os.path.dirname(norm_p)
                    )
                    if len(self._chapter_dir_cache) > 1024:
                        self._chapter_dir_cache.clear()
                    self._chapter_dir_cache[norm_p] = chapter_dir

                files_map[key] = {
                    "name": name,
                    "path": norm_p,
                    "chapter_dir": chapter_dir,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime * 1000,
                    "isLocal": is_local,
                    "balloonCount": stats["balloonCount"],
                    "pendingCount": stats["pendingCount"],
                    "status": stats["status"]
                }
        except Exception:
            pass

    def scan_directory(self, root_dir: str, files_map: dict, current_depth: int = 0, max_depth: int = 3):
        """Varre recursivamente diretórios locais respeitando limites de profundidade e blacklist."""
        if current_depth > max_depth or not root_dir or not os.path.exists(root_dir) or not os.path.isdir(root_dir):
            return
        try:
            with os.scandir(root_dir) as entries:
                for entry in entries:
                    try:
                        if entry.is_file():
                            if self.is_valid_script_txt(entry.name, entry.path):
                                self.register_file(entry.path, files_map, is_local=True, stat_info=entry.stat())
                        elif entry.is_dir():
                            d_lower = entry.name.lower()
                            if d_lower in ("node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", "library", "output", "limpos", "temp_in"):
                                continue
                            if not d_lower.startswith(('.', '_')):
                                self.scan_directory(entry.path, files_map, current_depth + 1, max_depth)
                    except Exception:
                        continue
        except Exception:
            pass

    def list_library_files(self, current_path: str = None) -> dict:
        """
        Descobre todos os arquivos de roteiro nos diretórios de trabalho ativos,
        pastas irmãs de capítulos, pasta base configurada e biblioteca central legada.
        """
        try:
            from src.config import Config
            files_map = {}

            # 1. Verifica workspace ativo e capítulos irmãos
            if not current_path or not os.path.exists(current_path):
                current_path = Config.get("last_opened_folder", "")

            if current_path and os.path.exists(current_path):
                if os.path.isdir(current_path):
                    try:
                        with os.scandir(current_path) as entries:
                            for entry in entries:
                                if entry.is_file():
                                    self.register_file(entry.path, files_map, is_local=True, stat_info=entry.stat())
                    except Exception:
                        pass

                    parent_dir = os.path.dirname(os.path.normpath(current_path))
                    if parent_dir and os.path.exists(parent_dir) and os.path.isdir(parent_dir):
                        self.scan_directory(parent_dir, files_map, current_depth=0, max_depth=2)
                else:
                    parent_dir = os.path.dirname(os.path.normpath(current_path))
                    if parent_dir and os.path.exists(parent_dir):
                        self.scan_directory(parent_dir, files_map, current_depth=0, max_depth=2)

            # 2. Verifica baseFolder configurada nas preferências do usuário
            base_folder = Config.get("baseFolder", "")
            if base_folder and os.path.exists(base_folder) and os.path.isdir(base_folder):
                self.scan_directory(base_folder, files_map, current_depth=0, max_depth=3)

            # 3. Verifica pasta central library (fallback)
            lib_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'library'))
            if os.path.exists(lib_dir):
                try:
                    with os.scandir(lib_dir) as entries:
                        for entry in entries:
                            if entry.is_file() and self.is_valid_script_txt(entry.name):
                                if entry.name.lower() not in files_map:
                                    self.register_file(entry.path, files_map, is_local=False, stat_info=entry.stat())
                except Exception:
                    pass

            files = list(files_map.values())
            return {"success": True, "files": sorted(files, key=lambda x: x["name"])}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def resolve_chapter_dir(self, script_path: str, current_path: str = None) -> str:
        """Resolve o diretório físico do capítulo em disco que contém as imagens e pasta output/."""
        clean_path = os.path.normpath(str(script_path))
        parent_dir = os.path.dirname(clean_path) if (os.path.isfile(clean_path) or clean_path.lower().endswith(".txt")) else clean_path

        if self._dir_has_images(parent_dir):
            return parent_dir

        base_name = os.path.splitext(os.path.basename(clean_path))[0]
        from src.config import Config
        last_opened = Config.get("last_opened_folder", "")
        candidate_roots = [
            current_path,
            os.path.dirname(os.path.normpath(current_path)) if current_path and os.path.exists(current_path) else None,
            last_opened,
            os.path.dirname(os.path.normpath(last_opened)) if last_opened and os.path.exists(last_opened) else None,
            Config.get("baseFolder", "")
        ]
        for c_root in candidate_roots:
            if not c_root or not os.path.exists(c_root):
                continue
            if os.path.basename(os.path.normpath(c_root)).lower() == base_name.lower():
                if self._dir_has_images(c_root):
                    return c_root
            sub = os.path.join(c_root, base_name)
            if self._dir_has_images(sub):
                return sub

        return parent_dir if (parent_dir and os.path.isdir(parent_dir)) else None
