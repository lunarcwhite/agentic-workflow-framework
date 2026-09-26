#!/usr/bin/env python3
"""UAAF v1.5 Context Economics & Observability.

Read-only reporting by default. Event recording stores metadata only; prompt,
source contents, and secret values are never copied into the observability log.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "1.5"
OBS_SCHEMA_VERSION = "1.5"
TOKEN_DIVISOR = 4  # transparent heuristic: approx. 4 chars/token
MAX_DIR_FILES = 200
MAX_FILE_BYTES = 2 * 1024 * 1024


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def estimate_tokens(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return min(path.stat().st_size, MAX_FILE_BYTES) // TOKEN_DIVISOR
        except OSError:
            return 0
    total = 0
    seen = 0
    try:
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            try:
                total += min(child.stat().st_size, MAX_FILE_BYTES) // TOKEN_DIVISOR
            except OSError:
                continue
            seen += 1
            if seen >= MAX_DIR_FILES:
                break
    except OSError:
        pass
    return total


def receipt_paths(root: Path) -> list[Path]:
    base = root / ".ai"
    if not base.exists():
        return []
    return sorted(base.rglob("context-receipt*.yaml")) + sorted(base.rglob("context-receipt*.yml"))


def load_receipts(root: Path) -> list[dict[str, Any]]:
    out = []
    for path in receipt_paths(root):
        data = load_yaml(path)
        if data:
            data["_path"] = str(path.relative_to(root))
            out.append(data)
    return out


def read_events(root: Path) -> list[dict[str, Any]]:
    path = root / ".ai/observability/EVENTS.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                events.append(value)
        except json.JSONDecodeError:
            continue
    return events


def memory_stats(root: Path) -> dict[str, Any]:
    base = root / ".ai/memory/entries"
    counts: Counter[str] = Counter()
    if base.exists():
        for path in base.glob("*.md"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if text.startswith("---\n"):
                    parts = text.split("---", 2)
                    meta = yaml.safe_load(parts[1]) or {} if len(parts) >= 3 else {}
                else:
                    meta = {}
                status = str(meta.get("status", "UNKNOWN")).upper()
            except Exception:
                status = "UNKNOWN"
            counts[status] += 1
    active_total = sum(v for k, v in counts.items() if k not in {"ARCHIVED", "SUPERSEDED"})
    stale = sum(counts.get(k, 0) for k in {"STALE", "SUSPECT"})
    return {
        "entries": int(sum(counts.values())),
        "by_status": dict(sorted(counts.items())),
        "active_or_reviewable": active_total,
        "stale_or_suspect": stale,
        "stale_rate": round(stale / active_total, 4) if active_total else None,
    }


def compaction_stats(root: Path) -> dict[str, Any]:
    base = root / ".ai/memory/compaction"
    reports = sorted(base.glob("COMPACTION-*.yaml")) if base.exists() else []
    if not reports:
        return {"reports": 0, "last_duplicate_entries": 0, "last_entries_scanned": 0, "last_compaction_ratio": None}
    data = load_yaml(reports[-1])
    scanned = int(data.get("entries_scanned", 0) or 0)
    duplicates = int(data.get("duplicate_entries", 0) or 0)
    return {
        "reports": len(reports),
        "last_duplicate_entries": duplicates,
        "last_entries_scanned": scanned,
        "last_compaction_ratio": round(duplicates / scanned, 4) if scanned else None,
    }


def context_metrics(root: Path) -> dict[str, Any]:
    receipts = load_receipts(root)
    token_values: list[int] = []
    depths: Counter[str] = Counter()
    loaded_paths: list[str] = []
    declared_used = 0
    declared_total = 0
    for receipt in receipts:
        loaded = receipt.get("loaded") or []
        if isinstance(loaded, str):
            loaded = [loaded]
        estimated = receipt.get("estimated_tokens")
        if estimated is None:
            estimated = sum(estimate_tokens(root / str(item)) for item in loaded)
        token_values.append(int(estimated or 0))
        depths[str(receipt.get("context_depth", "unknown"))] += 1
        loaded_paths.extend(str(item) for item in loaded)
        usage = receipt.get("usage") or {}
        used = usage.get("used") or []
        unused = usage.get("unused") or []
        if isinstance(used, str): used = [used]
        if isinstance(unused, str): unused = [unused]
        declared_used += len(used)
        declared_total += len(used) + len(unused)

    counts = Counter(loaded_paths)
    repeated = sum(v - 1 for v in counts.values() if v > 1)
    return {
        "receipts": len(receipts),
        "estimated_tokens_total": sum(token_values),
        "estimated_tokens_average": round(sum(token_values) / len(token_values), 2) if token_values else 0,
        "estimated_tokens_max": max(token_values) if token_values else 0,
        "depth_distribution": dict(sorted(depths.items())),
        "loaded_path_occurrences": len(loaded_paths),
        "unique_loaded_paths": len(counts),
        "repeated_path_rate": round(repeated / len(loaded_paths), 4) if loaded_paths else None,
        "declared_use_rate": round(declared_used / declared_total, 4) if declared_total else None,
    }


def event_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    memory_retrievals = 0
    memory_reused = 0
    gates = 0
    gate_pass = 0
    replans = 0
    tasks = set()
    for e in events:
        typ = str(e.get("type", ""))
        if typ == "memory_reuse":
            retrieved = e.get("retrieved_ids") or []
            reused = e.get("reused_ids") or []
            memory_retrievals += len(retrieved)
            memory_reused += len(reused)
        elif typ == "gate":
            gates += 1
            if str(e.get("status", "")).upper() == "DONE":
                gate_pass += 1
        elif typ == "replan":
            replans += 1
        task_id = e.get("task_id")
        if task_id:
            tasks.add(str(task_id))
    return {
        "events": len(events),
        "memory_retrievals": memory_retrievals,
        "memory_reused": memory_reused,
        "memory_reuse_rate": round(memory_reused / memory_retrievals, 4) if memory_retrievals else None,
        "gate_events": gates,
        "gate_done_rate": round(gate_pass / gates, 4) if gates else None,
        "replans": replans,
        "replan_rate_per_task": round(replans / len(tasks), 4) if tasks else None,
        "observed_tasks": len(tasks),
    }


def policy(root: Path) -> dict[str, Any]:
    default = {
        "schema_version": SCHEMA_VERSION,
        "enabled": True,
        "budgets": {
            "max_average_context_tokens": 12000,
            "max_declared_unused_rate": 0.40,
            "max_repeated_path_rate": 0.35,
            "max_memory_stale_rate": 0.25,
            "min_memory_reuse_rate": 0.25,
            "max_replans_per_task": 2.0,
        },
        "retention": {"events_days": 90},
        "privacy": {"store_content": False, "store_prompt": False, "store_secret_values": False},
    }
    path = root / ".ai/observability/POLICY.yaml"
    if path.exists():
        data = load_yaml(path)
        default.update({k: v for k, v in data.items() if k != "budgets"})
        default["budgets"].update(data.get("budgets") or {})
    return default


def build_report(root: Path) -> dict[str, Any]:
    events = read_events(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now(),
        "context": context_metrics(root),
        "memory": memory_stats(root),
        "compaction": compaction_stats(root),
        "events": event_metrics(events),
    }


def evaluate(report: dict[str, Any], pol: dict[str, Any]) -> dict[str, Any]:
    budgets = pol.get("budgets") or {}
    checks = []

    def add(name: str, value: Any, limit: Any, direction: str, comparable: bool = True):
        if not comparable or value is None or limit is None:
            checks.append({"name": name, "status": "NOT_ENOUGH_DATA", "value": value, "limit": limit})
            return
        ok = value <= limit if direction == "max" else value >= limit
        checks.append({"name": name, "status": "PASS" if ok else "WARN", "value": value, "limit": limit})

    ctx = report["context"]
    mem = report["memory"]
    evt = report["events"]
    add("average_context_tokens", ctx["estimated_tokens_average"], budgets.get("max_average_context_tokens"), "max", bool(ctx["receipts"]))
    add("declared_unused_rate", (1 - ctx["declared_use_rate"]) if ctx["declared_use_rate"] is not None else None, budgets.get("max_declared_unused_rate"), "max")
    add("repeated_path_rate", ctx["repeated_path_rate"], budgets.get("max_repeated_path_rate"), "max")
    add("memory_stale_rate", mem["stale_rate"], budgets.get("max_memory_stale_rate"), "max")
    add("memory_reuse_rate", evt["memory_reuse_rate"], budgets.get("min_memory_reuse_rate"), "min")
    add("replan_rate_per_task", evt["replan_rate_per_task"], budgets.get("max_replans_per_task"), "max")

    warnings = [c for c in checks if c["status"] == "WARN"]
    return {
        "status": "WARN" if warnings else "PASS",
        "checks": checks,
        "warnings": warnings,
    }


def append_event(root: Path, event: dict[str, Any]) -> Path:
    path = root / ".ai/observability/EVENTS.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"schema_version": OBS_SCHEMA_VERSION, "event_id": event.get("event_id") or f"OBS-{datetime.now().strftime('%Y%m%d%H%M%S%f')}", "at": now(), **event}
    # Explicit privacy guard.
    event.pop("prompt", None)
    event.pop("content", None)
    event.pop("secret", None)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.5 context economics and observability")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["report", "check", "record"], nargs="?", default="report")
    p.add_argument("event_type", choices=["context", "memory", "gate", "replan"], nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument("--receipt")
    p.add_argument("--task")
    p.add_argument("--session")
    p.add_argument("--agent")
    p.add_argument("--used", nargs="*", default=[])
    p.add_argument("--retrieved", nargs="*", default=[])
    p.add_argument("--reused", nargs="*", default=[])
    p.add_argument("--status")
    p.add_argument("--evidence-depth")
    args = p.parse_args()
    root = Path(args.path).resolve()

    if args.action == "record":
        if args.event_type == "context":
            if not args.receipt:
                p.error("record context requires --receipt")
            receipt = root / args.receipt
            if not receipt.exists():
                p.error(f"receipt not found: {args.receipt}")
            data = load_yaml(receipt)
            loaded = data.get("loaded") or []
            estimated = data.get("estimated_tokens")
            if estimated is None:
                estimated = sum(estimate_tokens(root / str(item)) for item in loaded)
            event = {"type": "context_load", "task_id": args.task or data.get("task_id"), "session_id": args.session or data.get("session_id"), "agent_id": args.agent or data.get("agent_id"), "receipt": args.receipt, "estimated_tokens": int(estimated or 0), "loaded_count": len(loaded), "context_depth": data.get("context_depth")}
        elif args.event_type == "memory":
            event = {"type": "memory_reuse", "task_id": args.task, "session_id": args.session, "agent_id": args.agent, "retrieved_ids": args.retrieved, "reused_ids": args.reused}
        elif args.event_type == "gate":
            event = {"type": "gate", "task_id": args.task, "session_id": args.session, "agent_id": args.agent, "status": str(args.status or "").upper(), "evidence_depth": args.evidence_depth}
        else:
            event = {"type": "replan", "task_id": args.task, "session_id": args.session, "agent_id": args.agent}
        out = append_event(root, event)
        print(f"RECORDED {out.relative_to(root)}")
        return

    report = build_report(root)
    pol = policy(root)
    evaluation = evaluate(report, pol)
    payload = {**report, "evaluation": evaluation}
    if args.action == "check":
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(evaluation["status"])
            for item in evaluation["checks"]:
                print(f"{item['name']}={item['status']} value={item['value']} limit={item['limit']}")
        raise SystemExit(1 if evaluation["status"] == "WARN" else 0)

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"OBSERVABILITY {evaluation['status']}")
        print(f"CONTEXT_RECEIPTS {report['context']['receipts']}")
        print(f"CONTEXT_TOKENS_AVG {report['context']['estimated_tokens_average']}")
        print(f"CONTEXT_REPETITION {report['context']['repeated_path_rate']}")
        print(f"MEMORY_STALE_RATE {report['memory']['stale_rate']}")
        print(f"MEMORY_REUSE_RATE {report['events']['memory_reuse_rate']}")
        print(f"GATE_DONE_RATE {report['events']['gate_done_rate']}")
        print(f"REPLAN_RATE {report['events']['replan_rate_per_task']}")
    return


if __name__ == "__main__":
    main()
