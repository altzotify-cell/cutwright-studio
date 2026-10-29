import React, {useMemo} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {makeLayout} from '../layout';
import {Style, Word} from '../types';

// Word-by-word captions. Everything is derived from the word frames in timeline.json, so it
// stays in sync with the voice by construction. Three looks: clean | bold | karaoke.

type Page = {words: Word[]; start: number; end: number};

const SENTENCE_END = /[.!?…]["')\]]*$/;
const SOFT_BREAK = /[,;:—–]["')\]]*$/;

const defaults = {
  clean: {maxWords: 7, maxChars: 44},
  bold: {maxWords: 3, maxChars: 22},
  karaoke: {maxWords: 5, maxChars: 34},
};

export const buildPages = (
  words: Word[],
  fps: number,
  maxWords: number,
  maxChars: number,
  segmentFrames: number
): Page[] => {
  const pages: Word[][] = [];
  let cur: Word[] = [];
  let chars = 0;
  for (const w of words) {
    const prev = cur[cur.length - 1];
    const gap = prev ? w.startFrame - prev.endFrame : 0;
    const full = cur.length >= maxWords || chars + w.word.length + 1 > maxChars;
    const afterSentence = prev ? SENTENCE_END.test(prev.word) : false;
    const afterSoft = prev ? SOFT_BREAK.test(prev.word) && cur.length >= 3 : false;
    if (prev && (full || afterSentence || afterSoft || gap > fps * 0.5)) {
      pages.push(cur);
      cur = [];
      chars = 0;
    }
    cur.push(w);
    chars += w.word.length + 1;
  }
  if (cur.length) pages.push(cur);

  return pages.map((ws, i) => {
    const start = ws[0].startFrame;
    const lastEnd = ws[ws.length - 1].endFrame + Math.round(fps * 0.5);
    const nextStart = i + 1 < pages.length ? pages[i + 1][0].startFrame : segmentFrames;
    return {words: ws, start, end: Math.max(start + 2, Math.min(lastEnd, nextStart))};
  });
};

export const Captions: React.FC<{words: Word[]; style: Style; segmentFrames: number}> = ({
  words,
  style,
  segmentFrames,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const cc = style.captions;
  const L = makeLayout(width, height);
  const look = cc.style;
  const d = defaults[look] ?? defaults.karaoke;
  const maxWords = cc.max_words > 0 ? cc.max_words : L.portrait ? Math.min(d.maxWords, look === 'clean' ? 5 : 4) : d.maxWords;
  const maxChars = L.portrait ? Math.round(d.maxChars * 0.75) : d.maxChars;

  const pages = useMemo(
    () => buildPages(words, fps, maxWords, maxChars, segmentFrames),
    [words, fps, maxWords, maxChars, segmentFrames]
  );

  const page = pages.find((p) => frame >= p.start - 1 && frame < p.end);
  if (!page) return null;

  const upper = cc.uppercase === null || cc.uppercase === undefined ? look === 'bold' : cc.uppercase;
  const sizeBase = look === 'bold' ? 86 : look === 'karaoke' ? 62 : 52;
  const fontSize = sizeBase * L.u * (cc.size || 1) * (L.portrait ? 1.05 : 1);
  const accent = style.accent;
  const local = frame - page.start;

  // the page pops in with a little spring (bold and karaoke) or fades in (clean)
  const pop = spring({frame: local + 1, fps, config: {damping: 14, stiffness: 220}, durationInFrames: 10});
  const fadeIn = interpolate(local, [-1, 2], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fadeOut = interpolate(frame, [page.end - 3, page.end], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const pageScale = look === 'clean' ? 1 : interpolate(pop, [0, 1], [0.88, 1]);

  const bottom = cc.position === 'middle' ? Math.round(height * 0.42) : L.captionBottom + (look === 'bold' ? Math.round(height * 0.04) : 0);

  const activeIndex = (() => {
    let a = -1;
    page.words.forEach((w, i) => {
      if (frame >= w.startFrame) a = i;
    });
    return a;
  })();

  return (
    <div
      style={{
        position: 'absolute',
        left: L.safeSide,
        right: L.safeSide,
        bottom,
        display: 'flex',
        justifyContent: 'center',
        pointerEvents: 'none',
        opacity: Math.min(fadeIn, fadeOut),
        transform: `scale(${pageScale})`,
        transformOrigin: '50% 100%',
        fontFamily: style.font,
      }}
    >
      <div
        style={{
          textAlign: 'center',
          lineHeight: 1.18,
          fontSize,
          fontWeight: 800,
          textTransform: upper ? 'uppercase' : 'none',
          letterSpacing: look === 'bold' ? 1 * L.u : 0,
          padding: look === 'clean' ? `${0.22 * fontSize}px ${0.5 * fontSize}px` : 0,
          background: look === 'clean' ? 'rgba(0,0,0,0.5)' : 'transparent',
          borderRadius: look === 'clean' ? 0.35 * fontSize : 0,
          maxWidth: '100%',
        }}
      >
        {page.words.map((w, i) => {
          const spoken = i < activeIndex;
          const current = i === activeIndex;
          const wp = current
            ? spring({frame: frame - w.startFrame, fps, config: {damping: 12, stiffness: 260}, durationInFrames: 8})
            : 1;
          const emph = !!w.emphasis;
          let color = '#ffffff';
          let scale = 1;
          let bg = 'transparent';
          let shadow = `0 ${2 * L.u}px ${10 * L.u}px rgba(0,0,0,0.85)`;
          let stroke = '0px transparent';

          if (look === 'clean') {
            color = current ? accent : spoken ? '#ffffff' : 'rgba(255,255,255,0.6)';
            scale = current ? 1 + 0.08 * (1 - wp) : 1;
            shadow = 'none';
          } else if (look === 'bold') {
            color = current || emph ? accent : '#ffffff';
            scale = (current ? 1.08 + 0.12 * (1 - wp) : 1) * (emph ? 1.1 : 1);
            stroke = `${Math.max(3, 7 * L.u)}px #000000`;
            shadow = `0 ${5 * L.u}px 0 rgba(0,0,0,0.9)`;
          } else {
            // karaoke: dim until spoken, the current word sits on an accent box
            color = current ? '#111111' : spoken ? '#ffffff' : 'rgba(255,255,255,0.45)';
            bg = current ? accent : emph && !current ? 'rgba(255,255,255,0.12)' : 'transparent';
            scale = current ? 1 + 0.1 * (1 - wp) : 1;
          }

          return (
            <span
              key={i}
              style={{
                display: 'inline-block',
                margin: `0 ${0.14 * fontSize}px`,
                padding: look === 'karaoke' ? `0 ${0.14 * fontSize}px` : 0,
                borderRadius: 0.18 * fontSize,
                background: bg,
                color,
                transform: `scale(${scale})`,
                textShadow: shadow,
                WebkitTextStroke: stroke,
                paintOrder: 'stroke fill',
              }}
            >
              {w.word}
            </span>
          );
        })}
      </div>
    </div>
  );
};
