# Cutwright (merged with Recap Studio)

**One project, two halves.** An engine of tools an AI agent calls to make videos of any kind.

| half | folder | role |
|---|---|---|
| Cutwright | `cutwright/` | agent layer (stdlib only): `doctor`, `probe`, subtitle gate, moments, frame verification, whisper, write guard, and the **engine** (manifest -> typed ops on Kinocut / FFmpeg) |
| Recap Studio | `recapstudio/` | the video engine: Python pipeline (script, TTS, frame-exact timing, `timeline.json`) + Remotion renderer + agent-written TSX scenes + web UI; Premiere XML / VideoPad / ffmpeg exports |

**Editing infrastructure (2026-10-29, executed in M4/M5):** Kinocut first, direct FFmpeg where the
measured capability matrix says Kinocut did not pass, Remotion for motion graphics. There is **no
editor-application backend**: the old timeline writer, its window automation and its checks were
deleted in M5 (2026-10-30). Nothing in the pipeline opens an editor, and none may come back.

Agents (DeepSeek via Cline, or any other) start at **`.clinerules/`**, then **`HANDOFF.md`** (status +
milestone table), then **`docs/ROADMAP.md`**. Specs are in `docs/` (`ARCHITECTURE.md`, `CODEMAP.md`,
`TOOLS.md`, `CAPABILITY_MATRIX.md`, `KINOCUT_FINDINGS.md`, `VISUAL_STANDARD.md`). Old handoffs,
reports and the v2 vision are in `docs/legacy/`.

Quick start on Windows: run `recapstudio\SETUP.bat` (Node + Remotion + voice tools), install Kinocut
once into its own venv (`docs/KINOCUT_FINDINGS.md` section 1), then `python -m cutwright doctor`.

## Layout

```
cutwright\            agent layer (stdlib only)
  cli.py              every verb below; parses and prints, decides nothing
  guard.py            the write invariant: nothing outside this folder is ever written
  probe.py subs.py moments.py frames.py transcribe.py    perception tools
  engine\             ops.py (op data), registry.py (discovery + routing),
                      manifest.py (run/resume/checkpoints), validate.py, gates.py,
                      report.py, ids.py, checkpoint.py,
                      executors\kinocut.py, executors\ffmpeg.py
recapstudio\          the video engine (Python + Remotion); _template\recap.py is the pipeline,
                      _template\engine_bridge.py the only bridge to cutwright.engine
docs\                 architecture, roadmap, capability matrix, evidence, schemas
.venvs\kinocut\       isolated Kinocut CLI (not in git)
testclips\ out\        short samples and per-video analysis output (not in git)
```

## What works today

| command | does |
|---|---|
| `doctor` | what this machine has: ffmpeg, whisper, **Kinocut, Recap Studio engine, Node, Remotion, Python modules**; proves the write guard |
| `probe <file>` | streams, duration, subtitle tracks |
| `subs <video>` | find the best subtitle source and prove it usable |
| `moments <video>` | transcript -> beats -> ranked candidate moments + agent digest |
| `verify <video>` | grade picks against frames: verified / retimed / replaced |
| `transcribe <video>` | whisper.cpp transcript, then gated (needs `bin\`, `models\`) |
| `tools list\|describe\|envelope` | what the engine can do, one op or one stage at a time |
| `validate <manifest>` | pre-render check: ops, params, refs, budget, asset provenance |
| `run <manifest>` | execute it; cached steps are skipped on a re-run |
| `resume <run-dir>` / `status <run-dir>` | continue from the checkpoint / read it step by step |
| `approve <run-dir> <gate>` | release the step sitting behind an approval gate |

Recap Studio steps run inside a project folder (`cd recapstudio\Projects\<name>`, then
`python recap.py <step>` with `RECAP_NONINTERACTIVE=1`): `tts`, `video`, `timeline`, `scenes`,
`remotion`, `premiere`. `studio.py` is the web UI. What is verified on this PC, with numbers, is in
`HANDOFF.md` and `LOG.md`.

## Usage

```powershell
cd C:\Users\user\Desktop\Cutwright-kinocut-handoff\cutwright
python -m cutwright doctor
python -m cutwright probe "C:\path\to\film.mp4"
python -m cutwright subs "C:\path\to\film.mp4"
python -m cutwright moments "C:\path\to\film.mp4" --top 10
python -m cutwright verify  "C:\path\to\film.mp4"
python -m cutwright transcribe "C:\path\to\clip.mp4" --subs "C:\path\to\film.srt"
python -m cutwright tools list --stage assemble
python -m cutwright tools describe trim
python -m cutwright validate out\fx\demo_manifest.json
python -m cutwright run      out\fx\demo_manifest.json --json
python -m cutwright resume   out\fx\run
python -m cutwright status   out\fx\run
```

A manifest is JSON: one `steps` list, each step naming an op, its declared inputs, params, outputs and
what must be validated. The full shape the M3 demo renders is `docs/schemas/manifest.example.json`;
op names and params come from `python -m cutwright tools describe <op>`, and the measured evidence
behind every routing decision is `docs/CAPABILITY_MATRIX.md`.

```json
{
  "schema": 1, "run_id": "demo-0001", "pipeline": "recap",
  "fps": 24, "size": [1920, 1080],
  "assets": [{"id": "src_a", "path": "out/fx/a.mp4", "origin": "footage", "license": "owner-supplied"}],
  "steps": [
    {"id": "cut_1", "op": "trim_exact", "inputs": {"src": "@asset.src_a"},
     "params": {"start_frame": 37, "frames": 50}, "executor": "kinocut",
     "outputs": {"video": "production/demo-0001/work/cut_1.mp4"},
     "validation": [{"check": "frame_count", "expect": 50}]}
  ]
}
```

## Testing rules

Never test on a full episode or a long file. Every test uses a short sample cut out of the footage
first, because a 24-minute file turns a 30-second check into a 30-minute wait and a 500 MB WAV.

* **30-90 seconds per clip, hard cap 2 minutes.** Cut with stream copy so it is instant and lossless
  and the sample is bit-identical to the source range:
  `ffmpeg -ss 00:05:00 -to 00:05:01:30 -i "<source>" -c copy -avoid_negative_ts make_zero "testclips\<name>.mp4"`
* **Pick samples that cover what is being tested**, not just the first minute: one clip with dialogue,
  one silent action clip, one with a hard cut on a known timestamp.
* **Never write into the original folders.** Samples are cut *from* the originals and saved *into*
  `testclips\`; the guard enforces this.
* **If a test would take more than about 2 minutes, say the estimate and ask** before running it.
* **Cache anything slow.** A transcript is written once and reused; a run re-uses any step whose cache
  key is unchanged (`status` shows it).
* **Test the real path**: produce media, decode it, count frames, check ids/audio, look at frames. An
  import that succeeds is not a test.
* **Full-length runs only when explicitly asked for.**

## Not built yet

| piece | status |
|---|---|
| agent bridge `recap <step> --json` + focused tool discovery | M6 (done) |
| agent-owned scene loop (3 scenes written by the agent, one revised after viewing frames) | M7 (done) |
| production blueprint: brief -> beats -> validated manifest, plus a 3-beat production run end to end | M8 (done) |
| visual quality overhaul + 5-scene benchmark at 16:9 and 9:16 (old G6) | M8b / before M9 - OPEN |
| perception -> script for arbitrary footage | M10 |
| blueprints / any-video profiles (the rest of G8/G9) | M11 |
| SFX engine | M12 |
| true 9:16, speed, polish | M13 |
| MCP server + portable skill | M14 |
| Cutwright Studio UI | M15 |

## Rules and provenance

`.clinerules/` holds the working rules (session loop, architecture and hard exclusions, testing and
evidence, session boundaries). `PROVENANCE.md` records where every byte came from and what was
deliberately not copied; `docs/legacy/PROVENANCE_removed_editor.md` keeps the deleted editor
backend's hashes as history. Nothing gets installed or downloaded without the owner's approval.

Standard library only in `cutwright/`. ffmpeg and ffprobe must be on PATH (they are). Kinocut lives in
`.venvs\kinocut` and is called by subprocess -- `import kinocut` appears nowhere in `cutwright/`.
`transcribe` additionally needs `bin\whisper\Release\whisper-cli.exe` and
`models\ggml-small.en.bin`; without them it prints the exact install steps and exits 3.
