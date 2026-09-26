#!/usr/bin/env python3
"""Initialize a project from the UAAF scaffold.

The initializer is adaptive only in structure and metadata. It never fabricates
project facts; unknown facts remain empty/unknown until discovered.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / "scaffold"

FULL_ONLY = [
    ".ai/agents",
    ".ai/evidence",
    ".ai/health",
    ".ai/migrations",
]
STANDARD_PLUS = [
    ".ai/tasks",
    ".ai/sessions",
    ".ai/decisions",
    ".ai/verification",
    ".ai/anti-slop",
]

CAPABILITY_SIGNALS = {
    # Prefer strong framework/file signals. Generic dependency manifests are not
    # enough to classify a project because they occur across many project types.
    "frontend": [
        "vite.config.ts", "vite.config.js", "next.config.js", "next.config.mjs",
        "nuxt.config.ts", "angular.json", "src/app", "app/routes.tsx",
        "app/page.tsx", "app/page.jsx",
    ],
    "backend": [
        "artisan", "manage.py", "server.js", "server.ts", "src/server.js",
        "src/server.ts", "app/main.py", "app/main.ts", "app/main.js",
    ],
    "api": [
        "openapi.yaml", "openapi.yml", "swagger.yaml", "swagger.yml",
        "app/Http/Controllers", "routes/api.php", "src/routes/api.ts",
    ],
    "database": [
        "prisma", "schema.prisma", "migrations", "database", "db/migrations",
    ],
    "mobile": [
        "android", "ios", "pubspec.yaml", "app.json", "capacitor.config.ts",
        "react-native.config.js",
    ],
    "data": [
        "pipeline", "pipelines", "etl", "dags", "notebooks", "dbt_project.yml",
        "data_pipeline.py", "etl.py",
    ],
    "testing": [
        "tests", "test", "pytest.ini", "jest.config.js", "jest.config.ts",
        "vitest.config.ts", "vitest.config.js",
    ],
    "infrastructure": [
        "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "k8s",
        "terraform", ".github/workflows",
    ],
}



def copy_tree(src: Path, dst: Path, *, overwrite: bool = False) -> tuple[list[Path], list[Path]]:
    copied: list[Path] = []
    skipped: list[Path] = []
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not overwrite:
                skipped.append(rel)
                continue
            shutil.copy2(item, target)
            copied.append(rel)
    return copied, skipped


def detect_capabilities(destination: Path) -> dict[str, bool]:
    result = {
        key: any((destination / signal).exists() for signal in signals)
        for key, signals in CAPABILITY_SIGNALS.items()
    }
    result["frontend"] = result["frontend"] or (
        (destination / "package.json").exists()
        and any((destination / signal).exists() for signal in ["src/components", "components"])
    )
    result["ui"] = result["frontend"] or any(
        (destination / signal).exists()
        for signal in ["src/components", "components", "resources/views"]
    )
    result["design_system"] = result["ui"] and any(
        (destination / signal).exists()
        for signal in ["components", "src/components", "design-system", "tokens"]
    )
    result["product"] = any(
        (destination / signal).exists()
        for signal in ["docs/product", "PRD.md", "docs/PRD.md"]
    )
    result["security"] = any(
        (destination / signal).exists()
        for signal in ["SECURITY.md", "docs/quality/SECURITY.md", "security"]
    )
    result["performance"] = any(
        (destination / signal).exists()
        for signal in ["performance", "docs/quality/PERFORMANCE.md", "lighthouse.config.js"]
    )
    result["deployment"] = result["infrastructure"]
    return result


def set_profile(data: dict, profile: str) -> None:
    data["profile"] = profile
    features = data.setdefault("features", {})
    # A conservative baseline that matches the three editions.
    features.update({
        "memory": True,
        "anti_slop": profile != "minimal",
        "verification": profile != "minimal",
        "replanning": profile != "minimal",
        "session_handoff": profile != "minimal",
        "traceability": profile == "full",
    })
    if profile == "full":
        data.setdefault("agent", {})["autonomy_level"] = 3


DOC_RULES = {
    "docs/product": ["product"],
    "docs/architecture": ["frontend", "backend", "api", "database", "data", "mobile", "infrastructure"],
    "docs/design": ["ui", "frontend", "mobile", "design_system"],
    "docs/data": ["database", "data"],
    "docs/development/API.md": ["api"],
    "docs/development/IMPLEMENTATION-PLAN.md": ["frontend", "backend", "api", "database", "data", "mobile"],
    "docs/development/TASKS.md": ["frontend", "backend", "api", "database", "data", "mobile"],
    "docs/quality/TESTING.md": ["testing"],
    "docs/quality/SECURITY.md": ["security"],
    "docs/quality/PERFORMANCE.md": ["performance"],
    "docs/operations/DEPLOYMENT.md": ["deployment", "infrastructure"],
    "docs/operations/ENVIRONMENT.md": ["deployment", "infrastructure"],
    "docs/operations/BACKUP.md": ["database", "deployment", "infrastructure"],
    "docs/operations/MONITORING.md": ["deployment", "infrastructure", "performance"],
}


def remove_copied_paths(destination: Path, copied: set[Path], rel_prefix: str) -> None:
    prefix = Path(rel_prefix)
    targets = sorted((p for p in copied if p == prefix or prefix in p.parents), key=lambda x: len(x.parts), reverse=True)
    for rel in targets:
        target = destination / rel
        if target.exists() and target.is_file():
            target.unlink()
        copied.discard(rel)
    # Remove only empty directories that were part of the copied scaffold.
    base = destination / prefix
    if base.exists():
        for d in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda x: len(x.parts), reverse=True):
            try:
                d.rmdir()
            except OSError:
                pass
        try:
            base.rmdir()
        except OSError:
            pass


def prune_profile(destination: Path, profile: str, capabilities: dict[str, bool], copied_paths: list[Path], docs_mode: str) -> None:
    copied = set(copied_paths)

    if profile == "minimal":
        prefixes = [
            ".ai/anti-slop", ".ai/verification", ".ai/agents", ".ai/sessions",
            ".ai/migrations", ".ai/evidence", ".ai/health", ".ai/decisions", ".ai/tasks",
            "docs",
        ]
        for rel in prefixes:
            remove_copied_paths(destination, copied, rel)
    elif profile == "standard":
        for rel in [".ai/agents", ".ai/evidence", ".ai/health", ".ai/migrations"]:
            remove_copied_paths(destination, copied, rel)

    if profile in {"standard", "full"}:
        if docs_mode == "none":
            remove_copied_paths(destination, copied, "docs")
        elif docs_mode == "auto":
            for rel, required_caps in DOC_RULES.items():
                if not any(capabilities.get(cap, False) for cap in required_caps):
                    remove_copied_paths(destination, copied, rel)
        # docs_mode=all keeps the entire copied documentation catalog.



def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a UAAF project")
    parser.add_argument("destination")
    parser.add_argument("--profile", choices=["minimal", "standard", "full"], default="standard")
    parser.add_argument("--name", default="")
    parser.add_argument("--type", default="")
    parser.add_argument("--auto-detect", action="store_true", help="detect capabilities from existing files")
    parser.add_argument("--force", action="store_true", help="allow reinitialization of an existing UAAF installation")
    parser.add_argument("--docs", choices=["auto", "all", "none"], default="auto", help="documentation generation mode for standard/full")
    parser.add_argument("--extension", choices=["none", "v1.1"], default="none", help="enable additive UAAF extensions")
    args = parser.parse_args()

    destination = Path(args.destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    existing_manifest = destination / ".ai/manifest.yaml"
    if existing_manifest.exists() and not args.force:
        raise SystemExit(
            f"UAAF installation already exists at {destination}. Use --force to reinitialize it."
        )

    # Detect capabilities from the user's project BEFORE adding UAAF scaffold files.
    detected_capabilities = detect_capabilities(destination) if args.auto_detect else None

    copied, skipped = copy_tree(SCAFFOLD, destination, overwrite=args.force)
    manifest_path = destination / ".ai/manifest.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    data.setdefault("project", {})["name"] = args.name
    data["project"]["type"] = args.type
    set_profile(data, args.profile)

    if detected_capabilities is not None:
        data["capabilities"].update(detected_capabilities)

    data.setdefault("anti_slop", {})["enabled"] = data["features"].get("anti_slop", False)
    data.setdefault("verification", {})["enabled"] = data["features"].get("verification", False)
    data.setdefault("sessions", {})["enabled"] = data["features"].get("session_handoff", False)
    if args.profile == "minimal":
        data["source_of_truth"].pop("decisions", None)
        data["source_of_truth"].pop("verification", None)
        data["source_of_truth"].pop("memory", None) if not data["features"].get("memory") else None

    if args.extension == "v1.1":
        data["extensions"] = {
            "version": "1.1",
            "capabilities": {"file": ".ai/capabilities.yaml", "mode": "layered"},
            "context_impact": {"file": ".ai/context/IMPACT-GRAPH.yaml", "mode": "advisory"},
        }
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    prune_profile(destination, args.profile, data.get("capabilities", {}), copied, args.docs)

    if args.extension == "v1.1":
        cap_path = destination / ".ai/capabilities.yaml"
        cap_path.parent.mkdir(parents=True, exist_ok=True)
        cap_doc = {
            "schema_version": "1.1",
            "updated_at": "",
            "source": "uaf_init.py",
            "capabilities": {},
        }
        for name, value in sorted(data.get("capabilities", {}).items()):
            cap_doc["capabilities"][name] = {
                "detected": bool(value),
                "override": "auto",
                "confidence": "HIGH" if value else "LOW",
                "source": "detector" if args.auto_detect else "manifest_default",
                "reason": "",
            }
        cap_path.write_text(yaml.safe_dump(cap_doc, sort_keys=False), encoding="utf-8")
        ctx_dir = destination / ".ai/context"
        ctx_dir.mkdir(parents=True, exist_ok=True)
        (ctx_dir / "README.md").write_text(
            "# Context Impact Graph\n\nGenerated by the UAAF v1.1 context-impact tool. Advisory only.\n",
            encoding="utf-8",
        )

    if skipped:
        print("Preserved existing files:")
        for rel in skipped:
            print(f"  - {rel}")
    print(f"Initialized UAAF {args.profile} at {destination}")


if __name__ == "__main__":
    main()
