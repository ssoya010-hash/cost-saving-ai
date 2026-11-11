#!/usr/bin/env python3
"""Weekly anti-pattern report from ~/.cost-coach/events.jsonl.

  python3 -m coach.report --days 7 [--json] [--post]   (--post sends it to the webhook)

"Avoidable units" are deliberately conservative:
  empty_prompt      -> 1 billed turn each (the message itself)
  correction_loop   -> 1 billed turn each (the extra correction beyond the threshold)
  long_turn         -> 1 likely continuation each
  bundled/vague/large_output are counted but not priced (effect depends on billing model).
"""
import argparse
import collections
import json
import os
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from coach import config, notify, state  # type: ignore
else:
    from . import config, notify, state

PRICED = {"empty_prompt": 1, "correction_loop": 1, "long_turn": 1}


def build(days: float):
    since = time.time() - days * 86400
    rules = collections.Counter()
    prompts = collections.defaultdict(int)
    tools = 0
    big_chars = 0
    blocked = 0
    for e in state.read_events(since):
        ev = e.get("event")
        if ev == "finding":
            rules[e["rule"]] += 1
        elif ev == "tool":
            tools += 1
            big_chars += e.get("chars", 0)
        elif ev == "prompt":
            prompts[e.get("session")] += 1
        elif ev == "blocked":
            blocked += 1
    total_prompts = sum(prompts.values())
    avoidable = sum(rules[r] * w for r, w in PRICED.items())
    return {
        "days": days, "sessions": len(prompts), "prompts": total_prompts, "tool_calls": tools,
        "tool_output_chars": big_chars, "blocked": blocked,
        "findings": dict(rules.most_common()), "avoidable_units": avoidable,
        "avoidable_share": round(avoidable / total_prompts, 3) if total_prompts else None,
    }


def render(r, price):
    lines = [f"Cost Coach habits - last {r['days']:g} days",
             f"sessions {r['sessions']} · prompts {r['prompts']} · tool calls {r['tool_calls']}", ""]
    for rule, n in r["findings"].items():
        tag = f"  ≈ ${n * PRICED[rule] * price:,.2f}" if rule in PRICED else ""
        lines.append(f"  {rule:20} {n:>5}{tag}")
    share = f" ({r['avoidable_share']:.0%} of prompts)" if r["avoidable_share"] is not None else ""
    lines += ["", f"Avoidable billed units: {r['avoidable_units']}{share}"
                  f"  ≈ ${r['avoidable_units'] * price:,.2f}"]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--post", action="store_true", help="send to webhook_url")
    a = ap.parse_args(argv)
    cfg = config.load()
    r = build(a.days)
    text = json.dumps(r, indent=2) if a.json else render(r, cfg["unit_price_usd"])
    print(text)
    if a.post and cfg.get("webhook_url"):
        notify._webhook(cfg["webhook_url"], "Cost Coach habits", render(r, cfg["unit_price_usd"]), r)


if __name__ == "__main__":
    main()
