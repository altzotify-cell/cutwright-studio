"""Build the M3 acceptance demo: fixtures, a five-step manifest, and nothing else.

    python -m tests.engine_demo

Writes only inside the fork:
  out/fx/a.mp4, out/fx/b.mp4   160x90 24 fps counter clips (frame N is drawn as N), with beeps
  out/fx/music.wav             a 3 s 220 Hz bed at -16 dB, to mix under the cut
  out/fx/demo_manifest.json    trim -> fit -> concat -> mix -> export, with one gate

The manifest is what `python -m cutwright run out\\fx\\demo_manifest.json` executes
(`docs/ROADMAP.md` M3 acceptance). It lives in the repo so the demo is rebuilt rather than
remembered; `out/` itself stays gitignored, so nothing here is an artifact in git.

The gate `final_ok` before `export` is deliberate: one run shows the run stopping at a closed
gate, `approve` opening it, and the next run skipping the four finished steps from cache.
"""
import os

from cutwright import guard
from cutwright.engine import manifest
from tests import media_fixtures as mf

FX = os.path.join(guard.OUT, "fx")
WORK = "out/runs/demo"


def _bed(path, seconds=3.0):
    """A 1 kHz burst bed from the fixtures: 50 ms at every whole second.

    Measurable on purpose: `media_fixtures.beep_onsets` can then say WHERE the music sits inside the
    final file, so a mix that shifts the bed is caught by a number rather than an ear. Code-made
    audio (no external asset, no AI).
    """
    return mf.make_beep_bed(path, seconds)


def fixtures(frames_a=120, frames_b=36):
    """(re)write every fixture. Counter clips keep frame ids readable after any edit.

    `b.mp4` is deliberately SILENT: `fit_to_frames` is video-only (`-an`, matrix row 2), and a
    concat of one silent and one audio clip makes `kino merge` re-time the whole output to 30 fps /
    44.1 kHz (measured 2026-10-30, 75 frames instead of 60). Picture first, one continuous audio
    track after (M2 gap 3, COMMS C-005), which is exactly what the `mix` step does.
    """
    guard.ensure_dir(FX)
    a = mf.make_counter_clip(os.path.join(FX, "a.mp4"), frames=frames_a, fps=24)
    b = mf.make_counter_clip(os.path.join(FX, "b.mp4"), frames=frames_b, fps=24, id_offset=1000,
                             with_audio=False)
    music = _bed(os.path.join(FX, "music.wav"))
    return {"a": a, "b": b, "music": music, "frames_b": frames_b}


def document(frames_b=36):
    """The five-step plan: cut 48 frames, fit to 24, join b, mix a bed, export."""
    joined = 24 + frames_b
    music = manifest.resolve_path("out/fx/music.wav")
    return {
        "schema": 1, "run_id": "demo", "pipeline": "recap", "fps": 24, "size": [160, 90],
        "budget": {"mode": "cap", "cap_usd": 0.0},
        "constraints": {"ai_generated_images": False,
                        "allowed_asset_origins": ["footage", "user_image", "code_graphic",
                                                  "stock_licensed"]},
        "assets": [
            {"id": "src_a", "path": "out/fx/a.mp4", "origin": "footage", "license": "code-made"},
            {"id": "src_b", "path": "out/fx/b.mp4", "origin": "footage", "license": "code-made"},
            {"id": "music", "path": "out/fx/music.wav", "origin": "user_audio",
             "license": "code-made"},
        ],
        "gates": [{"id": "final_ok", "before_step": "export", "approved": False}],
        "steps": [
            {"id": "cut", "op": "trim_exact", "inputs": {"src": "@asset.src_a"},
             "params": {"start_frame": 24, "frames": 48},
             "outputs": {"video": WORK + "/cut.mp4"},
             "validation": [{"check": "frame_count", "expect": 48},
                            {"check": "decodes_clean"}]},
            {"id": "fit", "op": "fit_to_frames", "inputs": {"src": "@cut.video"},
             "params": {"frames": 24, "fps": 24, "width": 160, "height": 90},
             "outputs": {"video": WORK + "/fit.mp4"},
             "validation": [{"check": "frame_count", "expect": 24},
                            {"check": "size", "expect": [160, 90]}]},
            {"id": "join", "op": "concat",
             "inputs": {"sources": ["@fit.video", "@asset.src_b"]},
             "outputs": {"video": WORK + "/join.mp4"},
             "validation": [{"check": "frame_count", "expect": joined},
                            {"check": "constant_fps", "expect": 24}]},
            {"id": "mix", "op": "mix_audio", "inputs": {"src": "@join.video"},
             "params": {"tracks": [{"path": music, "volume": 0.35}], "keep_source": True},
             "outputs": {"video": WORK + "/mix.mp4"},
             "validation": [{"check": "decodes_clean"}, {"check": "has_audio"}]},
            {"id": "export", "op": "export_h264", "inputs": {"src": "@mix.video"},
             "params": {"quality": "high", "container": "mp4"},
             "outputs": {"video": WORK + "/final.mp4"},
             "validation": [{"check": "decodes_clean"},
                            {"check": "frame_count", "expect": joined},
                            {"check": "constant_fps", "expect": 24}]},
        ],
        "note": "Built by tests/engine_demo.py. The mix track is absolute because Kinocut opens it "
                "itself, outside this process' working directory.",
    }


def main():
    built = fixtures()
    path = guard.write_json(os.path.join(FX, "demo_manifest.json"),
                            document(frames_b=built["frames_b"]))
    print("wrote %s (%d frames of b, joined length %d)"
          % (guard.rel(path), built["frames_b"], 24 + built["frames_b"]))


if __name__ == "__main__":
    main()
