"""The CLI verbs: tools / validate / run / resume / status / approve (M3), and the Recap Studio
bridge `recap ...` (M6 / G4).

Run: python -m unittest tests.test_engine_cli -v      (repo root)

Called in-process (`cli.main(argv)`) so a test sees exactly what a human or an agent sees: the exit
code, the stdout, and - with --json - the document it can parse. The media is real; nothing here is
mocked, because the point of these verbs is that they reach the real executors.

Two exceptions to "nothing is mocked", both in `RecapBridgeContractTest`: the bridge's subprocess
contract (argv, env, cwd, timeout) is checked against a replaced `subprocess.run`, because the real
`recap timeline`/`remotion` steps cost minutes and a test may not. The refusals need no subprocess
at all and are checked for real.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import unittest
from unittest import mock

from cutwright import cli, guard
from cutwright import recap as bridge
from cutwright.engine import blueprint, manifest, ops
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

    def test_envelope_covers_every_stage_with_ops_and_commands(self):
        """M6: one call per stage, and each tool comes with the schema needed to use it."""
        for stage in ("plan", "edit", "graphics", "review", "deliver"):
            code, _text, data = run("tools", "envelope", "--stage", stage, "--json")
            self.assertEqual(code, 0, stage)
            self.assertEqual(data["stage"], stage)
            self.assertGreater(data["tools"], 0, stage)
            self.assertLessEqual(data["tools"], data["max_tools"], stage)
            self.assertTrue(data["how_to_run"].strip(), stage)
            for row in data["ops"]:
                self.assertIn(row["kind"], ("op",), stage)
                self.assertIn("params", row, stage)
                self.assertIn("inputs", row, stage)
            for row in data["commands"]:
                self.assertEqual(row["kind"], "command", stage)
                self.assertIn("usage", row, stage)


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


class RecapBridgeTest(unittest.TestCase):
    """`recap ...` on real folders (M6 / G4): refusals first, then one real step on a throwaway copy.

    Everything except `test_a_real_step_...` is decided before a subprocess starts, so the refusals
    cost microseconds. The real step is `check` on a fresh template copy (~3 s): enough to prove
    the cwd, the non-interactive env, the exit code and the file diff without starting a render.
    """

    NAME = "m6_bridge_test"

    def tearDown(self):
        path = os.path.join(bridge.PROJECTS, self.NAME)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)

    def test_projects_lists_real_folders(self):
        code, _text, data = run("recap", "projects", "--json")
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        self.assertEqual(data["count"], len(data["projects"]))
        row = data["projects"][0]
        for key in ("name", "module", "segments", "audio_files", "outputs", "stale", "next"):
            self.assertIn(key, row)

    def test_force_is_refused_by_default(self):
        code, _text, data = run("recap", "tts", "--force", "--project", "regress", "--json")
        self.assertEqual(code, 2)
        self.assertFalse(data["ok"])
        self.assertEqual(data["code"], "forbidden_flag")
        self.assertIn("i-know-this-destroys-work", data["suggested"])

    def test_a_destructive_step_is_refused_with_its_reason(self):
        for step in ("init", "collect", "comic"):
            code, _text, data = run("recap", step, "--project", "regress", "--json")
            self.assertEqual(code, 2, step)
            self.assertEqual(data["code"], "forbidden_step", step)
            self.assertIn("not an unattended step", data["message"])

    def test_a_path_is_not_a_project_name(self):
        for name in ("..\\..", "a/b", ""):
            code, _text, data = run("recap", "check", "--project", name, "--json")
            self.assertEqual(code, 2, name)
            self.assertIn(data["code"], ("bad_project_name", "no_project"), name)

    def test_an_unknown_project_says_what_to_do(self):
        code, _text, data = run("recap", "check", "--project", "no_such_project_here", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(data["code"], "unknown_project")
        self.assertIn("recap new", data["suggested"])

    def test_new_writes_project_json_without_running_init(self):
        code, _text, data = run("recap", "new", self.NAME, "--module", "ranking", "--topic", "t",
                                "--json")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["module"], "ranking")
        path = os.path.join(bridge.PROJECTS, self.NAME)
        meta = guard.read_json(os.path.join(path, "project.json"), {})
        self.assertEqual(meta["module"], "ranking")
        self.assertEqual(meta["topic"], "t")
        self.assertTrue(os.path.isfile(os.path.join(path, "recap.py")))
        self.assertEqual(data["stale"]["stale"], [])          # a fresh copy matches _template
        code, _text, again = run("recap", "new", self.NAME, "--json")
        self.assertEqual(code, 2)
        self.assertEqual(again["code"], "project_exists")

    def test_status_of_a_fresh_project_points_at_the_first_step(self):
        run("recap", "new", self.NAME, "--json")
        code, _text, data = run("recap", "status", "--project", self.NAME, "--json")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["segments"], 0)                 # the template's segments.json is empty
        self.assertIn("demo", data["next"])
        self.assertFalse(data["outputs"]["timeline"])

    def test_a_real_step_runs_in_the_project_and_reports_its_files(self):
        run("recap", "new", self.NAME, "--json")
        code, _text, data = run("recap", "check", "--project", self.NAME, "--json")
        self.assertEqual(code, 0, data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["exit_code"], 0)
        self.assertTrue(data["noninteractive"])
        self.assertIn("recap.py", " ".join(data["command"]))
        self.assertNotIn("--json", data["command"])           # the bridge's flag never reaches recap.py
        self.assertIn("STATE.md", data["files_changed"])


class RecapBridgeContractTest(unittest.TestCase):
    """The subprocess contract with `subprocess.run` replaced: no step is really executed."""

    PROJECT = "regress"          # a real project folder, so project_dir() resolves

    def _fake(self, code=0, out=b"", err=b""):
        seen = {}

        def fake(argv, **kwargs):
            seen["argv"] = list(argv)
            seen.update(kwargs)
            return subprocess.CompletedProcess(argv, code, out, err)

        return seen, fake

    def test_argv_env_and_cwd_are_what_recap_py_expects(self):
        seen, fake = self._fake()
        with mock.patch.object(bridge.subprocess, "run", fake):
            data = bridge.run(self.PROJECT, "tts", only="a,b", engine="edge")
        self.assertTrue(data["ok"], data)
        self.assertEqual(seen["argv"][1:], ["recap.py", "tts", "--only", "a,b", "--engine", "edge"])
        self.assertEqual(seen["env"]["RECAP_NONINTERACTIVE"], "1")
        self.assertEqual(seen["env"]["RECAP_NO_REVEAL"], "1")
        self.assertEqual(seen["cwd"], os.path.join(bridge.PROJECTS, self.PROJECT))
        self.assertNotIn("--force", seen["argv"])
        for key in ("ok", "step", "project", "exit_code", "seconds", "stdout_tail",
                    "files_changed", "problems"):
            self.assertIn(key, data)

    def test_a_failed_step_is_a_result_not_an_exception(self):
        seen, fake = self._fake(code=1, out=b"MISSING SHOT d_04\n[!] scene 3 fell back\n",
                                err=b"Traceback (most recent call last):\n")
        with mock.patch.object(bridge.subprocess, "run", fake):
            data = bridge.run(self.PROJECT, "check")
        self.assertFalse(data["ok"])
        self.assertEqual(data["exit_code"], 1)
        self.assertEqual(data["code"], "step_failed")
        self.assertIn("MISSING SHOT d_04", data["problems"])
        self.assertIn("[!] scene 3 fell back", data["problems"])
        self.assertTrue(any("Traceback" in row for row in data["problems"]))
        self.assertIn("problems[]", data["suggested"])

    def test_a_timeout_is_reported_as_step_timeout(self):
        def fake(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 1), output=b"partial\n")

        with mock.patch.object(bridge.subprocess, "run", fake):
            data = bridge.run(self.PROJECT, "remotion", timeout=5)
        self.assertFalse(data["ok"])
        self.assertEqual(data["code"], "step_timeout")
        self.assertIn("partial", data["stdout_tail"])

    def test_the_force_gate_needs_both_halves(self):
        self.assertEqual(bridge.check("tts", force=True, override=True, comms="C-013"),
                         {"force": True, "comms": "C-013"})
        for kwargs in ({"override": True}, {"comms": "C-013"}, {}):
            with self.assertRaises(bridge.BridgeError) as ctx:
                bridge.check("tts", force=True, **kwargs)
            self.assertEqual(ctx.exception.code, "forbidden_flag")
        self.assertEqual(bridge.check("tts"), {})

    def test_an_unknown_step_lists_the_allowed_ones(self):
        with self.assertRaises(bridge.BridgeError) as ctx:
            bridge.check("render_everything")
        self.assertEqual(ctx.exception.code, "unknown_step")
        self.assertIn("timeline", ctx.exception.suggested)


class BlueprintCliTest(unittest.TestCase):
    """M8: a BRIEF becomes a blueprint (frame counts from the narration), which becomes a manifest.

    No network here on purpose: the narration is a beep bed and `--no-tts` is passed, so the timing
    falls back to the measured duration and a word-count split. The real production (edge-tts word
    timings, three scenes, a full render) is `recapstudio/Projects/m8_feature`.
    """

    @classmethod
    def setUpClass(cls):
        cls.work = guard.ensure_dir(os.path.join(WORK, "blueprint"))
        cls.project = guard.ensure_dir(os.path.join(cls.work, "project"))
        cls.clip = os.path.join(cls.work, "footage.mp4")
        if not os.path.isfile(cls.clip):
            mf.make_counter_clip(cls.clip, frames=48, fps=FPS, with_audio=False)
        cls.voice = os.path.join(cls.project, "audio", "narration.wav")
        guard.ensure_dir(os.path.dirname(cls.voice))
        if not os.path.isfile(cls.voice):
            mf.make_beep_bed(cls.voice, 6.0)
        cls.music = os.path.join(cls.work, "bed.wav")
        if not os.path.isfile(cls.music):
            mf.make_beep_bed(cls.music, 8.0)

    def brief(self, **extra):
        """Two beats, real footage, a beep narration: the smallest brief that is a production."""
        data = {"title": "Blueprint fixture", "slug": "bp_fixture",
                "project": guard.rel(self.project), "fps": FPS, "size": [160, 90],
                "voice": {"narration": guard.rel(self.voice)},
                "assets": {"footage_a": {"path": guard.rel(self.clip), "origin": "footage"},
                           "music": {"path": guard.rel(self.music), "origin": "user_audio"}},
                "music": "music",
                "beats": [{"id": "b1", "shot": "layered_push", "uses": ["footage_a"],
                           "say": "one two three four five"},
                          {"id": "b2", "shot": "kinetic_reveal",
                           "say": "six seven eight nine ten eleven"}],
                "deliver": {"output": guard.rel(os.path.join(self.project, "final.mp4"))}}
        data.update(extra)
        return data

    def brief_file(self, name, **extra):
        path = os.path.join(self.work, name + ".brief.json")
        return guard.rel(guard.write_json(path, self.brief(**extra)))

    def generate(self, name, **extra):
        """Brief -> blueprint, into its own file. Returns (repo-relative path, JSON summary)."""
        target = os.path.join(self.work, name + ".blueprint.json")
        code, _text, data = run("blueprint", "generate", self.brief_file(name, **extra),
                                "--no-tts", "--out", guard.rel(target), "--json")
        self.assertEqual(code, 0, data)
        return guard.rel(target), data

    def test_every_shot_names_a_scene_that_exists_and_a_registered_composition(self):
        """The blueprint is data; this pins it to the files that really render it."""
        with open(os.path.join(guard.RECAP, "remotion", "src", "SceneLab.tsx"), "r",
                  encoding="utf-8") as handle:
            registered = handle.read()
        for row in blueprint.SHOTS:
            path = os.path.join(guard.ROOT, row["scene"].replace("/", os.sep))
            self.assertTrue(os.path.isfile(path), row["scene"])
            # SceneLab registers a bench entry as `bench-<slug of the file name>` (src/SceneLab.tsx).
            stem = os.path.basename(row["scene"])[:-len(".tsx")]
            self.assertEqual(row["composition"], "bench-" + stem.replace("_", "-"))
            self.assertIn(stem, registered)

    def test_generate_measures_the_beats_from_the_narration(self):
        path, data = self.generate("measured")
        self.assertEqual(len(data["beats"]), 2)
        self.assertEqual(data["narration"]["engine"], "measured")
        self.assertEqual(data["narration"]["timing"], "word-count estimate")
        self.assertAlmostEqual(data["narration"]["seconds"], 6.0, places=2)
        self.assertEqual(data["beats"][0]["starts_at"], 0)
        self.assertEqual(data["beats"][1]["starts_at"], data["beats"][0]["frames"])
        self.assertTrue(all(row["frames"] >= blueprint.MIN_BEAT_FRAMES for row in data["beats"]))
        self.assertTrue(os.path.isfile(os.path.join(guard.ROOT, path)))

    def test_compile_writes_a_manifest_the_engine_can_plan(self):
        path, data = self.generate("compiled")
        out = os.path.join(self.work, "compiled.manifest.json")
        code, _text, compiled = run("blueprint", "compile", path, "--out", guard.rel(out),
                                    "--json")
        self.assertEqual(code, 0, compiled)
        self.assertEqual(compiled["steps"], ["b1_render", "b2_render", "join", "voice_over",
                                             "duck", "level", "export"])
        plan = manifest.load_plan(out)
        self.assertEqual([step.spec.name for step in plan.steps],
                         ["render_range", "render_range", "concat", "overlay_audio",
                          "duck_audio", "normalize_audio", "export_h264"])
        for step in plan.steps:                       # the matrix's executor, never an override
            self.assertEqual(step.executor, ops.get(step.spec.name).executor, step.id)
        self.assertEqual(plan.steps[0].params["frames"], data["beats"][0]["frames"])
        self.assertEqual(plan.steps[0].inputs["assets"],
                         {"footage_a": manifest.resolve_path(self.clip)})
        self.assertEqual(plan.steps[-1].outputs["video"],
                         manifest.resolve_path(guard.rel(os.path.join(self.project,
                                                                      "final.mp4"))))

    def test_the_brief_must_use_a_shot_the_engine_knows(self):
        brief = guard.read_json(self.brief_file("bad_shot"))
        brief["beats"][0]["shot"] = "ken_burns"
        path = guard.rel(guard.write_json(os.path.join(self.work, "bad_shot.brief.json"), brief))
        code, _text, out = run("blueprint", "generate", path, "--no-tts", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(out["code"], "bad_brief")
        self.assertIn("unknown_shot", [row["code"] for row in out["details"]["errors"]])

    def test_a_footage_shot_without_footage_is_refused(self):
        brief = guard.read_json(self.brief_file("no_footage"))
        brief["beats"][0].pop("uses")
        path = guard.rel(guard.write_json(os.path.join(self.work, "no_footage.brief.json"),
                                          brief))
        code, _text, out = run("blueprint", "generate", path, "--no-tts", "--json")
        self.assertEqual(code, 2)
        self.assertIn("shot_needs_asset", [row["code"] for row in out["details"]["errors"]])

    def test_without_tts_a_missing_narration_is_refused(self):
        brief = guard.read_json(self.brief_file("no_voice"))
        brief["voice"]["narration"] = guard.rel(os.path.join(self.work, "nothing.wav"))
        path = guard.rel(guard.write_json(os.path.join(self.work, "no_voice.brief.json"), brief))
        code, _text, out = run("blueprint", "generate", path, "--no-tts", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(out["code"], "narration_missing")

    def test_compile_refuses_a_blueprint_that_is_not_one(self):
        path = guard.rel(guard.write_json(os.path.join(self.work, "storyboard.json"),
                                          {"schema": 1, "kind": "storyboard", "beats": []}))
        code, _text, out = run("blueprint", "compile", path, "--json")
        self.assertEqual(code, 2)
        self.assertEqual(out["code"], "bad_blueprint")


if __name__ == "__main__":
    unittest.main()

