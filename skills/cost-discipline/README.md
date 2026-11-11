# cost-discipline: install

| Agent | How |
|---|---|
| Claude Code (personal) | `mkdir -p ~/.claude/skills && cp -r skills/cost-discipline ~/.claude/skills/` |
| Claude Code / Devin CLI (one repo) | `mkdir -p .claude/skills && cp -r <this repo>/skills/cost-discipline .claude/skills/` (Devin also reads `.claude/skills`) |
| Devin cloud / any agent | paste the body of `SKILL.md` into the repo’s `AGENTS.md` |

Cost of the skill itself: only its short description is always in context; the body loads when used.
In AGENTS.md the whole block (~400 tokens) is loaded every session, which is still small next to the
context it saves. Evidence: [guides/tool-verdicts.md](../../guides/tool-verdicts.md) (Ponytail principle).
