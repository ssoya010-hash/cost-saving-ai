"""Run: cd cost-coach && python3 -m unittest discover -s tests -v"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
HOOK = os.path.join(ROOT, "coach", "hook.py")
WORKER = os.path.join(ROOT, "coach", "worker.py")

from coach import rules  # noqa: E402


def _read(p):
    with open(p) as f:
        return f.read()


def _read_json(p):
    return json.loads(_read(p))


class RuleTests(unittest.TestCase):
    def test_empty_prompts_hit(self):
        for t in ["ok", "OK!", "ㅇㅇ", "넵", "continue", "계속 진행해줘", "go ahead.", "  ㄱㄱ  ", "lgtm"]:
            self.assertIsNotNone(rules.empty_prompt(t), t)

    def test_real_prompts_miss(self):
        for t in ["ok, now add tests for parse_date in utils/date.py",
                  "Continue but skip the migration step and run pytest",
                  "Fix the flaky test in tests/test_api.py"]:
            self.assertIsNone(rules.empty_prompt(t), t)

    def test_correction(self):
        self.assertTrue(rules.is_correction("아니 그게 아니라 date 포맷은 ISO로"))
        self.assertTrue(rules.is_correction("No, revert that change"))
        self.assertFalse(rules.is_correction("Add a note about the README"))
        self.assertTrue(rules.is_correction("다시 해봐 근데 이번엔 src/x.py만"))
        self.assertTrue(rules.is_correction("왜 그 파일을 지웠어?"))

    def test_correction_false_positives(self):
        for t in ["no need to change the tests, just fix parse()",
                  "stop the dev server and run pytest in tests/",
                  "Undo button should be disabled when list is empty in ui/list.tsx",
                  "wrong answer is returned by calc() in math.py, fix it",
                  "Nobody calls this function anymore; remove it",
                  "Add a stop() method to the worker"]:
            self.assertFalse(rules.is_correction(t), t)
        self.assertIsNone(rules.correction_streak(1, 2))
        self.assertIsNotNone(rules.correction_streak(2, 2))

    def test_bundled(self):
        t = "1. fix pricing link\n2. add retry to webhook\n3. upgrade eslint\n4. update README"
        self.assertIsNotNone(rules.bundled_tasks(t))
        self.assertIsNone(rules.bundled_tasks("fix the pricing link in footer.tsx"))
        # numbered steps of ONE task are fine
        self.assertIsNone(rules.bundled_tasks(
            "1. read src/a.py\n2. find the bug\n3. fix it\n4. add a test\n5. run pytest"))
        self.assertIsNone(rules.bundled_tasks("API 그리고 DB 그리고 캐시 그리고 로그 확인해서 원인 찾아줘"))

    def test_vague_large(self):
        self.assertIsNotNone(rules.vague_large("결제 모듈 전체 리팩토링 해줘"))
        self.assertIsNone(rules.vague_large("refactor parse() in src/billing/usage.py to use dataclasses"))
        self.assertIsNone(rules.vague_large("/plan rewrite billing"))

    def test_budget_and_output(self):
        self.assertIsNone(rules.tool_call_budget(29, 30))
        self.assertIsNotNone(rules.tool_call_budget(30, 30))
        self.assertIsNone(rules.tool_call_budget(31, 30))   # warn once per turn
        self.assertIsNotNone(rules.large_output(50000, 20000, "exec"))
        self.assertIsNone(rules.large_output(1000, 20000, "exec"))

    def test_repeats(self):
        self.assertIsNone(rules.repeated_read("/a/b.py", 2, 3))
        self.assertIsNotNone(rules.repeated_read("/a/b.py", 3, 3))
        self.assertIsNone(rules.repeated_read("/a/b.py", 4, 3))
        self.assertIsNotNone(rules.retry_loop("pytest -x", 3, 3))

    def test_config_edit(self):
        for p in ["/r/CLAUDE.md", "/r/AGENTS.md", "/r/.mcp.json", "/r/.claude/settings.local.json"]:
            self.assertIsNotNone(rules.config_edit(p), p)
        self.assertIsNone(rules.config_edit("/r/src/app.py"))

    def test_cache_expired_resume(self):
        cfg = {"cache_ttl_s": 300, "resume_context_tokens": 50000}
        self.assertIsNotNone(rules.cache_expired_resume(900, {"last_context": 120000, "ttl": 300}, cfg))
        self.assertIsNone(rules.cache_expired_resume(120, {"last_context": 120000, "ttl": 300}, cfg))
        self.assertIsNone(rules.cache_expired_resume(900, {"last_context": 10000, "ttl": 300}, cfg))
        self.assertIsNone(rules.cache_expired_resume(1800, {"last_context": 120000, "ttl": 3600}, cfg))


class HookTests(unittest.TestCase):
    """The no-side-effect contract: nothing on stdout, exit 0, never blocks, fast."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = dict(os.environ, COACH_HOME=self.home, COACH_NO_NOTIFY="1", COACH_NO_WORKER="1")
        self.env.pop("CLAUDE_PROJECT_DIR", None)
        self.env.pop("DEVIN_PROJECT_DIR", None)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def raw(self, payload, **env):
        e = dict(self.env, **env)
        data = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run([sys.executable, "-I", HOOK], input=data, capture_output=True,
                              text=True, env=e, timeout=20)

    def run_hook(self, payload, **env):
        r = self.raw(payload, **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def cfg(self, **kv):
        with open(os.path.join(self.home, "config.json"), "w") as f:
            json.dump(kv, f)

    def findings(self):
        try:
            with open(os.path.join(self.home, "events.jsonl")) as f:
                return [json.loads(x)["rule"] for x in f if '"finding"' in x]
        except OSError:
            return []

    ALL_EVENTS = [
        {"hook_event_name": "UserPromptSubmit", "prompt": "ok", "session_id": "s"},
        {"hook_event_name": "UserPromptSubmit", "prompt": "1. a\n2. b\n3. c\n4. d", "session_id": "s"},
        {"hook_event_name": "UserPromptSubmit", "prompt": "전체 리팩토링 해줘", "session_id": "s"},
        {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {"file_path": "/r/CLAUDE.md"}, "session_id": "s"},
        {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git status"}, "session_id": "s"},
        {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "pytest"},
         "tool_response": {"stdout": "x" * 60000}, "session_id": "s"},
        {"hook_event_name": "PostToolUse", "tool_name": "exec", "tool_input": {"command": "ls"},
         "tool_response": "ok", "session_id": "s"},
        {"hook_event_name": "Stop", "session_id": "s"},
    ]

    def test_hooks_never_print(self):
        for _ in range(3):
            for p in self.ALL_EVENTS:
                self.assertEqual(self.run_hook(p), "", p)

    def test_findings_still_recorded(self):
        for p in self.ALL_EVENTS:
            self.run_hook(p)
        got = set(self.findings())
        self.assertTrue({"empty_prompt", "bundled_tasks", "vague_large_task",
                         "config_edit_midsession", "large_tool_output"} <= got, got)

    def test_never_blocks_or_rewrites_by_default(self):
        out = self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "ㅇㅇ", "session_id": "b"})
        self.assertNotIn("block", out)
        out = self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "exec",
                             "tool_input": {"command": "git status"}, "session_id": "b"})
        self.assertEqual(out, "")

    def test_opt_in_hints_and_block(self):
        self.cfg(agent_hints=True)
        out = json.loads(self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "ok", "session_id": "h"}))
        self.assertIn("ALL remaining steps", out["hookSpecificOutput"]["additionalContext"])
        self.cfg(mode="block")
        out = json.loads(self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "ok", "session_id": "h2"}))
        self.assertEqual(out["decision"], "block")
        self.assertEqual(self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "!ok", "session_id": "h2"}), "")

    def test_paused(self):
        self.cfg(enabled=False)
        self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "ok", "session_id": "p"})
        self.assertEqual(self.findings(), [])

    def test_garbage_input(self):
        for bad in ["not json", "", "[]", "{}", '{"hook_event_name": "PostToolUse", "tool_response": [1,2]}',
                    '{"hook_event_name": "UserPromptSubmit", "prompt": null}']:
            r = self.raw(bad)
            self.assertEqual(r.returncode, 0, bad)
            self.assertEqual(r.stdout, "", bad)

    def test_corrupt_state_and_config(self):
        os.makedirs(os.path.join(self.home, "sessions"))
        open(os.path.join(self.home, "sessions", "c.json"), "w").write("{broken")
        open(os.path.join(self.home, "config.json"), "w").write("{broken")
        self.assertEqual(self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "ok", "session_id": "c"}), "")
        self.assertIn("empty_prompt", self.findings())

    def test_correction_streak_and_repeats(self):
        for t in ["아니 그게 아니라", "no, revert that"]:
            self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": t, "session_id": "k"})
        for i in range(3):   # Claude Code gives every tool call its own tool_use_id
            self.run_hook({"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_use_id": f"r{i}",
                           "tool_input": {"file_path": "/r/a.py"}, "tool_response": "x", "session_id": "k"})
            self.run_hook({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_use_id": f"b{i}",
                           "tool_input": {"command": "npm test"}, "tool_response": "fail", "session_id": "k"})
        got = self.findings()
        for r in ("correction_loop", "repeated_read", "retry_loop"):
            self.assertIn(r, got)

    def test_cooldown_and_cap(self):
        from coach import config, notify
        old = config.HOME
        config.HOME = self.home
        os.environ["COACH_NO_NOTIFY"] = "1"
        try:
            f = rules.empty_prompt("ok")
            cfg = {"notify_cooldown_s": 600, "max_notifications_per_hour": 2, "macos_notify": False}
            st = {}
            notify.maybe_send(cfg, st, "x", f, "claude")
            t0 = st["last_notify"]["empty_prompt"]
            notify.maybe_send(cfg, st, "x", f, "claude")          # cooldown: unchanged
            self.assertEqual(st["last_notify"]["empty_prompt"], t0)
            notify.maybe_send(cfg, {}, "y", f, "claude")           # 2nd allowed in the hour
            st3 = {}
            notify.maybe_send(cfg, st3, "z", f, "claude")          # hourly cap reached
            self.assertNotIn("empty_prompt", st3.get("last_notify", {}))
            st4 = {}
            notify.maybe_send(dict(cfg, muted_rules=["empty_prompt"], max_notifications_per_hour=99), st4, "m", f, "c")
            self.assertNotIn("empty_prompt", st4.get("last_notify", {}))
        finally:
            config.HOME = old

    def test_duplicate_delivery_counted_once(self):
        p = {"hook_event_name": "UserPromptSubmit", "prompt": "ok", "session_id": "dup", "prompt_id": "p1"}
        procs = [subprocess.Popen([sys.executable, "-I", HOOK], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  text=True, env=self.env) for _ in range(2)]   # two installs, same event
        for pr in procs:
            pr.communicate(json.dumps(p), timeout=20)
        self.assertEqual(self.findings().count("empty_prompt"), 1)
        # a genuinely new prompt in the next turn is still seen
        self.run_hook(dict(p, prompt_id="p2"))
        self.assertEqual(self.findings().count("empty_prompt"), 2)

    def test_devin_repeats_without_ids(self):
        # Devin has no tool_use_id; real repeats are seconds apart (tool run + model call)
        p = {"hook_event_name": "PostToolUse", "tool_name": "read", "tool_input": {"file_path": "/r/b.py"},
             "tool_response": {"success": True, "output": "x", "error": None}, "session_id": "dr", "prompt_id": "t"}
        for _ in range(3):
            self.run_hook(p, DEVIN_PROJECT_DIR="/r")
            time.sleep(1.6)
        self.assertIn("repeated_read", self.findings())

    def test_devin_payloads(self):
        patch = "*** Begin Patch\n*** Update File: /r/AGENTS.md\n@@\n-a\n+b\n*** End Patch"
        self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "apply_patch",
                       "tool_input": {"patch": patch}, "session_id": "dv", "prompt_id": "q"},
                      DEVIN_PROJECT_DIR="/r")
        self.run_hook({"hook_event_name": "PostToolUse", "tool_name": "exec", "tool_input": {"command": "make"},
                       "tool_response": {"success": True, "output": "y" * 30000, "error": None},
                       "session_id": "dv", "prompt_id": "q"}, DEVIN_PROJECT_DIR="/r")
        self.assertEqual(self.run_hook({"hook_event_name": "Stop", "session_id": "dv", "prompt_id": "q",
                                        "stop_hook_active": False}, DEVIN_PROJECT_DIR="/r"), "")
        got = self.findings()
        self.assertIn("config_edit_midsession", got)
        self.assertIn("large_tool_output", got)

    def test_reread_after_edit_is_not_flagged(self):
        def ev(tool, i, **ti):
            return {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_use_id": f"{tool}{i}",
                    "tool_input": ti, "tool_response": "x", "session_id": "ra"}
        self.run_hook(ev("Read", 1, file_path="/r/a.py"))
        self.run_hook(ev("Edit", 1, file_path="/r/a.py"))
        self.run_hook(ev("Read", 2, file_path="/r/a.py"))
        self.run_hook(ev("Edit", 2, file_path="/r/a.py"))
        self.run_hook(ev("Read", 3, file_path="/r/a.py"))
        self.assertNotIn("repeated_read", self.findings())

    def test_hook_latency(self):
        times = []
        for i in range(8):
            t = time.perf_counter()
            self.run_hook({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                           "tool_input": {"command": f"ls {i}"}, "tool_response": "x", "session_id": "lat"})
            times.append((time.perf_counter() - t) * 1000)
        self.assertLess(statistics.median(times), 300, times)

    def test_report(self):
        for t in ["ok", "ㅇㅇ", "fix bug in a.py"]:
            self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": t, "session_id": "r"})
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "coach", "report.py"), "--json"],
                           capture_output=True, text=True, env=self.env)
        rep = json.loads(r.stdout)
        self.assertEqual(rep["findings"]["empty_prompt"], 2)
        self.assertEqual(rep["prompts"], 3)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = dict(os.environ, COACH_HOME=self.home, COACH_NO_NOTIFY="1")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _line(self, mid, ts, w=0, r=0, out=100):
        return json.dumps({"type": "assistant", "timestamp": ts, "message": {
            "id": mid, "model": "claude-opus-4-6", "usage": {
                "input_tokens": 0, "cache_creation_input_tokens": w, "cache_read_input_tokens": r,
                "output_tokens": out, "cache_creation": {"ephemeral_5m_input_tokens": w}}}}) + "\n"

    def test_incremental_receipts(self):
        tp = os.path.join(self.home, "t.jsonl")
        with open(tp, "w") as f:
            f.write(self._line("a", "2026-11-11T00:00:00Z", w=100_000))
            f.write(self._line("b", "2026-11-11T00:00:10Z", w=2_000, r=100_000))
        subprocess.run([sys.executable, "-I", WORKER, "w1", tp], env=self.env, timeout=20, check=True)
        c = _read_json(os.path.join(self.home, "sessions", "w1.cost.json"))
        self.assertEqual(c["calls"], 2)
        self.assertEqual(c["busts"], 0)
        with open(tp, "a") as f:   # 20 min pause, then the whole prefix is re-written
            f.write(self._line("c", "2026-11-11T00:20:10Z", w=103_000))
        subprocess.run([sys.executable, "-I", WORKER, "w1", tp], env=self.env, timeout=20, check=True)
        c = _read_json(os.path.join(self.home, "sessions", "w1.cost.json"))
        self.assertEqual(c["calls"], 3)
        self.assertEqual(c["bust_causes"], {"pause_over_ttl": 1})
        ev = _read(os.path.join(self.home, "events.jsonl"))
        self.assertIn("cache_rebuild", ev)

    def test_cache_expired_resume_end_to_end(self):
        """Worker records the context size; the next prompt after a long idle gap is flagged."""
        tp = os.path.join(self.home, "t2.jsonl")
        with open(tp, "w") as f:
            f.write(self._line("a", "2026-11-11T00:00:00Z", w=120_000))
        subprocess.run([sys.executable, "-I", WORKER, "e2e", tp], env=self.env, timeout=20, check=True)
        os.makedirs(os.path.join(self.home, "sessions"), exist_ok=True)
        st_path = os.path.join(self.home, "sessions", "e2e.json")
        with open(st_path, "w") as f:   # as left by the Stop hook 30 minutes ago
            json.dump({"prompts": 1, "last_activity": time.time() - 1800}, f)
        r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(
            {"hook_event_name": "UserPromptSubmit", "prompt": "now add a test for parse()", "session_id": "e2e"}),
            capture_output=True, text=True, env=dict(self.env, COACH_NO_WORKER="1"), timeout=20)
        self.assertEqual(r.stdout, "")
        self.assertIn("cache_expired_resume", _read(os.path.join(self.home, "events.jsonl")))

    def test_worker_does_not_touch_hook_state(self):
        tp = os.path.join(self.home, "t3.jsonl")
        with open(tp, "w") as f:
            f.write(self._line("a", "2026-11-11T00:00:00Z", w=900_000))   # crosses $2 -> receipt
        os.makedirs(os.path.join(self.home, "sessions"), exist_ok=True)
        st_path = os.path.join(self.home, "sessions", "ws.json")
        with open(st_path, "w") as f:
            json.dump({"prompts": 7, "reads": {"/a.py": 2}}, f)
        before = _read(st_path)
        subprocess.run([sys.executable, "-I", WORKER, "ws", tp], env=self.env, timeout=20, check=True)
        self.assertEqual(_read(st_path), before)
        c = _read_json(os.path.join(self.home, "sessions", "ws.cost.json"))
        self.assertIn("session_cost", c["last_notify"])

    def test_missing_transcript(self):
        r = subprocess.run([sys.executable, "-I", WORKER, "w2", "/nope.jsonl"], env=self.env, timeout=20)
        self.assertEqual(r.returncode, 0)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = dict(os.environ, HOME=self.home, COACH_HOME=os.path.join(self.home, ".cost-coach"),
                        COACH_NO_LAUNCHCTL="1")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def sh(self, *args):   # run from the repo dir with a RELATIVE path, as users do
        return subprocess.run(["bash", "install.sh", *args], capture_output=True, cwd=ROOT,
                              text=True, env=self.env, timeout=60)

    def test_install_preserves_existing_settings_and_uninstalls_cleanly(self):
        d = os.path.join(self.home, ".claude")
        os.makedirs(d)
        orig = {"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "say done"}]}]}}
        json.dump(orig, open(os.path.join(d, "settings.json"), "w"))
        r = self.sh("--claude-user", "--daily", "09:30")
        self.assertIn("Fri 10:00", r.stdout)                       # weekly retro on by default
        self.assertIn('cost-coach schedule "Mon 09:30"', r.stdout)   # hint to change it
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        s = json.load(open(os.path.join(d, "settings.json")))
        self.assertEqual(s["model"], "opus")
        self.assertEqual(len(s["hooks"]["Stop"]), 2)
        self.assertTrue(os.path.exists(os.path.join(d, "settings.json.cost-coach.bak")))
        self.sh("--claude-user")   # idempotent
        s = json.load(open(os.path.join(d, "settings.json")))
        self.assertEqual(len(s["hooks"]["Stop"]), 2)
        self.assertTrue(os.access(os.path.join(self.home, ".local", "bin", "cost-coach"), os.X_OK))
        r = self.sh("--uninstall", "--claude-user")
        self.assertEqual(r.returncode, 0, r.stderr)
        la = os.path.join(self.home, "Library", "LaunchAgents")
        self.assertEqual(os.listdir(la) if os.path.isdir(la) else [], [])
        self.assertEqual(json.load(open(os.path.join(d, "settings.json"))), orig)

    def test_backup_keeps_original_and_uninstall_all(self):
        d = os.path.join(self.home, ".claude")
        os.makedirs(d)
        orig = {"model": "opus"}
        json.dump(orig, open(os.path.join(d, "settings.json"), "w"))
        self.sh("--claude-user")
        self.sh("--claude-user")       # reinstall must not overwrite the original backup
        bak = os.path.join(d, "settings.json.cost-coach.bak")
        self.assertEqual(_read_json(bak), orig)
        self.assertEqual(self.sh("--devin-user").returncode, 0)
        r = self.sh("--uninstall", "--all")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertNotIn("command not found", r.stderr + r.stdout)
        self.assertEqual(_read_json(os.path.join(d, "settings.json")), orig)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".config", "devin", "config.json")))
        self.assertFalse(os.path.exists(bak))   # nothing of ours left -> backup cleaned up

    def test_refuses_invalid_json(self):
        d = os.path.join(self.home, ".claude")
        os.makedirs(d)
        open(os.path.join(d, "settings.json"), "w").write("{oops")
        r = self.sh("--claude-user")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(open(os.path.join(d, "settings.json")).read(), "{oops")

    def test_devin_repo_and_rules_opt_in(self):
        repo = os.path.join(self.home, "repo")
        os.makedirs(repo)
        self.assertEqual(self.sh("--devin", repo).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(repo, "AGENTS.md")))     # rules are opt-in
        h = json.load(open(os.path.join(repo, ".devin", "hooks.v1.json")))
        self.assertEqual(h["PreToolUse"][0]["matcher"], "^(edit|write|apply_patch)$")
        self.assertEqual(self.sh("--devin", repo, "--rules").returncode, 0)
        self.assertIn("cost-coach:begin", open(os.path.join(repo, "AGENTS.md")).read())
        self.sh("--uninstall", "--devin", repo)
        self.assertFalse(os.path.exists(os.path.join(repo, "AGENTS.md")))
        # an AGENTS.md the user already had keeps its own content
        with open(os.path.join(repo, "AGENTS.md"), "w") as f:
            f.write("# Team rules\n- use pnpm\n")
        self.sh("--devin", repo, "--rules")
        self.sh("--uninstall", "--devin", repo)
        self.assertEqual(_read(os.path.join(repo, "AGENTS.md")), "# Team rules\n- use pnpm\n")


if __name__ == "__main__":
    unittest.main()
