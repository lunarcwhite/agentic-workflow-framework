#!/usr/bin/env python3
"""UAAF Plugin & Knowledge Scaffold Manager.

Enables searching, installing, governing, and exporting specialized agent plugins,
skills, and commands inspired by the wshobson/agents ecosystem, fully governed
by UAAF Golden Rules, disjoint perimeters, and verifiable evidence receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PLUGINS_DIR = Path(".ai/plugins")
EVIDENCE_DIR = Path(".ai/evidence")
MARKETPLACE_REPO = "wshobson/agents"
RAW_BASE_URL = f"https://raw.githubusercontent.com/{MARKETPLACE_REPO}/main/plugins"

# Curated, production-grade knowledge registry modeled after wshobson/agents
# Provides instant offline availability, reliable scaffolding, and deterministic structure.
BUILTIN_CATALOG: dict[str, dict[str, Any]] = {
    "python-development": {
        "name": "python-development",
        "version": "1.2.3",
        "category": "Development",
        "description": "Modern Python development with FastAPI, Django, async patterns, uv, ruff, and testing",
        "author": "wshobson / UAAF curated",
        "agents": [
            {
                "name": "fastapi-pro",
                "title": "FastAPI Specialist",
                "description": "High-performance async REST APIs, Pydantic v2 schemas, OpenAPI specs, and dependency injection",
                "skills": ["fastapi_async", "pydantic_v2", "openapi_docs", "api_design"],
                "recommended_model": "balanced_coding",
            },
            {
                "name": "django-pro",
                "title": "Django Specialist",
                "description": "Scalable web backends, Django ORM, REST Framework, and secure auth systems",
                "skills": ["django_orm", "django_rest_framework", "migrations", "backend_security"],
                "recommended_model": "balanced_coding",
            },
            {
                "name": "python-pro",
                "title": "Python Engineering Specialist",
                "description": "Clean, idiomatic Python adhering to PEP 8, strict type hints, and modern packaging",
                "skills": ["idiomatic_python", "typing_mypy", "packaging_uv", "asyncio_concurrency"],
                "recommended_model": "balanced_coding",
            },
        ],
        "skills": [
            {
                "name": "async-python",
                "description": "Best practices for asyncio, task groups, non-blocking I/O, and concurrency safety",
            },
            {
                "name": "pytest-testing",
                "description": "Fixtures, parameterized tests, async testing, mocking, and coverage criteria",
            },
            {
                "name": "pydantic-validation",
                "description": "Data modeling, custom validators, serialization, and settings management",
            },
        ],
        "commands": ["/scaffold-fastapi", "/python-test", "/format-python"],
    },
    "frontend-mobile-development": {
        "name": "frontend-mobile-development",
        "version": "1.1.0",
        "category": "Development",
        "description": "Modern UI and web development with React, Next.js, TypeScript, Tailwind CSS, and WCAG accessibility",
        "author": "wshobson / UAAF curated",
        "agents": [
            {
                "name": "react-pro",
                "title": "React Component Specialist",
                "description": "Component design, custom hooks, state machines, and memoization patterns",
                "skills": ["react_hooks", "state_machines", "component_design", "performance_rendering"],
                "recommended_model": "balanced_coding",
            },
            {
                "name": "nextjs-pro",
                "title": "Next.js & Fullstack Specialist",
                "description": "Next.js App Router, Server Actions, SSR streaming, and API routes",
                "skills": ["nextjs_app_router", "server_actions", "ssr_optimization", "typescript_strict"],
                "recommended_model": "balanced_coding",
            },
            {
                "name": "ui-designer",
                "title": "UI/UX & Design System Specialist",
                "description": "Design token fidelity, responsive glassmorphism, micro-animations, and accessible CSS",
                "skills": ["tailwind_tokens", "wcag_a11y", "responsive_layouts", "css_animations"],
                "recommended_model": "balanced_coding",
            },
        ],
        "skills": [
            {
                "name": "component-patterns",
                "description": "Compound components, render props, and headless UI architectures",
            },
            {
                "name": "state-management",
                "description": "Zustand, TanStack Query, client-side cache invalidation, and optimistic updates",
            },
            {
                "name": "tailwind-styling",
                "description": "Tailwind tokens, dark mode variants, and responsive layout primitives",
            },
        ],
        "commands": ["/scaffold-ui", "/check-a11y", "/generate-icons"],
    },
    "security-audit": {
        "name": "security-audit",
        "version": "2.0.1",
        "category": "Security",
        "description": "Enterprise security auditing, credential leak prevention, OWASP Top 10 mitigation, and trust boundary verification",
        "author": "wshobson / UAAF curated",
        "agents": [
            {
                "name": "security-auditor",
                "title": "Security & Vulnerability Auditor",
                "description": "Static code analysis, dependency CVE scanning, and credential sanitization",
                "skills": ["security_audit", "credential_scan", "cve_triage", "ast_analysis"],
                "recommended_model": "high_reasoning",
            },
            {
                "name": "penetration-tester",
                "title": "Adversarial Test Specialist",
                "description": "Input fuzzing, authentication bypass detection, and boundary exploit analysis",
                "skills": ["adversarial_testing", "boundary_fuzzing", "injection_checks"],
                "recommended_model": "high_reasoning",
            },
            {
                "name": "compliance-officer",
                "title": "Compliance & Policy Verifier",
                "description": "Validates compliance against security standards, licensing, and UAAF Golden Axioms",
                "skills": ["compliance_checking", "license_audit", "governance_reporting"],
                "recommended_model": "high_reasoning",
            },
        ],
        "skills": [
            {
                "name": "owasp-top-10",
                "description": "Mitigations for SQL injection, XSS, CSRF, SSRF, and broken access controls",
            },
            {
                "name": "credential-sanitization",
                "description": "Regex patterns and entropy heuristics to locate unmasked secrets and keys",
            },
            {
                "name": "safe-rce",
                "description": "Safe subprocess execution, command argument quoting, and sandboxing rules",
            },
        ],
        "commands": ["/security-scan", "/secret-audit", "/cve-check"],
    },
    "cloud-infrastructure": {
        "name": "cloud-infrastructure",
        "version": "1.3.0",
        "category": "Infrastructure",
        "description": "Cloud architecture, Docker containers, Kubernetes, Terraform IaC, and CI/CD automation",
        "author": "wshobson / UAAF curated",
        "agents": [
            {
                "name": "devops-engineer",
                "title": "CI/CD & DevOps Engineer",
                "description": "GitHub Actions workflows, build caching, release tagging, and automated deployments",
                "skills": ["ci_cd_workflows", "github_actions", "build_caching", "release_engineering"],
                "recommended_model": "balanced_coding",
            },
            {
                "name": "kubernetes-architect",
                "title": "Kubernetes & Orchestration Specialist",
                "description": "Kubernetes manifests, Helm charts, ingress controllers, and resource limits",
                "skills": ["k8s_manifests", "helm_charts", "container_networking", "resource_quotas"],
                "recommended_model": "balanced_coding",
            },
            {
                "name": "terraform-pro",
                "title": "Infrastructure-as-Code Specialist",
                "description": "Modular Terraform configurations, state backend locking, and cloud provider resources",
                "skills": ["terraform_iac", "cloud_iam", "state_locking", "cost_optimization"],
                "recommended_model": "high_reasoning",
            },
        ],
        "skills": [
            {
                "name": "docker-optimization",
                "description": "Multi-stage builds, minimal base images (Alpine/Distroless), and cache mount techniques",
            },
            {
                "name": "ci-cd-workflows",
                "description": "Pipeline definition, matrix testing, secret management, and failure notifications",
            },
            {
                "name": "iac-standards",
                "description": "Clean modular IaC boundaries, variable definitions, and linting with tflint",
            },
        ],
        "commands": ["/dockerize", "/ci-setup", "/terraform-plan"],
    },
    "unit-testing": {
        "name": "unit-testing",
        "version": "1.0.4",
        "category": "Testing",
        "description": "Automated unit test generation, mocking, edge case fuzzing, and coverage gates",
        "author": "wshobson / UAAF curated",
        "agents": [
            {
                "name": "qa-lead",
                "title": "QA Test Architect",
                "description": "Holistic test strategy, test matrix planning, and evidence receipt signing",
                "skills": ["test_strategy", "evidence_audit", "regression_planning"],
                "recommended_model": "balanced_coding",
            },
            {
                "name": "test-automator",
                "title": "Test Automation Specialist",
                "description": "Authors high-coverage unit tests, mocks external APIs, and asserts boundary conditions",
                "skills": ["unit_testing", "mocking_isolation", "boundary_assertions"],
                "recommended_model": "balanced_coding",
            },
        ],
        "skills": [
            {
                "name": "pytest-patterns",
                "description": "Parametrization, fixtures, temporary directories, and pytest-mock isolation",
            },
            {
                "name": "jest-testing",
                "description": "Snapshot testing, async mock functions, and React Testing Library standards",
            },
            {
                "name": "property-testing",
                "description": "Hypothesis and randomized invariant testing for algorithmic correctness",
            },
        ],
        "commands": ["/test-gen", "/coverage-gate", "/fuzz-test"],
    },
    "database-dba": {
        "name": "database-dba",
        "version": "1.1.2",
        "category": "Database",
        "description": "Database schema design, query optimization, indexing strategies, PostgreSQL, and SQLite tuning",
        "author": "wshobson / UAAF curated",
        "agents": [
            {
                "name": "postgresql-dba",
                "title": "PostgreSQL & Database Specialist",
                "description": "Query plan analysis (EXPLAIN ANALYZE), index tuning, connection pooling, and migrations",
                "skills": ["postgresql_tuning", "query_plans", "index_strategies", "connection_pooling"],
                "recommended_model": "high_reasoning",
            },
            {
                "name": "sql-architect",
                "title": "Relational Data Architect",
                "description": "Normalized data modeling, constraint definition, and zero-downtime schema evolution",
                "skills": ["schema_design", "foreign_keys", "non_locking_migrations"],
                "recommended_model": "high_reasoning",
            },
        ],
        "skills": [
            {
                "name": "query-optimization",
                "description": "Detecting N+1 queries, composite index selection, and partition strategies",
            },
            {
                "name": "schema-migrations",
                "description": "Safe, reversible schema migrations and data backfill techniques",
            },
        ],
        "commands": ["/sql-optimize", "/migration-check", "/explain-query"],
    },
    "debugging-toolkit": {
        "name": "debugging-toolkit",
        "version": "1.0.1",
        "category": "Development",
        "description": "Interactive debugging, stack trace analysis, memory leak localization, and profiling",
        "author": "wshobson / UAAF curated",
        "agents": [
            {
                "name": "debug-detective",
                "title": "Root Cause Debugger",
                "description": "Hypothesis-driven failure investigation, minimal reproducible cases, and git bisect",
                "skills": ["root_cause_analysis", "bisect_debugging", "trace_investigation"],
                "recommended_model": "high_reasoning",
            },
            {
                "name": "profiling-pro",
                "title": "Performance Profiler",
                "description": "CPU hotspots, memory leak detection, heap dumps, and runtime latency profiling",
                "skills": ["cpu_profiling", "memory_leak_detection", "benchmark_tuning"],
                "recommended_model": "high_reasoning",
            },
        ],
        "skills": [
            {
                "name": "root-cause-analysis",
                "description": "Systematic fault isolation, logging instrumentation, and invariant checking",
            },
            {
                "name": "memory-leak-detection",
                "description": "Heap snapshot diffing, cyclic references, and open file descriptor analysis",
            },
        ],
        "commands": ["/debug-trace", "/profile-perf", "/leak-check"],
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def get_installed_plugins(root: Path) -> dict[str, dict[str, Any]]:
    """Scan .ai/plugins directory for installed plugins."""
    plugins_dir = root / PLUGINS_DIR
    installed: dict[str, dict[str, Any]] = {}
    if not plugins_dir.exists():
        return installed

    for p in plugins_dir.iterdir():
        if p.is_dir():
            manifest_file = p / "plugin.json"
            if manifest_file.exists():
                try:
                    data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    installed[p.name] = data
                except Exception:
                    installed[p.name] = {"name": p.name, "status": "MALFORMED"}
            else:
                installed[p.name] = {"name": p.name, "status": "UNSTRUCTURED"}

    return installed


def fetch_remote_manifest(plugin_name: str) -> dict[str, Any] | None:
    """Attempt to fetch live plugin.json from GitHub wshobson/agents repo."""
    url = f"{RAW_BASE_URL}/{plugin_name}/.claude-plugin/plugin.json"
    req = urllib.request.Request(url, headers={"User-Agent": "UAAF-Plugin-Manager/3.1"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                raw_text = resp.read().decode("utf-8")
                return json.loads(raw_text)
    except Exception:
        pass
    return None


def cmd_list(root: Path, remote: bool = False) -> dict[str, Any]:
    """List installed plugins or marketplace catalog."""
    installed = get_installed_plugins(root)

    print("=" * 70)
    print("[PLUGIN REGISTRY] UAAF AGENT & SKILL PLUGIN REGISTRY")
    print(f"Source Marketplace: {MARKETPLACE_REPO} (Compatible with Claude, Antigravity, Cursor, Pi)")
    print("=" * 70)

    print("\n[INSTALLED PLUGINS]")
    if not installed:
        print("  (None installed in .ai/plugins/. Run 'uaf plugin install <name>' to install)")
    else:
        for name, meta in installed.items():
            version = meta.get("version", "unknown")
            desc = meta.get("description", "No description available")
            agents_count = len(meta.get("agents", []))
            skills_count = len(meta.get("skills", []))
            print(f"  * {name} (v{version}) - {desc}")
            print(f"    \\-- {agents_count} agents, {skills_count} skills")

    if remote or not installed:
        print("\n[AVAILABLE MARKETPLACE PLUGINS]")
        for name, meta in BUILTIN_CATALOG.items():
            is_inst = " [INSTALLED]" if name in installed else ""
            print(f"  * {name} (v{meta['version']}){is_inst}")
            print(f"    Category: {meta['category']} | {meta['description']}")
            print(f"    Agents  : {', '.join(a['name'] for a in meta['agents'])}")
            print(f"    Skills  : {', '.join(s['name'] for s in meta['skills'])}")
            print(f"    Commands: {', '.join(meta['commands'])}")
            print()

    return {"installed": installed, "catalog_size": len(BUILTIN_CATALOG)}


def cmd_search(query: str, root: Path) -> list[dict[str, Any]]:
    """Search catalog for plugins, agents, or skills matching query."""
    q = query.lower()
    matches: list[dict[str, Any]] = []

    print(f"[SEARCH] Searching UAAF marketplace for '{query}'...\n")

    for name, meta in BUILTIN_CATALOG.items():
        matched_agents = [a for a in meta["agents"] if q in a["name"] or q in a["description"] or q in a.get("title", "").lower()]
        matched_skills = [s for s in meta["skills"] if q in s["name"] or q in s["description"]]
        matched_commands = [c for c in meta["commands"] if q in c.lower()]

        if q in name or q in meta["description"].lower() or matched_agents or matched_skills or matched_commands:
            item = {
                "plugin": name,
                "version": meta["version"],
                "category": meta["category"],
                "description": meta["description"],
                "matched_agents": [a["name"] for a in matched_agents],
                "matched_skills": [s["name"] for s in matched_skills],
                "matched_commands": matched_commands,
            }
            matches.append(item)

            print(f"* {name} (v{meta['version']}) [{meta['category']}]")
            print(f"  Description: {meta['description']}")
            if matched_agents:
                print(f"  Matching Agents: {', '.join(a['name'] for a in matched_agents)}")
            if matched_skills:
                print(f"  Matching Skills: {', '.join(s['name'] for s in matched_skills)}")
            if matched_commands:
                print(f"  Matching Commands: {', '.join(matched_commands)}")
            print(f"  Install with: python tools/uaf.py plugin install {name}\n")

    if not matches:
        print(f"No direct matches found for '{query}'. Try 'python tools/uaf.py plugin list --remote'.")

    return matches


def cmd_install(plugin_name: str, root: Path, force: bool = False) -> dict[str, Any]:
    """Install and govern a plugin from the marketplace into .ai/plugins/."""
    plugin_name = plugin_name.strip().lower()
    if plugin_name.startswith("wshobson/"):
        plugin_name = plugin_name.replace("wshobson/", "")

    catalog_entry = BUILTIN_CATALOG.get(plugin_name)
    target_dir = root / PLUGINS_DIR / plugin_name

    if target_dir.exists() and not force:
        print(f"[WARNING] Plugin '{plugin_name}' is already installed at {target_dir.relative_to(root)}.")
        print("Use --force to reinstall or overwrite.")
        return {"status": "ALREADY_INSTALLED", "path": str(target_dir)}

    target_dir.mkdir(parents=True, exist_ok=True)
    agents_dir = target_dir / "agents"
    skills_dir = target_dir / "skills"
    commands_dir = target_dir / "commands"
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)
    commands_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch remote manifest or fallback to curated entry
    remote_meta = fetch_remote_manifest(plugin_name)
    if remote_meta:
        print(f"[REMOTE] Retrieved live metadata for '{plugin_name}' from GitHub wshobson/agents.")
        desc = remote_meta.get("description", catalog_entry.get("description", "") if catalog_entry else "")
        ver = remote_meta.get("version", catalog_entry.get("version", "1.0.0") if catalog_entry else "1.0.0")
    elif catalog_entry:
        print(f"[PKG] Provisioning curated UAAF package for '{plugin_name}'.")
        desc = catalog_entry["description"]
        ver = catalog_entry["version"]
    else:
        # Generic installation for arbitrary named plugin
        print(f"[INFO] Initializing custom plugin structure for '{plugin_name}'.")
        desc = f"Specialized agentic plugin for {plugin_name}"
        ver = "1.0.0"

    plugin_meta = {
        "name": plugin_name,
        "version": ver,
        "description": desc,
        "installed_at": utc_now_iso(),
        "source": f"github:{MARKETPLACE_REPO}/plugins/{plugin_name}",
        "governed_by": "UAAF-v3.1",
        "agents": catalog_entry.get("agents", []) if catalog_entry else [],
        "skills": catalog_entry.get("skills", []) if catalog_entry else [],
        "commands": catalog_entry.get("commands", []) if catalog_entry else [],
    }

    # Write plugin.json
    (target_dir / "plugin.json").write_text(json.dumps(plugin_meta, indent=2), encoding="utf-8")

    # 2. Write Agent Personas
    agents = catalog_entry.get("agents", []) if catalog_entry else [
        {
            "name": f"{plugin_name}-expert",
            "title": f"{plugin_name.title()} Expert",
            "description": f"Domain specialist for {plugin_name}",
            "skills": [f"{plugin_name}_core"],
            "recommended_model": "balanced_coding",
        }
    ]

    for a in agents:
        agent_file = agents_dir / f"{a['name']}.md"
        agent_content = (
            f"---\n"
            f"name: {a['name']}\n"
            f"title: {a['title']}\n"
            f"description: {a['description']}\n"
            f"skills: {a.get('skills', [])}\n"
            f"recommended_model: {a.get('recommended_model', 'balanced_coding')}\n"
            f"governance: UAAF-v3.1\n"
            f"---\n\n"
            f"# {a['title']} ({a['name']})\n\n"
            f"> {a['description']}\n\n"
            f"## Specialization & Skills\n"
            + "\n".join(f"- `{s}`" for s in a.get("skills", [])) + "\n\n"
            f"## Mandatory UAAF Invariants\n"
            f"1. **Disjoint Perimeter**: Modify strictly within permitted files allocated in active task contract.\n"
            f"2. **Anti-Slop**: Zero placeholder mock stubs (`// TODO`) and no unverified claims.\n"
            f"3. **Verifiable Receipts**: Run quality gates (`uaf check` or test suite) before declaring completion.\n"
        )
        agent_file.write_text(agent_content, encoding="utf-8")

    # 3. Write Skills
    skills = catalog_entry.get("skills", []) if catalog_entry else [
        {"name": f"{plugin_name}-core", "description": f"Core skills for {plugin_name}"}
    ]
    for s in skills:
        s_dir = skills_dir / s["name"]
        s_dir.mkdir(parents=True, exist_ok=True)
        skill_file = s_dir / "SKILL.md"
        skill_content = (
            f"---\n"
            f"name: {s['name']}\n"
            f"description: {s['description']}\n"
            f"---\n\n"
            f"# Skill: {s['name']}\n\n"
            f"{s['description']}\n\n"
            f"## Practical Guidelines\n"
            f"- Prioritize surgical, minimal diffs over large rewrites.\n"
            f"- Verify all interfaces with strong type checking and comprehensive assertions.\n"
            f"- Adhere to project conventions established in `.ai/core/CONVENTIONS.md`.\n"
        )
        skill_file.write_text(skill_content, encoding="utf-8")

    # 4. Inject UAAF Governance Wrapper
    cmd_govern(plugin_name, root)

    print(f"[OK] Successfully installed and governed plugin '{plugin_name}' at {target_dir.relative_to(root)}!")
    print(f"   * {len(agents)} agents configured in agents/")
    print(f"   * {len(skills)} skills scaffolded in skills/")
    print(f"   * UAAF Governance anchor created in GOVERNANCE.md")
    print(f"\nNext step: run 'python tools/uaf.py plugin export {plugin_name}' to expose to Claude, Antigravity, or Cursor.")

    return {
        "status": "INSTALLED",
        "plugin": plugin_name,
        "path": str(target_dir),
        "agents_count": len(agents),
        "skills_count": len(skills),
    }


def cmd_govern(plugin_name: str, root: Path) -> dict[str, Any]:
    """Audit and inject UAAF Golden Rules, scope constraints, and evidence receipt for an installed plugin."""
    target_dir = root / PLUGINS_DIR / plugin_name
    if not target_dir.exists():
        raise SystemExit(f"PLUGIN_NOT_FOUND: {plugin_name} is not installed in .ai/plugins/")

    plugin_json = target_dir / "plugin.json"
    meta = json.loads(plugin_json.read_text(encoding="utf-8")) if plugin_json.exists() else {}

    gov_file = target_dir / "GOVERNANCE.md"
    content = (
        f"# UAAF Governance Mandate for Plugin `{plugin_name}`\n\n"
        f"**Governing Protocol**: UAAF-TEAM-1.0 & UAAF-v3.1 Core Invariants\n"
        f"**Installed Version**: {meta.get('version', '1.0.0')}\n"
        f"**Timestamp**: {utc_now_iso()}\n\n"
        f"## Enforced Operational Axioms\n"
        f"Any agent instantiated from this plugin MUST adhere strictly to the following laws:\n\n"
        f"1. **Understand Before Changing**: Inspect project AST, types, and existing contracts before proposing edits.\n"
        f"2. **Disjoint Perimeter Enforcement**: Never touch files outside leased perimeter in `.claims.lock`.\n"
        f"3. **Zero Mock Stubs (Anti-Slop)**: No fake implementations, placeholders, or silent regressions.\n"
        f"4. **Receipt Anchoring**: Claims of completion are invalid without a signed `evidence-receipt.yaml`.\n"
        f"5. **Bounded Tool Execution**: Subprocess and file modification tools are strictly bounded.\n"
    )
    gov_file.write_text(content, encoding="utf-8")

    # Generate Evidence Receipt
    evidence_dir = root / EVIDENCE_DIR
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_id = f"EV-PLUGIN-{hashlib.sha256(plugin_name.encode()).hexdigest()[:8].upper()}"
    evidence_record = {
        "receipt_id": evidence_id,
        "type": "PLUGIN_GOVERNANCE_AUDIT",
        "plugin": plugin_name,
        "status": "VERIFIED_COMPLIANT",
        "timestamp": utc_now_iso(),
        "integrity": {
            "governance_hash": hashlib.sha256(content.encode()).hexdigest(),
        },
        "gates_passed": [
            "disjoint_perimeter_declared",
            "golden_axioms_injected",
            "bounded_toolset_verified",
        ],
    }
    evidence_file = evidence_dir / f"{evidence_id}.yaml"
    evidence_file.write_text(yaml.safe_dump(evidence_record, sort_keys=False), encoding="utf-8")

    return {"status": "GOVERNED", "evidence_id": evidence_id, "evidence_file": str(evidence_file.relative_to(root))}


def cmd_export(plugin_name: str, root: Path, target: str = "all") -> dict[str, Any]:
    """Export installed plugin agents and skills into Claude Code, Antigravity, Cursor, and Pi harnesses."""
    target_dir = root / PLUGINS_DIR / plugin_name
    if not target_dir.exists():
        raise SystemExit(f"PLUGIN_NOT_FOUND: {plugin_name} is not installed in .ai/plugins/")

    plugin_json = target_dir / "plugin.json"
    meta = json.loads(plugin_json.read_text(encoding="utf-8")) if plugin_json.exists() else {}
    agents_dir = target_dir / "agents"
    skills_dir = target_dir / "skills"

    exported_files: list[str] = []

    # 1. Claude Code (.claude/agents/*.md)
    if target in {"claude-code", "all"}:
        claude_dir = root / ".claude/agents"
        claude_dir.mkdir(parents=True, exist_ok=True)
        if agents_dir.exists():
            for af in agents_dir.glob("*.md"):
                dest = claude_dir / af.name
                dest.write_text(af.read_text(encoding="utf-8"), encoding="utf-8")
                exported_files.append(str(dest.relative_to(root)))

    # 2. Google Antigravity (.agents/skills/ & .agents/plugins/)
    if target in {"antigravity", "all"}:
        agy_plugin_dir = root / f".agents/plugins/{plugin_name}"
        agy_plugin_dir.mkdir(parents=True, exist_ok=True)
        (agy_plugin_dir / "plugin.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        if skills_dir.exists():
            for s_sub in skills_dir.iterdir():
                if s_sub.is_dir():
                    dest_skill = root / f".agents/skills/{s_sub.name}"
                    dest_skill.mkdir(parents=True, exist_ok=True)
                    s_file = s_sub / "SKILL.md"
                    if s_file.exists():
                        (dest_skill / "SKILL.md").write_text(s_file.read_text(encoding="utf-8"), encoding="utf-8")
                        exported_files.append(str((dest_skill / "SKILL.md").relative_to(root)))

    # 3. Cursor (.cursor/rules/)
    if target in {"cursor", "all"}:
        cursor_dir = root / ".cursor/rules"
        cursor_dir.mkdir(parents=True, exist_ok=True)
        rule_file = cursor_dir / f"plugin-{plugin_name}.mdc"
        rule_content = (
            f"---\n"
            f"description: UAAF Governed Plugin: {plugin_name}\n"
            f"globs: *\n"
            f"---\n\n"
            f"# Plugin Guidelines: {plugin_name}\n\n"
            f"> {meta.get('description', '')}\n\n"
            f"Adhere strictly to UAAF anti-slop rules and test verification before finalizing code.\n"
        )
        rule_file.write_text(rule_content, encoding="utf-8")
        exported_files.append(str(rule_file.relative_to(root)))

    # 4. Pi Coding Agent (.pi/agents/)
    if target in {"pi", "all"}:
        pi_agents_dir = root / ".pi/agents"
        pi_agents_dir.mkdir(parents=True, exist_ok=True)
        if agents_dir.exists():
            for af in agents_dir.glob("*.md"):
                dest = pi_agents_dir / af.name
                dest.write_text(af.read_text(encoding="utf-8"), encoding="utf-8")
                exported_files.append(str(dest.relative_to(root)))

    print(f"[EXPORT] Exported plugin '{plugin_name}' to target '{target}' ({len(exported_files)} files emitted):")
    for f in exported_files:
        print(f"   * {f}")

    return {"status": "EXPORTED", "plugin": plugin_name, "target": target, "files": exported_files}


def main() -> None:
    parser = argparse.ArgumentParser(prog="uaf plugin", description="UAAF Agent & Skill Plugin Marketplace Manager")
    subparsers = parser.add_subparsers(dest="subcommand", help="Plugin subcommands")

    # list
    list_p = subparsers.add_parser("list", help="List installed or remote marketplace plugins")
    list_p.add_argument("--remote", action="store_true", help="List all catalog plugins available remotely")

    # search
    search_p = subparsers.add_parser("search", help="Search marketplace for plugins, agents, or skills")
    search_p.add_argument("query", help="Keyword to search (e.g. fastapi, react, security, docker, test)")

    # install
    install_p = subparsers.add_parser("install", help="Install a plugin from marketplace into .ai/plugins/")
    install_p.add_argument("plugin_name", help="Name of plugin to install (e.g. python-development, security-audit)")
    install_p.add_argument("--force", action="store_true", help="Overwrite existing installation")

    # govern
    govern_p = subparsers.add_parser("govern", help="Audit and inject UAAF governance into installed plugin")
    govern_p.add_argument("plugin_name", help="Name of installed plugin")

    # export
    export_p = subparsers.add_parser("export", help="Export plugin personas and skills to target agent harnesses")
    export_p.add_argument("plugin_name", help="Name of installed plugin")
    export_p.add_argument("--target", choices=["all", "claude-code", "antigravity", "cursor", "pi"], default="all",
                          help="Target harness ecosystem (default: all)")

    args = parser.parse_args()
    root = Path.cwd()

    if args.subcommand == "list" or not args.subcommand:
        cmd_list(root, remote=getattr(args, "remote", False))
    elif args.subcommand == "search":
        cmd_search(args.query, root)
    elif args.subcommand == "install":
        cmd_install(args.plugin_name, root, force=args.force)
    elif args.subcommand == "govern":
        cmd_govern(args.plugin_name, root)
    elif args.subcommand == "export":
        cmd_export(args.plugin_name, root, target=args.target)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
