# Recap Studio scene contract and helper kit (kit version 1)

A scene is ONE .tsx file that draws the whole picture of one segment of the video (a stat, a timeline, a quote,
a comparison, a visual metaphor). It replaces the footage for that segment. The spoken captions, chapter cards,
lower thirds and transitions are drawn on top of it by the tool; do not draw those yourself.

## The file

```tsx
import React from 'react';
import {useCurrentFrame, interpolate, spring, random} from 'remotion';
import {SceneFrame, SceneProps, contentBox, RingChart, ease, progress} from '@kit';

export const cost = 'low';            // 'low' | 'medium' | 'high'  (be honest, see "Cost")

const MyScene: React.FC<SceneProps<{value?: number}>> = ({durationInFrames, fps, props, theme, words, layout}) => {
  const frame = useCurrentFrame();    // 0 = first frame of THIS scene
  const box = contentBox(layout);     // where content may go
  return <SceneFrame theme={theme} layout={layout}>{/* ... */}</SceneFrame>;
};

export default MyScene;               // required
```

## What you receive (SceneProps)

| prop | meaning |
| --- | --- |
| `durationInFrames`, `fps` | length of the scene. It can be anything from 1 s to 60 s: never assume a length. |
| `width`, `height` | 1920x1080 (16:9) or 1080x1920 (9:16). The scene must work in BOTH. |
| `props` | the data for this scene (from the script's `motion.data`). Every field may be missing: use defaults. |
| `theme` | `theme.palette.{bg,bg2,fg,muted,accent,accent2,good,bad}`, `theme.fonts.{heading,body}`, `theme.energy` |
| `words` | the narration: `{word, startFrame, endFrame}` counted from the scene start. May be an estimate. May be empty. |
| `layout` | `{portrait, u, safeSide, safeTop, safeBottom, captionBottom}`. `u` = 1 at 1080 px: multiply sizes by it. |

## Rules (the tool checks these; a scene that breaks one is replaced by a plain fallback)

1. Imports ONLY from `'remotion'`, `'react'` and `'@kit'`. No other packages, no relative imports.
2. From `'remotion'` you may NOT use: `Audio`, `Video`, `OffthreadVideo`, `Img`, `IFrame`, `staticFile`, `delayRender`,
   `continueRender`, `getInputProps`. No images or fonts from files or the internet: draw with SVG and CSS.
3. No network (`fetch`, `XMLHttpRequest`, URLs in strings), no `eval`, `Function`, dynamic `import()`, `window`,
   `document`, `localStorage`, `setTimeout`, `setInterval`, `requestAnimationFrame`.
4. Everything must be a pure function of the frame number. No `Math.random()` (use `random('seed')` from remotion),
   no `Date`, no `performance.now()`, no state that changes over time. Animate with `useCurrentFrame()`,
   `interpolate`, `spring`, or the kit's `progress`, `useEntrance`, `RevealText` ...
5. Use `layout` and `contentBox(layout)` for positions and `layout.u` for sizes. Never hard-code 1920 or 1080.
   Keep important content inside `contentBox`: the spoken captions sit below it.
6. Export a default component and `export const cost = 'low' | 'medium' | 'high'`.
7. Handle missing data: `props.items ?? []`, `props.value ?? 50`. A crash replaces the whole scene.
8. Start with `<SceneFrame theme={theme} layout={layout}>` (themed background + safe content area), or draw your own
   full-frame background from `theme.palette`.
9. Use theme colours and fonts, never fixed hex colours for the main look: the same scene must suit different movies.

## Cost (this video is rendered on a laptop without a graphics card)

- `low`: a handful of shapes and text, no filters. Default choice.
- `medium`: up to about 60 particles, a few `drop-shadow` or gradients, SVG with up to a few hundred elements.
- `high`: heavy filters (`blur()` on large areas, `feTurbulence`), more than 60 particles, thousands of SVG nodes.
Avoid `high`. Large `filter: blur()`, `mix-blend-mode` and `backdrop-filter` are slow: prefer gradients.

## Timing against the narration

```tsx
const t = wordStart(words, 'betrayed', 30);   // frame where "betrayed" is spoken, or 30 if it is not found
const k = spring({frame: frame - t, fps, config: springs.snappy});
```
Do not rely on it: `words` can be an estimate, so animations must also look fine at their fallback time.
Keep beats at least ~0.4 s apart and let the main idea be readable for at least 1.5 s before the end.

## Kit reference (`import {...} from '@kit'`)

**Layout:** `SceneFrame({theme, layout, children, backdrop?, vignette?, align?})`, `contentBox(layout)` -> `{left, top, width, height, right, bottom}`.

**Motion:** `ease.{out,inOut,in,back,linear}`, `springs.{soft,smooth,snappy,bouncy}`, `progress(frame, from, to, easing?)` (0..1 clamped),
`fadeOut(frame, total, frames?)`, `stagger(i, step?)`, `useEntrance(delay?, springName?)` (hook, 0..1), `wobble(frame, period, amount, phase)`,
`lerp`, `clamp01`.

**Text:** `RevealText({text, start?, step?, startFrames?, mode: 'words'|'chars', size, color, font?, weight?, highlight?, highlightColor?, align?, lineHeight?, rise?, uppercase?, letterSpacing?})`,
`wordStart(words, phrase, fallback)`, `findWords(words, phrase)` -> `{index, start, end} | null`, `spokenIndex(words, frame)`, `useSpokenIndex(words)`, `normWord(s)`.

**Numbers and charts:** `AnimatedCounter({to, from?, start?, duration?, decimals?, prefix?, suffix?, thousands?, style?})`,
`RingChart({value 0-100, size, stroke?, start?, duration?, color, trackColor, glow?, children})`,
`BarChart({items: [{label, value, color?}], width, rowHeight?, gap?, max?, start?, step?, duration?, color, trackColor, labelColor, valueColor?, font?, suffix?, decimals?})`,
`LineChart({points: number[] | {x,y}[], width, height, start?, duration?, color, strokeWidth?, smooth?, area?, gridColor?, dot?})`, `formatNumber(v, decimals?)`.

**Shapes:** `DrawPath({d, frame, start?, duration?, stroke, strokeWidth?, fill?, opacity?})` (inside an `<svg>`), `polylinePath(points)`, `smoothPath(points)`,
`arcPath(cx, cy, r, startDeg, endDeg)`.

**Particles:** `Particles({count?, seed?, color, mode: 'ambient'|'burst'|'rise', start?, duration?, size?, spread?, originX?, originY?, opacity?, period?})` (max 80).

**Theme helpers:** `withAlpha('#ffd23f', 0.4)`, `energyOf(theme)` -> `{speed, amp}` (scale your animation speed / distance by them so calm / punchy / chaotic themes feel different).

Everything else (React, `interpolate`, `spring`, `Easing`, `random`, `useCurrentFrame`, `useVideoConfig`, `AbsoluteFill`, `Sequence`, `Series`) comes from `'remotion'` / `'react'`.

## Reference scenes

`remotion/scenes_examples/` has three complete working scenes (`stat_ring`, `timeline_reveal`, `quote_moment`). They show a good structure, both aspect ratios, narration sync and honest costs. Copy their approach.
