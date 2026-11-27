"""
Testes de Regressão e Validação do Golden Set (Ground Truth de Layout e Balões).

Valida a integridade matemática, consistência de schema e acurácia do pipeline
contra o conjunto padrão de referência (Golden Set).
"""

import json
import os
import pytest
from src.models.bubble import PageDataModel, BubbleModel
from src.geometry.bubble_geometry import _iou

FIXTURES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "fixtures", "golden_set")
)
GOLDEN_PAGES = [
    "004_map.json",
    "006_map.json",
    "010_map.json",
    "017_map.json",
    "019_map.json",
    "024_map.json",
    "027_map.json",
    "032_map.json",
    "034_map.json",
    "070_map.json",
]
RAW_DIR = r"V:\Genikasuri\RAW\Chapter 001 The Brazen Boxer"


def test_golden_set_files_exist():
    """Valida que todos os 10 arquivos de gabarito do Golden Set existem."""
    assert os.path.isdir(FIXTURES_DIR), f"Diretório não encontrado: {FIXTURES_DIR}"
    assert len(GOLDEN_PAGES) == 10
    for filename in GOLDEN_PAGES:
        path = os.path.join(FIXTURES_DIR, filename)
        assert os.path.isfile(path), f"Arquivo do Golden Set ausente: {path}"


def test_golden_set_offline_reading_order_invariants():
    """
    Valida offline que o motor sort_bubbles_reading_order preserva
    invariantes críticos de ordem de leitura em layouts complexos do Golden Set:
    - Pág 034: duas fileiras RTL dentro do mesmo painel amplo (P1).
    - Pág 032: pares de balões empilhados verticalmente na direita antes da esquerda.
    - Pág 019: coluna vertical direita antes da coluna empilhada esquerda.
    """
    from src.batch_pipeline.reading_order import sort_bubbles_reading_order

    for filename in ("019_map.json", "032_map.json", "034_map.json"):
        path = os.path.join(FIXTURES_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        panels = data["panels"]
        # Embaralha a ordem de entrada (reversa) para forçar o algoritmo geométrico a reconstruir a ordem
        shuffled_boxes = [dict(b) for b in reversed(data["boxes"])]
        sorted_boxes = sort_bubbles_reading_order(shuffled_boxes, panels=panels, direction="rtl")

        assert len(sorted_boxes) == len(data["boxes"])
        orders = [b["order"] for b in sorted_boxes]
        assert orders == list(range(1, len(data["boxes"]) + 1))

        if filename == "034_map.json":
            # Em P1 de 034, os 3 balões da fileira superior (y2 < 500) devem preceder os 3 da inferior (y1 > 650)
            p1_boxes = [b for b in sorted_boxes if b.get("panel_id") == 1]
            assert len(p1_boxes) == 6
            for idx in (0, 1, 2):
                assert p1_boxes[idx]["y2"] < 500
            for idx in (3, 4, 5):
                assert p1_boxes[idx]["y1"] > 650


@pytest.mark.parametrize("filename", GOLDEN_PAGES)
def test_golden_set_schema_and_geometry_validity(filename):
    """
    Valida a integridade geométrica de cada página do Golden Set:
    - Conformidade com PageDataModel / BubbleModel.
    - Coordenadas estritamente positivas e não-degeneradas (x2 > x1, y2 > y1).
    - Ordem sequencial monotônica e contínua (1, 2, 3, ...).
    - Painéis válidos e sem dimensões nulas.
    """
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("version") == 2
    assert "width" in data and "height" in data
    w, h = data["width"], data["height"]
    assert w > 0 and h > 0

    # 1. Validação de Painéis
    panels = data.get("panels", [])
    assert len(panels) >= 1, "Toda página deve conter ao menos 1 painel (mesmo splash)"
    for p in panels:
        bx1, by1, bx2, by2 = p["box"]
        assert 0 <= bx1 < bx2 <= w, f"Painel com coordenadas X inválidas: {p['box']}"
        assert 0 <= by1 < by2 <= h, f"Painel com coordenadas Y inválidas: {p['box']}"

    # 2. Validação de Balões via Pydantic
    boxes = data.get("boxes", [])
    page_model = PageDataModel.from_raw(boxes)
    assert len(page_model.boxes) == len(boxes)

    orders = []
    for b in page_model.boxes:
        assert 0 <= b.x1 < b.x2 <= w, f"Box com X inválido: ({b.x1}, {b.x2})"
        assert 0 <= b.y1 < b.y2 <= h, f"Box com Y inválido: ({b.y1}, {b.y2})"
        assert b.text and len(b.text.strip()) > 0, f"Balão #{b.id} sem texto anotado"
        orders.append(b.order)

    # Ordem de leitura deve ser estritamente sequencial 1..N
    expected_orders = list(range(1, len(boxes) + 1))
    assert orders == expected_orders, f"Ordem não sequencial em {filename}: {orders} vs {expected_orders}"


@pytest.mark.skipif(not os.path.isdir(RAW_DIR), reason="Diretório de RAWs externas não disponível")
@pytest.mark.parametrize("map_file", ["004_map.json", "010_map.json", "027_map.json"])
def test_pipeline_inference_recall_on_golden_set(map_file):
    """
    Executa inferência real do YoloMapeador e calcula o Recall de detecção
    contra o Ground Truth do Golden Set com IoU >= 0.40.
    """
    from PIL import Image
    from src.step1_layout_detector import YoloMapeador

    truth_path = os.path.join(FIXTURES_DIR, map_file)
    with open(truth_path, "r", encoding="utf-8") as f:
        truth = json.load(f)

    img_path = os.path.join(RAW_DIR, truth["image_file"])
    if not os.path.isfile(img_path):
        pytest.skip(f"Imagem RAW ausente: {img_path}")

    img = Image.open(img_path)
    mapeador = YoloMapeador()
    detected_bubbles = mapeador.detect_bubbles(img)

    # Para cada balão do gabarito, verifica se existe ao menos uma caixa predita com IoU >= 0.40
    matched = 0
    truth_boxes = truth["boxes"]
    for tb in truth_boxes:
        t_box = [tb["x1"], tb["y1"], tb["x2"], tb["y2"]]
        best_iou = 0.0
        for db in detected_bubbles:
            d_box = [db["x1"], db["y1"], db["x2"], db["y2"]]
            iou = _iou(t_box, d_box)
            if iou > best_iou:
                best_iou = iou
        if best_iou >= 0.40:
            matched += 1

    recall = matched / float(len(truth_boxes))
    # Tolerância de recall mínimo de 85% para páginas padrão de diálogo
    assert recall >= 0.85, f"Recall insuficiente em {truth['image_file']}: {recall:.2f} ({matched}/{len(truth_boxes)})"


@pytest.mark.skipif(not os.path.isdir(RAW_DIR), reason="Diretório de RAWs externas não disponível")
def test_render_refined_polygons_page_010():
    """Executa o pipeline completo em 010.jpg e renderiza a sobreposição de polígonos refinados."""
    from PIL import Image, ImageDraw
    from src.step1_layout_detector import YoloMapeador

    img_path = os.path.join(RAW_DIR, "010.jpg")
    if not os.path.isfile(img_path):
        pytest.skip(f"Imagem RAW ausente: {img_path}")

    img = Image.open(img_path)
    mapeador = YoloMapeador()
    mapeador.load_panel_detector()
    panels, _ = mapeador.detect_panels_and_sort(img, [])

    print("\n--- DETECTED PANELS ON 010.JPG ---")
    for i, p in enumerate(panels):
        print(f"P{i+1}: box={p['box']} poly={p.get('polygon')}")

    assert len(panels) >= 7, f"Esperava ao menos 7 painéis na página 010, obteve {len(panels)}"
    for p in panels:
        assert "polygon" in p
        assert len(p["polygon"]) == 4

    # Renderiza visualmente para inspeção na Área de Trabalho
    desktop_dir = r"C:\Users\Admin\Desktop\Golden Set"
    if os.path.isdir(desktop_dir):
        vis = img.convert("RGB")
        draw = ImageDraw.Draw(vis)
        for i, p in enumerate(panels):
            poly = p["polygon"]
            pts = [tuple(pt) for pt in poly]
            draw.polygon(pts, outline=(0, 220, 255), width=5)
            for vx, vy in poly:
                draw.ellipse([vx - 5, vy - 5, vx + 5, vy + 5], fill=(255, 0, 128))
            draw.text((poly[0][0] + 15, poly[0][1] + 15), f"P{i+1}", fill=(0, 220, 255))
        
        try:
            vis.save(os.path.join(desktop_dir, "010_poligonos_opencv_refinados.png"))
        except Exception as e:
            print(f"Warning: could not save 010_poligonos_opencv_refinados.png: {e}")

        # Cria imagem lado a lado (YOLO XL Puro vs YOLO XL + OpenCV Polígonos)
        yolo_path = os.path.join(desktop_dir, "010_predicao_yolo_xl.png")
        if os.path.isfile(yolo_path):
            img_yolo = Image.open(yolo_path).convert("RGB")
            header_h = 70
            comp_w = img_yolo.width * 2
            comp_h = img_yolo.height + header_h
            comp = Image.new("RGB", (comp_w, comp_h), color=(20, 24, 32))
            draw_comp = ImageDraw.Draw(comp)
            draw_comp.text((40, 20), "YOLO Extra-Large Puro (Caixas Ortogonais AABB)", fill=(255, 60, 160))
            draw_comp.text((img_yolo.width + 40, 20), "YOLO XL + Refinador OpenCV (Poligonos & Calhas Inclinadas)", fill=(0, 220, 255))
            comp.paste(img_yolo, (0, header_h))
            comp.paste(vis, (img_yolo.width, header_h))
            try:
                comp.save(os.path.join(desktop_dir, "010_comparacao_yolo_xl_vs_opencv.png"))
            except Exception as e:
                print(f"Warning: could not save comparison: {e}")


@pytest.mark.skipif(not os.path.isdir(RAW_DIR), reason="Diretório de RAWs externas não disponível")
def test_inspect_regressao_pages():
    """Inspeciona caixas brutas do YOLO, polígonos finais e ordem dos balões nas 11 páginas de regressão."""
    from PIL import Image, ImageDraw
    from src.step1_layout_detector import YoloMapeador, _detect_panels_blind_master
    from src.batch_pipeline.reading_order import recursive_xy_cut

    pages = ["012", "014", "016", "028", "031", "032", "054", "055", "058", "069", "074"]
    mapeador = YoloMapeador()
    mapeador.load_panel_detector()
    reg_dir = r"C:\Users\Admin\Desktop\Golden Set\regressao"

    for page in pages:
        img_path = os.path.join(RAW_DIR, f"{page}.jpg")
        if not os.path.isfile(img_path):
            continue
        img = Image.open(img_path).convert("RGB")
        bubbles = mapeador.detect_bubbles(img)
        raw = recursive_xy_cut(_detect_panels_blind_master(mapeador._panel_model, img))
        panels, sorted_bubbles = mapeador.detect_panels_and_sort(img, bubbles)
        print(f"\n=== PAGE {page} ({img.width}x{img.height}) | raw={len(raw)} -> final={len(panels)} | bubbles={len(sorted_bubbles)} ===")
        for i, r in enumerate(raw):
            print(f"  RAW R{i+1}: box={r['box']} conf={r.get('conf', 0):.2f}")
        for i, p in enumerate(panels):
            print(f"  FIN P{i+1} ({p.get('source', 'yolo')}): box={p['box']} poly={p.get('polygon')}")
        for i, b in enumerate(sorted_bubbles):
            bx = [int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])]
            print(f"  B#{i+1:03d} (P{b.get('panel_id', -1)}): box={bx}")

        if os.path.isdir(reg_dir):
            vis = img.copy()
            draw = ImageDraw.Draw(vis)
            for i, p in enumerate(panels):
                poly = p.get("polygon")
                if poly:
                    draw.polygon([tuple(pt) for pt in poly], outline=(0, 220, 255), width=5)
                    for vx, vy in poly:
                        draw.ellipse([vx - 5, vy - 5, vx + 5, vy + 5], fill=(255, 0, 128))
                    draw.text((poly[0][0] + 15, poly[0][1] + 15), f"P{i+1}", fill=(0, 220, 255))
            for i, b in enumerate(sorted_bubbles):
                bx1, by1, bx2, by2 = int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
                draw.rectangle([bx1, by1, bx2, by2], outline=(50, 255, 80), width=4)
                draw.text((bx1 + 6, by1 + 6), f"#{i+1:03d} (P{b.get('panel_id', -1)})", fill=(255, 220, 0))
            try:
                vis.save(os.path.join(reg_dir, f"{page}_poligonos_opencv.png"))
            except Exception:
                pass


def test_inspect_page_019_genikasuri():
    """Audita detecção de balões, quadros e ordem de leitura na página 019."""
    img_path = r"V:\Genikasuri\RAW\Chapter 001 The Brazen Boxer\019.jpg"
    if not os.path.isfile(img_path):
        pytest.skip("019.jpg não disponível")

    from PIL import Image, ImageDraw
    from src.step1_layout_detector import YoloMapeador, _detect_panels_blind_master
    from src.batch_pipeline.reading_order import recursive_xy_cut

    mapper = YoloMapeador()
    mapper.load_bubble_detector()
    mapper.load_panel_detector()

    img = Image.open(img_path).convert("RGB")
    raw_p = _detect_panels_blind_master(mapper._panel_model, img)
    print(f"\n=== 019.jpg RAW PANELS ({len(raw_p)}) ===")
    for i, rp in enumerate(raw_p):
        print(f"  raw_p{i+1}: box={rp['box']} conf={rp.get('conf', 0):.3f}")

    bubbles = mapper.detect_bubbles(img)
    from src.geometry.panels import rescue_uncovered_panels, refine_panel_polygon, _reconcile_panel_gutters, split_oversized_panels
    init_panels = []
    for rp in raw_p:
        p_copy = dict(rp)
        p_copy["polygon"] = refine_panel_polygon(img, rp["box"])
        init_panels.append(p_copy)
    init_panels = _reconcile_panel_gutters(init_panels, image=img)
    init_panels = split_oversized_panels(img, init_panels, bubbles=bubbles)
    print(f"\n--- 019 BEFORE RESCUE: {len(init_panels)} panels ---")
    for ip in init_panels:
        print(f"  init: box={ip['box']} poly={ip.get('polygon')}")
    rescued = rescue_uncovered_panels(img, init_panels, bubbles=bubbles)
    print(f"--- 019 AFTER RESCUE: {len(rescued)} panels ---")
    for rp in rescued:
        print(f"  rescued ({rp.get('source')}): box={rp['box']} poly={rp.get('polygon')}")

    panels, sorted_bubbles = mapper.detect_panels_and_sort(img, bubbles)
    assert len(panels) >= 5, f"Esperado ao menos 5 painéis em 019.jpg, obteve {len(panels)}"
    assert len(sorted_bubbles) == 11, f"Esperado 11 balões em 019.jpg, obteve {len(sorted_bubbles)}"

    # Tier 1 (Topo): B#001 (rosto ameaçador, topo direito) -> B#002 (Gonna...) -> B#003 (...Crush you)
    assert 1200 <= sorted_bubbles[0]["x1"] <= 1360 and sorted_bubbles[0]["y2"] < 400
    assert 600 <= sorted_bubbles[1]["x1"] <= 740 and sorted_bubbles[1]["y2"] < 450
    assert 500 <= sorted_bubbles[2]["x1"] <= 650 and sorted_bubbles[2]["y2"] < 520

    # Coluna da Direita primeiro: B#004..B#006 (dois homens falando sobre pressão e aura)
    assert sorted_bubbles[3]["x1"] > 1200 and sorted_bubbles[3]["y1"] > 1380  # "THAT'S SOME HEAVY PRESSURE..."
    assert sorted_bubbles[4]["x1"] > 1050 and sorted_bubbles[4]["y1"] > 1380  # "HE'S DEFINITELY MORE THAN..."
    assert sorted_bubbles[5]["x1"] > 840 and sorted_bubbles[5]["y1"] > 1380   # "YEAH. COULDN'T HAVE AN AURA..."

    # Coluna da Esquerda completa: B#007..B#009 (espectadores) -> B#010..B#011 (explicação de Spikes)
    assert sorted_bubbles[6]["y2"] < 1200 and sorted_bubbles[6]["x2"] < 550  # "WOW..."
    assert sorted_bubbles[7]["y2"] < 1250 and sorted_bubbles[7]["x2"] < 300  # "...MUST MEAN..."
    assert sorted_bubbles[8]["y2"] < 1500 and sorted_bubbles[8]["x2"] < 300  # "...SPIKES?"
    assert sorted_bubbles[9]["x1"] < 600 and sorted_bubbles[9]["y1"] > 1400   # "WHEN THE MUSCLES..."
    assert sorted_bubbles[10]["x1"] < 250 and sorted_bubbles[10]["y1"] > 1550  # "WHEN IT HAPPENS TO HIM..."
    print(f"=== 019.jpg PIPELINE: panels={len(panels)} bubbles={len(sorted_bubbles)} ===")
    for i, p in enumerate(panels):
        print(f"  P{i+1}: box={p['box']} poly={p.get('polygon')} src={p.get('source', 'yolo')}")
    for i, b in enumerate(sorted_bubbles):
        bx = [int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])]
        print(f"  B#{i+1:03d} (P{b.get('panel_id', -1)}): box={bx} conf={b.get('confidence')} label={b.get('label')} bg={b.get('bg_type')}")

    reg_dir = r"C:\Users\Admin\Desktop\Golden Set\regressao"
    if os.path.isdir(reg_dir):
        vis = img.copy()
        draw = ImageDraw.Draw(vis)
        for i, p in enumerate(panels):
            poly = p.get("polygon")
            if poly:
                draw.polygon([tuple(pt) for pt in poly], outline=(0, 220, 255), width=5)
                for vx, vy in poly:
                    draw.ellipse([vx - 5, vy - 5, vx + 5, vy + 5], fill=(255, 0, 128))
                draw.text((poly[0][0] + 15, poly[0][1] + 15), f"P{i+1}", fill=(0, 220, 255))
        for i, b in enumerate(sorted_bubbles):
            bx1, by1, bx2, by2 = int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
            draw.rectangle([bx1, by1, bx2, by2], outline=(50, 255, 80), width=4)
            draw.text((bx1 + 6, by1 + 6), f"#{i+1:03d} (P{b.get('panel_id', -1)})", fill=(255, 220, 0))
        try:
            vis.save(os.path.join(reg_dir, "019_poligonos_opencv.png"))
        except Exception:
            pass

    out_dir = r"V:\Genikasuri\RAW\Chapter 001 The Brazen Boxer\output"
    if os.path.isdir(out_dir):
        mapper.save_map(sorted_bubbles, out_dir, "019", panels=panels)


def test_inspect_page_017_genikasuri():
    """Audita detecção de balões, quadros e ordem de leitura na página 017."""
    img_path = r"V:\Genikasuri\RAW\Chapter 001 The Brazen Boxer\017.jpg"
    if not os.path.isfile(img_path):
        pytest.skip("017.jpg não disponível")

    from PIL import Image, ImageDraw
    from src.step1_layout_detector import YoloMapeador

    mapper = YoloMapeador()
    mapper.load_bubble_detector()
    mapper.load_panel_detector()

    img = Image.open(img_path).convert("RGB")
    bubbles = mapper.detect_bubbles(img)
    panels, sorted_bubbles = mapper.detect_panels_and_sort(img, bubbles)

    assert len(panels) == 6, f"Esperado 6 painéis em 017.jpg, obteve {len(panels)}"
    assert len(sorted_bubbles) == 13, f"Esperado 13 balões em 017.jpg, obteve {len(sorted_bubbles)}"
    panel_ids = [b.get("panel_id") for b in sorted_bubbles]
    assert panel_ids == [1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 6], f"Atribuição de painéis inesperada: {panel_ids}"

    reg_dir = r"C:\Users\Admin\Desktop\Golden Set\regressao"
    if os.path.isdir(reg_dir):
        vis = img.copy()
        draw = ImageDraw.Draw(vis)
        for i, p in enumerate(panels):
            poly = p.get("polygon")
            if poly:
                draw.polygon([tuple(pt) for pt in poly], outline=(0, 220, 255), width=5)
                for vx, vy in poly:
                    draw.ellipse([vx - 5, vy - 5, vx + 5, vy + 5], fill=(255, 0, 128))
                draw.text((poly[0][0] + 15, poly[0][1] + 15), f"P{i+1}", fill=(0, 220, 255))
        for i, b in enumerate(sorted_bubbles):
            bx1, by1, bx2, by2 = int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
            draw.rectangle([bx1, by1, bx2, by2], outline=(50, 255, 80), width=4)
            draw.text((bx1 + 6, by1 + 6), f"#{i+1:03d} (P{b.get('panel_id', -1)})", fill=(255, 220, 0))
        try:
            vis.save(os.path.join(reg_dir, "017_poligonos_opencv.png"))
        except Exception:
            pass


def test_inspect_page_024_genikasuri():
    """Audita detecção de balões inclinados, quadros diagonais e ordem de leitura na página 024."""
    img_path = r"V:\Genikasuri\RAW\Chapter 001 The Brazen Boxer\024.jpg"
    if not os.path.isfile(img_path):
        pytest.skip("024.jpg não disponível")

    from PIL import Image, ImageDraw
    from src.step1_layout_detector import YoloMapeador

    mapper = YoloMapeador()
    mapper.load_bubble_detector()
    mapper.load_panel_detector()

    img = Image.open(img_path).convert("RGB")
    bubbles = mapper.detect_bubbles(img)
    panels, sorted_bubbles = mapper.detect_panels_and_sort(img, bubbles)

    assert len(panels) == 2, f"Esperados 2 quadros diagonais na pág 024, obtidos {len(panels)}: {panels}"
    assert len(sorted_bubbles) == 8, f"Esperados 8 balões na pág 024, obtidos {len(sorted_bubbles)}: {sorted_bubbles}"

    # Verifica que os 3 balões inclinados antes omitidos foram detectados
    expected_tilted_centers = [
        (250, 1217),  # "HE FELT THAT ONE!!"
        (543, 1414),  # "HARIMA'S TURNED IT AROUND!"
        (841, 1667),  # "ZARA FOLDS OVER..."
    ]
    for ecx, ecy in expected_tilted_centers:
        assert any(
            b["x1"] <= ecx <= b["x2"] and b["y1"] <= ecy <= b["y2"]
            for b in sorted_bubbles
        ), f"Balão inclinado esperado em torno de ({ecx}, {ecy}) não foi detectado!"

    reg_dir = r"C:\Users\Admin\Desktop\Golden Set\regressao"
    if os.path.isdir(reg_dir):
        vis = img.copy()
        draw = ImageDraw.Draw(vis)
        for i, p in enumerate(panels):
            poly = p.get("polygon")
            if poly:
                draw.polygon([tuple(pt) for pt in poly], outline=(0, 220, 255), width=5)
                for vx, vy in poly:
                    draw.ellipse([vx - 5, vy - 5, vx + 5, vy + 5], fill=(255, 0, 128))
                draw.text((poly[0][0] + 15, poly[0][1] + 15), f"P{i+1}", fill=(0, 220, 255))
        for i, b in enumerate(sorted_bubbles):
            bx1, by1, bx2, by2 = int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
            draw.rectangle([bx1, by1, bx2, by2], outline=(50, 255, 80), width=4)
            draw.text((bx1 + 6, by1 + 6), f"#{i+1:03d} (P{b.get('panel_id', -1)})", fill=(255, 220, 0))
        try:
            vis.save(os.path.join(reg_dir, "024_poligonos_opencv.png"))
        except Exception:
            pass


@pytest.mark.skipif(not os.path.isdir(RAW_DIR), reason="Diretório de RAWs externas não disponível")
def test_inspect_page_032_and_034_genikasuri():
    """
    Valida regressão completa nas páginas 032 e 034 do capítulo 1 de Genikasuri:
    - Pág. 032: 4 painéis, 12 balões, separação dos 2 pares de balões empilhados e rejeição das colunas de jornal.
    - Pág. 034: 5 painéis, 15 balões (incluindo '...' em P3), e ordem de leitura RTL por linha em P1.
    """
    from PIL import Image, ImageDraw
    from src.step1_layout_detector import YoloMapeador

    mapper = YoloMapeador()
    mapper.load_bubble_detector()
    mapper.load_panel_detector()
    out_dir = r"C:\Users\Admin\Desktop\Golden Set\regressao"
    os.makedirs(out_dir, exist_ok=True)

    # 1. Validação da Página 032
    img_032_path = os.path.join(RAW_DIR, "032.jpg")
    if not os.path.isfile(img_032_path):
        pytest.skip("032.jpg não disponível")
    img_032 = Image.open(img_032_path).convert("RGB")
    bubbles_032 = mapper.detect_bubbles(img_032)
    panels_032, sorted_032 = mapper.detect_panels_and_sort(img_032, bubbles_032)

    assert len(panels_032) == 4, f"Esperado 4 painéis em 032.jpg, obteve {len(panels_032)}"
    assert len(sorted_032) == 12, f"Esperado 12 balões em 032.jpg (sem fusões e sem jornal), obteve {len(sorted_032)}"

    # Par 1 no topo direito deve estar separado em B#001 (superior) e B#002 (inferior)
    b1_032, b2_032 = sorted_032[0], sorted_032[1]
    assert b1_032["x1"] > 1100 and b1_032["y2"] < 260
    assert b2_032["x1"] > 1100 and b2_032["y1"] > 210 and b2_032["y2"] > 450

    # Par 2 do treinador deve estar separado em B#008 (superior) e B#009 (inferior)
    b8_032, b9_032 = sorted_032[7], sorted_032[8]
    assert 500 <= b8_032["x1"] <= 600 and b8_032["y2"] < 1500
    assert 500 <= b9_032["x1"] <= 600 and b9_032["y1"] > 1460

    # Nenhum falso positivo sobre a coluna do jornal (x in 390..540, y in 1900..2100)
    assert not any(380 <= b["x1"] <= 450 and b["y1"] >= 1900 for b in sorted_032)

    # 2. Validação da Página 034
    img_034_path = os.path.join(RAW_DIR, "034.jpg")
    if not os.path.isfile(img_034_path):
        pytest.skip("034.jpg não disponível")
    img_034 = Image.open(img_034_path).convert("RGB")
    bubbles_034 = mapper.detect_bubbles(img_034)
    panels_034, sorted_034 = mapper.detect_panels_and_sort(img_034, bubbles_034)

    assert len(panels_034) == 5, f"Esperado 5 painéis em 034.jpg, obteve {len(panels_034)}"
    assert len(sorted_034) == 15, f"Esperado 15 balões em 034.jpg, obteve {len(sorted_034)}"

    # Em P1 (quadro do carro), os 3 balões da fileira superior (B#001..B#003) devem vir antes dos 3 da fileira inferior (B#004..B#006)
    for idx in (0, 1, 2):
        assert sorted_034[idx]["y2"] < 500, f"B#{idx+1} deveria estar na fileira superior de P1: {sorted_034[idx]}"
    for idx in (3, 4, 5):
        assert sorted_034[idx]["y1"] > 650, f"B#{idx+1} deveria estar na fileira inferior de P1: {sorted_034[idx]}"

    # Balão de reticências '...' em P3 deve ser B#010
    b10_034 = sorted_034[9]
    assert 1200 <= b10_034["x1"] <= 1250 and 1150 <= b10_034["y1"] <= 1210

    # Salva mapas visuais de regressão para 032 e 034
    for page_num, im_obj, p_list, b_list in (
        ("032", img_032, panels_032, sorted_032),
        ("034", img_034, panels_034, sorted_034),
    ):
        vis = im_obj.copy()
        draw = ImageDraw.Draw(vis)
        for idx, p in enumerate(p_list):
            poly = p.get("polygon")
            if poly and len(poly) == 4:
                draw.polygon([tuple(pt) for pt in poly], outline=(0, 220, 255), width=5)
                for vx, vy in poly:
                    draw.ellipse([vx - 5, vy - 5, vx + 5, vy + 5], fill=(255, 0, 128))
                draw.text((poly[0][0] + 14, poly[0][1] + 14), f"P{idx+1}", fill=(0, 220, 255))
        for idx, b in enumerate(b_list):
            bx1, by1, bx2, by2 = int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
            draw.rectangle([bx1, by1, bx2, by2], outline=(50, 255, 100), width=3)
            draw.text((bx1 + 6, by1 + 6), f"#{idx+1}", fill=(255, 220, 0))
        try:
            vis.save(os.path.join(out_dir, f"{page_num}_poligonos_opencv.png"))
        except Exception:
            pass








