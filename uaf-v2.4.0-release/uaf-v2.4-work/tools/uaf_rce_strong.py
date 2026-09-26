#!/usr/bin/env python3
"""UAAF v1.2 Strong Reality & Consistency Engine."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def refs_from_yaml(path: Path, key: str) -> list[str]:
    data = load_yaml(path)
    values = data.get(key, [])
    if isinstance(values, str):
        return [values]
    return [str(x) for x in values or []]


def relevant_paths(root: Path) -> set[str]:
    result: set[str] = set()
    manifest = load_yaml(root / ".ai/manifest.yaml") if (root / ".ai/manifest.yaml").exists() else {}
    for owner in (manifest.get("source_of_truth") or {}).values():
        if owner != "repository":
            result.add(str(owner).rstrip("/"))

    evidence = root / ".ai/evidence"
    if evidence.exists():
        for f in evidence.glob("*.yaml"):
            for src in refs_from_yaml(f, "sources"):
                result.add(src)
    entries = root / ".ai/memory/entries"
    if entries.exists():
        for f in entries.glob("*.md"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            meta = {}
            if text.startswith("---\n"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    try:
                        meta = yaml.safe_load(parts[1]) or {}
                    except Exception:
                        meta = {}
            for src in meta.get("source", []) or []:
                value = str(src)
                if not value.startswith(("TASK-", "DEC-", "EVD-", "MEM-")):
                    result.add(value)
    impact = root / ".ai/context/IMPACT-GRAPH.yaml"
    if impact.exists():
        for src in load_yaml(impact).get("changed_paths", []) or []:
            result.add(str(src))
    expanded: set[str] = set()
    for rel in result:
        p = root / rel
        if p.is_file():
            expanded.add(rel)
        elif p.is_dir():
            for child in p.rglob("*"):
                if child.is_file():
                    expanded.add(str(child.relative_to(root)))
    return expanded


def snapshot(root: Path) -> dict[str, Any]:
    records = []
    for rel in sorted(relevant_paths(root)):
        p = root / rel
        if not p.exists():
            records.append({"path": rel, "status": "MISSING"})
            continue
        stat = p.stat()
        records.append({
            "path": rel,
            "status": "PRESENT",
            "sha256": sha256(p),
            "size": stat.st_size,
        })
    return {
        "schema_version": "1.2",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "strong",
        "records": records,
    }


def write_snapshot(root: Path) -> Path:
    out = root / ".ai/health/REALITY-INDEX.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(snapshot(root), sort_keys=False), encoding="utf-8")
    return out


def scan(root: Path) -> tuple[str, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    idx = root / ".ai/health/REALITY-INDEX.yaml"
    if not idx.exists():
        warnings.append("RCE-S-001 no reality baseline; run `uaf rce snapshot`")
    else:
        data = load_yaml(idx)
        if data.get("schema_version") != "1.2":
            errors.append("RCE-S-002 invalid reality index schema_version")
        for rec in data.get("records", []) or []:
            rel = str(rec.get("path", ""))
            p = root / rel
            if not p.exists():
                errors.append(f"RCE-S-003 baseline path missing: {rel}")
                continue
            expected = rec.get("sha256")
            if expected and sha256(p) != expected:
                warnings.append(f"RCE-S-004 fingerprint drift: {rel}")

    manifest = root / ".ai/manifest.yaml"
    m = load_yaml(manifest) if manifest.exists() else {}
    for domain, owner in (m.get("source_of_truth") or {}).items():
        if owner != "repository" and not (root / str(owner)).exists():
            errors.append(f"RCE-S-005 canonical owner missing: {domain} -> {owner}")

    evidence = root / ".ai/evidence"
    if evidence.exists():
        for f in evidence.glob("*.yaml"):
            data = load_yaml(f)
            for src in data.get("sources", []) or []:
                if not (root / str(src)).exists():
                    errors.append(f"RCE-S-006 evidence source missing: {f.name} -> {src}")

    entries = root / ".ai/memory/entries"
    if entries.exists():
        for f in entries.glob("*.md"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            meta = {}
            if text.startswith("---\n"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    try:
                        meta = yaml.safe_load(parts[1]) or {}
                    except Exception:
                        meta = {}
            for src in meta.get("source", []) or []:
                value = str(src)
                if value.startswith("TASK-"):
                    found = list((root / ".ai/tasks").rglob(f"{value}*")) if (root / ".ai/tasks").exists() else []
                    if not found:
                        warnings.append(f"RCE-S-007 memory source task missing: {f.name} -> {value}")
                    continue
                if value.startswith("DEC-"):
                    found = list((root / ".ai/decisions").glob(f"{value}*")) if (root / ".ai/decisions").exists() else []
                    if not found:
                        warnings.append(f"RCE-S-008 memory source decision missing: {f.name} -> {value}")
                    continue
                if value.startswith("EVD-"):
                    found = list((root / ".ai/evidence").glob(f"{value}*")) if (root / ".ai/evidence").exists() else []
                    if not found:
                        warnings.append(f"RCE-S-009 memory source evidence missing: {f.name} -> {value}")
                    continue
                if value.startswith("MEM-"):
                    active = list((root / ".ai/memory/entries").glob(f"{value}*")) if (root / ".ai/memory/entries").exists() else []
                    archived = list((root / ".ai/memory/archive").rglob(f"{value}*")) if (root / ".ai/memory/archive").exists() else []
                    if not active and not archived:
                        warnings.append(f"RCE-S-010 memory source memory missing: {f.name} -> {value}")
                    continue
                if not (root / value).exists():
                    warnings.append(f"RCE-S-011 memory source path missing: {f.name} -> {value}")

    graph = root / ".ai/context/IMPACT-GRAPH.yaml"
    if graph.exists():
        for rel in load_yaml(graph).get("changed_paths", []) or []:
            if not (root / str(rel)).exists():
                warnings.append(f"RCE-S-008 impact path no longer exists: {rel}")

    status = "CONFLICT" if errors else ("DRIFT" if warnings else "CONSISTENT")
    return status, errors, warnings


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.2 Strong RCE")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["snapshot", "scan"], nargs="?", default="scan")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    root = Path(args.path).resolve()
    if args.action == "snapshot":
        out = write_snapshot(root)
        print(f"SNAPSHOT {out}")
        print(f"RECORDS {len(load_yaml(out).get('records', []))}")
        return
    status, errors, warnings = scan(root)
    payload = {"status": status, "errors": errors, "warnings": warnings}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(status)
        for item in errors:
            print("ERROR", item)
        for item in warnings:
            print("WARNING", item)
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
