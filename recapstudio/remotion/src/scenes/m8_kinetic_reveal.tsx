import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Camera, KineticText, MaskWipe, Particles, SceneProps, Theme, Word, progress, withAlpha} from '@kit';

// M8 BEAT 2 - the kinetic typography reveal: no footage, all type, the hardest beat to make look
// expensive and the easiest to make look like a PowerPoint slide.
//
// What keeps it from being a slide:
//   * three LINES arrive as separate units (mode 'lines'), each punching in from 1.18x, skewed 9 deg
//     and motion-blurred, on a snap spring - the eye reads travel, not a fade;
//   * one word carries the accent colour, so the line has a focal point;
//   * a hard-edged <MaskWipe> accent band sweeps out behind the second line, and the background
//     gradient itself is alive (a slow diagonal drift, 0 -> 1 over the beat), so no frame is static;
//   * a low plane of deterministic particles (seeded, never Math.random) gives depth.
//
// The block is anchored above the CAPTION BAND so the spoken captions never sit on the type.

type Props = {kicker?: string; lines?: string; sub?: string};

export const cost: 'low' | 'medium' | 'high' = 'medium';   // particles + gradients, no filters

const FPS = 24;
const META_SECONDS = 12;
const KICKER = 'No waiting';
const LINES = 'It makes\nits own\ndaylight';
const SUB = 'Perseverance does not wait for the sunrise.';
const NARRATION = 'Perseverance does not wait for daylight. It makes its own.';

const spread = (text: string, durationInFrames: number): Word[] => {
  const tokens = text.split(/\s+/).filter(Boolean);
  const span = durationInFrames * 0.85;
  return tokens.map((word, index) => ({
    word,
    startFrame: Math.round((index / tokens.length) * span),
    endFrame: Math.round(((index + 0.85) / tokens.length) * span),
  }));
};

const KineticReveal: React.FC<SceneProps<Props>> = ({props, theme, layout, durationInFrames}) => {
  const frame = useCurrentFrame();
  const p = theme.palette;
  const u = layout.u;
  const kicker = props.kicker ?? KICKER;
  const lines = props.lines ?? LINES;
  const sub = props.sub ?? SUB;
  const drift = progress(frame, 0, Math.max(1, durationInFrames));    // never a still frame
  const base = Math.round(layout.captionBottom + 190 * u);
  const bandWidth = Math.round(layout.width * 0.62);

  return (
    <AbsoluteFill style={{background: p.bg}}>
      {/* a 4 % push across the beat: the typography beat gets the same "always moving" treatment as
          the footage beats, so its middle is not a frozen frame (measured: slideshow_risk, M8). */}
      <Camera push={[1.0, 1.04]} duration={durationInFrames}>
      {/* the bed: two gradients that slide against each other for the length of the beat */}
      <AbsoluteFill
        style={{
          background: `linear-gradient(${150 + drift * 24}deg, ${p.bg2} 0%, ${p.bg} 58%, ${withAlpha(p.accent, 0.18)} 100%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at ${18 + drift * 22}% 26%, ${withAlpha(p.accent, 0.14)} 0%, ${withAlpha(p.accent, 0)} 58%)`,
        }}
      />
      <Particles count={60} seed="m8-reveal" color={p.accent} mode="rise" start={0}
                 duration={Math.min(durationInFrames, FPS * 6)} size={3.2 * u}
                 opacity={0.5} spread={layout.width * 0.9} />
      {/* the right-hand rule: a plane that keeps travelling while the type holds, so the middle of
          the beat is never a frozen frame */}
      <div style={{position: 'absolute', right: layout.safeSide,
                   top: layout.safeTop + 40 * u, width: 3 * u,
                   height: Math.round(layout.height * 0.42 * drift),
                   background: withAlpha(p.accent, 0.75)}} />
      <div style={{position: 'absolute', left: layout.safeSide + 24 * u, top: layout.safeTop}}>
        <MaskWipe direction="left" angle={18} start={1} duration={13}
                  box={{width: 420 * u, height: 40 * u}} style={{width: 420 * u}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 16 * u}}>
            <div style={{width: 64 * u, height: 4 * u, background: p.accent}} />
            <div
              style={{
                fontFamily: theme.fonts.body,
                fontSize: 24 * u,
                letterSpacing: '0.32em',
                textTransform: 'uppercase',
                color: p.accent,
                whiteSpace: 'pre',
              }}
            >
              {kicker}
            </div>
          </div>
        </MaskWipe>
      </div>
      <div style={{position: 'absolute', left: layout.safeSide + 24 * u, bottom: base}}>
        {/* the accent band arrives BEHIND the type - a plane, not a card */}
        <div style={{position: 'absolute', left: -18 * u, bottom: 26 * u, width: bandWidth,
                     height: 118 * u, overflow: 'hidden'}}>
          <MaskWipe direction="left" angle={12} start={8} duration={18}
                    box={{width: bandWidth, height: 118 * u}}>
            <AbsoluteFill style={{background: withAlpha(p.accent, 0.22)}} />
          </MaskWipe>
        </div>
        <KineticText
          text={lines}
          start={4}
          step={5}
          size={132 * u}
          color={p.fg}
          font={theme.fonts.heading}
          weight={900}
          lineHeight={0.94}
          rise={92}
          skew={9}
          blur={12}
          scaleFrom={1.18}
          emphasis={['daylight']}
          emphasisColor={p.accent}
          letterSpacing="-0.03em"
        />
        <div style={{height: 26 * u}} />
        <MaskWipe direction="up" angle={10} start={30} duration={14}
                  box={{width: 780 * u, height: 44 * u}} style={{width: 780 * u}}>
          <div
            style={{
              fontFamily: theme.fonts.body,
              fontSize: 27 * u,
              lineHeight: 1.25,
              color: withAlpha(p.fg, 0.88),
            }}
          >
            {sub}
          </div>
        </MaskWipe>
      </div>
      </Camera>
    </AbsoluteFill>
  );
};

// Render entry: composition "bench-m8-kinetic-reveal" (src/SceneLab.tsx).
export const kineticRevealEntry = {
  component: KineticReveal,
  meta: {
    id: 'm8_kinetic_reveal',
    title: 'M8 beat 2 - kinetic typography reveal',
    cost,
    durationInFrames: META_SECONDS * FPS,
    fps: FPS,
    width: 1920,
    height: 1080,
    props: {kicker: KICKER, lines: LINES, sub: SUB},
    words: spread(NARRATION, META_SECONDS * FPS),
    text: NARRATION,
    status: 'example',
  },
};

export default KineticReveal;
