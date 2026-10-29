// One place that knows about aspect ratio and safe zones (16:9 and 9:16), so no component hard-codes pixels.
// Later phases hand this same object to generated scenes as `layout`.

export type Layout = {
  width: number;
  height: number;
  portrait: boolean;
  u: number; // 1 at 1080 px on the short side: multiply font sizes / gaps by it
  safeSide: number; // px kept free left and right
  safeTop: number; // px kept free at the top (TikTok / Shorts UI)
  safeBottom: number; // px kept free at the bottom (their buttons and titles)
  captionBottom: number; // px from the bottom edge where the spoken captions sit
};

export const makeLayout = (width: number, height: number): Layout => {
  const portrait = height > width;
  const u = Math.min(width, height) / 1080;
  return {
    width,
    height,
    portrait,
    u,
    safeSide: Math.round(width * (portrait ? 0.07 : 0.06)),
    safeTop: Math.round(height * (portrait ? 0.1 : 0.06)),
    safeBottom: Math.round(height * (portrait ? 0.2 : 0.06)),
    captionBottom: Math.round(height * (portrait ? 0.24 : 0.09)),
  };
};
