"""M2 area: final export of a 60 s 1080p24 timeline (codec, faststart, clean decode, cost)."""
import os
import re
import time
import unittest

from tests.kinocut_vs_current import harness as hh

FPS, SECONDS = 24, 60


def export_measure(path, seconds):
    """Everything the export row needs: streams, atom order, decode cleanliness, cost."""
    if not path or not os.path.exists(path):
        return {"exists": False}
    info = hh.probe(path)
    v, a = info["video"], info["audio"]
    dec = hh.run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"])
    return {"exists": True, "size_mb": round(os.path.getsize(path) / 1048576.0, 2),
            "video": {"codec": v.get("codec_name"), "profile": v.get("profile"),
                      "pix_fmt": v.get("pix_fmt"), "width": v.get("width"),
                      "height": v.get("height"), "fps": v.get("avg_frame_rate")},
            "audio": {"codec": a.get("codec_name"), "sample_rate": a.get("sample_rate"),
                      "channels": a.get("channels")},
            "h264_high": v.get("profile") == "High" and v.get("pix_fmt") == "yuv420p",
            "aac_48k_stereo": a.get("codec_name") == "aac" and a.get("sample_rate") == "48000"
            and a.get("channels") == 2,
            "fps_constant_24": v.get("avg_frame_rate") == "24/1",
            "atoms": hh.moov_before_mdat(path)["atoms"],
            "faststart": hh.moov_before_mdat(path)["faststart"],
            "decode_clean": dec["exit"] == 0 and not dec["stderr"].strip(),
            "decode_stderr": dec["stderr"].strip()[-200:] or None,
            "encode_seconds": seconds}


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class ExportEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(hh.WORK_OUT, exist_ok=True)
        cls.tone = hh.tone(os.path.join(hh.WORK_OUT, "bed60.wav"), 300, 6000, SECONDS)
        cls.src = hh.out_path("export_src_60s.mp4")
        res = hh.ff("-stream_loop", "-1", "-i", hh.counter(240, FPS, 0), "-i", cls.tone,
                    "-vf", "scale=1920:1080:flags=neighbor,setsar=1", "-t", str(SECONDS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-ac", "2", cls.src)
        if res["exit"] != 0:
            raise RuntimeError(res["stderr"][-600:])

    def test_export_60s(self):
        rows = {}

        kout = hh.out_path("ex_kino.mp4")
        t0 = time.time()
        res = hh.kino("export", self.src, "-q", "high", "-f", "mp4", "-o", kout)
        rows["kinocut"] = dict(hh.note(res), **export_measure(kout, round(time.time() - t0, 2)))

        # The current pipeline's last step is join_av: copy the picture, re-encode the audio.
        cout = hh.out_path("ex_cur.mp4")
        recap = hh.current()
        recap.TIKTOK_TEMP = os.path.join(hh.WORK_OUT, "tmp")
        t0 = time.time()
        try:
            with hh.in_dir(hh.WORK_OUT):
                recap.join_av([{"video_file": self.src, "audio_file": self.src, "orig_file": None,
                                "frames": FPS * SECONDS, "fps": FPS, "id": "s"}], cout, "ex",
                              music=None)
            rows["current"] = export_measure(cout, round(time.time() - t0, 2))
        except SystemExit as e:
            rows["current"] = {"exists": False, "error": "recap.die exit %s" % e.code}

        fout = hh.out_path("ex_ff.mp4")
        t0 = time.time()
        res = hh.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-benchmark",
                      "-i", self.src, "-c:v", "libx264", "-preset", "veryfast",
                      "-profile:v", "high", "-crf", "18",
                      "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
                      "-ar", "48000", "-ac", "2", "-movflags", "+faststart", fout])

        bench = re.findall(r"maxrss=(\d+)kB", res["stderr"])
        rows["ffmpeg"] = dict(export_measure(fout, round(time.time() - t0, 2)),
                              exit=res["exit"], maxrss_kb=int(bench[-1]) if bench else None)

        hh.write_evidence("export", {
            "test": "export a %d s 1920x1080 24 fps timeline" % SECONDS,
            "source": hh.rel(self.src), "source_props": hh.vprops(self.src), "rows": rows})

        ff = rows["ffmpeg"]
        self.assertTrue(ff["h264_high"], "ffmpeg export profile -> %s" % ff)
        self.assertTrue(ff["aac_48k_stereo"], "ffmpeg export audio -> %s" % ff["audio"])
        self.assertTrue(ff["faststart"], "ffmpeg export faststart -> %s" % ff["atoms"])
        self.assertTrue(ff["decode_clean"], "ffmpeg export decode -> %s" % ff["decode_stderr"])
        k = rows["kinocut"]
        self.assertTrue(k.get("exists"), "kinocut export -> %s" % k)
        print("[export] kinocut: %s s, %s MB, audio=%s, faststart=%s"
              % (k.get("encode_seconds"), k.get("size_mb"), k.get("audio"), k.get("faststart")))

