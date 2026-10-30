# Sol 738 — Awake Before the Sun

**Module**: `m8_feature` (M8 end-to-end production) · **Length**: ~17.0 s (407 frames @ 24 fps) ·
**Format**: 1920×1080, h264 + AAC · **Source footage**: NASA Perseverance clip
`recapstudio/Projects/regress/footage/real_sample.mp4` (public domain) · **Voice**: edge-tts
`en-US-ChristopherNeural` · **Music**: `recapstudio/Projects/m4job/audio_trim/music_bed_24fps.wav`

This project is the M8 proof: an agent designs the beats (`brief.json`), the tool measures them
against the narration (`blueprint.json`), and the engine executes the compiled `manifest.json`.

## The script (what is actually spoken, in order)

**Beat 1 · 5.46 s · `layered_push`** — layered footage under a subtle camera push.
> Before the sun clears the ridge line, the rover is already awake and listening.

**Beat 2 · 4.79 s · `kinetic_reveal`** — high-impact kinetic typography, no footage.
> Perseverance does not wait for daylight. It makes its own.

**Beat 3 · 6.71 s · `directed_mask`** — a directed shot revealed by an angled mask wipe.
> Sol seven thirty eight. It reads the stone, and writes the dawn of another world.

Total narration: 16.66 s, 39 words. Picture: 407 frames (16.96 s) — the last 0.3 s is tail so the
file does not stop on a vowel.

## Why the frames are these frames

`blueprint generate` synthesised the narration through `tools/narrate.py`, which streams edge-tts's
`WordBoundary` cues. Beat 1 starts at frame 0; beat 2 starts at the first frame of the word
"Perseverance"; beat 3 at "Sol". Nothing was estimated: `blueprint.json` records
`"timing": "word timings"`.

## The step graph (compiled, not hand-written)

| step | op | executor | why |
|---|---|---|---|
| `beat1_render`, `beat2_render`, `beat3_render` | `render_range` | remotion | the motion graphics: the only renderer here that draws |
| `join` | `concat` | kinocut | 2400/2400 frames measured, audio re-encoded per join |
| `voice_over` | `overlay_audio` | ffmpeg | a Remotion render is video-only; `-c:v copy` preserves the frames |
| `duck` | `duck_audio` | kinocut | 16.4 dB of sidechain duck measured (m2_audio) |
| `level` | `normalize_audio` | kinocut | -15.9 LUFS / -9.0 dBTP measured |
| `export` | `export_h264` | kinocut | H.264 High, yuv420p, faststart |

Run it: `python -m cutwright run recapstudio/Projects/m8_feature/manifest.json --json`

## Asset origins (no AI-generated frame anywhere)

| handle | file | origin | licence |
|---|---|---|---|
| `footage_a` | `recapstudio/Projects/regress/footage/real_sample.mp4` | footage | NASA/JPL-Caltech, public domain |
| `voice` | `audio/narration.wav` (+ `.mp3`, `narration.json` timings) | user_audio | synthetic voice (edge-tts), generated for this project |
| `music` | `recapstudio/Projects/m4job/audio_trim/music_bed_24fps.wav` | user_audio | owner-supplied bed, read only |
