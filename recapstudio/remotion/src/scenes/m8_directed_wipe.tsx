import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {Camera, KineticText, LayeredMedia, MaskWipe, SceneProps, Theme, Word, ease, progress, withAlpha} from '@kit';

// M8 BEAT 3 - the directed shot, revealed by an ANGLED MASK WIPE.
//
//   transition  the whole shot is unmasked by <MaskWipe direction="left" angle={18}>: a real 18 deg
//               leading edge sweeps across the frame over ~20 frames, so the beat arrives THROUGH the
//               wipe instead of cutting in. `box` is the frame itself, which is what makes the edge
//               exactly 18 degrees rather than 18 percent of the axis (kit/kinetic.tsx).
//   footage     NASA Perseverance footage by HANDLE ("footage_a"), read from 3 s in - a different
//               part of the sky from beat 1, so the two footage beats are not the same plate.
//   camera      push 1.03 -> 1.13 and a 14 px rise: this is the beat that carries the story, so it
//               is the one allowed a real move.
//   type        <KineticText> headline plus a <MaskWipe> sub, above the caption band.
//
// The kicker arrives on a SECOND angled wipe just as the first edge clears: two edges travelling at
// different depths is what makes a wipe read as a designed transition rather than a glitch.

type Props = {kicker?: string; headline?: string; sub?: string};

export const cost: 'low' | 'medium' | 'high' = 'medium';   // video decode + two large transforms

const FPS = 24;
const META_SECONDS = 12;
const MOVE_SECONDS = 6.5;
const WIPE_SECONDS = 0.85;    // fast enough to be a transition, slow enough to see the edge move

const KICKER = 'Sol 738';
const HEADLINE = 'Reads the stone.\nWrites the dawn.';
const SUB = 'Every morning, another world is documented by a robot very far from home.';
const NARRATION = 'It reads the stone, and writes the dawn of another world.';

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
      background: `linear-gradient(200deg, ${theme.palette.bg2} 0%, ${theme.palette.bg} 58%, ${withAlpha(theme.palette.accent, 0.2)} 100%)`,
    }}
  />
);

const DirectedWipe: React.FC<SceneProps<Props>> = ({props, theme, layout, durationInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = theme.palette;
  const u = layout.u;
  const kicker = props.kicker ?? KICKER;
  const headline = props.headline ?? HEADLINE;
  const sub = props.sub ?? SUB;
  const left = layout.safeSide + 80 * u;      // +80u: the 1.16 push must not crop the headline (f370)
  const base = Math.round(layout.captionBottom + 150 * u);
  const move = Math.min(durationInFrames, Math.round(fps * MOVE_SECONDS));
  const wipe = Math.max(8, Math.round(fps * WIPE_SECONDS));
  const bed = progress(frame, 0, 16);
  const kickerBox = {width: 430 * u, height: 40 * u};

  return (
    <AbsoluteFill style={{backgroundColor: '#05060a'}}>
      <MaskWipe direction="left" angle={18} start={0} duration={wipe} from={0.14}
                box={{width: layout.width, height: layout.height}}
                style={{position: 'absolute', left: 0, top: 0, width: '100%', height: '100%'}}>
        <Camera push={[1.03, 1.16]} panY={[0, -20]} shake={0.26} curve={ease.inOut} duration={move}>
          {/* the same grade as beat 1 (see m8_layered_push.tsx): the pre-dawn plate needs exposure and
              colour before it can carry a shot - ungraded it measures flat, desaturated and still. */}
          <div style={{position: 'absolute', left: 0, top: 0, width: '100%', height: '100%',
                       filter: 'brightness(1.55) contrast(1.24) saturate(1.75)'}}>
          <LayeredMedia
            asset="footage_a"
            scrim={0.24}
            tint={p.accent}
            tintStrength={0.1}
            vignette={0.34}
            zoom={1.05}
            startFrom={84}
            fallback={drawnBackdrop(theme)}
          >
            <AbsoluteFill
              style={{
                background: `linear-gradient(90deg, ${withAlpha('#000000', 0.78)} 0%, ${withAlpha('#000000', 0.4)} 46%, ${withAlpha('#000000', 0)} 76%)`,
                opacity: bed,
              }}
            />
            <AbsoluteFill
              style={{
                background: `linear-gradient(0deg, ${withAlpha('#000000', 0.62)} 0%, ${withAlpha('#000000', 0)} 42%)`,
                opacity: bed,
              }}
            />
            <div style={{position: 'absolute', left, bottom: base, width: Math.round(layout.width * 0.56)}}>
              <MaskWipe direction="left" angle={18} start={wipe - 6} duration={14} box={kickerBox}
                        style={{width: kickerBox.width}}>
                <div style={{display: 'flex', alignItems: 'center', gap: 18 * u}}>
                  <div style={{width: 82 * u, height: 4 * u, background: p.accent}} />
                  <div
                    style={{
                      fontFamily: theme.fonts.body,
                      fontSize: 25 * u,
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
              <div style={{height: 20 * u}} />
              <KineticText
                text={headline}
                start={wipe + 2}
                step={6}
                size={92 * u}
                color={p.fg}
                font={theme.fonts.heading}
                weight={900}
                lineHeight={1.06}
                rise={78}
                skew={8}
                blur={11}
                scaleFrom={1.16}
                emphasis={['dawn']}
                emphasisColor={p.accent}
                letterSpacing="-0.02em"
              />
              <div style={{height: 22 * u}} />
              <MaskWipe direction="up" angle={12} start={wipe + 20} duration={14}
                        box={{width: 760 * u, height: 46 * u}} style={{width: 760 * u}}>
                <div
                  style={{
                    fontFamily: theme.fonts.body,
                    fontSize: 26 * u,
                    lineHeight: 1.26,
                    color: withAlpha(p.fg, 0.9),
                  }}
                >
                  {sub}
                </div>
              </MaskWipe>
            </div>
          </LayeredMedia>
          </div>
        </Camera>
      </MaskWipe>
    </AbsoluteFill>
  );
};

// Render entry: composition "bench-m8-directed-wipe" (src/SceneLab.tsx).
export const directedWipeEntry = {
  component: DirectedWipe,
  meta: {
    id: 'm8_directed_wipe',
    title: 'M8 beat 3 - directed shot, angled mask wipe',
    cost,
    durationInFrames: META_SECONDS * FPS,
    fps: FPS,
    width: 1920,
    height: 1080,
    props: {kicker: KICKER, headline: HEADLINE, sub: SUB},
    words: spread(NARRATION, META_SECONDS * FPS),
    text: NARRATION,
    status: 'example',
  },
};

export default DirectedWipe;
