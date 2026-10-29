"""Word timings for animated captions (gameplan Phase 1).

For every segment we want: the words of the caption text, each with a start and end time in SECONDS
measured on the fitted voice file (audio_trim/<fps>fps/<id>.wav, the one Remotion plays).

Where the timings come from, best first:
  1. "edge"    the word boundaries Edge-TTS reports while it speaks (saved by recap.py into words/_raw/<id>.json)
  2. "whisper" local faster-whisper run on the fitted voice file (any engine; needs: pip install faster-whisper)
  3. "even"    an estimate from character counts and punctuation pauses (always works, a little less exact)

The caption text (sub_text: the "subtitle" field or the narration) may differ from what was spoken, so the
timed words are matched to the caption words (difflib) and the gaps are interpolated.

Results are cached in words/<id>.json and only redone when the audio, the text or the Whisper model changes.
`rc` is the recap module (passed in so this file never imports recap).
"""

import hashlib
import importlib.util
import json
import os
import re
from difflib import SequenceMatcher

WORDS_DIR = "words"
RAW_DIR = os.path.join(WORDS_DIR, "_raw")
CACHE_VERSION = 1

_WHISPER = {"model": None, "name": None, "failed": False}
_PAUSE = {".": 8, "!": 8, "?": 8, "…": 8, ",": 4, ";": 5, ":": 5, "—": 4, "–": 3}


# --------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------
def norm(token):
    return re.sub(r"[\W_]+", "", token.lower())


def caption_tokens(text):
    return [t for t in str(text or "").split() if t.strip()]


def _h(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# --------------------------------------------------------------------
# Edge-TTS boundaries (called from recap.py while the voice is generated)
# --------------------------------------------------------------------
def save_raw(root, sid, bounds, audio_bytes):
    """bounds: [[start_s, end_s, text], ...] straight from the engine, relative to the start of audio/<id>.mp3."""
    try:
        _write_json(os.path.join(root, RAW_DIR, f"{sid}.json"),
                    {"engine": "edge", "audio_bytes": int(audio_bytes), "bounds": bounds})
    except Exception:
        pass            # word timings must never break the voice step


def lead_silence(rc, mp3):
    """Seconds of leading silence that fit_audio() cuts off the front of the mp3 (so raw times can be shifted)."""
    try:
        r = rc.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp3, "-t", "4",
                    "-af", f"silencedetect=noise={rc.SILENCE_DB}:d=0.02", "-f", "null", "-"])
        text = r.stderr or ""
        m_end = re.search(r"silence_end:\s*([0-9.]+)", text)
        m_start = re.search(r"silence_start:\s*(-?[0-9.]+)", text)
        if m_end and m_start and float(m_start.group(1)) <= 0.02:
            return max(0.0, float(m_end.group(1)) - 0.02)    # fit_audio keeps 0.02 s (start_silence)
    except Exception:
        pass
    return 0.0


# --------------------------------------------------------------------
# aligning timed words to caption words
# --------------------------------------------------------------------
def align(display, timed):
    """display: caption tokens. timed: [(start, end, text)]. Returns [(start, end)] (one per display token)."""
    n = len(display)
    if n == 0 or not timed:
        return None
    if len(timed) == n:
        res = [(t[0], t[1]) for t in timed]
    else:
        a = [norm(x) for x in display]
        b = [norm(t[2]) for t in timed]
        res = [None] * n
        sm = SequenceMatcher(None, a, b, autojunk=False)
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                if a[blk.a + k]:
                    res[blk.a + k] = (timed[blk.b + k][0], timed[blk.b + k][1])
        t_first, t_last = timed[0][0], timed[-1][1]
        i = 0
        while i < n:
            if res[i] is not None:
                i += 1
                continue
            j = i
            while j < n and res[j] is None:
                j += 1
            lo = res[i - 1][1] if i > 0 else t_first
            hi = res[j][0] if j < n else t_last
            hi = max(hi, lo)
            weights = [max(1, len(display[k])) for k in range(i, j)]
            total, acc = float(sum(weights)), lo
            for off, k in enumerate(range(i, j)):
                d = (hi - lo) * weights[off] / total
                res[k] = (acc, acc + d)
                acc += d
            i = j
    return res


def even_times(display, duration):
    """Last-resort timings: share the voice length by characters, with extra weight after punctuation."""
    if not display:
        return []
    weights = []
    for tok in display:
        w = len(norm(tok)) + 2.0
        w += _PAUSE.get(tok[-1:], 0) * 0.6
        weights.append(w)
    total = sum(weights)
    out, acc = [], 0.0
    for tok, w in zip(display, weights):
        d = duration * w / total
        out.append((acc, acc + d))
        acc += d
    return out


def _finish(times, duration):
    """Clamp into [0, duration], make starts non-decreasing, ends >= starts."""
    out, prev = [], 0.0
    for s, e in times:
        s = min(max(s, prev), max(duration - 0.01, 0.0))
        e = min(max(e, s + 0.02), duration)
        out.append((s, max(e, s)))
        prev = s
    return out


# --------------------------------------------------------------------
# Whisper (optional)
# --------------------------------------------------------------------
def _whisper_model(name):
    if _WHISPER["failed"]:
        return None
    if _WHISPER["model"] is not None and _WHISPER["name"] == name:
        return _WHISPER["model"]
    try:
        from faster_whisper import WhisperModel
        print(f"[i] loading the Whisper '{name}' model for word timings (first time downloads it)...")
        _WHISPER["model"] = WhisperModel(name, device="cpu", compute_type="int8")
        _WHISPER["name"] = name
        return _WHISPER["model"]
    except Exception as e:
        _WHISPER["failed"] = True
        print(f"[i] Whisper is not available ({e.__class__.__name__}); using estimated word timings instead. "
              "For exact timings with non-Edge voices: pip install faster-whisper")
        return None


def whisper_words(wav, name, language):
    model = _whisper_model(name)
    if model is None:
        return None
    try:
        segs, _ = model.transcribe(wav, word_timestamps=True, language=language or None,
                                   beam_size=1, vad_filter=False, condition_on_previous_text=False)
        out = []
        for s in segs:
            for w in (s.words or []):
                t = w.word.strip()
                if t:
                    out.append((float(w.start), float(w.end), t))
        return out or None
    except Exception as e:
        print(f"    [i] Whisper failed on {os.path.basename(wav)}: {e}")
        return None


# --------------------------------------------------------------------
# main entry
# --------------------------------------------------------------------
def ensure(rc, items, ccfg):
    """Returns {segment id: {"method": ..., "words": [{"w", "s", "e"}]}} for every item with caption text.

    ccfg: the "captions" settings (whisper_model: tiny|base|small|off, language: "" = auto)."""
    model_name = str(ccfg.get("whisper_model", "base") or "off").lower()
    language = str(ccfg.get("language", "") or "")
    root = rc.ROOT
    result, counts = {}, {"edge": 0, "whisper": 0, "even": 0, "cached": 0}
    todo = [i for i in items if caption_tokens(i.get("text"))]
    for n, it in enumerate(todo, 1):
        sid, fps = it["id"], it.get("fps") or rc.FPS
        display = caption_tokens(it["text"])
        wav = it["audio_file"]
        duration = it["frames"] / fps
        mp3 = os.path.join(rc.AUDIO_DIR, f"{sid}.mp3")
        try:
            st = os.stat(mp3)
            sig = f"{st.st_size}|{st.st_mtime_ns}"
        except OSError:
            sig = "nomp3"
        raw = _read_json(os.path.join(root, RAW_DIR, f"{sid}.json"))
        raw_ok = bool(raw and raw.get("engine") == "edge" and raw.get("bounds") and sig != "nomp3"
                      and raw.get("audio_bytes") == st.st_size)
        key = _h(f"{CACHE_VERSION}|{sig}|{' '.join(display)}|{model_name}|{it['frames']}|{fps}|{int(raw_ok)}")
        cpath = os.path.join(root, WORDS_DIR, f"{sid}.json")
        cached = _read_json(cpath)
        better_possible = (cached and cached.get("method") == "even" and model_name != "off"
                           and importlib.util.find_spec("faster_whisper") is not None)
        if cached and cached.get("key") == key and not better_possible:
            result[sid] = cached
            counts["cached"] += 1
            continue

        times, method = None, None
        if raw_ok:
            lead = lead_silence(rc, mp3)
            timed = [(max(0.0, b[0] - lead), max(0.0, b[1] - lead), b[2]) for b in raw["bounds"]]
            times, method = align(display, timed), "edge"
        if times is None and model_name != "off":
            timed = whisper_words(wav, model_name, language)
            if timed:
                times, method = align(display, timed), "whisper"
        if times is None:
            times, method = even_times(display, duration), "even"

        times = _finish(times, duration)
        data = {"key": key, "method": method,
                "words": [{"w": w, "s": round(s, 3), "e": round(e, 3)} for w, (s, e) in zip(display, times)]}
        _write_json(cpath, data)
        result[sid] = data
        counts[method] += 1
        print(f"    word timings {sid}: {method} ({n}/{len(todo)})")

    parts = [f"{v} {k}" for k, v in counts.items() if v]
    if parts:
        print("[+] word timings: " + ", ".join(parts))
    if counts["even"]:
        print("    [i] 'even' = estimated from the text. For exact timings use Edge-TTS (automatic) or "
              "pip install faster-whisper.")
    return result


def to_frames(words, fps, duration_frames, emphasis=()):
    """Seconds -> frame numbers inside the segment (what Remotion reads)."""
    if isinstance(emphasis, str):
        emphasis = [emphasis]
    emph = {norm(t) for e in (emphasis or []) for t in str(e).split() if norm(t)}
    out, prev = [], 0
    for w in words:
        s = int(round(w["s"] * fps))
        s = max(prev, min(s, max(duration_frames - 1, 0)))
        e = int(round(w["e"] * fps))
        e = min(max(e, s + 1), duration_frames)
        out.append({"word": w["w"], "startFrame": s, "endFrame": e, "emphasis": norm(w["w"]) in emph})
        prev = s
    return out
