"""Synthetic media with machine-readable timing, stdlib only (no fonts, no drawtext).

Why: to compare Kinocut / ffmpeg / the current recap.py code on FRAME ACCURACY and A/V SYNC you
need media where every frame says which frame it is and the audio has known onsets.

Video: 160x90. Frame number N is drawn as 16 black/white blocks (10 px wide each, MSB first).
       Survives h264 at crf 12 and survives scale up/down, because the decoder samples block centres.
Audio: 48 kHz mono. A 50 ms 1 kHz beep starts at every whole second (t = 0, 1, 2 ...).
Reading back: frame_ids(path) -> list of ints, one per decoded frame, in order.
              beep_onsets(path) -> list of seconds where each beep starts (+/- ~1 ms).
Everything shells out to ffmpeg/ffprobe on PATH with argument lists (no shell, Windows safe).
"""
import math
import os
import struct
import subprocess
import wave

W, H = 160, 90
BITS = 16
BLOCK = W // BITS
RATE = 48000


def _run(cmd, data=None):
    r = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError("%s failed:\n%s" % (cmd[0], r.stderr.decode("utf-8", "replace")[-1500:]))
    return r.stdout


def _frame_bytes(n, offset=0):
    v = (n + offset) & 0xFFFF
    row = bytearray()
    for b in range(BITS):
        bit = (v >> (BITS - 1 - b)) & 1
        row += (b"\xff\xff\xff" if bit else b"\x00\x00\x00") * BLOCK
    return bytes(row) * H


def _beep_wav(path, seconds):
    n = int(seconds * RATE)
    samples = bytearray()
    for i in range(n):
        t = i / RATE
        pos = t - math.floor(t)
        s = int(20000 * math.sin(2 * math.pi * 1000 * t)) if pos < 0.05 else 0
        samples += struct.pack("<h", s)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(samples))


def make_counter_clip(path, frames=240, fps=24, with_audio=True, id_offset=0):
    """Write an mp4 whose frame k carries the number k + id_offset. Returns path."""
    data = b"".join(_frame_bytes(k, id_offset) for k in range(frames))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-"]
    wav = None
    if with_audio:
        wav = path + ".beeps.wav"
        _beep_wav(wav, frames / float(fps) + 0.5)
        cmd += ["-i", wav]
    cmd += ["-c:v", "libx264", "-crf", "12", "-g", "12", "-pix_fmt", "yuv420p"]
    if with_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-t", "%.6f" % (frames / float(fps))]
    cmd += [path]
    _run(cmd, data)
    if wav and os.path.exists(wav):
        os.remove(wav)
    return path


def frame_ids(path):
    """Decode every video frame and read its number back. One int per frame, in play order."""
    raw = _run(["ffmpeg", "-loglevel", "error", "-i", path, "-an", "-vf",
                "scale=%d:%d:flags=neighbor" % (W, H), "-f", "rawvideo", "-pix_fmt", "gray", "-"])
    size = W * H
    out = []
    for f in range(len(raw) // size):
        base = f * size + (H // 2) * W
        v = 0
        for b in range(BITS):
            v = (v << 1) | (1 if raw[base + b * BLOCK + BLOCK // 2] > 128 else 0)
        out.append(v)
    return out


def beep_onsets(path, threshold=4000):
    """Seconds at which each beep starts (first sample above threshold after >=100 ms of quiet)."""
    raw = _run(["ffmpeg", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(RATE),
                "-f", "s16le", "-"])
    n = len(raw) // 2
    vals = struct.unpack("<%dh" % n, raw[:n * 2])
    out, quiet, gap = [], RATE, int(0.1 * RATE)
    for i, s in enumerate(vals):
        if abs(s) > threshold:
            if quiet >= gap:
                out.append(i / float(RATE))
            quiet = 0
        else:
            quiet += 1
    return out


def probe_counts(path):
    """(video_frames, video_seconds, audio_seconds) from ffprobe; frames counted by decoding."""
    import json
    j = json.loads(_run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                         "-show_entries", "stream=nb_read_frames,duration", "-of", "json", path]))
    s = j["streams"][0]
    a = json.loads(_run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                         "-show_entries", "stream=duration", "-of", "json", path]))
    adur = float(a["streams"][0]["duration"]) if a.get("streams") else None
    return int(s["nb_read_frames"]), float(s["duration"]), adur
