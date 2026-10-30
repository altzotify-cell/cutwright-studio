// The helper kit: the ONLY thing generated scenes may import besides 'remotion' and 'react'.
//   import {AbsoluteFill, useCurrentFrame} from 'remotion';
//   import {SceneFrame, RingChart, ease} from '@kit';
// Reference: kit/CONTRACT.md

export * from './types';
export * from './theme';
export * from './motion';
export * from './shapes';
export * from './text';
export * from './charts';
export * from './particles';
export * from './SceneFrame';
// kit/2 (M5.5B): footage as a HANDLE. Components only - `useAsset` is private to kit/media.tsx, so no
// resolver reaches a scene (a scene names a handle; the engine maps it to a staged file).
export {LayeredMedia, Camera, AssetScope} from './media';
export type {AssetInfo, AssetTable} from './media';
export {makeLayout} from '../src/layout';
