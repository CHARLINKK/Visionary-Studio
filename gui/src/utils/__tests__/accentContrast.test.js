import { describe, it, expect } from 'vitest';
import {
  LIGHT_THEMES,
  THEME_PANEL_BG,
  WHITE_ON_ACCENT_MIN_RATIO,
  contrastRatio,
  ensureAccentContrast,
  hexToRgb,
  pickOnAccentColor,
  resolveThemeAccent,
  rgbToHex,
} from '../accentContrast';

// Acentos oferecidos em Configurações (ver colorMap em useAppTheme)
const ACCENTS = {
  roxo: '#8b5cf6',
  azul: '#3b82f6',
  ciano: '#06b6d4',
  verde: '#10b981',
  laranja: '#f59e0b',
  rosa: '#ec4899',
  vermelho: '#ef4444',
};

describe('accentContrast', () => {
  it('converte hex <-> rgb e rejeita entradas inválidas', () => {
    expect(hexToRgb('#8b5cf6')).toEqual([139, 92, 246]);
    expect(rgbToHex([139, 92, 246])).toBe('#8b5cf6');
    expect(hexToRgb('linear-gradient(45deg, #f87171, #fbbf24)')).toBeNull();
    expect(hexToRgb(undefined)).toBeNull();
  });

  it('calcula razão de contraste WCAG conhecida (preto/branco = 21:1)', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 1);
    expect(contrastRatio('#ffffff', '#ffffff')).toBeCloseTo(1, 5);
    expect(contrastRatio('xx', '#ffffff')).toBe(1);
  });

  it.each(Object.entries(ACCENTS))(
    'acento %s atinge >= 4.5:1 em todos os temas claros',
    (_nome, hex) => {
      for (const theme of LIGHT_THEMES) {
        const bg = THEME_PANEL_BG[theme];
        const adjusted = ensureAccentContrast(hex, bg, 4.5);
        expect(contrastRatio(adjusted, bg)).toBeGreaterThanOrEqual(4.5);
      }
    }
  );

  it('preserva o matiz dominante ao escurecer (não vira cinza)', () => {
    const [r, g, b] = hexToRgb(ensureAccentContrast(ACCENTS.laranja, THEME_PANEL_BG.light, 4.5));
    expect(r).toBeGreaterThan(g);
    expect(g).toBeGreaterThan(b);
  });

  it('não altera acento que já cumpre o contraste', () => {
    const bg = THEME_PANEL_BG.light;
    const ja = ensureAccentContrast('#3b0764', bg, 4.5);
    expect(ja).toBe('#3b0764');
  });

  it('em fundo escuro clareia acentos escuros demais', () => {
    const bg = THEME_PANEL_BG.dark;
    const adjusted = ensureAccentContrast('#1e1b4b', bg, 4.5);
    expect(contrastRatio(adjusted, bg)).toBeGreaterThanOrEqual(4.5);
  });

  it('devolve gradientes sem alteração', () => {
    const grad = 'linear-gradient(45deg, #f87171, #fbbf24)';
    expect(ensureAccentContrast(grad, THEME_PANEL_BG.light)).toBe(grad);
  });

  it('escolhe texto escuro sobre acentos claros e branco sobre escuros', () => {
    expect(pickOnAccentColor('#f59e0b')).toBe('#000000');
    expect(pickOnAccentColor('#06b6d4')).toBe('#000000');
    expect(pickOnAccentColor('#6d28d9')).toBe('#ffffff');
    expect(pickOnAccentColor('linear-gradient(red, blue)')).toBe('#ffffff');
  });

  it('o texto escolhido sobre o acento atinge >= 3.5:1 para todos os acentos', () => {
    for (const hex of Object.values(ACCENTS)) {
      const on = pickOnAccentColor(hex);
      expect(contrastRatio(hex, on)).toBeGreaterThanOrEqual(WHITE_ON_ACCENT_MIN_RATIO);
    }
  });

  it('mantém branco no roxo padrão (visual original) e escurece só acentos claros', () => {
    expect(pickOnAccentColor(ACCENTS.roxo)).toBe('#ffffff');
    expect(pickOnAccentColor(ACCENTS.azul)).toBe('#ffffff');
    expect(pickOnAccentColor(ACCENTS.verde)).toBe('#000000');
  });

  it('em temas claros o acento ajustado mantém texto legível sobre si (botão primário)', () => {
    for (const hex of Object.values(ACCENTS)) {
      for (const theme of LIGHT_THEMES) {
        const adjusted = ensureAccentContrast(hex, THEME_PANEL_BG[theme], 4.5);
        const on = pickOnAccentColor(adjusted);
        expect(contrastRatio(adjusted, on)).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it('resolveThemeAccent preserva Roxo (Padrão) fielmente em todos os temas', () => {
    // Roxo nunca pode "morrer" em nanquim/carvão (#3b352f) ou índigo (#4f46e5)
    expect(resolveThemeAccent('Roxo (Padrão)', 'dark')).toBe('#8b5cf6');
    expect(resolveThemeAccent('Roxo (Padrão)', 'warm-paper')).toBe('#8b5cf6');
    expect(resolveThemeAccent('Roxo (Padrão)', 'light')).toBe('#8b5cf6');
    expect(resolveThemeAccent('Roxo (Padrão)', 'oled')).toBe('#8b5cf6');
    expect(resolveThemeAccent('Roxo (Padrão)', 'e-ink')).toBe('#8b5cf6');
    expect(resolveThemeAccent('Roxo (Padrão)', 'neo-tokyo')).toBe('#8b5cf6');
    expect(resolveThemeAccent(undefined, 'warm-paper')).toBe('#8b5cf6');
    expect(resolveThemeAccent('default', 'warm-paper')).toBe('#8b5cf6');
    
    // Suporte a 'Padrão do Tema' caso explicitamente requisitado
    expect(resolveThemeAccent('Padrão do Tema', 'warm-paper')).toBe('#3b352f');
    expect(resolveThemeAccent('Padrão do Tema', 'light')).toBe('#4f46e5');

    // Quando o usuário escolhe um acento explícito, respeita a escolha
    const map = { 'Azul Elétrico': '#3b82f6', 'Verde': '#10b981' };
    expect(resolveThemeAccent('Azul Elétrico', 'warm-paper', map)).toBe('#3b82f6');
    expect(resolveThemeAccent('Verde', 'light', map)).toBe('#10b981');
  });

  it('no tema WarmPaper o roxo permanece roxo vivo e legível com contraste WCAG AA', () => {
    const rawRoxo = resolveThemeAccent('Roxo (Padrão)', 'warm-paper');
    expect(rawRoxo).toBe('#8b5cf6');

    // Ao ajustar contraste para o papel claro, mantém matiz roxo e texto branco legível
    const adjusted = ensureAccentContrast(rawRoxo, THEME_PANEL_BG['warm-paper'], 4.5);
    const [r, g, b] = hexToRgb(adjusted);
    expect(b).toBeGreaterThan(g); // Componente azul/violeta predominante sobre o verde
    expect(r).toBeGreaterThan(g); // Componente vermelho predominante (matiz púrpura)
    expect(contrastRatio(adjusted, THEME_PANEL_BG['warm-paper'])).toBeGreaterThanOrEqual(4.5);
    expect(pickOnAccentColor(adjusted)).toBe('#ffffff');
  });

  it('suporta acento branco puro e preto puro com contraste e texto adequados', () => {
    // Branco puro sobre fundo escuro deve manter branco e escolher texto escuro
    const whiteOnDark = ensureAccentContrast('#ffffff', THEME_PANEL_BG.dark, 4.5);
    expect(whiteOnDark).toBe('#ffffff');
    expect(pickOnAccentColor(whiteOnDark)).toBe('#000000');
    expect(contrastRatio(whiteOnDark, '#000000')).toBeGreaterThanOrEqual(15);

    // Preto puro sobre fundo claro deve manter preto e escolher texto claro
    const blackOnLight = ensureAccentContrast('#000000', THEME_PANEL_BG.light, 4.5);
    expect(blackOnLight).toBe('#000000');
    expect(pickOnAccentColor(blackOnLight)).toBe('#ffffff');
    expect(contrastRatio(blackOnLight, '#ffffff')).toBeGreaterThanOrEqual(15);
  });
});
