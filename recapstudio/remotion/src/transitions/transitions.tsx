import React from 'react';
import {Easing, interpolate, random} from 'remotion';
import {TransitionName} from '../types';

// Transitions that need NO overlap between clips (every clip is already exactly as long as its voice-over,
// so nothing can be extended without breaking the sync). Each one is an effect on the picture only:
//   enter = the first n frames of the incoming segment
//   exit  = the last frames of the outgoing segment (driven by the NEXT segment's transition)
// The voice and the music are never touched.

export type Fx = {style: React.CSSProperties; overlay?: React.ReactNode};
export const NO_FX: Fx = {style: {}};

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

/** How many frames the outgoing segment spends on the exit half of the effect. */
export const exitLength = (type: TransitionName | undefined, n: number): number => {
  switch (type) {
    case 'fade':
      return Math.max(2, Math.round(n * 0.6));
    case 'whip':
      return n;
    case 'zoom':
      return Math.max(2, Math.round(n * 0.6));
    default:
      return 0; // cut, flash, glitch: only the incoming side moves
  }
};

/** f = frame inside the segment, n = transition length, w = picture width in px (for blur scale). */
export const enterFx = (type: TransitionName | undefined, f: number, n: number, w: number, seed: string): Fx => {
  if (!type || type === 'cut' || f >= n) return NO_FX;
  const p = clamp01(f / n); // 0 -> 1
  const e = 1 - ease(p); // 1 -> 0 (how far from the settled picture)
  const k = w / 1920;
  switch (type) {
    case 'fade':
      return {style: {opacity: ease(p)}};
    case 'whip':
      return {
        style: {
          transform: `translateX(${e * 0.18 * w}px) scaleX(${1 + 0.12 * e})`,
          filter: `blur(${e * 42 * k}px)`,
        },
      };
    case 'zoom':
      return {style: {transform: `scale(${1 + 0.14 * e})`, filter: `blur(${e * 12 * k}px)`}};
    case 'flash':
      return {
        style: {filter: `brightness(${1 + 1.2 * e})`},
        overlay: <div style={{position: 'absolute', inset: 0, background: '#fff', opacity: 0.95 * e}} />,
      };
    case 'glitch': {
      const strength = 1 - p;
      const r = (s: string) => random(`${seed}-${s}-${f}`) - 0.5;
      const bars = [0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: `${(random(`${seed}-bar${i}-${f}`) * 90).toFixed(1)}%`,
            height: `${(2 + random(`${seed}-h${i}-${f}`) * 9).toFixed(1)}%`,
            background: i % 2 ? 'rgba(0,255,255,0.35)' : 'rgba(255,0,80,0.35)',
            transform: `translateX(${r(`bx${i}`) * 0.2 * w * strength}px)`,
            mixBlendMode: 'screen',
          }}
        />
      ));
      return {
        style: {
          transform: `translateX(${r('x') * 0.07 * w * strength}px) skewX(${r('s') * 10 * strength}deg)`,
          filter: `hue-rotate(${r('h') * 140 * strength}deg) saturate(${1 + 1.4 * strength}) contrast(${1 + 0.3 * strength})`,
        },
        overlay: <>{bars}</>,
      };
    }
    default:
      return NO_FX;
  }
};

/** nextType = the NEXT segment's transition; r = frames left in this segment (1 on the last frame). */
export const exitFx = (nextType: TransitionName | undefined, r: number, n: number, w: number): Fx => {
  const len = exitLength(nextType, n);
  if (!nextType || len === 0 || r > len) return NO_FX;
  const x = clamp01(1 - (r - 1) / len); // 0 -> 1 towards the cut
  const k = w / 1920;
  switch (nextType) {
    case 'fade':
      return {style: {opacity: 1 - ease(x)}};
    case 'whip':
      return {
        style: {
          transform: `translateX(${-ease(x) * 0.18 * w}px) scaleX(${1 + 0.12 * ease(x)})`,
          filter: `blur(${ease(x) * 42 * k}px)`,
        },
      };
    case 'zoom':
      return {style: {transform: `scale(${1 + 0.3 * ease(x)})`, filter: `blur(${ease(x) * 18 * k}px)`}};
    default:
      return NO_FX;
  }
};
