---
title: Tool A/B v2 (latest versions, best-case scenarios)
summary: With latest versions and scenarios built to favour each tool, does any tool save ≥ 10%?
status: done
date: 2026-11-11
result: No tool passed the rule; caveman +46/+63%, combo +45%; Ponytail n=1 inconclusive
owners: FCS
---
# Tool A/B v2

54 graded sessions (6 arms × 3 scenarios × 3 reps) + 6 Ponytail sessions. Claude Code 2.1.322, claude-sonnet-5-5.
Billed $ matches Claude Code’s own reported cost in every session.

- Analysis: [analysis.md](analysis.md)
- Every session, one row each (72 rows incl. v1 long): [data/all_sessions.csv](data/all_sessions.csv) · column guide [data/DATA_INDEX.md](data/DATA_INDEX.md)
- v2 summary / per-session rows / versions: [data/v2/](data/v2/) · Ponytail: [data/v2_ponytail/](data/v2_ponytail/)
- Full transcripts (22 MB) are kept outside the repo; see `raw_file` in the CSV.

**Decision rule (fixed before running):** median billed $ ≥ 10% below base, every rep below base’s worst rep, quality ≥ base.

| Arm | S1 CI triage | S2 trace & fix | S3 long RCA | Verdict |
|---|---|---|---|---|
| rtk 1.2.0 | +9% | −5% | −2% | no effect |
| codegraph 1.6.2 | +5% | +28% | +7% | no effect |
| headroom 0.44 (cache) | +2% | +1% | −1% | no effect |
| caveman 4.1.0 | +46% | −1% | +63% | costs more |
| rtk + codegraph + caveman | −3% | +25% | +45% | costs more |
| Ponytail 5.3.3 (n=1) | +29% | +6% | −6% | inconclusive |

Open follow-up: Ponytail with 3 reps; codegraph on a large repo.
