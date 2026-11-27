import { useRef, useCallback, useEffect } from 'react';
import { clientApi } from '../api/bridge';
import {
  LIGHT_THEMES,
  THEME_PANEL_BG,
  DEFAULT_COLOR_MAP,
  resolveThemeAccent,
  ensureAccentContrast,
  pickOnAccentColor,
} from '../utils/accentContrast';

export function useAppTheme(setShowPagePills, setShowStatusDots) {
  const lastSettingsRef = useRef(null);
  const switchTimerRef = useRef(null);

  const applySettings = useCallback((settings) => {
    if (!settings) return;
    lastSettingsRef.current = settings;
    try {
      localStorage.setItem('visionary:app_settings', JSON.stringify(settings));
    } catch (_) {}
    const colorMap = DEFAULT_COLOR_MAP;

    let theme = (settings.theme && settings.theme !== 'System') ? settings.theme : 'Dark';
    const themeAttrMap = {
      'Light': 'light',
      'OLED': 'oled',
      'WarmPaper': 'warm-paper',
      'EInk': 'e-ink',
      'NeoTokyo': 'neo-tokyo',
    };
    const attr = themeAttrMap[theme] || 'dark';
    const root = document.documentElement;
    const currentAttr = root.getAttribute('data-theme');
    const isThemeChanging = Boolean(currentAttr && currentAttr !== attr && currentAttr !== 'dev-matrix');

    const commitDomTokens = () => {
      // Resolve o acento ideal: se for o padrão global, adota a identidade nativa do tema ativo
      const rawColor = resolveThemeAccent(settings.accent, attr, colorMap);
      const isLightTheme = LIGHT_THEMES.has(attr);
      const panelBg = THEME_PANEL_BG[attr] || THEME_PANEL_BG.dark;

      // Suporte fiel a Monocromático: Preto Puro (#000000) e Branco Puro (#ffffff) não sofrem mutação para cinza
      const normalized = typeof rawColor === 'string' ? rawColor.trim().toLowerCase() : '';
      const isMonochrome = normalized === '#000000' || normalized === '#ffffff';

      const hexColor = isMonochrome
        ? normalized
        : (isLightTheme ? ensureAccentContrast(rawColor, panelBg, 4.5) : rawColor);

      const hoverColor = isMonochrome
        ? (hexColor === '#ffffff' ? '#e2e8f0' : '#262626')
        : (isLightTheme ? ensureAccentContrast(hexColor, panelBg, 6) : hexColor);
      
      root.style.setProperty('--brand-primary', hexColor);
      root.style.setProperty('--brand-hover', hoverColor);
      root.style.setProperty('--on-brand', pickOnAccentColor(hexColor));
      
      // Glow discreto em temas claros (evita mancha suja sobre papel ou superfícies claras)
      const glowAlpha = isLightTheme ? '24' : '66';
      const glow = hexColor.includes('gradient') ? '#60a5fa44' : (hexColor + glowAlpha);
      root.style.setProperty('--brand-glow', glow);
      root.setAttribute('data-theme', attr);
    };

    if (isThemeChanging && !settings.reduceMotion) {
      if (switchTimerRef.current) clearTimeout(switchTimerRef.current);
      root.setAttribute('data-theme-switching', 'true');

      // Aplica tokens no DOM e permite a interpolação geométrica fluida de border-radius via CSS
      commitDomTokens();

      switchTimerRef.current = setTimeout(() => {
        root.removeAttribute('data-theme-switching');
      }, 350);
    } else {
      commitDomTokens();
    }

    // Densidade & Efeitos Visuais
    if (settings.uiDensity) {
      root.setAttribute('data-density', settings.uiDensity);
    }
    if (settings.reduceMotion) {
      root.setAttribute('data-reduce-motion', 'true');
    } else {
      root.removeAttribute('data-reduce-motion');
    }
    if (settings.acrylicBlur === false) {
      root.style.setProperty('--backdrop-blur', 'none');
    } else {
      root.style.removeProperty('--backdrop-blur');
    }

    // Tipografia da Interface
    const font = settings.fontFamily || 'modern';
    root.setAttribute('data-font', font);

    // Escala da Interface (Zoom da UI)
    const scale = settings.uiScale || '100%';
    const scaleFactorMap = { '90%': 0.9, '100%': 1.0, '110%': 1.1, '120%': 1.2 };
    const numFactor = scaleFactorMap[scale] || 1.0;
    if (window.electronAPI?.setZoomFactor) {
      window.electronAPI.setZoomFactor(numFactor);
    } else {
      root.style.zoom = scale;
    }

    // Opções de Detalhe do Explorador
    if (settings.showPagePills !== undefined && setShowPagePills) setShowPagePills(settings.showPagePills);
    if (settings.showStatusDots !== undefined && setShowStatusDots) setShowStatusDots(settings.showStatusDots);
  }, [setShowPagePills, setShowStatusDots]);

  // Aplica configurações em cache no primeiro ciclo para evitar flash de tema, fonte ou densidade
  useEffect(() => {
    try {
      const cached = localStorage.getItem('visionary:app_settings');
      if (cached) {
        applySettings(JSON.parse(cached));
      }
    } catch (_) {}
  }, [applySettings]);

  const applyDevTheme = useCallback(() => {
    document.documentElement.setAttribute('data-theme', 'dev-matrix');
    document.documentElement.style.setProperty('--brand-primary', '#ffffff');
    document.documentElement.style.setProperty('--brand-hover', '#e4e4e7');
    document.documentElement.style.setProperty('--brand-glow', 'rgba(255, 255, 255, 0.35)');
    document.documentElement.style.setProperty('--brand-purple', '#e4e4e7');
    document.documentElement.style.setProperty('--brand-pink', '#d4d4d8');
    document.documentElement.style.setProperty('--brand-green', '#d4d4d8');
  }, []);

  const restoreUserTheme = useCallback(() => {
    document.documentElement.style.removeProperty('--brand-purple');
    document.documentElement.style.removeProperty('--brand-pink');
    document.documentElement.style.removeProperty('--brand-green');
    if (lastSettingsRef.current) {
      applySettings(lastSettingsRef.current);
    } else {
      clientApi.getSettings().then(settings => {
        if (settings) applySettings(settings);
      }).catch(() => {
        document.documentElement.setAttribute('data-theme', 'dark');
        document.documentElement.style.setProperty('--brand-primary', '#8b5cf6');
        document.documentElement.style.setProperty('--brand-hover', '#8b5cf6');
        document.documentElement.style.setProperty('--brand-glow', '#8b5cf666');
      });
    }
  }, [applySettings]);

  return { applySettings, applyDevTheme, restoreUserTheme };
}
