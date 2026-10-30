"""`production_report.json`: one file that says what a run actually did.

`manifest.run()` returns its report in memory. A production inspected the next morning -- by the
owner, or by the next agent session -- needs the same facts on disk, next to the checkpoint, so the
two can never disagree about what happened.

Deliberately a REPORT and not a second state machine: nothing here decides anything. Step statuses
and digests come from the checkpoint, gate states from `gates.py`, the plan from `manifest.Plan`.
Written with `checkpoint.write_atomic`, so a killed process leaves the previous report intact
instead of half a JSON object.
"""
import json
import os

from cutwright import guard
from cutwright.engine import checkpoint, gates

FILE = "production_report.json"


def path_for(run_dir):
    """Absolute path of the report inside one run folder."""
    return os.path.join(os.path.abspath(run_dir), FILE)


def _rel(value):
    """One path (or list of paths) as the report should store it."""
    if isinstance(value, (list, tuple)):
        return [guard.rel(str(item)) for item in value]
    return guard.rel(str(value))


def build(plan, report, state=None):
    """The report for one run: every step in plan order, the gates, the budget, the versions."""
    report = report or {}
    state = state or {}
    recorded = state.get("steps") or {}
    rows = {row.get("id"): row for row in (report.get("steps") or [])}
    gate_rows = gates.all_status(getattr(plan, "gates", []) or [], plan.run_dir)
    versions, steps = {}, []
    for step in getattr(plan, "steps", []) or []:
        entry = recorded.get(step.id) or {}
        row = rows.get(step.id) or {}
        if step.tool_version:
            versions.setdefault(step.executor, step.tool_version)
        steps.append({
            "id": step.id, "op": step.spec.name, "executor": step.executor,
            "executor_reason": step.executor_reason,
            "status": entry.get("status") or row.get("status", ""),
            "attempts": int(entry.get("attempts") or 0),
            "seconds": entry.get("seconds", 0.0),
            "reason": entry.get("reason") or row.get("reason", ""),
            "inputs": {name: _rel(path) for name, path in step.inputs.items()},
            "outputs": entry.get("outputs") or {name: _rel(path)
                                                for name, path in step.outputs.items()},
            "output_digests": entry.get("output_digests") or {},
            "validation": entry.get("validation") or [dict(item) for item in step.validation],
            "error": entry.get("error") or {},
        })
    budget = dict(getattr(plan, "budget", {}) or {})
    return {
        "schema": 1, "run_id": getattr(plan, "run_id", ""), "created": checkpoint.now(),
        "run_dir": guard.rel(getattr(plan, "run_dir", "")),
        "manifest": getattr(plan, "manifest_path", ""),
        "manifest_sha256": getattr(plan, "manifest_sha256", ""),
        "ok": bool(report.get("ok", True)), "stopped": report.get("stopped", ""),
        "dry_run": bool(report.get("dry_run", False)), "budget": budget,
        "cost_usd": round(float(budget.get("total_usd") or 0.0), 6),
        "cursor": report.get("cursor") or state.get("cursor") or {},
        "steps": steps, "gates": gate_rows,
        "pending_gates": [row["id"] for row in gate_rows if not row["approved"]],
        "tool_versions": versions,
    }


def write(run_dir, data):
    """Persist one report atomically. Returns its absolute path."""
    return checkpoint.write_atomic(path_for(run_dir), data)


def load(run_dir):
    """The report on disk, or None. A missing or unreadable report is not an error here."""
    try:
        with open(path_for(run_dir), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
