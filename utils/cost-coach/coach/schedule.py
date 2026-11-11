"""Weekly retrospective schedule (macOS launchd). Times are the Mac's local time.

  cost-coach schedule "Fri 10:00"   set / change
  cost-coach schedule off           turn off
  cost-coach schedule               show current
"""
import os
import plistlib
import re
import subprocess
import sys

LABEL = "com.cost-coach.weekly"
DEFAULT = "Fri 10:00"
DAYS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6,
        "일": 0, "월": 1, "화": 2, "수": 3, "목": 4, "금": 5, "토": 6}
NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def plist_path():
    return os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")


def parse(spec: str):
    """'Fri 10:00', 'friday 9:30' -> (weekday, hour, minute). Korean day names are also accepted."""
    m = re.match(r"^\s*([A-Za-z]+|[일월화수목금토])[a-z요일]*\s+(\d{1,2}):(\d{2})\s*$", spec or "")
    if not m:
        raise ValueError('use a day and a time, e.g. "Fri 10:00" or "Mon 09:30"')
    day = m.group(1).lower()
    wd = DAYS.get(day[:3]) if day[:3] in DAYS else DAYS.get(day[:1])
    h, mi = int(m.group(2)), int(m.group(3))
    if wd is None or not (0 <= h < 24 and 0 <= mi < 60):
        raise ValueError('use a day and a time, e.g. "Fri 10:00" or "Mon 09:30"')
    return wd, h, mi


def current():
    try:
        with open(plist_path(), "rb") as f:
            c = plistlib.load(f)["StartCalendarInterval"]
        return f"{NAMES[c['Weekday']]} {c['Hour']:02d}:{c['Minute']:02d}"
    except (OSError, KeyError, ValueError, plistlib.InvalidFileException):
        return None


def _launchctl(*args):
    if os.environ.get("COACH_NO_LAUNCHCTL") or sys.platform != "darwin":
        return
    subprocess.run(["launchctl", *args, plist_path()], capture_output=True)


def set_weekly(spec: str, python: str, cli: str, home: str):
    wd, h, mi = parse(spec)
    os.makedirs(os.path.dirname(plist_path()), exist_ok=True)
    _launchctl("unload")
    with open(plist_path(), "wb") as f:
        plistlib.dump({
            "Label": LABEL,
            "ProgramArguments": [python, "-I", cli, "weekly"],
            "EnvironmentVariables": {"COACH_HOME": home},
            "StartCalendarInterval": {"Weekday": wd, "Hour": h, "Minute": mi},
            "StandardOutPath": "/dev/null", "StandardErrorPath": "/dev/null",
        }, f)
    _launchctl("load")
    return f"{NAMES[wd]} {h:02d}:{mi:02d}"


def off():
    if os.path.exists(plist_path()):
        _launchctl("unload")
        os.remove(plist_path())
        return True
    return False


HINT = ('Change the day/time anytime: cost-coach schedule "Mon 09:30" '
        '(your Mac\'s local time) · turn off: cost-coach schedule off')
