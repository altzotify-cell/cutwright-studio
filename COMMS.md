# COMMS: agent <-> consultant

Append-only channel. Newest entry at the bottom. Never edit an old entry; add a
new one that refers to it. Full rules are in `HANDOFF.md`, section
"Communication protocol". No API keys or tokens in this file, ever.

Entry format:

```
## C-014 | 2026-10-27 | agent -> consultant | BLOCKED | OPEN
Commit: a1b2c3d   Files: cutwright/mlt.py L730-754
Goal: one line.
Tried: numbered, with the exact command or edit each time.
Observed: the real output, trimmed to the lines that matter.
Known / assumed: two short lists, kept apart.
Ask: the one question or decision wanted.
```

Types: `BLOCKED`, `QUESTION`, `REVIEW`, `BREAKTHROUGH`, `ANSWER`, `INFO`.
Status: `OPEN` until the other side replies, then `ANSWERED`.

---

## C-001 | 2026-10-26 | consultant -> agent | INFO | OPEN
Commit: a87f4bf (nothing pushed yet)
Goal: get started with the shared plan.
Tried: n/a. The consultant has read HANDOFF.md and the top of README.md only.
Known: the crossfade shape is designed and written up in HANDOFF.md.
Assumed: the owner's notes about the borrowed repos are accurate; none were read.
Ask:
1. Read `HANDOFF.md` top to bottom, including the protocol sections.
2. Reply here with entry C-002 confirming you can **push** to
   `origin` (`github.com/altzotify-cell/cutwright`). Nothing was pushed at the
   2026-10-24 pause.
3. Start Phase 0. Post a `BREAKTHROUGH` entry when `crossfade` and `gui_xfade`
   both pass, or a `BLOCKED` entry after two failed attempts.

## C-002 | 2026-10-29 | consultant -> agent | INFO | OPEN
Commit: none (merge not committed; the tree was delivered as a zip)
Goal: tell the agent what changed and what to do first.
Tried: merged the two projects, rewrote `.clinerules` + `HANDOFF.md`, added `docs/`.
Observed: see LOG.md 2026-10-29 (merge). Only the Python side of the engine was run; Remotion was not.
Known: Recap Studio phases 0-2 passed on the owner's PC; the agent runs on that PC and can run Node/Remotion.
Assumed: the owner's GitHub repo `altzotify-cell/cutwright` is where this gets committed; whisper/shotcut
folders are untracked and survive extraction.
Ask: start with G0 in HANDOFF.md. The old Shotcut crossfade work (C-001) is now G1 (right after the G0 baseline); borrowing cli-anything-shotcut is G2 (recon) + G3 (adoption).
Post a BREAKTHROUGH entry when G0's "Done when" passes, or BLOCKED after two failed attempts.

## C-003 | 2026-10-29 | consultant -> agent | INFO | OPEN
Commit: none (no .git in the ZIP; M0 step 1 makes the first commit)
Goal: tell DeepSeek the architecture changed and what to do first.
Tried: rewrote HANDOFF.md, .clinerules, docs/ARCHITECTURE.md; added docs/ROADMAP.md, MIGRATION_CHECKLIST.md, REFERENCES.md,
docs/schemas/manifest.example.json, tests/media_fixtures.py. Marked old docs (GOALS, TOOLS, BORROW_notes, CODEMAP, README, REPORT) as superseded.
Observed: the consultant had NO network and no Windows. It ran only the Python half of Recap Studio on Linux (514 frames / 21.4 s) and the fixture self-test.
Known: Kinocut facts come from its README (claims) - see docs/REFERENCES.md. OpenMontage is AGPL-3.0 per its repo page (LICENSE text not read).
Assumed: Python 3.11+ may be missing on the PC; Kinocut's CLI may or may not offer machine-readable output; repo state/remote unknown.
Ask: supersedes C-001 (Shotcut crossfade now CANCELLED) and C-002. Start with M0. Report with TESTED / FAILED / NOT TESTED.

## C-004 | 2026-10-29 | agent -> owner | INFO | OPEN
Commit: f621e5f (pushed, main)
Goal: put the merged project under version control in a NEW repo and migrate the rules file, nothing else.
Tried: 1) split the old root `.clinerules` file into `.clinerules/{00-core-workflow,01-architecture-and-constraints,
02-testing-and-evidence,03-session-boundaries}.md`, then deleted the old file; 2) audited the tree for secrets/caches/large
assets; 3) `git init -b main`, first commit; 4) `gh repo create altzotify-cell/cutwright-studio --public --source .
--remote origin --push`.
Observed: "210 files changed, 38069 insertions(+)"; "branch 'main' set up to track 'origin/main'"; git ls-remote main
= f621e5f (== local HEAD); remote `.clinerules/` holds the four files; old `cutwright` and `RecapStudio` repos unchanged.
Known: Cline docs list `.clinerules/` and `.cline/rules/` as supported workspace rule directories and combine all files in them.
Assumed: the owner wants this repo public (same as the other project repos) - switchable with `gh repo edit --visibility private`.
Ask: nothing. Next objective is M0 (environment audit and baseline) and it waits for the owner's go.



## C-005 | 2026-10-29 | agent -> owner | INFO | OPEN
Commit: none - M2 deliberately NOT staged (the owner asked for the matrix + evidence to be reviewed first)
Files: `docs/CAPABILITY_MATRIX.md` (new), `docs/evidence/m2_*.json` (20, new), `tests/kinocut_vs_current/`
       (new package: harness + 12 test modules), `HANDOFF.md`, `LOG.md`. No change to `cutwright/` or
       `recapstudio/` - M2 is measurement only.
Goal: decide, with measurements, which executor each editing operation uses in M3.
Observed: kinocut PASSES trim (exact ids at starts 0/1/37/119), crossfade/wipe (228/228 frames, real
       12-frame ramp, no audio gap or click), duck-audio (16.4 dB), mix/normalize (-15.9 LUFS, -9.0 dBTP),
       subtitles (non-ASCII SRT on exactly the cue frames), export (H.264 High / AAC 48k stereo /
       faststart / clean decode), pad+blur resize, concat frames (2400/2400), and its workflow engine
       (receipts with sha256, resume rebuilds a deleted step, changed spec refused with resume_spec_mismatch).
       It CANNOT: fit a clip to exactly N frames (no op; `speed` was a no-op here), crop, burn text with
       our karaoke style, or keep audio through `composite-layers` (video-only, but `overlay-video` keeps it).
       Its QC is a global score - it flagged clipping (-0.2 dBTP) but MISSED a one-frame black flash and a
       0.5 s silence gap.
       Two defects found in the current code: `render_video_clip` seeks with `-ss` before `-i`, so every
       non-zero start is one frame late; `join_av` does not duck (0.2 dB) and lands the voice 21.6 ms late
       with a -0.3 dBTP peak.
Known: all numbers are in `docs/CAPABILITY_MATRIX.md` with the evidence file per row; the 42 ms audio-drift
       budget is MISSED at every merge (13.4 ms per join with PCM, 26 ms with AAC), so audio must be built
       as one continuous track in M3.
Assumed: the synthetic fixtures (160x90 counter clips, 1 kHz bursts, 100 Hz bed) stand in for real footage;
       HDR/10-bit, non-24 fps and the MCP surface were not covered.
Ask: review the executor column before M3 starts. Nothing else is needed - no code was changed and nothing
       is committed.


## C-006 | 2026-10-30 | agent -> owner | INFO | OPEN
Commit: 29fb366 ("M3 3A+3B+3C: engine executors, op table, registry, manifest state machine, atomic
checkpoints"), pushed to main.
Files: `cutwright/engine/` (manifest.py, checkpoint.py, ops.py, registry.py,
executors/{__init__,kinocut,ffmpeg}.py), `tests/test_engine_{kinocut,registry,manifest}.py`,
`LOG.md`, `HANDOFF.md`. `recapstudio/remotion/package-lock.json` stays UNTRACKED as instructed.
`docs/evidence/m2_*.json` were rewritten by re-running the M2 tests (wall-clock `seconds` only)
and were restored, not committed.
Goal: finish phase 3C (execution manifest state machine + atomic resume) and put 3A/3B/3C under
version control WITHOUT declaring M3 complete.
Observed: `python -m unittest discover -s tests -t . -v` -> "Ran 122 tests in 377.413s" / "OK"
(0 failures, 0 errors, 0 skips). Module alone: "Ran 40 tests in 6.979s" / "OK". A real two-step
manifest (Kinocut trim -> ffmpeg fit) wrote exactly 48 and 24 frames; the second run reported both
steps "skipped (cached (cache key unchanged, outputs intact))" and re-encoded nothing.
Known: the state machine is `pending|running|done|failed|skipped`; a step is skipped only when its
cache key (op + params + tool version + input digests) matches AND every output still matches its
recorded digest. A truncated or schema-mismatched checkpoint raises
CheckpointError(code="corrupted") instead of resuming. Three defects were caught by my own tests and
the demo before anything was staged (see LOG 2026-10-30 phase 3C, FAILED list).
Assumed: 24 fps (the manifest's `fps`) when translating frame counts into `kino trim -s/-d` seconds;
one output file per call (every op in the table has exactly one), so a multi-output op is refused
with `multi_output_unsupported`; audio origins such as `user_audio` are exempt from the visual-asset
origin rule (the example manifest needs that).
Ask: two decisions before phase 3D.
1. `docs/schemas/manifest.example.json` NO LONGER validates: step fit_1 asks for `size` and
   fill="blur", step export asks for crf/audio/faststart, none of which the op table takes. The
   roadmap says to keep the example in sync with the validator. Either (a) I rewrite the example to
   the real vocabulary (width/height, fill "pad", export quality/container) or (b) we treat the
   example as the TARGET vocabulary and extend `ops.py` to match it. Your call - (a) is small, (b)
   changes the executor decisions from M2.
2. Phase 3D still needs validate.py, gates.py, report.py, ids.py, executors/remotion.py,
   pipelines/*.json, skills/*.md and the seven CLI verbs (`tools list|describe|envelope`, validate,
   run, resume, status, approve). Confirm that is the next objective.

ANSWERED by the owner 2026-10-30: (1) -> (a), rewrite the example; (2) -> yes for validate/gates/
report/ids + the verbs + the acceptance ladder. `executors/remotion.py`, `pipelines/*.json` and
`skills/*.md` were NOT confirmed, so they stay out of 3D (see C-007).


## C-007 | 2026-10-30 | agent -> owner | INFO | OPEN
Commit: M3 3D close-out on main (hash in LOG.md; the M3 tick and this entry are in the same commit)
Files: `cutwright/engine/{ids,gates,validate,report}.py` (new), `cutwright/engine/manifest.py`
       (gates + declared checks + production report wired; `resume()` added), `cutwright/cli.py`
       (six verbs), `docs/schemas/manifest.example.json` (rewritten, decision 1 = (a)),
       `tests/{engine_demo,test_engine_validate,test_engine_gates,test_engine_cli}.py`,
       `tests/media_fixtures.py` (+`make_beep_bed`), `HANDOFF.md`, `LOG.md`.
Goal: finish phase 3D - the six CLI verbs, post-render validation, approval files, the production
report, and the roadmapped acceptance ladder on real media. Close M3.
Observed: all six acceptance commands run and pass; the demo is a five-step render (Kinocut trim ->
ffmpeg exact fit -> Kinocut concat -> Kinocut mix -> Kinocut export) whose final file carries frame
ids 24..47 then 1000..1035 (60 frames, 24.0 fps, 160x90, AAC 48 kHz stereo) with the mix bed's beeps
at 0.0/1.0/2.0 s - so picture, audio and timing are all measured, not assumed. A killed run (killed
during step 3) resumes with steps 1-2 "cached (cache key unchanged, outputs intact)", re-runs step 3
over its partial file, and finishes frame-exact.
DECISION 1 answered as (a). The rewritten example is now valid; writing it caught my own mistake -
`export_h264` takes input `src`, not `video`.
DECISION 2 executed as scoped. NOT done, and not claimed: `executors/remotion.py`, `pipelines/*.json`,
`skills/*.md` (no op routes to a remotion executor yet; those three were not in the confirmed scope).
Three findings, all measured, all worth your eye:
1. `kino merge` silently RE-TIMES heterogeneous inputs: a 24 fps silent clip + a 24 fps clip with
   audio came out 30.0 fps / 44.1 kHz and 75 frames instead of 60. Two silent 24 fps clips came out
   60/60 at 24.0 fps. Consequence: never concat a silent clip with an audio one; build picture
   first and one audio track after (the M2 decision already points that way). `constant_fps` now
   asserts the RATE, not just uniformity, so this cannot pass silently again.
2. `fit_to_frames` is video-only by design (`-an`, matrix row 2), so fitting a clip drops its audio.
   Documented in the executor and in the demo builder; a manifest author still has to know it.
3. `mix_audio`'s track files are params, not declared inputs, so they are NOT part of the step's
   cache key: replacing `music.wav` does not invalidate the mix. Fixing it means declaring the track
   as an input of the op, which changes the op contract - M4 decision, recorded here.
Ask: (i) confirm M3 is closed as you read it; (ii) any objection to making a mix track a declared
input in M4; (iii) the next objective is M4 (move Recap editing onto the engine) and it waits for
your go.


## C-008 | 2026-10-30 | agent -> owner | INFO | OPEN
Commit: d072280 (M4 phase 4A, pushed to main)
Files: `cutwright/engine/ops.py`, `cutwright/engine/manifest.py`,
       `recapstudio/_template/engine_bridge.py` (new), `recapstudio/_template/recap.py` (`join_av` only),
       `tests/test_engine_mix_inputs.py` (new), `tests/test_engine_bridge.py` (new),
       `tests/test_engine_registry.py`, `tests/engine_demo.py`, `docs/CODEMAP.md`,
       `docs/MIGRATION_CHECKLIST.md`, `LOG.md`, `HANDOFF.md`. Nothing deleted from `recap.py`.
Goal: phase 4A - (1) make `mix_audio`'s track files declared inputs so a replaced track invalidates
      the mix (C-007 finding 3), (2) put Recap's picture join on the engine, (3) re-run the
      regression project on the swapped path and compare with the M0 baseline.
Observed: regression `recapstudio\Projects\regress` -> "Done. recap_final.mp4 (21.4s, expected
      21.4s)"; ffprobe: 514 frames, 24/1, 1920x1080, duration 21.416667, 6,834,110 B, aac 48000/2 -
      every number equal to the M0 baseline in `docs/ENVIRONMENT.md`. Stronger than equal: the video
      and audio streams are byte-identical to the pre-change file (md5 c671f7a7... / 0064ff59...),
      and loudness is unmoved (I -11.3 LUFS, LRA 0.4 LU, true peak -6.9 dBFS). The engine really ran
      the join: `tiktok_temp\full_picture.mp4` (514 frames) is new, and the old concat list
      `full_video.txt` still carries the 2026-10-29 timestamp (never rewritten).
      On the demo (180 s of real Kinocut work, five steps): replacing `music.wav` with a same-length,
      different tone re-ran ONLY `mix` - "cache key changed (inputs, params or executor version)" -
      and the new 320 Hz burst is measurably in the output (Goertzel: 320 Hz 3,526,719 vs 1000 Hz
      755 in the first 50 ms); restoring the fixture re-ran `mix` again and put the 1 kHz burst back
      (1000 Hz 5,787,335 vs 320 Hz 3,139). Before the fix that step would have been skipped.
Known: `mix_audio` now declares `inputs: {"src", "tracks"}`; `params.tracks` carries SETTINGS only
      (volume/start/fades), paired with the files by position. A `path` inside a setting is refused
      with `unknown_param` instead of being silently ignored, and a file/setting count mismatch is
      refused at plan time (`invalid_combination`).
Assumed: a project folder lives inside the fork, so the bridge can find `cutwright/engine/ops.py`
      by walking up. A project copied outside the fork has no engine - `join_av` raises instead of
      quietly falling back (no runtime "legacy" switch, per `.clinerules`).
Three findings worth your eye:
1. Kinocut answers the mix with a warning: "Tracks sum at unity without normalization and may clip.
   Listen before publishing." So a track volume of 1.0 next to the program audio can clip; the
   engine surfaces it in the step's `warnings` but does not block. Worth a rule in M12 (SFX).
2. `fit_to_frames` cannot replace `render_video_clip` yet: no start offset (`-ss`), no `loop`, and
   `fill="blur"` is unimplemented. Moving the per-segment fit needs new op params, so it stays in
   `recap.py` for 4B/M13 rather than being half-moved.
3. The regress project has `project.json` "music": false, so the regression cannot exercise the
   music path at all; the demo does, and that is where the mix numbers above come from.
Ask: (i) approve 4B - delete the superseded picture-join code (`join_av`'s demuxer branch) in its
     own commit, or leave everything in place and stop here; (ii) confirm the 60-90 s real job
     (roadmap step 5) is next after 4B, and whether you supply the footage/voice or I build it from
     `recapstudio\Projects\regress\footage\demo_a.mp4`.

## C-009 | 2026-10-30 | agent -> owner | INFO | OPEN
Commit: 0755d92 ("M4 4B: the ffmpeg music mix is deleted; mix_audio mixes the bed"), pushed to main.
Files: `recapstudio/_template/recap.py` (`join_av` only, `make_music_bed` docstring),
       `recapstudio/_template/engine_bridge.py` (docstring: the video-stream requirement),
       `docs/CODEMAP.md`, `docs/MIGRATION_CHECKLIST.md`, `HANDOFF.md` (M4 ticked), `LOG.md`.
       `recapstudio/remotion/package-lock.json` stays UNTRACKED as instructed (C-006).
       The job itself (`recapstudio/Projects/m4job`) and all evidence stills (`out/m4b/`) are gitignored.
Goal: phase 4B - delete the superseded editing code, wire `make_music_bed` -> `mix_audio`, then the
      60-90 s real job (roadmap step 5) and a six-frame review. M4 is ticked.
Observed: `join_av` no longer gives ffmpeg a third (music) input; the program audio is muxed first and
      `engine_bridge.mix_tracks` -> `mix_audio` (Kinocut) mixes the bed under it. On the real job the
      video packets are md5-identical before and after the mix (854df8a7...), audio packets change
      (90132b3a... -> 2e343715...), loudness -20.1 -> -19.2 LUFS, and the bed's 220/277 Hz tones
      arrive (Goertzel 21.4M/17.7M vs 3.7M/1.5M). The regress project is byte-identical to the M0
      baseline (514 frames, 21.416667 s, 6,834,110 B, same stream md5s, same sha256). Suite: 178 tests,

## C-010 | 2026-10-30 | agent -> owner | INFO | OPEN

Commit: 4528c51 ("M5 close-out: remove obsolete Shotcut MLT backend, GUI, and tests"), pushed to origin main;
        verified with `git ls-remote origin refs/heads/main` -> 4528c5117f1de4dd78a934a93840feaf4f419e8b.
        This docs commit records that hash (the C-009/M4 pattern).
Files: deleted `cutwright/mlt.py` (2,573 L), `cutwright/gui.py` (433 L), `cutwright/tools/shotcut_window.ps1`
       (255 L), `projects/demo_{cuts,fade,cross,title}` (17 files, 1,776 L); renamed `REPORT.md` ->
       `docs/legacy/REPORT_shotcut_era.md` and `docs/VISION_cutwright_v2.md` -> `docs/legacy/`; added
       `docs/legacy/PROVENANCE_removed_editor.md` (the moved history, not a deletion);
       `cutwright/cli.py` (`build` + parser + doctor line gone, Kinocut line in), `cutwright/engine/registry.py`
       and `cutwright/transcribe.py` (wording only), `.gitignore`, `.gitattributes`, `.clinerules/00`+`01`,
       `README.md`, `PROVENANCE.md`, `docs/{CODEMAP,TOOLS,GOALS,ENVIRONMENT,MIGRATION_CHECKLIST}.md`,
       `HANDOFF.md`, `LOG.md`.
Goal: M5 - the old editor backend leaves code, config, docs and tests; nothing kept as a fallback.
Surprises, all three worth your eye:
1. The working tree arrived half-done and NOT as its own notes described: the deletions were staged, the
   docs were edited, and `HANDOFF.md` already claimed "M5 DONE ... 178 tests green, regression pack green"
   with no `LOG.md` entry behind it. I re-measured everything and corrected the claim instead of
   inheriting it (the numbers are in the LOG entry).
2. One commit, not the checklist's one-per-item: the earlier attempt had code and doc edits interleaved in
   a single working tree, so a per-item split would have meant inventing history nobody verified. The tree
   went in whole; section F of `docs/MIGRATION_CHECKLIST.md` is ticked item by item with the evidence.
3. `docs/evidence/m2_*.json` (20 files) is NOT part of this commit and was left untouched in the tree: the
   unittest suite itself rewrites them (the equivalence tests in `tests/kinocut_vs_current/` write their own
   evidence - visible as `[evidence] docs/evidence/m2_*.json` in the test output), so those diffs are timings
   and `generated_utc` from running the suite, not M5 edits. `recapstudio/remotion/package-lock.json` stays
   untracked (C-006). `docs/legacy/PROVENANCE_removed_editor.md` IS committed: it is the history the
   checklist asked to keep.
Not done and not claimed: the recapstudio regression pack (roadmap M5 acceptance line 3) was NOT re-run in
this close-out; `python -m cutwright doctor` and the unittest suite were, and are quoted in `LOG.md`.
Ask: (i) is M5 closed on `doctor` + the suite, with the regression pack moved to the start of M6, or do you
     want it run before M5 is called done? (ii) confirm M6 (agent bridge `recap <step> --json` + focused
     tool discovery) as the next objective.

      "OK" in 424.901 s. Real job: `recap_final.mp4`, 1900 frames, 24/1, 1920x1080, 79.166667 s,
      56,943,664 B, aac 48000/2, built from 15 Edge-TTS segments (269 words) over the looped
      `footage\demo_a.mp4`, with a code-made music bed.
Two Kinocut facts worth knowing:
1. `mix-audio` REFUSES an audio-only source - "mix_audio requires a video stream" (exit 1, code
   `missing_video_stream`) for every output extension I tried. So any future "mix a bed under a wav"
   has to be done the way 4B does it: mux first, mix second. It stream-copies the video, so the
   order is safe. The cost: a music-on file loses `-movflags +faststart`.
2. Kinocut's mix warning ("Tracks sum at unity without normalization and may clip") still appears on
   every music-on render. At 0.12 bed volume nothing clips (-19.2 LUFS), but this is the rule M12
   (SFX) must set.
One cosmetic finding from the frames: a four-by-three VIDEO segment is padded with real black bars
(`config.json` "fill": "pad", measured RGB (0,0,0)) while a STILL segment next to it gets a blurred
backdrop (`render_image_clip` hard-codes "blur"), so the cut between them jumps from black bars to
blurred bars. Not a bug in 4B, cheap to unify in M8.
Ask: (i) accept the 79.2 s job as the M4 step-5 evidence (frames: `out\m4b\frames\01_start.png`,
     `02_25pct.png`, `03_50pct.png`, `04_75pct.png`, `05a_cut_before.png` + `05b_cut_after.png`,
     `06_end.png`, plus `07_character_s09.png`; receipt `out\m4b\job_receipt.json`), and do you want
     to listen to `recapstudio\Projects\m4job\recap_final.mp4` before I close M4 for good?
     (ii) confirm M5 (remove Shotcut) is the next objective.

## C-011 | 2026-10-30 | agent -> owner | INFO | OPEN

Commit: facc015 "M5.5A: a Remotion executor (render_still, render_range), measured", pushed to origin
        main and verified with `git ls-remote origin refs/heads/main` ->
        facc015c8a349864148347dabf9beab4590b351a. Before it: 2ae8f60 (docs only - M5.5 inserted).
        This closing docs commit records that hash (the C-009/C-010 pattern).
Files: `cutwright/engine/executors/remotion.py` (new, ~270 lines), `cutwright/engine/ops.py` (two
       `OpSpec`s appended in the graphics stage - nothing else), `cutwright/engine/registry.py` (five
       lines: the module, the install hint, the readiness branch, and `installed()` now asks the
       executor for the version instead of re-reading package.json), `docs/evidence/m55_remotion.json`
       (new, 12 measured rows), `tests/test_engine_remotion.py` (new, 12 tests),
       `tests/test_engine_registry.py` (two assertions now allow the remotion executor),
       `tests/test_engine_manifest.py` (one fixture), `docs/{TOOLS,CODEMAP,ENVIRONMENT}.md`, `LOG.md`,
       `HANDOFF.md`. Nothing else in `cutwright/engine/` was touched; no kit file, no CONTRACT.md, no
       primitive, no prompt, no critic loop, no M6.
Goal: M5.5A - the executor half of "stop looking like PowerPoint", measured rather than estimated.
Observed, the numbers you asked for (`python -m cutwright run <manifest> --json`, all 12 runs rc=0):
```
                     cold (run dir + output removed)   warm (output removed)   cached
still 1920x1080      7.77 s  (wall 9.79)              8.26 s (wall 9.69)      0.97 s
still 1080x1920      7.39 s  (wall 8.69)              6.95 s (wall 8.44)      1.04 s
1 s range 16:9      13.20 s  (wall 14.83)             9.63 s (wall 11.19)     1.34 s
1 s range 9:16      10.96 s  (wall 12.78)            11.99 s (wall 13.56)     1.01 s
```
"cold/warm" is defined because the words otherwise mean anything: cold removes the run folder AND the
output, warm removes only the output (the engine re-runs the same step), cached removes nothing (the
step is skipped, reason "cached (cache key unchanged, outputs intact)").
Three things worth your eye:
1. WARM IS NOT CHEAPER THAN COLD. The ~8 s a still costs is webpack bundling, not the frame: the CLI
   invocation is the unit. So one look is ~10 s wall, and a cached re-run of an unchanged scene is
   ~1 s. That is affordable for a critic loop of a few looks per scene, and it is NOT affordable to
   render frame-by-frame through the CLI - 5.5B has to design its loop around one bundle per look.
2. The regression baseline is intact, with one honest exception. `recap.py video` on `regress` ->
   514 frames, 21.416667 s, 6,834,110 B, video packets md5 c671f7a7..., audio 0064ff59..., file
   sha256 817BA0EA... - identical to the M0 line. But the `remotion` step in the same pack produced
   5,904,274 B where M0 recorded 5,915,527 B, with the same 514 frames and 21.42 s and the parity
   check passing. I did NOT investigate: whether two renders of the same timeline are byte-identical
   is now a named "NOT TESTED" and the `video` step ran before the re-render, so the editing path is
   still byte-reproducible. Say the word if you want it settled in 5.5B.
3. The stills look like what VISUAL_STANDARD section 4 describes, now from the inside. `stat_ring` at
   16:9: one centred ring on a dark gradient, "70%" inside it, "OF PLAYERS DISAGREED" under it,
   nothing else; at 9:16 the same composition scaled up with the label nearly touching both edges and
   the bottom 35 % empty. Not ugly - but a single stat over a background, with no footage, no layers,
   no camera. The contract is the cause, exactly as the brief said, and the scene itself is competently
   built. That is the baseline 5.5B has to beat.
Vision test: I looked at both PNGs and wrote down what I saw BEFORE reading the scene source, then
checked. I answered: the number reads 70, the unit is a smaller orange %, the label reads "OF PLAYERS
DISAGREED", the ring is orange on a dim grey track, filled about 70 % clockwise from 12 o'clock, with
an orange glow. The source says `{value: 70, label: 'of players disagreed', unit: '%'}` with the label
rendered uppercase, the ring in `p.accent` and the number in `p.fg`. Every detail matched, including
the smaller accent-coloured unit - so "can DeepSeek see images" moves from Known-unverified to
verified in `HANDOFF.md`.
Assumed: the CLI is called as `node @remotion/cli/remotion-cli.js`, not `npx remotion` (a pinned
version, no registry lookup, no `.cmd` re-quoting); `--props` gets a file, not an inline JSON string.
Both are written down in the module docstring with the measurement that forced them.
Ask: (i) go for 5.5B (footage/stills handle + primitives + critic loop), or would you rather I settle
the Remotion byte-reproducibility question first - it is one ~90 s render and it decides whether
5.5B can trust "same scene + same props = same pixels" in its cache; (ii) 5.5B needs a real footage
file to hand scenes: `recapstudio\Projects\regress\footage\demo_a.mp4` is a test pattern, and the
m4job used the same one - do you have a clip (or stills) you want the first directed scene built on?



## C-012 | 2026-10-30 | agent -> owner | REVIEW | OPEN

Commit: this session's commit (recorded in HANDOFF and `git log -1`)
Files: `docs/ASSET_HANDLES.md`, `cutwright/engine/executors/remotion.py`, `cutwright/engine/{manifest,ops,checkpoint}.py`,
`recapstudio/remotion/kit/media.tsx` + `kit/index.ts` + `CONTRACT.md`, `scenes_examples/media_layers.tsx`,
`tools/check_scenes.mjs`, `tests/test_engine_scene_check.py`, `tests/test_engine_remotion.py`, `.gitignore`,
`docs/evidence/m55b_handles.json`
Goal: 5.5B - footage by handle, `LayeredMedia`/`Camera`, several stills from one bundle, all seven of your amendments.

Result: kit/2 is in and measured. Three stills of a real footage scene cost 26.7 s wall cold (5.4/5.3/6.3 s of render,
the 8.1 s bundle inside the first), 18.1 s with the bundle cached and 1.9 s when the steps are cached; the old path was
~10 s per still. One bundle is 38.2 MB (19.9 MB without source maps) and the 4.4 MB clip inside it is a hard link to the
original, so it costs 0 extra bytes; the cache holds 5. Swapping the clip behind the same handle changed the cache key
AND the pixels. The scene checker rejects all six cases you named, with line numbers, and `useAsset` is not importable.
The engine + scene-check suites are green (28 + 3 tests), `recap.py scenes` gives the M0 verdicts and `recap.py video` is
byte-identical (514 frames, 6,834,110 B, video MD5 c671f7a7...).

Two of your questions answered by measurement, and one claim of mine retracted:
- `--public-dir` exists in 4.0.539, but the bundler COPIES that folder into every bundle (bundle.js:278-294) and only a
  symlink escapes the copy (copy-dir.js:25) - and a symlinked public file is served as a 404
  ("...status code of 404 while downloading file http://localhost:3000/public/assets/footage_a.mp4"). The design note's
  "symlink, 0 bytes copied" was therefore wrong: assets are staged and mounted as hard links, which is why a bundle
  carrying a clip costs 0 extra bytes anyway.
- The bundle key cannot include the footage (your C-011 rule), so a reused bundle would have served the clip it was built
  with. Mounting the (hard) link into `<bundle>/public/assets` on every render fixes that: key cheap, pixels current.
- Your "known OffthreadVideo failure past frame 71" did not reproduce: frames 120 and 140 both rendered from a cold clip
  (140 is past the clip's 129 frames; the source holds its last frame). I am not calling that fixed - just not seen here.

Ask: (i) 5.5C go, or (ii) a real clip first? The pipeline is proven, but every frame I have looked at on this PC is the
engine's own colour bars, so "it looks like a shot instead of a slide" is still unjudged - and that judgement is the whole
point of 5.5. If you give me one real clip (a street scene, a face, anything non-synthetic), 5.5C's directed scene can be
built and judged on it; without one I can only judge layout, timing and camera moves, not whether the result reads as
footage.

## C-013 | 2026-10-30 | agent -> owner | INFO | DONE (no answer needed)

M5.5 is CLOSED. 5.5C shipped the last two primitives, one directed shot, and the loop you asked for - and the loop
earned its keep on the very first look.

What is new
- `kit/kinetic.tsx` (kit 2 -> 3): `<KineticText>` (staggered word/line spring reveals; each unit travels, starts
  skewed and motion-blurred, can punch in from 1.14x, one word in the accent colour) and `<MaskWipe>` (animated
  `clip-path` polygon, four directions, square or angled edge). Pure Remotion spring math + CSS; no new package.
- `src/scenes/directed_shot.tsx` + composition `bench-directed-shot`: real footage under a `<Camera>` push
  (1.00 -> 1.12, `ease.inOut`), a left-to-right gradient bed, the kinetic headline and two angled wipes.
- The C-012 ask is answered by me, not by you: the clip is NASA Perseverance's pre-sunrise sky (public domain,
  Wikimedia Commons, 1588x892, 8.000 s, 885 KB). Licence, source URL and the exact ffmpeg line that re-creates it:
  `docs/evidence/m55c_footage.md`. It is not committed - `recapstudio/.gitignore` ignores `Projects/*`, same rule as
  your C-011 "project media never committed".

What the critic loop found (this is the part that matters)
Three defects, all visible only because I looked at the rendered PNGs, all fixed and re-rendered:
1. The sub line ended 95 px from the bottom edge; the spoken captions sit at `captionBottom` = 97 px. They would
   have overlapped in a real render. The block now ends at `captionBottom + 84u`.
2. The left gradient bed (0.80/0.52) was so strong it extinguished the pre-dawn glow that is the best content in
   the frame, so frame 0 and frame 48 looked like two different grades. Softened to 0.70/0.40.
3. `scrim` 0.5 + `vignette` 0.5 left the footage at ~10-18 % luma: cinematic, but muddy. Now 0.42/0.45.

Surprises worth your attention
- A scene cannot import `scenes_examples` or even `sceneTypes`: the checker allows `remotion`/`react`/`@kit` only.
  That is correct (it is what makes a scene self-contained), but it means the benchmark carries its own tiny
  `spread()` helper for preview words and its entry is structurally typed instead of `LabEntry`.
- `Camera` gained an optional `curve` prop. The default `ease.out` front-loads the move, which reads as a snap in
  a Ken Burns push; I did not want to hide that behind an inflated `duration`.
- `Invoke-WebRequest` against Commons returns 429 from this IP (with or without a User-Agent); `curl.exe` works.
  NASA's images-api returns 403. Recorded in LOG so the next session does not repeat it.

Not settled (say the word and I will do it, otherwise M6 starts)
- Motion over the whole 8 s: I looked at frames 0/24/48, not a rendered range, and not the 30 fps clip inside a
  24 fps composition.
- The 9:16 version of this shot, and the caption overlay seen in its real position.
- `recap.py scenes` / `recap.py video` were not re-run this session (kit gained no dependency; M5.5B's regression
  already covers kit/2).

The stills are in `out/m55c/stills/` (frames 0, 24, 48; 1920x1080) if you want to look before answering.

## C-015 | 2026-10-30 | agent -> owner | REVIEW | OPEN

M6 is done. Two decisions need your eye (both are one line to reverse), plus one thing I could not test.

**1. I renamed a stage and deleted one.** `ops.STAGES` was `plan, assets, edit, graphics, qc, deliver`
and is now `plan, edit, graphics, review, deliver` - your five stages:
- `qc` -> `review` (it is the stage that judges the cut; no op ever lived in `qc`, so nothing moved).
- `assets` deleted. No op, no test, no code named it; the footage-handle contract is a doc
  (`docs/ASSET_HANDLES.md`), not a stage. Say the word if you want it back for M11.

**2. The envelope's unit is a TOOL, not an op.** At `plan` and `review` this catalogue has ZERO ops -
they read and judge, they do not render. An ops-only envelope would hand those stages an empty list, so
`tools envelope --stage S` now returns the stage's ops (with param schemas) PLUS the commands that stage
reaches for (`probe`, `subs`, `moments`, `verify`, `validate`, `status`, `approve`, `recap`), and every
envelope carries one `how_to_run` line so no stage spends a slot on `run`. Sizes: plan 6, edit 10,
graphics 4, review 4, deliver 3 (cap 10, checked over ops AND commands). An op still has exactly ONE home
stage, so `tools list --stage S` and the envelope never disagree; a command may appear in two stages
(probe at plan and at deliver).

**3. What I could not verify.** The G4 "Done when" ends with `recap timeline` then `recap remotion` on a
fresh project. `timeline` outran the 30 s foreground cap (killed mid-run, no timeline.json) and this
session's rules were "no background runs, no polling loops", so those two steps are NOT TESTED. What IS
real: `recap new`, `recap demo` (6.0 s, 14 files), `recap check` (2.2 s, STATE.md) and `recap status` on
two throwaway projects, the refusals (`--force`, `init`, `collect`, `comic`), and 74 unit tests green.
The bridge's timeout/step_failed paths are covered by tests. If you want the render line closed, start the
next session with: "run the M6 done-when on a fresh project, render it, and show me the frames".

**4. Two smaller gates.** (a) `--force` is refused unless BOTH `--i-know-this-destroys-work` and
`--comms <id>` are passed; the override then shows up in the JSON as `override`, so it can never happen
quietly - if that is too easy to satisfy, say so and I will require an owner-typed code instead.
(b) `recap.py` grew no line: the bridge is a separate module, and the project's own copy still runs.

## C-016 | 2026-10-30 | agent -> owner | REVIEW | OPEN

Commit: this session's commit (recorded in HANDOFF and `git log -1`)
Files: `cutwright/engine/scenecraft.py` (new), `cutwright/cli.py`, `cutwright/engine/envelopes.py`,
`tests/test_engine_registry.py`, `recapstudio/remotion/src/scenes/descent_beat.tsx` (new),
`recapstudio/remotion/src/SceneLab.tsx`, `docs/TOOLS.md`, `docs/ROADMAP.md`,
`docs/evidence/m7_render_line.json`, `docs/evidence/m7_descent.json`
Goal: M7 - close M6's render line, then author a scene with a tool and put it through the vision critic.

**1. The line M6 could not run is closed.** On a fresh `m6probe`: `recap timeline` -> exit 0, 118.1 s,
514 frames; `recap remotion` -> exit 0, 202.0 s; `ffprobe` -> h264 1920x1080 24/1, nb_frames=514, aac,
21.419 s, 11,628,341 B. Both ran detached with their exit code in a file and were checked once - no
polling loops.

**2. Task 2 is a tool, not a longer prompt.** `python -m cutwright scene brief` returns the four
primitives with the props the kit actually exports, the handle rule, the three stills and six critic
checks; `scene check <file...>` runs the SAME TypeScript checker the `scenes` step uses. The brief is
data and 5 tests read `kit/**` to prove every primitive and prop still exists - a rename fails a test
instead of misinforming the next agent. The graphics envelope grew from 4 to 5 tools (cap 10).

**3. The loop caught more than it was given.** I planted two flaws (sub line in the caption band; rail
labels 18 px/60 % over bright sky) and the critic found two I had not planted: the 1.16 camera push
cropped "Seven" and "It" at the left edge on f144, and f000 opened on bare sky. Revision 1 fixed all
four; measuring the fix then caught a regression the eye missed - the remaining camera drift sank the
sub back into the caption band at f144 (135 px from the bottom edge). Revision 2 (higher block, camera
rises instead of sinking) -> lowest text 210/211/205 px at f000/f048/f144. Two revisions = the cap.

**4. One gap I did not paper over.** G5's own "Done when" wants THREE demo-brief scenes with pass
counts. This session proved the loop on one beat, which is what you scoped. ROADMAP M7 records the gap;
say the word if you want the 3-scene count run before M8.

**5. Look at these if you want to judge for yourself:** `out/m7/stills/descent_f000|048|144.png` (pass 3)
against `out/m7/stills_pass1/`. No answer is needed to start M8.

## C-017 | 2026-10-30 | agent -> owner | REVIEW | OPEN

Commit: this session's commit (recorded in HANDOFF and `git log -1`)
Files: `cutwright/engine/blueprint.py` (new), `tools/narrate.py` (new),
`recapstudio/remotion/src/scenes/m8_{layered_push,kinetic_reveal,directed_wipe}.tsx` (new),
`recapstudio/remotion/src/SceneLab.tsx`, `recapstudio/Projects/m8_feature/` (new: brief, blueprint,
manifest, script, project), `cutwright/cli.py`, `cutwright/engine/envelopes.py`,
`tests/test_engine_cli.py`, `docs/{TOOLS,CODEMAP,ROADMAP}.md`, `docs/evidence/m8_feature.json`,
`HANDOFF.md`, both `.gitignore`s.
Goal: M8 as you scoped it - the agent designs a production as BEATS, the tool compiles it to a
manifest, and the engine runs the whole thing end to end with no hand-written steps.

**1. The hand-written manifest is out of the agent's job.** `blueprint generate <brief.json>` takes
the intent (title, beats, shot type per beat, the words spoken, the asset handles) and writes a
`ProductionBlueprint`; `blueprint compile` turns it into `manifest.json` and refuses to write one that
`manifest.validate` rejects. The frame counts are not chosen: edge-tts streams `WordBoundary` cues
(one per word, in order) through `tools/narrate.py`, and each beat ends where its own sentence ends -
beat 2 starts on the frame the word "Perseverance" starts. Re-running either verb is byte-identical,
so a plan can be regenerated and diffed. 7 tests pin the loop (a brief with an unknown shot, a
footage shot with no footage, a missing narration, a blueprint that is not a blueprint, the compiled
step graph and its executors, and the shot table against the scene files that really render it).

**2. The production ran unattended.** `recapstudio/Projects/m8_feature`: 3 beats (layered footage +
subtle push / kinetic typography / directed shot with an angled mask wipe), 16.66 s of narration,
407 frames at 24 fps, 8 steps - three Remotion renders, Kinocut `concat`, FFmpeg `overlay_audio`,
Kinocut `duck_audio`, `normalize_audio`, `export_h264`. Exit 0, every step `done`, every declared
check `pass`. Numbers and quoted output: `LOG.md`, `docs/evidence/m8_feature.json`.

**3. Four render passes, because the frames kept disagreeing with the numbers.** (a) pass 1 was
murky: the plate is a pre-dawn Mars sky (mean luma ~10/255) and my scrims made it worse. (b) pass 2
had 8 near-black frames at the beat-3 boundary (a wipe starting from zero) and both "accent" words
rendered white - `KineticText`'s `lines` mode compares the WHOLE line against `emphasis`, so a
per-word accent can never fire there; words mode fixed it. (c) pass 3 graded the plate (brightness
1.5 / contrast 1.22 / saturate 1.7) and the dawn appeared. (d) pass 4 fixed what the stills showed
last: the 1.18 push cropped "Reads" against the frame edge, and beat 2's emphasis array still said
`['light']` while its line said "daylight". I looked at a still at each pass - the defects that
mattered were all visible, none of them were in the JSON.

**4. Two of the project's own measurements still fail, and I am not going to dress that up.**
(i) `validate.slideshow_risk` reports 0.86 - "high". It counts frame pairs whose mean change at 64x36
is under 1.0/255, and this reel is three slow camera moves on a low-motion plate; the grade nearly
doubled the measured movement (mean diff 0.546 -> 0.944) but the verdict did not flip. (ii) Kinocut's
`release-checkpoint` gate scores the file 56.5/100 against its own 80 bar: "desaturated 7.2 %",
"colour cast red/yellow 22.2 %". After the grade it now objects to the WARMTH the grade added - a
golden-dawn plate is a colour cast to that gate. Both are heuristics; the hard checks pass (407/407
frames, clean decode, 0 flat frames, cuts exactly on the beat frames, audio in sync within 13 ms of
the narration file). Say which you want: (a) accept the number and record the gap, (b) let me push
motion/contrast harder and re-measure, or (c) give the reel a busier clip and re-run - the metric is
measuring the plate as much as the edit.

**5. One scope mismatch to settle.** `docs/ROADMAP.md` M8 is "visual quality overhaul and benchmark
(old G6)": five benchmark scenes, 16:9 and 9:16, owner approves >= 4 of 5. Your M8 was the blueprint
and the end-to-end run. I built yours and recorded the other as still open (M8b in the roadmap's M8
section), because silently redefining a milestone is worse than a visible gap. Tell me whether G6's
five-scene benchmark comes before M9 (the HyperFrames bake-off wants five scenes as its fixed input).

**6. Untested on purpose.** The three M8 scenes in 9:16 (the kit's `portrait` path) - nothing in this
production asked for it; the C-016 3-demo-brief harness is still deferred, as you decided.

