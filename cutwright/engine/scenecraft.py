"""The scene authoring brief (M7): what a scene may be written WITH, in one screen.

Why this file exists: M5.5 proved the kit can draw a directed shot, but the knowledge lived in one
example file and a doc. An agent starting a new scene had to read `kit/**` to learn that `Camera`
takes `push`/`pan`, that `KineticText` takes `emphasis` and `startFrames`, that footage is named by
a HANDLE and never by a path. This module is the tool-shaped version of that prompt
(`python -m cutwright scene brief`): the four primitives that carry a shot, the asset-handle rule,
how a scene file becomes a renderable composition, and the critic loop's checklist.

It is DATA, and it is checked against the real kit: `tests/test_engine_registry.py` reads
`recapstudio/remotion/kit/**` and fails if a primitive or a prop listed here stops existing, so the
brief cannot drift into advice the renderer does not honour.
"""
import os
import subprocess
import time

from .. import guard

KIT = os.path.join(guard.ROOT, "recapstudio", "remotion", "kit")
REMOTION = os.path.join(guard.ROOT, "recapstudio", "remotion")
CHECKER = os.path.join(REMOTION, "tools", "check_scenes.mjs")
NODE = os.environ.get("CUTWRIGHT_NODE", "node")   # same override the Remotion executor uses


class SceneError(ValueError):
    """A scene file that cannot be checked, with the machine-readable reason."""

    def __init__(self, message="", code="scene_error", suggested=""):
        self.code = code
        self.suggested = suggested
        self.message = message
        super().__init__(message)

# A scene may import these three and nothing else (kit/CONTRACT.md rule 1-3, enforced by the checker).
IMPORTS = ("remotion", "react", "@kit")

# The four primitives M5.5 added or proved. `props` lists the ones a directed shot actually reaches
# for; the kit's own files are the full list and `scene brief` points at them.
PRIMITIVES = (
    {"name": "Camera", "file": "kit/media.tsx",
     "job": "one transform on everything: push/pan/shake - the difference between a shot and a slide",
     "props": ("push", "pan", "panY", "shake", "start", "duration", "curve")},
    {"name": "LayeredMedia", "file": "kit/media.tsx",
     "job": "full-bleed footage or a still by HANDLE, with scrim / tint / vignette and content on top",
     "props": ("asset", "scrim", "tint", "tintStrength", "vignette", "zoom", "startFrom",
               "fallback")},
    {"name": "KineticText", "file": "kit/kinetic.tsx",
     "job": "type that ENTERS like a title: staggered spring, skew, blur, one accented word",
     "props": ("text", "start", "step", "startFrames", "size", "rise", "skew", "blur",
               "scaleFrom", "emphasis", "emphasisColor")},
    {"name": "MaskWipe", "file": "kit/kinetic.tsx",
     "job": "a hard, optionally slanted clip-path edge for reveals and instrument rails",
     "props": ("direction", "angle", "start", "duration", "from", "box")},
)

# Handle rule (docs/ASSET_HANDLES.md 1-2): a literal, declared by the STEP, never a path.
HANDLE_PATTERN = r"^[a-z][a-z0-9_]{0,31}$"
HANDLE_RULE = ("a scene writes asset=\"footage_a\" - a plain string literal matching %s; the step "
               "declares it as \"assets\": {\"footage_a\": \"@asset.footage_a\"} and the engine "
               "stages the file. No path, no template string, no .mp4 in a scene." % HANDLE_PATTERN)

# A scene becomes renderable only through a registered composition: the file exports
# `{component, meta}` and `src/SceneLab.tsx` adds it as bench-<id> / example-<name> / scene-<id>.
COMPOSITION_RULE = ("export `const <name>Entry = {component, meta: {id, title, cost, fps, "
                    "durationInFrames, width, height, props, words, text, status}}` and register it "
                    "in `src/SceneLab.tsx`; the manifest step names the COMPOSITION id "
                    "(bench-<id>, example-<name>, scene-<segment id>), not the file.")

# The three looks M5.5C settled on: the shot opens, develops, pays off. A still costs ~6-10 s.
STILL_LOOKS = (("start", 0.0), ("middle", 0.25), ("impact", 0.75))

# What the critic checks on those stills (docs/VISUAL_STANDARD.md sections 1 and 4) plus the one
# measured rule M5.5C paid for: the sub line sits ABOVE the caption band, not at safeBottom.
REVIEW_CHECKS = (
    ("composition", "does the frame read as a designed shot - one focal point, a clear hierarchy?"),
    ("readability", "type over footage: >12:1 contrast, no thin light text on a bright sky"),
    ("depth", "at least two planes: silhouette / subject / sky, or foreground type over footage"),
    ("motion contrast", "does the frame differ from start to impact (camera, reveal, entrance)?"),
    ("caption band", "nothing sits between safeBottom and captionBottom: captions end ~157 px up "
                     "at 1080p, so text blocks end at captionBottom + 84u or higher"),
    ("powerpoint", "VISUAL_STANDARD section 4: no card rows, no decorative circles, no fade-only"),
)
MAX_REVISIONS = 2
STANDARD = "docs/VISUAL_STANDARD.md"


def still_frames(duration):
    """The frames worth rendering: start, middle, impact - the same three M5.5C judged."""
    total = max(1, int(duration))
    out = []
    for name, at in STILL_LOOKS:
        frame = int(round(total * at))
        out.append({"look": name, "frame": min(total - 1, max(0, frame))})
    return out


def brief(handle="", composition="", duration=192):
    """The authoring brief for ONE new scene. `handle` is the footage handle the step will declare."""
    frames = still_frames(duration)
    return {
        "schema": 1,
        "imports": list(IMPORTS),
        "primitives": [dict(row, props=list(row["props"])) for row in PRIMITIVES],
        "handles": {"pattern": HANDLE_PATTERN, "rule": HANDLE_RULE,
                    "declared": [handle] if handle else [],
                    "kinds": ["video (.mp4/.mov/.webm)", "image (.png/.jpg)"]},
        "composition": {"id": composition or "bench-<id>", "rule": COMPOSITION_RULE,
                        "scene_dir": os.path.join("recapstudio", "remotion", "src", "scenes")},
        "duration_frames": int(duration),
        "stills": frames,
        "review": [{"check": name, "question": question} for name, question in REVIEW_CHECKS],
        "max_revisions": MAX_REVISIONS,
        "standard": STANDARD,
        "authoring_files": {"kit": "recapstudio/remotion/kit/CONTRACT.md",
                            "example": "recapstudio/remotion/src/scenes/directed_shot.tsx",
                            "handles": "docs/ASSET_HANDLES.md"},
    }


def check_manifest(files, handles=()):
    """The manifest `tools/check_scenes.mjs` reads: scenes by absolute path, the handles allowed."""
    scenes = []
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        scenes.append({"id": name, "file": os.path.abspath(path)})
    return {"out": "report.json", "handles": list(handles), "scenes": scenes}


def check(files, handles=(), out_dir="", timeout=180.0):
    """Run the real TypeScript static check (node + typescript) on scene files and return its report."""
    if not os.path.isfile(CHECKER):
        raise SceneError("the scene checker is missing: %s" % guard.rel(CHECKER),
                         code="checker_missing")
    missing = [path for path in files if not os.path.isfile(path)]
    if missing:
        raise SceneError("no such scene file: %s" % ", ".join(guard.rel(p) for p in missing),
                         code="scene_missing")
    folder = guard.ensure_dir(out_dir or os.path.join(guard.OUT, "scene-check"))
    report_path = os.path.join(folder, "report.json")
    # The checker resolves `out` against ITS cwd (recapstudio/remotion), so the manifest carries an
    # absolute path - a relative one silently lands a report next to the checker.
    document = check_manifest(files, handles)
    document["out"] = report_path
    manifest_path = guard.write_json(os.path.join(folder, "scenes.json"), document)
    if os.path.exists(report_path):
        os.remove(report_path)
    command = [NODE, CHECKER, manifest_path]
    started = time.monotonic()
    try:
        done = subprocess.run(command, cwd=REMOTION, capture_output=True, text=True,
                              timeout=timeout)
    except OSError as exc:
        raise SceneError("cannot run node: %s" % exc, code="node_missing",
                         suggested="node must be on PATH (it renders Remotion too)")
    except subprocess.TimeoutExpired:
        raise SceneError("the scene check did not finish in %ds" % int(timeout),
                         code="check_timeout")
    if not os.path.exists(report_path):
        raise SceneError("the checker wrote no report (exit %d)" % done.returncode,
                         code="check_failed", suggested=(done.stderr or done.stdout).strip()[-300:])
    report = guard.read_json(report_path, default={}) or {}
    rows = report.get("scenes") or {}
    errors = sum(len((row or {}).get("errors") or []) for row in rows.values())
    warnings = sum(len((row or {}).get("warnings") or []) for row in rows.values())
    return {"ok": errors == 0, "scenes": rows, "errors": errors, "warnings": warnings,
            "report": guard.rel(report_path), "command": command[:2],
            "seconds": round(time.monotonic() - started, 3)}
