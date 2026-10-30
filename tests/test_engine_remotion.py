"""Remotion executor + its two ops (M5.5A).

Run: python -m unittest tests.test_engine_remotion -v      (repo root)

Two layers, and NO render in either (a real still costs ~40 s here; it is measured in LOG, not in
the suite):

  * `RemotionArgvTest` - pure: the pinned-CLI argument order, the props file, the pre-flight
    refusals (missing scene, existing output, a path outside the fork, Remotion absent) and the
    stderr -> error-code mapping. `subprocess.Popen` is faked, so nothing starts.
  * `RemotionManifestTest` - the claim that makes the op cacheable: the scene file is a declared
    INPUT, so editing it changes the step's cache key in a real `manifest.derive()`.
"""
import os
import shutil
import unittest
from unittest import mock

from cutwright import guard
from cutwright.engine import manifest, ops, registry
from cutwright.engine.executors import ExecutorError, ExecutorUnavailable
from cutwright.engine.executors import remotion

WORK = os.path.join(guard.OUT, "engine_remotion")     # inside the fork: the guard allows it
COMPOSITION = "example-stat-ring"


def out(name):
    return os.path.join(WORK, name)


def scene_file(name="scene.tsx", text="export default () => null;\n"):
    """A stand-in scene file: the op only needs a real path to digest."""
    path = out(name)
    guard.write_text(path, text)
    return path


def fake_popen(created, payload=b"\x89PNG\r\n\x1a\n"):
    """A Popen that records argv and writes a small file where the render would have gone."""
    class Proc:
        returncode = 0

        def __init__(self, argv, cwd=None, stdout=None, stderr=None, stdin=None):
            created.append({"argv": list(argv), "cwd": cwd})
            guard.write_bytes(argv[5], payload)

        def communicate(self, timeout=None):
            return b"", b""

    return Proc


class RemotionArgvTest(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(WORK, ignore_errors=True)      # a clean slate: the outputs are real files
        guard.ensure_dir(WORK)
        self.created = []

    def _run(self, func, *args, **kwargs):
        with mock.patch.object(remotion, "available", lambda: True), \
                mock.patch.object(remotion.subprocess, "Popen", fake_popen(self.created)):
            return func(*args, **kwargs)

    def test_still_argv_puts_the_command_before_the_entry_point(self):
        scene = scene_file()
        target = out("still.png")
        result = self._run(remotion.render_still, scene, target, COMPOSITION, frame=90)
        argv = self.created[0]["argv"]
        self.assertEqual(argv[2], "still")                     # command FIRST (measured)
        self.assertEqual(argv[3], remotion.entry_point())
        self.assertEqual(argv[4], COMPOSITION)
        self.assertEqual(argv[5], target)
        self.assertIn("--frame=90", argv)
        self.assertIn("--image-format=png", argv)
        self.assertIn("--log=error", argv)
        self.assertEqual(self.created[0]["cwd"], remotion.remotion_dir())
        self.assertEqual(result.executor, "remotion")
        self.assertEqual(result.payload["command"], "still")
        self.assertTrue(os.path.isfile(target))

    def test_landscape_writes_no_props_file(self):
        scene = scene_file()
        target = out("still_landscape.png")
        self._run(remotion.render_still, scene, target, COMPOSITION, frame=0)
        self.assertFalse(os.path.exists(target + ".props.json"))
        self.assertNotIn("--props", " ".join(self.created[0]["argv"]))

    def test_portrait_writes_the_props_file_it_passes(self):
        scene = scene_file()
        target = out("still_portrait.png")
        result = self._run(remotion.render_still, scene, target, COMPOSITION, frame=12,
                           portrait=True)
        props = target + ".props.json"
        self.assertTrue(os.path.isfile(props))
        self.assertIn("--props=" + props, self.created[0]["argv"])
        self.assertTrue(result.payload["props_file"].endswith(".props.json"))

    def test_range_flags_are_inclusive_and_ask_for_h264(self):
        scene = scene_file()
        target = out("range.mp4")
        self._run(remotion.render_range, scene, target, COMPOSITION, start=0, frames=24)
        argv = self.created[0]["argv"]
        self.assertEqual(argv[2], "render")
        self.assertIn("--frames=0-23", argv)
        self.assertIn("--codec=h264", argv)
        self.assertIn("--crf=18", argv)

    def test_an_existing_output_is_refused_without_overwrite(self):
        scene = scene_file()
        target = out("existing.png")
        guard.write_bytes(target, b"already here")
        with self.assertRaises(ExecutorError) as ctx:
            self._run(remotion.render_still, scene, target, COMPOSITION)
        self.assertEqual(ctx.exception.code, "output_exists")
        self.assertEqual(self.created, [])

    def test_a_missing_scene_is_refused_before_anything_starts(self):
        with self.assertRaises(ExecutorError) as ctx:
            self._run(remotion.render_still, out("no_such_scene.tsx"), out("x.png"), COMPOSITION)
        self.assertEqual(ctx.exception.code, "input_missing")
        self.assertEqual(self.created, [])

    def test_a_write_outside_the_fork_is_refused_by_the_guard(self):
        scene = scene_file()
        with self.assertRaises(guard.GuardError):
            self._run(remotion.render_still, scene, r"C:\Windows\Temp\still.png", COMPOSITION)
        self.assertEqual(self.created, [])

    def test_remotion_absent_is_a_typed_error_that_writes_nothing(self):
        scene = scene_file()
        target = out("never.png")
        with mock.patch.object(remotion, "available", lambda: False):
            with self.assertRaises(ExecutorUnavailable) as ctx:
                remotion.render_still(scene, target, COMPOSITION)
        self.assertEqual(ctx.exception.code, "not_installed")
        self.assertFalse(os.path.exists(target))
        self.assertFalse(os.path.exists(target + ".props.json"))

    def test_error_codes_come_from_remotions_own_words(self):
        missing = remotion.error_from("render_still", [], 1, "",
                                      "Could not find composition example-nope")
        self.assertEqual(missing.code, "unknown_composition")
        scene = remotion.error_from("render_still", [], 1,
                                    "\x1b[31mError: x.toUpperCase is not a function\x1b[39m", "")
        self.assertEqual(scene.code, "render_failed")
        self.assertNotIn("\x1b", scene.message)
        self.assertIn("toUpperCase", scene.message)


class RemotionManifestTest(unittest.TestCase):
    """The op is cacheable only because the SCENE is an input - prove it in the real plan."""

    def setUp(self):
        guard.ensure_dir(WORK)

    def _document(self, scene_path, run_id, frame=90):
        return {
            "schema": 1, "run_id": run_id, "fps": 24, "size": [1920, 1080],
            "budget": {"mode": "cap", "cap_usd": 0.0},
            "constraints": {"ai_generated_images": False},
            "assets": [], "gates": [],
            "steps": [{
                "id": "still", "op": "render_still",
                "inputs": {"scene": scene_path},
                "params": {"composition": COMPOSITION, "frame": frame},
                "outputs": {"still": out(run_id + ".png")},
                "validation": [{"check": "size", "expect": [1920, 1080]}],
                "status": "pending", "attempts": 0, "cache_key": None, "cost_usd": 0.0,
            }],
        }

    def _plan(self, scene_path, run_id, frame=90):
        return manifest.derive(self._document(scene_path, run_id, frame),
                               versions={"remotion": remotion.version()}, strict_files=True)

    def test_editing_the_scene_changes_the_cache_key(self):
        scene = scene_file("cache_scene.tsx", "// version one\n")
        first = self._plan(scene, "m55-cache-a").steps[0]
        same = self._plan(scene, "m55-cache-b").steps[0]
        self.assertEqual(first.cache_key, same.cache_key)
        guard.write_text(scene, "// version two\n")
        changed = self._plan(scene, "m55-cache-c").steps[0]
        self.assertNotEqual(first.cache_key, changed.cache_key)

    def test_changing_a_param_changes_the_cache_key(self):
        scene = scene_file("param_scene.tsx", "// stable\n")
        first = self._plan(scene, "m55-param-a", 90).steps[0]
        other = self._plan(scene, "m55-param-b", 91).steps[0]
        self.assertNotEqual(first.cache_key, other.cache_key)

    def test_the_two_ops_route_to_remotion_and_fit_the_envelope(self):
        self.assertEqual(registry.route("render_still", {"composition": COMPOSITION}).executor,
                         "remotion")
        self.assertEqual(registry.route("render_range", {"composition": COMPOSITION}).executor,
                         "remotion")
        graphics = registry.envelope("graphics")
        self.assertIn("render_still", [row["name"] for row in graphics["ops"]])
        self.assertLessEqual(graphics["returned"], ops.MAX_ENVELOPE)
        with self.assertRaises(ops.OpError) as ctx:
            registry.route("render_still", {"frame": 3})
        self.assertEqual(ctx.exception.code, "missing_param")


if __name__ == "__main__":
    unittest.main()
