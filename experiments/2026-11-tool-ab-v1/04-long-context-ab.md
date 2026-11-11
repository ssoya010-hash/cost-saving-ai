# 04. Long-context A/B — analysis + RCA + code fix sessions (cache-aware)

> 12 valid 4-turn Claude Code sessions (claude-sonnet-5-5), 6 arms × 2 reps, measured 2026-11-10.
> Spend ≈ $13 (plus an earlier ≈ $5 run discarded after a network outage, kept in `bench/results/long_failed_network/`).
> Reproduce: `python3 bench/long_ab.py --seed <seed> --runs <dir> --py <venv python> --caveman <skill text> --reps 2`.
> Raw stream-json per session: `bench/results/long/raw/`.

## Why this test
Doc 03 used short tasks (2–33 K chars of tool output). Our real work is long: data analysis, RCA and code changes that fill the context.
The Syncfusion post (Headroom + Caveman, one repo audit) reports −75% input and −88% output **tokens**, with no caching or billed cost.
This test reproduces that kind of workload and measures **billed dollars**.

## Scenario (one resumed session, 4 turns)
- Repo: fresh clone of `headroom` (5.5 MB Python), with two planted bugs and a 1.3 MB incident log (INC-4127).
- Turns:
  1. **Data analysis**: per-key status counts and p95 latency over 4,951 JSON log lines; find error windows.
  2. **RCA + fix**: find the root cause (rate limiter deducts tokens from rejected requests, so a key stays locked out for 30+ minutes). Fix it, add a regression test, run the tests, write `RCA.md`.
  3. **Large static review** of `headroom/cache/` (12 files, 235 KB). One planted LRU bug (`popitem(last=True)`).
  4. **Write-up**: `SUMMARY.md`.
- Size: peak context **149–165 K tokens**, about 290 K chars of tool output, 22–27 API calls, about 5 minutes per session.
- Hidden grader (6 checks):
  - the fix actually works (behavioral test)
  - a test was added
  - `RCA.md` exists
  - `SUMMARY.md` exists
  - the LRU bug was found
  - the log count is correct (561)
- **All 12 sessions scored 6/6**, so quality is equal and cost can be compared directly.

## Arms
| Arm | What changes |
|---|---|
| base | nothing |
| rtk | PreToolUse hook → `rtk hook claude` |
| caveman | caveman `SKILL.md` appended to the system prompt (cloned 2026-11-08) |
| hr_token | headroom proxy 0.26, `--mode token` (default: compress for token savings) |
| hr_cache | headroom proxy, `--mode cache` (freeze prefix for cache hits) |
| hr_cache+caveman | closest to the Syncfusion combo |

All 6 arms of a rep ran concurrently (same time of day, same API conditions). Each arm got a warm-up call first.

## Results (mean of 2 sessions)

| Arm | Billed $ | vs base | $ if no cache | vs base | Output tok | Cache hit | Cache-write tok |
|---|---|---|---|---|---|---|---|
| **base** | **0.953** | — | 3.250 | — | 25.9 K | 90.7% | 140 K |
| rtk | 1.039 | +9% | 3.247 | 0% | 31.8 K | 90.0% | 147 K |
| caveman | 1.104 | +16% | 3.700 | +14% | 33.8 K | 90.8% | 153 K |
| hr_token | 1.530 | **+61%** | 3.586 | +10% | 33.7 K | 84.3% | **264 K** |
| hr_cache | 0.960 | +1% | 2.965 | −9% | 27.0 K | 89.3% | 142 K |
| hr_cache+caveman | 1.054 | +11% | 3.692 | +14% | 30.0 K | 91.2% | 150 K |

Per-session spread was small: base $0.96 / $0.95, hr_cache $0.97 / $0.95, rtk $1.05 / $1.03. The exception was hr_token at $1.08 / $1.98.

**Base was the cheapest arm. No tool lowered the billed cost of a long analysis and RCA session.**

## Where the money goes (base)
| Part | $ / session | Share |
|---|---|---|
| Cache write (1h TTL, 2×) | 0.558 | 59% |
| Output (incl. reasoning) | 0.259 | 27% |
| Cache read (0.05×) | 0.136 | 14% |
| Uncached input | ≈ 0 | 0% |

Caching makes the session **3.4× cheaper** than list price ($3.25 → $0.95). The remaining bill is mostly **writing new context into the cache** (each new tool result and file read is written once) and **output**.

## Why each tool failed here

**headroom token mode (+61%): compression breaks the cache.**
- The proxy's own stats show it removed only **2.5%** of input tokens (69.8 K of 2.83 M) and caused **4 cache busts that re-wrote 265 K tokens** at 2×.
- In one session, cache writes went from 170 K to 359 K tokens and the bill doubled ($1.98).
- The proxy reported "$0.14 saved, 6.2%" for the same traffic.
- Rewriting earlier messages changes the cached prefix, and a re-write at 2× costs far more than the input it saved.

**headroom cache mode (+1%): safe, but does nothing.**
- It compressed **0 requests** (0 of 4.68 M tokens). Freezing the prefix keeps the cache intact, which is why it is break-even.
- Bash/Read/Grep outputs are excluded by default anyway (`DEFAULT_EXCLUDE_TOOLS`), and those are where long sessions get their bulk.

**caveman (+16%): it trims prose, but prose is not where output tokens go.**
- Visible answer text fell about 25% (13.7 K → 10.3 K chars). Final answers were shorter.
- But total output tokens **rose** from 26 K to 34 K. Visible text plus tool inputs is only about 35 K chars (≈ 9 K tokens), so about 2/3 of output tokens are reasoning and code/file content that a style prompt cannot shorten.
- The extra system prompt (4.4 KB) is also re-read on every call.

**rtk (+9%): the large outputs in these sessions are not rtk-shaped.**
- Tool output volume was unchanged (≈ 290 K chars). The bulk is `Read` of source files, Python one-offs over the log, and pytest output, which rtk does not filter (Read is not a shell command).
- The cost difference is within noise plus slightly more output.

## Reconciling with the Syncfusion post
| | Syncfusion | This test |
|---|---|---|
| Metric | token counts | billed $ with cache |
| Caching | not mentioned | 90% hit rate, 3.4× discount |
| Headroom | MCP tool, explicitly invoked in the prompt | proxy (token and cache mode) |
| Runs | 1 vs 1 | 2 × 6 arms, graded |
| Quality check | none | 6-point hidden grader, all 6/6 |

Both can be true. Token counts can drop a lot while the bill does not. Under caching, removed input is mostly 0.05× reads, and any change to earlier context triggers 2× re-writes.

## Takeaways for long analysis / RCA / code work
1. **The bill is cache writes + output.** Optimize those, not raw input tokens.
2. **Never rewrite history mid-session** (proxy compression, editing CLAUDE.md, swapping MCP servers). One bust re-writes the whole prefix at 2×.
3. **Read less, once.** Every new file or log chunk is written to cache once. Point the agent at the right file and line range, ask for aggregated analysis (a script that prints a table) instead of dumping raw logs.
4. **Split big jobs into separate sessions** (analysis → RCA → review). A 160 K context is re-read on every call, and a fresh session starts small.
5. **Output is reasoning + code, not chat.** Style prompts don't move it; clearer, narrower asks do.

## Limits
- One repo, one model (Sonnet 5.5), 2 reps per arm. The spread was small except for hr_token.
- headroom was tested as a proxy, not as an MCP tool the agent calls explicitly (Syncfusion's setup).
- Sessions peaked at about 165 K tokens. Runs up to the 1 M context limit, and auto-compaction, were not tested.
- Devin was not measured. On its per-message plan these tools cannot change the credit count.
