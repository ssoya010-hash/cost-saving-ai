---
title: cost-coach
summary: Mac alerts at costly moments, cache-expiry warnings, weekly retro (Fri 10:00), billed-cost measurement
status: active
---
# cost-coach

macOS notifications for **cost anti-patterns** in Claude Code and Devin CLI, plus one-command
measurement of real, cache-aware spend. Python 3 stdlib only, local files only.

**Zero side effects on the AI:** hooks print nothing (no tokens added to the context), never block,
never rewrite commands, exit 0 on any error, and do the heavy work in a detached background process.
Verified by tests and by `cost-coach doctor`.

Part of [cost-saving-ai](../../README.md). Pairs with the [cost-discipline skill](../../skills/cost-discipline/).

→ **[INSTALL_GUIDE.md](INSTALL_GUIDE.md)** for users · [DESIGN.md](DESIGN.md) for the anti-pattern catalog and architecture

```bash
./install.sh && cost-coach doctor && cost-coach test-notify
```

## Why these patterns

Claude on AWS bills per token: new context is written to the prompt cache at 1.25–2×, old context
is re-read at 0.1×, output is 5×. Devin CLI bills ACU per token (Opus 4.6: 0.4 ACU / 1M input tokens)
and also uses a prompt cache.
On both, cost grows with **turns × context size**, plus **cache rebuilds** and **output**. Each rule
targets one of those (see DESIGN.md).

## Commands

| Command | Purpose |
|---|---|
| `cost-coach status [--days 7]` | Spend, bill shares, cache hit, rebuilds with cause, Devin ACU, tips |
| `cost-coach sessions [--days 1]` | Most expensive sessions |
| `cost-coach mark "<change>"` / `compare` | Before/after median $/session (and ACU/session) |
| `cost-coach devin add <ACU>` / `devin import <csv>` | Log Devin ACU |
| `cost-coach weekly` | Weekly retrospective: this vs last week, cache-rebuild loss, top habits, 3 actions |
| `cost-coach schedule ["Fri 10:00"\|off]` | When the weekly retro arrives (default Friday 10:00, Mac local time) |
| `cost-coach habits` | Anti-pattern counts |
| `cost-coach doctor` / `test-notify` | Health check / test notification |
| `cost-coach pause` / `resume` / `mute <rule>` | Control notifications |
| `cost-coach post` / `notify` | Webhook summary / daily notification |

## Layout

```
coach/hook.py      hook entry point (fast, silent)
coach/rules.py     anti-pattern rules (pure functions)
coach/worker.py    background: incremental transcript pricing, receipts, rebuild detection
coach/expiry.py    background: one idle timer per session → "Cache expired" before you resume
coach/weekly.py    weekly retrospective report
coach/schedule.py  weekly retro schedule (launchd), default Fri 10:00
coach/measure.py   cost aggregation, before/after compare, Devin ACU log
coach/pricing.py   cache-aware Claude pricing
coach/notify.py    macOS notification + webhook, cooldown / hourly cap / quiet hours
coach/cli.py       `cost-coach` command
install.sh         installer (backup, idempotent, dry-run, uninstall)
templates/AGENTS.md  optional cost rules for a repo (opt-in: --rules)
tests/             python3 -m unittest discover -s tests
```
