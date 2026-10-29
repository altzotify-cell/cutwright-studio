> **SUPERSEDED (2026-10-29).** Do not adopt cli-anything-shotcut, a Shotcut MCP, or NarratoAI on the strength of these notes.
> Current references and licences: `docs/REFERENCES.md`. HyperFrames: benchmark only (M9). FireRed: excluded.

# Borrow notes (first look, 2026-10-29; replaced by `docs/BORROW.md` in G2)

Source of these notes: web search results and project/PyPI pages read by the Claude consultant. NOT the repos'
code, NOT the LICENSE files. Treat every line as a lead to verify, not a fact to build on.

## cli-anything-shotcut (HKUDS/CLI-Anything) - the main thing the owner wants adopted

- PyPI `cli-anything-shotcut` 1.0.0, released 2026-03-13, status "4 - Beta", one maintainer. Licence shown on PyPI: MIT.
- "CLI harness for Shotcut - video editing and rendering via melt/ffmpeg." Works on MLT XML project files, no GUI.
- Needs Python 3.10+, `lxml`, `click` (optional `prompt_toolkit` for a REPL); `melt` and `ffmpeg`/`ffprobe` on the machine.
- Commands listed on the page:
  - project: create / open / save / inspect, list profiles (hd1080p30, 4k60 ...)
  - timeline: add / remove / move / trim / split clips; tracks, gaps, mute, hide
  - filters: list / add / set / remove (track or clip)
  - transitions: 11 types incl. dissolve, wipes, clock, iris-circle, crossfade
  - compositing: blend modes, track opacity, picture-in-picture (`composite pip`)
  - media: probe, list, check files exist, extract thumbnails
  - export: presets (h264-high, h265, prores, gif ...) and render
  - session: status, undo/redo; `--json` flag; interactive REPL
- NOT on the PyPI page (the owner's older notes claimed some of these; verify in the repo): audio ducking / volume
  envelopes, preview bundles, a `SKILL.md`.
- Known Cutwright risk that applies to ANY borrowed transition/blend: Shotcut disables a flat multitrack blend
  (`disable=1` on `frei0r.cairoblend`) on every Ctrl+S. Output must be proven after a real save.

## HyperFrames (heygen-com/hyperframes)

- Open source, Apache-2.0 (per its page). HTML + CSS + seekable animations -> MP4: "seeks each frame in headless
  Chrome and encodes with FFmpeg". Node 22+ and FFmpeg. CLI: `npx hyperframes init / preview / render`, `add` for catalog blocks,
  `skills add/update`. Presents itself as built for agents (non-interactive CLI, agent skills, Claude Code plugin).
- Its own comparison claims no bundler/build step (vs Remotion's React + bundler) and a more permissive licence than
  Remotion's source-available one. These are the project's claims about itself.
- Alpha / transparent output: not mentioned on the page. Unknown.
- Same render mechanism as Remotion, so overlap is large. Decision (owner, 2026-10-29): bake-off in G10, no switch.

## Shotcut MCP

- The owner's notes name `NoBanks/shotcut-mcp`. A search found other `shotcut-mcp` listings (for example under a
  different user on glama.ai) and a Shotcut forum thread asking whether any MCP server exists. Which repo is real and
  what it does is UNKNOWN: G2 must check.

## NarratoAI (linyqh/NarratoAI)

- Not looked at in this pass. Owner's notes list: Sonilo BGM/SFX API, Tavily plot-search, subtitle mask, keyframe
  batching, TwelveLabs option, cheap hosted captioning. All optional, default off, licences unread.

## Rules that already apply (from the old handoff)

Read a repo's LICENSE before copying anything. Unclear licence = copy the file-format shape and write code fresh.
Record every borrowed file in `PROVENANCE.md`. Each borrowed feature needs a Cutwright check and a real Ctrl+S test.
