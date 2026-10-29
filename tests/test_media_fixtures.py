"""Self-test of the fixtures. Run: python -m unittest tests.test_media_fixtures -v   (repo root)"""
import os
import shutil
import tempfile
import unittest

from tests import media_fixtures as mf


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe not on PATH")
class FixtureTest(unittest.TestCase):
    def test_roundtrip(self):
        d = tempfile.mkdtemp()
        try:
            p = mf.make_counter_clip(os.path.join(d, "c.mp4"), frames=96, fps=24)
            ids = mf.frame_ids(p)
            self.assertEqual(ids, list(range(96)))
            on = mf.beep_onsets(p)
            self.assertEqual(len(on), 4)
            for k, t in enumerate(on):
                self.assertAlmostEqual(t, float(k), delta=0.05)
            frames, vdur, adur = mf.probe_counts(p)
            self.assertEqual(frames, 96)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
