---
name: cost-discipline
description: Work in a way that keeps AI cost per task low. Use for every coding task: read narrowly, make the smallest change that fully solves the task, finish approved plans in one turn, and stop failing loops early.
summary: Read less, smallest change, finish in one turn, stop loops (Ponytail principle + cache habits)
works_with: Claude Code · Devin CLI · Devin cloud
---
# Cost discipline

The bill is mostly new context written into the prompt cache and output (reasoning + code).
Re-reading cached context is cheap. So: read less, write less, keep the prefix stable.

## Smallest change first
- Before writing code, check in order: does existing code already do it? can a config/flag do it?
  can a few lines in one file do it? Only then add functions, files or abstractions.
- No speculative features, options or layers the task did not ask for.
- Still required: a regression test for every bug fix or non-trivial logic, and doc updates when
  behaviour or a user-facing setting changes.

## Read less, once
- Locate before reading: search for the symbol, then read only the relevant line range.
- Never dump whole logs, lockfiles or generated files; write a short script that aggregates them.
- Don’t re-read a file you already read unless it changed.
- After 3 failed attempts with one approach, stop, summarize what you learned, change approach.

## Turns and sessions
- When the user approves (“ok”, “go”, “continue”), finish all remaining plan steps in that turn.
- Ask questions once, at the start, all together.
- Finish with one short message: what changed, how it was verified, remaining risks.
- Do not edit CLAUDE.md, AGENTS.md, MCP or agent settings during a task unless asked.
