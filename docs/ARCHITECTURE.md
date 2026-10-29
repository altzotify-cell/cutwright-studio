# Architecture: Kinocut + FFmpeg editing layer, Remotion graphics layer

Revised 2026-10-29 (architecture change). Supersedes the earlier version in which Shotcut was a
primary backend. Status of every claim about Kinocut: see `docs/REFERENCES.md` (what is documented vs
what DeepSeek must still verify on the owner's PC). Ordered work: `docs/ROADMAP.md`.

## One-paragraph picture

The agent is the creative director and production operator. Deterministic tools do the reliable
work. **Kinocut** (Apache-2.0, FFmpeg-based, typed tools + receipts) is the default editing toolkit.
**FFmpeg** is the engine under it and the direct tool for anything Kinocut cannot do or cannot do
accurately enough. **Remotion** renders programmatic motion graphics (captions, overlays, scenes).
**Python** (Recap Studio + Cutwright) is the brain: script, voice, timing, planning, validation.
Shotcut is NOT part of the target architecture. HyperFrames is a benchmark candidate only.
OpenMontage is an architectural reference only. FireRed-OpenStoryline is excluded.

## Responsibilities (who does what)

| Layer | Owner | Does | Does NOT |
|---|---|---|---|
| Creative direction | the agent (DeepSeek in Cline) | brief -> plan -> `segments.json`, scene briefs, review of rendered frames, revision decisions | run raw shell pipelines it has to remember; guess tool flags |
| Perception + trust | `cutwright/` (stdlib only) | probe, subtitle trust gate, moments, frame verification, whisper, write guard | edit video |
| Plan + timing | `recapstudio/_template/` (`authoring`, `recap`, `wordtimes`, `timeline`) | validate script, Edge-TTS voice, frame-exact timing, `timeline.json` | grow `recap.py` |
| **Editing execution** | **Kinocut first, FFmpeg direct second** (via our executor layer) | trim, resize/fit, concat/merge, transitions, overlays/PIP/blend, audio mix/duck/normalize, burn-in, export, QC | duplicate every Kinocut op with custom ffmpeg |
| Motion graphics | Remotion 4.0.539 (pinned) | captions, overlays, lower thirds, titles, agent-written TSX scenes | edit source footage |
| Orchestration state | `cutwright/engine/` (new) | registry, execution manifest, checkpoints, resume, approvals, cost log | decide creative content |
| Human-editable exports | `recap.py` exporters | Premiere XML, VideoPad | be the primary path |

### The selection rule (Kinocut vs FFmpeg)

For each operation the executor layer picks the executor from a measured table, not from taste:

1. If `docs/CAPABILITY_MATRIX.md` says Kinocut **passes** the acceptance test for the op -> use Kinocut.
2. If Kinocut lacks the op, or fails frame accuracy / A-V sync / quality / reliability on Windows ->
   use direct FFmpeg, and write the concrete technical reason into the matrix (`executor_reason`).
3. If neither passes -> report the gap to the owner; do not fake it.
4. Never write a second FFmpeg implementation of an op Kinocut already passes. Never wrap Kinocut
   around an op it fails just to keep "Kinocut-first" on paper.

The choice is data: each manifest step records `executor`, `executor_reason`, parameters, outputs,
hashes and validation results, so a run is reproducible and resumable whichever tool ran it.

## Data flow (one coherent plan and timeline)

```
 brief / topic / source footage / narration / music / user images
        |
        v
 [cutwright] probe, subs gate, moments, scene detect, coverage sheets -> analysis/ (index of assets + provenance)
        |
        v
 AGENT: creative plan  = segments.json (+ theme, `motion` briefs)         <- the ONE creative source
        |
        v   authoring.validate_script -> plain-English problems
 [recapstudio] voice (Edge-TTS) + word timings -> frame-exact timeline.json (schema 2)   <- the ONE timeline
        |
        v   derive (never hand-write)
 EXECUTION MANIFEST  production/<run>/manifest.json   <- the ONE execution plan: ordered ops over timeline ids
        |            each step: op, inputs, params, executor(kinocut|ffmpeg|remotion|python), executor_reason,
        |            outputs+hashes, validation, status, attempts, cost
        |
        +--> editing steps ------> [executor layer] --+--> Kinocut (venv, adapter, receipts)   default
        |                                              +--> FFmpeg  (direct, argument lists)     when justified
        +--> graphics steps -----> Remotion render (scenes/captions/overlays)  -> overlay clips
        |
        v
 assemble -> preview render -> VALIDATE (ffprobe, frame count, A/V sync, black frames, loudness, caption presence,
        |                              slideshow-risk check, asset-provenance check [no AI images])
        v
 AGENT inspects frames, lists concrete defects -> revise ONLY the affected scenes/ops (cache keeps the rest)
        v
 final render + verification -> deliverable + production_report.json (manifest, tools, versions, provenance)
        \--> optional: Premiere XML / VideoPad exports (existing)
```

### Diagram (division of responsibilities)

```
                      +------------------ AGENT (creative director) ------------------+
                      |  brief -> plan -> pick skills -> inspect frames -> revise       |
                      +-----------+---------------------------------------+------------+
                                  | typed tool calls (JSON)               | reads reports
                      +-----------v---------------------------------------v------------+
                      |  cutwright/engine : registry . manifest . checkpoints . gates   |
                      +---+------------------+-------------------+----------------+-----+
                          |                  |                   |                |
              +-----------v----+   +---------v--------+   +------v------+   +-----v--------+
              | KINOCUT (venv) |   | FFMPEG (direct)  |   |  REMOTION   |   | PYTHON       |
              | default editor |   | fallback/precise |   |  4.0.539    |   | recap.py etc |
              | trim resize    |   | frame-exact fit  |   |  captions   |   | script voice |
              | merge compose  |   | audio chains     |   |  overlays   |   | timing       |
              | QC receipts    |   | xfade, encode    |   |  TSX scenes |   | perception   |
              +-------+--------+   +---------+--------+   +------+------+   +------+-------+
                      \                      |                   |                |
                       +---------------------+--------+----------+----------------+
                                                      v
                                        media files + validation reports
```

Not in the picture on purpose: Shotcut (removed), HyperFrames (benchmark only, M9), FireRed (excluded),
any image generator (forbidden).

## Integration rules for Kinocut

- Install in an isolated venv (`.venvs/kinocut/`, gitignored), pinned to a release (start: `kinocut==1.16.4`).
  Cutwright core stays stdlib-only and talks to Kinocut by subprocess (CLI or `python -c` with the venv's
  interpreter). No `import kinocut` inside `cutwright/`.
- Kinocut's overwrite guard requires explicit `overwrite=true`/`--overwrite` for existing outputs; our
  adapter writes each step to a fresh path inside the run folder and never relies on overwrite.
- Kinocut's receipts are kept and referenced from our manifest (path + hash). Do not re-implement them.
- Optional extras: do NOT install `transcribe` (torch, ~1 GB; we have whisper.cpp / faster-whisper),
  `stems`, `upscale`, `ai`. Install only what a passed test needs.
- Network/telemetry: keep Kinocut's defaults (model calls, telemetry off). No cloud keys.
- Expose tools to the model through discovery, never as a dump: Kinocut's own default surface is ~20 of
  ~205 tools; our registry exposes only the ops needed by the current stage (see ROADMAP M3/M6).

## Integration rules for FFmpeg

- Direct calls use argument lists, never shell strings (Windows quoting). Paths with spaces are normal.
- Every direct call is a named, typed op in `cutwright/engine/executors/ffmpeg.py` with a validation
  function, not a free-form command the agent composes.
- Required build features (verified by `doctor` in M0): `libx264`, `aac`, `xfade`, `acrossfade`,
  `sidechaincompress`, `loudnorm`, `libass`/`subtitles`, `drawtext` only if a feature needs it.

## OpenMontage: concepts we re-implement clean-room (no code copied)

| Concept (from its public README/docs) | Our implementation |
|---|---|
| Pipeline manifests describing stages and gates | `pipelines/*.json` (JSON, stdlib), read by `engine/manifest.py` |
| Stage-director skills (markdown the agent reads per stage) | `skills/<stage>.md`, short, one per stage |
| Tool registry + support envelope + discovery | `engine/registry.py`: list ops by stage, describe one op, report what is installed |
| Schema-checked artifacts + checkpoints, resumable | `engine/checkpoint.py`, JSON schema checks in plain Python |
| Human approval gates (script, scene plan, final) | `approvals/<gate>.json` written by the owner or agent after owner OK; manifest refuses to proceed |
| Pre-compose validation, post-render self-review | `engine/validate.py`: plan checks before render, ffprobe/frame/audio checks after |
| Slideshow-risk scoring ("not animated PowerPoint") | `engine/validate.py: slideshow_risk()` using our own measurable rules |
| Decision/cost log, budget cap | `production_report.json`; default budget cap $0.00 (free-first) |
| Provider scoring across dimensions | NOT adopted now: we have few providers; a flat measured table is enough |
| AI image/video generation providers | NOT adopted: forbidden |

License: AGPL-3.0 per the repository page. Ideas only. Do not copy code, file text, prompts or schemas.
See `docs/REFERENCES.md` for the procedure and the question that needs the owner's approval before any code reuse.

## Hard constraints (apply everywhere)

- **No AI-generated images or video.** If an asset is missing: use real footage, a code-made graphic
  (SVG/HTML/CSS/React/Remotion, typography, charts, procedural motion), a user-supplied asset, or report it missing.
  The validator records every visual asset's origin (`footage | user_image | code_graphic | stock_licensed`) and fails on anything else.
- **Free-first, Windows-first, low resource** (i5-8350U, 12 GB, no GPU). No mandatory paid API, cloud service or heavy model.
- **FireRed-OpenStoryline: out of scope.** No dependency, no adapter, no design borrowing.
- **Shotcut: not required anywhere in the automated pipeline**, and no fallback to it.
- Cutwright code writes only through `cutwright/guard.py`. Never edit a user's footage in place.

## Scene contract (unchanged; full text `recapstudio/remotion/kit/CONTRACT.md`)

A scene is one default-exported React component receiving `{durationInFrames, fps, width, height, props, theme,
words, layout}`; imports only `remotion`, `react`, `@kit`; no network/eval/DOM/timers/`Date`/`Math.random`;
pure function of the frame; works 16:9 and 9:16; declares `cost`. Static check -> test render -> cache ->
`keywords` fallback on failure. Nothing runs before the static check passes.

## Files that are data contracts

`segments.json`, `project.json`, `config.json`, `theme.json`, `timeline.json` (schema 2), and (new)
`production/<run>/manifest.json`, `production/<run>/checkpoints/*.json`, `production/<run>/production_report.json`.
Field lists for the first five are unchanged (see `recapstudio/_template/authoring.py` and the module prompts).
The manifest schema is specified in `docs/schemas/manifest.example.json` and `docs/ROADMAP.md` M3.

## Code hygiene

- Do not grow `recap.py` (5,493 lines). New code in new modules + a thin bridge.
- New agent-facing code goes in `cutwright/` (stdlib only), under `cutwright/engine/`, writing through `guard.py`.
- Each Recap project folder has its own copy of the template modules; `_template/` changes must be synced
  (the bridge warns about stale copies).
- Delete code only after its replacement passed its acceptance test (see `docs/MIGRATION_CHECKLIST.md`).
- Run `python -m unittest discover -s tests -v` and the Recap regression (`ROADMAP.md`, "Regression pack") after every milestone.

## Constraints that shape decisions

i5-8350U / 12 GB / no GPU: Remotion renders ~5.7 frames/s. So: cache per scene and per manifest step,
keep scenes cheap, render overlays only where possible, preview at low resolution before the final.
