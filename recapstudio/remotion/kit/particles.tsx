import React from 'react';
import {random, useCurrentFrame, useVideoConfig} from 'remotion';
import {ease, progress} from './motion';

// Deterministic particles (random() from Remotion is seeded, so every frame and every render agrees).
// Cost: each particle is one small div, so the count is capped at MAX_PARTICLES. 'ambient' is cheap enough
// for 'low' scenes at about 20 particles; 'burst' with 60 is 'medium'.
export const MAX_PARTICLES = 80;

export const Particles: React.FC<{
  count?: number;
  seed?: string | number;
  color: string;
  mode?: 'ambient' | 'burst' | 'rise';
  start?: number; // frame the burst / rise begins (ambient runs the whole scene)
  duration?: number; // frames a burst / rise lasts
  size?: number; // px, average
  spread?: number; // 0..1 how much of the screen a burst covers
  originX?: number; // 0..1 (default centre) where a burst starts
  originY?: number;
  opacity?: number;
  period?: number; // ambient only: frames one drift cycle takes (default 300)
}> = ({count = 24, seed = 'p', color, mode = 'ambient', start = 0, duration = 36, size = 10, spread = 0.5, originX = 0.5, originY = 0.5, opacity = 0.9, period = 300}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const n = Math.max(0, Math.min(MAX_PARTICLES, Math.round(count)));
  const base = Math.min(width, height);

  const items = [];
  for (let i = 0; i < n; i++) {
    const r1 = random(`${seed}-a-${i}`);
    const r2 = random(`${seed}-b-${i}`);
    const r3 = random(`${seed}-c-${i}`);
    const r4 = random(`${seed}-d-${i}`);
    const s = size * (0.5 + r3);
    let x = 0;
    let y = 0;
    let o = 0;
    if (mode === 'ambient') {
      // slow drift upwards, looping every `period` frames
      const t = ((frame / Math.max(1, period)) * (0.4 + r4 * 0.6) + r1) % 1;
      x = (r2 + Math.sin((t + r1) * Math.PI * 2) * 0.03) * width;
      y = (1 - t) * height;
      o = Math.sin(t * Math.PI) * opacity * 0.7;
    } else if (mode === 'burst') {
      const p = progress(frame, start, start + duration, ease.out);
      const angle = r1 * Math.PI * 2;
      const dist = (0.15 + r2 * 0.85) * base * spread * p;
      x = originX * width + Math.cos(angle) * dist;
      y = originY * height + Math.sin(angle) * dist + p * p * base * 0.05;
      o = frame < start ? 0 : (1 - progress(frame, start + duration * 0.4, start + duration, ease.in)) * opacity;
    } else {
      const p = progress(frame, start, start + duration, ease.inOut);
      x = (originX + (r1 - 0.5) * spread * 2) * width + Math.sin(p * 6 + r2 * 6) * base * 0.01;
      y = originY * height - p * (0.15 + r2 * 0.5) * base;
      o = frame < start ? 0 : Math.sin(Math.min(1, p) * Math.PI) * opacity;
    }
    if (o <= 0.01) continue;
    items.push(
      <div
        key={i}
        style={{
          position: 'absolute',
          left: x - s / 2,
          top: y - s / 2,
          width: s,
          height: s,
          borderRadius: '50%',
          background: color,
          opacity: o,
        }}
      />
    );
  }
  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none'}}>{items}</div>;
};
