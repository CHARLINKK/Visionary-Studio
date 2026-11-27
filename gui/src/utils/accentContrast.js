/**
 * Utilitários de contraste (WCAG 2.x) para acentos de tema.
 *
 * O acento escolhido pelo usuário é aplicado via `style` inline e, sem ajuste,
 * ignora o fundo do tema ativo: laranja/verde/ciano sobre papel claro ficam
 * com ~2:1 de contraste (ilegíveis). Estas funções preservam o matiz e só
 * ajustam a luminosidade até atingir o contraste mínimo.
 */

/** Fundo de referência (--bg-panel) por tema, usado para medir o contraste do acento. */
export const THEME_PANEL_BG = {
  light: '#ffffff',
  'warm-paper': '#f6f4ee', // Papel suave e acolhedor (Warm Paper)
  dark: '#13141b',
  oled: '#0a0d14',
  'e-ink': '#1f2329',
  'neo-tokyo': '#0b1221',
};

/**
 * Acentos canônicos e harmoniosos por tema.
 *
 * Evita o clássico "Frankenstein estético" onde um tema de papel sepia/nanquim
 * japonês é forçado a usar roxo neon digital porque o app tem um default global.
 * Quando o usuário não escolhe uma cor customizada explícita, cada tema brilha
 * com sua paleta autêntica e intencional.
 */
export const DEFAULT_COLOR_MAP = {
  'Roxo (Padrão)': '#8b5cf6',
  'Roxo': '#8b5cf6',
  'Azul Elétrico': '#3b82f6',
  'Azul': '#3b82f6',
  'Ciano Cyber': '#06b6d4',
  'Verde Esmeralda': '#10b981',
  'Verde': '#10b981',
  'Laranja Solar': '#f59e0b',
  'Laranja': '#f59e0b',
  'Rosa Sakura': '#ec4899',
  'Vermelho Carmim': '#ef4444',
  'Vermelho': '#ef4444',
  'Branco Puro': '#ffffff',
  'Branco': '#ffffff',
  'Preto Puro': '#000000',
  'Preto': '#000000',
  'RGB': 'linear-gradient(45deg, #f87171, #fbbf24, #34d399, #60a5fa, #a78bfa)',
};

/**
 * Acentos canônicos de fallback caso o usuário escolha explicitamente 'Padrão do Tema'.
 */
export const THEME_DEFAULT_ACCENTS = {
  dark: '#8b5cf6',         // Modern Violet (Pro Studio)
  light: '#4f46e5',        // Royal Indigo (Editorial Swiss)
  'warm-paper': '#3b352f', // Deep Sumi-e Charcoal (Paperwhite Studio)
  oled: '#38bdf8',         // Blueprint Cyan (Cyber CAD)
  'e-ink': '#475569',      // Slate Graphite (E-Ink Matte)
  'neo-tokyo': '#06b6d4',  // Cyber Cyan (Neo-Tokyo HUD)
};

/**
 * Resolve o acento para um tema: preserva a cor escolhida pelo usuário
 * (inclusive Roxo / Roxo Padrão) em todos os temas sem substituí-la.
 * Se for explicitamente 'Padrão do Tema', utiliza o acento canônico daquele tema.
 *
 * @param {string|null|undefined} accent Acento configurado.
 * @param {string} themeAttr Atributo data-theme ('dark', 'light', 'warm-paper', etc).
 * @param {Record<string, string>} [colorMap] Dicionário opcional de rótulo para hex.
 * @returns {string} Cor hex do acento.
 */
export function resolveThemeAccent(accent, themeAttr, colorMap = DEFAULT_COLOR_MAP) {
  if (accent === 'Padrão do Tema') {
    return THEME_DEFAULT_ACCENTS[themeAttr] || THEME_DEFAULT_ACCENTS.dark;
  }
  const mergedMap = { ...DEFAULT_COLOR_MAP, ...colorMap };
  const color = mergedMap[accent] || accent;
  if (!color || color === 'default') {
    return mergedMap['Roxo (Padrão)'] || '#8b5cf6';
  }
  return color;
}

export const LIGHT_THEMES = new Set(['light', 'warm-paper']);

/** Contraste mínimo para manter texto branco sobre o acento (ver pickOnAccentColor). */
export const WHITE_ON_ACCENT_MIN_RATIO = 3.5;

const HEX_RE = /^#?([0-9a-f]{6})$/i;

/** @param {string} hex Cor `#rrggbb`. @returns {[number, number, number]|null} */
export function hexToRgb(hex) {
  const m = HEX_RE.exec(String(hex || '').trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** @param {[number, number, number]} rgb @returns {string} */
export function rgbToHex([r, g, b]) {
  const h = (v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0');
  return `#${h(r)}${h(g)}${h(b)}`;
}

/** Luminância relativa (0..1) conforme WCAG. */
export function relativeLuminance(rgb) {
  const [r, g, b] = rgb.map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Razão de contraste (1..21) entre duas cores `#rrggbb`. Retorna 1 se inválidas. */
export function contrastRatio(hexA, hexB) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  if (!a || !b) return 1;
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  const [hi, lo] = la >= lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Ajusta a luminosidade do acento (preservando o matiz) até atingir `minRatio`
 * contra `bgHex`. Em fundos claros escurece; em fundos escuros clareia.
 * Valores que não sejam `#rrggbb` (ex.: gradientes) são devolvidos sem alteração.
 *
 * @param {string} accentHex Acento `#rrggbb`.
 * @param {string} bgHex Fundo de referência `#rrggbb`.
 * @param {number} [minRatio=4.5] Contraste mínimo desejado.
 * @returns {string} Acento ajustado `#rrggbb` (ou o original, se inválido).
 */
export function ensureAccentContrast(accentHex, bgHex, minRatio = 4.5) {
  const rgb = hexToRgb(accentHex);
  const bg = hexToRgb(bgHex);
  if (!rgb || !bg) return accentHex;

  const bgIsLight = relativeLuminance(bg) > 0.4;
  let current = rgb;
  for (let i = 0; i < 40; i += 1) {
    if (contrastRatio(rgbToHex(current), bgHex) >= minRatio) break;
    current = bgIsLight
      ? current.map((v) => v * 0.94)
      : current.map((v) => v + (255 - v) * 0.08);
  }
  return rgbToHex(current);
}

/**
 * Escolhe a cor de texto/ícone sobre um fundo de acento.
 *
 * Mantém branco (visual padrão de botões de acento) enquanto o contraste for
 * >= 3.5:1; só cai para quase-preto em acentos realmente claros (ciano, verde,
 * laranja), onde o branco ficaria entre 2:1 e 2.6:1. Cores de luminância média
 * (ex.: roxo padrão #8b5cf6, ~4.2:1) não têm opção >= 4.5:1 com nenhum dos dois,
 * então preferir branco evita trocar o visual padrão sem ganho real.
 * Gradientes/valores inválidos caem em branco.
 *
 * @param {string} accentHex Acento `#rrggbb`.
 * @returns {string} `#ffffff` ou `#12141a`.
 */
export function pickOnAccentColor(accentHex) {
  const dark = '#000000';
  const light = '#ffffff';
  if (!hexToRgb(accentHex)) return light;
  return contrastRatio(accentHex, light) >= WHITE_ON_ACCENT_MIN_RATIO ? light : dark;
}
