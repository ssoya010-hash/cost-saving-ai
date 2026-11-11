"""Measure real, cache-aware Claude Code spend from local transcripts + Devin ACU logs.

Claude Code writes every API response (with its `usage` block) to
~/.claude/projects/<project>/<session>.jsonl. We price each *unique* response once
(streamed blocks repeat the same message id) and aggregate per session.

Devin has no local transcript; ACUs per session come from /session-stats, the Devin
usage page or the Enterprise API, logged with `cost-coach devin add` (or a CSV import).
"""
import csv
import glob
import json
import os
import statistics
import time
from datetime import datetime, timezone

if __package__ in (None, ""):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from coach import config, pricing  # type: ignore
else:
    from . import config, pricing


def _ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def transcript_files(root=None):
    root = root or os.path.expanduser("~/.claude/projects")
    return glob.glob(os.path.join(root, "*", "*.jsonl"))


def session_from_file(path, cfg=None, since=0.0, until=None):
    """Aggregate one transcript file. Returns None when it has no priced responses in range."""
    cfg = cfg or {}
    seen = set()
    s = {"session": os.path.basename(path)[:-6], "project": os.path.basename(os.path.dirname(path)),
         "start": None, "end": None, "usd": 0.0, "usd_no_cache": 0.0, "calls": 0, "user_prompts": 0,
         "parts": {"uncached_in": 0.0, "cache_write": 0.0, "cache_read": 0.0, "output": 0.0},
         "tokens": {"uncached_in": 0, "cache_write": 0, "cache_read": 0, "output": 0},
         "models": {}, "peak_context": 0, "cache_busts": 0, "cache_bust_usd": 0.0, "bust_causes": {},
         "_prev_ctx": 0, "_prev_t": None, "_ttl": 300}
    try:
        f = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with f:
        for line in f:
            if '"usage"' not in line and '"type":"user"' not in line and '"type": "user"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = _ts(d.get("timestamp"))
            if t is None or t < since or (until and t >= until):
                continue
            if d.get("type") == "user" and not d.get("isSidechain"):
                msg = d.get("message") or {}
                c = msg.get("content")
                if isinstance(c, str) or (isinstance(c, list) and any(
                        isinstance(b, dict) and b.get("type") == "text" for b in c)):
                    s["user_prompts"] += 1
                continue
            msg = d.get("message") or {}
            u = msg.get("usage")
            if d.get("type") != "assistant" or not u:
                continue
            key = msg.get("id") or d.get("requestId") or d.get("uuid")
            if key in seen:
                continue
            seen.add(key)
            model = msg.get("model") or "unknown"
            if model == "<synthetic>":
                continue
            c = pricing.cost(u, model, cfg)
            s["calls"] += 1
            s["usd"] += c["usd"]
            s["usd_no_cache"] += c["usd_no_cache"]
            for k in s["parts"]:
                s["parts"][k] += c["parts"][k]
                s["tokens"][k] += c["tokens"][k]
            s["models"][model] = s["models"].get(model, 0) + 1
            ctx = c["tokens"]["uncached_in"] + c["tokens"]["cache_write"] + c["tokens"]["cache_read"]
            # cache bust: the prefix cached by the previous call was NOT read back (re-written instead).
            # New content (a big file read) is not a bust; losing the old prefix is.
            lost = s["_prev_ctx"] - c["tokens"]["cache_read"]
            if (s["_prev_ctx"] and lost >= cfg.get("cache_bust_tokens", 30000)
                    and c["tokens"]["cache_write"] >= lost * 0.8):
                s["cache_busts"] += 1
                gap = t - (s["_prev_t"] or t)
                cause = "pause_over_ttl" if gap > s["_ttl"] - 10 else "prefix_changed"
                s["bust_causes"][cause] = s["bust_causes"].get(cause, 0) + 1
                cin = pricing.rates(model, cfg)[0]
                s["cache_bust_usd"] += lost * cin * 1.25 / 1e6 * float(cfg.get("price_multiplier", 1.0))
            if not d.get("isSidechain"):
                s["_prev_ctx"] = ctx
                s["_prev_t"] = t
                cc = u.get("cache_creation") or {}
                if cc.get("ephemeral_1h_input_tokens"):
                    s["_ttl"] = 3600
                elif cc.get("ephemeral_5m_input_tokens"):
                    s["_ttl"] = 300
            s["peak_context"] = max(s["peak_context"], ctx)
            s["start"] = t if s["start"] is None else min(s["start"], t)
            s["end"] = t if s["end"] is None else max(s["end"], t)
    for k in ("_prev_ctx", "_prev_t", "_ttl"):
        s.pop(k, None)
    return s if s["calls"] else None


def claude_sessions(since=0.0, until=None, root=None, cfg=None, project=None):
    cfg = cfg if cfg is not None else config.load()
    out = []
    for p in transcript_files(root):
        if project and project not in os.path.dirname(p):
            continue
        try:
            if os.path.getmtime(p) < since:
                continue
        except OSError:
            continue
        s = session_from_file(p, cfg, since, until)
        if s:
            out.append(s)
    return out


def summarize(sessions):
    if not sessions:
        return {"sessions": 0}
    usd = [s["usd"] for s in sessions]
    tot = {k: sum(s["tokens"][k] for s in sessions) for k in sessions[0]["tokens"]}
    parts = {k: sum(s["parts"][k] for s in sessions) for k in sessions[0]["parts"]}
    total = sum(usd)
    inp = tot["uncached_in"] + tot["cache_write"] + tot["cache_read"]
    return {
        "sessions": len(sessions),
        "total_usd": round(total, 4),
        "median_usd_per_session": round(statistics.median(usd), 4),
        "mean_usd_per_session": round(total / len(usd), 4),
        "usd_without_cache": round(sum(s["usd_no_cache"] for s in sessions), 4),
        "cache_hit_pct": round(100 * tot["cache_read"] / inp, 1) if inp else None,
        "share_pct": {k: round(100 * v / total, 1) if total else 0 for k, v in parts.items()},
        "prompts_per_session": round(statistics.mean(s["user_prompts"] for s in sessions), 2),
        "calls_per_session": round(statistics.mean(s["calls"] for s in sessions), 2),
        "median_peak_context": int(statistics.median(s["peak_context"] for s in sessions)),
        "tokens_total": tot,
        "token_share_pct": {k: round(100 * v / sum(tot.values()), 1) if sum(tot.values()) else 0
                            for k, v in tot.items()},
        "cache_busts": sum(s["cache_busts"] for s in sessions),
        "cache_bust_usd": round(sum(s["cache_bust_usd"] for s in sessions), 4),
        "bust_causes": {c: sum(s["bust_causes"].get(c, 0) for s in sessions)
                        for c in ("pause_over_ttl", "prefix_changed")},
    }


# ---------------- Devin ACU log ----------------
def _devin_path():
    return os.path.join(config.HOME, "devin_acu.jsonl")


def devin_add(acu, session="", note="", ts=None):
    os.makedirs(config.HOME, exist_ok=True)
    rec = {"ts": ts or time.time(), "acu": float(acu), "session": session, "note": note}
    with open(_devin_path(), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def devin_import_csv(path):
    """CSV with columns: date (ISO) or ts, acu, session (optional), note (optional)."""
    n = 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            ts = float(row["ts"]) if row.get("ts") else _ts(row.get("date"))
            if ts is None or not row.get("acu"):
                continue
            devin_add(row["acu"], row.get("session", ""), row.get("note", ""), ts)
            n += 1
    return n


def devin_sessions(since=0.0, until=None):
    out = []
    try:
        with open(_devin_path()) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r["ts"] >= since and (not until or r["ts"] < until):
                    out.append(r)
    except OSError:
        pass
    return out


def devin_summary(recs, acu_price):
    if not recs:
        return {"sessions": 0}
    acus = [r["acu"] for r in recs]
    return {"sessions": len(recs), "total_acu": round(sum(acus), 2),
            "total_usd": round(sum(acus) * acu_price, 2),
            "median_acu_per_session": round(statistics.median(acus), 2),
            "median_usd_per_session": round(statistics.median(acus) * acu_price, 2)}


# ---------------- marks: before/after comparison ----------------
def _marks_path():
    return os.path.join(config.HOME, "marks.jsonl")


def add_mark(label, ts=None):
    os.makedirs(config.HOME, exist_ok=True)
    rec = {"ts": ts or time.time(), "label": label}
    with open(_marks_path(), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def marks():
    try:
        with open(_marks_path()) as f:
            return [json.loads(x) for x in f if x.strip()]
    except (OSError, ValueError):
        return []


def compare(mark_ts, window_days=14, root=None, cfg=None, acu_price=0.40):
    """Sessions in the `window_days` before the mark vs. after it (up to now)."""
    cfg = cfg if cfg is not None else config.load()
    before_from = mark_ts - window_days * 86400
    b = claude_sessions(before_from, mark_ts, root, cfg)
    a = claude_sessions(mark_ts, None, root, cfg)
    sb, sa = summarize(b), summarize(a)
    res = {"claude": {"before": sb, "after": sa}}
    if sb.get("sessions") and sa.get("sessions"):
        res["claude"]["change_pct_median_usd_per_session"] = round(
            100 * (sa["median_usd_per_session"] / sb["median_usd_per_session"] - 1), 1) \
            if sb["median_usd_per_session"] else None
    db, da = devin_sessions(before_from, mark_ts), devin_sessions(mark_ts)
    dsb, dsa = devin_summary(db, acu_price), devin_summary(da, acu_price)
    res["devin"] = {"before": dsb, "after": dsa}
    if dsb.get("sessions") and dsa.get("sessions") and dsb["median_acu_per_session"]:
        res["devin"]["change_pct_median_acu_per_session"] = round(
            100 * (dsa["median_acu_per_session"] / dsb["median_acu_per_session"] - 1), 1)
    return res
