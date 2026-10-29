import type {SceneComponent, SceneCost, Theme, Word} from '../kit';

// What the Studio preview and the test render need to know about one scene.
// For generated scenes scenes.py writes this into src/generated/registry.ts (taken from timeline.json).
export type SceneMeta = {
  id: string; // segment id
  title: string;
  cost: SceneCost;
  durationInFrames: number;
  fps: number;
  width: number;
  height: number;
  props: Record<string, unknown>;
  words: Word[];
  text: string;
  status?: string; // ok | failed | unchecked (informational, shown in Studio)
  message?: string;
  source?: string; // project file the scene came from
};

export type LabEntry = {component: SceneComponent; meta: SceneMeta};
export type {Theme};
