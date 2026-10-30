"""Remotion executor: the graphics ops that DRAW a frame or a range of frames (M5.5A).

Why this executor exists at all (`.clinerules/01`, M5.5): the engine could edit but not draw in
code. `docs/VISUAL_STANDARD.md` section 4 names the consequence - scenes that pass every check still
look like PowerPoint - and one of its stated causes is that nothing in the pipeline can render a
directed shot and let the agent LOOK at it. Remotion is the renderer this project already owns
(pinned 4.0.539, `recapstudio/remotion`); M0 measured its output within one frame of the ffmpeg join
(`docs/ENVIRONMENT.md`), and 5.5A measured the cost of one look (LOG 2026-10-30 M5.5A).

Two ops, one call each - the same shape as every other executor:

  * `render_still` - ONE frame of a composition to a PNG. This is the critic loop's unit: render,
    look, name the defect, revise.
  * `render_range` - frames [start, start+frames-1] to an H.264 file, for a shot that needs to be
    judged in motion (or handed to an editing op as a clip).

Design rules this module follows, all of them learned from the other two executors:

  * The SCENE FILE is the op's declared input (`inputs=("scene",)`), so the engine digests it into
    the step's cache key: editing the scene re-renders, editing an unrelated scene does not.
  * argv only, never a shell string; the pinned CLI is called as `node @remotion/cli/remotion-cli.js`
    (not `npx`, which may resolve another version and prints its own noise).
  * cwd is `recapstudio/remotion`: `remotion.config.ts` resolves the `@kit` alias from
    `process.cwd()`, so a different cwd breaks the import alias.
  * `--props` gets a PATH to a JSON file written next to the output, never an inline JSON string:
    on Windows an inline `{"portrait":true}` survives Python's argv quoting but a `.cmd` shim can
    re-parse it. The props file is the render's own record of what was asked for.
  * Nothing is written outside the fork: `guard.assert_writable()` runs BEFORE the render starts.
"""
import json
import os
import re
import shutil
import subprocess
import time

from cutwright import guard
from cutwright.engine.executors import (ExecResult, ExecutorError, ExecutorTimeout,
                                        ExecutorUnavailable, decode_bytes, kill_tree)

EXECUTOR = "remotion"
NODE_ENV = "CUTWRIGHT_NODE"        # override for tests / a bundled node
DEFAULT_TIMEOUT = 1800.0           # a 22 s 1080p timeline took 96 s in M0; a long range may take many minutes
KILL_TIMEOUT = 20
_VERSION = {}


def remotion_dir():
    """The Remotion project this executor renders: `recapstudio/remotion`."""
    return os.path.join(guard.RECAP, "remotion")


def package_path():
    return os.path.join(remotion_dir(), "package.json")


def entry_point():
    return os.path.join(remotion_dir(), "src", "index.ts")


def cli_path():
    """The pinned CLI's JS entry (a file, not the `.cmd` shim: no shell, no re-quoting)."""
    return os.path.join(remotion_dir(), "node_modules", "@remotion", "cli", "remotion-cli.js")


def node_exe():
    return os.environ.get(NODE_ENV) or shutil.which("node") or ""


def available():
    """Node + the pinned CLI + the remotion package, all present. Never spawns a process."""
    return bool(node_exe()) and os.path.isfile(cli_path()) and os.path.isdir(
        os.path.join(remotion_dir(), "node_modules", "remotion"))


def version():
    """The pinned Remotion version from package.json (e.g. '4.0.539'), cached. '' if absent."""
    if "v" not in _VERSION:
        text = ""
        try:
            with open(package_path(), "r", encoding="utf-8") as handle:
                text = str((json.load(handle).get("dependencies") or {}).get("remotion") or "")
        except (OSError, ValueError):
            text = ""
        _VERSION["v"] = text
    return _VERSION["v"]

def build_argv(command, flags=(), exe=None):
    """`node <pinned cli> <command> <entry> <composition> <output> [flags]` - an argument list.

    The order matters: `@remotion/cli` takes the COMMAND first and the entry point second
    (measured: entry-first answered "Command .../src/index.ts not found"). Pure: no filesystem, no
    process beyond resolving node, so the tests check the flags here instead of starting a render.
    """
    head = [exe or node_exe(), cli_path(), str(command), entry_point()]
    return head + [str(value) for value in flags]


def _props_file(op, target, props):
    """Write the render's props beside its output; return the path to hand to `--props`.

    A file, not an inline JSON string (see the module docstring). `guard.write_json` is the one
    writer, so this cannot land outside the fork. No props -> no file (a landscape still needs none,
    SceneLab's defaultProps already carry portrait: false).
    """
    if not props:
        return ""
    path = target + ".props.json"
    try:
        return guard.write_json(path, props)
    except OSError as exc:
        raise ExecutorError(EXECUTOR, op, "cannot write the props file: %s" % exc,
                            code="props_unwritable",
                            suggested="check the output folder is writable inside the repository")


_CODES = (("could not find composition", "unknown_composition"),
          ("no composition with the id", "unknown_composition"),
          ("cannot find module", "bundle_failed"),
          ("module not found", "bundle_failed"),
          ("timed out", "render_timeout"),
          ("frame range", "bad_frames"))

_SUGGESTIONS = {
    "unknown_composition": "check the id with `remotion compositions`; SceneLab names them "
                           "scene-<segment id> and example-<name>",
    "bundle_failed": "the scene or its imports are broken; fix the file the error names",
    "bad_frames": "the frame range must sit inside the composition's duration",
    "render_timeout": "raise this step's timeout, or render fewer frames",
}


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _clean(text):
    """Remotion colour-codes its messages; the manifest holds the words, not escape codes."""
    return _ANSI.sub("", text or "")


def _first_error(text):
    """The most useful line of Remotion's output: its own error, else the last real line."""
    lines = [line.strip() for line in _clean(text).splitlines() if line.strip()]
    for line in lines:
        lowered = line.lower()
        if lowered.startswith(("error:", "uncaught", "typeerror", "referenceerror")) or \
                " is not a function" in line:
            return line[:400]
    return lines[-1][:400] if lines else ""


def error_from(op, argv, returncode, stdout, stderr):
    """Remotion's output -> ExecutorError with a code and the first real error line."""
    text = (stderr or "") + "\n" + (stdout or "")
    lowered = text.lower()
    code = "render_failed"
    for needle, candidate in _CODES:
        if needle in lowered:
            code = candidate
            break
    message = _first_error(text) or "remotion exited %s with no message" % returncode
    return ExecutorError(EXECUTOR, op, message, code=code, argv=argv, returncode=returncode,
                         stdout=stdout, stderr=stderr,
                         suggested=_SUGGESTIONS.get(code, "read this step's stderr"))


def invoke(op, command, composition, target, props=None, frame=None, first=None, last=None,
           image_format="png", crf=18, inputs=(), overwrite=False, timeout=DEFAULT_TIMEOUT):
    """Run one Remotion render. Returns ExecResult, or raises a typed ExecutorError.

    Pre-flight happens in Python, in this order: missing Node/CLI, a missing input, an existing
    output without `overwrite`, and only then the props file - so a machine without Remotion never
    leaves a file behind. The process tree is killed on a timeout (Chromium survives a plain
    `proc.kill()`).
    """
    argv = []
    if not available():
        raise ExecutorUnavailable(
            EXECUTOR, op, "Remotion is not installed in %s" % guard.rel(remotion_dir()),
            code="not_installed", argv=argv,
            suggested="npm install in recapstudio/remotion (Remotion stays 4.0.539), and put Node "
                      "on PATH (assumption A6: do not touch the system Node)")
    for path in inputs:
        if not os.path.exists(path):
            raise ExecutorError(EXECUTOR, op, "input does not exist: %s" % guard.rel(path),
                                code="input_missing", argv=argv,
                                suggested="check the path of the scene file")
    if os.path.exists(target) and not overwrite:
        raise ExecutorError(EXECUTOR, op, "output already exists: %s" % guard.rel(target),
                            code="output_exists", argv=argv,
                            suggested="pass overwrite=True to replace it deliberately")
    props_path = _props_file(op, target, props)
    flags = [composition, target]
    if command == "still":
        flags.append("--frame=%d" % int(frame or 0))
        flags.append("--image-format=%s" % image_format)
    else:
        flags.append("--frames=%d-%d" % (int(first or 0), int(last or 0)))
        flags.append("--codec=h264")
        flags.append("--crf=%d" % int(crf))
    if props_path:
        flags.append("--props=%s" % props_path)
    flags.append("--log=error")
    argv = build_argv(command, flags)
    started = time.time()
    try:
        proc = subprocess.Popen(argv, cwd=remotion_dir(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    except OSError as exc:
        raise ExecutorUnavailable(EXECUTOR, op, "cannot start node: %s" % exc,
                                  code="not_installed", argv=argv,
                                  suggested="check `node --version`, or set %s" % NODE_ENV)
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
                              suggested="raise this step's timeout, or render fewer frames",
                              transient=True)
    stdout, stderr = _clean(decode_bytes(out)), _clean(decode_bytes(err))
    if proc.returncode != 0:
        raise error_from(op, argv, proc.returncode, stdout, stderr)
    if not os.path.isfile(target) or os.path.getsize(target) == 0:
        raise ExecutorError(EXECUTOR, op, "remotion exited 0 but wrote no output",
                            code="output_missing", argv=argv, returncode=proc.returncode,
                            stdout=stdout, stderr=stderr,
                            suggested="check the composition id and the output extension")
    return ExecResult(executor=EXECUTOR, op=op, argv=argv, returncode=proc.returncode,
                      seconds=round(time.time() - started, 3), stdout=stdout, stderr=stderr,
                      output_path=os.path.abspath(target),
                      payload={"command": command, "composition": str(composition),
                               "props_file": guard.rel(props_path) if props_path else "",
                               "version": version()})


# ----------------------------------------------------------- typed ops (executor: remotion)
def _portrait(portrait):
    """The only prop these ops set. Landscape passes NOTHING: SceneLab's defaultProps already say
    portrait: false, so a 16:9 render needs no props file and leaves no extra artifact."""
    return {"portrait": True} if portrait else None


def render_still(scene, output, composition, frame=0, portrait=False, image_format="png",
                 timeout=DEFAULT_TIMEOUT, overwrite=False):
    """One frame of `composition` -> a PNG at `output`. The unit of the critic loop.

    `scene` is the scene file whose hash the engine puts in the step's cache key; it is checked for
    existence here and recorded in the result, but Remotion draws the composition, not the path.
    `portrait` renders the 9:16 shape (SceneLab's calculateMetadata swaps 1920x1080 to 1080x1920).
    """
    op = "render_still"
    target = guard.assert_writable(output)
    return invoke(op, "still", composition, target, props=_portrait(portrait),
                  frame=frame, image_format=image_format, inputs=[scene],
                  overwrite=overwrite, timeout=timeout)


def render_range(scene, output, composition, start=0, frames=24, portrait=False, crf=18,
                 timeout=DEFAULT_TIMEOUT, overwrite=False):
    """Frames [start, start+frames-1] of `composition` -> an H.264 MP4 at `output`.

    Inclusive on both ends, the same convention as `trim_exact`'s `start_frame` + `frames`, so a
    1-second range at 24 fps is frames=24 and not frames=25.
    """
    op = "render_range"
    target = guard.assert_writable(output)
    return invoke(op, "render", composition, target, props=_portrait(portrait),
                  first=int(start), last=int(start) + int(frames) - 1, crf=crf, inputs=[scene],
                  overwrite=overwrite, timeout=timeout)

