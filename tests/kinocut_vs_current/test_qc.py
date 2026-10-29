"""M2 area: QC gates on a deliberately bad clip (black flash, silence gap, clipping)."""
import os
import re
import unittest

from tests.kinocut_vs_current import harness as hh

FPS, SECONDS = 24, 4
BLACK_AT, SILENCE, CLIP_AT = 1.0, (2.0, 2.5), (3.0, 3.2)


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class QCEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(hh.WORK_OUT, exist_ok=True)
        # Audio is built from explicit PCM segments so silence and clipping are real, not implied.
        segs = [(hh.tone(os.path.join(hh.WORK_OUT, "qc_%d.wav" % k), 300, amp, dur), k)
                for k, (amp, dur) in enumerate([(6000, SILENCE[0]),      # normal level
                                                (0, SILENCE[1] - SILENCE[0]),  # silence
                                                (32000, CLIP_AT[1] - CLIP_AT[0]),  # clipping
                                                (6000, SECONDS - CLIP_AT[1])])]
        lst = os.path.join(hh.WORK_OUT, "qc_audio.txt")
        hh.current().write_concat_list(lst, [p for p, _ in segs])
        wav = hh.out_path("qc_audio.wav")
        res = hh.ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", wav)
        if res["exit"] != 0:
            raise RuntimeError(res["stderr"][-400:])

        cls.bad = hh.out_path("qc_bad.mp4")
        res = hh.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
                      "-f", "lavfi", "-i", "color=c=0xB03030:s=640x360:r=%d:d=%d" % (FPS, SECONDS),
                      "-i", wav, "-filter_complex",
                      "[0:v]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:"
                      "enable='between(t,%.2f,%.2f)'[v]" % (BLACK_AT, BLACK_AT + 0.1),
                      "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-crf", "12",
                      "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                      "-t", str(SECONDS), cls.bad])
        if res["exit"] != 0:
            raise RuntimeError(res["stderr"][-600:])


    def test_qc_flags(self):
        rows = {}

        res = hh.kino("video-quality-check", self.bad, "--format", "json")
        rows["kinocut_quality_check"] = hh.note(res)

        kout = hh.out_path("qc_receipt")
        res = hh.kino("release-checkpoint", self.bad, "-o", kout, "--min-score", "0")
        rows["kinocut_release_checkpoint"] = hh.note(res)
        rows["kinocut_release_checkpoint"]["files"] = sorted(
            os.path.relpath(os.path.join(d, f), hh.ROOT).replace("\\", "/")
            for d, _, fs in os.walk(kout) for f in fs)[:6] if os.path.isdir(kout) else []

        det = hh.run(["ffmpeg", "-hide_banner", "-nostats", "-i", self.bad,
                      "-vf", "blackdetect=d=0.05:pix_th=0.10", "-af",
                      "silencedetect=n=-45dB:d=0.2,volumedetect", "-f", "null", "-"])
        err = det["stderr"]
        rows["ffmpeg_detectors"] = {
            "black_intervals": re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err),
            "silence_intervals": re.findall(r"silence_start: ([\d.]+)", err),
            "max_volume_db": (re.findall(r"max_volume: (-?[\d.]+) dB", err) or [None])[-1],
            "exit": det["exit"]}

        from cutwright import frames as cwf
        rows["current_checks"] = {
            "luma_at_black_flash": round(cwf.luma_at(self.bad, BLACK_AT + 0.05), 2),
            "luma_at_clean_frame": round(cwf.luma_at(self.bad, 0.5), 2),
            "note": "cutwright/frames.py has luma/probe/cut helpers; no silence or clipping detector"}

        hh.write_evidence("qc", {
            "test": "clip with a black flash at %.1fs, silence %.1f-%.1fs, clipping %.1f-%.1fs"
                    % (BLACK_AT, SILENCE[0], SILENCE[1], CLIP_AT[0], CLIP_AT[1]),
            "fixture": hh.rel(self.bad), "rows": rows})

        ff = rows["ffmpeg_detectors"]
        self.assertTrue(ff["black_intervals"], "ffmpeg blackdetect found nothing -> %s" % ff)
        self.assertTrue(ff["silence_intervals"], "ffmpeg silencedetect found nothing -> %s" % ff)
        self.assertTrue(rows["current_checks"]["luma_at_black_flash"] < 2.0,
                        "our luma_at misses the black frame -> %s" % rows["current_checks"])
        print("[qc] kinocut quality-check exit=%s json=%s"
              % (rows["kinocut_quality_check"]["exit"], rows["kinocut_quality_check"]["json"]))
