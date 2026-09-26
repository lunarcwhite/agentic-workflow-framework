#!/usr/bin/env python3
"""UAAF v1.3 real claim leasing.

Atomic filesystem-backed leases for multi-process agent coordination. Claims are
coordination metadata, not a replacement for Git.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

LOCK = ".ai/agents/.claims.lock"
CLAIMS = ".ai/agents/CLAIMS.yaml"


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def acquire_lock(root: Path) -> int:
    lock = root / LOCK
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"pid={os.getpid()}\ncreated={now().isoformat()}\n".encode())
        return fd
    except FileExistsError:
        # Recover only from an obviously abandoned lock. Never break a recent lock.
        try:
            age = datetime.now().timestamp() - lock.stat().st_mtime
            if age > 60:
                lock.unlink()
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"pid={os.getpid()}\ncreated={now().isoformat()}\n".encode())
                return fd
        except (FileNotFoundError, OSError):
            pass
        raise SystemExit("CLAIM_LOCKED another claims operation is active")


def release_lock(root: Path, fd: int) -> None:
    os.close(fd)
    try:
        (root / LOCK).unlink()
    except FileNotFoundError:
        pass


def load(root: Path) -> dict[str, Any]:
    path = root / CLAIMS
    if not path.exists():
        return {"schema_version": "1.3", "claims": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {"schema_version": "1.3", "claims": []}


def save_atomic(root: Path, data: dict[str, Any]) -> None:
    path = root / CLAIMS
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="CLAIMS.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(yaml.safe_dump(data, sort_keys=False))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def expire(data: dict[str, Any]) -> int:
    changed = 0
    for claim in data.get("claims", []) or []:
        if claim.get("status") == "ACTIVE":
            until = parse_ts(str(claim.get("lease_until", "")))
            if until and until <= now():
                claim["status"] = "EXPIRED"
                claim["expired_at"] = now().astimezone().isoformat(timespec="seconds")
                changed += 1
    return changed


def normalized_resource(value: str) -> str:
    value = value.replace("\\", "/").strip()
    return value[2:] if value.startswith("./") else value


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.3 claim leasing")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["status", "acquire", "release", "reclaim"], nargs="?", default="status")
    p.add_argument("--resource")
    p.add_argument("--agent")
    p.add_argument("--task")
    p.add_argument("--lease", type=int, default=900)
    p.add_argument("--claim-id")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    root = Path(args.path).resolve()
    fd = acquire_lock(root)
    try:
        data = load(root)
        changed = expire(data)
        if changed:
            save_atomic(root, data)
        claims = data.setdefault("claims", [])

        if args.action == "status":
            print(yaml.safe_dump(data, sort_keys=False))
            return
        if args.action == "reclaim":
            n = 0
            for c in claims:
                if c.get("status") == "EXPIRED" and (not args.claim_id or c.get("claim_id") == args.claim_id):
                    c["status"] = "RECLAIMABLE"
                    n += 1
            save_atomic(root, data)
            print(f"RECLAIMABLE {n}")
            return
        if args.action == "release":
            target = args.claim_id
            if not target:
                raise SystemExit("--claim-id is required for release")
            if not args.agent:
                raise SystemExit("--agent is required for release")
            found = False
            for c in claims:
                if c.get("claim_id") == target:
                    if c.get("status") != "ACTIVE":
                        raise SystemExit(f"CLAIM_NOT_ACTIVE {target}")
                    if c.get("agent") != args.agent and not args.force:
                        raise SystemExit(f"CLAIM_OWNER_MISMATCH {target}")
                    c["status"] = "RELEASED"
                    c["released_at"] = now().astimezone().isoformat(timespec="seconds")
                    found = True
                    break
            if not found:
                raise SystemExit(f"CLAIM_NOT_FOUND {target}")
            save_atomic(root, data)
            print(f"RELEASED {target}")
            return

        if not args.resource or not args.agent or not args.task:
            raise SystemExit("--resource, --agent, and --task are required for acquire")
        resource = normalized_resource(args.resource)
        for c in claims:
            if normalized_resource(str(c.get("resource", ""))) != resource:
                continue
            if c.get("status") in {"ACTIVE", "EXPIRED"}:
                raise SystemExit(f"CLAIM_CONFLICT {c.get('claim_id')} owner={c.get('agent')} status={c.get('status')}")
        stamp = now()
        claim_id = args.claim_id or f"CLM-{stamp.strftime('%Y%m%d%H%M%S')}-{os.getpid()}"
        claim = {
            "claim_id": claim_id,
            "resource": resource,
            "agent": args.agent,
            "task": args.task,
            "status": "ACTIVE",
            "acquired_at": stamp.astimezone().isoformat(timespec="seconds"),
            "lease_until": (stamp + timedelta(seconds=max(1, args.lease))).astimezone().isoformat(timespec="seconds"),
        }
        claims.append(claim)
        save_atomic(root, data)
        print(yaml.safe_dump(claim, sort_keys=False))
    finally:
        release_lock(root, fd)


if __name__ == "__main__":
    main()
