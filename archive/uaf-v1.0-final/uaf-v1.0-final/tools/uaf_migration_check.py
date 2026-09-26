#!/usr/bin/env python3
"""Validate UAAF migration record shape without applying migrations."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REQUIRED_SECTIONS = [
    "from",
    "to",
    "changes",
    "compatibility",
    "automatic changes",
    "manual changes",
    "validation",
    "rollback",
    "memory impact",
    "decision impact",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate UAAF migration records")
    parser.add_argument("path", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.path).resolve()
    folder = root / ".ai/migrations"
    errors = []
    checked = 0
    if not folder.exists():
        print("NOT_APPLICABLE")
        return
    for path in folder.glob("MIGRATION-*.md"):
        checked += 1
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for section in REQUIRED_SECTIONS:
            if section not in text:
                errors.append(f"MIG-001 {path.name}: missing {section}")
        if not re.search(r"\b(additive|compatible|breaking)\b", text):
            errors.append(f"MIG-002 {path.name}: missing compatibility classification")
    print("FAIL" if errors else "PASS")
    for err in errors: print("ERROR", err)
    print(f"INFO checked={checked}")
    raise SystemExit(1 if errors else 0)

if __name__ == "__main__":
    main()
