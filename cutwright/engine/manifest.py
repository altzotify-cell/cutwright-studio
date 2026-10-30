"""The execution manifest: load, validate, derive, run. One state machine for every run.

`manifest.json` is the EXECUTION layer (`segments.json` is creative, `timeline.json` is timing):
one record per step naming the op, the executor and why, its inputs, its outputs, its checks and
its status. This module is the only place that moves a step through
`pending | running | done | failed | skipped`, and the only place that decides whether a step may
be skipped on a resume:

    skip  <=>  status == done AND cache_key unchanged AND every output still matches its digest

`derive()` turns a manifest into a `Plan`: every reference resolved to an absolute path, every
param checked against `ops.py`, every cache key computed. Nothing in a Plan is guessed; a problem
is a `ManifestError` naming the step, the field and the fix.

Divided on purpose, so each rule has exactly one implementation:

  * measuring a rendered file (frame counts, decodes-clean) -> `validate.py`; a step's declared
    checks are carried here as `not_run` rows and filled by `validate.run_checks` after the step;
  * approval gates' files in `<run_dir>/approvals/` -> `gates.py`; this module only asks it;
  * `production_report.json` -> `report.py`; `run()` writes it at the end of every real run.


Hard rules encoded here (`.clinerules/01`): the executor of every op is the measured one from
`docs/CAPABILITY_MATRIX.md` -- a different executor needs a written `executor_reason`; nothing runs
for money (a step cost above the cap is refused); no AI-generated visual asset may enter a plan;
every output path is checked by `cutwright.guard` before anything is written.
"""
import dataclasses
import inspect
import json
import os

from cutwright import guard
from cutwright.engine import checkpoint, gates, ops, registry
from cutwright.engine import report as production_report
from cutwright.engine import validate as media_validate
from cutwright.engine.executors import ExecutorError

SCHEMA = 1
MAX_ATTEMPTS = 2                      # roadmap: 2 for transient failures, 1 for deterministic ones
RUNS_DIR = os.path.join(guard.OUT, "runs")
ALLOWED_ORIGINS = ("footage", "user_image", "code_graphic", "stock_licensed")
AUDIO_ONLY_EXTS = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aiff", ".txt", ".srt")
DEFAULT_FPS = 24.0


class ManifestError(ValueError):
    """A plan that cannot be trusted: names the step, the field, the code and the fix."""

    def __init__(self, message="", code="invalid_manifest", step="", suggested="", errors=()):
        self.code = code
        self.step = step
        self.suggested = suggested
        self.message = message
        self.errors = list(errors)
        text = "manifest rejected (code %s)" % code
        if step:
            text += " [step %s]" % step
        if message:
            text += ": %s" % message
        if suggested:
            text += " -> %s" % suggested
        super().__init__(text)

    def to_dict(self):
        return {"code": self.code, "step": self.step, "message": self.message,
                "suggested": self.suggested, "errors": list(self.errors)}


@dataclasses.dataclass
class Step:
    """One runnable step, fully derived: paths resolved, params checked, cache key computed."""
    id: str
    spec: object                 # ops.OpSpec
    params: dict                 # checked, defaults filled in
    inputs: dict                 # input name -> absolute path (or list of paths)
    outputs: dict                # output name -> absolute path
    executor: str
    executor_reason: str
    validation: list
    fps: float = DEFAULT_FPS
    cache_key: str = ""
    tool_version: str = ""
    index: int = 0

    def to_dict(self):
        return {"id": self.id, "op": self.spec.name, "executor": self.executor,
                "executor_reason": self.executor_reason,
                "inputs": _rel_dict(self.inputs), "outputs": _rel_dict(self.outputs),
                "params": dict(self.params), "cache_key": self.cache_key,
                "validation": [dict(row) for row in self.validation], "index": self.index}


@dataclasses.dataclass
class Plan:
    """Everything `run()` needs, with no unresolved reference left in it."""
    run_id: str
    run_dir: str
    manifest_path: str
    manifest_sha256: str
    fps: float
    size: list
    budget: dict
    gates: list
    assets: dict
    steps: list
    warnings: list = dataclasses.field(default_factory=list)

    def step(self, step_id):
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def to_dict(self):
        return {"run_id": self.run_id, "run_dir": guard.rel(self.run_dir),
                "manifest": self.manifest_path, "fps": self.fps, "size": list(self.size),
                "budget": dict(self.budget), "gates": [dict(g) for g in self.gates],
                "assets": {key: guard.rel(path) for key, path in self.assets.items()},
                "steps": [step.to_dict() for step in self.steps],
                "warnings": list(self.warnings)}

# ------------------------------------------------------------------ small helpers
def _rel_dict(values):
    """{name: path} -> {name: repo-relative path} for anything printed or recorded."""
    out = {}
    for name, value in (values or {}).items():
        if isinstance(value, (list, tuple)):
            out[name] = [guard.rel(str(item)) for item in value]
        else:
            out[name] = guard.rel(str(value))
    return out


def _apath(value):
    """Manifest path -> absolute path. Relative paths are repo-relative (the example's style)."""
    text = os.path.expanduser(str(value))
    if os.path.isabs(text):
        return os.path.normpath(text)
    return os.path.normpath(os.path.join(guard.ROOT, text))


# Public alias: `validate.provenance` and the demo generator resolve paths the same way a plan does,
# so there is exactly one rule for "where does a manifest path point".
resolve_path = _apath



def _error(errors, code, message, step="", suggested=""):
    errors.append({"code": code, "step": step, "message": message, "suggested": suggested})


def _warn(warnings, code, message, step=""):
    warnings.append({"code": code, "step": step, "message": message})


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_visual(path):
    """A picture or a video: the only kinds whose provenance the project constrains."""
    return os.path.splitext(str(path))[1].lower() not in AUDIO_ONLY_EXTS


def load(path):
    """Read a manifest file. Typed failures: a typo in a plan costs nothing."""
    full = _apath(path)
    if not os.path.isfile(full):
        raise ManifestError("no such manifest: %s" % guard.rel(full), code="not_found",
                            suggested="pass the path to a manifest.json "
                                      "(shape: docs/schemas/manifest.example.json)")
    try:
        with open(full, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except ValueError as exc:
        raise ManifestError("not valid JSON: %s" % exc, code="not_json",
                            suggested="fix the JSON syntax (a trailing comma is the usual cause)")
    except OSError as exc:
        raise ManifestError("cannot read it: %s" % exc, code="unreadable",
                            suggested="check the file permissions")
    if not isinstance(data, dict):
        raise ManifestError("a manifest is a JSON object", code="bad_schema",
                            suggested="wrap the steps in {\"schema\": 1, \"steps\": [...]}")
    return data


def manifest_sha256(path):
    """Hash of the manifest file itself, so a checkpoint records which plan it belongs to."""
    full = _apath(path)
    return guard.sha256_file(full) if os.path.isfile(full) else ""


def _assets(manifest, allowed, strict_files, errors, warnings):
    """id -> absolute path, plus a per-asset check of origin and existence.

    Origin is checked for VISUAL assets only: the constraint set is about pictures and video
    (no AI-generated frames), while `user_audio` is a legitimate origin for a voice track.
    """
    paths = {}
    rows = manifest.get("assets") or []
    if not isinstance(rows, list):
        _error(errors, "bad_assets", "'assets' is a list of {id, path, origin}")
        return paths
    for row in rows:
        if not isinstance(row, dict) or not row.get("id") or not row.get("path"):
            _error(errors, "bad_asset", "every asset needs an id and a path")
            continue
        asset_id = str(row["id"])
        if asset_id in paths:
            _error(errors, "duplicate_asset", "asset id %r is used twice" % asset_id)
            continue
        path = _apath(row["path"])
        paths[asset_id] = path
        origin = str(row.get("origin") or "")
        if not origin:
            _error(errors, "asset_origin", "asset %r has no origin" % asset_id,
                   suggested="one of: %s" % ", ".join(ALLOWED_ORIGINS))
        elif _is_visual(path) and origin not in allowed:
            _error(errors, "asset_origin",
                   "asset %r is visual and its origin %r is not allowed" % (asset_id, origin),
                   suggested="use one of: %s (never an AI-generated frame)"
                             % ", ".join(allowed))
        if not os.path.isfile(path):
            message = "asset %r is missing on disk: %s" % (asset_id, guard.rel(path))
            if strict_files:
                _error(errors, "asset_missing", message,
                       suggested="drop the asset or fix its path before running")
            else:
                _warn(warnings, "asset_missing", message)
    return paths




def _resolve(value, step_id, assets, produced, declared, errors, warnings):
    """One input value -> absolute path, or None when it cannot be resolved.

    Two reference forms, both resolved here so no later code sees an '@': `@asset.<id>` and
    `@<step>.<output>`. A reference to a LATER step is a forward reference and is refused: the
    engine runs steps in manifest order, so it would read a file that does not exist yet.
    """
    if isinstance(value, (list, tuple)):
        if not value:
            _error(errors, "bad_input", "the input is an empty list", step=step_id,
                   suggested="give at least one path or reference")
            return None
        rows = [_resolve(item, step_id, assets, produced, declared, errors, warnings)
                for item in value]
        return None if any(item is None for item in rows) else rows
    if not isinstance(value, str) or not value.strip():
        _error(errors, "bad_input", "expected a path or an @reference, got %r" % (value,),
               step=step_id)
        return None
    if value.startswith("@"):
        head, _, tail = value[1:].partition(".")
        if head == "asset":
            if tail not in assets:
                _error(errors, "unknown_ref", "no asset %r for %s" % (tail, value), step=step_id,
                       suggested="declare it under 'assets', or check the spelling")
                return None
            return assets[tail]
        if head in declared and head not in produced:
            _error(errors, "forward_ref", "%s reads a step that has not run yet" % value,
                   step=step_id, suggested="move %r before %r, or read the asset directly"
                   % (head, step_id))
            return None
        outputs = produced.get(head) or {}
        if tail not in outputs:
            _error(errors, "unknown_ref", "step %r has no output %r" % (head, tail),
                   step=step_id, suggested="a step's outputs are named in its 'outputs' block")
            return None
        return outputs[tail]
    path = _apath(value)
    if not os.path.isfile(path):
        _warn(warnings, "input_missing", "input %s does not exist yet" % guard.rel(path),
              step=step_id)
    return path


def _outputs(row, spec, step_id, assets, seen, errors):
    """{output name: absolute path} for one step, refused if it is unsafe or already claimed."""
    given = row.get("outputs") or {}
    if not isinstance(given, dict):
        _error(errors, "bad_outputs", "'outputs' is a mapping of name -> path", step=step_id)
        return None
    missing = [name for name in spec.outputs if name not in given]
    unknown = [name for name in given if name not in spec.outputs]
    if missing:
        _error(errors, "missing_output", "op %s needs output(s) %s"
               % (spec.name, ", ".join(missing)), step=step_id,
               suggested="the op produces: %s" % ", ".join(spec.outputs))
    if unknown:
        _error(errors, "unknown_output", "op %s has no output(s) %s"
               % (spec.name, ", ".join(unknown)), step=step_id,
               suggested="the op produces: %s" % ", ".join(spec.outputs))
    if len(spec.outputs) != 1:
        _error(errors, "multi_output_unsupported",
               "every executor today writes exactly one file per call", step=step_id)
    if missing or unknown:
        return None
    outputs, ok = {}, True
    for name in spec.outputs:
        path = _apath(given[name])
        try:
            guard.assert_writable(path)
        except guard.GuardError as exc:
            _error(errors, "unsafe_output", str(exc), step=step_id,
                   suggested="write inside the Cutwright folder, e.g. "
                             "out/runs/<run>/work/<step>.mp4")
            ok = False
            continue
        key = os.path.normcase(path)
        if key in seen:
            _error(errors, "output_collision", "%s is already written by %r"
                   % (guard.rel(path), seen[key]), step=step_id,
                   suggested="give every step its own output file")
            ok = False
        if key in assets:
            _error(errors, "output_overwrites_asset", "%s is a declared asset" % guard.rel(path),
                   step=step_id, suggested="never write over an input; use a work path")
            ok = False
        seen[key] = step_id
        outputs[name] = path
    return outputs if ok else None


def _steps(manifest, assets, cap_usd, fps, versions, strict_files, errors, warnings):
    """Derive every step in manifest order. Returns (steps, {step id: outputs}, total cost)."""
    rows = manifest.get("steps")
    if not isinstance(rows, list) or not rows:
        _error(errors, "no_steps", "'steps' must be a non-empty list",
               suggested="one entry per operation, in the order they must run")
        return [], {}, 0.0
    declared = [str(row.get("id") or "") for row in rows if isinstance(row, dict)]
    seen_outputs, produced, steps, ids = {}, {}, [], {}
    total_cost = 0.0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _error(errors, "bad_step", "step %d is not an object" % index)
            continue
        step_id = str(row.get("id") or "").strip()
        if not step_id:
            _error(errors, "missing_step_id", "step %d has no id" % index)
            continue
        if step_id in ids:
            _error(errors, "duplicate_step", "step id %r is used twice" % step_id, step=step_id)
            continue
        before = len(errors)
        ids[step_id] = index
        spec = ops.get(str(row.get("op") or ""))
        if spec is None:
            _error(errors, "unknown_op", "op %r is not in the registry" % (row.get("op"),),
                   step=step_id, suggested="tools list --stage edit, or one of: %s"
                                            % ", ".join(ops.names()))
            continue
        try:
            params = ops.validate_params(spec, row.get("params") or {})
        except ops.OpError as exc:
            _error(errors, "invalid_params", str(exc), step=step_id,
                   suggested=exc.to_dict().get("suggested") or "")
            continue
        given = row.get("inputs") or {}
        if not isinstance(given, dict):
            _error(errors, "bad_inputs", "'inputs' is a mapping of name -> path or @ref",
                   step=step_id)
            continue
        missing = [name for name in spec.inputs if name not in given]
        unknown = [name for name in given if name not in spec.inputs]
        if missing:
            _error(errors, "missing_input", "op %s needs input(s) %s"
                   % (spec.name, ", ".join(missing)), step=step_id,
                   suggested="the op takes: %s" % ", ".join(spec.inputs))
        if unknown:
            _error(errors, "unknown_input", "op %s has no input(s) %s"
                   % (spec.name, ", ".join(unknown)), step=step_id,
                   suggested="the op takes: %s" % ", ".join(spec.inputs))
        if missing or unknown:
            continue
        inputs = {}
        for name in spec.inputs:
            inputs[name] = _resolve(given[name], step_id, assets, produced, declared,
                                    errors, warnings)
        if any(value is None for value in inputs.values()):
            continue

        asset_paths = set(os.path.normcase(path) for path in assets.values())
        outputs = _outputs(row, spec, step_id, asset_paths, seen_outputs, errors)
        if outputs is None:
            continue
        executor = str(row.get("executor") or spec.executor)
        reason = str(row.get("executor_reason") or "")
        if executor != spec.executor and not reason:
            _error(errors, "executor_conflict",
                   "executor %r overrides the measured %r without a reason"
                   % (executor, spec.executor), step=step_id,
                   suggested="add executor_reason, or drop the executor (matrix: %s because %s)"
                             % (spec.executor, spec.executor_reason))
        elif executor != spec.executor:
            _warn(warnings, "executor_override", "executor %r instead of the matrix's %r: %s"
                  % (executor, spec.executor, reason), step=step_id)
        if executor not in registry.MODULES:
            _error(errors, "unknown_executor", "executor %r is not wired into the engine"
                   % executor, step=step_id,
                   suggested="available: %s" % ", ".join(sorted(registry.MODULES)))
            continue
        cost = row.get("cost_usd", 0.0)
        if not _is_number(cost) or cost < 0:
            _error(errors, "bad_cost", "cost_usd must be a number >= 0", step=step_id)
        elif cost > cap_usd:
            _error(errors, "budget_exceeded",
                   "$%s for this step exceeds the $%s cap" % (cost, cap_usd), step=step_id,
                   suggested="the project is free-first: set cost_usd to 0, or raise the cap "
                             "only with the owner's approval")
        else:
            total_cost += float(cost)
        status = str(row.get("status") or checkpoint.PENDING)
        if status not in checkpoint.STATUSES:
            _error(errors, "bad_status", "status %r is not one of %s"
                   % (status, ", ".join(checkpoint.STATUSES)), step=step_id,
                   suggested="a manifest declares 'pending'; the checkpoint owns the rest")
        checks = []
        for check in (row.get("validation") or []):
            if not isinstance(check, dict) or not check.get("check"):
                _error(errors, "bad_validation", "each validation entry needs a 'check'",
                       step=step_id)
                continue
            checks.append({"check": str(check["check"]), "expect": check.get("expect"),
                           "result": None, "status": "not_run"})
        digests = checkpoint.input_digests(inputs)
        if strict_files:
            planned = set(os.path.normcase(path) for outputs in produced.values()
                          for path in outputs.values())
            for entry in digests:
                if entry["digest"]:
                    continue
                if os.path.normcase(_apath(entry["path"])) in planned:
                    continue        # an earlier step in THIS plan produces it: not missing
                _error(errors, "input_missing", "input %r is missing: %s"
                       % (entry["name"], entry["path"]), step=step_id,
                       suggested="run the step that produces it, or fix the path")
        if len(errors) > before:
            continue
        key = checkpoint.cache_key(spec.name, params, digests, executor,
                                   str((versions or {}).get(executor) or ""))
        produced[step_id] = outputs
        steps.append(Step(id=step_id, spec=spec, params=params, inputs=inputs, outputs=outputs,
                          executor=executor, executor_reason=reason or spec.executor_reason,
                          validation=checks, fps=float(fps), cache_key=key,
                          tool_version=str((versions or {}).get(executor) or ""), index=index))
    return steps, produced, total_cost



def _gates(manifest, step_ids, errors):
    """Approval gates as data: id, the step it sits in front of, and whether it is approved."""
    rows = manifest.get("gates") or []
    if not isinstance(rows, list):
        _error(errors, "bad_gates", "'gates' is a list of {id, before_step, approved}")
        return []
    gates = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            _error(errors, "bad_gate", "every gate needs an id and a before_step")
            continue
        gate_id = str(row["id"])
        before = str(row.get("before_step") or "")
        if before not in step_ids:
            _error(errors, "unknown_gate_step", "gate %r sits before unknown step %r"
                   % (gate_id, before), suggested="before_step must name a step id")
            continue
        gates.append({"id": gate_id, "before_step": before,
                      "approved": bool(row.get("approved"))})
    return gates


def _run_dir(manifest, run_id, override, errors):
    """Where the run folder lives: the override, the manifest's run_dir, or out/runs/<run_id>."""
    raw = override or manifest.get("run_dir") or os.path.join(RUNS_DIR, run_id or "run")
    path = _apath(raw)
    try:
        guard.assert_writable(path)
    except guard.GuardError as exc:
        _error(errors, "unsafe_run_dir", str(exc),
               suggested="keep runs inside the fork, e.g. out/runs/<run_id>")
    return path


def _prepare(manifest, manifest_path="", strict_files=False, versions=None, run_dir=None):
    """One pass over a manifest: header, assets, steps, gates, run folder.

    Never raises: it collects every problem (with its step) so one call reports all of them, the
    same reason `ops.validate_params` checks params before a render rather than during one.
    """
    errors, warnings = [], []
    if not isinstance(manifest, dict):
        _error(errors, "bad_schema", "a manifest is a JSON object")
        manifest = {}
    if manifest.get("schema") != SCHEMA:
        _error(errors, "bad_schema", "schema must be %d, got %r"
               % (SCHEMA, manifest.get("schema")),
               suggested="start from docs/schemas/manifest.example.json")
    run_id = str(manifest.get("run_id") or "").strip()
    if not run_id:
        _error(errors, "missing_run_id", "a manifest needs a run_id",
               suggested='"run_id": "demo-0001" (it names the run folder and the checkpoint)')
    fps = manifest.get("fps", DEFAULT_FPS)
    if not _is_number(fps) or fps <= 0:
        _error(errors, "bad_fps", "fps must be a positive number, got %r" % (fps,))
        fps = DEFAULT_FPS
    size = manifest.get("size") or []
    if size and (not isinstance(size, list) or len(size) != 2
                 or not all(_is_number(value) and value > 0 for value in size)):
        _error(errors, "bad_size", "'size' is [width, height] in pixels", suggested="[1920, 1080]")
        size = []
    budget = manifest.get("budget") or {"mode": "cap", "cap_usd": 0.0}
    if not isinstance(budget, dict):
        _error(errors, "bad_budget", "'budget' is an object with mode and cap_usd")
        budget = {"mode": "cap", "cap_usd": 0.0}
    cap = budget.get("cap_usd", 0.0)
    if not _is_number(cap) or cap < 0:
        _error(errors, "bad_budget", "budget.cap_usd must be a number >= 0", suggested="0.0")
        cap = 0.0
    constraints = manifest.get("constraints") or {}
    if not isinstance(constraints, dict):
        _error(errors, "bad_constraints", "'constraints' is an object")
        constraints = {}
    if constraints.get("ai_generated_images"):
        _error(errors, "ai_assets_forbidden", "constraints.ai_generated_images must be false",
               suggested="no AI-generated images or video, ever (.clinerules/01)")
    elif "ai_generated_images" not in constraints:
        _warn(warnings, "constraints_not_declared",
              "the manifest does not declare ai_generated_images: false; the rule still applies")
    allowed = tuple(constraints.get("allowed_asset_origins") or ALLOWED_ORIGINS)
    widened = [origin for origin in allowed if origin not in ALLOWED_ORIGINS]
    if widened:
        _error(errors, "asset_origin_policy", "origins %s are not allowed" % ", ".join(widened),
               suggested="use one of: %s" % ", ".join(ALLOWED_ORIGINS))
        allowed = tuple(origin for origin in allowed if origin in ALLOWED_ORIGINS)
    assets = _assets(manifest, allowed, strict_files, errors, warnings)
    steps, _produced, total_cost = _steps(manifest, assets, cap, fps, versions, strict_files,
                                          errors, warnings)
    declared_ids = set(str(row.get("id") or "") for row in (manifest.get("steps") or [])
                       if isinstance(row, dict))
    gates = _gates(manifest, declared_ids, errors)
    folder = _run_dir(manifest, run_id, run_dir, errors)
    plan = None
    if not errors:
        plan = Plan(run_id=run_id, run_dir=folder, manifest_path=guard.rel(_apath(manifest_path))
                    if manifest_path else "", manifest_sha256=manifest_sha256(manifest_path)
                    if manifest_path else "", fps=float(fps), size=list(size),
                    budget={"mode": str(budget.get("mode") or "cap"), "cap_usd": float(cap),
                            "total_usd": float(total_cost)},
                    gates=gates, assets=dict(assets), steps=steps, warnings=list(warnings))
    return {"ok": not errors, "plan": plan, "errors": errors, "warnings": warnings,
            "run_id": run_id, "run_dir": guard.rel(folder), "steps": len(steps),
            "cost_usd": round(float(total_cost), 6)}



# ------------------------------------------------------------------ the public steps
def validate(manifest, manifest_path="", versions=None, strict_files=False):
    """Pre-render check of a plan, as data: {ok, errors, warnings, run_dir, steps, cost_usd}.

    `strict_files=False` treats media that does not exist yet as a warning, so a plan can be
    validated before its footage is produced; `run()` derives with `strict_files=True`.
    """
    report = _prepare(manifest, manifest_path=manifest_path, strict_files=strict_files,
                      versions=versions)
    report.pop("plan", None)
    return report


def tool_versions():
    """executor -> version string, from `registry.installed()` (one probe per process, cached).

    The version is part of every cache key: upgrading Kinocut or ffmpeg invalidates cached steps
    instead of silently reusing output produced by a different binary.
    """
    try:
        rows = registry.installed()
    except (OSError, ValueError, KeyError):      # a probe may never break a run
        return {}
    return {name: str(row.get("version") or "")
            for name, row in rows.items() if row.get("ok")}


def derive(manifest, manifest_path="", versions=None, run_dir=None, strict_files=True):
    """Manifest -> Plan. Raises ManifestError on the first problem; `validate()` lists them all."""
    report = _prepare(manifest, manifest_path=manifest_path, versions=versions,
                      run_dir=run_dir, strict_files=strict_files)
    if not report["ok"]:
        first = report["errors"][0]
        raise ManifestError(first["message"], code=first["code"], step=first["step"],
                            suggested=first["suggested"], errors=report["errors"])
    return report["plan"]


def load_plan(path, versions=None, run_dir=None, strict_files=True):
    """`load()` + `derive()` in one call: what `run <manifest>` does before touching any media."""
    return derive(load(path), manifest_path=path, versions=versions, run_dir=run_dir,
                  strict_files=strict_files)


def _call(step, overwrite=False):
    """Run one step: route the op, translate its params, call the executor with typed arguments.

    kwarg filtering against the real signature is the last guard: a param that the executor does
    not take (a default, `accurate` on ffmpeg) is dropped here instead of raising a TypeError
    halfway through a render.
    """
    route = registry.route(step.spec.name, params=step.params, executor=step.executor,
                           reason=step.executor_reason
                           if step.executor != step.spec.executor else "")
    kwargs = ops.executor_kwargs(step.spec, route.params, fps=step.fps)
    accepted = inspect.signature(route.function).parameters
    kwargs = {key: value for key, value in kwargs.items() if key in accepted}
    if overwrite and "overwrite" in accepted:
        kwargs["overwrite"] = True
    arguments = [step.inputs[name] for name in step.spec.inputs]
    target = step.outputs[step.spec.outputs[0]]
    guard.ensure_dir(os.path.dirname(target))
    return route.function(*arguments, target, **kwargs)


def step_key(step):
    """The cache key of a step RIGHT NOW, with its inputs' current digests.

    Computed when the step is about to run, not when the plan was derived: a step's input is often
    the output of the step before it, so its digest only exists once that step has run. Deriving a
    key too early would make every chained step look changed on the next resume.
    """
    return checkpoint.cache_key(step.spec.name, step.params,
                                checkpoint.input_digests(step.inputs), step.executor,
                                step.tool_version)


def _blocking_gate(plan, step_id):
    """The id of an unapproved gate in front of `step_id`, or ''.

    `gates.py` owns the decision, because a gate can be opened two ways: the manifest's own
    `approved: true`, or an approval FILE in `<run_dir>/approvals/` written by `approve`. A step
    behind a closed gate is skipped and the run stops -- never silently executed.
    """
    return gates.blocking(plan.gates or [], plan.run_dir, before_step=step_id)



def _execute(plan, state, step, row, report, key):
    """Run one step with M3's retry policy: 2 attempts for a transient failure, 1 for anything else.

    `attempts` accumulates across runs, so a step that already burned its attempts and then failed
    deterministically is visibly a repeat rather than a mystery. A stale output from a killed run
    is overwritten only from the second attempt onwards -- never on a first, clean attempt.
    """
    prior = int((state.get("steps", {}).get(step.id) or {}).get("attempts") or 0)
    attempts, error, finished = 0, None, None
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        checkpoint.record(state, step.id, status=checkpoint.RUNNING, attempts=prior + attempts,
                          started=checkpoint.now(), cache_key=key,
                          executor=step.executor, op=step.spec.name,
                          outputs=_rel_dict(step.outputs), error={})
        checkpoint.save(plan.run_dir, state)
        try:
            finished = _call(step, overwrite=prior + attempts > 1)
            break
        except ExecutorError as exc:
            error = exc.to_dict()
            error["step"] = step.id
            if not exc.transient or attempts >= MAX_ATTEMPTS:
                break
        except (ops.OpError, registry.RegistryError, guard.GuardError) as exc:
            error = {"step": step.id, "code": getattr(exc, "code", "error"),
                     "type": type(exc).__name__, "message": str(exc),
                     "suggested": getattr(exc, "suggested", ""), "transient": False}
            break
    if finished is None:
        code = (error or {}).get("code", "failed")
        checkpoint.record(state, step.id, status=checkpoint.FAILED, error=error or {},
                          attempts=prior + attempts, finished=checkpoint.now(),
                          reason="%s failed (%s)" % (step.spec.name, code))
        checkpoint.save(plan.run_dir, state)
        row.update(status=checkpoint.FAILED, attempts=prior + attempts, error=error,
                   reason="%s failed (%s)" % (step.spec.name, code))
        report["stopped"] = "step %r failed (%s): %s" % (step.id, code,
                                                        (error or {}).get("message", ""))
        return row
    seconds = float(getattr(finished, "seconds", 0.0) or 0.0)
    # The step's declared checks are measured on the file it just wrote. A failing check fails the
    # step; it is deterministic, so the retry loop above never sees it (no second encode).
    checks = media_validate.run_checks(step, finished)
    failed = media_validate.failures(checks)
    if failed:
        message = "; ".join("%s: %s" % (item["check"], item.get("message") or "failed")
                            for item in failed)
        error = {"step": step.id, "code": "validation_failed", "type": "ValidationError",
                 "message": message, "transient": False,
                 "suggested": "measure the output again; fix the step or the expected value "
                              "(a failed check is never retried)"}
        checkpoint.record(state, step.id, status=checkpoint.FAILED, attempts=prior + attempts,
                          finished=checkpoint.now(), seconds=round(seconds, 3),
                          validation=checks, error=error,
                          reason="%s failed validation" % step.spec.name)
        checkpoint.save(plan.run_dir, state)
        row.update(status=checkpoint.FAILED, attempts=prior + attempts, error=error,
                   validation=checks)
        report["stopped"] = "step %r failed validation: %s" % (step.id, message)
        return row
    digests = {name: checkpoint.digest_file(path) for name, path in step.outputs.items()}
    checkpoint.record(state, step.id, status=checkpoint.DONE, attempts=prior + attempts,
                      finished=checkpoint.now(), seconds=round(seconds, 3),
                      output_digests=digests, cache_key=key, error={}, reason="",
                      validation=checks,
                      result=(finished.to_dict() if hasattr(finished, "to_dict") else {}))
    checkpoint.save(plan.run_dir, state)
    row.update(status=checkpoint.DONE, attempts=prior + attempts, seconds=round(seconds, 3),
               validation=checks, warnings=list(getattr(finished, "warnings", []) or []))
    return row



def run(plan, resume=True, only=None, dry_run=False):
    """Execute a plan in manifest order, checkpointing after every step.

    `resume=True` (default) skips a step only when `checkpoint.step_cached` proves it reusable.
    `only` restricts which steps execute (the rest are reported `skipped`, not selected).
    `dry_run` reports what would run and writes nothing at all -- not even the run folder.
    """
    report = {"ok": True, "run_id": plan.run_id, "run_dir": guard.rel(plan.run_dir),
              "dry_run": bool(dry_run), "steps": [], "stopped": "", "cursor": {}}
    selected = set(only or [])
    state = None
    if not dry_run:
        guard.ensure_dir(plan.run_dir)
        state = checkpoint.load(plan.run_dir, default=checkpoint.new_state(plan.run_id))
        state["run_id"] = plan.run_id
        state["manifest"] = plan.manifest_path
        state["manifest_sha256"] = plan.manifest_sha256
        state["order"] = [step.id for step in plan.steps]
    for step in plan.steps:
        row = {"id": step.id, "op": step.spec.name, "executor": step.executor, "status": ""}
        if selected and step.id not in selected:
            row.update(status=checkpoint.SKIPPED, reason="not selected by only")
            report["steps"].append(row)
            continue
        gate = _blocking_gate(plan, step.id)
        if gate:
            row.update(status=checkpoint.SKIPPED, reason="waiting for gate %s" % gate)
            report["steps"].append(row)
            report["ok"] = False
            report["stopped"] = "gate %r is not approved" % gate
            if state is not None:
                checkpoint.record(state, step.id, status=checkpoint.SKIPPED, reason=row["reason"])
                checkpoint.save(plan.run_dir, state)
            break
        if state is not None and resume:
            key = step_key(step)
            skip, why = checkpoint.step_cached(state, step.id, key, step.outputs)
            if skip:
                # The STEP stays `done` -- this RUN skipped it. Recording `skipped` here would
                # overwrite the fact that the step is finished, and the next resume would then
                # re-run it (step_cached requires status == done).
                row.update(status=checkpoint.SKIPPED,
                           reason="cached (cache key unchanged, outputs intact)")
                checkpoint.record(state, step.id, status=checkpoint.DONE,
                                  reason=row["reason"], cached_at=checkpoint.now(),
                                  cache_key=key)
                checkpoint.save(plan.run_dir, state)
                report["steps"].append(row)
                continue
            row["reason"] = why
        if dry_run:
            row.update(status="would_run", reason="dry run: nothing executed")
            report["steps"].append(row)
            continue
        _execute(plan, state, step, row, report, step_key(step))
        report["steps"].append(row)
        if row["status"] == checkpoint.FAILED:
            report["ok"] = False
            break
    if state is not None:
        report["cursor"] = checkpoint.cursor(state)
        report["checkpoint"] = guard.rel(checkpoint.state_path(plan.run_dir))
        written = production_report.write(plan.run_dir,
                                          production_report.build(plan, report, state))
        report["production_report"] = guard.rel(written)
    return report


def resume(run_dir, versions=None, only=None):
    """Continue a run from its checkpoint. Returns the same report shape as `run()`.

    The checkpoint records the manifest by its REPO-RELATIVE path (never an absolute user path), so
    a resume works from any working directory and after the folder moved inside the fork. A run
    whose manifest no longer exists is refused instead of being resumed against a guess.
    """
    folder = _apath(run_dir)
    state = checkpoint.load(folder)
    path = str(state.get("manifest") or "")
    if not path or not os.path.isfile(_apath(path)):
        raise ManifestError("this run does not name a manifest that still exists: %r" % (path,),
                            code="no_manifest",
                            suggested="run the manifest again with `run <manifest>`, or restore %s"
                                      % (path or "it"))
    plan = load_plan(path, versions=versions, run_dir=folder, strict_files=True)
    return run(plan, resume=True, only=only)


def status(run_dir):
    """What `status` prints: the cursor, every step, and whether its outputs still match.

    A done step whose output was deleted or re-encoded is reported with `stale`, so the next
    `resume` re-runs it instead of trusting a file that no longer matches the record.
    """
    folder = _apath(run_dir)
    state = checkpoint.load(folder)
    order = list(state.get("order") or [])
    order += [step_id for step_id in (state.get("steps") or {}) if step_id not in order]
    rows = []
    for step_id in order:
        entry = (state.get("steps") or {}).get(step_id) or {}
        row = {"id": step_id, "status": entry.get("status") or checkpoint.PENDING,
               "attempts": int(entry.get("attempts") or 0),
               "executor": entry.get("executor", ""), "op": entry.get("op", ""),
               "seconds": entry.get("seconds", 0.0), "outputs": entry.get("outputs") or {},
               "reason": entry.get("reason", ""), "stale": ""}
        if entry.get("status") == checkpoint.DONE:
            ok, why = checkpoint.outputs_intact(entry.get("outputs"),
                                               entry.get("output_digests") or {})
            row["stale"] = "" if ok else why
        if entry.get("error"):
            row["error"] = entry["error"]
        rows.append(row)
    return {"run_id": state.get("run_id", ""), "run_dir": guard.rel(folder),
            "updated": state.get("updated", ""), "checkpoint": guard.rel(checkpoint.state_path(folder)),
            "cursor": checkpoint.cursor(state), "steps": rows,
            "history": (state.get("history") or [])[-10:]}
