#!/usr/bin/env python3
"""Initialize a project from the UAAF v1.0 full scaffold.

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
    "frontend": ["package.json", "vite.config.ts", "vite.config.js", "next.config.js", "src/app"],
    "backend": ["artisan", "manage.py", "requirements.txt", "pyproject.toml", "server.js"],
    "api": ["openapi.yaml", "openapi.yml", "swagger.yaml", "routes", "app/Http/Controllers"],
    "database": ["prisma", "migrations", "database", "schema.prisma"],
    "mobile": ["android", "ios", "pubspec.yaml", "app.json"],
    "ui": ["components", "src/components", "app", "resources/views"],
}


def copy_tree(src: Path, dst: Path) -> None:
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def detect_capabilities(destination: Path) -> dict[str, bool]:
    result = {}
    for key, signals in CAPABILITY_SIGNALS.items():
        result[key] = any((destination / signal).exists() for signal in signals)
    result["product"] = False
    result["design_system"] = (destination / "components").exists() or (destination / "src/components").exists()
    result["security"] = False
    result["performance"] = False
    result["deployment"] = any((destination / x).exists() for x in ["Dockerfile", "docker-compose.yml", "k8s", ".github/workflows"])
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


def prune_profile(destination: Path, profile: str) -> None:
    if profile == "minimal":
        for rel in [
            ".ai/anti-slop", ".ai/verification", ".ai/agents", ".ai/sessions",
            ".ai/migrations", ".ai/evidence", ".ai/health", ".ai/decisions", ".ai/tasks",
            "docs",
        ]:
            target = destination / rel
            if target.is_dir(): shutil.rmtree(target)
            elif target.exists(): target.unlink()
    elif profile == "standard":
        for rel in FULL_ONLY:
            target = destination / rel
            if target.is_dir(): shutil.rmtree(target)
            elif target.exists(): target.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a UAAF v1.0 project")
    parser.add_argument("destination")
    parser.add_argument("--profile", choices=["minimal", "standard", "full"], default="standard")
    parser.add_argument("--name", default="")
    parser.add_argument("--type", default="")
    parser.add_argument("--auto-detect", action="store_true", help="detect capabilities from existing files")
    parser.add_argument("--force", action="store_true", help="allow initialization into a non-empty destination")
    args = parser.parse_args()

    destination = Path(args.destination).resolve()
    if destination.exists() and any(destination.iterdir()) and not args.force:
        raise SystemExit(f"Destination is not empty: {destination}. Use --force to initialize anyway.")
    destination.mkdir(parents=True, exist_ok=True)

    copy_tree(SCAFFOLD, destination)
    manifest_path = destination / ".ai/manifest.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    data.setdefault("project", {})["name"] = args.name
    data["project"]["type"] = args.type
    set_profile(data, args.profile)

    if args.auto_detect:
        data["capabilities"].update(detect_capabilities(destination))

    data.setdefault("anti_slop", {})["enabled"] = data["features"].get("anti_slop", False)
    data.setdefault("verification", {})["enabled"] = data["features"].get("verification", False)
    data.setdefault("sessions", {})["enabled"] = data["features"].get("session_handoff", False)
    if args.profile == "minimal":
        data["source_of_truth"].pop("decisions", None)
        data["source_of_truth"].pop("verification", None)
        data["source_of_truth"].pop("memory", None) if not data["features"].get("memory") else None

    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    prune_profile(destination, args.profile)

    print(f"Initialized UAAF {args.profile} at {destination}")


if __name__ == "__main__":
    main()
