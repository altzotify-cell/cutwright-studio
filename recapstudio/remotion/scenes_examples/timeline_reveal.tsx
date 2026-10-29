import React from 'react';
import {spring, useCurrentFrame} from 'remotion';
import {DrawPath, SceneFrame, SceneProps, contentBox, springs, wordStart, withAlpha} from '@kit';

// REFERENCE SCENE 2: "timeline_reveal"  (a line draws across, one event pops up per marker)
// Shows: DrawPath, spring(), narration sync per event, and a different layout for 16:9 (horizontal) and 9:16 (vertical).
// Data:  {"events": [{"when": "1999", "label": "The film is released", "word": "released"}, ...]}
// "word" is optional: when the narrator says it, that event appears. Without it events are spread evenly.

type Event = {when?: string; label: string; word?: string};
type Props = {events?: Event[]};

export const cost = 'low';

const SAMPLE: Event[] = [
  {when: '1999', label: 'The film premieres'},
  {when: '2003', label: 'The sequel flops'},
  {when: '2010', label: 'A cult following grows'},
  {when: '2021', label: 'The remake is announced'},
];

const TimelineReveal: React.FC<SceneProps<Props>> = ({durationInFrames, fps, props, theme, words, layout}) => {
  const frame = useCurrentFrame();
  const p = theme.palette;
  const events = (props.events && props.events.length ? props.events : SAMPLE).slice(0, 6);
  const n = events.length;
  const box = contentBox(layout);
  const W = box.width;
  const H = box.height;
  const portrait = layout.portrait;
  const u = layout.u;

  // appear frames: the spoken word if there is one, otherwise evenly over the first 70 % of the scene
  const evenGap = Math.max(10, Math.round((durationInFrames * 0.7 - 20) / n));
  const appear = events.map((e, i) => (e.word ? wordStart(words, e.word, 20 + i * evenGap) : 20 + i * evenGap));

  const pos = (i: number) => (portrait ? {x: W * 0.16, y: H * ((i + 0.5) / n)} : {x: W * ((i + 0.5) / n), y: H / 2});
  const lineD = portrait ? `M ${W * 0.16} 0 L ${W * 0.16} ${H}` : `M 0 ${H / 2} L ${W} ${H / 2}`;

  return (
    <SceneFrame theme={theme} layout={layout}>
      <div style={{position: 'relative', width: W, height: H}}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
          <DrawPath d={lineD} frame={frame} start={0} duration={Math.min(60, durationInFrames * 0.5)} stroke={withAlpha(p.fg, 0.28)} strokeWidth={6 * u} />
          {events.map((_, i) => {
            const k = spring({frame: frame - appear[i], fps, config: springs.bouncy});
            const c = pos(i);
            return (
              <g key={i}>
                <circle cx={c.x} cy={c.y} r={26 * u * k} fill={withAlpha(p.accent, 0.25)} />
                <circle cx={c.x} cy={c.y} r={13 * u * k} fill={p.accent} />
              </g>
            );
          })}
        </svg>
        {events.map((e, i) => {
          const k = spring({frame: frame - appear[i] - 3, fps, config: springs.smooth});
          const c = pos(i);
          const above = i % 2 === 0;
          const boxW = portrait ? W * 0.7 : Math.min(W / n - 20 * u, 380 * u);
          const style: React.CSSProperties = portrait
            ? {left: c.x + 44 * u, top: c.y, width: boxW, transform: `translateY(-50%) translateX(${(1 - k) * 30}px)`, textAlign: 'left'}
            : {
                left: c.x,
                width: boxW,
                marginLeft: -boxW / 2,
                textAlign: 'center',
                ...(above ? {bottom: H / 2 + 46 * u} : {top: H / 2 + 46 * u}),
                transform: `translateY(${(above ? 1 : -1) * (1 - k) * 30}px)`,
              };
          return (
            <div key={i} style={{position: 'absolute', opacity: Math.min(1, k * 1.5), ...style}}>
              {e.when ? (
                <div style={{fontFamily: theme.fonts.heading, fontWeight: 900, fontSize: 46 * u, color: p.accent, lineHeight: 1.05}}>{e.when}</div>
              ) : null}
              <div style={{fontFamily: theme.fonts.body, fontWeight: 700, fontSize: 30 * u, color: p.fg, lineHeight: 1.2, marginTop: 6 * u}}>{e.label}</div>
            </div>
          );
        })}
      </div>
    </SceneFrame>
  );
};

export default TimelineReveal;
