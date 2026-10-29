import React from 'react';
import {SceneFrame, SceneProps} from '@kit';

// DEMO (deliberately broken): looks fine to the static check, but crashes while rendering because
// props.items does not exist. The test render must catch this and the video must use the keywords scene.
export const cost = 'low';

const BrokenRuntime: React.FC<SceneProps<{items?: string[]}>> = ({props, theme, layout}) => {
  const items = props.items as string[];
  return (
    <SceneFrame theme={theme} layout={layout}>
      <div style={{color: theme.palette.fg, fontSize: 60}}>{items.map((x) => x.toUpperCase()).join(' / ')}</div>
    </SceneFrame>
  );
};

export default BrokenRuntime;
