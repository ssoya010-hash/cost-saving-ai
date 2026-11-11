<!-- cost-coach:begin -->
## Cost discipline (read by Devin, Devin CLI, Claude Code, Codex, Cursor via AGENTS.md / CLAUDE.md)

The bill is mostly (1) new context written into the prompt cache and (2) output: reasoning + code.
Old context re-read from the cache is cheap. So: read less, write less, keep the prefix stable.

### Smallest change first
- Before writing code, check in this order: does existing code already do it? can a config/flag do it?
  can a few lines in one file do it? Only then add new functions, files or abstractions.
- No speculative features, options or layers the task did not ask for.
- Still required: a regression test for any bug fix or non-trivial logic, and doc updates when
  behaviour or a user-facing setting changes. Small is not an excuse to skip these.

### Read less, once
- Locate before reading: search for the symbol, then read only the relevant line range.
- Never dump whole logs, lockfiles or generated files. Write a short script that aggregates
  (counts, top-N, error windows) and read its output.
- Don't re-read a file you already read unless it changed.
- After 3 failed attempts at the same approach, stop, summarize what you learned, change approach.

### Turns
- When the user approves ("ok", "go", "continue"), finish all remaining steps of the plan
  (implement → test → fix → summarize) in that turn.
- Ask questions once, at the start, all together.
- Finish with one message: what changed, how it was verified, remaining risks. No long recaps.

### Sessions
- One task per session. For an unrelated follow-up, suggest a new session.
- Spawn subagents only for independent work touching 3+ files.
<!-- cost-coach:end -->
