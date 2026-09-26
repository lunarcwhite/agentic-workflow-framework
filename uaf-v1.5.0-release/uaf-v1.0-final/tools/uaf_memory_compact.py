#!/usr/bin/env python3
"""UAAF v1.2 conservative memory compaction.

Dry-run by default. Apply archives duplicate entries instead of deleting them.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

TOKEN_RE = re.compile(r"[a-z0-9_]{3,}")
VALID_STATUSES = {"ACTIVE", "VALIDATED"}
AUTHORITY_ORDER = {"CANONICAL": 5, "CONTROLLED": 4, "AUTHORITATIVE": 4, "REFERENCE": 2, "HISTORICAL": 1}
CONFIDENCE_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}


def frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1]) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def body(text: str) -> str:
    if text.startswith("---\n"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
    return text


def tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(body(text).lower()))


def similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def recency(meta: dict[str, Any]) -> str:
    return str(meta.get("updated") or meta.get("created") or "")


def choose_canonical(items: list[dict[str, Any]]) -> dict[str, Any]:
    best = max(
        items,
        key=lambda x: (
            AUTHORITY_ORDER.get(str(x["meta"].get("authority", "REFERENCE")).upper(), 0),
            CONFIDENCE_ORDER.get(str(x["meta"].get("confidence", "UNKNOWN")).upper(), 0),
            recency(x["meta"]),
        ),
    )
    tied = [
        x for x in items
        if (
            AUTHORITY_ORDER.get(str(x["meta"].get("authority", "REFERENCE")).upper(), 0),
            CONFIDENCE_ORDER.get(str(x["meta"].get("confidence", "UNKNOWN")).upper(), 0),
            recency(x["meta"]),
        ) == (
            AUTHORITY_ORDER.get(str(best["meta"].get("authority", "REFERENCE")).upper(), 0),
            CONFIDENCE_ORDER.get(str(best["meta"].get("confidence", "UNKNOWN")).upper(), 0),
            recency(best["meta"]),
        )
    ]
    # Stable tie-break: preserve the oldest/smallest identity rather than the
    # newest identifier, so repeated compaction does not churn the canonical file.
    return min(tied, key=lambda x: x["id"])


def load_entries(root: Path) -> list[dict[str, Any]]:
    base = root / ".ai/memory/entries"
    result = []
    if not base.exists():
        return result
    for path in sorted(base.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        meta = frontmatter(text)
        if str(meta.get("status", "")).upper() not in VALID_STATUSES:
            continue
        ident = str(meta.get("id", ""))
        if not ident:
            continue
        result.append({"id": ident, "path": path, "meta": meta, "text": text, "tokens": tokens(text)})
    return result


def cluster(entries: list[dict[str, Any]], threshold: float) -> list[list[dict[str, Any]]]:
    parent = list(range(len(entries)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if entries[i]["tokens"] == entries[j]["tokens"] and entries[i]["tokens"]:
                union(i, j)
            elif similarity(entries[i]["tokens"], entries[j]["tokens"]) >= threshold:
                union(i, j)

    groups: dict[int, list[dict[str, Any]]] = {}
    for i, item in enumerate(entries):
        groups.setdefault(find(i), []).append(item)
    return list(groups.values())


def build_report(root: Path, threshold: float) -> dict[str, Any]:
    entries = load_entries(root)
    groups = [g for g in cluster(entries, threshold) if len(g) > 1]
    duplicates = []
    for group in groups:
        canonical = choose_canonical(group)
        for item in group:
            if item is canonical:
                continue
            duplicates.append({
                "id": item["id"],
                "path": str(item["path"].relative_to(root)),
                "superseded_by": canonical["id"],
                "canonical_path": str(canonical["path"].relative_to(root)),
                "similarity_to_canonical": round(similarity(item["tokens"], canonical["tokens"]), 4),
            })
    return {
        "schema_version": "1.2",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "conservative",
        "threshold": threshold,
        "entries_scanned": len(entries),
        "duplicate_entries": len(duplicates),
        "clusters": len(groups),
        "duplicates": duplicates,
    }


def apply_report(root: Path, report: dict[str, Any]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = root / ".ai/memory/archive/compaction" / stamp
    archive.mkdir(parents=True, exist_ok=True)
    for item in report["duplicates"]:
        src = root / item["path"]
        if not src.exists():
            continue
        dst = archive / src.name
        shutil.move(str(src), str(dst))
    # Rebuild lightweight memory index from active entries.
    idx = root / ".ai/memory/MEMORY.md"
    lines = ["# Memory Index", "", "Detailed durable knowledge belongs in `entries/`.", ""]
    for path in sorted((root / ".ai/memory/entries").glob("*.md")) if (root / ".ai/memory/entries").exists() else []:
        meta = frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        if str(meta.get("status", "")).upper() == "ACTIVE":
            lines.append(f"- {meta.get('id')}: {path.name}")
    idx.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["applied_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    report["archive"] = str(archive.relative_to(root))
    out = root / ".ai/memory/compaction" / f"COMPACTION-{stamp}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(report, sort_keys=False), encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.2 conservative memory compaction")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", nargs="?", choices=["compact"], default="compact")
    p.add_argument("--threshold", type=float, default=0.78)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--check", action="store_true", help="exit 1 when duplicate retrieval surface is detected")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    root = Path(args.path).resolve()
    report = build_report(root, args.threshold)
    if args.apply and report["duplicate_entries"]:
        out = apply_report(root, report)
        report["report_path"] = str(out.relative_to(root))
    status = "DUPLICATES_FOUND" if report["duplicate_entries"] else "COMPACT"
    if args.json:
        print(json.dumps({"status": status, **report}, indent=2, ensure_ascii=False))
    else:
        print(status)
        print(f"SCANNED {report['entries_scanned']}")
        print(f"DUPLICATES {report['duplicate_entries']}")
        print(f"CLUSTERS {report['clusters']}")
        if args.apply:
            print(f"APPLIED {'yes' if report['duplicate_entries'] else 'no'}")
    if args.check and report["duplicate_entries"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
