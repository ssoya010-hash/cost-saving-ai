# 05. Tool A/B v2: latest versions, best-case scenarios, billed cost

> Claude Code 2.1.322, claude-sonnet-5-5, measured 2026-11-11. 54 graded sessions: 6 arms × 3 scenarios × 3 reps, all valid. Spend $24.48.
> Reproduce:
> - `bash bench/v2/setup.sh <work>`
> - `python3 bench/tool_ab_v2.py --work <work> --reps 3`
> - `python3 bench/analyze_v2.py`
>
> Raw data: `bench/results/v2/` (`rows.jsonl`, `raw/`, `logs/`, `summary.md`).

## Why a v2
The v1 tests (docs 03 and 04) had three weaknesses:
- Old tool versions.
- Scenarios where 93% of tool output was file reads, so rtk and codegraph had little to work on.
- n=2 with no decision rule.

v2 fixes each one:
- **Latest releases, installed in isolation** under `~/cc/utils/ai_cost_v2`. Global setup untouched.

  | Tool | Version | Setup |
  |---|---|---|
  | rtk | 1.2.0 | |
  | codegraph | 1.6.2 | |
  | headroom | 0.44 | Default is now cache mode |
  | caveman | 4.1.0 | Signed Go binaries: compression proxy and recovery MCP, plus the voice plugin |
  | Ponytail | 5.3.3 | Prepared, but not run (see Limits) |

- **Each tool set up the way its own installer does it for Claude Code**, scoped to the benchmark process:
  - rtk: the `rtk hook claude` PreToolUse hook, plus the `RTK.md` block that `rtk init -g` writes.
  - codegraph: a `codegraph init` index, the MCP server with `alwaysLoad`, and the instructions block that `codegraph install` writes.
  - headroom: proxy, headroom MCP retrieve tool and `ENABLE_TOOL_SEARCH`, which is what `headroom wrap claude` sets up.
  - caveman: `caveman claude` wrap, recovery MCP and plugin.
- **Three scenarios, each built to favor certain tools.** Every scenario has a hidden behavioral grader. I checked each grader: it fails the buggy branch and passes a hand-fixed copy.

| # | Task | Shape | Favors |
|---|---|---|---|
| S1 | CI triage: run the 5,700-test suite (about 680 K chars), find the culprit commit among 16 commits, fix it, re-run | shell-heavy | rtk, headroom |
| S2 | Symptom-only incident: the cause is 3 hops from the symptom (rate-limit key → `resolve_client_ip` → `_normalize_ip`), and the test that would catch it was deleted | code navigation | codegraph |
| S3 | v1 long RCA session (1.3 MB log, RCA and fix, 235 KB review, summary), peak context about 150 K | long context | headroom, caveman |

**Decision rule, fixed before the run.** A tool counts as saving money only if all three hold:
- its median billed cost is at least 10% below base,
- every one of its reps is below base's worst rep,
- its quality is at least base's.

## Results: billed $ per session, median (min–max), n=3 per cell

| Arm | S1 CI triage | S2 trace & fix | S3 long RCA | Verdict |
|---|---|---|---|---|
| base | 0.180 (0.151–0.221) | 0.113 (0.111–0.125) | 0.890 (0.838–0.897) | — |
| rtk | 0.196 (0.092–0.211) **+9%** | 0.108 (0.099–0.115) **−5%** | 0.873 (0.859–0.921) **−2%** | no effect |
| codegraph | 0.189 (0.165–0.212) **+5%** | 0.144 (0.075–0.201) **+28%** | 0.949 (0.938–0.985) **+7%** | no effect |
| headroom (cache mode) | 0.184 (0.146–0.264) **+2%** | 0.114 (0.079–0.118) **+1%** | 0.881 (0.767–0.920) **−1%** | no effect |
| caveman | 0.262 (0.175–0.295) **+46%** | 0.112 (0.105–0.118) **−1%** | 1.446 (1.318–1.495) **+63%** | **costs more** |
| rtk + codegraph + caveman | 0.174 (0.158–0.318) **−3%**, one run 4/5 | 0.141 (0.131–0.168) **+25%** | 1.291 (1.142–1.302) **+45%** | **costs more** |

- **Quality:** 53 of 54 sessions scored full marks. The combo arm scored 4/5 on one S1 run.
- **Noise:** the same arm, re-run, swings ±30% on short tasks. rtk's S1 cost ranged from $0.09 to $0.21. After rep 1, four tools looked like they saved 11–28% on S1. Those "savings" disappeared with more reps.

## The tools were active, so "no effect" is real
| Tool | Evidence (summed over runs) |
|---|---|
| rtk | Rewrote 46 of 81 shell commands; rtk's own counter reports 19 K tokens saved |
| headroom | Compressed 152 of 170 requests; the proxy reports 73 K tokens saved |
| caveman | Compressed tool output by 46–72% (its own estimate) |
| codegraph | Connected; called 32 times over 9 sessions (most in S3). The agent mostly preferred grep and Read |

## Why caveman costs more on long work
Caveman shrinks tool output and leaves a recovery handle. On the 235 KB review, the agent needed the exact text, so it called `caveman_retrieve` **11–14 times per session**:

| | base | caveman |
|---|---|---|
| Tool calls | 29 | 61 / 55 |
| Peak context | 144 K | 206 K / 196 K |
| Output tokens | 22 K | 36 K |

Compression saved cheap cached input and paid for it with extra turns, extra cache writes and extra output.

## Consistency with v1 and with outside data
- **Same conclusion as v1** (docs 03 and 04): under prompt caching, input-shrinking tools do not move the bill. The bill is cache writes plus output.
- **Matches the independent studies** collected in `../new_research`: JetBrains, Quesma and Codepointer all land between −16% and +16%.
- **Vendor claims** of 60–99% are per-payload token ratios. They are not billed-cost reductions.

## Limits
- One repo, one model (Sonnet 5.5), n = 3 per cell. Differences under about 15% cannot be resolved with this n.
- **Ponytail (DietrichGebert/ponytail v5.3.3) is prepared but not measured.**
  - Prepared: official repo, plugin copy with hooks pointed at a sandbox `CLAUDE_CONFIG_DIR` (`bench/v2/ponytail_plugin.sh`), and an arm in the runner (`--arms ponytail`).
  - Not run because of the keychain stall.
  - Outside evidence: JetBrains 80 paired tasks, −10.3% cost (p=0.004). It acts on output and turns, not on input, so it is the one candidate worth a pilot.
- Devin was not measured. On per-message or ACU billing these tools cannot change the message count.
