# cost-coach — Install Guide

cost-coach shows a macOS notification when you hit a habit that makes AI coding more expensive
(Claude Code, Devin CLI), and measures what you actually spend. **It adds nothing to the AI's
context, never blocks it, and never changes its commands**, so it cannot add AI cost or alter results.

Time: about 3 minutes. Requirements: macOS, `python3` 3.8+ (comes with Xcode Command Line Tools).

---

## 1. Install

```bash
git clone https://github.com/ssoya010-hash/cost-saving-ai && cd cost-saving-ai/utils/cost-coach
./install.sh --dry-run                        # optional: preview the change, writes nothing
./install.sh                                  # all Claude Code sessions on this Mac
                                              # + weekly retro every Friday 10:00 (--weekly "Mon 09:30" or --no-weekly)
```

Also using **Devin CLI**? Add one of:

```bash
./install.sh --devin-user                     # all Devin CLI sessions
./install.sh --devin ~/src/my-repo            # one repo only
```

(Devin CLI also reads `~/.claude/settings.json`, so step 1 already covers it. Installing in more than
one place is harmless: duplicate events are ignored.)

Add the command to your PATH if the installer says so:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

## 2. Check

```bash
cost-coach doctor        # every line should show ✓
cost-coach test-notify   # you should see a notification
```

No notification? Open **System Settings → Notifications → Script Editor** and allow notifications
(cost-coach uses macOS' built-in `osascript`). For nicer notifications: `brew install terminal-notifier`.

Restart open Claude Code / Devin CLI sessions so they load the hooks.

## 3. Use

You do not need to do anything. Work as usual; a notification appears only when something costly
happens, at most once per rule per 10 minutes and 6 per hour.

| Notification | What it means | What to do |
|---|---|---|
| **Empty follow-up** | You sent only a bare acknowledgement ("ok", "continue", "go ahead") | Put the next instruction in the same message |
| **Correction loop** | 2+ corrections in a row | Restate the requirement once, or start a new session |
| **Too many tasks** | 4+ tasks in one prompt | One task per session |
| **Plan first** | Large request with no files or symbols named | Ask for a plan, name the files |
| **Cache expired** | Your session has been idle longer than the prompt cache lives (5 min by default; 1 h if your setup uses it), so the **next** message re-writes the whole context. Arrives **before** you resume, with the estimated cost | Same task: continue. New task: start a new session with a short summary |
| **Config edit mid-session** | The agent edits CLAUDE.md / AGENTS.md / MCP / settings | Make those edits between sessions |
| **Long turn** | 30+ tool calls in one turn | Check whether the agent is looping |
| **Large output** | A tool returned > 20K characters | Ask for a narrower command or a line range |
| **Repeated read / Retry loop** | Same file read or same command run 3+ times | Point the agent to what it already has, change approach |
| **Session receipt** ¹ | Session cost passed $2 / $5 / $10 | Consider `/clear` or a new session for the next task |
| **Cache rebuilt** ¹ | The cached context was re-written in full | Avoid long pauses mid-session; keep config stable |
| **Large context** ¹ | Context passed 150K tokens | `/clear` or a new session |

¹ Claude Code only: these need Claude Code's local session log to compute cost and context size.
Devin CLI gets all the other notifications. For **Cache expired** on Devin CLI the context size is
estimated from what the hooks saw, and the cache lifetime is assumed to be 5 minutes (Devin uses a
prompt cache, but does not document its lifetime; change `devin_cache_ttl_s` if you learn otherwise). Devin cloud sessions (app.devin.ai) run on Cognition's
machines, so local notifications cannot reach them; log their ACU with `cost-coach devin add`.

## 4. Measure your savings

```bash
cost-coach status                 # last 7 days: spend, cache hit, rebuilds and why, tips
cost-coach sessions               # most expensive sessions today
cost-coach mark "started cost-coach"   # mark when you change something
cost-coach compare                # after 1–2 weeks: median $/session before vs. after
cost-coach habits                 # how often each anti-pattern happened
```

Devin: log ACU per session from `/session-stats` or Session Insights:

```bash
cost-coach devin add 3.2 --session <devin-session-id>
cost-coach devin import consumption.csv     # columns: date, acu, session, note
```

### Weekly retrospective (on by default: **Friday 10:00**, your Mac's local time)

Every Friday at 10:00 you get a notification and a report in `~/.cost-coach/reports/`:
this week vs last week, money lost to cache rebuilds, your top habits, and 3 actions for next week.
Friday morning is chosen so the week's work is complete and there is still time to read it.
If the Mac is asleep at that time, it arrives when the Mac wakes.

```bash
cost-coach weekly                    # open the retro now
cost-coach schedule                  # show when it arrives
cost-coach schedule "Mon 09:30"      # change day/time (also "friday 9:30")
cost-coach schedule off              # turn it off
```

Optional daily summary at 9:30: `./install.sh --daily 09:30`

## 5. Settings (`~/.cost-coach/config.json`)

```json
{
  "quiet_hours": "22-08",
  "muted_rules": ["bundled_tasks"],
  "sound": "",
  "max_notifications_per_hour": 6,
  "price_multiplier": 1.0
}
```

```bash
cost-coach mute bundled_tasks     # silence one rule
cost-coach pause | resume         # turn everything off/on without uninstalling
```

`price_multiplier` applies your AWS/Bedrock contract discount to the dollar figures.

## 6. Uninstall

```bash
./install.sh --uninstall          # restores your settings.json exactly as before
./install.sh --uninstall --all    # if you installed in several places (Claude + Devin)
rm -rf ~/.cost-coach              # also delete history (optional)
```

---

## FAQ

**Does it cost AI tokens or slow the agent down?** No. The hooks print nothing (so nothing is added
to the AI's context), take about 0.15 s, and run cost analysis in a background process after each
turn. `cost-coach doctor` verifies this on your machine.

**Does it send my code or prompts anywhere?** No. Everything stays in `~/.cost-coach` on your Mac.
The only network call is an optional Slack webhook you configure yourself, and it sends summary
numbers only.

**What does it read and keep?** Hook events from Claude Code / Devin CLI, and Claude Code's local
session logs in `~/.claude/projects` (it uses only the token counts) to compute cost.
Prompt text is checked by local rules and **not stored**. To detect repeats, the per-session state in
`~/.cost-coach/sessions/` keeps file paths the agent read and the first 200 characters of shell
commands; these files are deleted automatically after 14 days (`cost-coach prune` to do it now).

**Can it break my setup?** The installer backs up every file it changes
(`settings.json.cost-coach.bak`), refuses to touch invalid JSON, and only removes its own entries on
uninstall. If the hook itself fails, it exits silently and the agent continues.

**Optional extras (off by default, they have side effects):**
`"agent_hints": true` sends a one-line hint to the agent (costs a few tokens);
`"mode": "block"` blocks bare "ok" prompts (prefix `!` to send anyway);
`./install.sh --devin <repo> --rules` adds cost-saving rules to the repo's AGENTS.md
(loaded every session, ~400 tokens).
