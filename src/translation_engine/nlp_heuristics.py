import re

def semantic_split_text(text: str, num_parts: int, original_lengths: list[int] = None) -> list[str]:
    """
    Divide um texto em num_parts de forma proporcional e gramaticalmente natural.
    Utiliza regex flexível para capturar [CORTE] em qualquer variação (maiúsculas, minúsculas, [CUT], [SPLIT]).
    """
    if num_parts <= 1 or not text or not text.strip():
        # Remove qualquer resíduo de tag
        clean = re.sub(r'\[\s*(?:corte|cut|split|quebra|break)\s*\]', '', text or '', flags=re.IGNORECASE).strip()
        return [clean]
        
    # 1. Busca por tags de corte com regex flexível (ex: [CORTE], [corte], [CUT], [SPLIT])
    split_pattern = re.compile(r'\[\s*(?:corte|cut|split|quebra|break)\s*\]', flags=re.IGNORECASE)
    raw_parts = [p.strip() for p in split_pattern.split(text) if p.strip()]
    
    if len(raw_parts) == num_parts:
        return raw_parts
        
    # 2. Se houver mais partes que o necessário, funde as excedentes no final
    if len(raw_parts) > num_parts:
        res = raw_parts[:num_parts - 1]
        res.append(" ".join(raw_parts[num_parts - 1:]).strip())
        return res
        
    # 3. Fallback semântico: se a IA esqueceu a tag ou retornou partes insuficientes
    clean_text = split_pattern.sub(" ", text).strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    words = clean_text.split()
    if len(words) <= num_parts:
        res = words + [""] * (num_parts - len(words))
        return res[:num_parts]
        
    if original_lengths and sum(original_lengths) > 0:
        total_len = sum(original_lengths)
        ratios = [l / total_len for l in original_lengths]
    else:
        ratios = [1.0 / num_parts] * num_parts
    
    target_char_indices = []
    accum = 0.0
    for r in ratios[:-1]:
        accum += r
        target_char_indices.append(int(len(clean_text) * accum))
        
    split_points = []
    last_idx = 0
    for target in target_char_indices:
        best_pt = None
        best_dist = float('inf')
        
        window_start = max(last_idx + 3, target - 25)
        window_end = min(len(clean_text) - 3, target + 25)
        
        if window_start < window_end:
            # Preferência 1: Pontuação natural atômica (preserva pontuação combinada típica de mangá: !?, ?!, ..., —, etc.)
            for p_match in re.finditer(r'(\?!|!\?|\.\.\.|…|--|—|[!?,;~])\s*', clean_text[window_start:window_end]):
                pt = window_start + p_match.end()
                dist = abs(pt - target)
                if dist < best_dist:
                    best_dist = dist
                    best_pt = pt
                    
            # Preferência 2: Conjunções / Conectivos
            if best_pt is None:
                for c_match in re.finditer(r'\s+(mas|porém|porque|que|quando|então|e|se|onde)\s+', clean_text[window_start:window_end], re.IGNORECASE):
                    pt = window_start + c_match.start() + 1
                    dist = abs(pt - target)
                    if dist < best_dist:
                        best_dist = dist
                        best_pt = pt
                        
            # Preferência 3: Espaço mais próximo
            if best_pt is None:
                for s_match in re.finditer(r'\s+', clean_text[window_start:window_end]):
                    pt = window_start + s_match.end()
                    dist = abs(pt - target)
                    if dist < best_dist:
                        best_dist = dist
                        best_pt = pt
                        
        if best_pt is None:
            best_pt = max(last_idx + 1, min(target, len(clean_text) - 1))
            
        split_points.append(best_pt)
        last_idx = best_pt
        
    result = []
    curr = 0
    for pt in split_points:
        result.append(clean_text[curr:pt].strip())
        curr = pt
    result.append(clean_text[curr:].strip())
    
    clean_strip_pattern = re.compile(r'\[\s*(?:corte|cut|split|quebra|break)\s*\]', flags=re.IGNORECASE)
    return [clean_strip_pattern.sub('', p).strip() for p in result]

def safe_bubble_sort_key(b, default_idx=0):
    raw_pid = b.get("panel_id")
    try:
        pid = int(raw_pid) if raw_pid is not None else 0
    except (ValueError, TypeError):
        pid = 0
    raw_order = b.get("order")
    if raw_order is None:
        raw_order = b.get("id")
    try:
        order = int(raw_order) if raw_order is not None else default_idx
    except (ValueError, TypeError):
        order = default_idx
    return (pid, order)

def auto_link_speech_bubbles(bubbles: list[dict]) -> list[dict]:
    """
    Analisa os balões da página e atribui group_id para orações contínuas divididas com '...' ou '-'.
    Respeita rigorosamente links manuais já definidos pelo usuário.
    Ignora balões contendo apenas silêncio dramático ('...', '…', '---').
    """
    if not bubbles or len(bubbles) < 2:
        return bubbles

    sorted_indices = sorted(range(len(bubbles)), key=lambda i: safe_bubble_sort_key(bubbles[i], i))
    
    auto_gid_counter = 1
    i = 0
    while i < len(sorted_indices) - 1:
        idx_curr = sorted_indices[i]
        b_curr = bubbles[idx_curr]
        
        if b_curr.get("group_id"):
            i += 1
            continue
            
        txt_curr = b_curr.get("text", "").strip()
        if not txt_curr:
            i += 1
            continue
            
        # Balões de silêncio puro (apenas reticências/travessões) não iniciam fusão de oração
        if re.fullmatch(r'[\.\s…—\-_~]+', txt_curr):
            i += 1
            continue

        ends_with_split = bool(re.search(r'(\.\.\.|…|—|-|~)\s*$', txt_curr))
        
        ends_with_terminal = bool(re.search(r'[\.\!\?。！？]\s*$', txt_curr)) and not ends_with_split
        can_start_chain = ends_with_split or (not ends_with_terminal and len(txt_curr) >= 2)
        if can_start_chain:
            chain = [idx_curr]
            j = i + 1
            while j < len(sorted_indices):
                idx_next = sorted_indices[j]
                b_next = bubbles[idx_next]
                
                if b_next.get("group_id"):
                    break
                    
                txt_next = b_next.get("text", "").strip()
                if not txt_next:
                    break
                    
                starts_with_cont = bool(re.search(r'^\s*(\.\.\.|…|—|-|~)', txt_next))
                b_prev = bubbles[chain[-1]]
                same_panel = (b_prev.get("panel_id") is not None and b_prev.get("panel_id") == b_next.get("panel_id"))
                first_letter_lower = txt_next and txt_next[0].islower()
                
                is_spatially_close = False
                if same_panel and not b_prev.get("is_sfx") and not b_next.get("is_sfx"):
                    ax1, ay1, ax2, ay2 = b_prev.get("x1", 0), b_prev.get("y1", 0), b_prev.get("x2", 0), b_prev.get("y2", 0)
                    bx1, by1, bx2, by2 = b_next.get("x1", 0), b_next.get("y1", 0), b_next.get("x2", 0), b_next.get("y2", 0)
                    if ax2 > ax1 and bx2 > bx1:
                        y_gap = max(0, by1 - ay2, ay1 - by2)
                        x_gap = max(0, bx1 - ax2, ax1 - bx2)
                        is_spatially_close = (y_gap <= 25 and x_gap <= 35)

                should_link = (
                    starts_with_cont
                    or (same_panel and first_letter_lower)
                    or (same_panel and is_spatially_close and not ends_with_terminal)
                )

                if should_link:
                    chain.append(idx_next)
                    if bool(re.search(r'(\.\.\.|…|—|-|~)\s*$', txt_next)):
                        j += 1
                    else:
                        break
                else:
                    break
                    
            if len(chain) > 1:
                gid = f"auto_{auto_gid_counter}"
                auto_gid_counter += 1
                for c_idx in chain:
                    bubbles[c_idx]["group_id"] = gid
                i = j
                continue
        i += 1
        
    return bubbles
