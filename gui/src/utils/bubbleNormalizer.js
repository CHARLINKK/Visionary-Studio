/**
 * Utilitário de normalização de blocos/balões para o Inspetor do SeamlessEditor.
 * Unifica leituras de texto OCR, tradução e metadados de edição sem ternários aninhados.
 *
 * @typedef {import('../types/bubble').Bubble} Bubble
 *
 * @typedef {Object} NormalizedInspectorBubble
 * @property {string} text - Texto OCR original higienizado
 * @property {string} translated - Texto traduzido corrente
 * @property {string} aiTranslated - Texto primordial gerado pela IA
 * @property {boolean} isEdited - Flag indicando alteração humana
 * @property {boolean} isDeleted - Flag indicando marcação de exclusão
 * @property {string} rawOcr - Texto OCR bruto original
 * @property {string} badgeLabel - Rótulo resumido (BUBBLE, SFX, FREE, TOOL, BOX)
 */

function extractStringField(value) {
  if (typeof value === "string") return value;
  if (typeof value === "object" && value !== null && typeof value.text === "string") {
    return value.text;
  }
  return String(value || "");
}

/**
 * Verifica se o bloco é um efeito sonoro / onomatopeia (SFX).
 * @param {Partial<Bubble>} [box]
 * @returns {boolean}
 */
export function isBubbleSfx(box) {
  if (!box || typeof box !== "object") return false;
  const label = String(box.label || "").toLowerCase();
  return Boolean(box.is_sfx || box.isSfx || box.bg_type === "sfx" || label.includes("sfx"));
}

/**
 * Extrai o texto original (EN/OCR) do balão unificando chaves canônicas e legadas.
 * @param {Partial<Bubble>} [box]
 * @returns {string}
 */
export function getBubbleText(box) {
  if (!box || typeof box !== "object") return "";
  return extractStringField(box.text ?? box.original ?? box.text_clean ?? box.ocr_raw);
}

/**
 * Extrai a tradução ativa (PT-BR) do balão unificando chaves canônicas e legadas.
 * @param {Partial<Bubble>} [box]
 * @returns {string}
 */
export function getBubbleTranslation(box) {
  if (!box || typeof box !== "object") return "";
  return extractStringField(box.translated ?? box.translated_text ?? box.text_ptbr ?? box.ptbr);
}

/**
 * Extrai a tradução original gerada pela IA para comparação de edição humana.
 * @param {Partial<Bubble>} [box]
 * @returns {string}
 */
export function getBubbleAiTranslation(box) {
  if (!box || typeof box !== "object") return "";
  const translated = getBubbleTranslation(box);
  if (typeof box.ai_translated === "object" && box.ai_translated !== null) {
    return box.ai_translated.text || "";
  }
  return String(
    box.ai_translated ||
      box.ai_translated_text ||
      (box.user_edited ? "" : translated) ||
      ""
  );
}

/**
 * Retorna o identificador de grupo ([CORTE]) do balão, se vinculado.
 * @param {Partial<Bubble>} [box]
 * @returns {string|number|null}
 */
export function getBubbleGroupId(box) {
  if (!box || typeof box !== "object") return null;
  return box.group_id ?? box.groupId ?? null;
}

/**
 * Remove chaves de agrupamento (`group_id` / `groupId`) de um balão imutavelmente.
 * @param {Partial<Bubble>} [box]
 * @returns {Partial<Bubble>}
 */
export function stripBubbleGroupId(box) {
  if (!box || typeof box !== "object") return box;
  const { group_id: _gid, groupId: _gId, ...rest } = box;
  return rest;
}

/**
 * Alterna imutavelmente um balão entre fala comum e efeito sonoro (SFX),
 * mantendo chaves canônicas (`is_sfx`) e legadas (`isSfx`) sincronizadas.
 * @param {Partial<Bubble>} [box]
 * @returns {Partial<Bubble>}
 */
export function toggleBubbleSfxState(box) {
  if (!box || typeof box !== "object") return box;
  const currentIsSfx = isBubbleSfx(box);
  const nextIsSfx = !currentIsSfx;
  return {
    ...box,
    is_sfx: nextIsSfx,
    isSfx: nextIsSfx,
    is_bubble: !nextIsSfx,
    label: nextIsSfx ? "text_free" : "text_bubble",
    bg_type: nextIsSfx ? "sfx" : "white",
    user_edited: true,
  };
}

/**
 * Resolve o rótulo do crachá do balão com base em seu tipo/morfologia.
 * @param {Partial<Bubble>} [box]
 * @returns {string}
 */
export function resolveBubbleBadgeLabel(box) {
  const label = String(box?.label || "").toLowerCase();
  if (isBubbleSfx(box)) return "SFX";
  if (label.includes("bubble")) return "BUBBLE";
  if (label.includes("free")) return "FREE";
  if (label.includes("tool")) return "TOOL";

  if (box?.is_bubble) return "BUBBLE";
  return "BOX";
}

/**
 * Normaliza propriedades de um balão para o inspetor de blocos do editor.
 * @param {Partial<Bubble>} [box]
 * @returns {NormalizedInspectorBubble}
 */
export function normalizeInspectorBubble(box = {}) {
  const text = extractStringField(box.text);
  const translated = getBubbleTranslation(box);
  const aiTranslated = getBubbleAiTranslation(box);

  const isEdited = Boolean(
    box.user_edited || (aiTranslated && translated.trim() !== aiTranslated.trim())
  );

  const isDeleted =
    text === "[DELETE]" ||
    translated === "[DELETE]" ||
    isBubbleSfx(box);

  let rawOcr = "";
  if (typeof box.ocr_raw === "string") {
    rawOcr = box.ocr_raw;
  } else if (typeof box.original === "string" && box.original !== "[DELETE]") {
    rawOcr = box.original;
  } else if (
    typeof box.ocr_raw === "object" &&
    box.ocr_raw !== null &&
    box.ocr_raw.text
  ) {
    rawOcr = String(box.ocr_raw.text);
  }

  return {
    text,
    translated,
    aiTranslated,
    isEdited,
    isDeleted,
    rawOcr,
    badgeLabel: resolveBubbleBadgeLabel(box),
    hasMoved: hasBubbleMoved(box),
  };
}

/**
 * Verifica se o balão foi deslocado ou redimensionado em relação ao seu estado inicial de detecção.
 * @param {Partial<Bubble>} [box]
 * @returns {boolean}
 */
export function hasBubbleMoved(box) {
  if (!box || typeof box !== "object") return false;
  const ibox = box.initial_box;
  if (!Array.isArray(ibox) || ibox.length !== 4) return false;

  const boxMoved =
    box.x1 !== ibox[0] ||
    box.y1 !== ibox[1] ||
    box.x2 !== ibox[2] ||
    box.y2 !== ibox[3];

  if (boxMoved) return true;

  const ipoly = box.initial_polygon;
  const poly = box.polygon;
  if (Array.isArray(ipoly) && Array.isArray(poly) && ipoly.length > 0) {
    if (ipoly.length !== poly.length) return true;
    for (let idx = 0; idx < poly.length; idx++) {
      if (
        poly[idx][0] !== ipoly[idx][0] ||
        poly[idx][1] !== ipoly[idx][1]
      ) {
        return true;
      }
    }
  }

  return false;
}

export function reindexBubbleOrders(boxes = []) {
  if (!Array.isArray(boxes)) return [];
  let nextOrder = 1;
  return boxes.map((box) => {
    if (!box || typeof box !== "object") return box;
    const isSfx = isBubbleSfx(box);
    return {
      ...box,
      order: isSfx ? null : nextOrder++,
    };
  });
}
