"""
Testes unitários e matemáticos para o refinamento de polígonos de quadros (OpenCV).
"""

import pytest
import numpy as np
from PIL import Image, ImageDraw
from src.geometry.panels import (
    _line_from_points,
    _intersect_lines,
    _detect_boundary_line,
    _reconcile_panel_gutters,
    refine_panel_polygon,
    refine_panels_to_polygons,
    is_point_in_panel,
    rescue_uncovered_panels,
    split_oversized_panels,
)
from src.batch_pipeline.reading_order import sort_bubbles_reading_order


def test_line_from_points_and_intersection():
    """Valida o cálculo de equações de reta e suas interseções."""
    # Linha vertical x = 100: passando por (100, 0) e (100, 200)
    l_v = _line_from_points((100, 0), (100, 200))
    # Linha horizontal y = 50: passando por (0, 50) e (200, 50)
    l_h = _line_from_points((0, 50), (200, 50))

    inter = _intersect_lines(l_v, l_h)
    assert inter == (100, 50)

    # Linha inclinada y = x: passando por (0, 0) e (100, 100)
    l_diag = _line_from_points((0, 0), (100, 100))
    inter_diag = _intersect_lines(l_diag, l_h)
    assert inter_diag == (50, 50)


def test_intersect_parallel_lines():
    """Valida que retas paralelas retornam None."""
    l1 = _line_from_points((0, 0), (100, 0))
    l2 = _line_from_points((0, 50), (100, 50))
    assert _intersect_lines(l1, l2) is None


def test_detect_boundary_line_on_synthetic_image():
    """Valida detecção de linha com Hough em imagem sintética."""
    # Cria uma imagem 200x200 branca com uma linha preta inclinada
    img = Image.new("L", (200, 200), color=255)
    draw = ImageDraw.Draw(img)
    # Linha preta quase vertical de (50, 10) até (70, 190)
    draw.line([(50, 10), (70, 190)], fill=0, width=4)

    gray_np = np.array(img)
    line = _detect_boundary_line(
        gray_np,
        x_range=(40, 80),
        y_range=(0, 200),
        orientation="vertical",
        min_length_ratio=0.5,
    )
    assert line is not None
    # Verifica que um ponto no meio da linha (60, 100) satisfaz Ax + By + C ~= 0
    A, B, C = line
    dist = abs(A * 60 + B * 100 + C)
    assert dist < 5.0, f"Distância do ponto à linha estimada é muito grande: {dist}"


def test_refine_panel_polygon_orthogonal():
    """Valida que painéis retangulares clássicos mantêm 4 vértices consistentes."""
    img = Image.new("RGB", (1000, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Desenha moldura preta de 100,100 até 500,500
    draw.rectangle([100, 100, 500, 500], outline=0, width=4)

    poly = refine_panel_polygon(img, [100, 100, 500, 500])
    assert len(poly) == 4
    # Top-Left, Top-Right, Bottom-Right, Bottom-Left
    tl, tr, br, bl = poly
    assert abs(tl[0] - 100) <= 5 and abs(tl[1] - 100) <= 5
    assert abs(tr[0] - 500) <= 5 and abs(tr[1] - 100) <= 5
    assert abs(br[0] - 500) <= 5 and abs(br[1] - 500) <= 5
    assert abs(bl[0] - 100) <= 5 and abs(bl[1] - 500) <= 5


def test_refine_panel_polygon_trapezoid():
    """Valida a detecção de calha inclinada (shasen-koma / trapézio)."""
    img = Image.new("RGB", (1000, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Desenha polígono com lado direito inclinado:
    # TL=(100, 100), TR=(450, 100), BR=(550, 600), BL=(100, 600)
    draw.polygon([(100, 100), (450, 100), (550, 600), (100, 600)], outline=0, width=4)

    # AABB detectada pelo YOLO seria [100, 100, 550, 600]
    box = [100, 100, 550, 600]
    poly = refine_panel_polygon(img, box)
    assert len(poly) == 4
    tl, tr, br, bl = poly

    # Top-Right deve ter X próximo de 450 (e não 550!)
    assert abs(tr[0] - 450) <= 15
    # Bottom-Right deve ter X próximo de 550
    assert abs(br[0] - 550) <= 15


def test_is_point_in_panel():
    """Valida atribuição precisa ponto-a-painel em polígonos trapézios."""
    # Painel trapézio cortado na diagonal:
    # TL=(0,0), TR=(50, 0), BR=(100, 100), BL=(0, 100)
    panel = {
        "box": [0, 0, 100, 100],
        "polygon": [[0, 0], [50, 0], [100, 100], [0, 100]],
    }

    # Ponto no centro inferior: dentro
    assert is_point_in_panel((40, 80), panel) is True

    # Ponto na quina superior direita (75, 10):
    # Dentro da bounding box [0, 0, 100, 100], mas FORA do polígono diagonal!
    assert is_point_in_panel((80, 10), panel, tolerance_px=2.0) is False


def test_refine_panels_to_polygons_batch():
    """Valida a injeção do campo 'polygon' na lista de painéis."""
    img = Image.new("RGB", (800, 800), color=(255, 255, 255))
    panels = [
        {"id": 1, "box": [50, 50, 400, 400], "conf": 0.95},
        {"id": 2, "box": [450, 50, 750, 400], "conf": 0.92},
    ]
    refined = refine_panels_to_polygons(img, panels)
    assert len(refined) == 2
    for p in refined:
        assert "polygon" in p
        assert len(p["polygon"]) == 4


def test_rescue_uncovered_panels_success():
    """Valida o resgate automático de painel omitido com moldura e arte interna."""
    img = Image.new("RGB", (1000, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Painel 1 (topo)
    draw.rectangle([100, 100, 900, 480], outline=0, width=4)
    # Painel 2 (inferior esquerdo)
    draw.rectangle([100, 520, 480, 900], outline=0, width=4)
    # Painel 3 (inferior direito - omitido pelo YOLO, com moldura e desenho/tinta dentro)
    draw.rectangle([520, 520, 900, 900], outline=0, width=4)
    draw.rectangle([560, 560, 860, 860], fill=(120, 120, 120))  # Retícula / arte

    # YOLO só detectou Painel 1 e Painel 2
    existing_panels = [
        {
            "id": 1,
            "box": [100, 100, 900, 480],
            "polygon": [[100, 100], [900, 100], [900, 480], [100, 480]],
            "source": "yolo",
        },
        {
            "id": 2,
            "box": [100, 520, 480, 900],
            "polygon": [[100, 520], [480, 520], [480, 900], [100, 900]],
            "source": "yolo",
        },
    ]

    rescued = rescue_uncovered_panels(img, existing_panels)
    assert len(rescued) == 3, f"Esperado 3 painéis (2 existentes + 1 resgatado), obteve {len(rescued)}"

    new_p = rescued[2]
    assert new_p["source"] == "uncovered_rescue"
    assert len(new_p["polygon"]) == 4

    # O painel resgatado deve estar contido na região inferior direita [~496, ~500, 900, 900]
    # respeitando a calha mínima de 16px em relação ao painel 2 (480 + 16 = 496)
    rx1, ry1, rx2, ry2 = new_p["box"]
    assert rx1 >= 480 and ry1 >= 480
    assert rx2 <= 920 and ry2 <= 920


def test_rescue_uncovered_panels_ignores_blank():
    """Valida que áreas em branco (sangria, calhas largas sem arte) não são resgatadas."""
    img = Image.new("RGB", (1000, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Painel 1 (topo)
    draw.rectangle([100, 100, 900, 480], outline=0, width=4)
    # Painel 2 (inferior esquerdo)
    draw.rectangle([100, 520, 480, 900], outline=0, width=4)
    # Região inferior direita é puramente branca (sem moldura e sem tinta)

    existing_panels = [
        {
            "id": 1,
            "box": [100, 100, 900, 480],
            "polygon": [[100, 100], [900, 100], [900, 480], [100, 480]],
            "source": "yolo",
        },
        {
            "id": 2,
            "box": [100, 520, 480, 900],
            "polygon": [[100, 520], [480, 520], [480, 900], [100, 900]],
            "source": "yolo",
        },
    ]

    rescued = rescue_uncovered_panels(img, existing_panels)
    assert len(rescued) == 2, "Área vazia sem moldura/tinta não deve ser resgatada como painel"


def test_split_oversized_panel_double_walled_gutter():
    """Valida a subdivisão de painel superdimensionado com calha vertical de parede dupla (flashback/screentone)."""
    # Fundo de retícula cinza (flashback)
    img = Image.new("RGB", (1000, 800), color=(150, 150, 150))
    draw = ImageDraw.Draw(img)

    # Moldura externa de 50,50 até 950,750
    draw.rectangle([50, 50, 950, 750], outline=0, width=4)
    # Calha vertical de parede dupla em x=[490..510]: duas paredes pretas com interior cinza claro (180)
    draw.rectangle([493, 50, 507, 750], fill=(180, 180, 180))
    draw.line([(492, 50), (492, 750)], fill=0, width=4)
    draw.line([(508, 50), (508, 750)], fill=0, width=4)

    oversized = [
        {
            "id": 1,
            "box": [50, 50, 950, 750],
            "polygon": [[50, 50], [950, 50], [950, 750], [50, 750]],
            "source": "uncovered_rescue",
        }
    ]
    bubbles = [
        {"id": 1, "x1": 150, "y1": 150, "x2": 350, "y2": 350},
        {"id": 2, "x1": 650, "y1": 150, "x2": 850, "y2": 350},
    ]

    split_panels = split_oversized_panels(img, oversized, bubbles=bubbles)
    assert len(split_panels) == 2, f"Esperado 2 sub-painéis após corte vertical, obteve {len(split_panels)}"


def test_reconcile_collinear_stacked_panels_against_slanted_neighbor():
    """Valida alinhamento colinear da borda esquerda de quadros empilhados contra vizinho inclinado."""
    panels = [
        # P_left: quadro alto da esquerda com borda direita inclinada de x=400 (y=0) até x=500 (y=1000)
        {
            "id": 1,
            "box": [0, 0, 500, 1000],
            "polygon": [[0, 0], [400, 0], [500, 1000], [0, 1000]],
        },
        # P_top_right: quadro superior direito cujo TL tinha puxado para x=460
        {
            "id": 2,
            "box": [420, 0, 1000, 480],
            "polygon": [[460, 0], [1000, 0], [1000, 480], [468, 480]],
        },
        # P_bot_right: quadro inferior direito
        {
            "id": 3,
            "box": [468, 500, 1000, 1000],
            "polygon": [[470, 500], [1000, 500], [1000, 1000], [520, 1000]],
        },
    ]

    reconciled = _reconcile_panel_gutters(panels, image=None)
    p_top = reconciled[1]["polygon"]
    p_bot = reconciled[2]["polygon"]

    # A borda esquerda de P_top (y=0 -> y=480) e P_bot (y=500 -> y=1000) devem ser estritamente colineares
    # com deslocamento uniforme (+16px) em relação a x_ref(y) = 400 + 0.1*y
    offsets = [
        p_top[0][0] - 400,
        p_top[3][0] - 448,
        p_bot[0][0] - 450,
        p_bot[3][0] - 500,
    ]
    assert max(offsets) - min(offsets) <= 1
    assert offsets[0] == 16


def test_upward_eruption_bubble_panel_assignment():
    """Valida que um balão de grito que explode para cima na borda superior de P2 permanece atribuído a P2."""
    panels = [
        # P1 (topo): y=[50..500]
        {
            "id": 1,
            "box": [100, 50, 900, 500],
            "polygon": [[100, 50], [900, 50], [900, 500], [100, 500]],
        },
        # P2 (meio): y=[520..760] (altura 240px, metade em y=640)
        {
            "id": 2,
            "box": [100, 520, 900, 760],
            "polygon": [[100, 520], [900, 520], [900, 760], [100, 760]],
        },
    ]
    bubbles = [
        # Balão normal na esquerda de P1
        {"id": "b_p1", "x1": 150, "y1": 200, "x2": 300, "y2": 400},
        # Balão de grito em P2 que explode para cima invadindo P1 (y1=380 < 520, y2=700 > 640)
        {"id": "b_scream_p2", "x1": 400, "y1": 380, "x2": 600, "y2": 700},
    ]

    ordered = sort_bubbles_reading_order(bubbles, panels=panels)
    # Em mangá RTL, P1 vem antes de P2; logo b_p1 deve ser #001 e b_scream_p2 (em P2) deve ser #002!
    assert [b["id"] for b in ordered] == ["b_p1", "b_scream_p2"]


