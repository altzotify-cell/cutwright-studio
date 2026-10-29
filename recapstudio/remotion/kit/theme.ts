import {Theme} from './types';

export const defaultTheme: Theme = {
  name: 'default',
  palette: {
    bg: '#0b0d14',
    bg2: '#1b2036',
    fg: '#f4f6ff',
    muted: '#8d95b3',
    accent: '#FFD23F',
    accent2: '#4cc9f0',
    good: '#3ddc97',
    bad: '#ff5a5f',
  },
  fonts: {
    heading: '"Arial Black", Impact, "Segoe UI", Arial, sans-serif',
    body: '"Segoe UI", Arial, sans-serif',
  },
  energy: 'punchy',
  grain: 0,
};

type Loose = {[k: string]: any} | undefined | null;

// Defaults < the project's accent/font from config.json < theme.json. Unknown keys are ignored.
export const mergeTheme = (partial?: Loose, base: Theme = defaultTheme): Theme => {
  const p = (partial ?? {}) as any;
  return {
    name: typeof p.name === 'string' ? p.name : base.name,
    palette: {...base.palette, ...(typeof p.palette === 'object' && p.palette ? p.palette : {})},
    fonts: {...base.fonts, ...(typeof p.fonts === 'object' && p.fonts ? p.fonts : {})},
    energy: p.energy === 'calm' || p.energy === 'punchy' || p.energy === 'chaotic' ? p.energy : base.energy,
    grain: typeof p.grain === 'number' ? p.grain : base.grain,
  };
};

// How lively a theme feels. Multiply animation SPEED by `speed` and distances / sizes of movement by `amp`.
export const energyOf = (theme: Theme): {speed: number; amp: number} => {
  switch (theme.energy) {
    case 'calm':
      return {speed: 0.75, amp: 0.7};
    case 'chaotic':
      return {speed: 1.35, amp: 1.4};
    default:
      return {speed: 1, amp: 1};
  }
};

// '#ffd23f' + 0.4 -> 'rgba(255,210,63,0.4)'. Anything that is not a 3/6 digit hex is returned unchanged.
export const withAlpha = (color: string, alpha: number): string => {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(color.trim());
  if (!m) return color;
  let h = m[1];
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const n = parseInt(h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${Math.max(0, Math.min(1, alpha))})`;
};
