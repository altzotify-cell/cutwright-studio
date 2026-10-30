"""mix_audio's track FILES are declared inputs (M4, phase 4A; fixes COMMS C-007 finding 3).

Run: python -m unittest tests.test_engine_mix_inputs -v      (repo root)

The defect this pins: a track named only in `params` is not part of a step's cache key, so
replacing `music.wav` left the mix marked "cached (cache key unchanged)" and the new music was
never heard. The fix moves the FILE into the op's inputs and keeps only the settings in params.

Three layers, no media rendered by the engine:
  * `TrackContractTest` - the op declares the input, pairs file<->settings, refuses a mismatch;
  * `CacheKeyTest`      - replacing a track changes the step's cache key, restoring it restores
                          the key (content identity, not just a new mtime);
  * `PlanTest`          - a count mismatch is refused while the plan is still data.
"""
import json
import os
import unittest

from cutwright import guard
from cutwright.engine import checkpoint, manifest, ops
from tests import media_fixtures as mf

WORK = os.path.join(guard.OUT, "engine_mix")      # inside the fork: the guard allows it
FPS = 24


def out(*parts):
    return os.path.join(WORK, *parts)


def source():
    """The mix's `src`: real 24-frame media, encoded once per run (cheap, no audio)."""
    guard.ensure_dir(WORK)
    path = out("src.mp4")
    if not os.path.isfile(path):
        mf.make_counter_clip(path, frames=24, fps=FPS, with_audio=False)
    return path


def bed(name="bed.wav", seconds=1.0):
    """A code-made audio track (1 kHz bursts), so the digest has real content to change."""
    guard.ensure_dir(WORK)
    return mf.make_beep_bed(out(name), seconds)


def mix_step(target="out/engine_mix/mix.mp4", tracks=None, settings=None):
    return {"id": "mix", "op": "mix_audio",
            "inputs": {"src": "@asset.src", "tracks": tracks or [bed()]},
            "params": {"tracks": settings if settings is not None else [{"volume": 0.35}],
                       "keep_source": True},
            "outputs": {"video": target}}


def plan_of(steps, assets=None, **extra):
    """A manifest that validates unless the test breaks exactly one thing."""
    data = {"schema": 1, "run_id": extra.pop("run_id", "mix-0001"), "fps": FPS,
            "size": [160, 90], "budget": {"mode": "cap", "cap_usd": 0.0},
            "constraints": {"ai_generated_images": False},
            "assets": assets if assets is not None else [
                {"id": "src", "path": guard.rel(source()), "origin": "footage",
                 "license": "code-made"}],
            "gates": [], "steps": steps}
    data.update(extra)
    return data


class TrackContractTest(unittest.TestCase):
    """What the op declares and how the file is paired with its settings."""

    def test_the_track_file_is_a_declared_input(self):
        spec = ops.get("mix_audio")
        self.assertEqual(tuple(spec.inputs), ("src", "tracks"))
        # Positional inputs are what `manifest._call` passes as arguments: the file goes in as the
        # `tracks` KEYWORD, built from inputs + params, never as a positional slot.
        self.assertEqual(ops.positional_inputs(spec), ["src"])
        self.assertEqual(ops.positional_inputs(ops.get("concat")), ["sources"])

    def test_files_and_settings_are_paired_in_order(self):
        spec = ops.get("mix_audio")
        params = {"tracks": [{"volume": 0.35}, {"volume": 0.1, "start": 2.0}]}
        inputs = {"src": "s.mp4", "tracks": ["a.wav", "b.wav"]}
        kwargs = ops.executor_kwargs(spec, params, fps=FPS, inputs=inputs)
        self.assertEqual(kwargs["tracks"],
                         [{"path": "a.wav", "volume": 0.35},
                          {"path": "b.wav", "volume": 0.1, "start": 2.0}])

    def test_a_count_mismatch_is_refused(self):
        spec = ops.get("mix_audio")
        with self.assertRaises(ops.OpError) as ctx:
            ops.mix_tracks(spec, {"tracks": [{"volume": 0.3}]},
                           {"tracks": ["a.wav", "b.wav"]})
        self.assertEqual(ctx.exception.code, "invalid_combination")
        self.assertEqual(ctx.exception.param, "tracks")
        self.assertIn("2 track file(s)", ctx.exception.message)

    def test_a_single_track_may_be_declared_as_a_bare_path(self):
        spec = ops.get("mix_audio")
        tracks = ops.mix_tracks(spec, {"tracks": [{"volume": 0.2}]}, {"tracks": "a.wav"})
        self.assertEqual(tracks, [{"path": "a.wav", "volume": 0.2}])


class CacheKeyTest(unittest.TestCase):
    """The resume decision: replacing a track must invalidate the mix."""

    def test_replacing_a_track_changes_the_cache_key(self):
        path = bed("swap.wav", 1.0)
        plan = manifest.derive(plan_of([mix_step(tracks=[path])]), strict_files=False)
        step = plan.step("mix")
        self.assertEqual([os.path.basename(p) for p in step.inputs["tracks"]], ["swap.wav"])
        names = [row["name"] for row in checkpoint.input_digests(step.inputs)]
        self.assertIn("tracks", names)                      # digested at all is the whole point
        before = manifest.step_key(step)

        mf.make_beep_bed(path, 2.0)                         # a DIFFERENT track, same filename
        changed = manifest.step_key(step)
        self.assertNotEqual(before, changed,
                            "replacing the track file must invalidate the step")

        mf.make_beep_bed(path, 1.0)                         # put the first one back
        self.assertEqual(before, manifest.step_key(step),
                         "identical content must give the identical key (sha256, not mtime)")


class PlanTest(unittest.TestCase):
    """A plan is data: the pairing is checked before anything renders."""

    def test_a_mismatch_is_reported_with_the_step(self):
        report = manifest.validate(plan_of([mix_step(tracks=[bed(), bed("bed2.wav", 1.0)],
                                                      settings=[{"volume": 0.3}])]),
                                  strict_files=False)
        self.assertFalse(report["ok"])
        codes = [row["code"] for row in report["errors"]]
        self.assertIn("invalid_combination", codes)
        self.assertIn("mix", [row["step"] for row in report["errors"]])

    def test_a_well_formed_mix_plan_validates(self):
        report = manifest.validate(plan_of([mix_step()]), strict_files=False)
        self.assertTrue(report["ok"], json.dumps(report["errors"], indent=2))
        self.assertEqual(report["steps"], 1)


if __name__ == "__main__":
    unittest.main()
