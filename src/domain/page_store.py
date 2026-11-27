import copy
import json
import os
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.utils.json_utils import dump_compact_map
from src.utils.file_resilience import resilient_read_json

_UNSET = object()

LEGACY_STAGE_SUFFIXES = (
    "_map_translated.json",
    "_ptbr.json",
    "_ocr.json",
    "_map_ocr.json",
    "_map_clean.json",
    "_map_layout.json",
)

SATELLITE_SUFFIXES = (
    "_panels.json",
    "_strokes.json",
    "_map_backup.json",
) + LEGACY_STAGE_SUFFIXES


class PageStore:
    """
    Repositório centralizado para persistência de páginas (Envelope Único v2)
    com cache de metadados em RAM invalidado por (st_mtime_ns, st_size).

    Formato canônico em disco (`output/{base}_map.json`):
    {
        "version": 2,
        "boxes": [...],
        "panels": [...],
        "backup": null | [...]
    }
    """

    SCHEMA_VERSION = 2
    MAX_CACHE_ENTRIES = 512
    _cache_lock = threading.RLock()
    # key: normcase(map_path) -> (mtime_ns, size, summary_dict)
    _summary_cache: Dict[str, Tuple[int, int, Dict[str, Any]]] = {}
    # key: normcase(source_path) -> (mtime_ns, size, record_dict)
    _record_cache: Dict[str, Tuple[int, int, Dict[str, Any]]] = {}

    @classmethod
    def _store_bounded_cache(
        cls,
        cache_dict: Dict[str, Any],
        norm_key: str,
        value: Any,
    ) -> None:
        """Armazena entrada em cache LRU simples limitado a `MAX_CACHE_ENTRIES` (requer `_cache_lock`)."""
        cache_dict.pop(norm_key, None)
        cache_dict[norm_key] = value
        while len(cache_dict) > cls.MAX_CACHE_ENTRIES:
            oldest_key = next(iter(cache_dict))
            cache_dict.pop(oldest_key, None)

    @classmethod
    def invalidate_cache(cls, path: Optional[str] = None) -> None:
        """Invalida o cache em RAM de uma página específica ou de todo o repositório."""
        with cls._cache_lock:
            if not path:
                cls._summary_cache.clear()
                cls._record_cache.clear()
                return
            norm = os.path.normcase(os.path.abspath(path))
            cls._summary_cache.pop(norm, None)
            cls._record_cache.pop(norm, None)
            try:
                resolved = cls.resolve_map_path(path, prefer_existing=True)
                if resolved:
                    norm_resolved = os.path.normcase(os.path.abspath(resolved))
                    cls._summary_cache.pop(norm_resolved, None)
                    cls._record_cache.pop(norm_resolved, None)
            except Exception:
                pass

    @staticmethod
    def extract_boxes(raw_data: Any) -> List[Dict[str, Any]]:
        """Extrai a lista de balões (`boxes`) tanto do envelope v2 (dict) quanto do formato legado v1 (list)."""
        if isinstance(raw_data, list):
            return [b for b in raw_data if isinstance(b, dict)]
        if isinstance(raw_data, dict):
            boxes = raw_data.get("boxes")
            if isinstance(boxes, list):
                return [b for b in boxes if isinstance(b, dict)]
        return []

    @staticmethod
    def extract_panels(raw_data: Any) -> List[Dict[str, Any]]:
        """Extrai a lista de painéis (`panels`) de um envelope v2 ou lista direta."""
        if isinstance(raw_data, dict):
            panels = raw_data.get("panels")
            if isinstance(panels, list):
                return [
                    p for p in panels
                    if isinstance(p, dict) and p.get("label") != "text_bubble" and not p.get("is_bubble")
                ]
        elif isinstance(raw_data, list):
            # Se for uma lista direta (ex: satélite legado _panels.json), só aceita se não for balão de fala
            return [
                p for p in raw_data
                if isinstance(p, dict) and p.get("label") != "text_bubble" and not p.get("is_bubble") and not p.get("ocr_raw")
            ]
        return []

    @classmethod
    def extract_backup(cls, raw_data: Any) -> Optional[List[Dict[str, Any]]]:
        """Extrai o snapshot de backup (`backup`) de um envelope v2."""
        if isinstance(raw_data, dict) and "backup" in raw_data:
            bkp = raw_data.get("backup")
            if isinstance(bkp, list):
                return [b for b in bkp if isinstance(b, dict)]
            if isinstance(bkp, dict) and isinstance(bkp.get("boxes"), list):
                return [b for b in bkp["boxes"] if isinstance(b, dict)]
        return None

    @classmethod
    def normalize_record(
        cls,
        raw_data: Any,
        panels: Optional[List[Dict[str, Any]]] = None,
        backup: Any = _UNSET,
    ) -> Dict[str, Any]:
        """Normaliza qualquer estrutura bruta (v1 list ou v2 dict) para o envelope canônico v2."""
        boxes = cls.extract_boxes(raw_data)
        norm_panels = panels if panels is not None else cls.extract_panels(raw_data)
        norm_backup = cls.extract_backup(raw_data) if backup is _UNSET else backup
        return {
            "version": cls.SCHEMA_VERSION,
            "boxes": boxes,
            "panels": norm_panels,
            "backup": norm_backup,
        }

    @staticmethod
    def _split_folder_and_base(image_or_map_path: str) -> Tuple[str, str, bool]:
        """
        Retorna (chapter_folder, base_name, is_already_in_output_dir)
        a partir do caminho de uma imagem ou de um arquivo JSON de página.
        """
        norm_path = os.path.normpath(image_or_map_path)
        parent_dir = os.path.dirname(norm_path)
        filename = os.path.basename(norm_path)
        lower_name = filename.lower()

        is_json = lower_name.endswith(".json")
        if is_json:
            base = filename[:-5]
            for suffix in ("_map",) + tuple(s[:-5] for s in SATELLITE_SUFFIXES):
                if base.lower().endswith(suffix):
                    base = base[: -len(suffix)]
                    break
        else:
            base = os.path.splitext(filename)[0]

        in_output = os.path.basename(parent_dir).lower() == "output"
        chapter_folder = os.path.dirname(parent_dir) if in_output else parent_dir
        return chapter_folder, base, in_output

    @classmethod
    def resolve_map_path(
        cls,
        image_or_map_path: str,
        prefer_existing: bool = True,
    ) -> str:
        """
        Resolve o caminho canônico de `{base}_map.json` para uma página.
        Prioriza `output/{base}_map.json`, mas respeita `{base}_map.json` na raiz
        se a pasta for portátil (sem subpasta `output`).
        """
        if not image_or_map_path or not isinstance(image_or_map_path, str):
            return ""
        chapter_folder, base, in_output = cls._split_folder_and_base(image_or_map_path)
        output_dir = os.path.join(chapter_folder, "output")
        output_map = os.path.join(output_dir, f"{base}_map.json")
        root_map = os.path.join(chapter_folder, f"{base}_map.json")

        if in_output:
            return output_map

        if prefer_existing:
            if os.path.exists(output_map):
                return output_map
            if os.path.exists(root_map):
                return root_map

        return output_map

    @classmethod
    def find_existing_source_path(cls, image_or_map_path: str) -> Optional[str]:
        """
        Localiza o arquivo JSON primário existente para a página (priorizando `_map.json`,
        com fallback para arquivos legados de estágio caso ainda não migrados).
        """
        if not image_or_map_path or not isinstance(image_or_map_path, str):
            return None
        chapter_folder, base, in_output = cls._split_folder_and_base(image_or_map_path)
        search_dirs = (
            [os.path.join(chapter_folder, "output")]
            if in_output
            else [os.path.join(chapter_folder, "output"), chapter_folder]
        )

        # 1. Prioridade absoluta: _map.json
        for d in search_dirs:
            candidate = os.path.join(d, f"{base}_map.json")
            if os.path.exists(candidate):
                return candidate

        # 2. Fallback para estágios legados (apenas se forem arquivos reais no disco)
        for suffix in LEGACY_STAGE_SUFFIXES:
            for d in search_dirs:
                candidate = os.path.join(d, f"{base}{suffix}")
                if os.path.isfile(candidate):
                    return candidate

        return None

    @classmethod
    def _read_satellite_list(cls, chapter_folder: str, base: str, suffix: str) -> Optional[List[Dict[str, Any]]]:
        """Lê um arquivo satélite legado (`_panels.json`, `_map_backup.json`) se existir em disco."""
        for d in (os.path.join(chapter_folder, "output"), chapter_folder):
            sat_path = os.path.join(d, f"{base}{suffix}")
            if os.path.isfile(sat_path):
                try:
                    raw = resilient_read_json(sat_path, default=None)
                    if isinstance(raw, list):
                        return [item for item in raw if isinstance(item, dict)]
                    if isinstance(raw, dict) and isinstance(raw.get("boxes"), list):
                        return [item for item in raw["boxes"] if isinstance(item, dict)]
                except Exception:
                    pass
        return None

    @classmethod
    def _cleanup_legacy_satellites(cls, chapter_folder: str, base: str, keep_map_path: str) -> None:
        """Remove arquivos satélites obsoletos após consolidação no envelope v2."""
        norm_keep = os.path.normcase(os.path.abspath(keep_map_path))
        for d in (os.path.join(chapter_folder, "output"), chapter_folder):
            for suffix in SATELLITE_SUFFIXES:
                sat_path = os.path.join(d, f"{base}{suffix}")
                if os.path.normcase(os.path.abspath(sat_path)) == norm_keep:
                    continue
                if os.path.isfile(sat_path):
                    try:
                        os.remove(sat_path)
                    except OSError:
                        pass

    @classmethod
    def _has_legacy_satellites(cls, chapter_folder: str, base: str) -> bool:
        for d in (os.path.join(chapter_folder, "output"), chapter_folder):
            for suffix in ("_panels.json", "_map_backup.json"):
                if os.path.isfile(os.path.join(d, f"{base}{suffix}")):
                    return True
        return False

    @classmethod
    def load_page_record(cls, image_or_map_path: str) -> Dict[str, Any]:
        """
        Carrega o registro completo da página no formato v2:
        `{"version": 2, "boxes": [...], "panels": [...], "backup": ...}`
        Utiliza cache em RAM validado por `(st_mtime_ns, st_size)` com cópia defensiva
        e absorve transparentemente arquivos v1 (`[...]`) e satélites legados (`_panels.json`, `_map_backup.json`).
        """
        empty_record = cls.normalize_record([], panels=[], backup=None)
        if not image_or_map_path or not isinstance(image_or_map_path, str) or "\0" in image_or_map_path:
            return empty_record

        chapter_folder, base, _ = cls._split_folder_and_base(image_or_map_path)
        source_path = cls.find_existing_source_path(image_or_map_path)
        has_satellites = cls._has_legacy_satellites(chapter_folder, base)

        norm_key: Optional[str] = None
        st_info: Optional[Tuple[int, int]] = None

        if source_path and os.path.exists(source_path):
            norm_key = os.path.normcase(os.path.abspath(source_path))
            try:
                st = os.stat(source_path)
                st_info = (st.st_mtime_ns, st.st_size)
            except OSError:
                st_info = None

            if st_info is not None and not has_satellites:
                with cls._cache_lock:
                    cached = cls._record_cache.get(norm_key)
                    if cached and cached[0] == st_info[0] and cached[1] == st_info[1]:
                        cls._store_bounded_cache(cls._record_cache, norm_key, cached)
                        return copy.deepcopy(cached[2])

        raw_data: Any = []
        if source_path and os.path.exists(source_path):
            try:
                raw_data = resilient_read_json(source_path, default=[])
            except Exception:
                raw_data = []

        record = cls.normalize_record(raw_data)

        # Absorção transparente de satélites legados caso o envelope ainda não os possua
        if not record["panels"] and has_satellites:
            sat_panels = cls._read_satellite_list(chapter_folder, base, "_panels.json")
            if sat_panels is not None:
                record["panels"] = sat_panels

        if record["backup"] is None and has_satellites:
            sat_backup = cls._read_satellite_list(chapter_folder, base, "_map_backup.json")
            if sat_backup is not None:
                record["backup"] = sat_backup

        if norm_key and st_info is not None and not has_satellites:
            with cls._cache_lock:
                cls._store_bounded_cache(
                    cls._record_cache,
                    norm_key,
                    (st_info[0], st_info[1], copy.deepcopy(record)),
                )

        return record

    @classmethod
    def load_boxes(cls, image_or_map_path: str) -> List[Dict[str, Any]]:
        """Retorna apenas a lista de balões (`boxes`) da página."""
        return cls.load_page_record(image_or_map_path)["boxes"]

    @classmethod
    def load_boxes_from_source(cls, json_path: str) -> List[Dict[str, Any]]:
        """
        Carrega `boxes` diretamente de um caminho JSON já resolvido (ex: `_map.json` ou `.json` portátil),
        aproveitando o `_record_cache` em O(1) validado por `(st_mtime_ns, st_size)`.
        """
        if not json_path or not isinstance(json_path, str) or not os.path.exists(json_path):
            return []

        norm_key = os.path.normcase(os.path.abspath(json_path))
        st_info: Optional[Tuple[int, int]] = None
        try:
            st = os.stat(json_path)
            st_info = (st.st_mtime_ns, st.st_size)
        except OSError:
            st_info = None

        if st_info is not None:
            with cls._cache_lock:
                cached = cls._record_cache.get(norm_key)
                if cached and cached[0] == st_info[0] and cached[1] == st_info[1]:
                    cls._store_bounded_cache(cls._record_cache, norm_key, cached)
                    return copy.deepcopy(cached[2]["boxes"])

        raw_data = resilient_read_json(json_path, default=[])
        record = cls.normalize_record(raw_data)

        if st_info is not None:
            chapter_folder, base, _ = cls._split_folder_and_base(json_path)
            if not cls._has_legacy_satellites(chapter_folder, base):
                with cls._cache_lock:
                    cls._store_bounded_cache(
                        cls._record_cache,
                        norm_key,
                        (st_info[0], st_info[1], copy.deepcopy(record)),
                    )

        return record["boxes"]

    @classmethod
    def save_page_record(
        cls,
        image_or_map_path: str,
        boxes: Optional[List[Dict[str, Any]]] = None,
        panels: Optional[List[Dict[str, Any]]] = None,
        backup: Any = _UNSET,
        target_map_path: Optional[str] = None,
        dump_fn: Optional[Callable[[Any, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Salva atomicamente o envelope v2 completo em `{base}_map.json`, preservando as seções
        não informadas, removendo arquivos satélites legados e atualizando o cache em RAM.
        """
        existing = cls.load_page_record(image_or_map_path)
        record = {
            "version": cls.SCHEMA_VERSION,
            "boxes": boxes if boxes is not None else existing["boxes"],
            "panels": panels if panels is not None else existing["panels"],
            "backup": existing["backup"] if backup is _UNSET else backup,
        }

        map_path = target_map_path or cls.resolve_map_path(image_or_map_path, prefer_existing=True)
        out_dir = os.path.dirname(map_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        writer = dump_fn or dump_compact_map
        writer(record, map_path)

        chapter_folder, base, _ = cls._split_folder_and_base(image_or_map_path)
        cls._cleanup_legacy_satellites(chapter_folder, base, keep_map_path=map_path)
        try:
            from src.utils.file_resilience import cleanup_orphaned_tmp_files
            if out_dir:
                cleanup_orphaned_tmp_files(out_dir, max_age_seconds=300.0)
        except Exception:
            pass
        cls._update_cache_from_record(map_path, record)
        return record

    @classmethod
    def save_boxes(
        cls,
        image_or_map_path: str,
        boxes: List[Dict[str, Any]],
        target_map_path: Optional[str] = None,
        dump_fn: Optional[Callable[[Any, str], None]] = None,
    ) -> Dict[str, Any]:
        """Atalho para salvar/atualizar apenas `boxes` mantendo `panels` e `backup`."""
        return cls.save_page_record(
            image_or_map_path,
            boxes=boxes,
            target_map_path=target_map_path,
            dump_fn=dump_fn,
        )

    @staticmethod
    def compute_summary_from_record(record: Dict[str, Any], file_exists: bool = True) -> Dict[str, Any]:
        """Calcula os indicadores rápidos de progresso da página a partir de um registro v2."""
        if not file_exists:
            return {
                "has_layout": False,
                "has_ocr": False,
                "has_translation": False,
                "block_count": 0,
                "has_backup": False,
            }

        boxes = record.get("boxes") if isinstance(record, dict) else (record if isinstance(record, list) else [])
        if not isinstance(boxes, list):
            boxes = []

        block_count = len(boxes)
        has_layout = True
        if block_count == 0:
            # Página com 0 balões após detecção é considerada completa em OCR/Tradução para não travar a fila
            has_ocr = True
            has_translation = True
        else:
            has_ocr = any(bool((b.get("text") or "").strip()) for b in boxes if isinstance(b, dict))
            has_translation = any(
                bool((b.get("translated_text") or b.get("translated") or "").strip())
                for b in boxes
                if isinstance(b, dict)
            )

        backup = record.get("backup") if isinstance(record, dict) else None
        has_backup = isinstance(backup, list)

        return {
            "has_layout": has_layout,
            "has_ocr": has_ocr,
            "has_translation": has_translation,
            "block_count": block_count,
            "has_backup": has_backup,
        }

    @classmethod
    def _update_cache_from_record(cls, map_path: str, record: Dict[str, Any]) -> None:
        if not map_path:
            return
        norm_key = os.path.normcase(os.path.abspath(map_path))
        try:
            st = os.stat(map_path)
            summary = cls.compute_summary_from_record(record, file_exists=True)
            with cls._cache_lock:
                cls._store_bounded_cache(cls._summary_cache, norm_key, (st.st_mtime_ns, st.st_size, summary))
                cls._store_bounded_cache(
                    cls._record_cache,
                    norm_key,
                    (st.st_mtime_ns, st.st_size, copy.deepcopy(record)),
                )
        except OSError:
            with cls._cache_lock:
                cls._summary_cache.pop(norm_key, None)
                cls._record_cache.pop(norm_key, None)

    @classmethod
    def get_page_summary(cls, image_or_map_path: str) -> Dict[str, Any]:
        """
        Retorna os indicadores da página (`has_layout`, `has_ocr`, `has_translation`, `block_count`, `has_backup`)
        usando cache em RAM validado por `(st_mtime_ns, st_size)`.
        Se o arquivo não mudou no disco, retorna em O(1) sem `json.load`.
        """
        source_path = cls.find_existing_source_path(image_or_map_path)
        if not source_path or not os.path.exists(source_path):
            return cls.compute_summary_from_record({}, file_exists=False)

        chapter_folder, base, _ = cls._split_folder_and_base(image_or_map_path)
        has_legacy_bkp = any(
            os.path.isfile(os.path.join(d, f"{base}_map_backup.json"))
            for d in (os.path.join(chapter_folder, "output"), chapter_folder)
        )

        norm_key = os.path.normcase(os.path.abspath(source_path))
        st_info: Optional[Tuple[int, int]] = None
        try:
            st = os.stat(source_path)
            st_info = (st.st_mtime_ns, st.st_size)
        except OSError:
            st_info = None

        if st_info is not None and not has_legacy_bkp:
            with cls._cache_lock:
                cached = cls._summary_cache.get(norm_key)
                if cached and cached[0] == st_info[0] and cached[1] == st_info[1]:
                    return dict(cached[2])

        record = cls.load_page_record(image_or_map_path)
        summary = cls.compute_summary_from_record(record, file_exists=True)
        if has_legacy_bkp:
            summary["has_backup"] = True

        if st_info is not None:
            with cls._cache_lock:
                cls._store_bounded_cache(cls._summary_cache, norm_key, (st_info[0], st_info[1], dict(summary)))

        return summary

    # =========================================================================
    # Backup Management (Snapshot embutido no Envelope v2)
    # =========================================================================

    @classmethod
    def check_backup(cls, image_or_map_path: str) -> bool:
        """Verifica se a página possui um snapshot de backup salvo no envelope ou em satélite legado."""
        if not image_or_map_path or not isinstance(image_or_map_path, str) or "\0" in image_or_map_path:
            return False
        summary = cls.get_page_summary(image_or_map_path)
        return bool(summary.get("has_backup"))

    @classmethod
    def create_backup(
        cls,
        image_or_map_path: str,
        dump_fn: Optional[Callable[[Any, str], None]] = None,
    ) -> bool:
        """Cria um ponto de restauração dos `boxes` atuais dentro da chave `backup` do envelope v2."""
        source_path = cls.find_existing_source_path(image_or_map_path)
        if not source_path or not os.path.exists(source_path):
            return False
        record = cls.load_page_record(image_or_map_path)
        snapshot = copy.deepcopy(record["boxes"])
        cls.save_page_record(
            image_or_map_path,
            backup=snapshot,
            target_map_path=source_path if source_path.lower().endswith("_map.json") else None,
            dump_fn=dump_fn,
        )
        return True

    @classmethod
    def restore_backup(
        cls,
        image_or_map_path: str,
        dump_fn: Optional[Callable[[Any, str], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Restaura `boxes` a partir do snapshot `backup` do envelope v2 (ou satélite legado)."""
        source_path = cls.find_existing_source_path(image_or_map_path)
        if not source_path or not os.path.exists(source_path):
            return None
        record = cls.load_page_record(image_or_map_path)
        if record["backup"] is None:
            return None
        restored_boxes = copy.deepcopy(record["backup"])
        return cls.save_page_record(
            image_or_map_path,
            boxes=restored_boxes,
            backup=record["backup"],
            target_map_path=source_path if source_path.lower().endswith("_map.json") else None,
            dump_fn=dump_fn,
        )

    @classmethod
    def delete_backup(
        cls,
        image_or_map_path: str,
        dump_fn: Optional[Callable[[Any, str], None]] = None,
    ) -> bool:
        """Remove o snapshot `backup` do envelope v2 e qualquer arquivo `_map_backup.json` residual."""
        source_path = cls.find_existing_source_path(image_or_map_path)
        if not source_path or not os.path.exists(source_path):
            return False
        record = cls.load_page_record(image_or_map_path)
        cls.save_page_record(
            image_or_map_path,
            backup=None,
            target_map_path=source_path if source_path.lower().endswith("_map.json") else None,
            dump_fn=dump_fn,
        )
        return True
