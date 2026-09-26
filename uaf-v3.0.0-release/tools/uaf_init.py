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
    parser.add_argument("--extension", choices=["none", "v1.1", "v1.2", "v1.3", "v1.4", "v1.5", "v1.6", "v1.7", "v1.8", "v1.9", "v2.0", "v2.1", "v2.2", "v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9", "v3.0"], default="none", help="enable additive UAAF extensions")
    args = parser.parse_args()
    requested_extension = args.extension
    # v3.0 is additive over v2.9. Reuse the existing v2.9 scaffold-generation
    # path, then append the v3.0 runtime layer before finalizing the manifest.
    if args.extension == "v3.0":
        args.extension = "v2.9"
    extension = "v1.9" if args.extension in {"v2.0", "v2.1", "v2.2", "v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"} else args.extension
    if args.extension in {"v1.3", "v1.4", "v1.5", "v1.6", "v1.7", "v1.8", "v1.9", "v2.0", "v2.1", "v2.2", "v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"} and args.profile != "full":
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

    if extension in {"v1.1", "v1.2", "v1.3", "v1.4", "v1.5", "v1.6", "v1.7", "v1.8", "v1.9"}:
        data["extensions"] = {
            "version": "1.1",
            "capabilities": {"file": ".ai/capabilities.yaml", "mode": "layered"},
            "context_impact": {"file": ".ai/context/IMPACT-GRAPH.yaml", "mode": "advisory"},
        }
        if extension == "v1.2":
            data["extensions"]["version"] = "1.2"
            data["extensions"]["memory_compaction"] = {
                "file": ".ai/memory/compaction/README.md",
                "mode": "conservative",
            }
            data["extensions"]["rce_strong"] = {
                "file": ".ai/health/RCE-STRONG.md",
                "mode": "snapshot_and_scan",
            }
        if extension in {"v1.3", "v1.4", "v1.5", "v1.6", "v1.7", "v1.8", "v1.9"}:
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
            if extension in {"v1.4", "v1.5", "v1.6", "v1.7", "v1.8", "v1.9"}:
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
                if extension in {"v1.5", "v1.6", "v1.7", "v1.8", "v1.9"}:
                    data["extensions"]["version"] = "1.5"
                    data["extensions"]["observability"] = {
                        "policy": ".ai/observability/POLICY.yaml",
                        "events": ".ai/observability/EVENTS.jsonl",
                        "mode": "metadata_first",
                    }
                    if extension in {"v1.6", "v1.7", "v1.8", "v1.9"}:
                        data["extensions"]["version"] = "1.6"
                        data["extensions"]["adaptive_learning"] = {
                            "policy": ".ai/optimization/POLICY.yaml",
                            "analysis": ".ai/optimization/ANALYSIS.yaml",
                            "proposals": ".ai/optimization/PROPOSALS.yaml",
                            "mode": "advisory_only",
                        }
                        if extension in {"v1.7", "v1.8", "v1.9"}:
                            data["extensions"]["version"] = "1.7"
                            data["extensions"]["governance"] = {
                                "policy": ".ai/governance/POLICY.yaml",
                                "proposals": ".ai/governance/PROPOSALS.yaml",
                                "audit": ".ai/governance/AUDIT.jsonl",
                                "mode": "explicit_approval",
                            }
                            if extension == "v1.9":
                                data["extensions"]["version"] = "1.9"
                                data["extensions"]["cryptographic_integrity"] = {
                                    "root": ".ai/trust/ROOT.yaml",
                                    "keys": ".ai/trust/KEYS.yaml",
                                    "mode": "signed_detached_ed25519",
                                    "cryptographic_required": False,
                                    "external_pin_required": False,
                                    "required_purposes": ["trust-root", "trust-keys", "trust-policy", "delegations"],
                                }
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    prune_profile(destination, args.profile, data.get("capabilities", {}), copied, args.docs)
    # The scaffold contains the v1.5 observability directory for reference
    # development, but legacy/earlier extension installs must not emit it.
    if extension not in {"v1.5", "v1.6", "v1.7", "v1.8", "v1.9"}:
        remove_copied_paths(destination, set(copied), ".ai/observability")
    if extension not in {"v1.6", "v1.7", "v1.8", "v1.9"}:
        remove_copied_paths(destination, set(copied), ".ai/optimization")
    if extension not in {"v1.7", "v1.8", "v1.9"}:
        remove_copied_paths(destination, set(copied), ".ai/governance")
    if extension not in {"v1.8", "v1.9"}:
        # These paths belong to the UAAF v1.8 extension namespace. Remove them on
        # explicit downgrade/reinitialization so an older extension does not leave
        # active v1.8 policy artifacts behind.
        for rel in [".ai/agents/TRUST.yaml", ".ai/agents/DELEGATIONS.yaml", ".ai/agents/TRUST-AUDIT.jsonl", ".ai/agents/TRUST-DELEGATION.md"]:
            target = destination / rel
            if target.exists():
                target.unlink()

    if extension in {"v1.1", "v1.2", "v1.3", "v1.4", "v1.5", "v1.6", "v1.7", "v1.8", "v1.9"}:
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

        if extension == "v1.2":
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

        if extension in {"v1.3", "v1.4", "v1.5", "v1.6", "v1.7", "v1.8", "v1.9"}:
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

        if extension in {"v1.4", "v1.5", "v1.6", "v1.7", "v1.8", "v1.9"}:
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

        if extension in {"v1.5", "v1.6", "v1.7", "v1.8", "v1.9"}:
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

            if extension in {"v1.6", "v1.7", "v1.8", "v1.9"}:
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
                if extension in {"v1.7", "v1.8", "v1.9"}:
                    gov_dir = destination / ".ai/governance"
                    gov_dir.mkdir(parents=True, exist_ok=True)
                    (gov_dir / "POLICY.yaml").write_text(
                        "schema_version: '1.7'\nenabled: true\nauto_apply: false\nrequire_reviewer: true\nrequire_precondition_match: true\nallowed_mutation_paths:\n  - .ai/optimization/POLICY.yaml\n  - .ai/context/ADAPTIVE-RULES.yaml\n  - .ai/capabilities.yaml\nforbidden_keys:\n  - intent\n  - safety.auto_apply\n  - safety.allow_policy_mutation\n  - safety.allow_intent_mutation\n", encoding="utf-8")
                    if extension == "v1.9":
                        trust_dir = destination / ".ai/trust"
                        trust_dir.mkdir(parents=True, exist_ok=True)
                        (trust_dir / "README.md").write_text(
                            "# UAAF v1.9 Trust Anchoring\n\nPublic trust material only. Private signing keys MUST remain outside the repository.\n",
                            encoding="utf-8")
                        (trust_dir / "ROOT.yaml").write_text(
                            "schema_version: '1.9'\nanchor: {}\npolicy:\n  enabled: true\n  cryptographic_required: false\n  external_pin_required: false\n  required_purposes:\n    - trust-root\n    - trust-keys\n    - trust-policy\n    - delegations\n", encoding="utf-8")
                        (trust_dir / "KEYS.yaml").write_text(
                            "schema_version: '1.9'\nkeys: []\n", encoding="utf-8")
                        (trust_dir / "KEY-ROTATION.yaml").write_text(
                            "schema_version: '1.9'\nstatus: NONE\n", encoding="utf-8")
                        (destination / ".ai/health/TRUST-CRYPTOGRAPHIC-INTEGRITY.md").write_text(
                            "# Cryptographic Integrity\n\nUse `uaf crypto trust-init`, `uaf crypto sign`, `uaf crypto verify`, `uaf crypto bundle-check`, and `uaf crypto audit-check`. Private keys stay outside the project.\n",
                            encoding="utf-8")
                        legacy_audit = destination / ".ai/agents/TRUST-AUDIT.jsonl"
                        if legacy_audit.exists() and legacy_audit.read_text(encoding="utf-8", errors="ignore").strip():
                            first_line = legacy_audit.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
                            if '"schema_version": "1.9"' not in first_line:
                                legacy = legacy_audit.with_name("TRUST-AUDIT.legacy.jsonl")
                                if not legacy.exists():
                                    legacy_audit.replace(legacy)
                                else:
                                    legacy_audit.unlink()
                                legacy_audit.write_text("", encoding="utf-8")
                    (gov_dir / "PROPOSALS.yaml").write_text("schema_version: '1.7'\ngenerated_at: ''\nupdated_at: ''\nproposals: []\n", encoding="utf-8")
                    (gov_dir / "AUDIT.jsonl").write_text("", encoding="utf-8")
                    (gov_dir / "README.md").write_text(
                        "# UAAF v1.7 Policy Governance\n\nAdaptive proposals remain advisory until explicitly reviewed and approved. Safe apply is allowlisted, precondition-checked, audited, and rollback-capable.\n", encoding="utf-8")
                    if extension in {"v1.8", "v1.9"}:
                        data["extensions"]["version"] = "1.8"
                        data["extensions"]["agent_trust"] = {
                            "policy": ".ai/agents/TRUST.yaml",
                            "delegations": ".ai/agents/DELEGATIONS.yaml",
                            "audit": ".ai/agents/TRUST-AUDIT.jsonl",
                            "mode": "bounded_delegation",
                        }
                        trust_dir = destination / ".ai/agents"
                        trust_dir.mkdir(parents=True, exist_ok=True)
                        (trust_dir / "TRUST.yaml").write_text(
                            "schema_version: '1.8'\npolicy:\n  enabled: true\n  deny_actions: []\nagents:\n  - id: AGENT-HUMAN\n    status: ACTIVE\n    direct_authority: true\n    authority: ROOT\n    can_delegate: true\n    capabilities: ['*']\n    domains: ['*']\n    max_risk: CRITICAL\n    min_evidence: E0\n    min_recent_verified_evidence: 0\n    evidence_window_days: 30\n", encoding="utf-8")
                        (trust_dir / "DELEGATIONS.yaml").write_text(
                            "schema_version: '1.8'\ndelegations: []\n", encoding="utf-8")
                        (trust_dir / "TRUST-AUDIT.jsonl").write_text("", encoding="utf-8")
                        (trust_dir / "TRUST-DELEGATION.md").write_text(
                            "# UAAF v1.8 Agent Trust & Delegation\n\nCapability, authority, and delegation are distinct. Delegations are bounded by capability, domain, risk, evidence floor, and expiry; escalation is forbidden.\n", encoding="utf-8")
                        if extension == "v1.9":
                            data["extensions"]["version"] = "1.9"

    if args.extension in {"v2.0", "v2.1", "v2.2", "v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
        data["framework"]["version"] = {
            "v2.0": "2.0.0", "v2.1": "2.1.0", "v2.2": "2.2.0",
            "v2.3": "2.3.0", "v2.4": "2.4.0", "v2.5": "2.5.0", "v2.6": "2.6.0", "v2.7": "2.7.0", "v2.8": "2.8.0", "v2.9": "2.9.0",
        }[args.extension]
        data.setdefault("protocols", {})["federation"] = "UAAF-FED-2.0"
        data["extensions"]["version"] = "2.0"
        data["extensions"]["distributed_federation"] = {
            "identity": ".ai/federation/IDENTITY.yaml",
            "peers": ".ai/federation/PEERS.yaml",
            "policy": ".ai/federation/FEDERATION-POLICY.yaml",
            "replay": ".ai/federation/REPLAY.yaml",
            "audit": ".ai/federation/AUDIT.jsonl",
            "state": ".ai/federation/state",
            "handoffs": ".ai/federation/HANDOFFS",
            "mode": "transport_agnostic",
            "default_deny": True,
            "signed_handoff": True,
            "signed_state": True,
        }
        fed = destination / ".ai/federation"
        for rel in ["HANDOFFS", "BUNDLES", "peers", "state"]:
            (fed / rel).mkdir(parents=True, exist_ok=True)
        (fed / "IDENTITY.yaml").write_text("schema_version: '2.0'\nidentity: {}\n", encoding="utf-8")
        (fed / "PEERS.yaml").write_text("schema_version: '2.0'\npeers: []\n", encoding="utf-8")
        (fed / "FEDERATION-POLICY.yaml").write_text(
            "schema_version: '2.0'\nfederation_id: ''\ndefault_deny: true\nrequire_signed_handoff: true\nrequire_signed_state: true\nallowed_actions:\n  - capability-sync\n  - handoff\n  - policy-sync\n  - state-pull\n  - state-push\npeers: []\n", encoding="utf-8")
        (fed / "REPLAY.yaml").write_text("schema_version: '2.0'\nseen: []\n", encoding="utf-8")
        (fed / "AUDIT.jsonl").write_text("", encoding="utf-8")
        state_dir = fed / "state"
        (state_dir / "VECTOR.yaml").write_text("schema_version: '2.0'\nclock: {}\n", encoding="utf-8")
        (state_dir / "REGISTERS.yaml").write_text("schema_version: '2.0'\nentries: {}\n", encoding="utf-8")
        (state_dir / "CONFLICTS.yaml").write_text("schema_version: '2.0'\nconflicts: []\n", encoding="utf-8")
        (fed / "README.md").write_text("# UAAF v2.0 Distributed Federation\n\nTransport-agnostic federation for cross-project identity, signed handoffs, replay protection, federated policy, and vector-clock state convergence.\n\nPrivate keys remain outside the repository.\n", encoding="utf-8")
        (fed / "TRUST-MODEL.md").write_text("# Federation Trust Model\n\nCapability ≠ authority ≠ delegation ≠ federation trust. Remote actions are deny-by-default, policy-bounded, signature-verified, replay-protected, and risk-bounded.\n", encoding="utf-8")

        if args.extension in {"v2.1", "v2.2", "v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
            data.setdefault("protocols", {})["federation_ops"] = "UAAF-FED-2.1"
            data["extensions"]["version"] = "2.1"
            data["extensions"]["federation_operations"] = {
                "mode": ".ai/federation/ops/MODE.yaml",
                "cursors": ".ai/federation/ops/CURSORS.yaml",
                "bundles": ".ai/federation/ops/BUNDLES.yaml",
                "revocations": ".ai/federation/ops/REVOCATIONS.yaml",
                "checkpoints": ".ai/federation/ops/CHECKPOINTS.yaml",
                "conflicts": ".ai/federation/ops/CONFLICTS.yaml",
                "observability": ".ai/federation/ops/OBSERVABILITY.jsonl",
                "modes": ["ONLINE", "OFFLINE", "PARTITIONED", "RECOVERING"],
            }
            ops = fed / "ops"
            ops.mkdir(parents=True, exist_ok=True)
            (ops / "MODE.yaml").write_text("schema_version: '2.1'\nmode: ONLINE\nupdated_at: null\n", encoding="utf-8")
            (ops / "CURSORS.yaml").write_text("schema_version: '2.1'\npeers: {}\n", encoding="utf-8")
            (ops / "BUNDLES.yaml").write_text("schema_version: '2.1'\nconsumed: []\n", encoding="utf-8")
            (ops / "REVOCATIONS.yaml").write_text("schema_version: '2.1'\nrevocation_epoch: 0\nentries: []\n", encoding="utf-8")
            (ops / "CHECKPOINTS.yaml").write_text("schema_version: '2.1'\ncheckpoints: []\n", encoding="utf-8")
            (ops / "CONFLICTS.yaml").write_text("schema_version: '2.1'\nconflicts: []\n", encoding="utf-8")
            (ops / "OBSERVABILITY.jsonl").write_text("", encoding="utf-8")
            (ops / "README.md").write_text("# UAAF v2.1 Federation Operations\n\nResilience layer: offline/partition modes, idempotent sync, revocation propagation, conflict workflow, checkpoints, recovery, and metadata-only observability.\n", encoding="utf-8")

            if args.extension in {"v2.2", "v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
                data.setdefault("protocols", {})["federation_intelligence"] = "UAAF-FED-2.2"
                data["extensions"]["version"] = "2.2"
                data["extensions"]["federation_intelligence"] = {
                    "policy": ".ai/federation/policy/INHERITANCE.yaml",
                    "effective_policy": ".ai/federation/policy/EFFECTIVE.yaml",
                    "conflict_analysis": ".ai/federation/intelligence/CONFLICT-ANALYSIS.yaml",
                    "sync_plans": ".ai/federation/intelligence",
                    "checkpoint_selection": ".ai/federation/intelligence/CHECKPOINT-SELECTION.yaml",
                    "recovery_recommendation": ".ai/federation/intelligence/RECOVERY-RECOMMENDATION.yaml",
                    "mode": "advisory_policy_intelligence",
                }
                policy_dir = fed / "policy"; intel_dir = fed / "intelligence"
                policy_dir.mkdir(parents=True, exist_ok=True); intel_dir.mkdir(parents=True, exist_ok=True)
                (policy_dir / "INHERITANCE.yaml").write_text("schema_version: '2.2'\nproject_id: ''\ninherit: false\nparents: []\nlocal:\n  allowed_actions: [handoff, state-pull, state-push, capability-sync, policy-sync]\n  denied_actions: []\n  max_risk: CRITICAL\n  min_evidence: E0\n  domains: []\n  require_signed_handoff: true\n  require_signed_state: true\n  require_approval: false\n", encoding="utf-8")
                (policy_dir / "EFFECTIVE.yaml").write_text("schema_version: '2.2'\nstatus: UNRESOLVED\neffective: {}\n", encoding="utf-8")
                (intel_dir / "CONFLICT-ANALYSIS.yaml").write_text("schema_version: '2.2'\nstatus: NOT_RUN\nconflicts: []\n", encoding="utf-8")
                (intel_dir / "CHECKPOINT-SELECTION.yaml").write_text("schema_version: '2.2'\nstatus: NOT_RUN\nselected: null\ncandidates: []\n", encoding="utf-8")
                (intel_dir / "RECOVERY-RECOMMENDATION.yaml").write_text("schema_version: '2.2'\nstatus: NOT_RUN\nrecommendation: null\n", encoding="utf-8")
                (intel_dir / "README.md").write_text("# UAAF v2.2 Federation Intelligence\n\nAdvisory policy inheritance, conflict classification, sync planning, checkpoint selection, and recovery recommendations. No semantic conflict resolution is applied automatically.\n", encoding="utf-8")

                if args.extension in {"v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
                    data.setdefault("protocols", {})["federation_policy"] = "UAAF-FED-2.3"
                    data["extensions"]["version"] = "2.3"
                    data["extensions"]["federation_policy_negotiation"] = {
                        "contract": ".ai/federation/negotiation/CAPABILITY-CONTRACT.yaml",
                        "negotiation": ".ai/federation/negotiation/NEGOTIATION.yaml",
                        "enforcement": ".ai/federation/negotiation/ENFORCEMENT-POLICY.yaml",
                        "mode": "deny_first_non_escalating",
                    }
                    n_dir = fed / "negotiation"
                    n_dir.mkdir(parents=True, exist_ok=True)
                    (n_dir / "CAPABILITY-CONTRACT.yaml").write_text("schema_version: '2.3'\nstatus: UNNEGOTIATED\npeer_id: ''\ncontract_hash: ''\ncontract: {}\n", encoding="utf-8")
                    (n_dir / "NEGOTIATION.yaml").write_text("schema_version: '2.3'\nstatus: NOT_RUN\npeer_id: ''\noffer_id: ''\nnegotiated_policy: {}\n", encoding="utf-8")
                    (n_dir / "ENFORCEMENT-POLICY.yaml").write_text("schema_version: '2.3'\ndefault_deny: true\nfail_closed: true\n", encoding="utf-8")
                    (n_dir / "README.md").write_text("# UAAF v2.3 Federation Policy Enforcement & Negotiation\n\nNegotiated capability contracts are restrictive intersections of local and remote policy. Negotiation cannot broaden authority. Enforcement is deny-first and requires an active negotiated contract.\n", encoding="utf-8")

                    if args.extension in {"v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
                        data.setdefault("protocols", {})["federation_protocol"] = "UAAF-FED-2.4"
                        data["extensions"]["version"] = "2.4"
                        data["extensions"]["federation_protocol_negotiation"] = {
                            "capabilities": ".ai/federation/protocol/CAPABILITIES.yaml",
                            "compatibility": ".ai/federation/protocol/COMPATIBILITY.yaml",
                            "negotiation": ".ai/federation/protocol/NEGOTIATION.yaml",
                            "contract": ".ai/federation/protocol/PROTOCOL-CONTRACT.yaml",
                            "audit": ".ai/federation/protocol/AUDIT.jsonl",
                            "mode": "deny_first_explicit_fallback",
                        }
                        pr = fed / "protocol"
                        pr.mkdir(parents=True, exist_ok=True)
                        (pr / "CAPABILITIES.yaml").write_text("schema_version: '2.4'\nproject_id: ''\npeer_id: ''\nprotocols:\n  federation: ['2.0']\n  federation_ops: ['2.1']\n  federation_intelligence: ['2.2']\n  federation_policy: ['2.3']\n  federation_protocol: ['2.4']\nfeatures:\n  capability-exchange: {required: true, optional: false, fallback_safe: true, min_protocol: {federation_protocol: '2.4'}}\n  protocol-negotiation: {required: true, optional: false, fallback_safe: true, min_protocol: {federation_protocol: '2.4'}}\n  safe-fallback: {required: false, optional: true, fallback_safe: true, min_protocol: {federation_protocol: '2.4'}}\nsecurity:\n  min_evidence: E3\n  require_signed_offer: true\n  require_signed_contract: true\ncompatibility:\n  fallbacks:\n    federation_protocol: ['2.3']\n", encoding="utf-8")
                        (pr / "COMPATIBILITY.yaml").write_text("schema_version: '2.4'\nstatus: READY\nprotocols:\n  federation_protocol:\n    supported: ['2.4']\n    fallback: ['2.3']\n    fallback_requires_peer_declaration: true\nfeatures:\n  capability-exchange: {requires: federation_protocol, minimum: '2.4'}\n  protocol-negotiation: {requires: federation_protocol, minimum: '2.4'}\n  safe-fallback: {requires: federation_protocol, minimum: '2.4'}\nsecurity:\n  deny_on_unknown: true\n  deny_on_ambiguous_version: true\n", encoding="utf-8")
                        (pr / "NEGOTIATION.yaml").write_text("schema_version: '2.4'\nstatus: NOT_RUN\npeer_id: ''\nselected_protocols: {}\nenabled_features: []\n", encoding="utf-8")
                        (pr / "PROTOCOL-CONTRACT.yaml").write_text("schema_version: '2.4'\nstatus: UNNEGOTIATED\npeer_id: ''\ncontract_hash: ''\ncontract: {}\n", encoding="utf-8")
                        (pr / "AUDIT.jsonl").write_text("", encoding="utf-8")
                        (pr / "README.md").write_text("# UAAF v2.4 Federation Capability Exchange & Protocol Negotiation\n\nCapability exchange and protocol negotiation are explicit, deny-first, and non-escalating. Safe fallback requires explicit declarations from both peers.\n", encoding="utf-8")


                    if args.extension in {"v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
                        data.setdefault("protocols", {})["federation_transport"] = "UAAF-FED-2.5"
                        data["framework"]["version"] = "2.6.0" if args.extension == "v2.6" else "2.5.0"
                        data["extensions"]["version"] = "2.5"
                        data["extensions"]["federation_transport"] = {
                            "channels": ".ai/federation/transport/CHANNELS",
                            "inbox": ".ai/federation/transport/INBOX",
                            "outbox": ".ai/federation/transport/OUTBOX",
                            "audit": ".ai/federation/transport/AUDIT.jsonl",
                            "mode": "transport_agnostic_reference",
                            "confidentiality": False,
                            "authentication": "Ed25519",
                            "integrity": True,
                            "anti_replay": True,
                            "session_binding": True,
                        }
                        td = fed / "transport"
                        for rel in ["CHANNELS", "INBOX", "OUTBOX"]:
                            (td / rel).mkdir(parents=True, exist_ok=True)
                        (td / "AUDIT.jsonl").write_text("", encoding="utf-8")
                        (td / "README.md").write_text(
                            "# UAAF v2.5 Secure Federation Transport\n\nReference transport layer for authenticated, integrity-protected, session-bound federation messaging with sequencing, secure reconnect, and anti-replay. This reference implementation does not provide confidentiality; encrypting transport is a separate concern.\n",
                            encoding="utf-8")
                        (td / "SECURITY-MODEL.md").write_text(
                            "# Transport Security Model\n\nAuthentication: Ed25519 signatures.\nIntegrity: payload hashes + signatures.\nReplay protection: channel sequence numbers.\nSession binding: negotiated protocol contract hash + channel nonce.\nReconnect: signed resume token.\nConfidentiality: NOT PROVIDED by this layer.\n",
                            encoding="utf-8")

                    if args.extension in {"v2.6", "v2.7", "v2.8", "v2.9"}:
                        data.setdefault("protocols", {})["federation_transport_confidential"] = "UAAF-FED-2.6"
                        data["framework"]["version"] = "2.6.0"
                        data["extensions"]["version"] = "2.6"
                        data["extensions"]["federation_confidential_transport"] = {
                            "channels": ".ai/federation/secure/CHANNELS",
                            "inbox": ".ai/federation/secure/INBOX",
                            "outbox": ".ai/federation/secure/OUTBOX",
                            "keys": ".ai/federation/secure/keys",
                            "audit": ".ai/federation/secure/AUDIT.jsonl",
                            "mode": "ephemeral_x25519_aead",
                            "confidentiality": True,
                            "cipher_suite": "ChaCha20-Poly1305",
                            "key_agreement": "X25519",
                            "kdf": "HKDF-SHA256",
                            "forward_secrecy_orientation": "ephemeral_per_epoch",
                            "no_static_session_keys": True,
                        }
                        sd = fed / "secure"
                        for rel in ["CHANNELS", "INBOX", "OUTBOX", "keys"]:
                            (sd / rel).mkdir(parents=True, exist_ok=True)
                        (sd / "AUDIT.jsonl").write_text("", encoding="utf-8")
                        (sd / "keys" / ".gitkeep").write_text("", encoding="utf-8")
                        (sd / "README.md").write_text(
                            "# UAAF v2.6 Confidential Federation Transport\n\nAdds authenticated confidentiality using ephemeral X25519 key agreement, HKDF-SHA256, ChaCha20-Poly1305, per-epoch keys, rekey, and key-erasure semantics. Private ephemeral keys must never be committed or bundled.\n", encoding="utf-8")
                        (sd / "SECURITY-MODEL.md").write_text(
                            "# Confidential Transport Security Model\n\nIdentity authentication: Ed25519.\nKey agreement: ephemeral X25519.\nConfidentiality + integrity: ChaCha20-Poly1305.\nKey derivation: HKDF-SHA256.\nRekey: authenticated fresh ephemeral exchange per epoch.\nOld ephemeral private keys are erased after successful rekey.\nThis layer does not claim traffic analysis resistance or availability.\n", encoding="utf-8")
                        (sd / "CONFIG.yaml").write_text(
                            "schema_version: '2.6'\nenabled: true\nrequire_confidentiality: true\ncipher_suite: ChaCha20-Poly1305\nkey_agreement: X25519\nkdf: HKDF-SHA256\nrekey_enabled: true\n", encoding="utf-8")
                        cap = pr / "CAPABILITIES.yaml"
                        if cap.exists():
                            ctext = cap.read_text(encoding="utf-8")
                            if "confidential-transport:" not in ctext:
                                ctext += "features:\n  confidential-transport: {required: false, optional: true, fallback_safe: false, min_protocol: {federation_protocol: '2.4'}}\n" if "features:" not in ctext else ""
                            # Rewrite through YAML for deterministic merging.
                            try:
                                cdoc = yaml.safe_load(ctext) or {}
                                cdoc.setdefault("features", {})["confidential-transport"] = {"required": False, "optional": True, "fallback_safe": False, "min_protocol": {"federation_protocol": "2.4"}}
                                cap.write_text(yaml.safe_dump(cdoc, sort_keys=False), encoding="utf-8")
                            except Exception:
                                pass

                    if args.extension in {"v2.7", "v2.8", "v2.9"}:
                        data.setdefault("protocols", {})["federation_key_lifecycle"] = "UAAF-FED-2.7"
                        data["framework"]["version"] = "2.7.0"
                        data["extensions"]["version"] = "2.7"
                        data["extensions"]["secure_key_lifecycle"] = {
                            "lifecycle": ".ai/federation/secure/LIFECYCLE.yaml",
                            "revocations": ".ai/federation/secure/KEY-REVOCATIONS.yaml",
                            "storage": ".ai/federation/secure/KEY-STORAGE.yaml",
                            "audit": ".ai/federation/secure/AUDIT.jsonl",
                            "mode": "explicit_lifecycle",
                            "recovery": "new_handshake_required_when_private_state_missing",
                            "secure_erasure": "provider_defined",
                        }
                        sd = fed / "secure"
                        for rel in ["CHANNELS", "INBOX", "OUTBOX", "keys"]:
                            (sd / rel).mkdir(parents=True, exist_ok=True)
                        (sd / "keys" / ".gitkeep").write_text("", encoding="utf-8")
                        (sd / "AUDIT.jsonl").touch(exist_ok=True)
                        (sd / "LIFECYCLE.yaml").write_text("schema_version: '2.7'\nstatus: READY\nupdated_at: ''\nchannels: {}\n", encoding="utf-8")
                        (sd / "KEY-REVOCATIONS.yaml").write_text("schema_version: '2.7'\nrevocation_epoch: 0\nentries: []\n", encoding="utf-8")
                        (sd / "KEY-STORAGE.yaml").write_text("schema_version: '2.7'\nprovider: filesystem\nmode: best_effort_delete\nsecret_export: DISABLED\n", encoding="utf-8")
                        (sd / "KEY-LIFECYCLE.md").write_text(
                            "# UAAF v2.7 Secure Key Lifecycle\n\nChannel close, expiry, revocation, retirement, recovery, and provider abstraction. The reference filesystem provider offers best-effort unlink only; it does not claim forensic secure erasure. Missing private state requires a new authenticated handshake and never resurrects an old channel.\n", encoding="utf-8")
                        cap = pr / "CAPABILITIES.yaml"
                        if cap.exists():
                            try:
                                cdoc = yaml.safe_load(cap.read_text(encoding="utf-8")) or {}
                                cdoc.setdefault("protocols", {})["federation_key_lifecycle"] = ["2.7"]
                                cdoc.setdefault("features", {})["secure-key-lifecycle"] = {"required": False, "optional": True, "fallback_safe": False, "min_protocol": {"federation_protocol": "2.4"}}
                                cap.write_text(yaml.safe_dump(cdoc, sort_keys=False), encoding="utf-8")
                            except Exception:
                                pass

    if args.extension in {"v2.8", "v2.9"}:
        data.setdefault("protocols", {})["federation_key_storage"] = "UAAF-FED-2.8"
        data["framework"]["version"] = "2.8.0"
        data["extensions"]["version"] = "2.8"
        data["extensions"]["key_custody"] = {
            "providers": ".ai/federation/secure/KEY-PROVIDERS.yaml",
            "references": ".ai/federation/secure/KEY-REFERENCES.yaml",
            "health": ".ai/federation/secure/KEY-STORAGE-HEALTH.yaml",
            "storage": ".ai/federation/secure/KEY-STORAGE.yaml",
            "audit": ".ai/federation/secure/KEY-CUSTODY-AUDIT.jsonl",
            "mode": "provider_abstracted",
            "secret_export": "DISABLED",
            "supported_providers": ["filesystem", "os-keychain", "kms", "hsm"],
            "external_kms": "adapter_required"
        }
        fed = destination / ".ai/federation"
        sd = fed / "secure"
        sd.mkdir(parents=True, exist_ok=True)
        (sd / "KEY-PROVIDERS.yaml").write_text(
            "schema_version: '2.8'\nactive_provider: filesystem\nproviders:\n  filesystem:\n    enabled: true\n    mode: reference_local\n    secret_export: DISABLED\n  os-keychain:\n    enabled: false\n    mode: optional_keyring\n    secret_export: DISABLED\n  kms:\n    enabled: false\n    mode: external_signing_adapter\n    secret_export: DISABLED\n  hsm:\n    enabled: false\n    mode: external_signing_adapter\n    secret_export: DISABLED\npolicy:\n  secret_export: DISABLED\n  private_key_return: DISABLED\n  fail_closed_when_unavailable: true\n  allow_filesystem_fallback: false\n", encoding="utf-8")
        (sd / "KEY-REFERENCES.yaml").write_text("schema_version: '2.8'\nreferences: []\n", encoding="utf-8")
        (sd / "KEY-STORAGE-HEALTH.yaml").write_text("schema_version: '2.8'\nstatus: NOT_RUN\nproviders: {}\n", encoding="utf-8")
        (sd / "KEY-CUSTODY-AUDIT.jsonl").write_text("", encoding="utf-8")
        (sd / "KEY-STORAGE.yaml").write_text("schema_version: '2.8'\nprovider: filesystem\nmode: provider_abstracted\nsecret_export: DISABLED\n", encoding="utf-8")
        (sd / "KEY-CUSTODY.md").write_text(
            "# UAAF v2.8 Key Custody\n\nKey lifecycle and key custody are separate concerns. The active provider controls where private material is held. Secret export and private-key return are disabled by policy. The reference build provides a local filesystem provider and optional OS-keychain/external KMS-HSM adapter contracts; cloud KMS/HSM implementations are not bundled.\n", encoding="utf-8")
        pr = fed / "protocol"
        cap = pr / "CAPABILITIES.yaml"
        if cap.exists():
            try:
                cdoc=yaml.safe_load(cap.read_text(encoding="utf-8")) or {}
                cdoc.setdefault("protocols", {})["federation_key_storage"]=["2.8"]
                cdoc.setdefault("features", {})["secure-key-custody"]={"required":False,"optional":True,"fallback_safe":False,"min_protocol":{"federation_protocol":"2.4"}}
                cap.write_text(yaml.safe_dump(cdoc,sort_keys=False),encoding="utf-8")
            except Exception:
                pass

    if args.extension == "v2.9":
        data.setdefault("protocols", {})["federation_key_operations"] = "UAAF-FED-2.9"
        data["framework"]["version"] = "2.9.0"
        data.setdefault("extensions", {})["version"] = "2.9"
        data["extensions"]["key_operations"] = {
            "audit": ".ai/federation/secure/KEY-OPERATIONS-AUDIT.jsonl",
            "mode": "provider_backed_signing",
            "private_key_return": "DISABLED",
            "secret_export": "DISABLED",
            "provider_required": True,
        }
        sd = destination / ".ai/federation/secure"
        sd.mkdir(parents=True, exist_ok=True)
        providers = sd / "KEY-PROVIDERS.yaml"
        if providers.exists():
            try:
                cfg = yaml.safe_load(providers.read_text(encoding="utf-8")) or {}
                cfg["schema_version"] = "2.9"
                cfg.setdefault("providers", {}).setdefault("filesystem", {})["operations"] = {"signing": True, "secret_export": "DISABLED"}
                cfg.setdefault("providers", {}).setdefault("os-keychain", {})["operations"] = {"signing": True, "secret_export": "DISABLED"}
                cfg.setdefault("providers", {}).setdefault("kms", {})["operations"] = {"signing": True, "secret_export": "DISABLED"}
                cfg.setdefault("providers", {}).setdefault("hsm", {})["operations"] = {"signing": True, "secret_export": "DISABLED"}
                cfg.setdefault("policy", {})["provider_backed_signing"] = True
                cfg.setdefault("policy", {})["private_key_return"] = "DISABLED"
                cfg.setdefault("policy", {})["secret_export"] = "DISABLED"
                cfg.setdefault("providers", {}).setdefault("filesystem", {})["material_dir"] = "env:UAAF_KEY_DIR"
                providers.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            except Exception:
                pass
        ops = sd / "KEY-OPERATIONS-AUDIT.jsonl"
        ops.touch(exist_ok=True)
        (sd / "KEY-OPERATIONS.md").write_text(
            "# UAAF v2.9 Provider-backed Key Operations\n\nSigning resolves a key reference through the active custody provider. Callers receive signatures, never private-key material. The filesystem reference provider uses `UAAF_KEY_DIR` outside the repository; external KMS/HSM adapters may implement the same contract without exporting keys.\n", encoding="utf-8")
        cap = pr / "CAPABILITIES.yaml"
        if cap.exists():
            try:
                cdoc = yaml.safe_load(cap.read_text(encoding="utf-8")) or {}
                cdoc.setdefault("protocols", {})["federation_key_operations"]=["2.9"]
                cdoc.setdefault("features", {})["provider-backed-signing"]={"required":False,"optional":True,"fallback_safe":False,"min_protocol":{"federation_protocol":"2.4"}}
                cap.write_text(yaml.safe_dump(cdoc, sort_keys=False), encoding="utf-8")
            except Exception:
                pass

    if requested_extension == "v3.0":
        data["framework"]["version"] = "3.0.0"
        data.setdefault("protocols", {})["federation_runtime"] = "UAAF-FED-3.0"
        data.setdefault("extensions", {})["version"] = "3.0"
        data["extensions"]["federated_agent_runtime"] = {
            "policy": ".ai/federation/runtime/POLICY.yaml",
            "routes": ".ai/federation/runtime/ROUTES.yaml",
            "task_contracts": ".ai/federation/runtime/TASK-CONTRACTS",
            "lease_receipts": ".ai/federation/runtime/LEASE-RECEIPTS",
            "leases": ".ai/federation/runtime/LEASES.yaml",
            "cancellations": ".ai/federation/runtime/CANCELLATIONS",
            "results": ".ai/federation/runtime/RESULTS",
            "evidence": ".ai/federation/runtime/EVIDENCE",
            "provenance": ".ai/federation/runtime/PROVENANCE.jsonl",
            "audit": ".ai/federation/runtime/AUDIT.jsonl",
            "mode": "contract_lease_evidence_provenance",
            "default_deny": True,
            "signed_contract": True,
            "signed_result": True,
            "cancellation": True,
            "timeout": True,
            "provenance_mode": "hash_chain",
        }
        runtime = destination / ".ai/federation/runtime"
        for rel in ["TASK-CONTRACTS", "LEASE-RECEIPTS", "CANCELLATIONS", "RESULTS", "EVIDENCE"]:
            (runtime / rel).mkdir(parents=True, exist_ok=True)
            (runtime / rel / ".gitkeep").write_text("", encoding="utf-8")
        (runtime / "POLICY.yaml").write_text(
            "schema_version: '3.0'\n"
            "default_deny: true\n"
            "require_signed_contract: true\n"
            "require_signed_result: true\n"
            "require_evidence: true\n"
            "allow_silent_scope_expansion: false\n"
            "authority_escalation: false\n"
            "private_key_storage: false\n"
            "max_remote_risk: HIGH\n"
            "max_lease_seconds: 3600\n"
            "result_grace_seconds: 300\n"
            "require_local_agent_authorization: true\n"
            "allow_remote_delete: false\n",
            encoding="utf-8")
        (runtime / "ROUTES.yaml").write_text(
            "schema_version: '3.0'\ndefault_deny: true\npeers: []\n", encoding="utf-8")
        (runtime / "LEASES.yaml").write_text(
            "schema_version: '3.0'\nleases: []\n", encoding="utf-8")
        (runtime / "PROVENANCE.jsonl").write_text("", encoding="utf-8")
        (runtime / "AUDIT.jsonl").write_text("", encoding="utf-8")
        (runtime / "README.md").write_text(
            "# UAAF v3.0 Federated Agent Runtime\n\n"
            "Explicit remote task delegation, capability-aware routing, execution leases, cancellation, signed results/evidence, and end-to-end provenance.\n\n"
            "Remote capability never grants authority. Every execution must be bounded by a signed task contract and a time-limited lease.\n", encoding="utf-8")
        (runtime / "SECURITY-MODEL.md").write_text(
            "# Federated Runtime Security Model\n\n"
            "Authorization: local trust profile + explicit task contract.\n"
            "Authentication: existing v2 federation peer identity.\n"
            "Contract integrity: Ed25519 signature.\n"
            "Execution bound: lease with expiry and terminal cancellation/expiry states.\n"
            "Evidence: signed remote attestation with SHA-256 artifact hashes; independent artifact checking is optional when the artifact is locally available.\n"
            "Provenance: append-only hash chain.\n"
            "Private key storage: delegated to v2.9 custody/provider layer; this runtime stores no private keys.\n", encoding="utf-8")
        cap = destination / ".ai/federation/protocol/CAPABILITIES.yaml"
        if cap.exists():
            try:
                cdoc = yaml.safe_load(cap.read_text(encoding="utf-8")) or {}
                cdoc.setdefault("protocols", {})["federation_runtime"] = ["3.0"]
                cdoc.setdefault("features", {})["federated-agent-runtime"] = {
                    "required": False, "optional": True, "fallback_safe": False,
                    "min_protocol": {"federation_runtime": "3.0"},
                }
                cap.write_text(yaml.safe_dump(cdoc, sort_keys=False), encoding="utf-8")
            except Exception:
                pass

    # Legacy extension installs must not emit federation artifacts.
    if args.extension not in {"v2.0", "v2.1", "v2.2", "v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
        remove_copied_paths(destination, set(copied), ".ai/federation")
    if args.extension not in {"v2.1", "v2.2", "v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
        remove_copied_paths(destination, set(copied), ".ai/federation/ops")
    if args.extension not in {"v2.2", "v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
        # Remove known UAAF v2.2 generated artifacts on explicit downgrade.
        # User-created files are preserved; directories are removed only when empty.
        for rel in [
            ".ai/federation/policy/INHERITANCE.yaml",
            ".ai/federation/policy/EFFECTIVE.yaml",
            ".ai/federation/intelligence/CONFLICT-ANALYSIS.yaml",
            ".ai/federation/intelligence/CHECKPOINT-SELECTION.yaml",
            ".ai/federation/intelligence/RECOVERY-RECOMMENDATION.yaml",
            ".ai/federation/intelligence/README.md",
        ]:
            target = destination / rel
            if target.exists() and target.is_file():
                target.unlink()
        for rel in [".ai/federation/policy", ".ai/federation/intelligence"]:
            d = destination / rel
            if d.exists() and d.is_dir():
                try: d.rmdir()
                except OSError: pass

    if args.extension not in {"v2.3", "v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
        for rel in [
            ".ai/federation/negotiation/CAPABILITY-CONTRACT.yaml",
            ".ai/federation/negotiation/NEGOTIATION.yaml",
            ".ai/federation/negotiation/ENFORCEMENT-POLICY.yaml",
            ".ai/federation/negotiation/README.md",
        ]:
            target = destination / rel
            if target.exists() and target.is_file():
                target.unlink()
        nd = destination / ".ai/federation/negotiation"
        if nd.exists() and nd.is_dir():
            try: nd.rmdir()
            except OSError: pass

    if args.extension not in {"v2.4", "v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
        for rel in [
            ".ai/federation/protocol/CAPABILITIES.yaml",
            ".ai/federation/protocol/COMPATIBILITY.yaml",
            ".ai/federation/protocol/NEGOTIATION.yaml",
            ".ai/federation/protocol/PROTOCOL-CONTRACT.yaml",
            ".ai/federation/protocol/AUDIT.jsonl",
            ".ai/federation/protocol/README.md",
        ]:
            target = destination / rel
            if target.exists() and target.is_file(): target.unlink()
        pr = destination / ".ai/federation/protocol"
        if pr.exists() and pr.is_dir():
            try: pr.rmdir()
            except OSError: pass

    if args.extension not in {"v2.5", "v2.6", "v2.7", "v2.8", "v2.9"}:
        for rel in [
            ".ai/federation/transport/AUDIT.jsonl",
            ".ai/federation/transport/README.md",
            ".ai/federation/transport/SECURITY-MODEL.md",
        ]:
            target = destination / rel
            if target.exists() and target.is_file():
                target.unlink()
        td = destination / ".ai/federation/transport"
        if td.exists() and td.is_dir():
            for sub in ["CHANNELS", "INBOX", "OUTBOX"]:
                d = td / sub
                if d.exists() and d.is_dir():
                    try: d.rmdir()
                    except OSError: pass
            try: td.rmdir()
            except OSError: pass

    if args.extension not in {"v2.6", "v2.7", "v2.8", "v2.9"}:
        for rel in [
            ".ai/federation/secure/AUDIT.jsonl",
            ".ai/federation/secure/README.md",
            ".ai/federation/secure/SECURITY-MODEL.md",
            ".ai/federation/secure/CONFIG.yaml",
            ".ai/federation/secure/keys/.gitkeep",
        ]:
            target = destination / rel
            if target.exists() and target.is_file():
                target.unlink()
        sd = destination / ".ai/federation/secure"
        if sd.exists() and sd.is_dir():
            for sub in ["CHANNELS", "INBOX", "OUTBOX", "keys"]:
                d = sd / sub
                if d.exists() and d.is_dir():
                    try: d.rmdir()
                    except OSError: pass
            try: sd.rmdir()
            except OSError: pass

    if args.extension not in {"v2.7", "v2.8", "v2.9"}:
        for rel in [
            ".ai/federation/secure/LIFECYCLE.yaml",
            ".ai/federation/secure/KEY-REVOCATIONS.yaml",
            ".ai/federation/secure/KEY-STORAGE.yaml",
            ".ai/federation/secure/KEY-LIFECYCLE.md",
        ]:
            target = destination / rel
            if target.exists() and target.is_file():
                target.unlink()

    if args.extension not in {"v2.8", "v2.9"}:
        # Explicit downgrade cleanup: remove only UAAF v2.8-generated custody artifacts.
        for rel in [
            ".ai/federation/secure/KEY-PROVIDERS.yaml",
            ".ai/federation/secure/KEY-REFERENCES.yaml",
            ".ai/federation/secure/KEY-STORAGE-HEALTH.yaml",
            ".ai/federation/secure/KEY-CUSTODY-AUDIT.jsonl",
            ".ai/federation/secure/KEY-CUSTODY.md",
        ]:
            target = destination / rel
            if target.exists() and target.is_file():
                target.unlink()

    if requested_extension != "v3.0":
        runtime = destination / ".ai/federation/runtime"
        for rel in [
            ".ai/federation/runtime/POLICY.yaml",
            ".ai/federation/runtime/ROUTES.yaml",
            ".ai/federation/runtime/LEASES.yaml",
            ".ai/federation/runtime/PROVENANCE.jsonl",
            ".ai/federation/runtime/AUDIT.jsonl",
            ".ai/federation/runtime/README.md",
            ".ai/federation/runtime/SECURITY-MODEL.md",
        ]:
            target = destination / rel
            if target.exists() and target.is_file():
                target.unlink()
        if runtime.exists() and runtime.is_dir():
            for sub in ["TASK-CONTRACTS", "LEASE-RECEIPTS", "CANCELLATIONS", "RESULTS", "EVIDENCE"]:
                d = runtime / sub
                if d.exists() and d.is_dir():
                    for child in list(d.iterdir()):
                        if child.name == ".gitkeep":
                            try: child.unlink()
                            except OSError: pass
                    try: d.rmdir()
                    except OSError: pass
            try: runtime.rmdir()
            except OSError: pass

    if args.extension != "v2.9":
        for rel in [
            ".ai/federation/secure/KEY-OPERATIONS-AUDIT.jsonl",
            ".ai/federation/secure/KEY-OPERATIONS.md",
        ]:
            target = destination / rel
            if target.exists() and target.is_file():
                target.unlink()

    # Extension metadata is finalized after all nested extension branches have run.
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    if skipped:
        print("Preserved existing files:")
        for rel in skipped:
            print(f"  - {rel}")
    print(f"Initialized UAAF {args.profile} at {destination}")


if __name__ == "__main__":
    main()
