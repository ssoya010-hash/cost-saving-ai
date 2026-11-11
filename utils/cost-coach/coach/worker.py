#!/usr/bin/env python3
"""Background worker started (detached) by the Stop hook. Never touches the agent.

Incrementally parses the Claude Code transcript from the last byte offset, keeps a running
cache-aware session cost, and sends receipts: cost thresholds, cache rebuilds, large context.

usage: worker.py <session_id> <transcript_path>
"""
import json
import os
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from coach import config, notify, pricing, state  # type: ignore
else:
    from . import config, notify, pricing, state


def _ts(s):
    from datetime import datetime
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def update(sid: str, path: str, cfg: dict) -> dict:
    c = state.load_cost(sid)
    c.setdefault("offset", 0)
    c.setdefault("usd", 0.0)
    c.setdefault("calls", 0)
    c.setdefault("busts", 0)
    c.setdefault("bust_usd", 0.0)
    c.setdefault("bust_causes", {})
    c.setdefault("last_context", 0)
    c.setdefault("last_t", None)
    c.setdefault("ttl", cfg.get("cache_ttl_s", 300))
    c.setdefault("seen", [])
    seen = set(c["seen"])
    try:
        size = os.path.getsize(path)
        if size < c["offset"]:  # transcript rewritten
            c["offset"] = 0
        with open(path, "rb") as f:
            f.seek(c["offset"])
            data = f.read()
    except OSError:
        return c
    end = data.rfind(b"\n")
    if end < 0:
        return c
    chunk, c["offset"] = data[:end + 1], c["offset"] + end + 1
    new_busts = 0
    for raw in chunk.splitlines():
        if b'"usage"' not in raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        m = d.get("message") or {}
        u = m.get("usage")
        if d.get("type") != "assistant" or not u or m.get("model") == "<synthetic>":
            continue
        key = m.get("id") or d.get("uuid")
        if key in seen:
            continue
        seen.add(key)
        r = pricing.cost(u, m.get("model", ""), cfg)
        c["usd"] += r["usd"]
        c["calls"] += 1
        c["model"] = m.get("model", "")
        tok = r["tokens"]
        ctx = tok["uncached_in"] + tok["cache_write"] + tok["cache_read"]
        t = _ts(d.get("timestamp"))
        if d.get("isSidechain"):
            continue
        lost = c["last_context"] - tok["cache_read"]
        if c["last_context"] and lost >= cfg.get("cache_bust_tokens", 30000) and tok["cache_write"] >= lost * 0.8:
            cause = "pause_over_ttl" if (t and c["last_t"] and t - c["last_t"] > c["ttl"] - 10) else "prefix_changed"
            c["busts"] += 1
            new_busts += 1
            c["bust_causes"][cause] = c["bust_causes"].get(cause, 0) + 1
            c["bust_usd"] += lost * pricing.rates(m.get("model", ""), cfg)[0] * 1.25 / 1e6 * float(cfg.get("price_multiplier", 1.0))
            c["last_bust_cause"] = cause
        cc = u.get("cache_creation") or {}
        if cc.get("ephemeral_1h_input_tokens"):
            c["ttl"] = 3600
        elif cc.get("ephemeral_5m_input_tokens"):
            c["ttl"] = 300
        c["last_context"], c["last_t"] = ctx, t
    c["seen"] = list(seen)[-2000:]
    c["new_busts"] = new_busts
    return c


def receipts(sid: str, c: dict, cfg: dict) -> list:
    out = []
    crossed = [x for x in cfg.get("session_notify_usd", []) if c["usd"] >= x > c.get("usd_notified", 0)]
    if crossed:
        c["usd_notified"] = max(crossed)
        out.append(("session_cost", f"This session has cost ${c['usd']:.2f} ({c['calls']} API calls, "
                                    f"context {c['last_context'] // 1000}K). For an unrelated task, start a new session."))
    if c.get("new_busts"):
        cause = c.get("last_bust_cause")
        why = ("you resumed after a pause longer than the cache lifetime" if cause == "pause_over_ttl"
               else "the cached prefix changed (config/MCP edit, model or effort switch, compaction)")
        out.append(("cache_rebuild", f"Cache rebuilt ({c['busts']}x this session, ≈ ${c['bust_usd']:.2f}): {why}."))
    lim = cfg.get("large_context_tokens", 150000)
    if c["last_context"] >= lim and not c.get("ctx_notified"):
        c["ctx_notified"] = True
        out.append(("large_context", f"Context is {c['last_context'] // 1000}K tokens and every call re-sends it. "
                                     "Use /clear or a new session for the next task."))
    return out


def main(argv):
    if len(argv) < 3:
        return 0
    sid, path = argv[1], argv[2]
    cfg = config.load()
    try:
        c = update(sid, path, cfg)
        found = receipts(sid, c, cfg)
        # The worker keeps its own notification state inside the cost file, so it never
        # overwrites the hook's session state (the two can run at the same time).
        wst = {"last_notify": c.setdefault("last_notify", {})}
        for rule, msg in found:
            f = type("F", (), {"rule": rule, "message": msg})()
            sent = notify.maybe_send(cfg, wst, sid, f, "claude")
            state.log({"event": "finding", "rule": rule, "session": sid, "host": "claude", "notified": sent})
        c["last_notify"] = wst["last_notify"]
        if int(time.time()) % 50 == 0:
            state.prune(14)
        state.log({"event": "session_cost", "session": sid, "usd": round(c["usd"], 4), "calls": c["calls"],
                   "cache_busts": c["busts"], "context": c["last_context"]})
        c.pop("new_busts", None)
        state.save_cost(sid, c)
    except Exception as e:
        state.log({"event": "coach_error", "where": "worker", "error": repr(e)[:300]})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
