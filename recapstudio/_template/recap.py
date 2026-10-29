"""Recap Studio engine v2 - one script for every step of the workflow.

You normally never run this by hand: the .bat files in the project folder do it.
Manual use:  python recap.py <step> [--video FILE] [--json FILE] [--pick] [--force] ...

Steps:
  init      Ask module / topic / target length / voice mode  -> project.json
  subs      Extract embedded subtitle tracks         -> subs/
  index     Contact sheets for EVERY file in footage/ -> sheets/
  sheets    Contact sheets for need_visual segments  -> sheets/
  comic     Import a comic/manga (.cbz .cbr .pdf) -> pages/, numbered panels, comic_review/*.pdf for Claude
  collect   Guided footage collection (yt-dlp / drag files) -> footage/, images/
  tts       Generate narration audio                 -> audio/
  review    Export narration to review_sheet.csv (or --import edits back)
  premiere  Cut clips + build multi-track Premiere XML -> premiere_sequence.xml
  videopad  Same timeline as a VideoPad project     -> videopad_project.vpj (--simple: V1+A1 only)
  video     Cut clips + join into ONE finished mp4   -> recap_final.mp4
  srt       Subtitles (+ on-screen text .srt)        -> recap_subtitles.srt
  timeline  Write timeline.json (the contract for the Remotion renderer)
  remotion  Render the timeline with Remotion          -> recap_remotion.mp4
  scenes    Check the custom scenes (static check + test render); --demo installs demo scenes
  preview   Open Remotion Studio to look at single scenes
  briefs    Scene authoring: write the prompt for Claude (pass 2) / import SCENE_REPLY.txt; --demo adds demo briefs
  tiktok    Build vertical 9:16 TikTok parts         -> tiktok_out/
  characters  Check characters/ (PNG cut-outs) + make characters/_preview.png
  check     Status report (also writes STATE.md)
  demo      Fill this project with synthetic test media (to test the pipeline / Premiere import)
"""

import argparse
import asyncio
import csv
import glob
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.parse
import uuid
import wave
import atexit
import webbrowser
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts", ".mts",
              ".m2ts", ".wmv", ".flv", ".mpg", ".mpeg")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff")
MUSIC_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac")
TEXT_SUB_CODECS = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text",
                   "subviewer", "microdvd"}
IMAGE_SUB_CODECS = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub",
                    "dvb_teletext"}

AUDIO_DIR = "audio"
CLIPS_DIR = "clips"
SHEETS_DIR = "sheets"
SUBS_DIR = "subs"
FOOTAGE_DIR = "footage"
IMAGES_DIR = "images"
MUSIC_DIR = "music"
GFX_DIR = "gfx"
PREVIEW_DIR = "audio_preview"
TIKTOK_OUT = "tiktok_out"
TIKTOK_TEMP = "tiktok_temp"
XML_OUT = "premiere_sequence.xml"
FINAL_OUT = "recap_final.mp4"
SRT_OUT = "recap_subtitles.srt"
ONSCREEN_SRT = "recap_onscreen.srt"
CHAPTERS_OUT = "chapters.txt"
SHOT_CSV = "shot_manifest.csv"
SHOTS_STATE = "shots.json"
CREDITS_OUT = "credits.txt"
REVIEW_CSV = "review_sheet.csv"
STATE_MD = "STATE.md"
CONFIG_FILE = "config.json"
PROJECT_FILE = "project.json"

MODULES = [
    ("movie_recap", "Movie recap      (one film file + its subtitles)"),
    ("show_recap", "Show recap       (many episode files)"),
    ("nba_minidoc", "NBA mini-doc     (collected clips + stills, chapters)"),
    ("nba_story", "NBA story        (shorter, hook + arc)"),
    ("real_story", "Real story       (mostly stills, news clips)"),
    ("ranking", "Ranking / top-N  (countdown with number graphics)"),
    ("comic_recap", "Comic / manga recap (.cbz .cbr .pdf -> panels, zooms + swipes)"),
]
RECAP_MODULES = ("movie_recap", "show_recap", "comic_recap")
DEFAULT_TARGETS = {"movie_recap": "10:00", "show_recap": "10:00", "nba_minidoc": "8:00",
                   "nba_story": "3:00", "real_story": "6:00", "ranking": "6:00", "comic_recap": "8:00"}

DEFAULT_CONFIG = {
    "fps": 24,
    "width": 1920,
    "height": 1080,
    "sample_rate": 48000,
    "fill": "pad",              # pad = black bars | blur = blurred copy of the clip fills the frame
    "keep_audio_volume": 0.30,  # used when a segment has "keep_audio": true
    "music_volume": 0.12,
    "tts": {
        "engine": "",
        "edge_voice": "en-US-ChristopherNeural",
        "edge_rate": "+0%",
        "elevenlabs_voice_id": "",
        "elevenlabs_model": "eleven_v3",
        "elevenlabs_stability": 0.5,
        "minimax_voice": "male-qn-qingse",
        "kokoro_voice": "am_michael",
        "kokoro_speed": 1.0,
        "kokoro_voice2": "",          # optional: blend a second voice in
        "kokoro_mix": 0,              # percent of voice 2 (0 = off)
        "kokoro_sentence_pause": 0.25,   # seconds of silence after a sentence (lower = more conversational)
        "kokoro_clause_pause": 0.1,      # seconds after a comma / clause
        # ---- Chatterbox (local, PyTorch, voice cloning, Turbo tags) ----
        "chatterbox_variant": "turbo",   # turbo (350M, [laugh] tags) | english (500M, exaggeration) | multilingual (23 languages)
        "chatterbox_voice": "",          # reference clip for zero-shot cloning: file in voices/ or a full path ("" = built-in voice)
        "chatterbox_language": "en",     # multilingual only
        "chatterbox_exaggeration": 0.5,  # english/multilingual: emotion intensity 0.25 (flat) .. 2.0 (dramatic)
        "chatterbox_cfg_weight": 0.5,    # english/multilingual: pacing / adherence (lower = slower, more deliberate)
        "chatterbox_temperature": 0.8,
        "chatterbox_seed": 0,            # 0 = random; a number makes a take repeatable
        "chatterbox_speed": 1.0,         # post-process tempo (pitch is kept)
        "chatterbox_device": "auto",     # auto | cuda | mps | cpu
        "chatterbox_sentence_pause": 0.25,
        # ---- Pocket TTS (Kyutai, 100M, CPU real-time, voice cloning) ----
        "pocket_voice": "alba",          # built-in name, a file in voices/, a path, or an hf:// url
        "pocket_temperature": 0.7,
        "pocket_lsd_steps": 1,           # decoding steps: more = cleaner (slower)
        "pocket_eos_threshold": -4.0,    # higher = stops sooner
        "pocket_speed": 1.0,
        "pocket_sentence_pause": 0.25,
        "tts_normalize": True,           # level every clip to the same loudness (Chatterbox / Pocket)
    },
    "tiktok": {"width": 1080, "height": 1920, "fps": 30},
    "subtitles": {"max_chars_per_line": 42, "max_lines": 2},
    "comic": {
        "panel_mode": "claude",   # claude = Claude decides the panels (boxes in segments.json) | auto = script finds + numbers them
        "snap": True,             # claude mode: nudge Claude's box edges onto the real panel edges when they nearly match
        "pdf_pages": 30,          # pages per PDF part you give to Claude
        "review_height": 1700,    # pixel height of the review pages in that PDF
        "annotate": True,         # draw panel numbers on the review pages
        "zoom": 1.12,             # default push-in strength (1.0 = none)
        "margin": 0.04,           # air around a panel when it fills the frame
        "enter_sec": 0.35,        # length of a swipe / fade / pop entrance
        "page_turn": "slide",     # entrance on a new page: slide | fade | pop | cut
        "same_panel_move": "slide",  # next panel on the same page: slide (toward it) | cut
    },
    "character": {                  # character animation sub-module (PNG cut-outs in characters/)
        "corner_pos": "bottom-right",  # where the character sits over a clip
        "corner_scale": 0.46,       # character height / frame height when over a clip
        "solo_pos": "center",       # solo commentary scene (character on a background)
        "solo_scale": 0.80,
        "max_width": 0.40,          # a corner character never takes more than this share of the frame width
        "solo_max_width": 0.80,
        "margin": 0.03,             # air between the character and the frame edge
        "idle": "talk",             # talk | breathe | bob | float | sway | shake | none  (combine with +)
        "enter": "slide", "exit": "slide",          # over a clip: slide | pop | fade | none
        "solo_enter": "pop", "solo_exit": "fade",
        "enter_sec": 0.35, "exit_sec": 0.25,
        "shadow": True,             # soft drop shadow so the cut-out sits on the footage
        "outline": "",              # "" = off, "#ffffff" = white sticker outline
        "solo_bg": "gradient:#1b2030,#43305f",      # #hex | gradient:#a,#b | image/video file name
        "mouth_threshold": 0.25,    # voice loudness (0-1) that opens the mouth pose
        "codec": "qtrle",           # layer file: qtrle (works everywhere) | png (smaller) | prores (smallest; not for VideoPad)
    },
}

DEFAULT_PROJECT = {
    "module": "movie_recap",
    "topic": "",
    "style": "retell",          # recap modules: retell | commentary | mixed
    "target_length": "",        # "8:00" or minutes, or {"youtube": "8:00", "tiktok_part": "1:00"}
    "platform": "youtube",
    "tts_mode": "plain",        # plain | light | heavy
    "voice_card": "",
    "fact_check": "off",
    "music": False,
    "captions": True,
    "reading": "ltr",           # comic_recap: ltr (western) | rtl (manga)
    "character": {"default": "", "auto": "off"},   # auto: off | commentary (segments with "commentary": true) | all
}


# ====================================================================
# Shared helpers
# ====================================================================
def die(msg):
    print(f"\n[ERROR] {msg}")
    sys.exit(1)


def need(*tools):
    for t in tools:
        if shutil.which(t) is None:
            die(f"'{t}' was not found. Run SETUP.bat (main Recap Studio folder), "
                "then close and reopen this window.")


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception as e:
            print(f"[!] Could not read {CONFIG_FILE} ({e}); using defaults.")
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def load_env():
    """Reads keys.env from this folder, the Projects folder, and the main folder."""
    here = ROOT
    for d in (here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))):
        p = os.path.join(d, "keys.env")
        if not os.path.isfile(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("\"'")
                if v and k not in os.environ:
                    os.environ[k] = v


CFG = load_config()
load_env()
FPS = int(CFG["fps"])
WIDTH = int(CFG["width"])
HEIGHT = int(CFG["height"])
SAMPLE_RATE = int(CFG["sample_rate"])


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def tail(text, n=8):
    return "\n".join(text.strip().splitlines()[-n:])


def parse_time(value):
    """Accepts 12.5, '12.5', 'MM:SS', 'HH:MM:SS(.ms)' -> float seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    secs = 0.0
    for p in str(value).strip().split(":"):
        secs = secs * 60 + float(p)
    return secs


def fmt_dash(seconds):
    s = int(seconds)
    return f"{s // 3600:02d}-{(s % 3600) // 60:02d}-{s % 60:02d}"


def get_duration(path):
    res = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", path])
    try:
        return float(res.stdout.strip())
    except ValueError:
        raise RuntimeError(f"ffprobe could not read '{path}':\n{tail(res.stderr)}")


def get_audio_info(path):
    res = run(["ffprobe", "-v", "error", "-select_streams", "a:0",
               "-show_entries", "stream=sample_rate,channels", "-of", "json", path])
    try:
        s = json.loads(res.stdout)["streams"][0]
        return int(s["sample_rate"]), int(s["channels"])
    except Exception:
        return 44100, 1


def find_video(override=None):
    if override:
        if not os.path.isfile(override):
            die(f"Video not found: {override}")
        return override
    vids = [f for f in os.listdir(".")
            if f.lower().endswith(VIDEO_EXTS) and os.path.isfile(f)
            and not f.lower().startswith("tiktok_")]
    if not vids and os.path.isdir(FOOTAGE_DIR):
        vids = [os.path.join(FOOTAGE_DIR, f) for f in os.listdir(FOOTAGE_DIR)
                if f.lower().endswith(VIDEO_EXTS) and os.path.isfile(os.path.join(FOOTAGE_DIR, f))
                and not f.lower().startswith("tiktok_")]
    if not vids:
        die("No video found. Put the film in the footage/ folder (or in the project folder).")
    vids.sort(key=os.path.getsize, reverse=True)
    if len(vids) > 1:
        print(f"[i] Several videos found, using the largest: {vids[0]}")
    return vids[0]


def find_json(override=None):
    if override:
        if not os.path.isfile(override):
            die(f"JSON not found: {override}")
        return override
    if os.path.isfile("segments.json"):
        return "segments.json"
    hits = glob.glob("*segments*.json")
    if not hits:
        hits = [h for h in glob.glob("*.json") if h.lower() != CONFIG_FILE]
    if not hits:
        die("No segments.json in this folder. Paste the JSON from Claude into segments.json.")
    return hits[0]


def load_data(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}")


def yt_segments(data):
    if isinstance(data, list):
        return data
    return data.get("youtube", []) if isinstance(data, dict) else []


def tiktok_parts(data):
    t = data.get("tiktok", {}) if isinstance(data, dict) else {}
    if isinstance(t, list):
        return {"tiktok": t}
    return t or {}


def all_segments(data):
    """YouTube segments + every TikTok clip, de-duplicated by id."""
    seen, out = set(), []
    pool = list(yt_segments(data))
    for clips in tiktok_parts(data).values():
        pool.extend(clips)
    for seg in pool:
        sid = seg.get("id")
        if sid and sid not in seen:
            seen.add(sid)
            out.append(seg)
    return out


def reveal(path):
    try:
        if os.name == "nt" and os.path.exists(path):
            os.startfile(os.path.abspath(path))  # noqa
    except Exception:
        pass


def progress(done, total, label=""):
    """Machine-readable progress line; the Recap Studio UI turns it into a progress bar."""
    print(f"@@PROGRESS {int(done)} {int(total)} {label}", flush=True)


class Cache:
    """Remembers how each clip was rendered so unchanged clips are skipped."""

    def __init__(self, path):
        self.path = path
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.d = json.load(f)
        except Exception:
            self.d = {}

    def fresh(self, key, value, file):
        return self.d.get(key) == value and os.path.exists(file)

    def set(self, key, value):
        self.d[key] = value
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.d, f)




# ====================================================================
# v2 helpers: project.json, media lookup, probing, fonts, tags
# ====================================================================
def load_project():
    p = json.loads(json.dumps(DEFAULT_PROJECT))
    if os.path.exists(PROJECT_FILE):
        try:
            with open(PROJECT_FILE, "r", encoding="utf-8") as f:
                p.update(json.load(f))
        except Exception as e:
            print(f"[!] Could not read {PROJECT_FILE} ({e}); using defaults.")
    return p


def save_project(p):
    with open(PROJECT_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2, ensure_ascii=False)


PROJECT = load_project()
MODULE = PROJECT.get("module") or "movie_recap"


def parse_target(value, key="youtube"):
    """'8:00' -> 480 s; a bare number means minutes; dict -> pick key. None if not set."""
    if isinstance(value, dict):
        value = value.get(key)
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)) or re.fullmatch(r"\d+(\.\d+)?", str(value).strip()):
            return float(value) * 60.0
        return parse_time(value)
    except Exception:
        return None


def fmt_mmss(sec):
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def find_in(name, *folders):
    """Looks for a file by name in the given folders (and as an absolute path)."""
    if not name:
        return None
    name = str(name).strip().strip('"')
    if os.path.isabs(name) and os.path.isfile(name):
        return name
    for d in folders:
        p = os.path.join(d, name) if d else name
        if os.path.isfile(p):
            return p
    return None


def glob_by_id(folder, sid, exts):
    for ext in exts:
        for pat in (f"{sid}{ext}", f"{sid}{ext.upper()}"):
            p = os.path.join(folder, pat)
            if os.path.isfile(p):
                return p
    return None


def _largest_video_in(folder):
    """Largest source video directly inside `folder` ("." = project folder), else None."""
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    vids = []
    for f in names:
        full = f if folder == "." else os.path.join(folder, f)
        low = f.lower()
        if (low.endswith(VIDEO_EXTS) and os.path.isfile(full)
                and not low.startswith("tiktok_") and low != FINAL_OUT):
            vids.append(full)
    if not vids:
        return None
    vids.sort(key=os.path.getsize, reverse=True)
    return vids[0]


def default_video():
    """The main source video (the film). Looks in the project folder first; for movie / show
    recaps it also looks in footage/ (the UI's Footage tab puts the film there). Else None."""
    found = _largest_video_in(".")
    if not found and MODULE in ("movie_recap", "show_recap"):
        found = _largest_video_in(FOOTAGE_DIR)
    return found


_PROBE = {}


def probe_media(path):
    """-> dict(w, h, dur, has_audio). Cached per run."""
    if path in _PROBE:
        return _PROBE[path]
    info = {"w": 0, "h": 0, "dur": 0.0, "has_audio": False}
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,width,height:format=duration", "-of", "json", path])
    try:
        d = json.loads(r.stdout or "{}")
        for s in d.get("streams", []):
            if s.get("codec_type") == "video" and not info["w"]:
                info["w"], info["h"] = int(s.get("width") or 0), int(s.get("height") or 0)
            if s.get("codec_type") == "audio":
                info["has_audio"] = True
        info["dur"] = float((d.get("format") or {}).get("duration") or 0)
    except Exception:
        pass
    _PROBE[path] = info
    return info


def has_motion_scene(seg):
    """True when the script gives this segment a custom motion scene (Phase 3): it needs no footage."""
    m = seg.get("motion") if isinstance(seg, dict) else None
    return isinstance(m, dict) and bool(str(m.get("brief") or "").strip())


def seg_media(seg, default_vid):
    """Decides where a segment's picture comes from.
    -> {"kind": video|image|slate, "file", "start", "avail", "why"}
    A solo commentary scene (character in the middle) gets its background instead, with "solo": True."""
    req = char_request(seg)
    if req and req["_solo"] == "forced":
        return char_solo_media(req)
    m = _seg_media_base(seg, default_vid)
    if (req and req["_solo"] == "auto" and m["kind"] == "slate"
            and str(m.get("why", "")).startswith(("no footage yet", "no page/focus"))):
        return char_solo_media(req)
    return m


def _seg_media_base(seg, default_vid):
    sid = seg.get("id", "?")
    if MODULE == "comic_recap" and any(seg.get(k) is not None for k in ("page", "focus", "panel", "panels")):
        return comic_media(seg)
    # 1. a still image
    if seg.get("image"):
        f = find_in(seg["image"], IMAGES_DIR, FOOTAGE_DIR, ".")
        if f:
            return {"kind": "image", "file": f, "start": 0.0, "avail": 0.0}
        return {"kind": "slate", "why": f"image '{seg['image']}' not found in images/"}
    # 2. explicit source file
    f = None
    if seg.get("src"):
        f = find_in(seg["src"], FOOTAGE_DIR, ".")
        if not f:
            return {"kind": "slate", "why": f"src '{seg['src']}' not found in footage/"}
    # 3. collected shot named after the segment id
    if not f:
        f = glob_by_id(FOOTAGE_DIR, sid, VIDEO_EXTS)
    # 4. a still named after the segment id
    if not f:
        im = glob_by_id(IMAGES_DIR, sid, IMAGE_EXTS)
        if im:
            return {"kind": "image", "file": im, "start": 0.0, "avail": 0.0}
    # 5. the one big source video (movie / episode recaps)
    if not f and default_vid and seg.get("src_start"):
        f = default_vid
    if not f:
        if MODULE == "comic_recap":
            return {"kind": "slate", "why": "no page/focus in this segment - it looks like a movie-recap segment "
                                            "(src_start/src_end). Ask Claude again with the COMIC prompt + the PDF."}
        return {"kind": "slate", "why": "no footage yet"}
    try:
        start = parse_time(seg["src_start"]) if seg.get("src_start") else 0.0
        dur = probe_media(f)["dur"]
        end = parse_time(seg["src_end"]) if seg.get("src_end") else dur
    except Exception as e:
        return {"kind": "slate", "why": f"bad time range ({e})"}
    if end <= start:
        return {"kind": "slate", "why": f"src_end must be after src_start ({start}->{end})"}
    return {"kind": "video", "file": f, "start": start, "avail": end - start}


def iter_segments(data):
    """Every segment dict (youtube + tiktok parts), in file order, by reference."""
    out = list(yt_segments(data))
    for clips in tiktok_parts(data).values():
        out.extend(clips)
    return [s for s in out if isinstance(s, dict)]


# ---- fonts (for slates, number cards, timestamps) ----
def find_font(bold=True):
    cands = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def ff_path(p):
    """Escape a path for use inside an ffmpeg filter option."""
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def font_opt():
    f = find_font()
    return f"fontfile='{ff_path(f)}':" if f else ""


def write_textfile(name, text):
    os.makedirs(GFX_DIR, exist_ok=True)
    p = f"{GFX_DIR}/_{name}.txt"
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


# ---- tags ----
TAG_RE = re.compile(r"\[[^\]\n]{1,40}\]")


def strip_tags(text):
    t = TAG_RE.sub(" ", str(text))
    return " ".join(t.replace("*", "").split())


def count_tags(text):
    return len(TAG_RE.findall(str(text)))


def est_speech_seconds(text):
    """~2.5 words per second, plus 0.6 s for each [pause]."""
    words = len(strip_tags(text).split())
    pauses = len(re.findall(r"\[(?:long )?pause\]", str(text), re.I))
    return words / 2.5 + 0.6 * pauses


# ---- scale / pad / blur-fill ----
def fit_graph(sw, sh, W, H, fill, src="[0:v]", dst="[f]"):
    """Filter graph that makes any picture W x H.
    Same aspect -> plain scale. Different -> black bars (pad) or blurred background (blur)."""
    if sw <= 0 or sh <= 0:
        return (f"{src}scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2{dst}")
    if abs((sw / sh) / (W / H) - 1.0) < 0.02:
        return f"{src}scale={W}:{H}{dst}"
    if fill == "blur":
        return (f"{src}split[bgs][fgs];"
                f"[bgs]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:5[bgb];"
                f"[fgs]scale={W}:{H}:force_original_aspect_ratio=decrease[fgb];"
                f"[bgb][fgb]overlay=(W-w)/2:(H-h)/2{dst}")
    return (f"{src}scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2{dst}")


def file_sig(path):
    try:
        st = os.stat(path)
        return f"{os.path.abspath(path)}:{st.st_size}:{st.st_mtime_ns}"
    except OSError:
        return f"{path}:missing"


# ====================================================================
# STEP 1: subtitles
# ====================================================================
def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def find_all_videos():
    """Every source video: the project root plus footage/ (episodes), natural-sorted by file name.
    Skips the finished outputs and collected per-segment shots (yt_001.mp4 etc. are tiny anyway)."""
    found = []
    for d in (".", FOOTAGE_DIR):
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            full = os.path.join(d, f)
            low = f.lower()
            if (os.path.isfile(full) and low.endswith(VIDEO_EXTS)
                    and not low.startswith("tiktok_") and low != FINAL_OUT):
                found.append(full)
    found.sort(key=lambda p: natural_key(os.path.basename(p)))
    return found


def extract_subs_from(video):
    """Extract every text subtitle track of one video into subs/. -> list of (srt_path, language)."""
    probe = run(["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries",
                 "stream=index,codec_name:stream_tags=language,title", "-of", "json", video])
    streams = json.loads(probe.stdout or "{}").get("streams", [])
    if not streams:
        print("  no embedded subtitle tracks.")
        return []
    print(f"  {len(streams)} subtitle track(s):")
    os.makedirs(SUBS_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(video))[0]
    safe = lambda s: "".join(c if c.isalnum() or c in "-_" else "_" for c in s)
    saved = []
    for n, s in enumerate(streams):
        codec = s.get("codec_name", "")
        t = s.get("tags", {})
        lang = t.get("language", "und")
        print(f"    #{n}: {lang}  {codec}  {t.get('title', '')}")
        label = safe(f"{base}.{n}.{lang}" + (f".{t['title']}" if t.get("title") else ""))
        if codec in IMAGE_SUB_CODECS:
            print(f"    skipping #{n} ({codec}): picture-based subs need OCR.")
            continue
        out = f"{SUBS_DIR}/{label}.srt"
        r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", video,
                 "-map", f"0:s:{n}", "-c:s", "srt", out])
        if r.returncode == 0:
            print(f"    saved {out}")
            saved.append((out, lang))
        else:
            print(f"    could not convert #{n} ({codec}): {r.stderr.strip()[:200]}")
        if codec in ("ass", "ssa"):
            out2 = f"{SUBS_DIR}/{label}.ass"
            r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", video,
                     "-map", f"0:s:{n}", "-c:s", "copy", out2])
            if r.returncode == 0:
                print(f"    saved {out2} (may include speaker names)")
    return saved


def pick_english(saved):
    """Best English track from [(path, lang)]: eng/en first, then undefined, else the first track."""
    for path, lang in saved:
        if lang.lower().startswith("en"):
            return path
    for path, lang in saved:
        if lang.lower() in ("und", ""):
            return path
    return saved[0][0] if saved else None


def step_subs(args):
    """Subtitles for ONE video (--video) or for EVERY episode found in the project root + footage/."""
    need("ffmpeg", "ffprobe")
    videos = [find_video(args.video)] if args.video else find_all_videos()
    if not videos:
        die("No video found. Put the film / episodes in footage/ (or the project folder), then run this again.")
    print(f"Found {len(videos)} video(s):")
    for v in videos:
        print(f"  {v}")
    chosen, missing = [], []
    for i, video in enumerate(videos, 1):
        progress(i - 1, len(videos), f"Subtitles: {os.path.basename(video)}")
        print(f"\n[{i}/{len(videos)}] {os.path.basename(video)}")
        saved = extract_subs_from(video)
        best = pick_english(saved)
        if not best:
            # a hand-downloaded subtitle named after the video (Episode03.srt for Episode03.mkv)
            base = os.path.splitext(os.path.basename(video))[0]
            hand = sorted(h for h in glob.glob(f"{SUBS_DIR}/{glob.escape(base)}*.srt")
                          if not os.path.basename(h).startswith("ALL_EPISODES"))
            if hand:
                best = hand[0]
                print(f"  using your own subtitle file {best}")
        if best:
            chosen.append((os.path.basename(video), best))
        else:
            missing.append(os.path.basename(video))

    # one combined file for Claude: every episode's English subtitles, labelled with the exact file name
    if len(videos) > 1 and chosen:
        combined = f"{SUBS_DIR}/ALL_EPISODES_for_claude.txt"
        with open(combined, "w", encoding="utf-8") as out:
            out.write("Subtitles for every episode. Each block starts with the EPISODE FILE name; "
                      "use that exact name as \"src\" for segments from it.\n"
                      "Timestamps below are the real ones for that episode.\n\n")
            for vname, srt in chosen:
                out.write(f"########## EPISODE FILE: {vname} ##########\n\n")
                with open(srt, "r", encoding="utf-8", errors="replace") as f:
                    out.write(f.read().strip() + "\n\n")
        print(f"\nWrote {combined}  <- attach THIS one file to Claude.")
    os.makedirs(SUBS_DIR, exist_ok=True)
    with open(f"{SUBS_DIR}/_episodes.txt", "w", encoding="utf-8") as ep:
        for vname, srt in chosen:
            ep.write(f"{vname}\t{os.path.basename(srt)}\n")
        for vname in missing:
            ep.write(f"{vname}\t(NO SUBTITLES)\n")

    progress(len(videos), len(videos), "Subtitles done")
    print(f"\nDone. {len(chosen)} of {len(videos)} video(s) have English-ish subtitles in subs/.")
    if missing:
        print("[!] No usable text subtitles in: " + ", ".join(missing))
        print("    Download an English .srt for each and put it in subs/ named like the video "
              "(e.g. Episode03.srt for Episode03.mkv).")
    reveal(SUBS_DIR)




# ====================================================================
# STEP: init (new project questions) + module name for MENU.bat
# ====================================================================
def ask_text(prompt, default=""):
    if os.environ.get("RECAP_NONINTERACTIVE"):
        return default
    raw = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return raw or default


def step_module(args):
    print(MODULE)


def step_init(args):
    p = load_project()
    print("\n=== New project setup (Enter = keep the suggestion) ===")
    keys = [k for k, _ in MODULES]
    default = keys.index(p["module"]) + 1 if p.get("module") in keys else 1
    p["module"] = ask_choice("What kind of video?", MODULES, default)
    p["topic"] = ask_text("Topic / title (e.g. 'Kobe 81-point game')", p.get("topic", ""))
    if p["module"] in RECAP_MODULES:
        p["style"] = ask_choice("Narration style:", [
            ("retell", "Retell      (what happens, scene by scene)"),
            ("commentary", "Commentary  (analysis: themes, mistakes, meaning)"),
            ("mixed", "Mixed       (retell + short analysis beats)")], 1)
    if p["module"] == "comic_recap":
        p["reading"] = ask_choice("Reading direction of the comic:", [
            ("ltr", "Left to right  (western comics, manhwa, webtoons)"),
            ("rtl", "Right to left  (Japanese manga)")], 1)
    p["target_length"] = ask_text("Target length of the final video (e.g. 8:00, or minutes; blank = module default)",
                                  str(p.get("target_length") or ""))
    p["platform"] = ask_choice("Main platform:", [("youtube", "YouTube"), ("tiktok", "TikTok"),
                                                  ("both", "Both")], 1)
    p["tts_mode"] = ask_choice("Voice text style (ElevenLabs v3 tags):", [
        ("plain", "plain  - no tags (Edge-TTS / safest)"),
        ("light", "light  - a few emotion tags on key beats"),
        ("heavy", "heavy  - tags on most segments")], 1)
    if p["tts_mode"] != "plain":
        p["voice_card"] = ask_text("Voice card (tone/pacing/allowed tags)",
                                   p.get("voice_card") or "calm documentary narrator; allowed tags: [excited] [whispers] [sad] [softly] [dramatic] [warmly] [pause]")
    p["music"] = ask_choice("Background music bed (put tracks in music/)?",
                            [(True, "yes"), (False, "no")], 2)
    p["captions"] = True
    save_project(p)
    for d in (FOOTAGE_DIR, IMAGES_DIR, MUSIC_DIR):
        os.makedirs(d, exist_ok=True)

    # keep only the prompt file for the chosen module
    chosen = f"PASTE_THIS_TO_CLAUDE_{p['module']}.txt"
    if os.path.exists(chosen):
        shutil.copyfile(chosen, "PASTE_THIS_TO_CLAUDE.txt")
    for f in glob.glob("PASTE_THIS_TO_CLAUDE_*.txt"):
        try:
            os.remove(f)
        except OSError:
            pass
    tgt = p["target_length"] or DEFAULT_TARGETS.get(p["module"], "")
    print(f"\n[OK] project.json written. Module: {p['module']} | target length: {tgt}")
    print("Next: open PASTE_THIS_TO_CLAUDE.txt - it is the prompt for this project type.")


# ====================================================================
# Contact sheets
# ====================================================================
def make_sheet(file, start, dur, cols, rows, width, out, stamp=True):
    n = cols * rows
    vf = f"fps={n}/{dur:.3f},scale={width}:-1"
    if stamp and find_font():
        vf += (f",drawtext={font_opt()}text='%{{pts\\:hms\\:{start:.2f}}}':x=6:y=h-th-6:"
               f"fontsize=20:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=3")
    vf += f",tile={cols}x{rows}"
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
             "-i", file, "-vf", vf, "-frames:v", "1", "-q:v", "3", out])
    if (r.returncode != 0 or not os.path.exists(out)) and stamp:
        return make_sheet(file, start, dur, cols, rows, width, out, stamp=False)
    return r.returncode == 0 and os.path.exists(out), tail(r.stderr, 4)


def step_sheets(args):
    if MODULE == "comic_recap":
        print("Comic projects do not need contact sheets: the numbered PDF from 'Import comic' does that job.")
        return
    need("ffmpeg", "ffprobe")
    jpath = find_json(args.json)
    data = load_data(jpath)
    dv = args.video if args.video else default_video()
    print(f"JSON : {jpath}\n")
    os.makedirs(SHEETS_DIR, exist_ok=True)

    flagged = made = 0
    nv = [x for x in yt_segments(data) if x.get("need_visual")]
    for k_nv, s in enumerate(nv):
        progress(k_nv, len(nv), f"Contact sheet {s.get('id', '?')}")
        if not s.get("need_visual"):
            continue
        flagged += 1
        m = seg_media(s, dv)
        if m["kind"] != "video":
            print(f"[-] {s['id']}: {m.get('why') or m['kind']} - no sheet")
            continue
        start, dur = m["start"], max(m["avail"], 1)
        cols, rows, width = (4, 4, 400) if dur > 40 else (3, 2, 480)
        out = f"{SHEETS_DIR}/{s['id']}_{fmt_dash(start)}.jpg"
        if os.path.exists(out) and not args.force:
            print(f"[-] {out} already exists (skipping)")
            continue
        print(f"[+] {s['id']}  {fmt_mmss(start)} -> {fmt_mmss(start + dur)}  ({os.path.basename(m['file'])})")
        ok, err = make_sheet(m["file"], start, dur, cols, rows, width, out)
        if not ok:
            print(f"    [!] failed: {err}")
            continue
        made += 1

    if flagged == 0:
        print("No segments with \"need_visual\": true found in the JSON.")
    else:
        print(f"\nDone. {made} new sheet(s) in sheets/ - upload them to Claude.")
        reveal(SHEETS_DIR)


def index_file(path, force=False, label=None):
    """Contact sheet(s) for a whole footage file; timestamps are burned into every tile."""
    info = probe_media(path)
    dur = info["dur"]
    if dur <= 0:
        print(f"[!] could not read {path}")
        return []
    stem = label or re.sub(r"[^A-Za-z0-9_-]+", "_", os.path.splitext(os.path.basename(path))[0])
    n_sheets = min(8, max(1, math.ceil(dur / 300)))
    chunk = dur / n_sheets
    made = []
    os.makedirs(SHEETS_DIR, exist_ok=True)
    for i in range(n_sheets):
        start = i * chunk
        out = f"{SHEETS_DIR}/footage_{stem}_{fmt_dash(start)}.jpg"
        if os.path.exists(out) and not force:
            made.append(out)
            continue
        ok, err = make_sheet(path, start, chunk, 4, 4, 400, out)
        if ok:
            made.append(out)
        else:
            print(f"    [!] sheet failed: {err}")
    return made


def step_index(args):
    need("ffmpeg", "ffprobe")
    todo = []
    if os.path.isdir(FOOTAGE_DIR):
        todo = [os.path.join(FOOTAGE_DIR, f) for f in sorted(os.listdir(FOOTAGE_DIR))
                if f.lower().endswith(VIDEO_EXTS)]
    dv = default_video()
    if dv and dv not in todo:
        todo.insert(0, dv)
    if not todo:
        die("No video files in footage/ (or in the project folder). Drop footage there first.")
    total = 0
    for k_ix, path in enumerate(todo):
        progress(k_ix, len(todo), f"Indexing {os.path.basename(path)}")
        info = probe_media(path)
        print(f"[+] {path}  {fmt_mmss(info['dur'])}  {info['w']}x{info['h']}")
        total += len(index_file(path, args.force))
    print(f"\nDone. {total} contact sheet(s) in sheets/ (timestamp is burned into each tile) - "
          "upload them to Claude so it can give exact in/out times.")
    reveal(SHEETS_DIR)


# ====================================================================
# STEP: collect - guided footage collection (yt-dlp or drag & drop)
# ====================================================================
def ytdlp_cmd():
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return None


def search_urls(shot, seg):
    q = [str(x).strip() for x in (shot.get("queries") or []) if str(x).strip()]
    if not q and shot.get("description"):
        q = [shot["description"]]
    kinds = ["https://www.youtube.com/results?search_query=",
             "https://x.com/search?f=video&q=",
             "https://www.google.com/search?tbm=isch&q="]
    urls = []
    for i, text in enumerate(q[:3]):
        urls.append(kinds[i] + urllib.parse.quote_plus(text))
    return urls


def parse_range(rest):
    """'1:42-1:51' / '1:42 1:51' / '1:42 to 1:51' -> ('1:42','1:51') or (None, None)."""
    rest = rest.strip()
    if not rest:
        return None, None
    parts = [p for p in re.split(r"\s*(?:-|to|\s)\s*", rest) if p]
    if len(parts) >= 2:
        try:
            a, b = parse_time(parts[0]), parse_time(parts[1])
            if b > a:
                return parts[0], parts[1]
        except Exception:
            pass
    return None, None


def load_shots():
    try:
        with open(SHOTS_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_shots(d):
    with open(SHOTS_STATE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    write_credits(d)


def write_credits(shots):
    rows = [(k, v) for k, v in shots.items() if v.get("url")]
    if not rows:
        return
    with open(CREDITS_OUT, "w", encoding="utf-8") as f:
        f.write("SOURCE LOG (clip -> where it came from)\n\n")
        for k, v in rows:
            rng = f"  [{v['in']} - {v['out']}]" if v.get("in") else ""
            f.write(f"{k}: {v['url']}{rng}\n")


def download_clip(url, sid, a, b):
    """Downloads ONLY the wanted section with yt-dlp -> footage/<sid>.mp4"""
    cmd = ytdlp_cmd()
    if not cmd:
        print("[!] yt-dlp is not installed. Run SETUP.bat (main folder), then try again.")
        return None
    os.makedirs(FOOTAGE_DIR, exist_ok=True)
    for old in glob.glob(f"{FOOTAGE_DIR}/{sid}.*"):
        try:
            os.remove(old)
        except OSError:
            pass
    base = cmd + ["--no-playlist", "--no-mtime", "-f",
                  "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
                  "--merge-output-format", "mp4", "-o", f"{FOOTAGE_DIR}/{sid}.%(ext)s"]
    section = ["--download-sections", f"*{a}-{b}", "--force-keyframes-at-cuts"] if (a and b) else []
    # YouTube often answers 403 to ffmpeg range downloads for some player clients,
    # so try several clients, then (optionally) fall back to the full video + local trim.
    attempts = [
        ("default client", []),
        ("tv client", ["--extractor-args", "youtube:player_client=tv,web_safari"]),
        ("ios/mweb client", ["--extractor-args", "youtube:player_client=ios,mweb"]),
        ("web client + native downloader", ["--extractor-args", "youtube:player_client=web,default",
                                             "--downloader", "native"]),
    ]
    print("    downloading..." + ("" if a else " (whole video - no time range given)"))
    hits = []
    for label, extra in attempts:
        for old in glob.glob(f"{FOOTAGE_DIR}/{sid}.*"):
            try:
                os.remove(old)
            except OSError:
                pass
        if label != "default client":
            print(f"    retrying with {label}...")
        r = subprocess.run(base + extra + section + [url])
        hits = [h for h in glob.glob(f"{FOOTAGE_DIR}/{sid}.*") if h.lower().endswith(VIDEO_EXTS)]
        if r.returncode == 0 and hits:
            return hits[0]
        if not section and label == "tv client":
            break
    if section:
        ans = "n"
        if not os.environ.get("RECAP_NONINTERACTIVE"):
            ans = input("    Section download keeps failing. Download the WHOLE video and cut it locally "
                        "(can be large/slow)? y/N > ").strip().lower()
        if ans == "y":
            tmp = f"{FOOTAGE_DIR}/_full_{sid}.%(ext)s"
            cmd_full = cmd + ["--no-playlist", "--no-mtime", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
                              "--merge-output-format", "mp4", "-o", tmp, url]
            subprocess.run(cmd_full)
            fulls = glob.glob(f"{FOOTAGE_DIR}/_full_{sid}.*")
            if fulls:
                out = f"{FOOTAGE_DIR}/{sid}.mp4"
                subprocess.run(["ffmpeg", "-y", "-ss", str(parse_time(a)), "-to", str(parse_time(b)),
                                "-i", fulls[0], "-c:v", "libx264", "-c:a", "aac", out])
                for f_ in fulls:
                    try:
                        os.remove(f_)
                    except OSError:
                        pass
                if os.path.exists(out):
                    return out
    print("    [!] download failed (YouTube is blocking it).")
    print("        Fixes: 1) run  yt-dlp -U   2) install Deno (winget install DenoLand.Deno) - yt-dlp needs a JS runtime")
    print("               3) or download the clip by hand and drag the file here.")
    return None
    return hits[0]


def step_collect(args):
    need("ffmpeg", "ffprobe")
    data = load_data(find_json(args.json))
    segs = [s for s in iter_segments(data)]
    seen, uniq = set(), []
    for s in segs:
        if s.get("id") and s["id"] not in seen:
            seen.add(s["id"])
            uniq.append(s)
    dv = default_video()
    shots = load_shots()
    missing = []
    for s in uniq:
        m = seg_media(s, dv)
        if m["kind"] == "slate" and not has_motion_scene(s):
            st = shots.get(s["id"], {}).get("status")
            if st == "skipped" and not args.retry:
                continue
            missing.append(s)
    print(f"{len(uniq)} segments, {len(missing)} still need footage.")
    if not missing:
        print("Nothing to collect - every segment has footage or a still.")
        write_shot_manifest(uniq, dv)
        return
    if not shots.get("_notice"):
        print("\nNote: downloading clips may breach some sites' terms, and heavy use of copyrighted "
              "footage with thin commentary can get claims. Your call - this message shows once.")
        shots["_notice"] = {"status": "shown"}
        save_shots(shots)
    print("\nFor each shot: paste a URL (optionally with a time range like  https://... 1:42-1:51 ),")
    print("or drag a video/image file into this window.  Enter = skip,  b = reopen search tabs,  q = quit.\n")

    for n, s in enumerate(missing, 1):
        sid = s["id"]
        shot = s.get("shot") or {}
        print("-" * 64)
        print(f"[{n}/{len(missing)}] {sid}")
        print(f"  Narration : {strip_tags(s.get('narration', ''))[:160]}")
        if shot.get("description"):
            print(f"  Need      : {shot['description']}")
        for i, qtxt in enumerate(shot.get("queries") or [], 1):
            print(f"  Search {i}  : {qtxt}")
        if shot.get("fallback"):
            print(f"  Fallback  : {shot['fallback']}")
        urls = search_urls(shot, s)
        if urls:
            for u in urls:
                webbrowser.open_new_tab(u)
        while True:
            raw = input("  URL [range] / file / Enter=skip / b / q > ").strip().strip('"')
            low = raw.lower()
            if low == "q":
                save_shots(shots)
                print("Saved. Run collect again to resume.")
                write_shot_manifest(uniq, dv)
                return
            if low == "b":
                for u in urls:
                    webbrowser.open_new_tab(u)
                continue
            if not raw:
                shots[sid] = {"status": "skipped"}
                save_shots(shots)
                break
            if os.path.isfile(raw):
                ext = os.path.splitext(raw)[1].lower()
                is_img = ext in IMAGE_EXTS
                dest_dir = IMAGES_DIR if is_img else FOOTAGE_DIR
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, sid + ext)
                shutil.copyfile(raw, dest)
                shots[sid] = {"status": "done", "file": dest, "url": "", "note": "dragged file"}
                save_shots(shots)
                print(f"    saved -> {dest}")
                break
            mt = re.match(r"(https?://\S+)\s*(.*)$", raw)
            if not mt:
                print("    That is not a URL or a file. Try again (Enter = skip).")
                continue
            url, rest = mt.group(1), mt.group(2)
            if os.path.splitext(url.split("?")[0])[1].lower() in IMAGE_EXTS:
                try:
                    import requests
                    r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
                    ext = os.path.splitext(url.split("?")[0])[1].lower()
                    os.makedirs(IMAGES_DIR, exist_ok=True)
                    dest = os.path.join(IMAGES_DIR, sid + ext)
                    with open(dest, "wb") as f:
                        f.write(r.content)
                    shots[sid] = {"status": "done", "file": dest, "url": url}
                    save_shots(shots)
                    print(f"    saved -> {dest}")
                    break
                except Exception as e:
                    print(f"    [!] image download failed: {e}")
                    continue
            a, b = parse_range(rest)
            if rest.strip() and not a:
                print("    Could not read the time range - use start-end like 1:42-1:51")
                continue
            path = download_clip(url, sid, a, b)
            if not path:
                continue
            info = probe_media(path)
            shots[sid] = {"status": "done", "file": path, "url": url, "in": a or "", "out": b or ""}
            save_shots(shots)
            print(f"    saved -> {path}  ({fmt_mmss(info['dur'])}, {info['w']}x{info['h']})")
            if not a and info["dur"] > 90:
                made = index_file(path, True, label=sid)
                print(f"    long video: contact sheet(s) made in sheets/ - send them to Claude "
                      f"for exact in/out times, then trim/cut with the timestamps.")
            break

    save_shots(shots)
    write_shot_manifest(uniq, dv)
    print("\nDone with this pass. Run collect again any time to resume skipped shots (--retry for those).")


def step_missing(args):
    """Print a JSON list of the segments that still need footage (for the web UI)."""
    data = load_data(find_json(args.json))
    seen, uniq = set(), []
    for s in iter_segments(data):
        if s.get("id") and s["id"] not in seen:
            seen.add(s["id"])
            uniq.append(s)
    dv = default_video()
    shots = load_shots()
    out = []
    for s in uniq:
        m = seg_media(s, dv)
        sh = s.get("shot") or {}
        st = shots.get(s["id"], {}).get("status")
        out.append({
            "id": s["id"],
            "missing": m["kind"] == "slate" and not has_motion_scene(s),
            "why": m.get("why", ""),
            "status": st or "",
            "narration": strip_tags(s.get("narration", ""))[:200],
            "description": sh.get("description", ""),
            "queries": sh.get("queries") or [],
            "fallback": sh.get("fallback", ""),
        })
    print(json.dumps(out, ensure_ascii=False))


def step_collect_one(args):
    """Non-interactive single-shot collection (for the web UI)."""
    need("ffmpeg", "ffprobe")
    data = load_data(find_json(args.json))
    seen, segs = set(), []
    for s in iter_segments(data):
        if s.get("id") and s["id"] not in seen:
            seen.add(s["id"])
            segs.append(s)
    seg = next((s for s in segs if s.get("id") == args.id), None)
    if seg is None:
        die(f"No segment with id '{args.id}'.")
    sid = seg["id"]
    shots = load_shots()
    dv = default_video()

    if args.skip:
        shots[sid] = {"status": "skipped"}
        save_shots(shots)
        write_shot_manifest(segs, dv)
        print(json.dumps({"id": sid, "status": "skipped"}))
        return

    if args.file:
        if not os.path.isfile(args.file):
            die(f"File not found: {args.file}")
        ext = os.path.splitext(args.file)[1].lower()
        dest_dir = IMAGES_DIR if ext in IMAGE_EXTS else FOOTAGE_DIR
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, sid + ext)
        shutil.copyfile(args.file, dest)
        shots[sid] = {"status": "done", "file": dest, "url": "", "note": "uploaded file"}
        save_shots(shots)
        write_shot_manifest(segs, dv)
        info = probe_media(dest)
        print(json.dumps({"id": sid, "status": "done", "file": dest,
                          "dur": round(info["dur"], 1), "w": info["w"], "h": info["h"]}))
        return

    if not args.url:
        die("Provide --url (with optional --range 'a-b'), --file, or --skip.")

    url = args.url.strip()
    a, b = None, None
    if args.range:
        a, b = parse_range(args.range)

    if os.path.splitext(url.split("?")[0])[1].lower() in IMAGE_EXTS:
        try:
            import requests
            r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            ext = os.path.splitext(url.split("?")[0])[1].lower()
            os.makedirs(IMAGES_DIR, exist_ok=True)
            dest = os.path.join(IMAGES_DIR, sid + ext)
            with open(dest, "wb") as f:
                f.write(r.content)
            shots[sid] = {"status": "done", "file": dest, "url": url}
            save_shots(shots)
            write_shot_manifest(segs, dv)
            print(json.dumps({"id": sid, "status": "done", "file": dest}))
            return
        except Exception as e:
            die(f"image download failed: {e}")

    path = download_clip(url, sid, a, b)
    if not path:
        die(f"download failed for {url}")
    info = probe_media(path)
    shots[sid] = {"status": "done", "file": path, "url": url, "in": a or "", "out": b or ""}
    save_shots(shots)
    if not a and info["dur"] > 90:
        index_file(path, True, label=sid)
    write_shot_manifest(segs, dv)
    print(json.dumps({"id": sid, "status": "done", "file": path,
                      "dur": round(info["dur"], 1), "w": info["w"], "h": info["h"]}))


def write_shot_manifest(segs, dv, items=None):
    """shot_manifest.csv: one row per segment - where its picture comes from."""
    shots = load_shots()
    rows = []
    for s in segs:
        m = seg_media(s, dv)
        sh = s.get("shot") or {}
        meta = shots.get(s["id"], {})
        rows.append([s["id"], "OK" if m["kind"] != "slate" else "MISSING", m["kind"],
                     m.get("file", ""), fmt_mmss(m["start"]) if m["kind"] == "video" else "",
                     meta.get("url", ""), sh.get("description", ""), "; ".join(sh.get("queries") or []),
                     sh.get("fallback", "")])
    with open(SHOT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "status", "type", "file", "in", "url", "description", "queries", "fallback"])
        w.writerows(rows)
    print(f"[+] {SHOT_CSV}: {sum(1 for r in rows if r[1] == 'OK')} ok, "
          f"{sum(1 for r in rows if r[1] == 'MISSING')} missing")


# ====================================================================
# STEP 3: TTS (Edge / ElevenLabs / MiniMax)
# ====================================================================
EDGE_VOICES = [
    ("en-US-ChristopherNeural", "Christopher (classic recap narrator)"),
    ("en-US-GuyNeural", "Guy (natural / documentary)"),
    ("en-US-EricNeural", "Eric (deep / serious)"),
    ("en-US-JennyNeural", "Jenny (clear female narrator)"),
]
MINIMAX_VOICES = [
    ("male-qn-qingse", "Male Qingse (calm & clear narrator)"),
    ("presenter_male", "Presenter Male (broadcast voice)"),
    ("Wise_Woman", "Wise Woman (mature narrative)"),
    ("audiobook_male_1", "Audiobook Male (deep storyteller)"),
]
KOKORO_VOICES = [   # every English voice in the Kokoro v1.0 model (same list as the hexgrad demo space)
    ("af_heart", "Heart - US female, warm (default of the demo)"), ("af_bella", "Bella - US female, expressive"),
    ("af_nicole", "Nicole - US female, soft"), ("af_sarah", "Sarah - US female, clear"),
    ("af_aoede", "Aoede - US female"), ("af_kore", "Kore - US female"), ("af_alloy", "Alloy - US female"),
    ("af_nova", "Nova - US female"), ("af_sky", "Sky - US female"), ("af_jessica", "Jessica - US female"),
    ("af_river", "River - US female"),
    ("am_michael", "Michael - US male, narrator"), ("am_fenrir", "Fenrir - US male, deep"),
    ("am_puck", "Puck - US male, lively"), ("am_adam", "Adam - US male"), ("am_echo", "Echo - US male"),
    ("am_eric", "Eric - US male"), ("am_liam", "Liam - US male"), ("am_onyx", "Onyx - US male"),
    ("am_santa", "Santa - US male"),
    ("bf_emma", "Emma - UK female"), ("bf_isabella", "Isabella - UK female"), ("bf_alice", "Alice - UK female"),
    ("bf_lily", "Lily - UK female"),
    ("bm_george", "George - UK male, narrator"), ("bm_fable", "Fable - UK male, storyteller"),
    ("bm_lewis", "Lewis - UK male, calm"), ("bm_daniel", "Daniel - UK male"),
]
KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
CHATTERBOX_VARIANTS = [
    ("nano", "Nano 110M - lightest, CPU-friendly, English, [laugh] tags"),
    ("turbo", "Turbo 350M - English, [laugh] [sigh] tags, fastest"),
    ("english", "Original 500M - English, exaggeration + pacing controls"),
    ("multilingual", "Multilingual 500M - 23 languages"),
]
CHATTERBOX_LANGS = [
    ("ar", "Arabic"), ("da", "Danish"), ("de", "German"), ("el", "Greek"), ("en", "English"), ("es", "Spanish"),
    ("fi", "Finnish"), ("fr", "French"), ("he", "Hebrew"), ("hi", "Hindi"), ("it", "Italian"), ("ja", "Japanese"),
    ("ko", "Korean"), ("ms", "Malay"), ("nl", "Dutch"), ("no", "Norwegian"), ("pl", "Polish"), ("pt", "Portuguese"),
    ("ru", "Russian"), ("sv", "Swedish"), ("sw", "Swahili"), ("tr", "Turkish"), ("zh", "Chinese"),
]
# paralinguistic tags the Turbo model performs (anything else in [brackets] is stripped so it is never read aloud)
CHATTERBOX_TAGS = ("laugh", "chuckle", "cough", "sigh", "gasp", "groan", "yawn", "sniff", "clearing_throat")
POCKET_VOICES = [
    ("alba", "Alba"), ("marius", "Marius"), ("javert", "Javert"), ("jean", "Jean"),
    ("fantine", "Fantine"), ("cosette", "Cosette"), ("eponine", "Eponine"), ("azelma", "Azelma"),
]
LOCAL_WORKER_ENGINES = ("chatterbox", "pocket")
ENGINES = [("edge", "Edge-TTS    (free, unlimited)"),
           ("kokoro", "Kokoro      (free, runs on your PC, offline)"),
           ("chatterbox", "Chatterbox  (free, local, voice cloning, emotion + [laugh] tags)"),
           ("pocket", "Pocket TTS  (free, local, CPU-friendly, voice cloning)"),
           ("elevenlabs", "ElevenLabs  (multi-key, premade voices)"),
           ("minimax", "MiniMax     (multi-key, speech-2.6-hd)")]


POOLS = []


class KeyPool:
    def __init__(self, raw):
        self.keys = [k.strip() for k in raw.replace(" ", ",").split(",") if k.strip()]
        self.idx = 0
        POOLS.append(self)

    @property
    def current(self):
        return self.keys[self.idx] if self.keys else None

    def rotate(self):
        if self.idx + 1 < len(self.keys):
            self.idx += 1
            print(f"\n[!] Key failed/quota hit. Switching to key #{self.idx + 1}...")
            return True
        print(f"\n[!] All {len(self.keys)} API key(s) exhausted.")
        return False


def ask_choice(title, options, default=1):
    if os.environ.get("RECAP_NONINTERACTIVE"):
        idx = default - 1 if 1 <= default <= len(options) else 0
        return options[idx][0]
    print(f"\n{title}")
    for i, (_, label) in enumerate(options, 1):
        print(f"  {i}. {label}")
    raw = input(f"Pick a number (Enter = {default}): ").strip()
    idx = int(raw) - 1 if raw.isdigit() and 1 <= int(raw) <= len(options) else default - 1
    return options[idx][0]


def get_keys(env_name, label):
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        print(f"\n[!] No {label} key found. Put it in keys.env as {env_name}=your_key")
        if not os.environ.get("RECAP_NONINTERACTIVE"):
            raw = input(f"Or paste {label} key(s) now (comma-separated): ").strip()
    if not raw:
        die(f"{label} API key is required.")
    return KeyPool(raw)


def make_edge(cfg, pick):
    try:
        import edge_tts
    except ImportError:
        die("edge-tts is not installed. Run SETUP.bat (main folder).")
    t = cfg["tts"]
    if pick:
        t["edge_voice"] = ask_choice("Edge-TTS voices:", EDGE_VOICES)
        save_config(cfg)
    voice, rate = t["edge_voice"], t.get("edge_rate", "+0%")
    print(f"Engine: Edge-TTS | Voice: {voice} | Rate: {rate}")

    def runner(text, out):
        # Streams the audio so the word boundaries can be saved too (animated captions, wordtimes.py).
        async def go():
            try:
                comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
            except TypeError:                                  # older edge-tts: no boundary argument
                comm = edge_tts.Communicate(text, voice, rate=rate)
            bounds, nbytes = [], 0
            with open(out, "wb") as f:
                async for ch in comm.stream():
                    if ch.get("type") == "audio":
                        f.write(ch["data"])
                        nbytes += len(ch["data"])
                    elif ch.get("type") == "WordBoundary":
                        try:
                            bounds.append([ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]])
                        except Exception:
                            pass
            if nbytes == 0:
                raise RuntimeError("Edge-TTS returned no audio")
            return bounds, nbytes
        bounds, nbytes = asyncio.run(go())
        if CUR_SEG_ID and bounds:
            try:
                import wordtimes
                wordtimes.save_raw(ROOT, CUR_SEG_ID, bounds, nbytes)
            except Exception:
                pass
        return True
    return runner


def kokoro_model_dir():
    """Shared folder for the ~350 MB model: <Recap Studio>/models/kokoro (found by walking up from the project)."""
    here = ROOT
    for d in (here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))):
        if all(os.path.isfile(os.path.join(d, "models", "kokoro", f)) for f in KOKORO_FILES):
            return os.path.join(d, "models", "kokoro")
    base = here
    for d in (os.path.dirname(os.path.dirname(here)), os.path.dirname(here), here):
        if os.path.isfile(os.path.join(d, "SETUP.bat")) or os.path.isfile(os.path.join(d, "studio.py")):
            base = d
            break
    return os.path.join(base, "models", "kokoro")


def kokoro_download(folder):
    import requests
    os.makedirs(folder, exist_ok=True)
    for name in KOKORO_FILES:
        dest = os.path.join(folder, name)
        if os.path.isfile(dest) and os.path.getsize(dest) > 1_000_000:
            continue
        print(f"Downloading Kokoro model file {name} (one time only) ...")
        tmp = dest + ".part"
        with requests.get(KOKORO_BASE + name, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        progress(got, total, f"Downloading {name}")
        os.replace(tmp, dest)
    return folder


CUR_SEG_ID = None   # set by step_tts before each clip (None while previewing) so Edge word timings can be saved
SEG_SPEED = 1.0     # set by step_tts before each clip: this segment's "speed" multiplier
SPEED_ENGINES = ("kokoro", "chatterbox", "pocket")   # engines that honour a per-segment "speed"


def seg_speed(seg):
    try:
        v = float(seg.get("speed") or 1.0)
    except (TypeError, ValueError):
        v = 1.0
    return max(0.6, min(1.4, v))


def make_kokoro(cfg, pick):
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
    except ImportError:
        die("Kokoro is not installed. Run SETUP.bat again (or:  pip install kokoro-onnx soundfile).")
    t = cfg["tts"]
    if pick:
        t["kokoro_voice"] = ask_choice("Kokoro voices:", KOKORO_VOICES)
        save_config(cfg)
    voice = t.get("kokoro_voice") or "am_michael"
    speed = float(t.get("kokoro_speed", 1.0) or 1.0)
    voice2 = t.get("kokoro_voice2") or ""
    mix = max(0.0, min(100.0, float(t.get("kokoro_mix", 0) or 0))) / 100.0
    folder = kokoro_model_dir()
    if not all(os.path.isfile(os.path.join(folder, f)) for f in KOKORO_FILES):
        die("The Kokoro model is not downloaded. Double-click SETUP.bat in the main Recap Studio folder and pick Kokoro.")
    k = Kokoro(os.path.join(folder, KOKORO_FILES[0]), os.path.join(folder, KOKORO_FILES[1]))
    style = voice
    if voice2 and voice2 != voice and mix > 0:
        style = k.get_voice_style(voice) * (1 - mix) + k.get_voice_style(voice2) * mix
        print(f"Engine: Kokoro (local) | Voice: {voice} {round((1 - mix) * 100)}% + {voice2} {round(mix * 100)}% | Speed: {speed}")
    else:
        print(f"Engine: Kokoro (local) | Voice: {voice} | Speed: {speed}")
    lang = "en-gb" if voice.startswith("b") else "en-us"
    pause_s = float(t.get("kokoro_sentence_pause", 0.25))
    pause_c = float(t.get("kokoro_clause_pause", 0.1))

    import inspect
    try:
        accepted = set(inspect.signature(k.create).parameters)
    except (TypeError, ValueError):
        accepted = set()
    extra = {}
    if "sentence_pause" in accepted:
        extra["sentence_pause"] = pause_s
    if "clause_pause" in accepted:
        extra["clause_pause"] = pause_c
    if not extra:
        print("[i] Your kokoro-onnx is an older version: the pause settings are ignored. "
              "Run SETUP.bat (or: pip install --upgrade kokoro-onnx) to get them.")

    def runner(text, out):
        samples, sr = k.create(text, voice=style, speed=speed * SEG_SPEED, lang=lang, **extra)
        wav = out + ".wav"
        sf.write(wav, samples, sr)
        r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ac", "1", "-b:a", "128k", "-f", "mp3", out])
        try:
            os.remove(wav)
        except OSError:
            pass
        if r.returncode != 0:
            raise RuntimeError("ffmpeg could not make the mp3: " + tail(r.stderr))
        return True
    return runner


# ---------- local worker engines: Chatterbox + Pocket TTS ----------
def studio_base():
    """The Recap Studio folder (holds venvs/, voices/, models/). Found by walking up from the project."""
    for d in (ROOT, os.path.dirname(ROOT), os.path.dirname(os.path.dirname(ROOT))):
        if os.path.isfile(os.path.join(d, "SETUP.bat")) or os.path.isfile(os.path.join(d, "studio.py")):
            return d
    return ROOT


def engine_python(name):
    base = os.path.join(studio_base(), "venvs", name)
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        p = os.path.join(base, *rel)
        if os.path.isfile(p):
            return p
    return None


def installed_state():
    """models/engines.json written by SETUP.bat ({} on an install that predates it: then nothing is blocked)."""
    try:
        with open(os.path.join(studio_base(), "models", "engines.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def clean_wav_ref(path):
    """Pocket TTS only reads plain 16-bit WAV without the soundfile library. If the clip is anything else
    (mp3, m4a, flac, ogg, or a 24-bit / float wav) convert it once with ffmpeg to voices/_converted/<name>.wav
    (mono, 24 kHz, 16-bit) and use that. If ffmpeg is missing or fails, the original file is used unchanged."""
    try:
        if path.lower().endswith(".wav"):
            with wave.open(path, "rb") as w:
                if w.getsampwidth() == 2:
                    return path
    except Exception:
        pass  # not a readable 16-bit PCM wav -> convert
    if not shutil.which("ffmpeg"):
        return path
    try:
        outdir = os.path.join(os.path.dirname(os.path.abspath(path)), "_converted")
        os.makedirs(outdir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(outdir, f"{stem}.wav")
        if not (os.path.isfile(out) and os.path.getmtime(out) >= os.path.getmtime(path)):
            r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", "24000",
                     "-c:a", "pcm_s16le", out])
            if r.returncode != 0 or not os.path.isfile(out):
                return path
        return out
    except Exception:
        return path


def resolve_voice_ref(value, allow_builtin=False):
    """voices/<name>[.wav|.mp3|.flac|.m4a|.ogg], a full path, an hf:// url or (Pocket) a built-in voice name.
    WAV (16-bit) is the safest format; anything else is converted to WAV automatically (see clean_wav_ref)."""
    v = str(value or "").strip()
    if not v:
        return ""
    if v.startswith(("hf://", "http://", "https://")):
        return v
    if os.path.isabs(v) and os.path.isfile(v):
        return clean_wav_ref(v)
    vd = os.path.join(studio_base(), "voices")
    for cand in (v, v + ".wav", v + ".mp3", v + ".flac", v + ".m4a", v + ".ogg"):
        p = os.path.join(vd, cand)
        if os.path.isfile(p):
            return clean_wav_ref(p)
    if allow_builtin:
        return v
    die(f"Reference voice '{v}' was not found. Put a clean 5-15 second clip in:\n  {vd}\n(or give a full path).")


class TTSWorker:
    """One long-lived process inside the engine's venv; the model stays loaded between clips."""

    def __init__(self, engine, params):
        py = engine_python(engine)
        if not py:
            die(f"{engine} is not installed yet. Double-click SETUP.bat in the main Recap Studio folder and pick it.")
        script = os.path.join(studio_base(), "tts_worker.py")
        if not os.path.isfile(script):
            die(f"tts_worker.py is missing from {studio_base()}.")
        env = dict(os.environ)
        env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
                    "HF_HOME": os.path.join(studio_base(), "models", "hf"), "TOKENIZERS_PARALLELISM": "false"})
        self.engine = engine
        self.proc = subprocess.Popen([py, script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
                                     text=True, encoding="utf-8", bufsize=1, env=env)
        atexit.register(self.close)
        r = self._call({"cmd": "load", "engine": engine, "params": params})
        self.info = r.get("info", engine)

    def _call(self, msg):
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
        except (BrokenPipeError, OSError):
            line = ""
        if not line:
            die(f"The {self.engine} worker stopped unexpectedly. Scroll up for its error message "
                f"(a missing GPU driver or out-of-memory are the usual causes).")
        r = json.loads(line)
        if not r.get("ok"):
            raise RuntimeError(r.get("error", "unknown worker error"))
        return r

    def say(self, text, out, params):
        return self._call({"cmd": "say", "text": text, "out": out, "params": params})

    def close(self):
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


PAUSE_RE = re.compile(r"\[(long )?pause\]", re.I)


def split_for_engine(text, max_chars):
    """-> list of ("text", str) / ("pause", seconds). [pause] / [long pause] become real silence;
    sentences are grouped into chunks <= max_chars (long clips drift or truncate on these models)."""
    out = []
    pos = 0
    pieces = []
    for m in PAUSE_RE.finditer(text):
        pieces.append(("text", text[pos:m.start()]))
        pieces.append(("pause", 1.2 if m.group(1) else 0.6))
        pos = m.end()
    pieces.append(("text", text[pos:]))
    for kind, val in pieces:
        if kind == "pause":
            out.append((kind, val))
            continue
        val = " ".join(val.split())
        if not val:
            continue
        sents = re.split(r"(?<=[.!?\u2026])\s+", val)
        cur = ""
        for sn in sents:
            while len(sn) > max_chars:                      # one monster sentence: cut at a comma / space
                cut = max(sn.rfind(",", 0, max_chars), sn.rfind(";", 0, max_chars), sn.rfind(" ", 0, max_chars))
                cut = cut if cut > 40 else max_chars
                if cur:
                    out.append(("text", cur)); cur = ""
                out.append(("text", sn[:cut + 1].strip()))
                sn = sn[cut + 1:].strip()
            if not sn:
                continue
            if cur and len(cur) + 1 + len(sn) > max_chars:
                out.append(("text", cur)); cur = sn
            else:
                cur = (cur + " " + sn).strip()
        if cur:
            out.append(("text", cur))
    return out


def wav_join(parts, out_wav):
    """parts: [("wav", path) | ("pause", seconds)] -> one mono 16-bit wav (all chunks share one sample rate)."""
    sr = None
    frames = []
    for kind, val in parts:
        if kind == "wav":
            with wave.open(val, "rb") as w:
                if sr is None:
                    sr = w.getframerate()
                frames.append(w.readframes(w.getnframes()))
        else:
            frames.append(None if sr is None else b"\x00\x00" * int(sr * val))
    if sr is None:
        raise RuntimeError("the model returned no audio")
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for f in frames:
            if f:
                w.writeframes(f)
    return sr


def wav_to_mp3(wav, out, speed, normalize):
    """speed uses atempo (keeps pitch); normalize levels clips so a whole video sounds consistent."""
    filters = []
    sp = max(0.5, min(2.0, float(speed or 1.0)))
    if abs(sp - 1.0) > 0.005:
        filters.append(f"atempo={sp:.4f}")
    if normalize:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", wav]
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd += ["-ac", "1", "-ar", "44100", "-b:a", "160k", "-f", "mp3", out]
    r = run(cmd)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg could not make the mp3: " + tail(r.stderr))


def make_worker_runner(worker, base_params, max_chars, pause_s, speed, normalize):
    def runner(text, out):
        chunks = split_for_engine(text, max_chars)
        if not any(k == "text" for k, _ in chunks):
            raise RuntimeError("nothing to speak")
        tmp_dir = out + ".chunks"
        os.makedirs(tmp_dir, exist_ok=True)
        parts = []
        try:
            n = 0
            for i, (kind, val) in enumerate(chunks):
                if kind == "pause":
                    parts.append(("pause", val))
                    continue
                n += 1
                wavp = os.path.join(tmp_dir, f"c{i:03d}.wav")
                worker.say(val, wavp, base_params)
                if parts and parts[-1][0] == "wav":
                    parts.append(("pause", pause_s))      # natural gap between two sentence groups
                parts.append(("wav", wavp))
            joined = os.path.join(tmp_dir, "joined.wav")
            wav_join(parts, joined)
            wav_to_mp3(joined, out, speed * SEG_SPEED, normalize)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return True
    return runner


def make_chatterbox(cfg, pick):
    t = cfg["tts"]
    if pick:
        t["chatterbox_variant"] = ask_choice("Chatterbox model:", CHATTERBOX_VARIANTS)
        if t["chatterbox_variant"] == "multilingual":
            t["chatterbox_language"] = ask_choice("Language:", CHATTERBOX_LANGS, 5)
        save_config(cfg)
    variant = t.get("chatterbox_variant") or "turbo"
    have = installed_state().get("chatterbox")
    if have is not None and variant not in have:
        die(f"The Chatterbox '{variant}' model was not downloaded. Run SETUP.bat, choose Chatterbox and tick it"
            f"{' (installed: ' + ', '.join(have) + ')' if have else ''}.")
    ref = resolve_voice_ref(t.get("chatterbox_voice"))
    params = {
        "variant": variant, "device": t.get("chatterbox_device", "auto"),
        "voice_ref": ref, "language": t.get("chatterbox_language", "en"),
        "exaggeration": t.get("chatterbox_exaggeration", 0.5), "cfg_weight": t.get("chatterbox_cfg_weight", 0.5),
        "temperature": t.get("chatterbox_temperature", 0.8), "seed": t.get("chatterbox_seed", 0),
    }
    print(f"Engine: Chatterbox {variant} | Voice: {os.path.basename(ref) if ref else 'built-in'} "
          f"| Speed: {t.get('chatterbox_speed', 1.0)}")
    print("Loading the model (the first run downloads ~1-3 GB, later runs take 10-30 s) ...")
    worker = TTSWorker("chatterbox", params)
    print(f"[+] {worker.info}")
    if "cpu" in worker.info and variant != "nano":
        print("[i] No GPU found - Chatterbox on CPU is slow (often 30-120 s per clip). "
              "Use Pocket TTS or Kokoro for long videos, or an NVIDIA GPU.")
    return make_worker_runner(worker, params, 300, float(t.get("chatterbox_sentence_pause", 0.25)),
                              float(t.get("chatterbox_speed", 1.0) or 1.0), bool(t.get("tts_normalize", True)))


def make_pocket(cfg, pick):
    t = cfg["tts"]
    if pick:
        t["pocket_voice"] = ask_choice("Pocket TTS voices:", POCKET_VOICES)
        save_config(cfg)
    voice = resolve_voice_ref(t.get("pocket_voice") or "alba", allow_builtin=True)
    params = {
        "voice": voice, "temperature": t.get("pocket_temperature", 0.7),
        "lsd_decode_steps": t.get("pocket_lsd_steps", 1), "eos_threshold": t.get("pocket_eos_threshold", -4.0),
    }
    print(f"Engine: Pocket TTS | Voice: {os.path.basename(voice) if os.path.isfile(voice) else voice} "
          f"| Speed: {t.get('pocket_speed', 1.0)}")
    worker = TTSWorker("pocket", params)
    print(f"[+] {worker.info}")
    return make_worker_runner(worker, params, 500, float(t.get("pocket_sentence_pause", 0.25)),
                              float(t.get("pocket_speed", 1.0) or 1.0), bool(t.get("tts_normalize", True)))


def make_elevenlabs(cfg, pick):
    import requests
    pool = get_keys("ELEVENLABS_API_KEY", "ElevenLabs")
    api = "https://api.elevenlabs.io/v1"
    t = cfg["tts"]
    if pick or not t.get("elevenlabs_voice_id"):
        voices = []
        try:
            r = requests.get(f"{api}/voices", headers={"xi-api-key": pool.current}, timeout=30)
            if r.status_code == 200:
                voices = [v for v in r.json().get("voices", []) if v.get("category") == "premade"]
        except Exception as e:
            print(f"[!] Could not fetch voices: {e}")
        if voices:
            opts = []
            for v in voices:
                lb = v.get("labels") or {}
                d = ", ".join(x for x in (lb.get("gender"), lb.get("accent"), lb.get("description")) if x)
                opts.append((v["voice_id"], v["name"] + (f"  ({d})" if d else "")))
            t["elevenlabs_voice_id"] = ask_choice("ElevenLabs voices (free plan):", opts)
        else:
            t["elevenlabs_voice_id"] = "21m00Tcm4TlvDq8ikWAM"  # Rachel fallback
        save_config(cfg)
    voice_id = t["elevenlabs_voice_id"]
    print(f"Engine: ElevenLabs | Voice ID: {voice_id} | Model: {t.get('elevenlabs_model', 'eleven_v3')} "
          f"| Stability: {t.get('elevenlabs_stability', 0.5)} | Keys: {len(pool.keys)}")
    verify_voice_on_keys(pool, voice_id)

    def runner(text, out):
        payload = {"text": text, "model_id": t.get("elevenlabs_model", "eleven_v3"),
                   "voice_settings": {"stability": float(t.get("elevenlabs_stability", 0.5)),
                                      "similarity_boost": 0.75}}
        waits = 0
        while True:
            r = requests.post(f"{api}/text-to-speech/{voice_id}", json=payload, timeout=120,
                              headers={"xi-api-key": pool.current,
                                       "Content-Type": "application/json",
                                       "Accept": "audio/mpeg"})
            if r.status_code == 200:
                with open(out, "wb") as f:
                    f.write(r.content)
                return True
            if r.status_code in (401, 402, 429):
                if r.status_code == 429 and len(pool.keys) == 1 and waits < 3:
                    waits += 1
                    time.sleep(5)
                    continue
                if not pool.rotate():
                    return False
                time.sleep(1)
                continue
            print(f"\n[!] Failed: {r.status_code} - {r.text[:200]}")
            return False
    return runner


def make_minimax(cfg, pick):
    import requests
    pool = get_keys("MINIMAX_API_KEY", "MiniMax")
    api = "https://api.minimax.io/v1/t2a_v2"
    t = cfg["tts"]
    if pick:
        opts = MINIMAX_VOICES + [("__custom__", "Custom voice_id (type it)")]
        v = ask_choice("MiniMax voices:", opts)
        if v == "__custom__":
            v = input("Enter voice_id: ").strip() or MINIMAX_VOICES[0][0]
        t["minimax_voice"] = v
        save_config(cfg)
    voice_id = t["minimax_voice"]
    print(f"Engine: MiniMax | Voice: {voice_id} | Keys: {len(pool.keys)}")

    def runner(text, out):
        payload = {"model": "speech-2.6-hd", "text": text,
                   "voice_setting": {"voice_id": voice_id, "speed": 1.0, "vol": 1.0},
                   "audio_setting": {"format": "mp3", "sample_rate": 32000}}
        while True:
            r = requests.post(api, json=payload, timeout=120,
                              headers={"Authorization": f"Bearer {pool.current}",
                                       "Content-Type": "application/json"})
            if r.status_code == 200:
                d = r.json()
                audio = (d.get("data") or {}).get("audio")
                if audio:
                    with open(out, "wb") as f:
                        f.write(bytes.fromhex(audio))
                    return True
                msg = (d.get("base_resp") or {}).get("status_msg", "no audio returned")
                print(f"\n[!] MiniMax error: {msg}")
                if not pool.rotate():
                    return False
            elif r.status_code in (401, 402, 429):
                if not pool.rotate():
                    return False
            else:
                print(f"\n[!] Failed: {r.status_code} - {r.text[:200]}")
                return False
    return runner




# ====================================================================
# TTS v2: tag modes, manifest (selective re-voice), preview, review sheet, length report
# ====================================================================
def verify_voice_on_keys(pool, voice_id):
    """Warn if the chosen voice is not usable on every API key (failover would change the voice)."""
    import requests
    if len(pool.keys) < 2:
        return
    bad = []
    for i, k in enumerate(pool.keys, 1):
        try:
            r = requests.get(f"https://api.elevenlabs.io/v1/voices/{voice_id}",
                             headers={"xi-api-key": k}, timeout=20)
            if r.status_code != 200:
                bad.append((i, r.status_code))
        except Exception:
            pass
    if bad:
        print("[!] WARNING: this voice was NOT found on key(s) " +
              ", ".join(f"#{i} (HTTP {c})" for i, c in bad) +
              " - if failover switches to those keys, the voice will change or fail.")
    else:
        print(f"    Voice checked on all {len(pool.keys)} keys: OK (failover keeps the same voice).")


def keeps_tags(engine, cfg):
    """Tags stay in the text only where the engine PERFORMS them (ElevenLabs v3, Chatterbox Turbo) and only
    when project.json tts_mode isn't plain. Every other engine/model would READ THEM ALOUD, so they are stripped."""
    if PROJECT.get("tts_mode", "plain") == "plain":
        return False
    if engine == "elevenlabs":
        return "v3" in str(cfg["tts"].get("elevenlabs_model", "")).lower()
    if engine == "chatterbox":
        return (cfg["tts"].get("chatterbox_variant") or "turbo") in ("turbo", "nano")
    return False


def engine_text(text, engine, cfg):
    """Prepare narration for an engine: keep the tags it performs, strip the rest."""
    t = str(text).replace("*", "")
    if engine == "elevenlabs" and keeps_tags(engine, cfg):
        return " ".join(t.split())
    if engine in LOCAL_WORKER_ENGINES:
        keep = set(CHATTERBOX_TAGS) if keeps_tags(engine, cfg) else set()

        def one(m):
            name = m.group(0)[1:-1].strip().lower().replace(" ", "_")
            if name in ("pause", "long_pause"):
                return m.group(0)                      # becomes real silence in split_for_engine
            return m.group(0) if name in keep else " "
        return " ".join(TAG_RE.sub(one, t).split())
    return strip_tags(t)


def voice_text(seg, engine, cfg):
    return engine_text(str(seg.get("narration", "")).strip(), engine, cfg)


def tts_signature(engine, cfg):
    t = cfg["tts"]
    if engine == "elevenlabs":
        return f"el|{t.get('elevenlabs_voice_id')}|{t.get('elevenlabs_model')}|{t.get('elevenlabs_stability')}"
    if engine == "minimax":
        return f"mm|{t.get('minimax_voice')}"
    if engine == "kokoro":
        return (f"kk|{t.get('kokoro_voice')}|{t.get('kokoro_speed')}|{t.get('kokoro_voice2')}|{t.get('kokoro_mix')}"
                f"|{t.get('kokoro_sentence_pause')}|{t.get('kokoro_clause_pause')}")
    if engine == "chatterbox":
        ref = ""
        try:
            rp = resolve_voice_ref(t.get("chatterbox_voice"))
            ref = f"{os.path.basename(rp)}:{os.path.getsize(rp)}" if rp and os.path.isfile(rp) else rp
        except SystemExit:
            ref = "missing"
        return (f"cb|{t.get('chatterbox_variant')}|{ref}|{t.get('chatterbox_language')}|{t.get('chatterbox_exaggeration')}"
                f"|{t.get('chatterbox_cfg_weight')}|{t.get('chatterbox_temperature')}|{t.get('chatterbox_seed')}"
                f"|{t.get('chatterbox_speed')}|{t.get('chatterbox_sentence_pause')}|{t.get('tts_normalize')}")
    if engine == "pocket":
        pv = str(t.get("pocket_voice"))
        try:
            rp = resolve_voice_ref(pv, allow_builtin=True)
            if os.path.isfile(rp):
                pv = f"{os.path.basename(rp)}:{os.path.getsize(rp)}"
        except SystemExit:
            pass
        return (f"pk|{pv}|{t.get('pocket_temperature')}|{t.get('pocket_lsd_steps')}|{t.get('pocket_eos_threshold')}"
                f"|{t.get('pocket_speed')}|{t.get('pocket_sentence_pause')}|{t.get('tts_normalize')}")
    return f"edge|{t.get('edge_voice')}|{t.get('edge_rate')}"


def h8(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def load_manifest():
    try:
        with open(os.path.join(AUDIO_DIR, "_manifest.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_manifest(m):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with open(os.path.join(AUDIO_DIR, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1)


def gen_with_retry(generate, text, out):
    tmp = out + ".part"
    retried = False
    for attempt in range(3):
        try:
            if generate(text, tmp):
                os.replace(tmp, out)
                return True, retried
        except Exception as e:
            print(f" error: {e}", end="", flush=True)
            time.sleep(1)
        retried = True
    if os.path.exists(tmp):
        os.remove(tmp)
    return False, retried


def step_tts(args):
    jpath = find_json(args.json)
    data = load_data(jpath)
    segs = [s for s in all_segments(data) if str(s.get("narration", "")).strip()]
    if not segs:
        die("No segments with narration found in the JSON.")

    cfg = CFG
    prev = cfg["tts"].get("engine") or ""
    keys_ = [k for k, _ in ENGINES]
    default_ = keys_.index(prev) + 1 if prev in keys_ else 1
    if args.engine:
        cfg["tts"]["engine"] = args.engine
    else:
        cfg["tts"]["engine"] = ask_choice("Which TTS engine do you want to use?", ENGINES, default_)
    save_config(cfg)
    engine = cfg["tts"]["engine"]

    if args.force and os.path.isdir(AUDIO_DIR):
        if not args.yes and input("This deletes ALL audio/*.mp3 and regenerates it. Type YES to confirm: ").strip() != "YES":
            die("Cancelled.")
        for f in glob.glob(os.path.join(AUDIO_DIR, "*.mp3")):
            os.remove(f)
        save_manifest({})

    maker = {"edge": make_edge, "kokoro": make_kokoro, "chatterbox": make_chatterbox, "pocket": make_pocket,
             "elevenlabs": make_elevenlabs, "minimax": make_minimax}.get(engine, make_edge)
    generate = maker(cfg, args.pick)
    sig = tts_signature(engine, cfg)
    tagged = keeps_tags(engine, cfg)
    print(f"Tags: {'KEPT (' + ('Chatterbox Turbo' if engine == 'chatterbox' else 'ElevenLabs v3') + ', mode ' + PROJECT.get('tts_mode', 'plain') + ')' if tagged else 'stripped (plain text goes to the voice)'}")

    only = [x.strip() for x in (args.only or "").split(",") if x.strip()]
    preview = bool(args.preview)
    if preview and not only:
        only = [s["id"] for s in segs[:3]]
        print(f"Preview of the first {len(only)} segments (use --only id1,id2 to pick others).")
    if only:
        known = {s["id"] for s in segs}
        for x in only:
            if x not in known:
                print(f"[!] unknown id '{x}'")
        segs = [s for s in segs if s["id"] in only]
        if not segs:
            die("None of those ids have narration.")

    out_dir = PREVIEW_DIR if preview else AUDIO_DIR
    os.makedirs(out_dir, exist_ok=True)
    man = {} if preview else load_manifest()

    # decide what needs (re)voicing
    plan = []
    resig = []
    for s in segs:
        sid = s["id"]
        text = voice_text(s, engine, cfg)
        out = os.path.join(out_dir, f"{sid}.mp3")
        th = h8(text + (f"|spd{seg_speed(s)}" if engine in SPEED_ENGINES and seg_speed(s) != 1.0 else ""))
        if preview or (only and not preview):
            plan.append((s, text, out, th, "preview" if preview else "re-voice (asked)"))
            continue
        if not os.path.exists(out):
            plan.append((s, text, out, th, "new"))
            continue
        rec = man.get(sid)
        if rec is None:
            man[sid] = {"text": th, "sig": sig}  # old audio of unknown origin: keep it
            continue
        if rec.get("text") != th:
            plan.append((s, text, out, th, "text changed"))
        elif rec.get("sig") != sig:
            resig.append((s, text, out, th, "voice/engine changed"))
    if resig:
        ans = "y" if args.yes else input(f"\n{len(resig)} existing clip(s) were made with a different voice/engine/settings. "
                    "Re-voice them too? (y = yes, Enter = keep them): ").strip().lower()
        if ans == "y":
            plan.extend(resig)
        else:
            for s, text, out, th, _ in resig:
                man[s["id"]] = {"text": th, "sig": man[s["id"]]["sig"]}
    if not preview:
        save_manifest(man)

    if not plan:
        print("\nAll audio is up to date - nothing to voice.")
        length_report(args)
        return

    print(f"\n{len(plan)} clip(s) to voice -> {out_dir}/\n")
    failed, retries = [], []
    for i, (s, text, out, th, why) in enumerate(plan, 1):
        sid = s["id"]
        progress(i - 1, len(plan), f"Voicing {sid}")
        print(f"[{i}/{len(plan)}] {sid} ({len(text)} chars, {why})...", end="", flush=True)
        before = POOLS[-1].idx if POOLS else 0
        global SEG_SPEED, CUR_SEG_ID
        SEG_SPEED = seg_speed(s) if engine in SPEED_ENGINES else 1.0
        CUR_SEG_ID = None if preview else sid
        ok, retried = gen_with_retry(generate, text, out)
        after = POOLS[-1].idx if POOLS else 0
        if ok:
            print(" done" + (f"  [key #{before + 1} -> #{after + 1}]" if after != before else ""))
            if not preview:
                man[sid] = {"text": th, "sig": sig}
                save_manifest(man)
            if retried or after != before:
                retries.append(f"{sid}: retry={retried} key {before + 1}->{after + 1}")
        else:
            print(" FAILED")
            failed.append(sid)
        time.sleep(0.2)
    CUR_SEG_ID = None
    progress(len(plan), len(plan), "Voice-over done")

    if retries:
        with open(os.path.join(out_dir, "_retries.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M") + "\n" + "\n".join(retries) + "\n")
        print(f"\n[i] {len(retries)} clip(s) needed a retry or key switch (logged in {out_dir}/_retries.log) - "
              "listen to those first.")
    if failed:
        die(f"Failed clips: {', '.join(failed)}  (just run this step again to retry them)")
    if preview:
        print(f"\nPreview done. Listen in {PREVIEW_DIR}/ - tweak the [tags] in segments.json "
              "(or review_sheet.csv), preview again, then run the full voice step.")
        reveal(PREVIEW_DIR)
        return
    print("\nAll audio generated.")
    length_report(args)


def audio_frames(sid, fps, acache):
    if not os.path.exists(os.path.join(AUDIO_DIR, f"{sid}.mp3")):
        return None
    try:
        return fit_audio(sid, fps, acache)[1]
    except Exception:
        return None


def length_report(args):
    """Actual narration length vs the target in project.json."""
    try:
        data = load_data(find_json(args.json))
    except SystemExit:
        return
    need("ffmpeg", "ffprobe")
    acache = Cache(os.path.join(TRIM_DIR, "_cache.json"))
    target = parse_target(PROJECT.get("target_length")) or parse_target(DEFAULT_TARGETS.get(MODULE), "youtube")
    yt = [s for s in yt_segments(data) if s.get("id")]
    if yt:
        rows, missing = [], 0
        for s in yt:
            fr = audio_frames(s["id"], FPS, acache)
            if fr is None:
                missing += 1
                continue
            rows.append((fr / FPS, s["id"]))
        total = sum(r[0] for r in rows)
        print(f"\n=== LENGTH (YouTube) ===")
        print(f"  actual narration: {fmt_mmss(total)}" + (f"   ({missing} segment(s) without audio yet)" if missing else ""))
        if target:
            diff = total - target
            word = "over" if diff > 0 else "under"
            print(f"  target {fmt_mmss(target)}, actual {fmt_mmss(total)}, {word} by {fmt_mmss(abs(diff))}")
            if diff > 0 and rows:
                print("  longest segments (trim these first):")
                for d, sid in sorted(rows, reverse=True)[:5]:
                    print(f"    {sid:<12} {d:5.1f}s")
        else:
            print("  (no target length set in project.json)")
    tt = tiktok_parts(data)
    tfps = int(CFG["tiktok"]["fps"])
    ttarget = parse_target(PROJECT.get("target_length"), "tiktok_part") if isinstance(PROJECT.get("target_length"), dict) else None
    for part, clips in tt.items():
        tot, n = 0.0, 0
        for c in clips:
            fr = audio_frames(c.get("id"), tfps, acache)
            if fr is not None:
                tot += fr / tfps
                n += 1
        if n:
            extra = f", target {fmt_mmss(ttarget)}" if ttarget else ""
            print(f"  TikTok {part}: {fmt_mmss(tot)} ({n}/{len(clips)} clips){extra}")


# ---- review sheet (edit narration/tags/captions in Excel, import back) ----
def step_review(args):
    jpath = find_json(args.json)
    data = load_data(jpath)
    segs = iter_segments(data)
    dv = default_video()

    if args.do_import:
        if not os.path.exists(REVIEW_CSV):
            die(f"{REVIEW_CSV} not found - export it first.")
        by_id = {s.get("id"): s for s in segs}
        shutil.copyfile(jpath, jpath + ".bak")
        changed = 0
        with open(REVIEW_CSV, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                s = by_id.get((row.get("id") or "").strip())
                if not s:
                    continue
                for col, key in (("narration", "narration"), ("subtitle", "subtitle"), ("caption", "caption")):
                    if col not in row:
                        continue
                    new = (row[col] or "").strip()
                    old = str(s.get(key, "")).strip()
                    if new != old:
                        if new:
                            s[key] = new
                        else:
                            s.pop(key, None)
                        changed += 1
        with open(jpath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Imported: {changed} field(s) changed in {jpath} (backup: {jpath}.bak).")
        print("Run the voice step - only the edited segments are re-voiced.")
        return

    need("ffmpeg", "ffprobe")
    acache = Cache(os.path.join(TRIM_DIR, "_cache.json"))
    rows, n_long, n_short = [], 0, 0
    seen = set()
    for s in segs:
        sid = s.get("id")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        text = str(s.get("narration", ""))
        est = est_speech_seconds(text)
        rng, flag = "", ""
        clip_len = ""
        if s.get("src_start") and s.get("src_end"):
            try:
                a, b = parse_time(s["src_start"]), parse_time(s["src_end"])
                rng = f"{s['src_start']} -> {s['src_end']}"
                clip_len = round(b - a, 1)
                if est > clip_len + 0.7:
                    flag = f"TOO LONG (last frame held ~{est - clip_len:.0f}s)"
                    n_long += 1
                elif clip_len > 4 and est < clip_len * 0.6:
                    flag = f"TOO SHORT (footage cut ~{clip_len - est:.0f}s)"
                    n_short += 1
            except Exception:
                pass
        fr = audio_frames(sid, FPS, acache)
        rows.append([sid, rng, clip_len, round(est, 1), round(fr / FPS, 1) if fr else "", flag,
                     count_tags(text), text, s.get("subtitle", ""), s.get("caption", "")])
    with open(REVIEW_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "source_range", "clip_sec", "est_voice_sec", "actual_voice_sec", "flag",
                    "tags", "narration", "subtitle", "caption"])
        w.writerows(rows)
    print(f"[+] {REVIEW_CSV}: {len(rows)} segments ({n_long} too long, {n_short} too short).")
    print("Edit narration / subtitle / caption in Excel (keep the id column), save as CSV, "
          "then run 'Import review edits'.")
    reveal(REVIEW_CSV)


# ====================================================================
# Shared by STEP 4 / 5 / 6: silence-free, frame-exact narration audio
# ====================================================================
TRIM_DIR = "audio_trim"
SILENCE_DB = "-50dB"


def fit_audio(sid, fps, cache):
    """audio/<id>.mp3  ->  audio_trim/<fps>fps/<id>.wav

    * silence at the start and end of the voice-over is removed
    * the result is padded (by less than 1 frame) to a WHOLE number of frames,
      so video and audio are exactly the same length.
    Returns (wav_path, frame_count).
    """
    src = os.path.join(AUDIO_DIR, f"{sid}.mp3")
    out_dir = os.path.join(TRIM_DIR, f"{fps}fps")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{sid}.wav")
    st = os.stat(src)
    ckey = f"{fps}fps/{sid}"
    key = f"{st.st_mtime_ns}|{st.st_size}|{fps}|{SAMPLE_RATE}|{SILENCE_DB}"
    if cache.fresh(ckey, key, out):
        return out, max(1, round(get_duration(out) * fps))

    trim = (f"silenceremove=start_periods=1:start_threshold={SILENCE_DB}:start_silence=0.02,"
            f"areverse,"
            f"silenceremove=start_periods=1:start_threshold={SILENCE_DB}:start_silence=0.03,"
            f"areverse")
    base = ["-c:a", "pcm_s16le", "-ar", str(SAMPLE_RATE), "-ac", "2"]
    tmp = out + ".tmp.wav"

    r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", trim] + base + [tmp])
    dur = get_duration(tmp) if r.returncode == 0 and os.path.exists(tmp) else 0.0
    if dur < 0.05:  # everything looked like silence -> keep the file untouched
        r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", src] + base + [tmp])
        if r.returncode != 0 or not os.path.exists(tmp):
            raise RuntimeError(f"ffmpeg failed on {src}:\n{tail(r.stderr)}")
        dur = get_duration(tmp)

    frames = max(1, math.ceil(dur * fps - 1e-3))
    total = frames / fps
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp,
             "-af", f"apad=whole_dur={total:.6f}", "-t", f"{total:.6f}"] + base + [out])
    try:
        os.remove(tmp)
    except OSError:
        pass
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"ffmpeg failed while fitting {src}:\n{tail(r.stderr)}")
    cache.set(ckey, key)
    return out, frames


def to_pathurl(abs_path):
    # Premiere-style URL: file://localhost/C%3a/Users/name/My%20Folder/file.mp3
    clean = os.path.abspath(abs_path).replace("\\", "/")
    enc = urllib.parse.quote(clean, safe="/").replace("%3A", "%3a")
    if not enc.startswith("/"):
        enc = "/" + enc
    return "file://localhost" + enc




# ====================================================================
# STEP 4 / 5 shared: build every picture clip to match its voice-over exactly
# ====================================================================
def ffrun(cmd, out):
    r = run(cmd)
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"ffmpeg failed:\n{tail(r.stderr)}")
    return r


X264 = ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-an"]


def render_video_clip(m, frames, W, H, F, out, fill):
    """Video-only clip of EXACTLY `frames` frames. Longer footage is cut at the end,
    shorter footage gets its last frame held (no black, no gap)."""
    total = frames / F
    loop = bool(m.get("loop"))                     # solo background video: repeat it for as long as the voice runs
    use = total if loop else min(m["avail"], total)
    info = probe_media(m["file"])
    g = fit_graph(info["w"], info["h"], W, H, fill)
    g += f";[f]fps={F},setsar=1,tpad=stop_mode=clone:stop_duration={total + 1:.3f}[v]"
    ffrun(["ffmpeg", "-y", "-loglevel", "error"] + (["-stream_loop", "-1"] if loop else [])
          + ["-ss", f"{m['start']:.3f}", "-t", f"{use:.3f}",
             "-i", m["file"], "-filter_complex", g, "-map", "[v]", "-frames:v", str(frames)] + X264 + [out], out)


def render_image_clip(m, frames, W, H, F, out):
    """Still image -> slow zoom (Ken Burns) lasting exactly `frames` frames."""
    info = probe_media(m["file"])
    g = fit_graph(info["w"], info["h"], W * 2, H * 2, "blur", "[0:v]", "[f]")
    g += (f";[f]zoompan=z='1+0.10*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"d={frames}:s={W}x{H}:fps={F},setsar=1,format=yuv420p[v]")
    ffrun(["ffmpeg", "-y", "-loglevel", "error", "-i", m["file"], "-filter_complex", g,
           "-map", "[v]", "-frames:v", str(frames)] + X264 + [out], out)


def wrap_block(text, width=58):
    out = []
    for para in str(text).split("\n"):
        out.extend(textwrap.wrap(para, width) or [""])
    return "\n".join(out)


def render_slate(seg, why, frames, W, H, F, out):
    """Placeholder card for a shot that is still missing, so the timeline length is right."""
    sid = seg.get("id", "?")
    shot = seg.get("shot") or {}
    lines = []
    if shot.get("description"):
        lines.append(shot["description"])
    for q in shot.get("queries") or []:
        lines.append(f"search: {q}")
    if shot.get("fallback"):
        lines.append(f"fallback: {shot['fallback']}")
    if not lines:
        lines.append(strip_tags(seg.get("narration", ""))[:200] or why)
    lines.append(f"({why})")
    t1 = write_textfile(f"slate_{sid}_t", f"MISSING SHOT  {sid}")
    t2 = write_textfile(f"slate_{sid}_b", wrap_block("\n".join(lines)))
    total = frames / F
    fo = font_opt()
    base = f"color=c=0x20232a:s={W}x{H}:r={F}"
    full = (f"{base},drawtext={fo}textfile='{t1}':fontcolor=0xffb020:fontsize={int(H / 13)}:x=(w-text_w)/2:y={int(H * 0.10)},"
            f"drawtext={fo}textfile='{t2}':fontcolor=white:fontsize={int(H / 27)}:x={int(W * 0.08)}:y={int(H * 0.28)}:line_spacing=12")
    for vf in (full, base):
        r = run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", vf, "-t", f"{total:.6f}",
                 "-frames:v", str(frames)] + X264 + [out])
        if r.returncode == 0 and os.path.exists(out):
            return
    raise RuntimeError(f"slate failed:\n{tail(r.stderr)}")


def render_gfx(rank, caption, frames, W, H, F, out):
    """Transparent overlay (.mov with alpha) for V2: big rank number and/or a caption line."""
    fo = font_opt()
    chain = f"color=c=black@0.0:s={W}x{H}:r={F},format=rgba"
    if rank not in (None, ""):
        tf = write_textfile("rank_" + os.path.splitext(os.path.basename(out))[0], f"#{rank}")
        chain += (f",drawtext={fo}textfile='{tf}':fontcolor=white:fontsize={int(H / 4.2)}:"
                  f"x={int(W * 0.04)}:y={int(H * 0.05)}:box=1:boxcolor=0x000000@0.55:boxborderw={int(H / 45)}:"
                  f"borderw=3:bordercolor=0xffb020")
    if caption:
        tf = write_textfile("cap_" + os.path.splitext(os.path.basename(out))[0], wrap_block(caption, 44))
        chain += (f",drawtext={fo}textfile='{tf}':fontcolor=white:fontsize={int(H / 20)}:"
                  f"x=(w-text_w)/2:y=h-text_h-{int(H * 0.08)}:box=1:boxcolor=0x000000@0.6:boxborderw={int(H / 60)}:"
                  f"line_spacing=8")
    os.makedirs(GFX_DIR, exist_ok=True)
    ffrun(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", chain, "-frames:v", str(frames),
           "-c:v", "qtrle", "-pix_fmt", "argb", out], out)


def render_orig_audio(m, frames, fps, vol, out):
    """The clip's own sound, ducked, padded/cut to the exact length. None if the clip has no audio."""
    if not probe_media(m["file"])["has_audio"]:
        return None
    total = frames / fps
    use = min(m["avail"], total)
    ffrun(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{m['start']:.3f}", "-t", f"{use:.3f}",
           "-i", m["file"], "-vn", "-af", f"volume={vol},apad=whole_dur={total:.6f}", "-t", f"{total:.6f}",
           "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", out], out)
    return out


def silent_wav(frames, fps, out):
    total = frames / fps
    if not os.path.exists(out) or abs(get_duration(out) - total) > 0.02:
        ffrun(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
               f"anullsrc=r={SAMPLE_RATE}:cl=stereo", "-t", f"{total:.6f}", "-c:a", "pcm_s16le", out], out)
    return out


def keep_audio_volume(seg):
    v = seg.get("keep_audio")
    if v in (None, False, 0, "0", "false", "False"):
        return 0.0
    if v is True or v in ("true", "True"):
        return float(CFG.get("keep_audio_volume", 0.30))
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return float(CFG.get("keep_audio_volume", 0.30))


# ====================================================================
# CHARACTER ANIMATION  (sub-module - works in every module)
#
#   Put transparent PNG cut-outs in characters/:
#       characters/kratos.png                   one picture
#       characters/kratos/default.png           or a folder of poses:
#       characters/kratos/talk.png                 default / talk (mouth open) / angry / ...
#       characters/kratos__angry.png            (same as a pose file: name__pose.png)
#       characters/kratos/character.json        optional: {"facing": "left"}   (which way the art looks)
#   Segment fields (ALL optional - a segment without them gets no character):
#       "character": "kratos"           (false = none; or an object with the fields below)
#       "char_pos"     bottom-right | bottom-left | bottom-center | center | middle | left | right |
#                      top-left | top-right          (default: bottom-right)
#       "char_layout"  corner (over the clip)  |  solo (character in the middle on a background)
#       "char_bg"      solo background: #112233 | gradient:#111,#333 | image / video file name
#       "char_pose"    pose name (file name without .png)
#       "char_anim"    talk | breathe | bob | float | sway | shake | none  (combine: "talk+sway")
#       "char_enter" / "char_exit"   slide | pop | fade | none
#       "char_scale"   character height as a fraction of the frame height (0.46 = 46 %)
#       "char_flip" true/false/"auto"   "char_outline" true/"#ffffff"   "char_shadow" true/false
#       "char_x" / "char_y"  exact spot (0-1 of the frame; x = centre, y = feet)
#       "commentary": true     marks a commentary beat (with project.json character.auto = "commentary"
#                              the default character appears; with no picture source it becomes a solo scene)
#   Output: one transparent .mov per segment in char_layers/ = its own video layer
#       Premiere V2 / VideoPad V2 (graphics move up one track) | mp4, VideoPad-simple, TikTok: baked in
# ====================================================================
CHARS_DIR = "characters"
CHAR_LAYERS_DIR = "char_layers"
CHAR_BURN_DIR = "char_burn"
CHAR_IMG_EXTS = (".png", ".webp")
CHAR_TALK_NAMES = ("talk", "talking", "speak", "speaking", "open", "mouth_open", "mouth")
CHAR_IDLE_NAMES = ("default", "idle", "neutral", "normal", "base", "closed")
CHAR_ANIMS = ("talk", "breathe", "bob", "float", "sway", "shake", "none")
CHAR_APPEAR = ("slide", "pop", "fade", "none")
CHAR_VERSION = "v1"
CHAR_CODECS = {                      # how the transparent layer is stored (config character.codec)
    "qtrle": ["-c:v", "qtrle", "-pix_fmt", "argb"],                                   # safest: same as the graphics layer
    "png": ["-c:v", "png", "-pix_fmt", "rgba"],                                       # about half the size
    "prores": ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-qscale:v", "12"],  # smallest for painted art
}
CHAR_FLAT = ("pos", "pose", "scale", "anim", "enter", "exit", "flip", "layout", "bg",
             "outline", "shadow", "x", "y")
CHAR_PICTURE_KEYS = ("src", "src_start", "image", "page", "focus", "panel", "panels")
CHAR_POS_ALIASES = {
    "bottom-right": ("r", "b"), "br": ("r", "b"), "corner": ("r", "b"), "right-bottom": ("r", "b"),
    "bottom-left": ("l", "b"), "bl": ("l", "b"), "left-bottom": ("l", "b"),
    "bottom-center": ("c", "b"), "bottom-centre": ("c", "b"), "bc": ("c", "b"), "bottom": ("c", "b"),
    "center": ("c", "b"), "centre": ("c", "b"),
    "middle": ("c", "m"), "middle-center": ("c", "m"),
    "left": ("l", "m"), "mid-left": ("l", "m"), "middle-left": ("l", "m"),
    "right": ("r", "m"), "mid-right": ("r", "m"), "middle-right": ("r", "m"),
    "top-left": ("l", "t"), "tl": ("l", "t"), "top-right": ("r", "t"), "tr": ("r", "t"),
    "top-center": ("c", "t"), "top-centre": ("c", "t"), "top": ("c", "t"),
}
CHAR_FRAME = [WIDTH, HEIGHT]          # size of the frame being built (solo backgrounds are made to match)
_CHAR_LIB = {}
_CHAR_WARNED = set()
_SPRITES = {}


def chcfg():
    c = CFG.get("character")
    return c if isinstance(c, dict) else {}


def char_project():
    c = PROJECT.get("character")
    if isinstance(c, str):
        c = {"default": c}
    return c if isinstance(c, dict) else {}


def char_warn(key, msg):
    if key not in _CHAR_WARNED:
        _CHAR_WARNED.add(key)
        print(f"[!] {msg}")


def char_pil():
    try:
        from PIL import Image  # noqa
        return True
    except ImportError:
        char_warn("pil", "Character animation needs Pillow - run SETUP.bat again (or: pip install pillow). "
                         "Continuing without characters.")
        return False


def _hex(c, default=(255, 255, 255)):
    c = str(c or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return default


def _truthy(v, default=False):
    if v is None or v == "":
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("0", "false", "no", "off", "none")
    return bool(v)


# ---- what a segment asks for (file-free, cheap) ----
def char_request(seg):
    """-> dict of the segment's character wishes, or None. Reads fields only, never files."""
    if not isinstance(seg, dict):
        return None
    c = seg.get("character")
    if c is False or (isinstance(c, str) and c.strip().lower() in ("none", "off", "no", "false")):
        return None
    req = {}
    if isinstance(c, dict):
        req.update({k: v for k, v in c.items() if v not in (None, "")})
        if "position" in req and "pos" not in req:
            req["pos"] = req.pop("position")
    elif isinstance(c, str) and c.strip():
        req["name"] = c.strip()
    for k in CHAR_FLAT:
        v = seg.get("char_" + k)
        if v not in (None, ""):
            req[k] = v
    if "layout" not in req and seg.get("layout") in ("solo", "corner"):
        req["layout"] = seg["layout"]
    explicit = bool(req) or c is True
    if not req.get("name"):
        pc = char_project()
        default = str(pc.get("default") or "").strip()
        auto = str(pc.get("auto") or "off").lower()
        if default and (explicit or auto == "all" or (auto == "commentary" and seg.get("commentary"))):
            req["name"] = default
    if not req.get("name"):
        return None
    layout = str(req.get("layout") or "").lower()
    if layout not in ("solo", "corner"):
        layout = ""
    forced = layout == "solo" or (bool(req.get("bg")) and layout != "corner")
    no_picture = not any(seg.get(k) not in (None, "", False) for k in CHAR_PICTURE_KEYS)
    auto_solo = (not layout) and bool(seg.get("commentary")) and no_picture
    req["layout"] = layout
    req["_solo"] = "forced" if forced else ("auto" if auto_solo else "")
    return req


def char_req_key(req):
    return json.dumps(req, sort_keys=True, default=str) if req else ""


# ---- solo background ----
def char_bg_file(bg):
    """'#202733' | 'gradient' | 'gradient:#1d2230,#43305f'  ->  PNG the size of the frame (cached)."""
    from PIL import Image, ImageOps
    W, H = CHAR_FRAME
    spec = str(bg or "gradient").strip()
    low = spec.lower()
    if low.startswith("#"):
        c1 = c2 = _hex(spec)
    else:
        parts = spec.split(":", 1)[1].split(",") if ":" in spec else []
        base = str(chcfg().get("solo_bg") or "gradient:#1b2030,#43305f")
        dflt = base.split(":", 1)[1].split(",") if ":" in base else ["#1b2030", "#43305f"]
        c1 = _hex(parts[0] if parts else dflt[0])
        c2 = _hex(parts[1] if len(parts) > 1 else (dflt[1] if len(dflt) > 1 else dflt[0]))
    name = f"_solo_bg_{h8(f'{c1}{c2}{W}x{H}')}.png"
    os.makedirs(GFX_DIR, exist_ok=True)
    path = os.path.join(GFX_DIR, name)
    if os.path.exists(path):
        return path
    grad = Image.linear_gradient("L").resize((W, H), Image.BILINEAR)
    img = ImageOps.colorize(grad, black=c1, white=c2).convert("RGB")
    if c1 != c2:                                    # soft light in the middle so the character pops
        glow = Image.radial_gradient("L").resize((W, H), Image.BILINEAR)
        glow = ImageOps.invert(glow).point(lambda v: int(v * 0.16))
        img = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), img, glow)
    img.save(path)
    return path


def char_solo_media(req):
    """Picture for a solo commentary scene (character on a background) -> a seg_media() dict."""
    bg = str(req.get("bg") or chcfg().get("solo_bg") or "gradient").strip()
    low = bg.lower()
    f = None
    if not (low.startswith("#") or low.startswith("gradient")):
        f = find_in(bg, IMAGES_DIR, os.path.join(CHARS_DIR, "backgrounds"), FOOTAGE_DIR, ".")
        if not f:
            char_warn("bg:" + bg, f"solo background '{bg}' not found (images/, characters/backgrounds/, footage/) "
                                  "- using the gradient.")
    if f and f.lower().endswith(VIDEO_EXTS):
        return {"kind": "video", "file": f, "start": 0.0, "avail": probe_media(f)["dur"], "solo": True,
                "loop": True}
    if f:
        return {"kind": "image", "file": f, "start": 0.0, "avail": 0.0, "solo": True}
    if not char_pil():
        return {"kind": "slate", "why": "solo scene needs Pillow for its background"}
    return {"kind": "image", "file": char_bg_file(bg), "start": 0.0, "avail": 0.0, "solo": True}


# ---- the character library ----
def char_library(refresh=False):
    """-> {lowercase name: {"name", "poses": {pose: path}, "default", "talk", "meta"}}"""
    global _CHAR_LIB
    if _CHAR_LIB and not refresh:
        return _CHAR_LIB
    lib = {}
    if os.path.isdir(CHARS_DIR):
        for entry in sorted(os.listdir(CHARS_DIR), key=natural_key):
            if entry.startswith(("_", ".")) or entry.lower() == "backgrounds":
                continue
            p = os.path.join(CHARS_DIR, entry)
            if os.path.isfile(p) and entry.lower().endswith(CHAR_IMG_EXTS):
                nm = os.path.splitext(entry)[0]
                pose = "default"
                if "__" in nm:                              # kratos__angry.png = pose "angry" of "kratos"
                    nm, pose = nm.split("__", 1)
                    pose = pose.lower().replace(" ", "_") or "default"
                ch = lib.setdefault(nm.lower(), {"name": nm, "poses": {}, "meta": {}})
                ch["poses"].setdefault(pose, p)
            elif os.path.isdir(p):
                ch = lib.setdefault(entry.lower(), {"name": entry, "poses": {}, "meta": {}})
                for f in sorted(os.listdir(p), key=natural_key):
                    if f.lower().endswith(CHAR_IMG_EXTS) and not f.startswith(("_", ".")):
                        ch["poses"][os.path.splitext(f)[0].lower().replace(" ", "_")] = os.path.join(p, f)
                mp = os.path.join(p, "character.json")
                if os.path.isfile(mp):
                    try:
                        with open(mp, "r", encoding="utf-8") as fh:
                            ch["meta"] = json.load(fh) or {}
                    except Exception as e:
                        char_warn("meta:" + p, f"{mp} is not valid JSON ({e}) - ignored.")
    for key in [k for k, v in lib.items() if not v["poses"]]:
        del lib[key]
    for ch in lib.values():
        poses = ch["poses"]
        ch["talk"] = next((n for n in CHAR_TALK_NAMES if n in poses), None)
        ch["default"] = (next((n for n in CHAR_IDLE_NAMES if n in poses), None)
                         or next((n for n in sorted(poses) if n != ch["talk"] and not n.endswith(("_talk", "_open"))), None)
                         or next(iter(poses)))
    _CHAR_LIB = lib
    return lib


def char_find(name):
    lib = char_library()
    n = str(name or "").strip().lower()
    for cand in (n, n.replace(" ", "_"), n.replace(" ", ""), n.replace("-", "_")):
        if cand in lib:
            return lib[cand]
    return None


def char_pos_of(value, default):
    key = str(value or default).strip().lower().replace("_", "-").replace(" ", "-")
    return CHAR_POS_ALIASES.get(key) or CHAR_POS_ALIASES.get(str(default).lower()) or ("r", "b")


def char_list(v, allowed, default):
    items = [x for x in re.split(r"[+,/ ]+", str(v if v not in (None, "") else default).lower()) if x]
    items = [x for x in items if x in allowed]
    if "none" in items:
        return []
    return items or ([x for x in re.split(r"[+,/ ]+", str(default).lower()) if x in allowed and x != "none"])


def char_resolve(req, layout, sid="?"):
    """Segment wishes + project defaults + library -> a complete, JSON-able spec (or None)."""
    ch = char_find(req.get("name"))
    if not ch:
        have = ", ".join(sorted(v["name"] for v in char_library().values())) or "none yet"
        char_warn("nochar:" + str(req.get("name")).lower(),
                  f"{sid}: character '{req.get('name')}' not found in {CHARS_DIR}/ (have: {have}) - skipped.")
        return None
    cfg = chcfg()
    solo = layout == "solo"
    poses = ch["poses"]
    pose = str(req.get("pose") or "").strip().lower().replace(" ", "_")
    pose = os.path.splitext(pose)[0] if pose.endswith(CHAR_IMG_EXTS) else pose
    if pose and pose not in poses:
        char_warn(f"nopose:{ch['name']}:{pose}",
                  f"{sid}: {ch['name']} has no pose '{pose}' (poses: {', '.join(sorted(poses))}) - using the default.")
        pose = ""
    pose = pose or ch["default"]
    talk = next((c for c in (f"{pose}_talk", f"{pose}_open", f"talk_{pose}", f"{pose}_talking") if c in poses), None)
    if not talk and pose == ch["default"]:
        talk = ch["talk"]
    hx, vy = char_pos_of(req.get("pos"), cfg.get("solo_pos", "center") if solo else cfg.get("corner_pos", "bottom-right"))
    try:
        scale = float(req.get("scale") or (cfg.get("solo_scale", 0.80) if solo else cfg.get("corner_scale", 0.46)))
    except (TypeError, ValueError):
        scale = 0.46
    scale = max(0.05, min(1.6, scale))
    enter = str(req.get("enter") or cfg.get("solo_enter" if solo else "enter", "pop" if solo else "slide")).lower()
    leave = str(req.get("exit") or cfg.get("solo_exit" if solo else "exit", "fade" if solo else "slide")).lower()
    facing = str((ch["meta"] or {}).get("facing") or "").lower()
    flip_req = req.get("flip")
    if str(flip_req).lower() in ("true", "1", "yes"):
        flip = True
    elif str(flip_req).lower() in ("false", "0", "no"):
        flip = False
    else:                                              # auto: face the middle of the screen
        want = "left" if hx == "r" else ("right" if hx == "l" else "")
        flip = bool(facing in ("left", "right") and want and facing != want)
    outline = req.get("outline", cfg.get("outline", ""))
    outline = "#ffffff" if outline is True or str(outline).lower() in ("true", "yes", "on") else (
        "" if not outline or str(outline).lower() in ("false", "no", "off", "none") else str(outline))
    spec = {
        "name": ch["name"], "pose": pose, "file": poses[pose], "talk_file": poses.get(talk) if talk else None,
        "layout": layout, "hx": hx, "vy": vy, "scale": scale,
        "max_w": float(cfg.get("solo_max_width", 0.80) if solo else cfg.get("max_width", 0.40)),
        "anims": char_list(req.get("anim"), CHAR_ANIMS, cfg.get("idle", "talk")),
        "enter": enter if enter in CHAR_APPEAR else "none", "exit": leave if leave in CHAR_APPEAR else "none",
        "enter_sec": float(cfg.get("enter_sec", 0.35)), "exit_sec": float(cfg.get("exit_sec", 0.25)),
        "flip": flip, "outline": outline, "shadow": _truthy(req.get("shadow"), _truthy(cfg.get("shadow"), True)),
        "margin": float(cfg.get("margin", 0.03)), "thr": float(cfg.get("mouth_threshold", 0.25)),
        "x": None, "y": None,
    }
    for k in ("x", "y"):
        try:
            if req.get(k) not in (None, ""):
                spec[k] = max(-0.5, min(1.5, float(req[k])))
        except (TypeError, ValueError):
            pass
    return spec


# ---- sprites ----
def _alpha_bbox(im):
    return im.getchannel("A").point(lambda v: 255 if v > 6 else 0).getbbox()


def char_has_alpha(path):
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    lo, hi = im.getchannel("A").getextrema()
    return lo < 250 and hi > 0


def char_aspect(path):
    from PIL import Image
    key = ("asp", file_sig(path))
    if key not in _SPRITES:
        bb = _alpha_bbox(Image.open(path).convert("RGBA"))
        _SPRITES[key] = ((bb[2] - bb[0]) / max(1, bb[3] - bb[1])) if bb else 1.0
    return _SPRITES[key]


def char_sprites(files, th, flip, outline, shadow):
    """Poses -> aligned, scaled, outlined, shadowed sprites [{'pm', 'w', 'h', 'pad'}] (cached)."""
    from PIL import Image, ImageChops, ImageFilter
    key = (tuple(file_sig(f) for f in files), int(th), flip, outline, shadow)
    if key in _SPRITES:
        return _SPRITES[key]
    RES = getattr(Image, "Resampling", Image)
    ims = [Image.open(f).convert("RGBA") for f in files]
    boxes = [_alpha_bbox(im) for im in ims]
    if not all(boxes):
        raise RuntimeError(f"{os.path.basename(files[boxes.index(None)])} is completely transparent")
    if len({im.size for im in ims}) == 1:           # same canvas: crop all to ONE box so poses stay aligned
        u = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
        ims = [im.crop(u) for im in ims]
    else:                                           # different canvases: line the poses up bottom-centre
        crops = [im.crop(b) for im, b in zip(ims, boxes)]
        cw, chh = max(c.width for c in crops), max(c.height for c in crops)
        ims = []
        for c in crops:
            cell = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
            cell.paste(c, ((cw - c.width) // 2, chh - c.height))
            ims.append(cell)
    th = max(8, int(th))
    tw = max(8, round(ims[0].width * th / ims[0].height))
    pad = max(10, int(th * 0.10))
    out = []
    for im in ims:
        if flip:
            im = im.transpose(getattr(Image, "Transpose", Image).FLIP_LEFT_RIGHT)
        spr = im.convert("RGBa").resize((tw, th), RES.LANCZOS).convert("RGBA")
        size = (tw + 2 * pad, th + 2 * pad)
        body = Image.new("RGBA", size, (0, 0, 0, 0))
        if outline:
            ap = Image.new("L", size, 0)
            ap.paste(spr.getchannel("A"), (pad, pad))
            for _ in range(max(2, round(th * 0.010))):
                ap = ap.filter(ImageFilter.MaxFilter(3))
            ap = ap.filter(ImageFilter.GaussianBlur(0.7)).point(lambda v: min(255, v * 2))
            ring = Image.new("RGBA", size, _hex(outline) + (0,))
            ring.putalpha(ap)
            body = Image.alpha_composite(body, ring)
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        layer.paste(spr, (pad, pad))
        body = Image.alpha_composite(body, layer)
        if shadow:
            sa = ImageChops.offset(body.getchannel("A"), int(th * 0.010), int(th * 0.016))
            sa = sa.filter(ImageFilter.GaussianBlur(max(2, th * 0.018))).point(lambda v: int(v * 0.42))
            sh = Image.new("RGBA", size, (0, 0, 0, 0))
            sh.putalpha(sa)
            body = Image.alpha_composite(sh, body)
        out.append({"pm": body.convert("RGBa"), "w": tw, "h": th, "pad": pad})
    _SPRITES[key] = out
    return out


# ---- the voice drives the mouth ----
def voice_envelope(wav, frames, fps):
    """Loudness per video frame, 0..1 (smoothed, relative to this clip's own peaks)."""
    from array import array
    try:
        with wave.open(wav, "rb") as w:
            ch, sr, sw = w.getnchannels(), w.getframerate(), w.getsampwidth()
            raw = w.readframes(w.getnframes())
        if sw != 2:
            return [0.0] * frames
        a = array("h")
        a.frombytes(raw[: len(raw) // 2 * 2])
        if sys.byteorder == "big":
            a.byteswap()
        per = max(1, int(sr / fps))
        vals = []
        for f in range(frames):
            seg = a[f * per * ch:(f + 1) * per * ch:ch * 3]
            vals.append(math.sqrt(sum(v * v for v in seg) / len(seg)) if len(seg) else 0.0)
    except Exception:
        return [0.0] * frames
    nz = sorted(v for v in vals if v > 1)
    ref = nz[int(len(nz) * 0.9)] if nz else 0
    if ref < 150:
        return [0.0] * frames
    env, prev = [], 0.0
    for v in vals:
        cur = min(1.0, v / ref)
        prev = max(cur, prev * 0.55)                # quick attack, short release
        env.append(prev)
    return env


def mouth_states(env, thr):
    """Open / closed per frame; blips shorter than 2 frames are ignored so the mouth doesn't flicker."""
    st = [e > thr for e in env]
    i = 0
    while i < len(st):
        j = i
        while j < len(st) and st[j] == st[i]:
            j += 1
        if j - i < 2 and i > 0:
            for k in range(i, j):
                st[k] = st[i - 1]
        i = j
    return st


def _ease_out_cubic(x):
    return 1 - (1 - x) ** 3


def _ease_in_cubic(x):
    return x ** 3


def _ease_out_back(x):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


class CharPlayer:
    """Draws one character frame by frame (used for the video layers and for the preview)."""

    def __init__(self, spec, W, H, F, frames, env=None, phase=0, enter=True, leave=True):
        from PIL import Image
        self.Image = Image
        self.RES = getattr(Image, "Resampling", Image)
        self.spec, self.W, self.H, self.F, self.frames, self.phase = spec, W, H, F, frames, phase
        self.env = env or []
        files = [spec["file"]] + ([spec["talk_file"]] if spec.get("talk_file") else [])
        ref = min(H, 0.9 * W)                        # tall (9:16) frames: size the character off the width
        th = min(spec["scale"] * ref, spec["max_w"] * W / max(0.05, char_aspect(spec["file"])))
        self.sprites = char_sprites(files, th, spec["flip"], spec["outline"], spec["shadow"])
        s0 = self.sprites[0]
        self.sw, self.sh, self.pad = s0["w"], s0["h"], s0["pad"]
        self.mouth = mouth_states(self.env, spec["thr"]) if len(self.sprites) > 1 and self.env else []
        m = spec["margin"] * H
        hx, vy = spec["hx"], spec["vy"]
        self.cx = (m + self.sw / 2) if hx == "l" else ((W - m - self.sw / 2) if hx == "r" else W / 2)
        self.base = (m + self.sh) if vy == "t" else ((H / 2 + self.sh / 2) if vy == "m" else H)
        if spec.get("x") is not None:
            self.cx = spec["x"] * W
        if spec.get("y") is not None:
            self.base = spec["y"] * H
        n_in = int(round(spec["enter_sec"] * F)) if enter and spec["enter"] != "none" else 0
        n_out = int(round(spec["exit_sec"] * F)) if leave and spec["exit"] != "none" else 0
        cap = max(0, frames // 2)
        self.n_in, self.n_out = min(n_in, cap), min(n_out, cap)
        self.blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # -- idle motion: scale, rotation, x / y offset (pixels, y positive = up)
    def idle(self, f, env):
        sp, W, H = self.spec, self.W, self.H
        t = (f + self.phase) / self.F
        k = sp["anims"]
        s, rot, dx, dy = 1.0, 0.0, 0.0, 0.0
        if "talk" in k or "breathe" in k:
            s *= 1 + 0.012 * math.sin(2 * math.pi * t / 3.4)
        if "talk" in k:
            s *= 1 + 0.030 * env
            dy += 0.010 * H * env
        if "bob" in k:
            dy += 0.014 * H * (1 - math.cos(2 * math.pi * t / 1.15)) / 2
        if "float" in k:
            dy += 0.028 * H * (1 - math.cos(2 * math.pi * t / 3.2)) / 2
            dx += 0.008 * W * math.sin(2 * math.pi * t / 4.3)
        if "sway" in k:
            rot += 2.2 * math.sin(2 * math.pi * t / 2.6)
        if "shake" in k:
            n = f + self.phase
            r1 = math.modf(abs(math.sin(n * 12.9898) * 43758.5453))[0] - 0.5
            r2 = math.modf(abs(math.sin(n * 78.233) * 12345.6789))[0] - 0.5
            dx += r1 * 0.012 * W
            rot += r2 * 2.0
        return s, rot, dx, dy

    # -- entrance / exit: offset (x, y px, y down), scale, opacity
    def appear(self, kind, p, entering):
        sp, W, H = self.spec, self.W, self.H
        if kind == "none":
            return 0.0, 0.0, 1.0, 1.0
        if kind == "fade":
            return 0.0, 0.0, 1.0, p if entering else p
        if kind == "pop":
            if entering:
                return 0.0, 0.0, max(0.02, _ease_out_back(p)), min(1.0, p * 3)
            return 0.0, 0.0, max(0.02, p), p
        e = _ease_out_cubic(p) if entering else p       # slide
        hx = sp["hx"]
        if hx == "r":
            return (1 - e) * (W - (self.cx - self.sw / 2) + self.pad), 0.0, 1.0, 1.0
        if hx == "l":
            return -(1 - e) * ((self.cx + self.sw / 2) + self.pad), 0.0, 1.0, 1.0
        return 0.0, (1 - e) * (H - (self.base - self.sh) + self.pad), 1.0, 1.0

    def frame(self, f):
        env = self.env[f] if f < len(self.env) else 0.0
        s, rot, dx, dy = self.idle(f, env)
        ox = oy = 0.0
        alpha, es = 1.0, 1.0
        if self.n_in and f < self.n_in:
            p = (f + 1) / self.n_in
            ox, oy, es, alpha = self.appear(self.spec["enter"], p, True)
        left = self.frames - 1 - f
        if self.n_out and left < self.n_out:
            q = (left + 0.0) / self.n_out                  # 1 -> 0 over the last frames
            ex = _ease_in_cubic(q) if self.spec["exit"] == "slide" else q
            ox2, oy2, es2, a2 = self.appear(self.spec["exit"], ex, False)
            ox, oy, es, alpha = ox + ox2, oy + oy2, es * es2, alpha * a2
        idx = 1 if (self.mouth and f < len(self.mouth) and self.mouth[f]) else 0
        spr = self.sprites[min(idx, len(self.sprites) - 1)]["pm"]
        sc = s * es
        ax, ay = self.pad + self.sw / 2, self.pad + self.sh      # feet, centre
        if abs(sc - 1.0) > 0.002:
            spr = spr.resize((max(1, round(spr.width * sc)), max(1, round(spr.height * sc))), self.RES.BICUBIC)
            ax, ay = ax * sc, ay * sc
        if abs(rot) > 0.05:
            spr = spr.rotate(rot, resample=self.RES.BICUBIC, center=(ax, ay))
        spr = spr.convert("RGBA")
        if alpha < 0.995:
            spr.putalpha(spr.getchannel("A").point(lambda v, k=max(0.0, alpha): int(v * k)))
        canvas = self.blank.copy()
        canvas.paste(spr, (round(self.cx + ox + dx - ax), round(self.base + oy - dy - ay)))
        return canvas


def render_character_layer(spec, wav, frames, W, H, F, out, phase=0, enter=True, leave=True):
    """Transparent .mov (qtrle + alpha) of exactly `frames` frames: the character, animated, on its own layer."""
    env = voice_envelope(wav, frames, F) if wav and os.path.exists(wav) else []
    player = CharPlayer(spec, W, H, F, frames, env, phase, enter, leave)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tmp = out[:-4] + ".part.mov"
    log = tmp + ".log"
    codec = CHAR_CODECS.get(str(chcfg().get("codec") or "qtrle").lower(), CHAR_CODECS["qtrle"])
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(F), "-i", "-", "-an"] + codec + [tmp]
    with open(log, "wb") as lf:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=lf)
        try:
            for f in range(frames):
                p.stdin.write(player.frame(f).tobytes())
            p.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        p.wait()
    if p.returncode != 0 or not os.path.exists(tmp):
        err = ""
        try:
            with open(log, "r", encoding="utf-8", errors="replace") as lf:
                err = tail(lf.read())
        except OSError:
            pass
        raise RuntimeError(f"ffmpeg could not write the character layer:\n{err}")
    os.replace(tmp, out)
    for junk in (log,):
        try:
            os.remove(junk)
        except OSError:
            pass
    return out


def burn_character(video, layer, out, frames):
    """Bake the character layer into the picture clip (for the mp4 / simple VideoPad / TikTok paths)."""
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    ffrun(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", layer, "-filter_complex",
           "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]", "-map", "[v]", "-frames:v", str(frames)]
          + X264 + [out], out)
    return out


def char_stage(sid, seg, req, m, item, wav, frames, W, H, fps, mode, phase, enter, leave, cache):
    """Make (or reuse) this segment's character layer. mode: 'layer' | 'burn'. Never stops the build."""
    if not char_pil():
        return
    try:
        spec = char_resolve(req, "solo" if m.get("solo") else "corner", sid)
        if not spec:
            return
        d = os.path.join(CHAR_LAYERS_DIR, f"{W}x{H}_{fps}fps")
        layer = os.path.join(d, f"{sid}.mov")
        sig = [file_sig(spec["file"]), file_sig(spec["talk_file"]) if spec["talk_file"] else "", file_sig(wav)]
        key = (f"char|{CHAR_VERSION}|{json.dumps(spec, sort_keys=True)}|{'|'.join(sig)}|{frames}|{fps}|{W}x{H}"
               f"|{phase}|{int(enter)}{int(leave)}|{chcfg().get('codec') or 'qtrle'}")
        if not cache.fresh(sid + "#char", key, layer):
            render_character_layer(spec, wav, frames, W, H, fps, layer, phase, enter, leave)
            cache.set(sid + "#char", key)
        if mode == "burn":
            bd = os.path.join(CHAR_BURN_DIR, f"{W}x{H}_{fps}fps")
            burned = os.path.join(bd, f"{sid}.mp4")
            bkey = f"burn|{file_sig(item['video_file'])}|{file_sig(layer)}|{frames}|v1"
            if not cache.fresh(sid + "#burn", bkey, burned):
                burn_character(item["video_file"], layer, burned, frames)
                cache.set(sid + "#burn", bkey)
            item["video_file"] = os.path.abspath(burned)
        else:
            item["char_file"] = os.path.abspath(layer)
        item["char_name"] = spec["name"]
        item["char_layout"] = spec["layout"]
    except Exception as e:
        print(f"    [!] {sid}: character skipped - {e}")


# ---- STEP: characters (check the library, preview sheet) ----
def step_characters(args):
    lib = char_library(refresh=True)
    os.makedirs(CHARS_DIR, exist_ok=True)
    pil = char_pil()
    if not lib:
        print(f"No characters yet. Put transparent PNG cut-outs in {CHARS_DIR}/ :")
        print(f"  {CHARS_DIR}/kratos.png                  one picture")
        print(f"  {CHARS_DIR}/kratos/default.png + talk.png + angry.png   several poses (talk = mouth open)")
        reveal(CHARS_DIR)
        return
    print(f"Characters in {CHARS_DIR}/ : {len(lib)}\n")
    for ch in lib.values():
        poses = ", ".join(sorted(ch["poses"]))
        extra = []
        if ch["talk"]:
            extra.append(f"mouth pose '{ch['talk']}' follows the voice")
        if (ch["meta"] or {}).get("facing"):
            extra.append(f"faces {ch['meta']['facing']}")
        print(f"  {ch['name']:<18} poses: {poses}" + (f"   ({'; '.join(extra)})" if extra else ""))
        if pil:
            from PIL import Image
            for pn, pth in sorted(ch["poses"].items()):
                try:
                    im = Image.open(pth)
                    if not char_has_alpha(pth):
                        print(f"      [!] {pn}: no transparency ({im.width}x{im.height}) - this is not a cut-out, "
                              "it would show as a rectangle. Remove the background first.")
                except Exception as e:
                    print(f"      [!] {pn}: cannot read ({e})")
    try:
        data = load_data(find_json(args.json))
        use = {}
        for s in iter_segments(data):
            r = char_request(s)
            if r:
                use.setdefault(str(r["name"]).lower(), []).append(s.get("id", "?"))
    except SystemExit:
        use = {}
    pc = char_project()
    print(f"\nProject default: {pc.get('default') or '-'}    auto: {pc.get('auto') or 'off'}")
    if use:
        print("Used in segments.json:")
        for nm, ids in use.items():
            ok = "OK" if char_find(nm) else "NOT IN characters/"
            print(f"  {nm:<18} {len(ids)} segment(s)   {ok}")
    if not pil:
        return
    from PIL import Image, ImageDraw, ImageFont
    TW, TH = 640, 360
    names = list(lib.values())
    sheet = Image.new("RGB", (TW * 2 + 30, (TH + 50) * len(names) + 10), (24, 24, 28))
    dr = ImageDraw.Draw(sheet)
    fp = find_font()
    font = ImageFont.truetype(fp, 22) if fp else ImageFont.load_default()
    old = CHAR_FRAME[:]
    CHAR_FRAME[:] = [TW, TH]
    try:
        for i, ch in enumerate(names):
            y0 = 10 + i * (TH + 50)
            dr.text((12, y0 + 4), ch["name"], fill=(255, 190, 40), font=font)
            for j, layout in enumerate(("corner", "solo")):
                x0 = 10 + j * (TW + 10)
                if layout == "solo":
                    tile = Image.open(char_bg_file("")).convert("RGBA")
                else:
                    tile = Image.new("RGBA", (TW, TH), (70, 78, 90, 255))
                    d2 = ImageDraw.Draw(tile)
                    for gx in range(0, TW, 80):
                        d2.line([(gx, 0), (gx, TH)], fill=(84, 92, 104), width=1)
                    d2.text((16, 14), "your footage", fill=(150, 160, 175), font=font)
                spec = char_resolve({"name": ch["name"]}, layout, "preview")
                if spec:
                    pl = CharPlayer(spec, TW, TH, 24, 240, [0.0] * 240, 0, False, False)
                    tile = Image.alpha_composite(tile, pl.frame(60))
                sheet.paste(tile.convert("RGB"), (x0, y0 + 36))
                dr.text((x0 + (TW - 90 if j else 150), y0 + 4), layout, fill=(170, 175, 190), font=font)
    finally:
        CHAR_FRAME[:] = old
    out = os.path.join(CHARS_DIR, "_preview.png")
    sheet.save(out)
    print(f"\n[+] preview: {out}  (left: corner over footage, right: solo scene)")
    reveal(out)


def build_items(segments, fps, W, H, clips_dir, fill, render=True, gfx=True, label="clips", characters="layer"):
    """For every segment that has narration audio: picture clip (+ original audio, + overlay, + character).
    Returns items in order. render=False only fits the audio (used for .srt).
    characters: "layer" = own transparent video layer (Premiere / VideoPad) | "burn" = baked into the picture
    (mp4, simple VideoPad, TikTok) | False = none."""
    need("ffmpeg", "ffprobe")
    os.makedirs(clips_dir, exist_ok=True)
    cache = Cache(os.path.join(clips_dir, "_cache.json"))
    acache = Cache(os.path.join(TRIM_DIR, "_cache.json"))
    dv = default_video()
    if MODULE == "comic_recap":
        comic_prepare(segments)
    CHAR_FRAME[:] = [W, H]
    reqs = [char_request(s) if (characters and render) else None for s in segments]
    run_frames, n_chars = 0, 0
    print(f"Building {len(segments)} {label}"
          + (f" (source: {dv})" if dv else "") + f" at {W}x{H} {fps}fps, fill={fill}...\n")
    items = []
    for n_seg, seg in enumerate(segments):
        sid = seg.get("id")
        if not sid:
            continue
        progress(n_seg, len(segments), f"Rendering {sid}")
        if not os.path.exists(os.path.join(AUDIO_DIR, f"{sid}.mp3")):
            print(f"[-] Skipping {sid}: no audio/{sid}.mp3 (run the voice step first)")
            continue
        try:
            wav, frames = fit_audio(sid, fps, acache)
            total = frames / fps
            m = seg_media(seg, dv)
            req = reqs[n_seg]
            clip = os.path.join(clips_dir, f"{sid}.mp4")
            tag, note = "", ""
            if render:
                if m["kind"] == "video":
                    use = min(m["avail"], total)
                    key = (f"video|{file_sig(m['file'])}|{m['start']:.3f}|{use:.3f}|{frames}|{fps}|{W}x{H}|{fill}|v3"
                           + ("|loop" if m.get("loop") else ""))
                    drawfn = lambda: render_video_clip(m, frames, W, H, fps, clip, fill)
                    if m["avail"] > total + 0.05:
                        note = f"footage trimmed by {m['avail'] - total:.2f}s to fit voice"
                    elif total > m["avail"] + 0.05:
                        note = f"last frame held {total - m['avail']:.2f}s (voice is longer than the clip)"
                    else:
                        note = "perfect fit"
                elif m["kind"] == "image":
                    key = f"image|{file_sig(m['file'])}|{frames}|{fps}|{W}x{H}|v3"
                    drawfn = lambda: render_image_clip(m, frames, W, H, fps, clip)
                    note = "still image, slow zoom"
                elif m["kind"] == "comic":
                    key = f"comic|{comic_key(seg, m)}|{frames}|{fps}|{W}x{H}"
                    drawfn = lambda: render_comic_clip(m, seg, frames, W, H, fps, clip)
                    note = comic_note(seg, m)
                else:
                    stext = json.dumps(seg.get("shot") or {}, sort_keys=True) + m.get("why", "")
                    key = f"slate|{h8(stext)}|{sid}|{frames}|{fps}|{W}x{H}|v3"
                    drawfn = lambda: render_slate(seg, m.get("why", ""), frames, W, H, fps, clip)
                    note = f"SLATE - {m.get('why', 'missing')}"
                if cache.fresh(sid, key, clip):
                    tag = "cached  "
                else:
                    drawfn()
                    cache.set(sid, key)
                    tag = "rendered"
                vdur = get_duration(clip)
                if abs(vdur - total) > 1.5 / fps:
                    print(f"    [!] warning: {sid} clip is {vdur:.3f}s but should be {total:.3f}s")
            item = {"id": sid, "kind": m["kind"], "media": m, "video_file": os.path.abspath(clip),
                    "audio_file": os.path.abspath(wav), "frames": frames, "text": sub_text(seg),
                    "caption": str(seg.get("caption") or "").strip(), "rank": seg.get("rank"),
                    "chapter": str(seg.get("chapter") or "").strip(), "orig_file": None,
                    "gfx_file": None, "char_file": None, "char_name": "", "seg": seg}

            if render and m["kind"] == "video":
                vol = keep_audio_volume(seg)
                if vol > 0:
                    of = os.path.join(TRIM_DIR, f"{fps}fps", f"{sid}_orig.wav")
                    okey = f"orig|{file_sig(m['file'])}|{m['start']:.3f}|{frames}|{fps}|{vol}|{SAMPLE_RATE}"
                    if cache.fresh(sid + "#orig", okey, of):
                        item["orig_file"] = os.path.abspath(of)
                    elif render_orig_audio(m, frames, fps, vol, of):
                        cache.set(sid + "#orig", okey)
                        item["orig_file"] = os.path.abspath(of)
                    else:
                        print(f"    [i] {sid}: keep_audio asked but the clip has no audio track")
            if render and gfx and (item["caption"] or seg.get("rank") not in (None, "")):
                gf = os.path.join(GFX_DIR, f"{sid}.mov")
                os.makedirs(GFX_DIR, exist_ok=True)
                gkey = f"gfx|{seg.get('rank')}|{item['caption']}|{frames}|{fps}|{W}x{H}|{find_font()}|v1"
                if not cache.fresh(sid + "#gfx", gkey, gf):
                    render_gfx(seg.get("rank"), item["caption"], frames, W, H, fps, gf)
                    cache.set(sid + "#gfx", gkey)
                item["gfx_file"] = os.path.abspath(gf)
            if render and characters and req:
                prev_same = n_seg > 0 and char_req_key(reqs[n_seg - 1]) == char_req_key(req)
                next_same = n_seg + 1 < len(reqs) and char_req_key(reqs[n_seg + 1]) == char_req_key(req)
                phase = run_frames if prev_same else 0          # idle motion carries on across segments
                char_stage(sid, seg, req, m, item, item["audio_file"], frames, W, H, fps, characters,
                           phase, not prev_same, not next_same, cache)
                run_frames = phase + frames
                if item["char_name"]:
                    n_chars += 1
                    note += f"  + {item['char_name']} ({item['char_layout']})"
            else:
                run_frames = 0
        except Exception as e:
            print(f"[!] Skipping {sid}: {e}")
            continue
        if render:
            print(f"[+] {tag} {sid:<10} {total:6.2f}s  {note}")
        items.append(item)

    progress(len(segments), len(segments), "Clips rendered")
    if n_chars:
        print(f"[+] character animation: {n_chars} segment(s) "
              + ("as their own video layer" if characters == "layer" else "baked into the picture"))
        if characters == "layer":
            mb = sum(os.path.getsize(i["char_file"]) for i in items if i.get("char_file") and os.path.exists(i["char_file"])) / 1e6
            if mb > 1500:
                print(f"    [i] the character layers take {mb / 1000:.1f} GB in char_layers/ - set "
                      "config.json character.codec to \"png\" or \"prores\" for smaller files")
    if not items:
        die("Nothing to build - no segment had audio. Run the voice step first.")
    return items


def make_music_bed(total_frames, fps, name="music_bed"):
    """First track in music/ -> one quiet bed exactly as long as the video (fade in/out). None if off."""
    if not PROJECT.get("music"):
        return None
    tracks = sorted(f for f in glob.glob(os.path.join(MUSIC_DIR, "*")) if f.lower().endswith(MUSIC_EXTS))
    if not tracks:
        print("[i] music is ON in project.json but music/ is empty - skipping the music bed.")
        return None
    total = total_frames / fps
    out = os.path.join(TRIM_DIR, f"{name}_{fps}fps.wav")
    os.makedirs(TRIM_DIR, exist_ok=True)
    vol = float(CFG.get("music_volume", 0.12))
    af = f"volume={vol},afade=t=in:d=2"
    if total > 6:
        af += f",afade=t=out:st={total - 3:.3f}:d=3"
    ffrun(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", tracks[0], "-t", f"{total:.6f}",
           "-af", af, "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", out], out)
    print(f"[+] music bed: {os.path.basename(tracks[0])} at volume {vol}")
    return os.path.abspath(out)


def sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, tag, **attrs)
    if text is not None:
        el.text = str(text)
    return el


def add_rate(parent):
    r = sub(parent, "rate")
    sub(r, "timebase", FPS)
    sub(r, "ntsc", "FALSE")




# ====================================================================
# STEP 4A: Premiere sequence (multi-track XML)
#   V1 footage/stills/slates | V2 character (if any) | V2/V3 number & caption graphics
#   A1 voice-over | A2 original audio (ducked) | A3 music bed
# ====================================================================
def xml_tcode(parent):
    tc_ = sub(parent, "timecode")
    add_rate(tc_)
    sub(tc_, "string", "00:00:00:00")
    sub(tc_, "frame", 0)
    sub(tc_, "displayformat", "NDF")


def xml_vchars(parent):
    vsc_ = sub(parent, "samplecharacteristics")
    add_rate(vsc_)
    for tag_, val in (("width", WIDTH), ("height", HEIGHT), ("anamorphic", "FALSE"),
                      ("pixelaspectratio", "square"), ("fielddominance", "none")):
        sub(vsc_, tag_, val)


def xml_links(parent, idx):
    for mtype, cid in (("video", f"clipitem-v-{idx}"), ("audio", f"clipitem-a-{idx}")):
        ln = sub(parent, "link")
        sub(ln, "linkclipref", cid)
        sub(ln, "mediatype", mtype)
        sub(ln, "trackindex", 1)
        sub(ln, "clipindex", idx + 1)


def xml_video_clip(track, cid, name, path, start, n, alpha=False):
    vc = sub(track, "clipitem", id=cid)
    sub(vc, "masterclipid", "master-" + cid)
    sub(vc, "name", name)
    sub(vc, "enabled", "TRUE")
    sub(vc, "duration", n)
    add_rate(vc)
    sub(vc, "start", start)
    sub(vc, "end", start + n)
    sub(vc, "in", 0)
    sub(vc, "out", n)
    sub(vc, "alphatype", "straight" if alpha else "none")
    sub(vc, "pixelaspectratio", "square")
    sub(vc, "anamorphic", "FALSE")
    vfile = sub(vc, "file", id="file-" + cid)
    sub(vfile, "name", os.path.basename(path))
    sub(vfile, "pathurl", to_pathurl(path))
    add_rate(vfile)
    sub(vfile, "duration", n)
    xml_tcode(vfile)
    vm = sub(vfile, "media")
    xml_vchars(sub(vm, "video"))
    return vc


def xml_audio_clip(track, cid, name, path, start, n):
    ac = sub(track, "clipitem", id=cid, premiereChannelType="stereo")
    sub(ac, "masterclipid", "master-" + cid)
    sub(ac, "name", name)
    sub(ac, "enabled", "TRUE")
    sub(ac, "duration", n)
    add_rate(ac)
    sub(ac, "start", start)
    sub(ac, "end", start + n)
    sub(ac, "in", 0)
    sub(ac, "out", n)
    afile = sub(ac, "file", id="file-" + cid)
    sub(afile, "name", os.path.basename(path))
    sub(afile, "pathurl", to_pathurl(path))
    add_rate(afile)
    sub(afile, "duration", n)
    xml_tcode(afile)
    afm = sub(sub(afile, "media"), "audio")
    afsc = sub(afm, "samplecharacteristics")
    sub(afsc, "depth", 16)
    sub(afsc, "samplerate", SAMPLE_RATE)
    sub(afm, "channelcount", 2)
    st = sub(ac, "sourcetrack")
    sub(st, "mediatype", "audio")
    sub(st, "trackindex", 1)
    return ac


def write_premiere_xml(items, music):
    total = sum(i["frames"] for i in items)
    seq_name = os.path.basename(ROOT) or "Recap Sequence"
    root = ET.Element("xmeml", version="4")
    proj = sub(root, "project")
    sub(proj, "name", seq_name)
    kids = sub(proj, "children")
    seq = sub(kids, "sequence", id="sequence-1")
    sub(seq, "uuid", str(uuid.uuid4()))
    sub(seq, "duration", total)
    add_rate(seq)
    sub(seq, "name", seq_name)
    media = sub(seq, "media")

    v_el = sub(media, "video")
    xml_vchars(sub(v_el, "format"))
    v1 = sub(v_el, "track")
    vch = {nm: sub(v_el, "track") for nm in char_names(items)}                       # one layer per character
    v2 = sub(v_el, "track") if any(i["gfx_file"] for i in items) else None            # numbers / captions on top

    a_el = sub(media, "audio")
    sub(a_el, "numOutputChannels", 2)
    asc = sub(sub(a_el, "format"), "samplecharacteristics")
    sub(asc, "depth", 16)
    sub(asc, "samplerate", SAMPLE_RATE)

    def atrack():
        return sub(a_el, "track", currentExplodedTrackIndex="0", totalExplodedTrackCount="1",
                   premiereTrackType="Stereo")
    a1 = atrack()
    a2 = atrack() if any(i["orig_file"] for i in items) else None
    a3 = atrack() if music else None

    cur, markers = 0, []
    for idx, it in enumerate(items):
        n = it["frames"]
        vc = xml_video_clip(v1, f"clipitem-v-{idx}", it["id"], it["video_file"], cur, n)
        xml_links(vc, idx)
        ac = xml_audio_clip(a1, f"clipitem-a-{idx}", it["id"], it["audio_file"], cur, n)
        xml_links(ac, idx)
        if it.get("char_file") and it["char_name"] in vch:
            xml_video_clip(vch[it["char_name"]], f"clipitem-c-{idx}", "CHAR " + it["char_name"], it["char_file"],
                           cur, n, alpha=True)
        if it["gfx_file"] and v2 is not None:
            label = (f"#{it['rank']} " if it["rank"] not in (None, "") else "") + (it["caption"] or "")
            xml_video_clip(v2, f"clipitem-g-{idx}", "GFX " + label.strip(), it["gfx_file"], cur, n, alpha=True)
        if it["orig_file"] and a2 is not None:
            xml_audio_clip(a2, f"clipitem-o-{idx}", it["id"] + " original", it["orig_file"], cur, n)
        if it["chapter"]:
            markers.append((cur, it["chapter"], "chapter"))
        if it["kind"] == "slate":
            markers.append((cur, f"MISSING: {it['id']}", it["media"].get("why", "")))
        cur += n
    if music and a3 is not None:
        xml_audio_clip(a3, "clipitem-m-0", "music bed", music, 0, total)

    for tr in [v1] + list(vch.values()) + [v2, a1, a2, a3]:
        if tr is not None:
            sub(tr, "enabled", "TRUE")
            sub(tr, "locked", "FALSE")
    xml_tcode(seq)
    for frame, name, comment in markers:
        mk = sub(seq, "marker")
        sub(mk, "comment", comment)
        sub(mk, "name", name)
        sub(mk, "in", frame)
        sub(mk, "out", -1)

    ET.indent(root)
    with open(XML_OUT, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' +
                ET.tostring(root, encoding="unicode"))
    return total, markers


# ====================================================================
# STEP 4D: VideoPad project (.vpj)
#   Same timeline as the Premiere XML, written in NCH VideoPad's own project format.
#   Format notes + the proof it was built from: videopad-agent-pipeline / docs/vpj-format-findings.md
#   V1 footage | V2 character (if any) | V2/V3 number & caption graphics | A1 voice-over | A2 original audio | A3 music
#   --simple: V1 + A1 only, picture and voice muxed into one file per segment.
# ====================================================================
VPJ_OUT = "videopad_project.vpj"
VPJ_AV_DIR = "clips_av"          # --simple: picture + voice muxed per segment
VPJ_FIRST_HANDLE = 3382          # hindex of the known-good template; new objects are numbered from here

# Fixed lines copied verbatim from a project VideoPad itself wrote (NCH VideoPad 8.91). The Computer_FilePath
# inside the export blob is the only value this writer changes: it sets the default export folder.
VPJ_EXPORT_BLOB = (
    "Type=2SubtitlesExport=1&Computer_Preset=Default&Computer_FilePath=C%3A%5CUsers%5Cuser%5CVideos%5Cmov"
    "ie.mp4&Portable_Preset=AppleiPhone6S_6SP&Portable_FilePath=C%3A%5CUsers%5Cuser%5CVideos%5Cmovie.mp4&"
    "360_Preset=Default&360_FilePath=C%3A%5CUsers%5Cuser%5CVideos%5Cmovie.mp4&Disc_Name=DiscName&Disc_Ima"
    "gePath=C%3A%5CUsers%5Cuser%5CVideos%5Cmydvd.iso&Disc_IDDrive=255&Disc_DVD_NTSC=0&Disc_DVD_Widescreen"
    "=1&Disc_DVD_AutoBitrate=1&Disc_DVD_AverageBitrate=4000&Disc_DVD_MaximumBitrate=9000&Disc_DVD_AudioBi"
    "trate=96&Disc_DVD_Data_Preset=Widescreen%20TV&Disc_Bluray_Data_Preset=Widescreen%20TV&ImageSequence_"
    "FilePath=C%3A%5CUsers%5Cuser%5CVideos%5Cmovie&ImageSequence_Format=0&ImageSequence_JPG_Quality=85&Im"
    "ageSequence_Width=1024&ImageSequence_Height=576&Upload_FilePath=C%3A%5CUsers%5Cuser%5CVideos%5Cmovie"
    ".mp4&Upload_DeleteFile=1&YouTube_Preset=YouTube%20720p&YouTube_FrameRate=30.000000&YouTube_ForceFixe"
    "dFrameRate=0&Youtube_Title=&Youtube_Description=&Youtube_CategoryID=&Youtube_Keywords=&Youtube_Priva"
    "cy=0&Flickr_Title=&Flickr_Description=&Flickr_Tags=&Flickr_Safety=1&Flickr_Public=1&Flickr_Friend=1&"
    "Flickr_Family=1&Flickr_Hidden=0&Vimeo_Title=&Vimeo_Resolution=&Vimeo_Description=&Vimeo_FrameRate=30"
    ".000000&Vimeo_IsAutoDetectedFrameRate=1&Vimeo_Privacy=0&Dropbox_Preset=720p&Dropbox_FilePath=C%3A%5C"
    "Users%5Cuser%5CVideos%5Cmovie.mp4&GoogleDrive_Preset=720p&GoogleDrive_FilePath=C%3A%5CUsers%5Cuser%5"
    "CVideos%5Cmovie.mp4&OneDrive_Preset=720p&OneDrive_FilePath=C%3A%5CUsers%5Cuser%5CVideos%5Cmovie.mp4&"
    "Stereoscopic_Preset=Widescreen%20TV&Stereoscopic_FilePath=C%3A%5CUsers%5Cuser%5CVideos%5Cmovie.mp4&S"
    "tereoscopic_StereoFormat=7&Stereoscopic_ConvertTo3D=1"
)
VPJ_EDITOUT = (
    "EditOutput_Settings=-1&EditOutput_Resize=0&EditOutput_ChangeFramerate=0&EditOutput_ForceFixedFramera"
    "te=0&EditOutput_ResizeType=0&EditOutput_Width=768&EditOutput_Height=576&EditOutput_ResizeKeepRatio=0"
    "&EditOutput_Framerate=30.000000"
)   # the template line ends in a lone CR; it is re-added when writing

VPJ_EXPORT_DEFAULT_PATH = "Computer_FilePath=C%3A%5CUsers%5Cuser%5CVideos%5Cmovie.mp4"
VPJ_SEQ_CACHE = "Seq9_1792790493_18467"   # template value; VideoPad re-derives it


def vpj_q(s):
    """URL-encode the way .vpj files do: C:\\Users\\a b -> C%3A%5CUsers%5Ca%20b ('.', '_', '-' stay)."""
    return urllib.parse.quote(str(s), safe="")


def vpj_ms(frames, fps):
    """Frame count -> milliseconds. Always converted from the running total so seams never drift."""
    return int(round(frames * 1000.0 / fps))


def vpj_media_lines(h, path, dur_ms, kind, h_pair=None, ctime=None, name=None):
    """Bin records. 'pair' = file with picture AND sound (two linked records, exactly as VideoPad writes
    them); 'video' / 'audio' = single-stream file (the same record without the link fields)."""
    name, p = vpj_q(name or os.path.basename(path)), vpj_q(path)
    ctime = int(ctime or time.time())
    thumb = 4500 if dur_ms > 4500 else dur_ms // 2     # 4500 = the placeholder VideoPad writes
    out = []
    if kind in ("pair", "audio"):
        link = f"&hlinked={h_pair}" if kind == "pair" else ""
        had = "&hadlinkedvideo=1" if kind == "pair" else ""
        out.append(f"h={h}&type=5&name={name}&path={p}&note=&creationtime={ctime}&hfolder=7{link}"
                   f"&in=0&out={dur_ms}{had}&thumbpos={thumb}&soundstreamindex=-1&isbackgroundsound=0")
    if kind in ("pair", "video"):
        hv = h_pair if kind == "pair" else h
        link = f"&hlinked={h}" if kind == "pair" else ""
        had = "&hadlinkedaudio=1" if kind == "pair" else ""
        out.append(f"h={hv}&type=3&sphen=0&sphho=0&sphve=0&name={name}&path={p}&note=&creationtime={ctime}"
                   f"&stereoformat=0&stereostretch=0&hfolder=6{link}&in=0&out={dur_ms}&thumb={thumb}{had}"
                   f"&thumbpos={thumb}")
    return out


def vpj_clip_line(h, media_h, name, offset, tin, tout, track_h, linked_h=None):
    link = f"&hlinked={linked_h}" if linked_h else ""
    return (f"h={h}&type=7&sphen=0&sphho=0&sphve=0&horiginalclip={media_h}&name={vpj_q(name)}"
            f"&offset={offset}&in={tin}&out={tout}{link}&fadeinduration=0&thumbpos=4500"
            f"&tlstart=0&tlend=0&tlstartoff=0&tlendoff=0&htrack={track_h}")


def vpj_chain_line(h, mute=0):
    return (f"size=0&fadepoints=0&speedchangef=1.000000&audiopitchchange=0&voll=0&volr=0"
            f"&mute={mute}&hclip={h}")


def assemble_vpj(seq_name, total_ms, n_vtracks, n_atracks, media, clips, export_path=None):
    """Build the text of a .vpj.

    media : list of {"key", "path", "dur", "kind": pair|video|audio, "ctime"?, "name"?}
    clips : list of {"media": key, "v": video-track number (1-based) or None, "a": audio-track number or None,
            "offset": ms on the timeline, "in": ms, "out": ms, "name"?}
    A 'pair' clip with both "v" and "a" is written as the linked picture+sound pair VideoPad makes.
    The trailing checksum is left stale on purpose: VideoPad then shows its 'Damaged File' prompt and
    'Try Load' opens the project untouched (the hash is a corruption warning, not a lock)."""
    nxt = [VPJ_FIRST_HANDLE]

    def new():
        nxt[0] += 1
        return nxt[0] - 1

    SEQ, SUBT = 9, 10
    # tracks: audio tracks first, then video tracks, as the template lists them; track 1 reuses 11 / 12
    atr = [11] + [new() for _ in range(n_atracks - 1)]
    vtr = [12] + [new() for _ in range(n_vtracks - 1)]
    track_lines = []
    for i, h in enumerate(atr, 1):
        track_lines.append(f"h={h}&type=2&name=Audio%20Track%20{i}&output=1&solo=0&volume=100&pan=0&collapsed0=0"
                           f"&collapsed1=0&collapsed2=1&collapsed3=0&collapsed4=0&collapsed5=0&collapsed6=0"
                           f"&collapsed7=0&locked=0&hsequence={SEQ}")
    for i, h in enumerate(vtr, 1):
        track_lines.append(f"h={h}&type=1&name=Video%20Track%20{i}&output=1&solo=0&collapsed0=0&collapsed1=0"
                           f"&collapsed2=0&collapsed3=0&collapsed4=1&collapsed5=0&collapsed6=0&collapsed7=0"
                           f"&locked=0&hsequence={SEQ}")

    # bin: audio record first, then its picture record (the order VideoPad writes them)
    mh, media_lines, chain_h = {}, [], []
    for m in media:
        h = new()
        hp = new() if m["kind"] == "pair" else None
        kind = m["kind"]
        media_lines += vpj_media_lines(h, m["path"], m["dur"], kind, hp, m.get("ctime"), m.get("name"))
        if kind == "pair":
            mh[m["key"]] = {"a": h, "v": hp}
        elif kind == "audio":
            mh[m["key"]] = {"a": h}
        else:
            mh[m["key"]] = {"v": h}
        chain_h += [x for x in (h, hp) if x]

    clip_lines, clip_h = [], []
    for c in clips:
        m = mh[c["media"]]
        src = next(x for x in media if x["key"] == c["media"])
        nm = c.get("name") or src.get("name") or os.path.basename(src["path"])
        hv = new() if c.get("v") else None
        ha = new() if c.get("a") else None
        both = hv and ha
        if ha:
            clip_lines.append(vpj_clip_line(ha, m["a"], nm, c["offset"], c["in"], c["out"],
                                            atr[c["a"] - 1], hv if both else None))
        if hv:
            clip_lines.append(vpj_clip_line(hv, m["v"], nm, c["offset"], c["in"], c["out"],
                                            vtr[c["v"] - 1], ha if both else None))
        clip_h += [x for x in (ha, hv) if x]

    export = VPJ_EXPORT_BLOB
    if export_path:
        export = export.replace(VPJ_EXPORT_DEFAULT_PATH, "Computer_FilePath=" + vpj_q(export_path))

    seq = (f"h={SEQ}&type=6&sphen=0&sphho=0&sphve=0&name={vpj_q(seq_name)}&note=&hfolder=5&duration={total_ms}"
           f"&in=0&out={total_ms}&thumb=1440000&seqcachename={VPJ_SEQ_CACHE}&thumbpos=1440000&timelinepos=0"
           f"&selected=1")
    chains = [vpj_chain_line(h) for h in clip_h] + [vpj_chain_line(SEQ)] + [vpj_chain_line(h) for h in chain_h]
    L = ["version=11", f"hindex={nxt[0]}", "folders=4",
         "h=8&name=Images&hfolder=0&open=0&type=2&foldertype=4&selected=0",
         "h=7&name=Audio%20Files&hfolder=0&open=0&type=5&foldertype=2&selected=0",
         "h=6&name=Video%20Files&hfolder=0&open=1&type=3&foldertype=1&selected=1",
         "h=5&name=Sequences&hfolder=0&open=0&type=6&foldertype=3&selected=0",
         f"clips={1 + len(media_lines)}&relativepaths=0", seq] + media_lines
    L += [f"tracks={len(track_lines)}"] + track_lines
    L += [f"trackclips={len(clip_lines)}"] + clip_lines
    L += ["subtitletracks=1", f"h={SUBT}&name=&subtitlechannels=0&hsequence={SEQ}", "subtitleclips=0",
          "transitions=0", f"effectchains={len(chains)}"] + chains
    L += ["groups=0", "bookmarks=0", export, VPJ_EDITOUT + "\r", "wizardused=0", "revision=565488",
          "checksum=" + "0" * 64]
    return "\n".join(L) + "\n"


def check_vpj(text):
    """Structural self-check of a .vpj: counts match, every handle that is referenced exists, links are
    mutual, clips stay inside their source, the sequence is exactly as long as its last clip. Returns a
    list of problems (empty = consistent)."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    bad, sec, i = [], {}, 0

    def q(line):
        out = {}
        for part in line.split("&"):
            k, _, v = part.partition("=")
            out[k] = v
        return out

    if not lines or lines[0] != "version=11":
        bad.append("first line is not version=11")
    while i < len(lines):
        k, _, v = lines[i].partition("=")
        if k in ("folders", "tracks", "trackclips", "subtitletracks", "subtitleclips", "transitions",
                 "effectchains", "groups", "bookmarks"):
            n = int(v)
            sec[k] = [q(x) for x in lines[i + 1:i + 1 + n]]
            if len(sec[k]) != n:
                bad.append(f"{k}={n} but the file ends after {len(sec[k])} lines")
            i += 1 + n
        elif k == "clips":
            n = int(v.split("&")[0])
            sec[k] = [q(x) for x in lines[i + 1:i + n + 1]]
            if len(sec[k]) != n:
                bad.append(f"clips={n} but the file ends after {len(sec[k])} lines")
            i += 1 + n
        else:
            i += 1
    for need in ("clips", "tracks", "trackclips", "effectchains"):
        if need not in sec:
            bad.append(f"section '{need}' is missing")
    if bad:
        return bad
    seqs = [c for c in sec["clips"] if c.get("type") == "6"]
    media = {c["h"]: c for c in sec["clips"] if c.get("type") in ("3", "5", "2")}   # 2 = still image
    tracks = {t["h"]: t for t in sec["tracks"]}
    if len(seqs) != 1:
        bad.append(f"expected 1 sequence record, found {len(seqs)}")
    handles = [c["h"] for c in sec["clips"]] + list(tracks) + [c["h"] for c in sec["trackclips"]]
    if len(set(handles)) != len(handles):
        bad.append("a handle is used twice")
    end = 0
    byh = {c["h"]: c for c in sec["trackclips"]}
    for c in sec["trackclips"]:
        m = media.get(c.get("horiginalclip"))
        t = tracks.get(c.get("htrack"))
        if m is None:
            bad.append(f"clip {c['h']}: horiginalclip {c.get('horiginalclip')} is not in the bin")
            continue
        if t is None:
            bad.append(f"clip {c['h']}: htrack {c.get('htrack')} does not exist")
            continue
        if (t["type"] == "1") != (m["type"] in ("3", "2")):
            bad.append(f"clip {c['h']}: a {'video' if m['type'] in ('3', '2') else 'audio'} source sits on a "
                       f"{'video' if t['type'] == '1' else 'audio'} track")
        tin, tout, off = int(c["in"]), int(c["out"]), int(c["offset"])
        mout = int(m.get("out") or m.get("duration") or 0)
        if not (0 <= tin < tout <= mout):
            bad.append(f"clip {c['h']}: trim {tin}-{tout} is outside its source (0-{mout})")
        end = max(end, off + tout - tin)
        if c.get("hlinked") not in (None, "", "0"):          # hlinked=0 = not linked (VideoPad writes it)
            o = byh.get(c["hlinked"])
            if o is None or o.get("hlinked") != c["h"]:
                bad.append(f"clip {c['h']}: link to {c['hlinked']} is not mutual")
    for m in media.values():
        if m.get("hlinked") not in (None, "", "0") and media.get(m["hlinked"], {}).get("hlinked") != m["h"]:
            bad.append(f"bin item {m['h']}: link to {m['hlinked']} is not mutual")
    chains = [c.get("hclip") for c in sec["effectchains"]]
    want = [c["h"] for c in sec["trackclips"]] + [seqs[0]["h"]] + list(media)
    if sorted(chains) != sorted(want):
        bad.append("effectchains do not cover exactly the clips, the sequence and the bin items")
    if seqs and (int(seqs[0]["duration"]) != end or seqs[0]["out"] != seqs[0]["duration"]):
        bad.append(f"sequence is {seqs[0]['duration']} ms but its last clip ends at {end} ms")
    return bad


def write_vpj(path, text):
    # newline="\n": the file is LF-terminated like VideoPad's own (Windows must not turn it into CRLF)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(text)


def vpj_mux_av(it, out_dir=VPJ_AV_DIR):
    """--simple: picture + voice in ONE file so VideoPad sees an ordinary video-with-sound source."""
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, it["id"] + ".mp4")
    cache = Cache(os.path.join(out_dir, "_cache.json"))
    key = f"{file_sig(it['video_file'])}|{file_sig(it['audio_file'])}|{it['frames']}|{FPS}|v1"
    if not cache.fresh(it["id"], key, out):
        ffrun(["ffmpeg", "-y", "-loglevel", "error", "-i", it["video_file"], "-i", it["audio_file"],
               "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-t", f"{it['frames'] / FPS:.6f}", "-movflags", "+faststart", out], out)
        cache.set(it["id"], key)
    return os.path.abspath(out)


def write_videopad_project(items, music, simple=False, out=VPJ_OUT):
    """Same timeline as write_premiere_xml, as a .vpj. Returns (total_ms, problems)."""
    total_frames = sum(i["frames"] for i in items)
    total_ms = vpj_ms(total_frames, FPS)
    seq_name = os.path.basename(ROOT) or "Recap Sequence"
    media, clips = [], []
    has_gfx = (not simple) and any(i["gfx_file"] for i in items)
    chars = [] if simple else char_names(items)                 # one video layer per character
    tr_char = {nm: 2 + k for k, nm in enumerate(chars)}
    tr_gfx = (2 + len(chars)) if has_gfx else None
    has_orig = (not simple) and any(i["orig_file"] for i in items)
    has_music = (not simple) and bool(music)
    cur = 0
    for idx, it in enumerate(items):
        off, end = vpj_ms(cur, FPS), vpj_ms(cur + it["frames"], FPS)
        n = end - off
        if simple:
            f = vpj_mux_av(it)
            media.append({"key": f"s{idx}", "path": f, "dur": n, "kind": "pair"})
            clips.append({"media": f"s{idx}", "v": 1, "a": 1, "offset": off, "in": 0, "out": n})
        else:
            media.append({"key": f"v{idx}", "path": it["video_file"], "dur": n, "kind": "video"})
            media.append({"key": f"a{idx}", "path": it["audio_file"], "dur": n, "kind": "audio"})
            clips.append({"media": f"v{idx}", "v": 1, "a": None, "offset": off, "in": 0, "out": n})
            clips.append({"media": f"a{idx}", "v": None, "a": 1, "offset": off, "in": 0, "out": n})
            if it.get("char_file") and it["char_name"] in tr_char:
                media.append({"key": f"c{idx}", "path": it["char_file"], "dur": n, "kind": "video",
                              "name": "CHAR " + it["char_name"]})
                clips.append({"media": f"c{idx}", "v": tr_char[it["char_name"]], "a": None, "offset": off,
                              "in": 0, "out": n})
            if has_gfx and it["gfx_file"]:
                media.append({"key": f"g{idx}", "path": it["gfx_file"], "dur": n, "kind": "video"})
                clips.append({"media": f"g{idx}", "v": tr_gfx, "a": None, "offset": off, "in": 0, "out": n})
            if has_orig and it["orig_file"]:
                media.append({"key": f"o{idx}", "path": it["orig_file"], "dur": n, "kind": "audio"})
                clips.append({"media": f"o{idx}", "v": None, "a": 2, "offset": off, "in": 0, "out": n})
        cur += it["frames"]
    if has_music:
        media.append({"key": "music", "path": music, "dur": total_ms, "kind": "audio"})
        clips.append({"media": "music", "v": None, "a": 2 + (1 if has_orig else 0), "offset": 0,
                      "in": 0, "out": total_ms, "name": "music bed"})
    n_v = 1 + len(chars) + (1 if has_gfx else 0)
    n_a = 1 + (1 if has_orig else 0) + (1 if has_music else 0)
    text = assemble_vpj(seq_name, total_ms, n_v, n_a, media, clips,
                        export_path=os.path.abspath(os.path.splitext(out)[0] + ".mp4"))
    problems = check_vpj(text)
    write_vpj(out, text)
    return total_ms, problems


def step_videopad(args):
    data = load_data(find_json(args.json))
    segments = yt_segments(data)
    if not segments:
        die("No 'youtube' segments in the JSON.")
    simple = bool(getattr(args, "simple", False))
    items = build_items(segments, FPS, WIDTH, HEIGHT, CLIPS_DIR, CFG.get("fill", "pad"),
                        gfx=not simple, label="segments", characters="burn" if simple else "layer")
    music = None if simple else make_music_bed(sum(i["frames"] for i in items), FPS)
    total_ms, problems = write_videopad_project(items, music, simple)
    write_extras(items)
    write_shot_manifest(segments, default_video())

    slates = [i["id"] for i in items if i["kind"] == "slate"]
    print(f"\nDone. '{VPJ_OUT}' written: {len(items)} segments, {fmt_mmss(total_ms / 1000)}"
          + (" (simple: picture + voice only)." if simple else "."))
    if problems:
        print("[!] The project failed its own consistency check - please send this to whoever maintains the tool:")
        for p in problems[:12]:
            print("    -", p)
    if slates:
        print(f"[!] {len(slates)} placeholder slate(s) on V1 (missing footage): {', '.join(slates[:12])}"
              + (" ..." if len(slates) > 12 else "") + "\n    Add the footage (collect step), run this again - slates are replaced.")
    print("In VideoPad: File > Open Project > pick the .vpj (or double-click it).\n"
          "VideoPad will say 'The provided file may be damaged' - that is expected, click Try Load (it can appear more than once).\n"
          + ("Tracks: V1 picture | A1 voice (one file per segment)"
             + (" - characters are baked into the picture." if any(i["char_name"] for i in items) else ".")
             if simple else
             track_help(items)))
    print("If VideoPad refuses the full project, run it again with 'Build VideoPad project (simple)'.")
    print_srt_help()
    print("Keep clips/, clips_av/, gfx/, audio_trim/" + (", char_layers/" if any(i.get("char_file") for i in items) else "")
          + " where they are (the project stores paths, not media).")
    reveal(".")


def char_names(items):
    """Characters that have a layer, in order of first appearance (each gets its own video track)."""
    out = []
    for i in items:
        if i.get("char_file") and i["char_name"] not in out:
            out.append(i["char_name"])
    return out


def track_help(items):
    """One line that tells the user what is on which track."""
    v = ["V1 footage"]
    for nm in char_names(items):
        v.append(f"V{len(v) + 1} {nm}")
    if any(i["gfx_file"] for i in items):
        v.append(f"V{len(v) + 1} number/caption graphics")
    return "Tracks: " + " | ".join(v) + " | A1 voice | A2 original sound | A3 music."


def write_extras(items):
    """captions .srt, on-screen text .srt, chapters, shot manifest."""
    write_timeline_srt(items)
    lab = []
    for it in items:
        t = ""
        if it["rank"] not in (None, ""):
            t = f"#{it['rank']}"
        if it["caption"]:
            t = (t + "  " if t else "") + it["caption"]
        lab.append((t, it["frames"]))
    if any(t for t, _ in lab):
        n = write_srt(ONSCREEN_SRT, lab, FPS)
        print(f"[+] on-screen text: {n} cue(s) -> {ONSCREEN_SRT} "
              "(backup option: import as captions if the graphics on V2 don't show)")
    cur, ch = 0, []
    for it in items:
        if it["chapter"]:
            ch.append((cur / FPS, it["chapter"]))
        cur += it["frames"]
    if ch:
        if ch[0][0] > 0.5:
            ch.insert(0, (0.0, "Intro"))
        with open(CHAPTERS_OUT, "w", encoding="utf-8") as f:
            for t, name in ch:
                f.write(f"{fmt_mmss(t)} {name}\n")
        print(f"[+] chapters: {len(ch)} -> {CHAPTERS_OUT} (paste into the YouTube description)")


def step_premiere(args):
    data = load_data(find_json(args.json))
    segments = yt_segments(data)
    if not segments:
        die("No 'youtube' segments in the JSON.")
    items = build_items(segments, FPS, WIDTH, HEIGHT, CLIPS_DIR, CFG.get("fill", "pad"),
                        label="segments")
    music = make_music_bed(sum(i["frames"] for i in items), FPS)
    total, markers = write_premiere_xml(items, music)
    write_extras(items)
    write_shot_manifest(segments, default_video())

    slates = [i["id"] for i in items if i["kind"] == "slate"]
    print(f"\nDone. '{XML_OUT}' written: {len(items)} segments, {fmt_mmss(total / FPS)}.")
    if slates:
        print(f"[!] {len(slates)} placeholder slate(s) on V1 (missing footage): {', '.join(slates[:12])}"
              + (" ..." if len(slates) > 12 else "") + "\n    Add the footage (collect step), run this again - slates are replaced.")
    print("In Premiere: File > Import > pick the XML. Double-click the sequence in the Project panel.\n"
          + track_help(items))
    print_srt_help()
    print("Keep clips/, gfx/, audio_trim/" + (", char_layers/" if any(i.get("char_file") for i in items) else "")
          + " where they are.")
    reveal(".")


def write_concat_list(path, files):
    with open(path, "w", encoding="utf-8") as f:
        for p in files:
            q = os.path.abspath(p).replace(os.sep, "/").replace("'", "'\\''")
            f.write(f"file '{q}'\n")




# ====================================================================
# STEP 4B: one finished video (picture + voice-over [+ original audio] [+ music])
# ====================================================================
def join_av(items, out, vlist_name, music=None):
    """Concats the picture clips and mixes narration (+ ducked original audio + music) into one mp4."""
    os.makedirs(TIKTOK_TEMP, exist_ok=True)
    vlist = os.path.join(TIKTOK_TEMP, f"{vlist_name}_video.txt")
    alist = os.path.join(TIKTOK_TEMP, f"{vlist_name}_audio.txt")
    olist = os.path.join(TIKTOK_TEMP, f"{vlist_name}_orig.txt")
    write_concat_list(vlist, [i["video_file"] for i in items])
    write_concat_list(alist, [i["audio_file"] for i in items])
    use_orig = any(i["orig_file"] for i in items)
    if use_orig:
        files = []
        for i in items:
            if i["orig_file"]:
                files.append(i["orig_file"])
            else:
                sf = os.path.join(TRIM_DIR, f"{i['fps']}fps", f"{i['id']}_sil.wav")
                files.append(silent_wav(i["frames"], i["fps"], sf))
        write_concat_list(olist, files)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", vlist,
           "-f", "concat", "-safe", "0", "-i", alist]
    n_audio = 1
    if use_orig:
        cmd += ["-f", "concat", "-safe", "0", "-i", olist]
        n_audio += 1
    if music:
        cmd += ["-i", music]
        n_audio += 1
    if n_audio == 1:
        cmd += ["-map", "0:v:0", "-map", "1:a:0"]
    else:
        ins = "".join(f"[{k}:a]" for k in range(1, n_audio + 1))
        cmd += ["-filter_complex", f"{ins}amix=inputs={n_audio}:duration=longest:dropout_transition=0,"
                                   f"volume={n_audio}[a]", "-map", "0:v:0", "-map", "[a]"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE),
            "-shortest", "-movflags", "+faststart", out]
    res = run(cmd)
    if res.returncode != 0 or not os.path.exists(out):
        die(f"Could not join the clips:\n{tail(res.stderr)}")


def step_video(args):
    data = load_data(find_json(args.json))
    segments = yt_segments(data)
    if not segments:
        die("No 'youtube' segments in the JSON.")
    items = build_items(segments, FPS, WIDTH, HEIGHT, CLIPS_DIR, CFG.get("fill", "pad"),
                        gfx=False, label="segments", characters="burn")
    for i in items:
        i["fps"] = FPS
    total = sum(i["frames"] for i in items) / FPS
    music = make_music_bed(sum(i["frames"] for i in items), FPS)
    print(f"\nJoining {len(items)} clips into {FINAL_OUT} ...")
    join_av(items, FINAL_OUT, "full", music)
    write_timeline_srt(items)
    got = get_duration(FINAL_OUT)
    print(f"\nDone. {FINAL_OUT}  ({got:.1f}s, expected {total:.1f}s)")
    if any(i["rank"] not in (None, "") or i["caption"] for i in items):
        print("[i] Number/caption graphics are NOT burned into the mp4 - use the Premiere XML for those.")
    if any(i.get("char_name") for i in items):
        print("[i] Characters ARE baked into this mp4. For a separate, movable character layer use the Premiere XML / VideoPad project.")
    if abs(got - total) > 1.0:
        print("[!] The length is off by more than a second - please send me a screenshot of this window.")
    reveal(FINAL_OUT)


# ====================================================================
# SUBTITLES (.srt) - text comes from the narration, timing from the real audio
# ====================================================================
PAUSE_W = {".": 8, "!": 8, "?": 8, "\u2026": 8, ",": 4, ";": 5, ":": 5, "\u2014": 4, "\u2013": 3}
ABBREVS = {"mr.", "mrs.", "ms.", "dr.", "st.", "vs.", "jr.", "sr.", "prof.", "mt.", "no."}


def sub_text(seg):
    """Subtitle text: the optional "subtitle" field if present (use it when you respell a
    name for the voice), otherwise the narration itself."""
    t = seg.get("subtitle") or seg.get("narration") or ""
    return strip_tags(t)


def split_sentences(text):
    parts = [p.strip() for p in re.findall(r'.*?(?:[.!?\u2026]+["\'\u201d\u2019)\]]*(?:\s+|$)|$)', text, re.S)
             if p.strip()]
    out = []
    for p in parts:
        if out and out[-1].split()[-1].lower() in ABBREVS:
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def wrap_lines(text, maxc, max_lines):
    """Wraps into at most max_lines lines; two lines are balanced."""
    words = text.split()
    if len(text) <= maxc:
        return [text]
    if max_lines == 2 and len(words) > 1:
        best = None
        for i in range(1, len(words)):
            a, b = " ".join(words[:i]), " ".join(words[i:])
            score = max(len(a), len(b))
            if best is None or score < best[0]:
                best = (score, a, b)
        if best[0] <= maxc:
            return [best[1], best[2]]
    return textwrap.wrap(text, maxc) or [text]


def make_cues(text, start, dur, maxc, max_lines):
    """Splits one narration into subtitle cues spread over [start, start+dur].
    Returns [(t0, t1, 'line1\\nline2'), ...]."""
    text = " ".join(text.split())
    if not text or dur <= 0:
        return []

    def fits(s):
        return len(textwrap.wrap(s, maxc)) <= max_lines

    def chunk_words(s):
        out, cur = [], ""
        for w in s.split():
            cand = (cur + " " + w).strip()
            if cur and not fits(cand):
                out.append(cur)
                cur = w
            else:
                cur = cand
        if cur:
            out.append(cur)
        return out

    units = []
    for s in split_sentences(text):
        if fits(s):
            units.append(s)
            continue
        for cl in re.split(r"(?<=[,;:])\s+", s):
            units.extend([cl] if fits(cl) else chunk_words(cl))

    cues, cur = [], ""
    for u in units:
        cand = (cur + " " + u).strip()
        ended = bool(cur) and cur[-1] in ".!?\u2026\"'\u201d\u2019)"
        if cur and (not fits(cand) or (ended and len(cur) >= maxc * 0.7)):
            cues.append(cur)
            cur = u
        else:
            cur = cand
    if cur:
        cues.append(cur)

    # How long each cue stays up: proportional to how much is spoken, with a little extra
    # weight for the natural pause after commas / full stops (not after the very last one).
    weights = []
    for c in cues:
        w = sum(ch.isalnum() for ch in c) + sum(PAUSE_W.get(ch, 0) for ch in c)
        weights.append(max(1.0, float(w)))
    tail = len(cues[-1]) - len(cues[-1].rstrip(".!?\u2026,;:\"'\u201d\u2019)"))
    weights[-1] = max(1.0, weights[-1] - sum(PAUSE_W.get(ch, 0) for ch in cues[-1][len(cues[-1]) - tail:]))

    total = sum(weights)
    out, acc = [], 0.0
    for c, w in zip(cues, weights):
        t0 = start + dur * acc / total
        acc += w
        t1 = start + dur * acc / total
        out.append((t0, t1, "\n".join(wrap_lines(c, maxc, max_lines))))
    return out


def srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path, timeline, fps):
    """timeline = [(text, frames), ...] played back to back at `fps`.
    Cue times line up with the Premiere sequence / the finished video."""
    sc = CFG.get("subtitles", {})
    maxc = int(sc.get("max_chars_per_line", 42))
    max_lines = int(sc.get("max_lines", 2))
    n, cur, lines = 0, 0, []
    for text, frames in timeline:
        start, dur = cur / fps, frames / fps
        cur += frames
        cues = make_cues(text, start, dur, maxc, max_lines)
        for i, (t0, t1, body) in enumerate(cues):
            n += 1
            # end exactly where the next cue starts (no overlaps, no flicker)
            lines.append(f"{n}\n{srt_time(t0)} --> {srt_time(t1)}\n{body}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return n


def write_timeline_srt(items):
    n = write_srt(SRT_OUT, [(i["text"], i["frames"]) for i in items], FPS)
    print(f"[+] subtitles: {n} cue(s) -> {SRT_OUT}")
    return n


def print_srt_help():
    print("In Premiere: File > Import the .srt, then drag it from the Project panel onto the "
          "timeline (above V1). It lands on a captions track you can style in Window > Text.")




def step_srt(args):
    """Subtitles only (no video rendering): same timeline as the Premiere XML."""
    need("ffmpeg", "ffprobe")
    data = load_data(find_json(args.json))
    segments = yt_segments(data)
    if not segments:
        die("No 'youtube' segments in the JSON.")
    items = build_items(segments, FPS, WIDTH, HEIGHT, CLIPS_DIR, CFG.get("fill", "pad"),
                        render=False, label="segments")
    write_extras(items)
    print_srt_help()
    reveal(SRT_OUT)


# ====================================================================
# STEP 5: TikTok (9:16, blurred background)
# ====================================================================
def step_tiktok(args):
    need("ffmpeg", "ffprobe")
    data = load_data(find_json(args.json))
    parts = tiktok_parts(data)
    if not parts:
        die("No 'tiktok' section in the JSON.")
    os.makedirs(TIKTOK_OUT, exist_ok=True)
    t = CFG["tiktok"]
    W, H, tfps = int(t["width"]), int(t["height"]), int(t["fps"])
    made = 0
    for part, clips in parts.items():
        print(f"\n=== TikTok: {part} ===")
        items = build_items(clips, tfps, W, H, TIKTOK_TEMP, "blur", gfx=False, label=f"{part} clips",
                            characters="burn")
        for i in items:
            i["fps"] = tfps
        music = make_music_bed(sum(i["frames"] for i in items), tfps, name=f"music_{part}")
        dest = os.path.join(TIKTOK_OUT, f"{part}.mp4")
        join_av(items, dest, part, music)
        made += 1
        print(f"SUCCESS: {dest}")
        srt_path = os.path.join(TIKTOK_OUT, f"{part}.srt")
        n_cues = write_srt(srt_path, [(i["text"], i["frames"]) for i in items], tfps)
        print(f"         subtitles: {srt_path} ({n_cues} cues)")
    if made == 0:
        die("No TikTok videos were produced.")
    print(f"\nDone. {made} video(s) in {TIKTOK_OUT}/")
    reveal(TIKTOK_OUT)


# ====================================================================
# STATUS + STATE.md
# ====================================================================
def status_lines(args_json=None):
    L = []
    L.append(f"Project : {os.path.basename(ROOT)}")
    L.append(f"Module  : {MODULE}   Topic: {PROJECT.get('topic') or '-'}   Style: {PROJECT.get('style')}")
    tg = PROJECT.get("target_length") or DEFAULT_TARGETS.get(MODULE, "")
    L.append(f"Target  : {tg}   TTS mode: {PROJECT.get('tts_mode')}   Music: {'on' if PROJECT.get('music') else 'off'}")
    dv = default_video()
    n_foot = len([f for f in glob.glob(FOOTAGE_DIR + "/*") if f.lower().endswith(VIDEO_EXTS)]) if os.path.isdir(FOOTAGE_DIR) else 0
    n_img = len([f for f in glob.glob(IMAGES_DIR + "/*") if f.lower().endswith(IMAGE_EXTS)]) if os.path.isdir(IMAGES_DIR) else 0
    if MODULE == "comic_recap":
        L.append(comic_status())
    else:
        L.append(f"Source  : {dv or 'no main video in folder'}   footage/: {n_foot} clip(s)   images/: {n_img}")
        L.append(f"Subtitles (.srt in subs/): {len(glob.glob(SUBS_DIR + '/*.srt'))}")
    L.append(f"Engine  : {CFG['tts']['engine'] or '-'}")
    clib = char_library(refresh=True)
    if clib or char_project().get("default"):
        L.append(f"Characters: {', '.join(v['name'] for v in clib.values()) or 'none in characters/'}   "
                 f"default: {char_project().get('default') or '-'}   auto: {char_project().get('auto') or 'off'}")
    nxt = []
    try:
        data = load_data(find_json(args_json))
    except SystemExit:
        L.append("segments.json: EMPTY - paste the JSON from Claude")
        return L, (["Import the comic, then give Claude the PDF(s) from comic_review/ + PASTE_THIS_TO_CLAUDE.txt"]
                   if MODULE == "comic_recap" and not comic_load_panels().get("pages")
                   else ["Get segments.json from Claude (see PASTE_THIS_TO_CLAUDE.txt)"])
    yt, tt, segs = yt_segments(data), tiktok_parts(data), all_segments(data)
    if not segs:
        L.append("segments.json: no segments yet")
        return L, ["Get segments.json from Claude (see PASTE_THIS_TO_CLAUDE.txt)"]
    have = sum(1 for s in segs if os.path.exists(os.path.join(AUDIO_DIR, f"{s['id']}.mp3")))
    need_vis = [s for s in yt if s.get("need_visual")]
    sheets_have = len(glob.glob(SHEETS_DIR + "/*.jpg"))
    miss = []
    for s in iter_segments(data):
        if s.get("id") and seg_media(s, dv)["kind"] == "slate":
            miss.append(s["id"])
    miss = sorted(set(miss))
    L.append(f"Segments: {len(yt)} youtube, {sum(len(v) for v in tt.values())} tiktok clips in {len(tt)} part(s)")
    L.append(f"Sheets  : {sheets_have} file(s), {len(need_vis)} segment(s) flagged need_visual")
    L.append(f"Footage : {len(miss)} segment(s) still without footage/still" + (f": {', '.join(miss[:10])}" if miss else ""))
    L.append(f"Audio   : {have} / {len(segs)} clips")
    L.append(f"Premiere XML: {'built' if os.path.exists(XML_OUT) else 'not built'}   "
             f"Full video: {'built' if os.path.exists(FINAL_OUT) else 'not built'}   "
             f"Subtitles: {'built' if os.path.exists(SRT_OUT) else 'not built'}   "
             f"TikTok: {len(glob.glob(TIKTOK_OUT + '/*.mp4'))} video(s)")
    if miss and MODULE not in RECAP_MODULES:
        nxt.append("Collect footage: run the collect step (missing shots show as slates in Premiere)")
    elif miss and MODULE == "comic_recap":
        nxt.append(f"{len(miss)} segment(s) point at a page/panel that does not exist: {', '.join(miss[:6])} (see the slate text)")
    elif miss:
        nxt.append(f"{len(miss)} segment(s) have no footage - check 'src' / file names")
    if have < len(segs):
        nxt.append("Generate the voice-over (preview a few segments first)")
    if have == len(segs) and not os.path.exists(XML_OUT) and not os.path.exists(FINAL_OUT):
        nxt.append("Build the Premiere XML (or the finished video for recaps)")
    if not nxt:
        nxt.append("Nothing pending - review the output, or edit segments.json and re-run a step")
    return L, nxt


def write_state(args_json=None):
    try:
        L, nxt = status_lines(args_json)
    except Exception:
        return
    with open(STATE_MD, "w", encoding="utf-8") as f:
        f.write("# STATE (auto-written by Recap Studio - paste this into a new chat to resume)\n\n")
        f.write(time.strftime("Updated: %Y-%m-%d %H:%M\n\n"))
        f.write("\n".join("- " + l for l in L) + "\n\n## Next\n")
        f.write("\n".join(f"{i}. {n}" for i, n in enumerate(nxt, 1)) + "\n")


def step_check(args):
    print(f"Tools\n")
    for t in ("ffmpeg", "ffprobe"):
        print(f"  {t:<9} {'OK' if shutil.which(t) else 'MISSING  -> run SETUP.bat'}")
    print(f"  {'yt-dlp':<9} {'OK' if ytdlp_cmd() else 'MISSING  -> run SETUP.bat (only needed for the collect step)'}")
    eng = CFG["tts"].get("engine")
    for name in ("chatterbox", "pocket"):
        if eng == name:
            print(f"  {name:<9} {'OK' if engine_python(name) else 'MISSING  -> run SETUP.bat (main folder)'}")
    for mod in (("requests", "edge_tts") + (("kokoro_onnx",) if CFG["tts"].get("engine") == "kokoro" else ())
                + (("PIL", "numpy", "fitz") if MODULE == "comic_recap" else (("PIL",) if char_library(True) else ()))):
        try:
            __import__(mod)
            print(f"  {mod:<9} OK")
        except ImportError:
            print(f"  {mod:<9} MISSING  -> run SETUP.bat")
    for k in ("ELEVENLABS_API_KEY", "MINIMAX_API_KEY"):
        raw = os.environ.get(k, "")
        n = len([x for x in raw.replace(" ", ",").split(",") if x.strip()])
        print(f"  {k:<19}: {str(n) + ' key(s)' if n else 'not set'}")
    print()
    L, nxt = status_lines(args.json)
    print("\n".join("  " + l for l in L))
    print("\n  NEXT:")
    for i, n in enumerate(nxt, 1):
        print(f"    {i}. {n}")
    write_state(args.json)
    print(f"\n  ({STATE_MD} updated)")
    if os.path.exists(os.path.join(AUDIO_DIR, "_manifest.json")):
        length_report(args)


# ====================================================================
# DEMO: synthetic media so you can test the whole pipeline (and Premiere import) in a minute
# ====================================================================
def demo_cutouts():
    """Two cartoon cut-outs (transparent PNG) so the character layer can be tried without any artwork."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False
    base = os.path.join(CHARS_DIR, "demo_buddy")
    os.makedirs(base, exist_ok=True)

    def buddy(mouth_open):
        im = Image.new("RGBA", (600, 900), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((150, 470, 450, 900), 90, fill=(52, 120, 220, 255), outline=(20, 50, 110, 255), width=8)
        d.ellipse((120, 80, 480, 470), fill=(255, 214, 160, 255), outline=(120, 70, 30, 255), width=8)
        d.ellipse((205, 220, 265, 290), fill=(255, 255, 255, 255), outline=(40, 40, 40, 255), width=5)
        d.ellipse((335, 220, 395, 290), fill=(255, 255, 255, 255), outline=(40, 40, 40, 255), width=5)
        d.ellipse((230, 245, 258, 280), fill=(30, 30, 30, 255))
        d.ellipse((360, 245, 388, 280), fill=(30, 30, 30, 255))
        if mouth_open:
            d.ellipse((240, 340, 360, 430), fill=(150, 30, 40, 255), outline=(60, 10, 20, 255), width=6)
        else:
            d.arc((235, 330, 365, 410), 20, 160, fill=(60, 10, 20, 255), width=8)
        return im
    buddy(False).save(os.path.join(base, "default.png"))
    buddy(True).save(os.path.join(base, "talk.png"))
    with open(os.path.join(base, "character.json"), "w", encoding="utf-8") as f:
        json.dump({"facing": "right"}, f)
    im = Image.new("RGBA", (500, 700), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((100, 260, 400, 690), 40, fill=(190, 195, 205, 255), outline=(60, 60, 70, 255), width=8)
    d.rounded_rectangle((130, 40, 370, 270), 40, fill=(210, 215, 225, 255), outline=(60, 60, 70, 255), width=8)
    d.ellipse((180, 110, 230, 160), fill=(255, 80, 60, 255))
    d.ellipse((270, 110, 320, 160), fill=(255, 80, 60, 255))
    d.rectangle((190, 200, 310, 220), fill=(60, 60, 70, 255))
    im.save(os.path.join(CHARS_DIR, "demo_robot.png"))
    return True


def step_demo(args):
    need("ffmpeg", "ffprobe")
    try:
        existing = all_segments(load_data(find_json(args.json)))
    except SystemExit:
        existing = []
    if existing and not args.force:
        die("This project already has segments. Run 'demo' in a FRESH project (or add --force to overwrite segments.json).")
    for d in (FOOTAGE_DIR, IMAGES_DIR, AUDIO_DIR):
        os.makedirs(d, exist_ok=True)

    def ff(*a):
        r = run(["ffmpeg", "-y", "-loglevel", "error"] + list(a))
        if r.returncode != 0:
            die(f"demo: ffmpeg failed\n{tail(r.stderr)}")

    ff("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=24:d=8", "-f", "lavfi", "-i", "sine=f=330:d=8",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", f"{FOOTAGE_DIR}/demo_a.mp4")
    ff("-f", "lavfi", "-i", "testsrc=s=640x480:r=30:d=8", "-f", "lavfi", "-i", "sine=f=523:d=8",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", f"{FOOTAGE_DIR}/demo_b_4x3.mp4")
    ff("-f", "lavfi", "-i", "testsrc2=s=1000x1000:d=1", "-frames:v", "1", f"{IMAGES_DIR}/demo_still.png")
    have_chars = demo_cutouts()
    lens = {"d_01": 3.2, "d_02": 4.0, "d_03": 3.0, "d_04": 3.0, "d_05": 4.0, "d_06": 4.0}
    for sid, ln in lens.items():
        # a tone that "speaks" in short bursts, so the character's mouth has something to follow
        ff("-f", "lavfi", "-i", f"aevalsrc=0.6*sin(2*PI*220*t)*gt(sin(2*PI*2.5*t)\\,-0.2):d={ln}:s=44100",
           "-c:a", "libmp3lame", f"{AUDIO_DIR}/{sid}.mp3")
    demo = {"youtube": [
        {"id": "d_01", "src": "demo_a.mp4", "src_start": "00:00:00", "src_end": "00:00:08", "keep_audio": True,
         "chapter": "Intro", "caption": "Chapter one starts here", "narration": "This is the first demo segment."},
        {"id": "d_02", "src": "demo_b_4x3.mp4", "src_start": "00:00:01", "src_end": "00:00:07", "rank": 3,
         "caption": "Third place", "narration": "A four by three clip gets pillarboxed."},
        {"id": "d_03", "image": "demo_still.png", "rank": 2, "caption": "Second place",
         "narration": "A still image with a slow zoom."},
        {"id": "d_04", "rank": 1, "chapter": "Finale", "caption": "First place",
         "shot": {"description": "Test shot that does not exist yet", "queries": ["demo clip youtube", "demo clip x", "demo image"],
                  "fallback": "any b-roll"}, "narration": "This shot is missing, so you get a slate."},
        {"id": "d_05", "src": "demo_a.mp4", "src_start": "00:00:06", "src_end": "00:00:08",
         "narration": "Short footage, long voice: the last frame is held."}], "tiktok": {}}
    if have_chars:                       # character animation: corner over a clip, other side, robot, solo scene
        yt = demo["youtube"]
        yt[0].update({"character": "demo_buddy"})
        yt[1].update({"character": "demo_buddy", "char_pos": "bottom-left", "char_anim": "talk+sway"})
        yt[2].update({"character": "demo_robot", "char_pos": "bottom-right", "char_enter": "pop"})
        yt[4].update({"character": "demo_robot", "char_pos": "right", "char_anim": "float"})
        yt.append({"id": "d_06", "commentary": True, "character": "demo_buddy",
                   "narration": "And this is a solo commentary scene: no footage, just the character on a background."})
    with open("segments.json", "w", encoding="utf-8") as f:
        json.dump(demo, f, indent=2)
    print("Demo media + audio + segments.json created. Now run: Build Premiere XML, import it, "
          "and tell me what you see on V1/V2/A1/A2 and whether the markers appear.")


# ====================================================================
# ====================================================================
# COMIC / MANGA RECAP  (module "comic_recap")
#   .cbz / .cbr / .pdf  ->  pages/p001.png ...  ->  numbered panels
#   -> comic_review/*.pdf for Claude  ->  segments point at page + panel
#   -> a virtual camera (zoom / pan / swipe) is rendered over the panels
# ====================================================================
COMIC_SRC_EXTS = (".cbz", ".cbr", ".cb7", ".zip", ".rar", ".7z", ".pdf", ".epub")
PAGES_DIR = "pages"
PANELS_FILE = os.path.join(PAGES_DIR, "panels.json")
REVIEW_DIR = "comic_review"
COMIC_TMP = "_comic_tmp"
COMIC_VER = "c1"
COMIC_MAX_PX = 5000          # longest page side kept on disk (bigger scans are shrunk)
_COMIC = None


def ccfg():
    return CFG.get("comic", {})


def comic_need_pil():
    try:
        import PIL  # noqa
        import numpy  # noqa
    except ImportError:
        die("The comic module needs Pillow and numpy. Run SETUP.bat again "
            "(or:  pip install pillow numpy pymupdf).")


# --------------------------------------------------------------------
# 1. find + unpack the comic file
# --------------------------------------------------------------------
def comic_sources(override=None):
    if override:
        if not os.path.isfile(override):
            die(f"Comic file not found: {override}")
        return [override]
    found, seen = [], set()
    for folder in (".", "comic", FOOTAGE_DIR):
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            if (os.path.isfile(p) and f.lower().endswith(COMIC_SRC_EXTS)
                    and os.path.abspath(p) not in seen):
                seen.add(os.path.abspath(p))
                found.append(p)
    found.sort(key=lambda p: natural_key(os.path.basename(p)))
    return found


def comic_kind(path):
    """Looks at the first bytes, not the extension (many .cbr files are really zips)."""
    with open(path, "rb") as f:
        head = f.read(8)
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK"):
        return "zip"
    if head.startswith(b"Rar!"):
        return "rar"
    if head.startswith(b"7z\xbc\xaf"):
        return "7z"
    ext = os.path.splitext(path)[1].lower()
    return {".pdf": "pdf", ".cbr": "rar", ".rar": "rar", ".cb7": "7z", ".7z": "7z"}.get(ext, "zip")


def _images_under(folder):
    out = []
    for root, _, files in os.walk(folder):
        if "__macosx" in root.lower():
            continue
        for f in files:
            if f.lower().endswith(IMAGE_EXTS) and not f.startswith("."):
                out.append(os.path.join(root, f))
    out.sort(key=lambda p: natural_key(os.path.relpath(p, folder)))
    return out


def comic_unpack(path, tmp):
    """-> list of image files (reading order) extracted into `tmp`."""
    kind = comic_kind(path)
    os.makedirs(tmp, exist_ok=True)
    if kind == "zip":
        import zipfile
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist()
                     if n.lower().endswith(IMAGE_EXTS) and "__macosx" not in n.lower()
                     and not os.path.basename(n).startswith(".")]
            names.sort(key=natural_key)
            out = []
            for i, n in enumerate(names):
                dst = os.path.join(tmp, f"{i:05d}{os.path.splitext(n)[1].lower()}")
                with z.open(n) as s, open(dst, "wb") as o:
                    shutil.copyfileobj(s, o)
                out.append(dst)
        return out
    if kind in ("rar", "7z"):
        tools = []
        for exe in ("7z", "7zz", "7za"):
            if shutil.which(exe):
                tools.append([exe, "x", "-y", f"-o{tmp}", path])
        w7 = r"C:\Program Files\7-Zip\7z.exe"
        if os.path.isfile(w7):
            tools.append([w7, "x", "-y", f"-o{tmp}", path])
        if shutil.which("unar"):
            tools.append(["unar", "-q", "-o", tmp, path])
        if shutil.which("unrar"):
            tools.append(["unrar", "x", "-y", "-inul", path, tmp + os.sep])
        for exe in ("bsdtar", "tar"):          # Windows 10/11 ships bsdtar as tar.exe (reads RAR)
            if shutil.which(exe):
                tools.append([exe, "-xf", path, "-C", tmp])
        for cmd in tools:
            try:
                run(cmd)
            except OSError:
                continue
            files = _images_under(tmp)
            if files:
                return files
        die(f"Could not open {os.path.basename(path)} ({kind.upper()}). Fixes, easiest first:\n"
            "  1. Rename .cbr to .cbz and try again (many are really zip files).\n"
            "  2. Install 7-Zip (winget install 7zip.7zip) and run this step again.\n"
            "  3. Open it in a comic reader and export / print it to PDF.")
    if kind == "pdf":
        try:
            import fitz  # PyMuPDF
            out = []
            doc = fitz.open(path)
            for i, pg in enumerate(doc):
                r = pg.rect
                z = min(4.0, max(1.0, 3000.0 / max(r.width, r.height, 1)))
                dst = os.path.join(tmp, f"{i:05d}.png")
                pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False).save(dst)
                out.append(dst)
            if out:
                return out
        except ImportError:
            pass
        if shutil.which("pdftoppm"):
            run(["pdftoppm", "-r", "200", "-png", path, os.path.join(tmp, "pg")])
            files = sorted(glob.glob(os.path.join(tmp, "pg*.png")), key=natural_key)
            if files:
                return files
        die("Reading a PDF needs PyMuPDF.  Run SETUP.bat again (or:  pip install pymupdf).")
    die(f"Unsupported comic file: {path}")


def comic_save_page(src, dst):
    from PIL import Image
    im = Image.open(src)
    im.load()
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, (255, 255, 255))
        flat.paste(im, mask=im.split()[3])
        im = flat
    else:
        im = im.convert("RGB")
    big = max(im.size)
    if big > COMIC_MAX_PX:
        f = COMIC_MAX_PX / big
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    im.save(dst, "PNG", compress_level=3)
    return im.size


# --------------------------------------------------------------------
# 2. panel detection (gutter / XY-cut) - plain numpy, no OpenCV
# --------------------------------------------------------------------
def _best_gap(is_gap, min_gut, min_side, frac=None, edge_min=0.30):
    """Longest run of gutter samples with real content on both sides -> (start, end) | None.
    With `frac` (ink fraction per line) a gutter must also be bounded by a line-like edge on both
    sides (a panel border or dense art), so white manga panels with sparse drawings are not cut in half."""
    n, best, i = len(is_gap), None, 0
    while i < n:
        if is_gap[i]:
            j = i
            while j < n and is_gap[j]:
                j += 1
            edged = (frac is None or (float(max(frac[max(0, i - 3):i])) >= edge_min
                                      and float(max(frac[j:j + 3])) >= edge_min))
            if j - i >= min_gut and i >= min_side and n - j >= min_side and edged:
                if best is None or (j - i) > (best[1] - best[0]):
                    best = (i, j)
            i = j
        else:
            i += 1
    return best


def comic_detect(img, rtl=False):
    """Panels as pixel boxes (x0, y0, x1, y1) in reading order."""
    import numpy as np
    from PIL import Image
    W, H = img.size
    k = 800.0 / max(W, H)
    sw, sh = max(16, int(W * k)), max(16, int(H * k))
    g = np.asarray(img.convert("L").resize((sw, sh), Image.BILINEAR), dtype=np.int16)
    b = max(1, int(0.012 * max(sw, sh)))
    border = np.concatenate([g[:b].ravel(), g[-b:].ravel(), g[:, :b].ravel(), g[:, -b:].ravel()])
    bg = int(np.bincount((border // 4).astype(np.int64), minlength=64).argmax() * 4 + 2)
    fg = np.abs(g - bg) > 28
    eps = 0.010
    min_gut = max(2, int(0.010 * max(sw, sh)))
    min_side = max(4, int(0.05 * min(sw, sh)))
    found = []

    def cut(x0, y0, x1, y1, depth=0):
        sub = fg[y0:y1, x0:x1]
        if sub.size == 0:
            return
        ys = np.nonzero(sub.mean(axis=1) > eps)[0]
        xs = np.nonzero(sub.mean(axis=0) > eps)[0]
        if len(ys) == 0 or len(xs) == 0:
            return
        y0, y1 = y0 + int(ys[0]), y0 + int(ys[-1]) + 1
        x0, x1 = x0 + int(xs[0]), x0 + int(xs[-1]) + 1
        sub = fg[y0:y1, x0:x1]
        rows, cols = sub.mean(axis=1), sub.mean(axis=0)
        if depth < 10:
            gh = _best_gap(rows <= eps, min_gut, min_side, rows)       # rows first = reading order
            if gh:
                cut(x0, y0, x1, y0 + gh[0], depth + 1)
                cut(x0, y0 + gh[1], x1, y1, depth + 1)
                return
            gv = _best_gap(cols <= eps, min_gut, min_side, cols)
            if gv:
                parts = [(x0, y0, x0 + gv[0], y1), (x0 + gv[1], y0, x1, y1)]
                if rtl:
                    parts.reverse()
                for p in parts:
                    cut(*p, depth + 1)
                return
        found.append((x0, y0, x1, y1))

    cut(0, 0, sw, sh)
    keep = [(x0, y0, x1, y1) for x0, y0, x1, y1 in found
            if (x1 - x0) >= 0.06 * sw and (y1 - y0) >= 0.05 * sh
            and (x1 - x0) * (y1 - y0) >= 0.012 * sw * sh]
    if not keep:
        ys, xs = np.nonzero(fg.any(axis=1))[0], np.nonzero(fg.any(axis=0))[0]
        keep = [(int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1)] if len(xs) and len(ys) \
            else [(0, 0, sw, sh)]
    out = []
    for x0, y0, x1, y1 in keep:
        out.append([max(0, int(x0 / k) - 2), max(0, int(y0 / k) - 2),
                    min(W, int(math.ceil(x1 / k)) + 2), min(H, int(math.ceil(y1 / k)) + 2)])
    return out


# --------------------------------------------------------------------
# 3. review images + PDFs for Claude (numbered panels)
# --------------------------------------------------------------------
def comic_mode():
    return "auto" if str(ccfg().get("panel_mode", "claude")).lower() == "auto" else "claude"


def comic_grid(v, fs):
    """Thin 0.1-step ruler grid with labels, so Claude can read box coordinates off the page."""
    from PIL import Image, ImageDraw, ImageFont
    fp = find_font()
    try:
        small = ImageFont.truetype(fp, max(13, int(fs * 0.55))) if fp else ImageFont.load_default()
    except Exception:
        small = ImageFont.load_default()
    ov = Image.new("RGBA", v.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i in range(1, 10):
        x, y = round(v.width * i / 10), round(v.height * i / 10)
        d.line((x, 0, x, v.height), fill=(0, 190, 255, 85), width=1)
        d.line((0, y, v.width, y), fill=(0, 190, 255, 85), width=1)
    for i in range(0, 11):
        lab = f"{i / 10:.1f}"
        x, y = round(v.width * i / 10), round(v.height * i / 10)
        tw = d.textlength(lab, font=small)
        for pos in ((min(max(x - tw / 2, 1), v.width - tw - 1), 2), (min(max(x - tw / 2, 1), v.width - tw - 1), v.height - small.size - 4)):
            d.rectangle((pos[0] - 1, pos[1] - 1, pos[0] + tw + 1, pos[1] + small.size + 1), fill=(0, 60, 90, 215))
            d.text(pos, lab, font=small, fill=(255, 255, 255, 255))
        for xx in (2, v.width - tw - 3):
            d.rectangle((xx - 1, y - small.size / 2 - 1, xx + tw + 1, y + small.size / 2 + 1), fill=(0, 60, 90, 215))
            d.text((xx, y - small.size / 2), lab, font=small, fill=(255, 255, 255, 255))
    return Image.alpha_composite(v.convert("RGBA"), ov).convert("RGB")


def comic_review_image(page_no, im, panels, annotate=True, grid=False):
    from PIL import Image, ImageDraw, ImageFont
    max_h = int(ccfg().get("review_height", 1700))
    s = min(1.0, max_h / im.height)
    v = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS) if s < 1 else im.copy()
    fs = max(24, int(v.height * 0.028))
    fp = find_font()
    try:
        font = ImageFont.truetype(fp, fs) if fp else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    if grid:
        v = comic_grid(v, fs)
    d = ImageDraw.Draw(v)
    pink, lw = (255, 0, 153), max(3, int(v.height * 0.0025))
    if annotate:
        for n, (x0, y0, x1, y1) in enumerate(panels, 1):
            r = (x0 * s, y0 * s, x1 * s - 1, y1 * s - 1)
            d.rectangle(r, outline=pink, width=lw)
            label = str(n)
            tw = d.textlength(label, font=font)
            d.rectangle((r[0], r[1], r[0] + tw + fs * 0.7, r[1] + fs * 1.35), fill=pink)
            d.text((r[0] + fs * 0.35, r[1] + fs * 0.12), label, font=font, fill=(255, 255, 255))
    band = int(fs * 1.9)
    out = Image.new("RGB", (v.width, v.height + band), (20, 20, 20))
    out.paste(v, (0, band))
    d2 = ImageDraw.Draw(out)
    d2.text((fs * 0.5, fs * 0.45), f"PAGE {page_no}" + (f"   ({len(panels)} panel{'s' if len(panels) != 1 else ''})" if annotate else "")
            + ("   ruler: 0.0 - 1.0 across and down" if grid else ""),
            font=font, fill=(255, 255, 255))
    return out


def comic_build_review(meta):
    from PIL import Image
    os.makedirs(REVIEW_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(REVIEW_DIR, "*")):
        try:
            os.remove(f)
        except OSError:
            pass
    auto = comic_mode() == "auto"
    annotate = auto and bool(ccfg().get("annotate", True))
    per = max(5, int(ccfg().get("pdf_pages", 30)))
    pages = meta["pages"]
    jpgs = []
    for i, pg in enumerate(pages):
        progress(i, len(pages), f"Review page {pg['page']}")
        im = Image.open(pg["file"]).convert("RGB")
        r = comic_review_image(pg["page"], im, pg["panels"], annotate, grid=not auto)
        jp = os.path.join(REVIEW_DIR, f"r{pg['page']:04d}.jpg")
        r.save(jp, "JPEG", quality=84)
        jpgs.append((pg["page"], jp))
    pdfs = []
    for part, start in enumerate(range(0, len(jpgs), per), 1):
        chunk = jpgs[start:start + per]
        name = os.path.join(REVIEW_DIR, f"comic_for_claude_part{part:02d}_p{chunk[0][0]:03d}-p{chunk[-1][0]:03d}.pdf")
        ims = [Image.open(p) for _, p in chunk]
        ims[0].save(name, "PDF", save_all=True, append_images=ims[1:], resolution=110.0, quality=84)
        for x in ims:
            x.close()
        pdfs.append(name)
    progress(len(pages), len(pages), "Review pages done")
    return pdfs


# --------------------------------------------------------------------
# 4. the import step
# --------------------------------------------------------------------
def comic_load_panels():
    global _COMIC
    if _COMIC is None:
        try:
            with open(PANELS_FILE, "r", encoding="utf-8") as f:
                _COMIC = json.load(f)
        except Exception:
            _COMIC = {"pages": []}
        _COMIC["_by"] = {p["page"]: p for p in _COMIC.get("pages", [])}
    return _COMIC


def step_comic(args):
    """Import a comic: unpack pages, find panels, write the numbered PDF(s) for Claude."""
    comic_need_pil()
    from PIL import Image
    rtl = str(PROJECT.get("reading", "ltr")).lower() == "rtl"
    os.makedirs(PAGES_DIR, exist_ok=True)
    sources = comic_sources(args.file)
    sig = [f"{os.path.basename(s)}:{os.path.getsize(s)}" for s in sources]
    meta = None
    if os.path.exists(PANELS_FILE):
        try:
            with open(PANELS_FILE, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = None
    reuse = (meta and meta.get("pages") and not args.force
             and (not sources or meta.get("sources") == sig)
             and meta.get("mode", "auto") == comic_mode()
             and all(os.path.exists(p["file"]) for p in meta["pages"]))
    if reuse:
        print(f"[i] Reusing the {len(meta['pages'])} imported pages (panels.json may contain your hand edits).")
        print("    Use 'force' to import the comic again and re-detect all panels.\n")
    else:
        if not sources:
            die("No comic found. Put a .cbz / .cbr / .pdf (or a .zip of page images) in this project "
                "folder, then run this step again.")
        for f in glob.glob(os.path.join(PAGES_DIR, "*")):
            try:
                os.remove(f)
            except OSError:
                pass
        shutil.rmtree(COMIC_TMP, ignore_errors=True)
        print("Importing:\n" + "\n".join("  " + s for s in sources) + "\n")
        pages, no = [], 0
        for si, src in enumerate(sources):
            tmp = os.path.join(COMIC_TMP, str(si))
            print(f"[{si + 1}/{len(sources)}] Unpacking {os.path.basename(src)} ({comic_kind(src).upper()}) ...")
            files = comic_unpack(src, tmp)
            if not files:
                die(f"No page images found inside {os.path.basename(src)}.")
            for fi, fpath in enumerate(files):
                no += 1
                progress(fi, len(files), f"{os.path.basename(src)}: page {fi + 1}/{len(files)}")
                dst = os.path.join(PAGES_DIR, f"p{no:03d}.png")
                try:
                    w, h = comic_save_page(fpath, dst)
                except Exception as e:
                    print(f"  [!] page {fi + 1} skipped ({e})")
                    no -= 1
                    continue
                im = Image.open(dst)
                pages.append({"page": no, "file": dst.replace("\\", "/"), "w": w, "h": h,
                              "source": os.path.basename(src), "auto": (det := comic_detect(im, rtl)),
                              "panels": det if comic_mode() == "auto" else []})
                im.close()
        shutil.rmtree(COMIC_TMP, ignore_errors=True)
        meta = {"_help": "Panels are [x0,y0,x1,y1] in pixels of the page image, in reading order. "
                         "You can edit them by hand, then run 'Import comic' again (without force) to refresh the PDFs. "
                         "'auto' = the script's own guess (used to snap Claude's boxes); 'panels' are used only in panel_mode auto.",
                "reading": "rtl" if rtl else "ltr", "mode": comic_mode(), "sources": sig, "pages": pages}
        with open(PANELS_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
    global _COMIC
    _COMIC = None
    npan = sum(len(p["panels"]) for p in meta["pages"])
    rd = 'right-to-left' if meta.get('reading') == 'rtl' else 'left-to-right'
    if comic_mode() == "claude":
        print(f"\n[+] {len(meta['pages'])} page(s) imported ({rd}). Claude will mark the panels itself (ruler grid on every page).")
    else:
        print(f"\n[+] {len(meta['pages'])} page(s), {npan} panel(s) detected ({rd} reading order)")
    odd = [p["page"] for p in meta["pages"] if len(p["panels"]) == 1 or len(p["panels"]) > 9] if comic_mode() == "auto" else []
    if odd:
        print(f"[i] Pages with 1 panel (splash?) or 10+ panels (check the numbering): {', '.join(map(str, odd[:30]))}")
    print("\nBuilding the numbered review pages + PDF(s) for Claude ...")
    pdfs = comic_build_review(meta)
    print("\n[+] Give these to Claude (one PDF per message), together with PASTE_THIS_TO_CLAUDE.txt:")
    for p in pdfs:
        print(f"      {p}   ({os.path.getsize(p) / 1e6:.1f} MB)")
    if comic_mode() == "claude":
        print("\nClaude points at panels with boxes: {\"page\": 7, \"focus\": [{\"box\": [0.05, 0.40, 0.52, 0.71]}]}  (fractions of the page).")
    else:
        print("\nPanel numbers shown in the PDF are what segments.json refers to: {\"page\": 7, \"focus\": [2]}.")
        print("If a page was split wrongly, edit pages/panels.json and run this step again (no force).")
    reveal(REVIEW_DIR)


# --------------------------------------------------------------------
# 5. segments -> camera targets
# --------------------------------------------------------------------
def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def comic_spec_to_target(spec, default_page, by):
    """One focus entry -> {"page", "box"} (px).  Raises ValueError with a readable message."""
    page = default_page
    panel = None
    box = None
    if isinstance(spec, dict):
        page = spec.get("page", default_page)
        panel = spec.get("panel", spec.get("panels"))
        box = spec.get("box")
        if panel is None and box is None:
            panel = "page"
    elif isinstance(spec, (list, tuple)) and len(spec) == 4 and all(_num(v) for v in spec):
        box = spec
    else:
        panel = spec
    if not _num(page) or int(page) not in by:
        raise ValueError(f"page {page!r} does not exist (comic has pages 1-{max(by) if by else 0})")
    pg = by[int(page)]
    W, H = pg["w"], pg["h"]
    if box is not None:
        if len(box) != 4 or not all(_num(v) for v in box):
            raise ValueError(f"bad box {box!r}")
        b = list(box)
        if max(b) <= 1.5:
            b = [b[0] * W, b[1] * H, b[2] * W, b[3] * H]
        b = [max(0, min(W, b[0])), max(0, min(H, b[1])), max(0, min(W, b[2])), max(0, min(H, b[3]))]
        if b[2] - b[0] < 8 or b[3] - b[1] < 8:
            raise ValueError(f"box {box!r} is empty")
        if ccfg().get("snap", True):
            best, bi = None, 0.0
            for a in pg.get("auto") or pg["panels"]:
                ix = max(0.0, min(b[2], a[2]) - max(b[0], a[0])) * max(0.0, min(b[3], a[3]) - max(b[1], a[1]))
                un = (b[2] - b[0]) * (b[3] - b[1]) + (a[2] - a[0]) * (a[3] - a[1]) - ix
                if un > 0 and ix / un > bi:
                    best, bi = a, ix / un
            if best is not None and bi >= 0.6:
                b = [float(v) for v in best]
        return {"page": int(page), "box": b}
    if isinstance(panel, str) and panel.strip().lower() in ("page", "full", "all", "whole"):
        return {"page": int(page), "box": [0, 0, W, H]}
    idx = []
    if _num(panel):
        idx = [int(panel)]
    elif isinstance(panel, str):
        for part in re.split(r"[,\s]+", panel.strip()):
            if not part:
                continue
            m = re.match(r"^(\d+)\s*[-:]\s*(\d+)$", part)
            if m:
                idx += list(range(int(m.group(1)), int(m.group(2)) + 1))
            elif part.isdigit():
                idx.append(int(part))
            else:
                raise ValueError(f"cannot read panel {part!r}")
    elif isinstance(panel, list):
        idx = [int(v) for v in panel if _num(v)]
    if not idx:
        raise ValueError(f"no panel given in {spec!r}")
    n = len(pg["panels"])
    if n == 0:
        raise ValueError(f"page {page}: panel numbers are not used in 'claude' mode - give a box, e.g. {{\"box\":[0.05,0.4,0.52,0.71]}}")
    for i in idx:
        if i < 1 or i > n:
            raise ValueError(f"page {page} has {n} panel(s), but panel {i} was asked for")
    return {"page": int(page), "box": _union([pg["panels"][i - 1] for i in idx])}


def comic_media(seg):
    """Where a comic segment's picture comes from -> a seg_media()-style dict."""
    data = comic_load_panels()
    by = data["_by"]
    if not by:
        return {"kind": "slate", "why": "comic not imported yet (run 'Import comic' first)"}
    focus = seg.get("focus", seg.get("panels", seg.get("panel")))
    if focus is None:
        focus = ["page"]
    if not isinstance(focus, list):
        focus = [focus]
    default_page = seg.get("page")
    if default_page is None and focus and isinstance(focus[0], dict):
        default_page = focus[0].get("page")
    targets = []
    try:
        for spec in focus:
            t = comic_spec_to_target(spec, default_page, by)
            pg = by[t["page"]]
            t.update(file=pg["file"], w=pg["w"], h=pg["h"])
            targets.append(t)
    except (ValueError, TypeError) as e:
        return {"kind": "slate", "why": f"comic: {e}"}
    return {"kind": "comic", "file": targets[0]["file"], "start": 0.0, "avail": 0.0, "targets": targets}


def comic_prepare(segments):
    """Fills in each segment's default entrance (page turn = swipe, next panel = swipe toward it)."""
    cfg = ccfg()
    rtl = str(comic_load_panels().get("reading", PROJECT.get("reading", "ltr"))).lower() == "rtl"
    prev = None
    for seg in segments:
        if not isinstance(seg, dict) or not (seg.get("page") is not None or seg.get("focus") is not None
                                             or seg.get("panel") is not None or seg.get("panels") is not None):
            continue
        m = comic_media(seg)
        if m["kind"] != "comic":
            prev = None
            continue
        want = str(seg.get("enter") or "auto").lower()
        first, last = m["targets"][0], m["targets"][-1]
        if want == "auto":
            if prev is None:
                want = "fade"
            elif prev["page"] != first["page"]:
                tp = str(cfg.get("page_turn", "slide")).lower()
                want = ("slide_right" if rtl else "slide_left") if tp == "slide" else tp
            elif str(cfg.get("same_panel_move", "slide")).lower() == "slide":
                pb, fb = prev["box"], first["box"]
                dx = ((fb[0] + fb[2]) - (pb[0] + pb[2])) / 2 / first["w"]
                dy = ((fb[1] + fb[3]) - (pb[1] + pb[3])) / 2 / first["h"]
                if max(abs(dx), abs(dy)) < 0.04:
                    want = "cut"
                elif abs(dx) >= abs(dy):
                    want = "slide_left" if dx > 0 else "slide_right"
                else:
                    want = "slide_up" if dy > 0 else "slide_down"
            else:
                want = "cut"
        seg["_enter"] = want
        prev = last


# --------------------------------------------------------------------
# 6. the virtual camera
# --------------------------------------------------------------------
def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _cwin(box, A, margin):
    """Smallest camera window (cx, cy, height) of aspect A that shows `box` plus a margin."""
    bw, bh = box[2] - box[0], box[3] - box[1]
    ww, wh = bw * (1 + 2 * margin), bh * (1 + 2 * margin)
    if ww / wh > A:
        wh = ww / A
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, wh)


def _lerp_win(a, b, f):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f,
            math.exp(math.log(a[2]) + (math.log(b[2]) - math.log(a[2])) * f))


ANCHORS = {"center": (0, 0), "left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1),
           "top-left": (-1, -1), "top-right": (1, -1), "bottom-left": (-1, 1), "bottom-right": (1, 1)}


def comic_motion_for(seg):
    mo = str(seg.get("motion") or "auto").lower().replace(" ", "_")
    if mo == "auto":
        mo = ["push_in", "drift", "push_in", "pull_out"][int(h8(seg.get("id", "x")), 16) % 4]
    return mo


def comic_single_path(seg, box, A, margin):
    """Start / end camera window for ONE panel."""
    cfg = ccfg()
    zoom = max(1.0, float(seg.get("zoom") or cfg.get("zoom", 1.12)))
    w0 = _cwin(box, A, margin)
    cx, cy, wh = w0
    bw, bh = box[2] - box[0], box[3] - box[1]
    ax, ay = ANCHORS.get(str(seg.get("anchor") or "center").lower(), (0, 0))
    mo = comic_motion_for(seg)
    sign = 1 if int(h8(seg.get("id", "x")), 16) % 2 == 0 else -1
    if mo == "still":
        return w0, w0, mo
    if mo in ("push_in", "shake"):
        return w0, (cx + ax * 0.16 * bw, cy + ay * 0.16 * bh, wh / zoom), mo
    if mo == "pull_out":
        return (cx + ax * 0.16 * bw, cy + ay * 0.16 * bh, wh / zoom), w0, mo
    if mo == "drift":
        return ((cx - sign * 0.025 * bw, cy - 0.02 * bh, wh / 1.05),
                (cx + sign * 0.025 * bw, cy + 0.02 * bh, wh / 1.05), mo)
    if mo.startswith("pan_"):
        zp = max(zoom, 1.3)
        wh2 = wh / zp
        ww2 = wh2 * A
        dirn = mo[4:]
        if dirn in ("left", "right"):
            d = max((bw - ww2) / 2, 0.08 * bw)
            s, e = (cx + d, cx - d) if dirn == "left" else (cx - d, cx + d)
            return (s, cy, wh2), (e, cy, wh2), mo
        if dirn in ("up", "down"):
            d = max((bh - wh2) / 2, 0.08 * bh)
            s, e = (cy + d, cy - d) if dirn == "up" else (cy - d, cy + d)
            return (cx, s, wh2), (cx, e, wh2), mo
    return w0, (cx, cy, wh / zoom), "push_in"


def comic_bg(page, clip, W, H):
    """Dark blurred copy of the panel that fills the frame behind it."""
    from PIL import Image, ImageFilter, ImageEnhance
    sw, sh = max(16, W // 8), max(16, H // 8)
    cr = page.crop((int(clip[0]), int(clip[1]), max(int(clip[0]) + 2, int(clip[2])),
                    max(int(clip[1]) + 2, int(clip[3]))))
    s = max(sw / cr.width, sh / cr.height)
    t = cr.resize((max(1, round(cr.width * s)), max(1, round(cr.height * s))), Image.BILINEAR)
    l, tp = (t.width - sw) // 2, (t.height - sh) // 2
    t = t.crop((l, tp, l + sw, tp + sh)).filter(ImageFilter.GaussianBlur(max(2, sw // 36)))
    t = ImageEnhance.Brightness(t).enhance(0.42)
    return t.resize((W, H), Image.BICUBIC)


def comic_compose(page, clips, bg, win, A, W, H, off=(0, 0), pop=1.0):
    """One frame: the parts of `page` inside camera `win` that belong to the chosen panels
    (`clips` = list of boxes), pasted over the blurred backdrop. Other panels never show."""
    from PIL import Image
    cx, cy, wh = win
    wh = wh / pop
    ww = wh * A
    wx0, wy0 = cx - ww / 2, cy - wh / 2
    s = W / ww
    fr = bg.copy()
    for clip in clips:
        vx0, vy0 = max(wx0, clip[0]), max(wy0, clip[1])
        vx1, vy1 = min(wx0 + ww, clip[2]), min(wy0 + wh, clip[3])
        if vx1 - vx0 < 1 or vy1 - vy0 < 1:
            continue
        dx0, dy0 = round((vx0 - wx0) * s), round((vy0 - wy0) * s)
        dx1, dy1 = round((vx1 - wx0) * s), round((vy1 - wy0) * s)
        dw, dh = dx1 - dx0, dy1 - dy0
        if dw < 2 or dh < 2:
            continue
        sb = (wx0 + dx0 / s, wy0 + dy0 / s, wx0 + dx1 / s, wy0 + dy1 / s)
        sb = (max(0.0, sb[0]), max(0.0, sb[1]), min(float(page.width), sb[2]), min(float(page.height), sb[3]))
        if sb[2] - sb[0] < 1 or sb[3] - sb[1] < 1:
            continue
        fr.paste(page.resize((dw, dh), Image.BICUBIC, box=sb), (dx0 + off[0], dy0 + off[1]))
    return fr


def comic_key(seg, m):
    parts = [f"{file_sig(t['file'])}|{[round(v) for v in t['box']]}" for t in m["targets"]]
    c = ccfg()
    return json.dumps([parts, comic_motion_for(seg), seg.get("zoom"), seg.get("anchor"), seg.get("_enter"),
                       seg.get("shake"), c.get("zoom"), c.get("margin"), c.get("enter_sec"), COMIC_VER], default=str)


def comic_note(seg, m):
    t = m["targets"]
    where = f"p{t[0]['page']}" + (f"+{len(t) - 1} more stop(s)" if len(t) > 1 else "")
    return f"comic {where}, {'glide' if len(t) > 1 else comic_motion_for(seg)}, enter={seg.get('_enter', 'cut')}"


def render_comic_clip(m, seg, frames, W, H, F, out):
    """Camera moves over the comic page(s); exactly `frames` frames, piped straight into ffmpeg."""
    from PIL import Image
    cfg = ccfg()
    A = W / H
    margin = float(cfg.get("margin", 0.04))
    targets = m["targets"]
    pages = {}
    for t in targets:
        if t["file"] not in pages:
            im = Image.open(t["file"])
            im.load()
            pages[t["file"]] = im.convert("RGB")
    # only the stops themselves are ever drawn (other panels on the page stay hidden)
    clips = {}
    for t in targets:
        clips.setdefault(t["file"], []).append(t["box"])
    bgs = {k: comic_bg(pages[k], _union(v), W, H) for k, v in clips.items()}

    n = len(targets)
    if n == 1:
        w_a, w_b, motion = comic_single_path(seg, targets[0]["box"], A, margin)
        wins = None
    else:
        wins = [_cwin(t["box"], A, margin) for t in targets]
        motion = "glide"

    enter = str(seg.get("_enter") or seg.get("enter") or "cut").lower()
    n_enter = 0 if enter == "cut" else max(2, min(int(round(float(cfg.get("enter_sec", 0.35)) * F)), int(frames * 0.45)))
    shake = motion == "shake" or bool(seg.get("shake"))

    log = out + ".log"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(F), "-i", "-", "-frames:v", str(frames)] + \
          [("veryfast" if x == "fast" else x) for x in X264] + [out]
    with open(log, "w") as lf:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=lf)
        try:
            for i in range(frames):
                u = (i + 0.5) / frames
                if wins is None:
                    win = _lerp_win(w_a, w_b, _ease(u) if motion != "still" else 0.0)
                    tgt = targets[0]
                else:
                    p = min(max(u * n - 0.5, 0.0), n - 1.0)
                    k = min(int(p), n - 2)
                    f = p - k
                    hold = 0.18
                    f = _ease((f - hold) / (1 - 2 * hold))
                    if targets[k]["file"] != targets[k + 1]["file"]:
                        f = 0.0 if (p - k) < 0.5 else 1.0
                    win = _lerp_win(wins[k], wins[k + 1], f)
                    tgt = targets[k + 1] if f >= 0.5 else targets[k]
                if shake:
                    t = i / F
                    amp = 0.014 * win[2] * math.exp(-t / 0.35)
                    win = (win[0] + amp * math.sin(2 * math.pi * 17 * t),
                           win[1] + amp * math.cos(2 * math.pi * 13 * t), win[2])
                off, pop, alpha = (0, 0), 1.0, 1.0
                if n_enter and i < n_enter:
                    e = _ease_out((i + 1) / n_enter)
                    if enter == "slide_left":
                        off = (round((1 - e) * W), 0)
                    elif enter == "slide_right":
                        off = (-round((1 - e) * W), 0)
                    elif enter == "slide_up":
                        off = (0, round((1 - e) * H))
                    elif enter == "slide_down":
                        off = (0, -round((1 - e) * H))
                    elif enter in ("fade", "pop"):
                        alpha = e
                        if enter == "pop":
                            pop = 0.9 + 0.1 * e
                fr = comic_compose(pages[tgt["file"]], clips[tgt["file"]], bgs[tgt["file"]], win, A, W, H, off, pop)
                if alpha < 1.0:
                    fr = Image.blend(bgs[tgt["file"]], fr, alpha)
                proc.stdin.write(fr.tobytes())
            proc.stdin.close()
        except BrokenPipeError:
            pass
        rc = proc.wait()
    if rc != 0 or not os.path.exists(out):
        err = ""
        try:
            err = open(log, "r").read()
        except OSError:
            pass
        raise RuntimeError(f"ffmpeg failed while rendering the comic clip:\n{tail(err)}")
    try:
        os.remove(log)
    except OSError:
        pass


def comic_status():
    meta = comic_load_panels()
    pages = meta.get("pages", [])
    pdfs = glob.glob(os.path.join(REVIEW_DIR, "*.pdf"))
    if not pages:
        return "Comic   : not imported yet (run 'Import comic')"
    return (f"Comic   : {len(pages)} page(s), {sum(len(p['panels']) for p in pages)} panel(s), "
            f"{len(pdfs)} PDF part(s) for Claude in {REVIEW_DIR}/")


def step_say(args):
    """Voice Lab: speak ONE text with the chosen engine (no project needed). Used by the browser."""
    global SEG_SPEED
    cfg = CFG
    t = cfg["tts"]
    if args.tts_file:
        with open(args.tts_file, "r", encoding="utf-8") as f:
            t.update(json.load(f))
    engine = args.engine or t.get("engine", "edge")
    t["engine"] = engine
    if not args.text_file or not args.out:
        die("say needs --text-file and --out")
    with open(args.text_file, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        die("There is no text to speak.")
    if engine == "elevenlabs" and not t.get("elevenlabs_voice_id"):
        t["elevenlabs_voice_id"] = "21m00Tcm4TlvDq8ikWAM"      # Rachel, so the Voice Lab never waits on a question
    v3 = engine == "elevenlabs" and str(t.get("elevenlabs_model", "eleven_v3")).lower() == "eleven_v3"
    if engine == "chatterbox" and (t.get("chatterbox_variant") or "turbo") == "turbo":
        PROJECT["tts_mode"] = "light"                  # Voice Lab: let Turbo perform [laugh] etc.
    text = " ".join(text.replace("*", "").split()) if v3 else engine_text(text, engine, cfg)
    if not text:
        die("Only tags were found - nothing to speak.")
    try:
        SEG_SPEED = max(0.6, min(1.4, float(t.get("seg_speed", 1) or 1))) if engine in SPEED_ENGINES else 1.0
    except (TypeError, ValueError):
        SEG_SPEED = 1.0
    maker = {"edge": make_edge, "kokoro": make_kokoro, "chatterbox": make_chatterbox, "pocket": make_pocket,
             "elevenlabs": make_elevenlabs, "minimax": make_minimax}.get(engine, make_edge)
    generate = maker(cfg, False)
    tmp = args.out + ".part"
    try:
        generate(text, tmp)
    except SystemExit:
        raise
    except Exception as e:
        die(f"{engine} could not make the audio: {e}")
    if not os.path.isfile(tmp) or os.path.getsize(tmp) < 200:
        die(f"{engine} returned no audio.")
    os.replace(tmp, args.out)
    print(f"[+] {args.out}")


def step_timeline(args):
    import timeline
    timeline.step_timeline(sys.modules[__name__], args)


def step_remotion(args):
    import timeline
    timeline.step_remotion(sys.modules[__name__], args)


def step_scenes(args):
    import scenes
    scenes.step_scenes(sys.modules[__name__], args)


def step_briefs(args):
    """Scene authoring from the menu: write SCENE_AUTHORING_PROMPT.txt (pass 2), import SCENE_REPLY.txt if present,
    or with --demo add demo motion briefs to the project."""
    import authoring
    base = studio_base()
    if getattr(args, "demo", False):
        print(authoring.demo_briefs(ROOT))
        return
    reply = os.path.join(ROOT, "SCENE_REPLY.txt")
    if os.path.isfile(reply):
        with open(reply, "r", encoding="utf-8", errors="replace") as f:
            res = authoring.import_reply(ROOT, f.read())
        print(f"Imported {len(res['imported'])} scene(s) from SCENE_REPLY.txt: {', '.join(res['imported']) or '-'}")
        for name, why in res["skipped"]:
            print(f"  [skipped] {name}: {why}")
        for w in res["warnings"]:
            print(f"  [!] {w}")
        print("Next: 'Check scenes'.")
        return
    p = authoring.build_prompt(ROOT, base, force=bool(getattr(args, "force", False)))
    if not p["count"]:
        print("No scenes to write: " + (f"{len(p['skipped'])} already written and up to date (use --force to write them again)."
              if p["skipped"] else "no segment in segments.json has a motion brief."))
        return
    print(f"Wrote {authoring.PROMPT_FILE} for {p['count']} scene(s): {', '.join(p['ids'])}.")
    print("Paste it to Claude, save Claude's whole reply as SCENE_REPLY.txt in the project folder, then run this step again to import it.")


def step_preview(args):
    import scenes
    scenes.step_preview(sys.modules[__name__], args)


STEPS = {"init": step_init, "module": step_module, "subs": step_subs, "index": step_index,
         "sheets": step_sheets, "say": step_say, "comic": step_comic, "collect": step_collect, "tts": step_tts, "review": step_review,
         "premiere": step_premiere, "videopad": step_videopad, "video": step_video, "srt": step_srt, "tiktok": step_tiktok,
         "check": step_check, "demo": step_demo, "characters": step_characters,
         "missing": step_missing, "collect_one": step_collect_one,
         "timeline": step_timeline, "remotion": step_remotion, "scenes": step_scenes, "preview": step_preview, "briefs": step_briefs}
NO_STATE = ("init", "module", "demo", "missing", "collect_one", "say", "scenes", "preview", "briefs")


def main():
    ap = argparse.ArgumentParser(description="Recap Studio engine")
    ap.add_argument("step", choices=STEPS)
    ap.add_argument("--video")
    ap.add_argument("--json")
    ap.add_argument("--pick", action="store_true", help="tts: choose engine/voice again")
    ap.add_argument("--force", action="store_true", help="redo existing outputs")
    ap.add_argument("--only", help="tts: comma-separated segment ids to (re)voice")
    ap.add_argument("--preview", action="store_true", help="tts: voice a few segments into audio_preview/")
    ap.add_argument("--import", dest="do_import", action="store_true", help="review: import edits from the CSV")
    ap.add_argument("--simple", action="store_true", help="videopad: picture + voice only (one muxed file per segment)")
    ap.add_argument("--retry", action="store_true", help="collect: ask again for skipped shots")
    ap.add_argument("--engine", choices=("edge", "kokoro", "chatterbox", "pocket", "elevenlabs", "minimax"), help="tts: skip the engine prompt")
    ap.add_argument("--yes", action="store_true", help="auto-confirm destructive / re-voice prompts")
    ap.add_argument("--id", help="collect_one: segment id")
    ap.add_argument("--url", help="collect_one: source URL")
    ap.add_argument("--range", help="collect_one: optional 'start-end' time range")
    ap.add_argument("--file", help="collect_one: local media file to copy in  |  comic: the .cbz/.cbr/.pdf to import")
    ap.add_argument("--skip", action="store_true", help="collect_one: mark the shot as skipped")
    ap.add_argument("--text-file", help="say: UTF-8 text file to speak")
    ap.add_argument("--tts-file", help="say: JSON file with tts setting overrides")
    ap.add_argument("--out", help="say: output mp3")
    ap.add_argument("--demo", action="store_true", help="scenes: install the demo scenes (reference + deliberately broken)")
    args = ap.parse_args()
    try:
        STEPS[args.step](args)
        if args.step not in NO_STATE:
            write_state(args.json)
    except KeyboardInterrupt:
        die("Cancelled.")
    except KeyError as e:
        die(f"Your segments JSON is missing a field: {e}")


if __name__ == "__main__":
    main()
