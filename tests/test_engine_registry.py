"""FFmpeg executor + op registry (M3, phase 3B).

Run: python -m unittest tests.test_engine_registry -v      (repo root)

Four layers, deliberately separated:

  * `FfmpegArgvTest`  - pure: argv shape, pre-flight errors, ffmpeg-stderr -> code mapping.
  * `FfmpegRealTest`  - real media: fit to an exact frame count (tpad clone), crop that fills,
    and the audio pass, each decoded/probed back. Skipped when ffmpeg is absent.
  * `OpsTableTest`    - the table is data, so it is checked as data: unique names, real targets,
    and (roadmap M3) an op may not name an executor without evidence that executor passed.
  * `RegistryTest`    - routing: matrix default, an override only with a reason, a missing
    executor reported instead of silently swapped, envelope capped, params checked on the way.
"""
import argparse
import math
import os
import struct
import unittest
import wave
from unittest import mock

from cutwright import cli, guard, probe
from cutwright.engine import envelopes, ops, registry
from cutwright.engine.executors import ExecutorError, ExecutorTimeout
from cutwright.engine.executors import ffmpeg, kinocut
from tests import media_fixtures as mf

WORK = os.path.join(guard.OUT, "engine_registry")     # inside the fork: the guard allows it
FPS = 24


def out(name):
    return os.path.join(WORK, name)


def tone(path, freq=440.0, seconds=1.0, rate=mf.RATE, amp=10000):
    """Mono 16-bit WAV, so the audio pass has a real file to attach."""
    samples = bytearray()
    for i in range(int(seconds * rate)):
        samples += struct.pack("<h", int(amp * math.sin(2 * math.pi * freq * i / rate)))
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(bytes(samples))
    return path


class FfmpegArgvTest(unittest.TestCase):
    """No subprocess: only the arguments and the checks that run before ffmpeg starts."""

    def test_global_flags_come_first(self):
        argv = ffmpeg.build_argv(["-i", "in.mp4", "out.mp4"])
        self.assertEqual(argv[1:5], ["-nostdin", "-n", "-loglevel", "error"])
        self.assertEqual(argv[-2:], ["in.mp4", "out.mp4"])

    def test_overwrite_switches_to_dash_y(self):
        self.assertIn("-y", ffmpeg.build_argv([], overwrite=True))
        self.assertNotIn("-y", ffmpeg.build_argv([]))

    def test_numbers_are_stringified_not_formatted(self):
        argv = ffmpeg.build_argv(["-frames:v", 53, "-crf", 18])
        self.assertEqual(argv[-4:], ["-frames:v", "53", "-crf", "18"])

    @unittest.skipUnless(ffmpeg.available(), "ffmpeg not on PATH")
    def test_missing_input_is_a_typed_error_before_spawn(self):
        with self.assertRaises(ExecutorError) as ctx:
            ffmpeg.fit_to_frames(out("nope.mp4"), out("x.mp4"), frames=10)
        self.assertEqual(ctx.exception.code, "input_missing")
        self.assertFalse(ctx.exception.transient)
        self.assertFalse(os.path.exists(out("x.mp4")))

    @unittest.skipUnless(ffmpeg.available(), "ffmpeg not on PATH")
    def test_existing_output_needs_overwrite(self):
        guard.ensure_dir(WORK)
        path = out("exists.mp4")
        with open(path, "wb") as handle:
            handle.write(b"not a video")
        with self.assertRaises(ExecutorError) as ctx:
            ffmpeg.crop_to_size(path, path, 90, 90)
        self.assertEqual(ctx.exception.code, "output_exists")
        with self.assertRaises(ExecutorError) as again:
            ffmpeg.fit_to_frames(path, path, frames=5)
        self.assertEqual(again.exception.code, "output_exists")

    def test_bad_counts_are_named_parameters(self):
        for bad, code in ((0, "bad_param"), (1.5, "bad_param"), ("many", "bad_param")):
            with self.assertRaises(ExecutorError) as ctx:
                ffmpeg.fit_to_frames("in.mp4", out("x.mp4"), frames=bad)
            self.assertEqual(ctx.exception.code, code, "frames=%r" % (bad,))
            self.assertIn("frames", ctx.exception.message)

    def test_odd_size_and_unknown_fill_are_refused(self):
        with self.assertRaises(ExecutorError) as ctx:
            ffmpeg.fit_to_frames("in.mp4", out("x.mp4"), frames=10, width=101, height=99)
        self.assertEqual(ctx.exception.code, "bad_param")
        with self.assertRaises(ExecutorError) as fill:
            ffmpeg.fit_to_frames("in.mp4", out("x.mp4"), frames=10, fill="blur")
        self.assertEqual(fill.exception.code, "unsupported_fill")
        self.assertIn("reframe_crop", fill.exception.suggested)

    def test_stderr_maps_to_a_code(self):
        cases = (("in.mp4: No such file or directory", "input_missing"),
                 ("Output file #0 does not contain any stream", "ffmpeg_failed"),
                 ("Stream map '1:a:0' matches no streams.", "no_audio_stream"),
                 ("[AVFilterGraph] Error initializing filter 'crop'", "bad_filter"),
                 ("Unknown encoder 'libx265'", "encoder_missing"))
        for text, expected in cases:
            err = ffmpeg.error_from("op", ["ffmpeg"], 1, "", "ffmpeg version 7.1\n" + text)
            self.assertEqual(err.code, expected, text)
            self.assertEqual(err.message, text)
            self.assertFalse(err.transient)

    def test_write_guard_refuses_paths_outside_the_fork(self):
        outside = os.path.join(os.path.expanduser("~"), "cutwright_should_not_write.mp4")
        with self.assertRaises(guard.GuardError):
            ffmpeg.fit_to_frames("in.mp4", outside, frames=10)
        with self.assertRaises(guard.GuardError):
            ffmpeg.overlay_audio("in.mp4", "a.wav", outside)


@unittest.skipUnless(ffmpeg.available(), "ffmpeg not on PATH")
class FfmpegRealTest(unittest.TestCase):
    """The three matrix roles on real media, decoded/probed back afterwards.

    Fixtures are 2 s / 48 frames at 160x90, so the whole class costs a couple of seconds.
    """

    FRAMES = 48

    @classmethod
    def setUpClass(cls):
        guard.ensure_dir(WORK)
        cls.src = mf.make_counter_clip(out("src_48.mp4"), frames=cls.FRAMES, fps=FPS)
        # A video-only clip, exactly what the audio pass consumes in the real flow
        # (matrix row 9: composite-layers returns has_audio:false).
        cls.silent = out("silent_24.mp4")
        ffmpeg.fit_to_frames(cls.src, cls.silent, frames=24, fps=FPS, overwrite=True)
        cls.tone = tone(out("tone_1s.wav"), 440.0, 1.0)

    def test_fit_clones_the_last_frame_to_hit_an_exact_count(self):
        target = out("fit_72.mp4")
        res = ffmpeg.fit_to_frames(self.src, target, frames=72, fps=FPS, overwrite=True)
        self.assertTrue(res.ok)
        self.assertTrue(res.payload.get("video_only"))
        frames, seconds, audio = mf.probe_counts(target)
        self.assertEqual(frames, 72)                     # exact, not "about 3 s"
        self.assertAlmostEqual(seconds, 3.0, delta=0.05)
        self.assertIsNone(audio)                         # video-only by design
        ids = mf.frame_ids(target)
        self.assertEqual(ids[:self.FRAMES], list(range(self.FRAMES)))
        self.assertEqual(ids[self.FRAMES:], [self.FRAMES - 1] * 24)   # tpad cloned frame 47

    def test_fit_letterboxes_into_a_size_without_stretching(self):
        target = out("fit_160x160.mp4")
        res = ffmpeg.fit_to_frames(self.src, target, frames=24, fps=FPS,
                                   width=160, height=160, overwrite=True)
        self.assertTrue(res.ok)
        info = probe.media_info(target)
        self.assertEqual((info["width"], info["height"]), (160, 160))
        self.assertEqual(mf.probe_counts(target)[0], 24)

    def test_crop_fills_the_target_size(self):
        target = out("crop_90.mp4")
        res = ffmpeg.crop_to_size(self.src, target, width=90, height=90, frames=24,
                                  overwrite=True)
        self.assertTrue(res.ok)
        info = probe.media_info(target)
        self.assertEqual((info["width"], info["height"]), (90, 90))
        self.assertEqual(mf.probe_counts(target)[0], 24)

    def test_audio_pass_attaches_sound_without_touching_the_frames(self):
        target = out("silent_24_audio.mp4")
        res = ffmpeg.overlay_audio(self.silent, self.tone, target, duration=1.0, overwrite=True)
        self.assertTrue(res.ok)
        self.assertEqual(res.warnings, [])
        frames, _seconds, audio = mf.probe_counts(target)
        self.assertEqual(frames, 24)                     # -c:v copy: frames untouched
        self.assertAlmostEqual(audio, 1.0, delta=0.08)

    def test_audio_pass_warns_when_it_falls_back_to_shortest(self):
        target = out("silent_24_shortest.mp4")
        res = ffmpeg.overlay_audio(self.silent, self.tone, target, overwrite=True)
        self.assertTrue(res.ok)
        self.assertTrue(any("-shortest" in warning for warning in res.warnings))


    def test_timeout_is_transient(self):
        with self.assertRaises(ExecutorTimeout) as ctx:
            ffmpeg.fit_to_frames(self.src, out("fit_timeout.mp4"), frames=600, fps=FPS,
                                 overwrite=True, timeout=0.05)
        self.assertTrue(ctx.exception.transient)
        self.assertEqual(ctx.exception.code, "timeout")


class OpsTableTest(unittest.TestCase):
    """The op table is data, so it is checked as data - before anything renders."""

    def test_names_are_unique_and_stages_are_known(self):
        names = ops.names()
        self.assertEqual(len(names), len(set(names)))
        for spec in ops.OPS:
            self.assertIn(spec.stage, ops.STAGES, spec.name)

    def test_every_op_names_a_real_target_in_its_executor(self):
        for spec in ops.OPS:
            module = registry.MODULES.get(spec.executor)
            if module is None:                       # e.g. "current", wired in M4
                continue
            self.assertTrue(callable(getattr(module, spec.target, None)),
                            "%s -> %s.%s is missing" % (spec.name, spec.executor, spec.target))

    def test_no_op_names_an_executor_without_passing_evidence(self):
        """Roadmap M3: an op may not claim an executor the matrix has no evidence for.

        M5.5A adds the `remotion` executor, which the M2 matrix has no row for (the matrix measures
        EDITING; Remotion DRAWS), so its two ops quote their own measurement file instead. Every
        kinocut and ffmpeg op still has to quote an M2 row.
        """
        for spec in ops.OPS:
            status = registry.evidence_status(spec)
            self.assertTrue(status["ok"],
                            "%s -> %s: %s" % (spec.name, spec.executor, status["reason"]))
            prefix = "docs/evidence/m55_" if spec.executor == "remotion" else "docs/evidence/m2_"
            self.assertTrue(spec.evidence.startswith(prefix), spec.name)
            self.assertTrue(spec.executor_reason, spec.name)

    def test_executors_come_from_the_matrix_not_from_taste(self):
        by_executor = {}
        for spec in ops.OPS:
            by_executor.setdefault(spec.executor, []).append(spec.name)
        self.assertEqual(sorted(by_executor), ["ffmpeg", "kinocut", "remotion"])
        self.assertEqual(sorted(by_executor["ffmpeg"]),
                         ["fit_to_frames", "overlay_audio", "reframe_crop"])
        self.assertEqual(sorted(by_executor["remotion"]), ["render_range", "render_still"])

    def test_defaults_are_filled_in(self):
        params = ops.validate_params("fit_to_frames", {"frames": 53})
        self.assertEqual(params["frames"], 53)
        self.assertEqual(params["fps"], 24)
        self.assertEqual(params["fill"], "pad")
        self.assertEqual(params["crf"], 18)
        self.assertIsNone(params["width"])

    def test_unknown_parameter_is_refused_with_the_valid_list(self):
        with self.assertRaises(ops.OpError) as ctx:
            ops.validate_params("fit_to_frames", {"frames": 10, "speed": 2})
        self.assertEqual(ctx.exception.code, "unknown_param")
        self.assertEqual(ctx.exception.param, "speed")
        self.assertIn("frames", ctx.exception.suggested)

    def test_missing_required_parameter_is_named(self):
        with self.assertRaises(ops.OpError) as ctx:
            ops.validate_params("fit_to_frames", {})
        self.assertEqual(ctx.exception.code, "missing_param")
        self.assertEqual(ctx.exception.param, "frames")
        with self.assertRaises(ops.OpError) as transition:
            ops.validate_params("transition", {"duration": 0.5})
        self.assertEqual(transition.exception.param, "type")

    def test_types_choices_and_bounds(self):
        cases = (("fit_to_frames", {"frames": "53"}, "bad_type"),
                 ("fit_to_frames", {"frames": 53.5}, "bad_type"),
                 ("fit_to_frames", {"frames": 0}, "out_of_range"),
                 ("transition", {"type": "spin", "duration": 0.5}, "bad_choice"),
                 ("transition", {"type": "fade", "duration": 0}, "out_of_range"),
                 ("reframe_crop", {"width": 1080}, "missing_param"))
        for name, params, expected in cases:
            with self.assertRaises(ops.OpError) as ctx:
                ops.validate_params(name, params)
            self.assertEqual(ctx.exception.code, expected, "%s %s" % (name, params))

    def test_cross_parameter_rules(self):
        with self.assertRaises(ops.OpError) as ctx:
            ops.validate_params("trim_exact", {"start_frame": 10})
        self.assertEqual(ctx.exception.code, "invalid_combination")
        self.assertIn("frames", ctx.exception.suggested)
        with self.assertRaises(ops.OpError) as half:
            ops.validate_params("fit_to_frames", {"frames": 10, "width": 1920})
        self.assertEqual(half.exception.code, "invalid_combination")
        with self.assertRaises(ops.OpError) as tracks:
            ops.validate_params("mix_audio", {"tracks": ["music.wav"]})
        self.assertEqual(tracks.exception.code, "bad_type")
        self.assertEqual(tracks.exception.param, "tracks")

    def test_tracks_are_validated_as_track_settings(self):
        good = [{"volume": 0.35}, {"volume": 0.1, "start": 2.0}]
        self.assertEqual(ops.validate_params("mix_audio", {"tracks": good})["tracks"], good)
        with self.assertRaises(ops.OpError):
            ops.validate_params("mix_audio", {"tracks": []})
        # The FILE is the op's "tracks" input, never a param: a path here is refused, because a
        # param is not digested and would not invalidate the cache key (COMMS C-007 finding 3).
        with self.assertRaises(ops.OpError) as path:
            ops.validate_params("mix_audio", {"tracks": [{"path": "music.wav"}]})
        self.assertEqual(path.exception.code, "unknown_param")
        self.assertIn("tracks", path.exception.suggested)

    def test_unknown_op_is_reported_with_the_catalogue(self):
        with self.assertRaises(ops.OpError) as ctx:
            ops.validate_params("trim", {"frames": 10})
        self.assertEqual(ctx.exception.code, "unknown_op")
        self.assertIn("trim_exact", ctx.exception.suggested)


class RegistryTest(unittest.TestCase):
    """Discovery and routing. The matrix decides; an override needs a reason."""

    def test_list_all_and_by_stage(self):
        self.assertEqual(len(registry.list_ops()), len(ops.OPS))
        edit = registry.list_ops("edit")
        self.assertTrue(edit)
        self.assertTrue(all(row["stage"] == "edit" for row in edit))
        self.assertEqual([row["name"] for row in registry.list_ops("deliver")], ["export_h264"])
        with self.assertRaises(registry.RegistryError) as ctx:
            registry.list_ops("rendering")
        self.assertEqual(ctx.exception.code, "unknown_stage")

    def test_describe_carries_evidence_and_readiness(self):
        row = registry.describe("trim_exact")
        self.assertEqual(row["executor"], "kinocut")
        self.assertTrue(row["evidence_status"]["ok"])
        self.assertIn("m2_trim.json", row["evidence_status"]["path"])
        self.assertEqual(row["defaults"]["start_frame"], 0)
        self.assertIn("executor_ready", row)
        with self.assertRaises(registry.RegistryError) as ctx:
            registry.describe("trim")
        self.assertEqual(ctx.exception.code, "unknown_op")

    def test_envelope_is_capped_and_marks_truncation(self):
        full = registry.envelope("edit")
        self.assertEqual(full["count"], len(ops.by_stage("edit")))
        self.assertLessEqual(full["returned"], ops.MAX_ENVELOPE)
        self.assertFalse(full["truncated"])
        small = registry.envelope("edit", limit=3)
        self.assertEqual(small["returned"], 3)
        self.assertTrue(small["truncated"])
        self.assertEqual(len(small["ops"]), 3)
        self.assertIn("name", small["ops"][0])

    def test_route_uses_the_matrix_executor(self):
        kinocut_route = registry.route("trim_exact", {"frames": 50})
        self.assertEqual(kinocut_route.executor, "kinocut")
        self.assertIs(kinocut_route.function, kinocut.trim)
        self.assertEqual(kinocut_route.params["frames"], 50)
        ffmpeg_route = registry.route("fit_to_frames", {"frames": 53})
        self.assertEqual(ffmpeg_route.executor, "ffmpeg")
        self.assertIs(ffmpeg_route.function, ffmpeg.fit_to_frames)
        self.assertIn("tpad", ffmpeg_route.reason)
        self.assertIn("m2_fit.json", ffmpeg_route.to_dict()["evidence"])

    def test_route_refuses_a_silent_executor_swap(self):
        with self.assertRaises(registry.RegistryError) as ctx:
            registry.route("trim_exact", {"frames": 50}, executor="ffmpeg")
        self.assertEqual(ctx.exception.code, "executor_conflict")
        self.assertIn("kinocut", ctx.exception.suggested)

    @unittest.skipUnless(ffmpeg.available(), "ffmpeg not on PATH")
    def test_route_allows_an_override_only_past_the_reason_gate(self):
        """A reason gets you past the matrix rule - it still cannot invent an implementation."""
        with self.assertRaises(registry.RegistryError) as ctx:
            registry.route("trim_exact", {"frames": 50}, executor="ffmpeg",
                           reason="kinocut venv unavailable in this job")
        self.assertEqual(ctx.exception.code, "executor_missing_target")
        self.assertIn("trim", ctx.exception.message)

    def test_route_reports_an_uninstalled_executor_instead_of_switching(self):
        with mock.patch.object(kinocut, "available", lambda: False):
            with self.assertRaises(registry.RegistryError) as ctx:
                registry.route("trim_exact", {"frames": 50})
            self.assertEqual(ctx.exception.code, "executor_not_installed")
            self.assertIn("kinocut", ctx.exception.suggested)
            self.assertFalse(registry.describe("trim_exact")["executor_ready"]["ok"])

    def test_route_validates_params_before_returning(self):
        with self.assertRaises(ops.OpError) as ctx:
            registry.route("transition", {"type": "spin", "duration": 0.5})
        self.assertEqual(ctx.exception.code, "bad_choice")
        with self.assertRaises(registry.RegistryError) as unknown:
            registry.route("trim")
        self.assertEqual(unknown.exception.code, "unknown_op")

    def test_installed_reports_the_five_tools(self):
        rows = registry.installed(refresh=True)
        self.assertEqual(sorted(rows), ["ffmpeg", "ffprobe", "kinocut", "node", "remotion"])
        for name, row in rows.items():
            self.assertEqual(sorted(row), ["install", "ok", "path", "version"], name)
            self.assertIsInstance(row["ok"], bool)
        self.assertTrue(rows["ffmpeg"]["ok"])
        self.assertIn("7.", rows["ffmpeg"]["version"])

    def test_tools_report_counts_per_stage(self):
        report = registry.tools_report()
        self.assertEqual(report["ops"], len(ops.OPS))
        self.assertEqual(sum(report["stages"].values()), len(ops.OPS))


class StageEnvelopeTest(unittest.TestCase):
    """M6: one focused tool set per production stage, capped, complete enough to write a step."""

    def test_the_stages_are_the_five_production_stages(self):
        self.assertEqual(ops.STAGES, ("plan", "edit", "graphics", "review", "deliver"))
        self.assertEqual(tuple(envelopes.STAGE_FOCUS), ops.STAGES)

    def test_every_stage_has_an_envelope_under_the_cap(self):
        for stage in ops.STAGES:
            data = registry.envelope(stage)
            self.assertTrue(data["ok"], stage)
            self.assertTrue(data["why"].strip(), stage)
            self.assertGreater(data["tools"], 0, stage)
            self.assertLessEqual(data["tools"], ops.MAX_ENVELOPE, stage)
            self.assertEqual(data["tools"], len(data["ops"]) + len(data["commands"]), stage)
            self.assertTrue(data["how_to_run"].strip(), stage)

    def test_every_op_is_shown_in_exactly_one_stage(self):
        shown = [row["name"] for stage in ops.STAGES for row in registry.envelope(stage)["ops"]]
        self.assertEqual(sorted(shown), sorted(ops.names()))

    def test_every_op_row_carries_the_schema_to_write_a_step(self):
        for row in registry.envelope("edit")["ops"]:
            self.assertEqual(row["kind"], "op")
            self.assertEqual(row["stage"], "edit")
            for key in ("name", "executor", "description", "inputs", "outputs", "params"):
                self.assertIn(key, row, row["name"])
            self.assertEqual(row["required"],
                             [key for key, param in row["params"].items() if param["required"]])
            for param in row["params"].values():
                self.assertIn("type", param)
                self.assertIn("required", param)
                self.assertNotIn("doc", param)      # prose stays behind `tools describe <op>`

    def test_the_edit_limit_truncates_and_is_recorded(self):
        full = registry.envelope("edit")
        self.assertEqual(full["returned"], len(ops.by_stage("edit")))
        self.assertFalse(full["truncated"])
        small = registry.envelope("edit", limit=3)
        self.assertEqual(small["returned"], 3)
        self.assertTrue(small["truncated"])
        self.assertEqual(len(small["ops"]), 3)

    def test_an_unknown_stage_is_refused_with_the_list(self):
        with self.assertRaises(registry.RegistryError) as ctx:
            registry.envelope("qc")
        self.assertEqual(ctx.exception.code, "unknown_stage")
        self.assertIn("review", ctx.exception.suggested)

    def test_a_stage_that_would_exceed_the_cap_is_refused(self):
        too_many = {"why": "everything at once", "commands": ("tools",)}
        with mock.patch.dict(envelopes.STAGE_FOCUS, {"edit": too_many}):
            with self.assertRaises(registry.RegistryError) as ctx:
                registry.envelope("edit")
        self.assertEqual(ctx.exception.code, "envelope_too_big")
        self.assertIn("cap %d" % ops.MAX_ENVELOPE, ctx.exception.message)

    def test_commands_are_real_cli_verbs_with_real_flags(self):
        """A declared command, argument or flag that the CLI does not have is a lie to the agent."""
        parser = cli.build_parser()
        sub = [action for action in parser._actions
               if isinstance(action, argparse._SubParsersAction)][0]
        def options_of(parser):
            """Every option string a parser accepts, including the leaves of its subcommands."""
            found = {option for action in parser._actions for option in action.option_strings}
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for leaf in action.choices.values():
                        found |= options_of(leaf)
            return found

        for name, row in envelopes.COMMANDS.items():
            self.assertIn(name, sub.choices, name)
            leaf = sub.choices[name]
            options = options_of(leaf)
            for flag in row["flags"]:
                self.assertIn(flag, options, "%s %s" % (name, flag))
            positionals = [action.dest for action in leaf._actions
                           if not action.option_strings
                           and not isinstance(action, argparse._SubParsersAction)]
            self.assertEqual(sorted(positionals), sorted(row["args"]), name)
            self.assertTrue(row["usage"].startswith("python -m cutwright "), name)



if __name__ == "__main__":
    unittest.main()



