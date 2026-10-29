# 03 - Objectives and session boundaries

## One objective at a time, then STOP
- One milestone at a time, in order (`HANDOFF.md`). Work in discrete objectives.
- After finishing an objective: run its required checks, then update the handoff/roadmap with the completed work and
  the evidence, summarize changes and test results, list the next objective, then **STOP and WAIT for the owner's
  approval**.
- **Never automatically proceed to the next objective.** Never begin implementation (or install dependencies) inside an
  objective that did not ask for it.
- The owner starts a fresh Cline session between objectives to save tokens. Leave enough state in `HANDOFF.md`,
  `LOG.md` and `COMMS.md` that the next session resumes without repeating completed work. Keep documentation concise.

## When an objective/milestone is done (before anything else)
1. `LOG.md` entry with TESTED / FAILED / NOT TESTED lists (command + quoted result).
2. Tick the milestone and update the status block in `HANDOFF.md`.
3. Decisions, surprises, failed assumptions -> `COMMS.md` entry.
4. `git add` + `git commit -F msg.txt` + push (if a verified remote exists).
5. Tell the owner "Milestone Mx done. Start a new session." and print the kickoff text from `HANDOFF.md`.

## When stuck
After two failed attempts at the same problem, STOP. `BLOCKED` entry in `COMMS.md` (commit hash, files, what you
tried, real output, one question). No third try.

## Keeping costs low
Context is re-read every request. Past ~60% or at a milestone end: do the "done" steps and ask for a new session.
