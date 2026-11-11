"""Cache-expiry timer and weekly retrospective."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from coach import config, expiry, state, weekly  # noqa: E402

HOOK = os.path.join(ROOT, "coach", "hook.py")


class Clock:
    def __init__(self, t):
        self.t = t
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class ExpiryTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.old = config.HOME
        config.HOME = self.home
        os.environ["COACH_NO_NOTIFY"] = "1"
        self.cfg = dict(config.DEFAULTS, macos_notify=False, max_notifications_per_hour=99)

    def tearDown(self):
        config.HOME = self.old
        shutil.rmtree(self.home, ignore_errors=True)

    def _session(self, sid, ctx=120_000, ttl=300, stop=1000.0, last_activity=1000.0):
        state.save_cost(sid, {"last_context": ctx, "ttl": ttl, "model": "claude-opus-4-6"})
        state.save(sid, {"prompts": 1, "last_activity": last_activity})
        expiry.write_timer(sid, {"stop": stop})

    def test_notifies_once_after_ttl(self):
        self._session("a")
        clk = Clock(1000.0)
        msg = expiry.run("a", "claude", self.cfg, sleep=clk.sleep, now=clk.now)
        self.assertIsNotNone(msg)
        self.assertIn("120K", msg)
        self.assertIn("$0.75", msg)            # 120K x $5/MTok x 1.25 (5-min write)
        self.assertGreaterEqual(clk.t, 1000 + 300)
        self.assertIsNone(expiry.run("a", "claude", self.cfg, sleep=clk.sleep, now=clk.now))  # once only

    def test_silent_when_user_resumed(self):
        self._session("b", last_activity=1200.0)   # user typed before expiry
        clk = Clock(1000.0)
        self.assertIsNone(expiry.run("b", "claude", self.cfg, sleep=clk.sleep, now=clk.now))

    def test_silent_for_small_context(self):
        self._session("c", ctx=8_000)
        clk = Clock(1000.0)
        self.assertIsNone(expiry.run("c", "claude", self.cfg, sleep=clk.sleep, now=clk.now))

    def test_one_hour_ttl_waits_longer(self):
        self._session("d", ttl=3600)
        clk = Clock(1000.0)
        msg = expiry.run("d", "claude", self.cfg, sleep=clk.sleep, now=clk.now)
        self.assertGreaterEqual(clk.t, 1000 + 3600)
        self.assertIn("$1.20", msg)            # 1-h write = 2x

    def test_newer_turn_extends_timer(self):
        self._session("e")
        clk = Clock(1000.0)

        def sleep(s):
            clk.sleep(s)
            if not getattr(clk, "bumped", False):   # another turn ended while we slept
                clk.bumped = True
                expiry.write_timer("e", {"stop": 1200.0})
                state.save("e", {"prompts": 2, "last_activity": 1200.0})
        msg = expiry.run("e", "claude", self.cfg, sleep=sleep, now=clk.now)
        self.assertIsNotNone(msg)
        self.assertGreaterEqual(clk.t, 1200 + 300)

    def test_devin_estimate(self):
        state.save("f", {"prompts": 1, "last_activity": 1000.0, "approx_ctx_chars": 400_000})
        expiry.write_timer("f", {"stop": 1000.0})
        clk = Clock(1000.0)
        msg = expiry.run("f", "devin", self.cfg, sleep=clk.sleep, now=clk.now)
        self.assertIn("100K", msg)
        self.assertIn("ACU", msg)

    def test_resume_warning_not_repeated_after_timer_warned(self):
        env = dict(os.environ, COACH_HOME=self.home, COACH_NO_NOTIFY="1", COACH_NO_WORKER="1")
        now = time.time()
        state.save_cost("h", {"last_context": 120_000, "ttl": 300})
        state.save("h", {"prompts": 1, "last_activity": now - 1800})
        expiry.write_timer("h", {"stop": now - 1800, "notified": now - 1800})
        subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(
            {"hook_event_name": "UserPromptSubmit", "prompt": "add a test for parse()", "session_id": "h"}),
            text=True, env=env, timeout=20, check=True)
        with open(os.path.join(self.home, "events.jsonl")) as f:
            self.assertNotIn("cache_expired_resume", f.read())

    def test_single_timer_per_session(self):
        env = dict(os.environ, COACH_HOME=self.home, COACH_NO_NOTIFY="1")
        for i in range(3):
            subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(
                {"hook_event_name": "Stop", "session_id": "g", "prompt_id": f"p{i}"}),
                text=True, env=env, timeout=20, check=True)
        t = expiry.read_timer("g")
        self.assertTrue(expiry._alive(t.get("pid")))
        out = subprocess.run(["pgrep", "-f", "expiry.py g "], capture_output=True, text=True).stdout.split()
        self.assertEqual(len(out), 1, out)
        os.kill(int(t["pid"]), 15)


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = dict(os.environ, HOME=self.home, COACH_HOME=os.path.join(self.home, ".cost-coach"),
                        COACH_NO_LAUNCHCTL="1")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def cli(self, *a):
        return subprocess.run([sys.executable, "-I", os.path.join(ROOT, "coach", "cli.py"), *a],
                              capture_output=True, text=True, env=self.env, timeout=30)

    def test_parse(self):
        from coach import schedule
        self.assertEqual(schedule.parse("Fri 10:00"), (5, 10, 0))
        self.assertEqual(schedule.parse("monday 9:30"), (1, 9, 30))
        self.assertEqual(schedule.parse("금 10:00"), (5, 10, 0))
        self.assertEqual(schedule.parse("금요일 10:00"), (5, 10, 0))
        for bad in ["10:00", "Fri", "Fri 25:00", "xyz 10:00"]:
            with self.assertRaises(ValueError):
                schedule.parse(bad)

    def test_set_change_off(self):
        self.assertIn("off", self.cli("schedule").stdout)
        self.assertIn("Fri 10:00", self.cli("schedule", "Fri 10:00").stdout)
        self.assertIn("Mon 09:30", self.cli("schedule", "Mon 9:30").stdout)
        r = self.cli("schedule")
        self.assertIn("Mon 09:30", r.stdout)
        self.assertIn('cost-coach schedule "Mon 09:30"', r.stdout)   # hint
        self.assertEqual(self.cli("schedule", "someday").returncode, 1)
        self.assertIn("off", self.cli("schedule", "off").stdout)
        self.assertFalse(os.listdir(os.path.join(self.home, "Library", "LaunchAgents")))


class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp()
        self.old = config.HOME
        config.HOME = self.home

    def tearDown(self):
        config.HOME = self.old
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.root, ignore_errors=True)

    def _t(self, sid, ts, w):
        from datetime import datetime, timezone
        d = os.path.join(self.root, "p")
        os.makedirs(d, exist_ok=True)
        iso = datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")
        with open(os.path.join(d, sid + ".jsonl"), "w") as f:
            f.write(json.dumps({"type": "assistant", "timestamp": iso, "message": {
                "id": sid, "model": "claude-sonnet-5-5", "usage": {"cache_creation_input_tokens": w,
                                                                  "output_tokens": 100}}}) + "\n")

    def test_retro_compares_weeks_and_ranks_actions(self):
        now = time.time()
        self._t("old", now - 10 * 86400, 400_000)
        self._t("new", now - 2 * 86400, 200_000)
        state.log({"event": "finding", "rule": "cache_expired"})
        state.log({"event": "finding", "rule": "empty_prompt"})
        state.log({"event": "finding", "rule": "empty_prompt"})
        r = weekly.build(now=now, cfg=dict(config.DEFAULTS), root=self.root)
        md = weekly.render(r)
        self.assertIn("-50%", md)                           # spend halved vs last week
        self.assertIn("1. After a break longer than 5 minutes", md)   # weighted above 2x empty_prompt
        self.assertIn("instead of replying only 'ok'", md)
        self.assertIn("cost-coach schedule", md)                    # how to change the day/time

    def test_cli_weekly_writes_report(self):
        env = dict(os.environ, COACH_HOME=self.home, COACH_NO_NOTIFY="1")
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "coach", "cli.py"), "--root", self.root,
                            "weekly", "--no-send"], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.listdir(os.path.join(self.home, "reports")))


if __name__ == "__main__":
    unittest.main()
