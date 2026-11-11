# 02. Cost-saving tool verification — measured by actually running them

> Every number comes from local runs. Reproduce: `bench/` scripts → `bench/results/*.json`.
> Tokens are approximated as chars/4 (the same method rtk uses internally). Measured 2026-11-10 on a MacBook.

## Summary verdict

| Tool | How it works | Measured result | Devin per-message | Devin token/ACU | Claude Code | Verdict |
|---|---|---|---|---|---|---|
| **rtk** 0.42.4 | Compresses shell output (CLI proxy) | **median 50.5% / weighted 68.5%** fewer output tokens (39 commands × 3 repos) | Indirect (fewer continuations) | **Direct** | **Direct** | ✅ Adopt (hook) |
| **headroom** | Compresses tool_result context (proxy/library/MCP) | Default settings **0%** (bash protected) / non-protected tools **48.5%** | ✗ | Proxy can't be inserted (Cognition backend) | ✅ Proxy | ⚠ Claude Code only, tune settings |
| **codegraph** 0.9.4 | Code graph MCP → fewer exploration calls | (In-repo A/B, 37 cells) **reads −76%, tool calls −41%, time −21%**, **cost +12%** on short questions | Indirect (fewer continuations) | Long tasks only | Long tasks only | ⚠ Large repos and long exploration only |
| **caveman** | Shortens output tokens (prompt) | Repo bench 65% output reduction (not measured here) | ✗ | Output share only | Output share only | △ Optional |

## 1. rtk — measured
`python3 -I bench/rtk_bench.py <rtk> <headroom> <codegraph>` → `results/rtk_bench.json`

| Command type | Savings (3-repo range) | Notes |
|---|---|---|
| `git log -n 30` | 58–94% | Largest effect |
| `git log --stat` | 50–94% | |
| `git diff HEAD~3` | 61–79% | |
| `git show HEAD` | 22–70% | |
| `ls -la` | 65–69% | |
| `find . -name '*.py'` | 10–99.9% | 99.9% on a large repo (418K → 306 tokens) |
| `git status` | 48–72% | Small absolute size |
| `git diff --stat`, `cat`, `grep` | **0% or −13%** | `rtk grep` output is actually larger on small results |
| `find … -not -path …` | **❌ fails** | "rtk find does not support compound predicates" → the agent retries → **extra turn** |

**Takeaways**
- Clearly effective on git, ls and find output: **50–70%** on a typical agent session's shell output.
- **No effect** on `cat` and `grep`. Claude Code's Read/Grep tools are also excluded from the hook (rtk README).
- **Risk**: when a rewrite fails, the agent retries, which costs more. → Our coach only applies **commands `rtk rewrite` supports** and falls back to the raw command on failure.
- Devin CLI officially supports PreToolUse `updatedInput` (the docs example is `rtk git status`), **so it applies with zero code changes.**

## 2. headroom — measured
`headroom/.venv/bin/python -I bench/headroom_bench.py <headroom repo>` → `results/headroom_bench.json`

| Sample | Arm A: tool name `bash` (default) | Arm B: MCP tool name |
|---|---|---|
| git diff (36K tok) | 0% | **60.2%** (17 s!) |
| grep result (8K) | 0% | **89.8%** |
| Python file read | 0% | 52.4% |
| JSON API result (16K) | 0% | **71.7%** |
| Build log (10K) | 0% | **98.3%** |
| git log (37K) | 0% | 0% |
| **Weighted total** | **0.0%** | **48.5%** |

**Takeaways**
- By default, headroom **excludes** Read, Grep, Bash, Edit and Write from compression (`DEFAULT_EXCLUDE_TOOLS` in `headroom/config.py`). The reason is safety: compressing exact file contents breaks edits.
- So in a coding agent, savings **only come from MCP/API-type tool results and old turns.**
- Diff compression took **17 seconds** (ML model) → latency cost.
- Devin calls models through Cognition's backend, so **headroom's proxy can't sit in the path** → no effect on Devin.
- → **Apply only in Claude Code (proxy mode)**, for workloads with heavy MCP and API responses.

## 3. codegraph — repo benchmark review
`docs/benchmarks/codegraph-ab-matrix.md` (37 cells, Claude Opus, with/without)
- File reads 159 → 38 (**−76%**), tool calls 321 → 189 (**−41%**), time 48 s → 38 s
- **Cost $13.8 → $15.4 (+12%)**: the MCP tool definitions are fixed overhead on short questions
- Net savings only on long multi-turn exploration (`call-sequence-analysis.md`)
- → For Devin per-message billing, **fewer tool calls → fewer continuations** is the only indirect effect. Adopt only on large repos.

## 4. Conclusion for the talk
1. "Install a token-saving tool and costs drop" is **half true**. It depends on the billing unit.
2. Devin (per-message): tools have **little effect**. **Prompt hygiene** (fewer messages, corrections and continuations) is the main lever.
3. Devin (token/ACU) + Claude Code: **rtk alone gives 50–70% on shell output**, and the hook makes it automatic.
4. headroom and codegraph **depend on settings and workload**; their cost can even go up (codegraph +12%, headroom 0% by default).
