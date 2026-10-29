import React from 'react';
import {useCurrentFrame} from 'remotion';
import {
  AnimatedCounter,
  Particles,
  RevealText,
  RingChart,
  SceneFrame,
  SceneProps,
  contentBox,
  ease,
  progress,
  wordStart,
  withAlpha,
} from '@kit';

// REFERENCE SCENE 1: "stat_ring"  (a single percentage that fills a ring, counts up and bursts)
// Shows: SceneFrame + contentBox, RingChart, AnimatedCounter, RevealText, Particles, wordStart (narration sync).
// Data (segments.json "motion.data"):  {"value": 70, "label": "players affected", "unit": "%", "syncWord": "seventy"}

type Props = {value?: number; label?: string; unit?: string; syncWord?: string};

export const cost = 'low';

const StatRing: React.FC<SceneProps<Props>> = ({durationInFrames, props, theme, words, layout}) => {
  const frame = useCurrentFrame();
  const p = theme.palette;
  const value = typeof props.value === 'number' ? props.value : 70;
  const label = props.label ?? 'of the audience';
  const unit = props.unit ?? '%';
  const box = contentBox(layout);

  // start when the narrator says the sync word (if the script gave one), otherwise almost at once
  const t0 = props.syncWord ? wordStart(words, props.syncWord, 6) : 6;
  const dur = Math.max(18, Math.min(48, durationInFrames - t0 - 24));
  const done = t0 + dur;

  const size = Math.min(box.width * 0.9, box.height * (layout.portrait ? 0.6 : 0.74));
  const pulse = Math.sin(progress(frame, done, done + 14, ease.out) * Math.PI) * 0.045;
  const glowIn = progress(frame, t0, t0 + 20);

  return (
    <SceneFrame
      theme={theme}
      layout={layout}
      backdrop={
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '44%',
            width: size * 1.9,
            height: size * 1.9,
            marginLeft: -size * 0.95,
            marginTop: -size * 0.95,
            borderRadius: '50%',
            background: `radial-gradient(circle, ${withAlpha(p.accent, 0.22 * glowIn)} 0%, ${withAlpha(p.accent, 0)} 65%)`,
          }}
        />
      }
    >
      <div style={{transform: `scale(${1 + pulse})`}}>
        <RingChart value={value} size={size} start={t0} duration={dur} color={p.accent} trackColor={withAlpha(p.fg, 0.12)}>
          <div style={{fontFamily: theme.fonts.heading, fontWeight: 900, color: p.fg, fontSize: size * 0.27, lineHeight: 1}}>
            <AnimatedCounter to={value} start={t0} duration={dur} />
            <span style={{fontSize: size * 0.15, color: p.accent, marginLeft: size * 0.01}}>{unit}</span>
          </div>
        </RingChart>
      </div>
      <div style={{marginTop: size * 0.07, maxWidth: box.width}}>
        <RevealText
          text={label}
          start={t0 + 10}
          step={5}
          size={size * 0.1}
          color={p.fg}
          font={theme.fonts.heading}
          weight={800}
          uppercase
          letterSpacing="0.04em"
        />
      </div>
      <Particles mode="burst" start={done} count={22} color={p.accent} size={size * 0.03} spread={0.55} originY={0.44} seed="stat" />
    </SceneFrame>
  );
};

export default StatRing;
