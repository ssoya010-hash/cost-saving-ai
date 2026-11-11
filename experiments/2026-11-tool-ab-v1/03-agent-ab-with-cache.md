# 03. End-to-end A/B — do rtk, codegraph and headroom lower the *billed* cost?

> 60 real Claude Code runs (claude-sonnet-5-5), measured 2026-11-10. Total spend ≈ $4.
> Reproduce: `python3 bench/agent_ab.py --work <dir> --reps 3` then `python3 bench/analyze_ab.py <json>`.
> Raw stream-json per run: `bench/results/light_raw/`, `bench/results/heavy/agent_ab_raw/`.

## Why this test
Doc 02 measured **output size** (rtk −50%, headroom −48% on MCP output). Size is not the bill.
The bill is priced per token *type*, and with prompt caching most input is billed at 0.05–0.1×.
So we ran the whole agent loop and priced every API call by its real usage fields.

## Method
- Target: a fresh clone of `rtk-ai/rtk` (107 Rust files). codegraph arm uses a copy indexed with `codegraph init`.
- 4 arms that differ in one thing each:
  - `base`: no hooks, no MCP, direct API
  - `rtk`: + PreToolUse(Bash) → `rtk hook claude`
  - `codegraph`: + codegraph MCP server
  - `headroom`: + `ANTHROPIC_BASE_URL` → headroom proxy 0.26 (default config)
- Isolation: `--setting-sources project`, `--strict-mcp-config`, `--no-session-persistence`. Only Bash/Read/Grep/Glob are allowed (plus codegraph tools in that arm).
- 5 tasks × 3 reps × 4 arms. Each answer is checked against ground truth, and all 60 runs passed.
  - Light: find an error message, find the callers of a function, summarize recent PRs.
  - Heavy: review a 118 KB diff, trace a call path across files.
- Cache fairness: one warm-up call per arm (not recorded). Arm order rotates every rep.
- Cost is priced per call from `usage`: uncached input $2, cache write 5m $2.5 / 1h $4, cache read $0.10, output $10 per MTok.
- "Cost w/o cache" reprices the same tokens as if no caching existed. This isolates **token volume** from cache luck.

## Results (sum of per-task medians, 5 tasks)

| Arm | Pass | Billed $ | vs base | Cost w/o cache $ | vs base |
|---|---|---|---|---|---|
| base | 15/15 | 0.192 | — | 1.080 | — |
| rtk | 15/15 | 0.205 | **+7%** | 1.266 | +17% |
| codegraph | 15/15 | 0.206 | **+7%** | 1.166 | +8% |
| headroom | 15/15 | 0.305 | **+59%** | 1.325 | +23% |

Per-task tables: `python3 bench/analyze_ab.py bench/results/agent_ab_light.json` and `… bench/results/heavy/agent_ab.json`.

**None of the three tools lowered the billed cost on these tasks.** n=3 is small, and run-to-run spread is ±50% on single runs. So read these as "no measurable saving", not as precise penalties.

## What actually drives the bill (cache)

| Observation | Number |
|---|---|
| Cache hit rate (all arms, after warm-up) | 90–99% of input tokens |
| Cost w/o cache ÷ billed cost | **5–8×** |
| Where billed $ goes (base, heavy tasks) | cache write 62%, output 23%, cache read 15%, uncached ≈ 0% |

→ Caching already removes 80–90% of input cost. Every tool now competes for what is left, which is mostly **cache writes and output**.
→ A tool that changes earlier messages can **cost more** than it saves. Changed context forces a new cache write at 1.25–2× instead of a 0.1× read.

## Why each tool did not pay off

**rtk — format changes broke pipelines (measured bug).**
- Sonnet 5.5 already narrows output itself (`git diff --numstat | sort | head`), so there was little left to compress. The tool output was 2–3 K chars.
- rtk rewrites piped commands too. `git diff … | grep -E '^\+.*fn '` returns **59 lines raw and 0 lines through rtk**, because rtk's condensed diff drops the `+` prefixes.
- The agent got "(no output)", retried with `git --no-pager diff`, and made 4–5 API calls instead of 2–3. diff_review cost +46%.
- Fix shipped in devin-cost-coach: **never rewrite commands that contain a pipe** (test `test_pipeline_not_rewritten`).

**codegraph — overhead on short tasks.**
- The MCP tool definitions add a fixed prefix of about 1.5 K extra cache-write tokens.
- On trace_hook, the agent still read files after `codegraph_explore`, so tool output went up from 17 K to 33 K chars.
- This matches the repo's own benchmark (+12% cost on short questions). It pays off only on long, exploration-heavy sessions in large repos.

**headroom — Bash/Read/Grep are excluded by default, and the proxy adds cache writes.**
- Tool output was not compressed (same chars as base). This is consistent with `DEFAULT_EXCLUDE_TOOLS`.
- The headroom arm wrote 2× more cache tokens (21 K vs 9.8 K median), and its hit rate was 90% vs 95%. A plausible cause is the proxy rewriting request bodies, which shifts cache breakpoints. This is not proven at n=3.
- **Its dashboard overstates savings.** The proxy on this machine reports "$84 saved (37%)", but `savings_tracker._estimate_compression_savings_usd` prices removed tokens at the **full input price**. With an 81.5% cache hit rate, most of those tokens would have been cache reads at 0.1×. The real figure is closer to about $8–15, before counting any extra cache writes it causes.

## Conclusions for the talk
1. **Measure cost, not compression ratio.** Output −50% turned into billed cost +7% once caching and retries were counted.
2. **Caching is the biggest lever already in place.** Protect it:
   - keep the prefix (system prompt, tools, CLAUDE.md/AGENTS.md) stable
   - don't add or remove MCP servers mid-session
   - avoid pauses longer than the cache TTL in long sessions
3. Token tools only win when tool output is **large and repeatedly re-sent**: long sessions, big logs, huge MCP/JSON results. Under a 98%-cached short loop they don't.
4. If you adopt rtk, exclude pipelines (done in devin-cost-coach) and check `rtk gain` against **billed** cost, not tokens.

## Limits
- 5 tasks on one repo, one model, n=3 per cell. Long multi-hour sessions were not tested; that is where rtk and codegraph should do best.
- Devin was not measured directly. Under Devin's per-message billing, these tools don't change the credit count anyway (doc 01 §0).
