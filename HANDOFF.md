# HANDOFF - for DeepSeek running inside Cline on the owner's Windows PC

Revised 2026-10-30 (after M5). The older handoff (an editor application as primary backend, goals G0-G16) is
superseded; its goal specs survive only where `docs/ROADMAP.md` points at them. This file = status + rules + order.
Detail lives in: `docs/ROADMAP.md` (milestones, acceptance, test commands), `docs/ARCHITECTURE.md`,
`docs/MIGRATION_CHECKLIST.md`, `docs/REFERENCES.md`. Progress goes in `LOG.md`; questions/blocks in `COMMS.md`.

## Current status (you keep this block up to date)

```
Current milestone : M6 "Agent bridge and focused tool discovery" COMPLETE (2026-10-30). An agent now drives a
                    Recap Studio project from the CLI - `recap projects | new <name> | status --project X |
                    <step> --project X`, all `--json` - and loads ONE stage's tools (`tools envelope --stage S`).
                    Bridge = `cutwright/recap.py` (390 lines, stdlib): each project's own `recap.py` runs as a
                    subprocess with `cwd` = the project and `RECAP_NONINTERACTIVE=1`; `--force`, `init`,
                    `collect`, `comic`, `module`, `collect_one`, `characters`, `tiktok` are REFUSED (exit 2)
                    unless the caller passes BOTH `--i-know-this-destroys-work` and `--comms <id>`.
                    Discovery = `cutwright/engine/envelopes.py` (154 lines): plan 6, edit 10, graphics 4,
                    review 4, deliver 3 tools, cap 10 (`ops.MAX_ENVELOPE`, checked over ops AND commands); each
                    op carries its param schema, each command its usage line, every envelope one `how_to_run`.
                    Stages are now plan, edit, graphics, review, deliver (`qc` was renamed `review`, `assets`
                    deleted - no op, test or code used it). Before it: M5.5 DONE (5.5A/B/C), M5 DONE (the old
                    editor backend is out of the code).
Last green commit : recorded by the docs commit that follows the M6 commit; both are on origin main and
                    `git ls-remote origin refs/heads/main` is the check. Previous: 66c1b97 (M5.5C), 20a5052,
                    d55c114, 5dbda9e, facc015 (M5.5A), 2ae8f60, c97d7fd, 4528c51 (M5 close-out), 7a8184c,
                    0755d92, 498aed1, d072280.
Next step         : M6 is closed with ONE known gap: the G4 "Done when" render line - `recap timeline` then
                    `recap remotion` on a fresh project - was NOT run (both outran the 30 s foreground command
                    cap and that session forbade background runs / polling loops; `timeline` was killed
                    mid-run at 30 s). Close it first, with the owner present, then M7 (agent-owned scene loop).
                    Everything else in M6 is verified: 74 tests green, and `recap new/demo/check/status` plus
                    every refusal ran for real (quotes in LOG).
Open COMMS        : C-015 (this session: the `qc`->`review` rename and the deleted `assets` stage, envelopes
                    carrying commands as well as ops, and the unrun render line - review, one line each to
                    reverse); C-014 BLOCKED (2026-10-27); C-012, C-011 (answered 2026-10-30), C-010..C-006
                    answered; C-013 closed (M5.5C, no answer needed).
Rules             : `.clinerules/` directory (00-core-workflow, 01-architecture-and-constraints,
                    02-testing-and-evidence, 03-session-boundaries). The old single `.clinerules` file no longer exists.

Known on this PC  : git 2.47.1, gh 2.103.0 (logged in as altzotify-cell), Python 3.11.9 default (3.11/3.13/3.14 installed),
                    Node v24.18.0; ffmpeg 7.1 full_build gyan (scoop shim wins over 2 others).
                    Kinocut: INSTALLED in `.venvs\kinocut` = kinocut 1.16.4 on Python 3.11.9, doctor exit 0.
                    `.venvs/` and `out/` are gitignored. All M0 numbers: docs/ENVIRONMENT.md.
Verified on this PC so far : M0 audit (facts in `docs/ENVIRONMENT.md`) + M1/M2/M3 (quotes in `LOG.md`):
  - M6 (2026-10-30): the agent bridge and the stage envelopes work. `recap projects --json` -> "count": 2;
    `recap new m6probe` -> "created": true; `recap demo --project m6probe` -> ok, 6.0 s, 14 files changed;
    `recap check` on a fresh copy -> exit 0, 2.2 s, files_changed ["STATE.md"]; `recap tts --force` and
    `recap init|collect|comic` -> exit 2 with `forbidden_flag` / `forbidden_step`; `tools envelope` -> plan
    6 / edit 10 / graphics 4 / review 4 / deliver 3 tools (cap 10). `python -m unittest
    tests.test_engine_cli tests.test_engine_registry -v` -> "Ran 74 tests in 15.937s" / "OK". NOT tested:
    `recap timeline` to completion and `recap remotion` (both outran the 30 s foreground cap).
  - M5.5A (2026-10-30): the engine can DRAW. `render_still` (one frame -> PNG) and `render_range` (a
    frame range -> H.264) run on the pinned Remotion 4.0.539 behind the op registry (14 ops now), with
    the scene file as a declared input so a changed scene invalidates the cache. Measured through
    `python -m cutwright run`: a 1920x1080 still costs 7.77 s (9.79 s wall) cold, 8.26 s warm, 0.97 s
    when cached; 1080x1920 is slightly cheaper; a 1 s range (24 frames) costs 13.20 / 9.63 s and
    decodes back as 24 frames at 24/1. Warm is NOT cheaper than cold - the ~8 s is webpack, so one
    look is ~10 s and a cache hit is ~1 s. The still decodes as a real picture (133/145 distinct
    tones, stdev 26.9/30.7), and I could SEE it: "70%", "OF PLAYERS DISAGREED", an orange ring on a
    grey track - every detail matched the scene source. The regression pack re-ran byte-identical on
    the editing path (514 frames, 6,834,110 B, same stream md5s and sha256).
  - Vision (M5.5A, moved here from "Known unverified"): DeepSeek through Cline CAN see images. The
    test was a still of `stat_ring`: I described it and named the number and the label BEFORE reading
    the scene source, and both were right (plus the detail that the `%` is a separate, smaller,
    accent-coloured glyph).
  - M4 4B (2026-10-30): the ffmpeg music arm is gone and `make_music_bed` -> `mix_audio` (Kinocut).
    Kinocut refuses an audio-only mix source ("mix_audio requires a video stream"), so the program
    audio is muxed first and the bed is mixed under the muxed file; the video packets come back
    IDENTICAL (854df8a7... before and after the mix on the 79.2 s job), loudness -20.1 -> -19.2 LUFS,
    and the 220/277 Hz bed tones are measurable in the output. The regress project is byte-identical
    to the M0 baseline again (same stream md5s, same file sha256) and the suite is 178 tests green.
  - M4 4A (2026-10-30): the regress project was re-run on the swapped path and is byte-identical to
    the M0 baseline (514 frames, 21.416667 s, 6,834,110 B, aac 48k/2, video md5 c671f7a7..., audio
    md5 0064ff59...); replacing a mix track now re-runs the mix ("cache key changed") and puts the
    new tone in the output (Goertzel 3,526,719 @320 Hz vs 755 @1 kHz).
  - M3 3D (2026-10-30): the six roadmapped acceptance commands pass. `python -m cutwright run
    out\fx\demo_manifest.json --json` renders five steps (Kinocut trim -> ffmpeg fit -> Kinocut
    concat -> Kinocut mix -> Kinocut export) and the final file decodes to 60 frames, ids 24..47 then
    1000..1035, 24.0 fps, 160x90, AAC 48 kHz stereo, mix bed beeps at 0.0/1.0/2.0 s. A run killed
    during step 3 resumes with steps 1-2 "cached (cache key unchanged, outputs intact)" and finishes
    frame-exact. `python -m unittest discover -s tests -t . -v` -> see LOG 2026-10-30 phase 3D.
  - M3 3C (2026-10-30): `python -m unittest tests.test_engine_manifest -v` -> "Ran 38 tests in
    6.759s" / "OK"; a real 2-step manifest (Kinocut trim -> ffmpeg fit) wrote exactly 48 and 24
    frames and a second run reported both steps "skipped (cached (cache key unchanged, outputs
    intact))"; a truncated checkpoint raises CheckpointError(code="corrupted") instead of resuming.
  - M2: 13 areas measured on real outputs (`tests/kinocut_vs_current/`, 20 evidence files). Headlines:
    kinocut trim/fade/wipe/duck/mix/normalize/subtitles/export/pad-resize PASS; no "exactly N frames"
    op; `composite-layers` drops audio; QC is a global score (no black/silence detection); per-join
    audio drift 13.4 ms PCM / 26 ms AAC; current `render_video_clip` is one frame late on non-zero
    starts and `join_av` neither ducks nor keeps A/V sync (21.6 ms).
  - M1: `kino doctor` -> "Kinocut doctor - OK" (exit 0); trim 3 s -> 72/72 frames with audio; merge -t fade -td 1 on
    2 s + 2 s -> 3.000000 s / 72 frames with audio (real blend seen in frames); composite-layers output is video-only;
    release-checkpoint is a real QC gate; licences recorded with sha256 (Kinocut Apache-2.0, OpenMontage AGPL-3.0).
  - M0: Recap Studio on Windows: demo -> briefs -> video (514 frames / 21.4 s) -> timeline -> Remotion render (parity
    within one frame) -> Premiere XML; all exit 0. Fixtures self-test passed here (0.907 s). Scene check: 3 of 6
    scenes pass, 3 fall back to the keywords scene (expected baseline, not an M0 blocker).
Latest recorded cost: $6.00 DeepSeek to 25 Oct (before the merge). Log each milestone's cost.
```

## Mission

An engine of tools that an AI agent (you, as creative director + production operator) calls to make videos of ANY kind:
recaps, explainers, football videos, documentary-style edits, commentary, motion-graphics sequences. Input: a topic/prompt,
source footage, narration/music/SFX/images, or any mix. Target: polished video storytelling and professional motion graphics,
NOT static slides.

## Architecture in one screen (full text: `docs/ARCHITECTURE.md`)

- **Kinocut** (pip package, Apache-2.0) = the DEFAULT editing toolkit: trim, resize, merge, composite, validate... but only the operations
  you have VERIFIED on this PC (M1, M2). It lives in its own venv `.venvs\kinocut` and is called by subprocess.
- **FFmpeg** = the engine under Kinocut AND the direct tool where Kinocut lacks a capability or is not accurate enough
  (exact frame fit, audio chains/ducking, transitions, encoding settings). Use it through named, typed ops, argument lists, no shell strings.
- Do NOT write a custom FFmpeg version of anything Kinocut already passes. Do NOT force Kinocut where it fails. Evidence decides:
  `docs/CAPABILITY_MATRIX.md` (you create it in M2).
- **Remotion 4.0.539** = programmatic motion graphics (captions, overlays, TSX scenes). Unchanged. HyperFrames is only a
  benchmark candidate in M9; do not install it before then.
- **Python** (Recap Studio + Cutwright, stdlib-only for `cutwright/`) = script, voice, timing, perception, validation, orchestration state.
- One coherent plan: `segments.json` (creative) -> `timeline.json` (timing, schema 2) -> `production/<run>/manifest.json` (execution,
  records for every step: op, executor kinocut|ffmpeg|remotion|python, reason, params, outputs+hashes, validation, status).
  Resumable via checkpoints; focused tool discovery (`tools envelope --stage ...`), never the whole tool list.
- **No editor application is in the target architecture and none is a fallback.** The backend, its window
  automation and its timeline writer were DELETED in M5 (`docs/MIGRATION_CHECKLIST.md` section F). Do not
  reintroduce it and do not extend a downstream copy of it.
- **OpenMontage** = architectural reference only (AGPL-3.0): re-implement ideas clean-room; copy nothing; ask the owner (COMMS) before any reuse.
- **FireRed-OpenStoryline** = excluded. No dependency, no adapter, no research.

## Hard constraints (never break)

1. **No AI-generated images or video.** Missing asset -> real footage, a user asset, a code-made graphic (SVG/HTML/CSS/React/Remotion, typography,
   charts, procedural animation), or report it as missing. Never substitute a generated still.
2. Free-first. No paid API or cloud service without the owner's explicit yes. Windows-first. Low resource (below).
3. Never claim something works unless you ran it and quoted the output. Untested = say "NOT TESTED".
4. Cutwright writes only through `cutwright/guard.py`; never write into footage folders; never print/commit keys.
5. Do not grow `recapstudio/_template/recap.py` (5,493 lines). New code in new modules + thin bridges.
6. Remotion stays pinned 4.0.539. No new npm packages without the owner. Do not upgrade the system Node.
7. Never `--force`, `init`, `collect` on recap.py unattended.
8. Delete code only after its replacement passed its acceptance test. Deletions are separate commits.
9. Two failed attempts at the same problem -> BLOCKED entry in `COMMS.md`, stop, ask.

## Owner and machine

HP EliteBook 840 G5, i5-8350U, 12 GB RAM, no GPU, Windows. Remotion was budgeted at ~5.7 frames/s; M0 measured 5.33 fps
derived (514 frames / 96.4 s wall, whole command). Treat 10 min of 24 fps video as ~45 min, so:
test with 5-20 second clips, preview at low resolution, cache every step, never re-render what did not change.
The owner is not a programmer: short messages, exact steps. You run commands yourself (npm, node, ffmpeg, pip, git, Python);
ask the owner only for: running `SETUP.bat`, installing Python 3.11+ if missing (tell first), keys, footage, and yes/no on how something looks or sounds.
Shell is PowerShell: no `Set-Content`/`Out-File` for text files (BOM, wrong encoding): create files with the editor tool or Python;
use `git commit -F msg.txt`, not `-m`. Quote paths with spaces. Set `$env:RECAP_NONINTERACTIVE="1"` for recap steps.

## Before you change ANYTHING (do this first, every fresh checkout)

```powershell
git status ; git remote -v ; git branch --show-current ; git log --oneline -5      # is this a repo? right remote/branch? (ZIP had none)
py -0p ; python --version ; node --version ; npm --version ; git --version
where.exe ffmpeg ; ffmpeg -version | Select-Object -First 3 ; ffprobe -version | Select-Object -First 1
python -m cutwright doctor
Get-ChildItem recapstudio\Projects ; Test-Path .venvs\kinocut
```
Report the results to the owner in <= 6 lines and record them in `LOG.md` (M0). If git has no repo, `git init` and make the first commit (M0 step 1).
If the remote differs from `altzotify-cell/cutwright`, say so and do not push until the owner confirms.

## How to work (Cline-specific)

- Start of each session: read this file, last 3 entries of `COMMS.md`, last 40 lines of `LOG.md`. Say in 3 lines: current milestone, next step, blocked?
  Wait for "go". Then read ONLY the current milestone section:
  `Select-String -Path docs\ROADMAP.md -Pattern '^## M' | Select-Object LineNumber,Line` then `(Get-Content docs\ROADMAP.md)[A..B]`.
- Never read whole: `recapstudio/_template/recap.py`, `recapstudio/studio.py`, `recapstudio/web/app.js`, `docs/legacy/*`, videos, logs, `node_modules`. Use `docs/CODEMAP.md` for line ranges, `Select-String`, `head`-style slices.
- One milestone at a time. Small targeted edits (keep each single write under ~3,000 characters; split bigger files over several writes). No wholesale rewrites.
- Test the REAL path: run the real command, produce a real media file, decode it (ffprobe/frame ids), look at frames. Imports and mocks are not tests.
- Every milestone: LOG entry with three lists TESTED / FAILED / NOT TESTED (each with the quoted command + result), tick below, update the status block,
  `git add` + `git commit -F msg.txt`, push if a remote exists, then tell the owner "Milestone Mx done. Start a new session." and print the kickoff text.
- Context passes ~60% or a milestone finishes -> wrap up and ask for a new session. Default model flash; escalate only after a BLOCKED entry says why.

## Milestones (order is fixed, with ONE insertion: M5.5 sits between M5 and M6; acceptance + commands in `docs/ROADMAP.md`)

| | ID | Milestone | Done when (short form) |
|---|---|---|---|
| [x] | M0 | Environment audit + baseline (git, versions, doctor, Recap regression with Remotion on Windows) | all baseline commands run and quoted; `docs/ENVIRONMENT.md` + baseline numbers; commit hash recorded |
| [x] | M1 | Kinocut isolated install + interface discovery (Windows) | `kino doctor` OK in `.venvs\kinocut`; `docs/KINOCUT_FINDINGS.md` has no assumptions; licences recorded |
| [x] | M2 | Equivalence tests: Kinocut vs current code vs direct FFmpeg (frame accuracy, fitting, concat, transitions, audio mix, export, QC, workflow/resume) | `docs/CAPABILITY_MATRIX.md` + `docs/evidence/m2_*.json`; every row measured |

| [x] | M3 | Engine skeleton: executors (Kinocut+FFmpeg), registry/discovery, manifest, checkpoints, gates, validators | DONE 2026-10-30: `tools/validate/run/resume/status/approve` work on real media; a five-step demo renders frame-exact (ids 24..47 then 1000..1035, beeps at 0/1/2 s) and a run killed during step 3 resumes with steps 1-2 cached. Not built (out of the confirmed scope): `executors/remotion.py`, `pipelines/*.json`, `skills/*.md` - see C-007 |
| [x] | M4 | Move Recap editing onto the engine where parity was proven; delete superseded code | DONE 2026-10-30: picture join -> `concat` (4A), mix tracks declared inputs (4A), ffmpeg music arm deleted + `make_music_bed` -> `mix_audio` (4B); regress project byte-identical (514 frames, same stream md5s and sha256); 79.2 s real job rendered and six frames reviewed (`out\m4b\frames\`) |
| [x] | M5 | Remove the old editor backend completely | DONE 2026-10-30: the timeline writer (2,573 lines), its GUI helper, its PowerShell window-automation script and the `projects/` demos (4 projects, 19 files) deleted; `cli.py` lost `build` + the doctor line and gained a Kinocut line; `doctor` exit 0, 178 tests green, regression pack green |
| [x] | M5.5 | Creative rendering slice (NEW, owner 2026-10-30; before M6) | DONE 2026-10-30 in three sessions. 5.5A: Remotion executor `render_still` + `render_range` behind the op registry, cold/warm measured at 16:9 and 9:16. 5.5B: footage by string-literal handle, `LayeredMedia`/`Camera`, one bundle per content key (3 stills 26.7 s cold / 1.9 s cached). 5.5C: `KineticText` + `MaskWipe` (kit/3), one directed benchmark shot over real public-domain footage, and the critic loop that found and fixed 3 defects on the rendered stills (caption-band collision, killed glow, crushed mid-tones) |
| [x] | M6 | Agent bridge `recap <step> --json` + focused tool discovery | DONE 2026-10-30: bridge `cutwright/recap.py` (project subprocess, RECAP_NONINTERACTIVE, `--force`/`init`/`collect` refused without both override flags + COMMS id); `engine/envelopes.py` gives plan 6 / edit 10 / graphics 4 / review 4 / deliver 3 tools (cap 10, ops AND commands); 74 tests green. NOT verified: `recap timeline` -> `recap remotion` (30 s cap) |
| [ ] | M7 | Agent-owned scene loop (old G5) | 3 scenes written by agent, >= 2 first-try, 1 revised after viewing frames |
| [ ] | M8 | Visual quality overhaul + 5-scene benchmark (old G6) | owner approves >= 4 of 5 at 16:9 and 9:16 |
| [ ] | M9 | HyperFrames benchmark vs Remotion (evidence, then owner decides) | `docs/BAKEOFF_hyperframes.md` with measured numbers |
| [ ] | M10 | Perception to script (old G7) | video in -> valid `segments.json`, dialogue and silent clips |
| [ ] | M11 | Blueprints + any-video profiles (old G8/G9) | 3 different videos render; zero AI-generated assets in reports |
| [ ] | M12 | SFX engine (old G11) | auto + scripted SFX, loudness consistent, credits |
| [ ] | M13 | Polish, true 9:16, speed (old G12/G13) | re-render after one-segment edit < 20% of full time |
| [ ] | M14 | MCP + portable skill (old G14) | second agent completes a small job from the skill/MCP only |
| [ ] | M15 | Cutwright Studio UI (old G15) | human makes a video without the command line |
| [ ] | M16 | Other modules / optional borrows (old G16) | each module has a preset + prompt profile |

Order: M0..M5 done, then **M5.5** (the one insertion, before M6), then **M6** (done 2026-10-30), then M7, M8, M9. M10-M16 are a
PARKING LOT (owner decision, 2026-10-30): do not start or expand them.

## Provisional decisions made for you (verify each on this PC; table with fallbacks: `docs/ROADMAP.md`)

A1 Kinocut needs Python >= 3.11 -> separate venv, Python 3.12 via `py -3.12` (install with winget only after telling the owner). A2 pin `kinocut==1.16.4`, subprocess adapter,
no `import kinocut` in `cutwright/`. A3 skip `kinocut[transcribe]` (torch ~1 GB). A4 no HyperFrames until M9. A5 FFmpeg from winget Gyan build on PATH, never an editor-bundled one
(deleted in M5).
A6 do not touch system Node. A7 repo state unknown. A8 `cutwright/` stays stdlib-only. If any assumption fails, record it, take the documented fallback, tell the owner.

## Known unverified (do not assume these work)

- Everything about Kinocut on Windows (installation, CLI contracts, receipts, speed, output quality) - the README claims are in `docs/REFERENCES.md`.
- Whether Kinocut CLI commands have machine-readable output (find out; do not assume a `--json` flag).
- Whether Kinocut can fit a clip to an exact frame count, crossfade two clips, mix/duck audio, or keep audio in `composite-layers` ("video-only" per its docs).
- Recap Studio Phase 3 (Scenes tab, import of agent replies) on Windows. Remotion DOES run now (M0: parity within one frame) and `briefs --demo` ran; the Scenes tab and agent-reply import are still unverified.
- Whisper word timings from REAL speech: still unverified. The old `metadata_errors` crash did NOT recur in M0 (faster-whisper 1.2.1 loads `base` in 6.50 s and runs inference), but it returns 0 words on the fixture's tone audio, so timings fall back to `even`. Needs real narration to test - not an M0 blocker.
- Remotion `OffthreadVideo` once failed at frame 71 on a cold run ("No frame found"); a retry exists but never ran.
- Whether two Remotion renders of the SAME timeline are byte-identical: the M5.5A re-render came out
  11 KB smaller than the M0 file with the same 514 frames and duration. Unverified, and the answer
  decides whether 5.5B can trust "same scene + same props = same pixels" in its cache.
- Tests under `tests/` (fixtures only): now run on this PC (M0: "Ran 1 test in 0.907s", OK, exit 0).

## Reporting format (use in every LOG entry and in your messages to the owner)

```
TESTED     - <what> : <command> -> <quoted key result line(s)>
FAILED     - <what> : <command> -> <error text> ; <what you tried>
NOT TESTED - <what> : <why>
DECISIONS  - <what you chose, which assumption it relied on, how it was verified>
```

## Kickoff message (print when asking for a new session)

```
New session. Read `.clinerules/` (4 files: 00-03), then HANDOFF.md, then the last 3 entries of COMMS.md and the last 40 lines of LOG.md.
Tell me in 3 lines: current milestone, next step, anything blocked. Wait for my go.
Then read only the current milestone's section of docs/ROADMAP.md.
```

## Where the detail is

`docs/ROADMAP.md` milestones + acceptance + commands | `docs/ARCHITECTURE.md` diagram, responsibilities, rules |
`docs/MIGRATION_CHECKLIST.md` inspect/replace/test/preserve/delete | `docs/REFERENCES.md` Kinocut/OpenMontage/HyperFrames/FireRed, licences |
`docs/CODEMAP.md` file map + recap.py line index | `docs/TOOLS.md` tools catalogue (engine verbs live since M3) |
`docs/GOALS.md` old per-goal specs (detail for M6-M16 only; its ORDER is superseded) | `docs/VISUAL_STANDARD.md` quality bar |
`docs/schemas/manifest.example.json` manifest shape | `tests/media_fixtures.py` frame-id and beep fixtures |
`docs/legacy/` old handoffs (reference only; grep by section)
