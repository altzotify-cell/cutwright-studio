import React from 'react';
import {useVideoConfig} from 'remotion';
import {Theme} from '../../kit';
import {generated} from '../generated/registry';
import {makeLayout} from '../layout';
import {SegmentTimeline} from '../types';
import {Keywords} from './Keywords';

// Draws the picture of a segment whose scene is NOT plain footage.
//   scene.type "generated"  a scene file that passed scenes.py (static check + test render)
//   scene.type "keywords"   the fixed fallback scene (no footage, or a scene that failed)
// A generated scene that still throws while rendering is caught here and replaced by the keywords scene,
// so one bad scene can never stop a long render. (The check in scenes.py normally catches it earlier.)

class SceneBoundary extends React.Component<{fallback: React.ReactNode; label: string; children?: React.ReactNode}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() {
    return {failed: true};
  }
  componentDidCatch(error: Error) {
    // eslint-disable-next-line no-console
    console.error(`[scene ${this.props.label}] crashed while rendering, showing the keywords scene instead: ${error.message}`);
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export const SceneHost: React.FC<{seg: SegmentTimeline; theme: Theme}> = ({seg, theme}) => {
  const {width, height, fps} = useVideoConfig();
  const layout = makeLayout(width, height);
  const common = {durationInFrames: seg.durationFrames, fps, width, height, theme, words: seg.words ?? [], layout};
  const fallback = <Keywords {...common} props={{text: seg.text}} />;

  if (seg.scene.type === 'generated') {
    const entry = generated[seg.scene.id ?? seg.id];
    if (entry) {
      const Scene = entry.component;
      return (
        <SceneBoundary label={seg.id} fallback={fallback}>
          <Scene {...common} props={seg.scene.props ?? {}} />
        </SceneBoundary>
      );
    }
    // eslint-disable-next-line no-console
    console.error(`[scene ${seg.id}] is not in the scene registry (run "Check scenes" again), showing the keywords scene.`);
  }
  return fallback;
};
