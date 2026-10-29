import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// Easing curves and spring presets, so every scene moves with the same "feel".
export const ease = {
  out: Easing.bezier(0.16, 1, 0.3, 1), // fast start, long soft landing: the default for things appearing
  inOut: Easing.bezier(0.65, 0, 0.35, 1),
  in: Easing.bezier(0.7, 0, 0.84, 0), // things leaving
  back: Easing.bezier(0.34, 1.56, 0.64, 1), // small overshoot (pop)
  linear: (t: number) => t,
};

export const springs = {
  soft: {damping: 200}, // no bounce
  smooth: {damping: 26, stiffness: 120},
  snappy: {damping: 16, stiffness: 180},
  bouncy: {damping: 9, stiffness: 140, mass: 0.8},
} as const;

export type SpringName = keyof typeof springs;

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

// 0 -> 1 between two frames (clamped). `progress(frame, 10, 40)`
export const progress = (frame: number, from: number, to: number, easing: (t: number) => number = ease.out): number =>
  interpolate(frame, [from, Math.max(from + 1, to)], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing,
  });

// 1 -> 0 at the end: `fadeOut(frame, durationInFrames, 12)` is 1 until 12 frames before the end.
export const fadeOut = (frame: number, total: number, frames = 10): number =>
  interpolate(frame, [total - frames, total], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

// Frame offset of the i-th item in a staggered list.
export const stagger = (index: number, step = 4) => index * step;

// A spring that starts at `delay` (frames) and settles at 1. Hook: call it at the top of a component.
export const useEntrance = (delay = 0, preset: SpringName = 'smooth'): number => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: frame - delay, fps, config: springs[preset]});
};

// Deterministic wobble (never use Math.random: frames are rendered in parallel and must match).
export const wobble = (frame: number, period = 60, amount = 1, phase = 0): number =>
  Math.sin(((frame + phase) / period) * Math.PI * 2) * amount;
