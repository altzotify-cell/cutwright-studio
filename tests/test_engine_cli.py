"""The CLI verbs: tools / validate / run / resume / status / approve (M3, phase 3D).

Run: python -m unittest tests.test_engine_cli -v      (repo root)

Called in-process (`cli.main(argv)`) so a test sees exactly what a human or an agent sees: the exit
code, the stdout, and - with --json - the document it can parse. The media is real; nothing here is
mocked, because the point of these verbs is that they reach the real executors.
"""
import contextlib
import io
import json
import os
import shutil
import unittest

from cutwright import cli, guard
from tests import media_fixtures as mf

WORK = os.path.join(guard.OUT, "engine_cli")
RUNS = os.path.join(guard.OUT, "runs")
FPS = 24
RUN_ID = "cli-demo"
RUN_DIR = os.path.join(RUNS, RUN_ID)


def src():
    path = os.path.join(WORK, "src.mp4")
    guard.ensure_dir(WORK)
    if not os.path.isfile(path):
        mf.make_counter_clip(path, frames=48, fps=FPS, with_audio=False)
    return guard.rel(path)


def document(run_id=RUN_ID, gates=None, second_op=None):
    """Cut 24 frames with Kinocut, fit them back to 12 with ffmpeg: two executors, two steps."""
    work = "out/runs/" + run_id
    steps = [{"id": "cut", "op": "trim_exact", "inputs": {"src": "@asset.src"},
              "params": {"start_frame": 12, "frames": 24},
              "outputs": {"video": work + "/cut.mp4"},
              "validation": [{"check": "frame_count", "expect": 24}]}]
    if second_op is not False:
        steps.append({"id": "fit", "op": "fit_to_frames", "inputs": {"src": "@cut.video"},
                      "params": {"frames": 12, "fps": FPS, "width": 160, "height": 90},
                      "outputs": {"video": work + "/fit.mp4"},
                      "validation": [{"check": "frame_count", "expect": 12},
                                     {"check": "constant_fps", "expect": FPS}]})
    return {"schema": 1, "run_id": run_id, "fps": FPS, "size": [160, 90],
            "budget": {"mode": "cap", "cap_usd": 0.0},
            "constraints": {"ai_generated_images": False,
                            "allowed_asset_origins": ["footage", "user_image", "code_graphic",
                                                      "stock_licensed"]},
            "assets": [{"id": "src", "path": src(), "origin": "footage"}],
            "gates": gates or [], "steps": steps}


def write(name, data):
    guard.ensure_dir(WORK)
    return guard.write_json(os.path.join(WORK, name), data)


def run(*argv):
    """(exit code, stdout text, parsed JSON or None) -- exactly what a caller would get."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = cli.main([str(item) for item in argv])
    text = buffer.getvalue()
    try:
        return code, text, json.loads(text)
    except ValueError:
        return code, text, None


class DiscoveryTest(unittest.TestCase):
    """`tools ...` never touches media: it is what an agent calls before it plans anything."""

    def test_list_returns_json_per_stage(self):
        code, _text, data = run("tools", "list", "--stage", "edit", "--json")
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        self.assertEqual(data["count"], len(data["ops"]))
        self.assertTrue(all(row["stage"] == "edit" for row in data["ops"]))
        self.assertIn("kinocut", data["installed"])

    def test_list_without_a_stage_returns_everything(self):
        _code, _text, data = run("tools", "list", "--json")
        self.assertEqual(data["count"], sum(data["stages"].values()))

    def test_an_unknown_stage_is_refused_with_a_code(self):
        code, _text, data = run("tools", "list", "--stage", "nope", "--json")
        self.assertEqual(code, 2)
        self.assertFalse(data["ok"])
        self.assertEqual(data["code"], "unknown_stage")

    def test_describe_returns_params_and_evidence(self):
        code, _text, data = run("tools", "describe", "trim_exact", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(data["executor"], "kinocut")
        self.assertIn("frames", data["params"])
        self.assertTrue(data["evidence_status"]["ok"], data["evidence_status"])
        self.assertTrue(data["executor_ready"]["ok"])

    def test_describe_an_unknown_op_is_refused(self):
        code, _text, data = run("tools", "describe", "make_coffee", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(data["code"], "unknown_op")

    def test_envelope_stays_small(self):
        code, _text, data = run("tools", "envelope", "--json")
        self.assertEqual(code, 0)
        self.assertLessEqual(data["returned"], 10)
        self.assertEqual(data["stage"], "edit")


class ValidateTest(unittest.TestCase):
    """`validate` on the shipped example and on a plan with one thing broken."""

    def test_the_example_manifest_validates(self):
        code, _text, data = run("validate", "docs/schemas/manifest.example.json", "--json")
        self.assertEqual(code, 0, data)
        self.assertTrue(data["ok"], data["errors"])
        self.assertEqual(len(data["provenance"]["assets"]), 2)
        self.assertEqual(data["steps"], 3)

    def test_an_unknown_op_is_reported_not_crashed(self):
        data = document(run_id="cli-bad")
        data["steps"][0]["op"] = "make_coffee"
        code, _text, report = run("validate", write("bad.json", data), "--json")
        self.assertEqual(code, 1)
        self.assertFalse(report["ok"])
        self.assertEqual(report["errors"][0]["code"], "unknown_op")
        self.assertEqual(report["errors"][0]["step"], "cut")

    def test_a_missing_manifest_is_refused(self):
        code, _text, data = run("validate", "out/engine_cli/nope.json", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(data["code"], "not_found")


class RunTest(unittest.TestCase):
    """The real path: encode, checkpoint, resume, status - then read the report it wrote."""

    def setUp(self):
        if os.path.isdir(RUN_DIR):
            shutil.rmtree(RUN_DIR)

    def test_dry_run_writes_nothing(self):
        path = write("dry.json", document(run_id="cli-dry"))
        dry_dir = os.path.join(RUNS, "cli-dry")
        if os.path.isdir(dry_dir):
            shutil.rmtree(dry_dir)
        code, _text, data = run("run", path, "--dry-run", "--json")
        self.assertEqual(code, 0, data)
        self.assertTrue(data["dry_run"])
        self.assertEqual([row["status"] for row in data["steps"]], ["would_run", "would_run"])
        self.assertFalse(os.path.isdir(dry_dir), "a dry run must not create the run folder")

    def test_run_then_status_then_resume(self):
        path = write("demo.json", document())
        code, _text, first = run("run", path, "--json")
        self.assertEqual(code, 0, first)
        self.assertTrue(first["ok"], first)
        self.assertEqual([row["status"] for row in first["steps"]], ["done", "done"])
        self.assertEqual([row["executor"] for row in first["steps"]], ["kinocut", "ffmpeg"])
        self.assertTrue(os.path.isfile(os.path.join(RUN_DIR, "fit.mp4")))
        self.assertTrue(os.path.isfile(os.path.join(RUN_DIR, "production_report.json")))

        code, _text, state = run("status", RUN_DIR, "--json")
        self.assertEqual(code, 0, state)
        self.assertTrue(state["ok"])
        self.assertTrue(all(state["output_digests"][row["id"]] for row in state["steps"]))
        self.assertTrue(state["production_report"])

        code, _text, again = run("resume", RUN_DIR, "--json")
        self.assertEqual(code, 0, again)
        self.assertEqual([row["status"] for row in again["steps"]], ["skipped", "skipped"])
        self.assertTrue(all("cached" in row["reason"] for row in again["steps"]))

    def test_only_runs_the_step_it_names(self):
        path = write("only.json", document(run_id="cli-only"))
        if os.path.isdir(os.path.join(RUNS, "cli-only")):
            shutil.rmtree(os.path.join(RUNS, "cli-only"))
        code, _text, data = run("run", path, "--only", "cut", "--json")
        self.assertEqual(code, 0, data)
        self.assertEqual([row["status"] for row in data["steps"]], ["done", "skipped"])
        self.assertIn("not selected", data["steps"][1]["reason"])

    def test_a_failed_check_fails_the_run_with_its_own_code(self):
        data = document()
        data["steps"][1]["validation"] = [{"check": "frame_count", "expect": 99}]
        code, _text, report = run("run", write("fail.json", data), "--json")
        self.assertEqual(code, 1)
        self.assertFalse(report["ok"])
        self.assertEqual(report["steps"][1]["status"], "failed")
        self.assertEqual(report["steps"][1]["error"]["code"], "validation_failed")
        self.assertIn("expected 99", report["stopped"])

    def test_status_of_a_folder_without_a_checkpoint_is_refused(self):
        empty = guard.ensure_dir(os.path.join(WORK, "empty-run"))
        code, _text, data = run("status", empty, "--json")
        self.assertEqual(code, 2)
        self.assertEqual(data["code"], "not_found")

    def test_a_missing_run_folder_is_not_found(self):
        code, text, _data = run("status", os.path.join(WORK, "no-such-run"), "--json")
        self.assertEqual(code, 3)
        self.assertIn("no such run folder", text)


class ApproveTest(unittest.TestCase):
    """`approve` writes the file the run is waiting for, and says what is still closed."""

    def setUp(self):
        if os.path.isdir(RUN_DIR):
            shutil.rmtree(RUN_DIR)

    def test_approve_releases_a_gated_run(self):
        gated = document(gates=[{"id": "final_ok", "before_step": "fit", "approved": False}])
        path = write("gated.json", gated)
        code, _text, blocked = run("run", path, "--json")
        self.assertEqual(code, 1)
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["steps"][1]["status"], "skipped")

        code, _text, approved = run("approve", RUN_DIR, "final_ok", "--note", "ok by owner",
                                    "--json")
        self.assertEqual(code, 0, approved)
        self.assertTrue(approved["approved"]["approved"])
        self.assertEqual(approved["pending_gates"], [])

        code, _text, released = run("run", path, "--json")
        self.assertEqual(code, 0, released)
        self.assertTrue(released["ok"], released)
        self.assertEqual([row["status"] for row in released["steps"]], ["skipped", "done"])


if __name__ == "__main__":
    unittest.main()
