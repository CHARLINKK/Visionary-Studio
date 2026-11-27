// ── Sistema de Feedback Sonoro Harmônico (Web Audio API) ──

let sharedAudioCtx = null;

function getAudioContext() {
  if (typeof window === 'undefined') return null;
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return null;
  if (!sharedAudioCtx || sharedAudioCtx.state === 'closed') {
    sharedAudioCtx = new AudioCtx();
  }
  if (sharedAudioCtx.state === 'suspended') {
    sharedAudioCtx.resume().catch(() => {});
  }
  return sharedAudioCtx;
}

// Desbloqueia o AudioContext no primeiro gesto do usuário
if (typeof window !== 'undefined') {
  const unlockAudio = () => {
    const ctx = getAudioContext();
    if (ctx && ctx.state === 'suspended') ctx.resume().catch(() => {});
  };
  window.addEventListener('pointerdown', unlockAudio, { once: true, passive: true });
  window.addEventListener('keydown', unlockAudio, { once: true, passive: true });
}

export function isSoundEnabled() {
  if (typeof window === 'undefined') return true;
  const stored = localStorage.getItem('visionary:sound_feedback');
  if (stored !== null) return stored === 'true';
  return true;
}

export function setSoundEnabled(enabled) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('visionary:sound_feedback', enabled ? 'true' : 'false');
}

export function getSoundStyle() {
  if (typeof window === 'undefined') return 'harmonic';
  const stored = localStorage.getItem('visionary:sound_style');
  return stored || 'harmonic';
}

export function setSoundStyle(style) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('visionary:sound_style', style);
}

export function getSoundVolume() {
  if (typeof window === 'undefined') return 0.8;
  const stored = localStorage.getItem('visionary:sound_volume');
  if (stored !== null) {
    const val = parseFloat(stored);
    if (!isNaN(val) && val >= 0.05 && val <= 1.0) return val;
  }
  return 0.8;
}

export function setSoundVolume(volume) {
  if (typeof window === 'undefined') return;
  const clamped = Math.max(0.05, Math.min(1.0, volume));
  localStorage.setItem('visionary:sound_volume', clamped.toString());
}

/**
 * Toca feedback acústico (Harmônico, Pop Sutil ou Tech Bip)
 */
export const playChime = async (force = false, explicitStyle = null) => {
  if (!force && !isSoundEnabled()) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    if (ctx.state === 'suspended') await ctx.resume();
    const now = ctx.currentTime;
    const style = explicitStyle || getSoundStyle();
    const masterVol = getSoundVolume();

    if (style === 'pop') {
      // Micro-pop duplo suave e orgânico
      const pops = [
        { freq: 520, delay: 0,    vol: 0.14 * masterVol, dur: 0.05 },
        { freq: 760, delay: 0.04, vol: 0.16 * masterVol, dur: 0.08 },
      ];
      pops.forEach(({ freq, delay, vol, dur }) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, now + delay);
        osc.frequency.exponentialRampToValueAtTime(freq * 0.7, now + delay + dur);
        gain.gain.setValueAtTime(vol, now + delay);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + delay + dur);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + delay);
        osc.stop(now + delay + dur);
      });
    } else if (style === 'tech') {
      // Bi-tom eletrônico sutil e limpo
      const tones = [
        { freq: 587.33, delay: 0,    vol: 0.10 * masterVol, dur: 0.10 }, // D5
        { freq: 880.00, delay: 0.07, vol: 0.12 * masterVol, dur: 0.20 }, // A5
      ];
      tones.forEach(({ freq, delay, vol, dur }) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, now + delay);
        gain.gain.setValueAtTime(vol, now + delay);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + delay + dur);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + delay);
        osc.stop(now + delay + dur);
      });
    } else {
      // 'harmonic' (Padrão: Acorde tríade suave C5->E5->G5)
      const notes = [
        { freq: 523.25, delay: 0,    vol: 0.08 * masterVol, dur: 0.30 },
        { freq: 659.25, delay: 0.07, vol: 0.10 * masterVol, dur: 0.42 },
        { freq: 783.99, delay: 0.14, vol: 0.12 * masterVol, dur: 0.55 },
      ];
      notes.forEach(({ freq, delay, vol, dur }) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, now + delay);
        gain.gain.setValueAtTime(vol, now + delay);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + delay + dur);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + delay);
        osc.stop(now + delay + dur);
      });
    }
  } catch (err) {
    console.warn('Audio feedback failed:', err);
  }
};

/**
 * Micro-pop discreto para cópia de balão individual (880->440 Hz, 50ms)
 */
export const playCopySound = async (force = false) => {
  if (!force && !isSoundEnabled()) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    if (ctx.state === 'suspended') await ctx.resume();
    const now = ctx.currentTime;
    const masterVol = getSoundVolume();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.exponentialRampToValueAtTime(440, now + 0.05);
    gain.gain.setValueAtTime(0.06 * masterVol, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.05);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.05);
  } catch (err) {
    console.warn('Audio feedback failed:', err);
  }
};
