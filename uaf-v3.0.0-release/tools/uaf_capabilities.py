#!/usr/bin/env python3
"""UAAF v1.1 capability detection and override utility.

Detection remains advisory. Explicit overrides are persisted separately so
UAAF v1.0 boolean capability fields remain backward compatible.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

CAPABILITY_NAMES = [
    "product", "frontend", "backend", "api", "database", "ui",
    "design_system", "security", "performance", "deployment", "mobile",
    "data", "testing", "infrastructure",
]
OVERRIDE_VALUES = {"auto", "force_true", "force_false", "review_required"}
CONFIDENCE_VALUES = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def detect_capabilities(root: Path) -> dict[str, bool]:
    """Conservative capability detector independent of the initializer."""
    signals: dict[str, list[str]] = {
        "frontend": [
            "vite.config.ts", "vite.config.js", "next.config.js", "next.config.mjs",
            "nuxt.config.ts", "angular.json", "src/app", "app/routes.tsx",
            "app/page.tsx", "app/page.jsx", "resources/views",
        ],
        "backend": [
            "artisan", "manage.py", "server.js", "server.ts", "src/server.js",
            "src/server.ts", "app/main.py", "app/main.ts", "app/main.js",
        ],
        "api": [
            "openapi.yaml", "openapi.yml", "swagger.yaml", "swagger.yml",
            "app/Http/Controllers", "routes/api.php", "src/routes/api.ts",
        ],
        "database": ["schema.prisma", "prisma", "database", "db/migrations"],
        "mobile": ["android", "ios", "pubspec.yaml", "app.json", "capacitor.config.ts", "react-native.config.js"],
        "data": ["pipeline", "pipelines", "etl", "dags", "notebooks", "dbt_project.yml", "data_pipeline.py", "etl.py"],
        "testing": ["tests", "test", "pytest.ini", "jest.config.js", "jest.config.ts", "vitest.config.ts", "vitest.config.js"],
        "infrastructure": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", "k8s", "terraform", ".github/workflows"],
    }
    result = {name: any((root / s).exists() for s in paths) for name, paths in signals.items()}
    result["frontend"] = result["frontend"] or (
        (root / "package.json").exists()
        and any((root / s).exists() for s in ["src/components", "components", "src/pages", "pages"])
    )
    result["ui"] = result["frontend"] or any(
        (root / s).exists() for s in ["src/components", "components", "resources/views"]
    )
    result["design_system"] = result["ui"] and any(
        (root / s).exists() for s in ["design-system", "tokens", "src/design-system"]
    )
    result["product"] = any((root / s).exists() for s in ["docs/product", "PRD.md", "docs/PRD.md"])
    result["security"] = any((root / s).exists() for s in ["SECURITY.md", "docs/quality/SECURITY.md", "security"])
    result["performance"] = any((root / s).exists() for s in ["performance", "docs/quality/PERFORMANCE.md", "lighthouse.config.js"])
    result["deployment"] = result["infrastructure"]
    for name in CAPABILITY_NAMES:
        result.setdefault(name, False)
    return {name: bool(result[name]) for name in CAPABILITY_NAMES}


def read_manifest(root: Path) -> dict[str, Any]:
    path = root / ".ai/manifest.yaml"
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit("Manifest must be a YAML mapping")
    return data


def capability_path(root: Path) -> Path:
    manifest = read_manifest(root)
    rel = (((manifest.get("extensions") or {}).get("capabilities") or {}).get("file"))
    return root / str(rel or ".ai/capabilities.yaml")


def normalize_record(value: Any, detected_default: bool) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"detected": value, "override": "auto", "confidence": "UNKNOWN", "source": "legacy_manifest", "reason": ""}
    value = value if isinstance(value, dict) else {}
    detected = bool(value.get("detected", detected_default))
    override = str(value.get("override") or "auto")
    if override not in OVERRIDE_VALUES:
        override = "review_required"
    confidence = str(value.get("confidence") or "UNKNOWN")
    if confidence not in CONFIDENCE_VALUES:
        confidence = "UNKNOWN"
    return {
        "detected": detected,
        "override": override,
        "confidence": confidence,
        "source": value.get("source") or "detector",
        "reason": value.get("reason") or "",
    }


def effective(record: dict[str, Any]) -> bool:
    override = record.get("override", "auto")
    if override == "force_true":
        return True
    if override == "force_false":
        return False
    return bool(record.get("detected", False))


def build_document(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    detected = detect_capabilities(root)
    existing: dict[str, Any] = {}
    path = root / ".ai/capabilities.yaml"
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                existing = loaded.get("capabilities") or {}
        except Exception:
            existing = {}
    records: dict[str, Any] = {}
    for name in CAPABILITY_NAMES:
        previous = normalize_record(existing.get(name), detected[name])
        previous["detected"] = detected[name]
        if previous["override"] == "auto":
            previous["source"] = "detector"
            previous["reason"] = ""
            previous["confidence"] = "HIGH" if detected[name] else "LOW"
        records[name] = previous
    return {
        "schema_version": "1.1",
        "updated_at": now_iso(),
        "source": "uaf_capabilities.py",
        "capabilities": records,
    }


def write_effective_projection(root: Path, records: dict[str, Any]) -> None:
    manifest_path = root / ".ai/manifest.yaml"
    manifest = read_manifest(root)
    manifest.setdefault("capabilities", {})
    for name, record in records.items():
        manifest["capabilities"][name] = effective(record)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def ensure(root: Path) -> Path:
    root = root.resolve()
    path = root / ".ai/capabilities.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = build_document(root, read_manifest(root))
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    write_effective_projection(root, doc["capabilities"])
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage UAAF v1.1 capability overrides")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("action", choices=["ensure", "show", "set"], nargs="?", default="show")
    parser.add_argument("assignment", nargs="?", help="capability=auto|force_true|force_false|review_required")
    parser.add_argument("--reason", default="")
    parser.add_argument("--source", default="user")
    args = parser.parse_args()
    root = Path(args.path).resolve()

    path = root / ".ai/capabilities.yaml"
    if args.action == "ensure":
        print(f"WROTE {ensure(root)}")
        return

    if not path.exists():
        ensure(root)

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    records = doc.get("capabilities") or {}

    if args.action == "set":
        if "=" not in (args.assignment or ""):
            raise SystemExit("set requires capability=override")
        name, override = args.assignment.split("=", 1)
        if name not in CAPABILITY_NAMES:
            raise SystemExit(f"Unknown capability: {name}")
        if override not in OVERRIDE_VALUES:
            raise SystemExit(f"Invalid override: {override}")
        if override != "auto" and not args.reason.strip():
            raise SystemExit("--reason is required for explicit overrides")
        record = normalize_record(records.get(name), False)
        record.update({"override": override, "source": args.source, "reason": args.reason.strip()})
        record["updated_at"] = now_iso()
        records[name] = record
        doc["capabilities"] = records
        doc["updated_at"] = now_iso()
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        write_effective_projection(root, records)
        print(f"SET {name}={override} effective={str(effective(record)).lower()}")
        return

    print("CAPABILITY | DETECTED | OVERRIDE | EFFECTIVE | CONFIDENCE")
    for name in CAPABILITY_NAMES:
        record = normalize_record(records.get(name), False)
        print(f"{name} | {str(record['detected']).lower()} | {record['override']} | {str(effective(record)).lower()} | {record['confidence']}")


if __name__ == "__main__":
    main()
