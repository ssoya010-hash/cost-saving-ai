---
title: Tool survey: 16 GitHub tools
summary: Stars, claims vs independent benchmarks, user reviews, security
---
# Do AI coding token-saving tools really save money?

> **Update 2026-11-11:** our own re-test with the latest tool versions (54 graded sessions) supersedes the "our measurement" figures below. See [../experiments/2026-11-tool-ab-v2/analysis.md](../experiments/2026-11-tool-ab-v2/analysis.md) and [../experiments/](../experiments/).

### A practical guide to 17 GitHub star-ranked tools, compared against independent benchmarks and our own billed-cost measurements

> Basis: November 11, 2026 · GitHub star snapshot (`data/stars_2026-11-11.csv`) · independent benchmarks (`data/independent_benchmarks.md`) · our measurements (`../experiments/2026-11-tool-ab-v1/03-agent-ab-with-cache.md`, `04`)

---

**TL;DR**
- **Stars are not savings.** The top-starred tools (Ponytail 188K, Graphify 146K, caveman 119K, rtk 86K, headroom 79K) claim 60–99% savings. That number is the **per-response (payload) compression ratio**.
- Once caching, cache writes, output and retries are counted in the **actual billed cost**, independent measurements land at **−16% to +16%**.
  - JetBrains (86 tasks): caveman output −8.5%, rtk **+7.6%** cost at low effort
  - Quesma (1,740 runs): rtk ±5%, pass rate **−1 to −2pp** → "not recommended as a generic cost-saving tool"
  - Codepointer (614M tokens of real sessions): all three tools combined saved **3.7%**
  - Our measurement (long RCA sessions): headroom token mode **+61%**
- **What actually worked:**
  1. Code graph/search tools on **large repos with long exploration** (codegraph −16% cost)
  2. "Session/tool controllers" that look at the whole session (TokenEconomizer −18 to −31%, not yet independently replicated)
  3. A "write less code" prompt (Ponytail −10%, p=0.004)
  4. **Basic habits that protect the cache**
- **Recommendation: measure first (ccusage/codeburn) → change one at a time → judge by billed $.**

---

## 1. Why AI coding costs grow so fast — and why compression ratio misleads

The model reads far more than it writes. Source files, logs, git diffs, MCP responses and earlier conversation are **re-sent on every turn.** So it looks like "shrink the input and you save money."

But the 2026 Claude bill does not work that way.

| Token type | Price multiplier (vs input) | Share of a real bill (our long-session measurement) |
|---|---|---|
| Cache read | **0.05–0.1×** | 14% |
| Cache write | 1.25× (5 min) / 2× (1 h) | **59%** |
| Output (including reasoning and code) | 5× | **27%** |
| Uncached input | 1× | ≈ 0% |

- With a 90%+ cache hit rate, **most of the "input tokens" a tool removes were costing 0.05× to begin with.**
- If a tool **changes** earlier context, the cache breaks and the whole prefix is **re-written at 2×.** That is why compression can raise the bill.
- Codepointer found the same split in 500 real sessions: **42% cache_create + 29% output**. None of the three tools reduces those.

> **Key line for the slides:** "Payload −90% ≠ bill −90%. What you should cut is *cache writes + output*."

---

## 2. Popularity ranking at a glance (GitHub stars, 2026-11-11)

| # | Tool | ★ Stars | Category | Advertised savings | Independently measured (billed cost) |
|---|---|---|---|---|---|
| 1 | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | 188.3K | "Write less code" skill | 54% less code | **−10.3% cost (JetBrains, p=0.004)** |
| 2 | [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | 145.6K | Code knowledge graph | 71.5×, 80% (Cloud) | 7.3× tokens (n=1); 0 on implementation sessions |
| 3 | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | 118.9K | Output style (+ input compression in 4.0) | 65% output | **−8.5% output, quality unchanged** (JetBrains); 0.4% of spend (Codepointer) |
| 4 | [rtk-ai/rtk](https://github.com/rtk-ai/rtk) | 86.1K | Shell-output compression | 60–90% | **+7.6% at low effort / ±0% at high effort** (JetBrains); Django −20% / SymPy +7% (MS) |
| 5 | [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | 79.3K | Context-compression proxy | 21–57% input | 2.8% of spend (Codepointer); **our measurement +1% to +61%** |
| 6 | [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph) | 77.3K | Code graph MCP | 44% cheaper | **−16.3% cost, +22.7% time** (7 repos × 5 runs) |
| 7 | [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | 48.5K | Code graph MCP | 10× fewer tokens | Authors' paper: **answer quality 83% vs 92% (lower)** |
| 8 | [mksglu/context-mode](https://github.com/mksglu/context-mode) | 33.8K | Tool output → sandbox/SQLite | 98–99% | **No independent measurement** (HN 570 points) |
| 9 | [oraios/serena](https://github.com/oraios/serena) | 31.3K | LSP-based symbol search | 50–90% (blogs) | −66% tokens on a small repo (tiktoken, no cost measurement) |
| 10 | [ccusage/ccusage](https://github.com/ccusage/ccusage) | 19.4K | **Measurement** | — | (not a saving tool) |
| 11 | [getagentseal/codeburn](https://github.com/getagentseal/codeburn) | 11.8K | **Measurement + spending caps** | — | (not a saving tool) |
| 12 | [Maciek-roboblog/Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor) | 8.8K | Measurement | — | — |
| 13 | [microsoft/LLMLingua](https://github.com/microsoft/LLMLingua) | 6.8K | Prompt compression (for API apps) | up to 20× | No measurement in a coding-agent context |
| 14 | [drona23/claude-token-efficient](https://github.com/drona23/claude-token-efficient) | 6.2K | One CLAUDE.md file | 63% words | −40% tokens (n=1); original 61 lines cost **+10–20%** (issue #1) |
| 15 | [microsoft/TokenEconomizer](https://github.com/microsoft/TokenEconomizer) | 5.6K (1 month old) | **Session/tool controller** | 18–31% | Authors' paper: **cache-aware cost −18.4 to −30.9%** |
| 16 | [alexgreensh/token-optimizer](https://github.com/alexgreensh/token-optimizer) | 3.0K | Config/memory audit | — | −18% tokens (n=1) |
| 17 | [jgravelle/jcodemunch-mcp](https://github.com/jgravelle/jcodemunch-mcp) | 2.8K | Symbol-level code retrieval | 96% per lookup | No independent measurement |

Out of scope: model routing (claude-code-router 38K, LiteLLM 63K). This guide excludes model changes.

**Pattern:** the more stars, the bigger the advertised number, but **there is no correlation between stars and billed-cost savings.** caveman and rtk spread through viral memes and the reach of "60–90%", while the tools with significant results in independent measurements (Ponytail, codegraph, TokenEconomizer) all reduce **actions** (code written, files explored, failure loops) rather than **compressing text**.

---

## 3. Tools in five categories

```
                What the model reads (input)          What the model writes (output)
              ┌───────────────────────────────┐    ┌───────────────────────┐
  Compress    │ rtk · headroom · context-mode │    │ caveman · token-      │
  text        │ (caveman 4.0 "Read less")     │    │ efficient             │
              └───────────────────────────────┘    └───────────────────────┘
  Reduce      ┌───────────────────────────────┐    ┌───────────────────────┐
  actions     │ graphify · codegraph · serena │    │ Ponytail              │
              │ codebase-memory · jcodemunch  │    │ (less code written)   │
              └───────────────────────────────┘    └───────────────────────┘
  Control     TokenEconomizer (micro-skills · tool pruning · failure-loop guard) · token-optimizer
  sessions
  Measure     ccusage · codeburn · Claude-Code-Usage-Monitor
```

**Lesson:** text compression shrinks *what is already cheap* (cached input, prose). Reducing actions and controlling sessions cut **the number of turns, cache writes and code output** themselves, so they show up on the bill.

---

## 4. Tool by tool: claims vs reality

### 4.1 rtk — shell-output compression (86K★, Rust, Apache-2.0 + BUSL-1.1)
- **How it works:** a PreToolUse hook rewrites commands such as `git status` and `git log` into `rtk git …` and filters the output.
- **Claim:** 60–90% fewer tokens.
- **Measurements:**
  - Per command (ours): `git log` 58–94%, `ls` 65–69%, `find` (large repo) 99.9% / `cat`, `grep` **0% or −13%**
  - JetBrains SkillsBench: **+7.6% cost at low effort (p=0.004)**, ±0% at high effort
  - Quesma Terminal-Bench, 1,740 runs: total bill −5% to +5% depending on model, per task up to **+17%**, pass rate −1 to −2pp. "We do not recommend RTK as a generic cost-saving tool."
  - Codepointer: rtk covers only **22%** of tool output (the remaining 78% is Read and other built-in tools) → **0.5% of spend**
  - MS TokenEconomizer paper: Django −19.9% / SymPy +7.3%, depending on the repo
  - Ours (60 short runs + 12 long sessions): +7% / +9%. Real bug found: `git diff | grep '^\+'` returns 59 lines raw, **0 lines** through rtk → the agent retries
- **Verdict:** ⚠️ Conditional. Worth it only for **repos and workflows with long git/build/test logs**. Exclude pipe commands, and check `rtk gain` against **billed $**.
- Note: since 2026 the full edition includes the BUSL-1.1 compression engine and proxy. Use `rtk-oss` if Apache-2.0 only is required.

### 4.2 headroom — context-compression proxy/MCP (79K★, Python, Apache-2.0)
- **How it works:** sits between the agent and the API as a proxy, or is called as an MCP tool, and compresses JSON, logs and code by type. Originals are recoverable (CCR).
- **Claim:** 21–57% fewer input tokens (4 agent scenarios), 90%+ on JSON and logs.
- **Measurements:**
  - Our per-sample measurement: **0%** at defaults, because `DEFAULT_EXCLUDE_TOOLS` excludes Bash/Read/Grep for safety. Non-excluded tools 48.5% (diff compression takes 17 s).
  - Codepointer replay: activated on 45% of payloads, median 25% → **2.8% of total spend**
  - Our long-session measurement: `--mode token` **+61%** (4 cache busts, 265K re-written), `--mode cache` +1% (0 requests compressed)
  - Our measurement: the dashboard shows "$84 saved (37%)", but it prices removed tokens at **full input price**. Actual ≈ $8–15.
- **Verdict:** ⚠️ Fits **API apps heavy on JSON/RAG**. For coding agents, use only `--mode cache` or MCP (explicit calls). The proxy holds your API key, so it needs a security review.
- vs Syncfusion's "−75% input": that was 1 run per arm, by token count, with no caching or quality measurement. Our cache-aware billed $ points the other way.

### 4.3 caveman — "speak like a caveman" output style (119K★, Apache-2.0)
- **How it works:** a skill/system prompt that strips filler and narration. 4.0 adds input compression ("Read less"), model auto-selection (Auto) and more.
- **Claim:** 65% fewer output tokens (range 22–87%); in 4.0, 33% fewer input tokens and Auto 54% cheaper.
- **Measurements:**
  - JetBrains (86 paired tasks): **output −8.5%**, quality unchanged (p=0.82); raw cost +11.6% (because of one outlier)
  - Codepointer: **0.4%** of spend
  - Ours (long sessions): visible text −25%, but **total output tokens +30%** and cost **+16%**. Two-thirds of output tokens are reasoning and code, which a style prompt cannot shorten.
  - Vendor's own newer data: /caveman is only **~3%** better than "Answer concisely"
- **Verdict:** △ Little to lose, little to gain. Good for readability. Don't expect cost savings. The 4.0 Auto feature is effectively a model change, so it is a separate question.

### 4.4 Ponytail — "the laziest senior dev" (188.3K★, MIT, #1 in stars)
- **How it works:** a skill that pushes the agent to the simplest solution with the least code.
- **Measurements:** JetBrains, 80 paired tasks: **−10.3% cost (p=0.004)**. The only statistically significant saving in the series.
- **Verdict:** ✅ Worth a pilot. It reduces **actions (code written)**, not text. Quality checks are still needed.
- **Security warning:** a trojanized clone was distributed through a plugin marketplace (issue #735, Aug 2026). **Install only from the official `DietrichGebert/ponytail`.**

### 4.5 Code graph/search: graphify · codegraph · serena · codebase-memory-mcp · jcodemunch
- **How they work:** index the repo once, then answer with a single symbol/call-graph query instead of grep → read → read.
- **Measurements:**
  - codegraph: 7 repos × 5 runs, **tokens −86.5%, cost −16.3%, time +22.7%** (author runs a competing tool). Our measurement on short questions: **+7–12%** (MCP definitions are a fixed overhead)
  - graphify: **7.3×** vs the claimed 71.5× (n=1); the index build itself costs ≈ 240K tokens; 0 on implementation sessions
  - codebase-memory-mcp: authors' paper, 10× fewer tokens but **answer quality 83% vs 92%**
  - serena: 29 tools' schema ≈ 24K tokens of fixed overhead; extra cost on short lookups (anecdotal)
- **Verdict:** ✅ For **large repos and long exploration sessions only**. Expect losses on short Q&A. Watch the fixed cost of tool definitions.

### 4.6 TokenEconomizer — Microsoft Research + UC Berkeley (5.6K★, released Oct 2026)
- **How it works:** a black-box controller that sits outside the agent.
  1. Learns repo-specific **micro-skills** (build commands, file locations, etc.)
  2. **Prunes** tools that are never used
  3. Intervenes in **failure loops**
- **Measurements** (authors' paper, arXiv 2610.22732):
  - 579 tasks, 3 agents (Claude Code, Codex, Copilot CLI): **cache-aware cost −18.4 to −30.9%**, cheaper in all 30/30 cells, Pass@1 up in 4 of 5 settings
  - Claude Code + Sonnet 5: −23.6%
  - With rtk stacked: −33.2%
  - Caveat: the **first 5 tasks** in each repo can cost more (learning period)
- **Verdict:** ✅ The most promising candidate. It is the only one that **measured billed cost (cache-aware)** with statistical design. But it is the authors' own figures, not independently replicated, and one month old → **an internal pilot is required.**

### 4.7 Measurement tools: ccusage (19K★) · codeburn (12K★)
- **ccusage:** reads local Claude Code JSONL and produces daily/session/model reports, including cache tracking.
- **codeburn:** finds unused MCP servers, repeatedly re-read files and bloated CLAUDE.md files (`optimize`), plus **spending caps** (`guard`: warns at $5 and stops at $15 per session).
- **Verdict:** ✅ **Step 0 of any adoption.** You cannot judge any tool's effect without them.

---

## 5. Advertised vs independently measured vs our measurement — the core slide

| Tool | Advertised | Independent (billed cost) | Our measurement (billed $, Sonnet 5.5) | Verdict |
|---|---|---|---|---|
| rtk | −60–90% | **+7.6% / ±0%** (JetBrains), −0.5% (Codepointer), −5%/+5% (Quesma, 1,740 runs, pass rate −1 to −2pp) | +7% (short) / +9% (long) | ⚠️ Conditional |
| headroom | −21–57% | −2.8% (Codepointer) | **+59% / +61%** (token mode), +1% (cache mode) | ⚠️ Not for coding |
| caveman | −65% output | −8.5% output (JetBrains) | **+16%** | △ Optional |
| Ponytail | −54% code | **−10.3% (p=0.004)** | Not measured | ✅ Pilot |
| codegraph | −44% | **−16.3%** (time +23%) | +7% (short questions) | ✅ Large repos |
| graphify | 71.5× | 7.3× tokens (n=1) | Not measured | △ |
| TokenEconomizer | −18–31% | (authors' paper) **−18.4 to −30.9%** | Not measured | ✅ Pilot first |
| claude-token-efficient | −63% words | −40% tokens (n=1) / original 61 lines **+10–20%** (issue #1) | Not measured | △ Keep it short |

> **Takeaway in one line:** "Compression ratio 60–99% → billed savings 0–16%. Tools that win reduce *actions*; tools that compress *text* lose to the cache."

---

## 6. Real user reviews

> Collected from: Hacker News comments, GitHub issues (sorted by most comments), and personal blogs. Reddit had only SEO/promotional posts and is excluded.

| Tool | Sentiment | User voices (quotes) | Recurring complaints |
|---|---|---|---|
| **rtk** | 🔴 Mixed–negative | "My RTK findings are the same. It worsens task performance overall and you don't save money." ([HN](https://news.ycombinator.com/item?id=49658835)) / "rtk randomly messes modification and agent start polling same tool continuously" ([HN](https://news.ycombinator.com/item?id=49657097)) / Positive: shell output −31.4% ([Daniela Baron](https://danielabaron.me/blog/how-i-stopped-running-out-of-tokens/)) | Broken commands (grep glob #2167, `;;` mangling #3197, find predicates #664), **lossy output** (pytest error reported as "No tests collected" #2317), telemetry was opt-out until v0.36 (#1154) |
| **headroom** | 🟡 Mixed | "a much more legit alternative to RTK… transparent about the compression algorithms" ([HN](https://news.ycombinator.com/item?id=48593858)) / "'90% Token Savings' is a LIE — Reality is 7-19%" ([#1843](https://github.com/headroomlabs-ai/headroom/issues/1843), the maintainer acknowledged 15–20% for coding agents) | "Saved 0%" regression after 230 requests (#327, fixed in July), proxy auth/API errors (#71, #3017), ~0.3% compression on long sessions (#1696), idle CPU use |
| **caveman** | 🟡 Mixed (popular for readability) | "You use caveman to save on tokens, I use it to make the agent shut up." ([HN](https://news.ycombinator.com/item?id=49666629)) / "saving a couple hundred tokens in final output is going to be negligible" ([HN](https://news.ycombinator.com/item?id=47954745)) / Issue #733: "Advertised 65%, measured 8.5%"; analysis of 662 sessions: **bill change ±0.2%** → the project replaced its README figures | Cache busting on every request (#1105), install failures (OpenCode, PowerShell), **articles deleted from CJK text** (#575, relevant to Korean users) |
| **context-mode** | 🟡 Mixed (little evidence) | "codegraph + context mode are all I need" ([HN](https://news.ycombinator.com/item?id=49574056)) / "tools don't seem to trigger reliably… Claude used regular fetch" ([HN](https://news.ycombinator.com/item?id=47148025)) | Conflicts with the auto-mode classifier denying **~40% of subagent spawns** (#967), agents hanging for hours (#947), inflated stats (#950: 100% savings with 0 calls) |
| **codegraph** | 🟡 Mixed | "used fewer tokens. However… more issues… re-implemented a function that already existed" ([HN](https://news.ycombinator.com/item?id=49626630)) / "[after blocking grep] it started using Python to find/search instead" ([HN](https://news.ycombinator.com/item?id=49669905)) | Out of memory (#1553), **the LLM doesn't call the tools on long tasks** (#914), Windows console flashing |
| **codebase-memory-mcp** | 🟡 Mixed | "one of the two most outsized ROI wins… improved the quality of output" ([HN](https://news.ycombinator.com/item?id=49171701)) / "85k input tokens with the tool versus 80k without it… made it worse" ([HN](https://news.ycombinator.com/item?id=48175406)) | **20GB+ RSS** (#832), Claude ignores the tools without CLAUDE.md edits (#69), hook timeouts (#1335) |
| **serena** | 🟢 Mixed–positive | "I use serena as an MCP for all LSPs and it works great" ([HN](https://news.ycombinator.com/item?id=49563290)) | `replace_symbol_body` duplicates code (#576, 41 comments), memory use around 30GB (#944), connection failures (#494) |
| **graphify** | 🔴 Skeptical | "static graphs… like graphify… +5% increase in token usage in the same benchmark" ([HN](https://news.ycombinator.com/item?id=50442899)) / "structured information… the model isn't set up to work with effectively" ([HN](https://news.ycombinator.com/item?id=50092211)) | Files and entities silently dropped (#4101, #1689), node ID collisions (#4281), hook failures (#651). **No first-hand positive reviews found** |
| **claude-token-efficient** | 🔴 Skeptical | Issue #1 benchmark: the original 61-line CLAUDE.md cost **10–20% more** than a 1-line baseline → the author cut it to 7 lines and conceded it "changes tone, not correctness" ([#1](https://github.com/drona23/claude-token-efficient/issues/1)) | Rules load every turn → extra input cost |
| **ccusage** | 🟢 Positive | "on the $100/mo Max plan… running $600-800/mo in terms of usage" ([HN](https://news.ycombinator.com/item?id=44610925)) | Inaccurate live blocks (#483), statusline at 100% CPU (#459), npx supply-chain concern |
| **codeburn** | 🟢 Positive | "Activity classification is the actually useful feature" ([HN](https://news.ycombinator.com/item?id=47759035)) / "Works quite well" | Subagent/Cline sessions missing (#336, #874), stale menu bar data |

**Five patterns in the reviews**
1. **Advertised numbers are not reproducible.** Measured against the whole bill, savings are about 0.5–3% (Quesma, Codepointer, caveman #733).
2. **Agents ignore the tools.** codegraph, codebase-memory and context-mode get bypassed, or the agent routes around a blocked hook with Python.
3. **Lossy compression → retries → cost and quality loss** (rtk is the prime example).
4. **Practical friction:** Windows, memory/CPU, hook conflicts.
5. **Measurement tools get the best reviews.** They don't promise savings.

**Additional independent benchmark: [Quesma – Does RTK make AI coding cheaper?](https://quesma.com/blog/does-rtk-make-ai-coding-cheaper/)** (Terminal-Bench, **1,740 runs**)
- Total bill: Fable −5%, DeepSeek **+5%**. Per task: Fable +1%, DeepSeek **+17%**. Pass rate **−1 to −2 percentage points**.
- In v0.45, a `find` rewrite bug caused **339 consecutive errors**.
- Conclusion: "`rtk gain` counts removed output, not money saved." / "We do not recommend RTK as a generic cost-saving tool." ([HN discussion, 84 comments](https://news.ycombinator.com/item?id=49656471))

---

## 7. Recommended stack — by situation

| Situation | Recommendation | Don't |
|---|---|---|
| **Everyone (day 0)** | Measure with ccusage/codeburn → clean up unused MCP servers and bloated CLAUDE.md → codeburn guard caps | Install tools before you have a baseline |
| Long sessions on large monorepos | codegraph *or* serena (pick one) + a TokenEconomizer pilot | Run several MCP servers at once (stacked schema cost) |
| Agents writing too much code | Ponytail (official repo only) | — |
| Long build/test logs | rtk (exclude pipes) or a log-summary script | Compress-proxy everything |
| Hard-to-read answers | caveman lite/full (for readability) | Expect cost savings |
| JSON/RAG-heavy API apps | headroom (in a library/app, not an agent) | headroom token mode in front of a coding agent |

**Habits that protect the cache (free, often the biggest effect)**
1. Keep the prefix stable: don't edit CLAUDE.md or add/remove MCP servers mid-session.
2. Split large jobs into separate sessions (analysis → RCA → review). Use `/clear` actively.
3. Ask for an aggregation script instead of a raw log dump ("read less, once").
4. Spell out the spec and done criteria in the first prompt → fewer correction loops.

---

## 8. Expected impact (projection) and how to verify it

> This is a **projection, not a measured result**. It combines the evidence above (Ponytail −10.3% from JetBrains, TokenEconomizer −18.4 to −30.9% from its paper, codegraph −16.3% on large repos, ≈0 for compression tools in our A/B). A 30% overlap discount is applied.

| Scenario | Assumptions | Billed cost change | At $10K/month* |
|---|---|---|---|
| **Conservative** | Ponytail at half its effect (−5%); TokenEconomizer at half its lowest result (−9%); codegraph 0 | **≈ −10%** | −$1.0K |
| **Expected** | Ponytail −10%; TokenEconomizer at its lowest result (−18%); codegraph 0 | **≈ −18%** | −$1.8K |
| **Optimistic** | Ponytail −10%; TokenEconomizer best case (−31%); codegraph −16% on the half of work in large repos | **≈ −30%** | −$3.0K |
| Compression stack only (rtk + headroom + caveman) | Independent and our measurements | −4% to +16% | −$0.4K to +$1.6K |

\* Illustrative spend. Replace with your own `ccusage` baseline. Combined effect = 1 − Π(1 − each lever), × 0.7 for overlap. TokenEconomizer's first ~5 tasks per repo can cost more while it learns.

**How to verify: 2-week pilot**
1. **Week 0:** `npx ccusage@latest daily` / `codeburn` to record a baseline ($/session, cache hit rate, output share).
2. **Week 1:** add **one** lever (TokenEconomizer or Ponytail).
3. **Week 2:** compare billed $ per session, task success/rework, and time. Ignore token counts and compression ratio.
4. Keep it only if it saves ≥ 10% and quality holds, then try the next one.

Install commands (check each repo before use):
```bash
npx ccusage@latest daily                                   # measure
npm i -g codeburn && codeburn optimize && codeburn guard install
claude plugin install tokeneconomizer@tokeneconomizer      # session control (MS)
/plugin marketplace add DietrichGebert/ponytail            # in Claude Code
/plugin install ponytail@ponytail
curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh && codegraph install
brew install rtk && rtk init -g                            # optional: log-heavy workflows
```

---

## 9. FAQ

**Q. Stars are huge. Is it still not worth it?** Stars measure spread, not savings. caveman (119K) cut cost by 0.4–8.5% in independent tests.

**Q. Syncfusion measured −75% input and −88% output.** That was 1 run per arm, by token count, without caching. When we reproduced a similar setup and measured billed $ with caching, the result was +11%.

**Q. Do these tools apply to Devin?** On per-message (credit) plans, tools don't change the message count, so there is no direct effect. On ACU/token plans, the same logic as this guide applies.

**Q. Any security concerns?** Proxies (headroom, rtk-proxy) see your API key and all your code. Malicious clones have appeared in plugin marketplaces (Ponytail #735). Check licenses: rtk full edition is BUSL, context-mode is source-available.

**Q. What is the single most important thing?** **Measure.** The same tool goes from −20% to +7% depending on the repo (rtk: Django vs SymPy).

---

## Sources
- User reviews: Hacker News comment threads and GitHub issues (links inline in §6)
- Independent: [Quesma rtk](https://quesma.com/blog/does-rtk-make-ai-coding-cheaper/) · [JetBrains caveman](https://blog.jetbrains.com/ai/2026/07/speak-to-ai-agents-like-cavemen-tosave-tokens/) · [JetBrains rtk](https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/) · [JetBrains Ponytail](https://blog.jetbrains.com/ai/2026/07/ponytail-skill-claude-tested/) · [Codepointer](https://codepointer.dev/p/cutting-llm-token-costs-with-rtk) · [ComputingForGeeks](https://computingforgeeks.com/reduce-claude-code-token-usage-tools/) · [vagkaratzas benchmark](https://github.com/vagkaratzas/token-consumption-benchmark) · [codegraph #1393](https://github.com/colbymchenry/codegraph/issues/1393)
- Papers: [TokenEconomizer arXiv 2610.22732](https://arxiv.org/abs/2610.22732) · [codebase-memory-mcp arXiv 2603.27277](https://arxiv.org/abs/2603.27277)
- Reference article: [Syncfusion – Headroom vs Caveman](https://www.syncfusion.com/blogs/post/headroom-vs-caveman-ai-token-costs)
- Our measurements: `../brownbag_session/research/01–04`, `../brownbag_session/bench/`
