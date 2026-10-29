"""timeline.json writer + Remotion render bridge (gameplan Phase 0).

recap.py stays the brain. This module only:
  * turns the items from build_items() into timeline.json (the contract Remotion renders),
  * stages the files Remotion needs into remotion_public/ (hard links, so no extra disk space),
  * validates the timeline (files exist, clip lengths match the frame counts),
  * runs the Remotion CLI and checks the result against the expected length.

The bridge steps in recap.py are thin wrappers:  step_timeline / step_remotion.
`rc` below is the recap module (passed in, so this file never imports recap and nothing runs twice).
"""

import json
import os
import shutil
import subprocess
import sys
import time

import scenes
import wordtimes

SCHEMA_VERSION = 2
TIMELINE_FILE = "timeline.json"
PUBLIC_DIR = "remotion_public"
REMOTION_OUT = "recap_remotion.mp4"


# --------------------------------------------------------------------
# style (config.json "captions" / "transitions" / "overlays" blocks -> timeline["style"])
# --------------------------------------------------------------------
CAPTION_STYLES = ("clean", "bold", "karaoke")
TRANSITIONS = ("cut", "fade", "whip", "zoom", "flash", "glitch")
DEFAULT_STYLE = {
    "font": '"Arial Black", Impact, "Segoe UI", Arial, sans-serif',
    "accent": "#FFD23F",
    "captions": {"enabled": True, "style": "karaoke", "size": 1.0, "position": "bottom", "max_words": 0,
                 "uppercase": None, "whisper_model": "base", "language": ""},
    "transitions": {"enabled": True, "auto": "cut", "on_chapter": "whip", "frames": 8},
    "overlays": {"chapter_cards": True, "lower_thirds": True, "rank_stamp": True, "caption_badge": True,
                 "chapter_seconds": 2.4},
}


def style_from_cfg(rc):
    """Defaults + whatever the project's config.json says. Bad values fall back with a plain message."""
    st = json.loads(json.dumps(DEFAULT_STYLE))
    cfg = rc.CFG
    for k in ("captions", "transitions", "overlays"):
        if isinstance(cfg.get(k), dict):
            st[k].update(cfg[k])
    for k in ("font", "accent"):
        if cfg.get(k):
            st[k] = cfg[k]
    if st["captions"]["style"] not in CAPTION_STYLES:
        print(f"[!] captions.style '{st['captions']['style']}' is not one of {', '.join(CAPTION_STYLES)}; using karaoke.")
        st["captions"]["style"] = "karaoke"
    for k in ("auto", "on_chapter"):
        if st["transitions"][k] not in TRANSITIONS:
            print(f"[!] transitions.{k} '{st['transitions'][k]}' is not one of {', '.join(TRANSITIONS)}; using cut.")
            st["transitions"][k] = "cut"
    return st


def resolve_transition(index, seg, chapter_start, tcfg):
    """The transition INTO this segment: explicit "transition" in segments.json, else the auto rule."""
    if not tcfg.get("enabled", True) or index == 0:
        return "cut"
    want = str(seg.get("transition") or "auto").strip().lower()
    if want in TRANSITIONS:
        return want
    if want != "auto":
        print(f"[!] {seg.get('id')}: unknown transition '{want}' (use one of {', '.join(TRANSITIONS)}); using auto.")
    return tcfg["on_chapter"] if chapter_start else tcfg["auto"]


def parse_lower_third(v):
    if not v:
        return None
    if isinstance(v, dict):
        name = str(v.get("name") or "").strip()
        role = str(v.get("role") or "").strip()
    else:
        name, _, role = str(v).partition("|")
        name, role = name.strip(), role.strip()
    return {"name": name, "role": role} if name else None


# --------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------
def _posix(p):
    return p.replace("\\", "/")


def _stage(src, rel, pub_root):
    """Hard-link (or copy) src into remotion_public/<rel>. Returns the public-relative path."""
    dst = os.path.join(pub_root, *rel.split("/"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return rel


def _frames_ok(rc, path, frames, fps):
    """True if the media file's duration is within 1.5 frames of what the timeline says."""
    try:
        return abs(rc.get_duration(path) - frames / fps) <= 1.5 / fps
    except Exception:
        return False


# --------------------------------------------------------------------
# build
# --------------------------------------------------------------------
def build_timeline(rc, items, music, fps, width, height, words=None, style=None):
    """items: output of rc.build_items(). Returns (timeline dict). Stages files into remotion_public/."""
    pub = os.path.join(rc.ROOT, PUBLIC_DIR)
    if os.path.isdir(pub):
        shutil.rmtree(pub, ignore_errors=True)
    os.makedirs(pub, exist_ok=True)

    style = style or json.loads(json.dumps(DEFAULT_STYLE))
    words = words or {}
    tcfg = style["transitions"]
    segments, start, chapter_no, last_chapter = [], 0, 0, None
    for idx, it in enumerate(items):
        sid = it["id"]
        src = it.get("seg") or {}
        chapter = it.get("chapter", "")
        chapter_start = bool(chapter) and chapter != last_chapter
        if chapter_start:
            chapter_no += 1
            last_chapter = chapter
        trans = resolve_transition(idx, src, chapter_start, tcfg)
        n = int(round(int(tcfg.get("frames", 8)) * fps / 24.0))
        n = max(2, min(n, it["frames"] // 3))
        if it["frames"] < 6:
            trans = "cut"
        wd = words.get(sid)
        seg = {
            "id": sid,
            "kind": it["kind"],                               # video | image | comic | slate
            "startFrame": start,
            "durationFrames": it["frames"],
            "video": _stage(it["video_file"], f"clips/{sid}.mp4", pub),
            "audio": _stage(it["audio_file"], f"voice/{sid}.wav", pub),
            "origAudio": (_stage(it["orig_file"], f"orig/{sid}.wav", pub) if it.get("orig_file") else None),
            "text": it.get("text", ""),
            "caption": it.get("caption", ""),
            "rank": it.get("rank"),
            "chapter": it.get("chapter", ""),
            "words": (wordtimes.to_frames(wd["words"], fps, it["frames"], src.get("emphasis"))
                      if wd else []),
            "wordMethod": wd["method"] if wd else None,
            "chapterStart": chapter_start,
            "chapterIndex": chapter_no,
            "lowerThird": parse_lower_third(src.get("lower_third")),
            "transition": trans,                              # how this segment is entered
            "transitionFrames": n,
            # scene: footage | keywords | generated (set by scenes.resolve, Phase 2); sfx = Phase 4
            "scene": {"type": "footage"},
            "sfx": [],
        }
        segments.append(seg)
        start += it["frames"]

    music_ref = None
    if music and os.path.exists(music):
        music_ref = {"file": _stage(music, "music/bed.wav", pub)}

    return {
        "schema": SCHEMA_VERSION,
        "module": rc.PROJECT.get("module", "movie_recap"),
        "fps": fps,
        "width": width,
        "height": height,
        "totalFrames": start,
        "theme": {},                                          # theme.json (scenes.resolve fills it)
        "style": style,
        "music": music_ref,
        "segments": segments,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def write_timeline(tl, path=TIMELINE_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tl, f, indent=2, ensure_ascii=False)
    return path


def validate_timeline(rc, tl):
    """Returns a list of plain-English problems (empty = fine)."""
    problems = []
    pub = os.path.join(rc.ROOT, PUBLIC_DIR)
    fps, running = tl["fps"], 0
    for s in tl["segments"]:
        if s["startFrame"] != running:
            problems.append(f"{s['id']}: starts at frame {s['startFrame']} but the previous segment ends at {running}")
        running += s["durationFrames"]
        for key in ("video", "audio", "origAudio"):
            ref = s.get(key)
            if ref and not os.path.exists(os.path.join(pub, *ref.split("/"))):
                problems.append(f"{s['id']}: {key} file is missing ({ref})")
        vpath = os.path.join(pub, *s["video"].split("/"))
        if os.path.exists(vpath) and not _frames_ok(rc, vpath, s["durationFrames"], fps):
            problems.append(f"{s['id']}: picture clip length does not match {s['durationFrames']} frames")
        apath = os.path.join(pub, *s["audio"].split("/"))
        if os.path.exists(apath) and not _frames_ok(rc, apath, s["durationFrames"], fps):
            problems.append(f"{s['id']}: voice length does not match {s['durationFrames']} frames")
        prev = 0
        for w in s.get("words", []):
            if w["startFrame"] < prev or w["startFrame"] >= s["durationFrames"] or w["endFrame"] > s["durationFrames"]:
                problems.append(f"{s['id']}: word '{w['word']}' timing is outside the segment or out of order")
                break
            prev = w["startFrame"]
        if s.get("transition") not in TRANSITIONS:
            problems.append(f"{s['id']}: unknown transition '{s.get('transition')}'")
    if running != tl["totalFrames"]:
        problems.append(f"totalFrames is {tl['totalFrames']} but the segments add up to {running}")
    return problems


# --------------------------------------------------------------------
# steps (called from recap.py)
# --------------------------------------------------------------------
def make(rc, args):
    """Shared by both steps: build items the same way `video` does, write + validate timeline.json."""
    data = rc.load_data(rc.find_json(args.json))
    segments = rc.yt_segments(data)
    if not segments:
        rc.die("No 'youtube' segments in the JSON.")
    # same flags as step_video, so the Remotion video can be compared to recap_final.mp4:
    # no ffmpeg graphics layer (Remotion draws those later), characters baked in.
    items = rc.build_items(segments, rc.FPS, rc.WIDTH, rc.HEIGHT, rc.CLIPS_DIR, rc.CFG.get("fill", "pad"),
                           gfx=False, label="segments", characters="burn")
    for i in items:
        i["fps"] = rc.FPS
    music = rc.make_music_bed(sum(i["frames"] for i in items), rc.FPS)
    style = style_from_cfg(rc)
    words = {}
    if style["captions"].get("enabled", True):
        print("\nWord timings for the captions...")
        words = wordtimes.ensure(rc, items, style["captions"])
    tl = build_timeline(rc, items, music, rc.FPS, rc.WIDTH, rc.HEIGHT, words, style)
    # Phase 2: scenes (custom Remotion scenes + the keywords fallback) replace the picture of some segments.
    # Generated scenes are checked here; a failing one becomes the keywords scene. Never blocks the timeline.
    scenes.resolve(rc, tl, {i["id"]: (i.get("seg") or {}) for i in items}, "check")
    write_timeline(tl)
    problems = validate_timeline(rc, tl)
    secs = tl["totalFrames"] / tl["fps"]
    print(f"\n[+] {TIMELINE_FILE}: {len(tl['segments'])} segments, {tl['totalFrames']} frames "
          f"({secs:.1f}s at {tl['fps']}fps, {tl['width']}x{tl['height']})")
    if problems:
        print("[!] The timeline has problems (paste this to Claude):")
        for p in problems[:25]:
            print("    - " + p)
        rc.die("Fix the problems above, then run this step again.")
    print("[+] Timeline check passed: every file exists and every clip matches its frame count.")
    chap = sum(1 for s in tl["segments"] if s["chapterStart"])
    sc = {}
    for s in tl["segments"]:
        t = (s.get("scene") or {}).get("type", "footage")
        sc[t] = sc.get(t, 0) + 1
    trn = {}
    for s in tl["segments"]:
        trn[s["transition"]] = trn.get(s["transition"], 0) + 1
    print(f"    captions: {style['captions']['style'] if style['captions'].get('enabled', True) else 'off'}"
          f" | chapters: {chap} | transitions: " + ", ".join(f"{k} x{v}" for k, v in sorted(trn.items())))
    print("    pictures: " + ", ".join(f"{k} x{v}" for k, v in sorted(sc.items())))
    return tl


def step_timeline(rc, args):
    make(rc, args)
    print(f"Next: run 'Render with Remotion' (or: python recap.py remotion).")


def _remotion_dir(rc):
    d = os.path.join(rc.studio_base(), "remotion")
    return d if os.path.isfile(os.path.join(d, "package.json")) else None


def _npx():
    for name in (("npx.cmd", "npx") if os.name == "nt" else ("npx",)):
        p = shutil.which(name)
        if p:
            return p
    return None


def step_remotion(rc, args):
    rdir = _remotion_dir(rc)
    if not rdir:
        rc.die("The remotion/ folder was not found next to Recap Studio. Re-download the project.")
    if not shutil.which("node") or not _npx():
        rc.die("Node.js is not installed. Run SETUP.bat (it installs Node), then try again.\n"
               "Your normal 'Build full video' still works without it.")
    if not os.path.isdir(os.path.join(rdir, "node_modules", "remotion")):
        rc.die("Remotion is not installed yet. Run SETUP.bat again, or run 'npm install' inside the remotion folder:\n"
               f"  {rdir}")

    tl = make(rc, args)                       # always rebuild so the timeline matches the current audio
    out = os.path.abspath(REMOTION_OUT)
    rcfg = rc.CFG.get("remotion", {}) if isinstance(rc.CFG.get("remotion"), dict) else {}
    conc = int(rcfg.get("concurrency", 2))
    cache_mb = int(rcfg.get("cache_mb", 1024))
    # Remotion's OffthreadVideo keeps decoded frames in a memory cache. If it is too small (or two frames
    # are decoded at once on a small machine) it fails with "No frame found at position". So: try the
    # configured settings first, then automatically retry one frame at a time with a bigger cache.
    attempts = [(conc, cache_mb)]
    if conc > 1 or cache_mb < 1536:
        attempts.append((1, max(cache_mb, 1536)))
    t0 = time.time()
    ok = False
    for n, (c, mb) in enumerate(attempts, 1):
        cmd = [_npx(), "remotion", "render", "src/index.ts", "MovieRecap", out,
               f"--props={os.path.abspath(TIMELINE_FILE)}",
               f"--public-dir={os.path.abspath(os.path.join(rc.ROOT, PUBLIC_DIR))}",
               f"--concurrency={c}", f"--offthreadvideo-cache-size-in-bytes={mb * 1024 * 1024}",
               "--codec=h264", "--crf=18", "--overwrite"]
        if rcfg.get("browser_executable"):          # optional: use an existing Chrome / headless shell (offline setups)
            cmd.append(f"--browser-executable={rcfg['browser_executable']}")
        print(f"\nRendering with Remotion, attempt {n}/{len(attempts)} ({c} parallel frame(s), {mb} MB video cache; "
              "the first run downloads a headless browser)...")
        print("  " + " ".join(cmd) + "\n")
        res = subprocess.run(cmd, cwd=rdir)
        if res.returncode == 0 and os.path.exists(out):
            ok = True
            break
        print(f"\n[!] Attempt {n} failed.")
    if not ok:
        rc.die("Remotion could not render. Read the message above (paste it to Claude).\n"
               "Your normal 'Build full video' is unaffected.")
    took = time.time() - t0

    got = rc.get_duration(out)
    want = tl["totalFrames"] / tl["fps"]
    diff_frames = abs(got - want) * tl["fps"]
    print(f"\nDone. {out}  ({got:.2f}s, expected {want:.2f}s, rendered in {took / 60:.1f} min)")
    if diff_frames <= 1.5:
        print("[+] PARITY CHECK PASSED: length matches the timeline within one frame.")
    else:
        print(f"[!] PARITY CHECK FAILED: the video is {diff_frames:.1f} frames off the timeline.")
    ref = rc.FINAL_OUT
    if os.path.exists(ref):
        ref_d = rc.get_duration(ref)
        d = abs(got - ref_d) * tl["fps"]
        print(f"    vs {ref}: {ref_d:.2f}s -> {'within one frame' if d <= 1.5 else f'{d:.1f} frames apart'}")
    else:
        print(f"    (Run 'Build full video' once if you want it compared with {ref} too.)")
    rc.reveal(out)
