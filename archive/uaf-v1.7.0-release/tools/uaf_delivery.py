#!/usr/bin/env python3
"""UAAF v1.4 delivery gate with optional runtime-evidence enforcement."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def find_task(root: Path, task_id: str) -> tuple[Path | None, dict[str, Any]]:
    for p in (root / ".ai/tasks").rglob(f"{task_id}*.yaml") if (root / ".ai/tasks").exists() else []:
        data = load_yaml(p)
        if str(data.get("id", "")) == task_id:
            return p, data
    return None, {}


def runtime_required(task: dict[str, Any], manifest: dict[str, Any]) -> bool:
    verification = task.get("verification") or []
    if isinstance(verification, dict):
        verification = [verification]
    for item in verification:
        if isinstance(item, dict) and str(item.get("type", "")).lower() in {"runtime", "runtime_verification", "runtime-evidence"}:
            if item.get("required") is True:
                return True
    ext = manifest.get("extensions") or {}
    policy = (ext.get("runtime_evidence") or {}).get("required_for_risk") or []
    risk = (((task.get("scope") or {}).get("risk")) or "LOW").upper()
    return risk in {str(x).upper() for x in policy}


def runtime_receipts(root: Path, task_id: str) -> list[dict[str, Any]]:
    out = []
    for p in (root / ".ai/evidence").glob("RTV-*.yaml") if (root / ".ai/evidence").exists() else []:
        data = load_yaml(p)
        if str(data.get("task_id", "")) == task_id:
            data["_path"] = str(p.relative_to(root))
            out.append(data)
    return sorted(out, key=lambda x: str(x.get("verified_at") or x.get("started_at") or ""), reverse=True)


def evaluate(root: Path, task_id: str) -> dict[str, Any]:
    task_path, task = find_task(root, task_id)
    manifest = load_yaml(root / ".ai/manifest.yaml")
    checks = {"task": task_path is not None, "intent": bool(task.get("intent")), "requirements": bool(task.get("requirements")), "acceptance_criteria": bool(task.get("acceptance_criteria")), "verification_plan": bool(task.get("verification"))}
    required = runtime_required(task, manifest) if task_path else False
    receipts = runtime_receipts(root, task_id)
    runtime_status = "NOT_REQUIRED"
    if required:
        runtime_status = "VERIFIED" if any(r.get("status") == "VERIFIED" for r in receipts) else ("FAILED" if any(r.get("status") == "FAILED" for r in receipts) else "NOT_RUN")
        checks["runtime_evidence"] = runtime_status == "VERIFIED"
    else:
        checks["runtime_evidence"] = True
    critical_fail = not all(checks.values())
    status = "NOT_READY" if critical_fail else "DONE"
    return {"status": status, "task_id": task_id, "task_artifact": str(task_path.relative_to(root)) if task_path else None, "checks": checks, "runtime_required": required, "runtime_status": runtime_status, "runtime_receipts": receipts[:5]}


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.4 delivery gate")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["check"], nargs="?", default="check")
    p.add_argument("--task", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    payload = evaluate(Path(args.path).resolve(), args.task)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload["status"])
        print(f"TASK {payload['task_id']}")
        print(f"RUNTIME_REQUIRED {str(payload['runtime_required']).lower()}")
        print(f"RUNTIME_STATUS {payload['runtime_status']}")
        for name, ok in payload["checks"].items():
            print(f"CHECK {name}={'PASS' if ok else 'FAIL'}")
    raise SystemExit(0 if payload["status"] == "DONE" else 1)


if __name__ == "__main__":
    main()
