# cost-saving-ai · AI Playground

**Spend less per task. Do more with AI.**

## Why this repo exists
Our AI coding usage (Claude Code on AWS, Devin) is capped per quarter, roughly $200–1,000 per person.
When the cap runs out, AI work stops. This repo exists so that **the same budget buys more AI work**:
we find out what really lowers the *billed* cost per completed task, share it in a form anyone can use
in minutes, and keep testing new tools and habits together.

**What we optimize:** billed $ per completed task ↓ · AI tasks per person per quarter ↑
**Guardrail:** task success and review quality must not drop.

## Principles
1. **Measure billed cost, not tokens.** Cached input costs 0.1×, cache writes 1.25–2×, output 5×.
   Token counts mislead; see [design/billing-model.md](design/billing-model.md).
2. **Every claim links to evidence**: an experiment in this repo or a cited source.
3. **Zero side effects on the AI.** Our own utilities never add tokens or change agent behaviour.
4. **Decide with a rule fixed in advance**: ≥ 10% billed saving, ≥ 20 sessions per side, no quality loss
   ([design/decision-rule.md](design/decision-rule.md)).
5. **Open to everyone.** Add your own experiment or tool card without asking; the index below updates itself.

---

## Quick index: I want to…

| I want to… | Go to | Time |
|---|---|---|
| Start saving today, no install | [guides/quickstart.md](guides/quickstart.md) | 3 min |
| Know which tools are worth it | [guides/tool-verdicts.md](guides/tool-verdicts.md) | 3 min |
| Get Mac alerts at costly moments + a weekly retro | [utils/cost-coach](utils/cost-coach/) | 3 min |
| Give my agent cost-saving rules | [skills/cost-discipline](skills/cost-discipline/) | 2 min |
| See the evidence and raw data | [experiments/](#experiments) | — |
| Watch the GOT talk | [the deck](experiments/2026-11-got-sharing/deck/) · [speaker notes (KO)](experiments/2026-11-got-sharing/speaker-notes/script.ko.md) | 1 h session |
| Run my own experiment | [experiments/_template](experiments/_template/) · [CONTRIBUTING.md](CONTRIBUTING.md) | — |
| Find internal channels and tips | [community/](community/) | — |

## Repo map

```
guides/        short, actionable answers built from the evidence      ← start here
skills/        rules and agent skills you can drop into Claude Code / Devin
utils/         tools we build (cost-coach)
playground/    one card per external tool: what, where it acts, verdict, results from colleagues
experiments/   one folder per experiment or project (incl. this talk): question → method → data → verdict
research/      long-form surveys, analyses and sources the guides are built from
design/        principles and models: billing model, decision rule, zero-side-effect contract, deck style
community/     internal channels, tips, the #ai-playground proposal
scripts/       repo tooling (index builder)
```

How the pieces relate: **experiments** produce evidence → **research** collects outside evidence →
**guides** turn both into advice → **skills / utils** put the advice into the tools people already use →
**playground** tracks each external tool → results flow back into experiments.

---

## Guides
<!-- index:guides:start -->
| Guide | What you get | Read time |
|---|---|---|
| [Devin cost guide](guides/devin.md) | What lowers ACU on Devin cloud and Devin CLI | 3 min |
| [Measure your savings](guides/measure-your-savings.md) | How to tell whether a tool or habit really saved money | 4 min |
| [Quickstart: save today](guides/quickstart.md) | The 6 habits that cut the bill, no install needed | 3 min |
| [Tool verdicts](guides/tool-verdicts.md) | Which cost tools to use, pilot or avoid, in one table | 3 min |
<!-- index:guides:end -->

## Skills
<!-- index:skills:start -->
| Skill | What it does | Works with |
|---|---|---|
| [cost-discipline](skills/cost-discipline/) | Read less, smallest change, finish in one turn, stop loops (Ponytail principle + cache habits) | Claude Code · Devin CLI · Devin cloud |
<!-- index:skills:end -->

## Utils
<!-- index:utils:start -->
| Utility | What it does | Status |
|---|---|---|
| [cost-coach](utils/cost-coach/) | Mac alerts at costly moments, cache-expiry warnings, weekly retro (Fri 10:00), billed-cost measurement | active |
<!-- index:utils:end -->

## Playground (tool cards)
<!-- index:playground:start -->
| Tool | Acts on | Evidence | Verdict |
|---|---|---|---|
| [caveman](playground/caveman/) | ⑤ output | ours +46 / −1 / +63% | 🔴 costs more |
| [codegraph](playground/codegraph/) | ③ tool calls | −16% large repos; ours +5/+28/+7% | 🟡 large repos only |
| [context-mode](playground/context-mode/) | ③ tool output | no billed-cost data | ⚪ unproven |
| [headroom](playground/headroom/) | ④ model + cache | cache mode ±2%, token mode +61% | 🔴 avoid |
| [Ponytail](playground/ponytail/) | ⑤ output | −10.3% JetBrains; ours n=1 inconclusive | 🟢 use as rule |
| [rtk](playground/rtk/) | ③ tool output | ours −5 to +9%; JetBrains +7.6% | 🔴 not a cost tool |
| [TokenEconomizer](playground/tokeneconomizer/) | ② agent turn | −18 to −31% (authors’ paper) | 🟢 pilot first |
<!-- index:playground:end -->

## Experiments
<!-- index:experiments:start -->
| Experiment | Question | Result | Status | Date |
|---|---|---|---|---|
| [GOT sharing talk (Nov 2026)](experiments/2026-11-got-sharing/) | Can a 1-hour talk + playground get teams to adopt cost-saving habits and join #ai-playground? | Deck and script ready; adoption to be measured | active | 2026-11-12 |
| [Tool A/B v2 (latest versions, best-case scenarios)](experiments/2026-11-tool-ab-v2/) | With latest versions and scenarios built to favour each tool, does any tool save ≥ 10%? | No tool passed the rule; caveman +46/+63%, combo +45%; Ponytail n=1 inconclusive | done | 2026-11-11 |
| [Tool A/B v1 (cache-aware billed cost)](experiments/2026-11-tool-ab-v1/) | Do rtk, codegraph, headroom, caveman lower billed cost on short tasks and long RCA sessions? | No tool lowered billed cost; headroom token mode +61% (cache rebuilds) | done | 2026-11-10 |
<!-- index:experiments:end -->

## Research
<!-- index:research:start -->
| Document | What it covers |
|---|---|
| [Tool analysis for Claude (AWS) and Devin (ACU)](research/analysis.md) | First principles, five whys, per-tool pros/cons/security/fit, savings ranges |
| [Billing anatomy: Devin and Claude](research/billing-anatomy.md) | How each product bills and which levers move it |
| [Tool survey: 16 GitHub tools](research/tool-survey.md) | Stars, claims vs independent benchmarks, user reviews, security |
<!-- index:research:end -->

## Design
<!-- index:design:start -->
| Document | What it decides |
|---|---|
| [Billing model](design/billing-model.md) | What the AI bill is made of and which atoms each lever moves |
| [Decision rule](design/decision-rule.md) | When a tool or habit counts as saving money and becomes a default |
| [Deck style](design/deck-style.md) | How talks in experiments/ are built (HTML, tokens, charts) |
| [Zero side effects contract](design/zero-side-effects.md) | Rules every utility in this repo must follow so it never adds AI cost |
<!-- index:design:end -->

---

## Contribute
Anything goes as long as it is measured and linked: a new experiment, a tool card, a guide fix, a skill.
No owners, no approvals: commit and push directly, or open a PR if you want feedback. See [CONTRIBUTING.md](CONTRIBUTING.md).

The tables above are generated: after adding a folder, run `python3 scripts/build_index.py` (CI checks it).

## Status
Started June 2026 as an FCS brownbag series; shared at GOT level in November 2026.
Proposed next: a GOT-level `#ai-playground` channel ([community/ai-playground.md](community/ai-playground.md)).
