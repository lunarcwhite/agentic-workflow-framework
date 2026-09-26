#!/usr/bin/env python3
"""UAAF v1.0 conformance validator.

The validator is read-only by default. It validates structure, manifest semantics,
feature/profile contracts, IDs/metadata, cross-references, task contracts,
and selected lifecycle invariants.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

CORE_FILES = [
    "AGENTS.md",
    ".ai/manifest.yaml",
    ".ai/INDEX.md",
    ".ai/core/SOUL.md",
    ".ai/core/CONTEXT.md",
    ".ai/core/RULES.md",
    ".ai/core/WORKFLOW.md",
    ".ai/core/CONVENTIONS.md",
    ".ai/core/KNOWLEDGE-CONTRACT.md",
    ".ai/memory/STATE.md",
    ".ai/memory/MEMORY.md",
]

STANDARD_FILES = [
    ".ai/memory/POLICY.md",
    ".ai/decisions/INDEX.md",
    ".ai/tasks/INDEX.md",
    ".ai/verification/VERIFICATION-MATRIX.md",
    ".ai/verification/DELIVERY-GATE.md",
    ".ai/anti-slop/PROTOCOL.md",
    ".ai/anti-slop/GATES.md",
    ".ai/sessions/README.md",
]

FULL_FILES = [
    ".ai/evidence",
    ".ai/health",
    ".ai/agents/REGISTRY.yaml",
    ".ai/agents/CLAIMS.yaml",
    ".ai/migrations",
    ".ai/verification/REGRESSION-MAP.md",
    ".ai/verification/INTENT-EVALUATION.md",
]

PROTOCOLS = {
    "agent": "UAP-1.0",
    "context": "CLE-1.0",
    "intent": "IRE-1.0",
    "planning": "APRE-1.0",
    "memory": "MEE-1.0",
    "anti_slop": "ASE-1.0",
    "verification": "VEE-1.0",
    "reality": "RCE-1.0",
}

VALID = {
    "profile": {"minimal", "standard", "full"},
    "maturity": {"greenfield", "existing", "mature"},
    "status": {"active", "maintenance", "paused", "archived"},
    "risk": {"LOW", "MEDIUM", "HIGH", "CRITICAL"},
    "level": {"MICRO", "FEATURE", "SYSTEM"},
    "confidence": {"HIGH", "MEDIUM", "LOW", "UNKNOWN"},
    "memory_status": {
        "OBSERVATION", "CANDIDATE", "VALIDATED", "ACTIVE", "UPDATED",
        "SUPERSEDED", "SUSPECT", "STALE", "ARCHIVED"
    },
    "authority": {"CANONICAL", "CONTROLLED", "AUTHORITATIVE", "REFERENCE", "HISTORICAL"},
    "stability": {"STABLE", "EVOLVING", "VOLATILE", "TEMPORARY"},
}

ID_PATTERNS = {
    "task": re.compile(r"TASK-\d{4,}"),
    "memory": re.compile(r"MEM-\d{4,}"),
    "decision": re.compile(r"DEC-\d{4,}"),
    "evidence": re.compile(r"EVD-\d{4,}"),
    "handoff": re.compile(r"HND-\d{8}-\d{3,}"),
    "session": re.compile(r"SES-\d{8}-\d{3,}"),
    "agent": re.compile(r"AGENT-[A-Z0-9_-]+"),
}


def load_yaml(path: Path, errors: list[str], code: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            errors.append(f"{code} {path}: top-level YAML must be a mapping")
            return {}
        return data
    except Exception as exc:
        errors.append(f"{code} {path}: invalid YAML: {exc}")
        return {}


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


def normalized_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def collect_ids(root: Path, errors: list[str], warnings: list[str]) -> dict[str, list[tuple[str, str]]]:
    """Collect identity-bearing artifact IDs only from canonical artifact locations.

    Do not regex-scan entire files because references such as `task_id: TASK-0001`
    inside a change manifest are not a second task identity.
    """
    seen: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    specs = [
        (root / ".ai/tasks", "task", {".md", ".yaml", ".yml"}),
        (root / ".ai/memory/entries", "memory", {".md"}),
        (root / ".ai/decisions", "decision", {".md"}),
        (root / ".ai/evidence", "evidence", {".yaml", ".yml"}),
        (root / ".ai/agents/handoffs", "handoff", {".md"}),
    ]
    for base, kind, suffixes in specs:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes or path.name == "README.md":
                continue
            ident = None
            if kind == "task":
                match = ID_PATTERNS["task"].match(path.name)
                if match:
                    ident = match.group(0)
                else:
                    data = _safe_yaml(path) if path.suffix in {".yaml", ".yml"} else frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
                    ident = data.get("id") if isinstance(data, dict) else None
            elif kind == "memory":
                ident = frontmatter(path.read_text(encoding="utf-8", errors="ignore")).get("id")
            elif kind == "decision":
                match = ID_PATTERNS["decision"].match(path.name)
                ident = match.group(0) if match else None
            elif kind == "evidence":
                match = ID_PATTERNS["evidence"].match(path.name)
                ident = match.group(0) if match else None
                if not ident:
                    data = _safe_yaml(path)
                    ident = data.get("id") if isinstance(data, dict) else None
            elif kind == "handoff":
                match = ID_PATTERNS["handoff"].match(path.name)
                ident = match.group(0) if match else None
            if ident:
                seen[kind][str(ident)].append(str(path.relative_to(root)))

    for kind, mapping in seen.items():
        for ident, paths in mapping.items():
            if len(paths) > 1:
                errors.append(f"CONF-REF-004 duplicate {kind} ID {ident}: {', '.join(paths)}")
    return {kind: [(ident, path) for ident, paths in mapping.items() for path in paths] for kind, mapping in seen.items()}


def _safe_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def validate_manifest(root: Path, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    path = root / ".ai/manifest.yaml"
    if not path.exists():
        errors.append("CONF-MAN-001 missing .ai/manifest.yaml")
        return {}
    manifest = load_yaml(path, errors, "CONF-MAN-002")
    required = ["schema_version", "framework", "protocols", "project", "agent", "features", "capabilities"]
    for key in required:
        if key not in manifest:
            errors.append(f"CONF-MAN-003 missing manifest key: {key}")
    if manifest.get("schema_version") != "1.0":
        errors.append(f"CONF-MAN-004 unsupported schema_version: {manifest.get('schema_version')!r}")
    framework = manifest.get("framework") or {}
    if framework.get("id") != "UAAF":
        errors.append("CONF-MAN-005 framework.id must be UAAF")
    if not str(framework.get("version", "")).startswith("1."):
        errors.append("CONF-MAN-006 framework.version must be 1.x for UAAF v1 conformance")
    protocols = manifest.get("protocols") or {}
    for key, expected in PROTOCOLS.items():
        if protocols.get(key) != expected:
            errors.append(f"CONF-MAN-007 protocols.{key} must be {expected}")
    project = manifest.get("project") or {}
    if project.get("maturity") not in VALID["maturity"]:
        warnings.append(f"CONF-MAN-008 project.maturity is unusual: {project.get('maturity')!r}")
    if project.get("status") not in VALID["status"]:
        warnings.append(f"CONF-MAN-009 project.status is unusual: {project.get('status')!r}")
    return manifest


def required_for_profile(profile: str, level: str) -> list[str]:
    target = list(CORE_FILES)
    if level in {"standard", "full"}:
        target.extend(STANDARD_FILES)
    if level == "full":
        target.extend(FULL_FILES)
    if profile == "minimal" and level == "core":
        return target
    return target


def validate_structure(root: Path, profile: str, level: str, errors: list[str], warnings: list[str]) -> None:
    for rel in required_for_profile(profile, level):
        if not (root / rel).exists():
            errors.append(f"CONF-STR-001 missing {rel}")
    if profile == "minimal" and level != "core":
        errors.append("CONF-PRO-001 minimal profile cannot claim standard/full conformance")
    if profile == "full" and level == "full":
        for rel in FULL_FILES:
            if not (root / rel).exists():
                errors.append(f"CONF-FUL-001 full profile missing {rel}")


def validate_features(root: Path, manifest: dict[str, Any], level: str, errors: list[str], warnings: list[str]) -> None:
    features = manifest.get("features") or {}
    mappings = {
        "memory": [".ai/memory/STATE.md", ".ai/memory/MEMORY.md"],
        "anti_slop": [".ai/anti-slop/PROTOCOL.md", ".ai/anti-slop/GATES.md"],
        "verification": [".ai/verification/VERIFICATION-MATRIX.md", ".ai/verification/DELIVERY-GATE.md"],
        "session_handoff": [".ai/sessions", ".ai/sessions/README.md"],
        "traceability": [".ai/evidence", ".ai/verification/REGRESSION-MAP.md"],
    }
    for feature, paths in mappings.items():
        if features.get(feature):
            for rel in paths:
                if not (root / rel).exists():
                    errors.append(f"CONF-FEA-{feature.upper()} feature enabled but missing {rel}")
    if level in {"standard", "full"} and not features.get("memory", False):
        warnings.append("CONF-FEA-001 standard/full conformance normally expects memory enabled")


def validate_state(root: Path, errors: list[str], warnings: list[str]) -> None:
    path = root / ".ai/memory/STATE.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    m = re.search(r"(?:^|\n)version:\s*(\d+)\s*(?:$|\n)", text)
    if not m:
        errors.append("CONF-MEM-001 STATE.md has no numeric version")


def validate_memory(root: Path, errors: list[str], warnings: list[str]) -> None:
    entries = root / ".ai/memory/entries"
    if not entries.exists():
        return
    required = {"id", "type", "status", "created", "updated"}
    for path in entries.glob("*.md"):
        meta = frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        missing = required - set(meta)
        for key in sorted(missing):
            errors.append(f"CONF-MEM-002 {path.name} missing required metadata: {key}")
        if meta.get("status") not in VALID["memory_status"]:
            warnings.append(f"CONF-MEM-003 {path.name} has unknown status {meta.get('status')!r}")
        if meta.get("authority") and meta["authority"] not in VALID["authority"]:
            warnings.append(f"CONF-MEM-004 {path.name} has unknown authority {meta['authority']!r}")
        if meta.get("confidence") and meta["confidence"] not in VALID["confidence"]:
            warnings.append(f"CONF-MEM-005 {path.name} has unknown confidence {meta['confidence']!r}")
        if meta.get("stability") and meta["stability"] not in VALID["stability"]:
            warnings.append(f"CONF-MEM-006 {path.name} has unknown stability {meta['stability']!r}")


def validate_decisions(root: Path, errors: list[str], warnings: list[str]) -> None:
    decisions = root / ".ai/decisions"
    if not decisions.exists():
        return
    for path in decisions.glob("DEC-*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for required in ["status:", "scope:", "## Decision", "## Rationale"]:
            if required not in text:
                errors.append(f"CONF-DEC-001 {path.name} missing {required}")


def validate_tasks(root: Path, errors: list[str], warnings: list[str]) -> None:
    tasks = root / ".ai/tasks"
    if not tasks.exists():
        return
    for path in tasks.rglob("TASK-*.*"):
        if path.suffix not in {".md", ".yaml", ".yml"} or path.name == "README.md":
            continue
        if path.suffix in {".yaml", ".yml"}:
            data = _safe_yaml(path)
            required = ["id", "type", "status", "scope", "intent", "requirements",
                        "constraints", "non_goals", "acceptance_criteria", "verification"]
            for key in required:
                if key not in data:
                    errors.append(f"CONF-TASK-001 {path.name} missing {key}")
            if not ID_PATTERNS["task"].fullmatch(str(data.get("id", ""))):
                errors.append(f"CONF-TASK-002 {path.name} has invalid task id")
            if not data.get("non_goals"):
                warnings.append(f"CONF-TASK-003 {path.name} has empty non_goals")
            integrity = data.get("integrity") or {}
            for key in ["intent_hash", "requirements_hash", "constraints_hash", "non_goals_hash"]:
                if not integrity.get(key):
                    warnings.append(f"CONF-TASK-004 {path.name} missing {key}")
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
            required = ["status:", "scope:", "## Intent", "## Requirements", "## Acceptance criteria", "## Verification"]
            for marker in required:
                if marker not in text:
                    errors.append(f"CONF-TASK-001 {path.name} missing {marker}")
            if "## Non-goals" not in text:
                warnings.append(f"CONF-TASK-003 {path.name} has no explicit Non-goals section")
            if "## Change budget" not in text:
                warnings.append(f"CONF-TASK-004 {path.name} has no Change budget section")
            meta = frontmatter(text)
            if meta.get("id") and not ID_PATTERNS["task"].fullmatch(str(meta["id"])):
                errors.append(f"CONF-TASK-005 {path.name} has invalid task id")
            if "integrity:" not in text and "intent_hash" not in text:
                warnings.append(f"CONF-TASK-006 {path.name} has no contract integrity fingerprint")


def validate_change_manifests(root: Path, errors: list[str], warnings: list[str]) -> None:
    for path in (root / ".ai").rglob("change-manifest*.yaml") if (root / ".ai").exists() else []:
        data = _safe_yaml(path)
        if not data:
            continue
        if not ID_PATTERNS["task"].fullmatch(str(data.get("task_id", ""))):
            errors.append(f"CONF-TASK-007 {path.relative_to(root)} has invalid task_id")
        unexpected = data.get("unexpected") or {}
        justification = data.get("justification") or {}
        if isinstance(unexpected, dict):
            for key in unexpected:
                if key not in justification:
                    errors.append(f"CONF-TASK-008 {path.relative_to(root)} unexpected change {key!r} has no justification")
        if data.get("status") not in {"draft", "accepted", "rejected"}:
            warnings.append(f"CONF-TASK-009 {path.relative_to(root)} has unusual status {data.get('status')!r}")


def validate_context_receipts(root: Path, errors: list[str], warnings: list[str]) -> None:
    for path in (root / ".ai").rglob("context-receipt*.yaml") if (root / ".ai").exists() else []:
        data = _safe_yaml(path)
        if not data:
            continue
        if not ID_PATTERNS["task"].fullmatch(str(data.get("task_id", ""))):
            errors.append(f"CONF-CTX-001 {path.relative_to(root)} has invalid task_id")
        depth = data.get("context_depth")
        if depth not in {0, 1, 2, 3}:
            errors.append(f"CONF-CTX-002 {path.relative_to(root)} context_depth must be 0..3")


def validate_verification(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    matrix = root / ".ai/verification/VERIFICATION-MATRIX.md"
    if not matrix.exists():
        return
    text = matrix.read_text(encoding="utf-8", errors="ignore")
    for col in ["Requirement", "Acceptance Criteria", "Evidence", "Method", "Status"]:
        if col not in text:
            errors.append(f"CONF-VER-002 verification matrix missing column {col}")
    delivery = root / ".ai/verification/DELIVERY-GATE.md"
    if delivery.exists():
        delivery_text = delivery.read_text(encoding="utf-8", errors="ignore")
        for term in ["DONE", "NOT_READY", "BLOCKED"]:
            if term not in delivery_text:
                warnings.append(f"CONF-VER-003 delivery gate does not mention {term}")


def validate_refs(root: Path, errors: list[str], warnings: list[str]) -> None:
    # Manifest canonical owner references.
    manifest_path = root / ".ai/manifest.yaml"
    if manifest_path.exists():
        data = _safe_yaml(manifest_path)
        for domain, owner in (data.get("source_of_truth") or {}).items():
            owner = str(owner)
            if owner == "repository":
                continue
            if not (root / owner).exists():
                warnings.append(f"CONF-REF-001 source_of_truth.{domain} points to missing path {owner}")

    # Memory sources: verify IDs when they reference UAAF artifacts.
    entries = root / ".ai/memory/entries"
    if entries.exists():
        for path in entries.glob("*.md"):
            meta = frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
            for source in meta.get("source", []) or []:
                s = str(source)
                if ID_PATTERNS["task"].fullmatch(s) and not list((root / ".ai/tasks").rglob(f"{s}*")):
                    warnings.append(f"CONF-REF-002 {path.name}: missing task source {s}")
                if ID_PATTERNS["decision"].fullmatch(s) and not list((root / ".ai/decisions").glob(f"{s}*")):
                    warnings.append(f"CONF-REF-002 {path.name}: missing decision source {s}")
                if ID_PATTERNS["evidence"].fullmatch(s) and not list((root / ".ai/evidence").glob(f"{s}*")):
                    warnings.append(f"CONF-REF-002 {path.name}: missing evidence source {s}")

    # Evidence source paths.
    evidence = root / ".ai/evidence"
    if evidence.exists():
        for path in evidence.glob("*.yaml"):
            data = _safe_yaml(path)
            for source in data.get("sources", []) or []:
                src = root / str(source)
                if not src.exists():
                    warnings.append(f"CONF-REF-003 {path.name}: evidence source path missing {source}")


def validate_agent_registry(root: Path, errors: list[str], warnings: list[str]) -> None:
    reg = root / ".ai/agents/REGISTRY.yaml"
    claims = root / ".ai/agents/CLAIMS.yaml"
    if not reg.exists() or not claims.exists():
        return
    r = _safe_yaml(reg)
    agents = r.get("agents", [])
    for agent in agents:
        if not isinstance(agent, dict):
            errors.append("CONF-MA-001 REGISTRY.yaml contains non-mapping agent entry")
            continue
        for key in ["id", "capabilities", "authority", "status"]:
            if key not in agent:
                errors.append(f"CONF-MA-002 agent entry missing {key}")
        if "id" in agent and not ID_PATTERNS["agent"].fullmatch(str(agent["id"])):
            warnings.append(f"CONF-MA-003 non-standard agent ID {agent['id']!r}")
    c = _safe_yaml(claims)
    claim_items = c.get("claims", c if isinstance(c, list) else [])
    if isinstance(claim_items, dict):
        claim_items = [claim_items]
    for claim in claim_items:
        if not isinstance(claim, dict):
            continue
        for key in ["resource", "agent", "task", "status"]:
            if key not in claim:
                errors.append(f"CONF-MA-004 claim missing {key}")


def validate_contract_fingerprints(root: Path, errors: list[str], warnings: list[str]) -> None:
    tasks = root / ".ai/tasks"
    if not tasks.exists():
        return
    for path in tasks.rglob("TASK-*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        # Markdown task contracts may omit hashes; this is a warning, not a structural error.
        if "integrity:" not in text and "intent_hash" not in text:
            warnings.append(f"CONF-TASK-004 {path.name} has no contract integrity fingerprint")


def validate_lifecycle(root: Path, errors: list[str], warnings: list[str]) -> None:
    entries = root / ".ai/memory/entries"
    if entries.exists():
        for path in entries.glob("*.md"):
            meta = frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
            status = str(meta.get("status", ""))
            if status == "SUPERSEDED" and not (meta.get("superseded_by") or meta.get("supersedes")):
                warnings.append(f"CONF-LIFE-001 {path.name} is SUPERSEDED without supersession link")
            if status == "STALE" and not meta.get("review_after"):
                warnings.append(f"CONF-LIFE-002 {path.name} is STALE without review_after")


def validate_v11_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    extensions = manifest.get("extensions") or {}
    version = str(extensions.get("version", ""))
    if not version:
        return
    if version not in {"1.1", "1.2"}:
        errors.append(f"CONF-V11-001 unsupported extensions.version: {version!r}")
        return

    caps_cfg = extensions.get("capabilities") or {}
    cap_rel = str(caps_cfg.get("file", ".ai/capabilities.yaml"))
    cap_path = root / cap_rel
    if not cap_path.exists():
        errors.append(f"CONF-V11-002 capability override file missing: {cap_rel}")
    else:
        data = _safe_yaml(cap_path)
        if data.get("schema_version") != "1.1":
            errors.append("CONF-V11-003 capabilities schema_version must be 1.1")
        caps = data.get("capabilities") or {}
        for name, record in caps.items():
            if not isinstance(record, dict):
                errors.append(f"CONF-V11-004 capability {name} record must be a mapping")
                continue
            if name not in manifest.get("capabilities", {}):
                warnings.append(f"CONF-V11-005 extension defines unknown capability {name}")
            override = record.get("override", "auto")
            if override not in {"auto", "force_true", "force_false", "review_required"}:
                errors.append(f"CONF-V11-006 capability {name} has invalid override {override!r}")
            confidence = record.get("confidence", "UNKNOWN")
            if confidence not in VALID["confidence"]:
                warnings.append(f"CONF-V11-007 capability {name} has invalid confidence {confidence!r}")
            if override in {"force_true", "force_false", "review_required"} and not str(record.get("reason", "")).strip():
                errors.append(f"CONF-V11-008 capability {name} explicit override requires reason")
            effective = bool(record.get("detected", False))
            if override == "force_true": effective = True
            elif override == "force_false": effective = False
            elif override == "review_required": effective = bool(record.get("detected", False))
            manifest_value = (manifest.get("capabilities") or {}).get(name)
            if manifest_value is not None and bool(manifest_value) != effective:
                errors.append(f"CONF-V11-009 capability projection mismatch for {name}: manifest={manifest_value!r} effective={effective!r}")

    impact_cfg = extensions.get("context_impact") or {}
    impact_rel = str(impact_cfg.get("file", ".ai/context/IMPACT-GRAPH.yaml"))
    mode = impact_cfg.get("mode", "advisory")
    if mode != "advisory":
        errors.append("CONF-V11-010 context_impact.mode must be advisory in v1.1")
    impact_path = root / impact_rel
    if impact_path.exists():
        data = _safe_yaml(impact_path)
        if data.get("schema_version") != "1.1":
            errors.append("CONF-V11-011 context impact graph schema_version must be 1.1")
        if data.get("mode") not in {"advisory", None}:
            errors.append("CONF-V11-012 context impact graph mode must be advisory")
        changed = data.get("changed_paths") or []
        nodes = data.get("nodes") or []
        node_paths = [n.get("path") for n in nodes if isinstance(n, dict)]
        for path in changed:
            if str(path) not in node_paths:
                warnings.append(f"CONF-V11-013 impact graph path has no node: {path}")
    elif impact_cfg:
        warnings.append(f"CONF-V11-014 context impact graph not generated yet: {impact_rel}")


def validate_v12_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    extensions = manifest.get("extensions") or {}
    if str(extensions.get("version", "")) != "1.2":
        return

    comp_cfg = extensions.get("memory_compaction") or {}
    comp_rel = str(comp_cfg.get("file", ".ai/memory/compaction/README.md"))
    comp_path = root / comp_rel
    if not comp_path.exists():
        errors.append(f"CONF-V12-001 memory compaction contract missing: {comp_rel}")
    elif "dry-run" not in comp_path.read_text(encoding="utf-8", errors="ignore").lower():
        warnings.append("CONF-V12-002 memory compaction contract does not document dry-run safety")

    rce_cfg = extensions.get("rce_strong") or {}
    rce_rel = str(rce_cfg.get("file", ".ai/health/RCE-STRONG.md"))
    rce_path = root / rce_rel
    if not rce_path.exists():
        errors.append(f"CONF-V12-003 strong RCE contract missing: {rce_rel}")
    else:
        text = rce_path.read_text(encoding="utf-8", errors="ignore").lower()
        for marker in ["snapshot", "scan", "read-only"]:
            if marker not in text:
                warnings.append(f"CONF-V12-004 strong RCE contract missing concept: {marker}")

    index = root / ".ai/health/REALITY-INDEX.yaml"
    if index.exists():
        data = _safe_yaml(index)
        if data.get("schema_version") != "1.2":
            errors.append("CONF-V12-005 reality index schema_version must be 1.2")
        records = data.get("records") or []
        if not isinstance(records, list):
            errors.append("CONF-V12-006 reality index records must be a list")
        else:
            for rec in records:
                if not isinstance(rec, dict) or not rec.get("path") or not rec.get("sha256"):
                    errors.append("CONF-V12-007 every reality record requires path and sha256")
    elif rce_cfg:
        warnings.append("CONF-V12-008 strong RCE baseline not created yet: .ai/health/REALITY-INDEX.yaml")


def check(path: Path, level: str = "standard") -> tuple[list[str], list[str], list[str]]:
    root = path.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    manifest = validate_manifest(root, errors, warnings)
    profile = str(manifest.get("profile", "standard")).lower()
    if profile not in VALID["profile"]:
        errors.append(f"CONF-MAN-010 unknown profile {profile!r}")
        profile = "standard"

    validate_structure(root, profile, level, errors, warnings)
    validate_features(root, manifest, level, errors, warnings)
    validate_state(root, errors, warnings)
    validate_memory(root, errors, warnings)
    validate_decisions(root, errors, warnings)
    validate_tasks(root, errors, warnings)
    validate_change_manifests(root, errors, warnings)
    validate_context_receipts(root, errors, warnings)
    validate_verification(root, manifest, errors, warnings)
    validate_refs(root, errors, warnings)
    collect_ids(root, errors, warnings)
    validate_agent_registry(root, errors, warnings)
    validate_contract_fingerprints(root, errors, warnings)
    validate_v11_extensions(root, manifest, errors, warnings)
    validate_v12_extensions(root, manifest, errors, warnings)

    # Placeholder warning in stable kernel files.
    for rel in [".ai/core/CONTEXT.md", ".ai/core/CONVENTIONS.md"]:
        p = root / rel
        if p.exists() and "<!--" in p.read_text(encoding="utf-8", errors="ignore"):
            warnings.append(f"CONF-DOC-001 placeholder content remains in {rel}")

    infos.append(f"profile={profile}")
    infos.append(f"requested_level={level}")
    if manifest.get("extensions", {}).get("version"):
        infos.append(f"extensions={manifest.get('extensions', {}).get('version')}")
    return errors, warnings, infos


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a UAAF v1.0 project")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--level", choices=["minimal", "core", "standard", "full"], default="standard")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args()

    level = "core" if args.level == "minimal" else args.level
    errors, warnings, infos = check(Path(args.path), level)
    status = "FAIL" if errors else (("FAIL" if args.strict else "PASS_WITH_WARNINGS") if warnings else "PASS")
    payload = {"status": status, "errors": errors, "warnings": warnings, "info": infos}

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(status)
        for item in errors:
            print("ERROR", item)
        for item in warnings:
            print("WARNING", item)
        for item in infos:
            print("INFO", item)
    raise SystemExit(1 if errors or (args.strict and warnings) else 0)


if __name__ == "__main__":
    main()
