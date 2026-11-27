import re
from src.config import Config


_COMMON_PORTUGUESE_STARTERS = {
    # Artigos e pronomes
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "ele", "ela", "eles", "elas", "você", "vocês", "nós", "eu", "tu", "vós",
    "meu", "minha", "meus", "minhas", "seu", "sua", "seus", "suas",
    "nosso", "nossa", "nossos", "nossas", "teu", "tua", "teus", "tuas",
    "dele", "dela", "deles", "delas",
    "este", "esta", "estes", "estas", "isto",
    "esse", "essa", "esses", "essas", "isso",
    "aquele", "aquela", "aqueles", "aquelas", "aquilo",
    "quem", "qual", "quais", "quanto", "quanta", "quantos", "quantas",
    "alguém", "ninguém", "tudo", "nada", "algo", "todos", "todas", "todo", "toda",
    "outro", "outra", "outros", "outras", "mesmo", "mesma", "mesmos", "mesmas",
    # Preposições e conjunções
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "pelo", "pela", "pelos", "pelas", "para", "pra", "pro", "pras", "pros",
    "com", "sem", "sob", "sobre", "entre", "até", "desde", "após",
    "e", "ou", "mas", "porém", "contudo", "todavia", "entretanto",
    "porque", "por que", "por quê", "porquê", "pois",
    "que", "se", "quando", "onde", "como", "embora", "caso",
    # Advérbios e marcadores temporais/espaciais
    "não", "sim", "já", "ainda", "agora", "então", "depois", "antes",
    "sempre", "nunca", "jamais", "talvez",
    "aqui", "aí", "ali", "lá", "cá",
    "muito", "pouco", "mais", "menos", "tão", "tanto", "quase", "apenas", "só", "somente",
    "bem", "mal", "assim", "melhor", "pior", "cedo", "tarde",
    # Formas verbais e auxiliares comuns no início de sentenças
    "é", "era", "foi", "será", "seria", "são", "eram", "foram", "serão", "seriam", "seja", "sejam",
    "está", "estou", "estava", "esteve", "estarão", "estão", "esteja", "estejam",
    "tem", "tenho", "tinha", "teve", "terá", "teriam", "têm", "tenham",
    "haver", "há", "havia", "houve", "haverá",
    "vai", "vou", "vamos", "vão", "ia", "fui", "fora", "vá",
    "pode", "posso", "podemos", "podem", "podia", "pude", "pudera",
    "deve", "devo", "devemos", "devem", "devia",
    "sabe", "sei", "sabemos", "sabem", "sabia",
    "acha", "acho", "achamos", "acham", "achava",
    "quer", "quero", "queremos", "querem", "queria", "quis",
    "olha", "olhe", "olhem", "veja", "vejam", "viu", "ver", "repare",
    "ouça", "escute", "escutem", "ouvi", "ouviu",
    "espere", "espera", "esperem", "aguarde", "calma",
    "pare", "para", "parem", "chega", "basta",
    "deixe", "deixa", "deixem", "largue", "larga",
    "fale", "fala", "falou", "diga", "diz", "disse", "conte", "conta",
    "venha", "vem", "venham", "chegue", "saia", "sai", "saiam", "corra", "corre", "corram",
    "tome", "toma", "pegue", "pega", "pegou",
    # Formas verbais conversacionais expandidas (evita falsos positivos de nome próprio em início de balão)
    "parece", "parecem", "parecia", "preciso", "precisa", "precisamos", "precisam",
    "tento", "tenta", "tentamos", "tente", "tentem", "tentar",
    "consigo", "consegue", "conseguimos", "conseguem",
    "duvido", "imagino", "imagine", "imagina",
    "lembro", "lembra", "lembre", "lembrem",
    "acredito", "acredita", "acredite", "acreditam",
    "juro", "prometo", "espero", "esperava", "esperem",
    "entendo", "entende", "entendemos", "entendem",
    "sinto", "sente", "sentimos", "sentia",
    "conheço", "conhece", "conhecem",
    "gosto", "gosta", "odeio", "adoro", "prefiro",
    "deveria", "poderia", "iria", "seria", "faria", "teria", "saberia", "falaria",
    "pensava", "pensando", "pensou", "pense", "pensem", "pensa", "penso",
    "aposto", "garanto", "avisei", "avisando",
    "certeza", "exato", "exatamente",
    # Interjeições e saudações comuns
    "oi", "olá", "ei", "opa", "epa", "psiu", "eita", "uai", "oxe",
    "uau", "oba", "viva", "nossa", "puxa", "droga", "merda", "porra", "caramba",
    "putz", "socorro", "atenção", "cuidado", "perigo", "adeus", "tchau",
    "por favor", "obrigado", "obrigada", "valeu", "desculpe", "desculpa", "perdão",
    "claro", "certo", "entendi", "beleza", "combinado", "perfeito", "ótimo", "tudo bem",
}

_DESIGNATION_PREFIXES = {
    "capítulo", "capitulo", "cap.", "volume", "vol.", "parte", "fase", "ato",
    "livro", "século", "seculo", "séc.", "sec.", "episódio", "episodio", "ep.",
    "temporada", "temp.", "geração", "geracao", "classe", "grau", "nível", "nivel"
}


def _is_sentence_starter(preceding: str) -> bool:
    """Identifica se uma posição na string é início de frase respeitando reticências e abreviações."""
    p = preceding.rstrip()
    if not p:
        return True
    p_core = p.rstrip('"\'”)»]')
    if not p_core:
        return True
    if p_core.endswith(('...', '…', '--', '—')):
        return True
    if p_core.endswith('.'):
        if re.search(r'\b[A-Za-zÀ-Ý]\.$', p_core):
            return False
        return True
    if p_core[-1] in ('.', '!', '?', '\n', ':', ';', '(', '[', '“', '"', '«', '—'):
        return True
    return False


def _extract_proper_nouns_from_instructions(custom_instructions: str) -> list[str]:
    """Extrai nomes próprios, siglas e termos capitalizados definidos nas instruções/glossário."""
    if not custom_instructions or not isinstance(custom_instructions, str):
        return []

    candidates = set()

    # 1. Captura alvos em mapeamentos do tipo 'A -> B' ou 'A => B'
    for match in re.finditer(r'(?:->|=>)\s*([A-Za-zÀ-Ý0-9_.\-\'\s]+?)(?:[,\n;\/]|$)', custom_instructions):
        val = match.group(1).strip()
        if val and len(val) >= 2:
            candidates.add(val)

    # 2. Captura termos entre aspas
    for match in re.finditer(r'["\']([A-Za-zÀ-Ý0-9_.\-\'\s]{2,})["\']', custom_instructions):
        candidates.add(match.group(1).strip())

    # 3. Captura siglas em caixa alta (ex: ONU, FBI, EUA, SSJ)
    for match in re.finditer(r'\b[A-ZÀ-Ý]{2,}\b', custom_instructions):
        candidates.add(match.group(0))

    # 4. Captura nomes próprios capitalizados simples e compostos
    for match in re.finditer(r'\b[A-ZÀ-Ý][a-zà-ÿ]+(?:[\s\-][A-ZÀ-Ýa-zà-ÿ]+)*\b', custom_instructions):
        candidates.add(match.group(0))

    # Filtra palavras reservadas dos cabeçalhos das instruções
    reserved_headers = {
        "glossário", "glossario", "glossary", "instruções", "instrucoes", "highest", "priority",
        "work-specific", "work", "specific", "override", "everything", "above", "conflict",
        "apply", "these", "translations", "strictly", "whenever", "terms", "appear",
        "exemplo", "exemplos", "regra", "regras", "nota", "importante", "atenção"
    }

    filtered = [
        c for c in candidates
        if not any(part in reserved_headers for part in re.split(r'[\s\-]+', c.lower())) and len(c) >= 2
    ]
    return sorted(filtered, key=len, reverse=True)


def _apply_intelligent_casing(text: str, preserve_terms: list[str] | None = None) -> str:
    """
    Aplica normalização de caixa inteligente sem destruir nomes próprios, siglas ou pontuação:
    - Preserva siglas pontuadas (E.U.A., U.S.A., K.O.).
    - Preserva siglas e gritos em caixa alta (FBI, ONU, SSJ, SSGSS, MONSTRO, BOOM).
    - Preserva numerais romanos (IV, VII, XXI e I/V após designações como 'Capítulo I').
    - Preserva nomes próprios em início de frase que não são palavras comuns do português.
    - Preserva nomes próprios no meio da frase com inicial maiúscula (Sasuke, Tóquio, Naruto).
    - Preserva termos do glossário e palavras com caixa mista (McDonald's, Doki-Doki).
    - Preserva 100% da pontuação artística e símbolos de mangá (?!, !?, ..., —, ♪, ★, ☆, 〜, ~).
    """
    if not text:
        return ""

    pattern = re.compile(r'(\[.*?\]|\b(?:[A-Za-zÀ-Ý]\.){2,}|\b[A-Za-zÀ-Ýa-zà-ÿ0-9_\-\']+\b)')
    last_idx = 0
    pieces = []

    term_lookup = {}
    if preserve_terms:
        for t in preserve_terms:
            if t and len(t) >= 2:
                term_lookup[t.lower()] = t

    for match in pattern.finditer(text):
        start, end = match.span()
        pieces.append(text[last_idx:start])
        token = match.group(0)

        # 1. Tags estruturais ([CORTE], [DELETE], etc.)
        if token.startswith('[') and token.endswith(']'):
            pieces.append(token)
            last_idx = end
            continue

        token_lower = token.lower()

        # 2. Termo explícito no glossário/preserve_terms
        if token_lower in term_lookup:
            pieces.append(term_lookup[token_lower])
            last_idx = end
            continue

        # 3. Siglas pontuadas (ex: E.U.A., U.S.A., K.O.)
        if re.fullmatch(r'(?:[A-Za-zÀ-Ý]\.){2,}', token):
            pieces.append(token.upper())
            last_idx = end
            continue

        clean_letters = re.sub(r'[^A-Za-zÀ-Ý]', '', token)

        # 4. Palavras inteiras em maiúsculas com 2+ letras (Siglas: FBI, ONU, SSJ; Gritos: MONSTRO; Romanos: IV, VII, XXI)
        if len(clean_letters) >= 2 and token.isupper():
            pieces.append(token)
            last_idx = end
            continue

        # 5. Numerais Romanos isolados (I, V, X) após palavras de designação (Capítulo I, Volume V)
        if token_lower in ("i", "v", "x"):
            preceding_words = re.findall(r'[A-Za-zÀ-Ýa-zà-ÿ]+', text[:start].lower())
            if preceding_words and preceding_words[-1] in _DESIGNATION_PREFIXES:
                pieces.append(token.upper())
                last_idx = end
                continue

        # 6. Palavras com caixa mista interna / camelCase (McDonald's, iPhone, DeLorean)
        if any(c.isupper() for c in token[1:]) and any(c.islower() for c in token):
            pieces.append(token)
            last_idx = end
            continue

        # 7. Palavras hifenizadas com partes capitalizadas (Doki-Doki, Spider-Man, Ba-Dump)
        if '-' in token and any(part and part[0].isupper() for part in token.split('-')):
            pieces.append(token)
            last_idx = end
            continue

        # 8. Análise de fronteira de sentença
        preceding_text = text[:start]
        is_starter = _is_sentence_starter(preceding_text)

        if is_starter:
            if token_lower in _COMMON_PORTUGUESE_STARTERS:
                pieces.append(token_lower)
            else:
                # Palavra com inicial maiúscula não-comum no início da frase (Nome próprio: Sasuke, Goku, Tóquio)
                pieces.append(token)
        else:
            # No meio da sentença: se veio com inicial maiúscula, é Nome Próprio
            if token and token[0].isupper():
                pieces.append(token)
            else:
                pieces.append(token_lower)

        last_idx = end

    pieces.append(text[last_idx:])
    result = "".join(pieces)

    # Aplica substituição para termos preservados compostos (multi-word, ex: "Kage Bunshin", "Son Goku")
    if preserve_terms:
        for t in preserve_terms:
            if t and " " in t:
                result = re.sub(rf'\b{re.escape(t)}\b', t, result, flags=re.IGNORECASE)

    return result


def sanitize_translated_text(
    text: str,
    preserve_terms: list[str] | None = None,
    preserve_case: bool | None = None,
) -> str:
    """Higieniza e valida o texto traduzido retornado pelo LLM contra alucinações, prefixos e loops."""
    if not text or not isinstance(text, str):
        return ""
    cleaned = text.strip()

    # 0. Strip defensivo de eventuais tags de reasoning residuais (<think>...</think>)
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'</?think>', '', cleaned, flags=re.IGNORECASE).strip()

    # 1. Remove blocos de markdown residuais
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned)

    # 2. Remove prefixos meta-discursivos comuns de LLMs (Tradução:, Tradução PT-BR:, etc.)
    cleaned = re.sub(
        r'^(?:tradu[çc][ãa]o(?:\s+(?:pt-br|pt|para\s+o\s+portugu[êe]s))?|traduzido|pt-br|portugu[êe]s|resposta|nota|sentido|significado):\s*',
        '',
        cleaned,
        flags=re.IGNORECASE,
    )

    # 3. Remove aspas externas redundantes inseridas pelo LLM preservando o conteúdo
    for q_open, q_close in [('"', '"'), ("'", "'"), ('“', '”'), ('«', '»'), ('”', '”'), ('「', '」')]:
        if cleaned.startswith(q_open) and cleaned.endswith(q_close) and len(cleaned) >= (len(q_open) + len(q_close)):
            cleaned = cleaned[len(q_open):-len(q_close)].strip()
            break

    # 4. Trata loops degenerativos de repetição do LLM:
    # Se uma palavra (3+ caracteres) se repete 4 ou mais vezes consecutivas, colapsa para 2
    cleaned = re.sub(r'(\b\w{3,}\b)(?:\s+\1){3,}', r'\1 \1', cleaned, flags=re.IGNORECASE)
    # Se uma frase curta (2 a 4 palavras) se repete 3 ou mais vezes consecutivas, colapsa para 1
    cleaned = re.sub(r'(\b\w+(?:\s+\w+){1,3}\b)(?:\s+\1){2,}', r'\1', cleaned, flags=re.IGNORECASE)

    # 5. Normaliza espaços múltiplos
    cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()

    # 6. Preserva gritos de combate e exclamações de impacto em caixa alta (M5)
    # ou caixa original quando configurado (preserve_case / preserve_translation_case).
    if cleaned.isupper():
        return cleaned
    if preserve_case is None:
        preserve_case = bool(Config.get("preserve_translation_case", False))
    if preserve_case:
        return cleaned

    # 7. Normalização inteligente com preservação de siglas, nomes próprios, numerais e pontuação artística
    return _apply_intelligent_casing(cleaned, preserve_terms=preserve_terms)


_DRAMATIC_PUNCT_PATTERNS = [
    ("?!", "?!"),
    ("!?", "!?"),
    ("??", "??"),
    ("!!", "!!"),
    ("...", "..."),
    ("…", "…"),
    ("—", "—"),
    ("~", "~"),
    ("!", "!"),
    ("?", "?"),
]


def sync_trailing_punctuation(original: str, translated: str) -> str:
    """
    Restaura a pontuação dramática/expressiva do original se o LLM tiver 'achatado'
    o balão para um ponto final simples ou omitido a pontuação terminal.
    """
    if not original or not translated or not isinstance(original, str) or not isinstance(translated, str):
        return translated

    orig = original.strip()
    trad = translated.strip()
    if not orig or not trad:
        return trad

    # Identifica a pontuação terminal expressiva do original
    orig_terminal = None
    for pattern, target in _DRAMATIC_PUNCT_PATTERNS:
        if orig.endswith(pattern):
            orig_terminal = target
            break

    if not orig_terminal:
        return trad

    # Se a tradução já termina com pontuação dramática equivalente, não altera
    if trad.endswith(orig_terminal):
        return trad
    if orig_terminal in ("?!", "!?") and trad.endswith(("?!", "!?")):
        return trad
    if orig_terminal in ("...", "…") and trad.endswith(("...", "…")):
        return trad

    # Se a tradução terminou com ponto final simples, substitui pelo terminal expressivo do original
    if trad.endswith("."):
        return trad[:-1].rstrip() + orig_terminal

    # Se a tradução terminou sem pontuação terminal (letra, número ou fechamento)
    if trad[-1] not in ".!?…—~":
        return trad + orig_terminal

    return trad



TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["id", "text"],
            },
        }
    },
    "required": ["translations"],
}
