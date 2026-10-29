import React from 'react';
import {ease, progress} from './motion';

export type Point = {x: number; y: number};

// Straight lines through the points: 'M x y L x y ...'
export const polylinePath = (pts: Point[]): string =>
  pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ');

// A smooth curve through the points (Catmull-Rom converted to cubic beziers).
export const smoothPath = (pts: Point[], tension = 0.5): string => {
  if (pts.length < 3) return polylinePath(pts);
  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const k = (tension * 2) / 6;
    const c1 = {x: p1.x + (p2.x - p0.x) * k, y: p1.y + (p2.y - p0.y) * k};
    const c2 = {x: p2.x - (p3.x - p1.x) * k, y: p2.y - (p3.y - p1.y) * k};
    d += ` C ${c1.x.toFixed(2)} ${c1.y.toFixed(2)} ${c2.x.toFixed(2)} ${c2.y.toFixed(2)} ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  return d;
};

// Arc of a circle, angles in degrees (0 = 3 o'clock, clockwise).
export const arcPath = (cx: number, cy: number, r: number, startDeg: number, endDeg: number): string => {
  const a0 = (startDeg * Math.PI) / 180;
  const a1 = (endDeg * Math.PI) / 180;
  const large = Math.abs(endDeg - startDeg) > 180 ? 1 : 0;
  return `M ${cx + r * Math.cos(a0)} ${cy + r * Math.sin(a0)} A ${r} ${r} 0 ${large} 1 ${cx + r * Math.cos(a1)} ${cy + r * Math.sin(a1)}`;
};

// A path that draws itself between two frames. Put it inside an <svg>.
export const DrawPath: React.FC<{
  d: string;
  frame: number;
  start?: number;
  duration?: number;
  stroke: string;
  strokeWidth?: number;
  fill?: string;
  opacity?: number;
  linecap?: 'round' | 'butt' | 'square';
}> = ({d, frame, start = 0, duration = 30, stroke, strokeWidth = 4, fill = 'none', opacity = 1, linecap = 'round'}) => {
  const p = progress(frame, start, start + duration, ease.inOut);
  return (
    <path
      d={d}
      pathLength={1}
      fill={fill}
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeLinecap={linecap}
      strokeLinejoin="round"
      strokeDasharray={1}
      strokeDashoffset={1 - p}
      opacity={p > 0 ? opacity : 0}
    />
  );
};
