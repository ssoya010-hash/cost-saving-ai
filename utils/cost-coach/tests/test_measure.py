"""Measurement tests on synthetic Claude Code transcripts (no network, no real data)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from coach import measure, pricing  # noqa: E402

CLI = os.path.join(ROOT, "coach", "cli.py")


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def asst(mid, ts, inp=0, w1h=0, read=0, out=0, model="claude-sonnet-5-5"):
    return {"type": "assistant", "timestamp": iso(ts), "message": {
        "id": mid, "model": model, "usage": {
            "input_tokens": inp, "cache_creation_input_tokens": w1h, "cache_read_input_tokens": read,
            "output_tokens": out, "cache_creation": {"ephemeral_1h_input_tokens": w1h,
                                                     "ephemeral_5m_input_tokens": 0}}}}


def user(ts, text="do it"):
    return {"type": "user", "timestamp": iso(ts), "message": {"role": "user", "content": text}}


def write(root, project, sid, rows):
    d = os.path.join(root, project)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, sid + ".jsonl")
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


class PricingTests(unittest.TestCase):
    def test_sonnet_55_parts(self):
        c = pricing.cost({"input_tokens": 1_000_000, "cache_creation_input_tokens": 1_000_000,
                          "cache_read_input_tokens": 1_000_000, "output_tokens": 1_000_000,
                          "cache_creation": {"ephemeral_1h_input_tokens": 1_000_000,
                                             "ephemeral_5m_input_tokens": 0}}, "claude-sonnet-5-5")
        self.assertAlmostEqual(c["parts"]["uncached_in"], 2.0)
        self.assertAlmostEqual(c["parts"]["cache_write"], 4.0)   # 1h TTL = 2x
        self.assertAlmostEqual(c["parts"]["cache_read"], 0.10)
        self.assertAlmostEqual(c["parts"]["output"], 10.0)

    def test_5m_default_and_override(self):
        c = pricing.cost({"cache_creation_input_tokens": 1_000_000}, "claude-opus-4-6")
        self.assertAlmostEqual(c["parts"]["cache_write"], 6.25)  # 5 x 1.25
        c = pricing.cost({"input_tokens": 1_000_000}, "anthropic.claude-opus-4-6-v1",
                         {"price_multiplier": 0.5})
        self.assertAlmostEqual(c["usd"], 2.5)


class MeasureTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.home = tempfile.mkdtemp()
        measure.config.HOME = self.home

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)

    def test_dedupe_and_bust_detection(self):
        t = time.time() - 3600
        rows = [user(t), asst("m1", t + 1, w1h=50_000, out=100),
                asst("m1", t + 1, w1h=50_000, out=100),            # streamed duplicate
                asst("m2", t + 10, read=50_000, w1h=2_000, out=100),
                asst("m3", t + 20, read=0, w1h=53_000, out=100),    # lost prefix -> bust
                asst("m4", t + 30, read=53_000, w1h=60_000, out=100)]  # big new file read: not a bust
        p = write(self.root, "proj", "s1", rows)
        s = measure.session_from_file(p, {})
        self.assertEqual(s["calls"], 4)
        self.assertEqual(s["cache_busts"], 1)
        self.assertEqual(s["bust_causes"], {"prefix_changed": 1})
        self.assertEqual(s["user_prompts"], 1)

    def test_pause_over_ttl_cause(self):
        t = time.time() - 9000
        rows = [asst("a", t, w1h=40_000), asst("b", t + 4000, w1h=40_500)]
        s = measure.session_from_file(write(self.root, "p", "s2", rows), {})
        self.assertEqual(s["bust_causes"], {"pause_over_ttl": 1})

    def test_compare_before_after_mark(self):
        now = time.time()
        mark = now - 5 * 86400
        for i in range(3):   # before: expensive sessions
            write(self.root, "p", f"b{i}", [asst(f"b{i}", mark - 86400 - i * 100, w1h=100_000, out=5000)])
        for i in range(3):   # after: cheaper
            write(self.root, "p", f"a{i}", [asst(f"a{i}", mark + 86400 + i * 100, w1h=50_000, out=5000)])
        measure.devin_add(10, "d1", ts=mark - 3600)
        measure.devin_add(8, "d2", ts=mark + 3600)
        r = measure.compare(mark, 14, self.root, {}, 0.40)
        self.assertEqual(r["claude"]["before"]["sessions"], 3)
        self.assertLess(r["claude"]["change_pct_median_usd_per_session"], 0)
        self.assertEqual(r["devin"]["change_pct_median_acu_per_session"], -20.0)

    def test_cli_status_runs(self):
        t = time.time() - 600
        write(self.root, "p", "s", [user(t), asst("x", t + 1, w1h=10_000, out=500)])
        env = dict(os.environ, COACH_HOME=self.home, COACH_NO_NOTIFY="1")
        r = subprocess.run([sys.executable, "-I", CLI, "--root", self.root, "status", "--days", "1"],
                           capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Claude Code  1 sessions", r.stdout)


if __name__ == "__main__":
    unittest.main()
