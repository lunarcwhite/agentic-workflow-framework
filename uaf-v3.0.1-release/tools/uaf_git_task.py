#!/usr/bin/env python3
"""UAAF v1.4 semantic Git↔Task traceability."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml


def run_git(root: Path, args: list[str]) -> str:
    p = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False, timeout=5)
    if p.returncode != 0:
        raise SystemExit(f"GIT_ERROR {p.stderr.strip() or 'git command failed'}")
    return p.stdout


def normalize(p: str) -> str:
    return p.replace("\\", "/").removeprefix("./")


def find_task(root: Path, task_id: str) -> tuple[Path | None, dict[str, Any]]:
    tasks = root / ".ai/tasks"
    if not tasks.exists():
        return None, {}
    for p in tasks.rglob(f"{task_id}*.yaml"):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if str(data.get("id", "")) == task_id:
            return p, data
    return None, {}


def git_changed_with_untracked(root: Path, base: str | None) -> tuple[list[str], set[str]]:
    if base:
        out = run_git(root, ["diff", "--name-only", f"{base}...HEAD", "--"])
    else:
        out = run_git(root, ["diff", "--name-only", "HEAD", "--"])
    paths = {normalize(x) for x in out.splitlines() if x.strip()}
    untracked: set[str] = set()
    status = run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    for line in status.splitlines():
        if len(line) >= 3:
            raw = line[3:]
            if " -> " in raw:
                raw = raw.split(" -> ")[-1]
            if raw.strip():
                rel = normalize(raw)
                paths.add(rel)
                if line.startswith("??"):
                    untracked.add(rel)
    return sorted(paths), untracked


def git_changed(root: Path, base: str | None) -> list[str]:
    return git_changed_with_untracked(root, base)[0]


def trace(root: Path, task_id: str, base: str | None = None) -> dict[str, Any]:
    task_path, task = find_task(root, task_id)
    if task_path is None:
        return {"status": "UNLINKED", "task_id": task_id, "reason": "task artifact not found", "changed_files": git_changed(root, base)}
    expected = task.get("expected_changes") or {}
    expected_files = {normalize(str(x)) for x in expected.get("files", []) or []}
    expected_modules = {normalize(str(x)).rstrip("/") for x in expected.get("modules", []) or []}
    changes, untracked = git_changed_with_untracked(root, base)
    explicit_uaf = {normalize(x) for x in expected_files if normalize(x).startswith(".ai/")}
    bootstrap_untracked = {"AGENTS.md", "CHANGELOG.md", "README.md"}
    semantic_changes = [
        p for p in changes
        if not (p.startswith(".ai/") and p not in explicit_uaf)
        and not (p in bootstrap_untracked and p in untracked and p not in expected_files)
    ]
    covered: list[str] = []
    uncovered: list[str] = []
    for path in semantic_changes:
        exact = path in expected_files
        module = any(path == m or path.startswith(m + "/") for m in expected_modules)
        if exact or module:
            covered.append(path)
        else:
            uncovered.append(path)
    subjects = run_git(root, ["log", "--format=%H%x09%s", "-20"]).splitlines()
    linked_commits = [line for line in subjects if task_id.lower() in line.lower()]
    relation = "LINKED" if covered and (linked_commits or not uncovered) else ("PARTIAL" if covered or linked_commits else "UNLINKED")
    if not semantic_changes and linked_commits:
        relation = "LINKED"
    return {
        "status": relation,
        "task_id": task_id,
        "task_artifact": str(task_path.relative_to(root)),
        "expected_files": sorted(expected_files),
        "expected_modules": sorted(expected_modules),
        "changed_files": semantic_changes,
        "all_changed_files": changes,
        "covered_files": covered,
        "uncovered_files": uncovered,
        "linked_commits": [{"hash": s.split("\t", 1)[0], "subject": s.split("\t", 1)[1] if "\t" in s else ""} for s in linked_commits],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.4 semantic Git↔Task traceability")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["trace"], nargs="?", default="trace")
    p.add_argument("--task", required=True)
    p.add_argument("--base")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    payload = trace(Path(args.path).resolve(), args.task, args.base)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload["status"])
        print(f"TASK {payload['task_id']}")
        print(f"CHANGED {len(payload.get('changed_files', []))}")
        print(f"COVERED {len(payload.get('covered_files', []))}")
        print(f"UNCOVERED {len(payload.get('uncovered_files', []))}")
        print(f"COMMITS {len(payload.get('linked_commits', []))}")
    raise SystemExit(0 if payload["status"] in {"LINKED", "PARTIAL"} else 1)


if __name__ == "__main__":
    main()
