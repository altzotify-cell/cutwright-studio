"""M2 area: fit a clip or a still to EXACTLY N frames at 1920x1080 / 24 fps / yuv420p.

Candidates: Kinocut (resize + speed: it has no "exactly N frames" parameter), the current
recap.render_video_clip / render_image_clip, and a minimal direct-ffmpeg reference.
"""
import os
import time
import unittest

from tests.kinocut_vs_current import harness as hh

FPS = 24
W, H = 1920, 1080
TARGETS = [53, 97, 241]


def measure(path, target):
    """Frame count, id monotonicity, format and first/last frame brightness."""
    if not path or not os.path.exists(path):
        return {"exists": False, "frames": None, "ok": False}
    props = hh.vprops(path)
    got = hh.ids(path)
    frames = hh.gray_frames(path)
    mono = all(got[k + 1] >= got[k] for k in range(len(got) - 1))
    return {"exists": True, "frames": props["frames"], "expected_frames": target,
            "frames_exact": props["frames"] == target,
            "width": props["width"], "height": props["height"],
            "pix_fmt": props["pix_fmt"], "fps": props["fps"],
            "size_ok": props["width"] == W and props["height"] == H,
            "fmt_ok": props["pix_fmt"] == "yuv420p" and props["fps"] in ("24/1", "24"),
            "ids_monotonic": mono, "first_id": got[0] if got else None,
            "first_luma": hh.mean_luma(frames[0]) if frames else None,
            "last_luma": hh.mean_luma(frames[-1]) if frames else None,
            "no_black_ends": bool(frames) and hh.mean_luma(frames[0]) > 5
            and hh.mean_luma(frames[-1]) > 5}


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class FitEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = hh.counter(120, FPS, 0)      # 5 s: shorter than 241 frames on purpose
        cls.still = hh.still(900)

    def test_fit_clip_exact_frames(self):
        rows, recap = [], hh.current()
        for target in TARGETS:
            row = {"target_frames": target}

            # (a) Kinocut: the only frame-count levers are speed (factor 120/target) and trim.
            kout = hh.out_path("fit_kino_%d.mp4" % target)
            res = hh.kino("speed", self.src, "-f", "%.6f" % (120.0 / target), "-o", kout)
            row["kinocut_speed"] = dict(hh.note(res), **measure(kout, target))
            kout2 = hh.out_path("fit_kino_trim_%d.mp4" % target)
            res2 = hh.kino("trim", self.src, "-s", "0", "-d", "%.6f" % (target / float(FPS)),
                           "-o", kout2)
            row["kinocut_trim"] = dict(hh.note(res2), **measure(kout2, target))

            # (b) the current implementation (exactly `frames`, pad / blur / crop fill).
            for fill in ("pad", "blur", "crop"):
                cout = hh.out_path("fit_cur_%d_%s.mp4" % (target, fill))
                t0 = time.time()
                try:
                    recap.render_video_clip({"file": self.src, "start": 0.0, "avail": 6.0},
                                            target, W, H, FPS, cout, fill)
                    row["current_" + fill] = dict(measure(cout, target),
                                                  seconds=round(time.time() - t0, 2))
                except Exception as e:  # noqa: BLE001
                    row["current_" + fill] = {"exists": False, "error": str(e)[-300:]}

            # (c) direct ffmpeg: fit_graph + fps + tpad(clone) + -frames:v
            fout = hh.out_path("fit_ff_%d.mp4" % target)
            graph = recap.fit_graph(hh.W, hh.H, W, H, "pad")
            graph += ";[f]fps=%d,setsar=1,tpad=stop_mode=clone:stop_duration=%.3f[v]" % (
                FPS, target / float(FPS) + 1)
            t0 = time.time()
            res = hh.ff("-i", self.src, "-filter_complex", graph, "-map", "[v]",
                        "-frames:v", str(target), "-c:v", "libx264", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-an", fout)
            row["ffmpeg"] = dict(measure(fout, target), seconds=round(time.time() - t0, 2),
                                 exit=res["exit"])
            rows.append(row)

        hh.write_evidence("fit", {
            "test": "fit a 120-frame clip to 53/97/241 frames at 1920x1080; exact count + format",
            "fixture": hh.rel(self.src), "targets": TARGETS, "rows": rows})

        for row in rows:
            t = row["target_frames"]
            self.assertTrue(row["current_pad"]["frames_exact"],
                            "current pad fit %d -> %s" % (t, row["current_pad"]))
            self.assertTrue(row["current_blur"]["frames_exact"], "current blur fit %d" % t)
            self.assertTrue(row["ffmpeg"]["frames_exact"], "ffmpeg fit %d -> %s" % (t, row["ffmpeg"]))
            self.assertTrue(row["ffmpeg"]["size_ok"] and row["ffmpeg"]["fmt_ok"],
                            "ffmpeg format %d" % t)
            # Kinocut: recorded, not asserted - speed/trim are the only levers and neither takes
            # a target frame count, so inexactness here is the expected capability gap.
            print("[fit] target %d: kinocut speed -> %s frames, trim -> %s frames"
                  % (t, row["kinocut_speed"].get("frames"), row["kinocut_trim"].get("frames")))

    def test_fit_still_exact_frames(self):
        rows, recap = [], hh.current()
        for target in (53, 97):
            row = {"target_frames": target}
            cout = hh.out_path("fitst_cur_%d.mp4" % target)
            t0 = time.time()
            recap.render_image_clip({"file": self.still}, target, 640, 360, FPS, cout)
            row["current_render_image_clip"] = dict(measure(cout, target),
                                                    seconds=round(time.time() - t0, 2))

            fout = hh.out_path("fitst_ff_%d.mp4" % target)
            t0 = time.time()
            res = hh.ff("-loop", "1", "-i", self.still, "-vf",
                        "scale=640:360:force_original_aspect_ratio=decrease,"
                        "pad=640:360:(ow-iw)/2:(oh-ih)/2,fps=%d,setsar=1" % FPS,
                        "-frames:v", str(target), "-c:v", "libx264", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-an", fout)
            row["ffmpeg"] = dict(measure(fout, target), seconds=round(time.time() - t0, 2),
                                 exit=res["exit"])
            # Kinocut: no still -> clip command; `still_plates` capability is unavailable (no pillow).
            help_res = hh.kino("--help")
            row["kinocut"] = {"supported": False, "help_exit": help_res["exit"],
                              "reason": "no image->clip command; still_plates unavailable (pillow absent)"}
            rows.append(row)

        hh.write_evidence("fit_still", {
            "test": "fit a PNG still to 53/97 frames at 640x360",
            "fixture": hh.rel(self.still), "rows": rows})
        for row in rows:
            self.assertTrue(row["current_render_image_clip"]["frames_exact"],
                            "current still %d -> %s"
                            % (row["target_frames"], row["current_render_image_clip"]))
            self.assertTrue(row["ffmpeg"]["frames_exact"], "ffmpeg still %d" % row["target_frames"])


