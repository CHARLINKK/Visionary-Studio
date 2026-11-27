import os
import json
import uuid
import time
import stat
import threading
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("visionary.reorder")

JOURNAL_FILENAME = ".visionary_reorder_journal.json"

_folder_locks: Dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()


def _get_folder_lock(norm_folder: str) -> threading.Lock:
    with _locks_mutex:
        canonical = os.path.normcase(norm_folder)
        if canonical not in _folder_locks:
            _folder_locks[canonical] = threading.Lock()
        return _folder_locks[canonical]


def safe_rename(src: str, dst: str, max_retries: int = 5, retry_delay: float = 0.05) -> None:
    """
    Atomically renames src to dst (using os.replace).
    Retries on transient Windows file lock errors (antivirus, search indexer, thumbnailer)
    and removes Windows ReadOnly file flags if necessary.
    """
    if not os.path.exists(src):
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {src}")

    dst_dir = os.path.dirname(dst)
    if dst_dir and not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)

    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            os.replace(src, dst)
            return
        except (PermissionError, OSError) as e:
            last_err = e
            # Tentar remover atributo ReadOnly no Windows
            try:
                os.chmod(src, stat.S_IWRITE)
                if os.path.exists(dst):
                    os.chmod(dst, stat.S_IWRITE)
            except Exception:
                pass
            time.sleep(retry_delay * (attempt + 1))

    if last_err is not None:
        raise last_err


def _find_associated_files(folder_path: str, sorted_bases: List[str]) -> Dict[str, List[Dict[str, str]]]:
    """
    Scans root, output/, and output/crops/ to locate all auxiliary
    files (.json maps, balloon crops) mapped to each base name.
    Matches are resolved against sorted_bases (longest prefix first) to eliminate
    ambiguity between names like '1' and '1_A' or '10'.
    """
    associated_by_base: Dict[str, List[Dict[str, str]]] = {b: [] for b in sorted_bases}

    def match_base(filename: str, require_json_only: bool = False) -> Optional[tuple]:
        if filename.startswith('.'):
            return None
        if require_json_only and not filename.lower().endswith('.json'):
            return None

        for base in sorted_bases:
            if filename.startswith(base) and filename != base:
                suffix = filename[len(base):]
                if suffix.startswith('_') or suffix.startswith('.'):
                    return base, suffix
        return None

    # 1. Root folder (JSON files only - scripts like .txt are explicitly ignored)
    try:
        root_entries = os.listdir(folder_path)
    except Exception:
        root_entries = []

    for f in root_entries:
        full_p = os.path.join(folder_path, f)
        if os.path.isfile(full_p):
            matched = match_base(f, require_json_only=True)
            if matched:
                b, s = matched
                associated_by_base[b].append({
                    "sub_dir": folder_path,
                    "filename": f,
                    "suffix": s
                })

    # Subdirectories to scan for artifacts
    out_dir = os.path.join(folder_path, 'output')
    subdirs_to_scan = []
    if os.path.isdir(out_dir):
        subdirs_to_scan.append(out_dir)
        crops_dir = os.path.join(out_dir, 'crops')
        if os.path.isdir(crops_dir):
            subdirs_to_scan.append(crops_dir)

    for s_dir in subdirs_to_scan:
        try:
            entries = os.listdir(s_dir)
        except Exception:
            entries = []

        for f in entries:
            full_p = os.path.join(s_dir, f)
            if os.path.isfile(full_p):
                matched = match_base(f, require_json_only=False)
                if matched:
                    b, s = matched
                    associated_by_base[b].append({
                        "sub_dir": s_dir,
                        "filename": f,
                        "suffix": s
                    })

    return associated_by_base


def plan_reorder(folder_path: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates input parameters and prepares a complete transactional rename plan.
    Each file (main image and associated files) receives an original, temp, and final path.
    Pre-flight checks verify that:
      - All source files exist.
      - No unexpected foreign file occupies any target final path.
    """
    norm_folder = os.path.normpath(os.path.abspath(folder_path))
    if not os.path.isdir(norm_folder):
        raise ValueError(f"Diretório não encontrado: {folder_path}")

    if not files:
        return {
            "run_id": "",
            "folder_path": norm_folder,
            "digits": 3,
            "entries": []
        }

    # Validate file objects
    seen_paths = set()
    for idx, f in enumerate(files):
        if not isinstance(f, dict) or "name" not in f or "path" not in f:
            raise ValueError(f"Entrada inválida de arquivo no índice {idx}")
        p = os.path.normpath(f["path"])
        if os.path.normcase(os.path.dirname(p)) != os.path.normcase(norm_folder):
            raise ValueError(f"O arquivo {p} não pertence à pasta do capítulo: {norm_folder}")
        if p in seen_paths:
            raise ValueError(f"Caminho duplicado na lista de reordenação: {p}")
        seen_paths.add(p)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Arquivo não encontrado: {p}")

    run_id = uuid.uuid4().hex[:8]
    digits = max(3, len(str(len(files))))

    all_bases = [os.path.splitext(f['name'])[0] for f in files]
    sorted_bases = sorted(all_bases, key=len, reverse=True)

    associated_map = _find_associated_files(norm_folder, sorted_bases)

    entries = []
    planned_originals = set()

    for i, f in enumerate(files):
        orig_path = os.path.normpath(f['path'])
        ext = os.path.splitext(f['name'])[1]
        old_base = os.path.splitext(f['name'])[0]

        temp_base = f"__temp_visionary_{run_id}_{i:04d}"
        temp_name = f"{temp_base}{ext}"
        temp_path = os.path.normpath(os.path.join(norm_folder, temp_name))

        new_base = f"{i + 1:0{digits}d}"
        new_name = f"{new_base}{ext}"
        new_path = os.path.normpath(os.path.join(norm_folder, new_name))

        entries.append({
            "original": orig_path,
            "temp": temp_path,
            "final": new_path
        })
        planned_originals.add(orig_path)

        # Associated files for this base
        for assoc in associated_map.get(old_base, []):
            a_orig = os.path.normpath(os.path.join(assoc["sub_dir"], assoc["filename"]))
            a_temp = os.path.normpath(os.path.join(assoc["sub_dir"], temp_base + assoc["suffix"]))
            a_final = os.path.normpath(os.path.join(assoc["sub_dir"], new_base + assoc["suffix"]))

            entries.append({
                "original": a_orig,
                "temp": a_temp,
                "final": a_final
            })
            planned_originals.add(a_orig)

    # Pre-flight check: ensure no foreign file occupies any final path (canonized with normcase for Windows)
    planned_originals_canonical = {os.path.normcase(orig) for orig in planned_originals}
    for e in entries:
        final_p = e["final"]
        if os.path.exists(final_p) and os.path.normcase(final_p) not in planned_originals_canonical:
            raise FileExistsError(
                f"O arquivo de destino já existe e não faz parte da reordenação: {final_p}"
            )

    return {
        "run_id": run_id,
        "folder_path": norm_folder,
        "digits": digits,
        "entries": entries
    }


def write_journal(folder_path: str, plan: Dict[str, Any]) -> str:
    """
    Atomically writes the journal file to disk with fsync before any file modification.
    """
    journal_path = os.path.join(folder_path, JOURNAL_FILENAME)
    temp_journal = journal_path + ".tmp"

    data = {
        "version": 1,
        "run_id": plan["run_id"],
        "folder_path": plan["folder_path"],
        "created_at": time.time(),
        "entries": plan["entries"]
    }

    with open(temp_journal, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_journal, journal_path)
    return journal_path


def rollback_transaction(folder_path: str, entries: List[Dict[str, str]], journal_path: Optional[str] = None) -> None:
    """
    Executes transactional rollback:
    Step 1: Move any files currently at 'final' back to 'temp'.
    Step 2: Move all files at 'temp' back to 'original'.
    Step 3: Remove the journal file.
    """
    if not journal_path:
        journal_path = os.path.join(folder_path, JOURNAL_FILENAME)

    # Step 1: files at final -> temp
    for e in entries:
        try:
            if os.path.exists(e["final"]) and not os.path.exists(e["temp"]):
                safe_rename(e["final"], e["temp"])
        except Exception as err:
            logger.error("Falha ao mover arquivo final de volta para temp no rollback: %s -> %s (%s)", e["final"], e["temp"], err)

    # Step 2: files at temp -> original
    for e in reversed(entries):
        try:
            if os.path.exists(e["temp"]):
                safe_rename(e["temp"], e["original"])
        except Exception as err:
            logger.error("Falha ao restaurar arquivo temp para original no rollback: %s -> %s (%s)", e["temp"], e["original"], err)

    # Step 3: Remove journal
    try:
        if os.path.exists(journal_path):
            os.remove(journal_path)
    except Exception as err:
        logger.warning("Falha ao remover journal após rollback: %s (%s)", journal_path, err)

    try:
        from src.domain.page_store import PageStore
        PageStore.invalidate_cache()
    except Exception:
        pass

    try:
        from src.utils.txt_sync import sync_chapter_txt
        sync_chapter_txt(folder_path)
    except Exception:
        pass


def recover_reorder_if_needed(folder_path: str) -> Dict[str, Any]:
    """
    Checks if an interrupted reorder journal exists in folder_path.
    If found:
      - If all files are already at their final paths, finalizes and cleans the journal.
      - Otherwise, executes a rollback to restore all files to their original state.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return {"recovered": False}

    journal_path = os.path.join(folder_path, JOURNAL_FILENAME)
    if not os.path.isfile(journal_path):
        # Also clean up any orphan .tmp journal
        tmp_journal = journal_path + ".tmp"
        if os.path.isfile(tmp_journal):
            try:
                os.remove(tmp_journal)
            except Exception:
                pass
        return {"recovered": False}

    try:
        with open(journal_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Journal corrompido ou ilegível em %s: %s", journal_path, e)
        return {"recovered": False, "error": f"Journal corrompido: {e}"}

    entries = data.get("entries", [])
    if not entries:
        try:
            os.remove(journal_path)
        except Exception:
            pass
        return {"recovered": False}

    # Case A: Check if all files are already at final
    all_final = all(
        os.path.exists(e["final"]) and not os.path.exists(e["temp"])
        for e in entries
    )

    if all_final:
        try:
            os.remove(journal_path)
        except Exception:
            pass
        try:
            from src.utils.txt_sync import sync_chapter_txt
            sync_chapter_txt(folder_path)
        except Exception:
            pass
        return {"recovered": True, "action": "finalized"}

    # Case B: Incomplete reorder -> Rollback to original
    rollback_transaction(folder_path, entries, journal_path)
    return {"recovered": True, "action": "rolled_back"}


def execute_reorder(folder_path: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Performs a 2-phase transactional reordering with automatic rollback and journal persistence.
    Protected by per-folder non-blocking concurrency locks.
    """
    norm_folder = os.path.normpath(os.path.abspath(folder_path)) if folder_path else ""
    if not norm_folder or not os.path.isdir(norm_folder):
        return {"success": False, "error": "Folder not found"}

    folder_lock = _get_folder_lock(norm_folder)
    if not folder_lock.acquire(blocking=False):
        return {"success": False, "error": "Uma reordenação já está em andamento nesta pasta."}

    try:
        # Auto-recover any previous crash before starting
        recover_reorder_if_needed(norm_folder)

        if not files:
            return {"success": True}

        plan = plan_reorder(norm_folder, files)
        entries = plan["entries"]
        if not entries:
            return {"success": True}

        journal_path = write_journal(norm_folder, plan)

        # Phase 1: Rename original -> temp
        try:
            for e in entries:
                safe_rename(e["original"], e["temp"])
        except Exception as e:
            rollback_transaction(norm_folder, entries, journal_path)
            return {"success": False, "error": f"Erro na Fase 1 (Original -> Temp): {e}"}

        # Phase 2: Rename temp -> final
        try:
            for e in entries:
                safe_rename(e["temp"], e["final"])
        except Exception as e:
            rollback_transaction(norm_folder, entries, journal_path)
            return {"success": False, "error": f"Erro na Fase 2 (Temp -> Final): {e}"}

        # Success: Delete journal
        try:
            if os.path.exists(journal_path):
                os.remove(journal_path)
        except Exception:
            pass

        try:
            from src.domain.page_store import PageStore
            PageStore.invalidate_cache()
        except Exception:
            pass

        # Sync chapter script
        try:
            from src.utils.txt_sync import sync_chapter_txt
            sync_chapter_txt(norm_folder)
        except Exception:
            pass

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        folder_lock.release()
