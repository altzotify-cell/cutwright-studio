"""FFmpeg executor: the ops the capability matrix does NOT give Kinocut.

Matrix rows that land here (all measured in M2, `docs/CAPABILITY_MATRIX.md`):

  * `fit_to_frames` - row 2: no Kinocut op takes "exactly N frames" (`speed` was a no-op, `trim`
    truncates). `fps` + `setsar=1` + `tpad=stop_mode=clone` + `-frames:v` was exact at 53/97/241
    frames (`m2_fit.json`).
  * `crop_to_size`  - row 4: neither `kino resize` nor the current `fit_graph` has a crop branch
    (both letterbox); `scale=increase,crop=W:H,setsar=1` fills 1080x1920 (`m2_resize.json`).
  * `overlay_audio` - row 9: `composite-layers` returns video only, so the audio is re-attached
    from the source with `-map 0:v -map 1:a -c:v copy` (`m2_composite.json`).

Same contract as the Kinocut executor (`executors/__init__.py`): an `ExecResult`, or a typed
`ExecutorError` carrying a code, a suggested fix and `transient`. Argument lists only (never a
shell string), stdin is DEVNULL, a timeout kills the process tree, and every output path passes
`guard.assert_writable()` BEFORE ffmpeg starts.

The video passes are video-only (`-an`) on purpose: the matrix says a timeline's audio is ONE
continuous track (M2 gap 3, per-join drift 13-26 ms), so audio is attached in a single later pass.
"""
import os
import shutil
import subprocess
import time

from cutwright import guard
from cutwright.engine.executors import (ExecResult, ExecutorError, ExecutorTimeout,
                                        ExecutorUnavailable, decode_bytes, kill_tree)

EXECUTOR = "ffmpeg"
FFMPEG_ENV = "CUTWRIGHT_FFMPEG"    # override for tests / a bundled build
DEFAULT_TIMEOUT = 600.0           # a 60 s 1080p export took 54 s on Kinocut (matrix row 11)
KILL_TIMEOUT = 20
_VERSION = {}


def ffmpeg_exe():
    """Absolute path (or PATH name) of the ffmpeg binary this executor calls."""
    return os.environ.get(FFMPEG_ENV) or shutil.which("ffmpeg") or "ffmpeg"


def available():
    return shutil.which(ffmpeg_exe()) is not None


def version():
    """Version token from `ffmpeg -version` (e.g. '7.1-full_build-...'), cached. '' if absent."""
    if "v" not in _VERSION:
        text = ""
        if available():
            try:
                proc = subprocess.run([ffmpeg_exe(), "-version"], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                      timeout=30)
                lines = decode_bytes(proc.stdout).splitlines()
                parts = lines[0].split() if lines else []
                text = parts[2] if len(parts) > 2 else ""
            except (OSError, subprocess.TimeoutExpired):
                text = ""
        _VERSION["v"] = text
    return _VERSION["v"]


def build_argv(args, overwrite=False, exe=None):
    """argv for one call. `-nostdin` matters: ffmpeg otherwise reads the parent's stdin.

    `-n` (not `-y`) unless the caller asked for overwrite: a second run may not silently replace
    a render, the same rule the Kinocut adapter follows (findings 7.7).
    """
    argv = [exe or ffmpeg_exe(), "-nostdin", "-y" if overwrite else "-n", "-loglevel", "error"]
    return argv + [str(a) for a in args]


def invoke(op, args, output=None, inputs=(), overwrite=False, timeout=DEFAULT_TIMEOUT, exe=None):
    """Run one ffmpeg command. Returns ExecResult, or raises a typed ExecutorError.

    Pre-flight happens in Python, not inside ffmpeg: a missing input and an existing output
    without `overwrite` are typed errors before a single frame is decoded.
    """
    argv = build_argv(args, overwrite=overwrite, exe=exe)
    if not available():
        raise ExecutorUnavailable(EXECUTOR, op, "ffmpeg is not on PATH",
                                  code="not_installed", argv=argv,
                                  suggested="install ffmpeg 7.x (Gyan build, assumption A5) or "
                                            "set %s to a full path" % FFMPEG_ENV)
    for path in inputs:
        if not os.path.exists(path):
            raise ExecutorError(EXECUTOR, op, "input does not exist: %s" % guard.rel(path),
                                code="input_missing", argv=argv,
                                suggested="check the path, earlier or run the step that should "
                                          "have produced it")
    if output and os.path.exists(output) and not overwrite:
        raise ExecutorError(EXECUTOR, op,
                            "output already exists: %s" % guard.rel(output),
                            code="output_exists", argv=argv,
                            suggested="pass overwrite=True to replace it deliberately")
    started = time.time()
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL)
    except OSError as exc:
        raise ExecutorUnavailable(EXECUTOR, op, "cannot start %s: %s" % (guard.rel(argv[0]), exc),
                                  code="not_installed", argv=argv,
                                  suggested="check that the ffmpeg binary is executable")
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=KILL_TIMEOUT)
        except subprocess.TimeoutExpired:
            out, err = b"", b""
        raise ExecutorTimeout(EXECUTOR, op,
                              "no result after %ss; the process tree was killed" % timeout,
                              code="timeout", argv=argv, stdout=decode_bytes(out),
                              stderr=decode_bytes(err),
                              suggested="raise this step's timeout, or split the range into "
                                        "smaller steps", transient=True)
    stdout, stderr = decode_bytes(out), decode_bytes(err)
    if proc.returncode != 0:
        raise error_from(op, argv, proc.returncode, stdout, stderr)
    if output and not os.path.exists(output):
        raise ExecutorError(EXECUTOR, op, "ffmpeg exited 0 but wrote no output",
                            code="output_missing", argv=argv, returncode=proc.returncode,
                            stdout=stdout, stderr=stderr,
                            suggested="check the filter graph and the output path/extension")
    return ExecResult(executor=EXECUTOR, op=op, argv=argv, returncode=proc.returncode,
                      seconds=round(time.time() - started, 3), stdout=stdout, stderr=stderr,
                      output_path=os.path.abspath(output) if output else "",
                      payload={"binary": os.path.basename(argv[0]),
                               "video_only": "-an" in argv})


_CODES = (("no such file or directory", "input_missing"),
          ("already exists", "output_exists"),
          ("matches no streams", "no_audio_stream"),
          ("unknown encoder", "encoder_missing"),
          ("error initializing", "bad_filter"),
          ("error opening filters", "bad_filter"),
          ("no such filter", "bad_filter"),
          ("invalid argument", "bad_filter"))

_SUGGESTIONS = {
    "input_missing": "check the input path, or run the step that should have produced it",
    "output_exists": "pass overwrite=True to replace the existing file deliberately",
    "no_audio_stream": "the audio input has no audio stream: probe it first (probe.media_info)",
    "encoder_missing": "this ffmpeg build lacks the encoder; check `ffmpeg -encoders`",
    "bad_filter": "check the filter graph and its values (yuv420p needs even width and height)",
}


def error_from(op, argv, returncode, stdout, stderr):
    """ffmpeg's stderr -> ExecutorError with a code and the last real error line. Deterministic."""
    text = stderr or ""
    lowered = text.lower()
    code = "ffmpeg_failed"
    for needle, candidate in _CODES:
        if needle in lowered:
            code = candidate
            break
    message = _last_error(text) or "ffmpeg exited %s with no message" % returncode
    return ExecutorError(EXECUTOR, op, message, code=code, argv=argv, returncode=returncode,
                         stdout=stdout, stderr=text,
                         suggested=_SUGGESTIONS.get(code, "read this step's stderr"))


def _last_error(text):
    """Last non-empty stderr line without the banner/configuration noise."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    for line in reversed(lines):
        if not line.lower().startswith(("ffmpeg version", "built with", "configuration:")):
            return line[:400]
    return ""


# ------------------------------------------------------ typed ops (executor: ffmpeg, per the matrix)
def _out(path):
    """The write guard, applied BEFORE ffmpeg starts: never write into an original folder."""
    return guard.assert_writable(path)


def _count(op, name, value, minimum=1):
    """A whole number >= minimum, or a deterministic typed error naming the parameter."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ExecutorError(EXECUTOR, op, "%s must be a number, got %r" % (name, value),
                            code="bad_param",
                            suggested="pass a whole number, e.g. %s=%d" % (name, minimum))
    if number != int(number):
        raise ExecutorError(EXECUTOR, op, "%s must be a whole count, got %r" % (name, value),
                            code="bad_param",
                            suggested="round it: %s=%d" % (name, round(number)))
    if int(number) < minimum:
        raise ExecutorError(EXECUTOR, op, "%s must be >= %d, got %r" % (name, minimum, value),
                            code="bad_param", suggested="use at least %d" % minimum)
    return int(number)


def _rate(op, name, value, minimum=0.001):
    """A positive number (fps, seconds), or a typed error naming the parameter."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ExecutorError(EXECUTOR, op, "%s must be a number, got %r" % (name, value),
                            code="bad_param", suggested="e.g. %s=24" % name)
    if number < minimum:
        raise ExecutorError(EXECUTOR, op, "%s must be >= %s, got %r" % (name, minimum, value),
                            code="bad_param", suggested="e.g. %s=24" % name)
    return number


def fit_to_frames(input_path, output, frames, fps=24, width=None, height=None, fill="pad",
                  crf=18, overwrite=False, timeout=DEFAULT_TIMEOUT):
    """Exactly `frames` frames at `fps`, fitted into width x height without stretching.

    Matrix row 2 (`m2_fit.json`): `fps` + `setsar=1` + `tpad=stop_mode=clone`, then `-frames:v`,
    was frame-exact at 53/97/241 on a 120-frame source - the one thing no Kinocut op can do
    (`speed` was a no-op on that input, `trim` just truncates). Cloning the last frame is what
    makes a short clip reach a target length instead of failing.

    Video only: the timeline's audio is one continuous track (M2 gap 3). `fill="pad"` is the only
    fill implemented here - "blur" is the existing `recap.fit_graph` (moves in M4, no second
    implementation before then) and "crop" is `crop_to_size`.
    """
    op = "fit_to_frames"
    count = _count(op, "frames", frames)
    rate = _rate(op, "fps", fps)
    if fill != "pad":
        raise ExecutorError(EXECUTOR, op, "fill=%r is not implemented in this executor" % (fill,),
                            code="unsupported_fill",
                            suggested="use fill=pad, or reframe_crop for a crop pass")
    graph = []
    if width is not None and height is not None:
        size = (_count(op, "width", width, 2), _count(op, "height", height, 2))
        if size[0] % 2 or size[1] % 2:
            raise ExecutorError(EXECUTOR, op,
                                "width and height must be even for yuv420p, got %dx%d" % size,
                                code="bad_param", suggested="e.g. width=1920, height=1080")
        graph.append("scale=%d:%d:force_original_aspect_ratio=decrease" % size)
        graph.append("pad=%d:%d:(ow-iw)/2:(oh-ih)/2" % size)
    graph += ["setsar=1", "fps=%g" % rate,
              "tpad=stop_mode=clone:stop_duration=%.3f" % (count / rate + 1.0)]
    target = _out(output)
    args = ["-i", input_path, "-vf", ",".join(graph), "-frames:v", str(count),
            "-c:v", "libx264", "-crf", str(_count(op, "crf", crf, 0)),
            "-pix_fmt", "yuv420p", "-an", target]
    return invoke(op, args, output=target, inputs=[input_path], overwrite=overwrite,
                  timeout=timeout)


def crop_to_size(input_path, output, width, height, frames=None, fps=None, crf=18,
                 overwrite=False, timeout=DEFAULT_TIMEOUT):
    """Centre crop that FILLS width x height (matrix row 4, `m2_resize.json`).

    `scale=increase` then `crop`: the content box fills the frame (1080x1920 measured, no bars),
    which is a true 9:16 reframe. Kinocut `resize -a 9:16` only letterboxes, and the current
    `fit_graph` has no crop branch at all - it silently pads (same matrix row).
    """
    op = "crop_to_size"
    size = (_count(op, "width", width, 2), _count(op, "height", height, 2))
    parts = ["scale=%d:%d:force_original_aspect_ratio=increase" % size,
             "crop=%d:%d" % size, "setsar=1"]
    if fps is not None:
        parts.append("fps=%g" % _rate(op, "fps", fps))
    target = _out(output)
    args = ["-i", input_path, "-vf", ",".join(parts)]
    if frames is not None:
        args += ["-frames:v", str(_count(op, "frames", frames))]
    args += ["-c:v", "libx264", "-crf", str(_count(op, "crf", crf, 0)),
             "-pix_fmt", "yuv420p", "-an", target]
    return invoke(op, args, output=target, inputs=[input_path], overwrite=overwrite,
                  timeout=timeout)


def overlay_audio(video, audio, output, duration=None, delay=None, bitrate="192k",
                  overwrite=False, timeout=DEFAULT_TIMEOUT):
    """Re-attach an audio track to a video-only file (matrix row 9, `m2_composite.json`).

    `composite-layers` measured `has_audio: false`, so its output gets this pass. Video is
    stream-copied (`-c:v copy`): no re-encode, no second generation of compression, no frame
    drift. `delay` shifts the audio in seconds via `adelay` (all channels).

    Without `duration` the mux uses `-shortest`, which cuts the video to the shorter stream; that
    is reported in `warnings`, because it can silently shorten a render. Pass `duration`
    whenever the intended length is known.
    """
    op = "overlay_audio"
    target = _out(output)
    args = ["-i", video, "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", str(bitrate)]
    warnings = []
    if delay is not None:
        args += ["-af", "adelay=%d:all=1" % int(_rate(op, "delay", delay, 0.0) * 1000)]
    if duration is not None:
        args += ["-t", "%.3f" % _rate(op, "duration", duration)]
    else:
        args.append("-shortest")
        warnings.append("no duration given: -shortest cuts the video to the shorter stream")
    args.append(target)
    res = invoke(op, args, output=target, inputs=[video, audio], overwrite=overwrite,
                 timeout=timeout)
    res.warnings.extend(warnings)
    return res



