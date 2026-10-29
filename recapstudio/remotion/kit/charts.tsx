import React from 'react';
import {useCurrentFrame} from 'remotion';
import {ease, progress} from './motion';
import {DrawPath, Point, polylinePath, smoothPath} from './shapes';
import {withAlpha} from './theme';

// ---------------------------------------------------------------------------------------------
// AnimatedCounter: counts from `from` to `to` between `start` and `start + duration` frames.
// ---------------------------------------------------------------------------------------------
export const formatNumber = (v: number, decimals = 0): string =>
  v.toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});

export const AnimatedCounter: React.FC<{
  to: number;
  from?: number;
  start?: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  thousands?: boolean; // 1,234 instead of 1234
  style?: React.CSSProperties;
}> = ({to, from = 0, start = 0, duration = 36, decimals = 0, prefix = '', suffix = '', thousands = true, style}) => {
  const frame = useCurrentFrame();
  const p = progress(frame, start, start + duration, ease.out);
  const v = from + (to - from) * p;
  const body = thousands ? formatNumber(v, decimals) : v.toFixed(decimals);
  return <span style={{fontVariantNumeric: 'tabular-nums', ...style}}>{`${prefix}${body}${suffix}`}</span>;
};

// ---------------------------------------------------------------------------------------------
// RingChart: a circular progress ring (0-100). Put your own content (a number, an icon) as children.
// ---------------------------------------------------------------------------------------------
export const RingChart: React.FC<{
  value: number; // 0..100
  size: number; // px (outer diameter)
  stroke?: number; // px
  start?: number;
  duration?: number;
  color: string;
  trackColor: string;
  glow?: boolean;
  children?: React.ReactNode;
}> = ({value, size, stroke = size * 0.1, start = 0, duration = 40, color, trackColor, glow = true, children}) => {
  const frame = useCurrentFrame();
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const p = progress(frame, start, start + duration, ease.out);
  const shown = Math.max(0, Math.min(100, value)) / 100;
  return (
    <div style={{position: 'relative', width: size, height: size}}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={trackColor} strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${c * shown * p} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={glow ? {filter: `drop-shadow(0 0 ${stroke * 0.8}px ${withAlpha(color, 0.55)})`} : undefined}
        />
      </svg>
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        {children}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------------------------
// BarChart: horizontal bars that grow one after another, with labels and counting values.
// ---------------------------------------------------------------------------------------------
export type BarItem = {label: string; value: number; color?: string};

export const BarChart: React.FC<{
  items: BarItem[];
  width: number;
  rowHeight?: number;
  gap?: number;
  max?: number; // default: the largest value
  start?: number;
  step?: number; // frames between bars
  duration?: number; // frames each bar needs to grow
  color: string;
  trackColor: string;
  labelColor: string;
  valueColor?: string;
  font?: string;
  suffix?: string;
  decimals?: number;
}> = ({
  items,
  width,
  rowHeight = 64,
  gap = 22,
  max,
  start = 0,
  step = 8,
  duration = 30,
  color,
  trackColor,
  labelColor,
  valueColor,
  font,
  suffix = '',
  decimals = 0,
}) => {
  const frame = useCurrentFrame();
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  const labelW = Math.min(width * 0.32, rowHeight * 5);
  const valueW = rowHeight * 2;
  const barW = Math.max(10, width - labelW - valueW);
  return (
    <div style={{width, fontFamily: font}}>
      {items.map((it, i) => {
        const p = progress(frame, start + i * step, start + i * step + duration, ease.out);
        const v = it.value * p;
        return (
          <div key={i} style={{display: 'flex', alignItems: 'center', height: rowHeight, marginBottom: i < items.length - 1 ? gap : 0}}>
            <div
              style={{
                width: labelW,
                color: labelColor,
                fontSize: rowHeight * 0.42,
                fontWeight: 700,
                paddingRight: rowHeight * 0.3,
                textAlign: 'right',
                opacity: Math.min(1, p * 3),
                overflow: 'hidden',
                whiteSpace: 'nowrap',
                textOverflow: 'ellipsis',
              }}
            >
              {it.label}
            </div>
            <div style={{width: barW, height: rowHeight * 0.62, background: trackColor, borderRadius: rowHeight, overflow: 'hidden'}}>
              <div
                style={{
                  width: `${(Math.max(0, v) / top) * 100}%`,
                  height: '100%',
                  background: it.color ?? color,
                  borderRadius: rowHeight,
                }}
              />
            </div>
            <div
              style={{
                width: valueW,
                color: valueColor ?? labelColor,
                fontSize: rowHeight * 0.5,
                fontWeight: 800,
                paddingLeft: rowHeight * 0.3,
                fontVariantNumeric: 'tabular-nums',
                opacity: Math.min(1, p * 3),
              }}
            >
              {formatNumber(v, decimals)}
              {suffix}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------------------------------------
// LineChart: a line that draws itself over a faint area, ending with a glowing dot.
// `points` are plain numbers (spread evenly left to right) or {x, y} in 0..1 chart space (y up).
// ---------------------------------------------------------------------------------------------
export const LineChart: React.FC<{
  points: number[] | Point[];
  width: number;
  height: number;
  start?: number;
  duration?: number;
  color: string;
  strokeWidth?: number;
  smooth?: boolean;
  area?: boolean;
  gridColor?: string;
  dot?: boolean;
}> = ({points, width, height, start = 0, duration = 40, color, strokeWidth = 6, smooth = true, area = true, gridColor, dot = true}) => {
  const frame = useCurrentFrame();
  const pad = strokeWidth * 2;
  const nums = typeof points[0] === 'number';
  const raw: Point[] = (points as any[]).map((p, i, arr) =>
    nums ? {x: arr.length > 1 ? i / (arr.length - 1) : 0.5, y: p as number} : (p as Point)
  );
  const lo = Math.min(...raw.map((p) => p.y));
  const hi = Math.max(...raw.map((p) => p.y));
  const span = hi - lo || 1;
  const pts = raw.map((p) => ({
    x: pad + p.x * (width - pad * 2),
    y: pad + (1 - (nums ? (p.y - lo) / span : p.y)) * (height - pad * 2),
  }));
  const d = smooth ? smoothPath(pts) : polylinePath(pts);
  const p = progress(frame, start, start + duration, ease.inOut);
  const last = pts[pts.length - 1];
  const areaD = `${d} L ${last.x} ${height} L ${pts[0].x} ${height} Z`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{overflow: 'visible'}}>
      {gridColor
        ? [0, 1, 2, 3].map((i) => (
            <line key={i} x1={0} x2={width} y1={pad + ((height - pad * 2) / 3) * i} y2={pad + ((height - pad * 2) / 3) * i} stroke={gridColor} strokeWidth={2} />
          ))
        : null}
      {area ? <path d={areaD} fill={withAlpha(color, 0.14)} opacity={p} /> : null}
      <DrawPath d={d} frame={frame} start={start} duration={duration} stroke={color} strokeWidth={strokeWidth} />
      {dot && p >= 1 ? (
        <circle cx={last.x} cy={last.y} r={strokeWidth * 1.6} fill={color} style={{filter: `drop-shadow(0 0 ${strokeWidth * 2}px ${withAlpha(color, 0.8)})`}} />
      ) : null}
    </svg>
  );
};
