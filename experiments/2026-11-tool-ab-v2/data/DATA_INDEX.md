# Raw data and final results: index

All runs used Claude Code 2.1.322 with claude-sonnet-5-5, measured 2026-11-10 and 2026-11-11.

**Prices (USD per MTok):** input 2, output 10, cache write 1h 4, cache write 5m 2.5, cache read 0.10.

**Billed $** is recomputed from Claude Code's cumulative `modelUsage`. It matches Claude Code's own `total_cost_usd` in every session (column `claude_reported_usd`).

## 1. One table with every session
`all_sessions.csv` has 72 rows, one per graded session.

| Column | Meaning |
|---|---|
| study | `v2-4tools` (54), `v2-ponytail` (6, partial), `v1-long` (12) |
| scenario | `s1` CI triage · `s2` trace & fix · `s3` long RCA · `s3-v1` v1 long session |
| arm | `base`, `rtk`, `codegraph`, `headroom`, `caveman`, `combo`, `ponytail` (v1 also has `hr_token`, `hr_cache`, `hr_cache+caveman`) |
| score / max_score | hidden grader result |
| billed_usd | cache-aware billed cost |
| no_cache_usd | same tokens at list price, no cache |
| cache_write_usd, cache_read_usd, output_usd, uncached_in_usd | cost breakdown |
| *_tokens, cache_hit_pct, api_calls, tool_result_chars, peak_context_tokens, duration_s | usage and activity |
| raw_file | full Claude Code stream-json transcript of that session |

## 2. Final results (deck numbers come from these files)

| Study | Summary (markdown) | Summary (JSON) | Per-session rows | Run setup and versions |
|---|---|---|---|---|
| v2, 4 tools + combo (54 sessions, n=3) | `v2/summary.md` | `v2/summary.json` | `v2/rows.jsonl` (backup `v2/rows_reps0-2.jsonl`) | `v2/setup.json` |
| v2, Ponytail (partial: 1 of 3 reps) | `../../bench/results/v2_ponytail/summary.md`, generated with `python3 bench/analyze_v2.py bench/results/v2_ponytail` | | `v2_ponytail/rows.jsonl` | `v2_ponytail/setup.json` |
| v1 long session (12 sessions) | `../../research/04-long-context-ab.md` | | `long/long_ab.json` | |
| v1 short tasks (60 runs) | `../../research/03-agent-ab-with-cache.md` | | `agent_ab_light.json`, `heavy/agent_ab.json` | |
| Output-size micro-benchmarks | `../../research/02-tool-verification.md` | | `rtk_bench.json`, `headroom_bench.json` | |

## 3. Raw evidence
- `v2/raw/<scenario>.<arm>.<rep>.jsonl`: full transcript for each session, 22 MB. Every tool call, tool output and per-call token usage is in here.
- `v2/logs/<scenario>.<arm>.<rep>/`: per-session tool logs.
  - `rtk_hook.log`: every rewrite decision.
  - `rtk.db`: rtk's own savings counter.
- `v2/logs/headroom_proxy.log`: the headroom proxy log. Per-session proxy stats are stored in each row under `activity.headroom_delta`.
- `long/raw/`, `light_raw/`, `heavy/agent_ab_raw/`: v1 transcripts.
- Run logs: `v2_run.log`, `v2_ponytail_run.log`.
- Excluded from analysis:
  - smoke runs: `v2_smoke*`, `v2_pt_smoke`
  - the v1 run lost to a network outage: `long_failed_network/`

## 4. Reproduce
```bash
bash bench/v2/setup.sh <work>                                   # tools + seed repo, no API cost
bash bench/v2/ponytail_plugin.sh <work>                         # Ponytail plugin in a sandbox
python3 bench/tool_ab_v2.py --work <work> --reps 3              # 6 arms
python3 bench/tool_ab_v2.py --work <work> --reps 3 --arms base,ponytail --out bench/results/v2_ponytail
python3 bench/analyze_v2.py bench/results/v2
```
- Seed builder: `bench/v2/make_seed.py`. It is deterministic: the same commit hashes come out on every build.
- Hidden graders: `bench/v2/graders.py`.
