"""Scene-checker rules for kit/2 asset handles (M5.5B).

Run: python -m unittest tests.test_engine_scene_check -v      (repo root)

Why a suite entry and not a one-off run: the whole point of `asset` handles is that a scene can only
NAME footage the step declared. That claim rests on five rejections the checker must keep making, so
each one is pinned here against the real checker (a real TypeScript program, not a regex):

  * `Img`, `OffthreadVideo`, `staticFile` imported by a scene (a scene draws, the kit loads files)
  * a non-literal `asset` (`asset={handle}` - the engine cannot know what it names)
  * an undeclared handle, a path and a URL where a handle belongs
  * `useAsset`, the kit's resolver, which kit/index.ts must NOT export

The suite skips (not passes) when Node or the pinned Remotion install is absent: `not_run` is not a
pass. `tests/test_engine_remotion.py` covers the Python side of the same rules.
"""
import json
import os
import shutil
import subprocess
import unittest

from cutwright import guard

REMOTION = os.path.join(guard.RECAP, "remotion")
CHECKER = os.path.join(REMOTION, "tools", "check_scenes.mjs")
WORK = os.path.join(guard.OUT, "engine_scene_check")
# The fixtures must live INSIDE recapstudio/remotion: TypeScript resolves 'react'/'remotion' from the
# file's own folder upwards, and that is the tree the real scenes are checked in. `s_check_*.tsx`
# matches the existing .gitignore rule for generated scenes, so nothing a test writes is committed.
SCENE_DIR = os.path.join(REMOTION, "src", "generated")
NODE = shutil.which("node")

HEAD = """import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {LayeredMedia, SceneFrame, SceneProps} from '@kit';
%s
export const cost = 'low';

const S: React.FC<SceneProps> = ({theme, layout}) => (
  <SceneFrame theme={theme} layout={layout}>
    %s
  </SceneFrame>
);

export default S;
"""


def scene(body, extra_import=""):
    return HEAD % (extra_import, body)


CASES = (
    # id, scene source, fragments each of which must appear in that scene's errors
    ("ok_declared", scene('<LayeredMedia asset="footage_a" />'), ()),
    ("img", scene('<LayeredMedia asset="footage_a" />',
                  "import {Img} from 'remotion';"),
     ("imports 'Img' from 'remotion'",)),
    ("offthread", scene('<LayeredMedia asset="footage_a" />',
                        "import {OffthreadVideo} from 'remotion';"),
     ("imports 'OffthreadVideo' from 'remotion'",)),
    ("static_file", scene('<LayeredMedia asset="footage_a" />',
                          "import {staticFile} from 'remotion';"),
     ("imports 'staticFile' from 'remotion'",)),
    ("non_literal", scene("const h = 'footage_a';\n    <LayeredMedia asset={h} />"),
     ("non-literal 'asset'",)),
    ("undeclared", scene('<LayeredMedia asset="shot_b" />'),
     ("declares no such handle",)),
    ("path", scene('<LayeredMedia asset="../../clips/s_04.mp4" />'),
     ("is not a handle",)),
    ("url", scene('<LayeredMedia asset="https://example.com/a.mp4" />'),
     ("is not a handle", "contains an internet address")),
    ("use_asset", scene('<LayeredMedia asset="footage_a" />',
                        "import {useAsset} from '@kit';"),
     ("useAsset",)),
)

HANDLES = ["footage_a"]



def run_checker():
    """Run the real checker over every fixture once; return ({id: report entry}, {id: fixture text})."""
    shutil.rmtree(WORK, ignore_errors=True)
    guard.ensure_dir(WORK)
    guard.ensure_dir(SCENE_DIR)
    scenes, texts = [], {}
    for case_id, text, _fragments in CASES:
        path = os.path.join(SCENE_DIR, "s_check_%s.tsx" % case_id)
        guard.write_text(path, text)
        scenes.append({"id": case_id, "file": path})
        texts[case_id] = text
    report_path = os.path.join(WORK, "report.json")
    manifest_path = os.path.join(WORK, "manifest.json")
    guard.write_json(manifest_path, {"out": report_path, "handles": HANDLES,
                                     "scenes": scenes})
    proc = subprocess.run([NODE, CHECKER, manifest_path], cwd=REMOTION,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if not os.path.isfile(report_path):
        raise AssertionError("the checker wrote no report: %s %s"
                             % (proc.stdout.decode("utf-8", "replace")[-400:],
                                proc.stderr.decode("utf-8", "replace")[-400:]))
    with open(report_path, "r", encoding="utf-8") as handle:
        return json.load(handle)["scenes"], texts


def asset_line(text):
    """1-based line of the first `asset=` in a fixture - where a handle rule must fire."""
    for number, line in enumerate(text.splitlines(), start=1):
        if "asset=" in line:
            return number
    return 0


@unittest.skipUnless(NODE and os.path.isfile(CHECKER), "node + recapstudio/remotion needed")
class AssetHandleRulesTest(unittest.TestCase):
    """Each rejection is a line-numbered error from the real TypeScript program."""

    @classmethod
    def setUpClass(cls):
        cls.report, cls.texts = run_checker()

    @classmethod
    def tearDownClass(cls):
        """Remove the fixtures: they are deliberately broken, so they must not outlive the test
        (`tsc -p` would report them, and they are part of the bundle key while they exist)."""
        for case_id, _text, _fragments in CASES:
            path = os.path.join(SCENE_DIR, "s_check_%s.tsx" % case_id)
            if os.path.isfile(path):
                os.remove(path)

    def _errors(self, case_id):
        return (self.report.get(case_id) or {}).get("errors") or []

    def test_a_declared_handle_passes(self):
        self.assertEqual(self._errors("ok_declared"), [])

    def test_every_bad_scene_is_rejected_with_a_line_number(self):
        for case_id, _text, fragments in CASES:
            if not fragments:
                continue
            errors = self._errors(case_id)
            self.assertTrue(errors, "%s was accepted" % case_id)
            self.assertTrue(all(row["line"] > 0 for row in errors),
                            "%s: an error without a line number: %r" % (case_id, errors))
            joined = " | ".join(row["message"] for row in errors)
            for fragment in fragments:
                self.assertIn(fragment, joined, "%s: %r not in %r"
                              % (case_id, fragment, joined))

    def test_the_handle_rules_fire_on_the_jsx_line(self):
        for case_id in ("non_literal", "undeclared", "path", "url"):
            want = asset_line(self.texts[case_id])
            lines = [row["line"] for row in self._errors(case_id)]
            self.assertIn(want, lines, "%s: wanted line %s, got %r" % (case_id, want, lines))


if __name__ == "__main__":
    unittest.main()
