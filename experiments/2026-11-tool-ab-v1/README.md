---
title: Tool A/B v1 (cache-aware billed cost)
summary: Do rtk, codegraph, headroom, caveman lower billed cost on short tasks and long RCA sessions?
status: done
date: 2026-11-10
result: No tool lowered billed cost; headroom token mode +61% (cache rebuilds)
owners: FCS
---
# Tool A/B v1

72 graded Claude Code sessions (Sonnet 5.5): 60 short-task runs and 12 long RCA sessions.

| Doc | What |
|---|---|
| [02-tool-verification.md](02-tool-verification.md) | Output-size micro-benchmarks (per command) |
| [03-agent-ab-with-cache.md](03-agent-ab-with-cache.md) | 60 short-task runs, 4 arms |
| [04-long-context-ab.md](04-long-context-ab.md) | 12 long RCA sessions, 6 arms incl. headroom modes and caveman |

Superseded for current tool versions by [2026-11-tool-ab-v2](../2026-11-tool-ab-v2/).
