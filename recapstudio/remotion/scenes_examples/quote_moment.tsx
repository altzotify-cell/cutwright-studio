import React from 'react';
import {useCurrentFrame} from 'remotion';
import {Particles, RevealText, SceneFrame, SceneProps, contentBox, ease, progress, useEntrance, withAlpha} from '@kit';

// REFERENCE SCENE 3: "quote_moment"  (a quote appears word by word, key words in the accent colour)
// Shows: RevealText with stagger, useEntrance (spring hook), ambient Particles, progress() for a fade-in line.
// Data:  {"quote": "Every man dies. Not every man really lives.", "author": "Braveheart", "highlight": ["lives"]}

type Props = {quote?: string; author?: string; highlight?: string[]};

export const cost = 'low';

const QuoteMoment: React.FC<SceneProps<Props>> = ({durationInFrames, props, theme, layout}) => {
  const frame = useCurrentFrame();
  const p = theme.palette;
  const quote = props.quote ?? 'The best stories are the ones that refuse to stay quiet.';
  const author = props.author ?? '';
  const box = contentBox(layout);
  const u = layout.u;

  const count = quote.split(/\s+/).filter(Boolean).length;
  // all words in about 60 % of the scene, but never slower than 7 frames per word or faster than 2
  const step = Math.max(2, Math.min(7, Math.floor((durationInFrames * 0.6) / Math.max(1, count))));
  const lastWordAt = 8 + step * count;
  const mark = useEntrance(0, 'bouncy');
  const authorIn = progress(frame, lastWordAt, lastWordAt + 16);

  const size = Math.min(76 * u, (box.width / Math.max(8, Math.sqrt(quote.length) * 1.6)) * 1.15) * (layout.portrait ? 1.15 : 1);

  return (
    <SceneFrame theme={theme} layout={layout} backdrop={<Particles mode="ambient" count={16} color={p.accent2} size={8 * u} opacity={0.55} seed="quote" />}>
      <div style={{maxWidth: box.width * (layout.portrait ? 1 : 0.86), textAlign: 'center'}}>
        <div
          style={{
            fontFamily: theme.fonts.heading,
            fontSize: 200 * u,
            lineHeight: 0.7,
            height: 110 * u,
            color: p.accent,
            opacity: 0.9,
            transform: `scale(${0.6 + mark * 0.4})`,
            transformOrigin: 'center bottom',
          }}
        >
          {'\u201C'}
        </div>
        <RevealText
          text={quote}
          start={8}
          step={step}
          size={size}
          color={p.fg}
          highlight={props.highlight ?? []}
          highlightColor={p.accent}
          font={theme.fonts.heading}
          weight={800}
          lineHeight={1.18}
          rise={22 * u}
        />
        {author ? (
          <div
            style={{
              marginTop: 40 * u,
              opacity: authorIn,
              transform: `translateY(${(1 - ease.out(authorIn)) * 16}px)`,
              fontFamily: theme.fonts.body,
              fontSize: 32 * u,
              fontWeight: 700,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: p.muted,
            }}
          >
            <span style={{display: 'inline-block', width: 56 * u, height: 3 * u, background: withAlpha(p.accent, 0.8), verticalAlign: 'middle', marginRight: 18 * u}} />
            {author}
          </div>
        ) : null}
      </div>
    </SceneFrame>
  );
};

export default QuoteMoment;
