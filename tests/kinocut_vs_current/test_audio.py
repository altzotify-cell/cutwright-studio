"""M2 area: audio mixing, sidechain ducking, fades and loudness normalisation.

Fixture: a 6 s video whose audio is five 1 kHz voice bursts, plus a separate 300 Hz music bed.
The two are separated after the fact by band-pass filtering, so "music level during voice"
is measured on the real output instead of being assumed.
"""
import json
import os
import unittest

from tests.kinocut_vs_current import harness as hh

FPS = 24
SECONDS = 6.0
FRAMES = int(SECONDS * FPS)
VOICE_BURSTS = [(0.5, 0.3), (1.5, 0.3), (2.5, 0.3), (3.5, 0.3), (4.5, 0.3)]
MUSIC_HZ, VOICE_HZ = 100, 1000     # far apart: the voice must not leak into the music band
BAND = (60, 140)
DURING = (0.55, 0.25)        # inside the first voice burst
OUTSIDE = (1.05, 0.35)       # quiet stretch between bursts


def music_band(path):
    return {"during_voice_db": hh.band_level(path, BAND[0], BAND[1], *DURING),
            "outside_voice_db": hh.band_level(path, BAND[0], BAND[1], *OUTSIDE)}



def analyse(path, tag=""):
    """Everything the audio row of the matrix needs, measured on the produced file."""
    if not path or not os.path.exists(path):
        return {"exists": False}
    props = hh.vprops(path)
    mb = music_band(path)
    duck = None
    if mb["during_voice_db"] is not None and mb["outside_voice_db"] is not None:
        duck = round(mb["outside_voice_db"] - mb["during_voice_db"], 2)
    ons = hh.band_onsets(path, VOICE_HZ - 120, VOICE_HZ + 120, tag=tag or "a")
    expected = [b[0] for b in VOICE_BURSTS]
    err = None
    if ons:
        err = round(max(min(abs(o - e) for o in ons) for e in expected), 4)
    return {"exists": True, "has_audio": props["has_audio"],
            "audio_seconds": props["audio_seconds"], "music_band": mb,
            "duck_db": duck, "voice_onsets": ons, "voice_onset_error_s": err,
            "loudness": hh.loudness(path), "clipped_samples": hh.clipped_samples(path),
            "gaps_over_10ms": [g for g in hh.silence_gaps(path) if g[1] > 0.010]}


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class AudioEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(hh.WORK_OUT, exist_ok=True)
        cls.voice = hh.tone(os.path.join(hh.WORK_OUT, "voice.wav"), VOICE_HZ, 20000, SECONDS,
                            bursts=VOICE_BURSTS)
        cls.music = hh.tone(os.path.join(hh.WORK_OUT, "music.wav"), MUSIC_HZ, 12000, SECONDS)

        base = hh.counter(FRAMES, FPS, 0)
        cls.src = hh.out_path("audio_voice.mp4")
        res = hh.ff("-i", base, "-i", cls.voice, "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", cls.src)
        if res["exit"] != 0:
            raise RuntimeError(res["stderr"][-600:])

    def test_mix_and_duck(self):
        rows = {}

        kout = hh.out_path("au_kino_mix.mp4")
        # --sounds wants JSON track descriptions, NOT a path (kinocut 1.16.4 contract).
        tracks = json.dumps([{"path": self.music, "volume": 0.35}], ensure_ascii=False)
        res = hh.kino("mix-audio", self.src, "--sounds", tracks, "-o", kout)
        rows["kinocut_mix"] = dict(hh.note(res), **analyse(kout, "kmix"))

        kd = hh.out_path("au_kino_duck.mp4")
        res = hh.kino("duck-audio", self.src, self.music, "-o", kd)
        rows["kinocut_duck"] = dict(hh.note(res), **analyse(kd, "kduck"))

        kt = hh.out_path("au_kino_duck_tuned.mp4")
        res = hh.kino("duck-audio", self.src, self.music, "-o", kt, "--music-volume", "0.35",
                      "--threshold", "0.02", "--ratio", "8", "--attack", "5", "--release", "250")
        rows["kinocut_duck_tuned"] = dict(hh.note(res), **analyse(kt, "kduckt"))

        kn = hh.out_path("au_kino_norm.mp4")
        src_for_norm = kt if os.path.exists(kt) else (kd if os.path.exists(kd) else self.src)
        res = hh.kino("normalize-audio", src_for_norm, "-l", "-16", "--true-peak-dbtp", "-1.5",
                      "-o", kn)
        rows["kinocut_normalize"] = dict(hh.note(res), **analyse(kn, "knorm"))


        cout = hh.out_path("au_cur.mp4")
        recap = hh.current()
        recap.TIKTOK_TEMP = os.path.join(hh.WORK_OUT, "tmp")
        try:
            with hh.in_dir(hh.WORK_OUT):
                recap.join_av([{"video_file": self.src, "audio_file": self.src,
                                "orig_file": None, "frames": FRAMES, "fps": FPS, "id": "v"}],
                              cout, "au", music=self.music)
            rows["current"] = analyse(cout, "cur")
        except SystemExit as e:
            rows["current"] = {"exists": False, "error": "recap.die exit %s" % e.code}

        fdn = hh.out_path("au_ff_duck.mp4")
        graph = ("[1:a]volume=0.35[m];[0:a]asplit=2[v][sc];[sc]volume=6[scg];"
                 "[m][scg]sidechaincompress=threshold=0.1:ratio=20:attack=5:release=300[d];"
                 "[v][d]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")

        res = hh.ff("-i", self.src, "-i", self.music, "-filter_complex", graph,
                    "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-ar", "48000", fdn)
        rows["ffmpeg_duck"] = dict(analyse(fdn, "ffd"), exit=res["exit"])

        # Loudness normalisation is measured on its own pass: loudnorm is dynamic and would
        # flatten the duck if it ran inside the same graph.
        fn = hh.out_path("au_ff_norm.mp4")
        res = hh.ff("-i", fdn, "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", fn)
        rows["ffmpeg_norm"] = dict(analyse(fn, "ffn"), exit=res["exit"])


        hh.write_evidence("audio", {
            "test": "voice bursts (1 kHz) + music bed (300 Hz): mix, duck, normalize",
            "fixture": hh.rel(self.src), "music": hh.rel(self.music),
            "voice_bursts_s": VOICE_BURSTS, "during_window": DURING, "outside_window": OUTSIDE,
            "criterion": "music during voice >= 8 dB below music outside voice; "
                         "-16 LUFS +/- 1.5; true peak <= -1 dBTP; onset error <= 20 ms",
            "rows": rows})

        duck = rows["kinocut_duck_tuned"] if rows["kinocut_duck_tuned"].get("exists") else rows["kinocut_duck"]
        self.assertTrue(duck.get("exists"), "kinocut duck-audio -> %s" % duck)
        self.assertLessEqual(duck.get("voice_onset_error_s") or 9, 0.020,
                             "kinocut duck onsets -> %s" % duck.get("voice_onsets"))
        ff = rows["ffmpeg_duck"]
        self.assertGreaterEqual(ff.get("duck_db") or -99, 8.0, "ffmpeg duck -> %s" % ff.get("duck_db"))
        lo = (rows["ffmpeg_norm"].get("loudness") or {}).get("integrated_lufs")
        self.assertTrue(lo is not None and -17.5 <= lo <= -14.5, "ffmpeg loudnorm -> %s" % lo)
        klo = (rows["kinocut_normalize"].get("loudness") or {}).get("integrated_lufs")
        self.assertTrue(klo is not None and -17.5 <= klo <= -14.5,
                        "kinocut normalize -> %s" % klo)
        print("[audio] duck dB: kinocut=%s tuned=%s ffmpeg=%s current=%s"
              % (rows["kinocut_duck"].get("duck_db"), rows["kinocut_duck_tuned"].get("duck_db"),
                 ff.get("duck_db"), rows["current"].get("duck_db")))

