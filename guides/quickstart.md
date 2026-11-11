---
title: Quickstart: save today
summary: The 6 habits that cut the bill, no install needed
read_time: 3 min
---
# Quickstart: save today

The Claude bill is mostly **writing new context into the prompt cache** (72% in our sessions) and
**output** (14%). Re-reading cached context is cheap (0.1×). These habits target what costs money.

| # | Habit | Why it saves |
|---|---|---|
| 1 | **New task → new session.** After a break longer than the cache lifetime (5 min by default on AWS), start fresh with a short summary. | An expired cache re-writes the whole context at 1.25–2×. |
| 2 | **Keep the prefix stable.** Don’t edit CLAUDE.md / AGENTS.md / MCP servers / model mid-session. | Any prefix change forces a full cache rebuild. |
| 3 | **One message, full intent.** No bare “ok”: include the next step, spec and done-criteria. | Every turn re-sends the context. |
| 4 | **Read less, once.** Name files and line ranges; ask for a script that aggregates logs. | New context is written once and re-read every call. |
| 5 | **Smallest change first.** Reuse before writing; still require tests for fixes and doc updates. | Output is 5× and is mostly code. |
| 6 | **Stop loops early.** After 2 corrections or 3 failed tries, restate the requirement or restart. | Loops multiply calls. |

Want reminders at exactly these moments? Install [cost-coach](../utils/cost-coach/).
Want the agent to follow rules 3–6 itself? Add [skills/cost-discipline](../skills/cost-discipline/).

Evidence: [experiments/2026-11-tool-ab-v2](../experiments/2026-11-tool-ab-v2/) · [design/billing-model.md](../design/billing-model.md)
