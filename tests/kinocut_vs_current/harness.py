"""Shared helpers for the M2 equivalence tests (Kinocut vs current code vs direct FFmpeg).

Measurement only: no production code imports this package. Every helper shells out to
ffmpeg/ffprobe (PATH) or to `.venvs\\kinocut\\Scripts\\kino.exe` with argument lists (no shell,
Windows safe) and a hard per-command timeout so a bad render can never hang the suite.
"""
import array
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests import media_fixtures as mf  # noqa: E402

KINO = os.path.join(ROOT, ".venvs", "kinocut", "Scripts", "kino.exe")
EVIDENCE_DIR = os.path.join(ROOT, "docs", "evidence")
WORK = os.path.join(ROOT, "out", "m2")
FIX = os.path.join(WORK, "fixtures")
WORK_OUT = os.path.join(WORK, "out")
CMD_LIMIT = 240.0          # hard ceiling per external command, seconds
W, H = mf.W, mf.H          # 160x90 counter-clip geometry


def have_kinocut():
    return os.path.exists(KINO)


def _kill_tree(proc):
    """Kill a process AND its children: the scoop ffmpeg shim leaves a live child otherwise."""
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except (subprocess.TimeoutExpired, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def run(cmd, timeout=CMD_LIMIT, cwd=None):
    """Run a command, never raise, never hang. Returns exit code, text and wall seconds.

    stdin is DEVNULL (ffmpeg otherwise polls it) and a timeout kills the whole process tree,
    so a runaway render cannot block the suite on an inherited pipe.
    """
    t0 = time.time()
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, cwd=cwd)
    except OSError as e:
        return {"cmd": list(cmd), "exit": None, "stdout": "", "stderr": "OSError: %s" % e,
                "seconds": round(time.time() - t0, 2)}
    try:
        out, err = proc.communicate(timeout=timeout)
        return {"cmd": list(cmd), "exit": proc.returncode,
                "stdout": out.decode("utf-8", "replace"),
                "stderr": err.decode("utf-8", "replace"),
                "seconds": round(time.time() - t0, 2)}
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            out, err = b"", b""
        return {"cmd": list(cmd), "exit": None,
                "stdout": out.decode("utf-8", "replace"),
                "stderr": (err.decode("utf-8", "replace") + "\nTIMEOUT after %ss" % timeout).strip(),
                "seconds": round(time.time() - t0, 2)}


def raw(cmd, timeout=CMD_LIMIT):
    """Same as run() but returns stdout BYTES and raises on failure (for PCM/video dumps)."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL)
    except OSError as e:
        raise RuntimeError("cannot run %s: %s" % (rel(cmd[0]), e))
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        raise RuntimeError("timeout after %ss: %s" % (timeout, rel(cmd[0])))
    if proc.returncode != 0:
        raise RuntimeError("command failed: %s\n%s"
                           % (rel(cmd[0]), err.decode("utf-8", "replace")[-1200:]))
    return out



def ff(*args, **kw):
    return run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error"] + [str(a) for a in args], **kw)



def _first_json(text):
    """Kinocut may print log lines before/after its JSON. Extract the first JSON object."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


def kino(*args, overwrite=True, timeout=CMD_LIMIT, cwd=None):
    """Call the Kinocut CLI. Global flags MUST precede the subcommand (KINOCUT_FINDINGS 7.2)."""
    argv = [KINO, "--format", "json"] + (["--overwrite"] if overwrite else [])
    argv += [str(a) for a in args]
    res = run(argv, timeout=timeout, cwd=cwd)
    res["json"] = _first_json(res["stdout"]) or _first_json(res["stderr"])
    return res


# ---------------------------------------------------------------- probe / media ids
def probe(path):
    """Video + audio stream properties of a file (ffprobe). Empty dicts when absent."""
    res = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=index,codec_type,codec_name,profile,width,height,pix_fmt,"
               "r_frame_rate,avg_frame_rate,duration,sample_rate,channels,bit_rate",
               "-of", "json", path])
    j = _first_json(res["stdout"]) or {}
    streams = j.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    return {"video": v, "audio": a}


def vprops(path):
    """Just the numbers the matrix quotes: frames, size, fps, pix_fmt, codec."""
    frames, seconds, audio_seconds = mf.probe_counts(path)
    info = probe(path)
    v = info["video"]
    return {"frames": frames, "seconds": round(seconds, 4),
            "audio_seconds": None if audio_seconds is None else round(audio_seconds, 4),
            "width": v.get("width"), "height": v.get("height"), "pix_fmt": v.get("pix_fmt"),
            "codec": v.get("codec_name"), "profile": v.get("profile"),
            "fps": v.get("avg_frame_rate"), "audio_codec": info["audio"].get("codec_name"),
            "has_audio": bool(info["audio"])}


def ids(path):
    """Frame numbers read back from the counter fixture, one per decoded frame."""
    return mf.frame_ids(path)


def onsets(path):
    """Beep onsets in seconds (the fixtures beep at every whole second)."""
    return [round(t, 4) for t in mf.beep_onsets(path)]


# ---------------------------------------------------------------- audio measurement
def samples(path, start=None, dur=None, rate=mf.RATE):
    cmd = ["ffmpeg", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", "%.6f" % start]
    if dur is not None:
        cmd += ["-t", "%.6f" % dur]
    cmd += ["-i", path, "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"]
    data = raw(cmd)
    a = array.array("h")
    a.frombytes(data[:len(data) // 2 * 2])
    return a


def db(vals):
    """RMS level of int16 samples as dBFS."""
    if not vals:
        return None
    rms = math.sqrt(sum(float(v) * v for v in vals) / float(len(vals)))
    if rms <= 0:
        return -120.0
    return round(20 * math.log10(rms / 32768.0), 2)


def level(path, start, dur):
    return db(samples(path, start=start, dur=dur))


def loudness(path):
    """Integrated loudness / true peak / LRA via ffmpeg's EBU R128 scanner."""
    res = run(["ffmpeg", "-nostats", "-hide_banner", "-i", path,
               "-af", "ebur128=peak=true", "-f", "null", "-"])
    err = res["stderr"]
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    tp = re.findall(r"(?:True )?Peak:\s+(-?[\d.]+) dBFS", err)
    lra = re.findall(r"LRA:\s+(-?[\d.]+) LU", err)
    return {"integrated_lufs": float(i[-1]) if i else None,
            "true_peak_dbfs": float(tp[-1]) if tp else None,
            "lra": float(lra[-1]) if lra else None,
            "exit": res["exit"]}


def max_step_db(path, at, radius=0.05, rate=mf.RATE):
    """Largest sample-to-sample jump near time `at` (a click shows up as a big jump)."""
    vals = samples(path, start=max(0.0, at - radius), dur=2 * radius, rate=rate)
    step = 0
    for k in range(1, len(vals)):
        d = abs(vals[k] - vals[k - 1])
        if d > step:
            step = d
    return round(20 * math.log10(step / 32768.0), 2) if step else -120.0


def silence_gaps(path, threshold_db=-45.0, min_gap=0.05, rate=mf.RATE):
    """(start_seconds, length_seconds) of every silent stretch, used for gap and clipping checks."""
    vals = samples(path, rate=rate)
    thr = 32768.0 * (10 ** (threshold_db / 20.0))
    gaps, start = [], None
    for k, s in enumerate(vals):
        if abs(s) <= thr:
            if start is None:
                start = k
        else:
            if start is not None and (k - start) / float(rate) >= min_gap:
                gaps.append((round(start / float(rate), 3), round((k - start) / float(rate), 3)))
            start = None
    if start is not None and (len(vals) - start) / float(rate) >= min_gap:
        gaps.append((round(start / float(rate), 3), round((len(vals) - start) / float(rate), 3)))
    return gaps


def clipped_samples(path, ceiling=32700):
    return sum(1 for s in samples(path) if abs(s) >= ceiling)


# ---------------------------------------------------------------- picture measurement
def gray_frames(path, width=W, height=H):
    """Every frame decoded to 8-bit gray at width x height (neighbour scaling keeps blocks)."""
    data = raw(["ffmpeg", "-loglevel", "error", "-i", path, "-an", "-vf",
                "scale=%d:%d:flags=neighbor" % (width, height),
                "-f", "rawvideo", "-pix_fmt", "gray", "-"])
    size = width * height
    return [data[k * size:(k + 1) * size] for k in range(len(data) // size)]


def mean_luma(frame):
    return round(sum(frame) / float(len(frame)), 2) if frame else None


def bright(frame, thr=180):
    return sum(1 for b in frame if b >= thr)


def row_profile(frame, width=W, height=H):
    """Mean luma per column, to see where the picture actually sits (centring / aspect checks)."""
    out = []
    for x in range(width):
        out.append(round(sum(frame[y * width + x] for y in range(height)) / float(height), 1))
    return out


# ---------------------------------------------------------------- evidence + fixtures
def rel(value):
    """Repo-relative, forward slashes: keeps evidence small and machine independent."""
    if isinstance(value, (list, tuple)):
        return [rel(v) for v in value]
    s = str(value)
    if os.path.isabs(s) and s.lower().startswith(ROOT.lower()):
        s = os.path.relpath(s, ROOT)
    return s.replace("\\", "/")


def note(res, keep=("success", "operation", "error", "output_path", "duration")):
    """Compact, JSON-safe summary of one external command for the evidence files."""
    js = res.get("json") or {}
    summary = {k: js.get(k) for k in keep if k in js}
    return {"cmd": rel(res["cmd"]), "exit": res["exit"], "seconds": res["seconds"],
            "json": summary or None,
            "stderr_tail": (res.get("stderr") or "").strip()[-300:] or None}


_VER = {}


def versions():
    if not _VER:
        f = run(["ffmpeg", "-version"])
        _VER["ffmpeg"] = (f["stdout"].splitlines() or ["?"])[0][:90]
        k = run([KINO, "--version"]) if have_kinocut() else {"stdout": "absent"}
        _VER["kinocut"] = (k["stdout"].strip().splitlines() or ["?"])[-1][:60]
        _VER["python"] = sys.version.split()[0]
    return dict(_VER)


def write_evidence(area, payload):
    """One small JSON file per area: docs/evidence/m2_<area>.json."""
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    out = dict(payload)
    out["area"] = area
    out["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out["versions"] = versions()
    path = os.path.join(EVIDENCE_DIR, "m2_%s.json" % area)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("[evidence] %s (%d bytes)" % (rel(path), os.path.getsize(path)))
    return path


def fixture(name, builder):
    os.makedirs(FIX, exist_ok=True)
    path = os.path.join(FIX, name)
    if not os.path.exists(path):
        builder(path)
    return path


def counter(frames=240, fps=24, offset=0, audio=True):
    """Counter clip: frame k decodes to the number k + offset. Beeps every whole second."""
    return fixture("counter_%d_%dfps_off%d%s.mp4" % (frames, fps, offset, "" if audio else "_noaudio"),
                   lambda p: mf.make_counter_clip(p, frames=frames, fps=fps,
                                                  with_audio=audio, id_offset=offset))


def regeometry(src, name, scale_to):
    """Same content, different resolution (for the mixed-input concat test)."""
    def build(p):
        r = ff("-i", src, "-vf", "scale=%s:flags=neighbor,setsar=1" % scale_to,
               "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "copy", p)
        if r["exit"] != 0:
            raise RuntimeError(r["stderr"][-800:])
    return fixture(name, build)


def still(offset=900, name=None):
    """One PNG frame (a still picture carrying frame number `offset`) from a counter clip."""
    src = counter(6, 24, offset)

    def build(p):
        r = ff("-i", src, "-frames:v", "1", "-update", "1", p)
        if r["exit"] != 0:
            raise RuntimeError(r["stderr"][-800:])
    return fixture(name or "still_%d.png" % offset, build)


def out_path(name):
    """A clean output path under out/m2/out (Kinocut refuses to overwrite by default)."""
    os.makedirs(WORK_OUT, exist_ok=True)
    path = os.path.join(WORK_OUT, name)
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)
    return path



class in_dir(object):
    """Temporarily chdir (the current recap code writes some paths relative to cwd)."""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        os.makedirs(self.path, exist_ok=True)
        self.old = os.getcwd()
        os.chdir(self.path)
        return self.path

    def __exit__(self, *exc):
        os.chdir(self.old)
        return False


def colour_clip(name, colour, frames=48, fps=24, tone_hz=None, tone_amp=6000):
    """A flat-colour clip (optionally with a continuous tone) - letterbox and blend measurements
    need a source that is not black, and a tone that has no gaps."""
    path = os.path.join(WORK_OUT, name)
    os.makedirs(WORK_OUT, exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi",
           "-i", "color=c=%s:s=%dx%d:r=%d:d=%.4f" % (colour, W, H, fps, frames / float(fps))]
    if tone_hz:
        wav = os.path.join(WORK_OUT, name + ".wav")
        tone(wav, tone_hz, tone_amp, frames / float(fps) + 0.2)
        cmd += ["-i", wav, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k",
                "-shortest"]
    cmd += ["-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", path]
    res = run(cmd)
    if res["exit"] != 0:
        raise RuntimeError(res["stderr"][-500:])
    return path


def current():
    """The current Recap implementation (recapstudio/_template/recap.py), imported lazily."""
    import importlib
    sys.path.insert(0, os.path.join(ROOT, "recapstudio", "_template"))
    if "recap" in sys.modules:
        return sys.modules["recap"]
    return importlib.import_module("recap")


# ---------------------------------------------------------------- audio fixtures / bands
def tone(path, freq, amp, seconds, bursts=None, rate=mf.RATE):
    """WAV of a steady tone, or of `bursts` [(start_s, length_s)] separated by silence."""
    import struct
    import wave
    n = int(seconds * rate)
    frames = bytearray()
    for i in range(n):
        t = i / float(rate)
        on = True
        if bursts is not None:
            on = any(s <= t < s + d for s, d in bursts)
        v = int(amp * math.sin(2 * math.pi * freq * t)) if on else 0
        frames += struct.pack("<h", v)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


def band_level(path, lo, hi, start, dur, rate=mf.RATE):
    """RMS (dBFS) of ONE frequency band in a window: isolates the music bed from the voice."""
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", "%.6f" % start, "-t", "%.6f" % dur, "-i", path,
           "-vn", "-af", "highpass=f=%d,lowpass=f=%d" % (lo, hi), "-ac", "1", "-ar", str(rate),
           "-f", "s16le", "-"]
    data = raw(cmd)
    a = array.array("h")
    a.frombytes(data[:len(data) // 2 * 2])
    return db(a)


def band_onsets(path, lo, hi, tag="band", rate=mf.RATE):
    """Onsets of the voice band after band-pass filtering (A/V drift measurement)."""
    os.makedirs(WORK_OUT, exist_ok=True)
    wav = os.path.join(WORK_OUT, "band_%s.wav" % tag)
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vn", "-af",
             "highpass=f=%d,lowpass=f=%d" % (lo, hi), "-ac", "1", "-ar", str(rate), wav])
    if r["exit"] != 0 or not os.path.exists(wav):
        return []
    try:
        return [round(t, 4) for t in mf.beep_onsets(wav)]
    finally:
        if os.path.exists(wav):
            os.remove(wav)


def moov_before_mdat(path):
    """True when the moov atom precedes mdat (faststart) - read the top-level atom order."""
    order = []
    with open(path, "rb") as f:
        while len(order) < 4:
            head = f.read(8)
            if len(head) < 8:
                break
            size = int.from_bytes(head[:4], "big")
            kind = head[4:8].decode("latin-1")
            order.append(kind)
            if size == 0:
                break
            if size == 1:
                size = int.from_bytes(f.read(8), "big") - 8
                f.seek(size, 1)
            else:
                f.seek(size - 8, 1)
    return {"atoms": order, "faststart": bool(order) and order.index("moov") < (
        order.index("mdat") if "mdat" in order else 99)}

