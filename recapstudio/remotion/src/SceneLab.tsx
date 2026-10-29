import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {mergeTheme} from '../kit';
import {exampleScenes} from '../scenes_examples';
import {generated, projectTheme} from './generated/registry';
import {makeLayout} from './layout';
import {LabEntry} from './sceneTypes';
import {SceneFrame} from '../kit';

// Remotion Studio preview of single scenes ("npm run studio", or project menu "Preview scenes").
// One composition per scene: "scene-<segment id>" for the project's scenes, "example-<name>" for the reference
// scenes. In the right-hand props panel, set  portrait: true  to see the 9:16 version.
// There is deliberately NO error boundary here: a broken scene shows its real error so you can fix it.

export type LabProps = {portrait: boolean};

const slug = (s: string) => s.replace(/[^A-Za-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'scene';

const labComponent = (entry: LabEntry): React.FC<LabProps> => {
  const Scene = entry.component;
  const m = entry.meta;
  const Lab: React.FC<LabProps> = ({portrait}) => {
    const w = portrait ? Math.min(m.width, m.height) : Math.max(m.width, m.height);
    const h = portrait ? Math.max(m.width, m.height) : Math.min(m.width, m.height);
    return (
      <Scene
        durationInFrames={m.durationInFrames}
        fps={m.fps}
        width={w}
        height={h}
        props={m.props}
        theme={mergeTheme(projectTheme)}
        words={m.words}
        layout={makeLayout(w, h)}
      />
    );
  };
  return Lab;
};

const metaFor = (entry: LabEntry): CalculateMetadataFunction<LabProps> => ({props}) => {
  const m = entry.meta;
  const portrait = !!props.portrait;
  return {
    durationInFrames: Math.max(1, m.durationInFrames),
    fps: m.fps,
    width: portrait ? Math.min(m.width, m.height) : Math.max(m.width, m.height),
    height: portrait ? Math.max(m.width, m.height) : Math.min(m.width, m.height),
  };
};

// The plain themed background with nothing on it. tools/test_scenes.mjs renders it once and compares: a scene whose
// middle frames look the same as this drew nothing.
const EmptyRef: React.FC<LabProps> = ({portrait}) => {
  const w = portrait ? 1080 : 1920;
  const h = portrait ? 1920 : 1080;
  return <SceneFrame theme={mergeTheme(projectTheme)} layout={makeLayout(w, h)} />;
};

export const labCompositions = (): React.ReactElement[] => {
  const out: React.ReactElement[] = [];
  const add = (idPrefix: string, key: string, entry: LabEntry) =>
    out.push(
      <Composition
        key={`${idPrefix}-${key}`}
        id={`${idPrefix}-${slug(key)}`}
        component={labComponent(entry)}
        durationInFrames={Math.max(1, entry.meta.durationInFrames)}
        fps={entry.meta.fps}
        width={Math.max(entry.meta.width, entry.meta.height)}
        height={Math.min(entry.meta.width, entry.meta.height)}
        defaultProps={{portrait: false}}
        calculateMetadata={metaFor(entry)}
      />
    );
  Object.entries(generated).forEach(([id, entry]) => add('scene', id, entry));
  Object.entries(exampleScenes).forEach(([id, entry]) => add('example', id, entry));
  out.push(
    <Composition
      key="empty-ref"
      id="scene-empty-ref"
      component={EmptyRef}
      durationInFrames={24}
      fps={24}
      width={1920}
      height={1080}
      defaultProps={{portrait: false}}
      calculateMetadata={({props}) => ({width: props.portrait ? 1080 : 1920, height: props.portrait ? 1920 : 1080})}
    />
  );
  return out;
};

export const sceneCompositionId = (segmentId: string) => `scene-${slug(segmentId)}`;
