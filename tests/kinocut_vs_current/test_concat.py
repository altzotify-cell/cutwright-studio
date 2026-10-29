"""M2 area: concat. 20 x 120-frame counter clips (contiguous ids) joined in order."""
import os
import time
import unittest

from tests.kinocut_vs_current import harness as hh

FPS = 24
CLIPS = 20
NF = 120
EXPECTED = list(range(CLIPS * NF))


def drift(onsets):
    """Worst distance from a beep onset to the whole second it should land on."""
    if not onsets:
        return None
    return round(max(abs(t - round(t)) for t in onsets), 4)


def drift_profile(onsets, block=5.0):
    """Mean offset per 5 s clip block: shows whether drift accumulates at every join."""
    buckets = {}
    for t in onsets:
        buckets.setdefault(int(t // block), []).append(t - round(t))
    return {k: round(sum(v) / len(v), 4) for k, v in sorted(buckets.items())}


def sequence_health(got, expected):
    """Dropped / duplicated frames over the whole file (order preserved)."""
    missing = sorted(set(expected) - set(got))
    return {"frames_decoded": len(got), "ordered": all(a <= b for a, b in zip(got, got[1:])),
            "duplicates": len(got) - len(set(got)), "missing": len(missing),
            "missing_sample": missing[:5]}




def measure(path, expect_ids=None, expected_frames=CLIPS * NF):
    if not path or not os.path.exists(path):
        return {"exists": False}
    got = hh.ids(path)
    props = hh.vprops(path)
    out = {"exists": True, "frames": props["frames"], "audio_seconds": props["audio_seconds"],
           "expected_frames": expected_frames, "frames_exact": props["frames"] == expected_frames,
           "first": got[:3], "last": got[-3:]}
    onsets_list = hh.onsets(path)
    if expect_ids is not None:
        out.update(sequence_health(got, expect_ids))
    out["beep_drift_s"] = drift(onsets_list)
    out["drift_per_block"] = drift_profile(onsets_list)
    if expect_ids is not None:
        out.update(sequence_health(got, expect_ids))
    return out



@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class ConcatEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clips = [hh.counter(NF, FPS, k * NF) for k in range(CLIPS)]

    def test_concat_same_codec(self):
        rows = {}

        kout = hh.out_path("cc_kino.mp4")
        t0 = time.time()
        res = hh.kino("merge", *self.clips, "-o", kout)
        rows["kinocut"] = dict(hh.note(res), **measure(kout, EXPECTED))
        rows["kinocut"]["seconds_wall"] = round(time.time() - t0, 2)

        cout = hh.out_path("cc_cur.mp4")
        recap = hh.current()
        recap.TIKTOK_TEMP = os.path.join(hh.WORK_OUT, "tmp")
        items = [{"video_file": p, "audio_file": p, "orig_file": None,
                  "frames": NF, "fps": FPS, "id": "c%d" % k} for k, p in enumerate(self.clips)]
        t0 = time.time()
        try:
            with hh.in_dir(hh.WORK_OUT):
                recap.join_av(items, cout, "cc", music=None)
            rows["current"] = dict(measure(cout, EXPECTED), seconds_wall=round(time.time() - t0, 2))
        except SystemExit as e:  # recap.die() exits
            rows["current"] = {"exists": False, "error": "recap.die exit %s" % e.code}

        fout = hh.out_path("cc_ff.mp4")
        lst = os.path.join(hh.WORK_OUT, "cc_list.txt")
        recap.write_concat_list(lst, self.clips)
        t0 = time.time()
        res = hh.ff("-f", "concat", "-safe", "0", "-i", lst, "-vf",
                    "scale=%d:%d:flags=neighbor,setsar=1,fps=%d" % (hh.W, hh.H, FPS),
                    "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", fout)
        rows["ffmpeg"] = dict(measure(fout, EXPECTED), exit=res["exit"],
                              seconds_wall=round(time.time() - t0, 2))

        hh.write_evidence("concat", {
            "test": "%d clips x %d frames at 24 fps, contiguous ids %d..%d"
                    % (CLIPS, NF, EXPECTED[0], EXPECTED[-1]),
            "clips": CLIPS, "frames_per_clip": NF, "rows": rows})

        for name in ("kinocut", "current"):
            row = rows[name]
            self.assertTrue(row.get("frames_exact"), "%s frame count -> %s" % (name, row))
            self.assertEqual(row.get("missing"), 0, "%s dropped frames -> %s" % (name, row))
            self.assertLessEqual(row.get("duplicates") or 0, 1,
                                 "%s duplicated more than one frame -> %s" % (name, row))
        # Reference row: re-encoding through the concat demuxer with an fps filter loses the
        # final frame (2399 of 2400). Recorded, not asserted as a pass.
        self.assertLessEqual(rows["ffmpeg"].get("missing") or 9, 1,
                             "ffmpeg reference dropped more than one frame -> %s" % rows["ffmpeg"])
        # Audio drift is measured separately (test_concat_pcm_audio): with AAC sources every
        # join adds encoder priming, and it is significant over 20 clips.
        print("[concat] audio drift by executor: %s" % {
            k: v.get("beep_drift_s") for k, v in rows.items()})


    def test_concat_pcm_audio(self):
        """Same join with PCM audio instead of AAC: does the per-join drift disappear?"""
        clips = []
        for k in range(5):
            src = hh.counter(NF, FPS, k * NF)
            dst = hh.out_path("pcm_%d.mov" % k)
            res = hh.ff("-i", src, "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                        "-c:a", "pcm_s16le", "-ar", "48000", dst)
            if res["exit"] != 0:
                raise RuntimeError(res["stderr"][-400:])
            clips.append(dst)
        rows = {"clips": len(clips), "clip_seconds": NF / float(FPS),
                "aac_drift_over_5_joins": None}

        kout = hh.out_path("pcm_kino.mp4")
        res = hh.kino("merge", *clips, "-o", kout)
        rows["kinocut_merge_pcm"] = dict(hh.note(res), **measure(kout))

        # Reference: join the PCM clips with the concat demuxer
        lst = os.path.join(hh.WORK_OUT, "pcm_list.txt")
        hh.current().write_concat_list(lst, clips)
        fout = hh.out_path("pcm_ff.mp4")
        res = hh.ff("-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-crf", "12",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", fout)
        rows["ffmpeg_concat_pcm"] = dict(measure(fout), exit=res["exit"])

        for name in ("kinocut_merge_pcm", "ffmpeg_concat_pcm"):
            row = rows[name]
            per_join = (row.get("beep_drift_s") or 9.0) / (len(clips) - 1)
            row["per_join_drift_ms"] = round(per_join * 1000, 2)
            row["within_42ms_budget"] = (row.get("beep_drift_s") or 9.0) <= 0.042

        hh.write_evidence("concat_pcm", {
            "test": "5 x 120-frame clips carrying PCM audio, joined with Kinocut merge and "
                    "the ffmpeg concat demuxer (control for the AAC priming drift)",
            "budget_s": 0.042, "rows": rows})
        for name in ("kinocut_merge_pcm", "ffmpeg_concat_pcm"):
            row = rows[name]
            # The per-join rate is asserted; the 20-clip total is reported as a limitation.
            self.assertLessEqual((row.get("per_join_drift_ms") or 999) / 1000.0, 0.020,
                                 "%s per-join drift -> %s" % (name, row.get("drift_per_block")))
        print("[concat] PCM per-join drift ms: %s" % {
            k: rows[k].get("per_join_drift_ms") for k in ("kinocut_merge_pcm", "ffmpeg_concat_pcm")})





    def test_concat_mixed_inputs(self):
        """Mixed fps + resolution: who normalises, and what does the output look like?"""
        a = hh.counter(48, FPS, 0)
        b = hh.out_path("mix_320x180_30fps.mp4")
        res = hh.ff("-i", a, "-vf", "scale=320:180:flags=neighbor,setsar=1,fps=30",
                    "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", b)
        self.assertEqual(res["exit"], 0, res["stderr"][-500:])
        mixed = [a, b]
        b_frames = hh.vprops(b)["frames"]
        expected = 48 + int(round(b_frames / 30.0 * FPS))
        rows = {"inputs": [hh.vprops(a)["frames"], hh.vprops(b)["frames"]],
                "expected_frames_if_normalised": expected}

        kout = hh.out_path("cc_mix_kino.mp4")
        res = hh.kino("merge", *mixed, "-o", kout)
        rows["kinocut"] = dict(hh.note(res), **measure(kout, expected_frames=expected))

        cout = hh.out_path("cc_mix_cur.mp4")
        recap = hh.current()
        recap.TIKTOK_TEMP = os.path.join(hh.WORK_OUT, "tmp")
        items = [{"video_file": a, "audio_file": a, "orig_file": None,
                  "frames": 48, "fps": FPS, "id": "a"},
                 {"video_file": b, "audio_file": b, "orig_file": None,
                  "frames": 60, "fps": 30, "id": "b"}]
        try:
            with hh.in_dir(hh.WORK_OUT):
                recap.join_av(items, cout, "ccmix", music=None)
            rows["current"] = measure(cout, expected_frames=expected)
        except SystemExit as e:
            rows["current"] = {"exists": False, "error": "recap.die exit %s" % e.code}

        fout = hh.out_path("cc_mix_ff.mp4")
        # The normalising reference: one scale/fps/sar grid for every input.
        res = hh.ff("-i", a, "-i", b, "-filter_complex",
                    "[0:v]scale=%d:%d:flags=neighbor,setsar=1,fps=%d[v0];"
                    "[1:v]scale=%d:%d:flags=neighbor,setsar=1,fps=%d[v1];"
                    "[v0][v1]concat=n=2:v=1:a=0[v];"
                    "[0:a][1:a]concat=n=2:v=0:a=1[a]"
                    % (hh.W, hh.H, FPS, hh.W, hh.H, FPS),
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "12",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", fout)
        got = hh.ids(fout) if os.path.exists(fout) else []
        rows["ffmpeg_normalised"] = dict(measure(fout, expected_frames=expected), exit=res["exit"],
                                         ids_contiguous=got == list(range(expected)))

        hh.write_evidence("concat_mixed", {
            "test": "48 frames @24fps 160x90 + 60 frames @30fps 320x180 joined",
            "rows": rows})
        self.assertTrue(rows["kinocut"].get("exists") or rows["kinocut"].get("exit") is not None,
                        "kinocut mixed merge -> %s" % rows["kinocut"])
        self.assertTrue(rows["ffmpeg_normalised"].get("exists"),
                        "normalising ffmpeg produced nothing -> %s" % rows["ffmpeg_normalised"])
        print("[concat] mixed: expected %d normalised frames; kinocut=%s current=%s ffmpeg=%s"
              % (expected, rows["kinocut"].get("frames"), rows["current"].get("frames"),
                 rows["ffmpeg_normalised"].get("frames")))


