---
title: Tool analysis for Claude (AWS) and Devin (ACU)
summary: First principles, five whys, per-tool pros/cons/security/fit, savings ranges
---
# AI Cost Saving — Tool Analysis for Claude (AWS) and Devin (ACU)

> **Update 2026-11-11:** our own re-test with the latest tool versions (54 graded sessions) supersedes the "our measurement" figures below. See [../experiments/2026-11-tool-ab-v2/analysis.md](../experiments/2026-11-tool-ab-v2/analysis.md) and [../experiments/](../experiments/).


> As of 2026-11-11. Companion to `report.md` (popularity, reviews) and the deck.
> Every number has a source; numbers we measured ourselves are marked **[ours]**; estimates are marked **[est]**.

## 0. Our billing context

| | Claude Code | Devin |
|---|---|---|
| Purchase | AWS, usage-based, end-to-end per token (assumed Amazon Bedrock; confirm the exact AWS offering) | Windsurf/Devin enterprise contract, **$0.40 per ACU**, Opus 4.6, locked until 2027 |
| Meter | Tokens by type: uncached input, cache write (1.25× 5-min / 2× 1-h), cache read (0.1×), output (5×) | **ACU**. Cloud sessions: "a mix of tokens, compute, VMs". Local agents (Devin CLI, Devin Local, Cascade) on ACU: "tokens consumed … converted into ACUs at the per-token rates" |
| Model price | Opus 4.6 $5 / $25 per MTok, cache read $0.50; Sonnet 4.6 $3 / $15 (list; Bedrock rates may differ) | **Opus 4.6 = 0.4 ACU per 1M tokens** as shown in Devin (= $0.16/MTok at $0.40/ACU). Whether input, cache read, cache write and output share this rate is not yet confirmed |
| Where tools run | On the developer's Mac → hooks, skills, MCP, proxies all possible | Cloud: in Devin's VM via environment snapshot + **plugins** (skills, hooks best-effort, MCP). No API proxy possible. CLI: local hooks (`.devin/hooks.v1.json`, also reads `.claude/settings.json`) |
| Cache TTL | **5 minutes by default on cloud providers** (Claude Code docs); 1 h via `CLAUDE_CODE_PROMPT_CACHE_TTL=1h` (v2.1.242+) | Managed by Cognition; not configurable |
| Measurement | Local transcripts `~/.claude/projects/*/*.jsonl` (usage per call) → `cost-coach` | `/session-stats`, Session Insights, `GET /v3/enterprise/consumption/daily/sessions/{id}` |

Confirmed: our Devin CLI users are on the **ACU plan, not Legacy Windsurf Auth**, so Devin CLI usage converts tokens to ACU linearly and the Claude Code levers apply to it.

Caveat: with a prepaid commitment (AWS or Devin), savings show up as **slower burn / smaller renewal / no overage**, not as an immediate invoice cut.

---

## 1. Method

### 1.1 First principles — what is the bill, physically?

```
Claude $  = Σ_calls [ uncached_in·p + cache_write·p·(1.25|2) + cache_read·p·0.1 + output·p·5 ]
            calls  = turns × tool-calls-per-turn
            context per call = everything before it (system + tools + history + tool results)

Devin ACU (cloud) = f(tokens, actions, VM time)          ← mix, no public formula
Devin ACU (CLI, ACU plan) = Σ tokens_by_type × per-token ACU rate   ← linear in tokens
```

From this, only four things can lower a bill:
1. **Fewer calls** (fewer turns, fewer tool calls, fewer retries).
2. **Less new context per call** (each new file/log/tool result is written into the cache once, at 1.25–2×).
3. **Fewer cache rebuilds** (a lost prefix is re-written in full at 1.25–2× instead of read at 0.1×).
4. **Less output** (reasoning + code + prose, at 5×).

Shrinking *old* context barely matters: it is already read at 0.1×. Changing old context is harmful: it forces a rebuild (point 3).

### 1.2 Atomic decomposition — which atom does each tool touch?

Measured share of our bill **[ours]** (90 Claude Code sessions on one Mac, last 3 days, `cost-coach status`):

| Bill atom | Share | Price | What moves it |
|---|---|---|---|
| Cache write (new context + rebuilds) | **72%** | 1.25–2× | read less, fewer rebuilds, shorter sessions |
| Output (reasoning, code, prose) | 14% | 5× | less code, fewer turns, less prose |
| Cache read (old context) | 14% | 0.1× | shorter sessions |
| Uncached input | 0% | 1× | — |

Also measured: 52 cache rebuilds re-wrote ≈ $36 of $124 (≈ 29% of spend; includes benchmark runs).
Codepointer's 500 real sessions (614M tokens) show the same shape: cache_create 42% + output 29%.

| Tool | Atom it targets | Atom it actually moves on a cached agent |
|---|---|---|
| rtk | tool-output size (new context) | Small share: only Bash output (22% of tool output); Read/Grep untouched |
| headroom | old + new context size | Old context = 0.1× atom; rewriting it **adds** rebuilds (+61% [ours]) |
| caveman | prose output | Prose ≈ ⅓ of output; reasoning + code untouched |
| Ponytail | code output + turns | Code output, files touched, follow-up turns |
| codegraph / serena | number of reads/calls | Fewer exploration calls; adds fixed tool-schema tokens |
| TokenEconomizer | failure loops, unused tools, repeated discovery | Calls, schema tokens, retries |
| cost-coach (ours) | rebuilds, session length, empty turns | Cache rebuilds, turns |

### 1.3 Five Whys — why did "60–90% fewer tokens" not lower the bill?

1. **Why didn't the bill drop?** Because the tokens removed were mostly cheap tokens.
2. **Why were they cheap?** Because 89% of input is served from the prompt cache at 0.1× [ours].
3. **Why does compression sometimes raise the bill?** Because changing earlier messages invalidates the cached prefix, and the whole prefix is re-written at 1.25–2× (headroom token mode: 4 rebuilds, +61% [ours]).
4. **Why don't output-style tools help much?** Because two-thirds of output tokens are reasoning and code, which a style prompt cannot shorten (caveman +16% [ours], −8.5% output in JetBrains' 86 tasks).
5. **Root cause:** the tools optimise *token count per payload*; the bill is driven by *calls × new context × rebuilds + output*. Levers must change agent **behaviour** (fewer calls, less new context, fewer rebuilds, less code), not compress text.

---

## 2. How each tool saves — concept flows

```
               ┌──────────── what the agent writes ───────────┐
User prompt ─► Agent ──(tool call)──► Tool ──(result)──► Agent ──(API request)──► Model
   ▲   │          ▲                     ▲                   ▲            ▲
   │   │          │ skill / AGENTS.md   │ hook rewrites      │ MCP tool   │ proxy rewrites
   │   │          │ (Ponytail,          │ command (rtk)      │ (codegraph,│ request body
   │   │          │  caveman, rules)    │                    │  serena)   │ (headroom, caveman proxy)
   │   └─ controller watches the whole session (TokenEconomizer: skills, tool pruning, loop guard)
   └──── coach hooks: prompt checks, session receipts, cache-rebuild alerts (cost-coach)
```

| Insertion point | Tools | Works in Claude Code (AWS) | Works in Devin cloud | Works in Devin CLI |
|---|---|---|---|---|
| Skill / rules file | Ponytail, caveman, claude-token-efficient, AGENTS.md | ✅ | ✅ (skills via `.agents/skills`, `.claude/skills`, AGENTS.md ≤16 KiB, plugins) | ✅ |
| PreToolUse hook | rtk, cost-coach | ✅ | ⚠ via plugins, best-effort; `updatedInput` in cloud not documented | ✅ (`.devin/hooks.v1.json`, official rtk example) |
| MCP server | codegraph, serena, codebase-memory, context-mode, headroom MCP | ✅ | ✅ (MCP marketplace / custom) | ✅ |
| API proxy | headroom proxy, caveman proxy, rtk-proxy | ✅ (`ANTHROPIC_BEDROCK_BASE_URL`-style routing needed for Bedrock; verify) | ❌ (model calls go through Cognition's backend) | ❌ |
| Session controller plugin | TokenEconomizer | ✅ (Claude Code plugin; judge runs `claude -p`) | ❌ not supported (needs `claude` CLI + Claude settings files) | ⚠ unverified (Devin installs Claude plugins as-is, but judge needs `claude`) |
| Local measurement | ccusage, codeburn, cost-coach | ✅ | ❌ (use Devin consumption API / Session Insights) | ⚠ cost-coach logs ACU you enter or import |

---

## 3. Tool-by-tool analysis

Format per tool: concept · pros · cons · security · quality/performance · considerations · Claude/Devin fit · savings range (pessimistic → optimistic, billed cost).

### 3.1 TokenEconomizer (microsoft/TokenEconomizer) — session controller
- **Concept:** an external controller that learns from past sessions in the same repo. ① injects repo "micro-skills" (build/test commands, file locations), ② prunes tools never used in this repo (deny rules), ③ detects failure loops and redirects. No proxy, no prompt rewriting.
- **Pros:** the only tool measured on **cache-aware billed cost with Pass@1** across 579 tasks; cheaper in 30/30 repo-settings (−5.2% to −40.1%); Pass@1 up in 4 of 5 settings (Claude Code Sonnet 5: 74.7 → 76.0 at −23.6%). Plays well with caching (doesn't rewrite history).
- **Cons:** authors' own paper, one month old, not independently replicated. Savings build over repeated sessions in the **same repo**; first ~5 tasks can cost more. Few users yet.
- **Security:** Apache-2.0; no telemetry found; never handles credentials; its own LLM calls run through your `claude -p` (Haiku by default) and send command shapes only (80–120 chars). Writes `~/.tokeneconomizer`, hooks, and deny rules into `.claude/settings.local.json` (git-excluded; `toolprune restore` undoes).
- **Quality/perf:** Pass@1 table in the paper; plugin overhead is counted in its cost figures.
- **Fit:** Claude Code ✅. Devin cloud ❌. Devin CLI ⚠ unverified.
- **Savings [est]:** Claude **0% → −24%**. Devin **0%** (not available).

### 3.2 Ponytail (DietrichGebert/ponytail) — "smallest change" skill, 188K★
- **Concept:** a skill that pushes the agent to the least code: reuse first, no speculative features.
- **Pros:** JetBrains 80 paired tasks: **−10.3% cost, p=0.004**. Own benchmark (Opus 5.5, 585 sessions): lines −53%, cost −26%, hidden checks 96.7% vs 95.6%.
- **Cons:** independent PR-level review (narration-studio #3032): **27 vs 17 missed items** (docs, regression tests); its "trivial changes need no test" rule skips tests on bug/CI fixes. Its tests caught fewer injected bugs (69% vs 77%). A 7-word YAGNI prompt matched it on the original benchmark.
- **Security:** MIT. A **trojanized clone** shipped Windows malware via a plugin marketplace (issue #735) → install only from `DietrichGebert/ponytail`. Its hook asks the agent to edit `~/.claude/settings.json`.
- **Fit:** Claude Code ✅. Devin cloud ✅ as a skill or as text in AGENTS.md. Devin CLI ✅.
- **Recommendation:** adopt the **principle** (smallest change ladder) as an AGENTS.md rule with an explicit "tests + docs still required" clause (our `cost-coach` template does this); pilot the plugin only on feature work.
- **Savings [est]:** Claude **0% → −10%**. Devin **0% → −8%** (ACU includes non-token parts).

### 3.3 codegraph (colbymchenry/codegraph), serena, codebase-memory-mcp, graphify — code graph / symbol search
- **Concept:** index the repo once; answer "where is X / who calls Y" with one query instead of grep → read → read.
- **Pros:** codegraph 7 repos × 5 runs (Opus 4.8): tokens −86.5%, **cost −16.3%**. Fewer file reads (our A/B: reads −76%, tool calls −41%).
- **Cons:** time +22.7% (same study); **+7% to +12% on short questions** (fixed tool-schema overhead) [ours + vendor]; agents often bypass the tools (#914); ~80% more retrieval context stays resident in multi-turn sessions (README). TokenEconomizer paper: **Serena raised pooled cost** (+28.6% sklearn, +30.8% SymPy). codebase-memory-mcp: answer quality 83% vs 92% (authors' paper). graphify: 7.3× vs 71.5× claimed; ~240K tokens to build.
- **Security:** codegraph MIT, **telemetry on by default** (`CODEGRAPH_TELEMETRY=0`), installer adds auto-allow permissions + prompt hook (+3.5 s median). serena GPL-3.0, past **critical RCE** + 2 high (patched); unauthenticated dashboard. graphify: official PyPI is `graphifyy` (impostor risk); docs/PDFs go to your LLM. codebase-memory: 20 GB+ RSS reports.
- **Fit:** Claude Code ✅. Devin cloud ✅ via MCP. Devin CLI ✅.
- **Savings [est]:** large repos with long exploration **+3% → −16%**; small repos / short Q&A: expect a loss. Pick **one**, never several.

### 3.4 rtk (rtk-ai/rtk) — shell-output compression hook, 86K★
- **Concept:** PreToolUse hook rewrites `git status` → `rtk git status` and filters the output.
- **Pros:** per command 58–94% on git log, 99.9% on huge `find` [ours]; <10 ms overhead.
- **Cons:** billed cost **+7.6%** at low effort (JetBrains, p=0.004), ±5% total / +17% per task with **Pass@1 −1 to −2 pt** (Quesma, 1,740 runs), 0.5% of spend (Codepointer), +7/+9% [ours]. Lossy output → retries (pipe `| grep` returns 0 lines [ours]; pytest error shown as "No tests collected"; `find` bug → 339 consecutive errors). Covers Bash only.
- **Security:** Apache-2.0 CLI, BUSL-1.1 engine/proxy (use `rtk-oss` for Apache-only). 3 CVEs (permission-gate bypass, filter tampering, plugin injection), all fixed. Telemetry now opt-in.
- **Fit:** Claude Code ✅. Devin cloud ⚠ (install in snapshot + plugin hook, best-effort). Devin CLI ✅ (official hook example).
- **Savings [est]:** **+7% → −2%**. Not recommended as a cost tool. (`cost-coach` keeps the rtk rewrite **off** by default.)

### 3.5 headroom (headroomlabs-ai/headroom) — context-compression proxy, 79K★
- **Concept:** a local proxy (or MCP tool) between agent and API that compresses JSON, logs and code in the request.
- **Pros:** strong on JSON/RAG API apps (90%+ on repeated arrays); accuracy suite holds (GSM8K, SQuAD).
- **Cons:** default excludes Bash/Read/Grep (0% on coding output [ours]); token mode **+61%** from 4 cache rebuilds; cache mode +1% (compressed nothing) [ours]; 2.8% of spend (Codepointer); dashboard prices savings at full input price (overstates ~5–10×) [ours].
- **Security:** the proxy **handles API keys and full prompts**; keys stored in cleartext under `~/.headroom`; originals kept unencrypted in `ccr_store.db`; **telemetry beacon on by default**; 2 advisories (WebSocket hijack — high; MCP arbitrary file read, Nov 9 2026).
- **Fit:** Claude Code ⚠ (works, but a security review is required). Devin ❌.
- **Savings [est]:** coding agents **+61% → −3%**. Do not use in front of coding agents.

### 3.6 caveman (JuliusBrussee/caveman) — terse output style, 119K★
- **Concept:** a skill that strips filler and narration from answers (4.0 adds a proxy, input compression and a cloud "Auto" router).
- **Pros:** quality unchanged (JetBrains p=0.82); answers easier to read.
- **Cons:** output −8.5% (JetBrains), bill ±0.2% (662 sessions, #733), 0.4% of spend (Codepointer), +16% [ours]; rules cost ~1,160 input tokens per request; cache-bust bug (#1105); deletes articles in CJK text (#575).
- **Security:** CLI usage stats **on by default**; "Auto" sends prompts + CLAUDE.md + files to Caveman Cloud; `curl | bash` install; `caveman-compress` flagged "DANGEROUS" by skills.sh.
- **Fit:** Claude Code ✅. Devin ✅ (skill). 
- **Savings [est]:** **+16% → −3%**. Use only for readability, never Auto/cloud.

### 3.7 context-mode (mksglu/context-mode), 34K★
- **Concept:** keeps large tool output out of the context (sandbox + SQLite FTS search); the agent queries it.
- **Pros:** 93–99.9% output bytes kept out per call (vendor); HN-popular.
- **Cons:** **no independent billed-cost measurement**; hook conflicts deny ~40% of subagent spawns in auto mode (#967); hangs (#947); a hook deleted users' other hooks (#415).
- **Security:** **ELv2 (source-available)**; `ctx_execute` runs code as you; a dependency pulled malicious packages once (#838, closed).
- **Fit:** Claude Code ⚠. Devin ⚠ (MCP only).
- **Savings [est]:** unknown; not recommended until measured.

### 3.8 Measurement: ccusage, codeburn, cost-coach
- **ccusage** (MIT): reads local logs; fetches LiteLLM prices (use `--offline`); no telemetry. Pricing is list price (no Bedrock discount).
- **codeburn** (MIT): CLI clean; **desktop/menubar telemetry on by default**; `guard` hooks warn at $5 / stop at $15.
- **cost-coach** (ours, this repo): stdlib Python, no network except an optional Slack webhook you set. Prices every API call cache-aware, detects cache rebuilds and their cause, logs Devin ACU, marks before/after changes, and coaches in the moment via macOS notifications.

---

## 4. Devin: can these tools move the ACU bill?

| Lever | Reaches Devin cloud? | Mechanism | Expected effect on ACU |
|---|---|---|---|
| AGENTS.md rules (smallest change, read less, one task per session) | ✅ always loaded (≤16 KiB) | fewer actions, less context | **0 → −8%** [est] |
| Devin-native: Prompt precheck / Devin Coach, sleep timeout, usage policies, per-automation ACU budget | ✅ admin settings | fewer wasted sessions, caps | **−2 → −10%** [est] |
| Avoid `fast` mode (4× ACU) and Ultra on trivial tasks | ✅ | mode multiplier | large if used today; check Consumption Analytics |
| Fewer back-and-forth messages (docs list it as a cost driver) | ✅ habit | fewer actions/turns | included in the native row |
| codegraph MCP | ✅ MCP | fewer exploration actions on large repos | **+2 → −5%** [est] |
| rtk via snapshot + plugin hook | ⚠ best-effort hooks | smaller shell output | **+3 → −2%** [est], not recommended |
| headroom / caveman proxy | ❌ | — | 0 |
| TokenEconomizer | ❌ | needs `claude` CLI + Claude settings | 0 |

**Devin CLI** (our setup: ACU plan, confirmed not Legacy Windsurf Auth) converts tokens to ACU linearly → the Claude Code analysis applies: cache hygiene, smallest-change rules, codegraph on large repos, and cost-coach hooks (`./install.sh --project <repo>`). TokenEconomizer remains unverified there. Expected range for Devin CLI work: **≈ 0% / −10% / −20%** [est] (Claude levers minus TokenEconomizer).


### 4.1 What the 0.4 ACU / 1M token rate changes (Devin CLI)

If the rate is **flat across token types** (to confirm in Devin's model table), Devin CLI's bill behaves differently from Claude's:

| | Claude (AWS) | Devin CLI at a flat 0.4 ACU/MTok |
|---|---|---|
| Re-read old context | 0.1× (cheap) | **same price as everything else** |
| Cache rebuild | 1.25–2× (expensive) | no extra cost |
| Output | 5× | same price |
| Biggest driver | cache writes (72%) | **total tokens re-sent each call** (87% of our tokens are re-read context) |
| Best levers | fewer rebuilds, less new context, less code | **shorter sessions, smaller context, fewer calls** (`/clear`, one task per session, read less) |

Our 3-day Claude Code token volume (138.7M tokens) would cost ≈ 55 ACU ≈ **$22** at that rate, vs $145 on Claude list prices [ours, `cost-coach status`]. Under a flat rate, context-size tools (rtk, codegraph, context-mode) matter more on Devin CLI than on Claude, because re-read context is no longer discounted; headroom's cache rebuilds would cost nothing extra. This does not hold if Devin prices cache reads lower; confirm before acting on it.

---

## 5. Expected savings — pessimistic / expected / optimistic **[est]**

Combination: 1 − Π(1 − each lever), then × 0.7 for overlap (levers partly hit the same waste). These are projections from the evidence above, **not measured results**. Verify with `cost-coach compare`.

### Claude Code (AWS, usage-based)
| Lever | Pessimistic | Expected | Optimistic | Basis |
|---|---|---|---|---|
| Cache hygiene (coach alerts, session splitting, TTL choice) | −3% | −7% | −12% | rebuilds ≈ 29% of our spend [ours]; 10–40% avoidable |
| Smallest-change rule (AGENTS.md / Ponytail) | 0% | −5% | −10% | JetBrains −10.3% |
| TokenEconomizer (repeat-work repos) | 0% | −12% | −24% | paper, Claude Code −23.6% |
| codegraph (large repos only) | +3% | −2% | −8% | −16.3% on half of work |
| **Combined** | **≈ 0%** | **≈ −17%** | **≈ −31%** | |

### Devin (ACU $0.40, Opus 4.6)
| Lever | Pessimistic | Expected | Optimistic |
|---|---|---|---|
| Devin-native settings + habits | −2% | −6% | −10% |
| AGENTS.md smallest-change / read-less rules | 0% | −4% | −8% |
| codegraph MCP (large repos) | +2% | −1% | −5% |
| **Combined** | **≈ 0%** | **≈ −8%** | **≈ −16%** |

Dollar example: at $10K/month on Claude → −$0 / −$1.7K / −$3.1K per month. At 25,000 ACU/month on Devin ($10K) → −$0 / −$0.8K / −$1.6K.

### What we do not recommend (and the expected downside)
| Tool | Downside range |
|---|---|
| headroom in front of a coding agent | up to **+61%** |
| caveman as a cost tool | up to **+16%** |
| rtk as a generic cost tool | up to **+7–17%**, Pass@1 −1–2 pt |
| several code-graph MCPs at once | stacked schema overhead, +7–30% |

---

## 6. Security summary

| Risk | Tools |
|---|---|
| **Sees API keys / full prompts (proxy)** | headroom proxy, caveman proxy/Auto, rtk-proxy |
| **Telemetry on by default** | headroom (beacon), caveman CLI, codegraph, codeburn desktop/menubar |
| **Non-OSI license** | context-mode (ELv2), rtk engine/proxy (BUSL-1.1) |
| **Past critical/high CVEs (patched)** | serena (critical RCE + 2 high), headroom (high), rtk (high), graphify (high) |
| **Impostor / malicious clones** | Ponytail (#735 trojan), graphify (`graphifyy` is official), rtk name collision |
| **Writes agent settings / permissions** | codegraph (auto-allow), TokenEconomizer (deny rules), context-mode (hooks), Ponytail (asks to edit settings) |
| Lowest risk | cost-coach (stdlib, local), ccusage `--offline`, AGENTS.md rules |

---

## 7. Sources
- Billing: docs.devin.ai (admin/billing/usage, desktop/accounts/usage, cli/adaptive, product-guides/plugins, cli/extensibility/hooks, api-reference v3 consumption), docs.aws.amazon.com/bedrock prompt caching, code.claude.com/docs (amazon-bedrock, prompt-caching).
- Independent: JetBrains (caveman, rtk, Ponytail), Quesma (rtk), Codepointer, narration-studio #3032, codegraph #1393, Exchangepedia (graphify).
- Papers: TokenEconomizer arXiv 2610.22732; codebase-memory-mcp arXiv 2603.27277.
- Security: each repo's README/SECURITY.md/TELEMETRY.md and GitHub security advisories (checked 2026-11-11).
- Ours: `../experiments/2026-11-tool-ab-v1/03-agent-ab-with-cache.md`, `04` (72 runs, Sonnet 5.5), `cost-coach status` on this Mac (90 sessions, 3 days).
