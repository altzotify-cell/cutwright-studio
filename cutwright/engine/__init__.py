"""Cutwright engine: ONE plan and ONE timeline, whatever tool executes an op (M3).

Layers, in dependency order (full text: `docs/ARCHITECTURE.md`):

  ops.py        what can be done (name, stage, params, validator, default executor)
  executors/    who does it: kinocut | ffmpeg | remotion | python -- typed calls only
  manifest.py   run state machine: pending | running | done | failed | skipped
  checkpoint.py atomic JSON state, resume cursor, per-step cache key
  gates.py      approval gates in production/<run>/approvals/
  validate.py   pre-render plan checks, post-render media checks
  report.py     production_report.json

The executor for each op is data taken from `docs/CAPABILITY_MATRIX.md`, never a guess.
Stdlib only (`cutwright/` stays dependency-free); Kinocut is reached through
`engine/executors/kinocut.py` in `.venvs\\kinocut` by subprocess. Every file written goes
through `cutwright.guard.write_*/ensure_dir`.
"""
