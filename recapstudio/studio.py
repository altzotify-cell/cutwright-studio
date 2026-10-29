#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recap Studio — local web UI.

Run this file (or double-click START_UI.bat) and it opens a browser tab
that drives the whole video pipeline. Standard library only — no new deps.
"""
import glob
import json
import mimetypes
import os
import atexit
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(BASE, "_template")
PROJECTS = os.path.join(BASE, "Projects")
WEB = os.path.join(BASE, "web")
ENGINE_SRC = os.path.join(TEMPLATE, "recap.py")
PROMPT_AUTHORING = "PASTE_THIS_TO_CLAUDE_scene_authoring.txt"
LAB_DIR = os.path.join(BASE, "_voicelab")      # scratch folder for the Voice Lab (no project needed)
LAB_ENGINES = ("edge", "kokoro", "chatterbox", "pocket", "elevenlabs", "minimax")
LAB_KEYS = ("edge_", "kokoro_", "chatterbox_", "pocket_", "elevenlabs_", "minimax_", "seg_speed", "tts_normalize")
VOICES_DIR = os.path.join(BASE, "voices")        # reference clips for voice cloning (Chatterbox / Pocket TTS)
VOICE_EXTS = (".wav", ".mp3", ".flac", ".m4a", ".ogg")
PY = sys.executable

VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts", ".mts",
              ".m2ts", ".wmv", ".flv", ".mpg", ".mpeg")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff")
MUSIC_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac")

MODULES = [
    ("movie_recap", "Movie recap"),
    ("show_recap", "Show recap"),
    ("nba_minidoc", "NBA mini-doc"),
    ("nba_story", "NBA story"),
    ("real_story", "Real story"),
    ("ranking", "Ranking / top-N"),
    ("comic_recap", "Comic / manga recap"),
]
RECAP_MODULES = ("movie_recap", "show_recap", "comic_recap")
COMIC_EXTS = (".cbz", ".cbr", ".cb7", ".zip", ".rar", ".7z", ".pdf", ".epub")
DEFAULT_TARGETS = {"movie_recap": "10:00", "show_recap": "10:00", "nba_minidoc": "8:00",
                   "nba_story": "3:00", "real_story": "6:00", "ranking": "6:00", "comic_recap": "8:00"}

ENGINES = [
    ("edge", "Edge-TTS (free, unlimited)"),
    ("kokoro", "Kokoro (free, local, offline)"),
    ("chatterbox", "Chatterbox (free, local, voice cloning, emotion + [laugh] tags)"),
    ("pocket", "Pocket TTS (free, local, CPU-friendly, voice cloning)"),
    ("elevenlabs", "ElevenLabs (multi-key, premade voices)"),
    ("minimax", "MiniMax (multi-key, speech-2.6-hd)"),
]
EDGE_VOICES = [
    ("en-US-ChristopherNeural", "Christopher (classic recap narrator)"),
    ("en-US-GuyNeural", "Guy (natural / documentary)"),
    ("en-US-EricNeural", "Eric (deep / serious)"),
    ("en-US-JennyNeural", "Jenny (clear female narrator)"),
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
ENGINES_FILE = os.path.join(BASE, "models", "engines.json")   # written by SETUP.bat


def installed_engines():
    try:
        with open(ENGINES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


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
CHATTERBOX_TAGS = ["laugh", "chuckle", "cough", "sigh", "gasp", "groan", "yawn", "sniff", "clearing_throat"]
POCKET_VOICES = [
    ("alba", "Alba"), ("marius", "Marius"), ("javert", "Javert"), ("jean", "Jean"),
    ("fantine", "Fantine"), ("cosette", "Cosette"), ("eponine", "Eponine"), ("azelma", "Azelma"),
]
MINIMAX_VOICES = [
    ("male-qn-qingse", "Male Qingse (calm & clear narrator)"),
    ("presenter_male", "Presenter Male (broadcast voice)"),
    ("Wise_Woman", "Wise Woman (mature narrative)"),
    ("audiobook_male_1", "Audiobook Male (deep storyteller)"),
]

DEFAULT_PROJECT = {
    "module": "movie_recap", "topic": "", "style": "retell", "target_length": "",
    "platform": "youtube", "tts_mode": "plain", "voice_card": "",
    "fact_check": "off", "music": False, "captions": True, "reading": "ltr",
    "character": {"default": "", "auto": "off"},
}
DEFAULT_CONFIG = {
    "fps": 24, "width": 1920, "height": 1080, "sample_rate": 48000,
    "fill": "pad", "keep_audio_volume": 0.30, "music_volume": 0.12,
    "tts": {
        "engine": "", "edge_voice": "en-US-ChristopherNeural", "edge_rate": "+0%",
        "elevenlabs_voice_id": "", "elevenlabs_model": "eleven_v3",
        "elevenlabs_stability": 0.5, "minimax_voice": "male-qn-qingse",
        "kokoro_voice": "am_michael", "kokoro_speed": 1.0, "kokoro_voice2": "", "kokoro_mix": 0,
        "kokoro_sentence_pause": 0.25, "kokoro_clause_pause": 0.1,
        "chatterbox_variant": "turbo", "chatterbox_voice": "", "chatterbox_language": "en",
        "chatterbox_exaggeration": 0.5, "chatterbox_cfg_weight": 0.5, "chatterbox_temperature": 0.8,
        "chatterbox_seed": 0, "chatterbox_speed": 1.0, "chatterbox_device": "auto",
        "chatterbox_sentence_pause": 0.25,
        "pocket_voice": "alba", "pocket_temperature": 0.7, "pocket_lsd_steps": 1,
        "pocket_eos_threshold": -4.0, "pocket_speed": 1.0, "pocket_sentence_pause": 0.25,
        "tts_normalize": True,
    },
    "tiktok": {"width": 1080, "height": 1920, "fps": 30},
    "subtitles": {"max_chars_per_line": 42, "max_lines": 2},
    "character": {
        "corner_pos": "bottom-right", "corner_scale": 0.46, "solo_pos": "center", "solo_scale": 0.80,
        "max_width": 0.40, "solo_max_width": 0.80, "margin": 0.03, "idle": "talk",
        "enter": "slide", "exit": "slide", "solo_enter": "pop", "solo_exit": "fade",
        "enter_sec": 0.35, "exit_sec": 0.25, "shadow": True, "outline": "",
        "solo_bg": "gradient:#1b2030,#43305f", "mouth_threshold": 0.25, "codec": "qtrle",
    },
}

FOLDERS = ["footage", "images", "music", "characters", "sheets", "subs", "comic_review", "audio", "audio_preview",
           "clips", "gfx", "audio_trim"]
CHAR_EXTS = (".png", ".webp")

JOBS = {}
JOBS_LOCK = threading.Lock()
ACTIVE = {}          # project name -> job id (one active job per project)
ACTIVE_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def has_module(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


def load_keys():
    """Count API keys in keys.env without ever returning the values."""
    out = {"ELEVENLABS_API_KEY": 0, "MINIMAX_API_KEY": 0, "HF_TOKEN": 0}
    paths = [os.path.join(BASE, "keys.env"),
             os.path.join(os.path.dirname(BASE), "keys.env"),
             os.path.join(os.path.dirname(os.path.dirname(BASE)), "keys.env")]
    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            for line in open(p, "r", encoding="utf-8"):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k = line.split("=", 1)[0].strip()
                if k in out:
                    v = line.split("=", 1)[1].strip().strip("\"'")
                    out[k] = len([x for x in v.replace(" ", ",").split(",") if x.strip()])
        except Exception:
            pass
    return out


def get_first_key(name):
    paths = [os.path.join(BASE, "keys.env"),
             os.path.join(os.path.dirname(BASE), "keys.env"),
             os.path.join(os.path.dirname(os.path.dirname(BASE)), "keys.env")]
    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            for line in open(p, "r", encoding="utf-8"):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == name:
                    vals = [x.strip() for x in v.strip().strip("\"'").replace(" ", ",").split(",") if x.strip()]
                    if vals:
                        return vals[0]
        except Exception:
            pass
    return None


KEY_NAMES = ("ELEVENLABS_API_KEY", "MINIMAX_API_KEY", "HF_TOKEN")
KEY_PLACEHOLDER = "paste_your_key_here"
KEY_ALLOWED = re.compile(r"^[A-Za-z0-9_\-\.]+$")


def keys_file():
    return os.path.join(BASE, "keys.env")


def split_keys(v):
    return [x.strip() for x in re.split(r"[,\s]+", (v or "").strip().strip("\"'")) if x.strip()]


def keys_overview():
    """Per key name: how many keys are saved and the LAST 4 characters of each. Never the full key."""
    out = {n: [] for n in KEY_NAMES}
    p = keys_file()
    if os.path.isfile(p):
        try:
            for line in open(p, "r", encoding="utf-8"):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                if k in out:
                    out[k] = ["\u2022\u2022\u2022\u2022" + x[-4:] for x in split_keys(v)
                              if x != KEY_PLACEHOLDER]
        except Exception:
            pass
    return out


def save_keys(updates):
    """updates: {NAME: "key1, key2"}.  Empty string removes (comments out) that key.
    Only the known names (ElevenLabs, MiniMax, HF_TOKEN) are touched; every other line in keys.env is kept as it was."""
    p = keys_file()
    lines = []
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    for name, raw in updates.items():
        if name not in KEY_NAMES:
            raise ValueError("unknown key name: %s" % name)
        vals = split_keys(raw)
        if name == "HF_TOKEN" and len(vals) > 1:
            raise ValueError("HF_TOKEN: paste just one Hugging Face token.")
        for v in vals:
            if not KEY_ALLOWED.match(v):
                raise ValueError("%s: a key contains characters that are not allowed (spaces, quotes or symbols). "
                                 "Paste only the key itself." % name)
        new = ("%s=%s" % (name, ",".join(vals))) if vals else ("#%s=%s" % (name, KEY_PLACEHOLDER))
        active = [i for i, l in enumerate(lines)
                  if l.strip().startswith(name + "=") or l.strip().startswith(name + " =")]
        commented = [i for i, l in enumerate(lines)
                     if l.strip().startswith("#" + name + "=") or l.strip().startswith("# " + name + "=")]
        if active:
            lines[active[0]] = new
            for i in reversed(active[1:]):
                del lines[i]
        elif commented:
            lines[commented[0]] = new
        else:
            lines.append(new)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, p)


def venv_python(name):
    base = os.path.join(BASE, "venvs", name)
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        p = os.path.join(base, *rel)
        if os.path.isfile(p):
            return p
    return None


def to_clean_wav(path):
    """Convert an uploaded reference clip to mono 24 kHz 16-bit WAV next to it (the original is removed).
    Returns (file_name, converted?). A clip that is already a 16-bit WAV is left alone."""
    import wave
    try:
        if path.lower().endswith(".wav"):
            with wave.open(path, "rb") as w:
                if w.getsampwidth() == 2:
                    return os.path.basename(path), False
    except Exception:
        pass
    if not shutil.which("ffmpeg"):
        return os.path.basename(path), False
    out = os.path.splitext(path)[0] + ".wav"
    tmp_out = out + ".conv.wav"
    try:
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", "24000",
                            "-c:a", "pcm_s16le", tmp_out], capture_output=True, timeout=120)
        if r.returncode != 0 or not os.path.isfile(tmp_out):
            return os.path.basename(path), False
        if os.path.abspath(out) != os.path.abspath(path):
            os.remove(path)
        os.replace(tmp_out, out)
        return os.path.basename(out), True
    except Exception:
        try:
            if os.path.isfile(tmp_out):
                os.remove(tmp_out)
        except OSError:
            pass
        return os.path.basename(path), False


def voice_files():
    try:
        return sorted(f for f in os.listdir(VOICES_DIR)
                      if f.lower().endswith(VOICE_EXTS) and os.path.isfile(os.path.join(VOICES_DIR, f)))
    except OSError:
        return []


def tools_status():
    return {
        "python": PY,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
        "ytdlp": shutil.which("yt-dlp") is not None or has_module("yt_dlp"),
        "edge_tts": has_module("edge_tts"),
        "requests": has_module("requests"),
        "kokoro": has_module("kokoro_onnx"),
        "chatterbox": venv_python("chatterbox") is not None,
        "pocket": venv_python("pocket") is not None,
        "pillow": has_module("PIL"),
        "numpy": has_module("numpy"),
        "pymupdf": has_module("fitz"),
        "keys": load_keys(),
    }


def safe_name(name):
    name = (name or "").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .")
    return name


def project_dir(name):
    return os.path.join(PROJECTS, name)


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def deep_merge(base, update):
    out = json.loads(json.dumps(base))
    for k, v in (update or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def list_projects():
    if not os.path.isdir(PROJECTS):
        return []
    out = []
    for d in sorted(os.listdir(PROJECTS)):
        p = os.path.join(PROJECTS, d)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "recap.py")):
            out.append(d)
    return out


def engine_is_current(name):
    p = os.path.join(project_dir(name), "recap.py")
    if not os.path.isfile(p):
        return False
    try:
        txt = open(p, "r", encoding="utf-8").read()
    except Exception:
        return False
    return ("def step_missing" in txt and "def step_collect_one" in txt
            and "def find_all_videos" in txt and "def step_comic" in txt)


def ensure_engine(name):
    """Give a project the current engine (only when it is clearly outdated)."""
    p = os.path.join(project_dir(name), "recap.py")
    if not engine_is_current(name) and os.path.isfile(ENGINE_SRC):
        shutil.copyfile(ENGINE_SRC, p)
        return True
    return False


def preview_kind(fname):
    e = os.path.splitext(fname)[1].lower()
    if e in IMAGE_EXTS:
        return "image"
    if e in VIDEO_EXTS:
        return "video"
    if e in MUSIC_EXTS:
        return "audio"
    if e == ".pdf":
        return "pdf"
    return "other"


def project_detail(name):
    d = project_dir(name)
    if not os.path.isdir(d):
        return None
    proj = read_json(os.path.join(d, "project.json"), dict(DEFAULT_PROJECT))
    cfg = read_json(os.path.join(d, "config.json"), {})
    seg = read_json(os.path.join(d, "segments.json"), {"youtube": [], "tiktok": {}})
    state = ""
    sp = os.path.join(d, "STATE.md")
    if os.path.isfile(sp):
        try:
            state = open(sp, "r", encoding="utf-8").read()
        except Exception:
            pass

    yt = seg.get("youtube", []) if isinstance(seg, dict) else (seg if isinstance(seg, list) else [])
    tt = seg.get("tiktok", {}) if isinstance(seg, dict) else {}
    n_tt = sum(len(v) for v in tt.values()) if isinstance(tt, dict) else 0

    outputs = {
        "premiere": os.path.exists(os.path.join(d, "premiere_sequence.xml")),
        "videopad": os.path.exists(os.path.join(d, "videopad_project.vpj")),
        "video": os.path.exists(os.path.join(d, "recap_final.mp4")),
        "srt": os.path.exists(os.path.join(d, "recap_subtitles.srt")),
        "onscreen_srt": os.path.exists(os.path.join(d, "recap_onscreen.srt")),
        "chapters": os.path.exists(os.path.join(d, "chapters.txt")),
        "shot_manifest": os.path.exists(os.path.join(d, "shot_manifest.csv")),
        "credits": os.path.exists(os.path.join(d, "credits.txt")),
        "review_csv": os.path.exists(os.path.join(d, "review_sheet.csv")),
    }

    files = {}
    for folder in FOLDERS:
        fp = os.path.join(d, folder)
        if os.path.isdir(fp):
            items = []
            for f in sorted(os.listdir(fp)):
                full = os.path.join(fp, f)
                if os.path.isfile(full):
                    items.append({"name": f, "size": os.path.getsize(full),
                                  "kind": preview_kind(f)})
            files[folder] = items
    root_media = []
    for f in os.listdir(d):
        full = os.path.join(d, f)
        if os.path.isfile(full) and f.lower().endswith(VIDEO_EXTS + IMAGE_EXTS + COMIC_EXTS) \
                and not f.lower().startswith("tiktok_"):
            root_media.append({"name": f, "size": os.path.getsize(full), "kind": preview_kind(f)})

    prompt = ""
    pp = os.path.join(d, "PASTE_THIS_TO_CLAUDE.txt")
    if os.path.isfile(pp):
        try:
            prompt = open(pp, "r", encoding="utf-8").read()
        except Exception:
            pass

    shots = read_json(os.path.join(d, "shots.json"), {})

    return {
        "name": name,
        "folder": d,
        "project": proj,
        "config": cfg,
        "segment_counts": {"youtube": len(yt) if isinstance(yt, list) else 0, "tiktok": n_tt},
        "outputs": outputs,
        "files": files,
        "characters": character_library(d),
        "root_media": root_media,
        "prompt": prompt,
        "state": state,
        "shots": shots,
        "engine_current": engine_is_current(name),
    }


def character_library(d):
    """characters/ -> [{name, facing, poses: [{pose, file}]}] for the Characters tab (mirrors recap.py)."""
    base = os.path.join(d, "characters")
    out = {}
    if not os.path.isdir(base):
        return []
    for entry in sorted(os.listdir(base), key=lambda s: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]):
        if entry.startswith(("_", ".")) or entry.lower() == "backgrounds":
            continue
        p = os.path.join(base, entry)
        if os.path.isfile(p) and entry.lower().endswith(CHAR_EXTS):
            nm, pose = os.path.splitext(entry)[0], "default"
            if "__" in nm:
                nm, pose = nm.split("__", 1)
                pose = pose.lower().replace(" ", "_") or "default"
            ch = out.setdefault(nm.lower(), {"name": nm, "facing": "", "poses": []})
            if not any(x["pose"] == pose for x in ch["poses"]):
                ch["poses"].append({"pose": pose, "file": "characters/" + entry})
        elif os.path.isdir(p):
            ch = out.setdefault(entry.lower(), {"name": entry, "facing": "", "poses": []})
            for f in sorted(os.listdir(p)):
                if f.lower().endswith(CHAR_EXTS) and not f.startswith(("_", ".")):
                    pose = os.path.splitext(f)[0].lower().replace(" ", "_")
                    if not any(x["pose"] == pose for x in ch["poses"]):
                        ch["poses"].append({"pose": pose, "file": "characters/%s/%s" % (entry, f)})
            meta = read_json(os.path.join(p, "character.json"), {})
            if isinstance(meta, dict):
                ch["facing"] = str(meta.get("facing") or "")
    return [c for c in out.values() if c["poses"]]


def load_segments(name):
    return read_json(os.path.join(project_dir(name), "segments.json"), {"youtube": [], "tiktok": {}})


def authoring_module():
    """_template/authoring.py (stdlib only, no recap import): scene briefs, prompt export, reply import, status."""
    if TEMPLATE not in sys.path:
        sys.path.insert(0, TEMPLATE)
    import authoring
    return authoring


def scenes_overview(name):
    A = authoring_module()
    d = project_dir(name)
    theme = A.load_theme(d)
    return {"rows": A.status(d), "theme": (theme.get("name") or "") if theme else "", "has_theme": bool(theme),
            "has_timeline": os.path.isfile(os.path.join(d, "timeline.json")),
            "has_fix_prompt": os.path.isfile(os.path.join(d, A.FIX_PROMPT_FILE)),
            "has_proposed_theme": os.path.isfile(os.path.join(d, A.THEME_PROPOSED_FILE)),
            "segments": len(A.youtube_segments(d))}


# ---------------------------------------------------------------------------
# jobs (run engine steps in the background, stream logs)
# ---------------------------------------------------------------------------
STEP_LABELS = {"init": "Project setup", "subs": "Extract subtitles", "index": "Index footage",
               "sheets": "Contact sheets", "comic": "Import comic", "collect": "Collect footage", "collect_one": "Download / attach shot",
               "tts": "Voice-over", "review": "Review sheet", "premiere": "Build Premiere XML", "videopad": "Build VideoPad project",
               "video": "Build full video", "srt": "Build subtitles", "tiktok": "Build TikTok",
               "check": "Status check", "demo": "Demo media", "characters": "Check characters",
               "timeline": "Build timeline.json", "remotion": "Render with Remotion",
               "scenes": "Check scenes", "preview": "Preview scenes", "briefs": "Scene prompt"}
PROCS = {}           # job id -> subprocess.Popen (kept out of the JSON payload)
PROGRESS_PREFIX = "@@PROGRESS "


def start_job(project, step, args_list):
    jid = uuid.uuid4().hex[:12]
    label = STEP_LABELS.get(step, step)
    if step == "tts" and "--preview" in args_list:
        label = "Voice preview (3 segments)"
    job = {"id": jid, "project": project, "step": step, "label": label, "status": "running",
           "log": [], "exit_code": None, "started": time.time(), "finished": None,
           "progress": None, "stop_requested": False}
    with JOBS_LOCK:
        JOBS[jid] = job
    with ACTIVE_LOCK:
        ACTIVE[project] = jid
    threading.Thread(target=_run_job, args=(jid, project, step, args_list), daemon=True).start()
    return jid


def kill_tree(proc):
    """Stop the engine AND everything it started (ffmpeg, yt-dlp ...)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=15)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            for _ in range(20):
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def stop_job(jid):
    """-> True if a running job was asked to stop."""
    with JOBS_LOCK:
        job = JOBS.get(jid)
        proc = PROCS.get(jid)
        if not job or job["status"] != "running" or proc is None:
            return False
        job["stop_requested"] = True
        job["log"].append("[stopping ...]")
    kill_tree(proc)
    return True


def stop_all_jobs():
    for jid in list(PROCS):
        proc = PROCS.get(jid)
        if proc is not None and proc.poll() is None:
            kill_tree(proc)


atexit.register(stop_all_jobs)


def _run_job(jid, project, step, args_list):
    job = JOBS[jid]
    d = project_dir(project)
    cmd = [PY, "-u", "recap.py", step] + args_list
    env = os.environ.copy()
    env["RECAP_NONINTERACTIVE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, cwd=d, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace",
                                bufsize=1, env=env, **kw)
    except Exception as e:
        with JOBS_LOCK:
            job["status"] = "error"
            job["log"].append("[ERROR] could not start: %s" % e)
            job["exit_code"] = -1
            job["finished"] = time.time()
        with ACTIVE_LOCK:
            ACTIVE.pop(project, None)
        return
    PROCS[jid] = proc
    for line in iter(proc.stdout.readline, ""):
        if not line:
            continue
        line = line.rstrip("\n")
        if line.startswith(PROGRESS_PREFIX):
            parts = line[len(PROGRESS_PREFIX):].split(" ", 2)
            try:
                with JOBS_LOCK:
                    job["progress"] = {"done": int(parts[0]), "total": int(parts[1]),
                                       "label": parts[2] if len(parts) > 2 else "",
                                       "at": time.time()}
            except (ValueError, IndexError):
                pass
            continue
        with JOBS_LOCK:
            job["log"].append(line)
            if len(job["log"]) > 4000:
                job["log"] = job["log"][-4000:]
    proc.wait()
    PROCS.pop(jid, None)
    with JOBS_LOCK:
        job["exit_code"] = proc.returncode
        if job["stop_requested"]:
            job["status"] = "stopped"
            job["log"].append("[stopped by you]")
        else:
            job["status"] = "done" if proc.returncode == 0 else "error"
        job["finished"] = time.time()
    with ACTIVE_LOCK:
        ACTIVE.pop(project, None)


def jobs_summary():
    """Running jobs first, then the most recent finished ones (no logs)."""
    with JOBS_LOCK:
        rows = [{k: v for k, v in j.items() if k != "log"} for j in JOBS.values()]
    now = time.time()
    rows.sort(key=lambda j: (j["status"] != "running", -(j["finished"] or j["started"])))
    out = []
    for j in rows[:12]:
        j = dict(j)
        j["elapsed"] = (j["finished"] or now) - j["started"]
        out.append(j)
    return out


def job_payload(jid):
    with JOBS_LOCK:
        j = JOBS.get(jid)
        if not j:
            return None
        out = dict(j)
        out["elapsed"] = (j["finished"] or time.time()) - j["started"]
        return out


def run_sync(name, args_list, timeout=600):
    """Run a quick engine command synchronously; return (rc, stdout, stderr)."""
    d = project_dir(name)
    cmd = [PY, "recap.py"] + args_list
    env = os.environ.copy()
    env["RECAP_NONINTERACTIVE"] = "1"
    try:
        p = subprocess.run(cmd, cwd=d, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "timed out"
    except Exception as e:
        return -1, "", str(e)


def run_missing(name):
    ensure_engine(name)
    rc, out, err = run_sync(name, ["missing"])
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("["):
            try:
                return json.loads(line)
            except Exception:
                pass
    return {"error": (err or out or "could not read segments").strip()[-2000:]}


def extract_json(text):
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text or ""):
        if ch in "{[":
            try:
                obj, _ = decoder.raw_decode(text[i:])
                return obj
            except Exception:
                continue
    return None


def normalize_segments(obj):
    """Coerce whatever Claude pasted into {youtube: [...], tiktok: {...}}."""
    if isinstance(obj, list):
        return {"youtube": obj, "tiktok": {}}
    if isinstance(obj, dict):
        if "youtube" in obj or "tiktok" in obj:
            out = dict(obj)
            if not isinstance(out.get("youtube"), list):
                out["youtube"] = []
            if not isinstance(out.get("tiktok"), dict):
                out["tiktok"] = {}
            return out
        return {"youtube": [obj], "tiktok": {}}
    return {"youtube": [], "tiktok": {}}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8", ".md": "text/markdown; charset=utf-8",
    ".csv": "text/csv; charset=utf-8", ".srt": "text/plain; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
    ".flac": "audio/flac", ".ogg": "audio/ogg", ".aac": "audio/aac",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
}


def content_type(path):
    e = os.path.splitext(path)[1].lower()
    if e in CONTENT_TYPES:
        return CONTENT_TYPES[e]
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def serve_file(handler, path, ctype=None, download_name=None):
    if not os.path.isfile(path):
        handler.send_response(404)
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return
    size = os.path.getsize(path)
    ctype = ctype or content_type(path)
    rng = handler.headers.get("Range")
    if rng and rng.startswith("bytes="):
        try:
            a, b = rng[6:].split("-", 1)
            start = int(a) if a else 0
            end = int(b) if b else size - 1
        except Exception:
            start, end = 0, size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            handler.send_response(416)
            handler.send_header("Content-Range", "bytes */%d" % size)
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            return
        handler.send_response(206)
        handler.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        handler.send_header("Content-Length", str(end - start + 1))
        handler.send_header("Accept-Ranges", "bytes")
        handler.send_header("Content-Type", ctype)
        handler.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                remaining -= len(chunk)
        return
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(size))
    handler.send_header("Accept-Ranges", "bytes")
    if download_name:
        handler.send_header("Content-Disposition",
                            'attachment; filename="%s"' % download_name.replace('"', "_"))
    handler.end_headers()
    with open(path, "rb") as f:
        shutil.copyfileobj(f, handler.wfile)


def parse_path(handler):
    parsed = urllib.parse.urlsplit(handler.path)
    return urllib.parse.unquote(parsed.path), urllib.parse.parse_qs(parsed.query)


def q1(qs, key, default=""):
    v = qs.get(key)
    return v[0] if v else default


def projects_summary():
    out = []
    for name in list_projects():
        d = project_dir(name)
        proj = read_json(os.path.join(d, "project.json"), {})
        seg = read_json(os.path.join(d, "segments.json"), {"youtube": [], "tiktok": {}})
        yt = seg.get("youtube", []) if isinstance(seg, dict) else []
        tt = seg.get("tiktok", {}) if isinstance(seg, dict) else {}
        n_tt = sum(len(v) for v in tt.values()) if isinstance(tt, dict) else 0
        mtime = os.path.getmtime(d)
        out.append({
            "name": name,
            "module": proj.get("module", "movie_recap"),
            "topic": proj.get("topic", ""),
            "target_length": proj.get("target_length", ""),
            "platform": proj.get("platform", "youtube"),
            "segments": len(yt) if isinstance(yt, list) else 0,
            "tiktok_parts": n_tt,
            "updated": time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)),
            "has_video": os.path.exists(os.path.join(d, "recap_final.mp4")),
            "has_premiere": os.path.exists(os.path.join(d, "premiere_sequence.xml")),
            "engine_current": engine_is_current(name),
        })
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "RecapStudio/2"

    def log_message(self, fmt, *args):
        pass  # keep the console quiet

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:
            n = 0
        if n <= 0:
            return b""
        return self.rfile.read(n)

    def read_json_body(self):
        try:
            return json.loads(self.read_body().decode("utf-8"))
        except Exception:
            return None

    def origin_ok(self):
        """Block other websites (CSRF) and DNS-rebinding from talking to this local server."""
        port = self.server.server_address[1]
        allowed_hosts = ("127.0.0.1:%d" % port, "localhost:%d" % port)
        if (self.headers.get("Host") or "").lower() not in allowed_hosts:
            self.send_json({"error": "bad host"}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin.lower() not in tuple("http://" + h for h in allowed_hosts):
            self.send_json({"error": "cross-origin request blocked"}, 403)
            return False
        return True

    def require_project(self, name):
        if not os.path.isdir(project_dir(name)):
            self.send_json({"error": "project not found: %s" % name}, 404)
            return False
        return True

    def serve_project_file(self, name, relpath):
        d = project_dir(name)
        if not os.path.isdir(d):
            return self.send_json({"error": "project not found"}, 404)
        full = os.path.realpath(os.path.join(d, relpath))
        root = os.path.realpath(d)
        if full != root and not full.startswith(root + os.sep):
            return self.send_json({"error": "invalid path"}, 403)
        if not os.path.isfile(full):
            return self.send_json({"error": "file not found"}, 404)
        return serve_file(self, full)

    # ---- GET --------------------------------------------------------------
    def do_GET(self):
        if not self.origin_ok():
            return
        return self._do_GET()

    def _do_GET(self):
        path, qs = parse_path(self)
        if path in ("/", "/index.html"):
            return serve_file(self, os.path.join(WEB, "index.html"), "text/html; charset=utf-8")
        if path == "/style.css":
            return serve_file(self, os.path.join(WEB, "style.css"), "text/css; charset=utf-8")
        if path == "/app.js":
            return serve_file(self, os.path.join(WEB, "app.js"), "text/javascript; charset=utf-8")
        m = re.match(r"^/api/voicelab/audio/(lab_[0-9a-f_]+\.mp3)$", path)
        if m:
            full = os.path.join(LAB_DIR, "out", m.group(1))
            if not os.path.isfile(full):
                return self.send_json({"error": "file not found"}, 404)
            return serve_file(self, full, "audio/mpeg", m.group(1) if qs.get("download") else None)
        if path == "/api/bootstrap":
            return self.send_json({
                "modules": MODULES, "engines": ENGINES,
                "edge_voices": EDGE_VOICES, "minimax_voices": MINIMAX_VOICES, "kokoro_voices": KOKORO_VOICES,
                "chatterbox_variants": [v for v in CHATTERBOX_VARIANTS if v[0] in (installed_engines().get("chatterbox") or [v[0] for v in CHATTERBOX_VARIANTS])] or CHATTERBOX_VARIANTS,
                "chatterbox_langs": CHATTERBOX_LANGS if installed_engines().get("languages") == "all" else [l for l in CHATTERBOX_LANGS if l[0] == "en"],
                "setup_state": installed_engines(),
                "chatterbox_tags": CHATTERBOX_TAGS, "pocket_voices": POCKET_VOICES, "voice_files": voice_files(),
                "default_targets": DEFAULT_TARGETS, "default_project": DEFAULT_PROJECT,
                "default_config": DEFAULT_CONFIG, "tools": tools_status(),
            })
        if path == "/api/projects":
            return self.send_json(projects_summary())
        if path == "/api/keys":
            return self.send_json({"keys": keys_overview()})
        if path == "/guide":
            return serve_file(self, os.path.join(WEB, "guide.html"), "text/html; charset=utf-8")
        if path == "/api/tools":
            return self.send_json(tools_status())
        if path == "/api/jobs":
            return self.send_json({"jobs": jobs_summary()})
        m = re.match(r"^/api/jobs/([^/]+)$", path)
        if m:
            p = job_payload(m.group(1))
            return self.send_json(p if p is not None else {"error": "no such job"})
        m = re.match(r"^/api/projects/([^/]+)/missing$", path)
        if m:
            if not self.require_project(m.group(1)):
                return
            return self.send_json(run_missing(m.group(1)))
        m = re.match(r"^/api/projects/([^/]+)/segments$", path)
        if m:
            return self.send_json(load_segments(m.group(1)))
        m = re.match(r"^/api/projects/([^/]+)/scenes$", path)
        if m:
            return self.api_scenes_get(m.group(1))
        m = re.match(r"^/api/projects/([^/]+)/scenes/fixprompt$", path)
        if m:
            return self.api_scenes_fixprompt(m.group(1))
        m = re.match(r"^/api/projects/([^/]+)/file/(.+)$", path)
        if m:
            return self.serve_project_file(m.group(1), m.group(2))
        m = re.match(r"^/api/projects/([^/]+)$", path)
        if m:
            d = project_detail(m.group(1))
            return self.send_json(d if d else {"error": "project not found"}, 200 if d else 404)
        return self.send_json({"error": "not found"}, 404)

    # ---- POST -------------------------------------------------------------
    def do_POST(self):
        if not self.origin_ok():
            return
        return self._do_POST()

    def _do_POST(self):
        path, qs = parse_path(self)
        if path == "/api/projects":
            return self.create_project(self.read_json_body())
        if path == "/api/elevenlabs/voices":
            return self.api_elevenlabs_voices()
        if path == "/api/voicelab/say":
            return self.api_voicelab_say(self.read_json_body())
        if path == "/api/voices/upload":
            return self.api_voice_upload(qs)
        if path == "/api/keys":
            return self.api_save_keys(self.read_json_body())
        m = re.match(r"^/api/jobs/([^/]+)/stop$", path)
        if m:
            ok = stop_job(m.group(1))
            return self.send_json({"ok": ok} if ok else {"error": "That job is not running."}, 200 if ok else 404)
        m = re.match(r"^/api/projects/([^/]+)/settings$", path)
        if m:
            return self.api_settings(m.group(1), self.read_json_body())
        m = re.match(r"^/api/projects/([^/]+)/config$", path)
        if m:
            return self.api_config(m.group(1), self.read_json_body())
        m = re.match(r"^/api/projects/([^/]+)/segments$", path)
        if m:
            return self.api_segments(m.group(1), self.read_json_body())
        m = re.match(r"^/api/projects/([^/]+)/paste$", path)
        if m:
            return self.api_paste(m.group(1), self.read_json_body())
        m = re.match(r"^/api/projects/([^/]+)/scenes/(prompt|import|action|demo)$", path)
        if m:
            fn = {"prompt": self.api_scenes_prompt, "import": self.api_scenes_import, "action": self.api_scenes_action}.get(m.group(2))
            return fn(m.group(1), self.read_json_body()) if fn else self.api_scenes_demo(m.group(1))
        m = re.match(r"^/api/projects/([^/]+)/run$", path)
        if m:
            return self.api_run(m.group(1), self.read_json_body())
        m = re.match(r"^/api/projects/([^/]+)/upload$", path)
        if m:
            return self.api_upload(m.group(1), qs)
        m = re.match(r"^/api/projects/([^/]+)/character$", path)
        if m:
            return self.api_character(m.group(1), self.read_json_body())
        m = re.match(r"^/api/projects/([^/]+)/download$", path)
        if m:
            return self.api_collect(m.group(1), self.read_json_body())
        m = re.match(r"^/api/projects/([^/]+)/skip$", path)
        if m:
            return self.api_skip(m.group(1), self.read_json_body())
        m = re.match(r"^/api/projects/([^/]+)/sync$", path)
        if m:
            return self.api_sync(m.group(1))
        m = re.match(r"^/api/projects/([^/]+)/open$", path)
        if m:
            return self.api_open(m.group(1))
        return self.send_json({"error": "not found"}, 404)

    # ---- actions ----------------------------------------------------------
    def create_project(self, body):
        name = safe_name((body or {}).get("name", ""))
        if not name:
            return self.send_json({"error": "Project name is required."}, 400)
        dest = project_dir(name)
        if os.path.exists(dest):
            return self.send_json({"error": "A project with that name already exists."}, 409)
        if not os.path.isdir(TEMPLATE):
            return self.send_json({"error": "The _template folder is missing."}, 500)
        try:
            shutil.copytree(TEMPLATE, dest)
        except Exception as e:
            return self.send_json({"error": "Could not create project: %s" % e}, 500)
        proj = deep_merge(DEFAULT_PROJECT, (body or {}).get("project") or {})
        write_json(os.path.join(dest, "project.json"), proj)
        chosen = "PASTE_THIS_TO_CLAUDE_%s.txt" % proj.get("module", "movie_recap")
        chosen_path = os.path.join(dest, chosen)
        if os.path.isfile(chosen_path):
            shutil.copyfile(chosen_path, os.path.join(dest, "PASTE_THIS_TO_CLAUDE.txt"))
        for f in os.listdir(dest):
            if f.startswith("PASTE_THIS_TO_CLAUDE_") and f.endswith(".txt"):
                try:
                    os.remove(os.path.join(dest, f))
                except OSError:
                    pass
        for d in ("footage", "images", "music", "characters"):
            os.makedirs(os.path.join(dest, d), exist_ok=True)
        return self.send_json(project_detail(name))

    def api_settings(self, name, body):
        if not self.require_project(name):
            return
        d = project_dir(name)
        existing = read_json(os.path.join(d, "project.json"), dict(DEFAULT_PROJECT))
        new = deep_merge(existing, (body or {}).get("project") or {})
        write_json(os.path.join(d, "project.json"), new)
        # refresh the module-specific Claude prompt if it changed
        chosen = "PASTE_THIS_TO_CLAUDE_%s.txt" % new.get("module", "movie_recap")
        chosen_path = os.path.join(d, chosen)
        if not os.path.isfile(chosen_path):          # project was made as another module: take it from _template
            chosen_path = os.path.join(TEMPLATE, chosen)
        if os.path.isfile(chosen_path):
            shutil.copyfile(chosen_path, os.path.join(d, "PASTE_THIS_TO_CLAUDE.txt"))
        return self.send_json({"ok": True})

    def api_config(self, name, body):
        if not self.require_project(name):
            return
        d = project_dir(name)
        existing = read_json(os.path.join(d, "config.json"), {})
        new = deep_merge(existing, (body or {}).get("config") or {})
        write_json(os.path.join(d, "config.json"), new)
        return self.send_json({"ok": True})

    def api_segments(self, name, body):
        if not self.require_project(name):
            return
        seg = (body or {}).get("segments")
        if seg is None:
            return self.send_json({"error": "No segments provided."}, 400)
        p = os.path.join(project_dir(name), "segments.json")
        if os.path.exists(p):
            shutil.copyfile(p, p + ".bak")
        write_json(p, normalize_segments(seg))
        return self.send_json({"ok": True})

    def api_paste(self, name, body):
        if not self.require_project(name):
            return
        text = (body or {}).get("text") or ""
        obj = extract_json(text)
        if obj is None:
            return self.send_json({"error": "No JSON found in the pasted text."}, 400)
        seg = normalize_segments(obj)
        p = os.path.join(project_dir(name), "segments.json")
        if os.path.exists(p):
            shutil.copyfile(p, p + ".bak")
        write_json(p, seg)
        yt = len(seg["youtube"])
        tt = sum(len(v) for v in seg["tiktok"].values())
        out = {"ok": True, "youtube": yt, "tiktok": tt}
        try:  # Phase 3: plain-language check of motion briefs / transitions, and theme.json from the script's "theme"
            A = authoring_module()
            v = A.validate_script(seg)
            out.update(motion=v["motion"], errors=v["errors"], warnings=v["warnings"],
                       theme_messages=A.apply_theme(project_dir(name), seg))
        except Exception as e:  # never let the extra check break the import
            out["check_failed"] = str(e)
        return self.send_json(out)

    # ---- scenes (Phase 3) -------------------------------------------------
    def api_scenes_get(self, name):
        if not self.require_project(name):
            return
        return self.send_json(scenes_overview(name))

    def api_scenes_prompt(self, name, body):
        if not self.require_project(name):
            return
        A = authoring_module()
        b = body or {}
        only = [str(x) for x in b.get("only")] if isinstance(b.get("only"), list) else None
        res = A.build_prompt(project_dir(name), BASE, only=only, force=bool(b.get("force")))
        return self.send_json(res)

    def api_scenes_import(self, name, body):
        if not self.require_project(name):
            return
        text = (body or {}).get("text") or ""
        if not text.strip():
            return self.send_json({"error": "Paste Claude's reply first."}, 400)
        res = authoring_module().import_reply(project_dir(name), text)
        res["has_timeline"] = os.path.isfile(os.path.join(project_dir(name), "timeline.json"))
        return self.send_json(res)

    def api_scenes_action(self, name, body):
        if not self.require_project(name):
            return
        b = body or {}
        if b.get("what") not in ("fallback", "unfallback", "retry", "discard"):
            return self.send_json({"error": "unknown action"}, 400)
        msg = authoring_module().action(project_dir(name), str(b.get("id") or ""), b["what"])
        return self.send_json({"ok": True, "message": msg})

    def api_scenes_demo(self, name):
        if not self.require_project(name):
            return
        return self.send_json({"ok": True, "message": authoring_module().demo_briefs(project_dir(name))})

    def api_scenes_fixprompt(self, name):
        if not self.require_project(name):
            return
        return self.send_json({"text": authoring_module().fix_prompt_text(project_dir(name))})

    def api_run(self, name, body):
        if not self.require_project(name):
            return
        ensure_engine(name)
        step = (body or {}).get("step")
        if step not in ("init", "subs", "index", "sheets", "comic", "collect", "tts", "review",
                        "premiere", "videopad", "video", "srt", "tiktok", "check", "demo", "characters",
                        "timeline", "remotion", "scenes", "preview"):
            return self.send_json({"error": "unknown step: %s" % step}, 400)
        flags = (body or {}).get("flags") or {}
        args = []
        for f in ("preview", "force", "yes", "retry", "pick", "simple", "demo"):
            if flags.get(f):
                args.append("--" + f)
        if flags.get("import"):
            args.append("--import")
        for k, flag in (("engine", "--engine"), ("only", "--only"),
                        ("video", "--video"), ("json", "--json")):
            if flags.get(k):
                args += [flag, str(flags[k])]
        with ACTIVE_LOCK:
            if ACTIVE.get(name):
                return self.send_json({"error": "This project already has a step running.",
                                       "job": ACTIVE.get(name)}, 409)
        jid = start_job(name, step, args)
        return self.send_json({"job": jid})

    def _start_collect_job(self, name, args):
        ensure_engine(name)
        with ACTIVE_LOCK:
            if ACTIVE.get(name):
                return self.send_json({"error": "This project already has a step running.",
                                       "job": ACTIVE.get(name)}, 409)
        jid = start_job(name, "collect_one", args)
        return self.send_json({"job": jid})

    def api_collect(self, name, body):
        if not self.require_project(name):
            return
        sid = (body or {}).get("id")
        url = (body or {}).get("url")
        rng = (body or {}).get("range")
        if not sid:
            return self.send_json({"error": "Segment id is required."}, 400)
        if not url:
            return self.send_json({"error": "URL is required."}, 400)
        args = ["--id", sid, "--url", url]
        if rng:
            args += ["--range", rng]
        return self._start_collect_job(name, args)

    def api_skip(self, name, body):
        if not self.require_project(name):
            return
        sid = (body or {}).get("id")
        if not sid:
            return self.send_json({"error": "Segment id is required."}, 400)
        return self._start_collect_job(name, ["--id", sid, "--skip"])

    def api_upload(self, name, qs):
        if not self.require_project(name):
            return
        folder = q1(qs, "folder", "footage")
        if folder not in ("footage", "images", "music", "characters", "root"):
            return self.send_json({"error": "folder must be footage, images, music, characters or root"}, 400)
        fname = os.path.basename(q1(qs, "name", "") or "upload.bin")
        if folder == "characters":
            return self.api_character_upload(name, qs, fname)
        attach_id = q1(qs, "id", "")
        d = project_dir(name)
        if not attach_id:
            return self._stream_upload(d, folder, fname)
        data = self.read_body()
        if not data:
            return self.send_json({"error": "no file data received"}, 400)
        if attach_id:
            ensure_engine(name)
            ext = os.path.splitext(fname)[1].lower()
            tmp_dir = os.path.join(d, "_uploads")
            os.makedirs(tmp_dir, exist_ok=True)
            tmp = os.path.join(tmp_dir, uuid.uuid4().hex + ext)
            with open(tmp, "wb") as f:
                f.write(data)
            rc, out, err = run_sync(name, ["collect_one", "--id", attach_id, "--file", tmp])
            try:
                os.remove(tmp)
                os.rmdir(tmp_dir)
            except OSError:
                pass
            return self.send_json({"ok": rc == 0, "stdout": out[-1500:], "stderr": err[-1500:]})

    def api_character_upload(self, name, qs, fname):
        """A cut-out for the character library: characters/<sub>/<fname> (sub = the character, fname = pose.png)."""
        d = project_dir(name)
        if not fname.lower().endswith(CHAR_EXTS):
            return self.send_json({"error": "Characters must be transparent .png (or .webp) files."}, 400)
        sub = safe_name(q1(qs, "sub", ""))
        base = os.path.join(d, "characters")
        os.makedirs(base, exist_ok=True)
        if not sub:
            return self._stream_upload(d, "characters", safe_name(fname) or "character.png")
        folder = os.path.join(base, sub)
        flat = [os.path.join(base, sub + e) for e in CHAR_EXTS if os.path.isfile(os.path.join(base, sub + e))]
        if flat and not os.path.isdir(folder):          # a single-file character gets its own folder when it gets a pose
            os.makedirs(folder)
            shutil.move(flat[0], os.path.join(folder, "default" + os.path.splitext(flat[0])[1]))
        return self._stream_upload(d, os.path.join("characters", sub), safe_name(fname) or "default.png")

    def api_character(self, name, body):
        """Delete a pose / a whole character, or set which way its art faces."""
        if not self.require_project(name):
            return
        body = body or {}
        base = os.path.realpath(os.path.join(project_dir(name), "characters"))
        ch = safe_name(body.get("name", ""))
        if not ch or not os.path.isdir(base):
            return self.send_json({"error": "character name is required."}, 400)
        action = body.get("action")
        if action == "facing":
            folder = os.path.join(base, ch)
            flat = [os.path.join(base, ch + e) for e in CHAR_EXTS if os.path.isfile(os.path.join(base, ch + e))]
            if flat and not os.path.isdir(folder):
                os.makedirs(folder)
                shutil.move(flat[0], os.path.join(folder, "default" + os.path.splitext(flat[0])[1]))
            if not os.path.isdir(folder):
                return self.send_json({"error": "no such character."}, 404)
            mp = os.path.join(folder, "character.json")
            meta = read_json(mp, {})
            meta = meta if isinstance(meta, dict) else {}
            f = str(body.get("facing") or "")
            if f in ("left", "right"):
                meta["facing"] = f
            else:
                meta.pop("facing", None)
            write_json(mp, meta)
            return self.send_json({"ok": True})
        if action != "delete":
            return self.send_json({"error": "unknown action."}, 400)
        pose = safe_name(body.get("pose", ""))
        targets = []
        if pose:
            for e in CHAR_EXTS:
                targets += [os.path.join(base, ch, pose + e), os.path.join(base, "%s__%s%s" % (ch, pose, e))]
                if pose == "default":
                    targets.append(os.path.join(base, ch + e))
        else:
            targets = [os.path.join(base, ch)] + [os.path.join(base, ch + e) for e in CHAR_EXTS]
            for f in os.listdir(base):
                if f.lower().startswith(ch.lower() + "__") and f.lower().endswith(CHAR_EXTS):
                    targets.append(os.path.join(base, f))
        n = 0
        for t in targets:
            full = os.path.realpath(t)
            if not full.startswith(base + os.sep):
                continue
            if os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
                n += 1
            elif os.path.isfile(full):
                os.remove(full)
                n += 1
        return self.send_json({"ok": n > 0, "removed": n})

    def _stream_upload(self, d, folder, fname):
        """Write the upload to disk in chunks so multi-GB films don't fill memory."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:
            n = 0
        if n <= 0:
            return self.send_json({"error": "no file data received"}, 400)
        if folder == "root":
            # the film itself: "Extract subtitles" and single-film recaps look in the project root
            if not fname.lower().endswith(VIDEO_EXTS + COMIC_EXTS):
                return self.send_json({"error": "Only video files or comic files (.cbz .cbr .pdf) can go in the project root."}, 400)
            dest = os.path.join(d, fname)
        else:
            os.makedirs(os.path.join(d, folder), exist_ok=True)
            dest = os.path.join(d, folder, fname)
        tmp = dest + ".part"
        left = n
        with open(tmp, "wb") as f:
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left > 0:
            os.remove(tmp)
            return self.send_json({"error": "upload was cut off - try again"}, 400)
        os.replace(tmp, dest)
        return self.send_json({"ok": True, "file": fname if folder == "root" else os.path.join(folder, fname)})

    def api_sync(self, name):
        if not self.require_project(name):
            return
        if not os.path.isfile(ENGINE_SRC):
            return self.send_json({"error": "No engine source at _template/recap.py"}, 500)
        shutil.copyfile(ENGINE_SRC, os.path.join(project_dir(name), "recap.py"))
        for mod in ("timeline.py", "scenes.py", "wordtimes.py", "authoring.py", PROMPT_AUTHORING):
            src = os.path.join(TEMPLATE, mod)
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(project_dir(name), mod))
        return self.send_json({"ok": True})

    def api_open(self, name):
        if not self.require_project(name):
            return
        try:
            os.startfile(os.path.abspath(project_dir(name)))
        except Exception as e:
            return self.send_json({"error": str(e)}, 500)
        return self.send_json({"ok": True})

    def api_save_keys(self, body):
        updates = {k: v for k, v in (body or {}).items() if k in KEY_NAMES and isinstance(v, str)}
        if not updates:
            return self.send_json({"error": "nothing to save"}, 400)
        try:
            save_keys(updates)
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)
        except Exception as e:
            return self.send_json({"error": "Could not write keys.env: %s" % e}, 500)
        return self.send_json({"ok": True, "keys": keys_overview(), "tools": tools_status()})

    def api_voicelab_say(self, body):
        engine = str(body.get("engine") or "edge")
        text = str(body.get("text") or "").strip()
        if engine not in LAB_ENGINES:
            return self.send_json({"error": "unknown engine"}, 400)
        if not text:
            return self.send_json({"error": "Type some text first."}, 400)
        if len(text) > 5000:
            return self.send_json({"error": "Too long for a preview (max 5000 characters)."}, 400)
        tts = {k: v for k, v in (body.get("tts") or {}).items()
               if isinstance(k, str) and k.startswith(LAB_KEYS) and isinstance(v, (str, int, float, bool))}
        try:
            os.makedirs(os.path.join(LAB_DIR, "out"), exist_ok=True)
            dst = os.path.join(LAB_DIR, "recap.py")
            if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(ENGINE_SRC):
                shutil.copyfile(ENGINE_SRC, dst)
            pj = os.path.join(LAB_DIR, "project.json")
            if not os.path.isfile(pj):
                with open(pj, "w", encoding="utf-8") as f:
                    json.dump({"module": "movie_recap"}, f)
            uid = "%d_%s" % (int(time.time() * 1000), uuid.uuid4().hex[:6])
            tf, cf = os.path.join(LAB_DIR, uid + ".txt"), os.path.join(LAB_DIR, uid + ".json")
            out = os.path.join(LAB_DIR, "out", "lab_%s.mp3" % uid)
            with open(tf, "w", encoding="utf-8") as f:
                f.write(text)
            with open(cf, "w", encoding="utf-8") as f:
                json.dump(tts, f)
            env = dict(os.environ)
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            env["RECAP_NONINTERACTIVE"] = "1"
            r = subprocess.run([PY, "recap.py", "say", "--engine", engine, "--text-file", tf,
                                "--tts-file", cf, "--out", out], cwd=LAB_DIR, env=env, timeout=1500,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for x in (tf, cf):
                try:
                    os.remove(x)
                except OSError:
                    pass
            log = r.stdout.decode("utf-8", "replace")
            if r.returncode != 0 or not os.path.isfile(out):
                lines = [l.strip() for l in log.splitlines() if l.strip() and "@@" not in l]
                err = [l for l in lines if "ERROR" in l or "[!]" in l] or lines[-3:]
                return self.send_json({"error": " ".join(err)[:500] or "The voice engine failed."}, 502)
            olds = sorted(glob.glob(os.path.join(LAB_DIR, "out", "lab_*.mp3")), key=os.path.getmtime)[:-40]
            for x in olds:
                try:
                    os.remove(x)
                except OSError:
                    pass
            return self.send_json({"url": "/api/voicelab/audio/" + os.path.basename(out),
                                   "name": os.path.basename(out), "bytes": os.path.getsize(out)})
        except subprocess.TimeoutExpired:
            return self.send_json({"error": "Timed out (the first Kokoro / Chatterbox / Pocket run downloads its model - try again)."}, 504)
        except Exception as e:
            return self.send_json({"error": str(e)}, 500)

    def api_voice_upload(self, qs):
        """Save a reference clip into voices/ (used for voice cloning)."""
        fname = safe_name(os.path.basename(q1(qs, "name", "") or "voice.wav"))
        if not fname.lower().endswith(VOICE_EXTS):
            return self.send_json({"error": "Use a .wav .mp3 .flac .m4a or .ogg file."}, 400)
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:
            n = 0
        if n <= 0:
            return self.send_json({"error": "no file data received"}, 400)
        if n > 100 * 1024 * 1024:
            return self.send_json({"error": "That file is too big for a reference clip (max 100 MB). "
                                            "5-15 seconds is all the model needs."}, 400)
        os.makedirs(VOICES_DIR, exist_ok=True)
        dest = os.path.join(VOICES_DIR, fname)
        tmp = dest + ".part"
        left = n
        with open(tmp, "wb") as f:
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left > 0:
            os.remove(tmp)
            return self.send_json({"error": "upload was cut off - try again"}, 400)
        os.replace(tmp, dest)
        note = ""
        # Pocket TTS reads plain 16-bit WAV most reliably: convert anything else to WAV right here.
        wav_name, converted = to_clean_wav(dest)
        if converted:
            fname = wav_name
            note = "Converted to WAV automatically."
        elif not dest.lower().endswith(".wav"):
            note = ("Saved, but ffmpeg could not convert it to WAV. Pocket TTS may need a WAV: see "
                    "voices/README.txt for the one-line ffmpeg command.")
        return self.send_json({"ok": True, "file": fname, "voice_files": voice_files(), "note": note})

    def api_elevenlabs_voices(self):
        key = get_first_key("ELEVENLABS_API_KEY")
        if not key:
            return self.send_json({"error": "No ELEVENLABS_API_KEY in keys.env"}, 400)
        try:
            import requests
            r = requests.get("https://api.elevenlabs.io/v1/voices",
                             headers={"xi-api-key": key}, timeout=30)
            if r.status_code != 200:
                return self.send_json({"error": "HTTP %d" % r.status_code,
                                       "detail": r.text[:200]}, 502)
            voices = [v for v in r.json().get("voices", []) if v.get("category") == "premade"]
            out = []
            for v in voices:
                lb = v.get("labels") or {}
                desc = ", ".join(x for x in (lb.get("gender"), lb.get("accent"),
                                             lb.get("description")) if x)
                out.append({"voice_id": v["voice_id"],
                            "name": v["name"] + (("  (" + desc + ")") if desc else "")})
            return self.send_json({"voices": out})
        except Exception as e:
            return self.send_json({"error": str(e)}, 502)


def main():
    port = 7860
    server = None
    while port < 7900:
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            port += 1
    if server is None:
        print("Could not find a free port.")
        sys.exit(1)
    url = "http://127.0.0.1:%d" % port
    print("=" * 60)
    print("  Recap Studio")
    print("  Open your browser at:  %s" % url)
    print("  Press Ctrl+C here (or close this window) to stop.")
    print("=" * 60)
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()







