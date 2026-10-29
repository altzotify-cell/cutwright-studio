"""M2 area: transitions. A 12-frame crossfade between two 120-frame clips (+ a wipe).

Two fixture pairs: counter clips (frame ids survive) and white/black solid clips carrying a
continuous tone (an unambiguous blend ramp and gap/click measurement).
"""
import os
import unittest

from tests.kinocut_vs_current import harness as hh

FPS = 24
A_FRAMES, B_FRAMES, TD = 120, 120, 12
TOTAL = A_FRAMES + B_FRAMES - TD


def structure(path, a_off=0, b_off=600):
    """Frame count and intact heads/tails, read back from the counter clips."""
    if not path or not os.path.exists(path):
        return {"exists": False}
    got = hh.ids(path)
    props = hh.vprops(path)
    return {"exists": True, "frames": props["frames"], "expected_frames": TOTAL,
            "frames_exact": props["frames"] == TOTAL,
            "head_ids_intact": got[:A_FRAMES - TD] == list(range(a_off, a_off + A_FRAMES - TD)),
            "tail_ids_intact": got[-(B_FRAMES - TD):] == list(range(b_off + TD, b_off + B_FRAMES)),
            "audio_seconds": props["audio_seconds"]}


def blend_and_audio(path):
    """Overlap luma ramp between the two solid sources, plus audio continuity."""
    if not path or not os.path.exists(path):
        return {"exists": False}
    frames = hh.gray_frames(path)
    luma = [hh.mean_luma(f) for f in frames]
    head = luma[A_FRAMES - TD - 1]        # last pure white frame
    tail = luma[A_FRAMES] if len(luma) > A_FRAMES else None   # first pure black frame
    overlap = luma[A_FRAMES - TD:A_FRAMES]
    steps = [round(overlap[k + 1] - overlap[k], 2) for k in range(len(overlap) - 1)]
    gaps = [g for g in hh.silence_gaps(path, threshold_db=-45.0, min_gap=0.010) if g[1] > 0.010]
    span = (max(overlap) - min(overlap)) if overlap else 0.0
    full = abs((head or 0) - (tail or 0))
    return {"exists": True, "frames": len(frames), "head_luma": head, "tail_luma": tail,
            "overlap_luma": overlap, "overlap_steps": steps,
            # a real blend: monotone ramp covering at least half the distance between the sources,
            # never leaving the two source levels
            "overlap_is_blend": bool(overlap) and tail is not None
            and all(s <= 0.5 for s in steps) and span >= 0.5 * full
            and min(overlap) >= min(head, tail) - 3 and max(overlap) <= max(head, tail) + 3,
            "overlap_monotonic": all(s <= 0.5 for s in steps),

            "gaps_over_10ms": gaps,
            "audio_seconds": hh.vprops(path)["audio_seconds"],
            "max_step_db_at_join": hh.max_step_db(path, at=(A_FRAMES - TD / 2.0) / float(FPS),
                                                  radius=0.15),
            "max_step_db_elsewhere": hh.max_step_db(path, at=1.0, radius=0.15)}


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class TransitionEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = hh.counter(A_FRAMES, FPS, 0)
        cls.b = hh.counter(B_FRAMES, FPS, 600)
        cls.white = hh.colour_clip("tr_white.mp4", "white", A_FRAMES, FPS, tone_hz=300)
        cls.black = hh.colour_clip("tr_black.mp4", "black", B_FRAMES, FPS, tone_hz=300)

    def test_crossfade_12_frames(self):
        rows = {}
        td = "%.6f" % (TD / float(FPS))

        for kind in ("fade", "wipe-left"):
            kout = hh.out_path("tr_kino_%s_ids.mp4" % kind)
            res = hh.kino("merge", self.a, self.b, "-t", kind, "-td", td, "-o", kout)
            sout = hh.out_path("tr_kino_%s_solid.mp4" % kind)
            res2 = hh.kino("merge", self.white, self.black, "-t", kind, "-td", td, "-o", sout)
            rows["kinocut_" + kind] = dict(hh.note(res), structure=structure(kout),
                                           blend=blend_and_audio(sout),
                                           solid_exit=res2["exit"])

        fout = hh.out_path("tr_ff_fade_ids.mp4")
        res = hh.ff("-i", self.a, "-i", self.b, "-filter_complex",
                    "[0:v][1:v]xfade=transition=fade:duration=%.6f:offset=%.6f[v];"
                    "[0:a][1:a]acrossfade=d=%.6f[a]"
                    % (TD / float(FPS), (A_FRAMES - TD) / float(FPS), TD / float(FPS)),
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "12",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", fout)
        fsolid = hh.out_path("tr_ff_fade_solid.mp4")
        res2 = hh.ff("-i", self.white, "-i", self.black, "-filter_complex",
                     "[0:v][1:v]xfade=transition=fade:duration=%.6f:offset=%.6f[v];"
                     "[0:a][1:a]acrossfade=d=%.6f[a]"
                     % (TD / float(FPS), (A_FRAMES - TD) / float(FPS), TD / float(FPS)),
                     "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "12",
                     "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", fsolid)
        rows["ffmpeg_xfade"] = dict(structure=structure(fout), blend=blend_and_audio(fsolid),
                                    exit=res["exit"], solid_exit=res2["exit"])

        rows["current"] = {"supported": False,
                           "reason": "no xfade in recap.py (join_av = concat demuxer, hard cut); "
                                     "Remotion/transitions.tsx does picture effects only"}

        hh.write_evidence("transition", {
            "test": "12-frame (0.5 s) %s between a 120-frame and a 120-frame clip" % td,
            "expected_frames": TOTAL, "clip_a": hh.rel(self.a), "clip_b": hh.rel(self.b),
            "solid_pair": [hh.rel(self.white), hh.rel(self.black)], "rows": rows})

        for name in ("kinocut_fade", "kinocut_wipe-left", "ffmpeg_xfade"):
            s = rows[name]["structure"]
            self.assertTrue(s.get("frames_exact"), "%s frames -> %s" % (name, s))
            self.assertTrue(s.get("head_ids_intact") and s.get("tail_ids_intact"),
                            "%s intact ids -> %s" % (name, s))
            b = rows[name]["blend"]
            self.assertTrue(b.get("overlap_is_blend"), "%s blend -> %s" % (name, b))

            self.assertEqual(b.get("gaps_over_10ms"), [], "%s audio gaps -> %s" % (name, b))

