#!/usr/bin/env python3
"""cost-coach: measure real AI coding spend and before/after savings in one command.

  cost-coach status [--days 7]          Claude Code cache-aware $ (from local transcripts) + Devin ACU log
  cost-coach sessions [--days 1]        per-session receipts, most expensive first
  cost-coach mark "<label>"             mark the moment you changed something (tool, habit, rule)
  cost-coach compare [--label X] [--window 14]
                                        median $/session before vs. after the mark
  cost-coach devin add <ACU> [--session ID] [--note TEXT]
  cost-coach devin import <file.csv>    columns: date|ts, acu, session, note
  cost-coach habits [--days 7]          anti-pattern counts from the hooks + their ACU/$ cost
  cost-coach post [--days 7]            send the status to the Slack-compatible webhook
  cost-coach notify [--days 1]          macOS notification + webhook (used by the daily launchd job)
  cost-coach weekly [--no-send] [--open] weekly retrospective (this vs last week, top habits, 3 actions)
  cost-coach schedule ["Fri 10:00"|off] when the weekly retro arrives (Mac local time; default Fri 10:00)
  cost-coach doctor                     check install, hooks, notifications, data
  cost-coach test-notify                send a test notification
  cost-coach pause | resume             turn all hooks off / on without uninstalling
  cost-coach mute <rule> | unmute <rule>
  cost-coach prune [--days 14]          delete old session state
"""
import argparse
import json
import os
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from coach import config, measure, notify, report, schedule, state, weekly  # type: ignore
else:
    from . import config, measure, notify, report, schedule, state, weekly


def _usd(x):
    return f"${x:,.2f}" if x is not None else "-"


def render_status(days, cfg, root=None):
    since = time.time() - days * 86400
    cs = measure.claude_sessions(since, None, root, cfg)
    s = measure.summarize(cs)
    d = measure.devin_summary(measure.devin_sessions(since), cfg["acu_price_usd"])
    L = [f"AI cost - last {days:g} days", ""]
    if s.get("sessions"):
        sh = s["share_pct"]
        L += [f"Claude Code  {s['sessions']} sessions · total {_usd(s['total_usd'])} · "
              f"median {_usd(s['median_usd_per_session'])}/session",
              f"  cache hit {s['cache_hit_pct']}% · without cache it would be {_usd(s['usd_without_cache'])}",
              f"  bill = cache write {sh['cache_write']}% · output {sh['output']}% · "
              f"cache read {sh['cache_read']}% · uncached {sh['uncached_in']}%",
              f"  {s['prompts_per_session']} prompts & {s['calls_per_session']} API calls per session · "
              f"median peak context {s['median_peak_context']:,} tok",
              f"  cache busts {s['cache_busts']} (≈ {_usd(s['cache_bust_usd'])} re-written): "
              f"{s['bust_causes']['pause_over_ttl']} after a pause > cache TTL, "
              f"{s['bust_causes']['prefix_changed']} prefix lost mid-session"]
        tok = sum(s["tokens_total"].values())
        acu = tok / 1e6 * cfg.get("devin_acu_per_mtok", 0.4)
        L.append(f"  same {tok / 1e6:,.1f}M tokens on Devin CLI ≈ {acu:,.1f} ACU = {_usd(acu * cfg['acu_price_usd'])} "
                 f"(flat {cfg.get('devin_acu_per_mtok', 0.4)} ACU/MTok; {s['token_share_pct']['cache_read']}% of it is "
                 "re-read context)")
    else:
        L.append("Claude Code  no sessions found in ~/.claude/projects")
    if d.get("sessions"):
        L.append(f"Devin        {d['sessions']} sessions · {d['total_acu']} ACU = {_usd(d['total_usd'])} · "
                 f"median {d['median_acu_per_session']} ACU/session")
    else:
        L.append("Devin        no ACU logged yet (cost-coach devin add <ACU>)")
    tips = []
    if s.get("sessions"):
        if s["share_pct"]["cache_write"] > 50:
            tips.append("Cache writes dominate: read fewer/smaller files once, split long jobs into new sessions.")
        if s["cache_busts"]:
            if s["bust_causes"]["pause_over_ttl"]:
                tips.append("Pauses longer than the cache TTL re-write the whole context: after a long break, "
                            "start a new session with a short summary instead of continuing.")
            if s["bust_causes"]["prefix_changed"]:
                tips.append("Cached prefix lost mid-session (CLAUDE.md/MCP/settings edits, model or effort "
                            "switch, compaction, or provider-side eviction): keep config stable within a session.")
        if s["share_pct"]["output"] > 35:
            tips.append("Output is a big share: ask for narrower changes, smaller diffs, no long summaries.")
        if s["median_peak_context"] > 150000:
            tips.append("Contexts are large: /clear between tasks, aggregate logs with a script instead of dumping.")
    if tips:
        L += ["", "Tips:"] + [f"  - {t}" for t in tips]
    return "\n".join(L), {"claude": s, "devin": d}


def render_sessions(days, cfg, limit=15, root=None):
    since = time.time() - days * 86400
    cs = sorted(measure.claude_sessions(since, None, root, cfg), key=lambda s: -s["usd"])[:limit]
    L = [f"{'$':>8} {'calls':>5} {'prompts':>7} {'peak ctx':>9} {'hit%':>5} {'busts':>5}  project/session"]
    for s in cs:
        inp = s["tokens"]["uncached_in"] + s["tokens"]["cache_write"] + s["tokens"]["cache_read"]
        hit = 100 * s["tokens"]["cache_read"] / inp if inp else 0
        L.append(f"{s['usd']:>8.2f} {s['calls']:>5} {s['user_prompts']:>7} {s['peak_context']:>9,} "
                 f"{hit:>5.0f} {s['cache_busts']:>5}  {s['project'][-28:]}/{s['session'][:8]}")
    return "\n".join(L)


def render_compare(r, label):
    c, d = r["claude"], r["devin"]
    L = [f"Before vs. after mark '{label}'", ""]
    for name, side in (("before", c["before"]), ("after", c["after"])):
        if side.get("sessions"):
            L.append(f"Claude {name:6} {side['sessions']:>4} sessions · median {_usd(side['median_usd_per_session'])}"
                     f"/session · cache hit {side['cache_hit_pct']}% · busts {side['cache_busts']}")
        else:
            L.append(f"Claude {name:6} no sessions")
    if c.get("change_pct_median_usd_per_session") is not None:
        L.append(f"  -> median $/session change: {c['change_pct_median_usd_per_session']:+.1f}%")
    for name, side in (("before", d["before"]), ("after", d["after"])):
        if side.get("sessions"):
            L.append(f"Devin  {name:6} {side['sessions']:>4} sessions · median {side['median_acu_per_session']} ACU/session")
    if d.get("change_pct_median_acu_per_session") is not None:
        L.append(f"  -> median ACU/session change: {d['change_pct_median_acu_per_session']:+.1f}%")
    n = min(c["before"].get("sessions", 0), c["after"].get("sessions", 0))
    if n < 20:
        L.append(f"\nNote: only {n} sessions on one side. Collect ≥20 per side before deciding; "
                 "compare similar work (task mix changes the bill more than most tools).")
    return "\n".join(L)


def _set_cfg(**kv):
    p = os.path.join(config.HOME, "config.json")
    try:
        with open(p) as f:
            c = json.load(f)
    except (OSError, ValueError):
        c = {}
    c.update(kv)
    os.makedirs(config.HOME, exist_ok=True)
    with open(p, "w") as f:
        json.dump(c, f, indent=2)


def doctor(cfg):
    import platform
    import shutil
    import subprocess
    ok = True

    def line(good, label, detail=""):
        nonlocal ok
        ok = ok and good
        print(f"  {'✓' if good else '✗'} {label}" + (f"  {detail}" if detail else ""))

    print("cost-coach doctor")
    hook = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook.py")
    line(os.path.exists(hook), "app installed", os.path.dirname(hook))
    line(cfg.get("enabled", True), "enabled", "" if cfg.get("enabled", True) else "run: cost-coach resume")
    found = []
    for f in (os.path.expanduser("~/.claude/settings.json"), os.path.expanduser("~/.config/devin/config.json")):
        try:
            if "coach/hook.py" in open(f).read():
                found.append(f)
        except OSError:
            pass
    line(bool(found), "hooks registered (user level)", ", ".join(found) or "none (repo-level installs are not checked)")
    # side-effect check: hook must print nothing
    t0 = time.time()
    import tempfile
    tmp_home = tempfile.mkdtemp(prefix="cost-coach-doctor-")   # self-test never touches real data
    env = dict(os.environ, COACH_NO_NOTIFY="1", COACH_NO_WORKER="1", COACH_HOME=tmp_home)
    r = subprocess.run([sys.executable, "-I", hook], input=json.dumps(
        {"hook_event_name": "UserPromptSubmit", "prompt": "ok", "session_id": "doctor-selftest"}),
        capture_output=True, text=True, env=env, timeout=10)
    ms = (time.time() - t0) * 1000
    shutil.rmtree(tmp_home, ignore_errors=True)
    silent = r.stdout == "" or cfg.get("agent_hints") or cfg.get("mode") == "block"
    line(r.returncode == 0 and silent, "hook adds nothing to the agent context",
         "" if not (cfg.get("agent_hints") or cfg.get("mode") == "block") else "NOTE: agent_hints/block mode is ON (opt-in)")
    line(ms < 500, f"hook latency {ms:.0f} ms")
    mac = platform.system() == "Darwin"
    tn = shutil.which("terminal-notifier")
    line(mac, "macOS notifications", "terminal-notifier" if tn else "osascript (allow 'Script Editor' in Notifications)")
    n = len(measure.transcript_files())
    line(n > 0, "Claude Code transcripts found", f"{n} files")
    print(f"  · weekly retro: {schedule.current() or 'off'}  ({schedule.HINT.split(' · ')[0]})")
    print("  · config: " + os.path.join(config.HOME, "config.json"))
    print("  · data:   " + config.HOME)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cost-coach", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", help="Claude transcripts dir (default ~/.claude/projects)")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("status"); p.add_argument("--days", type=float, default=7)
    p = sub.add_parser("sessions"); p.add_argument("--days", type=float, default=1); p.add_argument("--limit", type=int, default=15)
    p = sub.add_parser("mark"); p.add_argument("label")
    p = sub.add_parser("compare"); p.add_argument("--label"); p.add_argument("--window", type=float, default=14)
    p = sub.add_parser("devin"); ds = p.add_subparsers(dest="dcmd")
    q = ds.add_parser("add"); q.add_argument("acu", type=float); q.add_argument("--session", default=""); q.add_argument("--note", default="")
    q = ds.add_parser("import"); q.add_argument("csv")
    p = sub.add_parser("habits"); p.add_argument("--days", type=float, default=7)
    p = sub.add_parser("post"); p.add_argument("--days", type=float, default=7)
    p = sub.add_parser("notify"); p.add_argument("--days", type=float, default=1)
    p = sub.add_parser("weekly"); p.add_argument("--no-send", action="store_true"); p.add_argument("--open", action="store_true")
    p = sub.add_parser("schedule"); p.add_argument("spec", nargs="?")
    sub.add_parser("doctor"); sub.add_parser("test-notify"); sub.add_parser("pause"); sub.add_parser("resume")
    p = sub.add_parser("mute"); p.add_argument("rule")
    p = sub.add_parser("unmute"); p.add_argument("rule")
    p = sub.add_parser("prune"); p.add_argument("--days", type=float, default=14)
    a = ap.parse_args(argv)
    cfg = config.load()

    if a.cmd in (None, "status"):
        text, data = render_status(getattr(a, "days", 7), cfg, a.root)
        print(json.dumps(data, indent=2) if a.json else text)
    elif a.cmd == "sessions":
        print(render_sessions(a.days, cfg, a.limit, a.root))
    elif a.cmd == "mark":
        m = measure.add_mark(a.label)
        print(f"marked '{a.label}' at {time.strftime('%Y-%m-%d %H:%M', time.localtime(m['ts']))}. "
              "Run `cost-coach compare` after a week or two of normal work.")
    elif a.cmd == "compare":
        ms = measure.marks()
        if a.label:
            ms = [m for m in ms if m["label"] == a.label]
        if not ms:
            print("no mark yet: run `cost-coach mark \"<what you changed>\"` first"); return 1
        m = ms[-1]
        r = measure.compare(m["ts"], a.window, a.root, cfg, cfg["acu_price_usd"])
        print(json.dumps(r, indent=2) if a.json else render_compare(r, m["label"]))
    elif a.cmd == "devin":
        if a.dcmd == "add":
            r = measure.devin_add(a.acu, a.session, a.note)
            print(f"logged {r['acu']} ACU (= ${r['acu'] * cfg['acu_price_usd']:.2f})")
        elif a.dcmd == "import":
            print(f"imported {measure.devin_import_csv(a.csv)} rows")
        else:
            print("usage: cost-coach devin add <ACU> | import <csv>"); return 1
    elif a.cmd == "habits":
        r = report.build(a.days)
        print(json.dumps(r, indent=2) if a.json else report.render(r, cfg["unit_price_usd"]))
    elif a.cmd == "notify":
        text, data = render_status(a.days, cfg, a.root)
        c = data["claude"]
        if c.get("sessions"):
            body = (f"Yesterday: {c['sessions']} sessions, {_usd(c['total_usd'])}, cache hit {c['cache_hit_pct']}%, "
                    f"{c['cache_busts']} cache busts. Run `cost-coach status` for tips.")
            notify.send(dict(cfg, webhook_url=""), "Cost Coach · daily", body, {})
            if cfg.get("webhook_url"):
                notify._webhook(cfg["webhook_url"], "AI cost daily", "```" + text + "```", data)
        print(text)
    elif a.cmd == "weekly":
        path, md = weekly.run(cfg, a.root, send=not a.no_send)
        print(md)
        print(f"saved: {path}")
        if a.open and sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
    elif a.cmd == "schedule":
        if a.spec is None:
            cur = schedule.current()
            print(f"weekly retro: {cur or 'off'} (Mac local time)")
            print(schedule.HINT)
        elif a.spec.lower() in ("off", "none", "disable"):
            print("weekly retro: off" if schedule.off() else "weekly retro was already off")
        else:
            try:
                when = schedule.set_weekly(a.spec, sys.executable, os.path.abspath(__file__), config.HOME)
            except ValueError as e:
                print(f"error: {e}"); return 1
            print(f"weekly retro: every {when} (Mac local time)")
    elif a.cmd == "doctor":
        return doctor(cfg)
    elif a.cmd == "test-notify":
        sent = notify.send(dict(cfg, macos_notify=True), "Cost Coach · test",
                           "Notifications work. You will see tips like this when a cost anti-pattern happens.", {})
        print("sent via: " + (", ".join(sent) or "nothing (not macOS, or notifier unavailable)"))
        print("Not visible? System Settings > Notifications > Script Editor (or terminal-notifier): allow alerts.")
    elif a.cmd in ("pause", "resume"):
        _set_cfg(enabled=(a.cmd == "resume"))
        print(f"cost-coach {'enabled' if a.cmd == 'resume' else 'paused'} (hooks stay installed)")
    elif a.cmd in ("mute", "unmute"):
        m = set(cfg.get("muted_rules") or [])
        (m.add if a.cmd == "mute" else m.discard)(a.rule)
        _set_cfg(muted_rules=sorted(m))
        print(f"muted rules: {sorted(m) or 'none'}")
    elif a.cmd == "prune":
        print(f"removed {state.prune(a.days)} old session files")
    elif a.cmd == "post":
        text, data = render_status(a.days, cfg, a.root)
        if not cfg.get("webhook_url"):
            print("no webhook_url in ~/.cost-coach/config.json (or COACH_WEBHOOK_URL)"); return 1
        notify._webhook(cfg["webhook_url"], "AI cost weekly", "```" + text + "```", data)
        print("posted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
