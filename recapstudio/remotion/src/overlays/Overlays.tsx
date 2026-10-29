import React from 'react';
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {makeLayout} from '../layout';
import {Style} from '../types';

// On-screen text that is not the spoken captions. All of it lives inside the segment's Sequence,
// so `frame` is counted from the start of the segment.

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const easeOut = Easing.bezier(0.16, 1, 0.3, 1);

const fadeEnds = (frame: number, total: number, inF: number, outF: number) =>
  Math.min(
    interpolate(frame, [0, inF], [0, 1], clamp),
    interpolate(frame, [total - outF, total], [1, 0], clamp)
  );

// ---- chapter card: number + title wipe in over the footage, then out ------------------------------
export const ChapterCard: React.FC<{index: number; title: string; style: Style; segmentFrames: number}> = ({
  index,
  title,
  style,
  segmentFrames,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const L = makeLayout(width, height);
  const total = Math.min(segmentFrames, Math.round(style.overlays.chapter_seconds * fps));
  if (frame >= total) return null;

  const wipe = interpolate(frame, [0, 14], [0, 1], {...clamp, easing: easeOut});
  const textIn = interpolate(frame, [6, 22], [0, 1], {...clamp, easing: easeOut});
  const out = interpolate(frame, [total - 9, total], [1, 0], clamp);
  const num = String(index).padStart(2, '0');
  const big = (L.portrait ? 128 : 150) * L.u;
  const small = (L.portrait ? 34 : 30) * L.u;
  const titleSize = (L.portrait ? 62 : 70) * L.u;

  return (
    <div style={{position: 'absolute', inset: 0, opacity: out, fontFamily: style.font, pointerEvents: 'none'}}>
      {/* soft dark band so the text reads over any footage */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: L.portrait ? '18%' : '34%',
          height: L.portrait ? '26%' : '32%',
          background: 'linear-gradient(90deg, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0.55) 70%, rgba(0,0,0,0) 100%)',
          transform: `scaleX(${wipe})`,
          transformOrigin: '0 50%',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: L.safeSide,
          top: L.portrait ? '20%' : '36%',
          display: 'flex',
          alignItems: 'center',
          gap: 28 * L.u,
          maxWidth: width - L.safeSide * 2,
          opacity: textIn,
          transform: `translateX(${(1 - textIn) * -40 * L.u}px)`,
        }}
      >
        <div style={{fontSize: big, lineHeight: 1, color: style.accent, fontWeight: 900}}>{num}</div>
        <div style={{borderLeft: `${5 * L.u}px solid ${style.accent}`, paddingLeft: 24 * L.u}}>
          <div style={{fontSize: small, letterSpacing: 6 * L.u, color: 'rgba(255,255,255,0.8)', fontWeight: 700}}>
            CHAPTER {index}
          </div>
          <div style={{fontSize: titleSize, lineHeight: 1.05, color: '#fff', fontWeight: 900, marginTop: 6 * L.u}}>
            {title}
          </div>
        </div>
      </div>
    </div>
  );
};

// ---- lower third: name + role bar, first appearance of a character -----------------------------------
export const LowerThird: React.FC<{name: string; role: string; style: Style; segmentFrames: number}> = ({
  name,
  role,
  style,
  segmentFrames,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const L = makeLayout(width, height);
  const start = Math.round(fps * 0.6);
  const total = Math.min(Math.round(fps * 3.6), Math.max(0, segmentFrames - start));
  const f = frame - start;
  if (f < 0 || f >= total) return null;

  const slide = spring({frame: f, fps, config: {damping: 16, stiffness: 140}, durationInFrames: 18});
  const out = interpolate(f, [total - 8, total], [1, 0], clamp);

  return (
    <div
      style={{
        position: 'absolute',
        left: L.safeSide,
        bottom: Math.round(height * (L.portrait ? 0.32 : 0.2)),
        opacity: out,
        transform: `translateX(${(1 - slide) * -120 * L.u}px)`,
        fontFamily: style.font,
        pointerEvents: 'none',
        display: 'flex',
      }}
    >
      <div style={{width: 8 * L.u, background: style.accent}} />
      <div style={{background: 'rgba(0,0,0,0.72)', padding: `${14 * L.u}px ${28 * L.u}px`}}>
        <div style={{color: '#fff', fontWeight: 900, fontSize: 48 * L.u, lineHeight: 1.1}}>{name}</div>
        {role ? (
          <div style={{color: style.accent, fontWeight: 700, fontSize: 28 * L.u, letterSpacing: 2 * L.u, marginTop: 4 * L.u}}>
            {role.toUpperCase()}
          </div>
        ) : null}
      </div>
    </div>
  );
};

// ---- rank stamp (#N, for countdowns) -----------------------------------------------------------------
export const RankStamp: React.FC<{rank: string | number; style: Style; segmentFrames: number}> = ({
  rank,
  style,
  segmentFrames,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const L = makeLayout(width, height);
  const pop = spring({frame, fps, config: {damping: 11, stiffness: 200}, durationInFrames: 14});
  const out = interpolate(frame, [segmentFrames - 6, segmentFrames], [1, 0], clamp);
  return (
    <div
      style={{
        position: 'absolute',
        left: L.safeSide,
        top: L.safeTop,
        opacity: out,
        transform: `scale(${interpolate(pop, [0, 1], [0.4, 1])})`,
        transformOrigin: '0 0',
        fontFamily: style.font,
        pointerEvents: 'none',
        background: 'rgba(0,0,0,0.6)',
        border: `${4 * L.u}px solid ${style.accent}`,
        padding: `${6 * L.u}px ${26 * L.u}px`,
        color: '#fff',
        fontWeight: 900,
        fontSize: (L.portrait ? 130 : 170) * L.u,
        lineHeight: 1.05,
      }}
    >
      #{rank}
    </div>
  );
};

// ---- caption badge: the segment's "caption" field (date, stat line, label) ----------------------------
export const CaptionBadge: React.FC<{text: string; style: Style; segmentFrames: number}> = ({
  text,
  style,
  segmentFrames,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const L = makeLayout(width, height);
  const delay = 4;
  const total = Math.min(segmentFrames, Math.round(fps * 5));
  const f = frame - delay;
  if (f < 0 || f >= total - delay) return null;
  const inP = spring({frame: f, fps, config: {damping: 15, stiffness: 170}, durationInFrames: 14});
  const op = fadeEnds(f, total - delay, 5, 8);
  return (
    <div
      style={{
        position: 'absolute',
        left: L.safeSide,
        right: L.safeSide,
        top: L.safeTop,
        display: 'flex',
        justifyContent: 'center',
        opacity: op,
        transform: `translateY(${(1 - inP) * -30 * L.u}px)`,
        fontFamily: style.font,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          background: 'rgba(0,0,0,0.68)',
          borderBottom: `${5 * L.u}px solid ${style.accent}`,
          color: '#fff',
          fontWeight: 800,
          fontSize: (L.portrait ? 44 : 40) * L.u,
          padding: `${12 * L.u}px ${30 * L.u}px`,
          textAlign: 'center',
          maxWidth: '100%',
        }}
      >
        {text}
      </div>
    </div>
  );
};
