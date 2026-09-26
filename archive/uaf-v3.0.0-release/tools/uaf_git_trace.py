#!/usr/bin/env python3
"""UAAF v1.3 Git traceability.

Read-only Git inspection plus an explicit baseline snapshot. No history is rewritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def run_git(root: Path, args: list[str], timeout: float = 4.0) -> tuple[int, str, str]:
    try:
        p = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, timeout=timeout, check=False)
        return p.returncode, p.stdout.rstrip("\n"), p.stderr.strip()
    except FileNotFoundError:
        return 127, "", "git not installed"
    except subprocess.TimeoutExpired:
        return 124, "", "git command timed out"


def repo_info(root: Path) -> dict[str, Any]:
    code, head, err = run_git(root, ["rev-parse", "HEAD"])
    if code != 0:
        raise SystemExit(f"GIT_ERROR {err or 'not a git repository'}")
    _, branch, _ = run_git(root, ["branch", "--show-current"])
    _, status, _ = run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    paths = []
    for line in status.splitlines():
        if len(line) >= 3:
            raw = line[3:]
            if " -> " in raw:
                raw = raw.split(" -> ")[-1]
            paths.append(raw)
    return {
        "repository": str(root),
        "head": head,
        "branch": branch or "DETACHED",
        "dirty": bool(paths),
        "dirty_paths": sorted(set(paths)),
    }


def commit_subjects(root: Path, base: str | None = None) -> list[dict[str, str]]:
    args = ["log", "--format=%H%x09%aI%x09%s"]
    if base:
        args.append(f"{base}..HEAD")
    code, out, err = run_git(root, args)
    if code != 0:
        raise SystemExit(f"GIT_LOG_ERROR {err or 'unable to read git log'}")
    rows = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            rows.append({"hash": parts[0], "committed_at": parts[1], "subject": parts[2]})
    return rows


def changed_files(root: Path, base: str | None = None) -> list[str]:
    paths: set[str] = set()
    args = ["diff", "--name-only"]
    if base:
        args.append(f"{base}...HEAD")
    else:
        args.append("HEAD")
    args.append("--")
    code, out, _ = run_git(root, args)
    if code == 0:
        paths.update(x.strip() for x in out.splitlines() if x.strip())
    # Include uncommitted and untracked worktree changes as part of traceability.
    _, status, _ = run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    for line in status.splitlines():
        if len(line) >= 3:
            raw = line[3:]
            if " -> " in raw:
                raw = raw.split(" -> ")[-1]
            if raw.strip():
                paths.add(raw.strip())
    return sorted(paths)


def write_baseline(root: Path) -> Path:
    info = repo_info(root)
    payload = {
        "schema_version": "1.3",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        **info,
    }
    out = root / ".ai/health/GIT-BASELINE.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return out


def trace(root: Path, task_id: str | None, base: str | None) -> dict[str, Any]:
    baseline = root / ".ai/health/GIT-BASELINE.yaml"
    base_ref = base
    if not base_ref and baseline.exists():
        data = yaml.safe_load(baseline.read_text(encoding="utf-8")) or {}
        base_ref = data.get("head")
    files = changed_files(root, base_ref)
    commits = commit_subjects(root, base_ref)
    task_exists = None
    matching_commits: list[dict[str, str]] = []
    if task_id:
        task_exists = bool(list((root / ".ai/tasks").rglob(f"{task_id}*"))) if (root / ".ai/tasks").exists() else False
        matching_commits = [c for c in commits if task_id in c.get("subject", "")]
    payload = {
        "schema_version": "1.3",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "task_id": task_id,
        "task_artifact_exists": task_exists,
        "commits_matching_task": matching_commits,
        "base": base_ref,
        "head": repo_info(root)["head"],
        "changed_files": files,
        "commits": commits,
    }
    payload["trace_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.3 Git traceability")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["status", "snapshot", "trace"], nargs="?", default="status")
    p.add_argument("--task")
    p.add_argument("--base")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    root = Path(args.path).resolve()
    if args.action == "status":
        payload = repo_info(root)
    elif args.action == "snapshot":
        out = write_baseline(root)
        payload = {"status": "SNAPSHOT", "path": str(out)}
    else:
        payload = trace(root, args.task, args.base)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
