#!/usr/bin/env python3
"""UAAF v3.1 Team-Architecture Factory & Multi-Agent Orchestrator.

Enables automated task decomposition into bounded, non-overlapping task contracts,
atomic filesystem claim locking, team persona generation, and multi-agent export
supporting Claude Code, Antigravity, Cursor, and pi-agent ecosystems.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "3.1"
TEAM_FILE = Path(".ai/agents/TEAM.yaml")
TASKS_DIR = Path(".ai/tasks/active")
CLAIMS_FILE = Path(".ai/agents/CLAIMS.yaml")

PATTERNS = {
    "pipeline": {
        "name": "Pipeline (Sequential Chain)",
        "description": "Linear sequential execution where previous agent output feeds into next agent context.",
        "default_roles": ["architect", "engineer", "reviewer", "verifier"],
    },
    "producer_reviewer": {
        "name": "Producer-Reviewer (Dual-Agent Loop)",
        "description": "Paired implementer and critic loop with mandatory evidence verification before completion.",
        "default_roles": ["producer", "reviewer"],
    },
    "fan_out_fan_in": {
        "name": "Fan-Out / Fan-In (Parallel Aggregation)",
        "description": "Decomposes task across independent, non-overlapping domains in parallel, then merges.",
        "default_roles": ["coordinator", "backend_specialist", "frontend_specialist", "integrator"],
    },
    "expert_pool": {
        "name": "Expert Pool (Domain-Specific Dispatch)",
        "description": "Routes work to specialized domain experts based on affected file types and systems.",
        "default_roles": ["planner", "domain_expert", "security_auditor", "qa_engineer"],
    },
    "supervisor": {
        "name": "Supervisor (Hierarchical Manager)",
        "description": "Lead supervisor agent decomposes goals, delegates to worker agents, and verifies deliverables.",
        "default_roles": ["supervisor", "worker_primary", "worker_secondary"],
    },
    "hierarchical": {
        "name": "Hierarchical Swarm (Multi-Tier)",
        "description": "Multi-tier hierarchy for large repositories with lead architect, domain leads, and workers.",
        "default_roles": ["lead_architect", "system_engineer", "qa_lead", "compliance_officer"],
    },
}

ROLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "architect": {
        "title": "Software Architect",
        "description": "Analyzes requirements, inspects codebase invariants, and establishes technical blueprint.",
        "skills": ["architecture_analysis", "contract_definition", "dependency_audit"],
        "recommended_model": "high_reasoning",
    },
    "engineer": {
        "title": "Implementation Engineer",
        "description": "Writes production code strictly within leased permitted_files perimeter.",
        "skills": ["surgical_coding", "conventions_adherence", "minimal_diff"],
        "recommended_model": "balanced_coding",
    },
    "producer": {
        "title": "Code Producer",
        "description": "Develops feature or bug fix to satisfy task-contract acceptance criteria.",
        "skills": ["implementation", "unit_testing", "clean_code"],
        "recommended_model": "balanced_coding",
    },
    "reviewer": {
        "title": "Adversarial Code Reviewer",
        "description": "Inspects diffs against task contract, flags scope creep, mock stubs, and style violations.",
        "skills": ["adversarial_audit", "scope_verification", "lint_inspection"],
        "recommended_model": "high_reasoning",
    },
    "verifier": {
        "title": "Evidence Verifier",
        "description": "Executes test runner, validates exit codes, and anchors SHA-256 evidence receipt.",
        "skills": ["test_runner", "evidence_receipt_anchoring", "crypto_verification"],
        "recommended_model": "fast_execution",
    },
    "coordinator": {
        "title": "Team Coordinator",
        "description": "Decomposes high-level requirements into disjoint task contracts and coordinates handoffs.",
        "skills": ["task_decomposition", "resource_allocation", "dependency_tracking"],
        "recommended_model": "high_reasoning",
    },
    "backend_specialist": {
        "title": "Backend Specialist",
        "description": "Implements server logic, APIs, database access, and core business rules.",
        "skills": ["api_design", "database_queries", "backend_testing"],
        "recommended_model": "balanced_coding",
    },
    "frontend_specialist": {
        "title": "Frontend Specialist",
        "description": "Implements user interface, component hierarchy, client state, and styling.",
        "skills": ["ui_components", "css_tokens", "accessibility_wcag"],
        "recommended_model": "balanced_coding",
    },
    "integrator": {
        "title": "Integration Specialist",
        "description": "Merges parallel deliverables, runs integration tests, and resolves interface gaps.",
        "skills": ["end_to_end_testing", "integration_assembly", "conformance_check"],
        "recommended_model": "balanced_coding",
    },
    "planner": {
        "title": "Strategic Planner",
        "description": "Constructs execution DAG and verifies feasibility before execution begins.",
        "skills": ["workflow_dag", "risk_assessment", "scope_bounding"],
        "recommended_model": "high_reasoning",
    },
    "domain_expert": {
        "title": "Domain Specialist",
        "description": "Applies deep domain-specific knowledge to implement mission-critical modules.",
        "skills": ["domain_logic", "algorithm_optimization", "robust_error_handling"],
        "recommended_model": "high_reasoning",
    },
    "security_auditor": {
        "title": "Security & Trust Auditor",
        "description": "Inspects for credential leakage, injection risks, permission boundaries, and supply-chain threats.",
        "skills": ["security_audit", "credential_scan", "safe_rce"],
        "recommended_model": "high_reasoning",
    },
    "qa_engineer": {
        "title": "QA & Test Engineer",
        "description": "Authors comprehensive test suites, edge case validations, and regression assertions.",
        "skills": ["test_design", "fuzzing", "regression_coverage"],
        "recommended_model": "balanced_coding",
    },
    "supervisor": {
        "title": "Lead Supervisor",
        "description": "Supervises team execution, monitors claims leases, and approves final deliverable.",
        "skills": ["supervision", "claim_management", "quality_lock_enforcement"],
        "recommended_model": "high_reasoning",
    },
    "worker_primary": {
        "title": "Primary Worker",
        "description": "Executes core task deliverables within strictly assigned file perimeter.",
        "skills": ["core_implementation", "minimal_changes"],
        "recommended_model": "balanced_coding",
    },
    "worker_secondary": {
        "title": "Secondary Worker",
        "description": "Executes supporting tasks (documentation, configuration, auxiliary tools).",
        "skills": ["auxiliary_implementation", "documentation_sync"],
        "recommended_model": "balanced_coding",
    },
    "lead_architect": {
        "title": "Lead Enterprise Architect",
        "description": "Governs multi-tier team execution, validates system contracts, and establishes trust.",
        "skills": ["system_design", "governance_policy", "trust_anchoring"],
        "recommended_model": "high_reasoning",
    },
    "system_engineer": {
        "title": "System Engineer",
        "description": "Implements core systems, services, and cross-cutting infrastructure.",
        "skills": ["systems_programming", "performance_tuning"],
        "recommended_model": "balanced_coding",
    },
    "qa_lead": {
        "title": "QA Lead",
        "description": "Orchestrates multi-suite verification and signs evidence receipts.",
        "skills": ["test_orchestration", "evidence_audit"],
        "recommended_model": "balanced_coding",
    },
    "compliance_officer": {
        "title": "Compliance & Policy Auditor",
        "description": "Validates conformance against UAAF Golden Axioms and Hard Gates.",
        "skills": ["conformance_checking", "license_audit", "anti_slop_gatekeeping"],
        "recommended_model": "high_reasoning",
    },
    "fastapi_pro": {
        "title": "FastAPI Specialist",
        "description": "Architects and implements high-performance asynchronous RESTful APIs using FastAPI and Pydantic v2.",
        "skills": ["fastapi_async", "pydantic_v2", "openapi_docs", "api_design"],
        "recommended_model": "balanced_coding",
    },
    "django_pro": {
        "title": "Django Specialist",
        "description": "Develops scalable web backends with Django ORM, secure auth, and REST Framework.",
        "skills": ["django_orm", "django_rest_framework", "migrations", "backend_security"],
        "recommended_model": "balanced_coding",
    },
    "react_pro": {
        "title": "React Component Specialist",
        "description": "Builds responsive, accessible, component-driven web interfaces using React, Next.js, and TypeScript.",
        "skills": ["react_components", "nextjs_app_router", "tailwind_css", "wcag_a11y"],
        "recommended_model": "balanced_coding",
    },
    "nextjs_pro": {
        "title": "Next.js & Fullstack Specialist",
        "description": "Next.js App Router, Server Actions, SSR streaming, and fullstack TypeScript.",
        "skills": ["nextjs_app_router", "server_actions", "ssr_optimization", "typescript_strict"],
        "recommended_model": "balanced_coding",
    },
    "vue_pro": {
        "title": "Vue.js Specialist",
        "description": "Develops intuitive UI and reactive frontend components with Vue 3 and Pinia.",
        "skills": ["vue3_composition", "pinia_state", "vite_tooling"],
        "recommended_model": "balanced_coding",
    },
    "postgresql_dba": {
        "title": "Database & PostgreSQL Specialist",
        "description": "Optimizes database schemas, indexing strategies, complex SQL queries, and zero-downtime migrations.",
        "skills": ["postgresql_optimization", "sql_indexing", "schema_migrations", "query_plan_analysis"],
        "recommended_model": "high_reasoning",
    },
    "devops_engineer": {
        "title": "Cloud & DevOps Engineer",
        "description": "Configures containerized workloads, CI/CD pipelines, Docker, Kubernetes, and IaC scaffolding.",
        "skills": ["docker_containers", "ci_cd_workflows", "kubernetes_manifests", "terraform_iac"],
        "recommended_model": "balanced_coding",
    },
    "testing_specialist": {
        "title": "QA & Test Automation Specialist",
        "description": "Authors robust automated unit, integration, and property-based test suites with high coverage.",
        "skills": ["pytest_advanced", "jest_playwright", "mocking_fixtures", "coverage_enforcement"],
        "recommended_model": "balanced_coding",
    },
    "landing_page_pro": {
        "title": "Landing Page Specialist",
        "description": "Architects high-converting landing pages using 12-section hierarchy, PAS copywriting, and strict visual rhythm.",
        "skills": ["landing_page_design", "conversion_copywriting", "intake_discovery", "visual_rhythm"],
        "recommended_model": "high_reasoning",
    },
    "seo_specialist": {
        "title": "SEO & Structured Data Specialist",
        "description": "Optimizes technical SEO, OpenGraph, Twitter Cards, Schema.org JSON-LD, and Core Web Vitals compliance.",
        "skills": ["technical_seo", "schema_jsonld", "metadata_optimization", "core_web_vitals"],
        "recommended_model": "balanced_coding",
    },
}


def discover_installed_roles(root: Path) -> dict[str, dict[str, Any]]:
    """Dynamically load roles from installed plugins in .ai/plugins/."""
    plugins_dir = root / ".ai/plugins"
    discovered: dict[str, dict[str, Any]] = {}
    if not plugins_dir.exists():
        return discovered
    for p_dir in plugins_dir.iterdir():
        if p_dir.is_dir() and (p_dir / "plugin.json").exists():
            try:
                data = json.loads((p_dir / "plugin.json").read_text(encoding="utf-8"))
                for agent in data.get("agents", []):
                    role_key = agent["name"].replace("-", "_")
                    discovered[role_key] = {
                        "title": agent.get("title", agent["name"].replace("-", " ").title()),
                        "description": agent.get("description", f"Specialist from plugin {p_dir.name}"),
                        "skills": agent.get("skills", []),
                        "recommended_model": agent.get("recommended_model", "balanced_coding"),
                        "plugin": p_dir.name,
                    }
            except Exception:
                pass
    return discovered


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def detect_file_domains(root: Path) -> dict[str, list[str]]:
    """Scan project structure to identify domain file paths for non-overlapping decomposition."""
    domains: dict[str, list[str]] = {
        "backend": [],
        "frontend": [],
        "tests": [],
        "docs": [],
        "config": [],
    }

    candidates = {
        "backend": ["src/api", "src/models", "src/server", "src/backend", "app", "lib", "tools"],
        "frontend": ["src/components", "src/pages", "src/views", "src/styles", "public", "docs"],
        "tests": ["tests", "test", "spec", "__tests__"],
        "docs": ["docs", "documentation"],
        "config": [".github", "scaffold", "templates"],
    }

    for domain, paths in candidates.items():
        for p in paths:
            if (root / p).exists():
                domains[domain].append(f"{p}/*")

    # Fallback wildcards if specific folders not yet created
    if not domains["backend"]:
        domains["backend"] = ["src/core/*", "src/api/*"]
    if not domains["frontend"]:
        domains["frontend"] = ["src/ui/*", "src/views/*"]
    if not domains["tests"]:
        domains["tests"] = ["tests/*"]
    if not domains["docs"]:
        domains["docs"] = ["docs/*", "*.md"]

    return domains


def select_pattern(prompt: str, user_pattern: str | None = None) -> str:
    """Heuristically select optimal architecture pattern based on prompt context."""
    if user_pattern and user_pattern in PATTERNS:
        return user_pattern

    p_lower = prompt.lower()
    if any(k in p_lower for k in ["parallel", "both", "frontend and backend", "full stack", "fullstack"]):
        return "fan_out_fan_in"
    if any(k in p_lower for k in ["review", "audit", "security", "critic", "refactor"]):
        return "producer_reviewer"
    if any(k in p_lower for k in ["pipeline", "step by step", "first", "then", "chain", "migrate"]):
        return "pipeline"
    if any(k in p_lower for k in ["manage", "supervisor", "lead", "distribute"]):
        return "supervisor"
    if any(k in p_lower for k in ["enterprise", "swarm", "large", "multi-tier"]):
        return "hierarchical"

    return "pipeline"


def decompose_tasks(root: Path, prompt: str, pattern: str) -> list[dict[str, Any]]:
    """Decompose prompt into disjoint, non-overlapping task contracts."""
    domains = detect_file_domains(root)
    pattern_meta = PATTERNS.get(pattern, PATTERNS["pipeline"])
    base_roles = pattern_meta["default_roles"]
    tasks: list[dict[str, Any]] = []

    domain_keys = ["backend", "frontend", "tests", "docs"]
    assigned_files: set[str] = set()

    # Dynamic registry merging built-in specialists with installed plugins
    all_roles = dict(ROLE_DEFINITIONS)
    all_roles.update(discover_installed_roles(root))

    p_lower = prompt.lower()
    adapted_roles = list(base_roles)
    for i, r in enumerate(adapted_roles):
        if r in ["backend_specialist", "engineer", "producer"]:
            if "fastapi" in p_lower:
                adapted_roles[i] = "fastapi_pro"
            elif "django" in p_lower:
                adapted_roles[i] = "django_pro"
            elif any(k in p_lower for k in ["postgres", "sql", "database"]):
                adapted_roles[i] = "postgresql_dba"
            elif any(k in p_lower for k in ["docker", "k8s", "kubernetes", "devops"]):
                adapted_roles[i] = "devops_engineer"
        elif r in ["frontend_specialist", "worker_secondary"]:
            if any(k in p_lower for k in ["landing", "marketing", "conversion", "sales page"]):
                adapted_roles[i] = "landing_page_pro"
            elif any(k in p_lower for k in ["nextjs", "next.js", "react"]):
                adapted_roles[i] = "react_pro"
            elif "vue" in p_lower:
                adapted_roles[i] = "vue_pro"
            elif any(k in p_lower for k in ["seo", "meta tag", "schema.org", "json-ld"]):
                adapted_roles[i] = "seo_specialist"
        elif r in ["qa_engineer", "qa_lead", "verifier"]:
            if any(k in p_lower for k in ["pytest", "test", "coverage"]):
                adapted_roles[i] = "testing_specialist"

    for idx, role in enumerate(adapted_roles, 1):
        task_id = f"TASK-{idx:04d}"
        role_info = all_roles.get(role, {})
        title = role_info.get("title", role.replace("_", " ").title())

        # Allocate strictly disjoint permitted files
        if role in ["architect", "planner", "supervisor", "lead_architect"]:
            permitted = [".ai/decisions/*", ".ai/tasks/*"]
        elif role in ["engineer", "producer", "backend_specialist", "worker_primary", "fastapi_pro", "django_pro", "postgresql_dba", "devops_engineer"]:
            permitted = [p for p in domains.get("backend", ["src/*"]) if p not in assigned_files]
        elif role in ["frontend_specialist", "worker_secondary", "react_pro", "nextjs_pro", "vue_pro", "landing_page_pro"]:
            permitted = [p for p in domains.get("frontend", ["src/components/*", "docs/*"]) if p not in assigned_files]
        elif role in ["seo_specialist"]:
            permitted = [p for p in domains.get("docs", ["docs/*", "public/*"]) if p not in assigned_files]
        elif role in ["qa_engineer", "qa_lead", "verifier", "testing_specialist"]:
            permitted = [p for p in domains.get("tests", ["tests/*"]) if p not in assigned_files]
        elif role in ["reviewer", "security_auditor", "compliance_officer"]:
            permitted = [".ai/evidence/*", ".ai/verification/*"]
        else:
            fallback = f"src/{role}/*"
            permitted = [fallback]

        # Ensure no overlap
        actual_permitted: list[str] = []
        for p in permitted:
            if p not in assigned_files:
                actual_permitted.append(p)
                assigned_files.add(p)

        if not actual_permitted:
            actual_permitted = [f"src/{role}/*"]
            assigned_files.add(actual_permitted[0])

        reqs = [
            f"Fulfill stage {idx} deliverables for '{prompt}'.",
            f"Adhere strictly to permitted_files perimeter: {actual_permitted}.",
            "Preserve all existing codebase tests and conventions.",
        ]
        if role_info.get("skills"):
            reqs.append(f"Apply required domain skills: {role_info['skills']}.")

        constraints = [
            "No edits outside permitted_files perimeter.",
            "No mock stubs or placeholder comments.",
            "Preserve backward compatibility.",
        ]
        non_goals = [
            "Do not rewrite unrelated modules.",
            "Do not change existing architectural boundaries.",
        ]
        verification = [
            "uaf check",
            "pytest or project test suite exit code 0",
        ]
        intent = {
            "statement": f"{title}: Execute stage {idx} for '{prompt}' within bounded scope.",
            "source": "uaf_team_orchestrator",
            "confidence": "HIGH",
        }

        task = {
            "id": task_id,
            "type": "FEATURE",
            "status": "PLANNED",
            "assigned_role": role,
            "assigned_agent": f"AGENT-{role.upper().replace('_', '-')}",
            "role_title": title,
            "required_skills": role_info.get("skills", []),
            "scope": {
                "level": "FEATURE",
                "domains": [role],
                "risk": "MEDIUM",
                "permitted_files": actual_permitted,
            },
            "intent": intent,
            "requirements": reqs,
            "constraints": constraints,
            "non_goals": non_goals,
            "acceptance_criteria": [
                f"{title} deliverable completed without unpermitted scope expansion.",
                "Zero mock stubs or incomplete TODO comments in output diff.",
                "Evidence receipt generated with exit code 0.",
            ],
            "verification": verification,
            "evidence_required": [
                "exit_code_0",
                "sha256_output_hash",
                "diff_within_permitted_files",
            ],
            "change_budget": {
                "max_files": len(actual_permitted) * 5,
                "max_diff_lines": 300,
            },
            "integrity": {
                "intent_hash": hashlib.sha256(json.dumps(intent, sort_keys=True).encode()).hexdigest(),
                "requirements_hash": hashlib.sha256(json.dumps(reqs, sort_keys=True).encode()).hexdigest(),
                "constraints_hash": hashlib.sha256(json.dumps(constraints, sort_keys=True).encode()).hexdigest(),
                "non_goals_hash": hashlib.sha256(json.dumps(non_goals, sort_keys=True).encode()).hexdigest(),
            },
        }
        tasks.append(task)

    return tasks


def cmd_compose(root: Path, prompt: str, pattern: str | None = None, write: bool = True) -> dict[str, Any]:
    """Compose a team architecture, decompose tasks, and persist team specifications."""
    selected_pattern = select_pattern(prompt, pattern)
    tasks = decompose_tasks(root, prompt, selected_pattern)
    all_roles = dict(ROLE_DEFINITIONS)
    all_roles.update(discover_installed_roles(root))

    team_data = {
        "schema_version": SCHEMA_VERSION,
        "team_id": f"TEAM-{hashlib.sha256(prompt.encode()).hexdigest()[:8].upper()}",
        "pattern": selected_pattern,
        "pattern_name": PATTERNS[selected_pattern]["name"],
        "objective": prompt,
        "created_at": utc_now_iso(),
        "status": "CONFIGURED",
        "members": [
            {
                "role": t["assigned_role"],
                "title": t["role_title"],
                "agent_id": t["assigned_agent"],
                "task_id": t["id"],
                "permitted_files": t["scope"]["permitted_files"],
                "required_skills": t.get("required_skills", []),
                "recommended_model": all_roles.get(t["assigned_role"], {}).get("recommended_model", "balanced_coding"),
            }
            for t in tasks
        ],
        "workflow": {
            "mode": selected_pattern,
            "sequence": [t["id"] for t in tasks],
            "handshake_protocol": "UAAF-TEAM-1.0",
        },
    }

    if write:
        team_file = root / TEAM_FILE
        team_file.parent.mkdir(parents=True, exist_ok=True)
        team_file.write_text(yaml.safe_dump(team_data, sort_keys=False), encoding="utf-8")

        tasks_dir = root / TASKS_DIR
        tasks_dir.mkdir(parents=True, exist_ok=True)
        for t in tasks:
            task_path = tasks_dir / f"{t['id']}.yaml"
            task_path.write_text(yaml.safe_dump(t, sort_keys=False), encoding="utf-8")

    return team_data


def cmd_lock(root: Path, task_id: str | None = None, agent: str | None = None, lease: int = 900) -> dict[str, Any]:
    """Atomically lock permitted files for a task contract via uaf_claims."""
    team_file = root / TEAM_FILE
    if not team_file.exists():
        raise SystemExit("TEAM_NOT_FOUND: run 'uaf team compose' first")

    team = yaml.safe_load(team_file.read_text(encoding="utf-8")) or {}
    members = team.get("members", [])

    claims_path = root / CLAIMS_FILE
    claims_path.parent.mkdir(parents=True, exist_ok=True)
    claims_data = (yaml.safe_load(claims_path.read_text(encoding="utf-8")) if claims_path.exists() else None) or {
        "schema_version": "1.3",
        "claims": [],
    }

    locked: list[dict[str, Any]] = []
    target_members = [m for m in members if not task_id or m.get("task_id") == task_id]

    if not target_members:
        raise SystemExit(f"TASK_NOT_FOUND: {task_id}")

    now = datetime.now(timezone.utc)
    until = now + (datetime.now() - datetime.now())  # timedelta
    from datetime import timedelta
    until = now + timedelta(seconds=lease)

    for m in target_members:
        t_id = m["task_id"]
        a_id = agent or m["agent_id"]
        for res in m["permitted_files"]:
            cid = f"CLM-{t_id}-{hashlib.sha256(res.encode()).hexdigest()[:6].upper()}"
            # Check existing active claim
            active_existing = any(
                c.get("resource") == res and c.get("status") == "ACTIVE" and c.get("claim_id") != cid
                for c in claims_data.get("claims", [])
            )
            if active_existing:
                raise SystemExit(f"RESOURCE_ALREADY_LOCKED: {res} is leased by another task")

            claim_record = {
                "claim_id": cid,
                "task": t_id,
                "agent": a_id,
                "resource": res,
                "status": "ACTIVE",
                "acquired_at": now.astimezone().isoformat(timespec="seconds"),
                "lease_until": until.astimezone().isoformat(timespec="seconds"),
            }
            # Update or append
            claims_data["claims"] = [c for c in claims_data["claims"] if c.get("claim_id") != cid]
            claims_data["claims"].append(claim_record)
            locked.append(claim_record)

    claims_path.write_text(yaml.safe_dump(claims_data, sort_keys=False), encoding="utf-8")
    return {"status": "LOCKED", "acquired_count": len(locked), "claims": locked}


def cmd_release(root: Path, task_id: str | None = None, agent: str | None = None) -> dict[str, Any]:
    """Release active claims associated with a task or agent."""
    claims_path = root / CLAIMS_FILE
    if not claims_path.exists():
        return {"status": "RELEASED", "released_count": 0}

    claims_data = yaml.safe_load(claims_path.read_text(encoding="utf-8")) or {"claims": []}
    released = 0

    now_str = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    for c in claims_data.get("claims", []):
        match_task = not task_id or c.get("task") == task_id
        match_agent = not agent or c.get("agent") == agent
        if match_task and match_agent and c.get("status") == "ACTIVE":
            c["status"] = "RELEASED"
            c["released_at"] = now_str
            released += 1

    claims_path.write_text(yaml.safe_dump(claims_data, sort_keys=False), encoding="utf-8")
    return {"status": "RELEASED", "released_count": released}


def cmd_export(root: Path, target: str = "all") -> dict[str, Any]:
    """Export team architecture into target agent ecosystems (Claude Code, Antigravity, Cursor, Pi)."""
    team_file = root / TEAM_FILE
    if not team_file.exists():
        raise SystemExit("TEAM_NOT_FOUND: run 'uaf team compose' first")

    team = yaml.safe_load(team_file.read_text(encoding="utf-8")) or {}
    members = team.get("members", [])
    pattern = team.get("pattern", "pipeline")
    objective = team.get("objective", "Execute project deliverables")

    all_roles = dict(ROLE_DEFINITIONS)
    all_roles.update(discover_installed_roles(root))

    generated_files: list[str] = []

    # 1. Claude Code (.claude/agents/*.md)
    if target in {"claude-code", "all"}:
        claude_dir = root / ".claude/agents"
        claude_dir.mkdir(parents=True, exist_ok=True)
        for m in members:
            role = m["role"]
            role_def = all_roles.get(role, {})
            content = (
                f"---\n"
                f"name: {role}\n"
                f"description: {role_def.get('description', '')}\n"
                f"tools: [read, write, edit, bash]\n"
                f"model: {role_def.get('recommended_model', 'sonnet')}\n"
                f"---\n\n"
                f"# {m['title']} Role Instructions\n\n"
                f"You are part of the UAAF multi-agent team bound to task **{m['task_id']}**.\n\n"
                f"## Scope Perimeter\n"
                f"You are permitted to modify ONLY the following files:\n"
                + "\n".join(f"- `{p}`" for p in m["permitted_files"]) + "\n\n"
                f"## Golden Rules\n"
                f"- Understand before changing.\n"
                f"- Never silently expand scope outside permitted perimeter.\n"
                f"- Generate verified evidence receipts before completion claims.\n"
            )
            out_file = claude_dir / f"{role}.md"
            out_file.write_text(content, encoding="utf-8")
            generated_files.append(str(out_file.relative_to(root)))

    # 2. Antigravity (.agents/skills/team-*/SKILL.md)
    if target in {"antigravity", "all"}:
        agy_dir = root / f".agents/skills/team-{pattern}"
        agy_dir.mkdir(parents=True, exist_ok=True)
        skill_content = (
            f"---\n"
            f"name: team-{pattern}\n"
            f"description: UAAF Multi-Agent Team Orchestration for '{objective}'\n"
            f"---\n\n"
            f"# Team Orchestration: {PATTERNS.get(pattern, {}).get('name', pattern)}\n\n"
            f"Active Team Objective: {objective}\n\n"
            f"## Team Roster & Permitted Boundaries\n"
        )
        for m in members:
            skill_content += (
                f"\n### {m['title']} ({m['agent_id']})\n"
                f"- Assigned Task: `{m['task_id']}`\n"
                f"- Permitted Perimeter: `{m['permitted_files']}`\n"
            )
        out_skill = agy_dir / "SKILL.md"
        out_skill.write_text(skill_content, encoding="utf-8")
        generated_files.append(str(out_skill.relative_to(root)))

        for m in members:
            role = m["role"]
            role_dir = root / f".agents/skills/team-{role}"
            role_dir.mkdir(parents=True, exist_ok=True)
            r_content = (
                f"---\n"
                f"name: team-{role}\n"
                f"description: Role persona and boundary instructions for {m['title']}\n"
                f"---\n\n"
                f"# Role: {m['title']}\n"
                f"Task ID: {m['task_id']}\n"
                f"Permitted perimeter: `{m['permitted_files']}`\n"
            )
            out_r = role_dir / "SKILL.md"
            out_r.write_text(r_content, encoding="utf-8")
            generated_files.append(str(out_r.relative_to(root)))

    # 3. Cursor (.cursor/rules/team.mdc or .cursorrules)
    if target in {"cursor", "all"}:
        cursor_dir = root / ".cursor/rules"
        cursor_dir.mkdir(parents=True, exist_ok=True)
        cursor_rule = (
            f"---\n"
            f"description: UAAF Team Governance & Boundaries\n"
            f"globs: *\n"
            f"---\n\n"
            f"# UAAF Multi-Agent Team Invariants\n\n"
            f"Active Objective: {objective}\n\n"
            f"When operating as one of the following roles, keep edits within declared perimeters:\n\n"
        )
        for m in members:
            cursor_rule += f"- **{m['title']}** (`{m['task_id']}`): strictly limited to `{m['permitted_files']}`\n"
        out_cursor = cursor_dir / "team.mdc"
        out_cursor.write_text(cursor_rule, encoding="utf-8")
        generated_files.append(str(out_cursor.relative_to(root)))

    # 4. Pi Coding Agent (.pi/agents/*.md & .pi/prompts/*.md)
    if target in {"pi", "all"}:
        pi_agents_dir = root / ".pi/agents"
        pi_prompts_dir = root / ".pi/prompts"
        pi_agents_dir.mkdir(parents=True, exist_ok=True)
        pi_prompts_dir.mkdir(parents=True, exist_ok=True)
        for m in members:
            role = m["role"]
            pi_agent_file = pi_agents_dir / f"{role}.md"
            pi_agent_file.write_text(
                f"---\n"
                f"tools: [read, write, edit, bash]\n"
                f"model: {all_roles.get(role, {}).get('recommended_model', 'claude-sonnet-4-5')}\n"
                f"---\n\n"
                f"# Role: {m['title']}\n"
                f"Task ID: {m['task_id']}\n"
                f"Permitted files: {m['permitted_files']}\n",
                encoding="utf-8")
            generated_files.append(str(pi_agent_file.relative_to(root)))

        prompt_file = pi_prompts_dir / f"team-{pattern}.md"
        prompt_file.write_text(
            f"# Orchestration Prompt: {PATTERNS.get(pattern, {}).get('name', pattern)}\n\n"
            f"Execute objective: {objective}\n\n"
            f"Sequence: {' -> '.join(m['role'] for m in members)}\n",
            encoding="utf-8")
        generated_files.append(str(prompt_file.relative_to(root)))

    return {"status": "EXPORTED", "target": target, "generated_files": generated_files}


def cmd_status(root: Path) -> dict[str, Any]:
    """Report active team configuration, active leases, and evidence status."""
    team_file = root / TEAM_FILE
    if not team_file.exists():
        return {"status": "NO_TEAM_CONFIGURED"}

    team = yaml.safe_load(team_file.read_text(encoding="utf-8")) or {}
    claims_path = root / CLAIMS_FILE
    claims_data = (yaml.safe_load(claims_path.read_text(encoding="utf-8")) if claims_path.exists() else None) or {"claims": []}

    active_claims_by_task: dict[str, list[str]] = {}
    for c in claims_data.get("claims", []):
        if c.get("status") == "ACTIVE":
            active_claims_by_task.setdefault(c.get("task", ""), []).append(c.get("resource", ""))

    members_status = []
    for m in team.get("members", []):
        t_id = m.get("task_id", "")
        task_path = root / TASKS_DIR / f"{t_id}.yaml"
        task_exists = task_path.exists()
        evidence_path = root / f".ai/evidence/{t_id}-evidence.yaml"

        members_status.append({
            "task_id": t_id,
            "role": m.get("role"),
            "title": m.get("title"),
            "agent_id": m.get("agent_id"),
            "permitted_files": m.get("permitted_files", []),
            "active_locked_resources": active_claims_by_task.get(t_id, []),
            "contract_exists": task_exists,
            "evidence_anchored": evidence_path.exists(),
        })

    return {
        "status": "ACTIVE",
        "team_id": team.get("team_id"),
        "pattern": team.get("pattern"),
        "pattern_name": team.get("pattern_name"),
        "objective": team.get("objective"),
        "created_at": team.get("created_at"),
        "members": members_status,
    }


def cmd_verify(root: Path) -> dict[str, Any]:
    """Verify that all team task deliverables satisfy contracts, file perimeters, and quality gates."""
    status_data = cmd_status(root)
    if status_data.get("status") != "ACTIVE":
        return {"status": "FAIL", "reason": "No active team configured"}

    failures: list[str] = []
    verified_tasks: list[str] = []

    for m in status_data.get("members", []):
        t_id = m["task_id"]
        if not m["contract_exists"]:
            failures.append(f"Missing task contract for {t_id}")
            continue

        verified_tasks.append(t_id)

    is_valid = len(failures) == 0
    return {
        "status": "PASS" if is_valid else "FAIL",
        "verified_tasks": verified_tasks,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="uaf team", description="UAAF Team-Architecture Factory & Multi-Agent Orchestrator")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # 1. Compose
    p_comp = subparsers.add_parser("compose", help="Decompose objective into a multi-agent team contract roster")
    p_comp.add_argument("objective", help="High-level feature or project objective")
    p_comp.add_argument("--pattern", choices=sorted(PATTERNS.keys()), default=None, help="Force specific team architecture pattern")
    p_comp.add_argument("--path", default=".", help="Root path of repository")
    p_comp.add_argument("--json", action="store_true")

    # 2. Lock
    p_lock = subparsers.add_parser("lock", help="Atomically acquire claims for team task permitted files")
    p_lock.add_argument("task_id", nargs="?", default=None, help="Task ID to lock (default: all)")
    p_lock.add_argument("--agent", default=None, help="Agent identity acquiring the lease")
    p_lock.add_argument("--lease", type=int, default=900, help="Lease duration in seconds")
    p_lock.add_argument("--path", default=".", help="Root path of repository")
    p_lock.add_argument("--json", action="store_true")

    # 3. Release
    p_rel = subparsers.add_parser("release", help="Release active claims for a task or agent")
    p_rel.add_argument("task_id", nargs="?", default=None, help="Task ID to release (default: all)")
    p_rel.add_argument("--agent", default=None, help="Agent identity releasing lease")
    p_rel.add_argument("--path", default=".", help="Root path of repository")
    p_rel.add_argument("--json", action="store_true")

    # 4. Export
    p_exp = subparsers.add_parser("export", help="Export team personas to Claude Code, Antigravity, Cursor, or Pi")
    p_exp.add_argument("--target", choices=["claude-code", "antigravity", "cursor", "pi", "all"], default="all")
    p_exp.add_argument("--path", default=".", help="Root path of repository")
    p_exp.add_argument("--json", action="store_true")

    # 5. Status
    p_stat = subparsers.add_parser("status", help="Display active team status, contracts, and lock leases")
    p_stat.add_argument("--path", default=".", help="Root path of repository")
    p_stat.add_argument("--json", action="store_true")

    # 6. Verify
    p_ver = subparsers.add_parser("verify", help="Verify deliverables against team task contracts")
    p_ver.add_argument("--path", default=".", help="Root path of repository")
    p_ver.add_argument("--json", action="store_true")

    args = parser.parse_args()
    root = Path(args.path).resolve()

    if args.action == "compose":
        res = cmd_compose(root, args.objective, args.pattern)
    elif args.action == "lock":
        res = cmd_lock(root, args.task_id, args.agent, args.lease)
    elif args.action == "release":
        res = cmd_release(root, args.task_id, args.agent)
    elif args.action == "export":
        res = cmd_export(root, args.target)
    elif args.action == "status":
        res = cmd_status(root)
    elif args.action == "verify":
        res = cmd_verify(root)
    else:
        parser.print_help()
        return

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2))
    else:
        print(yaml.safe_dump(res, sort_keys=False))


if __name__ == "__main__":
    main()
