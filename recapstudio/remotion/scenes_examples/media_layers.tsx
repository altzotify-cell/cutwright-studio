import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Camera, LayeredMedia, RevealText, SceneProps, Theme, progress, withAlpha} from '@kit';

// REFERENCE SCENE 4 (kit/2, M5.5B): "media_layers"  (real footage under a headline, with a camera move)
// Shows: <LayeredMedia asset="footage_a"> (a HANDLE, never a path), <Camera> push/pan/shake, RevealText
// over a scrim. The step declares the handle:  "assets": {"footage_a": "@asset.footage_a"}.
// `fallback` keeps the Studio preview working when no render staged the footage.
// Data (segments.json "motion.data"):  {"kicker": "1999", "headline": "The film nobody expected"}

type Props = {kicker?: string; headline?: string};

export const cost = 'medium';   // video decode + a large transform: heavier than the drawn examples

const drawnBackdrop = (theme: Theme): React.ReactElement => (
  <AbsoluteFill
    style={{
      background: `linear-gradient(135deg, ${theme.palette.bg2} 0%, ${theme.palette.bg} 60%, ${withAlpha(theme.palette.accent, 0.18)} 100%)`,
    }}
  />
);

const MediaLayers: React.FC<SceneProps<Props>> = ({props, theme, layout, words}) => {
  const frame = useCurrentFrame();
  const p = theme.palette;
  const kicker = props.kicker ?? 'archive';
  const headline = props.headline ?? 'The footage nobody expected';
  const left = layout.safeSide;
  // Distance from the BOTTOM edge, so the block sits just above the caption band (the first cut of this
  // scene used `height - safeBottom`, which parked the headline against the top edge - measured on a
  // still at frame 96 and fixed here).
  const base = Math.round(layout.safeBottom + 40 * layout.u);

  return (
    <Camera push={[1.02, 1.09]} pan={[0, -26]} shake={0.5}>
      <LayeredMedia
        asset="footage_a"
        scrim={0.45}
        tint={p.accent}
        tintStrength={0.06}
        vignette={0.55}
        zoom={1.04}
        fallback={drawnBackdrop(theme)}
      >
        <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'flex-start'}}>
          <div style={{position: 'absolute', left, bottom: base, maxWidth: layout.width - 2 * left}}>
            <div
              style={{
                fontFamily: theme.fonts.body,
                fontSize: 30 * layout.u,
                letterSpacing: '0.18em',
                textTransform: 'uppercase',
                color: p.accent,
                marginBottom: 14 * layout.u,
              }}
            >
              {kicker}
            </div>
            <div
              style={{
                width: 120 * layout.u * progress(frame, 12, 40),
                height: 5 * layout.u,
                background: p.accent,
                marginBottom: 22 * layout.u,
              }}
            />
            <RevealText
              text={headline}
              start={10}
              step={4}
              size={72 * layout.u}
              color={p.fg}
              font={theme.fonts.heading}
              weight={900}
              lineHeight={1.05}
              mode="words"
            />
          </div>
        </AbsoluteFill>
      </LayeredMedia>
    </Camera>
  );
};

export default MediaLayers;
