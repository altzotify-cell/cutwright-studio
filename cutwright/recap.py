"""Agent bridge to the Recap Studio engine (M6; goals G4 items 1-6).

One non-interactive command surface over the project pipeline, with machine-readable output:

    python -m cutwright recap projects --json
    python -m cutwright recap new <name> --module movie_recap --json
    python -m cutwright recap <step> --project <name> [--only IDS] [--engine E] --json
    python -m cutwright recap status <project> --json

Design rules this module keeps:

  * a project is driven by running ITS OWN `recap.py` as a subprocess with `cwd` = the project, so
    one project can never reach into another (recap.py chdir()s to its own folder by design);
  * `RECAP_NONINTERACTIVE=1` is always set: nothing here may sit waiting for a keypress;
  * `--force`, `init` and `collect` are REFUSED (typed error, exit 2) unless the caller passes both
    `--i-know-this-destroys-work` and a COMMS entry id - those three delete or re-ask work;
  * every refusal is a `BridgeError` with a code, a message and the fix, and the CLI prints it as
    the same JSON shape the engine verbs use (`_reject`);
  * stdlib only, and nothing is written except through `cutwright/guard.py` (the template copy is
    the one exception, and it is asserted writable before a byte is copied).
"""
import json
import os
import shutil
import subprocess
import sys
import time

from cutwright import guard

RECAP = guard.RECAP
PROJECTS = os.path.join(RECAP, "Projects")
TEMPLATE = os.path.join(RECAP, "_template")
DEFAULT_TIMEOUT = 900          # a Remotion render is minutes, not seconds

# Files a project owns a COPY of. A copy that drifted from _template runs old code: warn, never fix
# silently (G4 item 6).
BRIDGE_FILES = ("recap.py", "timeline.py", "scenes.py", "authoring.py", "wordtimes.py")

# G4 item 3: the steps an agent may run unattended. The rest either asks a human a question or
# deletes work; `WHY_REFUSED` says which, so a refusal is never a mystery.
STEPS = ("subs", "index", "sheets", "check", "missing", "say", "tts", "srt", "video", "timeline",
         "scenes", "remotion", "briefs", "preview", "demo")
WHY_REFUSED = {
    "init": "asks a human for module/topic/voice; write the project with `recap new` instead",
    "module": "rewrites project.json (module/topic); use `recap new`",
    "collect": "guided footage collection (yt-dlp / drag and drop) needs a human at the keyboard",
    "collect_one": "collects one shot from a URL interactively; not a pipeline step",
    "comic": "rewrites pages/ and panels/ from a comic file; run it with the owner present",
    "characters": "needs the owner's PNG cut-outs and rewrites characters/_preview.png",
    "tiktok": "spawns a second full pipeline into tiktok_out/; keep it deliberate, not unattended",
}
ALL_STEPS = tuple(WHY_REFUSED) + STEPS + ("review", "premiere", "videopad")


class BridgeError(RuntimeError):
    """A refused bridge call: code, message, fix. Never transient."""

    def __init__(self, message, code="bridge_error", suggested="", details=None):
        self.code = code
        self.suggested = suggested
        self.details = details or {}
        super().__init__(message)


# ------------------------------------------------------------------ projects on disk
def project_dir(name):
    """`recapstudio/Projects/<name>`, or a typed refusal. Name is ONE path segment, never a path."""
    text = (name or "").strip()
    if not text:
        raise BridgeError("no project given", code="no_project",
                          suggested="--project <name>, or `recap projects` to list them")
    if os.path.basename(text) != text or text in (".", "..") or ":" in text:
        raise BridgeError("%r is not a project name" % text, code="bad_project_name",
                          suggested="a bare folder name under recapstudio\\Projects")
    path = os.path.join(PROJECTS, text)
    if not os.path.isdir(path):
        raise BridgeError("no project %r in recapstudio\\Projects" % text, code="unknown_project",
                          suggested="`recap projects`, or `recap new %s --module movie_recap`" % text)
    return path


def _rel(path):
    return guard.rel(path).replace("\\", "/")


def _segments(path):
    """Segment ids in segments.json: the `youtube` list plus every `tiktok` part. `_` keys are notes."""
    data = guard.read_json(os.path.join(path, "segments.json"), None)
    if not isinstance(data, dict):
        return {"segments": 0, "ids": []}
    groups = []
    if isinstance(data.get("youtube"), list):
        groups.append(data["youtube"])
    tiktok = data.get("tiktok")
    if isinstance(tiktok, dict):
        groups.extend([row for row in tiktok.values() if isinstance(row, list)])
    ids = []
    for group in groups:
        for row in group:
            if isinstance(row, dict) and row.get("id"):
                ids.append(str(row["id"]))
    return {"segments": len(ids), "ids": ids}


def _audio(path):
    folder = os.path.join(path, "audio")
    if not os.path.isdir(folder):
        return 0
    return len([n for n in os.listdir(folder)
                if os.path.splitext(n)[1].lower() in (".mp3", ".wav", ".m4a", ".flac", ".ogg")])


OUTPUTS = {
    "segments": "segments.json",
    "audio": "audio",
    "timeline": "timeline.json",
    "subtitles": "recap_subtitles.srt",
    "final": "recap_final.mp4",
    "remotion": "recap_remotion.mp4",
    "premiere_xml": "premiere_sequence.xml",
    "state": "STATE.md",
}


def _outputs(path):
    return {label: os.path.exists(os.path.join(path, name)) for label, name in OUTPUTS.items()}


def stale(path):
    """Which of the project's own code copies no longer match `_template/` (hash compare)."""
    changed, missing = [], []
    for name in BRIDGE_FILES:
        mine, original = os.path.join(path, name), os.path.join(TEMPLATE, name)
        if not os.path.isfile(mine):
            missing.append(name)
        elif os.path.isfile(original) and guard.sha256_file(mine) != guard.sha256_file(original):
            changed.append(name)
    return {"checked": len(BRIDGE_FILES), "stale": changed, "missing": missing,
            "ok": not changed and not missing}


def summary(name):
    path = os.path.join(PROJECTS, name)
    project = guard.read_json(os.path.join(path, "project.json"), {}) or {}
    seg = _segments(path)
    row = {"name": name, "path": _rel(path), "module": project.get("module", ""),
           "topic": project.get("topic", ""), "segments": seg["segments"],
           "audio_files": _audio(path), "outputs": _outputs(path), "stale": stale(path)}
    row["next"] = next_step(row["segments"], row["audio_files"], row["outputs"])
    return row


def projects():
    """Every real project under recapstudio/Projects, with what exists and what is next."""
    rows = []
    if os.path.isdir(PROJECTS):
        for name in sorted(os.listdir(PROJECTS)):
            path = os.path.join(PROJECTS, name)
            if name.startswith((".", "_")) or not os.path.isdir(path):
                continue
            rows.append(summary(name))
    return {"ok": True, "count": len(rows), "projects": rows}


def new(name, module="movie_recap", topic=""):
    """Copy `_template` to Projects/<name> and write project.json directly. Never runs `init`."""
    text = (name or "").strip()
    if not text or os.path.basename(text) != text or text in (".", "..") or ":" in text:
        raise BridgeError("%r is not a project name" % text, code="bad_project_name",
                          suggested="a bare folder name, e.g. `recap new g1 --module movie_recap`")
    dest = os.path.join(PROJECTS, text)
    if os.path.exists(dest):
        raise BridgeError("project %r already exists" % text, code="project_exists",
                          suggested="pick another name, or work in it: recap status %s" % text)
    if not module:
        raise BridgeError("no module given", code="no_module",
                          suggested="--module movie_recap|show_recap|comic_recap|nba_minidoc|"
                                    "nba_story|real_story|ranking")
    guard.assert_writable(dest)
    shutil.copytree(TEMPLATE, dest,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"))
    base = guard.read_json(os.path.join(dest, "project.json"), {}) or {}
    base.update({"module": module, "topic": topic or ""})
    guard.write_json(os.path.join(dest, "project.json"), base)
    row = summary(text)
    row["ok"] = True
    row["created"] = True
    return row


# ------------------------------------------------------------------ refusals
def check(step, force=False, override=False, comms=""):
    """Refuse a step (or `--force`) that could destroy work. Returns the override record, or {}.

    The refusal is the feature: an agent must never rewrite work by accident, so `--force` needs
    BOTH `--i-know-this-destroys-work` and a COMMS id - the override then travels in the JSON.
    """
    text = (step or "").strip()
    if text in WHY_REFUSED:
        raise BridgeError("`recap %s` is not an unattended step: %s" % (text, WHY_REFUSED[text]),
                          code="forbidden_step",
                          suggested="allowed steps: %s" % ", ".join(STEPS))
    if text not in STEPS:
        raise BridgeError("unknown recap step %r" % text, code="unknown_step",
                          suggested="allowed steps: %s" % ", ".join(STEPS))
    if not force:
        return {}
    if not override or not (comms or "").strip():
        raise BridgeError("--force is refused: it rewrites outputs that already exist",
                          code="forbidden_flag",
                          suggested="drop --force, or pass BOTH --i-know-this-destroys-work and "
                                    "--comms <COMMS id> so the override is written down")
    return {"force": True, "comms": comms.strip()}


# ------------------------------------------------------------------ running one step
def _decode(raw):
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return str(raw)


def _tail(text, lines=40):
    rows = (text or "").replace("\r\n", "\n").split("\n")
    return "\n".join(rows[-lines:]).strip()


def _snapshot(root):
    """{relpath: [size, mtime_ns]} - cheap identity, no hashing (a project can hold 4 GB)."""
    rows = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for name in files:
            full = os.path.join(dirpath, name)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            rows[os.path.relpath(full, root).replace("\\", "/")] = [stat.st_size,
                                                                   stat.st_mtime_ns]
    return rows


def _diff(before, after):
    changed = sorted(key for key, value in after.items() if before.get(key) != value)
    removed = sorted(key for key in before if key not in after)
    return changed, removed


# Known plain-English lines a step prints when something needs the agent's attention (G4 item 4).
PROBLEM_MARKERS = ("MISSING SHOT", "MISSING  ->", "MISSING ->", "Traceback (most recent call last)")


def problems(text, limit=20):
    """The lines of a step's output that name a problem, de-duplicated, newest last."""
    found = []
    for line in (text or "").splitlines():
        clean = line.strip()
        if not clean:
            continue
        if (clean.startswith(("[!]", "Error", "ERROR"))
                or any(marker in clean for marker in PROBLEM_MARKERS)):
            if clean[:300] not in found:
                found.append(clean[:300])
    return found[-limit:]


def run(project, step, only="", engine="", preview=False, yes=False, demo=False,
        force=False, override=False, comms="", timeout=DEFAULT_TIMEOUT):
    """Run ONE step of the project's own `recap.py` and return the JSON contract.

    A step that exits non-zero is a RESULT (`ok: false`, `code: step_failed`, the tail of its
    output), not an exception: the agent needs to read what happened. Only a refusal or a missing
    project raises `BridgeError`.
    """
    path = project_dir(project)
    allowed = check(step, force=force, override=override, comms=comms)
    argv = [sys.executable, "recap.py", step]
    if only:
        argv += ["--only", only]
    if engine:
        argv += ["--engine", engine]
    if preview:
        argv += ["--preview"]
    if yes:
        argv += ["--yes"]
    if demo and step in ("scenes", "briefs"):
        argv += ["--demo"]
    if allowed.get("force"):
        argv += ["--force"]
    env = dict(os.environ)
    env.update({"RECAP_NONINTERACTIVE": "1", "RECAP_NO_REVEAL": "1",
                "PYTHONIOENCODING": "utf-8"})
    before = _snapshot(path)
    started = time.time()
    timed_out = False
    try:
        proc = subprocess.run(argv, cwd=path, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out, err, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        out, err, code = exc.stdout, exc.stderr, None
    except OSError as exc:
        raise BridgeError("could not start recap.py in %s: %s" % (_rel(path), exc),
                          code="spawn_failed", suggested="python -m cutwright doctor")
    seconds = round(time.time() - started, 1)
    stdout, stderr = _decode(out), _decode(err)
    changed, removed = _diff(before, _snapshot(path))
    data = {"ok": code == 0 and not timed_out, "step": step, "project": project,
            "project_dir": _rel(path), "exit_code": code, "seconds": seconds,
            "command": argv[1:], "noninteractive": True,
            "stdout_tail": _tail(stdout, 40), "stderr_tail": _tail(stderr, 20),
            "files_changed": changed[:200], "files_changed_count": len(changed),
            "files_removed": removed[:50],
            "problems": problems(stdout + "\n" + stderr)}
    if timed_out:
        data["code"] = "step_timeout"
        data["suggested"] = ("the step was stopped at %ds; raise --timeout or run that render on "
                             "its own" % int(timeout))
    elif code != 0:
        data["code"] = "step_failed"
        data["suggested"] = ("read problems[] and stdout_tail; RECAP_NONINTERACTIVE=1 was set, so "
                             "a prompt for a human is not the cause")
    if allowed:
        data["override"] = allowed
    return data


# ------------------------------------------------------------------ status
def next_step(segments, audio_files, outputs):
    """The next step worth running, from what exists on disk. A suggestion, never a promise.

    Counts, not file existence: the template ships an EMPTY segments.json, so "the file is there"
    would send an agent straight to `tts` on a project with nothing to voice.
    """
    has = outputs or {}
    if not segments:
        return "demo (synthetic test media) or author segments.json"
    if not audio_files:
        return "tts"
    if not has.get("timeline"):
        return "timeline"
    if not (has.get("remotion") or has.get("final")):
        return "remotion"
    return "check"


def _read_text(path, limit=4000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()[-limit:]
    except OSError:
        return ""


def status(project):
    """One JSON for one project: counts, what exists, what is stale, the failed scenes (G4 item 5)."""
    path = project_dir(project)
    meta = guard.read_json(os.path.join(path, "project.json"), {}) or {}
    seg = _segments(path)
    timeline = guard.read_json(os.path.join(path, "timeline.json"), None)
    outputs = _outputs(path)
    audio = _audio(path)
    data = {"ok": True, "project": project, "project_dir": _rel(path),
            "module": meta.get("module", ""), "topic": meta.get("topic", ""),
            "segments": seg["segments"], "segment_ids": seg["ids"], "audio_files": audio,
            "outputs": outputs, "timeline": None,
            "state_md_tail": _tail(_read_text(os.path.join(path, "STATE.md")), 12),
            "stale": stale(path), "problems": []}
    if isinstance(timeline, dict):
        data["timeline"] = {"fps": timeline.get("fps"), "width": timeline.get("width"),
                            "height": timeline.get("height"),
                            "total_frames": timeline.get("totalFrames"),
                            "segments": len(timeline.get("segments") or []),
                            "generated": timeline.get("generated", "")}
    if seg["segments"] and audio < seg["segments"]:
        data["problems"].append("%d segment(s) but only %d audio file(s): run tts"
                                % (seg["segments"], audio))
    if data["timeline"] and data["timeline"]["segments"] != seg["segments"]:
        data["problems"].append("timeline.json has %d segment(s), segments.json has %d: re-run "
                                "timeline" % (data["timeline"]["segments"], seg["segments"]))
    if data["stale"]["stale"]:
        data["problems"].append("stale code copies vs _template/: %s (the project runs old code)"
                                % ", ".join(data["stale"]["stale"]))
    data["next"] = next_step(seg["segments"], audio, outputs)
    return data
