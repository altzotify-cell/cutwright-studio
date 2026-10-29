# References: Kinocut, OpenMontage, HyperFrames, FireRed (licences, claims, what to verify)

Written 2026-10-29 by the Claude consultant from the projects' public GitHub pages. The consultant could NOT install
or run anything (sandbox without network). **Everything marked CLAIM is the project's own statement and unverified.**
DeepSeek verifies on the owner's Windows PC in M1/M2 and records results in `docs/KINOCUT_FINDINGS.md`
and `docs/CAPABILITY_MATRIX.md`. Do not build on a CLAIM before its check passes.

## 1. Kinocut  (https://github.com/KyaniteLabs/kinocut)

| Item | Value | Status |
|---|---|---|
| Licence | Apache-2.0 | repo page shows it; DeepSeek confirms the LICENSE file text and records sha256 in `PROVENANCE.md` |
| What | "Guardrailed video editing MCP server for AI agents"; wraps FFmpeg; Python `Client`, `kino` CLI, MCP server; formerly `mcp-video` | CLAIM |
| Version | 1.16.4 published 2026-10-24 (PyPI). `master` is an "unreleased QoL pass" | CLAIM. Pin the release, not master |
| Python | >= 3.11 (3.11-3.13 classifiers) | from an older `pyproject.toml` (1.15.2); re-check for 1.16.4 |
| Core deps | `mcp>=1.27,<2`, `pydantic>=2.13`, `rich>=15` | same caveat |
| Required binaries | FFmpeg + ffprobe on PATH | CLAIM |
| Optional | `transcribe` = openai-whisper (torch, ~1 GB); `image`, `audio`, `stems`, `upscale`, `ai`, `object-matte`. Hyperframes is NOT a pip extra: it is an external Node 22+ CLI, Kinocut accepts specific versions (0.8.104 / 0.8.140 when telemetry is off) | CLAIM |
| Windows | "first-class" since 1.15.0, windows-latest CI smoke job, `kino doctor` | CLAIM. M1 verifies |
| Surface | 203 MCP tools / 177 CLI commands published; dev tip: 20 default MCP tools, 205 with `KINOCUT_TOOLS=all`; `search_tools` for discovery; `KINOCUT_TOOLS=profile:editor` | CLAIM |
| Workflow engine | JSON job spec; ops allowlist `probe, trim, resize, convert, crop, merge, add_text, composite_layers, burn_in`; commands `workflow-validate / -plan / -render / -inspect`, `--resume`, `--all-variants`; receipts with per-step input/output sha256 and a resume cursor | CLAIM. Note: no audio-mix, transition or speed op in the allowlist |
| Compositing | `composite-layers`: image/video/solid layers, opacity, x/y, timing, mask/matte, blend (multiply/screen/overlay/darken/lighten), rotation. "Output remains video-only" | CLAIM |
| Other documented areas | trim/merge/resize/crop/rotate/convert, overlays, subtitles, fades, effects, transitions (glitch/morph/pixelate), picture-in-picture, split-screen, animated text, audio normalize/mix/ducking, scene detection, thumbnails, storyboard, quality compare, `video_quality_check`, `release_checkpoint`, repurposing, 360 assembly, rescue, AI-video review, still/plate editing | CLAIM |
| Guardrails | explicit `overwrite=true` for existing outputs; protected paths; preflight validation (filter bounds, merge compatibility, mix volume/timing); output-aliases-input rejection | CLAIM |
| Model/telemetry defaults | optional model calls default off; Hyperframes/Revideo telemetry default off | CLAIM |
| Maintenance | single maintainer, renamed recently (mcp-video -> kinocut), 1,664 commits, 223 stars, rapid release cadence | risk: pin versions, narrow adapter, tests as the safety net |

### Things the owner's brief assumed that are NOT as assumed
- "Whisper extra" is heavy (torch). We keep whisper.cpp / faster-whisper. Do not install `kinocut[transcribe]`.
- HyperFrames is an external Node tool, not a bundled Kinocut renderer.

### What must be discovered from the installed package (do not guess)
`kino --help`; `kino <command> --help` for each command we may use; whether any command emits machine-readable
output (look for a JSON/format flag in `--help` before assuming one exists); `Client.inspect("<op>")`;
`Client.search_tools("<word>")`; exit codes on failure; where outputs and receipts are written; Windows path handling
(spaces, drive letters, non-ASCII); behaviour under Cline's PowerShell (no TTY, UTF-8). Record all of it in `docs/KINOCUT_FINDINGS.md`.

## 2. OpenMontage  (https://github.com/calesthio/OpenMontage)  - ARCHITECTURAL REFERENCE ONLY

- Licence: **AGPL-3.0** (repo page shows an AGPL-3.0 licence badge/file; the consultant did not read the LICENSE text).
  DeepSeek: open the LICENSE on GitHub, confirm "GNU AFFERO GENERAL PUBLIC LICENSE Version 3", record it in `PROVENANCE.md`.
- Consequences: copying or adapting its code/prompts/schemas/skill text into this repo would make that part a derivative
  under AGPL-3.0 (copyleft incl. network-use clause). We do not do that.
- Policy (binding): **clean-room.** Read only its public README/architecture description for ideas. Do not paste, translate or
  closely paraphrase its files. Write our own schemas/skills from our own needs. If DeepSeek feels a file must be reused,
  STOP and write a COMMS entry; only the owner can approve, and the approval must be recorded in `PROVENANCE.md`.
- Ideas judged worth adapting: see the table in `docs/ARCHITECTURE.md`. Ideas rejected: its generative image/video/avatar
  providers (forbidden here), cloud providers and paid-API assumptions, the Backlot UI, 100+-tool scale.
- Observed (README, CLAIM): agent-as-orchestrator over YAML manifests + markdown stage skills + a tool registry; JSON
  checkpoints; human approval gates; pre-compose validation; post-render self-review (ffprobe, frame sampling, audio levels);
  slideshow-risk scoring; budget governance. It also uses Remotion AND HyperFrames, choosing one per project at proposal time
  and locking it - evidence that a project can carry both, not a reason for us to.

## 3. HyperFrames  (HeyGen; Apache-2.0 per its page; CLAIM)

Headless-Chrome frame seeking + FFmpeg encode from HTML/CSS/GSAP; Node 22+; CLI `init / preview / render`.
Same render mechanism as Remotion, so expect similar speed on the i5. **Not adopted.** Decision only after the M9 benchmark
(`docs/ROADMAP.md`). Through Kinocut it is reachable only via an external CLI at pinned versions; do not install it earlier.
Remotion stays: licence checked 2026-10 (free for individuals / teams up to 3), pinned 4.0.539.

## 4. FireRed-OpenStoryline - EXCLUDED

Deliberately out of scope by the owner. No dependency, no adapter, no architecture borrowing, no research time.
If a doc or tool suggests it, ignore the suggestion.

## 5. Shotcut / cli-anything-shotcut / Shotcut MCP - REMOVED from the target

Old plan G1-G3 (crossfade, recon, adopt `cli-anything-shotcut`) is cancelled. No recon of those repos. Nothing from
`docs/BORROW_notes.md` about them is to be adopted.

## 6. Licence table (fill the last column during M1; commit the result)

| Component | Licence (claimed) | LICENSE text read by DeepSeek? | Used as |
|---|---|---|---|
| Kinocut | Apache-2.0 | **yes, 2026-10-29** - Apache License 2.0 text, sha256 `733474B9...D837` (`PROVENANCE.md`) | pip dependency in isolated venv |
| FFmpeg (Gyan build) | LGPL/GPL depending on build (`ffmpeg -version` shows `--enable-gpl`) | **yes, 2026-10-29** - 7.1-full_build-www.gyan.dev, `--enable-gpl --enable-version3` = GPL build | external binary, called as a process |
| Remotion 4.0.539 | Remotion licence (free for individuals / <=3-person teams) | checked 2026-10, re-read once | npm dependency |
| HyperFrames | Apache-2.0 | todo (M9 only) | benchmark only |
| OpenMontage | AGPL-3.0 | **yes, 2026-10-29** - GNU AGPL v3 text (544 lines), sha256 `0D96A4FF...BCB0` (`PROVENANCE.md`) | ideas only, no code |
| Whisper.cpp / faster-whisper | MIT (claimed) | existing PROVENANCE | existing |
| Edge-TTS | n/a (uses a Microsoft online service; existing) | existing | existing |

Redistribution note: this repo does not vendor Kinocut, FFmpeg, Remotion or HyperFrames. They are installed by the user.
