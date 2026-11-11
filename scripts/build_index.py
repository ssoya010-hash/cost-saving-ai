#!/usr/bin/env python3
"""Regenerate the index tables in README.md from each entry's front matter.

Contributors never edit the index by hand: add a folder with a README.md (or a guide .md) that starts
with front matter, then run `python3 scripts/build_index.py`. CI runs it with `--check`.

Front matter (between two `---` lines, simple `key: value` pairs):
    title:   Short name
    summary: One line
    status:  draft | active | done | proposed     (optional)
    ...section-specific keys, see SECTIONS below
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")

# section -> (glob kind, columns as (header, key))
SECTIONS = {
    "guides": ("files", "guides", [("Guide", "title"), ("What you get", "summary"), ("Read time", "read_time")]),
    "experiments": ("dirs", "experiments", [("Experiment", "title"), ("Question", "summary"), ("Result", "result"),
                                             ("Status", "status"), ("Date", "date")]),
    "playground": ("dirs", "playground", [("Tool", "title"), ("Acts on", "loop_step"), ("Evidence", "evidence"),
                                           ("Verdict", "verdict")]),
    "skills": ("dirs", "skills", [("Skill", "name"), ("What it does", "summary"), ("Works with", "works_with")]),
    "utils": ("dirs", "utils", [("Utility", "title"), ("What it does", "summary"), ("Status", "status")]),
    "research": ("files", "research", [("Document", "title"), ("What it covers", "summary")]),
    "design": ("files", "design", [("Document", "title"), ("What it decides", "summary")]),
}
FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def front_matter(path):
    try:
        with open(path, encoding="utf-8") as f:
            m = FM.match(f.read())
    except OSError:
        return None
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def entries(kind, folder):
    base = os.path.join(ROOT, folder)
    found = []
    if not os.path.isdir(base):
        return found
    for name in sorted(os.listdir(base)):
        if name.startswith(("_", ".")) or name == "README.md":
            continue
        p = os.path.join(base, name)
        if kind == "dirs" and os.path.isdir(p):
            target = next((os.path.join(p, f) for f in ("SKILL.md", "README.md") if os.path.exists(os.path.join(p, f))), None)
            link = f"{folder}/{name}/"
        elif kind == "files" and name.endswith(".md"):
            target, link = p, f"{folder}/{name}"
        else:
            continue
        fm = front_matter(target) if target else None
        if fm:
            found.append((link, fm))
    if kind == "dirs" and folder == "experiments":
        found.sort(key=lambda e: e[1].get("date", ""), reverse=True)
    return found


def table(section):
    kind, folder, cols = SECTIONS[section]
    rows = entries(kind, folder)
    if not rows:
        return "_Nothing here yet. Be the first: see CONTRIBUTING.md._"
    head = "| " + " | ".join(h for h, _ in cols) + " |\n|" + "---|" * len(cols)
    lines = []
    for link, fm in rows:
        cells = []
        for i, (_, key) in enumerate(cols):
            v = (fm.get(key) or "").replace("|", "\\|")
            cells.append(f"[{v or link}]({link})" if i == 0 else v)
        lines.append("| " + " | ".join(cells) + " |")
    return head + "\n" + "\n".join(lines)


def render(text):
    for section in SECTIONS:
        start, end = f"<!-- index:{section}:start -->", f"<!-- index:{section}:end -->"
        if start in text and end in text:
            a, rest = text.split(start, 1)
            _, b = rest.split(end, 1)
            text = a + start + "\n" + table(section) + "\n" + end + b
    return text


def main(argv):
    with open(README, encoding="utf-8") as f:
        cur = f.read()
    new = render(cur)
    if "--check" in argv:
        if new != cur:
            print("README index is out of date: run python3 scripts/build_index.py")
            return 1
        print("README index is up to date")
        return 0
    with open(README, "w", encoding="utf-8") as f:
        f.write(new)
    print("README index updated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
