"""
Ordenação espacial de leitura para mangás (RTL, topo para base) e quadrinhos ocidentais (LTR).

- `recursive_xy_cut`: separa quadros por faixas horizontais (tiers) e colunas.
- `_bubble_xy_cut`: ordena balões dentro de cada quadro ou aglomerado.
- `sort_bubbles_reading_order`: vincula balões aos quadros, aplica regras de estouro de
  borda e dissocia efeitos sonoros (SFX) da numeração dos diálogos.
"""

from collections import defaultdict
from functools import cmp_to_key
from src.geometry.panels import is_point_in_panel


def _panel_effective_bounds(p: dict) -> tuple[float, float, float, float]:
    """
    Retorna (x1, y1, x2, y2) efetivos do painel. Quando há um polígono de 4 vértices
    [TL, TR, BR, BL], utiliza as médias das arestas opostas para evitar que quinas
    diagonais inflem o AABB e mascaram os corredores (gutters) entre linhas/colunas.
    """
    x1, y1, x2, y2 = 0.0, 0.0, 0.0, 0.0
    poly = p.get("polygon")
    if poly and len(poly) == 4:
        try:
            x1 = (float(poly[0][0]) + float(poly[3][0])) * 0.5
            x2 = (float(poly[1][0]) + float(poly[2][0])) * 0.5
            y1 = (float(poly[0][1]) + float(poly[1][1])) * 0.5
            y2 = (float(poly[3][1]) + float(poly[2][1])) * 0.5
            if not (x2 > x1 and y2 > y1):
                poly = None
        except (TypeError, ValueError, IndexError):
            poly = None
    if not poly or len(poly) != 4:
        bx1, by1, bx2, by2 = p["box"]
        x1, y1, x2, y2 = float(bx1), float(by1), float(bx2), float(by2)

    return x1, y1, x2, y2


def recursive_xy_cut(panels, min_x_gap=10, min_y_gap=15, direction="rtl"):
    """
    Ordena painéis recursivamente (topo-para-base e direita-para-esquerda no mangá, ou
    esquerda-para-direita quando `direction="ltr"`).
    Encolhe as projeções em 12-15% para não perder a calha quando molduras vizinhas se tocam.
    """
    if len(panels) <= 1:
        return panels

    is_ltr = str(direction).strip().lower() == "ltr"
    bounds = {id(p): _panel_effective_bounds(p) for p in panels}

    y_intervals = []
    for p in panels:
        _, py1, _, py2 = bounds[id(p)]
        sy = min(30, (py2 - py1) * 0.12)
        y_intervals.append((py1 + sy, py2 - sy))
    y_intervals.sort()
    
    y_gaps = []
    max_y_end = y_intervals[0][1]
    for current in y_intervals[1:]:
        if current[0] > max_y_end:
            y_gaps.append((current[0] - max_y_end, max_y_end, current[0]))
        max_y_end = max(max_y_end, current[1])
            
    x_intervals = []
    for p in panels:
        px1, _, px2, _ = bounds[id(p)]
        sx = min(45, (px2 - px1) * 0.15)
        x_intervals.append((px1 + sx, px2 - sx))
    x_intervals.sort()
    
    x_gaps = []
    max_x_end = x_intervals[0][1]
    for current in x_intervals[1:]:
        if current[0] > max_x_end:
            x_gaps.append((current[0] - max_x_end, max_x_end, current[0]))
        max_y_end = max(max_x_end, current[1])
        
    best_y_gap = max(y_gaps, key=lambda x: x[0]) if y_gaps else (0, 0, 0)
    best_x_gap = max(x_gaps, key=lambda x: x[0]) if x_gaps else (0, 0, 0)
    
    # Faixas horizontais que atravessam toda a página separam fileiras (tiers) inteiras e têm
    # prioridade sobre cortes verticais internos para evitar leitura em coluna através de fileiras distintas.
    if best_y_gap[0] >= min_y_gap:
        for gap in y_gaps:
            if gap[0] == best_y_gap[0]:
                cut_y = (gap[1] + gap[2]) / 2
                top_group = [p for p in panels if (bounds[id(p)][1] + bounds[id(p)][3]) / 2 < cut_y]
                bottom_group = [p for p in panels if p not in top_group]
                if top_group and bottom_group:
                    return (recursive_xy_cut(top_group, min_x_gap, min_y_gap, direction=direction) +
                            recursive_xy_cut(bottom_group, min_x_gap, min_y_gap, direction=direction))
                break

    # Sem corte horizontal global, divide por colunas (RTL em mangás; LTR em quadrinhos ocidentais)
    if best_x_gap[0] >= min_x_gap:
        gaps_to_check = x_gaps if is_ltr else reversed(x_gaps)
        for gap in gaps_to_check:
            if gap[0] == best_x_gap[0]:
                cut_x = (gap[1] + gap[2]) / 2
                if is_ltr:
                    first_group = [p for p in panels if (bounds[id(p)][0] + bounds[id(p)][2]) / 2 < cut_x]
                    second_group = [p for p in panels if p not in first_group]
                else:
                    first_group = [p for p in panels if (bounds[id(p)][0] + bounds[id(p)][2]) / 2 > cut_x]
                    second_group = [p for p in panels if p not in first_group]
                if first_group and second_group:
                    return (recursive_xy_cut(first_group, min_x_gap, min_y_gap, direction=direction) +
                            recursive_xy_cut(second_group, min_x_gap, min_y_gap, direction=direction))
                break

    if best_y_gap[0] >= min_y_gap:
        for gap in y_gaps:
            if gap[0] == best_y_gap[0]:
                cut_y = (gap[1] + gap[2]) / 2
                top_group = [p for p in panels if (bounds[id(p)][1] + bounds[id(p)][3]) / 2 < cut_y]
                bottom_group = [p for p in panels if p not in top_group]
                if top_group and bottom_group:
                    return (recursive_xy_cut(top_group, min_x_gap, min_y_gap, direction=direction) +
                            recursive_xy_cut(bottom_group, min_x_gap, min_y_gap, direction=direction))
                break
                    
    # Fallback para layouts encaixados/irregulares sem corredor livre contínuo em X nem em Y.
    def panel_cmp(pA, pB):
        boxA = bounds[id(pA)]
        boxB = bounds[id(pB)]
        y_overlap = max(0, min(boxA[3], boxB[3]) - max(boxA[1], boxB[1]))
        hA = boxA[3] - boxA[1]
        hB = boxB[3] - boxB[1]
        if y_overlap > min(hA, hB) * 0.25:
            cxA = (boxA[0] + boxA[2]) / 2
            cxB = (boxB[0] + boxB[2]) / 2
            if abs(cxA - cxB) > 20:
                if is_ltr:
                    return -1 if cxA < cxB else 1
                return -1 if cxA > cxB else 1
        if abs(boxA[1] - boxB[1]) > 20:
            return -1 if boxA[1] < boxB[1] else 1
        if is_ltr:
            return -1 if boxA[0] < boxB[0] else 1
        return -1 if boxA[2] > boxB[2] else 1

    return sorted(panels, key=cmp_to_key(panel_cmp))


def _bubble_xy_cut(bubbles: list[dict], min_x_gap=10, min_y_gap=15, direction="rtl") -> list[dict]:
    """
    Particiona e ordena recursivamente balões de fala em ordem de leitura (RTL oriental ou LTR ocidental).
    """
    if len(bubbles) <= 1:
        return bubbles

    is_ltr = str(direction).strip().lower() == "ltr"
        
    # Encolhe cada caixa em até 15% para achar calhas reais entre balões próximos
    y_intervals = []
    for b in bubbles:
        sy = min(15, (b["y2"] - b["y1"]) * 0.15)
        y_intervals.append((b["y1"] + sy, b["y2"] - sy))
    y_intervals.sort()
    
    y_gaps = []
    max_y_end = y_intervals[0][1]
    for current in y_intervals[1:]:
        if current[0] > max_y_end:
            y_gaps.append((current[0] - max_y_end, max_y_end, current[0]))
        max_y_end = max(max_y_end, current[1])
            
    x_intervals = []
    for b in bubbles:
        sx = min(15, (b["x2"] - b["x1"]) * 0.15)
        x_intervals.append((b["x1"] + sx, b["x2"] - sx))
    x_intervals.sort()
    
    x_gaps = []
    max_x_end = x_intervals[0][1]
    for current in x_intervals[1:]:
        if current[0] > max_x_end:
            x_gaps.append((current[0] - max_x_end, max_x_end, current[0]))
        max_x_end = max(max_x_end, current[1])
        
    best_y_gap = max(y_gaps, key=lambda x: x[0]) if y_gaps else (0, 0, 0)
    best_x_gap = max(x_gaps, key=lambda x: x[0]) if x_gaps else (0, 0, 0)
    
    # Dentro de um mesmo quadro, colunas de fala têm prioridade (multiplicador 0.5) sobre
    # quebras horizontais pequenas para manter a leitura vertical de balões empilhados.
    if best_x_gap[0] >= min_x_gap and best_x_gap[0] >= best_y_gap[0] * 0.5:
        gaps_to_check = x_gaps if is_ltr else reversed(x_gaps)
        for gap in gaps_to_check:
            if gap[0] == best_x_gap[0]:
                cut_x = (gap[1] + gap[2]) / 2
                if is_ltr:
                    first_group = [b for b in bubbles if b["x2"] - min(15, (b["x2"]-b["x1"])*0.15) < cut_x]
                    second_group = [b for b in bubbles if b not in first_group]
                else:
                    first_group = [b for b in bubbles if b["x1"] + min(15, (b["x2"]-b["x1"])*0.15) > cut_x]
                    second_group = [b for b in bubbles if b not in first_group]
                # Só recursa se ambos os lados tiverem itens; evita loop infinito quando um corte falha
                if first_group and second_group:
                    return (_bubble_xy_cut(first_group, min_x_gap, min_y_gap, direction=direction) +
                            _bubble_xy_cut(second_group, min_x_gap, min_y_gap, direction=direction))
                break
                
    if best_y_gap[0] >= min_y_gap:
        for gap in y_gaps:
            if gap[0] == best_y_gap[0]:
                cut_y = (gap[1] + gap[2]) / 2
                top_group = [b for b in bubbles if b["y2"] - min(15, (b["y2"]-b["y1"])*0.15) < cut_y]
                bottom_group = [b for b in bubbles if b not in top_group]
                if top_group and bottom_group:
                    return (_bubble_xy_cut(top_group, min_x_gap, min_y_gap, direction=direction) +
                            _bubble_xy_cut(bottom_group, min_x_gap, min_y_gap, direction=direction))
                break
                
    # Sem corte livre: par em cascata diagonal encostada (>= 45% de desnível vertical) é lido de cima para baixo
    if len(bubbles) == 2:
        b0, b1 = bubbles[0], bubbles[1]
        ix = min(b0["x2"], b1["x2"]) - max(b0["x1"], b1["x1"])
        iy = min(b0["y2"], b1["y2"]) - max(b0["y1"], b1["y1"])
        h0, h1 = b0["y2"] - b0["y1"], b1["y2"] - b1["y1"]
        cy0, cy1 = (b0["y1"] + b0["y2"]) * 0.5, (b1["y1"] + b1["y2"]) * 0.5
        if ix >= -10 and iy >= -10 and abs(cy0 - cy1) >= 0.45 * min(h0, h1):
            return sorted(bubbles, key=lambda b: (b["y1"] + b["y2"]) * 0.5)

    # Fallback por faixas (buckets) de coluna quando os balões formam um bloco único sem gaps
    if len(bubbles) > 0:
        avg_w = sum((b["x2"] - b["x1"]) for b in bubbles) / len(bubbles)
        bucket_x = max(50, avg_w * 0.5)
        if is_ltr:
            return sorted(bubbles, key=lambda b: (
                (((b["x1"] + b["x2"]) / 2) // bucket_x), 
                ((b["y1"] + b["y2"]) / 2)
            ))
        # Sinal negativo na coluna X faz a coluna mais à direita vir primeiro no mangá
        return sorted(bubbles, key=lambda b: (
            -(((b["x1"] + b["x2"]) / 2) // bucket_x), 
            ((b["y1"] + b["y2"]) / 2)
        ))
    return bubbles


def _bubble_panel_overlap_ratio(bubble: dict, panel: dict) -> float:
    """
    Calcula a fração da área do balão que intersecta o polígono (ou AABB) do painel.
    Permite atribuir corretamente balões que estouram a borda do painel mas têm maior
    interseção geométrica com ele.
    """
    bx1, by1 = float(bubble.get("x1", 0)), float(bubble.get("y1", 0))
    bx2, by2 = float(bubble.get("x2", 0)), float(bubble.get("y2", 0))
    b_area = max(1.0, (bx2 - bx1) * (by2 - by1))

    poly = panel.get("polygon")
    if poly and len(poly) >= 3:
        try:
            import cv2
            import numpy as np
            b_pts = np.array([[bx1, by1], [bx2, by1], [bx2, by2], [bx1, by2]], dtype=np.float32)
            p_pts = np.array(poly, dtype=np.float32)
            inter_area, _ = cv2.intersectConvexConvex(b_pts, p_pts)
            return float(max(0.0, inter_area)) / b_area
        except Exception:
            pass

    px1, py1, px2, py2 = [float(v) for v in panel.get("box", [0, 0, 0, 0])]
    ix1, iy1 = max(bx1, px1), max(by1, py1)
    ix2, iy2 = min(bx2, px2), min(by2, py2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    return float((ix2 - ix1) * (iy2 - iy1)) / b_area


def sort_bubbles_reading_order(bubbles: list[dict], panels: list[dict] = None, direction: str = "rtl") -> list[dict]:
    """
    Ordena uma lista de balões na ordem canônica de leitura (RTL para Mangá, LTR para Western comics),
    respeitando os painéis/quadros caso fornecidos.

    Balões de fala legítimos (diálogos) recebem ordenação sequencial estrita (order: 1..N).
    Efeitos sonoros e onomatopeias (is_sfx: True) são dissociados da sequência de fala
    para não corromper o fluxo narrativo nem a tradução.
    """
    if not bubbles:
        return []

    # Separação preservativa entre falas formais e SFX/onomatopeias
    speech_bubbles = []
    sfx_bubbles = []
    for b in bubbles:
        is_sfx = bool(b.get("is_sfx", False) or b.get("label") == "text_free" or b.get("bg_type") == "sfx")
        if is_sfx:
            sfx_bubbles.append(dict(b))
        else:
            speech_bubbles.append(dict(b))

    ordered_speech_data = []
    if speech_bubbles:
        if not panels:
            for b in speech_bubbles:
                b["panel_id"] = -1
            ordered_speech_data = _bubble_xy_cut(speech_bubbles, min_x_gap=15, min_y_gap=20, direction=direction)
        else:
            panel_to_clusters = defaultdict(list)
            unassigned = []
            
            # 1. Atribuição de balões aos painéis (prioriza maior fração de área sobreposta ao polígono + centro contido)
            for item in speech_bubbles:
                cx = (item["x1"] + item["x2"]) / 2
                cy = (item["y1"] + item["y2"]) / 2
                best_pidx = -1
                best_score = 0.0
                for pidx, p in enumerate(panels):
                    ov_ratio = _bubble_panel_overlap_ratio(item, p)
                    center_in = is_point_in_panel((cx, cy), p, tolerance_px=0.0)
                    upward_eruption_bonus = 0.0
                    chained_to_upper_bonus = 0.0
                    poly = p.get("polygon")
                    if ov_ratio >= 0.25 and poly and len(poly) == 4:
                        dx_top = poly[1][0] - poly[0][0]
                        p_top_y = float(poly[0][1]) if abs(dx_top) < 1e-4 else poly[0][1] + (poly[1][1] - poly[0][1]) * ((cx - poly[0][0]) / float(dx_top))
                        dx_bot = poly[2][0] - poly[3][0]
                        p_bot_y = float(poly[3][1]) if abs(dx_bot) < 1e-4 else poly[3][1] + (poly[2][1] - poly[3][1]) * ((cx - poly[3][0]) / float(dx_bot))
                        if (ov_ratio >= 0.30
                                and p_bot_y > p_top_y + 60
                                and item["y1"] < p_top_y - 25
                                and item["y2"] - p_top_y >= 100
                                and item["y2"] >= p_top_y + 0.50 * (p_bot_y - p_top_y)):
                            # Balão ancorado na metade inferior do quadro `p` que explode para cima cruzando a calha superior
                            upward_eruption_bonus = 0.45
                        elif item["y1"] < p_bot_y - 60 and item["y2"] > p_bot_y + 40:
                            # Balão na base de uma cascata do quadro `p` que transborda a borda inferior,
                            # mas possui interseção física direta com um balão contido em `p`.
                            for other in speech_bubbles:
                                if other is item:
                                    continue
                                if (min(item["x2"], other["x2"]) > max(item["x1"], other["x1"])
                                        and min(item["y2"], other["y2"]) > max(item["y1"], other["y1"])
                                        and (other["y1"] + other["y2"]) * 0.5 < cy - 80
                                        and _bubble_panel_overlap_ratio(other, p) >= 0.85):
                                    chained_to_upper_bonus = 0.60
                                    break

                    score = ov_ratio + (0.25 if center_in else 0.0) + upward_eruption_bonus + chained_to_upper_bonus
                    if (ov_ratio >= 0.15 or center_in) and score > best_score:
                        best_score = score
                        best_pidx = pidx

                if best_pidx != -1:
                    panel_to_clusters[best_pidx].append(item)
                    continue

                assigned = False
                for pidx, p in enumerate(panels):
                    if is_point_in_panel((cx, cy), p, tolerance_px=15.0):
                        panel_to_clusters[pidx].append(item)
                        assigned = True
                        break
                if not assigned:
                    unassigned.append(item)
                
            # 2. Adoção por proximidade imediata (balões que vazam a moldura do quadro em até 40px)
            truly_unassigned = []
            for item in unassigned:
                cx = (item["x1"] + item["x2"]) / 2
                cy = (item["y1"] + item["y2"]) / 2
                best_dist = float('inf')
                best_pidx = -1
                for pidx, p in enumerate(panels):
                    px1, py1, px2, py2 = p["box"]
                    dx = max(0, px1 - cx, cx - px2)
                    dy = max(0, py1 - cy, cy - py2)
                    # Penalidade vertical severa (8x): a separação de linhas em mangás é sagrada
                    dist = dx * dx + 8.0 * (dy * dy)
                    if dx <= 40 and dy <= 40 and dist < best_dist:
                        best_dist = dist
                        best_pidx = pidx
                if best_pidx != -1:
                    panel_to_clusters[best_pidx].append(item)
                else:
                    truly_unassigned.append(item)
                        
            unified_panels = []
            for pidx, p in enumerate(panels):
                if pidx in panel_to_clusters and panel_to_clusters[pidx]:
                    for b in panel_to_clusters[pidx]:
                        b["panel_id"] = pidx + 1
                    unified_panels.append({
                        "type": "real_panel",
                        "box": p["box"],
                        "polygon": p.get("polygon"),
                        "bubbles": panel_to_clusters[pidx]
                    })
                    
            # 3. Órfãos distantes (cenas abertas/sem borda ou quadros não detectados):
            # Agrupa órfãos próximos em painéis virtuais para manter sua integridade espacial
            unassigned_groups = []
            for b in truly_unassigned:
                merged_into_group = False
                for grp in unassigned_groups:
                    gx1, gy1, gx2, gy2 = grp["box"]
                    bx1, by1, bx2, by2 = b["x1"], b["y1"], b["x2"], b["y2"]
                    dx = max(0, gx1 - bx2, bx1 - gx2)
                    dy = max(0, gy1 - by2, by1 - gy2)
                    if dx <= 60 and dy <= 60:
                        grp["bubbles"].append(b)
                        grp["box"] = [min(gx1, bx1), min(gy1, by1), max(gx2, bx2), max(gy2, by2)]
                        merged_into_group = True
                        break
                if not merged_into_group:
                    unassigned_groups.append({
                        "type": "virtual_panel",
                        "box": [b["x1"], b["y1"], b["x2"], b["y2"]],
                        "bubbles": [b]
                    })

            for v_idx, grp in enumerate(unassigned_groups):
                v_pid = len(panels) + v_idx + 1
                for b in grp["bubbles"]:
                    b["panel_id"] = v_pid
                unified_panels.append(grp)

            sorted_unified_panels = recursive_xy_cut(unified_panels, direction=direction)
            
            for p in sorted_unified_panels:
                panel_bubbles = _bubble_xy_cut(p["bubbles"], min_x_gap=15, min_y_gap=20, direction=direction)
                ordered_speech_data.extend(panel_bubbles)
                
    final_bubbles = []
    for idx, b in enumerate(ordered_speech_data):
        b_copy = dict(b)
        b_copy["order"] = idx + 1
        if not b_copy.get("id"):
            b_copy["id"] = idx + 1
        if "text" not in b_copy:
            b_copy["text"] = ""
        b_copy["is_sfx"] = False
        b_copy["is_bubble"] = True
        final_bubbles.append(b_copy)

    # Associa SFX aos painéis correspondentes sem poluir a numeração de fala
    processed_sfx = []
    for s in sfx_bubbles:
        s_copy = dict(s)
        s_copy["is_sfx"] = True
        s_copy["is_bubble"] = False
        s_copy["bg_type"] = "sfx"
        s_copy["label"] = "text_free"
        s_copy["order"] = None
        if "text" not in s_copy:
            s_copy["text"] = ""

        if panels:
            cx = (s_copy["x1"] + s_copy["x2"]) / 2
            cy = (s_copy["y1"] + s_copy["y2"]) / 2
            best_pidx = -1
            best_score = 0.0
            for pidx, p in enumerate(panels):
                ov = _bubble_panel_overlap_ratio(s_copy, p)
                cin = is_point_in_panel((cx, cy), p, tolerance_px=0.0)
                score = ov + (0.5 if cin else 0.0)
                if (ov >= 0.15 or cin) and score > best_score:
                    best_score = score
                    best_pidx = pidx
            if best_pidx != -1:
                s_copy["panel_id"] = best_pidx + 1
            else:
                min_d = float('inf')
                for pidx, p in enumerate(panels):
                    px1, py1, px2, py2 = p["box"]
                    dx = max(0, px1 - cx, cx - px2)
                    dy = max(0, py1 - cy, cy - py2)
                    d = dx * dx + 8.0 * (dy * dy)
                    if dx <= 60 and dy <= 60 and d < min_d:
                        min_d = d
                        best_pidx = pidx
                s_copy["panel_id"] = (best_pidx + 1) if best_pidx != -1 else (len(panels) + 1)
        else:
            s_copy["panel_id"] = -1

        processed_sfx.append(s_copy)

    # Ordena SFX espacialmente (painel primeiro, topo para base; RTL: direita para esquerda, LTR: esquerda para direita)
    is_ltr = str(direction).strip().lower() == "ltr"
    if is_ltr:
        processed_sfx.sort(key=lambda s: (s.get("panel_id", 999), s.get("y1", 0), s.get("x1", 0)))
    else:
        processed_sfx.sort(key=lambda s: (s.get("panel_id", 999), s.get("y1", 0), -s.get("x2", 0)))
    for s_copy in processed_sfx:
        if not s_copy.get("id"):
            s_copy["id"] = len(final_bubbles) + 1
        final_bubbles.append(s_copy)

    return final_bubbles
