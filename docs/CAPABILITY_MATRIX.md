# Capability matrix (M2 equivalence verification)

Measured 2026-10-29 on the owner's Windows PC: Python 3.11.9, ffmpeg 7.1-full_build (gyan),
Kinocut 1.16.4 in `.venvs\kinocut`. Every row below was produced by a test that ran the
candidates on synthetic media with the frame number burned in as blocks and beeps on whole
seconds. Raw numbers: `docs/evidence/m2_*.json`. Tests: `tests/kinocut_vs_current/test_*.py`
(`python -m unittest discover -s tests -t . -v`). No production code was changed in M2.

## Legend

| verdict | meaning |
|---|---|
| **PASS** | every criterion stated in `docs/ROADMAP.md` met, measured on the produced file |
| **LIMITATION** | works, but at least one criterion missed (miss quoted) |
| **FAIL** | does not do the job |
| **NOT TESTED** | not attempted, reason given |

`executor` is what M3 should call: `kinocut`, `ffmpeg` (a named typed op), `current` (keep the
existing recap helper), `hybrid` (two passes), `none` (we have no op for it yet).

## Headline decisions

| # | operation | executor | reason (measured) |
|---|---|---|---|
| 1 | frame-exact trim | **kinocut** | `trim` returned exact ids for starts 0/1/37/119; the current `render_video_clip` is one frame late on every non-zero start |
| 2 | fit a clip to exactly N frames | **ffmpeg** | Kinocut has no "N frames" parameter (`speed` is a no-op on this input: 120 -> 120/119); `-frames:v` + `tpad` is exact |
| 3 | fit a still to N frames | **current** | `render_image_clip` exact at 53/97; Kinocut has no image->clip op |
| 4 | 16:9 -> 9:16 reframe | **kinocut** (pad/blur) + **ffmpeg** (crop) | `resize -a 9:16` letterboxes correctly; the current `fit_graph` has no crop branch |
| 5 | many-clip concat (same format) | **kinocut** | 2400/2400 frames, no missing frame; mixed formats need an ffmpeg normalise pass first |
| 6 | crossfade / wipe | **kinocut** | 228/228 frames, real 12-frame blend ramp, no audio gap or click; no current implementation |
| 7 | sidechain ducking | **kinocut** | `duck-audio` gave 16.4 dB of duck; the current `amix` gives 0.2 dB |
| 8 | audio mix / loudness | **kinocut** | `mix-audio` + `normalize-audio` hit -15.9 LUFS / -9.0 dBTP with exact onsets |
| 9 | overlay / compositing | **kinocut + separate audio pass** (hybrid) | `composite-layers` is video-only (audio dropped); timing window and alpha are correct |
| 10 | burned-in subtitles | **kinocut** | non-ASCII SRT burned on exactly the cue frames, no leakage before/after |
| 11 | final export | **kinocut** | H.264 High / yuv420p / AAC 48 kHz stereo / faststart / clean decode in 54 s for 60 s 1080p24 |
| 12 | QC gate | **hybrid** | `release-checkpoint` scores a release; per-frame black/silence/clip detection is ffmpeg's job |
| 13 | workflow / resume | see below | receipts + fail-closed resume verified; workspace paths must be relative |


## 1. Frame accuracy - trim (`test_trim.py`, `m2_trim.json`)

Fixture: 240-frame 24 fps counter clip (160x90, beeps each second). Start frames 0, 1, 37,
119; lengths 1, 50, 120. Readback compares the decoded frame numbers to `range(start, start+len)`.

| candidate | frame count | frame ids | wall | notes |
|---|---|---|---|---|
| Kinocut `trim -s -d -o` | exact (1/50/120/50) | **exact at all four starts** (`[37,38,39]` at start 37) | 2.09-3.48 s | `--accurate` measured identical to the default here |
| current `render_video_clip` (recap.py:2460) | exact | **off by one at every non-zero start** (`-ss` before `-i`): start 1 -> `[2,3,4]`, start 37 -> `[38,39,40]`, start 119 -> head right, tail duplicated | 0.68-1.22 s | video-only by design (`-an`) |
| direct ffmpeg (`-i` then `-ss`, `-frames:v`) | exact | **exact at all four starts** | 0.64-0.94 s | output seek = frame accurate |

Verdict: Kinocut **PASS**, ffmpeg **PASS**, current **LIMITATION** (`-ss` before `-i`).
Executor: **kinocut** (also gives the guardrails: refuses an existing output, sandboxed paths).
M4 must fix `render_video_clip`'s seek even if it keeps the helper - a one-frame slip at every
clip start is exactly the class of bug M2 exists to find.

## 2. Clip fitting to N frames (`test_fit.py`, `m2_fit.json`, `m2_fit_still.json`)

Targets 53 / 97 / 241 frames at 1920x1080 / 24 fps / yuv420p from a 120-frame source.

| candidate | 53 | 97 | 241 | format |
|---|---|---|---|---|
| Kinocut `speed -f 120/N` | 120 | 119 | 120 | **no effect** - `speed` did not change the frame count on this source |
| Kinocut `trim -d N/24` | 53 | 97 | 120 | exact while the source lasts, then truncates (no clone, no pad) |
| current `render_video_clip` pad / blur | 53 | 97 | 241 | 1920x1080, yuv420p, 24 fps, ids monotonic, no black first/last frame |
| direct ffmpeg (`fit_graph` + `fps` + `tpad=clone` + `-frames:v`) | 53 | 97 | 241 | same |

Still image (PNG -> 53 / 97 frames): current `render_image_clip` (recap.py:2474) exact; direct
ffmpeg `-loop 1 -frames:v` exact; Kinocut has no image->video op (`still_plates` unavailable,
pillow not installed).

Verdict: no Kinocut op accepts "exactly N frames" - **LIMITATION**, as predicted in
`docs/KINOCUT_FINDINGS.md` section 10. Executor: **ffmpeg** (`fit_to_frames`, `tpad` clone),
**current** for stills.

## 3. Reframing 16:9 -> 9:16 (`test_resize.py`, `m2_resize.json`, `m2_resize_nonsquare.json`)

Flat red 160x90 source; "content box" = the region that is not black, in output pixels.

| candidate | size | content box | aspect |
|---|---|---|---|
| current `fit_graph` fill="pad" | 1080x1920 | 1080x600, centred | 1.80 - no stretch |
| current `fit_graph` fill="blur" | 1080x1920 | fills 1080x1920 | blurred background |
| current `fit_graph` fill="crop" | 1080x1920 | **1080x600 - identical to pad** | **no crop branch exists**, the call silently letterboxes |
| direct ffmpeg `scale=increase,crop` | 1080x1920 | fills 1080x1920 | true centre crop |
| Kinocut `resize -w 1080 --height 1920 -a 9:16` | 1080x1920 | 1080x600, vertically centred | letterbox (pad) - no crop option |

Anamorphic source (SAR 2:1, displays 32:9): all three letterbox as if it were 16:9
(content height 600 instead of the correct 304) - **all three ignore the SAR**, so anamorphic
footage needs an explicit `setsar=1`/display-aspect step in M3.

Verdict: **kinocut** for pad/blur, **ffmpeg** for crop. **LIMITATION**: crop is missing from the
current code and from Kinocut's resize; non-square pixels are unhandled everywhere.


## 4. Concat (`test_concat.py`, `m2_concat.json`, `m2_concat_mixed.json`, `m2_concat_pcm.json`)

20 clips x 120 frames, contiguous ids 0..2399, joined in order.

| candidate | frames | missing / duplicated | audio drift over 20 clips | wall |
|---|---|---|---|---|
| Kinocut `merge a1..a20 -o` | 2400 | 0 missing, 1 duplicate (frame 0) | **0.4933 s** (~26 ms per join) | 7.92 s |
| current `join_av` (concat demuxer, `-c:v copy`) | 2400 | 0 missing, 1 duplicate (frame 0) | 0.2747 s (~14 ms per join) | 3.00 s |
| direct ffmpeg (demuxer + scale/fps re-encode) | **2399** | 1 missing (frame 2399) | 0.2747 s | 5.43 s |

Same join with **PCM** audio instead of AAC (5 clips, 4 joins): 0.0534 s total for BOTH kinocut
and ffmpeg, i.e. **13.4 ms per join** - so roughly half of the AAC drift is per-clip AAC priming
and half remains with PCM. `within_42ms_budget: false` for both.

Mixed fps/resolution inputs (48 frames @24 fps 160x90 + 60 frames @30 fps 320x180):

| candidate | result |
|---|---|
| Kinocut `merge` | exit 0, 119 frames, and it *warns*: `[MERGE GUARDRAIL] Clips have different frame rates: [24.0, 30.0]. Output may stutter or drop frames` |
| current `join_av` | exit 0, **82 frames - silently wrong**, no warning at all |
| direct ffmpeg (one scale/fps/sar grid per input, then `concat`) | 93 frames vs 95 expected - the fps filter still sheds frames |

Verdict: Kinocut **PASS** on frames for same-format joins and **is honest** about mixed inputs;
the current code is the dangerous one (broken timeline, no warning).
**LIMITATION (all three)**: audio offset accumulates at every join - 14-26 ms per join means a
20-clip 100 s sequence drifts 0.27-0.49 s, ten times the 42 ms budget. M3 must build audio as ONE
continuous track (or re-time it after the join) and never trust per-clip offsets across a merge.
Executor: **kinocut** for the join + a separate audio assembly pass.

## 5. Transitions (`test_transition.py`, `m2_transition.json`)

12-frame (0.5 s) crossfade between a 120-frame and a 120-frame clip; expected 228 frames
(120 + 120 - 12). Structure checks use the counter clips; blend/audio checks use a white -> black
pair carrying a continuous 300 Hz tone.

| candidate | frames | head / tail ids | overlap | audio |
|---|---|---|---|---|
| Kinocut `merge -t fade -td 0.5` | **228/228** | intact | linear ramp 255 -> 21 luma (-21 per frame over 12 frames) | no gap > 10 ms; step at the join -46.3 dB vs -42.9 dB elsewhere (no click) |
| Kinocut `merge -t wipe-left -td 0.5` | 228/228 | intact | wipe, same frame maths | clean |
| direct ffmpeg `xfade` + `acrossfade` | 228/228 | intact | same linear ramp | clean |
| current codebase | - | - | **no implementation** (`join_av` = hard cut; Remotion does picture effects only) | - |

Verdict: Kinocut **PASS** (fade and wipe). Executor: **kinocut**. The first overlap frame equals
the outgoing level and the last equals the incoming one, so a 12-frame fade consumes exactly
12 frames of each clip - the frame maths in the roadmap holds.

## 6. Overlay / compositing (`test_composite.py`, `m2_composite.json`, `m2_composite_pip.json`)

48-frame base clip; a 50 %-alpha magenta PNG placed at (50, 30) for frames [12, 24). Measured by
the mean luma inside that box on the four frames the roadmap names.

| candidate | frame 11 | frame 12 | frame 23 | frame 24 | base audio |
|---|---|---|---|---|---|
| Kinocut `composite-layers --spec` | 0.00 | 33.67 | 33.57 | 0.03 (off) | **dropped - output is video-only** |
| direct ffmpeg `overlay=...:enable='between(t,...)'` | 0.00 | 41.56 | 41.56 | 0.00 (off) | **preserved** |
| current codebase | - | - | - | - | drawn by Remotion at render time (`Overlays.tsx`) |

Kinocut's window is **exact** (on for frames 12-23, off at 24) and the alpha is honoured (the
magenta sits at 33.6 luma over a black region, i.e. blended, not pasted). The luma difference
between 33.6 and 41.6 is the 0.8 opacity in the spec versus 1.0 in the ffmpeg pass.

`overlay-video` (picture-in-picture) **keeps the background audio** (`has_audio: true`) - so the
audio loss is specific to `composite-layers`, as `docs/KINOCUT_FINDINGS.md` 5 recorded.
Executor: **kinocut + a separate audio pass (hybrid)** for `composite-layers`, or `overlay-video`
when PiP is enough.

## 7. Audio: mix, duck, normalise (`test_audio.py`, `m2_audio.json`)

Fixture: 6 s of five 1 kHz voice bursts (0.3 s each at 0.5/1.5/2.5/3.5/4.5 s) plus a separate
100 Hz music bed. The two are separated after the fact by band-pass filtering (60-140 Hz = music,
880-1120 Hz = voice), so "music under the voice" is measured on the real output.

| candidate | duck (outside - during) | integrated | true peak | voice onset error |
|---|---|---|---|---|
| Kinocut `duck-audio` (defaults) | **16.36 dB** | -12.1 LUFS | -3.2 dBTP | 0.3 ms |
| Kinocut `duck-audio` (tuned params) | 16.07 dB | -10.9 LUFS | -4.0 dBTP | 0.3 ms |
| Kinocut `mix-audio` (no duck, control) | 0.04 dB | -10.1 LUFS | -5.5 dBTP | 0.6 ms |
| Kinocut `normalize-audio -l -16 --true-peak-dbtp -1.5` | duck kept (16.08) | **-15.9 LUFS** | -9.0 dBTP | 0.6 ms |
| current `join_av` (`amix`, recap.py:4068) | **0.22 dB - no ducking** | -10.5 LUFS | **-0.3 dBTP (near clipping)** | **21.6 ms late** |
| direct ffmpeg `sidechaincompress` | 13.94 dB | -10.6 LUFS | -4.0 dBTP | 0.3 ms |
| direct ffmpeg `loudnorm` (separate pass) | duck kept | **-15.3 LUFS** | -7.8 dBTP | 0.6 ms |

Criteria: duck >= 8 dB **PASS** (kinocut, ffmpeg); -16 LUFS +/- 1.5 **PASS** (both);
true peak <= -1 dBTP **PASS**; onset error <= 20 ms **PASS** for kinocut/ffmpeg, **FAIL 21.6 ms**
for the current amix path; no clipping **FAIL -0.3 dBTP** for the current path.

Two things the measurement itself taught us (both in `m2_audio.json`):
- `--sounds` takes **JSON track descriptions**, not a path:
  `--sounds "[{\"path\": \"music.wav\", \"volume\": 0.35}]"`. A bare path is rejected with
  `invalid_parameter: sounds must be valid UTF-8 JSON track descriptions`.
- Loudness normalisation must be measured on its own pass: `loudnorm` is dynamic, so running it
  inside the duck graph flattens the duck (this produced a misleading 1 dB reading until the
  passes were separated - the M1 "audio not tested" question is now answered properly).

Executor: **kinocut** (`duck-audio`, `mix-audio`, `normalize-audio`); replace the `join_av` amix
path in M4.



## 8. Burned-in subtitles (`test_burn.py`, `m2_burn.json`)

Black 320x180 / 3 s clip, a 2-cue UTF-8 SRT (an accented Latin line, then a Japanese line) written
into a directory with a non-ASCII name, cues at 0.5-1.5 s and 1.5-2.5 s. "Bright pixels per frame"
is the measurement; the clip is otherwise black.

| candidate | frame 6 (before) | frame 24 (cue 1) | frame 42 (cue 2) | frame 66 (after) |
|---|---|---|---|---|
| Kinocut `subtitles clip subs.srt -o` | 0 | **372** | **239** | 0 |
| direct ffmpeg `subtitles=subs.srt` | 0 | 203 | 146 | 0 |
| current codebase | - | - | - | writes `.srt` for the player (`step_srt`); captions are a Remotion job |

Both burn exactly on the cue frames, no leakage before/after, no encoding error on the non-ASCII
Windows path. Verdict: Kinocut **PASS**. Executor: **kinocut**. Our karaoke-style captions stay in
Remotion (`src/captions/Captions.tsx`); this row covers plain SRT burn-ins only.

## 9. Final export (`test_export.py`, `m2_export.json`)

60 s, 1920x1080, 24 fps, AAC 48 kHz stereo source.

| candidate | wall | size | video | audio | faststart | decode |
|---|---|---|---|---|---|---|
| Kinocut `export -q high -f mp4` | **54.09 s** | 0.40 MB | H.264 **High**, yuv420p, 1920x1080 | AAC 48000 Hz, 2 ch | yes (moov before mdat) | clean (`-v error` silent) |
| current `join_av` (copy + AAC) | 1.66 s | 0.41 MB | H.264 High, yuv420p | AAC 48000 Hz, 2 ch | yes | clean |
| direct ffmpeg `-preset veryfast -profile:v high -movflags +faststart` | 29.79 s | 0.42 MB | H.264 High, yuv420p, 24/1 | AAC 48000 Hz, 2 ch | yes | clean |

All three meet the export criteria. The source's `avg_frame_rate` is 479/20 (23.95) because it was
built with `-stream_loop`; Kinocut and the current copy preserve that, the ffmpeg reference forces
`-r 24` and reports 24/1. `-benchmark` reported no `maxrss` on this build (field empty).
Executor: **kinocut** when the export must also carry the release gate; **ffmpeg** when only speed
matters (1.8x faster here); the current copy path is fastest because it re-muxes instead of
encoding, which is valid only when the picture is already final.

## 10. QC gates (`test_qc.py`, `m2_qc.json`)

Fixture: 4 s 640x360 with a black flash at 1.0 s, a silence gap at 2.0-2.5 s and a clipped
window at 3.0-3.2 s.

| candidate | black flash | silence gap | clipping | other |
|---|---|---|---|---|
| Kinocut `video-quality-check` | **not detected** | **not detected** | **detected** (`Audio is clipping (-0.2 dBTP)`) | 6 global checks, score 35.9, `all_passed: false`; also flags low contrast / colour cast / low motion |
| Kinocut `release-checkpoint --min-score` | - | - | - | score gate + storyboard + thumbnail (exit 1 when the score is under the minimum) |
| `cutwright/frames.py` `luma_at` | **detected** (`0.00` at the flash vs `82` on a clean frame) | no detector exists | no detector exists | - |
| direct ffmpeg `blackdetect` + `silencedetect` + `volumedetect` | **detected** `1.0-1.125` | **detected** at `2.0` | **detected** `max_volume -0.2 dB` | - |

Verdict: Kinocut's QC is a **global score**, not a per-frame integrity check - it cannot see a
one-frame black flash or a half-second dropout. Executor: **hybrid** - `release-checkpoint` as the
release gate, ffmpeg `blackdetect`/`silencedetect`/`volumedetect` (or our `frames.py`) for

## 11. Reliability (`test_reliability.py`, `m2_reliability_*.json`)

| check | result |
|---|---|
| 10 x `trim` | 10/10 exit 0, always 48 frames, 1.62-3.03 s per call |
| 10 x `resize` | 10/10 exit 0, always 120 frames, 2.11-4.59 s |
| 10 x `merge` | 10/10 exit 0, always 96 frames, 2.23-6.27 s |
| output dir the user cannot write (`icacls /deny W`) | exit 1, structured `{"type": "validation_error", "code": "unsafe_path", "message": "Atomic output could not preserve directory identity: PermissionError"}`, **no file written** |
| killed 1.2 s into a trim | process tree terminated, exit 1, **zero leftover files** in the output directory, no usable output |

Verdict: **PASS**. No flakes, clean structured errors, no orphaned temp files. Per-call wall time
is dominated by the ~1.3-1.8 s process start-up (M1), which is why M3 must batch where possible.

## 12. Workflow engine and resume (`test_workflow.py`, `m2_workflow.json`)

Spec: `trim -> resize -> trim -> merge` (4 steps) written as a Kinocut job spec.

| check | result |
|---|---|
| `workflow-validate --spec` | exit 0 |
| `workflow-render --spec --save-receipt --keep-intermediates` | exit 0, output written (60 frames), intermediates under `work/<uuid>/mcp_video_*.mp4` |
| receipt contents | keys `spec_hash, sources, steps, outputs, work_dir, status, warnings, resume_cursor, cleanup_manifest, feature_flags, receipt_kind, render_determinism_scope, schema_version, tool, versions, workflow`; the **output's sha256 is present** |
| delete one intermediate, `--resume receipt.json` | exit 0, the deleted step **was rebuilt**, final output present |
| edit the spec, `--resume` the old receipt | **exit 1, refused**: `resume_spec_mismatch` - "resume receipt spec_hash 'sha256:6b73...' does not match the current spec_hash 'sha256:a5ca...'; this is a different job" |

Contract facts M3 must implement (all measured, none documented):
- sources must be **relative paths inside the spec's workspace**; absolute input paths are rejected
  with `unsafe_workflow_source`.
- references are `@sources.<id>`, `@work/<file>`, `@outputs.<id>`; a step is
  `{"id", "op", "inputs": {"src"|"srcs"}, "params", "output"}`; `params` are validated against the
  engine signature, so the CLI flag names do **not** carry over (`start`/`duration`, not `-s`/`-d`).
- `--resume` is fail-closed on any spec change: a changed job is a different job, by design.

Verdict: **PASS** - receipts, resume-after-loss and fail-closed spec changes all behave.

## What is still a gap (carried into M3/M4, with the evidence above)

1. **No Kinocut op takes "exactly N frames"** (`test_fit`). Speed/trim can't do it -> typed FFmpeg op.
2. **`composite-layers` drops audio** (`m2_composite.json`, `has_audio: false`) -> always follow
   with an audio pass.
3. **Per-join audio drift** 13.4 ms (PCM) / 26 ms (AAC) -> build one continuous audio track;
   never trust per-clip offsets across a merge.
4. **QC is global, not per-frame** -> keep ffmpeg detectors / `frames.py` for black, silence, clip.
5. **Mixed fps/resolution inputs**: the current `join_av` produced 82 frames silently (`test_concat`).
   Kinocut at least warns. Both need an explicit normalise step.
6. **No crop fill and no SAR handling** anywhere (`test_resize`, `m2_resize_nonsquare.json`).
7. **Current `render_video_clip` off-by-one seek** and **`join_av` 21.6 ms voice delay + no ducking**
   (`test_trim`, `test_audio`) - both are M4 targets.
8. **Not tested in M2**: HDR/10-bit sources, non-24 fps timelines, `kino batch`, the MCP surface,
   Remotion-rendered overlay clips in `composite-layers`, blend modes/masks.

## Reproduce

```powershell
python -m unittest discover -s tests -t . -v              # ~11 min: 21 tests incl. M2
Get-ChildItem docs\evidence\m2_*.json | Measure-Object    # 20 evidence files
```

Fixtures and outputs are written under `out/m2/` (gitignored); only
`docs/evidence/m2_*.json` and `docs/CAPABILITY_MATRIX.md` are meant to be kept.

per-frame defects.
