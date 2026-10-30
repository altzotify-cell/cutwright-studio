"""Approval gates: a written approval that unblocks a step, kept next to the run it belongs to.

A gate declared in the manifest is DATA (`{id, before_step, approved}`). This module owns the FILES
in `<run_dir>/approvals/<gate>.json`, which is what `approve <run-dir> <gate>` writes and what the
run consults. Two-way by design:

  * a file can approve a gate the manifest left closed (that is how a run is released);
  * approving never un-approves: a manifest that already says `approved: true` stays approved even
    if no file exists, so a re-derived plan cannot silently re-lock a finished production.

Approval is additive and idempotent. The record is written with `checkpoint.write_atomic` (temp file
in the same folder + os.replace), because a half-written JSON file would read as "not approved" and
a resumed run would stop for no reason.

`manifest._blocking_gate` asks this module; no other code may decide whether a gate is open.
"""
import json
import os

from cutwright import guard
from cutwright.engine import checkpoint, ids

DIRNAME = "approvals"


def approvals_dir(run_dir):
    """Absolute path of the approvals folder (not created: reading must not have side effects)."""
    return os.path.join(os.path.abspath(run_dir), DIRNAME)


def path_for(run_dir, gate_id):
    """Where one gate's approval lives: the gate id is slugged, so a ': ' cannot break the path."""
    return os.path.join(approvals_dir(run_dir), ids.slug(gate_id, "gate") + ".json")


def approve(run_dir, gate_id, by="owner", note=""):
    """Write the approval file for `gate_id` and return the record (with its repo-relative path)."""
    if not str(gate_id or "").strip():
        raise ValueError("a gate needs an id")
    record = {"gate": str(gate_id), "approved": True, "by": str(by or "owner"),
              "at": checkpoint.now(), "note": str(note or "")}
    target = path_for(run_dir, gate_id)
    checkpoint.write_atomic(target, record)
    record["path"] = guard.rel(target)
    return record


def load(run_dir, gate_id):
    """The approval record for `gate_id`, or None. An unreadable file is treated as absent."""
    try:
        with open(path_for(run_dir, gate_id), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def records(run_dir):
    """gate id -> approval record for every readable file in the run's approvals folder."""
    folder = approvals_dir(run_dir)
    out = {}
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".json"):
            continue
        data = load(run_dir, name[:-5])
        if data and data.get("gate"):
            out[str(data["gate"])] = data
    return out


def status(gate, run_dir):
    """One gate as data: is it open, and which source opened it."""
    gate_id = str(gate.get("id") or "")
    row = {"id": gate_id, "before_step": str(gate.get("before_step") or ""),
           "approved": False, "source": "", "by": "", "at": ""}
    record = load(run_dir, gate_id) if gate_id else None
    if record and record.get("approved"):
        row.update(approved=True, source="approval file", by=str(record.get("by") or ""),
                   at=str(record.get("at") or ""))
    elif gate.get("approved"):
        row.update(approved=True, source="manifest")
    return row


def all_status(gates, run_dir):
    """Every gate with its state, in manifest order (what the report and `approve` print)."""
    return [status(gate, run_dir) for gate in (gates or [])]


def pending(gates, run_dir):
    """The gates that are still closed."""
    return [row for row in all_status(gates, run_dir) if not row["approved"]]


def blocking(gates, run_dir, before_step=""):
    """Id of the first unapproved gate in front of `before_step` (all gates when it is empty)."""
    for row in all_status(gates, run_dir):
        if row["approved"]:
            continue
        if before_step and row["before_step"] != before_step:
            continue
        return row["id"]
    return ""
