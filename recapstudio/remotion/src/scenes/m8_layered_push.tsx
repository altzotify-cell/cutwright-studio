import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {Camera, KineticText, LayeredMedia, MaskWipe, SceneProps, Theme, Word, ease, progress, withAlpha} from '@kit';

// M8 BEAT 1 - "awake before the sun": layered footage under a SUBTLE camera push.
//
//   footage  real NASA Perseverance footage by HANDLE ("footage_a"; the step declares it), read from
//            the top of the clip: this beat is the wide, quiet opening of the story.
//   camera   <Camera> push 1.02 -> 1.08 with an 8 px rise. The push is deliberately small - the
//            point of this beat is that a slow move on real footage never reads as a slide, and a
//            big Ken Burns would read as a zoom effect. The move finishes inside MOVE_SECONDS, so a
//            short beat is not left mid-move.
//   light    <LayeredMedia> scrim + accent tint + vignette, then a left-to-right graded bed so the
//            type sits on its own dark plane instead of on the sky.
//   type     <KineticText> headline (one accented word), a <MaskWipe> kicker and a <MaskWipe> sub.
//
// Text sits above the CAPTION BAND (layout.captionBottom), not merely above safeBottom: the spoken
// captions are drawn by the timeline under the picture and must never collide with the shot's copy.

type Props = {kicker?: string; headline?: string; sub?: string};

export const cost: 'low' | 'medium' | 'high' = 'medium';   // video decode + one large transform
const FPS = 24;
const META_SECONDS = 12;      // the composition may be rendered up to 12 s; the beat picks its length
const MOVE_SECONDS = 6.5;     // the push completes inside this, so a 4 s beat still moves throughout

const KICKER = 'Jezero Crater';
const HEADLINE = 'Awake before\nthe sun';
const SUB = 'Sol 738 begins in the dark, with the ridge still black against the sky.';
const NARRATION = 'Before the sun clears the ridge line, the rover is already awake and listening.';

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
      background: `linear-gradient(180deg, ${theme.palette.bg2} 0%, ${theme.palette.bg} 62%, ${withAlpha(theme.palette.accent, 0.12)} 100%)`,
    }}
  />
);

const LayeredPush: React.FC<SceneProps<Props>> = ({props, theme, layout, durationInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = theme.palette;
  const u = layout.u;
  const kicker = props.kicker ?? KICKER;
  const headline = props.headline ?? HEADLINE;
  const sub = props.sub ?? SUB;
  const left = layout.safeSide + 60 * u;               // +60u: the 1.12 push must not eat the margin
  const base = Math.round(layout.captionBottom + 150 * u);
  const move = Math.min(durationInFrames, Math.round(fps * MOVE_SECONDS));
  const bed = progress(frame, 0, 14);
  const sweep = progress(frame, 0, Math.max(1, durationInFrames));   // the light travels the beat
  const rail = Math.round(240 * u * progress(frame, 6, Math.min(durationInFrames, 70)));
  const kickerBox = {width: 460 * u, height: 40 * u};

  return (
    <Camera push={[1.02, 1.12]} panY={[0, -18]} shake={0.22} curve={ease.inOut} duration={move}>
      {/* The grade. The source plate is a pre-dawn Mars sky: mean luma ~10/255, almost monochrome.
          Rendered raw it measures as "flat, desaturated, nothing moves" - Kinocut's own release gate
          said exactly that (score 53.7/100, std dev 19.8, saturation 2.1 %) and the engine's
          slideshow_risk scored 0.91. Lifting exposure and colour is the fix a colourist would make
          first, and it is what makes the slow push measurable: at this level the motion shows.
          contrast/saturate/brightness are cheap CSS filters; the expensive ones (blur) stay unused. */}
      <div style={{position: 'absolute', left: 0, top: 0, width: '100%', height: '100%',
                   filter: 'brightness(1.5) contrast(1.22) saturate(1.7)'}}>
      <LayeredMedia
        asset="footage_a"
        scrim={0.2}
        tint={p.accent}
        tintStrength={0.09}
        vignette={0.3}
        zoom={1.02}
        startFrom={4}
        fallback={drawnBackdrop(theme)}
      >
        <AbsoluteFill
          style={{
            background: `linear-gradient(90deg, ${withAlpha('#000000', 0.74)} 0%, ${withAlpha('#000000', 0.36)} 44%, ${withAlpha('#000000', 0)} 72%)`,
            opacity: bed,
          }}
        />
        <AbsoluteFill
          style={{
            background: `linear-gradient(0deg, ${withAlpha('#000000', 0.6)} 0%, ${withAlpha('#000000', 0)} 40%)`,
            opacity: bed,
          }}
        />
        {/* the sweep: a soft band of light that crosses the frame once. It is what makes a slow
            push on a dark sky read as a moving shot instead of a still photograph. */}
        <AbsoluteFill
          style={{
            background: `linear-gradient(${74 + sweep * 18}deg, ${withAlpha(p.accent, 0)} 0%, ${withAlpha(p.accent, 0.16)} ${28 + sweep * 44}%, ${withAlpha(p.accent, 0)} ${62 + sweep * 30}%)`,
            opacity: bed,
          }}
        />
        <div style={{position: 'absolute', left, bottom: base, width: Math.round(layout.width * 0.54)}}>
          <MaskWipe direction="left" angle={15} start={2} duration={16} box={kickerBox}
                    style={{width: kickerBox.width}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 18 * u}}>
              <div style={{width: 76 * u, height: 4 * u, background: p.accent}} />
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
            start={10}
            step={6}
            size={100 * u}
            color={p.fg}
            font={theme.fonts.heading}
            weight={900}
            lineHeight={1.02}
            rise={70}
            skew={7}
            blur={9}
            scaleFrom={1.12}
            emphasis={['sun']}
            emphasisColor={p.accent}
            letterSpacing="-0.015em"
          />
          <div style={{height: 20 * u}} />
          <MaskWipe direction="up" angle={10} start={26} duration={14}
                    box={{width: 700 * u, height: 46 * u}} style={{width: 700 * u}}>
            <div
              style={{
                fontFamily: theme.fonts.body,
                fontSize: 26 * u,
                lineHeight: 1.28,
                color: withAlpha(p.fg, 0.9),
              }}
            >
              {sub}
            </div>
          </MaskWipe>
          {/* the rail: a third, moving plane - a line that finishes after the type has landed */}
          <div style={{height: 22 * u}} />
          <div style={{width: rail, height: 3 * u, background: withAlpha(p.accent, 0.85)}} />
        </div>
      </LayeredMedia>
      </div>
    </Camera>
  );
};

// Render entry: composition "bench-m8-layered-push" (src/SceneLab.tsx).
export const layeredPushEntry = {
  component: LayeredPush,
  meta: {
    id: 'm8_layered_push',
    title: 'M8 beat 1 - layered footage, subtle push',
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

export default LayeredPush;
