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

