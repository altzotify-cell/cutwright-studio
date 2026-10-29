import type React from 'react';
import type {Layout} from '../src/layout';

// The scene contract (see CONTRACT.md). Every generated scene is a default-exported component that
// receives SceneProps, and may export `cost` ('low' | 'medium' | 'high').

export type {Layout};
export type SceneCost = 'low' | 'medium' | 'high';

export type Word = {
  word: string;
  startFrame: number; // frames from the START OF THE SCENE (the segment), not of the whole video
  endFrame: number;
  emphasis?: boolean;
};

export type Theme = {
  name: string;
  palette: {
    bg: string; // darkest background
    bg2: string; // lighter background (gradient end)
    fg: string; // main text
    muted: string; // secondary text, tracks, grid lines
    accent: string; // the one highlight colour
    accent2: string; // a second highlight colour
    good: string;
    bad: string;
  };
  fonts: {heading: string; body: string};
  energy: 'calm' | 'punchy' | 'chaotic';
  grain: number; // 0..1, used by the fixed layers (not by scenes)
};

export type SceneProps<P = Record<string, any>> = {
  durationInFrames: number;
  fps: number;
  width: number;
  height: number;
  props: P; // the segment's data (segments.json "motion.data" / "scene.props")
  theme: Theme;
  words: Word[]; // spoken words of this segment, frames counted from the scene start
  layout: Layout; // safe zones for 16:9 and 9:16: use it instead of pixel numbers
};

export type SceneComponent = React.ComponentType<SceneProps<any>>;
