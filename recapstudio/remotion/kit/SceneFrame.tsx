import React from 'react';
import {AbsoluteFill} from 'remotion';
import {withAlpha} from './theme';
import {Layout, Theme} from './types';

// The area where scene content can live without hiding under the spoken captions or the TikTok / Shorts UI.
// (Captions are drawn on top of every scene, at layout.captionBottom from the bottom edge.)
export type Box = {left: number; top: number; width: number; height: number; right: number; bottom: number};

export const contentBox = (layout: Layout): Box => {
  const left = layout.safeSide;
  const right = layout.width - layout.safeSide;
  // below the caption badge and the rank stamp, which the tool draws in the top band
  const top = layout.safeTop + 80 * layout.u;
  const bottom = layout.height - Math.max(layout.safeBottom, layout.captionBottom + 150 * layout.u);
  return {left, top, right, bottom, width: right - left, height: Math.max(0, bottom - top)};
};

// Themed background (a soft gradient with a vignette) and a centred, safe content area.
// Every scene should start with it: <SceneFrame theme={theme} layout={layout}> ... </SceneFrame>
export const SceneFrame: React.FC<{
  theme: Theme;
  layout: Layout;
  children?: React.ReactNode;
  backdrop?: React.ReactNode; // full-bleed decoration behind the content (ignores the safe zones)
  vignette?: boolean;
  align?: 'center' | 'top';
}> = ({theme, layout, children, backdrop, vignette = true, align = 'center'}) => {
  const box = contentBox(layout);
  const p = theme.palette;
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 38%, ${p.bg2} 0%, ${p.bg} 78%)`,
        fontFamily: theme.fonts.body,
        color: p.fg,
      }}
    >
      {backdrop ? <AbsoluteFill style={{overflow: 'hidden'}}>{backdrop}</AbsoluteFill> : null}
      {vignette ? (
        <AbsoluteFill style={{background: `radial-gradient(ellipse at center, ${withAlpha('#000000', 0)} 55%, ${withAlpha('#000000', 0.45)} 100%)`}} />
      ) : null}
      <div
        style={{
          position: 'absolute',
          left: box.left,
          top: box.top,
          width: box.width,
          height: box.height,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: align === 'center' ? 'center' : 'flex-start',
        }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
};
