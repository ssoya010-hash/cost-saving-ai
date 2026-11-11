#!/usr/bin/env python3
"""Cache-expiry timer. Started (detached) by the Stop hook; at most ONE per session.

While a session is idle, the provider's prompt cache expires after its TTL (Claude Code on AWS:
5 min default; Devin: not documented, assumed 5 min). The next message then re-writes the whole
context at cache-write price. This timer notifies at that moment, BEFORE the user resumes, so they
can choose: continue (same task) or start a new session with a short summary (new task).

usage: expiry.py <session_id> <host>
State: sessions/<id>.timer.json  {"stop": <ts of latest Stop>, "pid": <timer pid>, "notified": <stop ts>}
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


def timer_path(sid):
    return state._path("sessions", state._safe(sid) + ".timer.json")


def read_timer(sid):
    return state._read_json(timer_path(sid), {})


def write_timer(sid, t):
    state._write_json(timer_path(sid), t)


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def context_estimate(sid, host, cfg):
    """(tokens, ttl_s, rebuild_usd or None, unit_text)."""
    if host == "claude":
        c = state.load_cost(sid)
        ctx = c.get("last_context", 0)
        ttl = c.get("ttl", cfg.get("cache_ttl_s", 300))
        rin = pricing.rates(c.get("model", ""), cfg)[0]
        mult = 2.0 if ttl >= 3600 else 1.25
        usd = ctx * rin * mult / 1e6 * float(cfg.get("price_multiplier", 1.0))
        return ctx, ttl, usd, f"≈ ${usd:.2f}"
    st = state.load(sid)                      # Devin CLI: no local transcript, estimate from hook data
    ctx = int(st.get("approx_ctx_chars", 0) / 4)
    ttl = cfg.get("devin_cache_ttl_s", 300)
    acu = ctx / 1e6 * cfg.get("devin_acu_per_mtok", 0.4)
    return ctx, ttl, None, f"≈ {acu:.2f} ACU (estimate)"


def run(sid, host, cfg, sleep=time.sleep, now=time.time):
    """Loop until the latest idle period passes the TTL, then notify once (or exit if resumed)."""
    while True:
        t = read_timer(sid)
        stop = t.get("stop", 0)
        _, ttl, _, _ = context_estimate(sid, host, cfg)
        due = stop + ttl + 15
        if now() < due:
            sleep(min(due - now(), 3600))
            continue
        st = state.load(sid)
        if st.get("last_activity", 0) > stop + 1:   # user resumed before expiry
            return None
        if read_timer(sid).get("stop", 0) != stop:  # a newer turn ended meanwhile
            continue
        if t.get("notified") == stop:
            return None
        ctx, ttl, usd, cost_txt = context_estimate(sid, host, cfg)
        if ctx < cfg.get("resume_context_tokens", 50000):
            return None
        t["notified"] = stop
        write_timer(sid, t)
        msg = (f"Idle {ttl // 60}+ min: the cached context ({ctx // 1000}K tokens) has expired. "
               f"Your next message re-writes it ({cost_txt}). Same task: continue. "
               f"New task: start a new session with a short summary.")
        f = type("F", (), {"rule": "cache_expired", "message": msg})()
        sent = notify.maybe_send(cfg, {"last_notify": {}}, sid, f, host)
        state.log({"event": "finding", "rule": "cache_expired", "session": sid, "host": host,
                   "notified": sent, "context": ctx, "rebuild_usd": round(usd, 4) if usd else None})
        return msg


def main(argv):
    if len(argv) < 3:
        return 0
    sid, host = argv[1], argv[2]
    cfg = config.load()
    t = read_timer(sid)
    t["pid"] = os.getpid()
    write_timer(sid, t)
    try:
        run(sid, host, cfg)
    except Exception as e:
        state.log({"event": "coach_error", "where": "expiry", "error": repr(e)[:300]})
    finally:
        t = read_timer(sid)
        if t.get("pid") == os.getpid():
            t.pop("pid", None)
            write_timer(sid, t)
    return 0


def arm(sid, host):
    """Called from the Stop hook: record the stop time; start a timer only if none is running."""
    import subprocess
    t = read_timer(sid)
    t["stop"] = time.time()
    write_timer(sid, t)
    if _alive(t.get("pid")):
        return False
    try:
        subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), sid, host],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True, env=dict(os.environ, COACH_HOME=config.HOME))
        return True
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(main(sys.argv))
