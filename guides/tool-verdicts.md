---
title: Tool verdicts
summary: Which cost tools to use, pilot or avoid, in one table
read_time: 3 min
---
# Tool verdicts

Billed-cost change, pessimistic → optimistic. Details per tool in [playground/](../playground/).

| Tool | Acts on | Verdict | Billed-cost evidence |
|---|---|---|---|
| TokenEconomizer | ② agent turn | 🟢 **Pilot first** (Claude Code only) | −18 to −31% (authors’ paper, 579 tasks) |
| Ponytail principle | ⑤ output | 🟢 **Use as a rule** ([skill](../skills/cost-discipline/)) | −10.3% (JetBrains, p=0.004); ours n=1 inconclusive |
| codegraph | ③ tool calls | 🟡 **Large repos only** | −16% on large repos; ours +5/+28/+7% on a small repo |
| rtk | ③ tool output | 🔴 **Not a cost tool** | ours −5 to +9%; JetBrains +7.6%; Pass@1 −1–2 pt (Quesma) |
| headroom | ④ model + cache | 🔴 **Avoid for coding agents** | cache mode ±2%, token mode +61% (ours); sees API keys |
| caveman | ⑤ output | 🔴 **Costs more on long work** | ours +46 / −1 / +63% |
| context-mode | ③ tool output | ⚪ **Unproven** | no billed-cost data |

Loop steps: ① prompt · ② agent turn · ③ tool calls · ④ model + cache · ⑤ output.

**Security policy:** no proxy in front of company code · telemetry off · official repos at pinned versions.
Sources: [research/tool-survey.md](../research/tool-survey.md) · [experiments/2026-11-tool-ab-v2](../experiments/2026-11-tool-ab-v2/)
