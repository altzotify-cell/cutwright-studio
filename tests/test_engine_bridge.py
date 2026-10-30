"""The Recap -> engine bridge (M4, phase 4A): what it declares, not what it renders.

Run: python -m unittest tests.test_engine_bridge -v      (repo root)

`recapstudio/_template/engine_bridge.py` is the only place Recap Studio calls `cutwright.engine`.
These tests pin the SHAPE of each call (which op, which declared inputs, which params) with the
executor stubbed out; the real media proof is the regression project (LOG 2026-10-30 M4 4A) and the
engine demo, which run Kinocut and ffmpeg for real. Mixing the two kinds of evidence here would
mean a 20 s encode to learn nothing about the bridge.
"""
import importlib
import os
import sys
import unittest
from unittest import mock

from cutwright import guard

ROOT = guard.ROOT


def bridge():
    """The bridge module, imported the way `recap.py` imports it (it sits beside recap.py)."""
    sys.path.insert(0, os.path.join(ROOT, "recapstudio", "_template"))
    return importlib.import_module("engine_bridge")


class BridgeTest(unittest.TestCase):

    def test_it_finds_the_fork_and_the_engine(self):
        b = bridge()
        self.assertEqual(os.path.normcase(b.repo_root()), os.path.normcase(ROOT))
        ok, why = b.available()
        self.assertTrue(ok, why)
        # A copied project (recapstudio/Projects/<job>) resolves the same root: one rule, no cwd.
        copied = os.path.join(ROOT, "recapstudio", "Projects", "m4-probe")
        self.assertEqual(os.path.normcase(b.repo_root(copied)), os.path.normcase(ROOT))

    def test_a_folder_outside_the_fork_has_no_engine(self):
        self.assertIsNone(bridge().repo_root(os.path.join(os.sep, "Windows")))

    def test_concat_picture_declares_the_clip_list(self):
        b = bridge()
        with mock.patch.object(b, "run_op", return_value="ok") as run:
            b.concat_picture([os.path.join("a", "one.mp4"), os.path.join("a", "two.mp4")],
                             os.path.join("a", "join.mp4"))
        op, inputs, output = run.call_args[0]
        self.assertEqual(op, "concat")
        self.assertEqual([os.path.basename(p) for p in inputs["sources"]], ["one.mp4", "two.mp4"])
        self.assertTrue(all(os.path.isabs(p) for p in inputs["sources"]))
        self.assertTrue(os.path.isabs(output))

    def test_mix_tracks_splits_the_file_from_its_settings(self):
        b = bridge()
        with mock.patch.object(b, "run_op", return_value="ok") as run:
            b.mix_tracks("in.mp4", "out.mp4", [{"path": "music.wav", "volume": 0.3}])
        op, inputs, output, params = run.call_args[0]
        self.assertEqual(op, "mix_audio")
        # The FILE is an input (digested -> part of the cache key); the settings are params.
        self.assertEqual([os.path.basename(p) for p in inputs["tracks"]], ["music.wav"])
        self.assertEqual(params["tracks"], [{"volume": 0.3}])
        self.assertTrue(params["keep_source"])

    def test_fit_clip_asks_for_an_exact_frame_count(self):
        b = bridge()
        with mock.patch.object(b, "run_op", return_value="ok") as run:
            b.fit_clip("in.mp4", "out.mp4", frames=48, fps=24, width=1920, height=1080)
        op, inputs, output, params = run.call_args[0]
        self.assertEqual(op, "fit_to_frames")
        self.assertEqual(params["frames"], 48)
        self.assertEqual((params["width"], params["height"]), (1920, 1080))
        self.assertEqual(os.path.basename(inputs["src"]), "in.mp4")


if __name__ == "__main__":
    unittest.main()
