# 01 - Architecture and hard constraints

Project = one repo, two halves: `cutwright/` (agent tools, stdlib only: perception, validation, and the new
`cutwright/engine/` executor layer) and `recapstudio/` (the video engine: Python + Remotion).
Goal: an AI agent (you) makes ANY kind of video by calling typed tools. Architecture: `docs/ARCHITECTURE.md`.
Editing infrastructure = Kinocut first, FFmpeg direct where justified by tests. Graphics = Remotion.
Shotcut is being REMOVED.

## Executor rule
- Use Kinocut when `docs/CAPABILITY_MATRIX.md` says it passed; use direct FFmpeg (a named typed op) when it did not,
  with `executor_reason`.
- Never duplicate an op Kinocut passes; never keep two implementations of one op.
- `cutwright/` stays stdlib-only; Kinocut runs in `.venvs\kinocut` via subprocess; writes go through
  `cutwright/guard.py`.

## Hard exclusions (never)
- No AI-generated images or video, ever. Use real footage, user assets, or code-made graphics; or report the asset
  missing.
- No FireRed-OpenStoryline. No Shotcut in the automated pipeline or as a fallback. No copying OpenMontage code
  (AGPL-3.0; ideas only; ask first).
- No paid API / cloud service / heavy model without the owner's explicit yes. No new npm packages without the owner.
  Remotion stays 4.0.539.
- Never print, commit or paste `keys.env`, API keys, `voices/`, `models/`, `venvs/`, `.venvs/`.
- Never run `recap.py` with `--force`, `init`, or `collect` unattended.

## Verify before depending
Kinocut's real interface and Windows behaviour must be shown by running it (M1/M2) before any code relies on it.
