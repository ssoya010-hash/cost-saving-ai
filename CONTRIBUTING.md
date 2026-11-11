# Contributing

Everyone can contribute without asking. Commit and push directly, or open a PR if you want feedback.

| I want to add… | Do this |
|---|---|
| An experiment or project | `cp -r experiments/_template experiments/YYYY-MM-name` · write the decision rule **before** running |
| A tool card | `cp -r playground/_template playground/<tool>` |
| A result for an existing tool | add a row to `playground/<tool>/RESULTS.md` |
| A guide | add `guides/<name>.md` with front matter (`title`, `summary`, `read_time`) |
| A skill | add `skills/<name>/SKILL.md` (keep it short: it costs tokens) |
| A utility | add `utils/<name>/` that follows [design/zero-side-effects.md](design/zero-side-effects.md) |

Then run `python3 scripts/build_index.py` so the README index picks it up, and open a PR.

## Rules
1. Measure **billed $** (or ACU), not tokens. Link raw data.
2. Install tools from **official sources at pinned versions**; telemetry off; no proxy in front of company code.
3. Don’t edit another folder’s data; open an issue or comment instead.
4. English for repo content. Speaker notes may be in your own language.

## Review
No owners and no required approvals. Push freely; if you change shared guidance (`guides/`, `skills/`,
`design/`), mention it in `#ai-playground` so others see it. Fix mistakes forward with another commit.
