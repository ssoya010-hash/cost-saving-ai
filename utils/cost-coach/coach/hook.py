#!/usr/bin/env python3
"""cost-coach hook: one entry point for Claude Code and Devin CLI hooks.

Contract (see DESIGN.md): prints NOTHING to stdout, never blocks, never rewrites, exits 0,
does only small O(1) work. Anything heavy (pricing the transcript) runs in a detached
background process (worker.py) started from the Stop hook.

Opt-in only (cost tokens or change behaviour): config "agent_hints" (one guidance line
for the agent), "mode": "block" (block bare "ok").
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from coach import config, expiry, notify, rules, state  # type: ignore
else:
    from . import config, expiry, notify, rules, state

SHELL_TOOLS = {"exec", "Bash", "bash", "shell", "run_command"}
READ_TOOLS = {"Read", "read", "read_file", "view"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "edit", "write", "apply_patch",
              "write_file", "str_replace", "create"}
_PATCH_FILE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", re.MULTILINE)


def _edited_paths(ti: dict) -> list:
    paths = [ti.get("file_path") or ti.get("path") or ti.get("notebook_path") or ""]
    patch = ti.get("patch") or ti.get("input") or ""
    if isinstance(patch, str):
        paths += _PATCH_FILE.findall(patch)
    return [p.strip() for p in paths if p]


def _first_delivery(payload: dict) -> bool:
    """Devin CLI also loads ~/.claude/settings.json, so the same event can reach two installed
    copies of this hook (user + repo level, Claude + Devin config). Only the first one acts."""
    key = json.dumps([payload.get("hook_event_name"), payload.get("session_id"), payload.get("prompt_id"),
                      payload.get("tool_use_id"), payload.get("tool_name"), payload.get("tool_input"),
                      payload.get("prompt"), (str(payload.get("tool_response")) or "")[:200]],
                     sort_keys=True, default=str, ensure_ascii=False)
    h = hashlib.sha1(key.encode()).hexdigest()[:20]
    d = os.path.join(config.HOME, "dedupe")
    try:
        os.makedirs(d, exist_ok=True)
        fd = os.open(os.path.join(d, h), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        try:
            if time.time() - os.path.getmtime(os.path.join(d, h)) < 1.5:   # duplicate installs fire within ms
                return False
            os.utime(os.path.join(d, h))   # same event again much later (e.g. same command re-run)
        except OSError:
            pass
        return True
    except OSError:
        return True
    if int(time.time()) % 20 == 0:        # cheap cleanup
        cutoff = time.time() - 60
        try:
            for n in os.listdir(d):
                fp = os.path.join(d, n)
                if os.path.getmtime(fp) < cutoff:
                    os.remove(fp)
        except OSError:
            pass
    return True


def _host(payload: dict) -> str:
    if os.environ.get("DEVIN_PROJECT_DIR") or payload.get("tool_name") in ("exec", "edit"):
        return "devin"
    if os.environ.get("CLAUDE_PROJECT_DIR") or "transcript_path" in payload:
        return "claude"
    return "unknown"


def _emit(cfg, st, sid, host, findings):
    for f in findings:
        sent = notify.maybe_send(cfg, st, sid, f, host)
        state.log({"event": "finding", "rule": f.rule, "billing_point": f.billing_point,
                   "session": sid, "host": host, "notified": sent})


def _hint_output(event, findings, cfg):
    """Only when the user opted in to agent_hints. Default: no output at all."""
    if not cfg.get("agent_hints"):
        return None
    ctx = "\n".join(f.agent_context for f in findings if f.agent_context)
    if not ctx:
        return None
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}


# ---------------------------------------------------------------- UserPromptSubmit
def on_prompt(p, cfg, st, sid, host):
    text = p.get("prompt") or ""
    now = time.time()
    st["prompts"] += 1
    findings = rules.check_prompt(text)

    if rules.is_correction(text):
        st["correction_streak"] += 1
        f = rules.correction_streak(st["correction_streak"], cfg["correction_streak"])
        if f:
            findings.append(f)
    else:
        st["correction_streak"] = 0

    cost = state.load_cost(sid)
    f = rules.cache_expired_resume(now - st.get("last_activity", now), cost, cfg)
    if f:
        tm = expiry.read_timer(sid)
        already = tm.get("notified") is not None and tm.get("notified") == tm.get("stop")
        if not already:   # the idle timer did not warn for this break, so warn now
            findings.append(f)
    st["last_activity"] = now
    st["turn_tools"] = 0
    state.log({"event": "prompt", "session": sid, "host": host, "len": len(text)})
    st["approx_ctx_chars"] = st.get("approx_ctx_chars", 0) + len(text)

    _emit(cfg, st, sid, host, findings)
    blocker = next((f for f in findings if f.block), None)
    if blocker and cfg.get("mode") == "block" and not text.lstrip().startswith("!"):
        state.log({"event": "blocked", "rule": blocker.rule, "session": sid, "host": host})
        return {"decision": "block", "reason": f"[cost-coach] {blocker.message} (prefix with '!' to send anyway)"}
    return _hint_output("UserPromptSubmit", findings, cfg)


# ---------------------------------------------------------------- PreToolUse
def on_pre_tool(p, cfg, st, sid, host):
    tool = p.get("tool_name") or ""
    ti = p.get("tool_input") or {}
    findings = []
    if tool in EDIT_TOOLS:
        for path in _edited_paths(ti):
            f = rules.config_edit(path)
            if f:
                findings.append(f)
                break
    _emit(cfg, st, sid, host, findings)
    return None


# ---------------------------------------------------------------- PostToolUse
def _output_chars(resp) -> int:
    if resp is None:
        return 0
    if isinstance(resp, str):
        return len(resp)
    if isinstance(resp, dict):
        return sum(len(str(resp.get(k) or "")) for k in ("output", "stdout", "stderr", "content", "error"))
    return len(json.dumps(resp, ensure_ascii=False))


def on_post_tool(p, cfg, st, sid, host):
    tool = p.get("tool_name") or "?"
    ti = p.get("tool_input") or {}
    st["turn_tools"] = st.get("turn_tools", 0) + 1
    chars = _output_chars(p.get("tool_response"))
    st["approx_ctx_chars"] = st.get("approx_ctx_chars", 0) + chars
    findings = [rules.tool_call_budget(st["turn_tools"], cfg["tool_call_warn_at"]),
                rules.large_output(chars, cfg["large_output_chars"], tool)]
    if tool in EDIT_TOOLS:   # re-reading a file after editing it is verification, not waste
        for path in _edited_paths(ti):
            st.setdefault("reads", {}).pop(path, None)
    if tool in READ_TOOLS:
        path = ti.get("file_path") or ti.get("path") or ""
        if path:
            n = st.setdefault("reads", {}).get(path, 0) + 1
            st["reads"][path] = n
            findings.append(rules.repeated_read(path, n, cfg["repeat_threshold"]))
    if tool in SHELL_TOOLS:
        cmd = (ti.get("command") or "").strip()[:200]
        if cmd:
            n = st.setdefault("commands", {}).get(cmd, 0) + 1
            st["commands"][cmd] = n
            findings.append(rules.retry_loop(cmd, n, cfg["repeat_threshold"]))
        # keep state small
        if len(st["commands"]) > 300:
            st["commands"] = dict(list(st["commands"].items())[-150:])
    if len(st.get("reads", {})) > 300:
        st["reads"] = dict(list(st["reads"].items())[-150:])
    findings = [f for f in findings if f]
    state.log({"event": "tool", "session": sid, "host": host, "tool": tool, "chars": chars,
               "turn_calls": st["turn_tools"]})
    _emit(cfg, st, sid, host, findings)
    return _hint_output("PostToolUse", findings, cfg)


# ---------------------------------------------------------------- Stop
def _spawn_worker(sid, transcript):
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.py")
    try:
        subprocess.Popen([sys.executable, "-I", worker, sid, transcript],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True,
                         env=dict(os.environ, COACH_HOME=config.HOME))
    except OSError:
        pass


def on_stop(p, cfg, st, sid, host):
    st["last_activity"] = time.time()
    state.log({"event": "turn_end", "session": sid, "host": host,
               "turn_calls": st.get("turn_tools", 0), "prompts": st["prompts"]})
    tp = p.get("transcript_path")
    if tp and os.path.exists(tp) and not os.environ.get("COACH_NO_WORKER"):
        _spawn_worker(sid, tp)
    if cfg.get("cache_expiry_notify", True) and not os.environ.get("COACH_NO_WORKER"):
        expiry.arm(sid, host)
    return None


HANDLERS = {"UserPromptSubmit": on_prompt, "PreToolUse": on_pre_tool,
            "PostToolUse": on_post_tool, "Stop": on_stop}


def handle(payload: dict):
    cfg = config.load()
    if not cfg.get("enabled", True):
        return None
    event = payload.get("hook_event_name") or (sys.argv[1] if len(sys.argv) > 1 else "")
    fn = HANDLERS.get(event)
    if not fn or not _first_delivery(payload):
        return None
    sid = payload.get("session_id") or "nosession"
    st = state.load(sid)
    out = fn(payload, cfg, st, sid, _host(payload))
    state.save(sid, st)
    return out


def main():
    try:
        payload = json.load(sys.stdin)
        out = handle(payload)
        if out:  # only with opt-in agent_hints / block mode
            sys.stdout.write(json.dumps(out, ensure_ascii=False))
    except Exception as e:  # never break the agent
        try:
            state.log({"event": "coach_error", "error": repr(e)[:300]})
        except Exception:
            pass
    sys.exit(0)


if __name__ == "__main__":
    main()
