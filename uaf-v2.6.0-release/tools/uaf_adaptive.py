#!/usr/bin/env python3
"""UAAF v1.6 Adaptive Learning & Context Optimization.

Advisory only by default. The tool learns from v1.5 metadata-first telemetry and
produces recommendations; it never silently mutates intent, policy, memory, or
retrieval configuration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "1.6"
MIN_OBSERVATIONS = 3


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def read_events(root: Path) -> list[dict[str, Any]]:
    path = root / ".ai/observability/EVENTS.jsonl"
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def receipts(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    base = root / ".ai"
    if not base.exists():
        return out
    for path in sorted(base.rglob("context-receipt*.yaml")) + sorted(base.rglob("context-receipt*.yml")):
        data = load_yaml(path)
        if data:
            data["_path"] = str(path.relative_to(root))
            out.append(data)
    return out


def token_estimate(path: Path) -> int:
    try:
        if not path.exists() or not path.is_file():
            return 0
        return min(path.stat().st_size, 2 * 1024 * 1024) // 4
    except OSError:
        return 0


def active_memory(root: Path) -> list[dict[str, Any]]:
    base = root / ".ai/memory/entries"
    out: list[dict[str, Any]] = []
    if not base.exists():
        return out
    for path in sorted(base.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        meta: dict[str, Any] = {}
        if text.startswith("---\n") and "\n---" in text[4:]:
            _, block, _ = text.split("---", 2)
            parsed = yaml.safe_load(block) or {}
            if isinstance(parsed, dict):
                meta = parsed
        status = str(meta.get("status", "UNKNOWN")).upper()
        if status not in {"ARCHIVED", "SUPERSEDED"}:
            out.append({"id": str(meta.get("id") or path.stem), "status": status, "path": str(path.relative_to(root))})
    return out


def policy(root: Path) -> dict[str, Any]:
    defaults = {
        "schema_version": SCHEMA_VERSION,
        "enabled": True,
        "min_observations": MIN_OBSERVATIONS,
        "adaptive": {
            "min_unused_rate": 0.60,
            "min_repeated_rate": 0.50,
            "min_memory_reuse_rate": 0.10,
            "max_replan_rate_per_task": 2.0,
            "min_gate_done_rate": 0.50,
        },
        "safety": {
            "auto_apply": False,
            "allow_policy_mutation": False,
            "allow_intent_mutation": False,
            "allow_memory_delete": False,
        },
    }
    path = root / ".ai/optimization/POLICY.yaml"
    if path.exists():
        data = load_yaml(path)
        for key, value in data.items():
            if key == "adaptive" and isinstance(value, dict):
                defaults["adaptive"].update(value)
            elif key == "safety" and isinstance(value, dict):
                defaults["safety"].update(value)
            elif key != "adaptive" and key != "safety":
                defaults[key] = value
    return defaults


def stable_id(prefix: str, seed: str) -> str:
    return prefix + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8].upper()


def analyze_context(root: Path, pol: dict[str, Any]) -> dict[str, Any]:
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"observations": 0, "used": 0, "unused": 0, "tokens": 0})
    for receipt in receipts(root):
        loaded = receipt.get("loaded") or []
        if isinstance(loaded, str):
            loaded = [loaded]
        used = receipt.get("usage", {}).get("used") or []
        unused = receipt.get("usage", {}).get("unused") or []
        used = [used] if isinstance(used, str) else list(used)
        unused = [unused] if isinstance(unused, str) else list(unused)
        used_set = {str(x) for x in used}
        unused_set = {str(x) for x in unused}
        for item in loaded:
            rel = str(item)
            row = stats[rel]
            row["observations"] += 1
            row["used"] += 1 if rel in used_set else 0
            row["unused"] += 1 if rel in unused_set else 0
            row["tokens"] = max(row["tokens"], token_estimate(root / rel))
    entries = []
    min_obs = int(pol.get("min_observations", MIN_OBSERVATIONS))
    for path, row in sorted(stats.items()):
        obs = int(row["observations"])
        unused_rate = (row["unused"] / obs) if obs else None
        used_rate = (row["used"] / obs) if obs else None
        entries.append({"path": path, **row, "unused_rate": unused_rate, "used_rate": used_rate, "eligible": obs >= min_obs})
    occurrences = sum(int(row["observations"]) for row in stats.values())
    repeated = sum(max(int(row["observations"]) - 1, 0) for row in stats.values())
    repeated_rate = (repeated / occurrences) if occurrences else None
    return {"paths": entries, "unique_paths": len(entries), "occurrences": occurrences, "repeated_rate": repeated_rate}


def analyze_memory(root: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    retrievals: Counter[str] = Counter()
    reused: Counter[str] = Counter()
    for event in events:
        if event.get("type") != "memory_reuse":
            continue
        for item in event.get("retrieved_ids") or []:
            retrievals[str(item)] += 1
        for item in event.get("reused_ids") or []:
            reused[str(item)] += 1
    active = active_memory(root)
    entries = []
    for memory in active:
        mid = memory["id"]
        entries.append({
            **memory,
            "retrieved": retrievals.get(mid, 0),
            "reused": reused.get(mid, 0),
            "reuse_rate": (reused.get(mid, 0) / retrievals[mid]) if retrievals.get(mid) else None,
        })
    return {"entries": entries, "active_count": len(active)}


def analyze_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    tasks: set[str] = set()
    replans = 0
    gates = 0
    done = 0
    for event in events:
        task_id = event.get("task_id")
        if task_id:
            tasks.add(str(task_id))
        if event.get("type") == "replan":
            replans += 1
        elif event.get("type") == "gate":
            gates += 1
            if str(event.get("status", "")).upper() == "DONE":
                done += 1
    return {
        "tasks": len(tasks),
        "replans": replans,
        "replan_rate_per_task": (replans / len(tasks)) if tasks else None,
        "gates": gates,
        "done": done,
        "gate_done_rate": (done / gates) if gates else None,
        "event_count": len(events),
    }


def build_analysis(root: Path) -> dict[str, Any]:
    pol = policy(root)
    events = read_events(root)
    context = analyze_context(root, pol)
    memory = analyze_memory(root, events)
    events_stats = analyze_events(events)
    global_retrieved = sum(len(e.get("retrieved_ids") or []) for e in events if e.get("type") == "memory_reuse")
    global_reused = sum(len(e.get("reused_ids") or []) for e in events if e.get("type") == "memory_reuse")
    recommendations: list[dict[str, Any]] = []
    adaptive = pol.get("adaptive") or {}
    min_obs = int(pol.get("min_observations", MIN_OBSERVATIONS))

    for row in context["paths"]:
        if row["observations"] < min_obs or row["unused_rate"] is None:
            continue
        if row["unused_rate"] >= float(adaptive.get("min_unused_rate", 0.60)):
            seed = f"context:{row['path']}"
            recommendations.append({
                "id": stable_id("OPT-CTX-", seed),
                "type": "CONTEXT_RETRIEVAL_REVIEW",
                "target": row["path"],
                "status": "PROPOSED",
                "confidence": "HIGH" if row["observations"] >= min_obs * 3 else "MEDIUM",
                "reason": f"unused_rate={row['unused_rate']:.2f} across {row['observations']} observations",
                "suggested_action": "Consider moving this path from direct/bootstrap retrieval to a supporting or on-demand context class.",
                "evidence": {"observations": row["observations"], "unused_rate": round(row["unused_rate"], 4), "estimated_tokens": row["tokens"]},
                "safety": "ADVISORY_ONLY",
            })

    repeated_rate = context.get("repeated_rate")
    if repeated_rate is not None and len(receipts(root)) >= min_obs and repeated_rate >= float(adaptive.get("min_repeated_rate", 0.50)):
        recommendations.append({
            "id": stable_id("OPT-CTX-", "global-repetition"),
            "type": "CONTEXT_REUSE_REVIEW",
            "target": ".ai/context",
            "status": "PROPOSED",
            "confidence": "HIGH" if len(receipts(root)) >= min_obs * 3 else "MEDIUM",
            "reason": f"repeated_path_rate={repeated_rate:.2f} across {len(receipts(root))} context receipts",
            "suggested_action": "Consider session-local caching or narrower prerequisite retrieval; do not change CLE policy automatically.",
            "evidence": {"context_receipts": len(receipts(root)), "repeated_path_rate": round(repeated_rate, 4)},
            "safety": "ADVISORY_ONLY",
        })

    mem_reuse = None
    total_retrieved = global_retrieved
    total_reused = global_reused
    if total_retrieved:
        mem_reuse = total_reused / total_retrieved
        if mem_reuse < float(adaptive.get("min_memory_reuse_rate", 0.10)):
            recommendations.append({
                "id": stable_id("OPT-MEM-", "global-low-reuse"),
                "type": "MEMORY_RETRIEVAL_REVIEW",
                "target": ".ai/memory/entries",
                "status": "PROPOSED",
                "confidence": "HIGH" if total_retrieved >= 10 else "MEDIUM",
                "reason": f"observed memory reuse rate={mem_reuse:.2f}",
                "suggested_action": "Review retrieval selectors and low-value memory candidates before changing memory contents.",
                "evidence": {"retrieved": total_retrieved, "reused": total_reused, "reuse_rate": round(mem_reuse, 4)},
                "safety": "ADVISORY_ONLY",
            })

    replan_rate = events_stats["replan_rate_per_task"]
    if replan_rate is not None and replan_rate > float(adaptive.get("max_replan_rate_per_task", 2.0)):
        recommendations.append({
            "id": stable_id("OPT-PLAN-", "high-replan-rate"),
            "type": "PLANNING_PREREQUISITE_REVIEW",
            "target": ".ai/tasks",
            "status": "PROPOSED",
            "confidence": "HIGH" if events_stats["tasks"] >= 5 else "MEDIUM",
            "reason": f"replan_rate_per_task={replan_rate:.2f}",
            "suggested_action": "Inspect recurring blocker categories and context prerequisites; do not change the task contract automatically.",
            "evidence": {"tasks": events_stats["tasks"], "replans": events_stats["replans"]},
            "safety": "ADVISORY_ONLY",
        })

    gate_rate = events_stats["gate_done_rate"]
    if gate_rate is not None and gate_rate < float(adaptive.get("min_gate_done_rate", 0.50)):
        recommendations.append({
            "id": stable_id("OPT-GATE-", "low-done-rate"),
            "type": "DELIVERY_GATE_REVIEW",
            "target": ".ai/verification/DELIVERY-GATE.md",
            "status": "PROPOSED",
            "confidence": "MEDIUM" if events_stats["gates"] >= 4 else "LOW",
            "reason": f"gate_done_rate={gate_rate:.2f}",
            "suggested_action": "Review recurring gate failures and evidence coverage; never weaken a gate to improve the metric.",
            "evidence": {"gates": events_stats["gates"], "done": events_stats["done"]},
            "safety": "ADVISORY_ONLY",
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now(),
        "mode": "advisory",
        "policy": pol,
        "context": context,
        "memory": {"summary": {"retrieved": total_retrieved, "reused": total_reused, "reuse_rate": mem_reuse}, "entries": memory["entries"]},
        "workflow": events_stats,
        "recommendations": recommendations,
        "safety": pol.get("safety") or {},
    }


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.6 adaptive learning and context optimization")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["analyze", "recommend", "check"], nargs="?", default="analyze")
    p.add_argument("--write", action="store_true", help="write analysis/proposals artifacts")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    root = Path(args.path).resolve()
    result = build_analysis(root)

    if args.write:
        out_dir = root / ".ai/optimization"
        write_yaml(out_dir / "ANALYSIS.yaml", result)
        proposals = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": result["generated_at"],
            "mode": "advisory",
            "recommendations": result["recommendations"],
        }
        write_yaml(out_dir / "PROPOSALS.yaml", proposals)
        print(f"WROTE {out_dir / 'ANALYSIS.yaml'}")
        print(f"WROTE {out_dir / 'PROPOSALS.yaml'}")
        if args.action == "check":
            raise SystemExit(0)
        return

    if args.action == "check":
        proposal_path = root / ".ai/optimization/PROPOSALS.yaml"
        ok = True
        if proposal_path.exists():
            proposal = load_yaml(proposal_path)
            if proposal.get("schema_version") != SCHEMA_VERSION:
                ok = False
            if proposal.get("mode") != "advisory":
                ok = False
        else:
            ok = False
        print("PASS" if ok else "FAIL")
        raise SystemExit(0 if ok else 1)

    payload = result["recommendations"] if args.action == "recommend" else result
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"ADAPTIVE {len(result['recommendations'])} recommendations")
        for rec in result["recommendations"]:
            print(f"{rec['id']} {rec['type']} target={rec['target']} confidence={rec['confidence']}")
        if not result["recommendations"]:
            print("NO_RECOMMENDATIONS")


if __name__ == "__main__":
    main()
