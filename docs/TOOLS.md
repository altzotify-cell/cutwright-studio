> **NOTE (2026-10-29).** The `build` (Shotcut .mlt) and `backends shotcut_cli` rows are CANCELLED/being removed (M5).
> **M3 (2026-10-30): the engine verbs are LIVE** - `tools list|describe|envelope`, `validate`, `run`,
> `resume`, `status`, `approve` (all with `--json`). They are built on `cutwright/engine/`.
> Editing runs through Kinocut (default) or direct FFmpeg ops; see `docs/ARCHITECTURE.md`.

# Tools catalogue (what the agent can call)

Status column: **works** = exists in the code (see HANDOFF for what is verified on the PC);
**G#** = planned in that goal. Commands run from the repo root unless noted.
Recap steps run from a project folder: `cd recapstudio\Projects\<name>` then `python recap.py <step>`
with `set RECAP_NONINTERACTIVE=1` (PowerShell: `$env:RECAP_NONINTERACTIVE=1`). After G4 use the bridge instead.

## Cutwright (agent layer) - `python -m cutwright <cmd>`

| cmd | does | status |
|---|---|---|
| `doctor` | machine report: ffmpeg, whisper, Shotcut, **Recap Studio engine, Node, Remotion, Python modules**, write-guard self test | works |
| `probe <file>` | streams, duration, subtitle tracks | works |
| `subs <video>` | find the best subtitle source and prove it usable (the subtitle trust gate) | works |
| `moments <video>` | transcript -> beats -> ranked candidate moments + agent digest | works |
| `verify` | grade picks against frames: verified / retimed / replaced | works |
| `transcribe <video>` | whisper.cpp fallback transcript, then gated (needs `bin/`, `models/`, not in git) | works if installed |
| `build <plan.json>` | plan -> Shotcut `.mlt` + checks (needs Shotcut portable) | works (crossfade unfinished, G1) |
| `tools list [--stage S]` | every op (or one stage): name, stage, executor, one line. `--json` | works (M3) |
| `tools describe <op>` | one op in full: params, defaults, executor + reason, evidence file, installed? | works (M3) |
| `tools envelope --stage S` | at most 10 op descriptions for ONE stage - what an agent should load | works (M3) |
| `validate <manifest>` | pre-render check: ops, params, refs, budget, asset provenance (+ `--json`) | works (M3) |
| `run <manifest>` | execute a manifest: `--dry-run`, `--only STEP`, `--json`; cached steps skipped | works (M3) |
| `resume <run-dir>` | continue from the checkpoint; the manifest path comes from the checkpoint | works (M3) |
| `status <run-dir>` | the cursor, every step, its outputs and whether they still match (stale) | works (M3) |
| `approve <run-dir> <gate>` | write `approvals/<gate>.json`, releasing the step behind that gate | works (M3) |
| `backends shotcut_cli` (wrapper over `cli-anything-shotcut`: transitions, blend/PIP, filters, ducking, export) | Shotcut editor controls without hand-building, each with a Cutwright check | **G3** |
| `recap ...` | non-interactive, JSON bridge to the engine | **G4** |
| `scene brief/write/check/sheet/metrics` | agent scene-authoring loop | **G5** |
| `analyze`, `script check`, `profile show` | perception pack, script validation, prompt profiles | **G7** |
| `blueprint check`, `direct` | Production Blueprint validation; Director orchestration over backends | **G8** |
| `make "<request>" --profile` | one-line entry for any video kind | **G9** |

## Recap Studio steps (`recap.py <step>`), safe vs dangerous

| step | does | agent use |
|---|---|---|
| `subs` | extract text subtitle tracks to `subs/*.srt` | ok |
| `index` | contact sheets per footage file (4x4 tiles, ~1 per 5 min) | ok |
| `sheets` | one contact sheet per segment with `need_visual` | ok |
| `check` | writes `STATE.md`; counts segments without footage; lists missing tools | ok, run after every step |
| `missing` | list segments with no picture | ok |
| `say --text-file f --out x.mp3` | one-off voice line | ok |
| `tts --engine edge --yes [--only ids] [--preview]` | voice per segment, incremental (`audio/_manifest.json`) | ok; never `--force` |
| `review` / `review --import` | narration to CSV and back | ok |
| `briefs [--demo]` | write the scene-authoring prompt; import `SCENE_REPLY.txt` | ok (Claude-chat fallback) |
| `scenes` | validate scenes: static check + test render + fallback + `scenes_report.json` | ok |
| `preview` | open Remotion Studio | owner only (opens a window) |
| `timeline` | write + validate `timeline.json`; stage files in `remotion_public/` | ok |
| `remotion` | render `recap_remotion.mp4` + parity check vs `recap_final.mp4` | ok (slow: ~5.7 fps on the i5) |
| `video` | ffmpeg full video `recap_final.mp4` (no captions burned) | ok |
| `srt` | `recap_subtitles.srt` | ok |
| `tiktok` | 9:16 ffmpeg build | ok |
| `premiere`, `videopad` | Premiere XML / VideoPad project | regression-test only |
| `demo` | synthetic demo media + segments | ok (test projects only) |
| `characters`, `comic` | character library / comic import+render | only if asked |
| `init` | interactive project questions | **FORBIDDEN** (write `project.json` directly) |
| `collect`, `collect_one` | yt-dlp footage collection, `input()` per shot | **FORBIDDEN** unattended; `collect_one --id --file` is OK |
| any `--force` | deletes outputs (`tts --force` deletes all audio; `comic --force` destroys panel edits) | **FORBIDDEN** without a COMMS entry |

Side effects: some steps open an Explorer window (`reveal()`); `tts` rewrites `config.json`.

## Node tools (in `recapstudio/remotion/`)

- `node tools/check_scenes.mjs` - static check of scene files via the TypeScript compiler (allowed imports,
  banned APIs, kit names exist, default export, `cost`).
- `node tools/test_scenes.mjs` - bundle once, render start / 40% / 75% / last frame at the project shape +
  one frame at the other ratio into `scenes/_checks/*.png`; `scenes.py` judges the PNGs (error, all-one-colour
  frame, or "looks the same as the empty background" = failure).
- `npm run typecheck` - `tsc --noEmit` over the renderer + kit (run after any `.ts/.tsx` change).
- `npm run studio` - Remotion Studio (compositions `scene-<id>`, `example-<name>`; `portrait` prop = 9:16).

## Reports to read after a step

`STATE.md` (resume snapshot), `scenes_report.json` + `SCENE_FIX_PROMPT.txt`, `timeline.json`
(`validate_timeline` messages), `credits.txt`, `shot_manifest.csv`, `chapters.txt`, `audio/_manifest.json`.

## Review loop for visuals (rule; tools arrive in G5)

write scene -> `scene check` -> `scene sheet` (one contact-sheet PNG) -> LOOK -> say in one line what is weak
(composition, hierarchy, contrast, cropping, density, movement) -> revise (max 2 rounds) -> keep the best ->
if still weak mark `needs_owner`. Preserve passing scenes through the cache; never regenerate everything.
Automated metrics report facts; they never decide that a scene is good.

## Paths the tools write (guard)

Cutwright code: only inside the repo (`guard.py`). Recap steps: only inside the project folder. Never write
into the footage folders (referenced by absolute path, read only).
