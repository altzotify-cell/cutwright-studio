"""Run state that survives a kill: one JSON checkpoint per run, written temp-then-replace.

Why a checkpoint and not "just look at the files": a render is minutes of work, and the engine is
run by an agent that may be interrupted. So every finished step is committed to disk immediately:

  * `write_atomic()` writes a temp file in the SAME folder and `os.replace()`s it over the
    checkpoint. A kill mid-write therefore leaves either the old state or the new one, never a
    half-written JSON file (which would silently lose earlier steps).
  * `load()` refuses to trust a checkpoint it cannot parse, whose schema is not this one, or whose
    `steps` is not a mapping: it raises CheckpointError(code="corrupted") and the caller starts
    over rather than resuming from garbage.
  * `cache_key()` is the resume decision: a hash of the step's op + params + executor version +
    the identity of every input file. Same key + outputs still present with the stored digest ->
    the step is skipped. Different key -> it runs again, because something it depends on changed.
  * `cursor()` is what `status`/`resume` report: the next step to run, and what is done/pending.

Writes go through `cutwright.guard`, so state can never land in an original project folder.

Note on hashing: files up to HASH_LIMIT are sha256'd; bigger media is identified by size + mtime
(`guard.file_sig`) because hashing a multi-GB film would cost minutes and prove nothing new -- the
same rule `guard.py` already documents for provenance.
"""
import hashlib
import json
import os
import tempfile
import time

from cutwright import guard

SCHEMA = 1
STATE_FILE = "checkpoint.json"
HASH_LIMIT = 64 << 20          # 64 MiB: hash below, size+mtime above
HISTORY_LIMIT = 200            # keep the tail of the event log, not an unbounded file

PENDING, RUNNING, DONE, FAILED, SKIPPED = "pending", "running", "done", "failed", "skipped"
STATUSES = (PENDING, RUNNING, DONE, FAILED, SKIPPED)


class CheckpointError(RuntimeError):
    """A state file that cannot be written, or must not be trusted. Never transient."""

    def __init__(self, path, message="", code="checkpoint_error", suggested=""):
        self.path = path
        self.code = code
        self.suggested = suggested
        self.message = message
        text = "checkpoint %s (code %s)" % (guard.rel(path) if path else "-", code)
        if message:
            text += ": %s" % message
        if suggested:
            text += " -> %s" % suggested
        super().__init__(text)

    def to_dict(self):
        return {"path": self.path, "code": self.code, "message": self.message,
                "suggested": self.suggested}


def now():
    """UTC timestamp, second resolution, the format the rest of the docs use."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def state_path(run_dir):
    """Absolute path of the checkpoint inside one run folder."""
    return os.path.abspath(os.path.join(run_dir, STATE_FILE))

def canonical(obj):
    """Stable JSON text for hashing: sorted keys, no spaces, no platform line endings."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def write_atomic(path, data):
    """`data` as JSON at `path`, via a temp file in the same folder + os.replace.

    Same-folder temp file matters on Windows: os.replace() is only atomic within a volume, and
    the temp name is unique per call so two runs cannot collide on it.
    """
    target = guard.assert_writable(path)
    parent = os.path.dirname(target)
    guard.ensure_dir(parent)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                        dir=parent, prefix=".tmp-state-", suffix=".json",
                                        delete=False)
    tmp = handle.name
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise CheckpointError(target, "could not write the checkpoint: %s" % exc,
                              code="write_failed",
                              suggested="check free space and that the folder is writable")
    return target


def _checked(state, path):
    """The state, or CheckpointError -- never a partially trusted dict."""
    if not isinstance(state, dict):
        raise CheckpointError(path, "state is not a JSON object", code="corrupted",
                              suggested="delete the checkpoint and re-run (steps re-execute)")
    if state.get("schema") != SCHEMA:
        raise CheckpointError(path, "schema %r, this engine writes %d"
                              % (state.get("schema"), SCHEMA), code="schema_mismatch",
                              suggested="delete the checkpoint, or read it with the engine "
                                        "version that wrote it")
    if not isinstance(state.get("steps"), dict):
        raise CheckpointError(path, "'steps' is not a mapping", code="corrupted",
                              suggested="delete the checkpoint and re-run")
    return state


def load(run_dir, default=None):
    """Read the checkpoint of `run_dir`. Missing -> `default`; unreadable -> CheckpointError."""
    path = state_path(run_dir)
    if not os.path.isfile(path):
        if default is not None:
            return default
        raise CheckpointError(path, "no checkpoint in this run folder", code="not_found",
                              suggested="start the run (manifest.run) before asking for status")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except ValueError as exc:
        raise CheckpointError(path, "not valid JSON: %s" % exc, code="corrupted",
                              suggested="delete the checkpoint and re-run; done steps re-execute")
    except OSError as exc:
        raise CheckpointError(path, "cannot read it: %s" % exc, code="unreadable",
                              suggested="check the file permissions")
    return _checked(state, path)


def save(run_dir, state):
    """Persist `state` for `run_dir`, stamping `updated`. Returns the checkpoint path."""
    state["updated"] = now()
    state["cursor"] = cursor(state)
    return write_atomic(state_path(run_dir), _checked(state, state_path(run_dir)))

# ------------------------------------------------------------------ state lifecycle
def new_state(run_id, manifest_path="", manifest_sha256="", order=()):
    """A fresh checkpoint for one run. `order` is the step order, so the cursor can say 'next'."""
    stamp = now()
    return {"schema": SCHEMA, "run_id": run_id, "manifest": manifest_path,
            "manifest_sha256": manifest_sha256, "created": stamp, "updated": stamp,
            "order": list(order), "steps": {}, "cursor": {}, "history": []}


def cursor(state):
    """The resume cursor: which step runs next and how the rest stand.

    `order` comes from the manifest (state["order"]); a step recorded before the order was known
    is still listed, after the ordered ones, so nothing silently disappears from `status`.
    """
    steps = state.get("steps") or {}
    order = list(state.get("order") or [])
    order += [step_id for step_id in steps if step_id not in order]
    status_of = {step_id: (steps.get(step_id) or {}).get("status", PENDING) for step_id in order}
    by_status = {name: [sid for sid in order if status_of[sid] == name] for name in STATUSES}
    nxt = ""
    for step_id in order:
        if status_of[step_id] != DONE:
            nxt = step_id
            break
    return {"next": nxt, "total": len(order), "done": by_status[DONE],
            "failed": by_status[FAILED], "running": by_status[RUNNING],
            "pending": by_status[PENDING] + by_status[SKIPPED]}


def record(state, step_id, **fields):
    """Merge `fields` into one step's record, append the event, refresh the cursor.

    The state machine lives here on purpose: status transitions and the history that explains
    them are written together, so a checkpoint always tells the same story as its `steps`.
    """
    entry = state.setdefault("steps", {}).setdefault(
        step_id, {"status": PENDING, "attempts": 0})
    entry.update(fields)
    entry["updated"] = now()
    event = {"at": entry["updated"], "step": step_id, "status": entry.get("status", "")}
    if entry.get("reason"):
        event["reason"] = entry["reason"]
    if entry.get("error"):
        event["code"] = (entry["error"] or {}).get("code", "")
    history = state.setdefault("history", [])
    history.append(event)
    del history[:-HISTORY_LIMIT]
    state["updated"] = entry["updated"]
    state["cursor"] = cursor(state)
    return entry


def is_done(state, step_id):
    """Has this step finished in this state (regardless of its cache key)?"""

# ------------------------------------------------------------------ identity of what a step consumes
_DIGEST_MEMO = {}      # (abspath, size, mtime_ns) -> sha256. A run digests the same clip many times.


def digest_file(path, memo=False):
    """Identity of one file: {'sha256', 'size'} below HASH_LIMIT, else {'size', 'mtime_ns'}.

    A path that does not exist digests to {} -- the caller decides whether that is an error
    (running) or just a warning (validating a plan whose media is produced later).

    `memo=True` (M5.5B, inputs only) reuses a sha256 keyed on (path, size, mtime_ns), so a 3-still
    batch does not rehash the same clip three times. It is NOT the default: an output can be rewritten
    with the same length inside one mtime tick, and `outputs_intact` must see that.
    """
    if not path or not os.path.isfile(path):
        return {}
    sig = guard.file_sig(path)
    size = sig["size"]
    if size <= HASH_LIMIT:
        if not memo:
            return {"sha256": guard.sha256_file(path), "size": size}
        key = (os.path.abspath(path), size, sig["mtime_ns"])
        if key not in _DIGEST_MEMO:
            _DIGEST_MEMO[key] = guard.sha256_file(path)
        return {"sha256": _DIGEST_MEMO[key], "size": size}
    return {"size": size, "mtime_ns": sig["mtime_ns"]}


def input_digests(inputs):
    """[{name, index, path, digest}] for one step's resolved inputs (lists flattened in order).

    `path` is stored relative to the repo when possible, so a checkpoint is readable and does not
    leak an absolute user path; the digest is what the resume decision actually compares.

    A MAPPING input (M5.5B's handle table) is flattened to `assets[footage_a]` rows, so two handles
    that swap files, or a handle that moves to another clip, change the key.
    """
    rows = []
    for name, value in sorted((inputs or {}).items()):
        if isinstance(value, dict):
            for handle in sorted(value):
                item = value[handle]
                rows.append({"name": "%s[%s]" % (name, handle), "index": 0,
                             "path": guard.rel(str(item)), "digest": digest_file(str(item), memo=True)})
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        for index, item in enumerate(values):
            rows.append({"name": name, "index": index, "path": guard.rel(str(item)),
                         "digest": digest_file(str(item), memo=True)})
    return rows


def cache_key(op, params, inputs, executor, tool_version=""):
    """The resume decision, as a hash: op + params + executor version + identity of each input.

    Anything that changes what a step would produce changes this key, so a step with a matching
    key is genuinely reusable; a step whose key differs re-runs (and says so in its reason).
    """
    payload = {"op": op, "params": params or {}, "inputs": inputs or [],
               "executor": executor, "tool_version": tool_version or ""}
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def _abs(path):
    """Checkpoint paths are repo-relative, so they are resolved against ROOT (never the CWD)."""
    text = str(path)
    return text if os.path.isabs(text) else os.path.join(guard.ROOT, text)


def outputs_intact(outputs, digests):
    """Do all of a step's outputs still exist with the digest recorded when it finished?

    Returns (ok, reason): the reason is what `resume` prints, so a stale step is explained rather
    than silently re-run or silently trusted.
    """
    if not outputs:
        return False, "the step recorded no outputs"
    if not digests:
        return False, "the step recorded no output digests"
    for name, path in sorted((outputs or {}).items()):
        full = _abs(path)
        if not os.path.isfile(full):
            return False, "output %s is missing (%s)" % (name, guard.rel(str(path)))
        stored = digests.get(name) or {}
        if not stored:
            return False, "no digest was recorded for output %s" % name
        if digest_file(full) != stored:
            return False, "output %s changed on disk (%s)" % (name, guard.rel(str(path)))
    return True, ""


def step_cached(state, step_id, key, outputs):
    """The resume rule in one place: same cache key AND outputs still intact -> skip.

    Returns (skip, reason). Any doubt skips nothing: a missing output digest, a changed status or
    an empty key all mean the step runs again, which is the safe side of the decision.
    """
    entry = (state.get("steps") or {}).get(step_id) or {}
    if entry.get("status") != DONE:
        # Phrased as a reason to RUN, because that is what the caller does with it: a step that was
        # never started, or was left `running` by a killed process, or was `skipped` behind a gate,
        # must run now. "step is skipped" on a row that just ran read like a contradiction.
        return False, "step was %s, so it runs again" % (entry.get("status") or "never started")
    if not key:
        return False, "no cache key was computed"
    if entry.get("cache_key") != key:
        return False, "cache key changed (inputs, params or executor version)"
    ok, reason = outputs_intact(outputs, entry.get("output_digests") or {})
    return (True, "cached") if ok else (False, reason)

    return (state.get("steps") or {}).get(step_id, {}).get("status") == DONE
