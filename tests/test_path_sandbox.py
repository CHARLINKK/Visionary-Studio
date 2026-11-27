"""
Testes do sandbox de leitura de /api/image (src/utils/path_sandbox.py).

Todos os testes usam `tmp_path`; o Config aponta para o settings.json temporário da sessão
(ver conftest.py), então nenhum dado real do usuário é lido ou gravado.
"""

import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api_services.fs_service import FileSystemService
from src.api_services.image_service import ImageService
from src.config import Config
from src.server import app
from src.utils import path_sandbox
from src.utils.path_sandbox import (
    FORMAT_NOT_PERMITTED,
    INVALID_PATH,
    OUTSIDE_AUTHORIZED_FOLDERS,
    ImageReadDenied,
    authorize_image_read,
    is_path_allowed,
    is_too_broad,
    register_root,
)

client = TestClient(app)

PNG = b"\x89PNG\r\n\x1a\n"


def _make_image(folder, name="page.png"):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(PNG)
    return path


def _get(path):
    return client.get("/api/image", params={"path": str(path)})


@pytest.fixture
def config_folders():
    """Isola baseFolder/last_opened_folder do Config temporário e restaura ao final."""
    keys = ("baseFolder", "last_opened_folder")
    before = {key: Config.get(key, "") for key in keys}
    yield Config
    Config.update(before)


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redireciona a pasta do usuário para dentro de tmp_path."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    return home


# ── Raízes registradas ────────────────────────────────────────────────────────

def test_file_inside_registered_root_is_allowed(tmp_path):
    chapter = tmp_path / "chapter"
    image = _make_image(chapter)
    assert register_root(str(chapter)) is True
    assert is_path_allowed(str(image)) is True


def test_nested_output_folders_are_covered(tmp_path):
    chapter = tmp_path / "chapter"
    _make_image(chapter)
    crop = _make_image(chapter / "output" / "crops", "crop_01.png")
    register_root(str(chapter))
    assert is_path_allowed(str(crop)) is True


def test_file_outside_every_root_is_denied(tmp_path):
    chapter = tmp_path / "chapter"
    _make_image(chapter)
    outside = _make_image(tmp_path / "outside")
    register_root(str(chapter))
    assert is_path_allowed(str(outside)) is False


def test_sibling_folder_with_shared_prefix_is_denied(tmp_path):
    """`cap1` não pode autorizar `cap10`: a comparação é por componente, não por prefixo de texto."""
    cap1 = tmp_path / "cap1"
    cap10 = tmp_path / "cap10"
    _make_image(cap1)
    sibling_image = _make_image(cap10)
    register_root(str(cap1))
    assert is_path_allowed(str(sibling_image)) is False


def test_dotdot_traversal_out_of_root_is_denied(tmp_path):
    chapter = tmp_path / "chapter"
    _make_image(chapter)
    secret = _make_image(tmp_path / "private", "secret.png")
    register_root(str(chapter))
    sneaky = os.path.join(str(chapter), "..", "private", "secret.png")
    assert os.path.isfile(sneaky)
    assert is_path_allowed(sneaky) is False
    assert is_path_allowed(str(secret)) is False


@pytest.mark.skipif(os.name != "nt", reason="Comparação case-insensitive é específica do Windows")
def test_root_match_is_case_insensitive_on_windows(tmp_path):
    chapter = tmp_path / "Chapter"
    image = _make_image(chapter)
    register_root(str(chapter))
    assert is_path_allowed(str(image).swapcase()) is True


def test_symlink_pointing_outside_root_is_denied(tmp_path):
    chapter = tmp_path / "chapter"
    _make_image(chapter)
    secret = _make_image(tmp_path / "private", "secret.png")
    link = chapter / "innocent.png"
    target_check = str(link)
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        if os.name == "nt":
            try:
                import _winapi
                private_dir = str(tmp_path / "private")
                junction_dir = str(chapter / "junction_secret")
                _winapi.CreateJunction(private_dir, junction_dir)
                target_check = os.path.join(junction_dir, "secret.png")
            except (OSError, AttributeError):
                pytest.skip("Criar symlinks/junções exige privilégio ou suporte do filesystem neste ambiente")
        else:
            pytest.skip("Criar symlinks exige privilégio/Developer Mode neste ambiente")
    register_root(str(chapter))
    assert is_path_allowed(target_check) is False


# ── Raízes recusadas ──────────────────────────────────────────────────────────

def test_register_root_rejects_missing_folder_and_regular_file(tmp_path):
    image = _make_image(tmp_path / "chapter")
    assert register_root(str(tmp_path / "does_not_exist")) is False
    assert register_root(str(image)) is False
    assert register_root("") is False
    assert register_root(None) is False


def test_register_root_rejects_drive_root():
    drive_root = os.path.abspath(os.sep)
    assert register_root(drive_root) is False
    assert is_too_broad(os.path.normcase(os.path.realpath(drive_root))) is True


def test_register_root_rejects_home_and_its_ancestors(tmp_path, fake_home):
    manga = fake_home / "Manga"
    manga.mkdir()
    assert register_root(str(fake_home)) is False, "a pasta do usuário é ampla demais"
    assert register_root(str(tmp_path)) is False, "ancestral da pasta do usuário é ampla demais"
    assert register_root(str(manga)) is True, "uma subpasta específica do usuário é válida"


def test_register_root_rejects_system_folder(tmp_path, monkeypatch):
    fake_windows = tmp_path / "FakeWindows"
    (fake_windows / "Web").mkdir(parents=True)
    monkeypatch.setenv("SystemRoot", str(fake_windows))
    assert register_root(str(fake_windows)) is False
    assert register_root(str(fake_windows / "Web")) is False


def test_runtime_registry_is_capped_and_drops_the_oldest(tmp_path, monkeypatch):
    monkeypatch.setattr(path_sandbox, "_MAX_RUNTIME_ROOTS", 2)
    folders = []
    for index in range(3):
        folder = tmp_path / f"root{index}"
        folder.mkdir()
        folders.append(folder)
        assert register_root(str(folder)) is True
    assert is_path_allowed(str(folders[0] / "x.png")) is False
    assert is_path_allowed(str(folders[1] / "x.png")) is True
    assert is_path_allowed(str(folders[2] / "x.png")) is True


# ── Raízes derivadas do Config e da biblioteca ────────────────────────────────

def test_base_folder_from_config_is_authorized(tmp_path, config_folders):
    base = tmp_path / "library_base"
    image = _make_image(base / "series" / "chapter")
    config_folders.update({"baseFolder": str(base), "last_opened_folder": ""})
    assert is_path_allowed(str(image)) is True


def test_last_opened_folder_and_its_parent_are_authorized(tmp_path, config_folders):
    series = tmp_path / "series"
    opened = series / "chapter_02"
    sibling_image = _make_image(series / "chapter_01")
    opened_image = _make_image(opened)
    config_folders.update({"baseFolder": "", "last_opened_folder": str(opened)})
    assert is_path_allowed(str(opened_image)) is True
    assert is_path_allowed(str(sibling_image)) is True, "capítulos irmãos aparecem na Biblioteca"


def test_parent_of_last_opened_folder_is_ignored_when_too_broad(tmp_path, config_folders, fake_home):
    """Se o pai do capítulo for a pasta do usuário, ele NÃO vira raiz (só o próprio capítulo)."""
    opened = fake_home / "chapter"
    opened_image = _make_image(opened)
    other_image = _make_image(fake_home / "Pictures", "holiday.png")
    config_folders.update({"baseFolder": "", "last_opened_folder": str(opened)})
    assert is_path_allowed(str(opened_image)) is True
    assert is_path_allowed(str(other_image)) is False


def test_drive_root_as_base_folder_does_not_authorize_the_whole_drive(tmp_path, config_folders):
    config_folders.update({"baseFolder": os.path.abspath(os.sep), "last_opened_folder": ""})
    outside = _make_image(tmp_path / "somewhere")
    assert is_path_allowed(str(outside)) is False


def test_central_library_folder_is_authorized(tmp_path, monkeypatch):
    library = tmp_path / "library_dir"
    image = _make_image(library)
    other = _make_image(tmp_path / "elsewhere")
    assert is_path_allowed(str(image)) is False, "sem a raiz da biblioteca nada é servido"
    monkeypatch.setattr(path_sandbox, "_LIBRARY_DIR", str(library))
    path_sandbox._canonical_root.cache_clear()
    assert is_path_allowed(str(image)) is True
    assert is_path_allowed(str(other)) is False


# ── Integração com o endpoint /api/image ──────────────────────────────────────

def test_endpoint_serves_authorized_image_with_nosniff(tmp_path):
    chapter = tmp_path / "chapter"
    image = _make_image(chapter)
    register_root(str(chapter))
    response = _get(image)
    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["x-content-type-options"] == "nosniff"


def test_endpoint_denies_image_outside_roots(tmp_path):
    outside = _make_image(tmp_path / "personal_photos", "family.jpg")
    response = _get(outside)
    assert response.status_code == 403


def test_endpoint_does_not_leak_existence_outside_roots(tmp_path):
    """Arquivo existente e inexistente fora do sandbox devem ser indistinguíveis (ambos 403)."""
    existing = _make_image(tmp_path / "personal_photos", "family.jpg")
    missing = tmp_path / "personal_photos" / "never_existed.jpg"
    assert _get(existing).status_code == 403
    assert _get(missing).status_code == 403


def test_endpoint_blocks_dotdot_traversal(tmp_path):
    chapter = tmp_path / "chapter"
    _make_image(chapter)
    _make_image(tmp_path / "private", "secret.png")
    register_root(str(chapter))
    sneaky = os.path.join(str(chapter), "..", "private", "secret.png")
    assert _get(sneaky).status_code == 403


def test_endpoint_rejects_svg_even_inside_root(tmp_path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    svg = chapter / "vector.svg"
    svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>")
    register_root(str(chapter))
    assert _get(svg).status_code == 403


def test_endpoint_rejects_non_image_extension_inside_root(tmp_path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    secrets = chapter / "settings.json"
    secrets.write_text("{}")
    register_root(str(chapter))
    assert _get(secrets).status_code == 403


def test_endpoint_returns_404_for_missing_file_inside_root(tmp_path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    register_root(str(chapter))
    assert _get(chapter / "missing.png").status_code == 404


def test_endpoint_null_byte_never_serves_files_nor_crashes(tmp_path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    outside = _make_image(tmp_path / "private", "secret.png")
    register_root(str(chapter))

    # Truncamento: APIs em C param no NUL, então `<fora>\0<dentro>.png` poderia abrir `<fora>`.
    truncation = str(outside) + "\x00" + str(chapter / "ok.png")
    response = client.get("/api/image", params={"path": truncation})
    assert response.status_code in (400, 403)

    # Byte nulo dentro da raiz: continua dentro do sandbox e o arquivo não existe -> nunca 200/500.
    inside = client.get("/api/image", params={"path": str(chapter / "a\x00.png")})
    assert inside.status_code in (400, 403, 404)


# ── Integração com o explorador (list_directory registra raízes) ──────────────

def test_list_directory_authorizes_folder_that_contains_images(tmp_path):
    chapter = tmp_path / "series" / "chapter"
    image = _make_image(chapter)
    crop = _make_image(chapter / "output" / "crops", "crop_01.png")

    assert _get(image).status_code == 403, "antes de abrir a pasta nada é servido"

    result = FileSystemService().list_directory(str(chapter))
    assert result["success"] is True
    assert _get(image).status_code == 200
    assert _get(crop).status_code == 200


def test_list_directory_of_folder_without_images_authorizes_nothing(tmp_path):
    """Navegar por uma pasta intermediária (só subpastas) não pode liberar as imagens abaixo dela."""
    series = tmp_path / "series"
    image = _make_image(series / "chapter")

    result = FileSystemService().list_directory(str(series))
    assert result["success"] is True
    assert _get(image).status_code == 403

    FileSystemService().list_directory(str(series / "chapter"))
    assert _get(image).status_code == 200


# ── Política única: authorize_image_read ──────────────────────────────────────

def test_authorize_image_read_returns_resolved_path_for_allowed_image(tmp_path):
    chapter = tmp_path / "chapter"
    image = _make_image(chapter)
    register_root(str(chapter))
    resolved = authorize_image_read(str(image))
    assert os.path.normcase(resolved) == os.path.normcase(os.path.realpath(str(image)))


def test_authorize_image_read_reports_the_reason_for_each_denial(tmp_path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    outside = _make_image(tmp_path / "private", "secret.png")
    config_file = chapter / "settings.json"
    config_file.write_text("{}")
    register_root(str(chapter))

    with pytest.raises(ImageReadDenied) as wrong_format:
        authorize_image_read(str(config_file))
    assert wrong_format.value.reason == FORMAT_NOT_PERMITTED

    with pytest.raises(ImageReadDenied) as outside_root:
        authorize_image_read(str(outside))
    assert outside_root.value.reason == OUTSIDE_AUTHORIZED_FOLDERS

    with pytest.raises(ImageReadDenied) as invalid:
        authorize_image_read(None)
    assert invalid.value.reason == INVALID_PATH


# ── RPC base64 (ImageService) não pode ser uma segunda porta de leitura ───────

@pytest.mark.parametrize("method", ["get_image_base64", "get_image_base64_full"])
def test_image_service_reads_image_inside_authorized_root(tmp_path, method):
    chapter = tmp_path / "chapter"
    image = _make_image(chapter)
    register_root(str(chapter))
    result = getattr(ImageService(), method)(str(image))
    assert result["success"] is True
    assert result["data_url"].startswith("data:image/")


@pytest.mark.parametrize("method", ["get_image_base64", "get_image_base64_full"])
def test_image_service_denies_image_outside_authorized_roots(tmp_path, method):
    outside = _make_image(tmp_path / "personal_photos", "family.jpg")
    result = getattr(ImageService(), method)(str(outside))
    assert result["success"] is False
    assert "data_url" not in result


@pytest.mark.parametrize("method", ["get_image_base64", "get_image_base64_full"])
def test_image_service_does_not_leak_existence_outside_roots(tmp_path, method):
    """Fora do sandbox, arquivo existente e inexistente devem produzir a MESMA resposta, sem eco do caminho."""
    existing = _make_image(tmp_path / "personal_photos", "family.jpg")
    missing = tmp_path / "personal_photos" / "never_existed.jpg"
    service = getattr(ImageService(), method)
    assert service(str(existing)) == service(str(missing))
    assert "personal_photos" not in service(str(existing))["error"]


@pytest.mark.parametrize("method", ["get_image_base64", "get_image_base64_full"])
def test_image_service_refuses_non_image_files_even_inside_root(tmp_path, method):
    """Antes do sandbox o fallback devolvia os bytes de QUALQUER arquivo como data URL."""
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    secret = chapter / "settings.json"
    secret.write_text('{"token": "segredo"}')
    svg = chapter / "vector.svg"
    svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    register_root(str(chapter))
    service = getattr(ImageService(), method)
    for blocked in (secret, svg):
        result = service(str(blocked))
        assert result["success"] is False
        assert "data_url" not in result


@pytest.mark.parametrize("method", ["get_image_base64", "get_image_base64_full"])
def test_image_service_blocks_dotdot_traversal(tmp_path, method):
    chapter = tmp_path / "chapter"
    _make_image(chapter)
    _make_image(tmp_path / "private", "secret.png")
    register_root(str(chapter))
    sneaky = os.path.join(str(chapter), "..", "private", "secret.png")
    assert os.path.isfile(sneaky)
    assert getattr(ImageService(), method)(sneaky)["success"] is False


def test_image_service_resolves_relative_path_against_current_path_then_authorizes(tmp_path):
    chapter = tmp_path / "chapter"
    _make_image(chapter)
    register_root(str(chapter))
    service = ImageService(api_bridge=SimpleNamespace(current_path=str(chapter)))
    assert service.get_image_base64_full("page.png")["success"] is True
    assert service.get_image_base64_full(os.path.join("..", "page.png"))["success"] is False


def test_image_service_returns_not_found_for_missing_file_inside_root(tmp_path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    register_root(str(chapter))
    result = ImageService().get_image_base64_full(str(chapter / "missing.png"))
    assert result["success"] is False
    assert "não encontrado" in result["error"]


def test_image_service_symlink_pointing_outside_root_is_denied(tmp_path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    secret = _make_image(tmp_path / "private", "secret.png")
    link = chapter / "innocent.png"
    target_check = str(link)
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        if os.name == "nt":
            try:
                import _winapi
                private_dir = str(tmp_path / "private")
                junction_dir = str(chapter / "junction_secret")
                _winapi.CreateJunction(private_dir, junction_dir)
                target_check = os.path.join(junction_dir, "secret.png")
            except (OSError, AttributeError):
                pytest.skip("Criar symlinks/junções exige privilégio ou suporte do filesystem neste ambiente")
        else:
            pytest.skip("Criar symlinks exige privilégio/Developer Mode neste ambiente")
    register_root(str(chapter))
    assert ImageService().get_image_base64_full(target_check)["success"] is False
