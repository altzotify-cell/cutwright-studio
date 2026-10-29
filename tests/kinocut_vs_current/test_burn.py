"""M2 area: burning an SRT into the picture (libass) on a Windows path with non-ASCII."""
import os
import unittest

from tests.kinocut_vs_current import harness as hh

FPS, FRAMES = 24, 72
SUB_DIR = "burn caf\u00e9"          # non-ASCII directory name on purpose
SRT = ("1\n00:00:00,500 --> 00:00:01,500\nCaf\u00e9 \u00d1and\u00fa\n\n"
       "2\n00:00:01,500 --> 00:00:02,500\n\u5b57\u5e55\u30c6\u30b9\u30c8\n")
PROBE_FRAMES = {"before": 6, "cue1": 24, "cue2": 42, "after": 66}


def text_marks(path):
    """Bright pixels per probed frame: text is the only bright thing on a black clip."""
    if not path or not os.path.exists(path):
        return {"exists": False}
    frames = hh.gray_frames(path, 320, 180)
    marks = {k: (hh.bright(frames[v]) if v < len(frames) else None)
             for k, v in PROBE_FRAMES.items()}
    return {"exists": True, "frames": len(frames), "bright_pixels": marks,
            "text_on_cues": bool(marks.get("cue1")) and bool(marks.get("cue2")),
            "clean_before": marks.get("before") == 0}


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class BurnEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = os.path.join(hh.WORK_OUT, SUB_DIR)
        os.makedirs(cls.dir, exist_ok=True)
        cls.clip = os.path.join(cls.dir, "black.mp4")
        hh.ff("-f", "lavfi", "-i", "color=c=black:s=320x180:r=%d:d=%.3f" % (FPS, FRAMES / float(FPS)),
              "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", cls.clip)
        with open(os.path.join(cls.dir, "subs.srt"), "w", encoding="utf-8") as f:
            f.write(SRT)

    def test_burn_srt(self):
        rows = {}
        kout = hh.out_path("bn_kino.mp4")
        res = hh.kino("subtitles", self.clip, os.path.join(self.dir, "subs.srt"), "-o", kout)
        rows["kinocut"] = dict(hh.note(res), **text_marks(kout))

        fout = hh.out_path("bn_ff.mp4")
        # Relative filename + cwd avoids the Windows drive-colon escaping problem entirely.
        with hh.in_dir(self.dir):
            res = hh.ff("-i", "black.mp4", "-vf", "subtitles=subs.srt:force_style='Fontsize=28'",
                        "-frames:v", str(FRAMES), "-c:v", "libx264", "-crf", "12",
                        "-pix_fmt", "yuv420p", hout(fout))
        rows["ffmpeg"] = dict(text_marks(fout), exit=res["exit"], stderr_tail=res["stderr"][-200:])

        rows["current"] = {"supported": False,
                           "reason": "recap.py writes .srt for the player (step_srt) and draws "
                                     "only drawtext slates/gfx; captions are rendered by Remotion"}

        hh.write_evidence("burn", {
            "test": "burn a 2-cue UTF-8 SRT (Caf\u00e9 \u00d1and\u00fa / \u5b57\u5e55) at %d fps on a "
                    "non-ASCII Windows directory" % FPS,
            "srt": SRT, "dir": hh.rel(self.dir), "rows": rows})

        k = rows["kinocut"]
        self.assertTrue(k.get("exists"), "kinocut subtitles -> %s" % k)
        self.assertTrue(k.get("clean_before"), "kinocut burn leaked before the first cue -> %s" % k)
        self.assertTrue(k.get("text_on_cues"), "kinocut burn text visible -> %s" % k.get("bright_pixels"))


def hout(path):
    """Output path expressed relative to the current directory (used inside in_dir)."""
    return os.path.abspath(path)
