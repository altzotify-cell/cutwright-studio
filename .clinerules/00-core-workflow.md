# 00 - Core workflow (read first, every session)

Project shape, constraints and testing rules are in `01`-`03` of this folder. This file is the work loop.

## Start of every session (cheap start, no exploring)
1. Read `HANDOFF.md` (status block, constraints, milestone table).
2. Read the last 3 entries of `COMMS.md` and the last 40 lines of `LOG.md`.
3. Tell the owner in 3 lines: current milestone, next step, anything blocked. Then WAIT for the go.
4. Read ONLY the current milestone's section of `docs/ROADMAP.md`
   (`Select-String -Path docs\ROADMAP.md -Pattern '^## M'` for line numbers, then slice).
5. Never read whole: `recapstudio/_template/recap.py` (5,400+ lines), `recapstudio/studio.py`, `recapstudio/web/app.js`,
   `cutwright/mlt.py` (to be deleted), `docs/legacy/*`, videos, logs, `node_modules`. Use `docs/CODEMAP.md` for ranges.

## Pre-flight on a fresh checkout (before changing anything)
Check git state (`git status`, `git remote -v`, branch), `py -0p`, `python --version`, `node --version`,
`where.exe ffmpeg`, `ffmpeg -version`, `python -m cutwright doctor`. Record in LOG. Do not assume the ZIP has git
history, the right remote, Python >= 3.11, or Kinocut installed.

## Editing discipline
- Small targeted edits; never rewrite a whole file to change a few lines. Keep any single write under ~3,000 characters.
- Do not grow `recap.py`; new code in new modules + thin bridge. Delete only after the replacement passed;
  deletions in their own commit.
- Windows/PowerShell: no `Set-Content`/`Out-File` for text (BOM); create files with the editor tool or Python;
  `git commit -F msg.txt`, not `-m`.

## Cost control
Talk to the owner plainly: short, exact Windows steps, paste-ready commands. Never ask the owner to run what you
can run yourself.
