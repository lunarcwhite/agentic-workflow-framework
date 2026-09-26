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
    ".ai/observability",
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
    parser.add_argument("--extension", choices=["none", "v1.1", "v1.2", "v1.3", "v1.4", "v1.5", "v1.6"], default="none", help="enable additive UAAF extensions")
    args = parser.parse_args()
    if args.extension in {"v1.3", "v1.4", "v1.5", "v1.6"} and args.profile != "full":
        raise SystemExit(f"UAAF {args.extension} extensions require --profile full")

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

    if args.extension in {"v1.1", "v1.2", "v1.3", "v1.4", "v1.5", "v1.6"}:
        data["extensions"] = {
            "version": "1.1",
            "capabilities": {"file": ".ai/capabilities.yaml", "mode": "layered"},
            "context_impact": {"file": ".ai/context/IMPACT-GRAPH.yaml", "mode": "advisory"},
        }
        if args.extension == "v1.2":
            data["extensions"]["version"] = "1.2"
            data["extensions"]["memory_compaction"] = {
                "file": ".ai/memory/compaction/README.md",
                "mode": "conservative",
            }
            data["extensions"]["rce_strong"] = {
                "file": ".ai/health/RCE-STRONG.md",
                "mode": "snapshot_and_scan",
            }
        if args.extension in {"v1.3", "v1.4", "v1.5", "v1.6"}:
            data["extensions"]["version"] = "1.3"
            data["extensions"]["memory_compaction"] = {
                "file": ".ai/memory/compaction/README.md",
                "mode": "conservative",
            }
            data["extensions"]["rce_strong"] = {
                "file": ".ai/health/RCE-STRONG.md",
                "mode": "snapshot_and_scan",
            }
            data["extensions"]["git_traceability"] = {
                "file": ".ai/health/GIT-BASELINE.yaml",
                "mode": "read_only_baseline",
            }
            data["extensions"]["claim_leasing"] = {
                "file": ".ai/agents/CLAIMS.yaml",
                "mode": "atomic_lease",
            }
            data["extensions"]["runtime_verification"] = {
                "file": ".ai/verification/RUNTIME-POLICY.yaml",
                "mode": "allowlisted_subprocess",
            }
            if args.extension in {"v1.4", "v1.5", "v1.6"}:
                data["extensions"]["version"] = "1.4"
                data["extensions"]["security_diagnostics"] = {
                    "file": ".ai/security/SECURITY-DIAGNOSTICS.md",
                    "mode": "static_read_only",
                }
                data["extensions"]["git_task_traceability"] = {
                    "file": ".ai/health/GIT-TASK-TRACEABILITY.md",
                    "mode": "semantic_advisory",
                }
                data["extensions"]["runtime_evidence"] = {
                    "file": ".ai/verification/RUNTIME-EVIDENCE.md",
                    "mode": "delivery_gate",
                    "required_for_risk": ["CRITICAL"],
                }
                if args.extension in {"v1.5", "v1.6"}:
                    data["extensions"]["version"] = "1.5"
                    data["extensions"]["observability"] = {
                        "policy": ".ai/observability/POLICY.yaml",
                        "events": ".ai/observability/EVENTS.jsonl",
                        "mode": "metadata_first",
                    }
                    if args.extension == "v1.6":
                        data["extensions"]["version"] = "1.6"
                        data["extensions"]["adaptive_learning"] = {
                            "policy": ".ai/optimization/POLICY.yaml",
                            "analysis": ".ai/optimization/ANALYSIS.yaml",
                            "proposals": ".ai/optimization/PROPOSALS.yaml",
                            "mode": "advisory_only",
                        }
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    prune_profile(destination, args.profile, data.get("capabilities", {}), copied, args.docs)
    # The scaffold contains the v1.5 observability directory for reference
    # development, but legacy/earlier extension installs must not emit it.
    if args.extension not in {"v1.5", "v1.6"}:
        remove_copied_paths(destination, set(copied), ".ai/observability")
    if args.extension != "v1.6":
        remove_copied_paths(destination, set(copied), ".ai/optimization")

    if args.extension in {"v1.1", "v1.2", "v1.3", "v1.4", "v1.5", "v1.6"}:
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

        if args.extension == "v1.2":
            comp_dir = destination / ".ai/memory/compaction"
            comp_dir.mkdir(parents=True, exist_ok=True)
            (comp_dir / "README.md").write_text(
                "# Memory Compaction\n\nConservative compaction removes duplicate retrieval surface while preserving audit history. Dry-run is the default.\n",
                encoding="utf-8",
            )
            health_dir = destination / ".ai/health"
            health_dir.mkdir(parents=True, exist_ok=True)
            (health_dir / "RCE-STRONG.md").write_text(
                "# Strong Reality & Consistency Engine\n\nSnapshot and scan are read-only. A snapshot records fingerprints for referenced knowledge and evidence paths; scan detects later drift.\n",
                encoding="utf-8",
            )

        if args.extension in {"v1.3", "v1.4", "v1.5", "v1.6"}:
            comp_dir = destination / ".ai/memory/compaction"
            comp_dir.mkdir(parents=True, exist_ok=True)
            (comp_dir / "README.md").write_text(
                "# Memory Compaction\n\nConservative compaction removes duplicate retrieval surface while preserving audit history. Dry-run is the default.\n",
                encoding="utf-8",
            )
            health_dir = destination / ".ai/health"
            (health_dir / "RCE-STRONG.md").write_text(
                "# Strong Reality & Consistency Engine\n\nSnapshot and scan are read-only. A snapshot records fingerprints for referenced knowledge and evidence paths; scan detects later drift.\n",
                encoding="utf-8",
            )
            health_dir.mkdir(parents=True, exist_ok=True)
            (health_dir / "GIT-BASELINE.yaml").write_text(
                "schema_version: '1.3'\ngenerated_at: ''\nrepository: ''\nhead: ''\nbranch: ''\ndirty: false\ndirty_paths: []\n",
                encoding="utf-8",
            )
            runtime_policy = destination / ".ai/verification/RUNTIME-POLICY.yaml"
            runtime_policy.parent.mkdir(parents=True, exist_ok=True)
            runtime_policy.write_text(
                "schema_version: '1.3'\nenabled: false\nallow: []\nnotes: 'Enable only explicit, trusted commands; execution uses shell=False.'\n",
                encoding="utf-8",
            )
            (destination / ".ai/health/GIT-TRACEABILITY.md").write_text(
                "# Git Traceability\n\nUse `uaf git snapshot` to establish a baseline and `uaf git trace --task TASK-xxxx` to inspect changes since that baseline. Read-only.\n",
                encoding="utf-8",
            )
            (destination / ".ai/agents/CLAIMS.yaml").write_text(
                "schema_version: '1.3'\nclaims: []\n",
                encoding="utf-8",
            )
            (destination / ".ai/agents/CLAIM-LEASING.md").write_text(
                "# Claim Leasing\n\nClaims are atomic filesystem-backed leases. Expired claims are not automatically reassigned; reclaim is explicit. Claims do not replace Git.\n",
                encoding="utf-8",
            )
            (destination / ".ai/verification/RUNTIME-VERIFICATION.md").write_text(
                "# Runtime Verification\n\nRuntime checks are disabled unless the allowlist explicitly enables the exact command. Commands execute without a shell and produce evidence receipts.\n",
                encoding="utf-8",
            )

        if args.extension in {"v1.4", "v1.5", "v1.6"}:
            sec_dir = destination / ".ai/security"
            sec_dir.mkdir(parents=True, exist_ok=True)
            (sec_dir / "SECURITY-DIAGNOSTICS.md").write_text(
                "# Security Diagnostics\n\nStatic, read-only checks for likely secret leakage and unsafe file permissions. Reports never print matched secret values.\n",
                encoding="utf-8",
            )
            health_dir = destination / ".ai/health"
            health_dir.mkdir(parents=True, exist_ok=True)
            (health_dir / "GIT-TASK-TRACEABILITY.md").write_text(
                "# Git ↔ Task Traceability\n\nUse `uaf git-task --task TASK-xxxx` to compare task expected changes with Git changes and task-linked commits. Advisory; does not replace Git or the task contract.\n",
                encoding="utf-8",
            )
            (destination / ".ai/verification/RUNTIME-EVIDENCE.md").write_text(
                "# Runtime Evidence & Delivery Gate\n\nRuntime evidence is enforced only when required by the task risk or explicit verification item. Delivery remains subject to all other gates.\n",
                encoding="utf-8",
            )

        if args.extension in {"v1.5", "v1.6"}:
            obs_dir = destination / ".ai/observability"
            obs_dir.mkdir(parents=True, exist_ok=True)
            (obs_dir / "POLICY.yaml").write_text(
                "schema_version: '1.5'\nenabled: true\nbudgets:\n  max_average_context_tokens: 12000\n  max_declared_unused_rate: 0.40\n  max_repeated_path_rate: 0.35\n  max_memory_stale_rate: 0.25\n  min_memory_reuse_rate: 0.25\n  max_replans_per_task: 2.0\nretention:\n  events_days: 90\nprivacy:\n  store_content: false\n  store_prompt: false\n  store_secret_values: false\n",
                encoding="utf-8",
            )
            (obs_dir / "README.md").write_text(
                "# UAAF v1.5 Observability\n\nMetadata-first telemetry for context economics, memory health/reuse, gate outcomes, and replanning. Prompt and source contents are not stored.\n",
                encoding="utf-8",
            )
            (obs_dir / "EVENTS.jsonl").write_text("", encoding="utf-8")

            if args.extension == "v1.6":
                opt_dir = destination / ".ai/optimization"
                opt_dir.mkdir(parents=True, exist_ok=True)
                (opt_dir / "POLICY.yaml").write_text(
                    "schema_version: '1.6'\nenabled: true\nmin_observations: 3\nadaptive:\n  min_unused_rate: 0.60\n  min_repeated_rate: 0.50\n  min_memory_reuse_rate: 0.10\n  max_replan_rate_per_task: 2.0\n  min_gate_done_rate: 0.50\nsafety:\n  auto_apply: false\n  allow_policy_mutation: false\n  allow_intent_mutation: false\n  allow_memory_delete: false\n",
                    encoding="utf-8",
                )
                (opt_dir / "README.md").write_text(
                    "# UAAF v1.6 Adaptive Learning\n\nAdvisory-only optimization derived from v1.5 metadata-first telemetry. Recommendations require explicit human/project-policy adoption; intent and policy are never mutated automatically.\n",
                    encoding="utf-8",
                )
                (opt_dir / "ANALYSIS.yaml").write_text("schema_version: '1.6'\nmode: advisory\nrecommendations: []\n", encoding="utf-8")
                (opt_dir / "PROPOSALS.yaml").write_text("schema_version: '1.6'\nmode: advisory\nrecommendations: []\n", encoding="utf-8")

    if skipped:
        print("Preserved existing files:")
        for rel in skipped:
            print(f"  - {rel}")
    print(f"Initialized UAAF {args.profile} at {destination}")


if __name__ == "__main__":
    main()
