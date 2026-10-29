// The contract between recap.py (timeline.py) and Remotion. Keep in sync with timeline.py.
// All file paths are relative to the project's remotion_public/ folder (use staticFile()).
// Every field added after schema 1 is optional here, so an old timeline.json still renders.

export type CaptionStyleName = 'clean' | 'bold' | 'karaoke';
export type TransitionName = 'cut' | 'fade' | 'whip' | 'zoom' | 'flash' | 'glitch';

export type Word = {
  word: string;
  startFrame: number; // inside the segment
  endFrame: number;
  emphasis?: boolean;
};

// How the picture of a segment is made. Absent or "footage" = the fitted clip (Phases 0-1).
//   keywords   the fixed fallback scene (reason says why)
//   generated  a validated scene file: id is the registry key, props the data, cost low | medium | high
export type SceneRef = {
  type: string;
  id?: string;
  cost?: 'low' | 'medium' | 'high';
  props?: Record<string, unknown>;
  reason?: string;
};

export type SegmentTimeline = {
  id: string;
  kind: string; // video | image | comic | slate
  startFrame: number;
  durationFrames: number;
  video: string; // pre-fitted picture clip, exactly durationFrames long, no audio
  audio: string; // narration, exactly durationFrames long
  origAudio: string | null; // ducked original sound of the footage, or null
  text: string;
  caption: string; // on-screen label (date, stat line) from segments.json "caption"
  rank: number | string | null;
  chapter: string;
  words?: Word[];
  wordMethod?: string | null; // edge | whisper | even
  chapterStart?: boolean;
  chapterIndex?: number;
  lowerThird?: {name: string; role: string} | null;
  transition?: TransitionName; // how this segment is entered
  transitionFrames?: number;
  scene: SceneRef;
  sfx: unknown[];
};

export type Style = {
  font: string;
  accent: string;
  captions: {
    enabled: boolean;
    style: CaptionStyleName;
    size: number; // 1 = default
    position: 'bottom' | 'middle';
    max_words: number; // 0 = automatic per style
    uppercase: boolean | null; // null = style default
  };
  transitions: {enabled: boolean; frames: number};
  overlays: {
    chapter_cards: boolean;
    lower_thirds: boolean;
    rank_stamp: boolean;
    caption_badge: boolean;
    chapter_seconds: number;
  };
};

export const defaultStyle: Style = {
  font: '"Arial Black", Impact, "Segoe UI", Arial, sans-serif',
  accent: '#FFD23F',
  captions: {enabled: true, style: 'karaoke', size: 1, position: 'bottom', max_words: 0, uppercase: null},
  transitions: {enabled: true, frames: 8},
  overlays: {chapter_cards: true, lower_thirds: true, rank_stamp: true, caption_badge: true, chapter_seconds: 2.4},
};

export type Timeline = {
  schema: number;
  module: string;
  fps: number;
  width: number;
  height: number;
  totalFrames: number;
  theme: Record<string, unknown>;
  style?: Style;
  music: {file: string} | null; // volume is already baked into the file
  segments: SegmentTimeline[];
  generated: string;
};

export const emptyTimeline: Timeline = {
  schema: 2,
  module: 'movie_recap',
  fps: 24,
  width: 1920,
  height: 1080,
  totalFrames: 24,
  theme: {},
  music: null,
  segments: [],
  generated: '',
};
