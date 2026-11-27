import os
import pytest
from PIL import Image
from src.api_services.fs_service import FileSystemService


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    """Cria workspace temporário estritamente isolado para testes de I/O de imagens."""
    work_dir = tmp_path / "manga_chapter"
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir = work_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    crops_dir = out_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    return str(work_dir)


def test_split_page_success(temp_workspace):
    """Testa divisão de página dupla em metades A e B com cálculo correto de dimensões e limpeza do original."""
    img_path = os.path.join(temp_workspace, "001.png")
    # Cria imagem de 200 de largura por 100 de altura
    img = Image.new("RGB", (200, 100), color=(255, 0, 0))
    img.save(img_path)

    fs = FileSystemService()
    res = fs.split_page(img_path)

    assert res["success"] is True
    # Imagem mãe deve ter sido removida
    assert not os.path.exists(img_path)

    # Metades A e B devem existir
    right_path = os.path.join(temp_workspace, "001_A.png")
    left_path = os.path.join(temp_workspace, "001_B.png")
    assert os.path.exists(right_path)
    assert os.path.exists(left_path)

    with Image.open(right_path) as r_img:
        assert r_img.size == (100, 100)
    with Image.open(left_path) as l_img:
        assert l_img.size == (100, 100)


def test_split_page_ltr_and_rtl_direction(temp_workspace):
    """Testa que split_page respeita direction='ltr' e 'rtl' mapeando A/B corretamente."""
    fs = FileSystemService()

    # Cria imagem onde lado esquerdo é vermelho (255, 0, 0) e lado direito é azul (0, 0, 255)
    ltr_img_path = os.path.join(temp_workspace, "spread_ltr.png")
    img_ltr = Image.new("RGB", (200, 100), color=(255, 0, 0))
    for x in range(100, 200):
        for y in range(100):
            img_ltr.putpixel((x, y), (0, 0, 255))
    img_ltr.save(ltr_img_path)

    # Divisão LTR: A = Esquerda (vermelho), B = Direita (azul)
    res_ltr = fs.split_page(ltr_img_path, direction="ltr")
    assert res_ltr["success"] is True
    part_a_ltr = os.path.join(temp_workspace, "spread_ltr_A.png")
    part_b_ltr = os.path.join(temp_workspace, "spread_ltr_B.png")

    with Image.open(part_a_ltr) as im_a:
        assert im_a.getpixel((10, 10)) == (255, 0, 0)
    with Image.open(part_b_ltr) as im_b:
        assert im_b.getpixel((10, 10)) == (0, 0, 255)

    # Divisão RTL: A = Direita (azul), B = Esquerda (vermelho)
    rtl_img_path = os.path.join(temp_workspace, "spread_rtl.png")
    img_rtl = Image.new("RGB", (200, 100), color=(255, 0, 0))
    for x in range(100, 200):
        for y in range(100):
            img_rtl.putpixel((x, y), (0, 0, 255))
    img_rtl.save(rtl_img_path)

    res_rtl = fs.split_page(rtl_img_path, direction="rtl")
    assert res_rtl["success"] is True
    part_a_rtl = os.path.join(temp_workspace, "spread_rtl_A.png")
    part_b_rtl = os.path.join(temp_workspace, "spread_rtl_B.png")

    with Image.open(part_a_rtl) as im_a:
        assert im_a.getpixel((10, 10)) == (0, 0, 255)
    with Image.open(part_b_rtl) as im_b:
        assert im_b.getpixel((10, 10)) == (255, 0, 0)


def test_merge_pages_rtl_success(temp_workspace):
    """Testa união horizontal de páginas no modo RTL (mangá) gerando _spread e limpando originais."""
    p1 = os.path.join(temp_workspace, "001.png")
    p2 = os.path.join(temp_workspace, "002.png")

    img1 = Image.new("RGB", (100, 120), color=(255, 255, 255))
    img2 = Image.new("RGB", (100, 120), color=(0, 0, 0))
    img1.save(p1)
    img2.save(p2)

    fs = FileSystemService()
    res = fs.merge_pages(temp_workspace, [p1, p2], direction="rtl")

    assert res["success"] is True
    spread_path = res["newPath"]
    assert os.path.exists(spread_path)
    assert "_spread" in os.path.basename(spread_path)

    # Originais devem ter sido removidos após sucesso
    assert not os.path.exists(p1)
    assert not os.path.exists(p2)

    with Image.open(spread_path) as s_img:
        assert s_img.size == (200, 120)


def test_delete_page_cleans_all_associated_artifacts(temp_workspace):
    """Testa deleção completa de página e todos os artefatos vinculados (crops, JSONs)."""
    img_path = os.path.join(temp_workspace, "005.jpg")
    img = Image.new("RGB", (50, 50), color=(100, 100, 100))
    img.save(img_path)

    out_dir = os.path.join(temp_workspace, "output")
    map_json = os.path.join(out_dir, "005_map.json")
    map_trans = os.path.join(out_dir, "005_map_translated.json")
    with open(map_json, "w", encoding="utf-8") as f: f.write("[]")
    with open(map_trans, "w", encoding="utf-8") as f: f.write("[]")

    crop_file = os.path.join(out_dir, "crops", "005_balao_1.png")
    with open(crop_file, "w", encoding="utf-8") as f: f.write("fake crop")

    fs = FileSystemService()
    res = fs.delete_page(img_path, sync_txt=False)

    assert res["success"] is True
    assert not os.path.exists(img_path)
    assert not os.path.exists(map_json)
    assert not os.path.exists(map_trans)
    assert not os.path.exists(crop_file)
