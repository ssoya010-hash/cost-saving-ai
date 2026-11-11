"""Config + paths. Everything lives under ~/.cost-coach (override: COACH_HOME)."""
import json
import os

HOME = os.environ.get("COACH_HOME") or os.path.expanduser("~/.cost-coach")

DEFAULTS = {
    "enabled": True,
    # ---- side effects on the AI: all OFF by default (they cost tokens or change behaviour) ----
    "agent_hints": False,     # inject one guidance line into the agent context (costs tokens)
    "mode": "warn",           # "block" blocks bare "ok" prompts (prefix "!" to bypass)
    # ---- notifications ----
    "macos_notify": True,
    "sound": "Tink",          # "" for silent
    "notify_cooldown_s": 600, # same rule, same session
    "max_notifications_per_hour": 6,
    "quiet_hours": "",        # e.g. "22-08"
    "muted_rules": [],        # e.g. ["bundled_tasks"]
    "webhook_url": "",        # Slack-compatible; env COACH_WEBHOOK_URL overrides
    "webhook_findings": False,  # also send each finding (default: only `cost-coach post`)
    # ---- rule thresholds ----
    "tool_call_warn_at": 30,
    "large_output_chars": 20000,
    "correction_streak": 2,
    "repeat_threshold": 3,
    "cache_ttl_s": 300,              # Claude Code on AWS/Bedrock defaults to 5 min
    "devin_cache_ttl_s": 300,        # Devin: not documented; assumed 5 min (Anthropic default)
    "cache_expiry_notify": True,     # notify when an idle session's cache expires (before you resume)
    "resume_context_tokens": 50000,
    "large_context_tokens": 150000,
    "cache_bust_tokens": 30000,
    "session_notify_usd": [2, 5, 10],
    # ---- pricing ----
    "acu_price_usd": 0.40,           # Devin contract: $0.40 / ACU
    "devin_acu_per_mtok": 0.4,       # Devin Opus 4.6: 0.4 ACU per 1M tokens
    "unit_price_usd": 0.40,          # price of one avoidable turn in `habits` (one ACU)
    "price_multiplier": 1.0,         # AWS/Bedrock discount, e.g. 0.9
    "prices": {},                    # per-model override {"opus-4-6": {"in": 5, "out": 25, "read": 0.5}}
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(HOME, "config.json")) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    if os.environ.get("COACH_WEBHOOK_URL"):
        cfg["webhook_url"] = os.environ["COACH_WEBHOOK_URL"]
    if os.environ.get("COACH_MODE"):
        cfg["mode"] = os.environ["COACH_MODE"]
    if os.environ.get("COACH_NO_NOTIFY"):
        cfg["macos_notify"] = False
    return cfg
