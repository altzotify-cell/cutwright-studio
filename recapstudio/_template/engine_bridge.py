"""The one place Recap Studio meets the Cutwright engine (M4).

`recap.py` keeps the creative pipeline (voice, timing, slates, characters, captions). The editing
operations whose executors `docs/CAPABILITY_MATRIX.md` measured live in `cutwright/engine/`, and
this module is the only bridge between the two: it finds the repo root, imports the engine from
it, calls ONE op per function, and hands back the result.

Nothing here re-implements an edit. Every call goes through `registry.route()`, so the executor
and its measured reason come from `cutwright/engine/ops.py` -- if the matrix says Kinocut, this
module cannot quietly call ffmpeg instead.

Why a bridge and not `python -m cutwright run <manifest>`: a recap project builds hundreds of
per-segment clips with its own cache; the manifest runner is the right tool for a whole production
plan (it arrives with the agent bridge in M6), not for one join inside an existing step. Both use
the same ops and the same executors, so neither is a second implementation.

The house rules this respects (`.clinerules/01`):
  * `cutwright/` stays stdlib-only - nothing here is imported BY the engine;
  * every write goes through the executor -> `cutwright.guard` (it refuses to write outside the fork);
  * picture is joined as VIDEO ONLY and the audio is one continuous track built afterwards --
    a mixed join is what re-timed a 24 fps render to 30 fps (COMMS C-007 finding 1).
"""
import inspect
import os

ROOT_MARKER = os.path.join("cutwright", "engine", "ops.py")   # a repo root looks like this


def repo_root(start=None):
    """The fork root: the nearest parent of this file that contains `cutwright/engine/ops.py`.

    Searched from this file's folder upwards, so the same module works from
    `recapstudio/_template/` and from a copied `recapstudio/Projects/<job>/`. None if the project
    was copied out of the fork entirely: the caller then refuses the step (no silent fallback to a
    second implementation of the same op, per `.clinerules/01`).
    """
    here = os.path.abspath(start or os.path.dirname(os.path.abspath(__file__)))
    while True:
        if os.path.isfile(os.path.join(here, ROOT_MARKER)):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def engine():
    """Import and return (ops, registry) from the fork root's `cutwright.engine`.

    `sys.path` gets the fork root once, so `import cutwright.engine` resolves to THIS fork's
    engine even when the process was started inside a project folder.
    """
    import sys
    root = repo_root()
    if root is None:
        raise RuntimeError("no cutwright/engine found above %s - is this project inside the fork?"
                           % os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from cutwright.engine import ops, registry
    return ops, registry


def available():
    """(ok, why): can this process reach the engine at all? Cheap, no media, no subprocess."""
    try:
        ops, _registry = engine()
    except (ImportError, RuntimeError) as exc:
        return False, str(exc)
    return True, "%d ops from %s" % (len(ops.OPS), repo_root())


def run_op(op, inputs, output, params=None, overwrite=True):
    """Run one engine op: op name, {input name: path}, the output path, checked params.

    The same steps `manifest._call` takes, and for the same reasons: params are validated before
    anything spawns, the executor is the matrix's choice (never a caller's guess), and the
    executor's own signature is the last filter so an unused param cannot become a TypeError
    halfway through a render. Returns the executor's ExecResult.
    """
    ops, registry = engine()
    route = registry.route(op, params=params or {})
    kwargs = ops.executor_kwargs(route.spec, route.params, inputs=inputs)
    accepted = inspect.signature(route.function).parameters
    kwargs = {key: value for key, value in kwargs.items() if key in accepted}
    if overwrite and "overwrite" in accepted:
        kwargs["overwrite"] = True
    arguments = [inputs[name] for name in ops.positional_inputs(route.spec)]
    return route.function(*arguments, output, **kwargs)


def concat_picture(clips, output):
    """Join VIDEO-ONLY clips into one file: the `concat` op (Kinocut merge, matrix row 6).

    Picture only, on purpose: the clips carry no audio (every picture pass here is `-an`), so
    Kinocut has nothing to re-time. Concatenating a silent clip with an audio one is what
    produced 30 fps / 75 frames instead of 24 fps / 60 (COMMS C-007 finding 1).
    """
    clips = [os.path.abspath(clip) for clip in clips]
    if not clips:
        raise ValueError("concat_picture needs at least one clip")
    return run_op("concat", {"sources": clips}, os.path.abspath(output))


def fit_clip(src, output, frames, fps, width, height, fill="pad"):
    """Exactly `frames` frames at `fps` in width x height: `fit_to_frames` (ffmpeg, matrix row 2).

    Video only by design (`-an`): a recap's audio is one continuous track built from the voice
    files, never a per-clip stream (M2 gap 3: 13-26 ms of drift per join).
    """
    return run_op("fit_to_frames", {"src": os.path.abspath(src)}, os.path.abspath(output),
                  {"frames": int(frames), "fps": float(fps), "width": int(width),
                   "height": int(height), "fill": fill})


def mix_tracks(src, output, tracks, keep_source=True):
    """Mix extra track FILES under a file's audio: `mix_audio` (Kinocut, matrix row 8).

    `tracks` is a list of paths or {path, ...} dicts. The FILE becomes the op's `tracks` input
    (digested, so it is part of the cache key); the rest of each dict stays params, exactly as
    `cutwright/engine/ops.py` declares them.

    `src` must be a MEDIA file with a video stream: Kinocut 1.16.4 refuses an audio-only source
    ("mix_audio requires a video stream", measured 2026-10-30), so Recap mixes the music bed under
    the already-muxed picture and not under a bare narration wav. The video is stream-copied - the
    packets came back md5-identical in the same run - so mixing cannot re-time the picture.
    """
    files, settings = [], []
    for row in tracks:
        if isinstance(row, dict):
            settings.append({key: value for key, value in row.items() if key != "path"})
            files.append(os.path.abspath(row["path"]))
        else:
            files.append(os.path.abspath(row))
            settings.append({})
    return run_op("mix_audio", {"src": os.path.abspath(src), "tracks": files},
                  os.path.abspath(output), {"tracks": settings, "keep_source": keep_source})
