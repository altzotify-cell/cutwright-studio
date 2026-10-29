# Kinocut findings (M1: isolated install and interface discovery)

Written 2026-10-29 by the agent on the owner's Windows PC. Everything below was observed by running the
installed package; nothing is inferred from the README. Raw captures live in `out/m1/` (gitignored):
`cap/` (stdout/stderr/exit per command), `edge/`, `ops/`, `help/`, `doctor.txt`, `install2.log`.

Platform: Windows 10.0.26200, Python 3.11.9, FFmpeg 7.1-full_build (gyan.dev), Node v24.18.0.

## 1. Install facts

| Item | Value |
|---|---|
| Interpreter | `py -3.11` -> `C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe` (3.11.9) |
| Venv | `.venvs\kinocut` (`include-system-site-packages = false`) |
| Venv creation time | **75.4 s** (Defender-heavy; a 30 s kill leaves a venv WITHOUT pip - see section 7.1) |
| pip | 24.0 (bundled) -> upgraded to 26.2.2 |
| Install command | `.venvs\kinocut\Scripts\python -m pip install "kinocut==1.16.4"` |
| Install time | **199.4 s**, exit 0 |
| Venv size on disk | **95.7 MB** |
| Installed | kinocut 1.16.4 (`--version` -> `Kinocut 1.16.4`, exit 0) |
| `.venvs/` in git | already ignored: `git check-ignore -v .venvs` -> `.gitignore:76:/.venvs/` (exit 0) |

Dependency tree actually installed (38 packages, `pip list`):

```
kinocut 1.16.4  -> mcp 1.30.0, pydantic 2.14.2, pydantic-settings 2.16.2, rich 15.0.0,
starlette 1.10.0, uvicorn 0.54.0, sse-starlette 3.6.0, python-multipart 0.0.32,
jsonschema 4.26.0, jsonschema-specifications 2025.9.1, referencing 0.37.0, rpds-py 2026.9.1,
httpx 0.28.1, httpx-sse 0.4.3, httpcore 1.0.9, anyio 4.15.1, h11 0.16.0, idna 3.20, certifi 2026.10.23,
cryptography 50.0.2, cffi 2.1.1, pycparser 3.12, PyJWT 2.15.1, pywin32 312,
attrs 26.1.0, annotated-types 0.8.0, typing_extensions 4.16.0, typing-inspection 0.4.4,
click 8.5.0, markdown-it-py 4.2.0, mdurl 0.1.2, Pygments 2.21.0, python-dotenv 1.2.4,
referencing/pip/setuptools (65.5.0)
```

Entry points in `.venvs\kinocut\Scripts`: `kino.exe`, `kinocut.exe`, `mcp-video.exe`, `mcp.exe`,
`uvicorn.exe`, `dotenv.exe`, `httpx.exe`, `idna.exe`, `jsonschema.exe`, `markdown-it.exe`,
`pygmentize.exe`, `cffi-gen-src.exe`, `pywin32_postinstall.exe`, `pywin32_testall.exe`.

**Not installed (deliberate, A3):** no `kinocut[transcribe]`, no torch, no numpy, no opencv, no pillow.
Consequence: `ai_transcribe` and `still_plates` capabilities report `unavailable` (see section 3).

## 2. `kino doctor`

`.venvs\kinocut\Scripts\kino.exe doctor` -> exit 0 in 9.7-12.0 s. First line, verbatim:

```
Kinocut doctor - OK
```

`kino doctor --json` (or `kino --format json doctor`, exit 0, 7.7 s) ->
`success: true`, `summary.required_ok: true`, `missing_required: []`, `total_checks: 37`,
`passed: 10`, `optional_available: 3`. `platform` reports
`python 3.11.9`, `executable ...\.venvs\kinocut\Scripts\python.exe`,
`system Windows-10-10.0.26200-SP0`.

Required checks, all `OK`: `Kinocut 1.16.4`, `mcp-server-import` ("kinocut.server imports cleanly"),
`ffmpeg` (7.1-full_build), `ffprobe` (7.1-full_build), `mcp 1.30.0`, `pydantic 2.14.2`, `rich 15.0.0`.
Optional and present: `node v24.18.0`, `sphere_director`, plus `optional_available: 3`.

Missing optional (27): `npx`, `npm`, `hyperframes`, `@hyperframes/core`, `pillow`, `scikit-learn`,
`webcolors`, `anthropic`, `openai-whisper`, `demucs`, `realesrgan`, `basicsr`, `numpy`,
`opencv-contrib-python`, `torch`, `torchaudio`, `torchcodec`, `imagehash`, `scipy`, `soundfile`,
`librosa`, `basic-pitch`, `meltysynth`, `crush_shaders`, `audio_engine`, `still_plates`,
`object_matte`.

Note: `doctor` also runs a `python` check that resolves the system interpreter (reported 3.13.2 on
PATH) - informational only; the venv interpreter is what runs.

## 3. What is actually usable here (`video-capabilities`)

`kino --format json video-capabilities` -> exit 0, 7.7 s, proper JSON.
`kino video-capabilities` (text) -> exit 0 but prints a **Python dict repr** (`{'success': True, ...}`,
single quotes) - not JSON, not for parsing.

| capability | available | why |
|---|---|---|
| `video_edit` | yes | ffmpeg |
| `subtitles` | yes | ffmpeg |
| `audio` | yes | ffmpeg |
| `c2pa_signing` | yes (optional dep `c2patool` absent) | - |
| `ai_transcribe` | **no** | `required_dep_missing: openai_whisper` |
| `still_plates` | **no** | `required_dep_missing: pillow` |

## 4. CLI contract

Global options (must come **before** the subcommand, see section 7.2):

```
kino [--mcp] [--overwrite] [--format {text,json,auto}] [--version] [-v] [--log-file PATH] <command> ...
```

`kino --help` lists ~200 subcommands. Also namespaced aliases: `kino <group> <action>` ->
flat command (`aivideo, audio, qa, edit, shorts, sound`). There is **no** `search-tools` CLI
command (that exists only on the Python `Client`). `quality-check` is spelled
`video-quality-check`.

Commands probed with `--help` (all exit 0), with the arguments that matter:

| command | key arguments | notes |
|---|---|---|
| `info` | `input` | prints a table; JSON via `--format json` |
| `trim` | `-s -d -e -o --accurate` | cut a segment; `--accurate` = frame-accurate seek (slower) |
| `merge` | `inputs... -t {fade,dissolve,wipe-left,wipe-right,wipe-up,wipe-down} --transitions ... -td -o` | **transitions built in** |
| `resize` | `-w --height -a {16:9,9:16,1:1,4:3,4:5,21:9} -q -o` | aspect presets incl. 9:16 |
| `crop` | `-w --height -x -y -o` | note: width short flag is `-w`, height only long |
| `speed` | `-f FACTOR -o` | |
| `convert` | `-f {av1,gif,hevc,mov,mp4,prores,webm} -q --two-pass --target-bitrate -o` | |
| `export` | `-q -f {mp4,webm,gif,mov} --c2pa-*` | |
| `add-text` | `-p` 9 anchors, `--font --size --color --no-shadow --start-time --duration -o`, `input text` | text as a positional arg |
| `subtitles` | `input subtitle --style -o` | |
| `fade` | `--fade-in --fade-out --crf --preset -o` | |
| `overlay-video` | `background overlay -p -w --height --opacity --start-time --duration --crf --preset -o` | PiP |
| `split-screen` | `left right -l {side-by-side,top-bottom} -o` | |
| `composite-layers` | `--spec SPEC -o --save-layer-plan --dry-run` | JSON spec, see section 5 |
| `mix-audio` | `input --sounds --keep-source/--no-keep-source --audio-bitrate -o` | |
| `duck-audio` | `input music -o --music-volume --threshold --ratio --attack --release` | sidechain ducking exists |
| `normalize-audio` | `-l LUFS --lra --true-peak-dbtp --fade-seconds -o` | loudness normalisation |
| `batch` | `--operation {trim,resize,convert,filter,blur,color_grade,watermark,speed,fade,normalize_audio} --params -o inputs...` | |
| `detect-scenes` | `-t threshold --min-duration` | |
| `video-quality-check` | `--fail-on-warning --format {text,json}` | |
| `release-checkpoint` | `-o --min-score --frame-count --require-audio/--no-require-audio --format {text,json}` | QC receipt + storyboard |
| `workflow-validate` | `--spec SPEC` | job-spec validation; `workflow-plan/-render/-inspect` exist |

## 5. Output contract (observed, not documented)

* Success JSON: `{success: true, output_path, duration, resolution, size_mb, format, operation,
  progress, thumbnail_base64, elapsed_ms, warnings, intermediates, c2pa}` (trim example).
  `info --format json` returns `{success: true, data: {path, duration, width, height, fps, codec,
  audio_codec, audio_sample_rate, bitrate, size_bytes, format, rotation}}`.
* Error JSON: `{success: false, error: {type, code, message, suggested_action {auto_fix,
  description}}}`; exit code **1**. Observed codes: `output_exists` (type `validation_error`),
  `invalid_input` (type `input_error`), `quality_gate_failed` (type `quality_error`),
  `unsafe_layer_source` (type `validation_error`).
* Text mode errors are rich panels with box-drawing characters (`┌─ Error ─┐`).
* argparse errors -> exit **2** (e.g. a misplaced global flag).
* `--format auto` is documented as "json when stdout is piped" but is **not** the default: with
  stdout piped and no flag, `doctor`/`info` still print tables. Pass `--format json` explicitly.
* Some commands carry their own `--format` (`doctor --json`, `release-checkpoint --format`,
  `video-quality-check --format`) - those work *after* the subcommand.

### `composite-layers` spec (recovered from the installed package, not guessed)

```json
{"canvas": {"width": 160, "height": 90, "fps": 24, "duration": 2.0, "background": "#000000"},
 "layers": [{"id": "base", "type": "video", "src": "a.mp4", "position": {"x": 0, "y": 0}},
            {"id": "tint", "type": "solid", "color": "#FF00FF", "opacity": 0.35,
             "position": {"x": 0, "y": 70}, "width": 160, "height": 20}]}
```

Layer types `video|image|solid`; supported fields `alpha_mode, anchor, blend, color, duration,
height, id, mask, matte, opacity, pivot, position, rotation, scale, src, start, transform, type,
width, x, y`. `src` must stay inside the spec file's directory (section 7.4). Output is **video-only**.

## 6. Python `Client`

`from kinocut import Client; Client()` works inside the venv; ~170 public methods, same names as
the CLI but snake_case (`trim`, `merge`, `composite_layers`, `release_checkpoint`,
`quality_check`, `capabilities`, `search_tools`, `inspect`, `workflow_render`, ...).
`Client.trim` signature: `(input, start=0, duration=None, end=None, output=None, accurate=False,
*, overwrite=False)`. `Client.inspect("trim")` returns
`{name, category, parameters, aliases{input->input_path, output->output_path}, return_type: EditResult}`.
`Client.search_tools("trim")` returns `{success, query, count, tools[{name, description,
required_params}]}` (4 hits for "trim", incl. `video_trim`, `video_batch`,
`video_workflow_render`, `video_workflow_validate`).

**Decision (unchanged): the adapter uses the CLI through subprocess, not `import kinocut` in
`cutwright/`** (A2, stdlib-only). `Client` is only used here to discover the surface.

## 7. Windows / Cline edge cases (each run, with the real result)

**7.1 A killed venv has no pip.** The first `py -3.11 -m venv .venvs\kinocut` was cut off at 30 s by
the tool timeout. The directory looked complete but `python -m pip` -> `No module named pip`, exit 1,
for both the pip upgrade and the install. Recreating the venv in a background process (75.4 s) fixed
it. Rule: never treat "`python.exe` exists" as "venv ready"; check `pip --version` / `kino.exe`.

**7.2 Global flags must precede the subcommand.** `kino video-capabilities --format json` ->
`kino: error: unrecognized arguments: --format json`, exit **2**. `kino --format json
video-capabilities` -> exit 0. `--overwrite` behaves the same way (`kino --overwrite trim ...` ->
exit 0). Per-command `--format`/`--json` flags are the exception and go after the command.

**7.3 No TTY is fine.** All probes ran with stdout/stderr as pipes and no console: exit codes and
JSON were correct. Only *rendering* suffers (section 7.4).

**7.4 Console encoding is the one real hazard.** Kinocut writes UTF-8; the PowerShell console here is
cp1252, so rich output shows mojibake when captured through a console, and a Python wrapper that
prints the captured stderr to that console dies with
`UnicodeEncodeError: 'charmap' codec can't encode character '\u2502'`. Mitigation for the adapter:
always capture bytes and decode UTF-8 in-process, never re-print Kinocut's panel text to a cp1252
console; prefer `--format json`. (`PYTHONIOENCODING=utf-8` is the alternative.)

**7.5 Path with spaces + non-ASCII works.** `out\fx dir\café.mp4` -> `info` exit 0, and
`trim ... -o "out\fx dir\sortie café.mp4"` exit 0 with the output file on disk (9648 B). JSON echoed
the path as `...\\sortie caf\u00e9.mp4`.

**7.6 Long path works.** 6 nested segments -> input path 253 characters: `trim` exit 0, output written.

**7.7 Existing output is refused, then replaceable.** Second `trim` to the same `-o` -> exit 1,
`{"type": "validation_error", "code": "output_exists", "message": "Output path already exists; pass
overwrite=true to replace permitted outputs: out\\m1\\edge\\trim.mp4"}`. With the global
`--overwrite` in front -> exit 0. The guardrail is real; the adapter must decide explicitly.

**7.8 Missing input is a clean error.** `info out\fx\does_not_exist.mp4` -> exit 1, rich panel
`Input file error: ...- File not found (archivo no encontrado)` `Code: invalid_input` +
`Suggested fix`; with `--format json` the same as `{"type": "input_error", "code":
"invalid_input", ...}`. (The message is localised - it appended Spanish.)

**7.9 Bare `kino` is an MCP server.** `kino` with no arguments and `kino --mcp`, stdin at EOF:
exit 0 after 7.1-7.8 s, no stdout. It is not a "print help" default. The adapter must always pass
a subcommand.

**7.10 `composite-layers` resolves relative paths against the SPEC directory.** With
`--spec out\m1\ops\layers\comp.json -o out\m1\ops\layers\comp.mp4` the file was written to
`out\m1\ops\layers\out\m1\ops\layers\comp.mp4` (nested dirs created silently), and
`--save-layer-plan` did the same, ending up three levels deep. Pass absolute paths for `-o` and
`--save-layer-plan`. Other commands (`trim`, `merge`) resolve `-o` against the current directory.

**7.11 Layer sources are sandboxed to the spec directory.** With `src: "../fx/a.mp4"` ->
exit 1, `{"type": "validation_error", "code": "unsafe_layer_source", "message": "layer 'base'
source escapes the spec directory"}`. Copy inputs next to the spec.

## 8. What was actually produced (behaviour, not just exit codes)

| probe | command | result |
|---|---|---|
| trim accuracy | `trim a.mp4 -s 1 -d 3 -o t_def.mp4` | 3.0 s, **72 frames** (24 fps x 3 s), audio kept (141 aac packets) |
| `--accurate` | same + `--accurate` | also 72 frames / 3.0 s - identical for this source |
| crossfade | `merge s1 s2 -t fade -td 1 -o merged` | exit 0, **3.0 s = 2 + 2 - 1**, 72 frames, audio kept (3.01 s). Frames at 0.5/1.5/2.5 s: one bar, **grey 50 %-blended bar**, two bars - the fade is a real alpha blend |
| composite | `composite-layers --spec comp.json` (video + 35 % magenta solid at y=70) | exit 0, 2.0 s / 48 frames; frame at 1.0 s shows the magenta band over the bar; **no audio stream** in the output |
| composite dry-run | `--dry-run --save-layer-plan` | exit 0, `operation: "composite_layers_dry_run"`, no media written |
| QC gate | `release-checkpoint merged_fade.mp4 --min-score 80 --no-require-audio` | exit 1, `quality_gate_failed`: "score 59.0 < 80.0. Video appears desaturated (estimated: 0.0%)" |
| QC receipt | same with `--min-score 50` | exit 0 in 7.0 s; wrote `rc50\thumbnail.jpg` + `rc50\storyboard\frame_01_0.6s.jpg ... frame_04_2.4s.jpg` |

Timing (matters for M3): every CLI invocation pays **~1.3-1.8 s of process start-up** (info: 1.8 s;
trim: 1.7 s wall for 0.27 s of work; merge: 3.5 s; release-checkpoint: 7.0 s). `Client()` in-process
avoids that cost but is excluded by A2. Batch ops are the mitigation (`kino batch`) - not tested yet.

## 9. README claims: CONFIRMED / REFUTED / NOT TESTED

| claim (`docs/REFERENCES.md`) | verdict |
|---|---|
| Apache-2.0 licence | **CONFIRMED** - LICENSE text is Apache 2.0 (sha256 `733474B93E5DF2016FAC0B6DDAF0471850DA64F2ABDB5B45C410C96EC170D837`); pip metadata `License-Expression: Apache-2.0` |
| Python >= 3.11 | **CONFIRMED** - runs on 3.11.9 |
| Core deps mcp/pydantic/rich | **CONFIRMED** - plus starlette/uvicorn/pywin32 (MCP server stack) |
| Requires FFmpeg + ffprobe on PATH | **CONFIRMED** - doctor checks both; 7.1 gyan build on PATH |
| Windows "first-class", `kino doctor` | **CONFIRMED** - doctor exit 0, all required checks OK on Windows 10.0.26200 |
| ~177 CLI commands / 203 MCP tools | **PARTLY** - CLI help lists ~200 subcommands; MCP tool count not measured |
| Workflow engine with receipts, `--resume` | **NOT TESTED** (`workflow-validate` help only) |
| `composite-layers` image/video/solid, opacity, blend, rotation, "video-only" | **CONFIRMED video-only**, opacity/position/solid verified; blend modes and masks NOT TESTED |
| Transitions in merge | **CONFIRMED** - `-t fade -td 1` produced a real 1 s blend |
| Audio normalize/mix/duck | **NOT TESTED** (help confirms the flags) |
| Guardrails: overwrite required, output-aliases-input, preflight | **CONFIRMED for overwrite + missing input + spec sandbox**; the rest NOT TESTED |
| `search_tools` for discovery | **CONFIRMED on the Python Client**, not a CLI command |
| HyperFrames as external pinned CLI | **CONFIRMED absent** - `hyperframes`, `@hyperframes/core`, `npx`, `npm` missing (fine: M9 only) |
| `kinocut[transcribe]` heavy (torch) | **CONFIRMED** - openai-whisper/torch absent, `ai_transcribe` unavailable |

## 10. Capabilities our project needs that Kinocut does NOT provide (first draft)

1. **Fit a clip to an exact frame count.** `trim` is frame-accurate on the cut and `speed` scales
   duration by a factor, but nothing accepts "make this exactly N frames". Our timeline needs it
   (Remotion parity is checked in frames) -> direct FFmpeg op (`-frames:v` / `tpad`).
2. **Audio through compositing.** `composite-layers` output carries no audio stream, so any composite
   must be followed by an audio pass (`mix-audio`) or handled by FFmpeg -> M3 design decision.
3. **Remotion/TSX graphics.** Kinocut bridges HyperFrames and Revideo, not Remotion. Remotion is ours.
4. **Word-level timing from real speech.** `ai_transcribe` unavailable (no whisper); we keep
   faster-whisper / whisper.cpp.
5. **Timeline/EDL as the source of truth.** `otio-export` / `otio-import` / `semantic-timeline` exist
   but were not exercised; our `timeline.json` stays authoritative.
6. **Per-call cost.** ~1.5 s start-up per invocation is significant across a 30-60 op timeline;
   `kino batch` covers only 9 operations.

Open questions for M2 (equivalence tests): do the other transition types keep exact frame counts; does
`merge` re-encode or copy audio; what happens to audio when a `composite-layers` plan includes an
audio layer; are `mix-audio` / `duck-audio` comparable to our FFmpeg chains; does
`release-checkpoint` scoring make sense on real footage (the synthetic bar fixture scored 59 as
"desaturated" - the metric is measuring the test pattern, not a defect).
