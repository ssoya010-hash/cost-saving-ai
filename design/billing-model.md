---
title: Billing model
summary: What the AI bill is made of and which atoms each lever moves
---
# Billing model

**Claude (AWS, per token):**
`$ = Σ calls × (uncached in × p + cache write × p × 1.25|2 + cache read × p × 0.1 + output × p × 5)`

**Devin CLI (ACU):** tokens → ACU at per-token rates (Opus 4.6: 0.4 ACU / 1M input tokens), separate cache prices.
**Devin cloud (ACU):** mix of tokens, compute and VM time.

| Atom | Share of our Claude bill | Moved by |
|---|---|---|
| Calls (turns × tool calls) | multiplies everything | fewer turns, loop guards, full-intent prompts |
| New context (cache write) | **72%** incl. rebuilds | read narrowly, aggregate logs, shorter sessions |
| Cache rebuilds | ~29% of spend in one measured week | stable prefix, new session after cache expiry |
| Output | 14% | smallest change, less prose |
| Cache read | 14% | shorter sessions |

**Consequence:** tools that shrink already-cached input barely move the bill; tools that rewrite history
can raise it. Levers must change what the agent does.
