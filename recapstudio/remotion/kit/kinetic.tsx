import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {ease, lerp, progress, springs, SpringName} from './motion';
import {normWord} from './text';

// kit/3 (M5.5C): the last two documentary primitives. Both are pure Remotion - spring math and CSS,
// no UI/animation package, no measuring the DOM (a render is parallel: every frame must be a pure
// function of the frame). They are the two things VISUAL_STANDARD.md asks for that the kit could not
// do yet: type that ENTERS like a title (not a paragraph) and a hard, angled mask edge.
//
//   <KineticText text="Dawn on another world" start={14} step={6} rise={70} skew={7} blur={8} />
//   <MaskWipe direction="left" angle={12} start={2} duration={16} box={{width: 520, height: 40}}>
//     ...anything: a line of text, a bar, a card...
//   </MaskWipe>

type Align = 'left' | 'center' | 'right';

// -------------------------------------------------------------------------------------------
// KineticText: words (or whole lines) spring in one after another.
// -------------------------------------------------------------------------------------------
// Why not RevealText: that one is a caption reader - small rise, no skew, built to follow narration.
// This one is a TITLE: it travels further, starts skewed and blurred (the eye reads that as motion,
// not as a fade), can punch in from 1.12x, and emphasises single words in the accent colour.
export const KineticText: React.FC<{
  text: string;                      // '\n' starts a new line in both modes
  start?: number;                    // frame the first unit lands on
  step?: number;                     // frames between units
  startFrames?: number[];            // exact frame per unit, overrides start/step (sync to narration)
  mode?: 'words' | 'lines';
  size: number;                      // px
  color: string;
  font?: string;
  weight?: number | string;
  align?: Align;
  lineHeight?: number;
  rise?: number;                     // px each unit travels up while appearing
  skew?: number;                     // deg of leaning start (0 = straight); straightens to 0
  blur?: number;                     // px blur at the start (motion smear)
  scaleFrom?: number;                // 1.12 punches in, 0.9 grows, 1 = no scale
  spring?: SpringName;
  emphasis?: string[];               // words (or whole lines) drawn in `emphasisColor`
  emphasisColor?: string;
  uppercase?: boolean;
  letterSpacing?: number | string;
  stroke?: {color: string; width: number};   // outline instead of fill (title cards)
  style?: React.CSSProperties;
}> = ({
  text,
  start = 0,
  step = 5,
  startFrames,
  mode = 'words',
  size,
  color,
  font,
  weight = 900,
  align = 'left',
  lineHeight = 1.02,
  rise = 64,
  skew = 0,
  blur = 0,
  scaleFrom = 1,
  spring: preset = 'snappy',
  emphasis = [],
  emphasisColor,
  uppercase = false,
  letterSpacing,
  stroke,
  style,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const hot = new Set(emphasis.map(normWord));
  const config = springs[preset];

  // One unit = one word (mode 'words') or one line (mode 'lines'). `delay` is decided by the caller
  // loop so a line and its words share the same spring curve.
  const unit = (content: string, delay: number, isHot: boolean, key: string, marginRight: number) => {
    const p = spring({frame: frame - delay, fps, config});
    // p overshoots on 'bouncy'; opacity must not, so it saturates early (1.6x) and then holds.
    const op = Math.max(0, Math.min(1, p * 1.6));
    const travel = (1 - p) * rise;
    const lean = (1 - p) * skew;
    const smear = Math.max(0, (1 - p) * blur);
    const scale = lerp(scaleFrom, 1, p);
    return (
      <span
        key={key}
        style={{
          display: 'inline-block',
          whiteSpace: 'pre',
          opacity: op,
          marginRight: marginRight ? '0.26em' : 0,
          transform: `translateY(${travel.toFixed(2)}px) skewY(${lean.toFixed(2)}deg) scale(${scale.toFixed(3)})`,
          filter: smear > 0.05 ? `blur(${smear.toFixed(2)}px)` : undefined,
          color: isHot && emphasisColor ? emphasisColor : color,
          WebkitTextStroke: stroke ? `${stroke.width}px ${stroke.color}` : undefined,
          WebkitTextFillColor: stroke ? 'transparent' : undefined,
        }}
      >
        {content}
      </span>
    );
  };

  const delayOf = (index: number) => startFrames?.[index] ?? start + step * index;

  const base: React.CSSProperties = {
    fontFamily: font,
    fontWeight: weight as any,
    fontSize: size,
    lineHeight,
    textAlign: align,
    textTransform: uppercase ? 'uppercase' : undefined,
    letterSpacing,
    ...style,
  };

  if (mode === 'lines') {
    const lines = text.split('\n').filter((line) => line.trim().length > 0);
    return (
      <div style={base}>
        {lines.map((line, index) => (
          <div key={index} style={{display: 'block', overflow: 'hidden'}}>
            {unit(line, delayOf(index), hot.has(normWord(line)), String(index), 0)}
          </div>
        ))}
      </div>
    );
  }

  // 'words': stagger across the WHOLE text, so a two-line title still reads as one gesture. A '\n'
  // starts a new line (an explicit break beats hoping the box wraps where you wanted).
  const wordsPerLine = text.split('\n').map((line) => line.split(/\s+/).filter(Boolean));
  let running = 0;
  return (
    <div style={base}>
      {wordsPerLine.map((tokens, line) => {
        const first = running;
        running += tokens.length;
        return (
          <div key={line} style={{display: 'block'}}>
            {tokens.map((token, column) =>
              unit(token, delayOf(first + column), hot.has(normWord(token)), `${line}-${column}`,
                   column < tokens.length - 1 ? 1 : 0)
            )}
          </div>
        );
      })}
    </div>
  );
};

// -------------------------------------------------------------------------------------------
// MaskWipe: a hard-edged, optionally SLANTED clip-path that sweeps across its children.
// -------------------------------------------------------------------------------------------
type Direction = 'left' | 'right' | 'up' | 'down';

const clipped = (open: number, direction: Direction, shear: number): string => {
  // `open` 0 -> the polygon is a zero-area sliver just outside the box (invisible), 1 -> it covers
  // past every edge (fully visible). `shear` is how far the leading edge leans, in % of the axis.
  switch (direction) {
    case 'right': {
      const x = 100 - open * (100 + shear);
      return `polygon(100% 0%, ${(x + shear).toFixed(2)}% 0%, ${x.toFixed(2)}% 100%, 100% 100%)`;
    }
    case 'up': {
      const y = 100 - open * (100 + shear);
      return `polygon(0% 100%, 100% 100%, 100% ${y.toFixed(2)}%, 0% ${(y + shear).toFixed(2)}%)`;
    }
    case 'down': {
      const y = open * (100 + shear);
      return `polygon(0% 0%, 100% 0%, 100% ${(y - shear).toFixed(2)}%, 0% ${y.toFixed(2)}%)`;
    }
    default: {
      const x = open * (100 + shear);
      return `polygon(0% 0%, ${x.toFixed(2)}% 0%, ${(x - shear).toFixed(2)}% 100%, 0% 100%)`;
    }
  }
};

// `angle` is a real angle in degrees, but a polygon only knows percentages - so it needs the box.
// Pass `box` (the size in px of the element you are wiping: the width you put in `style` and the
// height its content has) and the edge is exactly `angle` degrees. Without it the edge leans by
// `angle` percent of the axis: same code, rough angle. Both are deterministic - nothing is measured
// at render time, because a parallel render may never measure the DOM.
export const MaskWipe: React.FC<{
  children?: React.ReactNode;
  direction?: Direction;             // where the reveal grows FROM ('left' = sweeps rightwards)
  angle?: number;                    // deg of the leading edge (0 = straight edge)
  start?: number;                    // frame the sweep begins
  duration?: number;                 // frames the sweep takes
  from?: number;                     // 0..1, already-open amount at `start` (a partial reveal)
  box?: {width: number; height: number};
  curve?: (t: number) => number;     // easing of the sweep
  style?: React.CSSProperties;
}> = ({children, direction = 'left', angle = 0, start = 0, duration = 16, from = 0, box,
      curve = ease.inOut, style}) => {
  const frame = useCurrentFrame();
  const degrees = Math.min(45, Math.abs(angle));
  const tan = Math.tan((degrees * Math.PI) / 180);
  const horizontal = direction === 'left' || direction === 'right';
  const shear =
    box && box.width > 0 && box.height > 0
      ? horizontal
        ? ((tan * box.height) / box.width) * 100
        : ((tan * box.width) / box.height) * 100
      : tan * 100;
  const swept = progress(frame, start, start + Math.max(1, duration), curve);
  const open = Math.max(0, Math.min(1, lerp(from, 1, swept)));
  return <div style={{clipPath: clipped(open, direction, shear), ...style}}>{children}</div>;
};
