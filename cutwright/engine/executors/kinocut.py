"""Kinocut executor: the subprocess adapter to `.venvs\\kinocut\\Scripts\\kino.exe`.

Every fact used here was measured in M1/M2 (`docs/KINOCUT_FINDINGS.md`,
`docs/CAPABILITY_MATRIX.md`), never guessed. The ones that bite:

  * global flags (`--format json`, `--overwrite`) MUST precede the subcommand (findings 7.2);
  * Kinocut writes UTF-8 into a cp1252 console, so capture bytes and decode in-process;
    never re-print its box-drawing panels (7.4);
  * an existing output is refused with code `output_exists` unless `--overwrite` is passed
    (7.7) -> overwrite is an explicit caller decision, never a default;
  * bare `kino` is an MCP server (7.9) -> a subcommand is always required;
  * `composite-layers` resolves paths against the spec directory (7.10) and drops audio, so it
    is called only through `composite_layers()` with absolute paths;
  * workflow sources must be relative and inside the workspace, run with cwd = spec dir (11);
  * each call costs ~1.3-1.8 s of start-up, so one call must do as much as possible.

Stdlib only; `import kinocut` is never used (assumption A2). Only the ops the capability matrix
assigns to Kinocut are wrapped here -- everything else belongs in `executors/ffmpeg.py`.
Which wrappers the tests actually exercise on real media is recorded in `LOG.md` (M3).
"""
import json
import os
import subprocess
import time

from cutwright import guard
from cutwright.engine.executors import (ExecResult, ExecutorError, ExecutorTimeout,
                                        ExecutorUnavailable, decode_bytes, first_json,
                                        kill_tree)

EXECUTOR = "kinocut"
KINO_REL = os.path.join(".venvs", "kinocut", "Scripts", "kino.exe")
KINO_ENV = "CUTWRIGHT_KINO"        # override for tests / another venv
GLOBAL_FLAGS = ("--format", "json")
DEFAULT_TIMEOUT = 240.0            # M2: 20-clip merge took 7.9 s, export 54 s -> ceiling, not target
KILL_TIMEOUT = 20


def kino_exe():
    """Absolute path of the Kinocut CLI this adapter will call."""
    return os.environ.get(KINO_ENV) or os.path.join(guard.ROOT, KINO_REL)


def available():
    return os.path.exists(kino_exe())


def build_argv(op, args=(), overwrite=False, exe=None):
    """argv list for one call. Global flags first (findings 7.2); no shell string anywhere."""
    argv = [exe or kino_exe()]
    argv += list(GLOBAL_FLAGS)
    if overwrite:
        argv.append("--overwrite")
    argv.append(op)
    argv += [str(a) for a in args]
    return argv


def _kill_tree(proc):
    """Kept as the name `invoke` uses; the implementation is shared with the ffmpeg executor."""
    kill_tree(proc)



def invoke(op, args=(), overwrite=False, timeout=DEFAULT_TIMEOUT, cwd=None, exe=None):
    """Run one Kinocut command. Returns ExecResult, or raises a typed ExecutorError.

    stdin is DEVNULL (Kinocut otherwise waits on an inherited pipe) and a timeout kills the whole
    process tree, so one bad render cannot hang a run.
    """
    argv = build_argv(op, args, overwrite=overwrite, exe=exe)
    if not os.path.exists(argv[0]):
        raise ExecutorUnavailable(
            EXECUTOR, op, "Kinocut is not installed: %s is missing" % guard.rel(argv[0]),
            code="not_installed", argv=argv,
            suggested="create .venvs\\kinocut and pip install kinocut==1.16.4 "
                      "(docs/KINOCUT_FINDINGS.md section 1)")
    started = time.time()
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, cwd=cwd)
    except OSError as exc:
        raise ExecutorUnavailable(
            EXECUTOR, op, "cannot start %s: %s" % (guard.rel(argv[0]), exc),
            code="not_installed", argv=argv,
            suggested="check that the venv is complete (KINOCUT_FINDINGS 7.1)")
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=KILL_TIMEOUT)
        except subprocess.TimeoutExpired:
            out, err = b"", b""
        raise ExecutorTimeout(
            EXECUTOR, op, "no result after %ss; the process tree was killed" % timeout,
            code="timeout", argv=argv, stdout=decode_bytes(out), stderr=decode_bytes(err),
            suggested="raise this step's timeout, or run it as a background step",
            transient=True)
    return interpret(op, argv, proc.returncode, out, err,
                     seconds=round(time.time() - started, 3))


def interpret(op, argv, returncode, stdout, stderr, seconds=0.0):
    """Exit code + captured bytes -> ExecResult, or a typed ExecutorError. Pure, no I/O.

    Kinocut signals failure twice (exit code, and `success: false`), so both are checked and the
    error payload is what names the failure: `code` is Kinocut's own code when it gave one.
    """
    out = decode_bytes(stdout)
    err = decode_bytes(stderr)
    payload = first_json(out) or first_json(err)
    if not isinstance(payload, dict):
        payload = {}
    if returncode != 0 or payload.get("success") is False:
        raise error_from(op, argv, returncode, out, err, payload)
    return ExecResult(
        executor=EXECUTOR, op=op, argv=argv, returncode=returncode, seconds=seconds,
        stdout=out, stderr=err,
        output_path=_text(_first(payload, "output_path", "output")),
        receipt_path=_text(_first(payload, "receipt_path", "receipt")),
        warnings=list(payload.get("warnings") or []),
        payload=payload)


def error_from(op, argv, returncode, stdout, stderr, payload):
    """Kinocut's error JSON (or a bare exit code) -> ExecutorError with a suggested fix."""
    info = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(info, dict):
        info = {}
    fix = info.get("suggested_action")
    if isinstance(fix, dict):
        fix = fix.get("description") or fix.get("auto_fix") or ""
    suggested = fix if isinstance(fix, str) else ""
    code = info.get("code") or "exit_%s" % returncode
    message = info.get("message") or ""
    if not message:
        lines = [ln.strip() for ln in (stderr or "").splitlines() if ln.strip()]
        message = lines[-1][:400] if lines else "no message from Kinocut"
    if not suggested:
        if code == "output_exists":
            suggested = "pass overwrite=True to replace the existing file deliberately"
        elif returncode == 2:
            suggested = "argument error: global flags must precede the subcommand (KINOCUT_FINDINGS 7.2)"
    return ExecutorError(EXECUTOR, op, message, code=code, argv=argv, returncode=returncode,
                         suggested=suggested, error_type=info.get("type") or "",
                         stdout=stdout, stderr=stderr, transient=False)


def _first(payload, *keys):
    for key in keys:
        value = payload.get(key)
        if value:
            return value
    return ""


def _text(value):
    return value if isinstance(value, str) else ""


# ---------------------------------------------- typed ops (executor: kinocut per the matrix)
def _out(path):
    """The write guard, applied BEFORE Kinocut starts: never write into an original folder."""
    return guard.assert_writable(path)


def _opt(flag, value):
    """Optional flag -> [] when unset. Numbers are stringified, never formatted by hand."""
    return [] if value is None else [flag, str(value)]


def trim(input_path, output, start=None, duration=None, end=None, accurate=False,
         overwrite=False, timeout=DEFAULT_TIMEOUT):
    """Frame-exact cut. Matrix row 1: exact frame ids at starts 0/1/37/119 (2.1-3.5 s/call)."""
    args = [input_path] + _opt("-s", start) + _opt("-d", duration) + _opt("-e", end)
    if accurate:
        args.append("--accurate")
    args += ["-o", _out(output)]
    return invoke("trim", args, overwrite=overwrite, timeout=timeout)


def merge(inputs, output, transition=None, transition_duration=None, overwrite=False,
          timeout=DEFAULT_TIMEOUT):
    """Concat, optionally crossfaded. Matrix rows 5-6: exact frame counts, real blend.

    Audio is re-encoded and ~13-26 ms of offset accumulates per join, so a timeline whose audio
    must stay in sync is built as ONE continuous track (M2 decision), not by chaining merges.
    """
    args = list(inputs)
    if transition:
        args += ["-t", transition]
    args += _opt("-td", transition_duration)
    args += ["-o", _out(output)]
    return invoke("merge", args, overwrite=overwrite, timeout=timeout)


def resize(input_path, output, width=None, height=None, aspect=None, quality=None,
           overwrite=False, timeout=DEFAULT_TIMEOUT):
    """Pad/blur reframe (matrix row 4). There is NO crop option here - ffmpeg does crop."""
    args = [input_path] + _opt("-w", width) + _opt("--height", height) + _opt("-a", aspect)
    args += _opt("-q", quality) + ["-o", _out(output)]
    return invoke("resize", args, overwrite=overwrite, timeout=timeout)


def fade(input_path, output, fade_in=None, fade_out=None, overwrite=False,
         timeout=DEFAULT_TIMEOUT):
    """Fade in/out in seconds (matrix row 6 family)."""
    args = [input_path] + _opt("--fade-in", fade_in) + _opt("--fade-out", fade_out)
    args += ["-o", _out(output)]
    return invoke("fade", args, overwrite=overwrite, timeout=timeout)


def subtitles(input_path, subtitle, output, style=None, overwrite=False,
              timeout=DEFAULT_TIMEOUT):
    """Burn an SRT (matrix row 10: non-ASCII cue text on exactly the cue frames)."""
    args = [input_path, subtitle] + _opt("--style", style) + ["-o", _out(output)]
    return invoke("subtitles", args, overwrite=overwrite, timeout=timeout)


def export(input_path, output, quality=None, container=None, overwrite=False,
           timeout=DEFAULT_TIMEOUT):
    """Final encode (matrix row 11: H.264 High / yuv420p / AAC 48 kHz stereo / faststart)."""
    args = [input_path] + _opt("-q", quality) + _opt("-f", container) + ["-o", _out(output)]
    return invoke("export", args, overwrite=overwrite, timeout=timeout)


def mix_audio(input_path, output, tracks, keep_source=True, bitrate=None, overwrite=False,
              timeout=DEFAULT_TIMEOUT):
    """Mix extra tracks under the source audio (matrix row 8).

    `tracks` is a list of dicts (`path, start, volume, fade_in, fade_out`) serialised to JSON:
    Kinocut 1.16.4 rejects a bare path here (findings 11).
    """
    args = [input_path, "--sounds", json.dumps(tracks, ensure_ascii=False),
            "--keep-source" if keep_source else "--no-keep-source"]
    args += _opt("--audio-bitrate", bitrate) + ["-o", _out(output)]
    return invoke("mix-audio", args, overwrite=overwrite, timeout=timeout)


def duck_audio(input_path, music, output, music_volume=None, threshold=None, ratio=None,
               attack=None, release=None, overwrite=False, timeout=DEFAULT_TIMEOUT):
    """Sidechain duck (matrix row 7: 16.4 dB measured).

    `input_path` carries the key (speech); `music` is the bed that is ducked by it.
    """
    args = [input_path, music] + _opt("--music-volume", music_volume)
    args += _opt("--threshold", threshold) + _opt("--ratio", ratio)
    args += _opt("--attack", attack) + _opt("--release", release) + ["-o", _out(output)]
    return invoke("duck-audio", args, overwrite=overwrite, timeout=timeout)


def normalize_audio(input_path, output, lufs=None, lra=None, true_peak=None, fade_seconds=None,
                    overwrite=False, timeout=DEFAULT_TIMEOUT):
    """Loudness normalisation (matrix row 8: -15.9 LUFS / -9.0 dBTP achieved)."""
    args = [input_path] + _opt("-l", lufs) + _opt("--lra", lra)
    args += _opt("--true-peak-dbtp", true_peak) + _opt("--fade-seconds", fade_seconds)
    args += ["-o", _out(output)]
    return invoke("normalize-audio", args, overwrite=overwrite, timeout=timeout)


def overlay_video(background, overlay, output, position=None, width=None, height=None,
                  opacity=None, start=None, duration=None, overwrite=False,
                  timeout=DEFAULT_TIMEOUT):
    """Picture-in-picture that KEEPS the background audio (unlike composite-layers, findings 11)."""
    args = [background, overlay] + _opt("-p", position) + _opt("-w", width)
    args += _opt("--height", height) + _opt("--opacity", opacity)
    args += _opt("--start-time", start) + _opt("--duration", duration) + ["-o", _out(output)]
    return invoke("overlay-video", args, overwrite=overwrite, timeout=timeout)


def release_checkpoint(media, output_dir, min_score=None, frame_count=None, require_audio=None,
                       timeout=DEFAULT_TIMEOUT):
    """Kinocut's release gate: storyboard + score (matrix row 12, hybrid with ffmpeg detectors).

    A global score, not a per-frame check: it missed a one-frame black flash and a silence gap,
    so gates.py pairs it with the ffmpeg detectors.
    """
    args = [media, "-o", guard.assert_writable(output_dir), "--format", "json"]
    args += _opt("--min-score", min_score) + _opt("--frame-count", frame_count)
    if require_audio is not None:
        args.append("--require-audio" if require_audio else "--no-require-audio")
    return invoke("release-checkpoint", args, timeout=timeout)


# ----------------------------------------------------------- diagnostics / workflows
def info(path):
    """`kino info --format json`: duration, size, fps, codecs, bitrate (read-only)."""
    return invoke("info", [path])


def version():
    """Installed Kinocut version string, or '' when it is not installed."""
    if not available():
        return ""
    try:
        proc = subprocess.run([kino_exe(), "--version"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    text = decode_bytes(proc.stdout).strip()
    return text.splitlines()[-1] if text else ""


def doctor():
    """`kino doctor --json`; exit 0 means the venv is healthy (M1 evidence)."""
    return invoke("doctor", ["--json"], timeout=120)


def workflow_validate(spec):
    """Validate a workflow job spec (findings 11: params use engine names, not CLI flags)."""
    return invoke("workflow-validate", ["--spec", os.path.abspath(spec)], cwd=_spec_dir(spec))


def workflow_render(spec, output=None, resume=None, timeout=DEFAULT_TIMEOUT):
    """Run a workflow spec; the receipt carries spec_hash + per-output sha256.

    Sources must stay relative inside the spec's directory, so cwd is that directory and
    `-o`/`--resume` are absolute (findings 11 and 7.10). Reusing a receipt with a changed spec
    fails closed with `resume_spec_mismatch` -- that is a deterministic error, not a retry.
    """
    args = ["--spec", os.path.abspath(spec)]
    if output:
        args += ["-o", _out(output)]
    if resume:
        args += ["--resume", os.path.abspath(resume)]
    return invoke("workflow-render", args, timeout=timeout, cwd=_spec_dir(spec))


def _spec_dir(spec):
    return os.path.dirname(os.path.abspath(spec))

