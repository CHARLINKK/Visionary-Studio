import re

# Dicionário de respostas instantâneas para interjeições e gritos clássicos de mangá (0.0001s, sem chamar LLM)
EXCLAMATION_CACHE = {
    "WHAT?!": "o quê?!", "WHAT?": "o quê?", "WHAT...": "o quê...",
    "WHAT THE?!": "o que é isso?!", "WHAT THE...?!": "o que é isso...?!", "WHAT THE...": "o que é isso...",
    "HUH?": "hã?", "HUH?!": "hã?!", "EH?": "eh?", "EH?!": "eh?!",
    "N-NO WAY!": "de jeito nenhum!", "NO WAY!": "sem chance!", "NO WAY...": "sem chance...",
    "DAMN!": "droga!", "DAMN...": "droga...", "DAMN IT!": "droga!", "DAMN IT...": "droga...",
    "DAMMIT!": "droga!", "DAMMIT...": "droga...", "SHIT!": "merda!", "SHIT...": "merda...",
    "CRAP!": "droga!", "CRAP...": "droga...",
    "BASTARD!": "desgraçado!", "BASTARD...": "desgraçado...", "YOU BASTARD!": "seu desgraçado!",
    "IDIOT!": "idiota!",
    "SHEESH!": "putz!", "SHEESH...": "putz...",
    "TCH!": "tsc!", "TCH...": "tsc...", "TCH": "tsc", "TSK!": "tsc!", "TSK...": "tsc...",
    "UGH!": "ugh!", "UGH...": "ugh...", "OUCH!": "ai!", "OUCH...": "ai...",
    "HEH!": "heh!", "HEH...": "heh...", "HEHE...": "hehe...", "HAHA!": "haha!",
    "WOW!": "uau!", "WOW...": "uau...",
    "GAAAH!": "gaaah!", "AAAAH!": "aaaah!", "URGH!": "urgh!",
    "COME ON!": "vamos!", "COME ON...": "vamos...", "LET'S GO!": "vamos lá!",
    "STOP!": "pare!", "STOP IT!": "para com isso!",
    "WAIT!": "espere!", "WAIT...": "espere...", "HOLD ON!": "espera aí!",
    "SHUT UP!": "cala a boca!", "GET HIM!": "pega ele!",
    "YES!": "sim!", "NO!": "não!", "NO...": "não...",
    "YES, SIR!": "sim, senhor!", "YES, SIR": "sim, senhor!",
    "THANK YOU!": "obrigado!", "THANK YOU...": "obrigado...",
    "COACH!": "treinador!", "COACH...": "treinador...",
    "CAPTAIN!": "capitão!", "CAPTAIN...": "capitão...",
    "BOSS!": "chefe!", "BOSS...": "chefe...",
    "WHOA!": "uau!", "WHOA...": "uau...", "WHOAAA!": "uauuu!",
    "NANI?!": "o quê?!", "NANI?": "o quê?",
    "ARE YOU KIDDING ME?!": "tá de brincadeira comigo?!", "ARE YOU KIDDING?!": "tá de brincadeira?!",
    "DAMN YOU!": "seu maldito!", "YOU BASTARDS!": "seus desgraçados!",
    "GET LOST!": "dá o fora!", "GET OUT!": "saia daqui!",
    "NOT BAD!": "nada mal!", "NOT BAD...": "nada mal...",
    "NEVER MIND!": "deixa pra lá!", "NEVER MIND...": "deixa pra lá...",
    "SORRY!": "desculpa!", "SORRY...": "desculpa...",
    "GET 'EM!": "pega eles!", "GET THEM!": "pega eles!",
    "DON'T MOVE!": "não se mexa!", "DON'T MOVE": "não se mexa",
    "LOOK OUT!": "cuidado!", "LOOK OUT": "cuidado",
    "WATCH OUT!": "cuidado!", "WATCH OUT": "cuidado",
    "OVER HERE!": "aqui!", "OVER THERE!": "lá!",
    "GET DOWN!": "abaixe-se!", "GET DOWN": "abaixe-se",
    "OH NO!": "ah, não!", "OH NO...": "ah, não...", "OH, NO!": "ah, não!",
    "OH SHIT!": "puta merda!", "OH SHIT...": "puta merda...",
    "OH MY GOD!": "meu deus!", "OH MY GOD...": "meu deus...",
    "MY BAD!": "foi mal!", "MY BAD...": "foi mal...",
    "I'M SORRY!": "desculpa!", "I'M SORRY...": "desculpa...",
    "NO PROBLEM!": "sem problema!", "NO PROBLEM": "sem problema",
    "OF COURSE!": "claro!", "OF COURSE": "claro", "OF COURSE NOT!": "claro que não!",
    "ARE YOU OKAY?": "você tá bem?", "ARE YOU OKAY?!": "você tá bem?!",
    "ARE YOU ALRIGHT?": "você tá bem?", "ARE YOU ALRIGHT?!": "você tá bem?!",
    "I DID IT!": "consegui!", "WE DID IT!": "conseguimos!",
    "I GOT IT!": "entendi!", "I GOT IT": "entendi",
    "I SEE...": "entendi...", "I SEE!": "entendi!", "I SEE": "entendi",
    "UNDERSTOOD!": "entendido!", "UNDERSTOOD": "entendido",
    "ROGER!": "entendido!", "ROGER THAT!": "entendido!",
    "IMPOSSIBLE!": "impossível!", "IMPOSSIBLE...": "impossível...",
    "IT'S IMPOSSIBLE!": "é impossível!", "THAT'S IMPOSSIBLE!": "isso é impossível!",
    "UNBELIEVABLE!": "inacreditável!", "UNBELIEVABLE...": "inacreditável...",
    "HOW DARE YOU!": "como você ousa!", "HOW DARE YOU?!": "como você ousa?!",
    "DAMN IT ALL!": "que droga!",
    "SON OF A BITCH!": "filho da mãe!", "SON OF A BITCH": "filho da mãe",
    "FORGET IT!": "esquece!", "FORGET IT...": "esquece...",
    "CALM DOWN!": "calma!", "CALM DOWN": "calma",
    "RELAX!": "relaxa!", "RELAX": "relaxa",
    "DON'T WORRY!": "não se preocupe!", "DON'T WORRY...": "não se preocupe...",
    "TRUST ME!": "confia em mim!", "TRUST ME": "confia em mim",
    "LET GO!": "solta!", "LET ME GO!": "me solta!", "LET ME GO": "me solta",
    "STAY BACK!": "afaste-se!", "STAND BACK!": "afaste-se!",
    "FIRE!": "fogo!",
    "RUN!": "corra!", "RUN AWAY!": "fuja!", "RUN FOR IT!": "corram!",
    "HURRY!": "rápido!", "HURRY UP!": "depressa!",
    "FASTER!": "mais rápido!",
    "DIE!": "morra!", "DIE?!": "morrer?!", "DIE!!": "morra!!",
    "TAKE THAT!": "toma essa!", "TAKE THIS!": "toma isso!", "EAT THIS!": "toma isso!",
    "CHECKMATE!": "xeque-mate!",
    "TOO SLOW!": "lento demais!", "TOO SLOW": "lento demais",
    "SO FAST!": "tão rápido!", "TOO FAST!": "rápido demais!",
    "HE'S FAST!": "ele é rápido!", "SHE'S FAST!": "ela é rápida!",
    "WHAT A DRAG...": "que saco...", "WHAT A BOTHER...": "que incômodo...",
    "GOOD LUCK!": "boa sorte!",
    "SEE YA!": "até mais!", "SEE YA": "até mais", "SEE YOU LATER!": "até mais tarde!",
    "GOODBYE!": "adeus!", "FAREWELL!": "adeus!",
    "WELCOME BACK!": "bem-vindo de volta!",
    "I'M HOME!": "cheguei!",
    "CHEERS!": "saúde!",
    "BULLSHIT!": "balela!", "NONSENSE!": "besteira!",
    "EXCUSE ME!": "com licença!", "EXCUSE ME...": "com licença...", "PARDON ME...": "com licença..."
}

BASE_EXCLAMATIONS = {
    "WHAT": "o quê",
    "WHAT THE": "o que é isso",
    "WHAT IS THAT": "o que é aquilo",
    "WHAT'S THAT": "o que é aquilo",
    "HUH": "hã",
    "EH": "eh",
    "N-NO WAY": "de jeito nenhum",
    "NO WAY": "sem chance",
    "DAMN": "droga",
    "DAMN IT": "droga",
    "DAMMIT": "droga",
    "SHIT": "merda",
    "CRAP": "droga",
    "BASTARD": "desgraçado",
    "YOU BASTARD": "seu desgraçado",
    "YOU BASTARDS": "seus desgraçados",
    "IDIOT": "idiota",
    "SHEESH": "putz",
    "TCH": "tsc",
    "TSK": "tsc",
    "UGH": "ugh",
    "OUCH": "ai",
    "HEH": "heh",
    "HEHE": "hehe",
    "HAHA": "haha",
    "WOW": "uau",
    "WHOA": "uau",
    "WHOAA": "uauuu",
    "GAAAH": "gaaah",
    "AAAAH": "aaaah",
    "URGH": "urgh",
    "COME ON": "vamos",
    "LET'S GO": "vamos lá",
    "STOP": "pare",
    "STOP IT": "para com isso",
    "WAIT": "espere",
    "HOLD ON": "espera aí",
    "SHUT UP": "cala a boca",
    "GET HIM": "pega ele",
    "GET 'EM": "pega eles",
    "GET THEM": "pega eles",
    "YES": "sim",
    "NO": "não",
    "YES, SIR": "sim, senhor",
    "THANK YOU": "obrigado",
    "THANKS": "valeu",
    "COACH": "treinador",
    "CAPTAIN": "capitão",
    "BOSS": "chefe",
    "NANI": "o quê",
    "ARE YOU KIDDING ME": "tá de sacanagem",
    "ARE YOU KIDDING": "tá brincando",
    "DAMN YOU": "seu maldito",
    "GET LOST": "dá o fora",
    "GET OUT": "saia daqui",
    "NOT BAD": "nada mal",
    "NEVER MIND": "deixa pra lá",
    "SORRY": "desculpa",
    "I'M SORRY": "desculpa",
    "MY BAD": "foi mal",
    "DON'T MOVE": "não se mexa",
    "LOOK OUT": "cuidado",
    "WATCH OUT": "cuidado",
    "OVER HERE": "aqui",
    "OVER THERE": "lá",
    "GET DOWN": "abaixe-se",
    "OH NO": "ah, não",
    "OH, NO": "ah, não",
    "OH SHIT": "puta merda",
    "OH MY GOD": "meu deus",
    "NO PROBLEM": "sem problema",
    "OF COURSE": "claro",
    "OF COURSE NOT": "claro que não",
    "ARE YOU OKAY": "você tá bem",
    "ARE YOU ALRIGHT": "você tá bem",
    "I DID IT": "consegui",
    "WE DID IT": "conseguimos",
    "I GOT IT": "entendi",
    "I SEE": "entendi",
    "UNDERSTOOD": "entendido",
    "ROGER": "entendido",
    "ROGER THAT": "entendido",
    "IMPOSSIBLE": "impossível",
    "IT'S IMPOSSIBLE": "é impossível",
    "THAT'S IMPOSSIBLE": "isso é impossível",
    "UNBELIEVABLE": "inacreditável",
    "HOW DARE YOU": "como você ousa",
    "DAMN IT ALL": "que droga",
    "SON OF A BITCH": "filho da mãe",
    "FORGET IT": "esquece",
    "CALM DOWN": "calma",
    "RELAX": "relaxa",
    "DON'T WORRY": "não se preocupe",
    "TRUST ME": "confia em mim",
    "LET GO": "solta",
    "LET ME GO": "me solta",
    "STAY BACK": "afaste-se",
    "STAND BACK": "afaste-se",
    "FIRE": "fogo",
    "RUN": "corra",
    "RUN AWAY": "fuja",
    "RUN FOR IT": "corram",
    "HURRY": "rápido",
    "HURRY UP": "depressa",
    "FASTER": "mais rápido",
    "DIE": "morra",
    "TAKE THAT": "toma essa",
    "TAKE THIS": "toma isso",
    "EAT THIS": "toma isso",
    "CHECKMATE": "xeque-mate",
    "TOO SLOW": "lento demais",
    "SO FAST": "tão rápido",
    "TOO FAST": "rápido demais",
    "HE'S FAST": "ele é rápido",
    "SHE'S FAST": "ela é rápida",
    "WHAT A DRAG": "que saco",
    "WHAT A BOTHER": "que incômodo",
    "GOOD LUCK": "boa sorte",
    "SEE YA": "até mais",
    "SEE YOU LATER": "até mais tarde",
    "GOODBYE": "adeus",
    "FAREWELL": "adeus",
    "WELCOME BACK": "bem-vindo de volta",
    "I'M HOME": "cheguei",
    "CHEERS": "saúde",
    "BULLSHIT": "balela",
    "NONSENSE": "besteira",
    "EXCUSE ME": "com licença",
    "PARDON ME": "com licença",
    "HELP": "socorro",
    "HELP ME": "me ajuda",
    "SOMEONE HELP": "alguém ajude",
    "PLEASE": "por favor",
}

_FAST_PATH_TRAILING_PUNCT_RE = re.compile(r'[\s!?.,…—~\-_:;・！？～。、「」“”‘’"\'ー〜]+$')
_FAST_PATH_STRIP_PUNCT_RE = re.compile(r'^[\s!?.,…—~\-_:;・！？～。、「」“”‘’"\'ー〜]+|[\s!?.,…—~\-_:;・！？～。、「」“”‘’"\'ー〜]+$')


def resolve_fast_path_exclamation(text: str) -> str | None:
    """
    Resolve interjeições e gritos frequentes de mangá em 0.00005s sem chamar LLM.
    Extrai a base semântica (ex: 'HELP', 'WAIT', 'NO WAY') e recombina com a pontuação original.
    """
    if not text or not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None

    norm_key = re.sub(r'\s+([!?.,])', r'\1', raw.upper()).strip('"\'')
    if norm_key in EXCLAMATION_CACHE:
        return EXCLAMATION_CACHE[norm_key]

    punct_match = _FAST_PATH_TRAILING_PUNCT_RE.search(raw)
    trailing_punct = punct_match.group(0).strip() if punct_match else ""

    core = _FAST_PATH_STRIP_PUNCT_RE.sub('', raw)
    core_norm = re.sub(r'\s+', ' ', core.upper()).strip()

    if core_norm in BASE_EXCLAMATIONS:
        base_pt = BASE_EXCLAMATIONS[core_norm]
        if trailing_punct:
            return f"{base_pt}{trailing_punct}"
        return base_pt

    return None


def normalize_preset(preset: str = None) -> str:
    """Normaliza o nome do preset para valores canônicos ('neutral', 'boxing', 'shonen', 'seinen', 'comedy')."""
    p = (preset or "neutral").lower().strip()
    if p in ("neutro", "neutral", "default", "standard", "geral"):
        return "neutral"
    if p in ("boxing", "boxe", "luta", "combate"):
        return "boxing"
    if p in ("shonen", "shounen", "acao", "ação"):
        return "shonen"
    if p in ("seinen", "drama", "maduro"):
        return "seinen"
    if p in ("comedy", "comedia", "comédia", "humor"):
        return "comedy"
    return "neutral"


def is_reasoning_model(model: str = None) -> bool:
    """Identifica se o modelo pertence à classe de reasoning (DeepSeek-R1, QwQ, Marco-o1, etc)."""
    if not model:
        return False
    m = str(model).lower().strip()
    reasoning_keywords = ("r1", "deepseek-r1", "qwq", "marco-o1", "reasoning", "reasoner")
    return any(k in m for k in reasoning_keywords)


def is_amadeus_model(model: str = None) -> bool:
    """Identifica se o modelo pertence à família Amadeus Verbo."""
    if not model:
        return False
    m = str(model).lower().strip()
    return "amadeus" in m or "av-bi" in m


def detect_model_tier(model: str = None) -> str:
    """Identifica a classe de capacidade do modelo LLM ('7b', '14b' ou '32b')."""
    if not model:
        return "32b"
    m = str(model).lower().strip()
    if any(k in m for k in ("32b", "30b", "70b", "72b", "large")):
        return "32b"
    if any(k in m for k in ("14b", "12b", "13b", "16b", "nemo")):
        return "14b"
    if any(k in m for k in ("7b", "8b", "3b", "4b", "mini", "small")):
        return "7b"
    return "32b"


def build_system_prompt(preset: str = "neutral", custom_instructions: str = "", model: str = None) -> str:
    """Constrói o prompt de sistema do LLM com diretrizes modulares de tom pelo preset e calibração por capacidade do modelo (7B, 14B, 32B)."""
    preset_norm = normalize_preset(preset)
    tier = detect_model_tier(model)
    is_reasoning = is_reasoning_model(model)
    
    if preset_norm == "shonen":
        tone_section = """### 1. Diretriz de Tom: Shonen (Ação, Intensidade e Espírito Jovem)
- Adote o registro enérgico e vibrante característico de mangás Shonen de ação:
  - Diálogos dinâmicos, emotivos, cheios de garra, determinação e impacto.
  - Gírias e expressões jovens naturais da dublagem brasileira, sem soar forçado ou datado.
  - Gritos de golpe, exclamações e provocações com alta vibração e ritmo veloz."""
        glossary_section = """### 5. Termos Frequentes de Ação e Shonen
- Kid / Brat → garoto / moleque / pirralho
- Old man / Pops → velhote / coroa
- Let's go! / Come on! → vamos lá! / bora! / vem com tudo!
- No way! → sem chance! / de jeito nenhum!
- Damn! / Shit! → droga! / merda!
- Bastard! → desgraçado!"""
    elif preset_norm == "seinen":
        tone_section = """### 1. Diretriz de Tom: Seinen (Maduro, Dramático e Profundo)
- Adote o registro sóbrio, adulto e realista de mangás Seinen:
  - Vocabulário maduro e diálogos com peso psicológico, tensão e dramaticidade.
  - NUNCA force gírias juvenis, memes ou contrações caricatas. Mantenha sobriedade e refinamento literário.
  - Narrações e reflexões internas devem soar cinematográficas e profundas."""
        glossary_section = """### 5. Diretrizes Vocabulares Seinen
- Preserve a gravidade das palavras: "morrer", "conflito", "sangue", "destino".
- Traduza termos técnicos ou filosóficos com precisão conceitual em português padrão culto brasileiro."""
    elif preset_norm == "comedy":
        tone_section = """### 1. Diretriz de Tom: Comédia e Humor Brasileiro
- Adote timing cômico ágil, tiradas rápidas e expressões espirituosas do humor brasileiro:
  - Adapte trocadilhos, piadas e ironias com naturalidade e leveza em PT-BR.
  - Reações exageradas e diálogos sarcásticos devem soar cômicos e expressivos sem perder o sentido original."""
        glossary_section = """### 5. Expressões Cômicas e Reações
- Idiot! / Dummy! → idiota! / seu mané! / palerma!
- Sheesh! / Sheesh... → putz! / caramba...
- What the...?! → mas o que que é isso...?! / que droga é essa?!
- As if! → até parece! / sonha!"""
    elif preset_norm == "boxing":
        tone_section = """### 1. Espelhamento Dinâmico de Registro e Tom (REGRA DE OURO - Luta e Confronto)
Adote estritamente o tom e registro da fala original em inglês de cada balão. ABANDONE a tradução literal quando expressões idiomáticas em inglês soarem mal em português. Sua localização deve ter peso, gírias e agressividade de falantes reais do Brasil.

- **Evite Anglicismos e Traduções Literais Absolutas:**
  - "YOU BETTER PREPARE YOURSELF" → "é melhor você se preparar" (NUNCA traduza como "você melhor se preparar").
  - "TRADITIONAL BOXING MY ASS" → "boxe clássico uma ova!" ou "o caramba!" (NUNCA "minha bunda").
  - "YOU LEARN SOMETHIN' NEW EEEVERY DAY..." → "vivendo e aprendendo hein..."
  - "HIGHTAIL IT OUTTA HERE" → "dar no pé daqui" ou "vazar daqui".

- **Impacto e Agressividade em Combate:**
  - "NICE 'ND FIRED UP!" → "motivado pra caralho!" ou "com o sangue fervendo!".
  - "LAY OFF ALREADY..." → "já chega dessa merda..." ou "dá um tempo".
  - "OLDSCHOOL SLUGFEST" → "quebra pau a moda antiga".

- **Reconstrução Lógica em Balões Quebrados (MUITO IMPORTANTE):**
  - Frases cortadas por reticências em vários balões devem ser conectadas mentalmente para fazer sentido natural.
  - Exemplo (original): "DIDN'T CATCH THAT, DIDJA?" -> "NAH, NO WAY." -> "UP THIS CLOSE, NOT EVEN A PRO..." -> "CAN CATCH A PUNCH COMING."
  - Tradução natural PT-BR: "não deu nem pra ver, né?" -> "sabe o que mais não dá pra ver..." -> "mesmo se você fosse profissional?" -> "um soco."

- **NUNCA force gírias onde o texto em inglês for técnico/histórico.**"""
        glossary_section = """### 5. Glossário Obrigatório de Combate e Mangá
Aplique estritamente as seguintes traduções quando os termos aparecerem:
- Featherweight → peso-pena
- Fists / Bareknuckles → punhos / mãos nuas (ATENÇÃO: NUNCA gere "fistas" ou erro de gênero "mãos nus")
- Coach / Coach [Nome] → treinador / treinador [Nome]
- Gym (contexto de luta) → academia
- Purse / Fight purse → bolsa / bolsa da luta
- Dummy → saco de pancadas / imbecil
- Baited [someone] into close quarters → atraiu [alguém] pro infight
- Infight / In-fighting → infight
- Pugilism / Ancient Boxing / Boxing's Antiquity → pugilismo clássico
- Fist-fights between gentlemen → brigas de punhos nus entre cavalheiros"""
    else:  # "neutral"
        tone_section = """### 1. Diretriz de Tom: Neutro e Equilibrado
- Tradução fiel, fluida e equilibrada em Português Brasileiro contemporâneo:
  - Cadência natural da dublagem brasileira, evitando formalismos rígidos de dicionário e calques do inglês.
  - Equilíbrio entre coloquialismo leve e precisão vocabular, sem pender para gírias extremas nem formalidade arcaica.
  - Ideal para qualquer gênero de mangá com narração limpa e diálogos naturais."""
        glossary_section = """### 5. Equivalentes Essenciais de Dublagem BR
- Come on! / C'mon! → vamos! / vamos lá! / qual foi!
- No way! → sem chance! / de jeito nenhum!
- Are you kidding?! / You gotta be kidding! → tá de sacanagem?! / tá brincando?!
- Shut up! → cala a boca!
- What the heck / hell?! → mas que droga?! / que diabos?!
- Got it! / Understood! → entendi! / saquei!
- Don't worry! → não esquenta! / não se preocupa!
- Damn it! / Shit! → droga! / merda!"""

    reasoning_protocol = ""
    if is_reasoning:
        reasoning_protocol = """
### 6. Protocolo Operacional de Raciocínio (Modo Reasoning Ativo)
- Pondere livremente dentro da sua tag <think> sobre a dinâmica cênica, tom e intenção velada dos personagens.
- Elimine calques literais do inglês e aplique compressão ativa para caber no balão original.
- Assim que concluir a reflexão, feche obrigatoriamente com a tag </think> e emita EXCLUSIVAMENTE o bloco JSON no formato especificado, sem nenhum texto adicional fora do JSON."""

    if tier == "7b":
        prompt = f"""## Papel e Especialidade
Você é o motor de localização profissional de quadrinhos do Visionary Studio (EN -> PT-BR).
Sua missão é converter diálogos em inglês para a língua falada autêntica do Brasil, com ritmo ágil, sem floreios e com compressão máxima de texto para não estourar a área física dos balões.

{tone_section}

## Protocolo Operacional de Tradução (Nível 7B - Alta Precisão)

1. HEURÍSTICA DE COMPRESSÃO ESPACIAL (REGRA DO BALÃO):
- O português naturalmente expande 20% em relação ao inglês. Isso destrói o layout do balão.
- Sua tradução em PT-BR deve ter extensão visual IGUAL ou MENOR que o original em inglês.
- Método de corte: corte pronomes redundantes ("tá pronto?" e nunca "você tá pronto?"), elimine preposições dispensáveis e use verbos diretos.

2. FALA ORAL AUTÊNTICA (ZERO FORMALISMO DE DICIONÁRIO):
- Pessoas em quadrinhos conversam como brasileiros reais em momentos de tensão, desdém ou ação.
- NUNCA use traduções mecânicas de filmes dublados antigos ("vamos, agora", "eu disse para", "me vejo na situação").

3. TABELA DE CALIBRAGEM CONTRASTIVA (APRENDA COM OS ERROS):
Observe o erro típico de IA e siga estritamente a localização humana de referência:
• Entrada: "C'MON, NOW."
  ❌ Errado: "vamos, agora."
  ✅ Correto: "qual foi."
• Entrada: "I SAID STOP!!"
  ❌ Errado: "eu disse para!!"
  ✅ Correto: "eu falei pra parar!!"
• Entrada: "I CAN PICTURE IT."
  ❌ Errado: "eu me vejo na situação."
  ✅ Correto: "eu consigo até ver."
• Entrada: "GOING ALL OUT."
  ❌ Errado: "se mandando."
  ✅ Correto: "se esmurrando."
• Entrada: "HEY OLD MAN..."
  ❌ Errado: "ei velho..."
  ✅ Correto: "ei velhote..."
• Entrada: "THEY ALLOW HIM TO DEFLECT INCOMING ATTACKS."
  ❌ Errado: "elas o permitem desviar os ataques..."
  ✅ Correto: "permitem desviar os ataques do adversário."
• Entrada: "YOU'VE GOTTA BE KIDDING! I DIDN'T EXPECT YOU HERE!"
  ❌ Errado: "você deve estar brincando! eu não esperava você aqui!"
  ✅ Correto: "tá de sacanagem! não achei que você viria aqui!"

4. INVARIANTES ESTRUTURAIS DE SAÍDA (TOLERÂNCIA ZERO A FALHAS):
- Tags [CORTE]: Se uma fala contiver N tags [CORTE], a saída DEVE conter exatamente N tags [CORTE] posicionadas na quebra natural de respiração da oração em português.
- IDs Numéricos: Retorne exatamente os mesmos "id" recebidos. Nunca altere, mescle ou descarte nenhum ID.
- Nomes Próprios: Mantenha idênticos ao original. Omita sempre sufixos japoneses (-san, -kun, -chan, -sama).
- Ruído de OCR: O texto de entrada provém de OCR óptico, está em MAIÚSCULAS e pode conter falhas de pontuação ("! !", "... ."). Ignore os artefatos e traduza a intenção limpa da fala.
- Tipografia: Toda a fala corrente deve ser gerada em minúsculas (lowercase), mas PRESERVE rigorosamente a caixa alta de Nomes Próprios (ex: Sasuke, Goku), Siglas (ex: ONU, FBI, EUA, SSJ), Numerais Romanos (ex: IV, VII) e Gritos/Onomatopeias em MAIÚSCULAS.

{glossary_section}
{reasoning_protocol}

## Formato de Saída Obrigatório
Retorne EXCLUSIVAMENTE o JSON no schema abaixo, sem preâmbulos, sem markdown de bloco e sem explicações:
{{
  "translations": [
    {{"id": 1, "text": "fala localizada em pt-br minúsculo"}},
    {{"id": 90001, "text": "primeira parte... [CORTE] ...segunda parte da fala"}}
  ]
}}"""

    elif tier == "14b":
        prompt = f"""## Papel e Especialidade
Você é o motor de localização literária e adaptação de quadrinhos do Visionary Studio (EN -> PT-BR).
Sua missão é entregar diálogos com ritmo cinematográfico, naturalidade da dublagem brasileira contemporânea e compressão ativa de texto para preservação da área física dos balões.

{tone_section}

## Protocolo de Alta Performance (Nível 14B - Fluência e Cadência)

1. DESANGLICIZAÇÃO E FALA VISCERAL (ZERO CALQUE):
- Abandone a estrutura sintática do inglês:
  • "actually / to be honest" → "na real" / "sendo sincero" (evite o burocrático "na verdade").
  • "guess what?" → "sabe de uma coisa?" / "adivinha só?".
  • "you gotta be kidding me" → "tá de sacanagem" / "só pode ser piada".
- Elimine advérbios longos em "-mente" que incham o balão (troque "definitivamente não" por "nem a pau" ou "sem chance").

2. PARÁFRASE ATIVA E CONTROLE ESPACIAL (REGRA DO BALÃO):
- O português expande 20% em relação ao inglês. Em quadrinhos, isso estoura o desenho original.
- Converta orações passivas ou prolixas em afirmações ativas, curtas e de alto impacto dramático.
- A extensão final do texto em PT-BR deve manter equivalência visual ao balão original.

3. CASOS DE CALIBRAGEM COMPLEXA (REFERÊNCIA DE ALTO NÍVEL):
Observe a adaptação de ritmo, compressão e quebra de balões:

• Caso 1 - Conexão e Cadência em Balões Quebrados ([CORTE]):
  Entrada: "DIDN'T CATCH THAT, DIDJA? [CORTE] UP THIS CLOSE, NOT EVEN A PRO... [CORTE] CAN CATCH A PUNCH COMING."
  ✅ Saída: "não deu nem pra ver, né? [CORTE] de tão perto assim, nem um profissional... [CORTE] esquiva desse golpe."

• Caso 2 - Adaptação de Expressão de Confronto sem Calque:
  Entrada: "RESPECTING MY CHOICES MY ASS! YOU'RE JUST A BULLY RESORTING TO CHEAP TRICKS!"
  ✅ Saída: "respeitar minhas escolhas uma ova! você é só um covarde apelando pra golpe sujo!"

• Caso 3 - Síntese Rápida sem Perda de Conteúdo:
  Entrada: "YOU'D ALSO THINK THAT STANCE MAKES HIS PUNCHES LESS POWERFUL, BUT IT DOESN'T."
  ✅ Saída: "pode parecer que essa postura tira a força dos socos, mas não é verdade."

• Caso 4 - Desanglicização Visceral de Diálogo Oral:
  Entrada: "YOU'VE GOTTA BE KIDDING! I DIDN'T EXPECT YOU TO SHOW UP HERE!"
  ✅ Saída: "tá de sacanagem! não achei que você viria aqui!"

• Caso 5 - Ritmo e Provocação em Diálogo de Ação (Padrão Ouro Dublagem):
  Entrada: "C'MON, NOW. DON'T GET COCKY JUST BECAUSE YOU GOT ONE HIT IN."
  ✅ Saída: "vem cá, agora. não fique arrogante só porque você me acertou uma vez."

• Caso 6 - Fluidez Oral em Reação de Espanto e Desafio:
  Entrada: "ARE YOU KIDDING ME?! DO YOU REALLY THINK YOU CAN BEAT ME WITH THAT STANCE?"
  ✅ Saída: "você tá de brincadeira, né?! acha mesmo que vai me vencer com essa postura?"

4. HARMONIZAÇÃO DE SUBTEXTO E COERÊNCIA DE GÊNERO:
- Capte sarcasmo, duplos sentidos e ironias sutis. Nunca traduza deboche como declaração literal.
- Mantenha a coerência de gênero gramatical e o nível de intimidade/hierarquia entre os personagens da cena.

5. DEDUÇÃO CONTEXTUAL DE OCR:
- O texto original provém de OCR óptico, está predominantemente em MAIÚSCULAS por convenção de quadrinhos e pode conter erros ópticos (ex: pontuação colada, letras trocadas).
- Deduza e corrija a palavra real pelo sentido dramático da cena antes de traduzir.

6. INVARIANTES ESTRUTURAIS DE SAÍDA:
- Tags [CORTE]: A quantidade de tags [CORTE] na saída deve ser EXATAMENTE IGUAL à quantidade recebida.
- IDs Numéricos: Retorne exatamente os mesmos IDs recebidos, sem mesclar nem pular nenhum.
- Nomes Próprios: Permaneçam inalterados. Remova sufixos de tratamento japoneses (-san, -kun, -chan, -sama).
- Tipografia: Toda a fala corrente deve ser gerada em minúsculas (lowercase), mas PRESERVE rigorosamente a caixa alta de Nomes Próprios (ex: Sasuke, Goku), Siglas (ex: ONU, FBI, EUA, SSJ), Numerais Romanos (ex: IV, VII) e Gritos/Onomatopeias em MAIÚSCULAS.

{glossary_section}
{reasoning_protocol}

## Formato de Saída Obrigatório
Retorne EXCLUSIVAMENTE o JSON no schema abaixo, sem preâmbulos, sem markdown de bloco e sem explicações:
{{
  "translations": [
    {{"id": 1, "text": "fala localizada em pt-br minúsculo"}},
    {{"id": 90001, "text": "primeira parte... [CORTE] ...segunda parte da fala"}}
  ]
}}"""

    else:  # tier == "32b" (Padrão Editorial Máximo)
        prompt = f"""## Papel e Especialidade
Você é o editor-chefe de localização e tradução literária do Visionary Studio (EN -> PT-BR).
Sua missão é entregar uma adaptação impecável de quadrinhos/mangás de padrão editorial de elite: maestria na dinâmica cênica inter-balões, captação da intenção pragmática (subtexto e não-dito) e elasticidade espacial fonética para caber organicamente no lettering original.

{tone_section}

## Protocolo de Alta Performance (Nível 32B - Padrão Editorial Máximo)

1. ANÁLISE CÊNICA GLOBAL E DINÂMICA INTER-BALÕES:
- Nunca processe os balões de forma isolada. Analise todo o lote da página como um diálogo contínuo e vivo:
  • Identifique a dinâmica de poder: quem ataca, quem recua, quem debocha e quem hesita.
  • Sustente o idioleto (voz única) de cada personagem ao longo de todas as réplicas da página.
  • Desambigúe pronomes neutros do inglês ("you", "they") e tratamentos analisando a relação e gênero dos interlocutores na cena.

2. TRADUÇÃO PRAGMÁTICA E SUBTEXTO (A INTENÇÃO SOBRE A PALAVRA):
- O texto literal mente; o subtexto entrega a verdade da cena:
  • Se o personagem fala com sarcasmo defensivo, a tradução deve transparecer o veneno ou a insegurança velada.
  • Se a fala em inglês usa rodeios por hesitação ou medo, recrie essa mesma tensão psicológica em português sem "explicar" a piada ou o drama.
  • Adapte trocadilhos, metáforas e provocações para equivalentes que ressoem no imaginário cultural brasileiro com o mesmo peso e naturalidade.

3. ELASTICIDADE ESPACIAL E FONÉTICA DE QUADRINHO (BALLOON-AWARE):
- O português expande 20% a 25% em relação ao inglês. Em quadrinhos, isso desborda a arte e estraga o lettering.
- Exerça elasticidade literária ativa:
  • Recrie orações prolixas em construções brasileiras enxutas, cortantes e de impacto.
  • Em cenas de ação e confronto, priorize vocábulos com sonoridade percussiva e monossílabos fortes.
  • A extensão visual final em PT-BR deve respeitar rigorosamente o espaço físico do balão original.

4. MATRIZ DE CALIBRAGEM EDITORIAL AVANÇADA (MASTER FEW-SHOT):

• Caso 1 - Conexão Dramática, Respiração e Ironia em Balões Quebrados ([CORTE]):
  Entrada: "DIDN'T CATCH THAT, DIDJA? [CORTE] UP THIS CLOSE, NOT EVEN A PRO... [CORTE] CAN CATCH A PUNCH COMING."
  ✅ Saída: "não deu nem pra ver, né? [CORTE] de tão perto assim, nem um profissional... [CORTE] esquiva desse golpe."

• Caso 2 - Adaptação de Expressão de Confronto com Máxima Elasticidade Espacial:
  Entrada: "RESPECTING MY CHOICES MY ASS! YOU'RE JUST A BULLY RESORTING TO CHEAP TRICKS!"
  ✅ Saída: "respeitar minhas escolhas uma ova! você é só um covarde apelando pra golpe sujo!"

• Caso 3 - Reconstrução Sintética de Fala Técnica:
  Entrada: "YOU'D ALSO THINK THAT STANCE MAKES HIS PUNCHES LESS POWERFUL, BUT IT DOESN'T."
  ✅ Saída: "pode parecer que essa postura tira a força dos socos, mas não é verdade."

• Caso 4 - Desanglicização Visceral de Diálogo Oral:
  Entrada: "YOU'VE GOTTA BE KIDDING! I DIDN'T EXPECT YOU TO SHOW UP HERE!"
  ✅ Saída: "tá de sacanagem! não achei que você viria aqui!"
  ❌ Errado: "você deve estar brincando! eu não esperava você aparecer aqui!"

• Caso 5 - Compressão Espacial sem Sujeito Redundante:
  Entrada: "DO YOU THINK THAT YOU CAN ACTUALLY BEAT ME?"
  ✅ Saída: "acha que pode mesmo me vencer?"
  ❌ Errado: "você acha que você pode realmente me derrotar?"

5. RECONSTRUÇÃO ORGÂNICA DE RUÍDO DE OCR:
- O texto de entrada provém de OCR óptico, está predominantemente em MAIÚSCULAS por convenção de quadrinhos e frequentemente contém ruídos (pontuações estranhas, letras coladas, caracteres trocados).
- Use a compreensão ampla do contexto narrativo para inferir a intenção real do autor e traduzir com perfeição sem jamais alucinar.

6. INVARIANTES ESTRUTURAIS DE SAÍDA (TOLERÂNCIA ZERO):
- Tags [CORTE]: A quantidade de tags [CORTE] na saída deve ser RIGOROSAMENTE IGUAL à recebida.
- IDs Numéricos: Retorne exatamente os mesmos IDs numéricos recebidos, sem mesclar, omitir ou criar novos.
- Nomes Próprios: Permaneçam inalterados. Omita sempre sufixos japoneses (-san, -kun, -chan, -sama).
- Tipografia: Toda a fala corrente deve ser gerada em minúsculas (lowercase), mas PRESERVE rigorosamente a caixa alta de Nomes Próprios (ex: Sasuke, Goku), Siglas (ex: ONU, FBI, EUA, SSJ), Numerais Romanos (ex: IV, VII) e Gritos/Onomatopeias em MAIÚSCULAS.

{glossary_section}
{reasoning_protocol}

## Formato de Saída Obrigatório
Retorne EXCLUSIVAMENTE o JSON no schema abaixo, sem preâmbulos, sem blocos de markdown e sem notas:
{{
  "translations": [
    {{"id": 1, "text": "fala localizada em pt-br minúsculo"}},
    {{"id": 90001, "text": "primeira parte... [CORTE] ...segunda parte da fala"}}
  ]
}}"""

    if custom_instructions and custom_instructions.strip():
        prompt += f"\n\n## Work-Specific Glossary (Highest Priority — override everything above if conflict)\n{custom_instructions.strip()}\nApply these translations strictly whenever the terms appear."

    return prompt
