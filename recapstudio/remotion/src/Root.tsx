import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {MovieRecap} from './MovieRecap';
import {labCompositions} from './SceneLab';
import {emptyTimeline, Timeline} from './types';

// Length, size and fps all come from timeline.json (passed with --props), so the same
// composition renders 16:9 and (later) 9:16 without code changes.
const calculateMetadata: CalculateMetadataFunction<Timeline> = ({props}) => {
  return {
    durationInFrames: Math.max(1, props.totalFrames),
    fps: props.fps,
    width: props.width,
    height: props.height,
  };
};

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="MovieRecap"
        component={MovieRecap}
        durationInFrames={emptyTimeline.totalFrames}
        fps={emptyTimeline.fps}
        width={emptyTimeline.width}
        height={emptyTimeline.height}
        defaultProps={emptyTimeline}
        calculateMetadata={calculateMetadata}
      />
      {/* Studio previews of single scenes: scene-<segment id>, example-<name> (Phase 2) */}
      {labCompositions()}
    </>
  );
};
