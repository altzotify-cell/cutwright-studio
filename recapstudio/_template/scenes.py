"""Scene engine foundation (gameplan Phase 2): check, cache and fall back.

A segment's picture can be a SCENE instead of the footage clip:
    "scene": "keywords"                      the fixed fallback scene (narration key words over a themed background)
    "scene": {"type": "generated"}           a Remotion scene file  scenes/<segment id>.tsx  (written by Claude, Phase 3)
    "motion": {"brief": "..."}               alone (no "scene") also asks for scenes/<segment id>.tsx; authoring.py makes the prompt
    "scene": {"type": "generated", "file": "scenes/my_scene.tsx", "props": {...}}
    "motion": {"data": {...}, "cost": "low"}  data handed to the scene as props (the brief itself is Phase 3)

Nothing generated ever runs unchecked. For every generated scene this module:
  1. static check   remotion/tools/check_scenes.mjs   imports, network, eval, clocks, syntax, missing kit names
  2. test render    remotion/tools/test_scenes.mjs    a few real frames at 16:9 and one at 9:16, then judged here:
                                                      an error, an all-one-colour frame or "drew nothing" = failure
  3. result is cached (hash of code + data + theme + length + kit) so unchanged scenes are never re-checked
A scene that fails is replaced in timeline.json by the keywords scene, with a plain message, and a paste-ready
SCENE_FIX_PROMPT.txt (error + code + contract) is written for Claude. Nothing blocks the video.

`rc` is the recap module (passed in, so this file never imports recap).
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

SCENES_DIR = "scenes"
CHECK_DIR = os.path.join(SCENES_DIR, "_checks")
CACHE_FILE = os.path.join(SCENES_DIR, "_cache.json")
REPORT_FILE = "scenes_report.json"
FIX_PROMPT_FILE = "SCENE_FIX_PROMPT.txt"
THEME_FILE = "theme.json"
CACHE_VERSION = 1
STUDIO_PORT = 3123


# --------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------
def slug(sid):
    """Remotion composition ids allow letters, digits and '-'. Must match slug() in remotion/src/SceneLab.tsx."""
    return re.sub(r"[^A-Za-z0-9]+", "-", str(sid)).strip("-") or "scene"


def _safe(sid):
    return "s_" + (re.sub(r"[^A-Za-z0-9_]+", "_", str(sid)) or "scene")


def _rdir(rc):
    d = os.path.join(rc.studio_base(), "remotion")
    return d if os.path.isfile(os.path.join(d, "package.json")) else None


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


def _short(msg, n=150):
    msg = " ".join(str(msg).split())
    return msg if len(msg) <= n else msg[: n - 3] + "..."


def scenes_ready(rc):
    """(True, '') when Node, Remotion and TypeScript are installed; else (False, plain reason)."""
    rdir = _rdir(rc)
    if not rdir:
        return False, "the remotion/ folder was not found next to Recap Studio"
    if not shutil.which("node"):
        return False, "Node.js is not installed (run SETUP.bat)"
    for pkg in ("remotion", "typescript", os.path.join("@remotion", "bundler"), os.path.join("@remotion", "renderer")):
        if not os.path.isdir(os.path.join(rdir, "node_modules", pkg)):
            return False, "Remotion is not installed or is out of date (run SETUP.bat again)"
    return True, ""


def _kit_hash(rdir):
    h = hashlib.sha256()
    for sub in ("kit", "tools"):
        base = os.path.join(rdir, sub)
        for root, _dirs, files in sorted(os.walk(base)):
            for name in sorted(files):
                if name.endswith((".ts", ".tsx", ".mjs", ".md")):
                    with open(os.path.join(root, name), "rb") as f:
                        h.update(name.encode() + f.read())
    for rel in (os.path.join("src", "layout.ts"), os.path.join("src", "scenes", "Keywords.tsx"), os.path.join("src", "SceneLab.tsx")):
        p = os.path.join(rdir, rel)
        if os.path.exists(p):
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()[:16]


def load_theme(rc):
    """theme.json in the project (palette / fonts / energy ...). Missing or broken = {} (defaults apply)."""
    t = _read_json(os.path.join(rc.ROOT, THEME_FILE), {})
    return t if isinstance(t, dict) else {}


# --------------------------------------------------------------------
# what each segment asks for
# --------------------------------------------------------------------
def request_for(rc, sid, seg, kind):
    """Returns None (plain footage) or {"type": "keywords"|"generated", ...}."""
    cfg = rc.CFG.get("scenes") if isinstance(rc.CFG.get("scenes"), dict) else {}
    raw = seg.get("scene")
    motion = seg.get("motion") if isinstance(seg.get("motion"), dict) else {}
    if raw is None and str(motion.get("brief") or "").strip():
        raw = {"type": "generated"}          # Phase 3: a motion brief alone asks for a Claude-written scene
    if raw is None:
        if kind == "slate" and cfg.get("slate_to_keywords", True):
            return {"type": "keywords", "reason": "no footage for this shot yet"}
        return None
    if isinstance(raw, str):
        raw = {"type": raw}
    if not isinstance(raw, dict):
        print(f"[!] {sid}: 'scene' must be a name or an object; using the footage.")
        return None
    t = str(raw.get("type") or "").strip().lower()
    if t in ("", "footage"):
        return None
    if t == "keywords":
        return {"type": "keywords", "reason": "requested in segments.json"}
    if t == "generated":
        props = {}
        for part in (motion.get("data"), raw.get("props")):
            if isinstance(part, dict):
                props.update(part)
        return {"type": "generated", "file": str(raw.get("file") or f"{SCENES_DIR}/{sid}.tsx"), "props": props,
                "motion_cost": motion.get("cost"), "brief": motion.get("brief") or ""}
    print(f"[!] {sid}: unknown scene type '{t}' (use keywords or generated); using the footage.")
    return None


def _scene_path(rc, rel):
    """Absolute path of a scene file, only inside the project folder and only .tsx."""
    p = os.path.abspath(os.path.join(rc.ROOT, rel.replace("\\", "/")))
    root = os.path.abspath(rc.ROOT) + os.sep
    if not p.startswith(root) or not p.lower().endswith(".tsx"):
        return None
    return p


# --------------------------------------------------------------------
# Node tools
# --------------------------------------------------------------------
def _run_node(rc, rdir, script, manifest_path, show_progress=False):
    cmd = [shutil.which("node"), os.path.join("tools", script), manifest_path]
    try:
        p = subprocess.Popen(cmd, cwd=rdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
    except OSError as e:
        return 1, f"could not start Node: {e}"
    tail = []
    for line in p.stdout:
        line = line.rstrip()
        if show_progress and line.startswith("tested "):
            print("    " + line, flush=True)
        elif line.strip():
            tail.append(line)
            tail = tail[-12:]
    p.wait()
    return p.returncode, "\n".join(tail)


def _browser_exe(rc):
    r = rc.CFG.get("remotion") if isinstance(rc.CFG.get("remotion"), dict) else {}
    return r.get("browser_executable") or None


def _stage(rdir, files):
    """Copy scene files into remotion/src/generated/ (only what is listed); remove stale copies."""
    gen = os.path.join(rdir, "src", "generated")
    os.makedirs(gen, exist_ok=True)
    for name in os.listdir(gen):
        if name.startswith("s_") and name.endswith(".tsx"):
            os.remove(os.path.join(gen, name))
    out = {}
    for sid, src in files.items():
        dst = os.path.join(gen, _safe(sid) + ".tsx")
        shutil.copyfile(src, dst)
        out[sid] = dst
    return out


def _write_registry(rdir, entries, theme):
    """entries: [(sid, meta dict)]. Only these scene files are imported (and so bundled) by Remotion."""
    gen = os.path.join(rdir, "src", "generated")
    lines = ["// AUTO-GENERATED by scenes.py every time scenes are checked or previewed. Do not edit by hand.",
             "import type {LabEntry} from '../sceneTypes';"]
    for i, (sid, _m) in enumerate(entries):
        lines.append(f"import S{i} from './{_safe(sid)}';")
    lines.append(f"\nexport const projectTheme: Record<string, unknown> = {json.dumps(theme, ensure_ascii=False)};")
    lines.append("export const generated: Record<string, LabEntry> = {")
    for i, (sid, meta) in enumerate(entries):
        lines.append(f"  {json.dumps(sid)}: {{component: S{i}, meta: {json.dumps(meta, ensure_ascii=False)}}},")
    lines.append("};\n")
    with open(os.path.join(gen, "registry.ts"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    # drop staged copies that are not in the registry
    keep = {_safe(sid) + ".tsx" for sid, _ in entries}
    for name in os.listdir(gen):
        if name.startswith("s_") and name.endswith(".tsx") and name not in keep:
            os.remove(os.path.join(gen, name))


# --------------------------------------------------------------------
# judging the test frames
# --------------------------------------------------------------------
def _judge(rec, ref):
    """rec: node report for one scene. Returns (error_or_None, [warnings], [frame files])."""
    warnings, files = [], []
    land = rec.get("landscape", {}).get("frames", [])
    for fr in land:
        if fr.get("error"):
            return fr["error"], warnings, files
    for fr in land:
        if fr.get("file"):
            files.append(fr["file"])
    port = rec.get("portrait", {}).get("frames", [])
    for fr in port:
        if fr.get("file"):
            files.append(fr["file"])
        if fr.get("error"):
            warnings.append("the 9:16 version failed: " + _short(fr["error"], 110))
    for lg in rec.get("logs", [])[:3]:
        warnings.append("browser message: " + _short(lg, 110))
    if not land:
        return "no frames were rendered", warnings, files
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        warnings.append("blank-frame check skipped (Pillow / numpy are not installed)")
        return None, warnings, files

    def load(path):
        return np.asarray(Image.open(path).convert("RGB").resize((192, 108)), dtype=np.float32)

    imgs = [load(fr["file"]) for fr in land if fr.get("file")]
    if not imgs:
        return "no frames were rendered", warnings, files
    if all(float(a.std()) < 1.5 for a in imgs):
        return "the scene is blank (every test frame is one flat colour)", warnings, files
    mids = imgs[1:-1] if len(imgs) >= 3 else imgs[-1:]
    refp = ref.get("landscape")
    if refp and os.path.exists(refp):
        base = load(refp)
        changed = [float((np.abs(a - base).max(axis=2) > 12).mean()) for a in mids]
        if all(c < 0.002 for c in changed):
            return "the scene draws nothing: its middle frames look the same as the empty background", warnings, files
        if imgs and float((np.abs(imgs[-1] - base).max(axis=2) > 12).mean()) < 0.002 and len(imgs) > 1:
            warnings.append("the last frame is empty (the scene has faded out completely)")
    if len(imgs) > 1 and max(float(np.abs(a - imgs[0]).mean()) for a in imgs[1:]) < 0.3:
        warnings.append("the scene never changes between frames (is the animation connected to the frame number?)")
    return None, warnings, files


# --------------------------------------------------------------------
# main entry: resolve every segment's scene
# --------------------------------------------------------------------
def _meta_for(seg, sid, cost, props, status, message, source):
    return {"id": sid, "title": sid, "cost": cost, "durationInFrames": seg["durationFrames"], "fps": None,
            "width": None, "height": None, "props": props, "words": seg.get("words") or [],
            "text": seg.get("text", ""), "status": status, "message": message, "source": source}


def resolve(rc, tl, segs_by_id, mode="check"):
    """Sets tl['theme'] and every tl['segments'][i]['scene'].
    mode 'check'   : static check + test render of changed scenes; only scenes that passed are used.
    mode 'preview' : static check only; every statically safe scene goes into the Studio registry (nothing is rendered).
    Returns the report dict (also written to scenes_report.json in 'check' mode)."""
    theme = load_theme(rc)
    tl["theme"] = theme
    reqs = {}
    for seg in tl["segments"]:
        seg["scene"] = {"type": "footage"}
        r = request_for(rc, seg["id"], segs_by_id.get(seg["id"], {}) or {}, seg.get("kind", ""))
        if r:
            reqs[seg["id"]] = r

    report = {"checked": [], "scenes": {}, "kit": None}
    seg_by = {s["id"]: s for s in tl["segments"]}
    for sid, r in reqs.items():
        if r["type"] == "keywords":
            seg_by[sid]["scene"] = {"type": "keywords", "reason": r["reason"]}

    gen = {sid: r for sid, r in reqs.items() if r["type"] == "generated"}
    rdir = _rdir(rc)
    if not gen:
        if rdir:  # keep Studio's registry free of the previous project's scenes
            try:
                _stage(rdir, {})
                _write_registry(rdir, [], theme)
            except OSError:
                pass
        _finish(rc, tl, report, mode)
        return report

    print(f"\nScenes: {len(gen)} custom scene(s) to check...")
    ready, why = scenes_ready(rc)
    results = {}  # sid -> dict(status, message, messages, cost, warnings, frames, static_ok, hash, source)

    def fail(sid, status, message, **kw):
        results[sid] = dict(status=status, message=message, messages=kw.pop("messages", [message]), cost=kw.pop("cost", "medium"),
                            warnings=kw.pop("warnings", []), frames=kw.pop("frames", []), static_ok=kw.pop("static_ok", False),
                            hash=kw.pop("hash", ""), source=kw.pop("source", ""))

    if not ready:
        for sid, r in gen.items():
            fail(sid, "unchecked", f"scenes cannot be checked: {why}", source=r["file"])
    else:
        _check_generated(rc, tl, gen, seg_by, theme, results, mode, rdir)

    for sid, res in results.items():
        r = gen[sid]
        if res["status"] == "ok":
            seg_by[sid]["scene"] = {"type": "generated", "id": sid, "cost": res["cost"], "props": r["props"]}
        else:
            seg_by[sid]["scene"] = {"type": "keywords", "reason": _short(res["message"], 120), "requested": "generated"}
        report["scenes"][sid] = {k: res[k] for k in ("status", "message", "messages", "cost", "warnings", "frames", "source")}
    _finish(rc, tl, report, mode)
    _print_report(report, gen)
    if mode == "check":
        _fix_prompt(rc, gen, results, segs_by_id)
    return report


def _check_generated(rc, tl, gen, seg_by, theme, results, mode, rdir):
    kit = _kit_hash(rdir)
    cache = _read_json(os.path.join(rc.ROOT, CACHE_FILE), {})
    if cache.get("version") != CACHE_VERSION:
        cache = {"version": CACHE_VERSION, "scenes": {}}
    cs = cache["scenes"]
    paths, todo = {}, []
    fps = tl["fps"]

    for sid, r in gen.items():
        p = _scene_path(rc, r["file"])
        if not p:
            results[sid] = dict(status="blocked", message="the scene file must be a .tsx file inside the project folder",
                                messages=["the scene file must be a .tsx file inside the project folder"], cost="medium",
                                warnings=[], frames=[], static_ok=False, hash="", source=r["file"])
            continue
        if not os.path.isfile(p):
            if r.get("brief"):   # asked for in the script, not written yet: not an error, just not done
                msg = f"scene not written yet (use the Scenes tab: copy the scene prompt to Claude and paste the reply)"
                results[sid] = dict(status="pending", message=msg, messages=[msg], cost="medium", warnings=[], frames=[],
                                    static_ok=False, hash="", source=r["file"])
                continue
            msg = f"scene file {r['file']} was not found"
            results[sid] = dict(status="failed", message=msg, messages=[msg], cost="medium", warnings=[], frames=[],
                                static_ok=False, hash="", source=r["file"])
            continue
        seg = seg_by[sid]
        h = hashlib.sha256()
        with open(p, "rb") as f:
            h.update(f.read())
        h.update(json.dumps([r["props"], theme, seg["durationFrames"], fps, tl["width"], tl["height"], kit,
                             [(w["word"], w["startFrame"]) for w in seg.get("words") or []]],
                            sort_keys=True, ensure_ascii=False).encode("utf-8"))
        r["_hash"], r["_path"] = h.hexdigest()[:20], p
        paths[sid] = p
        old = cs.get(sid)
        if old and old.get("hash") == r["_hash"] and (old.get("status") == "ok" or (mode == "preview" and old.get("static_ok") is not None)
                                                      or old.get("status") in ("failed", "blocked")):
            results[sid] = dict(old, source=r["file"], cached=True)
        else:
            todo.append(sid)

    work = os.path.join(rc.ROOT, SCENES_DIR, "_work")
    os.makedirs(work, exist_ok=True)

    # ---- 1. static check (changed scenes only)
    if todo:
        staged = _stage(rdir, {sid: paths[sid] for sid in paths})
        man = os.path.join(work, "check_manifest.json")
        out = os.path.join(work, "check_report.json")
        _write_json(man, {"out": out, "scenes": [{"id": sid, "file": staged[sid]} for sid in todo]})
        print("  Static check (imports, network, clocks, syntax)...")
        code, tail = _run_node(rc, rdir, "check_scenes.mjs", man)
        rep = _read_json(out, {}).get("scenes") if code == 0 else None
        if rep is None:
            for sid in todo:
                results[sid] = dict(status="unchecked", message="the static check could not run: " + _short(tail, 120),
                                    messages=[tail], cost="medium", warnings=[], frames=[], static_ok=False,
                                    hash=gen[sid]["_hash"], source=gen[sid]["file"])
            todo = []
        else:
            nxt = []
            for sid in todo:
                one = rep.get(sid, {"errors": [{"line": 0, "message": "no result"}], "warnings": [], "cost": None})
                cost = one.get("cost") or gen[sid].get("motion_cost") or "medium"
                if cost not in ("low", "medium", "high"):
                    cost = "medium"
                warns = [(f"line {w['line']}: " if w.get("line") else "") + w["message"] for w in one.get("warnings", [])]
                if one["errors"]:
                    msgs = [(f"line {e['line']}: " if e.get("line") else "") + e["message"] for e in one["errors"]]
                    results[sid] = dict(status="blocked", message=msgs[0] + (f" (+{len(msgs) - 1} more)" if len(msgs) > 1 else ""),
                                        messages=msgs, cost=cost, warnings=warns, frames=[], static_ok=False,
                                        hash=gen[sid]["_hash"], source=gen[sid]["file"])
                else:
                    results[sid] = dict(status="static_ok", message="", messages=[], cost=cost, warnings=warns, frames=[],
                                        static_ok=True, hash=gen[sid]["_hash"], source=gen[sid]["file"])
                    nxt.append(sid)
            todo = nxt

    # ---- registry with every statically safe scene (needed for the test render and for Studio)
    safe = [sid for sid in gen if sid in results and (results[sid].get("static_ok") or results[sid].get("status") == "ok")]
    staged = _stage(rdir, {sid: paths[sid] for sid in safe})

    def entries(ids):
        out = []
        for sid in ids:
            seg, res = seg_by[sid], results[sid]
            m = _meta_for(seg, sid, res["cost"], gen[sid]["props"], res["status"], res.get("message", ""), gen[sid]["file"])
            m["fps"], m["width"], m["height"] = fps, tl["width"], tl["height"]
            out.append((sid, m))
        return out

    _write_registry(rdir, entries(safe), theme)

    # ---- 2. test render (changed, statically safe scenes only)
    if todo and mode == "check":
        man = os.path.join(work, "test_manifest.json")
        out = os.path.join(work, "test_report.json")
        os.makedirs(os.path.join(rc.ROOT, CHECK_DIR), exist_ok=True)
        _write_json(man, {"out": out, "outDir": os.path.join(rc.ROOT, CHECK_DIR), "browserExecutable": _browser_exe(rc),
                          "timeoutMs": 60000, "scenes": [{"id": sid, "composition": "scene-" + slug(sid)} for sid in todo]})
        print(f"  Test render ({len(todo)} scene(s); the first run downloads a headless browser)...")
        code, tail = _run_node(rc, rdir, "test_scenes.mjs", man, show_progress=True)
        rep = _read_json(out, {})
        if code != 0 or not rep.get("ok"):
            why = rep.get("error") or tail or "unknown error"
            for sid in todo:
                results[sid].update(status="unchecked", message="the test render could not run: " + _short(why, 120),
                                    messages=[why], static_ok=True)
        else:
            for sid in todo:
                err, warns, files = _judge(rep["scenes"].get(sid, {}), rep.get("ref", {}))
                res = results[sid]
                res["warnings"] = res["warnings"] + warns
                res["frames"] = [os.path.relpath(f, rc.ROOT) for f in files]
                if err:
                    res.update(status="failed", message=err, messages=[err])
                else:
                    res.update(status="ok", message="")
    elif todo and mode == "preview":
        for sid in todo:
            results[sid]["status"] = "unchecked"
            results[sid]["message"] = "not test-rendered yet (preview only)"

    # ---- cache + final registry
    for sid in gen:
        res = results.get(sid)
        if res and res.get("hash"):
            if res["status"] == "unchecked" and "could not run" in res.get("message", ""):
                continue  # an environment problem, not a verdict: retry next time
            cs[sid] = {k: res.get(k) for k in ("hash", "status", "message", "messages", "cost", "warnings", "frames", "static_ok")}
    _write_json(os.path.join(rc.ROOT, CACHE_FILE), cache)
    if mode == "check":
        _write_registry(rdir, entries([sid for sid in gen if results.get(sid, {}).get("status") == "ok"]), theme)
    else:
        _write_registry(rdir, entries([sid for sid in gen if results.get(sid, {}).get("static_ok") or results.get(sid, {}).get("status") == "ok"]), theme)
    shutil.rmtree(work, ignore_errors=True)
    # make the cached results look like fresh ones for the rest of the pipeline
    for sid, res in results.items():
        if res.get("status") == "static_ok":
            res["status"] = "unchecked"


def _finish(rc, tl, report, mode):
    if mode == "check":
        _write_json(os.path.join(rc.ROOT, REPORT_FILE), report)


def _print_report(report, gen):
    ok = failed = 0
    for sid, r in report["scenes"].items():
        tag = {"ok": "[ok]", "failed": "[FAILED]", "blocked": "[BLOCKED]", "unchecked": "[NOT CHECKED]", "pending": "[NOT WRITTEN]"}.get(r["status"], "[?]")
        if r["status"] == "ok":
            ok += 1
            n = len([f for f in r.get("frames", []) if "_portrait" not in f])
            print(f"  {tag:<14}{sid:<10} {r['source']}   cost {r['cost']}" + (f"   ({n} frames looked at)" if n else ""))
        else:
            if r["status"] != "pending":
                failed += 1
            print(f"  {tag:<14}{sid:<10} {r['source']}")
            for m in r["messages"][:4]:
                print("      - " + _short(m, 170))
            print("      -> the keywords scene is used for this segment instead")
        for w in r.get("warnings", [])[:3]:
            print("      note: " + _short(w, 150))
    print(f"  {ok} scene(s) passed, {failed} replaced by the keywords scene.")
    pend = [sid for sid, r in report["scenes"].items() if r["status"] == "pending"]
    if pend:
        print(f"  {len(pend)} scene(s) are not written yet ({', '.join(pend[:6])}{'...' if len(pend) > 6 else ''}): "
              "open the Scenes tab, copy the scene prompt to Claude, paste the reply back.")


def _fix_prompt(rc, gen, results, segs_by_id):
    bad = [sid for sid in gen if results.get(sid, {}).get("status") in ("failed", "blocked")]
    path = os.path.join(rc.ROOT, FIX_PROMPT_FILE)
    if not bad:
        if os.path.exists(path):
            os.remove(path)
        return
    rdir = _rdir(rc)
    contract = ""
    if rdir:
        try:
            with open(os.path.join(rdir, "kit", "CONTRACT.md"), "r", encoding="utf-8") as f:
                contract = f.read()
        except OSError:
            pass
    parts = ["Some Remotion scenes you wrote for my Recap Studio video failed the automatic check, so the video uses a plain "
             "fallback scene for them. Please fix ONLY the scenes below. Send each corrected scene as its own complete code block, "
             "with its file name on the line above the block (for example  scenes/d_04.tsx ). Keep the same look and the same "
             "data props; change only what is needed to fix the problem. Follow the contract at the end.\n"]
    for sid in bad:
        res, r = results[sid], gen[sid]
        parts.append(f"=== SCENE {sid}  ({r['file']}) ===")
        if r.get("brief"):
            parts.append(f"Original brief: {r['brief']}")
        parts.append("Problems found:")
        parts += [f"  - {m}" for m in res["messages"][:8]]
        seg = segs_by_id.get(sid, {})
        if r.get("props"):
            parts.append("Data props it receives: " + json.dumps(r["props"], ensure_ascii=False))
        p = r.get("_path")
        code = ""
        if p and os.path.isfile(p):
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
        parts.append("Current code:\n```tsx\n" + code.rstrip() + "\n```\n")
    if contract:
        parts.append("=== THE CONTRACT AND HELPER KIT (follow it exactly) ===\n" + contract)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"\n[!] {len(bad)} scene(s) need fixing. Paste {FIX_PROMPT_FILE} to Claude, save the corrected files over the old ones in "
          f"{SCENES_DIR}/, then run 'Check scenes' again.")


# --------------------------------------------------------------------
# steps (called from recap.py)
# --------------------------------------------------------------------
def _load_for_steps(rc, args):
    path = os.path.join(rc.ROOT, "timeline.json")
    if not os.path.isfile(path):
        rc.die("There is no timeline.json yet. Run 'Build timeline.json' first (it needs the voice-over).")
    tl = _read_json(path, None)
    if not tl or "segments" not in tl:
        rc.die("timeline.json is unreadable. Run 'Build timeline.json' again.")
    data = rc.load_data(rc.find_json(args.json))
    segs = {s["id"]: s for s in rc.yt_segments(data)}
    return path, tl, segs


def step_scenes(rc, args):
    if getattr(args, "demo", False):
        return demo(rc, args)
    path, tl, segs = _load_for_steps(rc, args)
    resolve(rc, tl, segs, "check")
    _write_json(path, tl)
    print("\ntimeline.json updated. Next: 'Render with Remotion', or 'Preview scenes' to look at them in Remotion Studio.")


def step_preview(rc, args):
    rdir = _rdir(rc)
    ready, why = scenes_ready(rc)
    if not ready:
        rc.die(f"Cannot open Remotion Studio: {why}.")
    path, tl, segs = _load_for_steps(rc, args)
    resolve(rc, tl, segs, "preview")      # stages the scenes + registry; does NOT touch timeline.json
    npx = shutil.which("npx.cmd" if os.name == "nt" else "npx") or shutil.which("npx")
    cmd = [npx, "remotion", "studio", "src/index.ts", f"--port={STUDIO_PORT}"]
    kw = {"cwd": rdir}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)
    print(f"\n[+] Remotion Studio is starting in its own window (http://localhost:{STUDIO_PORT}; your browser opens by itself).")
    print("    In the left list: 'scene-<segment id>' = your scenes, 'example-...' = the reference scenes.")
    print("    Tick  portrait  in the props panel to see the 9:16 version. Close the Studio window when you are done.")
    print("    Edited a scene file? Save it, then run 'Preview scenes' again (the Studio window reloads it).")


# --------------------------------------------------------------------
# demo: put the reference scenes + deliberately broken ones into the (demo) project
# --------------------------------------------------------------------
DEMO_PLAN = [  # (segment index, scene file, source folder, data for "motion")
    (0, "timeline_reveal", "example", None),
    (1, "stat_ring", "example", {"data": {"value": 70, "label": "of players disagreed", "syncWord": "four"}, "cost": "low"}),
    (2, "quote_moment", "example", {"data": {"quote": "Every man dies. Not every man really lives.", "author": "Braveheart", "highlight": ["lives"]}, "cost": "low"}),
    (3, "broken_runtime", "demo", None),
    (4, "broken_static", "demo", None),
    (5, "blank_scene", "demo", None),
]


def demo(rc, args):
    rdir = _rdir(rc)
    path = rc.find_json(args.json)
    data = rc.load_data(path)
    segs = rc.yt_segments(data)
    if len(segs) < 5:
        rc.die("Run this in a project made with the demo / test media (menu 'Demo / test media'): it needs at least 5 segments.")
    if not os.path.exists(path + ".bak"):
        shutil.copyfile(path, path + ".bak")
    os.makedirs(os.path.join(rc.ROOT, SCENES_DIR), exist_ok=True)
    print("Installing demo scenes (segments.json is backed up to segments.json.bak):")
    for idx, name, where, motion in DEMO_PLAN:
        if idx >= len(segs):
            continue
        src = os.path.join(rdir, "scenes_examples", name + ".tsx") if where == "example" else os.path.join(rc.ROOT, "demo_scenes", name + ".tsx")
        if not os.path.isfile(src):
            print(f"  [!] {name}.tsx not found at {src}; skipped.")
            continue
        sid = segs[idx]["id"]
        shutil.copyfile(src, os.path.join(rc.ROOT, SCENES_DIR, sid + ".tsx"))
        segs[idx]["scene"] = {"type": "generated"}
        if motion:
            segs[idx]["motion"] = motion
        kind = "reference scene" if where == "example" else "DELIBERATELY BROKEN (" + {"broken_runtime": "crashes while rendering",
                                                                                      "broken_static": "tries to use the network",
                                                                                      "blank_scene": "draws nothing"}[name] + ")"
        print(f"  {sid}: scenes/{sid}.tsx  <- {name}   [{kind}]")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("\nNow run 'Build timeline.json' (it checks the scenes), then 'Render with Remotion'.")
    print("Expected: 3 scenes pass, 3 are replaced by the keywords scene with a readable message.")
