"""Post-render media validation: prove the file a step wrote is the file the plan asked for.

Pre-render checks belong to `manifest.py` (references, params, budget, asset-origin policy). This
module only ever opens a file an executor has ALREADY written and measures it. Same rule as
`docs/CAPABILITY_MATRIX.md`: a number from a decode, never from a container header a muxer could
have written optimistically -- ffprobe's `nb_frames` is a claim, `nb_read_frames` is a measurement.

A step declares its checks in the manifest; `manifest._execute` calls `run_checks()` after the step
succeeds, and a failing check fails the step deterministically (never retried, `validation_failed`).
One implementation per check, so the acceptance commands and the tests measure the same thing.

Three entry points:

  run_checks(step, result)   the checks one step declared, filled in
  slideshow_risk(path)       is this "video" actually a sequence of stills?
  provenance(document)       every asset: origin policy, existence, digest
"""
import os
import subprocess

from cutwright import guard, probe
from cutwright.engine import checkpoint

DECODE_TIMEOUT = 600        # a 60 s 1080p decode took 54 s through Kinocut's export (matrix row 11)
STATIC_DIFF = 1.0           # mean per-pixel change below this (0-255) = the picture did not move
SLIDESHOW_HIGH = 0.85       # this share of static frame pairs is a slideshow, not an edit
SLIDESHOW_MEDIUM = 0.60
RISK_W, RISK_H = 64, 36     # what slideshow_risk decodes to: cheap, and real motion still shows
FPS_SLACK = 0.01            # a frame rate is not exact in a container; 0.01 is one frame in 100 s
JITTER = 0.001             # 1 ms: a constant-rate file's frame intervals vary by less than this
TIME_SLACK = 1.5            # a frame timestamp may drift this many frame intervals and still be CFR


# ------------------------------------------------------------------ measuring one file
def frame_count(path):
    """Video frames actually decoded. `-count_frames` decodes, so this is not a header claim."""
    data = probe.ffprobe_json(path, ["-count_frames", "-select_streams", "v:0",
                                     "-show_entries", "stream=nb_read_frames"])
    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError("no video stream in this file")
    return int(streams[0].get("nb_read_frames") or 0)


def frame_times(path):
    """Presentation timestamp of every video frame, in seconds, in decode order."""
    data = probe.ffprobe_json(path, ["-select_streams", "v:0", "-show_frames",
                                     "-show_entries", "frame=best_effort_timestamp_time"])
    out = []
    for row in data.get("frames") or []:
        value = row.get("best_effort_timestamp_time")
        if value in (None, "N/A", ""):
            continue
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            continue
    return out


def decodes_clean(path):
    """Decode the whole file to nowhere: (ok, first error line). A clean mux only is not enough."""
    result = probe.run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"],
                       timeout=DECODE_TIMEOUT)
    errors = (result.stderr or "").strip()
    ok = result.returncode == 0 and not errors
    return ok, "" if ok else (errors[:300] or "ffmpeg exit %d" % result.returncode)


def _raw_gray(path, width=RISK_W, height=RISK_H, timeout=DECODE_TIMEOUT):
    """Decode to tiny raw grayscale frames (bytes, not text): the cheapest honest motion probe."""
    argv = ["ffmpeg", "-v", "error", "-i", path, "-an", "-sn",
            "-vf", "scale=%d:%d:flags=bilinear,format=gray" % (width, height),
            "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          stdin=subprocess.DEVNULL, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or b"").decode("utf-8", "replace").strip()[:300]
                           or "ffmpeg exit %d" % proc.returncode)
    return proc.stdout


# ------------------------------------------------------------------ the checks themselves
# Each returns (measured, ok, message) and never raises: a broken file must fail the check,
# not abort the run that is trying to report it.
def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check_frame_count(path, expect):
    got = frame_count(path)
    want = _as_int(expect)
    if want is None:
        return got, True, "no expected count given; measured only"
    return got, got == want, "" if got == want else "expected %d frames, decoded %d" % (want, got)


def _check_size(path, expect):
    info = probe.media_info(path)
    got = [info["width"], info["height"]]
    want = list(expect) if isinstance(expect, (list, tuple)) else None
    if not want or len(want) != 2:
        return got, True, "no expected size given; measured only"
    want = [_as_int(value) for value in want]
    return got, got == want, "" if got == want else "expected %s, got %s" % (want, got)


def _check_fps(path, expect):
    got = probe.media_info(path)["fps"]
    want = _as_number(expect)
    if want is None:
        return got, True, "no expected rate given; measured only"
    ok = abs(float(got or 0.0) - want) <= FPS_SLACK
    return got, ok, "" if ok else "expected %s fps, container says %s" % (want, got)


def _check_constant_fps(path, expect):
    """Two things at once: every interval equals the last, AND the rate is the one expected.

    Checking only uniformity would pass a 30 fps file where 24 was asked for -- which is exactly the
    silent re-time `kino merge` performs on heterogeneous inputs (measured 2026-10-30).
    """
    times = frame_times(path)
    if len(times) < 2:
        return len(times), False, "need at least 2 frames to measure timing, found %d" % len(times)
    steps = [round(times[i + 1] - times[i], 6) for i in range(len(times) - 1)]
    interval = sum(steps) / float(len(steps))
    if interval <= 0:
        return len(times), False, "frames do not advance in time (interval %.6fs)" % interval
    fps = 1.0 / interval
    jitter = max(abs(step - interval) for step in steps)
    want = _as_number(expect)
    measured = {"frames": len(times), "interval": round(interval, 6), "fps": round(fps, 3),
                "jitter": round(jitter, 6)}
    if jitter > JITTER:
        return measured, False, ("frame timing is not constant: intervals vary by up to %.6fs"
                                 % jitter)
    if want is not None and abs(fps - want) > FPS_SLACK:
        return measured, False, "expected %.3f fps, the frame timing says %.3f" % (want, fps)
    return measured, True, ""


def _check_decodes_clean(path, expect):
    ok, message = decodes_clean(path)
    return ("clean" if ok else "errors"), ok, message


def _check_has_audio(path, expect):
    want = True if expect is None else bool(expect)
    streams = probe.media_info(path)["audio"]
    got = bool(streams)
    return got, got == want, "" if got == want else (
        "expected %s audio, found %s" % ("an" if want else "no",
                                         "%d stream(s)" % len(streams) if got else "none"))


def _check_contiguous(path, expect):
    """No repeated and no missing frames: timestamps strictly increase by ~1 frame."""
    times = frame_times(path)
    if len(times) < 2:
        return len(times), False, "need at least 2 frames, found %d" % len(times)
    interval = (times[-1] - times[0]) / float(len(times) - 1) or 0.0
    repeats = sum(1 for i in range(len(times) - 1) if times[i + 1] <= times[i])
    gaps = sum(1 for i in range(len(times) - 1)
               if interval and (times[i + 1] - times[i]) > TIME_SLACK * interval)
    ok = not repeats and not gaps
    return {"frames": len(times), "repeated": repeats, "gaps": gaps}, ok, "" if ok else (
        "%d repeated and %d missing frame(s) in the timestamps" % (repeats, gaps))


CHECKS = {
    "frame_count": (_check_frame_count, "decoded video frames == expect"),
    "size": (_check_size, "width/height == expect [w, h]"),
    "fps": (_check_fps, "container frame rate == expect"),
    "constant_fps": (_check_constant_fps, "every frame is one interval from the last"),
    "decodes_clean": (_check_decodes_clean, "the whole file decodes with no ffmpeg error"),
    "has_audio": (_check_has_audio, "an audio stream is present (expect: true/false)"),
    "frame_ids_contiguous": (_check_contiguous, "no repeated or missing frame timestamps"),
}


# ------------------------------------------------------------------ what a step declared
def _measured_file(step):
    """The file a step's checks measure: its FIRST output (every op writes exactly one)."""
    outputs = getattr(step, "outputs", None) or {}
    names = list(getattr(getattr(step, "spec", None), "outputs", ()) or [])
    if names and names[0] in outputs:
        return outputs[names[0]]
    for value in outputs.values():
        if isinstance(value, str):
            return value
    return ""


def run_checks(step, result=None):
    """Fill in every check a step declared. Never raises; a broken file becomes a failed check.

    An unknown check name fails loudly instead of passing silently: a manifest that asks for a
    check the engine does not have would otherwise look validated and never be measured.
    """
    rows, target = [], _measured_file(step)
    for declared in list(getattr(step, "validation", None) or []):
        name = str((declared or {}).get("check") or "")
        row = {"check": name, "expect": (declared or {}).get("expect"), "measured": None,
               "status": "fail", "message": ""}
        if name not in CHECKS:
            row["message"] = "unknown check -> one of: %s" % ", ".join(sorted(CHECKS))
        elif not target or not os.path.isfile(target):
            row["message"] = "no output file to measure: %s" % guard.rel(target or "(none)")
        else:
            try:
                measured, ok, message = CHECKS[name][0](target, row["expect"])
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
                # A corrupt or truncated render must fail this check, not abort the run that is
                # trying to record what happened to it.
                measured, ok, message = None, False, "%s: %s" % (type(exc).__name__, exc)
            row.update(measured=measured, status="pass" if ok else "fail", message=message)
        rows.append(row)
    return rows


def failures(rows):
    """The rows that failed, for a message that names each check."""
    return [row for row in (rows or []) if row.get("status") == "fail"]


# ------------------------------------------------------------------ slideshow detection
def slideshow_risk(path):
    """How much of this clip does NOT move -- the honest test for 'stills, not an edit'.

    Decodes every frame to 64x36 gray and measures the mean absolute change between consecutive
    frames. A slideshow has near-zero change on almost every pair; a real edit changes every frame,
    even in a slow pan. `score` is the share of static pairs, so 1.0 means nothing moves at all.
    """
    row = {"path": guard.rel(str(path or "")), "score": 0.0, "frames": 0, "pairs": 0,
           "mean_diff": 0.0, "verdict": "unknown", "detail": ""}
    if not path or not os.path.isfile(str(path)):
        row["detail"] = "no such file"
        return row
    try:
        data = _raw_gray(str(path))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        row["detail"] = "%s: %s" % (type(exc).__name__, exc)
        return row
    size = RISK_W * RISK_H
    frames = len(data) // size
    row["frames"] = frames
    if frames < 2:
        row["detail"] = "fewer than 2 frames: no motion to measure"
        return row
    diffs = []
    for index in range(1, frames):
        before = data[(index - 1) * size:index * size]
        after = data[index * size:(index + 1) * size]
        diffs.append(sum(abs(a - b) for a, b in zip(before, after)) / float(size))
    static = sum(1 for value in diffs if value < STATIC_DIFF)
    row["pairs"] = len(diffs)
    row["score"] = round(static / float(len(diffs)), 3)
    row["mean_diff"] = round(sum(diffs) / float(len(diffs)), 3)
    row["static_pairs"] = static
    if row["score"] >= SLIDESHOW_HIGH:
        row["verdict"] = "high"
        row["detail"] = "%d of %d frame pairs are identical: this is a slideshow" % (
            static, len(diffs))
    elif row["score"] >= SLIDESHOW_MEDIUM:
        row["verdict"] = "medium"
        row["detail"] = "%d of %d frame pairs are identical: check for long stills" % (
            static, len(diffs))
    else:
        row["verdict"] = "low"
    return row


# ------------------------------------------------------------------ asset provenance
def _manifest_module():
    """`manifest` imported lazily: manifest.py imports this module, so a top-level import cycles."""
    from cutwright.engine import manifest
    return manifest


def provenance(document):
    """One row per declared asset: origin, whether the policy allows it, existence, digest.

    Reports the rule; it does not invent one. The allowed origins and the visual/audio split come
    from `manifest` (which enforces them when a plan is derived), so `validate` can only ever AGREE
    with the plan and never widen it. Digests use `checkpoint.digest_file`, the same identity a
    resume compares against.
    """
    manifest = _manifest_module()
    constraints = (document or {}).get("constraints") or {}
    allowed = tuple(constraints.get("allowed_asset_origins") or manifest.ALLOWED_ORIGINS)
    rows, ok = [], True
    for entry in (document or {}).get("assets") or []:
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("path") or "")
        full = manifest.resolve_path(raw) if raw else ""
        origin = str(entry.get("origin") or "")
        visual = bool(raw) and os.path.splitext(raw)[1].lower() not in manifest.AUDIO_ONLY_EXTS
        exists = bool(full) and os.path.isfile(full)
        problems = []
        if not origin:
            problems.append("no origin declared")
        elif visual and origin not in allowed:
            problems.append("origin %r is not allowed for a visual asset" % origin)
        if not exists:
            problems.append("file is missing: %s" % guard.rel(full or "(no path)"))
        row = {"id": str(entry.get("id") or ""), "origin": origin,
               "license": str(entry.get("license") or ""),
               "path": guard.rel(full) if full else "", "visual": visual, "exists": exists,
               "ok": not problems, "problems": problems, "digest": None}
        if exists:
            try:
                row["digest"] = checkpoint.digest_file(full)
            except OSError as exc:
                row["digest"] = {"error": str(exc)}
        ok = ok and row["ok"]
        rows.append(row)
    return {"ok": ok, "allowed_origins": list(allowed), "assets": rows,
            "ai_generated_images": bool(constraints.get("ai_generated_images")),
            "count": len(rows)}




