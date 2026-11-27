"""
Utilitários de Segurança e Sanitização do Sistema de Arquivos (Windows/Cross-Platform).

Protege o Visionary Studio contra:
1. Caracteres ilegais para nomes de arquivos no NTFS/FAT32/exFAT (< > : " / \\ | ? *).
2. Nomes de dispositivos reservados do DOS/Windows (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
3. Espaços ou pontos finais à direita que causam travamento de API no Windows.
4. Nomes de arquivos excessivamente longos que violam MAX_PATH (255 caracteres por componente).
5. Vulnerabilidades de Path Traversal (../ ou caminhos absolutos forçados).
"""

import os
import re
from typing import Optional


# Caracteres estritamente proibidos em nomes de arquivos/pastas no Windows
_WINDOWS_ILLEGAL_CHARS_REGEX = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Dispositivos de sistema reservados pelo DOS/Windows
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}


def sanitize_filename(name: str, replacement: str = "_", max_length: int = 255, fallback: str = "unnamed") -> str:
    """
    Higieniza um nome de arquivo para torná-lo 100% seguro em qualquer sistema operacional,
    com foco rigoroso nas restrições de NTFS e da API Win32 do Windows.

    Exemplos:
        "Capítulo 01: O Início" -> "Capítulo 01_ O Início"
        "Quem é você?"          -> "Quem é você_"
        "CON.txt"               -> "_CON_.txt"
        "Capítulo 1/2"          -> "Capítulo 1_2"
        "Volume 1. "            -> "Volume 1"
    """
    if not name or not isinstance(name, str):
        return fallback

    # 1. Substitui barras e caracteres ilegais pelo replacement
    clean = _WINDOWS_ILLEGAL_CHARS_REGEX.sub(replacement, name)

    # 2. Compacta múltiplos replacements consecutivos (ex: "___" -> "_")
    if replacement:
        double_rep = replacement + replacement
        while double_rep in clean:
            clean = clean.replace(double_rep, replacement)

    # 3. No Windows, arquivos e pastas NÃO podem terminar com espaço ou ponto
    clean = clean.strip(" .")

    if not clean:
        return fallback

    # 4. Trata nomes reservados do Windows (com ou sem extensão)
    stem, ext = os.path.splitext(clean)
    if not stem or (replacement and stem == replacement):
        clean = f"{fallback}{ext}" if ext else fallback
        stem, ext = os.path.splitext(clean)

    if stem.upper() in _WINDOWS_RESERVED_NAMES:
        clean = f"_{stem}_{ext}"
        stem, ext = os.path.splitext(clean)

    # 5. Limita o tamanho máximo a 255 caracteres preservando a extensão
    if len(clean) > max_length:
        if ext:
            allowed_stem_len = max(1, max_length - len(ext))
            clean = f"{stem[:allowed_stem_len].rstrip(' .')}{ext}"
        else:
            clean = clean[:max_length].rstrip(" .")

    return clean if clean else fallback


def is_safe_filename(name: str) -> bool:
    """
    Verifica se um nome de arquivo é estritamente seguro para uso no Windows
    sem risco de erro de API de filesystem.
    """
    if not name or not isinstance(name, str):
        return False
    if len(name) > 255:
        return False
    if _WINDOWS_ILLEGAL_CHARS_REGEX.search(name):
        return False
    if name.endswith(" ") or name.endswith("."):
        return False
    stem = os.path.splitext(name)[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        return False
    return True


def safe_join(base_dir: str, *paths: str) -> Optional[str]:
    """
    Une caminhos com segurança garantindo que o destino final permaneça
    estritamente dentro do `base_dir` fornecido (prevenção contra Path Traversal).
    Retorna o caminho normalizado absoluto se for seguro, ou None se tentar escapar.
    """
    if not base_dir:
        return None
    try:
        abs_base = os.path.realpath(os.path.abspath(base_dir))
        joined = os.path.join(abs_base, *paths)
        abs_target = os.path.realpath(os.path.abspath(joined))

        # Deve ser igual ou filho do base_dir
        if abs_target == abs_base:
            return abs_target
        prefix = abs_base if abs_base.endswith(os.sep) else abs_base + os.sep
        if abs_target.startswith(prefix):
            return abs_target
        return None
    except Exception:
        return None


def send_to_trash(file_path: str) -> bool:
    """
    Envia um arquivo para a Lixeira do sistema (Recycle Bin) via send2trash ou SHFileOperationW (shell32.dll).
    NUNCA executa exclusão física permanente (os.remove / shutil.rmtree) como fallback silencioso.
    Levanta RuntimeError se a operação de envio para a Lixeira falhar.
    """
    if not file_path or not os.path.exists(file_path):
        return False

    # 1. Tenta biblioteca send2trash se disponível no ambiente
    try:
        import send2trash as _s2t
        _s2t.send2trash(os.path.abspath(file_path))
        if not os.path.exists(file_path):
            return True
    except ImportError:
        pass
    except Exception as exc:
        if os.name != "nt":
            raise RuntimeError(
                f"Não foi possível mover o arquivo para a Lixeira com segurança (exclusão permanente bloqueada): {file_path}"
            ) from exc

    # 2. API nativa Win32 (SHFileOperationW com FOF_ALLOWUNDO)
    if os.name == "nt":
        last_err = None
        try:
            import ctypes
            from ctypes import wintypes

            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.WORD),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR),
                ]

            FO_DELETE = 0x0003
            FOF_ALLOWUNDO = 0x0040       # Envia para a Lixeira (Recycle Bin)
            FOF_NOCONFIRMATION = 0x0010  # Não exibe diálogo de confirmação do Windows
            FOF_SILENT = 0x0004          # Não exibe animação de progresso do Windows
            FOF_NOERRORUI = 0x0400       # Silencia caixas de diálogo nativas de erro

            # A API SHFileOperationW requer terminação dupla por caractere nulo ('\0\0')
            abs_path = os.path.abspath(file_path) + "\0\0"
            fileop = SHFILEOPSTRUCTW()
            fileop.hwnd = None
            fileop.wFunc = FO_DELETE
            fileop.pFrom = abs_path
            fileop.pTo = None
            fileop.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI

            ret = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(fileop))
            if ret == 0 and not fileop.fAnyOperationsAborted and not os.path.exists(file_path):
                return True
            last_err = f"SHFileOperationW retornou código {ret} (aborted={bool(fileop.fAnyOperationsAborted)})"
        except Exception as exc:
            last_err = str(exc)

        raise RuntimeError(
            f"Não foi possível mover o arquivo para a Lixeira do Windows ({last_err}). "
            f"Exclusão física permanente bloqueada por segurança: {file_path}"
        )

    raise RuntimeError(
        f"Envio para a Lixeira indisponível neste sistema operacional. "
        f"Exclusão física permanente bloqueada por segurança: {file_path}"
    )

