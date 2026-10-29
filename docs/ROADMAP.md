# Roadmap: Kinocut-first agentic video engine

Revised 2026-10-29. Replaces the goal ORDER in `HANDOFF.md`/`GOALS.md`. Old per-goal specs in `GOALS.md` stay as
detail sources where a milestone says so (map at the end). Architecture: `docs/ARCHITECTURE.md`. References/licences:
`docs/REFERENCES.md`. Delete-list: `docs/MIGRATION_CHECKLIST.md`.

Milestones are in order. Do not start M(n+1) until M(n) acceptance is met and logged with quoted output.
Each milestone is sized for one or two Cline sessions. Paths are relative to the repo root. Shell = Windows PowerShell.

## Standing rules for every milestone

1. **Report only what was run.** In `LOG.md` write three lists: TESTED (command + quoted result), FAILED (command + error),
   NOT TESTED (and why). A claim without a quoted command result is not allowed. "It compiles/imports/rendered" is not a pass.
2. **Verify, then depend.** Machine-dependent facts (Python/Node/FFmpeg versions, Kinocut behaviour, Windows paths) are
   unknown until you ran the check on this PC.
3. **Small edits.** No wholesale rewrites. A change to a shared file needs the Regression pack (below) afterwards.
4. **Delete only after replacement passes.** Never delete first. Delete in its own commit.
5. **Two failed attempts at the same problem -> BLOCKED entry in `COMMS.md` and stop.**
6. **Hard exclusions:** no AI-generated images/video; no FireRed; no Shotcut dependency; no OpenMontage code; no paid API;
   Remotion stays 4.0.539; no new npm packages without the owner; never print keys.
7. After each milestone: LOG entry, tick in `HANDOFF.md`, update status block, `git commit -F msg.txt`, push if a remote exists, tell the owner to start a new session.

## Provisional decisions (made by the consultant; DeepSeek verifies each on this PC and records the outcome in LOG)

| # | Assumption | Verify with | If false |
|---|---|---|---|
| A1 | Kinocut needs Python >= 3.11; the PC may have older. Kinocut gets its own venv with a 3.11+ interpreter; Cutwright/Recap keep running on the existing Python | `py -0p` ; `python --version` | install 3.12 side by side: `winget install -e --id Python.Python.3.12`, then `py -3.12 -m venv .venvs\kinocut`. Tell the owner before installing |
| A2 | Kinocut lives in `.venvs\kinocut`, pinned `kinocut==1.16.4`, called by subprocess from `cutwright/engine/executors/kinocut.py` | `.venvs\kinocut\Scripts\kino.exe doctor` | if 1.16.4 fails on Windows, test the previous release once, record both, else BLOCKED |
| A3 | Skip `kinocut[transcribe]`; keep whisper.cpp / faster-whisper | n/a | only revisit if the existing whisper path is unfixable AND the owner agrees to ~1 GB |
| A4 | HyperFrames not installed until M9 | n/a | n/a |
| A5 | FFmpeg already on PATH via `winget Gyan.FFmpeg` (SETUP.bat), independent of Shotcut. Shotcut's bundled ffmpeg.exe must NOT be what runs | `where.exe ffmpeg` ; `ffmpeg -version` | run `recapstudio\SETUP.bat` or `winget install -e --id Gyan.FFmpeg`; restart the shell |
| A6 | Node >= 22 is not needed until M9; Remotion works with the current Node | `node --version` | do not upgrade Node for Remotion; M9 may need 22+, install side-by-side or in an isolated folder |
| A7 | No git history or remote in the ZIP | `git status` ; `git remote -v` ; `git branch --show-current` | see M0 step 1 |
| A8 | The executor layer is Python stdlib only | n/a | Kinocut-side code runs only inside its venv |

## Regression pack (run after any change to shared code; quote the key lines)

```powershell
cd recapstudio\Projects\regress        # create once: copy recapstudio\_template here (see M0)
$env:RECAP_NONINTERACTIVE = "1"
python recap.py demo
python recap.py briefs --demo
python recap.py video       # expect: Done. recap_final.mp4  (21.4s, expected 21.4s)
python recap.py timeline    # expect: timeline.json: 6 segments, 514 frames (21.4s at 24fps, 1920x1080) + Timeline check passed
python recap.py scenes      # expect: 3 example scenes [ok], 3 broken ones fall back to keywords with readable messages
python recap.py remotion    # expect: PARITY CHECK PASSED   (slow: ~5.7 fps)
python recap.py premiere    # expect: Premiere XML written
cd ..\..\..
python -m unittest discover -s tests -t . -v
python -m cutwright doctor
```
Baseline already seen on Linux without Remotion (consultant, 2026-10-29): `video` -> 21.4 s, 6.8 MB, `timeline` -> 514 frames. Record the Windows numbers in M0.

---

## M0 - Environment audit and baseline (no code changes except the first commit)

Objective: know the real machine and the real starting point.

Steps
1. Git: `git status`, `git remote -v`, `git branch --show-current`, `git log --oneline -5`. If this folder is not a repo, or the
   ZIP was extracted over an existing clone, find out which (`git rev-parse --show-toplevel`). Do NOT assume the remote is right
   (HANDOFF names `altzotify-cell/cutwright`; confirm with the owner only if `git remote -v` disagrees or is empty). Commit the tree
   as one commit "arch: Kinocut-first handoff (docs + tests fixtures)" BEFORE other edits. Check `git status` shows no
   `keys.env`, `Projects/*`, `node_modules`, `models/`, `bin/`, `shotcut/`, `.venvs/`.
2. Record versions into `LOG.md`: `py -0p`, `python --version`, `node --version`, `npm --version`, `ffmpeg -version` (first 3 lines),
   `where.exe ffmpeg`, `ffprobe -version`, `git --version`, Windows version (`[System.Environment]::OSVersion.VersionString`), free disk, RAM.
3. FFmpeg feature check (needed later): `ffmpeg -hide_banner -encoders | findstr /i "libx264 aac"`,
   `ffmpeg -hide_banner -filters | findstr /i "xfade acrossfade sidechaincompress loudnorm subtitles ebur128"`. Record which are missing.
4. `python -m cutwright doctor` (quote the whole output). Expected failures today: Shotcut, whisper.cpp not installed -> fine.
5. `python -m unittest discover -s tests -t . -v` -> the fixtures self-test must pass on this PC. If not, fix the fixture (Windows issue) before going on.
6. Recap baseline: create `recapstudio\Projects\regress` from `_template` (or `NEW_PROJECT.bat`), run the Regression pack.
   If Node/Remotion are missing, ask the owner to run `recapstudio\SETUP.bat`, then continue. Record render speed (frames/s) and scene-check time.
7. Whisper issue from HANDOFF ("Known unverified"): one attempt: `py -3 -m pip install --upgrade av faster-whisper`; rebuild timeline;
   look for `word timings ...: whisper`. Failed -> note it and move on (not a blocker).
8. Optional, only if `shotcut\Shotcut\melt.exe` exists: `python -m cutwright build projects/demo_cuts/plan.json` and quote the check table.
   Purpose: capture what Shotcut checks proved, so M5 can replace the essential ones. Skip silently if absent (say so).

Deliverables: `LOG.md` entry; `docs/ENVIRONMENT.md` (the recorded facts); baseline numbers.
Acceptance: all commands above were run and quoted; every failure is listed; commit hash recorded.

## M1 - Kinocut isolated install and interface discovery

Objective: learn what Kinocut REALLY offers on this PC. No integration code yet.

Steps
1. Create the venv with a 3.11+ interpreter (A1): `py -3.12 -m venv .venvs\kinocut` then
   `.venvs\kinocut\Scripts\python -m pip install --upgrade pip` and `.venvs\kinocut\Scripts\python -m pip install "kinocut==1.16.4"`.
   Record download size and install time. Add `.venvs/` to `.gitignore` if missing.
2. `.venvs\kinocut\Scripts\kino.exe doctor` (quote). `.venvs\kinocut\Scripts\python -m pip list` (quote). Note exactly which dependencies came in.
3. Run Kinocut's own 60-second proof from its docs/GOLDEN_PATH if it can run from the installed package; else run `kino info` and
   `kino trim` on a fixture from `tests/media_fixtures.py` (create via `python -c "from tests import media_fixtures as m; m.make_counter_clip('out/fx/a.mp4')"` after `mkdir out\fx`).
4. Discover the interface from the installed package (do not guess): `kino --help`; `kino <cmd> --help` for: info/probe, trim, resize, merge,
   convert, add_text/burn, subtitles, composite-layers, audio tools, fade/transition tools, normalize, quality-check, release-checkpoint, workflow-*,
   search-tools, and any command about speed/fit/duration. Find out for each: arguments, defaults, output path rules, overwrite flag, exit code on error,
   whether output is machine-readable (is there a JSON/format option? **find out; do not assume**), and where receipts are written.
5. Python Client: `.venvs\kinocut\Scripts\python -c "from kinocut import Client; c=Client(); print(c.search_tools('trim'))"` and `c.inspect('trim')` (adjust to what exists).
6. Test under the conditions Cline uses: run from PowerShell without a TTY, with a path containing spaces and one with a non-ASCII character (`out\fx dir\café.mp4`), an output path
   that already exists (expect refusal without overwrite), a missing input (expect a clear error), and a 250+ character path.
7. Optional extras: only list what a later test needs. Install nothing else. Never `kinocut[transcribe|ai|stems|upscale]`.
8. Licence: open the Kinocut LICENSE on GitHub, confirm Apache-2.0, write the sha256 of the text and the exact installed version into `PROVENANCE.md`.
   Same for FFmpeg: `ffmpeg -version` build line (`--enable-gpl`?) and note LGPL/GPL.
9. Verify the OpenMontage licence the same way (read its LICENSE on GitHub; record). Do not read or copy its source files.

Deliverables: `docs/KINOCUT_FINDINGS.md` containing: install facts; command table (command, key arguments, what it does, output contract, error behaviour);
Python Client surface actually used; what is machine-readable; Windows results for each of the checks in step 6; every README CLAIM from `docs/REFERENCES.md` marked CONFIRMED / REFUTED / NOT TESTED; list of capabilities
our project needs that Kinocut lacks (first draft).
Acceptance: `kino.exe doctor` output quoted with required checks passing (or a BLOCKED entry); the findings doc has no "assumed" entry; step 6 results present.

## M2 - Equivalence verification: Kinocut vs the current code vs direct FFmpeg

Objective: measured evidence for every "use Kinocut / use FFmpeg" decision. Nothing is replaced in this milestone.

Layout: `tests/kinocut_vs_current/test_<area>.py` (unittest, skipped when `.venvs\kinocut` or ffmpeg is missing), shared helpers in `tests/`.
Each test writes `docs/evidence/m2_<area>.json` (small: inputs, executor, command, measured values, pass/fail, seconds). Fixtures come from
`tests/media_fixtures.py` (frame numbers burned in as blocks; beeps at whole seconds). For each area run THREE candidates where they exist:
(a) Kinocut, (b) the current Recap/Cutwright implementation (find it with `docs/CODEMAP.md`: `render_video_clip`, `render_image_clip`, `fit_graph`, `fit_audio`, `join_av`, `make_music_bed`, `write_concat_list`), (c) a minimal direct-FFmpeg reference.

| Area (file) | Test | Pass criterion (exact unless stated) |
|---|---|---|
| frame accuracy `test_trim` | trim a 240-frame 24 fps counter clip: start frames 0, 1, 37 (non-keyframe), 119; length 1, 50, 120 frames; both re-encode and (if offered) stream-copy | `frame_ids(out) == list(range(start, start+len))` for re-encode. Stream-copy: report keyframe snapping, do not use it for cuts that must be exact |
| clip fitting `test_fit` | fit a clip to N target frames (N from voice durations, e.g. 53, 97, 241) with pad / blur / crop fill and a speed change; fit a still image to N frames | output frame count == N exactly; ids monotonic non-decreasing; output 1920x1080, yuv420p, constant 24 fps; no black first/last frame |
| resize / fill `test_resize` | 16:9 -> 9:16 with pad, blur, crop; non-square-pixel input | exact output size; content centred (pixel check on block row); no stretch (aspect measured) |
| concat `test_concat` | 20 clips of 120 frames, different `id_offset`, join in order; once with all-same-codec clips, once with mixed fps/resolution inputs | ids == concatenation of expected ids (no dropped/duplicated frame at any join); total frames exact; beep onsets stay on whole seconds with cumulative drift <= 42 ms (one frame) over the whole file |
| transitions `test_transition` | 12-frame crossfade between two clips; also a "cut" and a "whip/slide" if offered | frames == a + b - 12; first (a-12) ids and last (b-12) ids intact; overlap frames are blends (luma between the two sources); audio has no gap > 10 ms and no click (peak jump < 6 dB) |
| audio mixing `test_audio` | voice track (tone bursts) + music bed under it; duck music under voice; fades in/out; loudness normalize | music level during voice >= 8 dB below music level outside voice; integrated loudness -16 LUFS +/- 1.5 (measure with ffmpeg `ebur128`); true peak <= -1 dBTP; voice onset error <= 20 ms vs the timeline; no clipping |
| overlay / compositing `test_composite` | lower-third PNG with alpha and a Remotion-rendered overlay clip over footage with timing window, opacity, position; blend if offered | overlay appears exactly on [start, end) frames (check frames start-1, start, end-1, end); alpha respected; base audio preserved |
| burn-in / subtitles `test_burn` | burn an SRT with libass; with non-ASCII text | text visible on the right frames; no encoding error on Windows paths |
| export `test_export` | final export of a 60 s 1080p24 timeline | H.264 High yuv420p, AAC 48 kHz stereo, constant fps, `faststart` (moov before mdat), `ffmpeg -v error -i out.mp4 -f null -` prints nothing; record encode seconds and peak memory |
| QC `test_qc` | feed a clip with a deliberate black frame, silence gap, clipping | Kinocut's quality check flags each; compare with our own checks in `cutwright/frames.py` |
| reliability `test_reliability` | run the trim, fit, concat ops 10 times each; run with a read-only output dir; kill mid-run | zero flaky runs; clean error messages; no orphaned temp files |
| workflow `test_workflow` | express "trim -> resize -> merge -> add_text" as a Kinocut workflow spec; run, delete one intermediate, `--resume`; edit the spec, resume | resume skips completed steps; changed spec is refused (fail-closed); receipt hashes match `sha256` of the files |

Deliverables
- `docs/CAPABILITY_MATRIX.md`: one row per operation: current implementation (file:function), Kinocut command, test result, timing, **executor chosen (kinocut|ffmpeg|current|none)**, `executor_reason`, notes.
  Include the gaps: whatever Kinocut cannot do (expected candidates to verify: exact frame fit to a voice length, speed ramps, crossfade between clips, sidechain ducking, per-clip audio keep/mix rules, burn-in captions with our karaoke style (stays Remotion), audio in `composite-layers` ("video-only")).
- `docs/evidence/m2_*.json`.
- Updated `docs/KINOCUT_FINDINGS.md`.

Acceptance
```powershell
python -m unittest discover -s tests -t . -v           # fixtures + all M2 tests that apply; failures are allowed ONLY if recorded as capability gaps in the matrix
Get-ChildItem docs\evidence\m2_*.json | Measure-Object  # one evidence file per area above
```
Every matrix row has a measured result or an explicit "NOT TESTED because ...". No op is marked "kinocut" without a passing test.

## M3 - Executor layer, registry, manifest, checkpoints (the engine skeleton)

Objective: ONE coherent plan and timeline whatever tool executes an op; resumable; agent-friendly discovery. Stdlib only; writes through `guard.py`.

New files (create only these; do not touch `recap.py` yet):
```
cutwright/engine/__init__.py
cutwright/engine/ops.py            op specs: name, stage, description, param schema, required inputs, validator, default executor from CAPABILITY_MATRIX
cutwright/engine/registry.py       list/describe/envelope; discovery by stage; reports what is installed (kinocut venv, ffmpeg, node, remotion)
cutwright/engine/executors/kinocut.py   subprocess adapter to .venvs\kinocut ; typed errors; captures stdout/stderr/exit code/receipt path
cutwright/engine/executors/ffmpeg.py    argument-list ffmpeg calls, one function per justified op; no free-form commands
cutwright/engine/executors/remotion.py  thin: calls the existing recap step/bridge; returns output + checks
cutwright/engine/manifest.py       load/validate/derive/run ; step state machine
cutwright/engine/checkpoint.py     atomic JSON writes (write temp, replace), resume cursor, per-step input-hash cache key
cutwright/engine/validate.py       plan validation (pre-render) + media validation (post-render) + slideshow_risk + asset provenance
cutwright/engine/gates.py          approval gates (files in production/<run>/approvals/)
cutwright/engine/report.py         production_report.json
cutwright/engine/ids.py            run ids, hashing helpers
pipelines/recap.json, pipelines/explainer.json   stage lists (JSON), minimal at this point
skills/*.md                        one short stage-director skill per stage (plan, assets, edit, graphics, qc, deliver)
docs/schemas/manifest.example.json (exists; keep the real validator in sync)
tests/test_engine_*.py
```
CLI additions in `cutwright/cli.py` (thin; logic stays in `engine/`):
`python -m cutwright tools list [--stage S]`, `tools describe <op>`, `tools envelope`, `validate <manifest>`, `run <manifest> [--dry-run] [--only STEP]`, `resume <run-dir>`, `status <run-dir>`, `approve <run-dir> <gate>`. All print JSON with `--json`.

Manifest rules (see `docs/schemas/manifest.example.json`): every step has `id`, `op`, `inputs` (paths or `@step.output` refs), `params`, `executor`, `executor_reason`,
`outputs`, `cache_key`, `validation` (list of checks + results), `status` (pending|running|done|failed|skipped), `attempts`, `started`/`finished`, `cost_usd` (0.0), `tool_versions`.
Retry policy: at most 2 attempts for transient failures (subprocess timeout, locked file); deterministic failures (validation, bad params) are not retried. Every failure message names the step, the op, the parameter and a suggested fix.
Resume: a step is skipped iff its `cache_key` (hash of inputs + params + executor version) equals the stored one and its outputs still exist with the stored hash.
Exposure: `tools envelope` returns only ops for the requested stage (<= ~10 descriptions per call); never the whole registry.
The `executor` for each op comes from `docs/CAPABILITY_MATRIX.md` (encode it as data in `ops.py`; a unit test fails if an op has `executor: kinocut` without a passing evidence file).

Acceptance
```powershell
python -m unittest discover -s tests -t . -v
python -m cutwright tools list --stage edit --json
python -m cutwright tools describe trim_exact --json
python -m cutwright validate docs\schemas\manifest.example.json
python -m cutwright run out\fx\demo_manifest.json --json      # trim -> fit -> concat -> mix -> export on fixtures; real media written
python -m cutwright status out\runs\demo --json                # every step done, hashes present
# resume test: start a run, kill the process during step 3, then:
python -m cutwright resume out\runs\demo --json                # steps 1-2 reported "skipped (cached)", 3+ executed; final file frame-exact
```
Plus tests: manifest rejects an unknown op / missing input / non-zero cost with cap $0 / a visual asset whose origin is not in {footage, user_image, code_graphic, stock_licensed};
approval gate blocks until approved; a corrupted checkpoint is detected, not trusted. At least one step ran through Kinocut and one through direct FFmpeg, both shown in the manifest with `executor_reason`.

## M4 - Move Recap Studio's editing onto the engine (only where M2 proved parity)

Objective: remove duplicated editing infrastructure without breaking recaps.

Steps
1. From `docs/CAPABILITY_MATRIX.md` list the ops whose chosen executor is `kinocut` or `ffmpeg` AND that the current `recap.py` implements itself.
2. For each, one at a time: add a thin bridge in a NEW module (`recapstudio/_template/engine_bridge.py`) that calls `cutwright.engine` (path-safe import or subprocess `python -m cutwright run`); change the call site in `recap.py` to use it (3-10 line edits, never a rewrite); run the Regression pack; compare the output with the pre-change output (frame count equal, `frame_ids` equal on fixtures, durations within 1 frame, loudness within 0.5 LU).
3. Ops where Kinocut failed in M2 and `current` or `ffmpeg` won: leave in place; if the current code is a one-off, move it into `engine/executors/ffmpeg.py` as a named op with its validator. Do not leave two implementations of one op.
4. After ALL swapped ops pass: delete the superseded functions in `recap.py` in a separate commit ("remove superseded ffmpeg code") and update `docs/CODEMAP.md` line index. Git history is the fallback; do not add runtime "legacy" switches.
5. Real job: build a 60-90 s recap from the demo media plus one real footage clip (owner supplies or `testclips\`), voice by Edge-TTS, captions via Remotion, final through the engine. Then look at 6 frames (start, 25%, 50%, 75%, a transition, end) and describe concrete defects, if any.

Acceptance
```powershell
# Regression pack passes with the same key lines as in M0 (frame counts equal)
python -m unittest discover -s tests -t . -v
python -m cutwright status recapstudio\Projects\<job>\production\<run> --json     # every step done; executors listed
Select-String -Path recapstudio\_template\recap.py -Pattern "write_concat_list|join_av|fit_graph"   # shows only what was deliberately kept
```
LOG lists: which ops moved, which stayed and why, line count of `recap.py` before/after, and the real-job result with the six-frame review.

## M5 - Remove Shotcut from the architecture

Objective: Shotcut leaves the code, config, docs and tests. Not kept as a fallback.

Preconditions: M4 acceptance met; every row in `docs/MIGRATION_CHECKLIST.md` section "Shotcut capabilities and their replacements" has a replacement that passed (or an owner-approved "dropped" decision).
Steps: follow `docs/MIGRATION_CHECKLIST.md` section "Deletion order". Summary: delete `cutwright/mlt.py`, `cutwright/gui.py`, `cutwright/tools/shotcut_window.ps1`, the `build` command and the Shotcut lines of `doctor` in `cutwright/cli.py`, `projects/demo_*/*.mlt`, `shotcut/` (local folder, owner-approved size 522 MB), and the Shotcut sections of README/docs/PROVENANCE/.gitignore. Convert `projects/demo_*/plan.json` into manifest examples under `examples/` if they still teach something; otherwise delete. Keep `vendor/videopad/` (not Shotcut).
Acceptance
```powershell
git grep -n -i "shotcut\|melt\.exe\|\.mlt" -- . ":(exclude)LOG.md" ":(exclude)docs/legacy" ":(exclude)docs/MIGRATION_CHECKLIST.md" ":(exclude)docs/REFERENCES.md" ":(exclude)COMMS.md" ":(exclude)docs/GOALS.md" ":(exclude)docs/BORROW_notes.md" ":(exclude)docs/ROADMAP.md" ":(exclude)docs/ARCHITECTURE.md"
#   -> no output. (Historical mentions only in the excluded files.)
python -m cutwright doctor          # no Shotcut line; Kinocut + ffmpeg lines present and OK
python -m unittest discover -s tests -t . -v
# Regression pack passes
```

## M6 - Agent bridge and focused tool discovery (old G4 + discovery)

Objective: the agent drives everything through typed commands with `--json`, never raw shell.
Spec: `docs/GOALS.md` section G4 (bridge `python -m cutwright recap <step> --json`, forbidden flags refused) plus: `tools envelope --stage <stage>` and the stage skills in `skills/`.
Keep Kinocut's own MCP server OUT of the default setup (our registry already narrows tools); optional later (M14).
Acceptance
```powershell
python -m cutwright recap check --project g0test --json
python -m cutwright recap tts --force --project g0test --json     # must REFUSE (forbidden flag) and say why
python -m cutwright tools envelope --stage edit --json             # <= 10 ops, each with schema
```
Plus the G4 "Done when": new project -> demo -> timeline -> render using only the CLI.

## M7 - Agent-owned scene loop (old G5)

Spec: `docs/GOALS.md` section G5 unchanged (write TSX, static check, test render, look at frames, revise max 2 rounds), plus: scenes use only code graphics/footage/user images; the validator's provenance check runs on scene output.
First step of the milestone is still "can DeepSeek see images through Cline?" (HANDOFF known-unverified). If not, use `scene sheet` PNG metrics plus the owner's verdict and say so.
Acceptance: G5 "Done when" (agent writes 3 scenes, >= 2 pass first try, one revised after viewing frames), quoted.

## M8 - Visual quality overhaul and benchmark (old G6)

Spec: `docs/GOALS.md` section G6 and `docs/VISUAL_STANDARD.md` unchanged. Output: five distinct benchmark scenes at 16:9 and 9:16 (`benchmark/scenes/*.tsx`, props, expected durations). The owner approves >= 4 of 5. The five scenes are the fixed input for M9.
Acceptance: G6 "Done when". Also `python -m cutwright validate` reports slideshow_risk below the "high" threshold for the benchmark reel (thresholds defined in `engine/validate.py`, documented in the file header).

## M9 - HyperFrames benchmark and renderer decision (evidence first)

Objective: decide whether HyperFrames simplifies or complements Remotion. Remotion stays the renderer until the owner decides after this report.
Preconditions: M8 done (five scenes). Install only in an isolated folder `bench\hyperframes\` (gitignored). Needs Node 22+: check `node --version`; if lower, install Node 22 in an isolated way (e.g. portable zip in `bench\node22\`) - do NOT upgrade the system Node that Remotion uses without the owner. If it cannot be done cleanly, write that as the finding.
Measure for the same five scenes (agent-written in HTML/CSS/GSAP vs the existing TSX):
install size and time; render frames/s at 1080p24 on this PC (3 runs, median); peak RAM; first-try pass rate of an agent author (5 scenes each); lines of code per scene; failure modes; transparent/alpha output support and Windows behaviour; determinism (render twice, compare hashes); the Kinocut `hyperframes-*` commands (do they work with our installed pin? which CLI version do they demand?); owner's visual verdict (blind A/B of the same scene).
Deliverable: `docs/BAKEOFF_hyperframes.md` with the table and a recommendation: `keep Remotion only` | `HyperFrames optional per scene type` | `migrate` (needs a migration plan).
Decision rule (recommendation, owner decides): do not run two stacks unless HyperFrames is >= 25% faster on the i5, OR beats Remotion's first-try pass rate by >= 20 points, AND the owner approves its look on >= 4 of 5 scenes, AND install/maintenance cost is stated. Otherwise recommend Remotion only and remove the bench folder.
Acceptance: the doc exists with measured numbers (no "expected" figures); commands used are quoted.

## M10 - Perception to script (old G7)

Spec: `docs/GOALS.md` G7. Use Kinocut scene detection / quality tools only if M2 showed they beat `cutwright/moments.py` and `frames.py`; otherwise keep ours (record the comparison). Transcription stays whisper.cpp / faster-whisper.
Acceptance: G7 "Done when" (video in -> valid `segments.json`, no human paste, on a dialogue clip and a silent clip).

## M11 - Production blueprint and any-video profiles (old G8 + G9, without Shotcut)

The blueprint IS `pipelines/*.json` + profiles + the manifest. G8's "compiles to a Shotcut project" is CANCELLED; replace by "one blueprint compiles to a Remotion recap and a Remotion-free explainer through the same manifest".
Spec: `docs/GOALS.md` G9 (format profiles, no-footage mode, asset providers = footage / user images / code graphics / licensed stock only).
Acceptance: three different videos (movie recap, no-footage explainer, data story) render, look different, and each production report lists asset origins with zero AI-generated items.

## M12 - SFX engine (old G11)
Spec: `docs/GOALS.md` G11. SFX are mixed through the engine's `mix_audio` op (never a one-off ffmpeg call). Free/offline sources only, CC-BY credits recorded in `credits.txt`.
Acceptance: G11 "Done when" (automatic + scripted SFX, consistent loudness measured with ebur128, credits, works offline), quoted.

## M13 - Polish, true 9:16 and speed (old G12 + G13)
Specs: `docs/GOALS.md` G12, G13. Speed = manifest step caching + overlay-only re-render: after editing one segment, re-render time < 20% of the full render, measured and quoted.
Acceptance: the same timeline renders cleanly at 16:9 and 9:16 with captions in safe zones (frame review), and the 20% number.

## M14 - MCP server and portable skill (old G14)
Spec: `docs/GOALS.md` G14. May expose our registry over MCP and may reuse Kinocut's own MCP server for editing tools (check `KINOCUT_TOOLS=profile:editor`). Adds a portable `SKILL.md` describing the plan -> manifest -> validate loop.
Acceptance: a second agent completes a small job using only the skill/MCP, quoted.

## M15 - Cutwright Studio (old G15)
Spec: `docs/GOALS.md` G15. The UI must show the manifest, checkpoints and approval gates (a plain page reading `production/<run>/*.json` is enough).
Acceptance: a human makes one full video without the command line (owner verdict).

## M16 - Other modules and optional borrows (old G16)
Spec: `docs/GOALS.md` G16. Optional borrows default OFF; each needs a licence check in `PROVENANCE.md`. No generative-image providers, no FireRed.
Acceptance: every module has a preset + prompt profile.

---

## Old goal -> new milestone

| Old | Status |
|---|---|
| G0 baseline | merged into M0 |
| G1 Shotcut crossfade | CANCELLED (crossfade comes from the M2 transition test; executor chosen by evidence) |
| G2 recon of cli-anything-shotcut / Shotcut MCP / NarratoAI | CANCELLED (Kinocut recon is M1; NarratoAI optional later, G16) |
| G3 adopt cli-anything-shotcut | CANCELLED |
| G4 recap bridge | M6 |
| G5 scene loop | M7 |
| G6 visual quality | M8 |
| G7 perception to script | M10 |
| G8 blueprint/backend interface | M3 (skeleton) + M11 (blueprints) |
| G9 any kind of video | M11 |
| G10 HyperFrames bake-off | M9 |
| G11-G16 | M12-M16 |

## What "done" means for the whole project

The agent receives a brief and assets, plans, produces scenes and edits through Kinocut/FFmpeg/Remotion with a recorded manifest, previews, validates, looks at frames, fixes named defects, renders the final, and writes a report. A second run on the same manifest resumes or reproduces it. Shotcut is gone, FireRed is absent, no AI image exists anywhere in a produced video, and every claim in `LOG.md` has quoted proof.
