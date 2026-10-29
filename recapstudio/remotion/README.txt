Remotion renderer for Recap Studio
==================================

recap.py is the brain; this folder is the renderer. A project's  timeline.json  is the contract
between them (written by the "timeline" step, see _template/timeline.py and src/types.ts).

You normally never run anything here by hand:
  SETUP.bat                  installs Node.js (if missing) and runs "npm install" in this folder.
  Project menu 23 / 24       "Build timeline.json" and "Render with Remotion -> recap_remotion.mp4".

Phase 0 played the already-fitted clips + voice + music (same picture as the ffmpeg video).
Phase 1 adds, on top of that: word-by-word captions (clean / bold / karaoke), chapter cards, lower thirds,
a rank stamp, a caption badge and transitions (cut, fade, whip, zoom, flash, glitch).
  src/captions/      caption looks          src/overlays/      chapter card, lower third, rank, badge
  src/transitions/   picture effects        src/layout.ts      16:9 / 9:16 safe zones
Change the look in the project's config.json ("captions", "transitions", "overlays", "accent", "font").
SFX and motion-graphic scenes come in later phases (see the gameplan).

Phase 2 adds SCENES: a segment's picture can be a scene instead of the footage clip.
  kit/                helper kit every scene is built from (easing, springs, counters, ring/bar/line charts, text reveal,
                      particles, narration sync). kit/CONTRACT.md is the full scene contract + kit reference.
  scenes_examples/    three hand-written reference scenes (stat_ring, timeline_reveal, quote_moment)
  src/scenes/         Keywords.tsx (the fixed fallback scene) and SceneHost.tsx (draws a scene, never lets one crash the render)
  src/SceneLab.tsx    Studio previews: one composition per scene
  src/generated/      written by scenes.py (the registry of checked scenes). Do not edit.
  tools/              check_scenes.mjs (static safety check) and test_scenes.mjs (single-frame test render)
Project menu 25 "Check scenes", 26 "Preview scenes" (Remotion Studio), 27 "Demo scenes" (3 good + 3 deliberately broken).
In segments.json:  "scene": "keywords"   or   "scene": {"type": "generated"}  (file scenes/<segment id>.tsx), optional
"motion": {"data": {...}, "cost": "low"} for the data the scene receives. A scene that fails its checks is replaced by the
keywords scene and SCENE_FIX_PROMPT.txt (error + code + contract) is written for Claude. config.json "scenes":
{"slate_to_keywords": true} controls whether a missing shot becomes the keywords scene (default) or the old slate card.
The static check guards against mistakes and obvious hazards in AI-written code (network, eval, outside imports, clocks).
It is not a hardened sandbox: scenes only ever run inside Remotion's headless browser, but read code you did not write.

Manual use (from this folder, after npm install):
  npm run studio             open Remotion Studio (scenes of the last checked project + the example scenes)
  npm run typecheck          type-check everything in src/, kit/ and scenes_examples/

The normal "Build full video" (ffmpeg) keeps working with or without Node installed.

License note: Remotion is free for individuals and teams of up to 3 people. Check
https://www.remotion.dev/docs/license before using it in a company.

Phase 3 adds the Scenes tab in the web UI (_template/authoring.py does the work):
  1. The movie prompt now lets Claude add  "motion": {"brief", "data", "cost"}  to some segments and a top-level "theme" to the script.
  2. Scenes tab > "Copy scene prompt": one prompt with the contract, kit, reference scenes, theme and all briefs. Paste it to Claude,
     paste the reply back ("// FILE: scenes/<id>.tsx" blocks). The scenes are saved to Projects/<name>/scenes/ and checked.
  3. A failed scene becomes the keywords scene; "Copy fix prompt" gives Claude the error and the code.
Menu: 28 = scene prompt (or import SCENE_REPLY.txt), 29 = demo briefs for a test project.
