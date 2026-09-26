#!/usr/bin/env python3
"""Aggregate UAAF diagnostic checks without mutating the project."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent


def run_tool(script: str, path: Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(TOOLS_DIR / script), str(path), *extra],
        text=True,
        capture_output=True,
    )
    return proc.returncode, proc.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run UAAF aggregate diagnostics")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--level", choices=["minimal", "core", "standard", "full"], default="standard")
    parser.add_argument("--strict", action="store_true", help="treat validator warnings as failures")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.path).resolve()

    check_args = ["--level", args.level]
    if args.strict:
        check_args.append("--strict")
    check_rc, check_out = run_tool("uaf_check.py", root, *check_args)
    rce_rc, rce_out = run_tool("uaf_reconcile.py", root)
    mig_rc, mig_out = run_tool("uaf_migration_check.py", root)

    payload = {
        "status": "PASS" if check_rc == 0 and rce_rc == 0 and mig_rc == 0 else "FAIL",
        "checks": {
            "conformance": {"returncode": check_rc, "output": check_out},
            "reality": {"returncode": rce_rc, "output": rce_out},
            "migration": {"returncode": mig_rc, "output": mig_out},
        },
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload["status"])
        print(f"CONFORMANCE {check_rc}")
        print(f"REALITY {rce_rc}")
        print(f"MIGRATION {mig_rc}")
    raise SystemExit(0 if payload["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
