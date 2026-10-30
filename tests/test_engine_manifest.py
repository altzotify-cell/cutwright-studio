"""Execution manifest + checkpoint (M3, phase 3C).

Run: python -m unittest tests.test_engine_manifest -v      (repo root)

Three layers, separated on purpose:

  * `CheckpointTest`  - pure state: atomic writes, a corrupt checkpoint refused (not trusted),
    cache keys, the resume rule, the cursor.
  * `ManifestValidateTest` - a plan is data, so it is checked as data: unknown op, missing input,
    a paid step under a $0 cap, an AI-origin visual asset, a forward reference, an unsafe output,
    an unapproved gate.
  * `ManifestRunTest` - real media, real executors: a two-step chain through @refs, resume skipping
    cached steps, a deleted output re-running, a changed param re-running, a gate blocking, a
    corrupted checkpoint refused, and one step through Kinocut (skipped when it is not installed).
"""
import json
import os
import shutil
import unittest
from unittest import mock

from cutwright import guard
from cutwright.engine import checkpoint, manifest, ops
from cutwright.engine.executors import ExecutorError, ffmpeg, kinocut
from tests import media_fixtures as mf

WORK = os.path.join(guard.OUT, "engine_manifest")      # inside the fork: the guard allows it
FPS = 24


def out(*parts):
    return os.path.join(WORK, *parts)


def clip():
    """The shared fixture: 96 frames of numbered blocks, no audio (fast to encode)."""
    path = out("src.mp4")
    guard.ensure_dir(WORK)
    if not os.path.isfile(path):
        mf.make_counter_clip(path, frames=96, fps=FPS, with_audio=False)
    return guard.rel(path)


def plan_dict(steps, assets=None, gates=None, **extra):
    """A manifest that passes validation unless the test breaks exactly one thing."""
    data = {
        "schema": 1,
        "run_id": extra.pop("run_id", "probe-0001"),
        "fps": FPS,
        "size": [160, 90],
        "budget": extra.pop("budget", {"mode": "cap", "cap_usd": 0.0}),
        "constraints": {"ai_generated_images": False,
                        "allowed_asset_origins": ["footage", "user_image", "code_graphic",
                                                  "stock_licensed"]},
        "assets": assets if assets is not None else [
            {"id": "src", "path": "out/engine_manifest/src.mp4", "origin": "footage",
             "license": "owner-supplied"}],
        "gates": gates or [],
        "steps": steps,
    }
    data.update(extra)
    return data


def fit_step(step_id, source, frames, target, **extra):
    """A `fit_to_frames` step: the ffmpeg executor, exact frame count, no audio."""
    step = {"id": step_id, "op": "fit_to_frames",
            "inputs": {"src": source},
            "params": {"frames": frames, "fps": FPS, "width": 160, "height": 90},
            "outputs": {"video": target}, "status": "pending", "attempts": 0, "cost_usd": 0.0}
    step.update(extra)
    return step


def errors_of(report, code):
    return [row for row in report["errors"] if row["code"] == code]


class CheckpointTest(unittest.TestCase):
    """The state machine and the resume decision, with no media and no subprocess."""

    def setUp(self):
        self.run_dir = out("state", self._testMethodName)
        guard.ensure_dir(self.run_dir)
        for name in os.listdir(self.run_dir):
            os.remove(os.path.join(self.run_dir, name))

    def state(self, order=("a", "b")):
        return checkpoint.new_state("t-0001", order=list(order))

    def test_write_atomic_leaves_only_the_checkpoint(self):
        state = self.state()
        checkpoint.record(state, "a", status=checkpoint.DONE, cache_key="k")
        path = checkpoint.save(self.run_dir, state)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(os.listdir(self.run_dir), [checkpoint.STATE_FILE])
        self.assertEqual(checkpoint.load(self.run_dir)["steps"]["a"]["cache_key"], "k")

    def test_missing_checkpoint_is_typed_or_defaulted(self):
        with self.assertRaises(checkpoint.CheckpointError) as ctx:
            checkpoint.load(self.run_dir)
        self.assertEqual(ctx.exception.code, "not_found")
        self.assertEqual(checkpoint.load(self.run_dir, default="fresh"), "fresh")

    def test_corrupt_checkpoint_is_refused_not_trusted(self):
        guard.write_text(checkpoint.state_path(self.run_dir), '{"schema": 1, "steps": {')
        with self.assertRaises(checkpoint.CheckpointError) as ctx:
            checkpoint.load(self.run_dir)
        self.assertEqual(ctx.exception.code, "corrupted")

    def test_schema_and_shape_are_checked(self):
        guard.write_json(checkpoint.state_path(self.run_dir), {"schema": 99, "steps": {}})
        with self.assertRaises(checkpoint.CheckpointError) as ctx:
            checkpoint.load(self.run_dir)
        self.assertEqual(ctx.exception.code, "schema_mismatch")
        guard.write_json(checkpoint.state_path(self.run_dir), {"schema": 1, "steps": ["a"]})
        with self.assertRaises(checkpoint.CheckpointError) as again:
            checkpoint.load(self.run_dir)
        self.assertEqual(again.exception.code, "corrupted")

    def test_write_atomic_refuses_paths_outside_the_fork(self):
        outside = os.path.join(os.path.expanduser("~"), "cutwright_should_not_write.json")
        with self.assertRaises(guard.GuardError):
            checkpoint.write_atomic(outside, {"schema": 1, "steps": {}})

    def test_statuses_are_the_five_the_roadmap_names(self):
        self.assertEqual(checkpoint.STATUSES,
                         ("pending", "running", "done", "failed", "skipped"))

    def test_cache_key_changes_with_params_version_and_inputs(self):
        digests = [{"name": "src", "index": 0, "path": "out/a.mp4",
                    "digest": {"sha256": "aaa", "size": 10}}]
        base = checkpoint.cache_key("fit_to_frames", {"frames": 48}, digests, "ffmpeg", "7.1")
        self.assertEqual(base, checkpoint.cache_key("fit_to_frames", {"frames": 48},
                                                    digests, "ffmpeg", "7.1"))
        self.assertNotEqual(base, checkpoint.cache_key("fit_to_frames", {"frames": 47},
                                                       digests, "ffmpeg", "7.1"))
        self.assertNotEqual(base, checkpoint.cache_key("fit_to_frames", {"frames": 48},
                                                       digests, "ffmpeg", "8.0"))
        moved = [{"name": "src", "index": 0, "path": "out/b.mp4",
                  "digest": {"sha256": "bbb", "size": 10}}]
        self.assertNotEqual(base, checkpoint.cache_key("fit_to_frames", {"frames": 48},
                                                       moved, "ffmpeg", "7.1"))
        self.assertNotEqual(base, checkpoint.cache_key("crop_to_size", {"frames": 48},
                                                       digests, "ffmpeg", "7.1"))

    def test_outputs_intact_detects_missing_and_changed_files(self):
        path = out("state", "output.bin")
        guard.ensure_dir(os.path.dirname(path))
        guard.write_bytes(path, b"one")
        digests = {"video": checkpoint.digest_file(path)}
        self.assertEqual(checkpoint.outputs_intact({"video": path}, digests), (True, ""))
        self.assertEqual(checkpoint.outputs_intact({"video": guard.rel(path)}, digests),
                         (True, ""))          # recorded repo-relative: still resolved correctly
        guard.write_bytes(path, b"two")
        ok, reason = checkpoint.outputs_intact({"video": path}, digests)
        self.assertFalse(ok)
        self.assertIn("changed", reason)
        os.remove(path)
        ok, reason = checkpoint.outputs_intact({"video": path}, digests)
        self.assertFalse(ok)
        self.assertIn("missing", reason)

    def test_step_cached_needs_a_done_step_and_the_same_key(self):
        state = self.state()
        path = out("state", "cached.mp4")
        guard.write_bytes(path, b"frames")
        outputs, digests = {"video": path}, {"video": checkpoint.digest_file(path)}
        self.assertFalse(checkpoint.step_cached(state, "a", "k1", outputs)[0])
        checkpoint.record(state, "a", status=checkpoint.DONE, cache_key="k1",
                          output_digests=digests)
        self.assertTrue(checkpoint.step_cached(state, "a", "k1", outputs)[0])
        self.assertFalse(checkpoint.step_cached(state, "a", "k2", outputs)[0])
        checkpoint.record(state, "a", cache_key="k1", output_digests={})
        self.assertFalse(checkpoint.step_cached(state, "a", "k1", outputs)[0])

    def test_cursor_points_at_the_first_unfinished_step(self):
        state = self.state(("a", "b", "c"))
        checkpoint.record(state, "a", status=checkpoint.DONE)
        self.assertEqual(checkpoint.cursor(state)["next"], "b")
        checkpoint.record(state, "b", status=checkpoint.FAILED, reason="boom")
        self.assertEqual(checkpoint.cursor(state)["next"], "b")
        self.assertEqual(checkpoint.cursor(state)["failed"], ["b"])
        checkpoint.record(state, "b", status=checkpoint.DONE)
        self.assertEqual(checkpoint.cursor(state)["next"], "c")
        self.assertEqual(checkpoint.cursor(state)["done"], ["a", "b"])

    def test_a_kill_mid_step_leaves_a_readable_checkpoint(self):
        """`running` is written before the executor starts, so a kill leaves a resumable record."""
        state = self.state()
        checkpoint.record(state, "a", status=checkpoint.RUNNING, attempts=1, started="now")
        checkpoint.save(self.run_dir, state)
        reloaded = checkpoint.load(self.run_dir)
        self.assertEqual(reloaded["steps"]["a"]["status"], checkpoint.RUNNING)
        self.assertEqual(checkpoint.cursor(reloaded)["next"], "a")


class DigestIdentityTest(unittest.TestCase):
    """How a file is identified for the cache key (ASSET_HANDLES item 5, pinned in M5.5C).

    Two rules that a refactor could silently break, and both of them decide whether a cached step is
    genuinely reusable:

      * below HASH_LIMIT (64 MiB) identity is the sha256; above it, size + mtime and NO hashing
        (hashing a multi-GB film costs minutes and proves nothing new);
      * `memo=True` (used for step INPUTS) trades a stale hash for speed, keyed on (path, size,
        mtime_ns). It is not the default because an output can be rewritten with the same length
        inside one mtime tick, and `outputs_intact` must see that.
    """

    def setUp(self):
        self.dir = out("digest", self._testMethodName)
        guard.ensure_dir(self.dir)
        for name in os.listdir(self.dir):
            os.remove(os.path.join(self.dir, name))
        checkpoint._DIGEST_MEMO.clear()          # module-level cache, shared by every test

    def tearDown(self):
        checkpoint._DIGEST_MEMO.clear()

    def _file(self, name="clip.bin", size=4096, fill=b"\xa5"):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as handle:
            handle.write(fill * size)
        return path

    def _counting_hash(self):
        """A sha256_file that records every call and still returns the real digest."""
        calls = []
        real = guard.sha256_file

        def counting(path):
            calls.append(path)
            return real(path)

        return calls, counting

    def test_the_threshold_is_64_mib(self):
        self.assertEqual(checkpoint.HASH_LIMIT, 64 << 20)

    def test_below_the_limit_identity_is_the_sha256(self):
        path = self._file()
        digest = checkpoint.digest_file(path)
        self.assertEqual(sorted(digest), ["sha256", "size"])
        self.assertEqual(digest["size"], 4096)
        self.assertEqual(len(digest["sha256"]), 64)

    def test_above_the_limit_identity_is_size_and_mtime_and_nothing_is_hashed(self):
        path = os.path.join(self.dir, "feature.bin")
        with open(path, "wb") as handle:
            handle.truncate(checkpoint.HASH_LIMIT + 1)      # sparse: no 64 MiB write
        with mock.patch.object(guard, "sha256_file",
                               side_effect=AssertionError("a big file must never be hashed")):
            digest = checkpoint.digest_file(path, memo=True)
        self.assertEqual(sorted(digest), ["mtime_ns", "size"])
        self.assertEqual(digest["size"], checkpoint.HASH_LIMIT + 1)

    def test_the_memo_reuses_a_digest_until_the_file_changes(self):
        path = self._file()
        calls, counting = self._counting_hash()
        with mock.patch.object(guard, "sha256_file", counting):
            first = checkpoint.digest_file(path, memo=True)
            again = checkpoint.digest_file(path, memo=True)
        self.assertEqual(calls, [path])                  # hashed once, then served from the memo
        self.assertEqual(first, again)
        changed = self._file(size=8192)                  # same path, new size
        with mock.patch.object(guard, "sha256_file", counting):
            third = checkpoint.digest_file(path, memo=True)
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(first["sha256"], third["sha256"])
        self.assertEqual(third, checkpoint.digest_file(changed))   # and it agrees with a plain digest

    def test_the_memo_is_opt_in_so_an_in_place_rewrite_is_seen(self):
        """The documented risk: same length, same mtime tick -> the memo would return a stale hash."""
        path = self._file(fill=b"\xa5")
        original = checkpoint.digest_file(path, memo=True)   # this is what populates the memo
        stamp = guard.file_sig(path)["mtime_ns"]
        guard.write_bytes(path, b"\x5a" * 4096)          # different bytes, identical length
        os.utime(path, ns=(stamp, stamp))               # ...and the same mtime
        # memo=True cannot tell: same path, same size, same mtime_ns. That is why it is inputs-only.
        self.assertEqual(checkpoint.digest_file(path, memo=True)["sha256"], original["sha256"])
        # The default (no memo) hashes again, so `outputs_intact` does see the rewrite.
        self.assertNotEqual(checkpoint.digest_file(path)["sha256"], original["sha256"])

    def test_input_digests_use_the_memo_and_flatten_the_handle_table(self):
        clip = self._file(name="footage_a.mp4")
        calls, counting = self._counting_hash()
        with mock.patch.object(guard, "sha256_file", counting):
            rows = checkpoint.input_digests({"scene": clip, "assets": {"footage_a": clip}})
            checkpoint.input_digests({"scene": clip, "assets": {"footage_a": clip}})
        self.assertEqual([row["name"] for row in rows], ["assets[footage_a]", "scene"])
        self.assertEqual(len(calls), 1)                  # one path, hashed once for both rows
        self.assertEqual(rows[0]["path"], guard.rel(clip))



class ManifestValidateTest(unittest.TestCase):
    """A plan is data, so it is checked as data: every rejection is a typo that would cost a render."""

    def test_a_good_manifest_validates(self):
        report = manifest.validate(plan_dict([fit_step("a", "@asset.src", 48,
                                                       "out/runs/v1/a.mp4")]))
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["steps"], 1)
        self.assertEqual(report["cost_usd"], 0.0)
        self.assertTrue(report["run_dir"].endswith(os.path.join("out", "runs", "probe-0001")))

    def test_unknown_op_is_named_with_the_step(self):
        step = {"id": "a", "op": "make_magic", "inputs": {}, "params": {},
                "outputs": {"video": "out/runs/v1/a.mp4"}}
        report = manifest.validate(plan_dict([step]))
        self.assertFalse(report["ok"])
        self.assertEqual(errors_of(report, "unknown_op")[0]["step"], "a")

    def test_missing_and_unknown_inputs_are_rejected(self):
        step = fit_step("a", "@asset.src", 48, "out/runs/v1/a.mp4")
        step["inputs"] = {}
        self.assertEqual(errors_of(manifest.validate(plan_dict([step])),
                                   "missing_input")[0]["step"], "a")
        step = fit_step("a", "@asset.src", 48, "out/runs/v1/a.mp4",
                        inputs={"src": "@asset.src", "music": "m.wav"})
        self.assertTrue(errors_of(manifest.validate(plan_dict([step])), "unknown_input"))

    def test_bad_param_is_rejected_before_any_render(self):
        report = manifest.validate(plan_dict([fit_step("a", "@asset.src", "many",
                                                       "out/runs/v1/a.mp4")]))
        self.assertTrue(errors_of(report, "invalid_params"))

    def test_a_paid_step_under_a_zero_cap_is_refused(self):
        step = fit_step("a", "@asset.src", 48, "out/runs/v1/a.mp4", cost_usd=0.02)
        report = manifest.validate(plan_dict([step]))
        self.assertEqual(errors_of(report, "budget_exceeded")[0]["step"], "a")
        raised = plan_dict([step], budget={"mode": "cap", "cap_usd": 0.02})
        self.assertTrue(manifest.validate(raised)["ok"])

    def test_visual_asset_origin_is_constrained_but_audio_is_not(self):
        visual = [{"id": "src", "path": "out/engine_manifest/src.png", "origin": "ai_generated"}]
        report = manifest.validate(plan_dict([fit_step("a", "@asset.src", 48,
                                                       "out/runs/v1/a.mp4")], assets=visual))
        self.assertTrue(errors_of(report, "asset_origin"))
        audio = [{"id": "src", "path": "out/voice.wav", "origin": "user_audio"}]
        report = manifest.validate(plan_dict([fit_step("a", "@asset.src", 48,
                                                       "out/runs/v1/a.mp4")], assets=audio))
        self.assertFalse(errors_of(report, "asset_origin"))

    def test_ai_generated_images_must_be_off(self):
        data = plan_dict([fit_step("a", "@asset.src", 48, "out/runs/v1/a.mp4")])
        data["constraints"]["ai_generated_images"] = True
        self.assertTrue(errors_of(manifest.validate(data), "ai_assets_forbidden"))

    def test_forward_reference_is_rejected(self):
        steps = [fit_step("a", "@b.video", 48, "out/runs/v1/a.mp4"),
                 fit_step("b", "@asset.src", 48, "out/runs/v1/b.mp4")]
        report = manifest.validate(plan_dict(steps))
        self.assertEqual(errors_of(report, "forward_ref")[0]["step"], "a")

    def test_unknown_reference_is_rejected(self):
        report = manifest.validate(plan_dict([fit_step("a", "@asset.ghost", 48,
                                                       "out/runs/v1/a.mp4")]))
        self.assertTrue(errors_of(report, "unknown_ref"))


    def test_output_outside_the_fork_is_refused(self):
        outside = os.path.join(os.path.expanduser("~"), "escape.mp4")
        report = manifest.validate(plan_dict([fit_step("a", "@asset.src", 48, outside)]))
        self.assertTrue(errors_of(report, "unsafe_output"))

    def test_two_steps_may_not_claim_one_output(self):
        steps = [fit_step("a", "@asset.src", 48, "out/runs/v1/same.mp4"),
                 fit_step("b", "@asset.src", 24, "out/runs/v1/same.mp4")]
        self.assertEqual(errors_of(manifest.validate(plan_dict(steps)),
                                   "output_collision")[0]["step"], "b")

    def test_executor_override_needs_a_reason(self):
        step = fit_step("a", "@asset.src", 48, "out/runs/v1/a.mp4", executor="kinocut")
        self.assertTrue(errors_of(manifest.validate(plan_dict([step])), "executor_conflict"))
        step["executor_reason"] = "test: exercising the override path on purpose"
        report = manifest.validate(plan_dict([step]))
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue([w for w in report["warnings"] if w["code"] == "executor_override"])

    def test_unknown_executor_is_rejected(self):
        # M5.5A wired "remotion" in, so the example has to be a name no module answers to.
        step = fit_step("a", "@asset.src", 48, "out/runs/v1/a.mp4", executor="not_an_executor",
                        executor_reason="a name that is not wired into the engine")
        self.assertTrue(errors_of(manifest.validate(plan_dict([step])), "unknown_executor"))

    def test_gate_before_an_unknown_step_is_rejected(self):
        gates = [{"id": "final_ok", "before_step": "ghost", "approved": False}]
        report = manifest.validate(plan_dict([fit_step("a", "@asset.src", 48,
                                                       "out/runs/v1/a.mp4")], gates=gates))
        self.assertTrue(errors_of(report, "unknown_gate_step"))

    def test_duplicate_step_ids_are_rejected(self):
        steps = [fit_step("a", "@asset.src", 48, "out/runs/v1/1.mp4"),
                 fit_step("a", "@asset.src", 24, "out/runs/v1/2.mp4")]
        self.assertTrue(errors_of(manifest.validate(plan_dict(steps)), "duplicate_step"))

    def test_derive_raises_with_every_error_attached(self):
        with self.assertRaises(manifest.ManifestError) as ctx:
            manifest.derive(plan_dict([{"id": "a", "op": "make_magic"}]))
        self.assertEqual(ctx.exception.code, "unknown_op")
        self.assertTrue(ctx.exception.errors)

    def test_executor_kwargs_translate_frames_to_seconds(self):
        kwargs = ops.executor_kwargs(ops.get("trim_exact"),
                                     {"start_frame": 37, "frames": 50, "duration": None,
                                      "accurate": False}, fps=24)
        self.assertAlmostEqual(kwargs["start"], 37 / 24.0, places=5)
        self.assertAlmostEqual(kwargs["duration"], 50 / 24.0, places=5)
        self.assertNotIn("start_frame", kwargs)
        trans = ops.executor_kwargs(ops.get("transition"),
                                    {"type": "fade", "duration": 0.5}, fps=24)
        self.assertEqual(trans, {"transition": "fade", "transition_duration": 0.5})
        plain = ops.executor_kwargs(ops.get("fit_to_frames"), {"frames": 48, "crf": 18}, fps=24)
        self.assertEqual(plain, {"frames": 48, "crf": 18})



@unittest.skipUnless(ffmpeg.available(), "ffmpeg not on PATH")
class ManifestRunTest(unittest.TestCase):
    """Real media through the real executors: nothing here is mocked."""

    def setUp(self):
        self.run_dir = out("runs", self._testMethodName)
        if os.path.isdir(self.run_dir):
            shutil.rmtree(self.run_dir)
        guard.ensure_dir(self.run_dir)
        self.source = clip()

    def plan(self, steps, gates=None, run_dir=None):
        data = plan_dict(steps, gates=gates, run_id=self._testMethodName,
                         assets=[{"id": "src", "path": self.source, "origin": "footage"}])
        return manifest.derive(data, versions={}, run_dir=run_dir or self.run_dir)

    def chain(self):
        """cut_1 -> fit_1, the second reading the first through an @step.output reference."""
        return [fit_step("cut_1", "@asset.src", 48, guard.rel(os.path.join(self.run_dir,
                                                                         "cut_1.mp4"))),
                fit_step("fit_1", "@cut_1.video", 24, guard.rel(os.path.join(self.run_dir,
                                                                            "fit_1.mp4")))]

    def path(self, name):
        return os.path.join(self.run_dir, name)

    def test_a_chain_runs_and_every_step_is_recorded(self):
        plan = self.plan(self.chain())
        report = manifest.run(plan)
        self.assertTrue(report["ok"], report.get("stopped"))
        self.assertEqual([row["status"] for row in report["steps"]], ["done", "done"])
        self.assertEqual(mf.probe_counts(self.path("cut_1.mp4"))[0], 48)
        self.assertEqual(mf.probe_counts(self.path("fit_1.mp4"))[0], 24)
        state = checkpoint.load(self.run_dir)
        self.assertEqual(state["steps"]["cut_1"]["cache_key"], plan.steps[0].cache_key)
        self.assertTrue(state["steps"]["cut_1"]["output_digests"]["video"]["sha256"])
        self.assertEqual(state["steps"]["fit_1"]["executor"], "ffmpeg")
        status = manifest.status(self.run_dir)
        self.assertEqual(status["cursor"]["done"], ["cut_1", "fit_1"])
        self.assertEqual([row["stale"] for row in status["steps"]], ["", ""])
        self.assertTrue(os.path.isfile(checkpoint.state_path(self.run_dir)))

    def test_resume_skips_cached_steps(self):
        manifest.run(self.plan(self.chain()))
        again = manifest.run(self.plan(self.chain()))
        self.assertTrue(again["ok"])
        self.assertEqual([row["status"] for row in again["steps"]], ["skipped", "skipped"])
        self.assertIn("cached", again["steps"][0]["reason"])

    def test_a_cached_resume_keeps_the_step_done(self):
        """A skip must not overwrite `done`, or the run after it would re-render everything."""
        manifest.run(self.plan(self.chain()))
        manifest.run(self.plan(self.chain()))
        state = checkpoint.load(self.run_dir)
        self.assertEqual([state["steps"][name]["status"] for name in ("cut_1", "fit_1")],
                         ["done", "done"])
        self.assertEqual(state["cursor"]["done"], ["cut_1", "fit_1"])
        third = manifest.run(self.plan(self.chain()))
        self.assertEqual([row["status"] for row in third["steps"]], ["skipped", "skipped"])

    def test_a_deleted_output_makes_that_step_run_again(self):
        manifest.run(self.plan(self.chain()))
        os.remove(self.path("fit_1.mp4"))
        again = manifest.run(self.plan(self.chain()))
        self.assertEqual([row["status"] for row in again["steps"]], ["skipped", "done"])
        self.assertIn("missing", again["steps"][1]["reason"])
        self.assertEqual(mf.probe_counts(self.path("fit_1.mp4"))[0], 24)

    def test_a_changed_param_runs_that_step_only(self):
        manifest.run(self.plan(self.chain()))
        steps = self.chain()
        steps[1]["params"]["frames"] = 20
        again = manifest.run(self.plan(steps))
        self.assertEqual([row["status"] for row in again["steps"]], ["skipped", "done"])
        self.assertIn("cache key", again["steps"][1]["reason"])
        self.assertEqual(mf.probe_counts(self.path("fit_1.mp4"))[0], 20)

    def test_a_killed_run_resumes_from_its_cursor(self):
        manifest.run(self.plan(self.chain()), only=["cut_1"])
        self.assertEqual(checkpoint.load(self.run_dir)["cursor"]["next"], "fit_1")
        again = manifest.run(self.plan(self.chain()))
        self.assertEqual([row["status"] for row in again["steps"]], ["skipped", "done"])
        self.assertEqual(mf.probe_counts(self.path("fit_1.mp4"))[0], 24)

    def test_a_gate_blocks_until_it_is_approved(self):
        gates = [{"id": "final_ok", "before_step": "fit_1", "approved": False}]
        blocked = manifest.run(self.plan(self.chain(), gates=gates))
        self.assertFalse(blocked["ok"])
        self.assertIn("gate", blocked["stopped"])
        self.assertEqual([row["status"] for row in blocked["steps"]], ["done", "skipped"])
        self.assertFalse(os.path.exists(self.path("fit_1.mp4")))
        gates[0]["approved"] = True
        allowed = manifest.run(self.plan(self.chain(), gates=gates))
        self.assertTrue(allowed["ok"], allowed.get("stopped"))
        self.assertEqual([row["status"] for row in allowed["steps"]], ["skipped", "done"])

    def test_dry_run_writes_nothing(self):
        dry_dir = out("runs", "dry")
        if os.path.isdir(dry_dir):
            shutil.rmtree(dry_dir)
        report = manifest.run(self.plan(self.chain(), run_dir=dry_dir), dry_run=True)
        self.assertTrue(report["ok"])
        self.assertEqual([row["status"] for row in report["steps"]], ["would_run", "would_run"])
        self.assertFalse(os.path.exists(dry_dir))

    def test_a_corrupted_checkpoint_is_refused_not_trusted(self):
        manifest.run(self.plan(self.chain()))
        guard.write_text(checkpoint.state_path(self.run_dir), '{"schema": 1, "steps": ')
        with self.assertRaises(checkpoint.CheckpointError) as ctx:
            manifest.status(self.run_dir)
        self.assertEqual(ctx.exception.code, "corrupted")
        with self.assertRaises(checkpoint.CheckpointError):
            manifest.run(self.plan(self.chain()))



@unittest.skipUnless(kinocut.available(), "Kinocut is not installed in .venvs\\kinocut")
class ManifestKinocutTest(unittest.TestCase):
    """One step through the OTHER executor, so both halves of the engine are proven by a run."""

    def setUp(self):
        self.run_dir = out("runs", self._testMethodName)
        if os.path.isdir(self.run_dir):
            shutil.rmtree(self.run_dir)
        guard.ensure_dir(self.run_dir)
        self.source = clip()

    def test_a_trim_runs_through_kinocut_and_lands_frame_exact(self):
        data = plan_dict([{"id": "cut", "op": "trim_exact",
                           "inputs": {"src": "@asset.src"},
                           "params": {"start_frame": 24, "frames": 24},
                           "outputs": {"video": guard.rel(os.path.join(self.run_dir,
                                                                       "cut.mp4"))}}],
                         run_id=self._testMethodName,
                         assets=[{"id": "src", "path": self.source, "origin": "footage"}])
        plan = manifest.derive(data, versions={}, run_dir=self.run_dir)
        self.assertEqual(plan.steps[0].executor, "kinocut")
        self.assertIn("trim returned exact frame ids", plan.steps[0].executor_reason)
        report = manifest.run(plan)
        self.assertTrue(report["ok"], report.get("stopped"))
        self.assertEqual(report["steps"][0]["executor"], "kinocut")
        ids = mf.frame_ids(os.path.join(self.run_dir, "cut.mp4"))
        self.assertEqual(ids, list(range(24, 48)))
        state = checkpoint.load(self.run_dir)
        self.assertEqual(state["steps"]["cut"]["executor"], "kinocut")
        self.assertTrue(state["steps"]["cut"]["output_digests"]["video"]["sha256"])


class FakeResult:
    """Stands in for an ExecResult: the retry tests exercise the state machine, not an encode."""

    seconds = 0.5
    warnings = ()

    def to_dict(self):
        return {"executor": "ffmpeg", "op": "fit_to_frames", "returncode": 0}


@unittest.skipUnless(ffmpeg.available(), "ffmpeg not on PATH (routing needs it)")
class ManifestRetryTest(unittest.TestCase):
    """Retry policy from the roadmap: 2 attempts for a transient failure, 1 for a deterministic one.

    `manifest._call` is patched, so no encoder runs: what is under test is the state machine and
    what it records, not ffmpeg.
    """

    def setUp(self):
        self.run_dir = out("runs", self._testMethodName)
        if os.path.isdir(self.run_dir):
            shutil.rmtree(self.run_dir)
        guard.ensure_dir(self.run_dir)

    def plan(self):
        step = fit_step("a", "@asset.src", 24, guard.rel(os.path.join(self.run_dir, "a.mp4")))
        return manifest.derive(plan_dict([step], run_id=self._testMethodName), versions={},
                               run_dir=self.run_dir, strict_files=False)

    def test_a_transient_failure_is_retried_once_then_succeeds(self):
        calls = []

        def flaky(step, overwrite=False):
            calls.append(overwrite)
            if len(calls) == 1:
                raise ExecutorError("ffmpeg", step.spec.name, "timed out", code="timeout",
                                    transient=True)
            guard.write_bytes(step.outputs["video"], b"fake frames")
            return FakeResult()

        with mock.patch.object(manifest, "_call", flaky):
            report = manifest.run(self.plan())
        self.assertTrue(report["ok"], report.get("stopped"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(report["steps"][0]["attempts"], 2)
        self.assertEqual(calls, [False, True])      # overwrite only on the retry
        state = checkpoint.load(self.run_dir)
        self.assertEqual(state["steps"]["a"]["status"], "done")
        self.assertEqual(state["steps"]["a"]["attempts"], 2)

    def test_a_deterministic_failure_is_not_retried(self):
        calls = []

        def broken(step, overwrite=False):
            calls.append(overwrite)
            raise ExecutorError("ffmpeg", step.spec.name, "bad filter", code="bad_filter")

        with mock.patch.object(manifest, "_call", broken):
            report = manifest.run(self.plan())
        self.assertFalse(report["ok"])
        self.assertEqual(len(calls), 1)
        self.assertIn("bad_filter", report["stopped"])
        state = checkpoint.load(self.run_dir)
        self.assertEqual(state["steps"]["a"]["status"], "failed")
        self.assertEqual(state["steps"]["a"]["attempts"], 1)
        self.assertEqual(state["steps"]["a"]["error"]["code"], "bad_filter")

