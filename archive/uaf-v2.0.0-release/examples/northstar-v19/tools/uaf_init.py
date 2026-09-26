#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE_FILES = {
    "minimal": {
        ".ai/core", ".ai/memory/STATE.md", ".ai/memory/MEMORY.md",
        ".ai/INDEX.md", ".ai/manifest.yaml", "AGENTS.md", "README.md", "CHANGELOG.md"
    },
    "standard": None,
    "full": None,
}

OPTIONAL_CAPABILITY_DOCS = {
    "product": ["docs/product"],
    "frontend": ["docs/design", "docs/development"],
    "ui": ["docs/design"],
    "backend": ["docs/architecture", "docs/development"],
    "api": ["docs/development/API.md", "docs/architecture/INTEGRATIONS.md"],
    "database": ["docs/data"],
    "security": ["docs/quality/SECURITY.md"],
    "performance": ["docs/quality/PERFORMANCE.md"],
    "deployment": ["docs/operations"],
    "mobile": ["docs/design", "docs/development"],
}

def copy_tree(src: Path, dst: Path):
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)

def main():
    p = argparse.ArgumentParser(description="Initialize a UAAF project")
    p.add_argument("destination")
    p.add_argument("--profile", choices=["minimal", "standard", "full"], default="standard")
    p.add_argument("--name", default="")
    args = p.parse_args()

    destination = Path(args.destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    copy_tree(ROOT, destination)

    manifest = destination / ".ai/manifest.yaml"
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    data["project"]["name"] = args.name
    data["profile"] = args.profile
    if args.profile == "minimal":
        data["features"].update({"anti_slop": False, "verification": True, "replanning": False, "session_handoff": False})
    elif args.profile == "full":
        data["features"]["traceability"] = True
        data["agent"]["autonomy_level"] = 3
        data["capabilities"].update({k: True for k in ["security", "performance"]})
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    if args.profile == "minimal":
        # Remove optional modules while retaining a coherent kernel.
        for rel in [".ai/anti-slop", ".ai/verification/REGRESSION-MAP.md", ".ai/verification/INTENT-EVALUATION.md", ".ai/agents", ".ai/sessions", ".ai/migrations", ".ai/evidence", ".ai/health", ".ai/decisions", ".ai/tasks"]:
            target = destination / rel
            if target.is_dir(): shutil.rmtree(target)
            elif target.exists(): target.unlink()
    elif args.profile == "standard":
        # Full-only modules are intentionally omitted from standard installs.
        for rel in [".ai/agents", ".ai/evidence", ".ai/health", ".ai/migrations"]:
            target = destination / rel
            if target.is_dir(): shutil.rmtree(target)
            elif target.exists(): target.unlink()

    print(f"Initialized UAAF {args.profile} at {destination}")

if __name__ == "__main__":
    main()
