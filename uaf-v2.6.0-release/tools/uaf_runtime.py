#!/usr/bin/env python3
"""UAAF v1.3 runtime verification.

Runs explicit, allowlisted commands without shell interpolation and records an
observable receipt. Runtime verification is disabled by default unless policy
allows the command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

POLICY = ".ai/verification/RUNTIME-POLICY.yaml"


def load_policy(root: Path) -> dict[str, Any]:
    path = root / POLICY
    if not path.exists():
        return {"enabled": False, "allow": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {"enabled": False, "allow": []}


def command_key(parts: list[str]) -> str:
    # Human-readable canonical form preserving argv tokens.
    return " ".join(parts)


def parse_allow_entry(entry: Any) -> list[str] | None:
    if isinstance(entry, list):
        return [str(x) for x in entry]
    if isinstance(entry, str):
        try:
            return shlex.split(entry, posix=True)
        except ValueError:
            return None
    return None


def allowed(parts: list[str], policy: dict[str, Any]) -> bool:
    if not policy.get("enabled", False):
        return False
    for entry in policy.get("allow", []) or []:
        parsed = parse_allow_entry(entry)
        if parsed == parts:
            return True
    return False


def write_receipt(root: Path, payload: dict[str, Any]) -> Path:
    rid = "RTV-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    payload["receipt_id"] = rid
    payload["receipt_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    out = root / ".ai/evidence" / f"{rid}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.3 runtime verification")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["policy", "run"], nargs="?", default="policy")
    p.add_argument("--command", action="append", default=[])
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--task")
    args = p.parse_args()
    root = Path(args.path).resolve()
    policy = load_policy(root)
    if args.action == "policy":
        print(yaml.safe_dump(policy, sort_keys=False))
        return
    if not args.command:
        raise SystemExit("--command is required")
    parts = shlex.split(args.command[0], posix=True)
    if not parts:
        raise SystemExit("EMPTY_COMMAND")
    if not allowed(parts, policy):
        raise SystemExit("RUNTIME_COMMAND_NOT_ALLOWED")
    started = time.monotonic()
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    try:
        proc = subprocess.run(parts, cwd=root, text=True, capture_output=True, timeout=args.timeout, shell=False, check=False)
        status = "VERIFIED" if proc.returncode == 0 else "FAILED"
        payload = {
            "schema_version": "1.3",
            "type": "runtime_verification",
            "status": status,
            "task_id": args.task,
            "command": parts,
            "started_at": ts,
            "duration_seconds": round(time.monotonic() - started, 4),
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-12000:],
            "method": "allowlisted_subprocess_shell_false",
        }
    except subprocess.TimeoutExpired as exc:
        payload = {
            "schema_version": "1.3",
            "type": "runtime_verification",
            "status": "BLOCKED",
            "task_id": args.task,
            "command": parts,
            "started_at": ts,
            "duration_seconds": round(time.monotonic() - started, 4),
            "exit_code": None,
            "stdout": (exc.stdout or "")[-12000:],
            "stderr": (exc.stderr or "")[-12000:],
            "method": "allowlisted_subprocess_shell_false",
            "reason": "timeout",
        }
    out = write_receipt(root, payload)
    print(f"{payload['status']} {out}")
    if payload["status"] == "FAILED":
        raise SystemExit(1)
    if payload["status"] == "BLOCKED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
