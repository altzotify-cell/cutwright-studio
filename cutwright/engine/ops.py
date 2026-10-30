"""The engine's vocabulary: one `OpSpec` per operation the engine actually performs.

Every spec names the executor that `docs/CAPABILITY_MATRIX.md` measured as passing, the evidence
file that decision rests on, and the measured reason in words. `registry.route()` may not deviate
from that without an explicit, recorded reason (`.clinerules/01`: "never duplicate an op Kinocut
passes; use direct FFmpeg when it did not, with `executor_reason`").

Names follow `docs/schemas/manifest.example.json` (`trim_exact`, `fit_to_frames`, `export_h264`)
so the roadmap's acceptance commands and the example manifest stay valid.

Pure data + validation: nothing here spawns a process. `validate_params()` rejects an unknown
parameter, a missing required one, a bad type or an out-of-range value BEFORE an executor starts,
so a typo costs microseconds instead of a render. Deterministic, never retried.
"""
import dataclasses

STAGES = ("plan", "assets", "edit", "graphics", "qc", "deliver")
MAX_ENVELOPE = 10          # roadmap: never hand an agent the whole catalogue in one call


@dataclasses.dataclass(frozen=True)
class Param:
    """One parameter: a type, a doc string, and the bounds the validator enforces."""
    type: str                       # int | float | str | bool | enum | tracks
    doc: str
    required: bool = False
    default: object = None
    choices: tuple = ()
    minimum: float = None

    def to_dict(self):
        out = {"type": self.type, "doc": self.doc, "required": self.required}
        if self.default is not None:
            out["default"] = self.default
        if self.choices:
            out["choices"] = list(self.choices)
        if self.minimum is not None:
            out["minimum"] = self.minimum
        return out


@dataclasses.dataclass(frozen=True)
class OpSpec:
    """One operation: where it sits, who runs it, what it takes and what it produces."""
    name: str
    stage: str
    description: str
    executor: str                   # kinocut | ffmpeg | current
    target: str                     # function name inside that executor module
    executor_reason: str            # the measured reason, quoting the matrix
    evidence: str                   # docs/evidence/m2_*.json
    inputs: tuple = ("src",)
    outputs: tuple = ("video",)
    params: dict = dataclasses.field(default_factory=dict)
    validator: object = None        # optional cross-parameter rule

    def to_dict(self):
        return {"name": self.name, "stage": self.stage, "description": self.description,
                "executor": self.executor, "target": self.target,
                "executor_reason": self.executor_reason, "evidence": self.evidence,
                "inputs": list(self.inputs), "outputs": list(self.outputs),
                "params": {key: param.to_dict() for key, param in self.params.items()}}

    def defaults(self):
        """Parameter defaults, for a manifest that omitted them."""
        return {key: param.default for key, param in self.params.items()
                if param.default is not None and not param.required}


class OpError(ValueError):
    """A rejected op call: names the op, the parameter and the fix. Never transient."""

    def __init__(self, op, message="", code="invalid_params", param="", suggested=""):
        self.op = op
        self.code = code
        self.param = param
        self.suggested = suggested
        self.message = message
        text = "%s rejected (code %s)" % (op, code)
        if param:
            text += " [%s]" % param
        if message:
            text += ": %s" % message
        if suggested:
            text += " -> %s" % suggested
        super().__init__(text)

    def to_dict(self):
        return {"op": self.op, "code": self.code, "param": self.param,
                "message": self.message, "suggested": self.suggested}


# ------------------------------------------------------------------ lookup helpers
def get(name):
    """The spec called `name`, or None. Never raises: callers decide what a miss means."""
    return BY_NAME.get(name)


def names():
    return [spec.name for spec in OPS]


def by_stage(stage):
    """Specs for one stage, in table order (the envelope an agent gets)."""
    return [spec for spec in OPS if spec.stage == stage]


# ------------------------------------------------------------------ validation
def validate_params(op, params):
    """Check `params` against the spec; return them with defaults filled in.

    Raises OpError codes: unknown_op, unknown_param, missing_param, bad_type, bad_choice,
    out_of_range, invalid_combination. All deterministic.
    """
    if isinstance(op, str):
        spec = get(op)
        if spec is None:
            raise OpError(op, "no such op", code="unknown_op",
                          suggested="one of: %s" % ", ".join(names()))
    else:
        spec, op = op, op.name
    given = dict(params or {})
    for key in given:
        if key not in spec.params:
            raise OpError(op, "unknown parameter", code="unknown_param", param=key,
                          suggested="valid: %s" % (", ".join(spec.params) or "none"))
    filled = {}
    for key, param in spec.params.items():
        if key not in given:
            if param.required:
                raise OpError(op, "required parameter is missing", code="missing_param",
                              param=key, suggested=param.doc)
            filled[key] = param.default
            continue
        filled[key] = _check(op, key, param, given[key])
    if spec.validator is not None:
        spec.validator(spec, filled)
    return filled


def _check(op, key, param, value):
    """One parameter value -> a checked value, or OpError naming that parameter."""
    if value is None:
        # null means "not set": optional params keep it, required ones are missing. This also makes
        # validate_params idempotent -- re-checking its own output (a default filled in as None)
        # must pass, which is what a manifest does when it re-checks a derived step.
        if param.required:
            raise OpError(op, "required parameter is missing", code="missing_param",
                          param=key, suggested=param.doc)
        return None
    kind = param.type
    if kind == "bool":
        if not isinstance(value, bool):
            raise OpError(op, "expected true/false, got %r" % (value,), code="bad_type",
                          param=key)
        return value
    if kind in ("int", "float"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OpError(op, "expected a number, got %r" % (value,), code="bad_type",
                          param=key, suggested=param.doc)
        if kind == "int" and int(value) != value:
            raise OpError(op, "expected a whole number, got %r" % (value,), code="bad_type",
                          param=key, suggested="round it to an integer frame or pixel count")
        number = int(value) if kind == "int" else float(value)
        if param.minimum is not None and number < param.minimum:
            raise OpError(op, "must be >= %s, got %r" % (param.minimum, value),
                          code="out_of_range", param=key, suggested=param.doc)
        return number
    if kind == "tracks":
        if not isinstance(value, (list, tuple)) or not value:
            raise OpError(op, "expected a non-empty list of track settings", code="bad_type",
                          param=key, suggested='[{"volume": 0.35}] plus one "tracks" input')
        for index, track in enumerate(value):
            if not isinstance(track, dict):
                raise OpError(op, "track setting %d is not an object" % index, code="bad_type",
                              param=key, suggested='[{"volume": 0.35}]')
            if track.get("path"):
                raise OpError(op, "track setting %d carries a path" % index,
                              code="unknown_param", param=key,
                              suggested='declare the file as the op\'s "tracks" INPUT and keep '
                                        'only settings here (COMMS C-007 finding 3)')
        return [dict(track) for track in value]
    if not isinstance(value, str):
        raise OpError(op, "expected a string, got %r" % (value,), code="bad_type", param=key,
                      suggested=param.doc)
    if kind == "enum" and param.choices and value not in param.choices:
        raise OpError(op, "not one of the allowed values", code="bad_choice", param=key,
                      suggested="one of: %s" % ", ".join(param.choices))
    return value


def _trim_length(spec, params):
    """A cut needs a length: frames, or seconds. Never implicit."""
    if params.get("frames") is None and params.get("duration") is None:
        raise OpError(spec.name, "no length given", code="invalid_combination", param="frames",
                      suggested="frames=<count> for a frame-exact cut, or duration=<seconds>")


def _fit_geometry(spec, params):
    """A fit needs both dimensions or neither: half a size would silently keep the source."""
    width, height = params.get("width"), params.get("height")
    if (width is None) != (height is None):
        raise OpError(spec.name, "width and height must be given together",
                      code="invalid_combination", param="height",
                      suggested="give both (1920x1080) or neither (keep the source geometry)")


def _sounds(spec, params):
    """mix_audio without a track is a no-op that costs a re-encode; refuse it."""
    if not params.get("tracks"):
        raise OpError(spec.name, "no tracks to mix", code="invalid_combination", param="tracks",
                      suggested='one "tracks" input plus tracks=[{"volume": 0.35}]')


# Inputs that reach the executor as a NAMED argument built from params, never positionally.
KWARG_INPUTS = ("tracks",)


def positional_inputs(spec):
    """The inputs an executor takes positionally, in order (everything except KWARG_INPUTS).

    `manifest._call` builds its argument list from this, so an input that the executor takes as a
    keyword (mix_audio's track FILES, paired with their settings by `mix_tracks`) cannot end up in
    the wrong positional slot.
    """
    return [name for name in spec.inputs if name not in KWARG_INPUTS]


def mix_tracks(spec, params, inputs):
    """Pair the declared track FILES (inputs) with their settings (params), by position.

    COMMS C-007 finding 3, fixed here: a track named only in `params` is not part of a step's cache
    key, so replacing `music.wav` did not invalidate the mix. The file is now an input of the op --
    digested, hashed into the key -- and the settings stay params. Pairing is by position; a count
    mismatch is refused rather than guessed, because guessing would silently move the music.
    """
    value = (inputs or {}).get("tracks")
    if isinstance(value, (list, tuple)):
        paths = list(value)
    else:
        paths = [] if value is None else [value]
    settings = list(params.get("tracks") or [])
    if len(paths) != len(settings):
        raise OpError(spec.name, "%d track file(s) in inputs.tracks but %d track setting(s) in "
                      "params.tracks" % (len(paths), len(settings)),
                      code="invalid_combination", param="tracks",
                      suggested="give one input path per setting, in the same order")
    tracks = []
    for path, setting in zip(paths, settings):
        track = dict(setting)
        track["path"] = str(path)
        tracks.append(track)
    return tracks


# ------------------------------------------------------- manifest params -> executor kwargs
def executor_kwargs(spec, params, fps=24.0, inputs=None):
    """Checked manifest params -> keyword arguments for the executor function.

    Most ops forward their params unchanged. Three do not, and each for a measured reason:

      * `trim_exact` speaks FRAMES (`start_frame`, `frames`) while `kino trim` takes `-s`/`-d` in
        SECONDS, so the conversion needs the timeline's fps. Doing it here keeps the manifest's
        vocabulary frame-based (M2 measured trim by frame ids) and the adapter unchanged.
      * `transition` passes `type`/`duration` to `kino merge -t`/`-td`, whose wrapper names them
        `transition`/`transition_duration`.
      * `mix_audio` gets its track FILES from the step's `tracks` input and its per-track settings
        from `params.tracks`; `mix_tracks()` pairs them, so the file is part of the cache key.

    `manifest.py` filters the result against the executor function's signature, so an unused
    param (`accurate`, a default) cannot become a TypeError at render time.
    """
    out = dict(params or {})
    if spec.name == "trim_exact":
        rate = float(fps or 24.0)
        start = out.pop("start_frame", 0) or 0
        frames = out.pop("frames", None)
        out["start"] = round(float(start) / rate, 6)
        if frames is not None:
            out["duration"] = round(float(frames) / rate, 6)
    elif spec.name == "transition":
        out["transition"] = out.pop("type")
        out["transition_duration"] = out.pop("duration")
    elif spec.name == "mix_audio":
        out["tracks"] = mix_tracks(spec, out, inputs)
    return out



# ---------------------------------------------------------------------------- the table
# One line per matrix row. The `executor` is not a preference - it is the measured winner.
OPS = (
    OpSpec(
        name="trim_exact", stage="edit",
        description="Cut a frame-exact range out of a clip (start_frame + frames, or duration).",
        executor="kinocut", target="trim",
        executor_reason="trim returned exact frame ids at starts 0/1/37/119; the current "
                        "render_video_clip is one frame late on every non-zero start",
        evidence="docs/evidence/m2_trim.json",
        inputs=("src",),
        params={"start_frame": Param("int", "first frame to keep, 0-based", default=0, minimum=0),
                "frames": Param("int", "how many frames to keep", minimum=1),
                "duration": Param("float", "length in seconds (alternative to frames)",
                                  minimum=0.04),
                "accurate": Param("bool", "force accurate seek in Kinocut", default=False)},
        validator=_trim_length),
    OpSpec(
        name="reframe_pad", stage="edit",
        description="Reframe to a target aspect/size by letterboxing (no stretch, no crop).",
        executor="kinocut", target="resize",
        executor_reason="resize -a 9:16 letterboxes correctly (content 1080x600, centred, no "
                        "stretch); there is no crop option in Kinocut's resize",
        evidence="docs/evidence/m2_resize.json",
        inputs=("src",),
        params={"aspect": Param("str", 'target aspect, e.g. "9:16"'),
                "width": Param("int", "target width in pixels", minimum=2),
                "height": Param("int", "target height in pixels", minimum=2),
                "quality": Param("str", "Kinocut resize quality preset")}),
    OpSpec(
        name="concat", stage="edit",
        description="Join clips of the same format end to end, audio included.",
        executor="kinocut", target="merge",
        executor_reason="2400/2400 frames with no missing frame across a many-clip concat; "
                        "mixed formats need an ffmpeg normalise pass first",
        evidence="docs/evidence/m2_concat.json",
        inputs=("sources",)),
    OpSpec(
        name="transition", stage="edit",
        description="Join clips with a crossfade or wipe between them.",
        executor="kinocut", target="merge",
        executor_reason="228/228 frames with a real 12-frame blend ramp, no audio gap or click; "
                        "there is no implementation of this in the current code",
        evidence="docs/evidence/m2_transition.json",
        inputs=("sources",),
        params={"type": Param("enum", "transition kind", required=True,
                              choices=("fade", "wipe")),
                "duration": Param("float", "overlap in seconds", required=True, minimum=0.04)}),
    # ---- executor: ffmpeg (matrix rows 2, 4 and 9 - the ops Kinocut does not pass)
    OpSpec(
        name="fit_to_frames", stage="edit",
        description="Fit a clip to exactly N frames at a fixed fps, letterboxed into a size.",
        executor="ffmpeg", target="fit_to_frames",
        executor_reason="no Kinocut op takes a frame count (speed was a no-op, trim truncates); "
                        "fps + setsar + tpad=clone + -frames:v was exact at 53/97/241",
        evidence="docs/evidence/m2_fit.json",
        inputs=("src",),
        params={"frames": Param("int", "exact number of output frames", required=True, minimum=1),
                "fps": Param("float", "output frame rate", default=24, minimum=1),
                "width": Param("int", "target width in pixels", minimum=2),
                "height": Param("int", "target height in pixels", minimum=2),
                "fill": Param("enum", "pad = letterbox; blur comes from recap.fit_graph until M4",
                              default="pad", choices=("pad",)),
                "crf": Param("int", "libx264 quality (lower is better)", default=18, minimum=0)},
        validator=_fit_geometry),
    OpSpec(
        name="reframe_crop", stage="edit",
        description="Centre crop that fills the target size (a true 9:16 reframe, no bars).",
        executor="ffmpeg", target="crop_to_size",
        executor_reason="the current fit_graph has no crop branch (fill=crop letterboxed) and "
                        "Kinocut resize has no crop option; scale=increase,crop filled 1080x1920",
        evidence="docs/evidence/m2_resize.json",
        inputs=("src",),
        params={"width": Param("int", "target width in pixels", required=True, minimum=2),
                "height": Param("int", "target height in pixels", required=True, minimum=2),
                "frames": Param("int", "optional frame limit", minimum=1),
                "fps": Param("float", "optional frame rate", minimum=1)}),
    OpSpec(
        name="overlay_audio", stage="edit",
        description="Attach an audio track to a video-only file, video stream-copied.",
        executor="ffmpeg", target="overlay_audio",
        executor_reason="composite-layers returns video only (has_audio false), so every overlay "
                        "needs this audio pass; -c:v copy keeps the frames untouched",
        evidence="docs/evidence/m2_composite.json",
        inputs=("video", "audio"),
        params={"duration": Param("float", "intended length in seconds; omit = -shortest",
                                  minimum=0.04),
                "delay": Param("float", "shift the audio later by N seconds", default=0.0,
                               minimum=0),
                "bitrate": Param("str", "AAC bitrate for the attached audio", default="192k")}),
    # ---- executor: kinocut, audio (rows 7 and 8) and the two finishing passes (rows 10, 11)
    OpSpec(
        name="duck_audio", stage="edit",
        description="Duck a music bed under a voice track (sidechain compression).",
        executor="kinocut", target="duck_audio",
        executor_reason="duck-audio measured 16.4 dB of duck; the current amix path gives 0.2 dB "
                        "and clips at -0.3 dBTP",
        evidence="docs/evidence/m2_audio.json",
        inputs=("src", "music"),
        params={"music_volume": Param("float", "music level after ducking", minimum=0),
                "threshold": Param("float", "sidechain threshold in dB"),
                "ratio": Param("float", "compression ratio", minimum=1),
                "attack": Param("float", "attack in seconds", minimum=0),
                "release": Param("float", "release in seconds", minimum=0)}),
    OpSpec(
        name="mix_audio", stage="edit",
        description="Mix extra track files under the existing audio (music, SFX, stings).",
        executor="kinocut", target="mix_audio",
        executor_reason="mix-audio hit -15.9 LUFS / -9.0 dBTP with exact onsets; --sounds takes "
                        "JSON track descriptions, not a path",
        evidence="docs/evidence/m2_audio.json",
        inputs=("src", "tracks"),
        params={"tracks": Param("tracks", 'per-track settings ({"volume", "start", "fade_in", '
                                           '"fade_out"}), one per "tracks" input, same order: the '
                                           'FILES are the input, the settings are params',
                                required=True),
                "keep_source": Param("bool", "keep the source audio under the mix", default=True),
                "bitrate": Param("str", "output audio bitrate")},
        validator=_sounds),
    OpSpec(
        name="normalize_audio", stage="edit",
        description="Loudness-normalise to a target LUFS with a true-peak ceiling.",
        executor="kinocut", target="normalize_audio",
        executor_reason="normalize-audio reached -15.9 LUFS / -9.0 dBTP with the duck intact; "
                        "loudnorm must stay its own pass (running it inside the duck flattens it)",
        evidence="docs/evidence/m2_audio.json",
        inputs=("src",),
        params={"lufs": Param("float", "integrated loudness target", default=-16),
                "lra": Param("float", "loudness range target", minimum=0),
                "true_peak": Param("float", "true peak ceiling in dBTP", default=-1.5),
                "fade_seconds": Param("float", "fade at both ends", minimum=0)}),
    OpSpec(
        name="burn_subtitles", stage="graphics",
        description="Burn an SRT into the picture on exactly its cue frames.",
        executor="kinocut", target="subtitles",
        executor_reason="a non-ASCII SRT burned on exactly the cue frames with no leakage "
                        "before or after",
        evidence="docs/evidence/m2_burn.json",
        inputs=("src", "subtitle"),
        params={"style": Param("str", "Kinocut subtitle style preset")}),
    OpSpec(
        name="render_still", stage="graphics",
        description="Render ONE frame of a Remotion scene to a PNG - one look at the shot.",
        executor="remotion", target="render_still",
        executor_reason="the only renderer here that DRAWS: the pinned Remotion 4.0.539 drew the "
                        "514-frame M0 timeline within one frame, and one 1920x1080 still of "
                        "example-stat-ring cost 7.8 s cold / 8.3 s warm / 1.0 s cached "
                        "(measurements in docs/evidence/m55_remotion.json). No Kinocut row applies "
                        "- this op draws graphics, it does not edit media",
        evidence="docs/evidence/m55_remotion.json",
        inputs=("scene",), outputs=("still",),
        params={"composition": Param("str", "Remotion composition id (example-stat-ring, "
                                            "scene-<segment id>)", required=True),
                "frame": Param("int", "frame to draw", default=0, minimum=0),
                "portrait": Param("bool", "draw the 9:16 shape (1080x1920) instead of 16:9",
                                  default=False)}),
    OpSpec(
        name="render_range", stage="graphics",
        description="Render a frame range of a Remotion scene to an H.264 clip.",
        executor="remotion", target="render_range",
        executor_reason="same renderer as render_still, for the beats that only read in motion; "
                        "1 s (24 frames) at 1920x1080 cost 13.2 s cold / 9.6 s warm and decoded back "
                        "as 24 frames at 24/1 (docs/evidence/m55_remotion.json). M0 measured the "
                        "full-timeline render within one frame of the ffmpeg join",
        evidence="docs/evidence/m55_remotion.json",
        inputs=("scene",), outputs=("video",),
        params={"composition": Param("str", "Remotion composition id", required=True),
                "start": Param("int", "first frame of the range", default=0, minimum=0),
                "frames": Param("int", "how many frames, inclusive (24 = one second at 24 fps)",
                                default=24, minimum=1),
                "portrait": Param("bool", "render the 9:16 shape", default=False),
                "crf": Param("int", "H.264 quality (lower is better)", default=18, minimum=0)}),
    OpSpec(
        name="export_h264", stage="deliver",
        description="Final H.264/AAC encode: High profile, yuv420p, faststart.",
        executor="kinocut", target="export",
        executor_reason="H.264 High / yuv420p / AAC 48 kHz stereo / faststart with a clean "
                        "decode, 54 s for 60 s of 1080p24",
        evidence="docs/evidence/m2_export.json",
        inputs=("src",),
        params={"quality": Param("str", "Kinocut export quality preset"),
                "container": Param("str", "output container, e.g. mp4")}),
)

BY_NAME = {spec.name: spec for spec in OPS}




