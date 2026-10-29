# Recap Studio × Remotion: Movie Recap Gameplan

Oct 29, 2026 · @new · **Revision 9: Phases 0, 1 and 2 PASSED on your PC. Phase 3 (Claude-authored scene engine) is IMPLEMENTED and tested on the Python/UI side only; it needs your check on the PC (zip: RecapStudio-phase3.zip)**

**Revision 8:** Phases 0, 1 and 2 passed on your PC; Phase 3 was only scoped.

**Revision 7:** Phase 1 passed on your PC. Phase 2 is implemented and, unlike Phases 0-1, was **really rendered in my sandbox** (the npm registry and a Chromium were reachable this time): see the Phase 2 status block in section 7.

**Revision 3:** Phase 0 is implemented (see the Phase 0 status block in section 7). **Revision 2 changes:** the fixed scene vocabulary is no longer the main visual system. Structural pieces (captions, transitions, audio, lower thirds, avatar) stay as fixed, reliable components, while most explainer and motion-graphic scenes are now written by Claude as custom Remotion code, validated, cached and rendered. Sections 3, 4, 6, 7, 8 and 9 were updated; section 4b, the dynamic scene engine, is new.

## 1. Goal and scope

The goal is to turn Recap Studio (a local, free, Windows-first recap-video tool) into a versatile editor whose **movie recap** videos (retelling, commentary, mixed) look professionally edited: animated captions, motion graphics, transitions, sound design, and designed scenes instead of placeholder cards. Movie recap is the first module built end to end; the other modules (show recap, NBA mini-doc, NBA story, real story, ranking, comic recap) inherit the stack afterwards.

**"Professional" means, concretely:**

- Word-by-word animated captions burned into the mp4 (today captions exist only as an .srt).
- Lower thirds, chapter title cards, date/name stamps, and on-screen text that animates in and out.
- **Custom motion-graphic explainers written per scene** (stat breakdowns, timelines, comparisons, visual metaphors) so no two videos look templated.
- Transitions between segments (whip, zoom, glitch, flash) and camera motion on footage and stills.
- Sound design: automatic whooshes/impacts tied to graphics, SFX cues from the script, ducked music, consistent loudness.
- Designed fallback scenes when footage or a custom scene is missing or broken, so a gap never blocks the video.
- Real 9:16 layouts for TikTok/Shorts, not a blurred pad.
- A **theme that changes per movie** (look, colors, fonts, mood), not one fixed style.

**Out of scope for now:** paid services by default, cloud rendering, a mobile app, and rewriting the voice/TTS layer (it works).

**Hard constraints:** everything runs locally on Windows; free by default (Edge-TTS/Kokoro voices, free Freesound key, local Whisper, and Claude used through the user's own chat, no API required); the existing Premiere XML and VideoPad exports must keep working.

## 2. Where the project is today

Python is the brain and ffmpeg is the renderer. The new chat should attach the project zip (RecapStudio-main) again; these are the findings from reading it.

**Structure**

- `studio.py` (~1,500 lines): stdlib HTTP server and job runner behind the web UI in `web/` (app.js, index.html, guide.html).
- `_template/recap.py` (~5,400 lines): the whole pipeline in one file, run per project via numbered .bat steps and a menu. Each project is a copy of `_template/` with its own `config.json`, `project.json`, `segments.json`.
- `tts_worker.py`, `setup_engines.py`, `SETUP.bat`: voice engines (Edge, Kokoro, Pocket TTS, Chatterbox, ElevenLabs, MiniMax) installed into separate venvs.
- `_template/PASTE_THIS_TO_CLAUDE_*.txt`: one prompt per module telling Claude how to write `segments.json`.

**Data flow:** footage or subtitles in, Claude writes `segments.json` (id, src_start/src_end, narration, caption, chapter, shot, keep_audio, subtitle, speed, character fields), TTS makes `audio/<id>.mp3`, `build_items()` fits each clip to its voice-over length frame-exactly, then outputs: Premiere XML, VideoPad project, finished mp4 (`step_video`), TikTok mp4 (`step_tiktok`), .srt.

**Where the output is weak**

- Captions and number/caption graphics are **not burned into the mp4**; the code prints a note telling you to use the Premiere XML for them.
- Graphics are ffmpeg `drawtext` boxes written to a transparent qtrle .mov (`render_gfx`), which is plain.
- Subtitle cue timing is estimated from character counts, not real word timings.
- Missing footage becomes a "MISSING SHOT" slate card (`render_slate`).
- Stills get one slow zoom (`zoompan`); the comic module has its own PIL-based camera.
- Character animation (~700 lines, `CHARACTER ANIMATION` section) builds PIL sprites and multi-GB transparent layers.
- No SFX system at all; music is a single looped bed at fixed volume.

**What is already good and should be kept:** frame-exact timing from the audio, the clip cache, the multi-engine TTS and key pool, the Premiere/VideoPad exporters, `credits.txt` for collected footage, the review/export-import pattern for narration, and the prompt-per-module approach.

## 3. Target architecture

Python stays the brain; Remotion becomes the renderer; a single `timeline.json` is the contract between them. Every module is a recipe that produces a timeline, and every output reads it. The visual layer is **hybrid**: a fixed structural layer plus a dynamic, Claude-written scene layer.

1. **Script layer (pass 1):** Claude writes `segments.json` from a per-module prompt. Segments that deserve a custom motion graphic carry a short `motion` design brief (not code). Validated against a JSON Schema before anything renders.
2. **Scene authoring layer (pass 2, new):** a second prompt takes the briefs, the theme and the scene contract, and Claude returns one `.tsx` scene file per brief. The tool saves them to `remotion/scenes_generated/`, validates each, and falls back safely on failure (section 4b).
3. **Voice layer (unchanged):** TTS produces audio per segment; word timings are captured (Edge-TTS word boundaries, otherwise local Whisper on the generated audio).
4. **Asset providers:** footage (existing collect step), images, music, and SFX behind one provider interface, with a local cache and license tracking.
5. **Timeline builder (Python):** extends `build_items()` to write `timeline.json`: per segment the frame count, audio and video file paths, text, word timings, scene reference (fixed component or generated file), transitions, SFX cues, chapter and caption data, plus project-level theme and fps/size.
6. **Renderer (Remotion):** a `remotion/` folder (separate from `recap.py`) with a main composition that maps timeline entries to fixed structural components or to generated scene files. Render via the Remotion CLI.
7. **Exporters:** Remotion mp4 (YouTube 16:9 and TikTok 9:16 layouts), the existing ffmpeg path as a fallback, and the Premiere XML / VideoPad exports, which gain the new overlay and SFX tracks.
8. **UI and preview:** the existing web UI triggers the new steps; Remotion Studio (or the embedded Player) previews a single scene so it can be tweaked and the fix pasted back to Claude.

**Rendering strategy:** start overlay-first (Remotion renders captions and graphics as a transparent layer that ffmpeg composites; this slots into the existing V2 graphics track and keeps the Premiere/VideoPad exports valid), then move to a full Remotion render of the whole video once the scene engine is stable. Remotion renders frame by frame in headless Chromium, so long 1080p videos are slower than ffmpeg; overlay-first avoids that cost early. On the target machine (i5-8350U, 12 GB RAM, no discrete GPU) this matters even more, so dynamic scenes carry a cost budget (section 4b).

**Code hygiene:** do not grow `recap.py`. Put new code in `remotion/`, a `timeline.py` module, a `scenes.py` module (authoring, validation, cache) and a `providers/` package, with thin bridge steps added to the menu and UI.

## 4. Anatomy of a professional movie recap

### 4a. Structural layer (fixed components, written once)

These are repetitive, functional pieces where reliability matters more than novelty. Claude references them by name and never rewrites them.

**Structure of the video**

- **Cold-open hook (first 10-15 s):** the strongest moment or a question, kinetic title text, a riser SFX, then a title card with the movie name.
- **Chapters/acts:** chapter card with act number and title, optional progress bar along the bottom.
- **Closing:** verdict or takeaway card, an end screen slot, and a subscribe/next-video animation.

**Fixed components**

| Component | Use | Notes |
| --- | --- | --- |
| `footage` | Normal clip with the narration over it | Slow push-in or drift, optional vignette/grade, letterbox option |
| `footage_pip` | Commentary beats: clip shrinks into a frame over a background | Replaces the character corner for commentary |
| `still` | Poster, photo, screenshot | Parallax or Ken Burns with proper easing, not `zoompan` |
| `title_card` | Hook, chapter, film title | Kinetic typography driven by the theme |
| `character_avatar` | Optional commentary presenter | Simple Remotion component; the qtrle pipeline can retire |
| `keywords` | Safe fallback scene | Narration key words animate over a themed background; also replaces the MISSING SHOT slate |

**Always-on layers**

- Word-level captions with a highlighted current word; two or three theme styles (clean, bold, karaoke); safe-zone aware for 9:16.
- Lower thirds for character names the first time they appear.
- Grain/vignette and gentle color grade, off by default for clean clips.

**Transitions:** cut, crossfade, whip pan, zoom punch, glitch, flash-white, slide; chosen per segment with an `auto` default so Claude only sets them for emphasis.

**Pacing rules the scripts should follow:** a visual change at least every 3-5 seconds (a new scene, a zoom, a caption emphasis), the biggest SFX on the biggest beats only, and music ducked about 12-18 dB under the voice.

### 4b. Dynamic scene engine (Claude-written, per scene)

Most of the meat of the video (explainers, stat breakdowns, timelines, versus comparisons, quote moments, visual metaphors, fact cards) is **not** a template. Claude designs and codes each one for the specific line it covers. The old fixed `quote_card`, `fact_card`, `timeline` and `versus` templates become optional **example scenes** that ship in the helper kit as reference, not a vocabulary Claude is limited to.

**Two-pass authoring flow**

1. **Pass 1, script:** Claude writes `segments.json`. Where a segment deserves a custom graphic it adds `motion`: a one-to-three sentence design brief plus the data to show (for example `{"brief": "circular ring fills to 70%, pulsing red, recoil icon drops", "data": {"value": 70, "label": "players affected"}, "cost": "low"}`).
2. **Pass 2, scenes:** the tool exports all briefs, the theme and the scene contract as a paste-ready prompt. Claude returns one `.tsx` file per brief. The tool imports the batch into `remotion/scenes_generated/<project>/<segment_id>.tsx`.

**Scene contract (every generated scene follows it)**

- A default-exported React component receiving `{ durationInFrames, fps, width, height, props, theme, words, layout }` where `words` are the word timings (so scenes can sync to the narration) and `layout` carries the 16:9 / 9:16 safe zones.
- Imports allowed only from `remotion` and a whitelisted helper kit (`remotion/kit/`): easing and spring presets, shape and path helpers, animated counter, bar/ring/line chart primitives, text-reveal helpers, particle helper, theme accessors. No other packages.
- Must render correctly at any duration and in both aspect ratios, using `layout` instead of hard-coded pixel positions.
- Must declare a `cost` (`low`, `medium`, `high`) so heavy effects (many particles, blur, large SVG filters) are rationed on the target machine.

**Validation and fallback (nothing blocks the video)**

- Static check: reject network calls, filesystem access, `eval`/`Function`, dynamic imports, and any import outside the whitelist.
- Compile check, then a **single-frame test render** at a few sample frames (start, middle, end). A thrown error or an all-blank frame counts as a failure.
- On failure the tool substitutes the `keywords` scene for that segment, logs a plain message ("segment cm_014: scene failed, `Cannot read properties of undefined`"), and writes a paste-ready fix prompt for Claude containing the error and the failing code.
- Validation results are shown in a short review list in the UI; the user can retry, swap to the fallback, or open the scene in Remotion Studio.

**Cache and review**

- Scenes are cached by a hash of (brief, data, theme, duration, kit version) so unchanged scenes are never re-authored or re-rendered.
- Generated code is saved as plain files in the project so the user can read, hand-edit, or ask Claude to revise a single scene; code is never executed without passing the static check.

**Theme per movie**

- A small `theme.json` (palette, fonts, caption style, motion energy such as calm / punchy / chaotic, grain and grade, sound theme) is chosen or generated per movie. Claude may propose one from the film's tone in pass 1; the user can edit it. The fixed components and the scene-authoring prompt both read it, so the whole video changes look from one file.

## 5. SFX and asset system

One provider interface (search, filter, fetch, cache, credit) serves SFX first, then music, stock video and images. Details of Freesound's API and license rules are from memory; verify against its current docs before building.

**Freesound (primary SFX source)**

- Needs a free API key, stored in `keys.env` through the existing key mechanism. Search and previews work with the key; downloading original files needs OAuth2, so design around previews first.
- Default license filter: CC0 and CC-BY only. Non-commercial licenses are excluded because they conflict with monetized YouTube. CC-BY hits are written to the project's `credits.txt` automatically.
- Respect rate limits (cache aggressively, never re-download the same sound).

**Local library**

- A bundled starter pack of about 50 CC0 essentials (whoosh, impact, riser, tick, glitch, camera shutter, crowd, buzzer, heartbeat, record scratch) so the tool works offline.
- A global SFX index (tags, duration, license, source id, loudness) shared across projects; fetched sounds are added to it.
- Every imported sound is loudness-normalized with ffmpeg so levels are consistent.

**How sounds get chosen**

- **Sound themes:** each module has a theme mapping events to sounds (transition to whoosh, title card to impact, caption pop to tick, chapter card to riser). Most SFX are automatic and need no script input.
- **Semantic cues from Claude:** `"sfx": [{"cue": "door slam", "at": "start", "vol": 0.8}]`. `at` accepts `start`, `end`, seconds into the segment, or a word index. The tool searches, filters by license/duration/rating, and picks one.
- **Dynamic scenes can emit cues:** a generated scene may declare named audio hooks (for example `hits: [{frame: 24, cue: "impact"}]`) that the timeline builder turns into SFX cues, so sound lands exactly on the animation beat.
- **Review step:** like the narration export/import, an SFX review lets the user audition and swap picks before rendering.

**Mixing**

- Voice on top; music ducked under it (sidechain-style, fixed amount is acceptable at first); SFX on their own bus with per-cue volume.
- In Remotion, each cue is an `<Audio>` element at the right frame. In the Premiere/VideoPad exports, SFX become an extra audio track.

**Other providers later:** music (a curated local folder first; Free Music Archive or Jamendo only after checking license terms), stock video and images (Pexels, Pixabay), all behind the same interface and the same license filter.

## 6. The timeline contract and segment schema

Two files matter: `segments.json` (what Claude writes) and `timeline.json` (what Python derives and Remotion renders). Keep them separate so Claude's vocabulary stays small while the renderer gets everything resolved.

**New segment fields Claude may write (all optional, backward compatible)**

- `scene`: a fixed component from section 4a (for example `title_card`, `footage_pip`, `still`, `keywords`), with a small `props` object.
- `motion`: a design brief for a **dynamic scene** (section 4b): `brief` (short text), `data` (values/labels to show), `cost` (`low`/`medium`/`high`), optional `style_notes`. Claude writes the brief in pass 1 and the code in pass 2.
- `transition`: `auto` (default) or one of the named transitions.
- `sfx`: list of cues as in section 5.
- `emphasis`: list of words to highlight in captions.
- `lower_third`: name and role text for a character's first appearance.
- Existing fields stay as they are: `src`, `src_start`, `src_end`, `image`, `caption`, `chapter`, `keep_audio`, `subtitle`, `speed`, and `shot`.

**What `timeline.json` adds (derived, never written by Claude)**

- Project level: fps, width, height, theme (from `theme.json`), total frames, music bed file and ducking, kit version.
- Per segment: id, start frame, duration in frames, resolved video and audio file paths, display text, word timings, resolved scene (fixed component name, or path to a validated generated scene plus its cost), resolved transition, resolved SFX file paths with frame offsets, chapter flag.

**Validation:** a JSON Schema checks `segments.json` before the voice step. Errors come back as plain messages the user can paste to Claude ("segment cm_014: unknown scene type quote"). Unknown fields are warnings, not failures, so old projects keep working. Generated scene files have their own validation (section 4b).

**Prompt updates:** `PASTE_THIS_TO_CLAUDE_movie_recap.txt` gains a graphics-and-SFX section with rules like "use `motion` on roughly a third of segments at most", "always include a hook segment first", "keep `cost` honest". A new prompt, `PASTE_THIS_TO_CLAUDE_scene_authoring.txt`, carries the scene contract, the kit reference, example scenes and the theme.

## 7. Phased build plan

Each phase ends with something runnable and a check the user can verify. Do not start a phase until the previous check passes. Work on one real movie-recap project throughout.

1. **Phase 0: Foundation and parity.**
   - Add `timeline.py` that writes `timeline.json` from `build_items()`; add the `remotion/` scaffold (Node and Remotion install added to `SETUP.bat`, headless browser downloaded on first render).
   - A single `MovieRecap` composition plays footage, voice and music from the timeline.
   - *Check:* the Remotion mp4 matches the current ffmpeg mp4 in length (within one frame) and audio sync on a 2-minute test project.

**Phase 0 status: PASSED the length check on your PC (2nd run); two things left to eyeball**

*What was added (all in the updated RecapStudio zip):*

- `_template/timeline.py` (new): builds `timeline.json` from `build_items()`, stages the files Remotion needs into `remotion_public/` (hard links, so no extra disk space; falls back to copying), validates it (every file exists, every clip and voice file matches its frame count, segment starts add up), and runs the Remotion render with a length check. Plain-English problem list you can paste to Claude.
- `_template/recap.py`: only a thin bridge (two small functions + two entries in `STEPS`): `timeline` and `remotion`. Nothing else in the 5,400 lines changed.
- `_template/4f_build_timeline.bat`, `4g_render_remotion.bat`, and menu items 23 and 24 (movie/show recap modules).
- `remotion/` (new, lives once next to `studio.py`, shared by all projects): `package.json`, `tsconfig.json`, `remotion.config.ts`, `src/index.ts`, `src/Root.tsx`, `src/MovieRecap.tsx`, `src/types.ts`, `README.txt`. The `MovieRecap` composition takes its length, size and fps from `timeline.json` and plays each segment's clip + voice (+ ducked original sound) with the music bed underneath.
- `SETUP.bat`: new optional step 4/4 that installs Node.js with winget if missing and runs `npm install` in `remotion/`. Failure there never blocks the rest of setup.
- `studio.py` + `web/app.js`: the two new steps appear in the web UI step list ("Build timeline.json", "Render with Remotion").
- `.gitignore`: ignores `remotion/node_modules/`.

*How Phase 0 works:* it deliberately reuses the already-rendered, frame-exact clips from `build_items()` (same flags as "Build full video": characters baked in, no ffmpeg graphics layer). That makes the parity check meaningful and low risk. Remotion output goes to `recap_remotion.mp4`, so `recap_final.mp4` and the Premiere/VideoPad exports are untouched.

*Tested here (sandbox, Python side):* a demo project with 6 segments (video, still, slate, characters, a held last frame) produced `timeline.json` with 514 frames (21.42 s at 24 fps); the validator passed; the existing ffmpeg "Build full video" gave 21.42 s, i.e. exactly the same 514 frames. The new step also fails with a clear message when Node or Remotion is missing.

*NOT tested (important):* the package registries were not reachable from the sandbox, so Remotion could not be installed. The TypeScript/React files have not been type-checked or rendered. Expect possible small fixes on the first real run (for example a Remotion version or CLI flag detail).

*Your Phase 0 check (on your HP, about 10 minutes):*

1. Replace your RecapStudio folder files with the updated zip (keep `Projects/` and `keys.env`), run `SETUP.bat` (it installs Node.js and Remotion). If Node was just installed, close the window and run `SETUP.bat` again.
2. Make a fresh project and run menu 18 (demo/test media; it makes its own audio, so skip the voice step). Then run menu 5 (Build full video), then menu 24 (Render with Remotion). The first render downloads a headless browser.
3. Pass = the console prints `PARITY CHECK PASSED` and `within one frame` against `recap_final.mp4`, and `recap_remotion.mp4` plays with the voice in sync.
4. Then try a real 2-minute project the same way and note the render time on your i5.
5. If anything fails, paste the full console text to Claude.

*First run on your PC (result):* `SETUP.bat`, `npm install`, the headless browser download, bundling (public folder copy was only 11.2 MB) and the start of the render all worked. The render then stopped at frame 71 with `No frame found at position` for `clips/d_01.mp4`. Remotion's docs say the most likely cause is the OffthreadVideo memory cache being too small, which fits a 12 GB laptop decoding two frames at once. I checked the clip itself and it is normal (77 frames, correct timestamps), so the clips are not the problem.

*Safety net shipped in zip v2 (not yet exercised):* the render now passes `--offthreadvideo-cache-size-in-bytes` (1024 MB by default) and, if the first attempt fails, automatically retries with 1 parallel frame and a 1536 MB cache. Both are adjustable in `config.json` under `"remotion": {"concurrency": 2, "cache_mb": 1024}`. If this still fails, next options are: re-encode the staged clips without B-frames, or switch the video tag to `<Video>` from `@remotion/media` (the component Remotion now recommends for new projects).

*Also noted:* the project path contained a space (`Projects\test remotion`), and it worked.

*Second run on your PC (result):* it rendered all 514 frames and printed `PARITY CHECK PASSED`: `recap_remotion.mp4` is 21.42 s, expected 21.42 s, and within one frame of `recap_final.mp4`. Render time was 1.5 minutes for the 21-second demo, with 2 parallel frames and a 9.8 MB output.

*Important detail:* that log was produced by the first zip (it still shows the old "2 parallel frames" message and no cache flag), so the first-run failure at frame 71 was **not** fixed by my cache change. It was most likely a one-off on the very first run (browser download and bundling happening at the same time, with a cold cache). The v2 retry-with-bigger-cache protection is still in the zip and is harmless, but it has not been exercised yet; treat the error as "can come back, and the tool now retries automatically".

*What the numbers mean for planning:* about 5.7 frames per second on your i5 means roughly 4x slower than real time. A 10-minute 24 fps video (14,400 frames) would take about 40-45 minutes as a full Remotion render, and heavier graphics will make it slower. This confirms the overlay-first plan: from Phase 1 on, Remotion should render only the overlays (captions, graphics, transitions) and let ffmpeg handle the footage, with per-segment caching. Remotion's concurrency can also be tested at 3 on your machine later.

*Still to check by eye (the log can only prove length):* open `recap_remotion.mp4` next to `recap_final.mp4` and confirm the picture plays, the voice and the footage's own sound are in sync, and the character/slate segments look the same. Tell me if anything is off before we start Phase 1.

*Things found while building (decisions for the next phases):*

- **License verified (current terms):** Remotion's free license covers individuals (including commercial use) and teams of up to 3 people. Paid plans start at about $25/month per person for companies; verify again if the project ever becomes a company or is shared as a product.
- **Remotion version is not pinned** (`^4.0.0`). After the first successful install, pin the exact version in `package.json` (Remotion and `@remotion/cli` must match).
- **`--public-dir` behavior:** the bundler may copy the public folder. Only the fitted clips, voice, and music are staged (not your raw footage), so it should stay small; measure on the real project. If it is slow, switch to serving files over a local HTTP server.
- **Captions and rank/number graphics** are still not visible in `recap_remotion.mp4`. That is Phase 1 by design.
- **Word timings** (`words`), `scene`, `transition` and `sfx` already exist as empty fields in `timeline.json`, so later phases do not change the contract.

**Phase 1 status: PASSED on your PC ("phase 1 test went well"). Details of what was built are kept below.**

*What was added:*

- `_template/wordtimes.py` (new): word timings per segment, cached in `words/<id>.json`. Source order: Edge-TTS word boundaries (saved while the voice is made, shifted by the leading silence that `fit_audio` trims), then local `faster-whisper` on the fitted voice file (model `base`, CPU), then an estimate from the text. Timed words are matched to the caption text with difflib, so a `subtitle` respelling still works.
- `_template/recap.py`: only the Edge runner (streams the audio and saves the boundaries) plus a `CUR_SEG_ID` global set by the voice step. Existing Edge audio has no boundaries, so those segments use Whisper or the estimate until you re-voice them (menu 3 with the force option) or install faster-whisper.
- `_template/timeline.py`: schema 2. Adds per segment `words` (frames), `wordMethod`, `chapterStart/Index`, `lowerThird`, resolved `transition` + `transitionFrames`; top-level `style` from config.json. Validator checks word order and transition names.
- `remotion/src/`: `captions/Captions.tsx` (clean, bold, karaoke; 9:16 aware), `overlays/Overlays.tsx` (chapter card, lower third, rank stamp, caption badge), `transitions/transitions.tsx` (fade, whip, zoom, flash, glitch), `layout.ts` (safe zones), updated `MovieRecap.tsx` and `types.ts`.
- `config.json` template: `captions`, `transitions`, `overlays`, `accent`, `font` blocks. `SETUP.bat` installs faster-whisper (optional). The movie recap prompt documents `emphasis`, `transition`, `lower_third`.

*Design decision:* clips are exactly as long as their voice-over, so transitions cannot overlap two clips without breaking the sync. They are picture effects on the last frames of the outgoing clip and the first frames of the incoming one (voice and music untouched). A true crossfade needs extra footage handles; revisit when the render goes overlay-only.

*Tested here:* Python side on the demo project (6 segments): timeline.json written and validated, Edge-boundary path (with a fake boundary file), estimate path, alignment cases. TypeScript type-checked against stubbed Remotion/React typings (clean). *NOT tested:* an actual Remotion render (registries unreachable from my sandbox), so expect small fixes on the first run.

*Your Phase 1 check:* (1) replace the files with the new zip, run SETUP.bat. (2) New project, menu 18 (demo), then edit `segments.json` to add `chapter`, `transition` (glitch, zoom, flash, fade, whip) and `lower_third` on a few segments. (3) Menu 23 then 24. (4) Watch `recap_remotion.mp4`: captions highlight word by word in sync, chapter card appears on chapter starts, each transition plays. (5) Change `captions.style` to `bold` and `clean` in config.json and re-render. (6) Then a real 3-minute project with Edge voice; check for drift at the end. Paste any console error to Claude.

2. **Phase 1: Captions, overlays and transitions (structural layer).**
   - Capture word timings (Edge-TTS boundaries; Whisper fallback). Build animated captions, lower thirds, chapter cards, and 4-5 transitions. Burn everything into the mp4.
   - *Check:* a 3-minute recap with word-highlight captions, chapter cards and transitions renders with no sync drift, and the caption style can be switched in `config.json`.
**Phase 2 status: PASSED on your PC (zip: RecapStudio-phase2.zip). 3 good scenes passed; crash / network / blank scenes were caught and replaced by the keywords scene; Check scenes re-run took a few seconds (cache); render 1.1 min for the 21 s demo. After fixing d_04-d_06 all 6 scenes passed. The 'scene never changes' notes on those fixed scenes are only warnings.**

*What was added:*

- `remotion/kit/` (new): the helper kit scenes are built from: `types.ts` (the scene contract: `SceneProps`, `Theme`), `theme.ts`, `motion.ts` (easing, springs, `progress`, `useEntrance`), `shapes.tsx` (paths, `DrawPath`), `text.tsx` (`RevealText`, narration sync: `wordStart`, `findWords`, `spokenIndex`), `charts.tsx` (`AnimatedCounter`, `RingChart`, `BarChart`, `LineChart`), `particles.tsx` (deterministic, capped at 80), `SceneFrame.tsx` (themed background + `contentBox` safe area), `CONTRACT.md` (the contract and kit reference; it is also appended to the fix prompt).
- `remotion/scenes_examples/` (new): three hand-written reference scenes: `stat_ring`, `timeline_reveal` (horizontal in 16:9, vertical in 9:16), `quote_moment`.
- `remotion/src/scenes/Keywords.tsx` (the fixed fallback scene: the strongest narration words pop up exactly when spoken) and `SceneHost.tsx` (draws a scene; a React error boundary swaps a scene that still crashes at render time for the keywords scene, so a render never stops).
- `remotion/src/SceneLab.tsx` + `Root.tsx`: Remotion Studio compositions, one per scene (`scene-<segment id>`, `example-<name>`), `portrait` prop for 9:16. `src/generated/registry.ts` is written by `scenes.py` (an empty default ships).
- `remotion/tools/check_scenes.mjs`: static check with the real TypeScript compiler (AST, not regex): allowed imports only (`remotion`, `react`, `@kit`), no network/URLs, `eval`/`Function`/dynamic import, DOM, timers, `Date`, `Math.random`, banned Remotion exports (`Audio`, `Img`, `staticFile`...), syntax errors, kit names that do not exist, missing default export, `cost`.
- `remotion/tools/test_scenes.mjs`: bundles once, one browser, renders start / 40% / 75% / last frame at the project shape and one frame at the other aspect ratio. `scenes.py` then judges the PNGs: an error, an all-one-colour frame, or "middle frames look the same as the empty background" = failure. The PNGs stay in `scenes/_checks/` so you can look at them.
- `_template/scenes.py` (new module, `recap.py` only got two thin bridge functions): collects scene requests, cache (hash of code + data + theme + length + words + kit), staging, registry, the two Node tools, fallback, `scenes_report.json`, `SCENE_FIX_PROMPT.txt`, the demo installer.
- `timeline.py`: one call (`scenes.resolve`) after the timeline is built; segments get `scene` = `footage` | `keywords` | `generated`; `config.json` `remotion.browser_executable` is optional.
- New menu items / UI steps: 25 Check scenes, 26 Preview scenes (opens Remotion Studio), 27 Demo scenes.
- `package.json`: Remotion pinned to exact `4.0.539` (`remotion`, `@remotion/cli`, `@remotion/bundler`, `@remotion/renderer`); `@types/node` added. `remotion.config.ts` adds the `@kit` alias.

*How a scene gets into a video:* `segments.json` segment gets `"scene": {"type": "generated"}` (file `scenes/<segment id>.tsx`, or `"file": ...`) and optionally `"motion": {"data": {...}, "cost": "low"}` (the data becomes the scene's `props`). `"scene": "keywords"` forces the fallback. Phase 3 will let Claude write the `motion` briefs and the scene files; Phase 2 is the safe runtime for them.

*Decisions made (all easy to undo):*

- **Scene source of truth is the project** (`Projects/x/scenes/<id>.tsx`, so it travels with the project and you can hand-edit it); `scenes.py` mirrors the checked ones into `remotion/src/generated/` for bundling. (The gameplan said `remotion/scenes_generated/<project>/`; this is simpler and project-local.)
- **A missing shot (slate) now becomes the keywords scene by default** (section 4a said it replaces the MISSING SHOT card). Set `"scenes": {"slate_to_keywords": false}` in `config.json` for the old card.
- **`theme.json` is already read** (palette, fonts, energy) because the scene contract needs a theme. Generating/editing it is still Phase 3.
- A scene without `export const cost` is a warning (assumed `medium`), not a failure, to keep the first-try pass rate high; cost budgeting is still Phase 6. `react` is allowed as an import next to `remotion` and `@kit` (hooks need it).
- Studio preview includes scenes that fail the test render (so you can open them and see the real error) but never ones that fail the static check.
- Honest limit: the static check catches mistakes and obvious hazards in AI-written code; it is not a hardened sandbox (scenes only run inside Remotion's headless browser, never with Node access).

*Tested here (real, not stubs):* `npm install` of the pinned versions; `tsc` clean against the real Remotion types (this also type-checked all Phase 1 code for the first time); real renders of all three reference scenes at 16:9 and 9:16 (looked at the frames); the static checker against 12 good/bad scenes including false-positive traps (a local variable named `top`, the word "fetch" in text, a `.fetch` property); the whole pipeline on a demo project (menu 18, then 27, then 23): 3 reference scenes pass, the crashing scene (`Cannot read properties of undefined (reading 'map')`), the network scene (blocked, never run) and the blank scene are replaced by the keywords scene with plain messages; second run is served from the cache; the fix prompt is written; a full 21 s Remotion render with captions, chapter card, rank stamps and badges on top of scenes, parity check passed; Studio starts and serves with the right scenes; Node missing = scenes fall back with a clear reason; a project without scenes behaves as in Phase 1 (only the slate becomes keywords).

*Bugs the real run caught (would have failed on your PC):* `__dirname` inside `remotion.config.ts` points into Remotion's CLI folder (the `@kit` alias is now relative to the working directory); the ring glow was clipped to a square; a detached Studio process kept the output pipe open (would have hung the web UI job).

*NOT tested:* Windows specifics (a new console window for Studio, `winget`), your real Edge voices, how long the test render takes on your i5 (the bundle took 14 s here with 1 CPU; the 5-scene test render is a one-off per changed scene thanks to the cache), the Studio UI in an actual browser (only that it serves and compiles).

*Your Phase 2 check (about 10 minutes):*

1. Replace the files with the new zip (keep `Projects/` and `keys.env`), run `SETUP.bat` (npm installs the pinned Remotion; close and reopen if it asks).
2. New project, menu 18 (demo), then menu **27** (Demo scenes), then menu 23. Pass = the console lists 3 scenes `[ok]`, and `[FAILED]` (crash), `[BLOCKED]` (network) and `[FAILED]` (draws nothing) each with a readable message and "the keywords scene is used"; `SCENE_FIX_PROMPT.txt` exists; running menu **25** again is instant.
3. Menu 24: watch `recap_remotion.mp4`: the good scenes play under captions and overlays, the broken ones show the keywords fallback, no render error.
4. Menu **26**: Remotion Studio opens; click `scene-d-02`, then tick `portrait` in the props panel for the 9:16 look; also open `example-quote-moment`.
5. Open `scenes/d_04.tsx`, fix it (or paste `SCENE_FIX_PROMPT.txt` to Claude and save its answer over the file), run menu 25: it should pass now.
6. Note how long menu 25 takes on the HP for the first run. Paste any console error to Claude.

**Open item (not Phase 2):** on your PC Whisper fails on every segment with `open() got an unexpected keyword argument 'metadata_errors'`, so captions use estimated timings for non-Edge voices. Likely cause: `av` (PyAV) older than faster-whisper expects. Try `py -3 -m pip install --upgrade av faster-whisper`, rebuild the timeline, look for `word timings ...: whisper`. Edge-TTS timings are exact either way. Untested guess.

**Phase 3 status: IMPLEMENTED, waiting for your check (zip: RecapStudio-phase3.zip)**

*What was added:*

- `_template/authoring.py` (new, standard library only, takes folders so both `studio.py` and `recap.py` use it):
  - `validate_script`: plain-English messages for bad `motion` (not an object, `data` not an object, cost not low/medium/high), duplicate or unsafe ids, unknown transition or scene type, more than about a third of segments with a brief, TikTok briefs (ignored for now).
  - `apply_theme`: the script's top-level `theme` becomes `theme.json` (colours must be `#rrggbb`, energy calm/punchy/chaotic, unknown keys dropped). A `theme.json` you made or edited is never overwritten: the proposal goes to `theme.proposed.json`.
  - `build_prompt`: ONE pass-2 prompt (role, output format, design rules, theme, every brief with data, narration, measured length and its neighbours, `CONTRACT.md`, the three reference scenes). Scenes already written and still matching their brief are skipped unless forced. Also written to `SCENE_AUTHORING_PROMPT.txt`.
  - `import_reply`: finds the code blocks in Claude's reply (`// FILE: scenes/<id>.tsx` first line, or a path on the line above, or no fences at all), accepts only safe `<id>.tsx` names inside `scenes/`, moves the old version to `scenes/_old/`, records which brief each scene was written for (`scenes/_authoring.json`) so a later brief or theme change shows as **stale**.
  - `status`, `action` (retry check, use keywords instead / use the scene, write again), `demo_briefs`.
- `_template/PASTE_THIS_TO_CLAUDE_scene_authoring.txt` (new) and a **graphics section** in `PASTE_THIS_TO_CLAUDE_movie_recap.txt` (`motion` brief format with examples, "a third at most", "never on the hook or the best action", honest cost, the `theme` object, Windows-safe fonts).
- `_template/scenes.py`: a `motion` brief alone now implies a generated scene; a scene that is not written yet is the new status `pending` ("[NOT WRITTEN]", not counted as a failure, not in the fix prompt) and falls back to the keywords scene.
- `_template/recap.py` (thin): `has_motion_scene()` so motion segments are no longer listed as "missing footage" or sent to the footage collector; new step `briefs` (writes the prompt, imports `SCENE_REPLY.txt`, `--demo` adds demo briefs). Menu 28 and 29, `4k_scene_prompt.bat`, `4l_demo_briefs.bat`.
- `studio.py`: `GET/POST /api/projects/<n>/scenes[...]` (status, prompt, import, action, demo, fixprompt); the paste import now returns the script check and theme messages; "sync" also copies the helper modules.
- `web/`: new **Scenes** tab (movie and show recap only): how-it-works, theme line, "Copy scene prompt", "Copy fix prompt", a paste box that imports and then runs the check automatically (when `timeline.json` exists), a card per scene with state badge, brief, message, test-frame thumbnails, and Check again / Use keywords instead / Write again; Check scenes, Open in Remotion Studio, Add demo briefs. The Script tab shows a "Script check" popup after importing a script, with a "Copy as a message to Claude" button.

*Decisions made (easy to undo):* the scene prompt is built by the tool and copied from the UI (no separate pass-2 paste file); one reply can contain any number of scenes; scenes in the Premiere / VideoPad / ffmpeg exports still show the normal placeholder (they exist in the Remotion render only); `CONTRACT.md` and the kit were not changed, so Phase 2 scene results stay cached.

*Tested here (real):* the whole Python side on a demo project (validation cases, theme handling incl. "do not overwrite", prompt export with skip-done logic, reply parsing with CRLF / odd fence labels / unfenced replies / path-traversal names, import + stale detection, actions); the server endpoints over HTTP (demo briefs, status, prompt, paste with problems); `recap.py briefs` and `missing` from the command line; `scenes.resolve` with a not-yet-written scene; `node --check` on `app.js`.

*NOT tested (important):* no real Claude round trip; no Remotion install (registry unreachable), so no static check or test render of an AI-written scene in this build; the new tab in an actual browser (only that the page and script load and parse). Expect small UI fixes. Known risk: Claude will sometimes use a wrong kit prop name (a sample scene I wrote while testing guessed `value` instead of `to` and `box.x` instead of `box.left`). That is exactly what the check, the fallback and the fix prompt are for; the 80% pass rate has to be measured on your PC.

*Your Phase 3 check (about 20 minutes; the UI, not the menu):*

1. Replace the files with the new zip (keep `Projects/` and `keys.env`), restart `START_UI.bat`. No `SETUP.bat` needed (no new packages). Make a **fresh** project (it needs the new modules); existing projects: click the project's "sync" first.
2. Run steps: **Demo / test media**, then **Build timeline.json**. Scenes tab: **Add demo briefs (test)** (3 briefs and a "demo noir" theme appear). Run **Build timeline.json** again so the lengths are known.
3. Scenes tab: **Copy scene prompt**, paste it into a NEW Claude chat, paste Claude's whole reply into the box, **Import scenes and check them**. Pass = the console runs Check scenes and the cards show `passed` (or `failed: fallback used` with a readable reason) with thumbnails. Note how many of the 3 passed first try.
4. If any failed: **Copy fix prompt**, paste to Claude, paste the answer back (same box), import again. Pass = all pass after one round.
5. Run steps: **Render with Remotion**; the scenes should use the demo noir colours under the captions.
6. Real film: ask Claude for the script with the movie prompt (it now asks for `motion` and `theme`), paste it on the Script tab (read the Script check popup), then steps 2 to 5 again. Do it for a second, very different film and compare the looks.
7. Paste any console error or odd screen to Claude.

**Phase 3 prep notes (scoped before building; now implemented as described above):**

- The UI is the web app, not the numbered menu: write checks as card names (Run steps tab), not menu numbers. Tabs live in `web/index.html` (`#tabs`), rendered by `renderTab()` in `web/app.js`; the Script tab already has "Copy prompt" and "Paste Claude's reply" patterns to copy.
- `studio.py normalize_segments` keeps unknown fields, so `motion`, `scene` and a top-level `theme` in Claude's JSON survive the paste import. Project files can be served to the UI via `/api/projects/<name>/file/<path>` (PNG thumbnails of `scenes/_checks/` work).
- Planned Phase 3 pieces: `authoring.py` (script validation with plain messages, theme.json from Claude's `theme` key, scene-authoring prompt export that skips unchanged scenes, batch import of Claude's reply with `// FILE: scenes/<id>.tsx` markers then auto-check), `motion` without `scene` implies a generated scene, new `PASTE_THIS_TO_CLAUDE_scene_authoring.txt` and a graphics section in the movie prompt, a Scenes tab (status list, thumbnails, retry, swap to fallback, open in Studio), a "Demo briefs" card so the real Claude round trip can be tested without a film.

3. **Phase 2: Preview and dynamic scene foundation.**
   - Remotion Studio set up for single-scene preview; the helper kit (`remotion/kit/`); the scene contract; three hand-written reference scenes; the static check, single-frame test render and `keywords` fallback.
   - *Check:* a hand-written scene and a deliberately broken scene both go through the pipeline; the good one renders and the broken one is replaced by the fallback with a readable error message.
4. **Phase 3: Dynamic scene engine (Claude-authored).**
   - `motion` field and schema, brief export, the scene-authoring prompt, batch import, caching, review list in the UI, fix-prompt export for failed scenes, and `theme.json` per movie.
   - *Check:* given a real film's subtitles, Claude produces a script and a batch of scenes; at least 80% pass validation on the first try, the rest are fixed with one paste-back round, and the final video has no missing-asset errors and visibly different designs for different movies.
5. **Phase 4: SFX engine.**
   - Provider interface, Freesound provider, local starter pack, index, loudness normalization, `credits.txt` output, sound themes, `sfx` cues, scene audio hooks, review step, mixing and ducking.
   - *Check:* a project with automatic transition and title SFX plus 5 scripted cues renders with consistent loudness; CC-BY attributions appear in `credits.txt`; the tool still works offline from the starter pack.
6. **Phase 5: Polish and 9:16.**
   - Theme system refinement (fonts, colors, caption styles, motion energy), color grade/grain options, real 9:16 layouts with safe zones passed to scenes through `layout`, intro/outro templates.
   - *Check:* the same timeline, including dynamic scenes, renders cleanly as 16:9 and 9:16 with captions inside safe zones.
7. **Phase 6: Speed and UI.**
   - Overlay-only render path for fast iteration, render concurrency tuning for the i5/12 GB machine, per-segment render caching, cost-budget enforcement, Player preview in the web UI, theme editor and SFX browser.
   - *Check:* re-rendering after editing one segment takes under 20% of the full render time.
8. **Phase 7: Cleanup and other modules.**
   - Retire the qtrle character pipeline (or keep a lightweight avatar component), extend presets to show recap, NBA, real story, ranking and comic recap.
   - *Check:* each module has a working preset and an updated prompt.

## 8. Decisions, constraints and risks

**Decisions already made**

- Python stays the brain; Remotion is the renderer; `timeline.json` is the contract.
- **Hybrid visual layer:** fixed components for structure (captions, transitions, audio, lower thirds, titles, avatar); Claude-written code for most explainers and motion graphics.
- **Two-pass authoring:** script and briefs first, scene code second, using the user's own Claude chat (no API needed).
- **Safe by default:** generated scenes are statically checked, test-rendered, cached, and fall back to `keywords` on failure.
- Overlay-first rendering, then full Remotion rendering once scenes are stable.
- Free by default; no paid dependency is required for any phase.
- Movie recap is the vertical slice; other modules follow after Phase 5.
- The character system is demoted to an optional component, not deleted up front.
- Premiere XML and VideoPad exports keep working at every phase.

**Risks and how to handle them**

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Generated code fails or looks broken | Free-form code is less predictable than templates | Contract + whitelisted kit, test render, automatic fallback, fix-prompt export, example scenes in the prompt |
| Generated code safety | Code written by an LLM runs on the user's machine | Static check blocks network/file/eval/imports outside the whitelist; scenes are plain readable files; never run unvalidated code |
| Inconsistent look across scenes | Per-scene code can drift in style | One `theme.json` fed to every scene; shared kit primitives; scene-authoring prompt sees neighbouring briefs |
| Render time and memory | Dynamic scenes can be heavy; target is an i5-8350U with 12 GB RAM and no GPU | `cost` budget per scene, overlay-first, segment caching, concurrency tuning, low-cost defaults |
| Authoring overhead | Two passes mean an extra paste round | One batch prompt for all scenes, automatic import, retry only the failed scenes |
| Remotion license | Free for individuals and very small teams, paid above that | Verify current terms before Phase 0; keep the ffmpeg path as a fallback |
| Freesound terms and limits | Rate limits, original downloads need OAuth, attribution rules | Verify docs first; previews plus local cache; license filter on by default |
| Copyright on source footage | Heavy clip use with thin commentary can draw claims | Designed and custom scenes plus commentary reduce reliance on clips; keep `credits.txt` |
| Windows setup | Node, Chromium download, long paths | Extend `SETUP.bat`, test on a clean machine, document the failure modes |
| Scope creep | The idea list is endless | One module, one phase at a time, each with a pass/fail check |
| Word timing quality | Bad timings make captions and synced scenes feel cheap | Prefer engine-native boundaries; Whisper as fallback; manual offset option |

**Open questions (answered)**

- Preferred visual style? **Changes per movie and per the user's wishes**, so a per-movie `theme.json` replaces a single fixed style.
- YouTube long form or Shorts/TikTok? **Both**, so 16:9 and 9:16 layouts are needed from the start (dynamic scenes receive `layout` safe zones).
- Machine specs? **HP EliteBook 840 G5 (Intel Core i5-8350U, 12 GB RAM, Intel UHD Graphics 620, Windows).** Expect slow full renders, which is why overlay-first, caching and a scene cost budget are required.

## 9. Kickoff prompt for the new chat

Attach the RecapStudio-main zip and paste this document (or the block below) as the first message.

```markdown
I'm building on my local project Recap Studio (attached zip) to make professional-looking MOVIE RECAP videos
(retelling + commentary) with motion graphics, animated captions, transitions and SFX.
Read the attached gameplan first, then the project, then start at Phase 0.

Rules for this work:
- Python stays the brain; Remotion is the renderer; timeline.json is the contract between them.
- Hybrid visual layer: fixed components for structure (captions, transitions, audio, lower thirds, titles, avatar);
  Claude-written Remotion scenes for most explainers and motion graphics. No rigid template vocabulary for those.
- Two-pass authoring: pass 1 writes segments.json with short "motion" briefs; pass 2 writes one .tsx scene per brief
  following a strict scene contract and a whitelisted helper kit. Validate, test-render, cache, and fall back to the
  "keywords" scene on failure. Never run unvalidated generated code.
- Theme changes per movie through a theme.json.
- Do not grow _template/recap.py. New code goes in remotion/, timeline.py, scenes.py and a providers/ package.
- Premiere XML and VideoPad exports must keep working. Keep the ffmpeg path as a fallback.
- Free by default. Windows-first (.bat files, SETUP.bat installs Node). Target machine: i5-8350U, 12 GB RAM, no GPU,
  so scenes carry a cost budget and rendering is overlay-first with caching.
- Both 16:9 and 9:16 outputs are needed.
- Verify Remotion's current license terms and Freesound's current API/license rules before relying on them.
- Work one phase at a time. Finish each phase's check before starting the next, and show me how to verify it.
- Explain each step briefly; ask me before any decision that is hard to undo.

Start by: (1) summarizing what you understand in 10 lines, (2) listing the files you will add or change in
Phase 0, then (3) begin Phase 0.
```
