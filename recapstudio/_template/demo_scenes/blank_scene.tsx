import React from 'react';
import {SceneFrame, SceneProps} from '@kit';

// DEMO (deliberately broken): valid code that draws nothing but the background. The test render must notice.
export const cost = 'low';

const BlankScene: React.FC<SceneProps> = ({theme, layout}) => {
  return <SceneFrame theme={theme} layout={layout} />;
};

export default BlankScene;
