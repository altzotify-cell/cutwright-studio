"""Approval gates: the file in `<run_dir>/approvals/`, and the run that waits for it (M3, 3D).

Run: python -m unittest tests.test_engine_gates -v      (repo root)

Two layers: the FILE (slugged name, atomic write, idempotent, a corrupt file reads as absent) and
the RUN (a closed gate skips its step and stops the run; an approval file releases it without
touching the manifest).
"""
import json
import os
import shutil
import unittest

from cutwright import guard
from cutwright.engine import gates, manifest, report
from tests import media_fixtures as mf

WORK = os.path.join(guard.OUT, "engine_gates")
RUN = os.path.join(WORK, "runs", "gate-demo")
FPS = 24


def src():
    """48 frames of numbered blocks, no audio: a fast, frame-exact fixture.

    Returns the ABSOLUTE path. `guard.rel()` is called where a repo-relative path is what the test is
    actually exercising - not here, where a second relativisation is just a way to get it wrong.
    """
    path = os.path.join(WORK, "src.mp4")
    guard.ensure_dir(WORK)
    if not os.path.isfile(path):
        mf.make_counter_clip(path, frames=48, fps=FPS, with_audio=False)
    return path


def document(declared=None, approved=False):
    """One real step behind one gate, unless the test says otherwise."""
    return {
        "schema": 1, "run_id": "gate-demo", "fps": FPS, "size": [160, 90],
        "budget": {"mode": "cap", "cap_usd": 0.0},
        "constraints": {"ai_generated_images": False,
                        "allowed_asset_origins": ["footage", "user_image", "code_graphic",
                                                  "stock_licensed"]},
        "assets": [{"id": "src", "path": src(), "origin": "footage"}],
        "gates": declared if declared is not None else [
            {"id": "final_ok", "before_step": "fit", "approved": approved}],
        "steps": [{"id": "fit", "op": "fit_to_frames", "inputs": {"src": "@asset.src"},
                   "params": {"frames": 24, "fps": FPS, "width": 160, "height": 90},
                   "outputs": {"video": os.path.join("out", "engine_gates", "runs", "gate-demo",
                                                     "fit.mp4")},
                   "validation": [{"check": "frame_count", "expect": 24}]}],
    }


class GateFileTest(unittest.TestCase):
    """The approval file itself, with no media involved."""

    def setUp(self):
        if os.path.isdir(RUN):
            shutil.rmtree(RUN)
        guard.ensure_dir(RUN)

    def test_approve_writes_a_slugged_file(self):
        record = gates.approve(RUN, "Final OK: v2", note="checked by the owner")
        path = gates.path_for(RUN, "Final OK: v2")
        self.assertTrue(path.endswith(os.path.join("approvals", "final-ok-v2.json")), path)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(record["gate"], "Final OK: v2")
        self.assertTrue(record["approved"])
        self.assertEqual(record["note"], "checked by the owner")

    def test_approve_is_idempotent(self):
        gates.approve(RUN, "final_ok", by="owner")
        second = gates.approve(RUN, "final_ok", by="owner", note="again")
        self.assertTrue(second["approved"])
        self.assertEqual(len(gates.records(RUN)), 1)

    def test_load_and_records_read_it_back(self):
        gates.approve(RUN, "script_ok")
        self.assertEqual(gates.load(RUN, "script_ok")["gate"], "script_ok")
        self.assertEqual(sorted(gates.records(RUN)), ["script_ok"])
        self.assertIsNone(gates.load(RUN, "never_approved"))

    def test_a_corrupt_approval_file_is_treated_as_absent(self):
        path = gates.path_for(RUN, "final_ok")
        guard.write_text(path, "{not json")
        self.assertIsNone(gates.load(RUN, "final_ok"))
        self.assertEqual(gates.records(RUN), {})

    def test_status_reports_which_source_opened_the_gate(self):
        closed = {"id": "g1", "before_step": "fit", "approved": False}
        manifest_approved = {"id": "g2", "before_step": "fit", "approved": True}
        gates.approve(RUN, "g3")
        self.assertEqual(gates.status(closed, RUN)["source"], "")
        self.assertFalse(gates.status(closed, RUN)["approved"])
        self.assertEqual(gates.status(manifest_approved, RUN)["source"], "manifest")
        row = gates.status({"id": "g3", "before_step": "fit", "approved": False}, RUN)
        self.assertTrue(row["approved"])
        self.assertEqual(row["source"], "approval file")

    def test_blocking_names_the_gate_in_front_of_a_step(self):
        declared = [{"id": "script_ok", "before_step": "cut", "approved": False},
                    {"id": "final_ok", "before_step": "fit", "approved": False}]
        self.assertEqual(gates.blocking(declared, RUN, before_step="fit"), "final_ok")
        self.assertEqual(gates.blocking(declared, RUN, before_step="cut"), "script_ok")
        self.assertEqual(gates.blocking(declared, RUN, before_step="export"), "")
        gates.approve(RUN, "final_ok")
        self.assertEqual(gates.blocking(declared, RUN, before_step="fit"), "")
        self.assertEqual([row["id"] for row in gates.pending(declared, RUN)], ["script_ok"])


class GateRunTest(unittest.TestCase):
    """A closed gate skips its step and stops the run; a file releases it without editing the plan."""

    def setUp(self):
        if os.path.isdir(os.path.dirname(RUN)):
            shutil.rmtree(os.path.dirname(RUN))

    def test_a_closed_gate_blocks_the_run_and_a_file_releases_it(self):
        plan = manifest.derive(document(), run_dir=RUN)
        blocked = manifest.run(plan)
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["steps"][0]["status"], "skipped")
        self.assertIn("waiting for gate final_ok", blocked["steps"][0]["reason"])
        self.assertIn("final_ok", blocked["stopped"])
        self.assertFalse(os.path.isfile(os.path.join(RUN, "fit.mp4")),
                         "a blocked step must not have encoded anything")
        self.assertEqual(report.load(RUN)["pending_gates"], ["final_ok"])

        gates.approve(RUN, "final_ok", note="released in the test")
        released = manifest.run(plan)
        self.assertTrue(released["ok"], released)
        self.assertEqual(released["steps"][0]["status"], "done")
        self.assertEqual(released["steps"][0]["validation"][0]["measured"], 24)
        self.assertTrue(os.path.isfile(os.path.join(RUN, "fit.mp4")))
        self.assertEqual(report.load(RUN)["pending_gates"], [])
        self.assertEqual(report.load(RUN)["gates"][0]["source"], "approval file")

    def test_an_approved_manifest_needs_no_file(self):
        plan = manifest.derive(document(approved=True), run_dir=RUN)
        done = manifest.run(plan)
        self.assertTrue(done["ok"], done)
        self.assertEqual(done["steps"][0]["status"], "done")
        self.assertEqual(gates.records(RUN), {})

    def test_a_gate_stops_the_plan_at_its_step(self):
        """The steps before the gate stay done; the run stops instead of jumping over it."""
        data = document(declared=[{"id": "later", "before_step": "export", "approved": False}])
        data["steps"].append({"id": "export", "op": "export_h264",
                              "inputs": {"src": "@fit.video"},
                              "params": {"quality": "high", "container": "mp4"},
                              "outputs": {"video": os.path.join("out", "engine_gates", "runs",
                                                                "gate-demo", "final.mp4")},
                              "validation": [{"check": "decodes_clean"}]})
        blocked = manifest.run(manifest.derive(data, run_dir=RUN))
        self.assertFalse(blocked["ok"])
        self.assertEqual([row["status"] for row in blocked["steps"]], ["done", "skipped"])
        self.assertEqual(blocked["cursor"]["next"], "export")
        self.assertFalse(os.path.isfile(os.path.join(RUN, "final.mp4")))


if __name__ == "__main__":
    unittest.main()

