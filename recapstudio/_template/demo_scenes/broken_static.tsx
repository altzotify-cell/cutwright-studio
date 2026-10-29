import React from 'react';
import {SceneFrame, SceneProps} from '@kit';

// DEMO (deliberately broken): tries to download something. The static check must refuse it, so it is never run.
export const cost = 'low';

const BrokenStatic: React.FC<SceneProps> = ({theme, layout}) => {
  const [text, setText] = React.useState('loading');
  React.useEffect(() => {
    fetch('https://example.com/data.json').then((r) => r.text()).then(setText);
  }, []);
  return (
    <SceneFrame theme={theme} layout={layout}>
      <div style={{color: theme.palette.fg, fontSize: 60}}>{text}</div>
    </SceneFrame>
  );
};

export default BrokenStatic;
