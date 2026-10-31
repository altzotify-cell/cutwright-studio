# HANDOFF - for DeepSeek running inside Cline on the owner's Windows PC

Revised 2026-10-30 (after M5). The older handoff (an editor application as primary backend, goals G0-G16) is
superseded; its goal specs survive only where `docs/ROADMAP.md` points at them. This file = status + rules + order.
Detail lives in: `docs/ROADMAP.md` (milestones, acceptance, test commands), `docs/ARCHITECTURE.md`,
`docs/MIGRATION_CHECKLIST.md`, `docs/REFERENCES.md`. Progress goes in `LOG.md`; questions/blocks in `COMMS.md`. The consultant's 2026-10-31 wrapper (work
items W0-W5: plan-first storyboard gate, motion plates, engine merge, look budget, baseline) is merged as its own
section after the milestone table.

## Current status (you keep this block up to date)

```
Current milestone : M8 "Production blueprint + autonomous run" COMPLETE (2026-10-30, owner-scoped). The
                    agent now says WHAT the video is and the tool writes the plan:
                    `cutwright/engine/blueprint.py` -> `python -m cutwright blueprint generate <brief>`
                    (beats + shot types + asset handles -> blueprint.json, beat frames MEASURED from
                    edge-tts word cues via tools/narrate.py) and `blueprint compile <blueprint>`
                    (-> manifest.json, validated before it is written, byte-identical on re-run). The
                    production `recapstudio/Projects/m8_feature` ran end to end unattended: 3 beats,
                    16.96 s, 407 frames, 8 steps (3 x render_range -> concat -> overlay_audio ->
                    duck_audio -> normalize_audio -> export_h264), exit 0 in 267.9 s; the file is h264
                    1920x1080 24/1, 407/407 frames, aac 48k stereo, decodes clean, 0 flat frames, cuts
                    measured exactly on frames 131 and 246, engine A/V shift -0.013 s. Tests: 37 + 46 +
                    28 + 8 green. TWO MEASUREMENTS STILL FAIL and are recorded, not hidden: slideshow_risk
                    0.867 ("high", bar is <0.85) and Kinocut release_checkpoint 56.1/100 (its own bar is
                    80). Ask: C-017 item 4. KNOWN GAP: `docs/ROADMAP.md` M8 as written (G6: five scenes,
                    16:9 + 9:16, owner approves 4 of 5) is NOT done - it is now "M8b" in the roadmap.
                    Before it: M7 DONE, M6 DONE, M5.5 DONE, M5 DONE.
Last green commit : c6548b4 "M8: the production blueprint, and one production executed end to end by the
                    engine" (26 files, +2736/-38) on main, pushed to origin main; `git ls-remote origin
                    refs/heads/main` -> c6548b4b49ba1113f8a77654201fa1ce67824f4b. The commit that follows
                    it only records that hash in this line. Before it: f5b4328 (M7 close-out),
                    43fa769 (M7), d070fbb, fcae302 (M6), 66c1b97 (M5.5C),
                    20a5052, d55c114, 5dbda9e, facc015 (M5.5A), 2ae8f60, c97d7fd, 4528c51 (M5 close-out),
                    7a8184c, 0755d92, 498aed1, d072280.
Next step         : the owner picks ONE of: (a) M8b = the G6 five-scene benchmark at 16:9 and 9:16
                    (it is M9's fixed input, so it comes first if M9 is next), (b) M9 HyperFrames
                    bake-off (needs those five scenes), (c) close M8's two open measurements first
                    (C-017 item 4: accept, push motion/contrast, or a busier clip), (d) M10 perception
                    -> script. Do not start two of them.
Wrapper handoff   : 2026-10-31 consultant plan W0-W5, rev 2 (cut list and storyboard before any render, motion
                    plates, engine reconciliation, look budget + rubric, draft review, plain-agent baseline).
                    Four owner review stops, always in this order: cut list -> storyboard -> plates -> draft.
                    Build order W0 -> W1 -> W1b -> W2 -> W3 -> W3b -> W5; W4 is a note. Section "## Wrapper
                    handoff W0-W5" sits after the milestone table. Never move a threshold to pass a run
                    (slideshow_risk 0.867, release_checkpoint 56.1 stay). M8b and M9 stay open and the owner
                    chooses when; do not start two items at once. W0's input (the standalone Recap Studio zip,
                    phase 3.5 or later - whatever is current) is still missing: ask the owner for it before
                    starting W0.
Open COMMS        : C-017 (this session: the blueprint, the production, the four render passes, the two
                    failing measurements, and the ROADMAP M8/G6 scope question); C-016 resolved by the
                    owner (3-demo-brief benchmark deferred, M8 = blueprint + run); C-015 resolved;
                    C-014 BLOCKED (2026-10-27); C-012, C-011 answered 2026-10-30; C-013 closed.
Rules             : `.clinerules/` directory (00-core-workflow, 01-architecture-and-constraints,
                    02-testing-and-evidence, 03-session-boundaries). The old single `.clinerules` file no longer exists.

Known on this PC  : git 2.47.1, gh 2.103.0 (logged in as altzotify-cell), Python 3.11.9 default (3.11/3.13/3.14 installed),
                    Node v24.18.0; ffmpeg 7.1 full_build gyan (scoop shim wins over 2 others).
                    Kinocut: INSTALLED in `.venvs\kinocut` = kinocut 1.16.4 on Python 3.11.9, doctor exit 0.
                    `.venvs/` and `out/` are gitignored. All M0 numbers: docs/ENVIRONMENT.md.
Verified on this PC so far : M0 audit (facts in `docs/ENVIRONMENT.md`) + M1/M2/M3 (quotes in `LOG.md`):
  - M8 (2026-10-30): the blueprint and the autonomous run. `blueprint generate` -> narration 16.656 s /
    39 word cues / `"timing": "word timings"`, beats 131 / 115 / 161 frames; `blueprint compile` -> 8
    steps, 407 frames, re-run byte-identical; `validate` -> ok, 0 errors, provenance ok;
    `run` -> exit 0, all 8 steps done in 267.9 s; the file decodes to 407/407 frames (h264 1920x1080
    24/1, aac 48k stereo, 4,575,119 B), 0 flat frames, cuts measured on frames 131 and 246, engine A/V
    shift -0.013 s. `slideshow_risk` 0.867 "high" and Kinocut `release_checkpoint` 56.1/100 still fail
    their bars - see C-017 item 4. Suites: 37 + 46 + 28 + 8 green.
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
| [x] | M7 | Agent-owned scene loop (old G5) | DONE 2026-10-30: M6's render line closed on a fresh `m6probe` (`timeline` exit 0 / 118.1 s / 514 frames, `remotion` exit 0 / 202.0 s, ffprobe nb_frames=514, 21.419 s); `scene brief` + `scene check` (new `engine/scenecraft.py`, 5 tests that read `kit/**`); one agent-authored shot `descent_beat.tsx` through the critic loop (2 planted + 2 found defects, 1 regression caught by measurement, 2 revisions, caption band cleared at 205 px); 107 tests green. GAP: G5's 3-demo-brief count not run |
| [ ] | M8 | Visual quality overhaul + 5-scene benchmark (old G6) | owner approves >= 4 of 5 at 16:9 and 9:16 |
| [ ] | M9 | HyperFrames benchmark vs Remotion (evidence, then owner decides) | `docs/BAKEOFF_hyperframes.md` with measured numbers |
| [ ] | M10 | Perception to script (old G7) | video in -> valid `segments.json`, dialogue and silent clips |
| [ ] | M11 | Blueprints + any-video profiles (old G8/G9) | 3 different videos render; zero AI-generated assets in reports |
| [ ] | M12 | SFX engine (old G11) | auto + scripted SFX, loudness consistent, credits |
| [ ] | M13 | Polish, true 9:16, speed (old G12/G13) | re-render after one-segment edit < 20% of full time |
| [ ] | M14 | MCP + portable skill (old G14) | second agent completes a small job from the skill/MCP only |
| [ ] | M15 | Cutwright Studio UI (old G15) | human makes a video without the command line |
| [ ] | M16 | Other modules / optional borrows (old G16) | each module has a preset + prompt profile |

Order: M0..M5 done, then **M5.5** (the one insertion, before M6), then **M6** (done 2026-10-30), then **M7** (done 2026-10-30), then M8, M9. M10-M16 are a
PARKING LOT (owner decision, 2026-10-30): do not start or expand them.

## Wrapper handoff W0-W5 (consultant, 2026-10-31 rev 2: four review stops, cut list, draft review)

Written 2026-10-31 by the consultant for the owner. Rev 2 of the same day added W1b (the cut list), W3b (the
draft review) and the four owner review stops; rev 2 is what is merged here. It adds work items W0-W5 and does
NOT replace the milestone table above; read it after this file's status block and `.clinerules/`. Names of new
files and verbs below are **proposals**: check `docs/CODEMAP.md` and `python -m cutwright tools list` first and
reuse what exists. This section contains no code on purpose: every item starts with a short plan to the owner,
then waits for the go.

### First ask for the next session (W0's input, from the owner)

W0 cannot start without the standalone Recap Studio source. At the start of the session, ask the owner once:
"drop the current Recap Studio zip into `bench\recapstudio_standalone\` (it is gitignored, so it cannot be
committed)". Take whatever version is current: phase **3.5 or later**. The wrapper text below names
`RecapStudio-phase3.5.zip` because that was the latest on 2026-10-31; by the time W0 runs the standalone may be
finished or further along (phase 4, a release build, a git bundle). In that case use THAT file, and record its real
name and version in `docs/ENGINE_MERGE.md` and in the LOG entry. Never refuse a newer zip for not being 3.5, never
download or reconstruct the standalone yourself, and never guess its API: W0 reads the zip it is given.

### 0. Why this exists (decisions already made by the owner)

1. **The owner wants to see and tweak the plan before the video is built** ("the plan before it goes end to end"). Especially for motion-graphic explainers: the agent presents a storyboard, the owner changes it in plain language, only then does anything render.
2. **Motion plates** (term from a transcript the owner watched): a self-contained animated clip of about 3-8 s, picture-in-picture or alpha overlay, laid over footage at a timecode. Full-screen cards are what makes a film look like slides.
3. **One engine, two wrappers.** CutWright's `recapstudio/` (kit/3: `LayeredMedia`, `Camera`, `KineticText`, `MaskWipe`, string-literal asset handles, bundle cache) and the standalone Recap Studio (owner's free-chatbot product) have diverged. Recap Studio now has composition modes `overlay | inset | replace`, `<Footage>` / `<Still>` handles, `motion.assets` stills, a three-part contract (`CONTRACT.md` rules, `KIT.md` reference, `STYLE_GUIDE.md` advice) and boxless captions. CutWright must not build the same things a second time in a different grammar.
4. **Title / chapter cards are never mandatory.** Movie recaps use none; documentary-style formats may. A blueprint adds a title shot only if the brief asks for it.
5. **Every segment/beat can override** its shot, captions style, transition and theme patch.
6. **Taste needs a human in the loop.** `slideshow_risk` is a guard, not a judge. The owner approves at defined gates.
7. **Four owner review stops, in this order** (the agent never runs past one without approval): (a) the **cut list** (which clip goes with which line), (b) the **storyboard** (what appears and moves, including transitions), (c) the **plates** contact sheet, (d) the **draft review** (a rendered rough cut with all plates in place). The video the owner watched had the same stops: he reviewed storyboards and contact sheets, then a draft with plates inserted at timecodes.
8. **Verified fact:** DeepSeek through Cline can see images (HANDOFF, M5.5A). Whether it *judges* layout well is not verified; W3 and W5 measure it.
9. Evidence from a video the owner watched (Opus 5.5, ~6 h, ~20 takes, plan/contact sheet first, short script, motion plates over a human-recorded A-roll): quality came from a look-and-fix loop and a plan step, not from a bigger prompt. Treat that as a hypothesis to test here, not a result.

### 1. Rules for this handoff (in addition to `.clinerules/`)

- Report only what you ran: TESTED (command + quoted result), FAILED, NOT TESTED (why). No "it should work".
- Start each W item with a **plan of at most 10 lines + list of files to change**, post it, and wait for the owner's go.
- Small edits, stdlib-only agent layer (assumption A8), no new npm packages, Remotion stays 4.0.539, no AI-generated images/video, never print keys. Two failed attempts at the same problem = `COMMS.md` BLOCKED entry and stop.
- **Do not game a threshold.** `slideshow_risk` 0.867 and Kinocut `release_checkpoint` 56.1 are open and recorded (C-017 item 4). Do not change either bar to make a run pass; improve the film or ask the owner.
- Order: **W0 -> W1 -> W1b -> W2 -> W3 -> W3b -> W5**. W4 is a note. M8b and M9 stay open and the owner chooses when (do not start two milestones at once).

### W0. Engine reconciliation (analysis only, no code)

Objective: one engine source of truth, decided on evidence, before more features are built twice.
Depends on: the owner supplying the standalone Recap Studio zip (`RecapStudio-phase3.5.zip`) into an ignored folder, e.g. `bench/recapstudio_standalone/` (not in git).
Read first: `docs/ASSET_HANDLES.md`, `recapstudio/remotion/kit/` (read only the file list and exports), the standalone `remotion/kit/CONTRACT.md`, `KIT.md`, `STYLE_GUIDE.md`, `scenes.py`, `sceneassets.py`.
Deliver `docs/ENGINE_MERGE.md` with:
1. A feature table, one row per capability, columns: CutWright / standalone / winner / why. Rows at least: asset handle grammar (`asset="footage_a"` vs `<Still id>` and `<Footage>`), camera and layered media, kinetic text, mask wipe, composition modes, `motion.assets` stills (frame of the film / of the clip / project image), `camera` export, kit versioning, bundle cache, static checker rules, fallback policy (plain footage vs keywords), prompt/contract layout.
2. A **single handle grammar proposal** (one way a scene names footage or a still) and what each side must change to adopt it.
3. A migration plan for ONE direction: standalone becomes a thin wrapper over the shared engine, or CutWright vendors the standalone engine. State which and why. Include a drift guard (a test that fails if the two kits' exported names diverge).
4. What is NOT shared and stays in each wrapper: CutWright = manifest, ops, gates, agent verbs; Recap Studio = paste workflow, web UI, packs.
Acceptance: the document exists, every claim cites a file path, owner picks the direction. NOT TESTED items are listed, not guessed.

### W1. Storyboard gate: plan before build

Objective: after the agent designs the blueprint and before any render, the owner reads a storyboard, tweaks it in plain language, and approves. Nothing expensive runs until approval.
Depends on: W0 decision on the handle grammar (the storyboard names assets by handle). Existing pieces: `engine/blueprint.py` (`generate`, `compile`, `gates: []` is empty today), `engine/gates.py` and `approve <run-dir> <gate>`, `engine/manifest.py` (`_blocking_gate`), `render_still` (about 5-8 s a still).
Build (proposal, adapt to the code):
0. **Transitions are part of the storyboard.** Between every two beats the storyboard shows the transition (cut, crossfade, wipe, whip, flash: only those the engine has measured, Kinocut crossfade/wipe per the matrix) and its length in frames, so the owner can change it in the same plain-language tweak. Default is a plain cut; a transition the engine cannot produce is refused with the reason.
1. A `storyboard` view of a blueprint (new module `engine/storyboard.py`, stdlib): `storyboard.md` for the owner (readable) and `storyboard.json` for the machine. Per beat: id, time range and frame count from the real word timings, the narration line, **medium** (footage, still with camera, kinetic type, data graphic, plain cut; `motion.medium` in VISUAL_STANDARD section 2), shot type, composition (`overlay | pip/inset | full`), 1-3 sentences "what appears, what moves, what lands on which spoken word", assets with provenance, SFX notes, estimated render seconds and a risk flag (heavy footage + grade, many layers). Plates (W2) show their window (start-end seconds).
2. **Two tiers.** Tier A (free, instant): the table only. Tier B: one cheap still per beat (the beat's strongest frame, 16:9, low res) assembled into a contact sheet PNG, cached by content hash, so a tweak re-renders only the changed beat's still. The agent attaches the sheet itself when it reviews (vision works).
3. **Tweaking = conversation.** The owner says "beat 3: picture-in-picture, number lands on 'seventy'" in Cline; the agent edits the blueprint, regenerates the storyboard, and shows a short **diff** (beats changed, stills re-rendered). Also allow direct edits of `storyboard.json` fields, re-read by a verb (`blueprint storyboard --reread`). Never silently drop an owner change; list rejected edits with the reason (for example a shot that needs footage the beat does not have).
4. **The gate.** `blueprint compile` declares gate `storyboard` before the first render step. A run without approval stops with a plain message naming the gate and the command (`python -m cutwright approve <run-dir> storyboard`). Approval records the storyboard hash; if the blueprint changes afterwards, the approval no longer matches and the run says so (a stale approval must not release a changed plan). Optional switch for fully unattended runs: a recorded `--auto-approve storyboard` that writes who/why into the checkpoint (the owner's explicit choice, never default).
5. Titles: a title beat exists only if the brief or the owner asked for one.
Acceptance (quote the output):
- `blueprint generate` then `blueprint storyboard` writes both files; `run` before approval exits with the gate message; `approve` releases it.
- A tweak to one beat re-renders exactly one still (cache evidence) and the diff names it.
- Changing the blueprint after approval blocks the run until re-approved (test).
- Unit tests for: gate blocking, stale approval, diff, rejected edit. Existing suites stay green; `recap.py video` byte-identical.
Traps: do not render full beats for the storyboard (stills only); do not let `compile` write a runnable manifest when the gate is absent; keep the approval file written atomically like `gates.py` does.

### W1b. Cut-list gate: which clip goes with which line

Objective: before any plate or render, the owner sees and approves the chosen footage. This is where a recap goes wrong most often (a clip that does not match the line, a wrong scene, a spoiler).
Depends on: W1 (same gate mechanism). Existing pieces: `moments`, `verify` (grades picks against frames: verified / retimed / replaced), `frames.py`, `subs`.
Build (proposal):
1. A `cutlist` view (in `engine/storyboard.py` or a sibling): one row per beat with the narration line, the chosen source file and in/out times, the frame count, and **one or two frames** (start and strongest) from the chosen clip as a contact sheet. Cached by (file, time).
2. **Confidence flags.** The agent marks a pick `sure`, `unsure` or `replaced` using `verify`; for every `unsure` or `replaced` pick it shows extra frames (3-4 across the clip) and a one-line reason ("subtitle says the heist, frame shows a dinner"). The owner sees the unsure ones first.
3. Owner actions in plain language: approve all, swap a beat's clip ("beat 5: use the rooftop scene around 01:12:30"), retime, or drop. The agent re-verifies the new pick against frames before accepting it and shows the new frames.
4. Gate `cutlist` before the storyboard gate; approval records a hash of the cut list. A changed cut list invalidates the later approvals (storyboard, plates) and says so.
5. Spoiler/ending flag: if the narration order and the film order disagree, list the beats where it jumps (information only).
Acceptance: a 6-beat list with at least one `unsure` pick shows extra frames; swapping one clip re-verifies it and re-renders only that beat's frames (cache evidence); approving releases the storyboard step; changing a clip after approval blocks later gates until re-approved (test). Quote outputs.
Traps: frames come from the original file at the exact time (frame-accurate seek, as `frames.py` does); never show a frame from a re-encoded proxy without saying so.

### W2. Motion plates

Objective: make the plate a first-class unit: a 3-8 s self-contained clip placed over footage by timecode, as picture-in-picture or an alpha overlay, rendered and cached separately.
Depends on: W0, W1 (plates appear in the storyboard).
Build (proposal):
1. Blueprint field `plate`: `{start_s, end_s, mode: overlay | pip | full, alpha: true|false}`. Enforce 3-8 s (warn above 8 s, reject below 0.5 s: `MIN_BEAT_FRAMES`). `mode` maps to the Recap Studio composition modes: overlay = overlay, pip = inset, full = replace.
2. New shot types (start with two): `pip_plate` (footage in a rounded or slanted window beside a graphic, entrance and exit) and `overlay_plate` (graphic with transparency over the running footage: label, number landing on a word, kinetic words). Reuse `Camera`, `LayeredMedia`, `KineticText`, `MaskWipe`. Avoid solid-colour and generic-gradient backgrounds when a real film frame or graded clip is available (owner's dislike).
3. **Alpha output: verify, do not assume.** Find on this PC which format Remotion 4.0.539 can render with alpha (ProRes 4444, qtrle, VP9 alpha, PNG sequence), what Kinocut `composite-layers` accepts (it is video-only per the matrix: audio needs the separate pass), and what Premiere / VideoPad import. Record the measured table in `docs/ENVIRONMENT.md` or `CAPABILITY_MATRIX.md`.
4. Each plate is its own manifest step with its own cache key (scene file + props + handle digests), so editing one plate re-renders only that plate. Composite step places plates by frame; verify frame counts and that the composite is frame-exact against the plan.
5. Exportability: plates must be placeable in the Premiere XML / VideoPad exports as an overlay track at their timecodes (keep it possible; implement only if cheap, otherwise record the gap).
Acceptance: 3 plates (one `pip`, one `overlay`, one `full`) over a 20 s clip; changing one plate re-renders only that plate (quoted cache lines); composite frame count equals plan; a plate longer than 8 s produces the warning; ffprobe numbers quoted.
Traps: alpha can silently flatten on the way through a codec; check the pixel format on the produced file and a real alpha pixel, not the extension.

### W3. Look-and-fix loop: budget and rubric

Objective: more iterations where they are cheap, and a rubric the model must answer instead of "does this look good".
Build:
1. Replace the fixed "two revisions" with a **budget**: default 6 looks per scene, hard cap 10, stop early when the rubric passes. Every look logs: seconds of render, tokens used (if available from Cline, else NOT MEASURED), rubric result. Owner can raise or lower the budget per run.
2. **Rubric** (answered as JSON, one yes/no plus a one-line reason per item, from `VISUAL_STANDARD.md` section 4 and Recap Studio `STYLE_GUIDE.md`): graphics sit on the picture (not a card on a flat background); at least three layers; strong scale contrast; more than one kind of motion; text inside the safe zone and not in the caption band; footage visible and graded for legibility; key word lands on the spoken word; no generic gradient/stock-template look; one idea. Numeric measures (luma, caption-band distance, flat frames) stay as guards.
3. **Human checkpoints:** the `storyboard` gate (W1) and a `plates` gate before the final composite: the agent presents the contact sheet of all plate stills; the owner approves, or names plates to redo. Only named plates are revised.
4. Regression guard from the M7 log: after each revision re-measure everything, not only what changed (a camera drift sank the sub line back into the caption band once).
Acceptance: one real scene improved across at least 3 looks with the rubric rows and the cost table in `LOG.md`; the `plates` gate blocks and releases; no threshold changed.

### W3b. Draft review stop

Objective: before the final export, the owner sees a rendered rough cut with every plate in place and can send back changes by beat, as in the video ("a first montage with all the shots inserted at timecodes for review").
Depends on: W2, W3.
Build (proposal): a `draft` step that renders a low-cost review file (for example 720p, burned-in beat numbers and timecodes, final sound mix not required) through the normal manifest; gate `draft` before `export_h264`. The owner's notes are plain language per beat ("beat 4 plate too long, drop the transition at beat 6"). The agent maps each note to a blueprint change, shows the diff, and re-renders only the affected plates and the draft. After approval the final export runs.
Acceptance: a draft file with beat numbers is produced; a note on one beat re-renders only that beat (cache evidence); the final export refuses to run before the `draft` gate is approved. Quote outputs.
Traps: the review file must come from the same manifest as the final (no separate pipeline that can drift); burned-in numbers are for review only and must not appear in the final.

### W4. Notes (no work now)

- Open measurements (`slideshow_risk`, `release_checkpoint`): address through W1-W3, not by editing thresholds.
- Kinocut: do not deepen. Keep it only where the matrix says it won; the executor layer is frozen except for bug fixes.
- M10-M16 stay parked. The owner will later specify a character-animation path (an animation tool producing transparent clips by timecode); keep the plate format (alpha clip + timecode + handle) compatible with that, and design nothing for it now.

### W5. Baseline: does the engine earn its place?

Objective: evidence for "plain agent + ffmpeg + Remotion, no CutWright" versus CutWright.
Protocol (write it into `docs/BASELINE_plain_agent.md` BEFORE running): one 20 s brief, the same footage, the same narration file, the same model (DeepSeek in Cline), the same look budget. Run A: plain agent with ffmpeg, whisper and Remotion only, no `cutwright` verbs. Run B: CutWright with W1-W3. Measure: wall time, tokens if available, number of looks, rubric score on the final stills, frame-exactness of cuts and caption timing, number of silent failures (a step that claimed success but was wrong), owner blind verdict (A/B, not told which). Time-box it (one session per run).
Deliverable: the table and a one-paragraph recommendation: what the engine saves, what it costs, what to cut. Then the owner decides about M9 (HyperFrames bake-off: only with the same loop, same rubric, time-boxed).

### 2. Definition of done for this handoff

- `docs/ENGINE_MERGE.md` exists and the owner has picked a direction (W0).
- A production run stops at the `cutlist` gate and then the `storyboard` gate, the owner tweaks one beat in plain language, approves, and the run completes with only the changed beat re-rendered (W1).
- A film with at least three plates (pip / overlay / full) renders, with plate-level caching and a frame-exact composite (W2).
- The loop runs on a budget with a logged rubric and an owner `plates` gate (W3), followed by a `draft` review stop (W3b).
- A production stops at four owner stops in order, `cutlist` -> `storyboard` -> `plates` -> `draft`, and each approval is invalidated by a later change to anything before it (W1, W1b, W3, W3b).
- The baseline table exists (W5).
- LOG entries use TESTED / FAILED / NOT TESTED; HANDOFF status block and milestone table updated; one commit per item; the owner told to start a new session after each.

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
If the next item is W0 (HANDOFF section "Wrapper handoff W0-W5"): before planning anything, ask me to drop the
current standalone Recap Studio zip into bench\recapstudio_standalone\ - phase 3.5 or later, whatever is current.
```

## Where the detail is

`docs/ROADMAP.md` milestones + acceptance + commands | `docs/ARCHITECTURE.md` diagram, responsibilities, rules |
`docs/MIGRATION_CHECKLIST.md` inspect/replace/test/preserve/delete | `docs/REFERENCES.md` Kinocut/OpenMontage/HyperFrames/FireRed, licences |
`docs/CODEMAP.md` file map + recap.py line index | `docs/TOOLS.md` tools catalogue (engine verbs live since M3) |
`docs/GOALS.md` old per-goal specs (detail for M6-M16 only; its ORDER is superseded) | `docs/VISUAL_STANDARD.md` quality bar |
`docs/schemas/manifest.example.json` manifest shape | `tests/media_fixtures.py` frame-id and beep fixtures |
`docs/legacy/` old handoffs (reference only; grep by section)
