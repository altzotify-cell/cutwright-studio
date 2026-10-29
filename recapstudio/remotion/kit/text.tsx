import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {springs, SpringName} from './motion';
import {Word} from './types';

// ---------------------------------------------------------------------------------------------
// Narration sync: `words` (from SceneProps) are the spoken words with frames from the scene start.
// ---------------------------------------------------------------------------------------------
export const normWord = (s: string): string => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');

export type WordSpan = {index: number; start: number; end: number};

// Finds a word or short phrase ("last night") in the narration. Matches whole words, ignores case and
// punctuation. Returns null when it is not spoken (so always give a fallback).
export const findWords = (words: Word[], phrase: string, fromIndex = 0): WordSpan | null => {
  const want = phrase.split(/\s+/).map(normWord).filter(Boolean);
  if (!want.length) return null;
  for (let i = Math.max(0, fromIndex); i <= words.length - want.length; i++) {
    let ok = true;
    for (let k = 0; k < want.length; k++) {
      if (normWord(words[i + k].word) !== want[k]) {
        ok = false;
        break;
      }
    }
    if (ok) return {index: i, start: words[i].startFrame, end: words[i + want.length - 1].endFrame};
  }
  return null;
};

// The frame where `phrase` starts being spoken, or `fallback`. Use it to land an animation on a word.
export const wordStart = (words: Word[], phrase: string, fallback = 0, fromIndex = 0): number =>
  findWords(words, phrase, fromIndex)?.start ?? fallback;

// Index of the word being spoken right now (the last word that has started), -1 before the first word.
export const spokenIndex = (words: Word[], frame: number): number => {
  let idx = -1;
  for (let i = 0; i < words.length; i++) {
    if (words[i].startFrame <= frame) idx = i;
    else break;
  }
  return idx;
};

// Hook version: `const i = useSpokenIndex(words)`.
export const useSpokenIndex = (words: Word[]): number => spokenIndex(words, useCurrentFrame());

// ---------------------------------------------------------------------------------------------
// RevealText: words (or letters) pop in one after another.
// ---------------------------------------------------------------------------------------------
export const RevealText: React.FC<{
  text: string;
  start?: number; // frame of the first word
  step?: number; // frames between words (letters in mode 'chars')
  startFrames?: number[]; // exact start frame per word; overrides start/step (e.g. synced with wordStart)
  mode?: 'words' | 'chars';
  size: number; // px
  color: string;
  font?: string;
  weight?: number | string;
  highlight?: string[]; // words drawn in `highlightColor`
  highlightColor?: string;
  align?: 'left' | 'center' | 'right';
  lineHeight?: number;
  rise?: number; // px each word rises while appearing
  spring?: SpringName;
  uppercase?: boolean;
  letterSpacing?: number | string;
  style?: React.CSSProperties;
}> = ({
  text,
  start = 0,
  step = 4,
  startFrames,
  mode = 'words',
  size,
  color,
  font,
  weight = 800,
  highlight = [],
  highlightColor,
  align = 'center',
  lineHeight = 1.15,
  rise = 28,
  spring: preset = 'snappy',
  uppercase = false,
  letterSpacing,
  style,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const hl = new Set(highlight.map(normWord));
  const tokens = text.split(/\s+/).filter(Boolean);

  const unit = (content: string, delay: number, hot: boolean, key: string, trailingSpace: boolean) => {
    const p = spring({frame: frame - delay, fps, config: springs[preset]});
    const op = Math.max(0, Math.min(1, p * 1.4));
    return (
      <span
        key={key}
        style={{
          display: 'inline-block',
          opacity: op,
          transform: `translateY(${(1 - p) * rise}px)`,
          color: hot && highlightColor ? highlightColor : color,
          marginRight: trailingSpace ? '0.28em' : 0,
          whiteSpace: 'pre',
        }}
      >
        {content}
      </span>
    );
  };

  let charCounter = 0;
  return (
    <div
      style={{
        fontFamily: font,
        fontWeight: weight as any,
        fontSize: size,
        lineHeight,
        textAlign: align,
        textTransform: uppercase ? 'uppercase' : undefined,
        letterSpacing,
        ...style,
      }}
    >
      {tokens.map((tok, wi) => {
        const hot = hl.has(normWord(tok));
        if (mode === 'chars') {
          const chars = Array.from(tok);
          return (
            <span key={wi} style={{display: 'inline-block', whiteSpace: 'nowrap', marginRight: '0.28em'}}>
              {chars.map((ch, ci) => unit(ch, start + step * charCounter++, hot, `${wi}-${ci}`, false))}
            </span>
          );
        }
        const delay = startFrames?.[wi] ?? start + step * wi;
        return unit(tok, delay, hot, String(wi), wi < tokens.length - 1);
      })}
    </div>
  );
};
