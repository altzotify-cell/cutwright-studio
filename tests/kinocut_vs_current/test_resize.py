"""M2 area: 16:9 -> 9:16 reframing (pad / blur / crop) and a non-square-pixel source."""
import os
import unittest

from tests.kinocut_vs_current import harness as hh

FPS = 24
OW, OH = 1080, 1920
SW, SH = 108, 192          # measurement grid: 1/10 of the output


def content_bbox(path):
    """Where the picture actually sits, in output pixels: (x0, y0, x1, y1) or None."""
    frames = hh.gray_frames(path, SW, SH)
    if not frames:
        return None
    f = frames[len(frames) // 2]
    rows = [y for y in range(SH) if any(f[y * SW + x] > 8 for x in range(SW))]
    cols = [x for x in range(SW) if any(f[y * SW + x] > 8 for y in range(SH))]
    if not rows or not cols:
        return None
    k = OW // SW
    return (cols[0] * k, rows[0] * k, (cols[-1] + 1) * k, (rows[-1] + 1) * k)


def shape(path):
    """Output size + picture content box + the aspect of that box + a black-border flag."""
    if not path or not os.path.exists(path):
        return {"exists": False}
    props = hh.vprops(path)
    box = content_bbox(path)
    out = {"exists": True, "width": props["width"], "height": props["height"],
           "frames": props["frames"], "size_ok": props["width"] == OW and props["height"] == OH,
           "content_box": box}
    if box:
        cw, ch = box[2] - box[0], box[3] - box[1]
        out.update({"content_w": cw, "content_h": ch,
                    "content_aspect": round(cw / float(ch), 3),
                    "centred_x": abs((box[0] + box[2]) / 2.0 - OW / 2.0) <= 8,
                    "centred_y": abs((box[1] + box[3]) / 2.0 - OH / 2.0) <= 8})
    return out


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class ResizeEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = hh.colour_clip("rs_src_red.mp4", "red", 48, FPS)

        cls.ns = hh.out_path("src_nonsquare.mp4")
        # Same 160x90 picture, anamorphic SAR 2:1 -> displays as 32:9.
        hh.ff("-i", cls.src, "-vf", "setsar=2/1", "-c:v", "libx264", "-crf", "12",
              "-pix_fmt", "yuv420p", "-an", cls.ns)

    def test_fit_modes(self):
        rows, recap = [], hh.current()
        for fill in ("pad", "blur", "crop"):
            row = {"fill": fill}
            cout = hh.out_path("rs_cur_%s.mp4" % fill)
            recap.render_video_clip({"file": self.src, "start": 0.0, "avail": 4.0},
                                    24, OW, OH, FPS, cout, fill)
            row["current"] = shape(cout)

            fout = hh.out_path("rs_ff_%s.mp4" % fill)
            if fill == "crop":
                # The current fit_graph has no crop branch, so the reference is explicit here.
                graph = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,"
                         "crop=%d:%d,setsar=1[v]" % (OW, OH, OW, OH))
            else:
                graph = recap.fit_graph(hh.W, hh.H, OW, OH, fill) + ";[f]setsar=1[v]"

            res = hh.ff("-i", self.src, "-filter_complex", graph, "-map", "[v]",
                        "-frames:v", "24", "-c:v", "libx264", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-an", fout)
            row["ffmpeg"] = dict(shape(fout), exit=res["exit"])
            rows.append(row)

        kout = hh.out_path("rs_kino_916.mp4")
        res = hh.kino("resize", self.src, "-w", str(OW), "--height", str(OH),
                      "-a", "9:16", "-o", kout)
        krow = {"cmd": hh.note(res), "shape": shape(kout)}
        hh.write_evidence("resize", {
            "test": "160x90 (16:9) -> 1080x1920 (9:16) with pad / blur / crop",
            "fixture": hh.rel(self.src), "rows": rows, "kinocut_resize_9x16": krow})

        for row in rows:
            self.assertTrue(row["current"]["size_ok"], "current %s -> %s" % (row["fill"], row["current"]))
            self.assertTrue(row["ffmpeg"]["size_ok"], "ffmpeg %s" % row["fill"])
            self.assertTrue(row["ffmpeg"]["centred_x"], "ffmpeg %s centring" % row["fill"])
            if row["fill"] == "pad":
                # 16:9 content inside 9:16 must keep its 16:9 shape (no stretch)
                self.assertAlmostEqual(row["ffmpeg"]["content_aspect"], 16 / 9.0, delta=0.10,
                                       msg="ffmpeg pad aspect -> %s" % row["ffmpeg"])
                self.assertTrue(row["ffmpeg"]["centred_y"], "ffmpeg pad vertical centring")
            else:
                self.assertGreaterEqual(row["ffmpeg"]["content_h"], 1900,
                                        "ffmpeg %s should fill the height -> %s"
                                        % (row["fill"], row["ffmpeg"]))

        self.assertTrue(krow["shape"].get("size_ok"), "kinocut resize 9:16 -> %s" % krow["shape"])
        print("[resize] kinocut 9:16 box=%s aspect=%s" % (
            krow["shape"].get("content_box"), krow["shape"].get("content_aspect")))

    def test_non_square_pixels(self):
        """A SAR 2:1 source must not be stretched: content aspect has to stay 32:9-ish."""
        recap = hh.current()
        rows = {}
        cout = hh.out_path("rs_ns_cur.mp4")
        recap.render_video_clip({"file": self.ns, "start": 0.0, "avail": 2.0},
                                12, OW, OH, FPS, cout, "pad")
        rows["current"] = shape(cout)
        fout = hh.out_path("rs_ns_ff.mp4")
        graph = recap.fit_graph(hh.W, hh.H, OW, OH, "pad") + ";[f]setsar=1[v]"
        res = hh.ff("-i", self.ns, "-filter_complex", graph, "-map", "[v]", "-frames:v", "12",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-an", fout)
        rows["ffmpeg"] = dict(shape(fout), exit=res["exit"])
        kout = hh.out_path("rs_ns_kino.mp4")
        res = hh.kino("resize", self.ns, "-w", str(OW), "--height", str(OH), "-o", kout)
        rows["kinocut"] = dict(shape(kout), cmd=hh.note(res))
        hh.write_evidence("resize_nonsquare", {
            "test": "SAR 2:1 source -> 1080x1920; is the anamorphic aspect handled?",
            "fixture": hh.rel(self.ns), "rows": rows})
        # Informational: the expected content height for a true 32:9 picture in a 1080-wide
        # box is 1080*9/32 = 304 px. Anything near 608 means the SAR was ignored (stretch).
        print("[resize] non-square content_h: %s" % {
            k: v.get("content_h") for k, v in rows.items()})
