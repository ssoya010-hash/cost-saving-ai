"""Side-channel notifications: macOS Notification Center + optional Slack-compatible webhook.

Never raises and never blocks the hook: the notifier and the webhook run detached.
Rate limits: per-rule cooldown per session, global cap per hour, quiet hours.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from coach import config, state  # type: ignore
else:
    from . import config, state


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _mac(title: str, body: str, sound: str) -> bool:
    if platform.system() != "Darwin":
        return False
    tn = shutil.which("terminal-notifier")
    try:
        if tn:
            args = [tn, "-title", title, "-message", body, "-group", "cost-coach"]
            if sound:
                args += ["-sound", sound]
        elif shutil.which("osascript"):
            snd = f' sound name "{_esc(sound)}"' if sound else ""
            args = ["osascript", "-e", f'display notification "{_esc(body)}" with title "{_esc(title)}"{snd}']
        else:
            return False
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def _webhook(url: str, title: str, body: str, meta: dict) -> None:
    """Synchronous; only call from the CLI or the background worker, never from the hook."""
    payload = {"text": f"*{title}*\n{body}", "coach": meta}
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass


def _webhook_detached(url: str, title: str, body: str, meta: dict) -> None:
    code = ("import json,sys,urllib.request;d=json.loads(sys.argv[1]);"
            "r=urllib.request.Request(d['u'],data=json.dumps({'text':d['t'],'coach':d['m']}).encode(),"
            "headers={'Content-Type':'application/json'})\ntry: urllib.request.urlopen(r,timeout=3)\nexcept Exception: pass")
    arg = json.dumps({"u": url, "t": f"*{title}*\n{body}", "m": meta}, ensure_ascii=False)
    try:
        subprocess.Popen([sys.executable, "-I", "-c", code, arg], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def _quiet(cfg: dict) -> bool:
    q = cfg.get("quiet_hours")  # e.g. "22-08"
    if not q:
        return False
    try:
        a, b = (int(x) for x in q.split("-"))
    except ValueError:
        return False
    h = time.localtime().tm_hour
    return (a <= h < b) if a < b else (h >= a or h < b)


def send(cfg: dict, title: str, body: str, meta: dict, detached_webhook: bool = True) -> list:
    sent = []
    if os.environ.get("COACH_NO_NOTIFY"):
        return sent
    if cfg.get("macos_notify", True) and _mac(title, body, cfg.get("sound", "Tink")):
        sent.append("macos")
    if cfg.get("webhook_url") and cfg.get("webhook_findings", False):
        (_webhook_detached if detached_webhook else _webhook)(cfg["webhook_url"], title, body, meta)
        sent.append("webhook")
    return sent


def _hour_count_path():
    return os.path.join(config.HOME, "notify_rate.json")


def _allow_global(cfg: dict) -> bool:
    cap = int(cfg.get("max_notifications_per_hour", 6))
    now = time.time()
    p = _hour_count_path()
    try:
        with open(p) as f:
            ts = [t for t in json.load(f) if now - t < 3600]
    except (OSError, ValueError):
        ts = []
    if len(ts) >= cap:
        return False
    ts.append(now)
    try:
        os.makedirs(config.HOME, exist_ok=True)
        with open(p, "w") as f:
            json.dump(ts, f)
    except OSError:
        pass
    return True


def maybe_send(cfg: dict, st: dict, sid: str, finding, host: str) -> list:
    """Cooldown per rule per session + global hourly cap + quiet hours + per-rule mute."""
    if finding.rule in (cfg.get("muted_rules") or []):
        return []
    now = time.time()
    last = st.setdefault("last_notify", {}).get(finding.rule, 0)
    if now - last < cfg.get("notify_cooldown_s", 600) or _quiet(cfg) or not _allow_global(cfg):
        return []
    st["last_notify"][finding.rule] = now
    title = f"Cost Coach · {RULE_TITLES.get(finding.rule, finding.rule)}"
    return send(cfg, title, finding.message, {"rule": finding.rule, "session": sid, "host": host})


RULE_TITLES = {
    "empty_prompt": "Empty follow-up",
    "correction_loop": "Correction loop",
    "bundled_tasks": "Too many tasks",
    "vague_large_task": "Plan first",
    "cache_expired_resume": "Resumed after cache expiry",
    "cache_expired": "Cache expired",
    "config_edit_midsession": "Config edit mid-session",
    "long_turn": "Long turn",
    "large_tool_output": "Large output",
    "repeated_read": "Repeated read",
    "retry_loop": "Retry loop",
    "session_cost": "Session receipt",
    "cache_rebuild": "Cache rebuilt",
    "large_context": "Large context",
}
