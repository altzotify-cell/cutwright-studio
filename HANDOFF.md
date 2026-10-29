# HANDOFF - for DeepSeek running inside Cline on the owner's Windows PC

Revised 2026-10-29 (architecture change: Kinocut-first). The older handoff (Shotcut as primary backend, goals G0-G16) is
superseded; its goal specs survive only where `docs/ROADMAP.md` points at them. This file = status + rules + order.
Detail lives in: `docs/ROADMAP.md` (milestones, acceptance, test commands), `docs/ARCHITECTURE.md`,
`docs/MIGRATION_CHECKLIST.md`, `docs/REFERENCES.md`. Progress goes in `LOG.md`; questions/blocks in `COMMS.md`.

## Current status (you keep this block up to date)

```
Current milestone : M0  (environment audit and baseline)        status: NOT STARTED
Last green commit : none yet. Last commit f621e5f on main (initial import, pushed 2026-10-29 to
                    github.com/altzotify-cell/cutwright-studio)
Next step         : M0 step 2 - record versions (py -0p, python, node, npm, ffmpeg, ffprobe, doctor), then the baseline (step 1 git is done)
Open COMMS        : none required; C-003 (handoff note) and C-004 (new repo + rules split) are INFO
Rules             : `.clinerules/` directory (00-core-workflow, 01-architecture-and-constraints, 02-testing-and-evidence,
                    03-session-boundaries). The old single `.clinerules` file no longer exists.
Known on this PC  : git 2.47.1, gh 2.103.0 (logged in as altzotify-cell), Python 3.11.9 default (3.11/3.13/3.14 installed),
                    Node v24.18.0. ffmpeg, Kinocut, Remotion: NOT checked yet.
Verified on this PC so far : git/GitHub only. The consultant that prepared this ZIP had no network and ran only a Linux sandbox:
  - Python half of Recap Studio (demo -> video -> timeline) ran there: 514 frames / 21.4 s. Remotion, Kinocut, Windows: NOT run.
  - tests/media_fixtures.py round-trip passed on Linux (ffmpeg 6.1). Not run on Windows.
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
- **Shotcut is NOT in the target architecture and is not a fallback.** Remove it in M5, after replacements passed
  (`docs/MIGRATION_CHECKLIST.md`). Do not extend Shotcut code. Do not run `build`.
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

HP EliteBook 840 G5, i5-8350U, 12 GB RAM, no GPU, Windows. Remotion renders ~5.7 frames/s (10 min of 24 fps video = ~45 min), so:
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
Get-ChildItem recapstudio\Projects ; Test-Path shotcut ; Test-Path .venvs\kinocut
```
Report the results to the owner in <= 6 lines and record them in `LOG.md` (M0). If git has no repo, `git init` and make the first commit (M0 step 1).
If the remote differs from `altzotify-cell/cutwright`, say so and do not push until the owner confirms.

## How to work (Cline-specific)

- Start of each session: read this file, last 3 entries of `COMMS.md`, last 40 lines of `LOG.md`. Say in 3 lines: current milestone, next step, blocked?
  Wait for "go". Then read ONLY the current milestone section:
  `Select-String -Path docs\ROADMAP.md -Pattern '^## M' | Select-Object LineNumber,Line` then `(Get-Content docs\ROADMAP.md)[A..B]`.
- Never read whole: `recapstudio/_template/recap.py`, `recapstudio/studio.py`, `recapstudio/web/app.js`, `cutwright/mlt.py`, `docs/legacy/*`, videos, logs, `node_modules`. Use `docs/CODEMAP.md` for line ranges, `Select-String`, `head`-style slices.
- One milestone at a time. Small targeted edits (keep each single write under ~3,000 characters; split bigger files over several writes). No wholesale rewrites.
- Test the REAL path: run the real command, produce a real media file, decode it (ffprobe/frame ids), look at frames. Imports and mocks are not tests.
- Every milestone: LOG entry with three lists TESTED / FAILED / NOT TESTED (each with the quoted command + result), tick below, update the status block,
  `git add` + `git commit -F msg.txt`, push if a remote exists, then tell the owner "Milestone Mx done. Start a new session." and print the kickoff text.
- Context passes ~60% or a milestone finishes -> wrap up and ask for a new session. Default model flash; escalate only after a BLOCKED entry says why.

## Milestones (order is fixed; acceptance + commands in `docs/ROADMAP.md`)

| | ID | Milestone | Done when (short form) |
|---|---|---|---|
| [ ] | M0 | Environment audit + baseline (git, versions, doctor, Recap regression with Remotion on Windows) | all baseline commands run and quoted; `docs/ENVIRONMENT.md`; first commit |
| [ ] | M1 | Kinocut isolated install + interface discovery (Windows) | `kino doctor` OK in `.venvs\kinocut`; `docs/KINOCUT_FINDINGS.md` has no assumptions; licences recorded |
| [ ] | M2 | Equivalence tests: Kinocut vs current code vs direct FFmpeg (frame accuracy, fitting, concat, transitions, audio mix, export, QC, workflow/resume) | `docs/CAPABILITY_MATRIX.md` + `docs/evidence/m2_*.json`; every row measured |
| [ ] | M3 | Engine skeleton: executors (Kinocut+FFmpeg), registry/discovery, manifest, checkpoints, gates, validators | `tools/validate/run/resume/status` work on real media; resume skips done steps |
| [ ] | M4 | Move Recap editing onto the engine where parity was proven; delete superseded code | Regression pack unchanged; 60-90 s real job reviewed frame by frame |
| [ ] | M5 | Remove Shotcut completely | `git grep` check empty; doctor clean; tests + regression pass |
| [ ] | M6 | Agent bridge `recap <step> --json` + focused tool discovery | forbidden flags refused; envelope <= 10 ops |
| [ ] | M7 | Agent-owned scene loop (old G5) | 3 scenes written by agent, >= 2 first-try, 1 revised after viewing frames |
| [ ] | M8 | Visual quality overhaul + 5-scene benchmark (old G6) | owner approves >= 4 of 5 at 16:9 and 9:16 |
| [ ] | M9 | HyperFrames benchmark vs Remotion (evidence, then owner decides) | `docs/BAKEOFF_hyperframes.md` with measured numbers |
| [ ] | M10 | Perception to script (old G7) | video in -> valid `segments.json`, dialogue and silent clips |
| [ ] | M11 | Blueprints + any-video profiles (old G8/G9, no Shotcut) | 3 different videos render; zero AI-generated assets in reports |
| [ ] | M12 | SFX engine (old G11) | auto + scripted SFX, loudness consistent, credits |
| [ ] | M13 | Polish, true 9:16, speed (old G12/G13) | re-render after one-segment edit < 20% of full time |
| [ ] | M14 | MCP + portable skill (old G14) | second agent completes a small job from the skill/MCP only |
| [ ] | M15 | Cutwright Studio UI (old G15) | human makes a video without the command line |
| [ ] | M16 | Other modules / optional borrows (old G16) | each module has a preset + prompt profile |

## Provisional decisions made for you (verify each on this PC; table with fallbacks: `docs/ROADMAP.md`)

A1 Kinocut needs Python >= 3.11 -> separate venv, Python 3.12 via `py -3.12` (install with winget only after telling the owner). A2 pin `kinocut==1.16.4`, subprocess adapter,
no `import kinocut` in `cutwright/`. A3 skip `kinocut[transcribe]` (torch ~1 GB). A4 no HyperFrames until M9. A5 FFmpeg from winget Gyan build on PATH, never Shotcut's bundled one.
A6 do not touch system Node. A7 repo state unknown. A8 `cutwright/` stays stdlib-only. If any assumption fails, record it, take the documented fallback, tell the owner.

## Known unverified (do not assume these work)

- Everything about Kinocut on Windows (installation, CLI contracts, receipts, speed, output quality) - the README claims are in `docs/REFERENCES.md`.
- Whether Kinocut CLI commands have machine-readable output (find out; do not assume a `--json` flag).
- Whether Kinocut can fit a clip to an exact frame count, crossfade two clips, mix/duck audio, or keep audio in `composite-layers` ("video-only" per its docs).
- Recap Studio Phase 3 (Scenes tab, `briefs`, import of agent replies) on Windows. Remotion was not run after the merge.
- Whisper fallback fails on the owner's PC (`open() got an unexpected keyword argument 'metadata_errors'`; try `py -3 -m pip install --upgrade av faster-whisper`).
- Remotion `OffthreadVideo` once failed at frame 71 on a cold run ("No frame found"); a retry exists but never ran.
- Whether DeepSeek V4 Flash through Cline can SEE images (test first in M7).
- Tests under `tests/` (fixtures only) ran on Linux, not Windows.

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
`docs/CODEMAP.md` file map + recap.py line index | `docs/TOOLS.md` tools catalogue (engine commands arrive in M3) |
`docs/GOALS.md` old per-goal specs (detail for M6-M16 only; its ORDER is superseded) | `docs/VISUAL_STANDARD.md` quality bar |
`docs/schemas/manifest.example.json` manifest shape | `tests/media_fixtures.py` frame-id and beep fixtures |
`docs/legacy/` old handoffs (reference only; grep by section)
