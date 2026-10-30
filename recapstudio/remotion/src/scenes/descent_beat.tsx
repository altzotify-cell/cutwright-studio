import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Camera, KineticText, LayeredMedia, MaskWipe, SceneProps, Theme, Word, ease, progress, withAlpha} from '@kit';

// M7 beat: ENTRY - the seven minutes the rover falls through the Martian sky with no signal home.
//
//   footage  real NASA Perseverance footage by HANDLE ("footage_a", the step declares it) - the same
//            public-domain pre-sunrise clip M5.5C used, read from 3 s in so this beat is a different
//            part of the sky than directed_shot.
//   camera   <Camera> push 1.04 -> 1.16 and a 22 px downward drift: the frame falls with the rover,
//            and because it is a transform, the type falls too.
//   light    <LayeredMedia> scrim + a left-to-right shade so the type never sits on bare sky.
//   type     <KineticText> headline ("seven minutes of silence", one accented word) + <MaskWipe>
//            kicker and sub.
//   data     a right-hand instrument rail (three ticks) revealed by three <MaskWipe> sweeps - the
//            beat's second plane: numbers arriving while the camera drifts.
//
// The stills at frames 0 / 48 / 144 are the critic's material (LOG 2026-10-30, M7). Pass 1 carried
// two planted flaws (sub line inside the caption band, rail labels under the legibility floor) and
// the critic found two more it was not told about: the 1.16 camera push cropped the headline at the
// left edge on f144, and f000 opened on bare sky. Pass 2 fixed those four but the camera drift then
// sank the sub into the caption band at f144 (measured, 135 px from the bottom edge) - pass 3 is what
// this file is now: two revisions, the loop's maximum.

type Props = {kicker?: string; headline?: string; sub?: string; ticks?: string[]};

export const cost: 'low' | 'medium' | 'high' = 'medium';   // video decode + two large transforms
const FPS = 24;
const SECONDS = 8;

const KICKER = 'Entry interface';
const HEADLINE = 'Seven minutes\nof silence';
const SUB = 'It falls faster than its signal can reach us.';
const TICKS = ['20,000 km/h', '1,300 \u00b0C', '7 min'];
const NARRATION = 'Seven minutes of silence. It falls faster than its own signal can reach us.';

// Narration stand-in for the Studio preview (a scene may import only the kit, so this is local).
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
      background: `linear-gradient(170deg, ${theme.palette.bg2} 0%, ${theme.palette.bg} 64%, ${withAlpha(theme.palette.accent, 0.14)} 100%)`,
    }}
  />
);

const TICK_LABELS = ['peak speed', 'peak heat', 'to the ground'];

const DescentBeat: React.FC<SceneProps<Props>> = ({props, theme, layout, durationInFrames}) => {
  const frame = useCurrentFrame();
  const p = theme.palette;
  const u = layout.u;
  const kicker = props.kicker ?? KICKER;
  const headline = props.headline ?? HEADLINE;
  const sub = props.sub ?? SUB;
  const ticks = props.ticks ?? TICKS;
  const left = layout.safeSide + 40 * u;   // +40u: the 1.10 push must not eat the margin (f144)
  // Pass 3 (critic defect: the camera drift sank the sub into the caption band - measured 135 px
  // from the bottom edge at f144, captions reach ~157 px up). The block now starts higher and the
  // camera RISES while it pushes, so the worst frame clears the band by ~45 px.
  const base = Math.round(layout.captionBottom + 124 * u);
  const railLeft = Math.round(layout.width - layout.safeSide - 300 * u);
  const bed = progress(frame, 0, 12);
  const kickerBox = {width: 470 * u, height: 40 * u};

  return (
    <Camera push={[1.04, 1.1]} panY={[0, -14]} shake={0.25} curve={ease.inOut}
            duration={durationInFrames}>
      <LayeredMedia
        asset="footage_a"
        scrim={0.34}
        tint={p.accent}
        tintStrength={0.04}
        vignette={0.42}
        zoom={1.03}
        startFrom={72}
        fallback={drawnBackdrop(theme)}
      >
        <AbsoluteFill
          style={{
            background: `linear-gradient(90deg, ${withAlpha('#000000', 0.72)} 0%, ${withAlpha('#000000', 0.34)} 46%, ${withAlpha('#000000', 0)} 74%)`,
            opacity: bed,
          }}
        />
        {/* Pass 2 (critic defect 2): the rail needed a plane of its own. A right-edge shade gives the
            labels something dark to sit on without turning the data into cards. */}
        <AbsoluteFill
          style={{
            background: `linear-gradient(270deg, ${withAlpha('#000000', 0.66)} 0%, ${withAlpha('#000000', 0.3)} 20%, ${withAlpha('#000000', 0)} 42%)`,
            opacity: bed,
          }}
        />
        <div
          style={{
            position: 'absolute',
            left,
            bottom: base,
            width: Math.round(layout.width * 0.56),
          }}
        >
          <MaskWipe direction="left" angle={16} start={0} from={0.35} duration={16} box={kickerBox}
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
          <div style={{height: 22 * u}} />
          <KineticText
            text={headline}
            start={12}
            step={7}
            size={96 * u}
            color={p.fg}
            font={theme.fonts.heading}
            lineHeight={1.0}
            rise={72}
            skew={7}
            blur={9}
            scaleFrom={1.12}
            emphasis={['silence']}
            emphasisColor={p.accent}
            letterSpacing="-0.015em"
          />
          <div style={{height: 26 * u}} />
          {/* Pass 2 (critic defect 1): the sub lives INSIDE the column, so the block ends above the
              caption band. Pass 1 pinned it to safeBottom (65 px) - it would have collided with the
              burned captions at 97 px. */}
          <div
            style={{
              width: Math.round(layout.width * 0.5),
              fontFamily: theme.fonts.body,
              fontSize: 27 * u,
              lineHeight: 1.25,
              color: withAlpha(p.fg, 0.9),
            }}
          >
            {sub}
          </div>
        </div>

        {/* The instrument rail: three ticks wiped down while the camera drifts.
            Pass 2 (critic defect 2): the labels were 18 px at 60 % over bright sky; they are 24 px at
            85 % now, over the right-edge shade, and the numbers are set heavier. */}
        <div
          style={{
            position: 'absolute',
            left: railLeft,
            top: Math.round(layout.safeTop + 120 * u),
            width: 300 * u,
          }}
        >
          {ticks.map((tick, index) => (
            <MaskWipe
              key={tick}
              direction="down"
              angle={10}
              start={8 + index * 6}
              duration={12}
              box={{width: 300 * u, height: 96 * u}}
            >
              <div style={{paddingBottom: 26 * u}}>
                <div
                  style={{
                    fontFamily: theme.fonts.body,
                    fontSize: 42 * u,
                    fontWeight: 700,
                    letterSpacing: '0.02em',
                    color: p.accent,
                  }}
                >
                  {tick}
                </div>
                <div
                  style={{
                    fontFamily: theme.fonts.body,
                    fontSize: 24 * u,
                    letterSpacing: '0.14em',
                    textTransform: 'uppercase',
                    color: withAlpha(p.fg, 0.85),
                  }}
                >
                  {TICK_LABELS[index] ?? ''}
                </div>
              </div>
            </MaskWipe>
          ))}
        </div>
      </LayeredMedia>
    </Camera>
  );
};

// Preview + render entry: composition "bench-descent-beat" (registered in src/SceneLab.tsx).
export const descentEntry = {
  component: DescentBeat,
  meta: {
    id: 'descent_beat',
    title: 'Descent beat (M7 narrative shot)',
    cost,
    durationInFrames: SECONDS * FPS,
    fps: FPS,
    width: 1920,
    height: 1080,
    props: {kicker: KICKER, headline: HEADLINE, sub: SUB, ticks: TICKS},
    words: spread(NARRATION, SECONDS * FPS),
    text: NARRATION,
    status: 'example',
  },
};

export default DescentBeat;
