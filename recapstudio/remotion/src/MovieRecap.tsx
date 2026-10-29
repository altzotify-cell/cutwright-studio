import React from 'react';
import {AbsoluteFill, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {mergeTheme, Theme} from '../kit';
import {Captions} from './captions/Captions';
import {CaptionBadge, ChapterCard, LowerThird, RankStamp} from './overlays/Overlays';
import {SceneHost} from './scenes/SceneHost';
import {enterFx, exitFx, NO_FX} from './transitions/transitions';
import {defaultStyle, SegmentTimeline, Style, Timeline} from './types';

// Phase 1: picture + voice + music (as in Phase 0) plus the structural layer.
// Phase 2: a segment's picture can also be a scene (generated, or the fixed keywords fallback) instead of the clip.
// Structural layer:
//   word-by-word captions, chapter cards, lower thirds, rank stamp, caption badge and transitions.
// Every layer reads timeline.json only; nothing here depends on the ffmpeg pipeline.

const mergeStyle = (s?: Partial<Style>): Style => ({
  ...defaultStyle,
  ...(s ?? {}),
  captions: {...defaultStyle.captions, ...(s?.captions ?? {})},
  transitions: {...defaultStyle.transitions, ...(s?.transitions ?? {})},
  overlays: {...defaultStyle.overlays, ...(s?.overlays ?? {})},
});

// theme.json (if the project has one) over the defaults; the config.json accent and font fill in what it leaves out.
const resolveTheme = (tl: Timeline, style: Style): Theme => {
  const t = (tl.theme ?? {}) as any;
  return mergeTheme({
    ...t,
    palette: {accent: style.accent, ...(t.palette ?? {})},
    fonts: {heading: style.font, ...(t.fonts ?? {})},
  });
};

const SegmentLayers: React.FC<{seg: SegmentTimeline; next?: SegmentTimeline; style: Style; theme: Theme}> = ({seg, next, style, theme}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const dur = seg.durationFrames;
  const n = seg.transitionFrames ?? style.transitions.frames;
  const tOn = style.transitions.enabled;

  const enter = tOn ? enterFx(seg.transition, frame, n, width, seg.id) : NO_FX;
  const exit = tOn && next ? exitFx(next.transition, dur - frame, next.transitionFrames ?? n, width) : NO_FX;
  const fx = enter !== NO_FX ? enter : exit;

  const words = seg.words ?? [];
  const ov = style.overlays;

  return (
    <>
      <AbsoluteFill style={{...fx.style, willChange: 'transform, filter, opacity'}}>
        {seg.scene && seg.scene.type !== 'footage' ? (
          <SceneHost seg={seg} theme={theme} />
        ) : (
          <OffthreadVideo src={staticFile(seg.video)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        )}
      </AbsoluteFill>
      {fx.overlay}

      {ov.caption_badge && seg.caption ? <CaptionBadge text={seg.caption} style={style} segmentFrames={dur} /> : null}
      {ov.rank_stamp && seg.rank !== null && seg.rank !== undefined && seg.rank !== '' ? (
        <RankStamp rank={seg.rank} style={style} segmentFrames={dur} />
      ) : null}
      {ov.chapter_cards && seg.chapterStart && seg.chapter ? (
        <ChapterCard index={seg.chapterIndex ?? 1} title={seg.chapter} style={style} segmentFrames={dur} />
      ) : null}
      {ov.lower_thirds && seg.lowerThird ? (
        <LowerThird name={seg.lowerThird.name} role={seg.lowerThird.role} style={style} segmentFrames={dur} />
      ) : null}
      {style.captions.enabled && words.length ? <Captions words={words} style={style} segmentFrames={dur} /> : null}

      <Audio src={staticFile(seg.audio)} />
      {seg.origAudio ? <Audio src={staticFile(seg.origAudio)} /> : null}
    </>
  );
};

export const MovieRecap: React.FC<Timeline> = (tl) => {
  const style = mergeStyle(tl.style);
  const theme = resolveTheme(tl, style);
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      {tl.segments.map((seg, i) => (
        <Sequence key={seg.id} from={seg.startFrame} durationInFrames={seg.durationFrames}>
          <SegmentLayers seg={seg} next={tl.segments[i + 1]} style={style} theme={theme} />
        </Sequence>
      ))}
      {tl.music ? <Audio src={staticFile(tl.music.file)} /> : null}
    </AbsoluteFill>
  );
};
