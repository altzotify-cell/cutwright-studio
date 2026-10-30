"""Post-render media validation, slideshow_risk and asset provenance (M3, phase 3D).

Run: python -m unittest tests.test_engine_validate -v      (repo root)

Every check runs on a REAL file: the counter fixtures say how many frames they hold and which frame
is which, so a passing check can be proved to have looked at the right thing. A check that "passes"
on a missing file, or one that stays silent on a truncated render, would be worse than no check.
"""
import os
import subprocess
import unittest

from cutwright import guard
from cutwright.engine import validate
from tests import media_fixtures as mf

WORK = os.path.join(guard.OUT, "engine_validate")
FPS = 24


def out(*parts):
    return os.path.join(WORK, *parts)


def clip(frames=48, audio=False, name=None):
    """A counter clip: frame N is drawn as N, so a frame count can be checked by reading it back."""
    path = out(name or "c%d%s.mp4" % (frames, "_a" if audio else ""))
    guard.ensure_dir(WORK)
    if not os.path.isfile(path):
        mf.make_counter_clip(path, frames=frames, fps=FPS, with_audio=audio)
    return path


def still(frames=24):
    """One grey frame cloned: the definition of a slideshow."""
    path = out("still.mp4")
    guard.ensure_dir(WORK)
    if not os.path.isfile(path):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                        "-i", "color=c=gray:s=160x90:r=%d" % FPS, "-frames:v", str(frames),
                        "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", path],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return path


def truncated():
    """Half an mp4: the moov atom is gone, so a full decode cannot succeed."""
    path = out("broken.mp4")
    if not os.path.isfile(path):
        with open(clip(), "rb") as handle:
            data = handle.read()
        with open(path, "wb") as handle:
            handle.write(data[:len(data) // 2])
    return path


class Fake:
    """The only two attributes `run_checks` needs from a manifest.Step (duck-typed on purpose)."""

    class Spec:
        outputs = ("video",)

    def __init__(self, target, checks):
        self.outputs = {"video": target}
        self.spec = Fake.Spec()
        self.validation = checks


def rows(target, *checks):
    return validate.run_checks(Fake(target, list(checks)))


class CheckTest(unittest.TestCase):
    """Each check, on real media, once passing and once failing."""

    def test_frame_count_measures_a_real_decode(self):
        row = rows(clip(48), {"check": "frame_count", "expect": 48})[0]
        self.assertEqual(row["status"], "pass", row)
        self.assertEqual(row["measured"], 48)

    def test_a_wrong_frame_count_fails_and_says_both_numbers(self):
        row = rows(clip(48), {"check": "frame_count", "expect": 50})[0]
        self.assertEqual(row["status"], "fail")
        self.assertIn("expected 50", row["message"])
        self.assertIn("decoded 48", row["message"])

    def test_size_is_measured_not_assumed(self):
        self.assertEqual(rows(clip(48), {"check": "size", "expect": [160, 90]})[0]["status"],
                         "pass")
        self.assertEqual(rows(clip(48), {"check": "size", "expect": [1920, 1080]})[0]["status"],
                         "fail")

    def test_constant_fps_passes_on_a_cfr_file(self):
        row = rows(clip(48), {"check": "constant_fps", "expect": FPS})[0]
        self.assertEqual(row["status"], "pass", row)
        self.assertAlmostEqual(row["measured"]["fps"], FPS, places=2)
        self.assertLess(row["measured"]["jitter"], 0.001)

    def test_constant_fps_fails_when_the_rate_is_wrong(self):
        """A 24 fps file asked for 30: uniform timing is not enough, the RATE must match too."""
        row = rows(clip(48), {"check": "constant_fps", "expect": 30})[0]
        self.assertEqual(row["status"], "fail")
        self.assertIn("expected 30.000 fps", row["message"])

    def test_decodes_clean_passes_on_a_good_file(self):
        row = rows(clip(48), {"check": "decodes_clean"})[0]
        self.assertEqual(row["status"], "pass", row)
        self.assertEqual(row["measured"], "clean")

    def test_decodes_clean_fails_on_a_truncated_file(self):
        row = rows(truncated(), {"check": "decodes_clean"})[0]
        self.assertEqual(row["status"], "fail")
        self.assertTrue(row["message"], "a failure must say what ffmpeg said")

    def test_has_audio_reads_the_streams(self):
        self.assertEqual(rows(clip(24, audio=True), {"check": "has_audio"})[0]["status"], "pass")
        self.assertEqual(rows(clip(48), {"check": "has_audio", "expect": True})[0]["status"],
                         "fail")

    def test_frame_ids_are_contiguous_on_a_counter_clip(self):
        row = rows(clip(48), {"check": "frame_ids_contiguous"})[0]
        self.assertEqual(row["status"], "pass", row)
        self.assertEqual(row["measured"]["repeated"], 0)
        self.assertEqual(row["measured"]["gaps"], 0)

    def test_an_unknown_check_fails_instead_of_passing_silently(self):
        row = rows(clip(48), {"check": "looks_nice"})[0]
        self.assertEqual(row["status"], "fail")
        self.assertIn("unknown check", row["message"])

    def test_a_missing_output_fails_instead_of_raising(self):
        row = rows(out("does_not_exist.mp4"), {"check": "frame_count", "expect": 1})[0]
        self.assertEqual(row["status"], "fail")
        self.assertIn("no output file", row["message"])

    def test_every_declared_check_is_reported_even_when_one_fails(self):
        found = rows(clip(48), {"check": "frame_count", "expect": 48},
                     {"check": "size", "expect": [1, 1]}, {"check": "decodes_clean"})
        self.assertEqual([row["check"] for row in found],
                         ["frame_count", "size", "decodes_clean"])
        self.assertEqual([row["status"] for row in found], ["pass", "fail", "pass"])
        self.assertEqual(len(validate.failures(found)), 1)


class SlideshowTest(unittest.TestCase):
    """slideshow_risk: the cheapest honest answer to "is this an edit or a set of stills?"."""

    def test_a_still_is_high_risk(self):
        row = validate.slideshow_risk(still(24))
        self.assertEqual(row["verdict"], "high", row)
        self.assertEqual(row["score"], 1.0)
        self.assertEqual(row["frames"], 24)

    def test_the_counter_clip_is_low_risk(self):
        row = validate.slideshow_risk(clip(48))
        self.assertEqual(row["verdict"], "low", row)
        self.assertLess(row["score"], 0.1)

    def test_a_missing_file_is_unknown_not_a_crash(self):
        row = validate.slideshow_risk(out("nope.mp4"))
        self.assertEqual(row["verdict"], "unknown")
        self.assertIn("no such file", row["detail"])


class ProvenanceTest(unittest.TestCase):
    """Provenance reports the policy `manifest` enforces; it never widens it."""

    def document(self, *assets):
        return {"constraints": {"ai_generated_images": False,
                                "allowed_asset_origins": ["footage", "user_image",
                                                          "code_graphic", "stock_licensed"]},
                "assets": list(assets)}

    def test_footage_is_ok_and_digested(self):
        report = validate.provenance(self.document(
            {"id": "src", "path": guard.rel(clip(48)), "origin": "footage"}))
        self.assertTrue(report["ok"], report)
        row = report["assets"][0]
        self.assertTrue(row["exists"] and row["visual"])
        self.assertIn("sha256", row["digest"])

    def test_an_ai_origin_visual_asset_is_refused(self):
        report = validate.provenance(self.document(
            {"id": "src", "path": guard.rel(clip(48)), "origin": "ai_generated"}))
        self.assertFalse(report["ok"])
        self.assertIn("not allowed", report["assets"][0]["problems"][0])

    def test_a_missing_asset_is_reported(self):
        report = validate.provenance(self.document(
            {"id": "src", "path": "out/engine_validate/gone.mp4", "origin": "footage"}))
        self.assertFalse(report["ok"])
        self.assertIn("missing", " ".join(report["assets"][0]["problems"]))

    def test_user_audio_is_not_held_to_the_visual_rule(self):
        report = validate.provenance(self.document(
            {"id": "voice", "path": "out/engine_validate/voice.wav", "origin": "user_audio"}))
        row = report["assets"][0]
        self.assertFalse(row["visual"])
        self.assertNotIn("not allowed", " ".join(row["problems"]))


if __name__ == "__main__":
    unittest.main()


