import React, {createContext, useContext} from 'react';
import {AbsoluteFill, Img, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {withAlpha} from './theme';
import {lerp, progress} from './motion';

// kit/2 (M5.5B): real footage and stills, named by a HANDLE, never by a path.
//
//   <Camera push={[1, 1.08]} pan={[0, -40]}>
//     <LayeredMedia asset="footage_a" scrim={0.45}> ...content... </LayeredMedia>
//   </Camera>
//
// The handle is declared by the STEP (`"assets": {"footage_a": "@asset.footage_a"}`), staged by the
// engine into public/assets and handed to the render in its props file. A scene can therefore only
// name a handle the run declared. There is deliberately NO exported resolver: `useAsset` stays
// private to this file, so a scene cannot turn a handle into a file path or import `Img` itself.

export type AssetInfo = {file: string; kind: 'video' | 'image'; sha256?: string};
export type AssetTable = Record<string, AssetInfo>;

const AssetContext = createContext<AssetTable | null>(null);

// The provider SceneLab renders around a scene. A COMPONENT, not a resolver: it takes the table the
// render already carries (props.assets) and puts it where the primitives below can see it.
export const AssetScope: React.FC<{table?: AssetTable; children?: React.ReactNode}> = ({table, children}) => (
  <AssetContext.Provider value={table ?? {}}>{children}</AssetContext.Provider>
);

// The kit's ONLY handle resolver, and it is not exported (kit/2, owner decision 2026-10-30): a scene
// can name a handle but can never turn one into a file path. `fallback` on <LayeredMedia> is the one
// opt-out, used by the reference scene so the Studio preview still draws something without a render.
const useAsset = (handle: string): AssetInfo => {
  const table = useContext(AssetContext);
  if (!table) {
    throw new Error(
      `asset="${handle}" was used outside an <AssetScope>: footage only renders in a scene composition (kit/2).`,
    );
  }
  const info = table[handle];
  if (!info || !info.file) {
    throw new Error(
      `no asset "${handle}" was declared for this render: add it to the step's "assets" input in the manifest (kit/2).`,
    );
  }
  return info;
};

const fill: React.CSSProperties = {position: 'absolute', left: 0, top: 0, width: '100%', height: '100%'};

// A camera move on everything inside it: push (scale), pan (px), handheld shake (px, deterministic).
// It is a transform on a wrapper, so it also moves text and graphics - that is the point: a shot,
// not a slideshow. `duration` defaults to the rest of the scene; `start` delays the move.
export const Camera: React.FC<{
  push?: [number, number];
  pan?: [number, number];
  panY?: [number, number];
  shake?: number;
  start?: number;
  duration?: number;
  curve?: (t: number) => number;   // easing of the move; ease.inOut = a slow documentary push (M5.5C)
  children?: React.ReactNode;
}> = ({push, pan, panY, shake = 0, start = 0, duration, curve, children}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, width, height} = useVideoConfig();
  const span = Math.max(1, duration ?? durationInFrames - start);
  const k = progress(frame, start, start + span, curve);   // 0 -> 1, clamped
  const scale = push ? lerp(push[0], push[1], k) : 1;
  const x = pan ? lerp(pan[0], pan[1], k) : 0;
  const y = panY ? lerp(panY[0], panY[1], k) : 0;
  const amp = shake * Math.min(width, height) * 0.001;
  const sx = amp ? Math.sin(frame / 9.1) * amp + Math.sin(frame / 3.7) * amp * 0.4 : 0;
  const sy = amp ? Math.cos(frame / 7.3) * amp + Math.cos(frame / 4.1) * amp * 0.4 : 0;
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <AbsoluteFill
        style={{
          transform: `translate(${(x + sx).toFixed(2)}px, ${(y + sy).toFixed(2)}px) scale(${scale.toFixed(4)})`,
          transformOrigin: '50% 50%',
          willChange: 'transform',
        }}
      >
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};


// Full-bleed footage or a still, with the graded layers a real shot needs (scrim, tint, vignette),
// and optional content on top. `asset` is a HANDLE from the manifest's assets table.
export const LayeredMedia: React.FC<{
  asset: string;
  scrim?: number;          // 0..1 dark gradient from the top: keeps text readable over footage
  tint?: string;           // theme colour washed over the picture (withAlpha)
  tintStrength?: number;   // 0..1, 0 = no wash
  vignette?: number;       // 0..1 darkening at the edges
  zoom?: number;           // static crop zoom of the source (1 = fit the frame)
  offsetX?: number;        // crop shift in px, applied after zoom (0 = centre)
  offsetY?: number;
  startFrom?: number;      // frames into the clip to start reading (one file serves many shots)
  playbackRate?: number;
  fallback?: React.ReactNode;  // drawn instead of throwing when no handle was staged (reference scene)
  children?: React.ReactNode;
}> = ({asset, scrim = 0.35, tint, tintStrength = 0, vignette = 0.5, zoom = 1, offsetX = 0,
      offsetY = 0, startFrom = 0, playbackRate = 1, fallback, children}) => {
  // useAsset() is called on EVERY render (never conditionally); only its error is caught, and only
  // when the scene brought its own fallback. A step that declared no handle still fails loudly.
  let info: AssetInfo | null = null;
  try {
    info = useAsset(asset);
  } catch (error) {
    if (fallback === undefined) throw error;
  }
  if (!info) {
    return <AbsoluteFill style={{backgroundColor: '#000'}}>{fallback}</AbsoluteFill>;
  }
  const src = staticFile(info.file);
  const shape: React.CSSProperties = {
    ...fill,
    objectFit: 'cover',
    transform: `translate(${offsetX}px, ${offsetY}px) scale(${zoom})`,
  };
  return (
    <AbsoluteFill style={{overflow: 'hidden', backgroundColor: '#000'}}>
      {info.kind === 'video' ? (
        <OffthreadVideo src={src} muted startFrom={startFrom} playbackRate={playbackRate} style={shape} />
      ) : (
        <Img src={src} style={shape} />
      )}
      {tint && tintStrength > 0 ? (
        <AbsoluteFill style={{...fill, background: withAlpha(tint, tintStrength)}} />
      ) : null}
      {scrim > 0 ? (
        <AbsoluteFill
          style={{
            ...fill,
            background: `linear-gradient(180deg, ${withAlpha('#000000', scrim * 0.35)} 0%, ${withAlpha('#000000', scrim)} 100%)`,
          }}
        />
      ) : null}
      {vignette > 0 ? (
        <AbsoluteFill
          style={{
            ...fill,
            background: `radial-gradient(ellipse at center, ${withAlpha('#000000', 0)} 42%, ${withAlpha('#000000', vignette)} 100%)`,
          }}
        />
      ) : null}
      {children}
    </AbsoluteFill>
  );
};
