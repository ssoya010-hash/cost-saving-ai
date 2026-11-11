---
title: Billing anatomy: Devin and Claude
summary: How each product bills and which levers move it
---
# 01. Billing Anatomy — where charges occur in Devin and Claude

> Sources: docs.devin.ai (llms-full.txt, 2026-11-10 snapshot), the Claude API pricing docs. Each entry links its source as [D-x] / [C-x].

## TL;DR
**"The billing unit decides the strategy."**
Devin is not a single model — **its billing unit depends on the model and plan you choose.**

| Where you use it | Billing unit | What drives cost up | Effective levers |
|---|---|---|---|
| Devin CLI/Desktop — **per-message model** | message × model multiplier (credits) | number of messages, **turn continuations** | Fewer empty prompts, corrections and splits (**prompt hygiene**) |
| Devin CLI/Desktop — **per-token model** (Adaptive, etc.) | input, output and cache tokens | context size × number of turns | rtk, codegraph, smaller outputs, shorter sessions |
| Devin Enterprise (ACU) | ACU = actions and complexity + context + VM time | action count, context, conversation length, back-and-forth frequency | **Both** of the above |
| Claude Code (API/Team) | tokens (input / output / cache write / cache read) | context × turns, cache misses | rtk, codegraph, headroom, caching |

## 0. Our company's setup (confirmed 2026-11-10)

| Product | Purchase path | Billing unit | What saves money |
|---|---|---|---|
| Devin CLI/Desktop | Windsurf account (legacy credit plan) | **Prompt credits per message** × model multiplier. "It doesn't matter how many actions the agent takes… you only pay the initial prompt." Failed messages are free. Credits are allocated per seat, reset monthly; add-ons $120 / 1,000 pooled credits | Fewer messages, continuations and subagents (prompt hygiene). rtk/headroom do **not** change the credit count directly |
| Claude | AWS Marketplace committed purchase (private offer) | API usage is per token, billed in CCUs (100 CCU = $1 after the negotiated discount) and drawn down from the commitment | Fewer tokens → slower burn → **smaller commitment at renewal, no overage**. Not visible as an immediate cash cut |

Sources: docs.devin.ai/desktop/accounts/usage ("Legacy enterprise (credits)" tab); Claude Platform on AWS (AWS Marketplace listing, CloudYali FinOps write-up).
Open item: confirm in the private offer whether the Claude commitment covers API usage (tokens) or seats (Claude Team/Enterprise). With seats, token savings only matter for usage limits and extra usage.

## 1. Devin billing mechanics (from the official docs)

| # | Fact | Source |
|---|---|---|
| D-1 | Enterprise is billed in **ACUs**; self-serve uses quota plus on-demand credits. The metering mechanics are the same | admin/billing |
| D-2 | What usage depends on: "**number and complexity of actions** (planning, context gathering, execution, browser...)" plus VM time ("typically a small fraction") | admin/billing/usage |
| D-3 | Cost drivers: task complexity, **prompt specificity**, **context/codebase size**, files touched, session runtime, **conversation length**, **back-and-forth frequency** | admin/billing/usage |
| D-4 | No charge while waiting for a user reply, test runs or repo cloning. Sleep after 5 minutes idle, which is also unbilled | admin/billing/usage |
| D-5 | Model `pricing_dimensions`: `input`/`output`/`cache_read`/`cache_write` (per token) **or** `message` (**per-message**). Fusion bills the sidekick separately | Models API reference |
| D-6 | The model picker shows a credit multiplier such as "`1.25 credits / message`" | CLI changelog |
| D-7 | **Adaptive (ACU)**: "ACU consumption **scales with the tokens used** and the model selected" | cli/adaptive |
| D-8 | `/session-stats` shows credits, ACUs, **agent messages**, **turn continuations** and tokens. The `Model` row names the model that actually served the billed turns | cli/reference/commands |
| D-9 | Hitting the per-prompt tool-call limit triggers a **continue, which costs another prompt credit** (Cascade) | windsurf cascade docs |
| D-10 | Fast mode = **4x ACU** per session | changelog |
| D-11 | Session Insights: "**Many User Messages with Low ACU Usage**" = frequent interruptions and corrections, an anti-pattern the platform itself flags | product-guides/session-insights |
| D-12 | Devin Coach (enterprise): plan-first, unrelated follow-up, parallelizable, heavyweight-mode warnings | enterprise/features/devin-coach |
| D-13 | Hooks: `.devin/hooks.v1.json`; it also reads `.claude/settings.json` **as is**. PreToolUse `updatedInput` can rewrite commands (the official example is `rtk git status`) | cli/extensibility/hooks |

### Reinterpreting the earlier analysis (screenshot)
- "tool results produced 0 charges across 69,926 requests" + "Z=0.16 (p=0.87)" → **correct under a per-message model.** If a tool loop doesn't create a message, it isn't billed.
- But this **does not hold** for per-token, Adaptive or ACU models, or for Claude Code (D-5, D-7).
- The **indirect path** also exists under per-message billing: longer tool loops → **turn continuations** (D-8, D-9) → more billed units.
- So the conclusion changes from "tools don't work" to **"what works depends on the billing unit."**

## 2. Claude billing mechanics (API; Claude Code is the same)

| Item | Multiplier | Implication |
|---|---|---|
| Input | 1x (Opus 5.5 $4/MTok, Sonnet 5.5 $2/MTok) | **The whole context is re-sent every turn**, so cost ∝ turns × context |
| Output | 5x input | Long summaries and explanations cost more |
| Cache write | 1.25x (5m TTL) / 2x (1h TTL) | A paused session past TTL means a **cache miss** and the whole thing is billed again |
| Cache read | 0.05x (Opus 5.5, Sonnet 5.5) to 0.1x | Keeping the prefix stable is the biggest lever |
| Fast mode | 2x (Opus 5.5) | Use it only when you need it |

→ For Claude Code, **context size × turn count** is the cost, so rtk, codegraph and headroom reduce it directly.
For the same reason, a long session (40 turns) costs roughly ∝ turns² (the whole history is re-sent each turn).

## 3. Billing points → levers map

```
User message ──► [MSG] 1 billed unit per message (per-message models)
   │
   ├─ Agent turn: tool call ×N ──► [CONT] limit exceeded → turn continuation billed again
   │      └─ tool output ──► [CTX] stays in context → re-sent every turn after (token/ACU)
   └─ Subagent / child session ──► [MSG+CTX] separate context, billed separately
```

| Billing point | Anti-pattern | Counter-pattern | Tool |
|---|---|---|---|
| MSG | "ok", "ㅇㅇ", "continue" | Put the next instruction in the same message; delegate everything up to completion at once | devin-cost-coach (UserPromptSubmit) |
| MSG | Back-and-forth corrections | Specify the spec, constraints and done criteria **up front**; after 2 corrections, start a new session | coach correction_loop |
| MSG+CONT | Vague large request | `/plan` first, then run | coach vague_large, Devin Coach |
| CTX+CONT | Several tasks in one session | Split into separate sessions / child sessions | coach bundled_tasks |
| CONT | Exploration loops (30+ tool calls) | Narrow-scope exploration with codegraph; abort after 3 failures | coach long_turn, AGENTS.md |
| CTX | Huge outputs (logs, diffs, cat) | Compress with rtk; `--stat`, `head` | rtk hook (PreToolUse) |
| CTX | Too many subagents | Spawn only when ≥3 files and independent | AGENTS.md |
| ×4 | Habitual fast mode | Default off | Policy |
