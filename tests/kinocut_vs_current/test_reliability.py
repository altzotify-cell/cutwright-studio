"""M2 area: reliability. 10 repeats per op, a protected output directory, a killed run."""
import os
import subprocess
import time
import unittest

from tests.kinocut_vs_current import harness as hh

FPS = 24
RUNS = 10


@unittest.skipUnless(hh.have_kinocut(), "Kinocut venv missing (.venvs/kinocut)")
class ReliabilityEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = hh.counter(120, FPS, 0)
        cls.pair = [hh.counter(48, FPS, 0), hh.counter(48, FPS, 100)]

    def _repeat(self, label, build):
        results = []
        for k in range(RUNS):
            out = hh.out_path("rel_%s_%d.mp4" % (label, k))
            t0 = time.time()
            res = build(out)
            ok = res["exit"] == 0 and os.path.exists(out)
            results.append({"run": k, "exit": res["exit"], "seconds": round(time.time() - t0, 2),
                            "frames": hh.vprops(out)["frames"] if ok else None, "ok": ok,
                            "stderr_tail": (res.get("stderr") or "").strip()[-160:] or None})
        return {"label": label, "runs": RUNS,
                "failures": [r for r in results if not r["ok"]],
                "seconds": [r["seconds"] for r in results],
                "frames_seen": sorted({r["frames"] for r in results if r["frames"] is not None})}

    def test_repeats(self):
        rows = {}
        rows["trim"] = self._repeat("trim", lambda out: hh.kino(
            "trim", self.src, "-s", "1.5", "-d", "2.0", "-o", out))
        rows["fit_resize"] = self._repeat("resize", lambda out: hh.kino(
            "resize", self.src, "-w", "640", "--height", "360", "-o", out))
        rows["merge"] = self._repeat("merge", lambda out: hh.kino("merge", *self.pair, "-o", out))
        hh.write_evidence("reliability_repeats", {
            "test": "%d repeats of trim / resize / merge" % RUNS, "rows": rows})
        for name, row in rows.items():
            self.assertEqual(row["failures"], [], "%s had failures -> %s" % (name, row["failures"]))
            self.assertEqual(len(row["frames_seen"]), 1,
                             "%s output frames not stable -> %s" % (name, row["frames_seen"]))

    def test_read_only_output_dir(self):
        d = os.path.join(hh.WORK_OUT, "readonly")
        os.makedirs(d, exist_ok=True)
        user = os.environ.get("USERNAME", os.environ.get("USER", ""))
        res = hh.run(["icacls", d, "/deny", "%s:(W)" % user])
        rows = {"dir": hh.rel(d), "user": user, "icacls_exit": res["exit"],
                "icacls_error": (res["stderr"] or res["stdout"]).strip()[-200:] or None}
        try:
            out = os.path.join(d, "blocked.mp4")
            k = hh.kino("trim", self.src, "-s", "0", "-d", "1", "-o", out)
            rows["kinocut"] = dict(hh.note(k), wrote_file=os.path.exists(out))
        finally:
            hh.run(["icacls", d, "/remove:d", user])
        hh.write_evidence("reliability_readonly", {
            "test": "trim into a directory the user cannot write to", "rows": rows})
        k = rows["kinocut"]
        if rows["icacls_exit"] == 0 and not k.get("wrote_file"):
            self.assertNotEqual(k["exit"], 0, "write into a read-only dir must fail -> %s" % k)
            self.assertIn("error", (k.get("json") or {}), "error must be structured -> %s" % k)
            self.assertTrue((k.get("stderr_tail") or k.get("json")),
                            "the refusal must be explained -> %s" % k)
        print("[reliability] read-only: icacls=%s kinocut exit=%s json=%s"
              % (rows["icacls_exit"], k.get("exit"), k.get("json")))

    def test_kill_mid_run(self):
        d = os.path.join(hh.WORK_OUT, "kill")
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
        long_src = hh.out_path("rel_long.mp4")
        hh.ff("-i", hh.counter(240, FPS, 0), "-vf", "scale=640:360:flags=neighbor,setsar=1",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
              "-c:a", "copy", "-t", "10", long_src)
        out = os.path.join(d, "killed.mp4")
        argv = [hh.KINO, "--format", "json", "trim", long_src, "-s", "0", "-d", "10", "-o", out]
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(1.2)
        killed_early = p.poll() is None
        p.terminate()
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=30)
        leftovers = sorted(os.listdir(d))
        rows = {"killed_while_running": killed_early, "exit": p.returncode,
                "files_left": leftovers, "output_usable": False}
        if out in leftovers:
            try:
                rows["output_usable"] = hh.vprops(out)["frames"] > 0
            except Exception as e:  # noqa: BLE001
                rows["output_usable"] = "undecodable: %s" % str(e)[:120]
        hh.write_evidence("reliability_kill", {
            "test": "terminate a trim 1.2 s in; look for orphaned temp files", "rows": rows})
        self.assertLessEqual(len([f for f in leftovers if not f.endswith(".mp4")]), 6,
                             "orphaned temp files -> %s" % leftovers)

