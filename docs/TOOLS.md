> **NOTE (2026-10-30).** M5 removed the `build` row and the `backends editor_cli` row: this repo has no
> editor-application backend and no timeline writer any more. Edits go through the engine
> (`cutwright/engine/`). History: `docs/legacy/` and `docs/MIGRATION_CHECKLIST.md`.
> **M3 (2026-10-30): the engine verbs are LIVE** - `tools list|describe|envelope`, `validate`, `run`,
> `resume`, `status`, `approve` (all with `--json`). They are built on `cutwright/engine/`.
> Editing runs through Kinocut (default) or direct FFmpeg ops; see `docs/ARCHITECTURE.md`.
> **M6 (2026-10-30): the bridge and the stage envelopes are LIVE.** `recap ...` drives one project step
> (`cutwright/recap.py`), and `tools envelope --stage S` returns ONE stage's focused tool set
> (`cutwright/engine/envelopes.py`): its ops with schemas plus the commands it needs, capped at 10.
> Stages are `plan, edit, graphics, review, deliver` (`qc` was renamed `review`; `assets` was deleted).

# Tools catalogue (what the agent can call)

Status column: **works** = exists in the code (see HANDOFF for what is verified on the PC);
**G#** = planned in that goal. Commands run from the repo root unless noted.
Recap steps run from a project folder: `cd recapstudio\Projects\<name>` then `python recap.py <step>`
with `set RECAP_NONINTERACTIVE=1` (PowerShell: `$env:RECAP_NONINTERACTIVE=1`). After G4 use the bridge instead.

## Cutwright (agent layer) - `python -m cutwright <cmd>`

| cmd | does | status |
|---|---|---|
| `doctor` | machine report: ffmpeg, whisper, **Kinocut, Recap Studio engine, Node, Remotion, Python modules**, write-guard self test | works |
| `probe <file>` | streams, duration, subtitle tracks | works |
| `subs <video>` | find the best subtitle source and prove it usable (the subtitle trust gate) | works |
| `moments <video>` | transcript -> beats -> ranked candidate moments + agent digest | works |
| `verify` | grade picks against frames: verified / retimed / replaced | works |
| `transcribe <video>` | whisper.cpp fallback transcript, then gated (needs `bin/`, `models/`, not in git) | works if installed |
| `tools list [--stage S]` | every op (or one stage): name, stage, executor, one line. `--json` | works (M3) |
| `tools describe <op>` | one op in full: params, defaults, executor + reason, evidence file, installed? | works (M3) |
| `tools envelope --stage S` | at most 10 tools for ONE stage: its ops (with schemas) + the commands it needs | works (M3, M6) |
| `validate <manifest>` | pre-render check: ops, params, refs, budget, asset provenance (+ `--json`) | works (M3) |
| `run <manifest>` | execute a manifest: `--dry-run`, `--only STEP`, `--json`; cached steps skipped | works (M3) |
| `resume <run-dir>` | continue from the checkpoint; the manifest path comes from the checkpoint | works (M3) |
| `status <run-dir>` | the cursor, every step, its outputs and whether they still match (stale) | works (M3) |
| `approve <run-dir> <gate>` | write `approvals/<gate>.json`, releasing the step behind that gate | works (M3) |
| `recap projects\|new\|status\|<step>` | non-interactive bridge: one project step, `--project`, `--json`; `--force`/`init`/`collect` refused without the gate | works (M6) |
| `scene brief [--handle H] [--composition ID]` | the authoring brief: the 4 primitives + their real props, the handle rule, the 3 stills, the critic's checks | works (M7) |
| `scene check <file...> [--handle H]` | the real TypeScript static check of scene files (same checker `scenes` uses), `--json` | works (M7) |
| `scene write/sheet/metrics` | the rest of the G5 loop (write into the project, contact sheet, numbers) | **G5 remainder** |
| `analyze`, `script check`, `profile show` | perception pack, script validation, prompt profiles | **G7** |
| `blueprint check`, `direct` | Production Blueprint validation; Director orchestration over backends | **G8** |
| `make "<request>" --profile` | one-line entry for any video kind | **G9** |

## Engine ops that DRAW (M5.5A, executor `remotion`)

The engine could edit but not draw in code. Two ops now render a scene through the pinned Remotion
4.0.539 and record the output like any other step (`tools describe` has the full params):

| op | makes | measured cost on this PC (`docs/evidence/m55_remotion.json`) |
|---|---|---|
| `render_still` | ONE frame -> PNG (the critic loop's unit) | 1920x1080: 7.8 s cold / 8.3 s warm; 1080x1920: 7.4 / 7.0 s; 1.0 s when the step is cached |
| `render_range` | a frame range -> H.264 MP4 | 1 s (24 frames) at 1920x1080: 13.2 / 9.6 s; at 1080x1920: 11.0 / 12.0 s |

The SCENE FILE is the op's input, so editing that `.tsx` re-renders it and editing anything else does
not. `portrait: true` renders the 9:16 shape; a landscape render passes no props at all.

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

## Review loop for visuals (rule; `scene brief` + `scene check` arrived in M7)

`scene brief` -> write the scene -> `scene check` -> render 3 stills (`render_still` at the frames the brief
names) -> LOOK -> say in one line what is weak (composition, hierarchy, contrast, depth, motion contrast,
caption band) -> revise (max 2 rounds) -> keep the best -> if still weak mark `needs_owner`. Preserve passing
scenes through the cache; never regenerate everything. `scene sheet` (one contact-sheet PNG) and `scene metrics`
are still G5 remainder; three stills at 1920x1080 cost ~6 s each once the bundle exists.
Automated metrics report facts; they never decide that a scene is good.

## Paths the tools write (guard)

Cutwright code: only inside the repo (`guard.py`). Recap steps: only inside the project folder. Never write
into the footage folders (referenced by absolute path, read only).
