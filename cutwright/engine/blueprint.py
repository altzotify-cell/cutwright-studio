"""The production blueprint (M8): the plan an agent DESIGNS, compiled into a manifest.

Why this file exists: until M8 the agent's shape of work was a manifest written by hand - one JSON
object per op, every `@ref`, every path, every validation row typed out. M7 proved the drawing half
(a scene can be authored with a tool and judged on stills); M8 is about the other half: the agent
should say WHAT the video is - beats, shot types, which footage, which voice, which bed - and let
this module turn that into the step graph the engine already knows how to run.

So there are two verbs and one rule each:

  * `generate(brief)`  -> a `ProductionBlueprint`: beats with a SHOT TYPE, a scene file, a
    composition id and a frame count. The frame count is not invented: it comes from the narration's
    real word timings (edge-tts emits them), so a beat ends where its sentence ends.
  * `compile(blueprint)` -> `manifest.json`. Every op in it is chosen from `ops.py` (Kinocut/FFmpeg
    by the measured matrix), every asset is a declared handle, every step declares the checks
    `validate.py` knows, and the result is passed through `manifest.validate()` BEFORE it is written:
    a blueprint that compiles to an unrunnable plan fails here, not after a 3-minute render.

The blueprint is also the record of provenance (`docs/ASSET_HANDLES.md`): one row per asset saying
where it came from (footage / user_image / code_graphic / stock_licensed, never AI-generated), so
`production_report.json` and the deliverable can both answer "what is in this video".

Stdlib only (`.clinerules/01`, assumption A8). Narration is synthesised by `tools/narrate.py`, a
separate script run through `subprocess` - the same boundary `scenecraft.py` uses for the TypeScript
checker, so `import cutwright` never drags a voice engine into the agent's process.
"""
import json
import os
import subprocess
import sys

from .. import guard, probe
from . import manifest as engine_manifest

SCHEMA = 1
KIND = "production_blueprint"
DEFAULT_FPS = 24
DEFAULT_SIZE = (1920, 1080)
# A beat shorter than half a second cannot carry a shot; the engine renders at 24 fps and the kit's
# entrances need ~0.4 s. Anything below this is a brief that should be rewritten, not rendered.
MIN_BEAT_FRAMES = 12
# The picture is allowed to run past the last word so the final frame is not a hard stop on a vowel.
TAIL_SECONDS = 0.30
ORIGINS = ("footage", "user_image", "code_graphic", "stock_licensed", "user_audio")

NARRATE = os.path.join(guard.ROOT, "tools", "narrate.py")

# The shot types this module can compile. Each one names the scene file and the composition id that
# ALREADY EXIST in `recapstudio/remotion` (M8 authored the three below); `needs` says which kind of
# asset the shot requires, so a footage shot without footage is refused at compile time.
# `tests/test_engine_cli.py` reads the scene files and `SceneLab.tsx` to prove these have not drifted.
SHOTS = (
    {"id": "layered_push",
     "job": "layered footage under a slow camera push - the shot that must not read as a slide",
     "scene": "recapstudio/remotion/src/scenes/m8_layered_push.tsx",
     "composition": "bench-m8-layered-push", "needs": ("footage",)},
    {"id": "kinetic_reveal",
     "job": "high-impact kinetic typography: type that enters like a title, nothing else on screen",
     "scene": "recapstudio/remotion/src/scenes/m8_kinetic_reveal.tsx",
     "composition": "bench-m8-kinetic-reveal", "needs": ()},
    {"id": "directed_mask",
     "job": "a directed shot revealed by an angled mask wipe (the kit's MaskWipe, a real angle)",
     "scene": "recapstudio/remotion/src/scenes/m8_directed_wipe.tsx",
     "composition": "bench-m8-directed-wipe", "needs": ("footage",)},
)
BY_SHOT = {row["id"]: row for row in SHOTS}


class BlueprintError(ValueError):
    """A brief or a blueprint that cannot become a plan: names the code and the fix."""

    def __init__(self, message="", code="invalid_blueprint", suggested="", errors=()):
        self.code = code
        self.suggested = suggested
        self.message = message
        self.errors = list(errors)
        text = "blueprint rejected (code %s)" % code
        if message:
            text += ": %s" % message
        if suggested:
            text += " -> %s" % suggested
        super().__init__(text)

    def to_dict(self):
        return {"code": self.code, "message": self.message, "suggested": self.suggested,
                "errors": list(self.errors)}


# ------------------------------------------------------------------ small helpers
def _apath(value):
    """Blueprint path -> absolute path, resolved against the fork like a manifest path."""
    return engine_manifest.resolve_path(value)


def _rel(value):
    return guard.rel(str(value))


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def tokens(text):
    """The words a narration line is spoken as: whitespace split, punctuation kept off the count."""
    return [word for word in str(text or "").replace("\n", " ").split() if word.strip(" .,;:!?-")]


def load(path):
    """Read a blueprint file. Typed failures: a typo in a plan costs nothing."""
    full = _apath(path)
    if not os.path.isfile(full):
        raise BlueprintError("no such blueprint: %s" % _rel(full), code="not_found",
                             suggested="`python -m cutwright blueprint generate <brief.json>` writes one")
    data = guard.read_json(full)
    if not isinstance(data, dict):
        raise BlueprintError("not a blueprint: %s" % _rel(full), code="not_json",
                             suggested="a blueprint is a JSON object (see blueprint generate)")
    return data


def save(path, document):
    """Write a blueprint/plan document through the write guard. Returns the absolute path."""
    return guard.write_json(_apath(path), document)


# ------------------------------------------------------------------ the brief -> narration
def _check_brief(brief):
    """Every refusal a brief can earn, collected before any work is done."""
    errors = []
    if not isinstance(brief, dict):
        raise BlueprintError("a brief is a JSON object", code="bad_brief")
    beats = brief.get("beats")
    if not isinstance(beats, list) or not 2 <= len(beats) <= 6:
        errors.append({"code": "bad_beats", "message": "'beats' must be a list of 2 to 6 beats",
                       "suggested": "one entry per story beat: {\"id\", \"shot\", \"say\"}"})
        beats = []
    assets = brief.get("assets") or {}
    if not isinstance(assets, dict):
        errors.append({"code": "bad_assets", "message": "'assets' is a mapping of handle -> "
                                                      "{path, origin, license}"})
        assets = {}
    seen = set()
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            errors.append({"code": "bad_beat", "message": "beat %d is not an object" % index})
            continue
        beat_id = str(beat.get("id") or "").strip()
        if not beat_id:
            errors.append({"code": "missing_beat_id", "message": "beat %d has no id" % index})
        elif beat_id in seen:
            errors.append({"code": "duplicate_beat", "message": "beat id %r is used twice" % beat_id})
        seen.add(beat_id)
        shot = str(beat.get("shot") or "")
        if shot not in BY_SHOT:
            errors.append({"code": "unknown_shot",
                           "message": "beat %r has shot %r" % (beat_id, shot),
                           "suggested": "one of: %s" % ", ".join(BY_SHOT)})
        if not tokens(beat.get("say")):
            errors.append({"code": "missing_say",
                           "message": "beat %r has no narration line ('say')" % beat_id,
                           "suggested": "the narration IS the clock: a beat without words has no "
                                        "measured length"})
        for handle in beat.get("uses") or []:
            if handle not in assets:
                errors.append({"code": "unknown_handle",
                               "message": "beat %r uses %r, which 'assets' does not declare"
                                          % (beat_id, handle),
                               "suggested": "declare it under 'assets', or drop it from 'uses'"})
        if shot in BY_SHOT:
            for kind in BY_SHOT[shot]["needs"]:
                given = [h for h in (beat.get("uses") or [])
                         if str((assets.get(h) or {}).get("origin") or "") == kind]
                if not given:
                    errors.append({"code": "shot_needs_asset",
                                   "message": "beat %r is a %s shot but uses no %s asset"
                                              % (beat_id, shot, kind),
                                   "suggested": "add the handle to 'uses' (origin %r)" % kind})
    for handle, row in assets.items():
        if not isinstance(row, dict) or not row.get("path"):
            errors.append({"code": "bad_asset", "message": "asset %r needs a path" % handle})
            continue
        origin = str(row.get("origin") or "")
        if origin not in ORIGINS:
            errors.append({"code": "bad_origin", "message": "asset %r has origin %r"
                           % (handle, origin), "suggested": "one of: %s (never AI-generated)"
                           % ", ".join(ORIGINS)})
        if not os.path.isfile(_apath(row["path"])):
            errors.append({"code": "asset_missing", "message": "asset %r is not on disk: %s"
                           % (handle, row["path"]),
                           "suggested": "check the path; a blueprint never invents a file"})
    fps = brief.get("fps", DEFAULT_FPS)
    if not _number(fps) or fps <= 0:
        errors.append({"code": "bad_fps", "message": "fps must be a positive number"})
    size = brief.get("size") or list(DEFAULT_SIZE)
    if not isinstance(size, (list, tuple)) or len(size) != 2 or not all(_number(v) for v in size):
        errors.append({"code": "bad_size", "message": "size is [width, height]"})
    if errors:
        raise BlueprintError("the brief has %d problem(s)" % len(errors), code="bad_brief",
                             suggested=errors[0].get("suggested", ""), errors=errors)
    return beats, assets


def narrate(text, wav_path, voice="en-US-ChristopherNeural", rate="+0%", timeout=180.0):
    """Synthesise `text` into `wav_path` (+ .mp3 and a timings .json) via `tools/narrate.py`.

    Returns the timings document: {"seconds": float, "words": [{word, start, end}], ...}. The word
    timings are the reason this step exists - they are what turns a script into beat boundaries
    instead of a guess. A missing edge-tts, a dead network or a refused request is a typed error
    naming the workaround (a recorded narration file), never a silent fallback to a tone.
    """
    if not os.path.isfile(NARRATE):
        raise BlueprintError("the narration helper is missing: %s" % _rel(NARRATE),
                             code="narrate_missing",
                             suggested="restore tools/narrate.py, or pass --narration FILE")
    target = os.path.abspath(wav_path)
    folder = guard.ensure_dir(os.path.dirname(target))
    stem = os.path.splitext(os.path.basename(target))[0]
    request = guard.write_json(os.path.join(folder, stem + "_request.json"),
                               {"text": text, "wav": target, "voice": voice, "rate": rate})
    argv = [sys.executable, NARRATE, request]
    try:
        done = subprocess.run(argv, cwd=guard.ROOT, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        raise BlueprintError("narration did not finish in %ds" % int(timeout), code="tts_timeout",
                             suggested="a shorter script, or pass a recorded --narration FILE")
    except OSError as exc:
        raise BlueprintError("cannot start the narration helper: %s" % exc, code="tts_failed")
    timings = guard.read_json(os.path.join(folder, stem + ".json"), default={}) or {}
    if done.returncode != 0 or not timings.get("words"):
        lines = [line for line in (done.stderr or done.stdout or "").strip().splitlines() if line]
        raise BlueprintError("narration failed (exit %d): %s"
                             % (done.returncode, lines[-1] if lines else "no output"),
                             code="tts_failed",
                             suggested="check the voice name and the network; or pass --narration "
                                       "FILE with a narration you already have")
    return timings


def _narration(path, timings=None):
    """(seconds, words, engine) for the narration file, measured when no timings were recorded."""
    timings = timings or {}
    seconds = float(timings.get("seconds") or 0.0) if _number(timings.get("seconds")) else 0.0
    if seconds <= 0 and os.path.isfile(path):
        seconds = float(probe.media_info(path).get("duration") or 0.0)
    if seconds <= 0:
        raise BlueprintError("the narration has no measurable duration: %s" % _rel(path),
                             code="bad_narration",
                             suggested="probe it first: python -m cutwright probe FILE")
    return seconds, list(timings.get("words") or []), str(timings.get("engine") or "measured")


def _boundaries(beats, words, seconds, fps):
    """Where each beat starts and ends, in FRAMES, from the narration's own word timings.

    The word timings win when they cover the script (edge-tts emits one cue per word, in order):
    beat i starts where its first word starts and ends where beat i+1 starts, so the cut lands on
    the sentence, not on an average. Without timings the declared `seconds` are used, and failing
    that the narration is split by word count. Boundaries are rounded ONCE, at the frame, so the
    beat frames always add up to the total (no drift, no off-by-one tail).
    """
    counts = [len(tokens(beat.get("say"))) for beat in beats]
    starts = []
    if words and sum(counts) and len(words) >= sum(counts):
        offset = 0
        for count in counts:
            starts.append(float(words[offset].get("start") or 0.0))
            offset += count
        starts[0] = 0.0
        end = max(seconds, float(words[sum(counts) - 1].get("end") or 0.0))
        how = "word timings"
    elif all(_number(beat.get("seconds")) and beat["seconds"] > 0 for beat in beats):
        running = 0.0
        for beat in beats:
            starts.append(running)
            running += float(beat["seconds"])
        end = running
        how = "declared seconds"
    else:
        total = sum(counts) or len(beats)
        running, seen = 0.0, 0
        for count in counts:
            starts.append(running)
            seen += count
            running = seconds * seen / total
        end = seconds
        how = "word-count estimate"
    end += TAIL_SECONDS
    edges = [int(round(value * fps)) for value in starts] + [int(round(end * fps))]
    edges[0] = 0
    for index in range(1, len(edges)):                 # monotonic: a beat never has 0 or -3 frames
        edges[index] = max(edges[index], edges[index - 1] + MIN_BEAT_FRAMES)
    return [(edges[i], edges[i + 1] - edges[i]) for i in range(len(beats))], how


def generate(brief, out="", narration="", tts=None, project=""):
    """Design a ProductionBlueprint from a brief. Returns (document, path written).

    `brief`      the agent's intent: title, beats (shot type + the words spoken), asset handles
    `narration`  a narration file to use instead of synthesising one (any format ffmpeg reads)
    `tts`        None = synthesise when the narration file is absent; False = never touch the network
    `project`    the project folder (default: the brief's "project", else the folder of `out`)

    The blueprint is data, and it is the input to `compile()`: nothing here renders or writes media.
    """
    beats, assets = _check_brief(brief)
    folder = str(project or brief.get("project") or "").strip()
    if not folder and out:
        folder = os.path.dirname(os.path.abspath(_apath(out)))
    if not folder:
        raise BlueprintError("a brief must say which project it belongs to ('project')",
                             code="no_project",
                             suggested='"project": "recapstudio/Projects/<name>"')
    project_dir = guard.ensure_dir(_apath(folder))
    slug = str(brief.get("slug") or "").strip() or os.path.basename(project_dir)
    fps = float(brief.get("fps") or DEFAULT_FPS)
    size = [int(v) for v in (brief.get("size") or DEFAULT_SIZE)]
    voice = brief.get("voice") or {}
    voice_asset = str(voice.get("asset") or "voice")
    wav = narration or str(voice.get("narration") or "")
    wav_path = _apath(wav) if wav else os.path.join(project_dir, "audio", "narration.wav")
    timings_path = os.path.splitext(wav_path)[0] + ".json"
    timings = guard.read_json(timings_path, default={}) or {}
    if narration:
        timings = {}                                   # a handed-in file has no recorded timings
    elif not os.path.isfile(wav_path):
        if tts is False:
            raise BlueprintError("no narration at %s" % _rel(wav_path), code="narration_missing",
                                 suggested="pass --narration FILE, or let the tool synthesise one")
        script = "\n".join(str(beat.get("say") or "") for beat in beats)
        timings = narrate(script, wav_path, voice=str(voice.get("voice")
                                                     or "en-US-ChristopherNeural"),
                          rate=str(voice.get("rate") or "+0%"))
    seconds, words, engine = _narration(wav_path, timings)
    plan, how = _boundaries(beats, words, seconds, fps)
    rows = []
    for index, beat in enumerate(beats):
        shot = BY_SHOT[str(beat["shot"])]
        start, frames = plan[index]
        rows.append({
            "id": str(beat["id"]), "shot": shot["id"], "say": str(beat.get("say") or ""),
            "text": str(beat.get("text") or beat.get("say") or ""),
            "scene": str(beat.get("scene") or shot["scene"]),
            "composition": str(beat.get("composition") or shot["composition"]),
            "assets": [str(handle) for handle in (beat.get("uses") or [])],
            "starts_at": start, "frames": frames, "seconds": round(frames / fps, 3),
            "transition_in": str(beat.get("transition_in") or "cut"),
            "note": str(shot["job"]),
        })
    document = {
        "schema": SCHEMA, "kind": KIND,
        "title": str(brief.get("title") or ""), "slug": slug,
        "project": _rel(project_dir), "fps": fps, "size": size,
        "budget": dict(brief.get("budget") or {"mode": "cap", "cap_usd": 0.0}),
        "constraints": {"ai_generated_images": False,
                        "allowed_asset_origins": ["footage", "user_image", "code_graphic",
                                                  "stock_licensed"]},
        "assets": ([{"id": handle, "path": _rel(_apath(row["path"])),
                     "origin": str(row.get("origin") or ""),
                     "license": str(row.get("license") or "")}
                    for handle, row in assets.items()]
                   + [{"id": voice_asset, "path": _rel(wav_path), "origin": "user_audio",
                       "license": str(voice.get("license")
                                      or "synthetic voice (edge-tts), generated for this project")}]),
        "narration": {"asset": voice_asset, "seconds": round(seconds, 3),
                      "words": len(words), "engine": engine, "timing": how,
                      "voice": str(voice.get("voice") or "")},
        "beats": rows,
        "audio": {"music": str(brief.get("music") or ""),
                  "duck": dict(brief.get("duck") or {}),
                  "normalize": dict(brief.get("normalize") or {"lufs": -16.0,
                                                               "true_peak": -1.5})},
        "deliver": dict(brief.get("deliver") or {}),
        "note": "Designed by `cutwright blueprint generate`, compiled by `blueprint compile`. The "
                "beat frames are measured from the narration (%s), not chosen." % how,
    }
    document["deliver"].setdefault("quality", "high")
    document["deliver"].setdefault("container", "mp4")
    document["deliver"].setdefault("output", _rel(os.path.join(project_dir,
                                                               (document["slug"] or "production")
                                                               + ".mp4")))
    path = save(out or os.path.join(project_dir, "blueprint.json"), document)
    return document, path


# ------------------------------------------------------------------ blueprint -> manifest
def _beat_steps(document, work, size, fps):
    """One render_range step per beat. Named after the beat, so a run reads like the story."""
    steps = []
    for beat in document.get("beats") or []:
        row = {"id": "%s_render" % beat["id"], "op": "render_range",
               "inputs": {"scene": beat["scene"]},
               "params": {"composition": beat["composition"], "start": 0,
                          "frames": int(beat["frames"]), "portrait": False, "crf": 18},
               "outputs": {"video": "%s/%s.mp4" % (work, beat["id"])},
               "validation": [{"check": "frame_count", "expect": int(beat["frames"])},
                              {"check": "size", "expect": list(size)},
                              {"check": "constant_fps", "expect": fps}]}
        if beat.get("assets"):
            row["inputs"]["assets"] = dict((handle, "@asset.%s" % handle)
                                           for handle in beat["assets"])
        steps.append(row)
    return steps


def compile_document(blueprint):
    """A ProductionBlueprint -> a manifest document, checked by `manifest.validate` before return.

    The step graph is the engine's, not this module's invention: the pictures are Remotion renders,
    the join is Kinocut's `concat` (2400/2400 frames measured), the voice is attached by the FFmpeg
    `overlay_audio` op (a Remotion render is video-only), the bed is ducked and the loudness levelled
    by Kinocut's own two passes, and the file leaves through `export_h264`. Every executor therefore
    matches `docs/CAPABILITY_MATRIX.md` with no override and no `executor_reason` to justify.
    """
    errors = []
    if not isinstance(blueprint, dict):
        raise BlueprintError("a blueprint is a JSON object", code="bad_blueprint")
    if blueprint.get("kind") != KIND:
        errors.append({"code": "bad_kind", "message": "kind must be %r, got %r"
                       % (KIND, blueprint.get("kind")),
                       "suggested": "write it with `blueprint generate`, not by hand"})
    beats = blueprint.get("beats") or []
    if not isinstance(beats, list) or len(beats) < 2:
        errors.append({"code": "bad_beats", "message": "a blueprint needs at least 2 beats"})
    slug = str(blueprint.get("slug") or "").strip()
    if not slug:
        errors.append({"code": "missing_slug", "message": "a blueprint needs a slug (folder name)"})
    fps = blueprint.get("fps") or DEFAULT_FPS
    size = list(blueprint.get("size") or DEFAULT_SIZE)
    deliver = blueprint.get("deliver") or {}
    if not deliver.get("output"):
        errors.append({"code": "no_output", "message": "deliver.output names the finished file"})
    assets, handles = [], set()
    for row in blueprint.get("assets") or []:
        if not isinstance(row, dict) or not row.get("id") or not row.get("path"):
            errors.append({"code": "bad_asset", "message": "every asset needs an id and a path"})
            continue
        if not os.path.isfile(_apath(row["path"])):
            errors.append({"code": "asset_missing", "message": "asset %r is not on disk: %s"
                           % (row["id"], row["path"]),
                           "suggested": "generate the blueprint again after restoring it"})
        handles.add(str(row["id"]))
        assets.append({"id": str(row["id"]), "path": _rel(_apath(row["path"])),
                       "origin": str(row.get("origin") or ""),
                       "license": str(row.get("license") or "")})
    for beat in (beats if isinstance(beats, list) else []):
        for handle in (beat or {}).get("assets") or []:
            if handle not in handles:
                errors.append({"code": "unknown_handle",
                               "message": "beat %r uses %r, which the blueprint does not declare"
                                          % ((beat or {}).get("id"), handle)})
    if errors:
        raise BlueprintError("the blueprint has %d problem(s)" % len(errors),
                             code="bad_blueprint", suggested=errors[0].get("suggested", ""),
                             errors=errors)
    run_root = "out/runs/%s" % slug
    work = run_root + "/work"
    total = sum(int(beat["frames"]) for beat in beats)
    steps = _beat_steps(blueprint, work, size, fps)
    steps.append({"id": "join", "op": "concat",
                  "inputs": {"sources": ["@%s_render.video" % beat["id"] for beat in beats]},
                  "outputs": {"video": work + "/joined.mp4"},
                  "validation": [{"check": "frame_count", "expect": total},
                                 {"check": "decodes_clean"}]})
    narration = str((blueprint.get("narration") or {}).get("asset") or "")
    if not narration:
        raise BlueprintError("the blueprint has no narration", code="bad_blueprint",
                             suggested="narration.asset names the voice track",
                             errors=[{"code": "no_narration",
                                      "message": "narration.asset is empty"}])
    steps.append({"id": "voice_over", "op": "overlay_audio",
                  "inputs": {"video": "@join.video", "audio": "@asset.%s" % narration},
                  "params": {"duration": round(total / float(fps), 6), "bitrate": "192k"},
                  "outputs": {"video": work + "/voiced.mp4"},
                  "validation": [{"check": "frame_count", "expect": total},
                                 {"check": "has_audio", "expect": True}]})
    audio = blueprint.get("audio") or {}
    music = str(audio.get("music") or "")
    last = "voice_over"
    if music:
        steps.append({"id": "duck", "op": "duck_audio",
                      "inputs": {"src": "@%s.video" % last, "music": "@asset.%s" % music},
                      "params": dict(audio.get("duck") or {}),
                      "outputs": {"video": work + "/ducked.mp4"},
                      "validation": [{"check": "frame_count", "expect": total},
                                     {"check": "has_audio", "expect": True}]})
        last = "duck"
    steps.append({"id": "level", "op": "normalize_audio", "inputs": {"src": "@%s.video" % last},
                  "params": dict(audio.get("normalize") or {}),
                  "outputs": {"video": work + "/leveled.mp4"},
                  "validation": [{"check": "frame_count", "expect": total},
                                 {"check": "has_audio", "expect": True}]})
    steps.append({"id": "export", "op": "export_h264", "inputs": {"src": "@level.video"},
                  "params": {"quality": deliver.get("quality") or "high",
                             "container": deliver.get("container") or "mp4"},
                  "outputs": {"video": deliver["output"]},
                  "validation": [{"check": "frame_count", "expect": total},
                                 {"check": "decodes_clean"},
                                 {"check": "has_audio", "expect": True}]})
    document = {"schema": engine_manifest.SCHEMA, "run_id": slug,
                "pipeline": str(blueprint.get("title") or slug), "fps": fps, "size": list(size),
                "budget": dict(blueprint.get("budget") or {"mode": "cap", "cap_usd": 0.0}),
                "constraints": dict(blueprint.get("constraints") or {}),
                "assets": assets, "gates": [], "steps": steps,
                "note": "Compiled from the project's blueprint.json by `cutwright blueprint "
                        "compile`: the beats, assets and checks are the blueprint's, the ops and "
                        "executors are ops.py's (docs/CAPABILITY_MATRIX.md)."}
    verdict = engine_manifest.validate(document, strict_files=False)
    if not verdict.get("ok"):
        raise BlueprintError("compiled to an invalid manifest (%d error(s))"
                             % len(verdict.get("errors") or []), code="invalid_manifest",
                             suggested="the first error names the step and the field",
                             errors=verdict.get("errors") or [])
    return document


def compile(blueprint, out=""):
    """Read a blueprint (path or document), write `manifest.json`, return the summary dict."""
    document = blueprint if isinstance(blueprint, dict) else load(blueprint)
    plan = compile_document(document)
    path = save(out or os.path.join(_apath(document.get("project") or "."), "manifest.json"), plan)
    return {"ok": True, "manifest": _rel(path), "run_id": plan["run_id"],
            "steps": [row["id"] for row in plan["steps"]],
            "frames": sum(int(beat["frames"]) for beat in document["beats"]),
            "seconds": round(sum(float(beat["seconds"]) for beat in document["beats"]), 3),
            "beats": [{"id": beat["id"], "shot": beat["shot"], "frames": beat["frames"],
                       "starts_at": beat["starts_at"], "say": beat.get("say", "")}
                      for beat in document["beats"]],
            "output": document["deliver"]["output"]}




