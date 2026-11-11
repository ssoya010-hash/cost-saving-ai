# Independent benchmark source notes (collected 2026-11-11)

> Raw notes behind the report. ★ = strong evidence (has a methodology), △ = weak (n=1, or vendor claims quoted second-hand), ✗ = no tests of its own.

| Source | Date | Strength | Method | Key numbers |
|---|---|---|---|---|
| [codepointer.dev](https://codepointer.dev/p/cutting-llm-token-costs-with-rtk) (Yongkyun Lee, no affiliation) | 2026-06-18 | ★ | Microbenchmark on 4 repos + replay of 500 real sessions (614M tokens, $926) | Per payload: headroom 54%, rtk 33–99%, caveman 50%. **Share of total spend: headroom 2.8%, rtk 0.5%, caveman 0.4%, combined 3.7%.** The bill was 42% cache_create and 29% output |
| [Quesma – rtk](https://quesma.com/blog/does-rtk-make-ai-coding-cheaper/) | 2026 | ★ | Terminal-Bench, 1,740 runs, Fable/DeepSeek | Total bill −5% / +5%; per task +1% / **+17%**; pass rate −1 to −2pp; find bug caused 339 consecutive errors. "Not recommended as a generic cost-saving tool" |
| [caveman #733](https://github.com/JuliusBrussee/caveman/issues/733) | 2026 | △ (contributor analysis) | 662 sessions | Bill effect ±0.2% (indistinguishable from 0) |
| [JetBrains – caveman](https://blog.jetbrains.com/ai/2026/07/speak-to-ai-agents-like-cavemen-tosave-tokens/) | 2026-07 | ★ | SkillsBench, 86 paired A/B tasks, Claude Code + Sonnet 5 | Output tokens **−8.5%**; raw cost +11.6% (one outlier; −10% without it); quality unchanged (p=0.82) |
| [JetBrains – rtk](https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/) | 2026-07 | ★ | SkillsBench, low/high effort, Wilcoxon | **Cost +7.6% at low effort (p=0.004)**, ±0% at high effort |
| [JetBrains – Ponytail](https://blog.jetbrains.com/ai/2026/07/ponytail-skill-claude-tested/) | 2026-07 | ★ | 80 paired tasks | **Cost −10.3% (p=0.004)**, the series' only statistically significant saving |
| [TokenEconomizer paper](https://arxiv.org/abs/2610.22732) (MSR + UC Berkeley) | 2026-10 | ★ (but written by the tool's own authors) | 579 tasks, 3 agents, cache-aware cost | **−18.4 to −30.9%**, cheaper in all 30/30 cells, Pass@1 up in 4 of 5 settings. As a baseline, rtk ranged from Django −19.9% to SymPy +7.3% |
| [computingforgeeks](https://computingforgeeks.com/reduce-claude-code-token-usage-tools/) | 2026-04-22 | △ (n=1) | 1 prompt on sindresorhus/ky, Sonnet 4.5 | claude-token-efficient −40%, caveman −37/−38%, alexgreensh token-optimizer −18%, rtk ≈ 0 |
| [vagkaratzas/token-consumption-benchmark](https://github.com/vagkaratzas/token-consumption-benchmark) | 2026 | △ (tiktoken count, no quality check) | 30-file Python app, 9 tasks | serena −66%, graphify −66%, codegraph −54%, rtk −4.6%, caveman −0.7% |
| [codegraph issue #1393](https://github.com/colbymchenry/codegraph/issues/1393) (author runs a competing tool) | 2026-07-21 | △ | 7 repos × 5 runs, Opus 4.8 | Tokens −86.5%, **cost −16.3%**, time +22.7% |
| [Exchangepedia – graphify](https://exchangepedia.com) (Bharat Suneja) | 2026-04 | △ (n=1) | 140-file FastAPI repo, 5 queries | 7.3x (vs 71.5x claimed); index build ≈ 240K tokens; 0 savings on an implementation session |
| [codebase-memory-mcp paper](https://arxiv.org/abs/2603.27277) (written by the tool's own authors) | 2026-03 | △ | 31 repos | 10x fewer tokens, **answer quality 83% vs 92% baseline (lower)** |
| MindStudio / Pillitteri / andrew.ooo | — | ✗ | No tests of their own (relay JetBrains or quote READMEs) | Background only |

Our measurements (`../brownbag_session/research/03`, `04`, 2026-11-10, Sonnet 5.5, cache-aware billed $)
- Short tasks, 60 runs: rtk +7%, codegraph +7%, headroom proxy +59% (vs base)
- Long RCA sessions, 12 runs, all 6/6 on quality: rtk +9%, caveman +16%, headroom token mode **+61% (4 cache busts)**, headroom cache mode +1%

Note: the JetBrains originals returned 403 at collection time, so their numbers were cross-checked against InfoWorld and TechTimes coverage.
