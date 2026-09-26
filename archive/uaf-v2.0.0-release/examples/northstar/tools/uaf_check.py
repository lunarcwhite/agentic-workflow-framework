#!/usr/bin/env python3
import argparse
from pathlib import Path
import re
import yaml

REQUIRED = [
    "AGENTS.md", ".ai/manifest.yaml", ".ai/INDEX.md",
    ".ai/core/SOUL.md", ".ai/core/CONTEXT.md", ".ai/core/RULES.md",
    ".ai/core/WORKFLOW.md", ".ai/core/CONVENTIONS.md", ".ai/core/KNOWLEDGE-CONTRACT.md",
    ".ai/memory/STATE.md", ".ai/memory/MEMORY.md",
]
STANDARD = [
    ".ai/memory/POLICY.md", ".ai/decisions/INDEX.md", ".ai/verification/VERIFICATION-MATRIX.md",
    ".ai/verification/DELIVERY-GATE.md", ".ai/anti-slop/PROTOCOL.md", ".ai/anti-slop/GATES.md",
]
FULL = [
    ".ai/evidence", ".ai/health", ".ai/agents/REGISTRY.yaml", ".ai/agents/CLAIMS.yaml",
]

def check(path: Path, level: str):
    errors, warnings, infos = [], [], []
    for rel in REQUIRED:
        if not (path / rel).exists(): errors.append(f"CONF-STR-001 missing {rel}")
    try:
        manifest = yaml.safe_load((path / ".ai/manifest.yaml").read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"CONF-MAN-001 invalid manifest: {e}")
        manifest = {}
    for key in ["schema_version", "framework", "protocols", "project", "agent", "features", "capabilities"]:
        if key not in manifest: errors.append(f"CONF-MAN-002 missing manifest key: {key}")
    profile = manifest.get("profile", "standard")
    target = STANDARD if level in ("standard", "full") else []
    if profile == "full" or level == "full": target += FULL
    for rel in target:
        if not (path / rel).exists(): errors.append(f"CONF-PRO-001 missing {rel}")
    for rel in [".ai/core/CONTEXT.md", ".ai/core/CONVENTIONS.md"]:
        txt = (path / rel).read_text(encoding="utf-8") if (path / rel).exists() else ""
        if "<!--" in txt: warnings.append(f"CONF-DOC-001 placeholder content remains in {rel}")
    state = path / ".ai/memory/STATE.md"
    if state.exists() and not re.search(r"version:\s*\d+", state.read_text(encoding="utf-8")):
        errors.append("CONF-MEM-001 STATE.md has no numeric version")
    if (path / ".ai/manifest.yaml").exists():
        features = manifest.get("features", {})
        if features.get("anti_slop") and not (path / ".ai/anti-slop/PROTOCOL.md").exists():
            errors.append("CONF-AS-001 anti-slop enabled but protocol missing")
        if features.get("verification") and not (path / ".ai/verification/DELIVERY-GATE.md").exists():
            errors.append("CONF-VER-001 verification enabled but delivery gate missing")
    infos.append(f"profile={profile}")
    return errors, warnings, infos

def main():
    p = argparse.ArgumentParser(description="Validate a UAAF project")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--level", choices=["core", "standard", "full"], default="standard")
    args = p.parse_args()
    errors, warnings, infos = check(Path(args.path).resolve(), args.level)
    status = "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    print(status)
    for x in errors: print("ERROR", x)
    for x in warnings: print("WARNING", x)
    for x in infos: print("INFO", x)
    raise SystemExit(1 if errors else 0)

if __name__ == "__main__":
    main()
