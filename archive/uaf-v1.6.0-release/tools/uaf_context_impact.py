#!/usr/bin/env python3
"""UAAF v1.1 Context Impact Graph.

Advisory only. Maps changed paths to capabilities, domains, and canonical
knowledge candidates for targeted retrieval and freshness review.
"""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DOMAIN_RULES = [
    ("product", "product", ["docs/product/", "prd", "roadmap", "vision", "goals", "scope"]),
    ("architecture", "architecture", ["docs/architecture/", "architecture", "dockerfile", "terraform", "k8s/"]),
    ("design", "design", ["docs/design/", "design-system/", "tokens", "components/"]),
    ("data", "data", ["docs/data/", "schema.prisma", "migrations/", "db/migrations/", "database/"]),
    ("api", "api", ["openapi", "swagger", "routes/api", "controllers/", "docs/development/api"]),
    ("testing", "testing", ["tests/", "test/", "pytest", "jest", "vitest"]),
    ("security", "security", ["security", "auth", "permission", "policy", "docs/quality/security"]),
    ("performance", "performance", ["performance", "lighthouse", "benchmark", "docs/quality/performance"]),
    ("operations", "operations", [".github/workflows/", "deploy", "docker-compose", "monitoring", "backup", "docs/operations/"]),
]

CAPABILITY_BY_DOMAIN = {
    "product": ["product"],
    "architecture": ["frontend", "backend", "api", "database", "mobile", "infrastructure"],
    "design": ["ui", "frontend", "mobile", "design_system"],
    "data": ["database", "data"],
    "api": ["api", "backend"],
    "testing": ["testing"],
    "security": ["security", "backend", "api"],
    "performance": ["performance"],
    "operations": ["deployment", "infrastructure", "performance"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def git_paths(root: Path) -> tuple[list[str], str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "-c", "core.preloadindex=false", "status", "--porcelain=v1", "--untracked-files=all"],
            text=True, capture_output=True, check=False,
            timeout=3,
        )
        if proc.returncode != 0:
            return [], "git-unavailable"
        paths: list[str] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            raw = line[3:] if len(line) >= 3 else line
            if " -> " in raw:
                raw = raw.split(" -> ")[-1]
            paths.append(raw.strip())
        return sorted(set(paths)), "git-status"
    except FileNotFoundError:
        return [], "git-unavailable"
    except subprocess.TimeoutExpired:
        return [], "git-timeout"


def effective_capabilities(root: Path, manifest: dict[str, Any]) -> dict[str, bool]:
    base = {str(k): bool(v) for k, v in (manifest.get("capabilities") or {}).items()}
    cfg = root / ".ai/capabilities.yaml"
    if not cfg.exists():
        return base
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        for name, record in (data.get("capabilities") or {}).items():
            if not isinstance(record, dict):
                continue
            override = record.get("override", "auto")
            value = bool(record.get("detected", base.get(name, False)))
            if override == "force_true": value = True
            elif override == "force_false": value = False
            base[name] = value
    except Exception:
        pass
    return base


def classify_path(path: str, source_of_truth: dict[str, Any], effective_caps: dict[str, bool]) -> dict[str, Any]:
    normalized = path.replace("\\", "/").lower()
    domains: list[str] = []
    reasons: list[str] = []
    for domain, _, signals in DOMAIN_RULES:
        for signal in signals:
            if normalized.startswith(signal.lower()) or signal.lower() in normalized:
                domains.append(domain)
                reasons.append(f"matched:{signal}")
                break
    if normalized.startswith(".ai/"):
        if ".ai/memory/" in normalized:
            domains.append("memory")
        if ".ai/decisions/" in normalized:
            domains.append("decisions")
        if ".ai/tasks/" in normalized:
            domains.append("tasks")
        if ".ai/verification/" in normalized:
            domains.append("verification")
    if not domains:
        domains.append("implementation")
        reasons.append("default:implementation")

    knowledge: list[str] = []
    if normalized.startswith("docs/"):
        knowledge.append(path)
    for domain in domains:
        owner = source_of_truth.get(domain)
        if owner and owner != "repository":
            knowledge.append(str(owner))
    capability_set: list[str] = []
    for domain in domains:
        capability_set.extend(cap for cap in CAPABILITY_BY_DOMAIN.get(domain, []) if effective_caps.get(cap, False))

    return {
        "path": path,
        "domains": sorted(set(domains)),
        "capabilities": sorted(set(capability_set)),
        "knowledge": sorted(set(knowledge)),
        "reasons": reasons,
    }


def build_graph(root: Path, paths: list[str], source: str) -> dict[str, Any]:
    manifest_path = root / ".ai/manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest = manifest if isinstance(manifest, dict) else {}
    sot = manifest.get("source_of_truth") or {}
    effective_caps = effective_capabilities(root, manifest)
    nodes = [classify_path(path, sot, effective_caps) for path in paths]
    affected_domains = sorted({d for node in nodes for d in node["domains"]})
    affected_knowledge = sorted({k for node in nodes for k in node["knowledge"]})
    affected_caps = sorted({c for node in nodes for c in node["capabilities"]})
    return {
        "schema_version": "1.1",
        "generated_at": now_iso(),
        "source": source,
        "mode": "advisory",
        "changed_paths": paths,
        "affected_domains": affected_domains,
        "affected_capabilities": affected_caps,
        "affected_knowledge": affected_knowledge,
        "nodes": nodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the UAAF v1.1 Context Impact Graph")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--paths", nargs="*", default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    root = Path(args.path).resolve()

    if args.paths is not None:
        paths = sorted(set(args.paths))
        source = "explicit"
    else:
        paths, source = git_paths(root)
    graph = build_graph(root, paths, source)
    output = Path(args.output).resolve() if args.output else root / ".ai/context/IMPACT-GRAPH.yaml"
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(yaml.safe_dump(graph, sort_keys=False), encoding="utf-8")
        print(f"WRITTEN {output}")
        print(f"PATHS {len(paths)}")
        print(f"DOMAINS {','.join(graph['affected_domains']) or 'none'}")
        return

    print("READY")
    print(f"SOURCE {source}")
    print(f"PATHS {len(paths)}")
    print(f"DOMAINS {','.join(graph['affected_domains']) or 'none'}")
    print(f"KNOWLEDGE {','.join(graph['affected_knowledge']) or 'none'}")


if __name__ == "__main__":
    main()
