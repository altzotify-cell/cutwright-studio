"""Dynamic scene authoring (gameplan Phase 3): Claude writes the scenes, this module does the bookkeeping.

Two passes, both through the user's own Claude chat (no API):
  pass 1  segments.json  with a short  "motion": {"brief": "...", "data": {...}, "cost": "low"}  on the segments that
          deserve a custom motion graphic, plus an optional top-level  "theme": {...}  for the whole film.
  pass 2  this module exports ONE prompt (contract + helper kit + example scenes + theme + all briefs); Claude answers
          with one .tsx code block per scene; this module imports the batch into  scenes/<segment id>.tsx.
  then    scenes.py (Phase 2) statically checks and test-renders them; a scene that fails becomes the keywords scene.

Everything here is plain standard-library Python and takes folders, not the recap module, so the web UI (studio.py)
and the engine steps (recap.py) can both use it.

    root = a project folder       base = the Recap Studio folder (the one holding remotion/ and _template/)
"""

import hashlib
import json
import os
import re
import shutil
import time

SCENES_DIR = "scenes"
RECORD_FILE = os.path.join(SCENES_DIR, "_authoring.json")   # what each imported scene was written for
PROMPT_FILE = "SCENE_AUTHORING_PROMPT.txt"
FIX_PROMPT_FILE = "SCENE_FIX_PROMPT.txt"
REPORT_FILE = "scenes_report.json"
THEME_FILE = "theme.json"
THEME_PROPOSED_FILE = "theme.proposed.json"
PROMPT_TEMPLATE = "PASTE_THIS_TO_CLAUDE_scene_authoring.txt"

COSTS = ("low", "medium", "high")
ENERGIES = ("calm", "punchy", "chaotic")
PALETTE_KEYS = ("bg", "bg2", "fg", "muted", "accent", "accent2", "good", "bad")
TRANSITIONS = ("auto", "cut", "fade", "whip", "zoom", "flash", "glitch")
FIXED_SCENES = ("footage", "keywords", "generated")
MAX_SCENE_BYTES = 60000
HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
MARK = "[authoring]"


# --------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------
def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, data):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _read_text(path, default=""):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return default


def _short(s, n=110):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def youtube_segments(root):
    """The list of segments scenes can attach to (the main video, not the TikTok parts)."""
    data = _read_json(os.path.join(root, "segments.json"), {})
    if isinstance(data, list):
        return [s for s in data if isinstance(s, dict)]
    yt = data.get("youtube") if isinstance(data, dict) else None
    return [s for s in (yt or []) if isinstance(s, dict)]


def load_theme(root):
    t = _read_json(os.path.join(root, THEME_FILE), {})
    return t if isinstance(t, dict) else {}


def _motion(seg):
    m = seg.get("motion")
    return m if isinstance(m, dict) else {}


def wants_scene(seg):
    """True when this segment asks for a Claude-written scene: a motion brief, or scene.type == generated."""
    raw = seg.get("scene")
    if isinstance(raw, str) and raw.strip().lower() == "keywords":
        return False
    if isinstance(raw, dict) and str(raw.get("type") or "").lower() == "keywords":
        return False
    if isinstance(raw, dict) and str(raw.get("type") or "").lower() == "generated":
        return True
    return bool(str(_motion(seg).get("brief") or "").strip())


def forced_fallback(seg):
    raw = seg.get("scene")
    t = raw if isinstance(raw, str) else (raw.get("type") if isinstance(raw, dict) else "")
    return str(t or "").strip().lower() == "keywords"


def scene_file(seg, sid):
    raw = seg.get("scene")
    if isinstance(raw, dict) and raw.get("file"):
        return str(raw["file"]).replace("\\", "/")
    return f"{SCENES_DIR}/{sid}.tsx"


def brief_hash(seg, theme):
    """Changes when the brief, its data, its cost or the theme changes: the scene was written for the OLD one."""
    m = _motion(seg)
    key = [m.get("brief") or "", m.get("data") or {}, m.get("style_notes") or "", m.get("cost") or "", theme]
    return hashlib.sha256(json.dumps(key, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------
# pass 1: validate the script (plain messages Claude can act on)
# --------------------------------------------------------------------
def validate_script(obj):
    """Returns {"errors": [...], "warnings": [...], "motion": n, "segments": n}.
    Errors would break the scene engine for that segment; warnings are advice. Unknown fields are never a problem."""
    errors, warnings = [], []
    if isinstance(obj, list):
        yt, tt = obj, {}
    elif isinstance(obj, dict):
        yt, tt = obj.get("youtube") or [], obj.get("tiktok") or {}
    else:
        return {"errors": ["the script is not a JSON object"], "warnings": [], "motion": 0, "segments": 0}
    if not isinstance(yt, list):
        yt = []
    seen = set()
    n_motion = 0
    n = len([s for s in yt if isinstance(s, dict)])
    for i, seg in enumerate(yt):
        if not isinstance(seg, dict):
            errors.append(f"segment #{i + 1}: not an object")
            continue
        sid = str(seg.get("id") or f"#{i + 1}")
        if sid in seen:
            errors.append(f"segment {sid}: the id is used twice")
        seen.add(sid)
        if "id" in seg and not NAME_RE.match(str(seg["id"])):
            errors.append(f"segment {sid}: use only letters, digits, _ and - in the id (it becomes the scene file name)")
        m = seg.get("motion")
        if m is not None:
            if not isinstance(m, dict):
                errors.append(f"segment {sid}: 'motion' must be an object like {{\"brief\": \"...\", \"data\": {{}}, \"cost\": \"low\"}}")
                m = {}
            brief = m.get("brief")
            if brief is None or not str(brief).strip():
                if m.get("data") is None or seg.get("scene") is None:
                    warnings.append(f"segment {sid}: 'motion' has no 'brief', so no scene will be written for it")
            else:
                n_motion += 1
                if len(str(brief)) > 600:
                    warnings.append(f"segment {sid}: the brief is very long ({len(str(brief))} characters); 1-3 sentences work best")
            if "data" in m and not isinstance(m["data"], dict):
                errors.append(f"segment {sid}: motion.data must be an object (for example {{\"value\": 70, \"label\": \"...\"}})")
            if m.get("cost") is not None and m.get("cost") not in COSTS:
                errors.append(f"segment {sid}: motion.cost must be low, medium or high (not '{m.get('cost')}')")
            if m.get("cost") == "high":
                warnings.append(f"segment {sid}: cost 'high' is slow on the laptop; prefer 'low' or 'medium'")
            if m.get("style_notes") is not None and not isinstance(m.get("style_notes"), str):
                warnings.append(f"segment {sid}: motion.style_notes should be a short text")
            if seg.get("src") or seg.get("image"):
                warnings.append(f"segment {sid}: has a motion scene AND a src/image; the scene replaces the footage")
        sc = seg.get("scene")
        if sc is not None:
            t = sc if isinstance(sc, str) else (sc.get("type") if isinstance(sc, dict) else None)
            if str(t or "").strip().lower() not in FIXED_SCENES:
                errors.append(f"segment {sid}: unknown scene type '{t}' (use keywords or generated)")
        tr = seg.get("transition")
        if tr is not None and str(tr).lower() not in TRANSITIONS:
            errors.append(f"segment {sid}: unknown transition '{tr}' (use {', '.join(TRANSITIONS)})")
    if n and n_motion > max(1, round(n / 3 + 0.5)):
        warnings.append(f"{n_motion} of {n} segments have a motion brief; about a third at most keeps the film varied and the render fast")
    if yt and isinstance(yt[0], dict) and _motion(yt[0]).get("brief"):
        warnings.append("the first segment has a motion scene; that is fine for a hook, but make sure the film still opens with a strong line")
    if isinstance(tt, dict):
        tm = sum(1 for part in tt.values() if isinstance(part, list) for s in part if isinstance(s, dict) and _motion(s).get("brief"))
        if tm:
            warnings.append(f"{tm} TikTok segment(s) have a motion brief; custom scenes are only used in the main (youtube) video for now")
    return {"errors": errors, "warnings": warnings, "motion": n_motion, "segments": n}


# --------------------------------------------------------------------
# theme.json from Claude's "theme" key
# --------------------------------------------------------------------
def clean_theme(t):
    """Returns (theme dict, [messages]). Keeps only known keys with valid values."""
    msgs = []
    if not isinstance(t, dict):
        return {}, ["theme must be an object"]
    out = {}
    if isinstance(t.get("name"), str) and t["name"].strip():
        out["name"] = t["name"].strip()[:60]
    pal = t.get("palette")
    if isinstance(pal, dict):
        p = {}
        for k in PALETTE_KEYS:
            v = pal.get(k)
            if v is None:
                continue
            if isinstance(v, str) and HEX_RE.match(v.strip()):
                p[k] = v.strip()
            else:
                msgs.append(f"theme.palette.{k}: '{v}' is not a #rrggbb colour; ignored")
        for k in pal:
            if k not in PALETTE_KEYS:
                msgs.append(f"theme.palette.{k}: unknown colour name; ignored")
        if p:
            out["palette"] = p
    fonts = t.get("fonts")
    if isinstance(fonts, dict):
        f = {k: str(v)[:160] for k, v in fonts.items() if k in ("heading", "body") and isinstance(v, str) and v.strip()}
        if f:
            out["fonts"] = f
    if t.get("energy") is not None:
        if t["energy"] in ENERGIES:
            out["energy"] = t["energy"]
        else:
            msgs.append(f"theme.energy: '{t['energy']}' is not calm, punchy or chaotic; ignored")
    if isinstance(t.get("grain"), (int, float)) and not isinstance(t.get("grain"), bool):
        out["grain"] = max(0.0, min(1.0, float(t["grain"])))
    if isinstance(t.get("mood"), str):
        out["mood"] = t["mood"][:200]
    return out, msgs


def apply_theme(root, obj):
    """Writes theme.json from the script's top-level 'theme'. Never overwrites a theme the user edited by hand:
    in that case the proposal goes to theme.proposed.json. Returns a list of plain messages."""
    if not isinstance(obj, dict) or "theme" not in obj:
        return []
    theme, msgs = clean_theme(obj.get("theme"))
    if not theme:
        return msgs + ["the script's 'theme' had nothing usable; theme.json was not changed"]
    path = os.path.join(root, THEME_FILE)
    old = _read_json(path, None) if os.path.exists(path) else None
    if old is not None and old.get("_source") != "claude":
        _write_json(os.path.join(root, THEME_PROPOSED_FILE), dict(theme, _source="claude"))
        return msgs + [f"{THEME_FILE} already exists (made or edited by you), so it was kept. Claude's proposal is in "
                       f"{THEME_PROPOSED_FILE}; delete {THEME_FILE} and re-import to use the proposal."]
    _write_json(path, dict(theme, _source="claude"))
    return msgs + [f"theme '{theme.get('name', 'unnamed')}' saved to {THEME_FILE}"]


# --------------------------------------------------------------------
# status of every scene request
# --------------------------------------------------------------------
def _frames_of(report_entry):
    return [f.replace("\\", "/") for f in (report_entry or {}).get("frames", []) if "_portrait" not in f][:4]


def status(root):
    """One row per segment that wants a generated scene (or has a brief):
    state = missing | stale | ready | ok | failed | blocked | unchecked | fallback."""
    theme = load_theme(root)
    record = _read_json(os.path.join(root, RECORD_FILE), {})
    report = _read_json(os.path.join(root, REPORT_FILE), {}).get("scenes", {})
    tl = _read_json(os.path.join(root, "timeline.json"), {})
    dur = {s.get("id"): (s.get("durationFrames") or 0) / float(tl.get("fps") or 24) for s in tl.get("segments", [])} if tl else {}
    rows = []
    for seg in youtube_segments(root):
        sid = str(seg.get("id") or "")
        if not sid:
            continue
        m = _motion(seg)
        fb = forced_fallback(seg)
        if not (wants_scene(seg) or (fb and m.get("brief"))):
            continue
        rel = scene_file(seg, sid)
        exists = os.path.isfile(os.path.join(root, rel.replace("/", os.sep)))
        rec = record.get(sid)
        rep = report.get(sid)
        msg = ""
        if fb:
            state, msg = "fallback", "you chose the keywords scene for this segment"
        elif not exists:
            state, msg = "missing", "scene not written yet (pass 2)"
        elif rec and rec.get("hash") != brief_hash(seg, theme):
            state, msg = "stale", "the brief, data or theme changed after this scene was written"
        elif rep:
            state = rep.get("status") or "unchecked"
            msg = rep.get("message") or ""
        else:
            state, msg = "ready", "written, not checked yet"
        rows.append({
            "id": sid, "brief": str(m.get("brief") or ""), "cost": m.get("cost") or (rep or {}).get("cost") or "",
            "file": rel, "exists": exists, "state": state, "message": _short(msg, 220),
            "frames": _frames_of(rep) if state in ("ok", "failed") else [],
            "warnings": [_short(w, 160) for w in (rep or {}).get("warnings", [])][:3],
            "seconds": round(dur.get(sid, 0), 1) or None, "text": _short(seg.get("narration") or "", 160),
        })
    return rows


# --------------------------------------------------------------------
# pass 2: the scene-authoring prompt
# --------------------------------------------------------------------
def _find_remotion(base):
    d = os.path.join(base, "remotion")
    return d if os.path.isdir(d) else None


def _example_sources(base):
    d = _find_remotion(base)
    out = []
    if not d:
        return out
    for name in ("stat_ring", "timeline_reveal", "quote_moment"):
        p = os.path.join(d, "scenes_examples", name + ".tsx")
        if os.path.isfile(p):
            out.append((name, _read_text(p).strip()))
    return out


def _prompt_template(root, base):
    for folder in (root, os.path.join(base, "_template")):
        p = os.path.join(folder, PROMPT_TEMPLATE)
        if os.path.isfile(p):
            return _read_text(p)
    return ("Write one Remotion scene (.tsx) for each brief below. Send each as its own code block whose first line is "
            "// FILE: scenes/<id>.tsx . Follow the contract.\n\n{{THEME}}\n\n{{SCENES}}\n\n{{CONTRACT}}\n\n{{EXAMPLES}}\n")


def _est_seconds(text):
    return max(2.0, round(len(str(text).split()) / 2.5, 1))


def build_prompt(root, base, only=None, force=False):
    """Builds the pass-2 prompt. Scenes that are already written and still match their brief are skipped unless force.
    only = list of segment ids to restrict to. Returns {"text", "count", "skipped": [ids], "ids": [ids]} and writes
    SCENE_AUTHORING_PROMPT.txt."""
    segs = youtube_segments(root)
    theme = load_theme(root)
    rows = {r["id"]: r for r in status(root)}
    tl = _read_json(os.path.join(root, "timeline.json"), {})
    fps = float(tl.get("fps") or 24) if tl else 24.0
    tl_dur = {s.get("id"): (s.get("durationFrames") or 0) / fps for s in tl.get("segments", [])} if tl else {}
    ids_all = [str(s.get("id")) for s in segs]
    todo, skipped = [], []
    for seg in segs:
        sid = str(seg.get("id") or "")
        r = rows.get(sid)
        if not r or r["state"] == "fallback" or not _motion(seg).get("brief"):
            continue
        if only and sid not in only:
            continue
        if not force and not only and r["state"] in ("ok", "ready", "unchecked"):
            skipped.append(sid)
            continue
        todo.append(seg)
    if not todo:
        return {"text": "", "count": 0, "skipped": skipped, "ids": []}

    blocks = []
    for seg in todo:
        sid = str(seg["id"])
        m = _motion(seg)
        idx = ids_all.index(sid)
        secs = tl_dur.get(sid) or _est_seconds(seg.get("narration") or seg.get("subtitle") or "")
        lines = [f"=== SCENE {sid}   file: scenes/{sid}.tsx ===",
                 f"Length: about {secs:.1f} s ({'measured from the voice-over' if tl_dur.get(sid) else 'estimated from the narration'}); "
                 "it must still work at any length.",
                 f"Brief: {m.get('brief')}"]
        if m.get("data"):
            lines.append("Data (arrives as `props`): " + json.dumps(m["data"], ensure_ascii=False))
        if m.get("style_notes"):
            lines.append("Style notes: " + str(m["style_notes"]))
        lines.append("Cost budget: " + (m.get("cost") if m.get("cost") in COSTS else "low"))
        lines.append("Narration over it: " + json.dumps(str(seg.get("narration") or seg.get("subtitle") or ""), ensure_ascii=False))
        if seg.get("chapter"):
            lines.append("Chapter: " + str(seg["chapter"]))
        for label, j in (("Before it", idx - 1), ("After it", idx + 1)):
            if 0 <= j < len(segs):
                nb = segs[j]
                nbm = _motion(nb)
                what = ("custom scene: " + _short(nbm.get("brief"), 90)) if nbm.get("brief") else "footage"
                lines.append(f"{label} ({nb.get('id')}): {what}; narration: " + json.dumps(_short(nb.get("narration") or "", 90), ensure_ascii=False))
        blocks.append("\n".join(lines))

    theme_txt = json.dumps({k: v for k, v in theme.items() if not k.startswith("_")}, indent=2, ensure_ascii=False) if theme else \
        "(no theme.json yet: use the default theme and rely on theme.palette / theme.fonts at run time, never fixed colours)"
    contract = _read_text(os.path.join(_find_remotion(base) or "", "kit", "CONTRACT.md")) if _find_remotion(base) else ""
    ex = "\n\n".join(f"--- reference scene: {n}.tsx ---\n```tsx\n{src}\n```" for n, src in _example_sources(base))
    film = ""
    try:
        proj = _read_json(os.path.join(root, "project.json"), {})
        film = str(proj.get("topic") or proj.get("title") or "")
    except Exception:
        pass
    tpl = _prompt_template(root, base)
    text = (tpl.replace("{{FILM}}", film or "(not named)")
               .replace("{{COUNT}}", str(len(todo)))
               .replace("{{THEME}}", theme_txt)
               .replace("{{SCENES}}", "\n\n".join(blocks))
               .replace("{{CONTRACT}}", contract.strip() or "(CONTRACT.md was not found next to Recap Studio)")
               .replace("{{EXAMPLES}}", ex or "(reference scenes not found)"))
    with open(os.path.join(root, PROMPT_FILE), "w", encoding="utf-8") as f:
        f.write(text)
    return {"text": text, "count": len(todo), "skipped": skipped, "ids": [str(s["id"]) for s in todo]}


# --------------------------------------------------------------------
# pass 2: import Claude's reply
# --------------------------------------------------------------------
FENCE_RE = re.compile(r"(?P<before>[^\n]*(?:\n[^\n]*){0,2}?)\n?```[^\n]*\n(?P<code>.*?)\n?```", re.S)
FILE_LINE_RE = re.compile(r"^\s*(?://|/\*+|#)?\s*FILE\s*:\s*([^\s*]+)", re.I)
PATH_RE = re.compile(r"([A-Za-z0-9_\-./\\]+\.tsx)")


def _looks_like_scene(code):
    return "export default" in code or "import " in code


def parse_reply(text):
    """Finds the scene files in a pasted Claude reply: [(relative path, code), ...].
    A code block belongs to the file named by '// FILE: scenes/x.tsx' as its first line, or by a path on the line(s) above it.
    A reply without any code fences is also understood when every scene starts with a '// FILE:' line."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    found = []
    for m in FENCE_RE.finditer(text):
        code = m.group("code").strip("\n")
        stripped = code.lstrip()
        first = stripped.split("\n", 1)[0] if stripped else ""
        fm = FILE_LINE_RE.match(first)
        path = None
        if fm:
            path = fm.group(1)
            code = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        else:
            before = [ln for ln in m.group("before").split("\n") if ln.strip()]
            for ln in reversed(before[-2:]):
                pm = PATH_RE.search(ln)
                if pm:
                    path = pm.group(1)
                    break
        if path and _looks_like_scene(code):
            found.append((path.replace("\\", "/"), code.strip("\n") + "\n"))
    if found:
        return found
    # no fences: split on the FILE marker lines
    parts = re.split(r"(?m)^[ \t]*//[ \t]*FILE[ \t]*:[ \t]*(\S+)[ \t]*$", text)
    for i in range(1, len(parts) - 1, 2):
        code = parts[i + 1].strip("\n")
        if _looks_like_scene(code):
            found.append((parts[i].replace("\\", "/"), code + "\n"))
    return found


def import_reply(root, text):
    """Saves the scenes in a pasted reply into scenes/. Old versions go to scenes/_old/. Returns
    {"imported": [ids], "skipped": [(name, why)], "warnings": [...]}."""
    segs = {str(s.get("id")): s for s in youtube_segments(root) if s.get("id")}
    theme = load_theme(root)
    record = _read_json(os.path.join(root, RECORD_FILE), {})
    res = {"imported": [], "skipped": [], "warnings": []}
    files = parse_reply(text)
    if not files:
        res["skipped"].append(("(reply)", "no scene code blocks were found; each scene must be its own ``` code block with "
                                         "'// FILE: scenes/<id>.tsx' as its first line"))
        return res
    seen = set()
    for rel, code in files:
        base_name = os.path.basename(rel)
        sid = base_name[:-4] if base_name.lower().endswith(".tsx") else base_name
        if not NAME_RE.match(sid) or not base_name.lower().endswith(".tsx"):
            res["skipped"].append((base_name, "the file name may only contain letters, digits, _ and - and must end in .tsx"))
            continue
        if sid in seen:
            res["warnings"].append(f"{sid}: appeared twice in the reply; the last version was kept")
        seen.add(sid)
        if len(code.encode("utf-8")) > MAX_SCENE_BYTES:
            res["skipped"].append((base_name, f"too large ({len(code) // 1000} KB); a scene should be a few KB"))
            continue
        if "export default" not in code:
            res["warnings"].append(f"{sid}: no 'export default'; the check will reject it")
        if sid not in segs:
            res["warnings"].append(f"{sid}: no segment has this id in the script; saved anyway, but nothing uses it")
        dest_dir = os.path.join(root, SCENES_DIR)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, sid + ".tsx")
        if os.path.isfile(dest):
            old_dir = os.path.join(dest_dir, "_old")
            os.makedirs(old_dir, exist_ok=True)
            shutil.copyfile(dest, os.path.join(old_dir, f"{sid}.{time.strftime('%Y%m%d-%H%M%S')}.tsx"))
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        if sid in segs:
            record[sid] = {"hash": brief_hash(segs[sid], theme), "when": time.strftime("%Y-%m-%d %H:%M:%S")}
        res["imported"].append(sid)
    _write_json(os.path.join(root, RECORD_FILE), record)
    return res


# --------------------------------------------------------------------
# per-scene actions from the UI
# --------------------------------------------------------------------
def _save_segments(root, mutate):
    path = os.path.join(root, "segments.json")
    data = _read_json(path, None)
    if data is None:
        return False
    yt = data if isinstance(data, list) else data.get("youtube", [])
    changed = False
    for seg in yt:
        if isinstance(seg, dict) and mutate(seg):
            changed = True
    if changed:
        if os.path.exists(path):
            shutil.copyfile(path, path + ".bak")
        _write_json(path, data)
    return changed


def action(root, sid, what):
    """what = fallback (use the keywords scene) | unfallback (use the written scene again) | retry (re-check it)
    | discard (delete the written scene so pass 2 writes it again). Returns a plain message."""
    sid = str(sid)
    if what == "fallback":
        def f(seg):
            if str(seg.get("id")) != sid:
                return False
            seg["scene"] = "keywords"
            return True
        return "Using the keywords scene for " + sid if _save_segments(root, f) else "segment not found"
    if what == "unfallback":
        def f(seg):
            if str(seg.get("id")) != sid or "scene" not in seg:
                return False
            if forced_fallback(seg):
                del seg["scene"]
                return True
            return False
        _save_segments(root, f)
        return "The written scene will be used again for " + sid
    if what in ("retry", "discard"):
        cache_path = os.path.join(root, SCENES_DIR, "_cache.json")
        cache = _read_json(cache_path, {})
        if isinstance(cache.get("scenes"), dict) and sid in cache["scenes"]:
            del cache["scenes"][sid]
            _write_json(cache_path, cache)
        if what == "discard":
            p = os.path.join(root, SCENES_DIR, sid + ".tsx")
            if os.path.isfile(p):
                os.makedirs(os.path.join(root, SCENES_DIR, "_old"), exist_ok=True)
                shutil.move(p, os.path.join(root, SCENES_DIR, "_old", f"{sid}.{time.strftime('%Y%m%d-%H%M%S')}.tsx"))
            rec = _read_json(os.path.join(root, RECORD_FILE), {})
            rec.pop(sid, None)
            _write_json(os.path.join(root, RECORD_FILE), rec)
            return "Scene file moved to scenes/_old; it will be written again in the next pass-2 prompt"
        return "It will be checked again next time you run 'Check scenes'"
    return "unknown action"


def fix_prompt_text(root):
    return _read_text(os.path.join(root, FIX_PROMPT_FILE))


# --------------------------------------------------------------------
# demo briefs: test the real Claude round trip without a film
# --------------------------------------------------------------------
DEMO_BRIEFS = [
    {"brief": "A big ring fills to 70 percent in the accent colour with a small pulse at the end, and the label fades in underneath.",
     "data": {"value": 70, "label": "of viewers never finish the film"}, "cost": "low"},
    {"brief": "Three events appear along a line one after another, each marker popping in with its label, as if on a timeline.",
     "data": {"items": [{"label": "The heist", "when": "Day 1"}, {"label": "The betrayal", "when": "Day 4"}, {"label": "The chase", "when": "Day 6"}]}, "cost": "low"},
    {"brief": "Two bars grow side by side to compare the hero's and the villain's body count, a bold number counting up above each.",
     "data": {"left": {"label": "Hero", "value": 3}, "right": {"label": "Villain", "value": 27}}, "cost": "medium"},
]
DEMO_THEME = {"name": "demo noir", "palette": {"bg": "#0d0b10", "bg2": "#241a2e", "fg": "#f3eee6", "muted": "#9a8fa8",
              "accent": "#ff6b35", "accent2": "#3ec7c2", "good": "#6ee7a0", "bad": "#ff4d6d"}, "energy": "punchy"}


def demo_briefs(root):
    """Adds three motion briefs (no scene files) and a demo theme to the project's first segments."""
    path = os.path.join(root, "segments.json")
    data = _read_json(path, None)
    yt = None
    if isinstance(data, list):
        yt = data
    elif isinstance(data, dict) and isinstance(data.get("youtube"), list):
        yt = data["youtube"]
    segs = [s for s in (yt or []) if isinstance(s, dict)]
    if len(segs) < 3:
        return "This needs a project with at least 3 segments (use the demo / test media project)."
    shutil.copyfile(path, path + ".bak")
    pick = [1, 3, 5] if len(segs) >= 6 else [0, 1, 2]
    for n, i in zip(DEMO_BRIEFS, pick):
        segs[i]["motion"] = json.loads(json.dumps(n))
        if forced_fallback(segs[i]):
            del segs[i]["scene"]
    _write_json(path, data)
    msgs = apply_theme(root, {"theme": DEMO_THEME})
    ids = ", ".join(str(segs[i].get("id")) for i in pick)
    return (f"Added 3 motion briefs ({ids}) and a demo theme. {' '.join(msgs)} "
            "Now: Scenes tab, copy the scene-authoring prompt and paste it to Claude.")
