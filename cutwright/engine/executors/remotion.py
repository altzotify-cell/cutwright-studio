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

M5.5B added two things, both measured before they were trusted:

  * ASSET HANDLES. A scene says `<LayeredMedia asset="footage_a"/>`; the step's `assets` input maps
    that handle to a real file and the engine digests the file into the cache key. The executor
    stages each file in `remotion/public/assets/` (symlink, so the bundler forwards it instead of
    copying the clip into every bundle) and hands the table to the scene in the PROPS file.
  * ONE BUNDLE PER CONTENT KEY. `remotion bundle --out-dir=<cache>` runs once per
    `sha256(kit/** + src/** + scene + config)` and each render then names the bundle directory
    instead of the entry file: 8.1 s once, then 4.6-5.1 s per still instead of ~10 s each. The
    cache holds 5 bundles and deletes the oldest by mtime.
"""
import hashlib
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

def build_argv(command, flags=(), exe=None, entry=None):
    """`node <pinned cli> <command> <entry> [flags]` - an argument list.

    The order matters: `@remotion/cli` takes the COMMAND first and the entry point second
    (measured: entry-first answered "Command .../src/index.ts not found"). `entry` defaults to the
    Remotion entry file; M5.5B passes a BUNDLE DIRECTORY instead, which `still`/`render` accept as
    their entry and which saves the 8 s webpack step on every frame after the first.
    Pure: no filesystem, no process beyond resolving node, so the tests check the flags here
    instead of starting a render.
    """
    head = [exe or node_exe(), cli_path(), str(command), str(entry or entry_point())]
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
           image_format="png", crf=18, inputs=(), overwrite=False, timeout=DEFAULT_TIMEOUT,
           entry=None, bundle=""):
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
    argv = build_argv(command, flags, entry=entry)
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
                               "bundle": bundle or "", "version": version()})


# ------------------------------------------- asset handles, one bundle, the bundle cache (M5.5B)
# A scene names a HANDLE (`<LayeredMedia asset="footage_a"/>`); the step's `assets` input maps that
# handle to a real file and the engine digests it into the step's cache key. Only this executor ever
# sees a path - and only as a stage instruction, never as something a scene could spell.
ASSET_KINDS = {".mp4": "video", ".m4v": "video", ".mov": "video", ".webm": "video",
               ".mkv": "video", ".png": "image", ".jpg": "image", ".jpeg": "image",
               ".webp": "image"}
BUNDLE_CACHE = os.path.join(guard.OUT, ".cache", "remotion-bundle")
BUNDLE_LIMIT = 5                   # owner's cap (2026-10-30): oldest by mtime goes first
BUNDLE_TIMEOUT = 900.0
BUNDLE_MARK = "index.html"         # a finished bundle always has one; a half-written one does not
_BUNDLE_EXTS = (".ts", ".tsx", ".json", ".css", ".mjs")


def asset_kind(path):
    """'video' | 'image' | '' from the extension - the only thing that decides how to draw it."""
    return ASSET_KINDS.get(os.path.splitext(str(path))[1].lower(), "")


def _unlink(path):
    try:
        os.remove(path)
    except OSError:
        pass


def link_or_copy(source, dest):
    """Point `dest` at `source` WITHOUT copying bytes: HARD LINK first, then a plain copy.

    Measured 2026-10-30 (Remotion 4.0.539): a SYMLINK does not work - `@remotion/bundler` forwards it
    into the bundle (copy-dir.js:25) and the render then answers "Received a status code of 404 while
    downloading file http://localhost:3000/public/assets/footage_a.mp4"; with a real file in the same
    place the same still rendered normally. So the staged entry is a hard link (a real file, no bytes,
    no privilege) and a copy is the fallback across volumes.
    """
    real = os.path.realpath(source)
    if os.path.lexists(dest):
        try:
            if os.path.samefile(dest, real):        # a hard link IS the same file: nothing to do
                return "existing"
        except OSError:
            pass
        _unlink(dest)
    try:
        os.link(real, dest)
        return "hardlink"
    except OSError:
        pass
    shutil.copyfile(real, dest)
    return "copy"


def stage_assets(op, assets):
    """{handle: path} -> the table the props file carries, with the media staged in public/assets.

    Every handle is validated here, before a browser starts: a missing file, an extension that is
    not footage or an image, or a handle that is not a bare name is a typed ExecutorError.
    """
    from cutwright.engine import checkpoint          # local: engine -> executors would be a cycle

    table = {}
    if not assets:
        return table
    root = guard.ensure_dir(os.path.join(remotion_dir(), "public", "assets"))
    for handle in sorted(assets):
        path = str(assets[handle])
        ext = os.path.splitext(path)[1].lower()
        kind = ASSET_KINDS.get(ext)
        if not kind:
            raise ExecutorError(EXECUTOR, op,
                                "handle %r points at a %s file, which is not footage or an image"
                                % (handle, ext or "no-extension"),
                                code="bad_asset",
                                suggested="video: %s / image: %s" % (
                                    ", ".join(sorted(k for k in ASSET_KINDS
                                                     if ASSET_KINDS[k] == "video")),
                                    ", ".join(sorted(k for k in ASSET_KINDS
                                                     if ASSET_KINDS[k] == "image"))))
        if not os.path.isfile(path):
            raise ExecutorError(EXECUTOR, op, "handle %r is missing on disk: %s"
                                % (handle, guard.rel(path)), code="input_missing",
                                suggested="fix the asset path in the manifest")
        name = handle + ext
        link_or_copy(path, os.path.join(root, name))
        table[handle] = {"file": "assets/" + name, "kind": kind,
                         "sha256": (checkpoint.digest_file(path) or {}).get("sha256", "")}
    return table


def _bundle_files():
    """Every file whose CONTENT goes into the bundle: kit/**, src/** and scenes_examples/**.

    `scenes_examples` is here because `src/SceneLab.tsx` imports it, so all reference scenes really are
    inside every bundle - a key that ignored them would serve a stale scene after an edit.
    """
    files = []
    for name in ("kit", "src", "scenes_examples"):
        root = os.path.join(remotion_dir(), name)
        for dirpath, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in ("node_modules", "build"))
            for filename in sorted(names):
                if os.path.splitext(filename)[1] in _BUNDLE_EXTS:
                    files.append(os.path.join(dirpath, filename))
    files.append(os.path.join(remotion_dir(), "remotion.config.ts"))
    files.append(package_path())
    return files


def bundle_key(scene):
    """Content hash of everything that goes INTO the bundle. The footage is not in it.

    That is the point of mounting assets into `public/assets` at render time: a new clip does not
    rebuild the bundle (its sha256 is already in the step's cache key) and cannot go stale either,
    while an edited scene, kit or example file does rebuild. A scene that lives outside the roots
    above (a test scene in `out/`) is hashed by its own path as well.
    """
    digest = hashlib.sha256()
    files = _bundle_files()
    seen = set(os.path.normcase(os.path.abspath(path)) for path in files)
    extra = os.path.abspath(str(scene))
    if os.path.normcase(extra) not in seen:
        files.append(extra)
    for path in files:
        digest.update(guard.rel(path).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                digest.update(hashlib.sha256(handle.read()).digest())
        else:
            digest.update(b"missing")
    return digest.hexdigest()[:16]


def bundle_dir(key):
    return os.path.join(BUNDLE_CACHE, key)


def ensure_bundle(op, scene, timeout=BUNDLE_TIMEOUT):
    """The bundle directory for this scene, built once per content key. Returns (dir, key).

    Measured 2026-10-30: a bundle is 8.1 s and 33.8 MB (23.3 MB of it source maps); a still rendered
    FROM that bundle costs 4.6-5.1 s instead of ~10 s, so three stills of one scene went from
    ~3 x 10 s to 21.6 s cold / 14.4 s cached. A stale bundle is never reused: the key is content.
    """
    key = bundle_key(scene)
    target = bundle_dir(key)
    if os.path.isfile(os.path.join(target, BUNDLE_MARK)):
        os.utime(target)                        # LRU: this bundle is the most recently used
        return target, key
    guard.ensure_dir(BUNDLE_CACHE)
    staging = target + ".part"
    shutil.rmtree(staging, ignore_errors=True)
    argv = [node_exe(), cli_path(), "bundle", entry_point(), "--out-dir=" + staging,
            "--log=error"]
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
        raise ExecutorTimeout(EXECUTOR, op, "the bundle did not finish in %ss" % timeout,
                              code="timeout", argv=argv, transient=True,
                              suggested="raise this step's timeout")
    stdout, stderr = _clean(decode_bytes(out)), _clean(decode_bytes(err))
    if proc.returncode != 0:
        shutil.rmtree(staging, ignore_errors=True)
        raise error_from(op, argv, proc.returncode, stdout, stderr)
    if not os.path.isfile(os.path.join(staging, BUNDLE_MARK)):
        shutil.rmtree(staging, ignore_errors=True)
        raise ExecutorError(EXECUTOR, op,
                            "the bundler exited 0 but wrote no %s in %s"
                            % (BUNDLE_MARK, guard.rel(staging)),
                            code="bundle_failed", argv=argv, returncode=proc.returncode,
                            stdout=stdout, stderr=stderr,
                            suggested="delete that .part folder and run the step again")
    shutil.rmtree(target, ignore_errors=True)
    os.rename(staging, target)
    prune_bundles(keep=key)
    return target, key


def prune_bundles(keep="", limit=BUNDLE_LIMIT, cache=None):
    """Keep the `limit` most recently used bundles (mtime), deleting the oldest. Never `keep`.

    The owner's cap for 2026-10-30: `out/.cache/remotion-bundle` may hold 5 bundles, oldest first
    out, so a run that keeps rebuilding cannot fill the disk with 33.8 MB copies. Returns the names
    it removed, so a test can check the policy instead of trusting it.
    """
    root = cache or BUNDLE_CACHE
    if not os.path.isdir(root):
        return []
    rows = sorted((os.path.getmtime(os.path.join(root, name)), name)
                  for name in os.listdir(root) if os.path.isdir(os.path.join(root, name)))
    removed = []
    for _mtime, name in rows:
        if len(rows) - len(removed) <= int(limit):
            break
        if name == keep or name.endswith(".part"):
            continue
        shutil.rmtree(os.path.join(root, name), ignore_errors=True)
        removed.append(name)
    return removed


# ----------------------------------------------------------- typed ops (executor: remotion)
def _props(portrait=False, table=None):
    """The render's props. Landscape with no assets passes NOTHING (SceneLab's defaultProps already
    say portrait: false), so an asset-free step leaves no extra file - exactly as in M5.5A.

    The staged asset table travels HERE rather than in a generated module: the props file already
    exists per render, it is the render's own record of which handle drew which file, and a
    gitignored `src/generated/assets.ts` that the kit imports would break every bundle on a fresh
    checkout. SceneLab hands the table to the scene through the kit's `AssetScope`.
    """
    props = {}
    if portrait:
        props["portrait"] = True
    if table:
        props["assets"] = table
    return props or None


def mount_assets(bundle, table, assets):
    """Point `<bundle>/public/assets` at the CURRENT footage, before every render.

    Why this exists: the bundle key is CODE only (`kit/** + src/** + scene + config`), so a reused
    bundle would otherwise serve the clip that existed when it was built - a stale picture with a
    cache key that says otherwise. Mounting the files (hard link, 0 bytes) on each render keeps the
    key cheap and the media correct: a replaced clip changes the step's cache key AND the pixels.
    """
    if not table:
        return {}
    root = guard.ensure_dir(os.path.join(bundle, "public", "assets"))
    how = {}
    for handle in sorted(table):
        name = table[handle]["file"].split("/", 1)[-1]
        how[handle] = link_or_copy(str(assets[handle]), os.path.join(root, name))
    return how


def _preflight(op, scene, target, overwrite):
    """The refusals that must land BEFORE a bundle is built or a handle is staged.

    `invoke()` repeats them later; they run here too because building a bundle takes 8 s and staging
    writes into the repo - a missing scene or an existing output must cost nothing and leave no file.
    """
    if not available():
        raise ExecutorUnavailable(
            EXECUTOR, op, "Remotion is not installed in %s" % guard.rel(remotion_dir()),
            code="not_installed", argv=[],
            suggested="npm install in recapstudio/remotion (Remotion stays 4.0.539), and put Node "
                      "on PATH (assumption A6: do not touch the system Node)")
    if not os.path.exists(str(scene)):
        raise ExecutorError(EXECUTOR, op, "input does not exist: %s" % guard.rel(str(scene)),
                            code="input_missing", argv=[],
                            suggested="check the path of the scene file")
    if os.path.exists(target) and not overwrite:
        raise ExecutorError(EXECUTOR, op, "output already exists: %s" % guard.rel(target),
                            code="output_exists", argv=[],
                            suggested="pass overwrite=True to replace it deliberately")


def render_still(scene, output, composition, frame=0, portrait=False, image_format="png",
                 assets=None, timeout=DEFAULT_TIMEOUT, overwrite=False):
    """One frame of `composition` -> a PNG at `output`. The unit of the critic loop.

    `scene` is the scene file whose hash the engine puts in the step's cache key; it is checked for
    existence here and recorded in the result, but Remotion draws the composition, not the path.
    `portrait` renders the 9:16 shape (SceneLab's calculateMetadata swaps 1920x1080 to 1080x1920).
    `assets` is the step's handle -> path table: staged into public/assets, handed to the scene in
    the props file, and its files already digested into the cache key by the engine.
    """
    op = "render_still"
    target = guard.assert_writable(output)
    _preflight(op, scene, target, overwrite)
    table = stage_assets(op, assets)
    entry, key = ensure_bundle(op, scene, timeout=max(timeout, BUNDLE_TIMEOUT))
    mount_assets(entry, table, assets)
    return invoke(op, "still", composition, target, props=_props(portrait, table),
                  frame=frame, image_format=image_format, inputs=[scene], entry=entry,
                  bundle=key, overwrite=overwrite, timeout=timeout)


def render_range(scene, output, composition, start=0, frames=24, portrait=False, crf=18,
                 assets=None, timeout=DEFAULT_TIMEOUT, overwrite=False):
    """Frames [start, start+frames-1] of `composition` -> an H.264 MP4 at `output`.

    Inclusive on both ends, the same convention as `trim_exact`'s `start_frame` + `frames`, so a
    1-second range at 24 fps is frames=24 and not frames=25.
    """
    op = "render_range"
    target = guard.assert_writable(output)
    _preflight(op, scene, target, overwrite)
    table = stage_assets(op, assets)
    entry, key = ensure_bundle(op, scene, timeout=max(timeout, BUNDLE_TIMEOUT))
    mount_assets(entry, table, assets)
    return invoke(op, "render", composition, target, props=_props(portrait, table),
                  first=int(start), last=int(start) + int(frames) - 1, crf=crf, inputs=[scene],
                  entry=entry, bundle=key, overwrite=overwrite, timeout=timeout)


