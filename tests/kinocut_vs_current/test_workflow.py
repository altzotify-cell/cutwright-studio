"""M2 area: the Kinocut workflow engine - validate, render, then resume after a lost step."""
import json
import os
import shutil
import unittest

from tests.kinocut_vs_current import harness as hh

FPS = 24


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class WorkflowEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = os.path.join(hh.WORK_OUT, "wf")
        if os.path.isdir(cls.dir):
            shutil.rmtree(cls.dir)
        os.makedirs(cls.dir)
        # Workflow sources must be RELATIVE paths inside the spec's workspace (measured).
        shutil.copyfile(hh.counter(48, FPS, 0), os.path.join(cls.dir, "a.mp4"))
        shutil.copyfile(hh.counter(48, FPS, 100), os.path.join(cls.dir, "b.mp4"))

    def _spec(self, out_name="final.mp4", extra_step=True):
        final = os.path.join(self.dir, out_name)
        spec = {
            "schema_version": 1,
            "name": "m2-workflow",
            "sources": {"a": {"path": "a.mp4"}, "b": {"path": "b.mp4"}},
            "steps": [
                {"id": "trim_a", "op": "trim", "inputs": {"src": "@sources.a"},
                 "params": {"start": 0.0, "duration": 1.0}, "output": "@work/trim_a.mp4"},
                {"id": "resize_a", "op": "resize", "inputs": {"src": "@work/trim_a.mp4"},
                 "params": {"width": 320, "height": 180}, "output": "@work/resize_a.mp4"},
                {"id": "trim_b", "op": "trim", "inputs": {"src": "@sources.b"},
                 "params": {"start": 0.0, "duration": 1.0}, "output": "@work/trim_b.mp4"},
                {"id": "merge", "op": "merge",
                 "inputs": {"srcs": ["@work/resize_a.mp4", "@work/trim_b.mp4"]},
                 "params": {}, "output": "@outputs.final"},
            ],
            "outputs": {"final": {"path": out_name}},
        }
        if not extra_step:
            spec["steps"] = spec["steps"][:3]
        path = os.path.join(self.dir, "spec.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=1)
        return "spec.json", final, spec


    def test_workflow_render_resume(self):
        import hashlib

        def sha(p):
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    h.update(block)
            return h.hexdigest()

        spec, final, _ = self._spec()
        rows = {}
        rows["validate"] = hh.note(hh.kino("workflow-validate", "--spec", spec, cwd=self.dir))

        receipt = os.path.join(self.dir, "receipt.json")
        res = hh.kino("workflow-render", "--spec", spec, "--save-receipt", "receipt.json",
                      "--keep-intermediates", cwd=self.dir)
        rows["render"] = hh.note(res)
        rows["render"]["output_exists"] = os.path.exists(final)
        rows["render"]["output_frames"] = hh.vprops(final)["frames"] if os.path.exists(final) else None
        rows["render"]["dir_after"] = sorted(
            os.path.relpath(os.path.join(d, f), self.dir).replace("\\", "/")
            for d, _, fs in os.walk(self.dir) for f in fs)[:20]
        work = [os.path.join(d, f) for d, _, fs in os.walk(self.dir) for f in fs]
        rows["render"]["receipt_exists"] = os.path.exists(receipt)

        if os.path.exists(receipt):
            with open(receipt, encoding="utf-8") as f:
                rec = json.load(f)
            rows["render"]["receipt_keys"] = sorted(rec.keys())
            blob = json.dumps(rec)
            rows["render"]["receipt_has_output_sha"] = sha(final) in blob if os.path.exists(final) else False

        # Delete one INTERMEDIATE (inside work/), then resume: the deleted step must be rebuilt.
        victim = None
        for p in work:
            if os.path.isfile(p) and p.endswith(".mp4") and p != final and "work" in p:
                victim = p
                break

        rows["resume"] = {"deleted": hh.rel(victim) if victim else None}
        if victim and os.path.exists(receipt):
            os.remove(victim)
            res = hh.kino("workflow-render", "--spec", spec, "--resume", "receipt.json",
                          "--save-receipt", "receipt2.json",
                          "--keep-intermediates", cwd=self.dir)
            rows["resume"].update(hh.note(res))
            rows["resume"]["rebuilt"] = os.path.exists(victim)
            rows["resume"]["output_exists"] = os.path.exists(final)

        # Change the spec and resume against the old receipt: must fail closed.
        spec2, final2, _ = self._spec(out_name="final_changed.mp4", extra_step=False)
        res = hh.kino("workflow-render", "--spec", spec2, "--resume", "receipt.json",
                      "--save-receipt", "receipt3.json", cwd=self.dir)
        rows["changed_spec_refused"] = hh.note(res)


        hh.write_evidence("workflow", {
            "test": "trim -> resize -> trim -> merge as a Kinocut workflow; resume; changed spec",
            "spec": hh.rel(spec), "rows": rows})

        self.assertTrue(rows["render"]["output_exists"],
                        "workflow render produced no output -> %s" % rows["render"])
        self.assertNotEqual(rows["changed_spec_refused"]["exit"], 0,
                            "changed spec must be refused -> %s" % rows["changed_spec_refused"])


