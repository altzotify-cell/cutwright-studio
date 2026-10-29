import React from 'react';
import {interpolate, spring, useCurrentFrame} from 'remotion';
import {ease, progress, SceneFrame, SceneProps, springs, wobble, withAlpha, Word} from '../../kit';

// The fixed fallback scene. It is used when a shot has no footage (replaces the old "MISSING SHOT" card) and
// whenever a generated scene fails its checks or crashes. The strongest words of the narration pop up one by one,
// exactly when they are spoken, over a themed background. It needs nothing but the narration text and timings.

const STOP = new Set(
  ('about above after again against all also always among and another any are around because been before being between both but ' +
    'came can cannot could did does doing done down during each even ever every few for from get gets getting give gave goes going ' +
    'gone got had has have having her here hers him his how however into its itself just keep kept know known last let like made ' +
    'make many may might more most much must never new next nor not now off once only onto other our out over own said same ' +
    'she should since some still such than that the their them then there these they this those through too under until upon ' +
    'very was way were what when where which while who whom whose why will with within without would you your yours').split(' ')
);

const clean = (w: string) => w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '');

export type Keyword = {word: string; frame: number};

// Picks up to ~1 keyword per 1.2 s: long, uncommon words, numbers and capitalised names first; the words the
// script marked with "emphasis" always win. Spread out so two never fight for the same moment.
export const pickKeywords = (words: Word[], text: string, fps: number, total: number): Keyword[] => {
  type Cand = {word: string; frame: number; score: number};
  let cands: Cand[] = [];
  if (words.length) {
    cands = words.map((w, i) => ({word: clean(w.word), frame: w.startFrame, score: w.emphasis ? 100 : 0, i, raw: w.word}) as any);
  } else {
    const toks = text.split(/\s+/).filter(Boolean);
    const span = Math.max(1, total * 0.85);
    cands = toks.map((t, i) => ({word: clean(t), frame: Math.round((i / Math.max(1, toks.length)) * span), score: 0, i, raw: t}) as any);
  }
  cands = cands
    .map((c: any) => {
      const w: string = c.word;
      const low = w.toLowerCase();
      if (w.length < 4 && !/\d/.test(w)) return {...c, score: c.score >= 100 ? c.score : -1};
      if (STOP.has(low) && c.score < 100) return {...c, score: -1};
      let s = c.score + w.length * 2;
      if (/\d/.test(w)) s += 12;
      if (c.i > 0 && /^[A-Z]/.test(c.raw)) s += 6; // names (not just sentence starts)
      if (/[!?]$/.test(c.raw)) s += 3;
      return {...c, score: s};
    })
    .filter((c: any) => c.score >= 0);

  const minGap = Math.max(Math.round(fps * 1.0), 12);
  const maxCount = Math.max(1, Math.min(8, Math.floor(total / (fps * 1.2))));
  const chosen: Cand[] = [];
  for (const c of [...cands].sort((a, b) => b.score - a.score)) {
    if (chosen.length >= maxCount) break;
    if (chosen.every((o) => Math.abs(o.frame - c.frame) >= minGap)) chosen.push(c);
  }
  return chosen.sort((a, b) => a.frame - b.frame).map((c) => ({word: c.word, frame: c.frame}));
};

export const Keywords: React.FC<SceneProps<{text?: string; reason?: string}>> = ({
  durationInFrames,
  fps,
  props,
  theme,
  words,
  layout,
}) => {
  const frame = useCurrentFrame();
  const p = theme.palette;
  const picks = pickKeywords(words, props?.text ?? '', fps, durationInFrames);
  const L = layout;

  // which keyword is on screen now
  let cur = -1;
  for (let i = 0; i < picks.length; i++) if (picks[i].frame <= frame) cur = i;
  const kw = cur >= 0 ? picks[cur] : null;
  const nextFrame = cur + 1 < picks.length ? picks[cur + 1].frame : durationInFrames;
  const holdEnd = kw ? Math.min(nextFrame, kw.frame + Math.round(fps * 2.2)) : 0;

  const orb = (i: number, color: string, size: number, speed: number) => (
    <div
      key={i}
      style={{
        position: 'absolute',
        left: `${[22, 70, 48][i] + wobble(frame, 220 / speed, 6, i * 40)}%`,
        top: `${[30, 62, 80][i] + wobble(frame, 180 / speed, 5, i * 70)}%`,
        width: size,
        height: size,
        marginLeft: -size / 2,
        marginTop: -size / 2,
        borderRadius: '50%',
        background: `radial-gradient(circle, ${withAlpha(color, 0.3)} 0%, ${withAlpha(color, 0)} 68%)`,
      }}
    />
  );

  const big = (L.portrait ? 150 : 190) * L.u;
  let kwNode: React.ReactNode = null;
  if (kw) {
    const t = frame - kw.frame;
    const pop = spring({frame: t, fps, config: springs.snappy});
    const out = interpolate(frame, [holdEnd - 6, holdEnd], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    const size = big * Math.min(1, 10 / Math.max(4, kw.word.length));
    const bar = progress(t, 4, 20, ease.out);
    kwNode = (
      <div style={{textAlign: 'center', opacity: Math.min(1, pop * 1.5) * out, transform: `scale(${0.82 + pop * 0.18}) translateY(${(1 - pop) * 36}px)`}}>
        <div
          style={{
            fontFamily: theme.fonts.heading,
            fontSize: size,
            fontWeight: 900,
            lineHeight: 1,
            letterSpacing: '0.02em',
            textTransform: 'uppercase',
            color: p.fg,
            textShadow: `0 ${6 * L.u}px ${40 * L.u}px ${withAlpha(p.accent, 0.35)}`,
          }}
        >
          {kw.word}
        </div>
        <div style={{height: 10 * L.u, width: `${bar * 60}%`, margin: `${26 * L.u}px auto 0`, background: p.accent, borderRadius: 10 * L.u}} />
      </div>
    );
  }

  return (
    <SceneFrame
      theme={theme}
      layout={layout}
      backdrop={
        <>
          {orb(0, p.accent, L.width * 0.7, 1)}
          {orb(1, p.accent2, L.width * 0.6, 0.8)}
          {orb(2, p.accent, L.width * 0.45, 1.2)}
        </>
      }
    >
      {kwNode}
    </SceneFrame>
  );
};

export const cost = 'low';
export default Keywords;
