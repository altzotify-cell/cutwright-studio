"""M2 area: frame-exact trim. Kinocut vs recap.render_video_clip vs direct ffmpeg."""
import os
import time
import unittest

from tests.kinocut_vs_current import harness as hh

FPS = 24
COMBOS = [(0, 1), (1, 50), (37, 120), (119, 50)]


def readback(path, start, length):
    """Did the output carry exactly the frames [start, start+length)?"""
    if not path or not os.path.exists(path):
        return {"exists": False, "frames": None, "ids_match": False}
    got = hh.ids(path)
    expected = list(range(start, start + length))
    miss = next((k for k, (a, b) in enumerate(zip(got, expected)) if a != b), None)
    props = hh.vprops(path)
    return {"exists": True, "frames": len(got), "expected_frames": length,
            "first": got[:3], "last": got[-3:],
            "ids_match": got == expected, "first_mismatch_index": miss,
            "audio_seconds": props["audio_seconds"], "has_audio": props["has_audio"]}


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class TrimEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = hh.counter(240, FPS, 0)

    def test_trim_reencode(self):
        rows = []
        recap = hh.current()
        for start, length in COMBOS:
            t = start / float(FPS)
            d = length / float(FPS)
            row = {"start_frame": start, "length_frames": length, "start_s": round(t, 4)}

            kout = hh.out_path("trim_kino_%d_%d.mp4" % (start, length))
            res = hh.kino("trim", self.src, "-s", "%.6f" % t, "-d", "%.6f" % d, "-o", kout)
            row["kinocut"] = dict(hh.note(res), **readback(kout, start, length))

            cout = hh.out_path("trim_cur_%d_%d.mp4" % (start, length))
            t0 = time.time()
            try:
                recap.render_video_clip({"file": self.src, "start": t, "avail": 10.0},
                                        length, hh.W, hh.H, FPS, cout, "pad")
                row["current"] = dict(readback(cout, start, length),
                                      seconds=round(time.time() - t0, 2), exit=0)
            except Exception as e:  # noqa: BLE001 - a failure is a measurement
                row["current"] = {"exists": False, "exit": "exception",
                                  "error": str(e)[-300:], "seconds": round(time.time() - t0, 2)}

            fout = hh.out_path("trim_ff_%d_%d.mp4" % (start, length))
            t0 = time.time()
            res = hh.ff("-i", self.src, "-ss", "%.6f" % t, "-frames:v", str(length),
                        "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-an", fout)
            row["ffmpeg"] = dict(readback(fout, start, length),
                                 seconds=round(time.time() - t0, 2), exit=res["exit"])
            rows.append(row)

        hh.write_evidence("trim", {
            "test": "trim a 240-frame 24 fps counter clip; ids must equal range(start, start+length)",
            "fixture": {"clip": hh.rel(self.src), "frames": 240, "fps": FPS, "size": [hh.W, hh.H]},
            "combos": COMBOS, "rows": rows})

        for row in rows:
            tag = "start=%d len=%d" % (row["start_frame"], row["length_frames"])
            self.assertTrue(row["kinocut"]["ids_match"], "kinocut " + tag + " -> %s" % row["kinocut"])
            # LIMITATION (documented in docs/CAPABILITY_MATRIX.md, row "trim / frame accuracy"):
            # the current render_video_clip seeks with `-ss` BEFORE `-i`, so a non-zero start lands
            # one frame late (start 1 -> ids [2..50, 50]). Count stays exact, content does not.
            self.assertTrue(row["current"]["frames"] == row["length_frames"],
                            "current frame COUNT " + tag + " -> %s" % row["current"])
            self.assertTrue(row["ffmpeg"]["ids_match"], "ffmpeg " + tag + " -> %s" % row["ffmpeg"])
        off_by_one = [r["start_frame"] for r in rows if not r["current"]["ids_match"]]
        print("[trim] current render_video_clip not frame-exact at starts: %s" % off_by_one)


    def test_trim_accurate_flag(self):
        """Is `--accurate` different from the default on this source? (M1 saw no difference.)"""
        start, length = 37, 120
        t = start / float(FPS)
        rows = {}
        for label, extra in (("default", []), ("accurate", ["--accurate"])):
            out = hh.out_path("trim_acc_%s.mp4" % label)
            res = hh.kino("trim", self.src, "-s", "%.6f" % t, "-d", "%.6f" % (length / float(FPS)),
                          "-o", out, *extra)
            rows[label] = dict(hh.note(res), **readback(out, start, length))
        hh.write_evidence("trim_accurate", {
            "test": "--accurate vs default, start 37 / 120 frames",
            "rows": rows})
        self.assertTrue(rows["accurate"]["ids_match"], rows["accurate"])
