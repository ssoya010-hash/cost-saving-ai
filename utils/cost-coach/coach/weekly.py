"""Weekly retrospective: this week vs last week, where the money went, top habits, 3 actions.

Writes ~/.cost-coach/reports/week-<YYYY>-W<ww>.md, sends a macOS notification (and the webhook if set).
"""
import collections
import datetime
import os
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from coach import config, measure, notify, schedule, state  # type: ignore
else:
    from . import config, measure, notify, schedule, state

ACTIONS = {
    "cache_expired": "After a break longer than 5 minutes, start a new session with a short summary instead of continuing a large one.",
    "cache_expired_resume": "After a break longer than 5 minutes, start a new session with a short summary instead of continuing a large one.",
    "cache_rebuild": "Keep CLAUDE.md / AGENTS.md / MCP / model settings unchanged during a session.",
    "config_edit_midsession": "Edit agent config files between sessions, not during one.",
    "empty_prompt": "Put the next instruction in the same message instead of replying only 'ok'.",
    "correction_loop": "When you correct the agent twice, restate the full requirement once or restart.",
    "bundled_tasks": "Give each independent task its own session.",
    "vague_large_task": "For big changes, ask for a plan first and name the files.",
    "large_tool_output": "Ask for narrow commands (line ranges, --stat, filters) instead of full dumps.",
    "repeated_read": "Point the agent at what it already read instead of letting it re-read.",
    "retry_loop": "After 3 failed tries, stop and change approach.",
    "long_turn": "Watch long turns; if the agent loops, interrupt and narrow the task.",
    "large_context": "Use /clear or a new session when the context passes ~150K tokens.",
    "session_cost": "Split expensive sessions: one task per session.",
}
# rough share of waste each habit stands for, used only to rank actions
WEIGHT = {"cache_rebuild": 5, "cache_expired": 5, "cache_expired_resume": 4, "config_edit_midsession": 4,
          "large_context": 3, "correction_loop": 3, "bundled_tasks": 2, "large_tool_output": 2,
          "retry_loop": 2, "repeated_read": 1, "empty_prompt": 1, "vague_large_task": 1, "long_turn": 1,
          "session_cost": 1}


def _pct(a, b):
    return f"{100 * (a / b - 1):+.0f}%" if a is not None and b else "n/a"


def build(now=None, cfg=None, root=None):
    cfg = cfg or config.load()
    now = now or time.time()
    wk = 7 * 86400
    cur = measure.summarize(measure.claude_sessions(now - wk, now, root, cfg))
    prev = measure.summarize(measure.claude_sessions(now - 2 * wk, now - wk, root, cfg))
    dcur = measure.devin_summary(measure.devin_sessions(now - wk, now), cfg["acu_price_usd"])
    dprev = measure.devin_summary(measure.devin_sessions(now - 2 * wk, now - wk), cfg["acu_price_usd"])
    habits, hprev = collections.Counter(), collections.Counter()
    for e in state.read_events(now - 2 * wk):
        if e.get("event") == "finding":
            (habits if e["ts"] >= now - wk else hprev)[e["rule"]] += 1
    return {"now": now, "claude": cur, "claude_prev": prev, "devin": dcur, "devin_prev": dprev,
            "habits": habits, "habits_prev": hprev}


def render(r):
    c, p, d, dp = r["claude"], r["claude_prev"], r["devin"], r["devin_prev"]
    y, w, _ = datetime.date.fromtimestamp(r["now"]).isocalendar()
    L = [f"# AI cost retrospective · {y}-W{w:02d}", ""]
    L += ["## Spend", "", "| | This week | Last week | Change |", "|---|---|---|---|"]
    if c.get("sessions"):
        L.append(f"| Claude Code total | ${c['total_usd']:,.2f} | {('$%.2f' % p['total_usd']) if p.get('sessions') else '-'} "
                 f"| {_pct(c['total_usd'], p.get('total_usd'))} |")
        L.append(f"| Claude median $/session | ${c['median_usd_per_session']:.2f} | "
                 f"{('$%.2f' % p['median_usd_per_session']) if p.get('sessions') else '-'} | "
                 f"{_pct(c['median_usd_per_session'], p.get('median_usd_per_session'))} |")
        L.append(f"| Sessions | {c['sessions']} | {p.get('sessions', 0)} | |")
        L.append(f"| Cache hit | {c['cache_hit_pct']}% | {str(p['cache_hit_pct']) + '%' if p.get('sessions') else '-'} | |")
        L.append(f"| Re-written after cache loss | ${c['cache_bust_usd']:.2f} ({c['cache_busts']}x) | "
                 f"{('$%.2f' % p['cache_bust_usd']) if p.get('sessions') else '-'} | "
                 f"{_pct(c['cache_bust_usd'], p.get('cache_bust_usd'))} |")
    else:
        L.append("| Claude Code | no sessions | | |")
    if d.get("sessions"):
        L.append(f"| Devin ACU | {d['total_acu']} (${d['total_usd']:.2f}) | {dp.get('total_acu', '-')} | "
                 f"{_pct(d['total_acu'], dp.get('total_acu'))} |")
    L.append("")
    if c.get("sessions"):
        sh = c["share_pct"]
        L += ["## Where the Claude money went", "",
              f"cache write {sh['cache_write']}% · output {sh['output']}% · cache read {sh['cache_read']}% · "
              f"uncached {sh['uncached_in']}%", ""]
        if c["cache_busts"]:
            bc = c["bust_causes"]
            L += [f"Cache losses: {bc['pause_over_ttl']} after a pause longer than the cache lifetime, "
                  f"{bc['prefix_changed']} from a changed prefix (config, model, compaction).", ""]
    h, hp = r["habits"], r["habits_prev"]
    L += ["## Habits", ""]
    if h:
        L += ["| Pattern | This week | Last week |", "|---|---|---|"]
        for rule, n in h.most_common(8):
            L.append(f"| {rule} | {n} | {hp.get(rule, 0)} |")
    else:
        L.append("No cost anti-patterns detected this week.")
    L += ["", "## 3 actions for next week", ""]
    ranked = sorted(h, key=lambda k: -h[k] * WEIGHT.get(k, 1))
    if c.get("sessions") and c["cache_busts"] and "cache_rebuild" not in ranked:
        ranked.insert(0, "cache_rebuild")
    seen, n = set(), 0
    for rule in ranked:
        a = ACTIONS.get(rule)
        if a and a not in seen:
            seen.add(a)
            n += 1
            L.append(f"{n}. {a}")
        if n == 3:
            break
    if n == 0:
        L.append("1. Keep going. Run `cost-coach compare` after your next change to see its effect.")
    L += ["", "---", "", f"_{schedule.HINT}_"]
    return "\n".join(L) + "\n"


def headline(r):
    c, p = r["claude"], r["claude_prev"]
    if not c.get("sessions"):
        return "No Claude Code sessions this week."
    top = r["habits"].most_common(1)
    t = f"${c['total_usd']:,.0f} this week ({_pct(c['total_usd'], p.get('total_usd'))} vs last), " \
        f"${c['cache_bust_usd']:.0f} lost to cache rebuilds."
    if top:
        t += f" Top habit: {top[0][0]} ({top[0][1]}x)."
    return t


def run(cfg=None, root=None, send=True):
    cfg = cfg or config.load()
    r = build(cfg=cfg, root=root)
    md = render(r)
    y, w, _ = datetime.date.fromtimestamp(r["now"]).isocalendar()
    path = os.path.join(config.HOME, "reports", f"week-{y}-W{w:02d}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(md)
    if send:
        notify.send(dict(cfg, webhook_url=""), "Cost Coach · weekly retro", headline(r) + " Details: cost-coach weekly · change day/time: cost-coach schedule", {})
        if cfg.get("webhook_url"):
            notify._webhook(cfg["webhook_url"], "AI cost weekly retro", md, {"headline": headline(r)})
    return path, md
