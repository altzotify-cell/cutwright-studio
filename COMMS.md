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
