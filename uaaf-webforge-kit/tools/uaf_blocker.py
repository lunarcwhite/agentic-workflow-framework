#!/usr/bin/env python3
"""UAAF Blocker and Anomaly Tracker.

Allows agents to quickly and durably record pre-existing defects, blockers,
or environment anomalies in .ai/memory/STATE.md without violating task scope.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


def find_state_file(start: Path) -> Path | None:
    curr = start.resolve()
    for parent in [curr, *curr.parents]:
        state = parent / ".ai/memory/STATE.md"
        if state.is_file():
            return state
    return None


def add_blocker(state_path: Path, message: str, task: str | None = None) -> None:
    text = state_path.read_text(encoding="utf-8")

    # 1. Increment version
    v_match = re.search(r"^version:\s*(\d+)", text, re.MULTILINE)
    version = int(v_match.group(1)) + 1 if v_match else 1
    if v_match:
        text = re.sub(r"^version:\s*\d+", f"version: {version}", text, flags=re.MULTILINE)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = re.sub(r"^updated_by:.*$", "updated_by: agent", text, flags=re.MULTILINE)
    text = re.sub(r"^updated_at:.*$", f"updated_at: '{now_iso}'", text, flags=re.MULTILINE)

    # 2. Format blocker entry
    prefix = f"[{task}] " if task else ""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"- {prefix}({date_str}) {message}"

    # 3. Insert under ## Known blockers
    blockers_header = "## Known blockers"
    if blockers_header in text:
        parts = text.split(blockers_header, 1)
        header_part = parts[0] + blockers_header + "\n"
        rest = parts[1]

        lines = rest.splitlines(keepends=True)
        new_lines = []
        replaced = False
        inserted = False

        for line in lines:
            if line.strip() == "- None recorded." and not replaced:
                new_lines.append(f"{entry}\n")
                replaced = True
                inserted = True
            elif line.startswith("## ") and not inserted:
                new_lines.append(f"{entry}\n\n")
                new_lines.append(line)
                inserted = True
            else:
                new_lines.append(line)

        if not inserted:
            new_lines.append(f"{entry}\n")

        text = header_part + "".join(new_lines)
    else:
        text += f"\n\n## Known blockers\n{entry}\n"

    state_path.write_text(text, encoding="utf-8")
    print(f"[UAAF] Recorded blocker in {state_path} (v{version}): {entry}")


def list_blockers(state_path: Path) -> None:
    text = state_path.read_text(encoding="utf-8")
    blockers_header = "## Known blockers"
    if blockers_header not in text:
        print("No Known blockers section found.")
        return
    section = text.split(blockers_header, 1)[1]
    lines = []
    for line in section.splitlines():
        if line.startswith("## "):
            break
        if line.strip():
            lines.append(line)
    print("\n".join(lines) if lines else "- None recorded.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="uaf blocker", description="UAAF Blocker Tracking Utility")
    parser.add_argument("message", nargs="?", default=None, help="Blocker or anomaly description")
    parser.add_argument("--task", "-t", default=None, help="Associated Task ID (e.g. TASK-0001)")
    parser.add_argument("--list", "-l", action="store_true", help="List active blockers")
    parser.add_argument("--path", "-p", default=".", help="Target directory (defaults to current dir)")

    args = parser.parse_args()
    state_file = find_state_file(Path(args.path))
    if not state_file:
        print("[UAAF] Error: .ai/memory/STATE.md not found in current directory or parents.", file=sys.stderr)
        sys.exit(1)

    if args.list or args.message is None:
        if args.message:
            add_blocker(state_file, args.message, args.task)
        else:
            list_blockers(state_file)
    else:
        add_blocker(state_file, args.message, args.task)


if __name__ == "__main__":
    main()
