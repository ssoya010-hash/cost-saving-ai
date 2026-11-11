---
title: Devin cost guide
summary: What lowers ACU on Devin cloud and Devin CLI
read_time: 3 min
---
# Devin cost guide

- **Contract:** $0.40 per ACU, Opus 4.6. Devin CLI: tokens → ACU at per-token rates (0.4 ACU per 1M input tokens), with separate cache read/write prices.
- **Devin cloud** ACU mixes tokens, compute and VM time, so token tools move only part of it.
- **What reaches Devin cloud:** AGENTS.md (≤ 16 KiB), skills, MCP, plugins. No API proxy, no TokenEconomizer.

| Lever | Effect |
|---|---|
| Fast mode off by default | fast = 4× ACU |
| Fewer back-and-forth messages | listed by Devin as a cost driver |
| [cost-discipline rules](../skills/cost-discipline/) in AGENTS.md | fewer actions, less context |
| Prompt precheck (Devin Coach), sleep timeout, ACU budgets | admin settings |
| codegraph MCP | large repos only |

Expected saving: ≈ −8% cloud, ≈ −10% CLI (projection). Source: [research/billing-anatomy.md](../research/billing-anatomy.md)
