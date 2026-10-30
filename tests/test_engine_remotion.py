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
import json
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


def fake_bundle(op=None, scene=None, timeout=None):
    """Stand-in for ensure_bundle: a real directory with the marker file, no webpack run.

    The bundler itself is measured live (LOG 2026-10-30 M5.5B) and its reuse policy is tested in
    BundleCacheTest; the argv tests care only about what a render is told to use.
    """
    path = out("bundle")
    guard.ensure_dir(path)
    guard.write_text(os.path.join(path, "index.html"), "<html></html>\n")
    return path, "testbundle"


class RemotionArgvTest(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(WORK, ignore_errors=True)      # a clean slate: the outputs are real files
        guard.ensure_dir(WORK)
        self.created = []

    def _run(self, func, *args, **kwargs):
        with mock.patch.object(remotion, "available", lambda: True), \
                mock.patch.object(remotion, "ensure_bundle", fake_bundle), \
                mock.patch.object(remotion.subprocess, "Popen", fake_popen(self.created)):
            return func(*args, **kwargs)

    def test_still_argv_renders_from_the_cached_bundle(self):
        scene = scene_file()
        target = out("still.png")
        result = self._run(remotion.render_still, scene, target, COMPOSITION, frame=90)
        argv = self.created[0]["argv"]
        self.assertEqual(argv[2], "still")                     # command FIRST (measured)
        self.assertEqual(argv[3], out("bundle"))               # the BUNDLE, not src/index.ts (M5.5B)
        self.assertEqual(argv[4], COMPOSITION)
        self.assertEqual(argv[5], target)
        self.assertIn("--frame=90", argv)
        self.assertIn("--image-format=png", argv)
        self.assertIn("--log=error", argv)
        self.assertEqual(self.created[0]["cwd"], remotion.remotion_dir())
        self.assertEqual(result.executor, "remotion")
        self.assertEqual(result.payload["command"], "still")
        self.assertEqual(result.payload["bundle"], "testbundle")
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


class AssetStagingTest(unittest.TestCase):
    """kit/2 (M5.5B): a handle becomes a staged file plus a props table - and bad handles stop early."""

    def setUp(self):
        shutil.rmtree(WORK, ignore_errors=True)
        guard.ensure_dir(WORK)
        self.created = []
        self.staged_root = os.path.join(remotion.remotion_dir(), "public", "assets")
        guard.ensure_dir(self.staged_root)

    def tearDown(self):
        for name in os.listdir(self.staged_root):
            if name.startswith("t_"):
                os.remove(os.path.join(self.staged_root, name))

    def _run(self, func, *args, **kwargs):
        with mock.patch.object(remotion, "available", lambda: True), \
                mock.patch.object(remotion, "ensure_bundle", fake_bundle), \
                mock.patch.object(remotion.subprocess, "Popen", fake_popen(self.created)):
            return func(*args, **kwargs)

    def _clip(self, name="t_clip.mp4", data=b"\0\0\0\x18ftypmp42" + b"\0" * 64):
        path = out(name)
        guard.write_bytes(path, data)
        return path

    def _image(self):
        path = out("t_still.png")
        guard.write_bytes(path, b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
        return path

    def test_a_video_handle_is_staged_once_and_reaches_the_props(self):
        scene = scene_file()
        clip = self._clip()
        target = out("still_asset.png")
        self._run(remotion.render_still, scene, target, COMPOSITION, assets={"t_clip": clip})
        with open(target + ".props.json", "r", encoding="utf-8") as handle:
            props = json.load(handle)
        self.assertEqual(props["assets"]["t_clip"]["kind"], "video")
        self.assertEqual(props["assets"]["t_clip"]["file"], "assets/t_clip.mp4")
        self.assertEqual(len(props["assets"]["t_clip"]["sha256"]), 64)
        staged = os.path.join(self.staged_root, "t_clip.mp4")
        self.assertTrue(os.path.exists(staged))
        self.assertEqual(remotion.link_or_copy(clip, staged), "existing")   # never re-staged

    def test_a_still_is_an_image_handle(self):
        table = remotion.stage_assets("render_still", {"t_still": self._image()})
        self.assertEqual(table["t_still"]["kind"], "image")
        self.assertTrue(table["t_still"]["file"].endswith(".png"))

    def test_a_file_that_is_not_footage_is_refused(self):
        scene = scene_file()
        junk = out("t_notes.txt")
        guard.write_text(junk, "not media\n")
        with self.assertRaises(ExecutorError) as ctx:
            self._run(remotion.render_still, scene, out("nope.png"), COMPOSITION,
                      assets={"t_clip": junk})
        self.assertEqual(ctx.exception.code, "bad_asset")
        self.assertEqual(self.created, [])          # nothing was rendered

    def test_a_missing_asset_file_is_refused(self):
        scene = scene_file()
        with self.assertRaises(ExecutorError) as ctx:
            self._run(remotion.render_still, scene, out("nope2.png"), COMPOSITION,
                      assets={"t_clip": out("t_absent.mp4")})
        self.assertEqual(ctx.exception.code, "input_missing")

    def test_landscape_with_assets_still_writes_a_props_file(self):
        scene = scene_file()
        target = out("still_asset_landscape.png")
        self._run(remotion.render_still, scene, target, COMPOSITION,
                  assets={"t_clip": self._clip()})
        self.assertTrue(os.path.isfile(target + ".props.json"))

    def test_no_assets_means_no_props_file(self):
        scene = scene_file()
        target = out("still_plain.png")
        self._run(remotion.render_still, scene, target, COMPOSITION)
        self.assertFalse(os.path.exists(target + ".props.json"))
        self.assertEqual(remotion.stage_assets("render_still", None), {})



class BundleCacheTest(unittest.TestCase):
    """One bundle per content key, reused, and capped at five (owner's 2026-10-30 decision)."""

    def setUp(self):
        guard.ensure_dir(WORK)
        self.cache = out("bundles")
        shutil.rmtree(self.cache, ignore_errors=True)
        guard.ensure_dir(self.cache)

    def _bundle(self, name, age):
        path = os.path.join(self.cache, name)
        guard.ensure_dir(path)
        guard.write_text(os.path.join(path, remotion.BUNDLE_MARK), "<html></html>\n")
        stamp = 1000000000 + age
        os.utime(path, (stamp, stamp))
        return path

    def test_the_key_follows_the_scene_and_the_kit_not_the_footage(self):
        scene = scene_file("bundle_scene.tsx", "// one\n")
        first = remotion.bundle_key(scene)
        self.assertEqual(first, remotion.bundle_key(scene))       # stable without an edit
        guard.write_text(scene, "// two\n")
        self.assertNotEqual(first, remotion.bundle_key(scene))    # an edited scene rebuilds
        kit_file = os.path.join(remotion.remotion_dir(), "kit", "media.tsx")
        before = remotion.bundle_key(scene)
        with open(kit_file, "rb") as handle:
            original = handle.read()
        try:
            guard.write_bytes(kit_file, original + b"\n// a kit edit must rebuild every bundle\n")
            self.assertNotEqual(before, remotion.bundle_key(scene))
        finally:
            guard.write_bytes(kit_file, original)
        self.assertEqual(before, remotion.bundle_key(scene))

    def test_a_finished_bundle_is_reused_without_building(self):
        scene = scene_file("reuse_scene.tsx", "export default () => null;\n")
        key = remotion.bundle_key(scene)
        self._bundle(key, 0)
        with mock.patch.object(remotion, "BUNDLE_CACHE", self.cache), \
                mock.patch.object(remotion.subprocess, "Popen",
                                  side_effect=AssertionError("it rebuilt a cached bundle")):
            path, used = remotion.ensure_bundle("render_still", scene)
        self.assertEqual(used, key)
        self.assertEqual(path, os.path.join(self.cache, key))

    def test_pruning_keeps_five_and_drops_the_oldest(self):
        names = [os.path.basename(self._bundle("b%d" % index, index)) for index in range(7)]
        removed = remotion.prune_bundles(keep=names[-1], limit=5, cache=self.cache)
        left = sorted(os.listdir(self.cache))
        self.assertEqual(len(left), 5)
        self.assertIn(names[-1], left)                     # the one in use is never deleted
        self.assertNotIn(names[0], left)                   # the oldest went first
        self.assertEqual(sorted(removed), sorted(names[:2]))

    def test_pruning_never_touches_a_half_written_bundle(self):
        stale = os.path.join(self.cache, "abc.part")
        guard.ensure_dir(stale)
        for index in range(6):
            self._bundle("c%d" % index, index)
        remotion.prune_bundles(keep="", limit=5, cache=self.cache)
        self.assertTrue(os.path.isdir(stale))


if __name__ == "__main__":
    unittest.main()



class AssetHandleManifestTest(unittest.TestCase):
    """The step's `assets` input is what puts the footage in the cache key - and the rejections."""

    def setUp(self):
        guard.ensure_dir(WORK)

    def _document(self, clip, handle="footage_a", scene=None):
        return {
            "schema": 1, "run_id": "m55b-assets", "fps": 24, "size": [1920, 1080],
            "budget": {"mode": "cap", "cap_usd": 0.0},
            "constraints": {"ai_generated_images": False},
            "assets": [{"id": handle, "path": clip, "origin": "footage"}],
            "gates": [],
            "steps": [{
                "id": "still", "op": "render_still",
                "inputs": {"scene": scene or scene_file("asset_scene.tsx"),
                           "assets": {handle: "@asset.%s" % handle}},
                "params": {"composition": COMPOSITION, "frame": 90},
                "outputs": {"still": out("asset_still.png")},
                "status": "pending", "attempts": 0, "cache_key": None, "cost_usd": 0.0,
            }],
        }

    def _plan(self, document):
        return manifest.derive(document, versions={"remotion": remotion.version()},
                               strict_files=True)

    def test_replacing_the_clip_changes_the_cache_key(self):
        clip = out("asset_clip.mp4")
        guard.write_bytes(clip, b"\0" * 128)
        first = self._plan(self._document(clip)).steps[0]
        self.assertEqual(first.inputs["assets"], {"footage_a": clip})
        guard.write_bytes(clip, b"\0" * 129)          # a different file, same name
        second = self._plan(self._document(clip)).steps[0]
        self.assertNotEqual(first.cache_key, second.cache_key)

    def test_the_handle_table_reaches_the_executor_as_a_keyword(self):
        clip = out("asset_clip2.mp4")
        guard.write_bytes(clip, b"\0" * 64)
        step = self._plan(self._document(clip)).steps[0]
        kwargs = ops.executor_kwargs(step.spec, step.params, fps=24.0, inputs=step.inputs)
        self.assertEqual(kwargs["assets"], {"footage_a": clip})
        self.assertEqual(ops.positional_inputs(step.spec), ["scene"])   # never positional

    def test_an_undeclared_handle_is_refused(self):
        clip = out("asset_clip3.mp4")
        guard.write_bytes(clip, b"\0" * 64)
        document = self._document(clip)
        document["steps"][0]["inputs"]["assets"] = {"shot_b": "@asset.shot_b"}
        with self.assertRaises(manifest.ManifestError) as ctx:
            self._plan(document)
        self.assertEqual(ctx.exception.code, "unknown_handle")

    def test_a_handle_cannot_point_at_another_asset(self):
        clip = out("asset_clip4.mp4")
        guard.write_bytes(clip, b"\0" * 64)
        document = self._document(clip)
        document["assets"].append({"id": "second", "path": clip, "origin": "footage"})
        document["steps"][0]["inputs"]["assets"] = {"footage_a": "@asset.second"}
        with self.assertRaises(manifest.ManifestError) as ctx:
            self._plan(document)
        self.assertEqual(ctx.exception.code, "bad_handle_ref")

    def test_a_path_as_an_asset_id_is_refused(self):
        clip = out("asset_clip5.mp4")
        guard.write_bytes(clip, b"\0" * 64)
        document = self._document(clip, handle="../x")
        document["steps"][0]["inputs"]["assets"] = {"../x": "@asset.../x"}
        with self.assertRaises(manifest.ManifestError) as ctx:
            self._plan(document)
        self.assertEqual(ctx.exception.code, "bad_asset_id")

    def test_a_step_without_assets_still_derives(self):
        scene = scene_file("plain_scene.tsx")
        clip = out("asset_clip6.mp4")
        guard.write_bytes(clip, b"\0" * 64)
        document = self._document(clip, scene=scene)
        del document["steps"][0]["inputs"]["assets"]
        step = self._plan(document).steps[0]
        self.assertEqual(sorted(step.inputs), ["scene"])       # M5.5A manifests still work
