"""Op registry: what the engine can do, what is installed, and which executor runs an op.

Three questions, three answers, no media touched:

  * `list_ops()` / `describe()` - discovery behind `tools list` and `tools describe`
  * `envelope(stage)`           - at most `MAX_ENVELOPE` op descriptions for ONE stage, so an
                                  agent never loads the whole catalogue into its context
  * `route(name, ...)`          - op -> executor, bound function, params checked, reason recorded

Routing rules (`.clinerules/01-architecture-and-constraints.md`, `docs/CAPABILITY_MATRIX.md`):

  * the executor for an op is DATA in `ops.py`, copied from the measured matrix;
  * a different executor needs an explicit `reason` (the string that goes into the manifest's
    `executor_reason`); the matrix decision is a project decision, not a runtime probe;
  * a missing executor raises `executor_not_installed` with the install step - never a silent
    fallback, and never the editor backend this repo removed in M5 (2026-10-30);
  * parameters are validated before routing returns, so a bad manifest never reaches a render.
"""
import dataclasses
import json
import os
import shutil
import subprocess

from cutwright import guard
from cutwright.engine import ops
from cutwright.engine.executors import ffmpeg, kinocut

MODULES = {"kinocut": kinocut, "ffmpeg": ffmpeg}   # "current" (recap helpers) is wired in M4
INSTALL = {
    "kinocut": "create .venvs\\kinocut and pip install kinocut==1.16.4 "
               "(docs/KINOCUT_FINDINGS.md section 1)",
    "ffmpeg": "install ffmpeg 7.x on PATH (Gyan build, assumption A5)",
}
REMOTION = os.path.join(guard.RECAP, "remotion", "package.json")
_INSTALLED = {}


class RegistryError(RuntimeError):
    """A rejected routing request: names the op, the code and the fix. Never transient."""

    def __init__(self, op, message="", code="registry_error", suggested=""):
        self.op = op
        self.code = code
        self.suggested = suggested
        self.message = message
        text = "registry %s rejected (code %s)" % (op, code)
        if message:
            text += ": %s" % message
        if suggested:
            text += " -> %s" % suggested
        super().__init__(text)

    def to_dict(self):
        return {"op": self.op, "code": self.code, "message": self.message,
                "suggested": self.suggested}


@dataclasses.dataclass(frozen=True)
class Route:
    """A resolved op: its spec, the executor that will run it, and the bound function."""
    spec: ops.OpSpec
    executor: str
    function: object
    reason: str
    params: dict = dataclasses.field(default_factory=dict)

    def to_dict(self):
        return {"op": self.spec.name, "executor": self.executor, "target": self.spec.target,
                "reason": self.reason, "evidence": self.spec.evidence,
                "outputs": list(self.spec.outputs), "params": dict(self.params)}


# ---------------------------------------------------------------- discovery
def list_ops(stage=None):
    """Cheap discovery: name, stage, executor and the one-line description."""
    if stage is not None and stage not in ops.STAGES:
        raise RegistryError("-", "unknown stage %r" % (stage,), code="unknown_stage",
                            suggested="one of: %s" % ", ".join(ops.STAGES))
    specs = ops.by_stage(stage) if stage else list(ops.OPS)
    return [{"name": spec.name, "stage": spec.stage, "executor": spec.executor,
             "description": spec.description} for spec in specs]


def evidence_status(spec):
    """Is the evidence file that justifies this op's executor present and usable?

    Existence + parse + a non-empty `rows`/`checks` list: `harness.write_evidence` writes those
    from a real run, so an empty file means the test never executed. PASS/FAIL itself lives in
    `docs/CAPABILITY_MATRIX.md` and is re-asserted by the M2 tests, not re-derived here.
    """
    path = os.path.join(guard.ROOT, spec.evidence.replace("/", os.sep))
    status = {"path": spec.evidence, "exists": os.path.isfile(path), "ok": False, "reason": ""}
    if not status["exists"]:
        status["reason"] = "evidence file is missing"
        return status
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        status["reason"] = "evidence is not readable JSON: %s" % exc
        return status
    rows = data.get("rows") or data.get("checks") or []
    if not rows:
        status["reason"] = "evidence records no rows"
        return status
    verdict = str(data.get("verdict", "")).upper()
    if verdict and verdict != "PASS":
        status["reason"] = "evidence verdict is %s" % verdict
        return status
    status["ok"] = True
    status["rows"] = len(rows)
    return status


def describe(name):
    """Everything an agent needs about one op, including whether its executor is installed."""
    spec = ops.get(name)
    if spec is None:
        raise RegistryError(name, "no such op", code="unknown_op",
                            suggested="tools list, or one of: %s" % ", ".join(ops.names()))
    out = spec.to_dict()
    out["defaults"] = spec.defaults()
    out["evidence_status"] = evidence_status(spec)
    out["executor_ready"] = _executor_ready(spec.executor)
    return out


def envelope(stage, limit=ops.MAX_ENVELOPE):
    """At most `limit` op descriptions for ONE stage - the only catalogue an agent should get."""
    if stage not in ops.STAGES:
        raise RegistryError("-", "unknown stage %r" % (stage,), code="unknown_stage",
                            suggested="one of: %s" % ", ".join(ops.STAGES))
    specs = ops.by_stage(stage)
    shown = specs[:max(1, int(limit))]
    return {
        "stage": stage,
        "count": len(specs),
        "returned": len(shown),
        "truncated": len(shown) < len(specs),
        "ops": [{"name": spec.name, "description": spec.description,
                 "executor": spec.executor, "inputs": list(spec.inputs),
                 "outputs": list(spec.outputs),
                 "required": [key for key, param in spec.params.items() if param.required],
                 "params": {key: param.type for key, param in spec.params.items()}}
                for spec in shown],
        "installed": {name: row["ok"] for name, row in installed().items()},
    }


def tools_report():
    """The shape `tools list` prints: op counts per stage plus the installed tool versions."""
    return {"ops": len(ops.OPS),
            "stages": {stage: len(ops.by_stage(stage)) for stage in ops.STAGES},
            "installed": installed()}


# ---------------------------------------------------------------- what is installed
def _version_of(argv, timeout=30):
    """First line of a `-version`-style call, or '' when the tool cannot run."""
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              stdin=subprocess.DEVNULL, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    lines = (proc.stdout or b"").decode("utf-8", "replace").splitlines()
    return lines[0].strip()[:120] if lines else ""


def installed(refresh=False, timeout=30):
    """kinocut venv, ffmpeg, ffprobe, node and Remotion: what this PC can actually run.

    Cached per process - each probe is a process start - and `refresh=True` re-probes. The
    executor's own `version()` is reused where it already exists, so one version is measured one
    way only.
    """
    if _INSTALLED and not refresh:
        return {name: dict(row) for name, row in _INSTALLED.items()}
    has_kinocut, has_ffmpeg = kinocut.available(), ffmpeg.available()
    ffprobe = shutil.which("ffprobe") or ""
    node = shutil.which("node") or ""
    remotion_version = ""
    if os.path.isfile(REMOTION):
        try:
            with open(REMOTION, "r", encoding="utf-8") as handle:
                deps = json.load(handle).get("dependencies") or {}
            remotion_version = str(deps.get("remotion", ""))
        except (OSError, ValueError):
            remotion_version = ""
    rows = {
        "kinocut": {"ok": has_kinocut, "path": kinocut.kino_exe() if has_kinocut else "",
                    "version": kinocut.version() if has_kinocut else "",
                    "install": INSTALL["kinocut"]},
        "ffmpeg": {"ok": has_ffmpeg, "path": ffmpeg.ffmpeg_exe() if has_ffmpeg else "",
                   "version": ffmpeg.version() if has_ffmpeg else "",
                   "install": INSTALL["ffmpeg"]},
        "ffprobe": {"ok": bool(ffprobe), "path": ffprobe,
                    "version": _version_of([ffprobe, "-version"], timeout) if ffprobe else "",
                    "install": "ships with ffmpeg"},
        "node": {"ok": bool(node), "path": node,
                 "version": _version_of([node, "--version"], timeout) if node else "",
                 "install": "install Node; do not touch the system install (assumption A6)"},
        "remotion": {"ok": bool(remotion_version),
                     "path": REMOTION if remotion_version else "",
                     "version": remotion_version,
                     "install": "npm install in recapstudio/remotion (Remotion stays 4.0.539)"},
    }
    _INSTALLED.update(rows)
    return {name: dict(row) for name, row in rows.items()}


def _executor_ready(executor):
    """{'ok', 'reason'} for one executor name. Never spawns a process (versions are cached)."""
    if executor == "kinocut":
        ok = kinocut.available()
    elif executor == "ffmpeg":
        ok = ffmpeg.available()
    elif executor == "current":
        ok = True          # recap helpers live in the repo; M4 moves them behind ops
    else:
        return {"ok": False, "reason": "unknown executor %r" % (executor,)}
    return {"ok": ok, "reason": "" if ok else INSTALL.get(executor, "install it")}


# ---------------------------------------------------------------- routing
def route(name, params=None, executor=None, reason=""):
    """Resolve one op to its executor and bound function. Raises RegistryError, never guesses.

    Default: the executor the matrix measured. An explicit `executor` is honoured only together
    with a `reason` (that string belongs in the manifest's `executor_reason`), and never as a
    silent fallback when the default happens to be missing.
    """
    spec = ops.get(name)
    if spec is None:
        raise RegistryError(name, "no such op", code="unknown_op",
                            suggested="tools list, or one of: %s" % ", ".join(ops.names()))
    checked = ops.validate_params(spec, params) if params is not None else {}
    chosen = executor or spec.executor
    if chosen != spec.executor and not reason:
        raise RegistryError(
            name, "executor %r overrides the matrix choice %r" % (chosen, spec.executor),
            code="executor_conflict",
            suggested="pass reason='...' and store it as executor_reason (matrix executor: %s "
                      "because %s)" % (spec.executor, spec.executor_reason))
    ready = _executor_ready(chosen)
    if not ready["ok"]:
        raise RegistryError(name, "%s cannot run this op here" % chosen,
                            code="executor_not_installed", suggested=ready["reason"])
    module = MODULES.get(chosen)
    if module is None:
        raise RegistryError(name, "executor %r is not wired into the engine yet" % chosen,
                            code="no_executor_module",
                            suggested="available: %s" % ", ".join(sorted(MODULES)))
    function = getattr(module, spec.target, None)
    if not callable(function):
        raise RegistryError(name, "executor %r has no callable %r" % (chosen, spec.target),
                            code="executor_missing_target",
                            suggested="check ops.OPS[...].target against the executor module")
    return Route(spec=spec, executor=chosen, function=function,
                 reason=reason or spec.executor_reason, params=checked)


