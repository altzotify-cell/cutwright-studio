import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Camera, KineticText, LayeredMedia, MaskWipe, SceneProps, Theme, Word, ease, progress, withAlpha} from '@kit';

// BENCHMARK SHOT (M5.5C): one directed shot that uses every primitive the kit gained in M5.5, so the
// visual standard is measured on a real frame instead of argued about in prose.
//
//   footage  recapstudio/Projects/regress/footage/real_sample.mp4 (NASA Perseverance, public domain:
//            Mars before sunrise, ridge silhouette along the bottom). Framed by an FFmpeg crop at
//            asset-prep time - the clip already has the composition, the scene does not fake it with a
//            zoom, so the footage stays sharp.
//   camera   <Camera> push 1.00 -> 1.12 with a small drift, eased in-out: a slow Ken Burns push that
//            never stops. It moves the TEXT too, which is the difference between a shot and a slide.
//   light    <LayeredMedia> scrim + accent tint + vignette, then a LEFT-TO-RIGHT graded bed: the type
//            sits over the pre-dawn glow, so readability is bought with a gradient, not a text shadow.
//   type     <KineticText> staggered, skewed, motion-blurred word entrance + one accented word.
//   edge     <MaskWipe> angled reveal for the kicker and for the sub line.
//
// The stills at frames 0 / 24 / 48 are the critic's material (LOG 2026-10-30, M5.5C).

type Props = {kicker?: string; headline?: string; sub?: string};

export const cost = 'medium' as const;   // video decode + a large transform
const FPS = 24;
const SECONDS = 8;

const KICKER = 'Mars · Sol 738';
const HEADLINE = 'Dawn on\nanother world';
const SUB = 'The first light is older than the sunrise.';
const NARRATION = 'The rover wakes before the sun. Dawn on another world, where the light always arrives first.';

// Narration stand-in for the preview (a scene may only import the kit, so this is not shared code):
// the words spread evenly over 85 % of the shot, like the example scenes' sampleWords().
const spread = (text: string, durationInFrames: number): Word[] => {
  const tokens = text.split(/\s+/).filter(Boolean);
  const span = durationInFrames * 0.85;
  return tokens.map((word, index) => ({
    word,
    startFrame: Math.round((index / tokens.length) * span),
    endFrame: Math.round(((index + 0.85) / tokens.length) * span),
  }));
};

const drawnBackdrop = (theme: Theme): React.ReactElement => (
  <AbsoluteFill
    style={{
      background: `linear-gradient(160deg, ${theme.palette.bg2} 0%, ${theme.palette.bg} 70%, ${withAlpha(theme.palette.accent, 0.16)} 100%)`,
    }}
  />
);

const DirectedShot: React.FC<SceneProps<Props>> = ({props, theme, layout, durationInFrames}) => {
  const frame = useCurrentFrame();
  const p = theme.palette;
  const u = layout.u;
  const kicker = props.kicker ?? KICKER;
  const headline = props.headline ?? HEADLINE;
  const sub = props.sub ?? SUB;
  const left = layout.safeSide;
  // Above the CAPTION BAND, not just above safeBottom (M5.5C: measured on the f048 still - the sub
  // line landed at 95 px from the bottom edge and the spoken captions sit at captionBottom = 97 px,
  // so the two would have collided in the real render). Captions end ~157 px up; the block ends 181.
  const base = Math.round(layout.captionBottom + 84 * u);
  const bed = progress(frame, 0, 10);          // the shade comes up with the shot, not as a fade
  const kickerBox = {width: 520 * u, height: 38 * u};

  return (
    <Camera push={[1.0, 1.12]} pan={[0, -16]} panY={[0, -10]} shake={0.3}
            curve={ease.inOut} duration={durationInFrames}>
      <LayeredMedia
        asset="footage_a"
        scrim={0.42}
        tint={p.accent}
        tintStrength={0.05}
        vignette={0.45}
        zoom={1.04}
        startFrom={6}
        fallback={drawnBackdrop(theme)}
      >
        <AbsoluteFill
          style={{
            background: `linear-gradient(90deg, ${withAlpha('#000000', 0.7)} 0%, ${withAlpha('#000000', 0.4)} 42%, ${withAlpha('#000000', 0)} 72%)`,
            opacity: bed,
          }}
        />
        <AbsoluteFill
          style={{
            background: `linear-gradient(0deg, ${withAlpha('#000000', 0.55)} 0%, ${withAlpha('#000000', 0)} 38%)`,
            opacity: bed,
          }}
        />
        <div style={{position: 'absolute', left, bottom: base, width: Math.round(layout.width * 0.52)}}>
          <MaskWipe direction="left" angle={16} start={3} duration={14} box={kickerBox}
                    style={{width: kickerBox.width}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 18 * u}}>
              <div style={{width: 78 * u, height: 4 * u, background: p.accent}} />
              <div
                style={{
                  fontFamily: theme.fonts.body,
                  fontSize: 25 * u,
                  letterSpacing: '0.3em',
                  textTransform: 'uppercase',
                  color: p.accent,
                  whiteSpace: 'pre',
                }}
              >
                {kicker}
              </div>
            </div>
          </MaskWipe>
          <div style={{height: 24 * u}} />
          <KineticText
            text={headline}
            start={13}
            step={6}
            size={104 * u}
            color={p.fg}
            font={theme.fonts.heading}
            weight={900}
            lineHeight={1.0}
            rise={76}
            skew={8}
            blur={10}
            scaleFrom={1.14}
            emphasis={['another']}
            emphasisColor={p.accent}
            letterSpacing="-0.015em"
          />
          <div style={{height: 22 * u}} />
          <MaskWipe direction="up" angle={12} start={34} duration={14}
                    box={{width: 660 * u, height: 40 * u}} style={{width: 660 * u}}>
            <div
              style={{
                fontFamily: theme.fonts.body,
                fontSize: 27 * u,
                lineHeight: 1.25,
                color: withAlpha(p.fg, 0.9),
              }}
            >
              {sub}
            </div>
          </MaskWipe>
        </div>
      </LayeredMedia>
    </Camera>
  );
};

// Preview + render entry: composition "bench-directed-shot" in Remotion Studio (src/SceneLab.tsx).
// Typed structurally on purpose - a scene file may only import 'remotion', 'react' and '@kit', so it
// cannot name LabEntry; SceneLab checks the shape by assigning it.
export const directedEntry = {
  component: DirectedShot,
  meta: {
    id: 'directed_shot',
    title: 'Directed shot (M5.5C benchmark)',
    cost,
    durationInFrames: SECONDS * FPS,
    fps: FPS,
    width: 1920,
    height: 1080,
    props: {kicker: KICKER, headline: HEADLINE, sub: SUB},
    words: spread(NARRATION, SECONDS * FPS),
    text: NARRATION,
    status: 'example',
  },
};

export default DirectedShot;
