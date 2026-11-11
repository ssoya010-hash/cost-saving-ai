#!/usr/bin/env bash
# cost-coach installer (macOS; Linux works without notifications). Needs only python3.
#
#   ./install.sh                         = --claude-user (all Claude Code sessions on this Mac)
#   ./install.sh --claude-user           -> ~/.claude/settings.json            (Devin CLI also reads this file)
#   ./install.sh --devin-user            -> ~/.config/devin/config.json        (all Devin CLI sessions)
#   ./install.sh --claude <repo>         -> <repo>/.claude/settings.local.json (one repo, not committed)
#   ./install.sh --devin <repo>          -> <repo>/.devin/hooks.v1.json        (one repo)
#   ./install.sh --uninstall [same target flag]
#   ./install.sh --uninstall --all       remove from every user-level location + given repos (--claude/--devin)
#
# Options:
#   --daily HH:MM     daily cost summary notification (macOS launchd)
#   --weekly "Fri 10:00"  when the weekly retrospective arrives (default Fri 10:00, Mac local time)
#   --no-weekly       do not schedule the weekly retrospective
#   --webhook URL     Slack-compatible webhook for `cost-coach post` / daily summary
#   --rules           also add the cost-saving rules block to <repo>/AGENTS.md (repo targets only).
#                     Off by default: AGENTS.md is loaded into every session, so it costs ~400 tokens.
#   --dry-run         show what would change, change nothing
#
# Safe by design: hooks print nothing to the agent, never block, never rewrite commands.
# Every settings file is backed up to <file>.cost-coach.bak before it is changed.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SELF="$HERE/$(basename "$0")"
COACH_HOME="${COACH_HOME:-$HOME/.cost-coach}"
APP="$COACH_HOME/app"
PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "python3 not found. Install Xcode Command Line Tools: xcode-select --install"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || { echo "python3 >= 3.8 required"; exit 1; }

KIND=""; TARGET=""; UNINSTALL=0; DAILY=""; WEBHOOK=""; RULES=0; DRY=0; ALL=0; WEEKLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --claude-user) KIND=claude-user; shift;;
    --devin-user)  KIND=devin-user; shift;;
    --claude)      KIND=claude; TARGET="${2:?repo path}"; shift 2;;
    --devin)       KIND=devin; TARGET="${2:?repo path}"; shift 2;;
    --uninstall)   UNINSTALL=1; shift;;
    --all)         ALL=1; shift;;
    --daily)       DAILY="${2:?HH:MM}"; shift 2;;
    --weekly)      WEEKLY="${2:?Fri 10:00}"; shift 2;;
    --no-weekly)   WEEKLY="off"; shift;;
    --webhook)     WEBHOOK="${2:?url}"; shift 2;;
    --rules)       RULES=1; shift;;
    --dry-run)     DRY=1; shift;;
    -h|--help)     sed -n '2,19p' "$0"; exit 0;;
    *) echo "unknown option: $1 (see --help)"; exit 1;;
  esac
done
if [ $ALL = 1 ]; then
  [ $UNINSTALL = 1 ] || { echo "--all only works with --uninstall"; exit 1; }
  ARGS=(); [ $DRY = 1 ] && ARGS+=(--dry-run)
  for k in --claude-user --devin-user; do bash "$SELF" --uninstall "$k" "${ARGS[@]+"${ARGS[@]}"}"; done
  if [ -n "$TARGET" ]; then
    bash "$SELF" --uninstall --claude "$TARGET" "${ARGS[@]+"${ARGS[@]}"}"; bash "$SELF" --uninstall --devin "$TARGET" "${ARGS[@]+"${ARGS[@]}"}"
  fi
  exit 0
fi
KIND="${KIND:-claude-user}"
if [ -n "$TARGET" ]; then
  [ -d "$TARGET" ] || { echo "not a directory: $TARGET"; exit 1; }
  TARGET="$(cd "$TARGET" && pwd)"
fi
run() { if [ $DRY = 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

case "$KIND" in
  claude-user) FILE="$HOME/.claude/settings.json";            SHAPE=nested; EDITM="Edit|Write|MultiEdit";;
  devin-user)  FILE="$HOME/.config/devin/config.json";        SHAPE=nested; EDITM="^(edit|write|apply_patch)$";;
  claude)      FILE="$TARGET/.claude/settings.local.json";    SHAPE=nested; EDITM="Edit|Write|MultiEdit";;
  devin)       FILE="$TARGET/.devin/hooks.v1.json";           SHAPE=flat;   EDITM="^(edit|write|apply_patch)$";;
esac
ACTION=install; [ $UNINSTALL = 1 ] && ACTION=uninstall
if [ $UNINSTALL = 0 ] && [ "$KIND" != claude-user ] && grep -q "coach/hook.py" "$HOME/.claude/settings.json" 2>/dev/null; then
  echo "note    -> already installed in ~/.claude/settings.json, which Devin CLI also reads."
  echo "           This extra install is not needed (duplicate events are ignored either way)."
fi
HOOK_CMD="\"$PY\" -I \"$APP/coach/hook.py\""

# 1) app
if [ $UNINSTALL = 0 ]; then
  run mkdir -p "$APP"
  run rm -rf "$APP/coach"
  run cp -R "$HERE/coach" "$APP/coach"
  [ $DRY = 1 ] || find "$APP/coach" -name __pycache__ -prune -exec rm -rf {} +
  echo "app     -> $APP"
fi

# 2) config (keeps existing values)
if [ $UNINSTALL = 0 ] && [ $DRY = 0 ]; then
"$PY" -I - "$COACH_HOME/config.json" "$WEBHOOK" <<'EOF'
import json, os, sys
p, hook = sys.argv[1], sys.argv[2]
c = {}
if os.path.exists(p):
    try: c = json.load(open(p))
    except ValueError: os.replace(p, p + ".broken")
if hook: c["webhook_url"] = hook
os.makedirs(os.path.dirname(p), exist_ok=True)
json.dump(c, open(p, "w"), indent=2)
print(f"config  -> {p}")
EOF
fi

# 3) hooks (idempotent: removes previous cost-coach entries first; backup before change)
"$PY" -I - "$FILE" "$SHAPE" "$ACTION" "$HOOK_CMD" "$EDITM" "$DRY" <<'EOF'
import json, os, shutil, sys
path, shape, action, cmd, editm, dry = sys.argv[1:7]
if os.path.exists(path) and os.path.getsize(path):
    try:
        doc = json.load(open(path))
    except ValueError:
        sys.exit(f"{path} is not valid JSON; fix it first (nothing changed)")
else:
    doc = {}
hooks = doc if shape == "flat" else doc.setdefault("hooks", {})
mine = lambda h: "coach/hook.py" in h.get("command", "")
for ev in list(hooks):
    if not isinstance(hooks[ev], list):
        continue
    hooks[ev] = [g for g in hooks[ev] if not any(mine(h) for h in g.get("hooks", []))]
    if not hooks[ev]:
        del hooks[ev]
if action == "install":
    def g(matcher=None, timeout=5):
        e = {"hooks": [{"type": "command", "command": cmd, "timeout": timeout}]}
        if matcher is not None:
            e["matcher"] = matcher
        return e
    for ev, entry in (("UserPromptSubmit", g()), ("PreToolUse", g(editm)),
                      ("PostToolUse", g("")), ("Stop", g())):
        hooks.setdefault(ev, []).append(entry)
if shape != "flat" and not hooks:
    doc.pop("hooks", None)
if dry == "1":
    print(f"[dry-run] would write {path}:\n" + json.dumps(doc, indent=2)[:1500]); sys.exit(0)
bak = path + ".cost-coach.bak"
if action == "install":
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
if action == "install" and not os.path.exists(bak):     # keep the ORIGINAL, never overwrite it
    if os.path.exists(path):
        shutil.copy2(path, bak)
    else:
        open(bak, "w").write("")       # empty backup = the file did not exist before cost-coach
if action == "uninstall" and not os.path.exists(path):
    print(f"hooks   -> {path} (not installed)"); sys.exit(0)
tmp = path + ".tmp"
json.dump(doc, open(tmp, "w"), indent=2); os.replace(tmp, path)
created_by_us = action == "uninstall" and not doc and os.path.exists(bak) and not open(bak).read().strip()
if created_by_us:                      # file only existed for our hooks: remove it entirely
    for f in (path, bak):
        if os.path.exists(f):
            os.remove(f)
    print(f"hooks   -> {path} (uninstall; removed, it only held cost-coach)"); sys.exit(0)
if action == "uninstall" and os.path.exists(bak):
    try:
        cur = json.load(open(path))
        orig = json.load(open(bak))
        if cur == orig or (not cur and not orig):
            os.remove(bak)              # nothing of ours left: the backup is no longer needed
    except (OSError, ValueError):
        pass
print(f"hooks   -> {path} ({action}" + (f"; original kept at {bak})" if os.path.exists(bak) else ")"))
EOF

# 4) optional AGENTS.md rules (repo targets only, idempotent)
if [ -n "$TARGET" ] && { [ $RULES = 1 ] || [ $UNINSTALL = 1 ]; } && [ $DRY = 0 ]; then
"$PY" -I - "$TARGET/AGENTS.md" "$HERE/templates/AGENTS.md" "$ACTION" <<'EOF'
import os, re, sys
path, tpl, action = sys.argv[1:4]
cur = open(path).read() if os.path.exists(path) else ""
had = "cost-coach:begin" in cur
cur = re.sub(r"\n*<!-- (?:devin-)?cost-coach:begin -->.*?<!-- (?:devin-)?cost-coach:end -->\n?", "\n", cur, flags=re.S)
if had and action == "uninstall":
    cur = cur.rstrip("\n") + "\n" if cur.strip() else ""
if action == "install":
    cur = cur.rstrip() + ("\n\n" if cur.strip() else "") + open(tpl).read()
if action == "uninstall" and had and not cur.strip():
    os.remove(path)                    # the file only held our block
    print(f"rules   -> {path} (removed)")
elif action == "install" or had:
    open(path, "w").write(cur.lstrip("\n") if cur.strip() else "")
    print(f"rules   -> {path} ({action})")
EOF
fi

# 5) `cost-coach` command
BIN="$HOME/.local/bin"
if [ $UNINSTALL = 1 ]; then
  if [ "$KIND" = claude-user ] || [ "$KIND" = devin-user ]; then run rm -f "$BIN/cost-coach"; fi
elif [ $DRY = 0 ]; then
  mkdir -p "$BIN"
  printf '#!/bin/sh\nexec "%s" -I "%s/coach/cli.py" "$@"\n' "$PY" "$APP" > "$BIN/cost-coach"
  chmod +x "$BIN/cost-coach"; echo "command -> $BIN/cost-coach"
  case ":$PATH:" in *":$BIN:"*) ;; *) echo "note    -> add to your shell profile:  export PATH=\"\$HOME/.local/bin:\$PATH\"";; esac
fi

# 6) daily summary (macOS launchd)
PL="$HOME/Library/LaunchAgents/com.cost-coach.daily.plist"
if [ $UNINSTALL = 1 ] && [ -f "$PL" ] && [ $DRY = 0 ]; then
  launchctl unload "$PL" 2>/dev/null || true; rm -f "$PL"; echo "daily   -> removed"
fi
if [ -n "$DAILY" ] && [ $UNINSTALL = 0 ] && [ "$(uname)" = Darwin ] && [ $DRY = 0 ]; then
  H="${DAILY%%:*}"; M="${DAILY##*:}"; mkdir -p "$(dirname "$PL")"
  cat > "$PL" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.cost-coach.daily</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>-I</string><string>$APP/coach/cli.py</string><string>notify</string></array>
  <key>EnvironmentVariables</key><dict><key>COACH_HOME</key><string>$COACH_HOME</string></dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>$((10#$H))</integer><key>Minute</key><integer>$((10#$M))</integer></dict>
  <key>StandardOutPath</key><string>/dev/null</string><key>StandardErrorPath</key><string>/dev/null</string>
</dict></plist>
PLIST
  if [ -z "${COACH_NO_LAUNCHCTL:-}" ]; then launchctl unload "$PL" 2>/dev/null || true; launchctl load "$PL"; fi
  echo "daily   -> $PL ($DAILY)"
fi

# 7) weekly retrospective (macOS launchd; default Fri 10:00 local time; only on user-level installs)
PLW="$HOME/Library/LaunchAgents/com.cost-coach.weekly.plist"
if [ $UNINSTALL = 1 ] && [ -f "$PLW" ] && [ $DRY = 0 ]; then
  [ -z "${COACH_NO_LAUNCHCTL:-}" ] && { launchctl unload "$PLW" 2>/dev/null || true; }
  rm -f "$PLW"; echo "weekly  -> removed"
fi
if [ $UNINSTALL = 0 ] && [ $DRY = 0 ] && [ "$(uname)" = Darwin ] && [ "$WEEKLY" != off ]; then
  if [ -n "$WEEKLY" ] || { [ ! -f "$PLW" ] && { [ "$KIND" = claude-user ] || [ "$KIND" = devin-user ]; }; }; then
    W="${WEEKLY:-Fri 10:00}"
    COACH_HOME="$COACH_HOME" "$PY" -I "$APP/coach/cli.py" schedule "$W" | sed 's/^/weekly  -> /'
    echo "           change later: cost-coach schedule \"Mon 09:30\"  ·  off: cost-coach schedule off"
  fi
fi

if [ $UNINSTALL = 1 ] && [ $DRY = 0 ]; then
  pkill -f "$APP/coach/expiry.py" 2>/dev/null || true
fi

if [ $UNINSTALL = 1 ]; then
  echo "done. Data kept in $COACH_HOME (delete it to remove all history)."
else
  echo "done. Next: cost-coach doctor   then   cost-coach test-notify"
fi
