const { nativeImage } = require('electron');
const fs = require('fs');
const { getIconPath } = require('./paths');

// Cache de ícones com badge em memória por estado ('idle' | 'working' | 'success' | 'error' | 'warning')
const badgeIconCache = new Map();
const overlayIconCache = new Map();

// Paleta sóbria (Matte Dark Win11 / VS Code) para os badges do ícone e barra de tarefas
const BADGE_PALETTE = {
  working: { r: 96, g: 165, b: 250 },   // Azul Sóbrio (#60a5fa)
  success: { r: 78, g: 201, b: 176 },   // Verde Sóbrio (#4ec9b0)
  error:   { r: 244, g: 135, b: 113 },  // Coral / Alerta (#f48771)
  warning: { r: 220, g: 160, b: 75 },   // Âmbar Sóbrio (#dca04b)
};

/**
 * Desenha um círculo suave (anti-aliased) sobre um buffer BGRA nativo do Electron/Windows.
 * 
 * POR QUE MANIPULAÇÃO DIRETA DE BUFFER BGRA:
 * 1. Ausência de DOM no Main Process: O processo principal do Electron é Node.js puro e não tem acesso
 *    ao HTML5 <canvas>. Depender de bibliotecas nativas como node-canvas ou Sharp exigiria compilação
 *    via node-gyp e Python/Visual Studio, quebrando a portabilidade em máquinas de usuários comuns.
 * 2. Formato BGRA vs RGBA: O Windows e a API nativa de ícones do Electron (nativeImage.toBitmap())
 *    trabalham em ordem BGRA (Blue em byte 0, Green em 1, Red em 2, Alpha em 3).
 *    Esta rotina escreve diretamente na ordem correta, garantindo que as cores (#60a5fa, #4ec9b0)
 *    não sofram inversão de canais cromáticos.
 * 3. Anti-Aliasing Matemático: Faz a interpolação linear dos pixels de borda (edgeAlpha) com o fundo
 *    do ícone, entregando um badge nítido e estético mesmo em resolução reduzida (16x16 / 32x32).
 */
function drawBadgeCircleOnBgra(buf, width, height, cx, cy, radius, borderRadius, color) {
  const minX = Math.max(0, Math.floor(cx - borderRadius - 1));
  const maxX = Math.min(width - 1, Math.ceil(cx + borderRadius + 1));
  const minY = Math.max(0, Math.floor(cy - borderRadius - 1));
  const maxY = Math.min(height - 1, Math.ceil(cy + borderRadius + 1));

  for (let y = minY; y <= maxY; y++) {
    for (let x = minX; x <= maxX; x++) {
      const dx = x - cx;
      const dy = y - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > borderRadius + 0.8) continue;

      const idx = (y * width + x) * 4;
      if (dist <= radius - 0.5) {
        buf[idx] = color.b;
        buf[idx + 1] = color.g;
        buf[idx + 2] = color.r;
        buf[idx + 3] = 255;
      } else if (dist <= radius + 0.5) {
        const t = dist - (radius - 0.5);
        buf[idx] = Math.round(color.b * (1 - t) + 20 * t);
        buf[idx + 1] = Math.round(color.g * (1 - t) + 20 * t);
        buf[idx + 2] = Math.round(color.r * (1 - t) + 20 * t);
        buf[idx + 3] = 255;
      } else if (dist <= borderRadius) {
        buf[idx] = 20;
        buf[idx + 1] = 20;
        buf[idx + 2] = 20;
        buf[idx + 3] = 245;
      } else {
        const edgeAlpha = Math.max(0, Math.min(1, 1 - (dist - borderRadius) / 0.8));
        const srcB = buf[idx];
        const srcG = buf[idx + 1];
        const srcR = buf[idx + 2];
        const srcA = buf[idx + 3] / 255;
        const outA = edgeAlpha + srcA * (1 - edgeAlpha);
        if (outA > 0) {
          buf[idx] = Math.round((20 * edgeAlpha + srcB * srcA * (1 - edgeAlpha)) / outA);
          buf[idx + 1] = Math.round((20 * edgeAlpha + srcG * srcA * (1 - edgeAlpha)) / outA);
          buf[idx + 2] = Math.round((20 * edgeAlpha + srcR * srcA * (1 - edgeAlpha)) / outA);
          buf[idx + 3] = Math.round(outA * 255);
        }
      }
    }
  }
}

/**
 * Gera ou recupera do cache o nativeImage da bandeja com badge de estado.
 */
function getBadgedTrayIcon(state = 'idle') {
  const iconPath = getIconPath();
  if (!fs.existsSync(iconPath)) return null;

  if (badgeIconCache.has(state)) {
    return badgeIconCache.get(state);
  }

  try {
    const baseImg = nativeImage.createFromPath(iconPath);
    if (!baseImg || baseImg.isEmpty()) return null;

    if (state === 'idle' || !BADGE_PALETTE[state]) {
      badgeIconCache.set('idle', baseImg);
      return baseImg;
    }

    const size = 32;
    const resized = baseImg.resize({ width: size, height: size, quality: 'best' });
    const bitmap = resized.toBitmap();
    if (!bitmap || bitmap.length < size * size * 4) {
      return baseImg;
    }

    const buf = Buffer.from(bitmap);
    const color = BADGE_PALETTE[state];
    drawBadgeCircleOnBgra(buf, size, size, 24, 24, 5.5, 7.2, color);

    const badged = nativeImage.createFromBitmap(buf, { width: size, height: size });
    badgeIconCache.set(state, badged);
    return badged;
  } catch (err) {
    console.warn('[Tray] Falha ao compor badge no ícone:', err);
    return nativeImage.createFromPath(iconPath);
  }
}

/**
 * Gera um ícone de sobreposição (16x16) para a Barra de Tarefas do Windows (Taskbar Overlay Icon).
 */
function getTaskbarOverlayIcon(state = 'idle') {
  if (!state || state === 'idle' || !BADGE_PALETTE[state]) return null;
  if (overlayIconCache.has(state)) return overlayIconCache.get(state);

  try {
    const size = 16;
    const buf = Buffer.alloc(size * size * 4, 0);
    const color = BADGE_PALETTE[state];
    drawBadgeCircleOnBgra(buf, size, size, 8, 8, 5.2, 6.8, color);
    const img = nativeImage.createFromBitmap(buf, { width: size, height: size });
    overlayIconCache.set(state, img);
    return img;
  } catch (_) {
    return null;
  }
}

/**
 * Resolve o estado do badge visual a partir do status textual e flags.
 */
function resolveBadgeState(statusText, isWorking, explicitBadge) {
  if (explicitBadge && ['idle', 'working', 'success', 'error', 'warning'].includes(explicitBadge)) {
    return explicitBadge;
  }
  if (isWorking) return 'working';
  const lower = String(statusText || '').toLowerCase();
  if (lower.includes('alerta') || lower.includes('erro') || lower.includes('falha')) {
    return 'error';
  }
  if (lower.includes('concluído') || lower.includes('finalizado')) {
    return 'success';
  }
  return 'idle';
}

module.exports = {
  BADGE_PALETTE,
  drawBadgeCircleOnBgra,
  getBadgedTrayIcon,
  getTaskbarOverlayIcon,
  resolveBadgeState,
};
