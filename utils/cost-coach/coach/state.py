"""Tiny per-session state + JSONL event log (stdlib only, crash-safe enough for hooks)."""
import json
import os
import time

if __package__ in (None, ""):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from coach import config  # type: ignore
else:
    from . import config

MAX_LOG_BYTES = 5 * 1024 * 1024


def _path(*parts):
    p = os.path.join(config.HOME, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _safe(sid: str) -> str:
    return "".join(c for c in (sid or "nosession") if c.isalnum() or c in "-_")[:80]


def _read_json(p, default):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(p, obj):
    tmp = f"{p}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, p)


def load(session_id: str) -> dict:
    st = _read_json(_path("sessions", _safe(session_id) + ".json"), {})
    st.setdefault("prompts", 0)
    st.setdefault("correction_streak", 0)
    st.setdefault("last_notify", {})
    return st


def save(session_id: str, st: dict) -> None:
    _write_json(_path("sessions", _safe(session_id) + ".json"), st)


def load_cost(session_id: str) -> dict:
    """Written by the background worker: running session cost + incremental-parse offset."""
    return _read_json(_path("sessions", _safe(session_id) + ".cost.json"), {})


def save_cost(session_id: str, c: dict) -> None:
    _write_json(_path("sessions", _safe(session_id) + ".cost.json"), c)


def log(event: dict) -> None:
    p = _path("events.jsonl")
    try:
        if os.path.getsize(p) > MAX_LOG_BYTES:
            os.replace(p, p + ".1")
    except OSError:
        pass
    event = dict(event, ts=round(time.time(), 3))
    with open(p, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_events(since_ts: float = 0):
    for name in ("events.jsonl.1", "events.jsonl"):
        try:
            with open(_path(name)) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("ts", 0) >= since_ts:
                        yield e
        except OSError:
            continue


def prune(days: float = 14) -> int:
    """Delete session state files untouched for `days`."""
    d = _path("sessions", "x")[:-2]
    cutoff = time.time() - days * 86400
    n = 0
    try:
        for name in os.listdir(d):
            fp = os.path.join(d, name)
            if os.path.getmtime(fp) < cutoff:
                os.remove(fp)
                n += 1
    except OSError:
        pass
    return n
