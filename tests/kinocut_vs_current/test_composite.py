"""M2 area: compositing an overlay on footage in a timing window (alpha, position, opacity)."""
import json
import os
import shutil
import unittest

from tests.kinocut_vs_current import harness as hh

FPS, FRAMES = 24, 48
START, DUR = 12, 12          # frames: overlay lives on [12, 24)
BOX = (50, 110, 30, 55)      # x0, x1, y0, y1 in the 160x90 frame


def region(frame, box=BOX):
    """Mean luma inside the overlay box for one decoded frame."""
    x0, x1, y0, y1 = box
    vals = [frame[y * hh.W + x] for y in range(y0, y1) for x in range(x0, x1)]
    return round(sum(vals) / float(len(vals)), 2) if vals else None


def window(path):
    """Overlay-region luma on the frames the roadmap names: start-1, start, end-1, end."""
    if not path or not os.path.exists(path):
        return {"exists": False}
    frames = hh.gray_frames(path)
    props = hh.vprops(path)
    marks = {"start_minus_1": START - 1, "start": START, "end_minus_1": START + DUR - 1,
             "end": START + DUR}
    return {"exists": True, "frames": props["frames"], "has_audio": props["has_audio"],
            "audio_seconds": props["audio_seconds"],
            "region_luma": {k: (region(frames[v]) if v < len(frames) else None)
                            for k, v in marks.items()},
            "region_luma_all": [region(f) for f in frames[:START + DUR + 2]]}


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class CompositeEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = os.path.join(hh.WORK_OUT, "comp")
        os.makedirs(cls.dir, exist_ok=True)
        cls.base = os.path.join(cls.dir, "base.mp4")
        shutil.copyfile(hh.counter(FRAMES, FPS, 0), cls.base)
        cls.overlay = os.path.join(cls.dir, "overlay.png")
        hh.ff("-f", "lavfi", "-i", "color=c=0xFF00FF@0.5:s=60x20:d=1,format=rgba",
              "-frames:v", "1", "-update", "1", cls.overlay)

    def test_overlay_window(self):
        rows = {}
        spec = {"canvas": {"width": hh.W, "height": hh.H, "fps": FPS, "duration": FRAMES / float(FPS),
                           "background": "#000000"},
                "layers": [{"id": "base", "type": "video", "src": "base.mp4",
                            "position": {"x": 0, "y": 0}},
                           {"id": "lowerthird", "type": "image", "src": "overlay.png",
                            "position": {"x": BOX[0], "y": BOX[2]}, "opacity": 0.8,
                            "start": START / float(FPS), "duration": DUR / float(FPS)}]}
        spec_path = os.path.join(self.dir, "comp.json")
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=1)
        kout = hh.out_path("cp_kino.mp4")
        res = hh.kino("composite-layers", "--spec", spec_path, "-o", kout)
        rows["kinocut"] = dict(hh.note(res), **window(kout))

        fout = hh.out_path("cp_ff.mp4")
        res = hh.ff("-i", self.base, "-loop", "1", "-i", self.overlay,
                    "-filter_complex",
                    "[0:v][1:v]overlay=x=%d:y=%d:enable='between(t,%.6f,%.6f)'[v]"
                    % (BOX[0], BOX[2], START / float(FPS), (START + DUR) / float(FPS)),
                    "-map", "[v]", "-map", "0:a?", "-frames:v", str(FRAMES),
                    "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", fout)
        rows["ffmpeg"] = dict(window(fout), exit=res["exit"])

        rows["current"] = {"supported": False,
                           "reason": "recap.py has no compositing pass; overlays are drawn by "
                                     "Remotion (Overlays.tsx) at render time"}

        hh.write_evidence("composite", {
            "test": "lower-third PNG (50%% alpha) over footage on frames [%d, %d)"
                    % (START, START + DUR),

            "spec": spec, "box": BOX, "rows": rows})

        k = rows["kinocut"]
        self.assertTrue(k.get("exists"), "kinocut composite -> %s" % k)
        lum = k.get("region_luma") or {}
        self.assertTrue(lum.get("start") is not None and lum.get("end") is not None,
                        "kinocut region luma -> %s" % lum)
        self.assertNotEqual(lum["start"], lum["start_minus_1"], "overlay must change frame start")
        self.assertFalse(k.get("has_audio"), "KINOCUT composite output carries audio -> %s" % k)

    def test_overlay_video_keeps_audio(self):
        """`overlay-video` (PiP): does the background audio survive?"""
        pip = hh.out_path("cp_pip_src.mp4")
        res = hh.ff("-i", self.base, "-vf", "scale=40:24,setsar=1", "-c:v", "libx264",
                    "-crf", "12", "-pix_fmt", "yuv420p", "-an", pip)

        kout = hh.out_path("cp_kino_pip.mp4")
        res = hh.kino("overlay-video", self.base, pip, "-p", "top-right", "-o", kout)
        hh.write_evidence("composite_pip", {
            "test": "overlay-video (picture in picture) over a clip that has audio",
            "rows": {"kinocut": dict(hh.note(res), **window(kout))}})
        print("[composite] overlay-video has_audio=%s" % window(kout).get("has_audio"))


