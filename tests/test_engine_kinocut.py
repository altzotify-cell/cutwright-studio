"""Kinocut executor: argv building, error mapping and real media (M3, phase 3A).

Run: python -m unittest tests.test_engine_kinocut -v      (repo root)

Two layers on purpose:

  * pure tests - no subprocess at all. argv shape (`--format json` and `--overwrite` BEFORE the
    subcommand, KINOCUT_FINDINGS 7.2), JSON extraction from noisy output, error mapping from
    Kinocut's own error payload, the write guard. These run everywhere, even without Kinocut.
  * real tests - skipped when `.venvs\\kinocut` is absent. They drive kino.exe through the adapter
    on 2 s / 48-frame fixtures under `out\\engine_adapter` and decode the produced media back
    (frame ids, frame count, audio presence), because "it exited 0" proves nothing.
"""
import json
import math
import os
import struct
import unittest
import wave
from unittest import mock

from cutwright import guard
from cutwright.engine.executors import ExecutorError, ExecutorTimeout
from cutwright.engine.executors import kinocut
from tests import media_fixtures as mf

WORK = os.path.join(guard.OUT, "engine_adapter")     # inside the fork: the guard allows it


def out(name):
    return os.path.join(WORK, name)


def tone_wav(path, freq, seconds, rate=mf.RATE, amp=12000):
    """Mono 16-bit WAV (mix-audio needs a real file, not a fixture generator call)."""
    frames = bytearray()
    for i in range(int(seconds * rate)):
        frames += struct.pack("<h", int(amp * math.sin(2 * math.pi * freq * i / rate)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


def record(fn, *args, **kwargs):
    """Call a wrapper with `invoke` replaced by a recorder; return what it would have run."""
    calls = []

    def fake(op, opargs=(), **kw):
        calls.append({"op": op, "args": [str(a) for a in opargs], "kwargs": kw})
        return "recorded"

    with mock.patch.object(kinocut, "invoke", fake):
        fn(*args, **kwargs)
    return calls


class ArgvTest(unittest.TestCase):
    """What the adapter would run - checked without starting a process."""

    def test_global_flags_precede_subcommand(self):
        argv = kinocut.build_argv("trim", ["in.mp4", "-o", "o.mp4"])
        self.assertEqual(argv[1:4], ["--format", "json", "trim"])
        self.assertLess(argv.index("--format"), argv.index("trim"))

    def test_overwrite_is_a_global_flag(self):
        argv = kinocut.build_argv("trim", [], overwrite=True)
        self.assertEqual(argv[1:], ["--format", "json", "--overwrite", "trim"])

    def test_trim_passes_only_set_options(self):
        rec = record(kinocut.trim, "in.mp4", out("t.mp4"), start=1, duration=2.5, accurate=True)
        self.assertEqual(rec[0]["op"], "trim")
        self.assertEqual(rec[0]["args"],
                         ["in.mp4", "-s", "1", "-d", "2.5", "--accurate", "-o", out("t.mp4")])
        rec = record(kinocut.trim, "in.mp4", out("t.mp4"), end=3.25)
        self.assertEqual(rec[0]["args"], ["in.mp4", "-e", "3.25", "-o", out("t.mp4")])

    def test_merge_passes_transition_and_seconds(self):
        rec = record(kinocut.merge, ["a.mp4", "b.mp4"], out("m.mp4"),
                     transition="fade", transition_duration=0.5)
        self.assertEqual(rec[0]["args"],
                         ["a.mp4", "b.mp4", "-t", "fade", "-td", "0.5", "-o", out("m.mp4")])

    def test_mix_audio_sends_json_not_a_path(self):
        tracks = [{"path": "bed.wav", "volume": 0.35}]
        rec = record(kinocut.mix_audio, "in.mp4", out("x.mp4"), tracks)
        args = rec[0]["args"]
        self.assertEqual(args[1], "--sounds")
        self.assertEqual(json.loads(args[2]), tracks)
        self.assertIn("--keep-source", args)
        rec = record(kinocut.mix_audio, "in.mp4", out("x.mp4"), tracks, keep_source=False)
        self.assertIn("--no-keep-source", rec[0]["args"])

    def test_resize_uses_kino_spelling(self):
        rec = record(kinocut.resize, "in.mp4", out("r.mp4"), width=1080, height=1920,
                     aspect="9:16")
        self.assertEqual(rec[0]["args"],
                         ["in.mp4", "-w", "1080", "--height", "1920", "-a", "9:16",
                          "-o", out("r.mp4")])

    def test_duck_audio_key_then_bed(self):
        rec = record(kinocut.duck_audio, "voice.mp4", "music.wav", out("d.mp4"),
                     music_volume=0.35, ratio=8)
        self.assertEqual(rec[0]["args"][:2], ["voice.mp4", "music.wav"])
        self.assertIn("--music-volume", rec[0]["args"])

    def test_write_guard_refuses_paths_outside_the_fork(self):
        outside = os.path.join(os.path.expanduser("~"), "cutwright_should_not_write.mp4")
        with self.assertRaises(guard.GuardError):
            kinocut.trim("in.mp4", outside)
        with self.assertRaises(guard.GuardError):
            kinocut.release_checkpoint("in.mp4", outside)

    def test_workflow_render_runs_in_the_spec_directory(self):
        spec = out("job.json")
        rec = record(kinocut.workflow_render, spec, output=out("w.mp4"))
        self.assertEqual(rec[0]["kwargs"]["cwd"], os.path.dirname(os.path.abspath(spec)))
        self.assertEqual(rec[0]["args"][0], "--spec")


class InterpretTest(unittest.TestCase):
    """Exit code + captured bytes -> result or typed error. No process, no media."""

    def test_success_payload_becomes_a_result(self):
        payload = {"success": True, "output_path": "out\\t.mp4", "warnings": ["variable fps"],
                   "duration": 1.0}
        res = kinocut.interpret("trim", ["kino", "trim"], 0,
                                json.dumps(payload).encode("utf-8"), b"", seconds=2.5)
        self.assertTrue(res.ok)
        self.assertEqual(res.executor, "kinocut")
        self.assertEqual(res.output_path, "out\\t.mp4")
        self.assertEqual(res.warnings, ["variable fps"])
        self.assertEqual(res.seconds, 2.5)
        self.assertEqual(res.payload["duration"], 1.0)

    def test_json_is_found_between_log_lines(self):
        noisy = b"INFO starting\ntrailing log\n" \
                b'{"success": true, "output_path": "o.mp4", "warnings": []}\nDone %\n'
        res = kinocut.interpret("merge", [], 0, noisy, b"")
        self.assertEqual(res.output_path, "o.mp4")

    def test_error_payload_names_code_and_fix(self):
        payload = {"success": False, "error": {
            "type": "validation_error", "code": "output_exists",
            "message": "Output path already exists; pass overwrite=true",
            "suggested_action": {"auto_fix": False, "description": "delete it or allow overwrite"}}}
        with self.assertRaises(ExecutorError) as ctx:
            kinocut.interpret("trim", ["kino", "trim"], 1, json.dumps(payload).encode("utf-8"), b"")
        err = ctx.exception
        self.assertEqual(err.code, "output_exists")
        self.assertEqual(err.error_type, "validation_error")
        self.assertEqual(err.returncode, 1)
        self.assertEqual(err.suggested, "delete it or allow overwrite")
        self.assertFalse(err.transient)
        self.assertIn("output_exists", str(err))
        self.assertEqual(err.to_dict()["code"], "output_exists")

    def test_failure_needs_no_error_object(self):
        with self.assertRaises(ExecutorError) as ctx:
            kinocut.interpret("trim", [], 1, b"", b"boom: no such file")
        self.assertEqual(ctx.exception.code, "exit_1")
        self.assertIn("boom", ctx.exception.message)
        self.assertEqual(ctx.exception.stdout, "")

    def test_argparse_exit_2_hints_at_flag_order(self):
        with self.assertRaises(ExecutorError) as ctx:
            kinocut.interpret("video-capabilities", [], 2, b"",
                              b"kino: error: unrecognized arguments: --format json")
        err = ctx.exception
        self.assertEqual(err.code, "exit_2")
        self.assertIn("global flags must precede the subcommand", err.suggested)

    def test_success_false_with_exit_zero_still_fails(self):
        payload = {"success": False, "error": {"code": "invalid_input", "message": "no file"}}
        with self.assertRaises(ExecutorError) as ctx:
            kinocut.interpret("info", [], 0, json.dumps(payload).encode("utf-8"), b"")
        self.assertEqual(ctx.exception.code, "invalid_input")

    def test_utf8_panels_decode_instead_of_crashing(self):
        panel = "\u250c\u2500 Error \u2500\u2510\n\u2502 File not found \u2502\n\u2514\u2500 End \u2500\u2518"
        with self.assertRaises(ExecutorError) as ctx:
            kinocut.interpret("info", [], 1, b"", panel.encode("utf-8"))
        self.assertIn("\u2502", ctx.exception.stderr)   # cp1252 would have raised before this

    def test_missing_install_is_not_an_error_to_retry(self):
        with mock.patch.dict(os.environ, {kinocut.KINO_ENV: out("no_such_kino.exe")}):
            self.assertFalse(kinocut.available())
            self.assertEqual(kinocut.version(), "")
            with self.assertRaises(ExecutorError) as ctx:
                kinocut.invoke("info", ["x.mp4"])
        self.assertEqual(ctx.exception.code, "not_installed")
        self.assertFalse(ctx.exception.transient)


@unittest.skipUnless(kinocut.available(), "Kinocut venv missing (.venvs\\kinocut)")
class KinocutRealTest(unittest.TestCase):
    """The real path: kino.exe through the adapter, then decode what it wrote.

    Fixtures are 2 s / 48 frames at 24 fps, so the whole class costs well under a minute.
    """
    FRAMES = 48
    FPS = 24

    @classmethod
    def setUpClass(cls):
        guard.ensure_dir(WORK)
        cls.src = mf.make_counter_clip(out("adapter_src.mp4"), frames=cls.FRAMES, fps=cls.FPS)

    def test_version(self):
        self.assertTrue(kinocut.version().startswith("Kinocut "))

    def test_info_returns_stream_facts(self):
        res = kinocut.info(self.src)
        self.assertTrue(res.ok)
        data = res.payload.get("data") or {}
        self.assertEqual((data.get("width"), data.get("height")), (160, 90))
        self.assertAlmostEqual(float(data.get("duration")), 2.0, delta=0.1)
        self.assertGreater(res.seconds, 0.0)

    def test_trim_is_frame_exact_after_the_adapter(self):
        target = out("adapter_trim.mp4")
        res = kinocut.trim(self.src, target, start=1.0, duration=1.0, overwrite=True)
        self.assertTrue(res.ok)
        self.assertTrue(os.path.exists(target))
        self.assertEqual(os.path.basename(res.output_path), "adapter_trim.mp4")
        self.assertEqual(mf.frame_ids(target), list(range(24, 48)))
        frames, _seconds, audio = mf.probe_counts(target)
        self.assertEqual(frames, 24)
        self.assertIsNotNone(audio)          # audio survives the cut

    def test_merge_crossfade_keeps_the_frame_maths(self):
        first = mf.make_counter_clip(out("adapter_a.mp4"), frames=24, fps=self.FPS)
        second = mf.make_counter_clip(out("adapter_b.mp4"), frames=24, fps=self.FPS, id_offset=100)
        target = out("adapter_fade.mp4")
        res = kinocut.merge([first, second], target, transition="fade",
                            transition_duration=0.5, overwrite=True)
        self.assertTrue(res.ok)
        self.assertEqual(mf.probe_counts(target)[0], 24 + 24 - 12)   # 0.5 s = 12 frames at 24 fps

    def test_output_exists_needs_an_explicit_overwrite(self):
        target = out("adapter_clash.mp4")
        kinocut.trim(self.src, target, duration=0.5, overwrite=True)
        with self.assertRaises(ExecutorError) as ctx:
            kinocut.trim(self.src, target, duration=0.5)
        self.assertEqual(ctx.exception.code, "output_exists")
        self.assertFalse(ctx.exception.transient)
        self.assertTrue(kinocut.trim(self.src, target, duration=0.5, overwrite=True).ok)

    def test_missing_input_is_a_typed_input_error(self):
        with self.assertRaises(ExecutorError) as ctx:
            kinocut.info(out("no_such_input.mp4"))
        self.assertEqual(ctx.exception.code, "invalid_input")
        self.assertTrue(ctx.exception.message)
        self.assertNotEqual(ctx.exception.returncode, 0)

    def test_mix_audio_accepts_json_tracks(self):
        bed = tone_wav(out("adapter_bed.wav"), 100.0, 2.2)
        target = out("adapter_mix.mp4")
        res = kinocut.mix_audio(self.src, target, [{"path": bed, "volume": 0.35}], overwrite=True)
        self.assertTrue(res.ok)
        frames, _seconds, audio = mf.probe_counts(target)
        self.assertEqual(frames, self.FRAMES)
        self.assertIsNotNone(audio)

    def test_timeout_is_transient_and_kills_the_call(self):
        with self.assertRaises(ExecutorTimeout) as ctx:
            kinocut.trim(self.src, out("adapter_timeout.mp4"), duration=1.0, overwrite=True,
                         timeout=0.05)
        self.assertTrue(ctx.exception.transient)
        self.assertEqual(ctx.exception.code, "timeout")


if __name__ == "__main__":
    unittest.main()


