"""
Sandbox de leitura de arquivos locais servidos pela API (ex.: `/api/image`).

Problema que resolve: sem restrição de raiz, qualquer caminho absoluto com extensão de imagem
(fotos pessoais, screenshots, downloads) podia ser lido por quem alcançasse o endpoint.

Modelo: um caminho só é servido se, depois de resolvido (symlinks/junctions/`..`), estiver DENTRO
de alguma "raiz autorizada". As raízes autorizadas vêm de três fontes:

1. Pasta `library/` central do projeto (fallback legado do scanner de roteiros).
2. Pastas já escolhidas pelo usuário nas configurações: `baseFolder`, `last_opened_folder` e a
   pasta-pai de `last_opened_folder` (capítulos irmãos exibidos na Biblioteca).
3. Registro em memória (`register_root`), alimentado quando o usuário navega até uma pasta que
   contém imagens (`FileSystemService.list_directory`). Navegar por pastas sem imagens não autoriza
   nada.

Raízes "largas demais" (raiz de unidade, pasta do usuário e seus ancestrais, Windows, Program Files)
são sempre recusadas: autorizar `C:\\` equivaleria a não ter sandbox.

DEPENDÊNCIA DE SEGURANÇA: o registro de raízes é alcançável via RPC (`list_directory`, `saveSettings`).
Este módulo só é uma barreira de verdade porque a API exige o token de sessão (`session_auth`): sem
ele, qualquer chamador local poderia registrar a pasta que quisesse e depois lê-la. Em modo dev
(`VISIONARY_DEV_NO_AUTH=1`) essa garantia não existe.
"""

import logging
import os
import threading
from functools import lru_cache

_logger = logging.getLogger("visionary.path_sandbox")

_PROJECT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_LIBRARY_DIR = os.path.join(_PROJECT_DIR, "library")

# Teto do registro em memória: evita crescimento ilimitado numa sessão muito longa.
# Ao estourar, a raiz registrada há mais tempo é descartada (e volta a ser registrada ao navegar).
_MAX_RUNTIME_ROOTS = 256

_runtime_roots = {}
_lock = threading.RLock()


def resolve_real_path(path):
    """
    Caminho absoluto com symlinks/junctions resolvidos e `..` colapsado, preservando a caixa original
    (é este o valor que deve ser aberto/servido). Retorna None se o caminho for inválido (vazio,
    não-string, byte nulo etc.).
    """
    if not path or not isinstance(path, str):
        return None
    try:
        return os.path.realpath(os.path.abspath(path))
    except (OSError, ValueError):
        return None


def _canonical(path):
    """
    Forma canônica para COMPARAÇÃO: `resolve_real_path` + normalização de caixa e separadores no
    Windows. Retorna None se o caminho for inválido.
    """
    real = resolve_real_path(path)
    return os.path.normcase(real) if real else None


@lru_cache(maxsize=64)
def _canonical_root(raw_path):
    """Versão memoizada de `_canonical` para raízes vindas do Config (evita I/O repetido em unidades de rede).

    Falha de forma segura: se um junction for reapontado depois do cache, os caminhos reais deixam de
    estar dentro da raiz memoizada e o acesso é negado (nunca ampliado).
    """
    return _canonical(raw_path)


def _is_within(child, parent):
    """True se `child` for `parent` ou estiver dentro dele. Compara por componente, nunca por prefixo cru
    (`...\\cap1` NÃO contém `...\\cap10`)."""
    if child == parent:
        return True
    prefix = parent if parent.endswith(os.sep) else parent + os.sep
    return child.startswith(prefix)


def _protected_locations():
    locations = []
    for env_name in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)"):
        canonical = _canonical(os.environ.get(env_name))
        if canonical:
            locations.append(canonical)
    return locations


def is_too_broad(canonical):
    """True se a raiz candidata autorizaria uma área ampla demais do disco."""
    # Raiz de unidade / de filesystem (`C:\\`, `/`, `\\\\servidor\\share\\`).
    if os.path.dirname(canonical) == canonical:
        return True
    # Pasta do usuário ou qualquer ancestral dela (ex.: `C:\\Users`).
    home = _canonical(os.path.expanduser("~"))
    if home and _is_within(home, canonical):
        return True
    # Dentro de áreas do sistema.
    return any(_is_within(canonical, location) for location in _protected_locations())


def register_root(path):
    """
    Autoriza `path` (e tudo dentro dele) como raiz de leitura pelo restante da sessão.
    Retorna True se a raiz está (ou já estava) autorizada; False se o caminho não é uma pasta existente
    ou é largo demais.
    """
    canonical = _canonical(path)
    if canonical is None or not os.path.isdir(canonical):
        return False
    if is_too_broad(canonical):
        _logger.debug("Raiz recusada por ser ampla demais: %s", path)
        return False
    with _lock:
        if canonical in _runtime_roots:
            return True
        if len(_runtime_roots) >= _MAX_RUNTIME_ROOTS:
            _runtime_roots.pop(next(iter(_runtime_roots)))
        _runtime_roots[canonical] = True
    return True


def clear_runtime_roots():
    """Esvazia o registro em memória e o cache de raízes do Config. Usado por testes."""
    with _lock:
        _runtime_roots.clear()
    _canonical_root.cache_clear()


def _static_roots():
    canonical = _canonical_root(_LIBRARY_DIR)
    return [canonical] if canonical else []


def _config_roots():
    from src.config import Config

    base_folder = Config.get("baseFolder", "") or ""
    last_opened = Config.get("last_opened_folder", "") or ""
    candidates = [base_folder, last_opened]
    if isinstance(last_opened, str) and last_opened.strip():
        candidates.append(os.path.dirname(os.path.normpath(last_opened)))

    roots = []
    for raw in candidates:
        if not isinstance(raw, str) or not raw.strip():
            continue
        canonical = _canonical_root(raw)
        if canonical and not is_too_broad(canonical):
            roots.append(canonical)
    return roots


def get_allowed_roots():
    """Lista (canônica) de todas as raízes atualmente autorizadas."""
    with _lock:
        runtime = list(_runtime_roots)
    return _static_roots() + _config_roots() + runtime


def is_path_allowed(path):
    """True se `path`, depois de resolvido, estiver dentro de alguma raiz autorizada."""
    canonical = _canonical(path)
    if canonical is None:
        return False
    return any(_is_within(canonical, root) for root in get_allowed_roots())


# `.svg` fica de fora de propósito: aberto diretamente no navegador, SVG executa script. A GUI só
# consome páginas raster.
ALLOWED_IMAGE_EXTS = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.avif', '.gif', '.ico'})

INVALID_PATH = "invalid_path"
FORMAT_NOT_PERMITTED = "format_not_permitted"
OUTSIDE_AUTHORIZED_FOLDERS = "outside_authorized_folders"


class ImageReadDenied(Exception):
    """Leitura de imagem negada pela política do sandbox. `reason` é uma das constantes acima."""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


def authorize_image_read(path):
    """
    Política única de leitura de imagens locais (usada pelo endpoint `/api/image` e pelo RPC base64).

    Valida sobre o caminho RESOLVIDO (symlinks/junctions seguidos), nunca sobre o texto cru: um symlink
    `a.png` apontando para `segredo.txt` ou para fora da raiz é negado. Retorna o caminho resolvido, que
    é o único valor que deve ser aberto. Levanta `ImageReadDenied` se a leitura não for permitida.

    A existência do arquivo NÃO é verificada aqui de propósito: o chamador deve checá-la só depois, para
    que fora do sandbox um arquivo existente e um inexistente sejam indistinguíveis.
    """
    real_path = resolve_real_path(path)
    if real_path is None:
        raise ImageReadDenied(INVALID_PATH, "Invalid path")
    if os.path.splitext(real_path)[1].lower() not in ALLOWED_IMAGE_EXTS:
        raise ImageReadDenied(FORMAT_NOT_PERMITTED, "File format not permitted")
    if not is_path_allowed(real_path):
        raise ImageReadDenied(OUTSIDE_AUTHORIZED_FOLDERS, "Path is outside the authorized folders")
    return real_path
