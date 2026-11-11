# cost-coach — design

## Goal
Notify the developer (macOS Notification Center) the moment a **cost anti-pattern** happens in
Claude Code or Devin CLI, so they can change the habit. Measure the effect with one command.

## Hard constraints (zero side effects on the AI)
| Constraint | How it is enforced | Test |
|---|---|---|
| **No extra tokens** | Hooks print **nothing** to stdout (Claude Code adds UserPromptSubmit stdout to the context). No `additionalContext`, no `systemMessage`. | `test_hooks_never_print` |
| **No behaviour change** | Never blocks, never rewrites commands, never edits files the agent uses. Exit code always 0. | `test_never_blocks`, `test_garbage_input` |
| **No noticeable latency** | Hook does O(1) work on small state files; transcript parsing runs in a detached background process. Target p95 < 150 ms per hook. | `test_hook_latency` |
| **No network** | Only an optional Slack-compatible webhook the user configures, sent from the background process. | code review: `notify.py` |
| **No AI calls** | No LLM, no API key. Pure Python stdlib. | — |
| **Fail silent** | Any exception → exit 0, no output, error logged to `~/.cost-coach/events.jsonl`. | `test_garbage_input` |
| **Not spammy** | Per-rule cooldown per session + global cap per hour + quiet hours + mute. Thresholds set from real logs (30+ tool calls = top 3.5% of turns, >20K output = top 2% of tool results). | `test_cooldown_and_cap` |
| **No duplicates** | Devin CLI also reads `~/.claude/settings.json`; an event delivered to two installed copies is handled once (atomic marker, 1.5 s window). | `test_duplicate_delivery_counted_once` |
| **Safe install** | Original settings backed up once, invalid JSON refused, only own entries removed, `--dry-run`, `--uninstall --all`. | `InstallTests` |

Optional, off by default: `agent_hints` (injects one guidance line to the agent — costs tokens) and
`mode: "block"` (blocks bare "ok" prompts). Both stay off unless the user opts in. Command rewriting
(e.g. rtk) is deliberately not included: independent A/Bs found no billed saving.

## Billing model the rules target
Claude (AWS, per token): `$ = calls × (new context at 1.25–2× + old context at 0.1×) + rebuilds + output × 5`.
Devin CLI (ACU, Opus 4.6 = 0.4 ACU / 1M input tokens): Devin also uses a prompt cache (separate
cache_read / cache_write prices); its TTL is not documented, assumed 5 minutes.
Both are cut by: **fewer turns, smaller and stable context, fewer rebuilds, less code.**

## Anti-pattern catalog
| ID | Detected when | Hook | Billing atom | Message (short) |
|---|---|---|---|---|
| `empty_prompt` | prompt is only a bare acknowledgement ("ok", "continue", and Korean equivalents) | UserPromptSubmit | extra turn re-sends the whole context | Put the next instruction in the same message |
| `correction_loop` | 2+ correction prompts in a row ("no, …", "revert that", and Korean equivalents) | UserPromptSubmit | turns + growing context | Restate the spec once, start a new session |
| `bundled_tasks` | 4+ separate tasks in one prompt | UserPromptSubmit | context grows across unrelated work | One task per session |
| `vague_large_task` | "refactor everything" style ask with no file/symbol | UserPromptSubmit | trial-and-error turns | Plan first, name files |
| `cache_expired` | session idle longer than the cache TTL with ≥50K context; fires **before** the user resumes, with the rebuild cost | Stop → expiry timer | full context re-written at 1.25–2× | Same task: continue. New task: new session |
| `cache_expired_resume` | prompt after idle > TTL, only if the timer did not already warn (e.g. Mac was asleep) | UserPromptSubmit | same | same |
| `config_edit_midsession` | agent edits CLAUDE.md / AGENTS.md / .mcp.json / settings | PreToolUse | cached prefix invalidated | Edit config between sessions |
| `long_turn` | 30+ tool calls in one turn | PostToolUse | many calls, each re-sending context | Agent may be looping |
| `large_tool_output` | one tool output > 20K chars | PostToolUse | large new context, re-read every call | Narrow the command / read a line range |
| `repeated_read` | same file read 3+ times in a session | PostToolUse | duplicate context | Read once, reference it |
| `retry_loop` | same shell command 3+ times in a session | PostToolUse | wasted calls | Change approach after 3 tries |
| `session_cost` | session passes $2 / $5 / $10 (Claude) | Stop → worker | — | Receipt: cost, calls, context |
| `cache_rebuild` | previous cached prefix not read back | Stop → worker | rebuild at 1.25–2× | Cause: pause > TTL or prefix changed |
| `large_context` | context passes 150K tokens | Stop → worker | every call re-sends it | /clear or new session |

## How prompt rules decide (word lists + length + structure)
Exact phrase lists miss rewording, so prompt rules combine three signals:
- **Words:** each word is checked against acknowledgement words / Korean stems / politeness endings,
  not the whole phrase ("넵넵", "계속해 주세요", "sounds good, proceed" all match).
- **Length:** a prompt of ≤ 12 characters and ≤ 3 words is treated as a bare acknowledgement even with
  unknown slang ("gogo", "ㄱㄱ씽"), unless it carries content.
- **Structure / content signals:** file names, code, `()`, identifiers (snake_case, camelCase), URLs,
  `#123`, numbers and action verbs (add, fix, run, 추가, 수정, 실행 …) mark a real instruction, so
  "fix login.ts" or "run pytest" are never flagged.
- **Corrections:** a cue at the start ("no", "not quite", "still failing", "아닌데", "다시", "취소") or
  anywhere ("방금 거 취소", "I said"), excluding requests to build something ("취소 버튼 추가해줘",
  "write a rollback script") and ordinary phrasing ("no need to …", "stop the dev server").
Regression set: `tests/test_rule_variants.py` (54 phrasings, all must pass). Misses only mean a
missing notification; they never affect the AI.

## Architecture
```
Claude Code / Devin CLI
   │ hook JSON on stdin
   ▼
coach/hook.py  (fast path, prints nothing, exit 0)
   ├─ rules.py  (pure functions on the prompt / tool event)
   ├─ state.py  (~/.cost-coach/sessions/<id>.json)
   └─ on Stop: spawn detached  coach/worker.py <session> <transcript>     (Claude Code)
   │                               ├─ incremental parse (byte offset) → cost, context, rebuilds
   │                               └─ notify.py  macOS notification (+ optional webhook)
   └─ on Stop: arm             coach/expiry.py <session> <host>         (one timer per session)
                                   └─ sleeps until stop + TTL; if still idle and context ≥ 50K → "Cache expired"
cost-coach CLI ─ status · sessions · mark · compare · weekly · devin add/import · habits · doctor · notify
launchd ─ weekly `weekly` (default Fri 10:00 local; `cost-coach schedule` to change/off) · daily `notify` (opt-in)
```

## Language
All user-facing text (notifications, CLI output, reports, docs) is English. The rule keyword lists in
`coach/rules.py` and their tests also contain Korean words, because they must recognise prompts that
developers type in Korean (e.g. a bare "continue" written in Korean). These are detection data only
and never appear in output.

