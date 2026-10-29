> **NOTE (2026-10-29).** `cutwright/mlt.py` and `cutwright/gui.py` are scheduled for deletion (M5); `cutwright/engine/` is added in M3.
> Line numbers for `recap.py` drift: re-grep before reading a range.

# Code map (read ranges, not whole files)

Line numbers are for the merge date (2026-10-29); re-check with `grep -n` if they drift.
Find a function: `grep -n "def name" file`. Read a range: Read tool with offset/limit.

## recapstudio/ top level

| file | lines | what |
|---|---|---|
| `studio.py` | 1,598 | local web server (127.0.0.1) + job runner behind the UI. Agent uses the CLI, not this. `do_GET` ~953, `do_POST` ~1021; routes `/api/projects`, `/api/jobs`, `/api/keys`, `/api/projects/<n>/scenes...` |
| `web/app.js` | 2,048 | UI. `renderTab()` ~197; tabs: dashboard, pipeline, script, scenes, footage/comic, characters, voice, outputs, settings |
| `tts_worker.py`, `setup_engines.py` | 320, 350 | voice engines in their own venvs (Edge, Kokoro, Pocket, Chatterbox, ElevenLabs, MiniMax) |
| `SETUP.bat` | | installs base tools, Node + `npm install` in `remotion/`, faster-whisper, engines |
| `START_UI.bat`, `NEW_PROJECT.bat` | | UI launcher, copies `_template` to `Projects/<name>` |
| `keys.env.example` | | copy to `keys.env` (never committed) |

## recapstudio/_template/ (copied into every project)

| file | lines | what |
|---|---|---|
| `recap.py` | 5,493 | the pipeline in one file (index below). `STEPS` dict at ~5449, `main()` after it |
| `timeline.py` | 357 | `build_timeline`, `write_timeline`, `validate_timeline`, `step_timeline`, `step_remotion` (render + parity + retry) |
| `scenes.py` | 645 | scene requests, cache hash, staging into `remotion/src/generated`, `resolve`, `_check_generated` (runs Node tools), `_judge` (PNG verdict), `_fix_prompt`, `demo` |
| `authoring.py` | 608 | `validate_script`, `apply_theme`/`clean_theme`, `build_prompt` (pass-2 prompt), `parse_reply`/`import_reply`, `status`, `action`, `fix_prompt_text`, `demo_briefs` |
| `wordtimes.py` | 277 | word timings: Edge boundaries -> faster-whisper -> estimate; cached in `words/<id>.json` |
| `PASTE_THIS_TO_CLAUDE_*.txt` | | one script prompt per module + `scene_authoring` (graphics rules, kit reference) |
| `config.json`, `project.json`, `segments.json` | | defaults/templates |
| `*.bat` | | numbered step launchers; `MENU.bat` is the menu (23 timeline, 24 remotion, 25 check scenes, 26 preview, 27 demo scenes, 28/29 scene prompt/demo briefs) |

### recap.py section index (line = first line of the section body)

193 Shared helpers | 404 v2 helpers: project.json, media lookup, probing, fonts, tags (`reveal` at 367) |
673 STEP subs (`step_subs` 746) | 805 STEP init (`step_init` 818, `step_module` 814) |
867 Contact sheets (`step_sheets` 883, `step_index` 951) | 974 STEP collect (`step_collect` 1111,
`step_missing` 1229, `step_collect_one` 1257) | 1355 TTS engines Edge/ElevenLabs/MiniMax (local worker engines
at 1609) | 1998 TTS v2: tag modes, manifest, preview, review (`step_tts` 2122, `step_review` 2308) |
2383 silence-free frame-exact narration audio | 2448 **build every picture clip to match its voice-over
(`build_items`)** | 2572 CHARACTER ANIMATION (`step_characters` 3221) | 3468 Premiere XML (`step_premiere`
4031) | 3626 VideoPad (`step_videopad` 3947) | 4066 one finished video (`step_video` 4109) | 4135 .srt
(`step_srt` 4280) | 4295 TikTok (`step_tiktok` 4297) | 4328 STATUS + STATE.md (`step_check` 4404) |
4437 DEMO synthetic media (`step_demo` 4477) | 4532 COMIC/MANGA (`step_comic` 4897) | 5357 `step_say` |
5401-5445 thin bridges: `step_timeline`, `step_remotion`, `step_scenes`, `step_briefs`, `step_preview`

## recapstudio/remotion/

```
package.json            Remotion pinned 4.0.539; scripts: studio, typecheck
remotion.config.ts      @kit alias (relative to cwd)
src/index.ts Root.tsx   registers MovieRecap + SceneLab compositions
src/MovieRecap.tsx      main composition: maps timeline.json to clips, voice, music, scenes, overlays
src/types.ts layout.ts sceneTypes.ts   timeline types; 16:9/9:16 safe zones
src/captions/Captions.tsx   clean | bold | karaoke word-highlight captions
src/overlays/Overlays.tsx   chapter card, lower third, rank stamp, caption badge
src/transitions/transitions.tsx   fade, whip, zoom, flash, glitch (picture effects on clip ends)
src/scenes/Keywords.tsx     the fallback scene; SceneHost.tsx draws a scene inside an error boundary
src/SceneLab.tsx            Studio compositions per scene
src/generated/registry.ts   written by scenes.py (empty default ships); s_*.tsx are generated, git-ignored
kit/                        the helper kit scenes import as '@kit' (index.ts lists exports):
  types.ts theme.ts motion.ts shapes.tsx text.tsx charts.tsx particles.tsx SceneFrame.tsx CONTRACT.md
scenes_examples/            stat_ring, timeline_reveal, quote_moment (reference scenes + index.ts)
tools/check_scenes.mjs      static checker (TypeScript AST)
tools/test_scenes.mjs       bundle once + render sample frames
```

## cutwright/ (stdlib only)

| file | lines | what |
|---|---|---|
| `cli.py` | 775 | argparse entry; `cmd_doctor` (now includes `_doctor_recap`), probe, subs, moments, verify, transcribe, build |
| `guard.py` | 150 | the write invariant (`assert_writable`, `write_text/json`), `RECAP` path constant, hashing |
| `probe.py` `subs.py` `moments.py` `frames.py` `transcribe.py` | | perception tools |
| `mlt.py` | 2,573 | plan -> Shotcut `.mlt` + checks. HUGE: never read whole; see legacy HANDOFF_FULL |
| `gui.py` | | small Windows helper UI |
| `tools/shotcut_window.ps1` | | Shotcut window automation |

Other: `projects/demo_*` (Cutwright demo plans + checks), `vendor/videopad/` (VideoPad automation research,
PowerShell), `docs/`, `LOG.md`, `COMMS.md`, `PROVENANCE.md`, `REPORT.md`, `README.md` (Cutwright details).

## Greps worth knowing

- where a segment field is read: `grep -n '"motion"\|"transition"\|"lower_third"' recapstudio/_template/*.py`
- all CLI steps: `sed -n 5449,5453p recapstudio/_template/recap.py`
- timeline schema fields: `grep -n "def build_timeline" -A60 recapstudio/_template/timeline.py`
- kit exports: `cat recapstudio/remotion/kit/index.ts`
