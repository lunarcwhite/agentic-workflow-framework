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
from datetime import datetime, timezone
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


def extension_num(manifest: dict[str, Any]) -> float:
    try:
        return float(str((manifest.get("extensions") or {}).get("version", "0")))
    except (TypeError, ValueError):
        return 0.0


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
    version = str(framework.get("version", ""))
    if not (version.startswith("1.") or version.startswith("2.")):
        errors.append("CONF-MAN-006 framework.version must be 1.x or 2.x")
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
    if extension_num(manifest) < 1.1 or extension_num(manifest) >= 3.0:
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
    if extension_num(manifest) < 1.2:
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


def validate_v13_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    extensions = manifest.get("extensions") or {}
    if extension_num(manifest) < 1.3:
        return
    profile = str(manifest.get("profile", "")).lower()
    if profile != "full":
        errors.append("CONF-V13-001 UAAF v1.3 extensions require full profile")

    git_cfg = extensions.get("git_traceability") or {}
    git_rel = str(git_cfg.get("file", ".ai/health/GIT-BASELINE.yaml"))
    git_path = root / git_rel
    if not git_path.exists():
        errors.append(f"CONF-V13-002 git baseline missing: {git_rel}")
    else:
        data = _safe_yaml(git_path)
        if data.get("schema_version") != "1.3":
            errors.append("CONF-V13-003 git baseline schema_version must be 1.3")
        if not data.get("head"):
            warnings.append("CONF-V13-004 git baseline has no captured HEAD yet")
        elif not re.fullmatch(r"[0-9a-fA-F]{40,64}", str(data.get("head"))):
            errors.append("CONF-V13-005 git baseline head must be a hexadecimal commit id")

    claim_cfg = extensions.get("claim_leasing") or {}
    claim_rel = str(claim_cfg.get("file", ".ai/agents/CLAIMS.yaml"))
    claim_path = root / claim_rel
    if not claim_path.exists():
        errors.append(f"CONF-V13-006 claims file missing: {claim_rel}")
    else:
        data = _safe_yaml(claim_path)
        if str(data.get("schema_version", "1.3")) != "1.3":
            errors.append("CONF-V13-007 claims schema_version must be 1.3")
        for claim in data.get("claims", []) or []:
            if not isinstance(claim, dict):
                errors.append("CONF-V13-008 claim must be a mapping")
                continue
            for key in ["claim_id", "resource", "agent", "task", "status"]:
                if not claim.get(key):
                    errors.append(f"CONF-V13-009 claim missing {key}")
            status = str(claim.get("status", ""))
            if status not in {"ACTIVE", "RELEASED", "EXPIRED", "RECLAIMABLE"}:
                errors.append(f"CONF-V13-010 claim has invalid status {status!r}")
            if status == "ACTIVE" and not claim.get("lease_until"):
                errors.append("CONF-V13-011 active claim requires lease_until")

    runtime_cfg = extensions.get("runtime_verification") or {}
    runtime_rel = str(runtime_cfg.get("file", ".ai/verification/RUNTIME-POLICY.yaml"))
    runtime_path = root / runtime_rel
    if not runtime_path.exists():
        errors.append(f"CONF-V13-012 runtime verification policy missing: {runtime_rel}")
    else:
        data = _safe_yaml(runtime_path)
        if data.get("schema_version") != "1.3":
            errors.append("CONF-V13-013 runtime policy schema_version must be 1.3")
        if data.get("enabled") is True and not isinstance(data.get("allow"), list):
            errors.append("CONF-V13-014 runtime policy allow must be a list")



def validate_v14_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    extensions = manifest.get("extensions") or {}
    if extension_num(manifest) < 1.4:
        return
    profile = str(manifest.get("profile", "")).lower()
    if profile != "full":
        errors.append("CONF-V14-001 UAAF v1.4 extensions require full profile")

    sec_cfg = extensions.get("security_diagnostics") or {}
    sec_rel = str(sec_cfg.get("file", ".ai/security/SECURITY-DIAGNOSTICS.md"))
    sec_path = root / sec_rel
    if not sec_path.exists():
        errors.append(f"CONF-V14-002 security diagnostics contract missing: {sec_rel}")
    else:
        text = sec_path.read_text(encoding="utf-8", errors="ignore").lower()
        for marker in ["static", "read-only", "secret"]:
            if marker not in text:
                warnings.append(f"CONF-V14-003 security diagnostics contract missing concept: {marker}")

    git_cfg = extensions.get("git_task_traceability") or {}
    git_rel = str(git_cfg.get("file", ".ai/health/GIT-TASK-TRACEABILITY.md"))
    git_path = root / git_rel
    if not git_path.exists():
        errors.append(f"CONF-V14-004 Git↔Task traceability contract missing: {git_rel}")
    else:
        text = git_path.read_text(encoding="utf-8", errors="ignore").lower()
        for marker in ["task", "git", "expected changes", "advisory"]:
            if marker not in text:
                warnings.append(f"CONF-V14-005 Git↔Task contract missing concept: {marker}")

    runtime_cfg = extensions.get("runtime_evidence") or {}
    runtime_rel = str(runtime_cfg.get("file", ".ai/verification/RUNTIME-EVIDENCE.md"))
    runtime_path = root / runtime_rel
    if not runtime_path.exists():
        errors.append(f"CONF-V14-006 runtime evidence contract missing: {runtime_rel}")
    required_risk = runtime_cfg.get("required_for_risk", [])
    if not isinstance(required_risk, list):
        errors.append("CONF-V14-007 runtime_evidence.required_for_risk must be a list")
    else:
        allowed_risk = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        for value in required_risk:
            if str(value).upper() not in allowed_risk:
                errors.append(f"CONF-V14-008 invalid required_for_risk value: {value!r}")

    policy = root / ".ai/verification/RUNTIME-POLICY.yaml"
    if not policy.exists():
        errors.append("CONF-V14-009 runtime policy required for v1.4 delivery evidence")
    else:
        data = _safe_yaml(policy)
        if data.get("schema_version") != "1.3":
            errors.append("CONF-V14-010 runtime policy schema_version must remain 1.3")

    for path in (root / ".ai/tasks").rglob("TASK-*.yaml") if (root / ".ai/tasks").exists() else []:
        data = _safe_yaml(path)
        if not data:
            continue
        expected = data.get("expected_changes")
        if expected is not None and not isinstance(expected, dict):
            errors.append(f"CONF-V14-011 {path.relative_to(root)} expected_changes must be a mapping")
        verification = data.get("verification") or []
        if isinstance(verification, dict):
            verification = [verification]
        for item in verification:
            if isinstance(item, dict) and str(item.get("type", "")).lower() in {"runtime", "runtime_verification", "runtime-evidence"}:
                if item.get("required") is True and not str(item.get("command", "")).strip():
                    warnings.append(f"CONF-V14-012 {path.relative_to(root)} requires runtime verification but declares no command")


def validate_v15_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    extensions = manifest.get("extensions") or {}
    if extension_num(manifest) < 1.5:
        return
    profile = str(manifest.get("profile", "")).lower()
    if profile != "full":
        errors.append("CONF-V15-001 UAAF v1.5 extensions require full profile")

    obs_cfg = extensions.get("observability") or {}
    policy_rel = str(obs_cfg.get("policy", ".ai/observability/POLICY.yaml"))
    events_rel = str(obs_cfg.get("events", ".ai/observability/EVENTS.jsonl"))
    mode = str(obs_cfg.get("mode", "metadata_first"))
    if mode != "metadata_first":
        errors.append("CONF-V15-002 observability.mode must be metadata_first")

    policy = root / policy_rel
    events = root / events_rel
    readme = root / ".ai/observability/README.md"
    if not policy.exists():
        errors.append(f"CONF-V15-003 observability policy missing: {policy_rel}")
    else:
        data = _safe_yaml(policy)
        if data.get("schema_version") != "1.5":
            errors.append("CONF-V15-004 observability policy schema_version must be 1.5")
        budgets = data.get("budgets") or {}
        required = [
            "max_average_context_tokens",
            "max_declared_unused_rate",
            "max_repeated_path_rate",
            "max_memory_stale_rate",
            "min_memory_reuse_rate",
            "max_replans_per_task",
        ]
        for key in required:
            if key not in budgets:
                errors.append(f"CONF-V15-005 observability budget missing: {key}")
        privacy = data.get("privacy") or {}
        for key in ["store_content", "store_prompt", "store_secret_values"]:
            if privacy.get(key) is not False:
                errors.append(f"CONF-V15-006 observability privacy.{key} must be false")
        retention = data.get("retention") or {}
        if int(retention.get("events_days", 0) or 0) < 1:
            warnings.append("CONF-V15-007 observability retention.events_days should be >= 1")

    if not events.exists():
        errors.append(f"CONF-V15-008 observability event log missing: {events_rel}")
    else:
        for idx, line in enumerate(events.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"CONF-V15-009 invalid JSON event at {events_rel}:{idx}")
                continue
            if not isinstance(item, dict):
                errors.append(f"CONF-V15-010 event at {events_rel}:{idx} must be an object")
                continue
            if item.get("schema_version") != "1.5":
                errors.append(f"CONF-V15-011 event at {events_rel}:{idx} schema_version must be 1.5")
            if item.get("type") not in {"context_load", "memory_reuse", "gate", "replan"}:
                errors.append(f"CONF-V15-012 event at {events_rel}:{idx} has unsupported type")
            for forbidden in ["prompt", "content", "secret"]:
                if forbidden in item:
                    errors.append(f"CONF-V15-013 event at {events_rel}:{idx} contains forbidden field {forbidden!r}")

    if not readme.exists():
        warnings.append("CONF-V15-014 observability README missing")
    else:
        text = readme.read_text(encoding="utf-8", errors="ignore").lower()
        for marker in ["metadata-first", "context", "memory", "prompt"]:
            if marker not in text:
                warnings.append(f"CONF-V15-015 observability README missing concept: {marker}")



def validate_v16_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    extensions = manifest.get("extensions") or {}
    if extension_num(manifest) < 1.6:
        return
    profile = str(manifest.get("profile", "")).lower()
    if profile != "full":
        errors.append("CONF-V16-001 UAAF v1.6 extensions require full profile")
    cfg = extensions.get("adaptive_learning") or {}
    if not cfg:
        errors.append("CONF-V16-002 adaptive_learning extension configuration missing")
        return
    if str(cfg.get("mode", "")) != "advisory_only":
        errors.append("CONF-V16-003 adaptive_learning.mode must be advisory_only")
    for key, default in [("policy", ".ai/optimization/POLICY.yaml"), ("analysis", ".ai/optimization/ANALYSIS.yaml"), ("proposals", ".ai/optimization/PROPOSALS.yaml")]:
        rel = str(cfg.get(key, default))
        if not (root / rel).exists():
            errors.append(f"CONF-V16-004 adaptive learning {key} missing: {rel}")
    policy = root / str(cfg.get("policy", ".ai/optimization/POLICY.yaml"))
    if policy.exists():
        data = _safe_yaml(policy)
        if data.get("schema_version") != "1.6":
            errors.append("CONF-V16-005 adaptive policy schema_version must be 1.6")
        if data.get("enabled") is True:
            safety = data.get("safety") or {}
            for key in ["auto_apply", "allow_policy_mutation", "allow_intent_mutation", "allow_memory_delete"]:
                if safety.get(key) is not False:
                    errors.append(f"CONF-V16-006 safety.{key} must be false by default")
        adaptive = data.get("adaptive") or {}
        for key in ["min_unused_rate", "min_repeated_rate", "min_memory_reuse_rate", "max_replan_rate_per_task", "min_gate_done_rate"]:
            if key not in adaptive:
                errors.append(f"CONF-V16-007 adaptive policy missing threshold: {key}")
    for key, code in [("analysis", "CONF-V16-008"), ("proposals", "CONF-V16-009")]:
        path = root / str(cfg.get(key, f".ai/optimization/{key.upper()}.yaml"))
        if path.exists():
            data = _safe_yaml(path)
            if data.get("schema_version") != "1.6":
                errors.append(f"{code} {key} schema_version must be 1.6")
            if data.get("mode") != "advisory":
                errors.append(f"{code} {key} mode must be advisory")
    proposals = root / str(cfg.get("proposals", ".ai/optimization/PROPOSALS.yaml"))
    if proposals.exists():
        data = _safe_yaml(proposals)
        for rec in data.get("recommendations", []) or []:
            if not isinstance(rec, dict):
                errors.append("CONF-V16-010 recommendation must be a mapping")
                continue
            if rec.get("status") not in {"PROPOSED", "ACCEPTED", "REJECTED", "EXPIRED"}:
                errors.append(f"CONF-V16-011 invalid recommendation status: {rec.get('status')!r}")
            if str(rec.get("safety", "ADVISORY_ONLY")) != "ADVISORY_ONLY":
                errors.append("CONF-V16-012 recommendations must remain ADVISORY_ONLY")
            if not rec.get("evidence"):
                warnings.append(f"CONF-V16-013 recommendation {rec.get('id')} has no evidence payload")


def validate_v17_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    extensions = manifest.get("extensions") or {}
    if extension_num(manifest) < 1.7:
        return
    profile = str(manifest.get("profile", "")).lower()
    if profile != "full":
        errors.append("CONF-V17-001 UAAF v1.7 extensions require full profile")
    cfg = extensions.get("governance") or {}
    if not cfg:
        errors.append("CONF-V17-002 governance extension configuration missing")
        return
    if str(cfg.get("mode", "")) != "explicit_approval":
        errors.append("CONF-V17-003 governance.mode must be explicit_approval")
    rels = {
        "policy": str(cfg.get("policy", ".ai/governance/POLICY.yaml")),
        "proposals": str(cfg.get("proposals", ".ai/governance/PROPOSALS.yaml")),
        "audit": str(cfg.get("audit", ".ai/governance/AUDIT.jsonl")),
    }
    for key, rel in rels.items():
        if not (root / rel).exists():
            errors.append(f"CONF-V17-004 governance {key} missing: {rel}")
    policy = root / rels["policy"]
    if policy.exists():
        data = _safe_yaml(policy)
        if data.get("schema_version") != "1.7":
            errors.append("CONF-V17-005 governance policy schema_version must be 1.7")
        if data.get("auto_apply") is not False:
            errors.append("CONF-V17-006 governance policy auto_apply must be false")
        if data.get("require_reviewer") is not True:
            errors.append("CONF-V17-007 governance policy require_reviewer must be true")
        if data.get("require_precondition_match") is not True:
            errors.append("CONF-V17-008 governance policy require_precondition_match must be true")
        allowed = data.get("allowed_mutation_paths") or []
        if not isinstance(allowed, list) or not allowed:
            errors.append("CONF-V17-009 allowed_mutation_paths must be non-empty")
        forbidden = data.get("forbidden_keys") or []
        if "intent" not in [str(x) for x in forbidden]:
            errors.append("CONF-V17-010 forbidden_keys must protect intent")
    proposals = root / rels["proposals"]
    if proposals.exists():
        data = _safe_yaml(proposals)
        if data.get("schema_version") != "1.7":
            errors.append("CONF-V17-011 governance proposals schema_version must be 1.7")
        valid = {"PROPOSED", "REVIEWED", "APPROVED", "REJECTED", "APPLIED", "VERIFIED", "EXPIRED"}
        transitions = {"PROPOSED": {"reviewed", "approved", "rejected", "expired"}}
        for row in data.get("proposals", []) or []:
            if not isinstance(row, dict):
                errors.append("CONF-V17-012 proposal must be a mapping")
                continue
            status = str(row.get("status", ""))
            if status not in valid:
                errors.append(f"CONF-V17-013 invalid governance proposal status: {status!r}")
            gov = row.get("governance") or {}
            if status == "APPROVED" and not gov.get("approved_by"):
                errors.append(f"CONF-V17-014 approved proposal {row.get('id')} missing approved_by")
            if status in {"APPLIED", "VERIFIED"} and not gov.get("backup"):
                errors.append(f"CONF-V17-015 applied proposal {row.get('id')} missing rollback backup")
            if status == "VERIFIED" and not gov.get("verified_at"):
                errors.append(f"CONF-V17-016 verified proposal {row.get('id')} missing verified_at")
    audit = root / rels["audit"]
    if audit.exists():
        for idx, line in enumerate(audit.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"CONF-V17-017 invalid audit JSON at {rels['audit']}:{idx}")
                continue
            if not isinstance(event, dict) or event.get("schema_version") != "1.7":
                errors.append(f"CONF-V17-018 invalid audit event at {rels['audit']}:{idx}")


def validate_v18_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    extensions = manifest.get("extensions") or {}
    if extension_num(manifest) < 1.8:
        return
    profile = str(manifest.get("profile", "")).lower()
    if profile != "full":
        errors.append("CONF-V18-001 UAAF v1.8 extensions require full profile")
    cfg = extensions.get("agent_trust") or {}
    if not cfg:
        errors.append("CONF-V18-002 agent_trust extension configuration missing")
        return
    if str(cfg.get("mode", "")) != "bounded_delegation":
        errors.append("CONF-V18-003 agent_trust.mode must be bounded_delegation")
    rels = {
        "policy": str(cfg.get("policy", ".ai/agents/TRUST.yaml")),
        "delegations": str(cfg.get("delegations", ".ai/agents/DELEGATIONS.yaml")),
        "audit": str(cfg.get("audit", ".ai/agents/TRUST-AUDIT.jsonl")),
    }
    for key, rel in rels.items():
        if not (root / rel).exists():
            errors.append(f"CONF-V18-004 agent_trust {key} missing: {rel}")
    policy = root / rels["policy"]
    agents: dict[str, dict[str, Any]] = {}
    if policy.exists():
        data = _safe_yaml(policy)
        if data.get("schema_version") != "1.8":
            errors.append("CONF-V18-005 trust policy schema_version must be 1.8")
        policy_cfg = data.get("policy") or {}
        if policy_cfg.get("enabled") is not True:
            errors.append("CONF-V18-006 trust policy.enabled must be true")
        deny = policy_cfg.get("deny_actions") or []
        if not isinstance(deny, list):
            errors.append("CONF-V18-007 trust policy deny_actions must be a list")
        for agent in data.get("agents", []) or []:
            if not isinstance(agent, dict):
                errors.append("CONF-V18-008 trust agent entry must be a mapping")
                continue
            required = ["id", "status", "capabilities", "max_risk", "min_evidence"]
            for key in required:
                if key not in agent:
                    errors.append(f"CONF-V18-009 trust agent {agent.get('id')} missing {key}")
            ident = str(agent.get("id", ""))
            if not ident:
                continue
            if ident in agents:
                errors.append(f"CONF-V18-010 duplicate trust agent ID: {ident}")
            agents[ident] = agent
            if str(agent.get("status", "")) not in {"ACTIVE", "SUSPENDED", "REVOKED"}:
                errors.append(f"CONF-V18-011 invalid trust agent status for {ident}")
            if str(agent.get("max_risk", "")).upper() not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                errors.append(f"CONF-V18-012 invalid max_risk for {ident}")
            ev = str(agent.get("min_evidence", ""))
            if not re.fullmatch(r"E[0-5]", ev.upper()):
                errors.append(f"CONF-V18-013 invalid min_evidence for {ident}")
    delegations = root / rels["delegations"]
    delegation_map: dict[str, dict[str, Any]] = {}
    if delegations.exists():
        data = _safe_yaml(delegations)
        if data.get("schema_version") != "1.8":
            errors.append("CONF-V18-014 delegations schema_version must be 1.8")
        for row in data.get("delegations", []) or []:
            if not isinstance(row, dict):
                errors.append("CONF-V18-015 delegation must be a mapping")
                continue
            did = str(row.get("delegation_id", ""))
            for key in ["delegation_id", "from_agent", "to_agent", "status", "expires_at"]:
                if not row.get(key):
                    errors.append(f"CONF-V18-016 delegation {did or '<unknown>'} missing {key}")
            if did and did in delegation_map:
                errors.append(f"CONF-V18-017 duplicate delegation ID: {did}")
            delegation_map[did] = row
            status = str(row.get("status", ""))
            if status not in {"ACTIVE", "REVOKED", "EXPIRED", "SUSPENDED"}:
                errors.append(f"CONF-V18-018 invalid delegation status for {did}")
            from_id = str(row.get("from_agent", "")); to_id = str(row.get("to_agent", ""))
            if from_id and from_id not in agents:
                errors.append(f"CONF-V18-019 unknown delegator {from_id} in {did}")
            if to_id and to_id not in agents:
                errors.append(f"CONF-V18-020 unknown delegatee {to_id} in {did}")
            if from_id == to_id and from_id:
                errors.append(f"CONF-V18-021 self-delegation forbidden: {did}")
            expires = str(row.get("expires_at", ""))
            try:
                datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"CONF-V18-022 invalid expires_at for {did}")
            caps = row.get("capabilities") or []
            if not isinstance(caps, list) or not caps:
                errors.append(f"CONF-V18-023 delegation {did} capabilities must be a non-empty list")
            risk = str(row.get("max_risk", "")).upper()
            if risk not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                errors.append(f"CONF-V18-024 invalid delegation max_risk for {did}")
    # Validate non-escalation for every delegation.
    rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    active_graph: dict[str, list[str]] = defaultdict(list)
    for did, row in delegation_map.items():
        parent = agents.get(str(row.get("from_agent", "")))
        child = agents.get(str(row.get("to_agent", "")))
        if not parent or not child:
            continue
        pcaps = {str(x).lower() for x in (parent.get("capabilities") or [])}
        dcaps = {str(x).lower() for x in (row.get("capabilities") or [])}
        if "*" not in pcaps and not dcaps.issubset(pcaps):
            errors.append(f"CONF-V18-025 delegation capability escalation: {did}")
        pdomains = {str(x).lower() for x in (parent.get("domains") or [])}
        ddomains = {str(x).lower() for x in (row.get("domains") or [])}
        if pdomains and "*" not in pdomains and not ddomains.issubset(pdomains):
            errors.append(f"CONF-V18-026 delegation domain escalation: {did}")
        if rank.get(str(row.get("max_risk", "")).upper(), 99) > rank.get(str(parent.get("max_risk", "")).upper(), 0):
            errors.append(f"CONF-V18-027 delegation risk escalation: {did}")
        if not str(row.get("expires_at", "")).strip():
            errors.append(f"CONF-V18-028 delegation expiry required: {did}")
        if str(row.get("status", "")) == "ACTIVE" and str(row.get("from_agent", "")) and str(row.get("to_agent", "")):
            active_graph[str(row.get("from_agent"))].append(str(row.get("to_agent")))

    visited: set[str] = set()
    stack: set[str] = set()
    def dfs_cycle(node: str) -> None:
        if node in stack:
            errors.append(f"CONF-V18-031 active delegation cycle detected at {node}")
            return
        if node in visited:
            return
        visited.add(node); stack.add(node)
        for nxt in active_graph.get(node, []):
            dfs_cycle(nxt)
        stack.remove(node)
    for node in list(active_graph):
        dfs_cycle(node)

    audit = root / rels["audit"]
    if audit.exists() and extension_num(manifest) < 1.9:
        for idx, line in enumerate(audit.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"CONF-V18-029 invalid trust audit JSON at {rels['audit']}:{idx}")
                continue
            if not isinstance(event, dict) or event.get("schema_version") != "1.8":
                errors.append(f"CONF-V18-030 invalid trust audit event at {rels['audit']}:{idx}")



def validate_v19_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str], pinned_root_fingerprint: str | None = None) -> None:
    extensions = manifest.get("extensions") or {}
    if extension_num(manifest) < 1.9:
        return
    profile = str(manifest.get("profile", "")).lower()
    if profile != "full":
        errors.append("CONF-V19-001 UAAF v1.9 extensions require full profile")
    cfg = extensions.get("cryptographic_integrity") or {}
    if not cfg:
        errors.append("CONF-V19-002 cryptographic_integrity extension configuration missing")
        return
    if str(cfg.get("mode", "")) != "signed_detached_ed25519":
        errors.append("CONF-V19-003 cryptographic_integrity.mode must be signed_detached_ed25519")
    required_purposes = cfg.get("required_purposes") or []
    if not isinstance(required_purposes, list):
        errors.append("CONF-V19-003A required_purposes must be a list")
    else:
        missing_purposes = [p for p in ["trust-root", "trust-keys", "trust-policy", "delegations"] if p not in required_purposes]
        if missing_purposes:
            errors.append(f"CONF-V19-003B required_purposes missing: {','.join(missing_purposes)}")
    rels = {
        "root": str(cfg.get("root", ".ai/trust/ROOT.yaml")),
        "keys": str(cfg.get("keys", ".ai/trust/KEYS.yaml")),
    }
    for name, rel in rels.items():
        if not (root / rel).exists():
            errors.append(f"CONF-V19-004 trust {name} missing: {rel}")
    trust_root = root / rels["root"]
    keys = root / rels["keys"]
    root_doc = _safe_yaml(trust_root) if trust_root.exists() else {}
    key_doc = _safe_yaml(keys) if keys.exists() else {}
    if trust_root.exists() and root_doc.get("schema_version") != "1.9":
        errors.append("CONF-V19-005 ROOT.yaml schema_version must be 1.9")
    if keys.exists() and key_doc.get("schema_version") != "1.9":
        errors.append("CONF-V19-006 KEYS.yaml schema_version must be 1.9")
    anchor = root_doc.get("anchor") or {}
    if anchor:
        try:
            import base64
            import hashlib
            raw = base64.b64decode(str(anchor.get("public_key", "")), validate=True)
            if len(raw) != 32:
                errors.append("CONF-V19-007 root public key must be 32 raw bytes")
            if hashlib.sha256(raw).hexdigest() != str(anchor.get("fingerprint_sha256", "")):
                errors.append("CONF-V19-008 root fingerprint mismatch")
        except Exception:
            errors.append("CONF-V19-009 invalid root public key encoding")
    else:
        warnings.append("CONF-V19-010 trust anchor is not initialized")
    for entry in key_doc.get("keys", []) or []:
        if not isinstance(entry, dict):
            errors.append("CONF-V19-011 key entry must be a mapping")
            continue
        for key in ["key_id", "algorithm", "public_key", "fingerprint_sha256", "status"]:
            if not entry.get(key):
                errors.append(f"CONF-V19-012 key entry missing {key}")
        if str(entry.get("algorithm")) != "Ed25519":
            errors.append(f"CONF-V19-013 unsupported key algorithm for {entry.get('key_id')}")
        try:
            import base64, hashlib
            raw = base64.b64decode(str(entry.get("public_key", "")), validate=True)
            if len(raw) != 32 or hashlib.sha256(raw).hexdigest() != str(entry.get("fingerprint_sha256", "")):
                errors.append(f"CONF-V19-014 key fingerprint mismatch for {entry.get('key_id')}")
        except Exception:
            errors.append(f"CONF-V19-015 invalid public key encoding for {entry.get('key_id')}")
    for candidate in (root / ".ai/trust").rglob("*") if (root / ".ai/trust").exists() else []:
        if candidate.is_file() and (candidate.name.endswith(".private.pem") or ".private." in candidate.name):
            errors.append(f"CONF-V19-016 private key must not exist in project trust directory: {candidate.relative_to(root)}")
    root_policy = root_doc.get("policy") or {}
    required = bool(root_policy.get("cryptographic_required", False))
    root_required_purposes = root_policy.get("required_purposes") or []
    if required:
        missing_root_purposes = [p for p in ["trust-root", "trust-keys", "trust-policy", "delegations"] if p not in root_required_purposes]
        if missing_root_purposes:
            errors.append(f"CONF-V19-020 ROOT.yaml policy required_purposes missing: {','.join(missing_root_purposes)}")
    try:
        from uaf_crypto import verify_project_bundle
        result = verify_project_bundle(root, pinned_root_fingerprint=pinned_root_fingerprint)
        if required and result.get("status") != "PASS":
            errors.append(f"CONF-V19-017 cryptographic bundle verification failed: {result.get('failed', [])}")
        elif not required and result.get("status") != "PASS":
            warnings.append("CONF-V19-018 cryptographic bundle is not fully verified (policy does not require signatures)")
    except Exception as exc:
        errors.append(f"CONF-V19-019 unable to evaluate cryptographic bundle: {exc}")


def validate_v20_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    extensions = manifest.get("extensions") or {}
    if extension_num(manifest) < 2.0:
        return
    profile = str(manifest.get("profile", "")).lower()
    if profile != "full":
        errors.append("CONF-V20-001 UAAF v2.0 federation requires full profile")
    if not str((manifest.get("framework") or {}).get("version", "")).startswith("2."):
        errors.append("CONF-V20-002 framework.version must be 2.x for v2.0")
    if str((manifest.get("protocols") or {}).get("federation", "")) != "UAAF-FED-2.0":
        errors.append("CONF-V20-003 protocols.federation must be UAAF-FED-2.0")
    cfg = extensions.get("distributed_federation") or {}
    if not cfg:
        errors.append("CONF-V20-004 distributed_federation extension configuration missing")
        return
    required = {
        "identity": ".ai/federation/IDENTITY.yaml",
        "peers": ".ai/federation/PEERS.yaml",
        "policy": ".ai/federation/FEDERATION-POLICY.yaml",
        "replay": ".ai/federation/REPLAY.yaml",
        "audit": ".ai/federation/AUDIT.jsonl",
        "state": ".ai/federation/state",
        "handoffs": ".ai/federation/HANDOFFS",
    }
    for key, default in required.items():
        rel = str(cfg.get(key, default))
        if not (root / rel).exists():
            errors.append(f"CONF-V20-005 missing {key}: {rel}")
    identity = _safe_yaml(root / required["identity"])
    if identity.get("schema_version") != "2.0":
        errors.append("CONF-V20-006 IDENTITY.yaml schema_version must be 2.0")
    peers = _safe_yaml(root / required["peers"])
    policy = _safe_yaml(root / required["policy"])
    replay = _safe_yaml(root / required["replay"])
    for key, doc in [("PEERS.yaml", peers), ("FEDERATION-POLICY.yaml", policy), ("REPLAY.yaml", replay)]:
        if doc.get("schema_version") != "2.0":
            errors.append(f"CONF-V20-007 {key} schema_version must be 2.0")
    if bool(cfg.get("default_deny", True)) and policy.get("default_deny") is not True:
        errors.append("CONF-V20-008 federation policy must be default_deny")
    if bool(cfg.get("signed_handoff", True)) and policy.get("require_signed_handoff") is not True:
        errors.append("CONF-V20-009 signed handoff requirement missing")
    if bool(cfg.get("signed_state", True)) and policy.get("require_signed_state") is not True:
        errors.append("CONF-V20-010 signed state requirement missing")
    if not isinstance(replay.get("seen", []), list):
        errors.append("CONF-V20-011 replay store seen must be a list")
    state_dir = root / required["state"]
    if state_dir.exists():
        for rel in ["VECTOR.yaml", "REGISTERS.yaml", "CONFLICTS.yaml"]:
            if not (state_dir / rel).exists():
                errors.append(f"CONF-V20-012 missing state file: {rel}")
        conflicts = _safe_yaml(state_dir / "CONFLICTS.yaml").get("conflicts", []) or []
        unresolved = [x for x in conflicts if isinstance(x, dict) and str(x.get("status", "UNRESOLVED")) == "UNRESOLVED"]
        if unresolved:
            warnings.append(f"CONF-V20-013 {len(unresolved)} unresolved federation state conflicts")
    # Private keys must never be stored in federation namespace.
    fed = root / ".ai/federation"
    if fed.exists():
        for candidate in fed.rglob("*"):
            if candidate.is_file() and (candidate.name.endswith(".private.pem") or ".private." in candidate.name or candidate.name.endswith(".key")):
                errors.append(f"CONF-V20-014 private key material must not exist in federation namespace: {candidate.relative_to(root)}")
    try:
        identity_rel = str(cfg.get("identity", required["identity"]))
        identity_path = root / identity_rel
        identity_sig = root / (identity_rel + ".sig")
        identity_body = identity.get("identity") or {}
        trust_root = root / ".ai/trust/ROOT.yaml"
        anchor = (_safe_yaml(trust_root).get("anchor") or {}) if trust_root.exists() else {}
        import base64, json
        root_public_raw = base64.b64decode(str(anchor.get("public_key", "")), validate=True) if anchor.get("public_key") else b""
        from uaf_federation import verify_payload

        if identity_body:
            if not identity_sig.exists():
                warnings.append("CONF-V20-015 federation identity is not signed yet")
            elif not root_public_raw:
                errors.append("CONF-V20-016 federation identity cannot be verified without a trust-root public key")
            else:
                try:
                    identity_env = json.loads(identity_sig.read_text(encoding="utf-8"))
                    ok, reason = verify_payload(identity, identity_env, root_public_raw, "federation-identity")
                except Exception as exc:
                    ok, reason = False, f"VERIFY_ERROR:{exc}"
                if not ok:
                    errors.append(f"CONF-V20-016 federation identity signature invalid: {reason}")

        policy_rel = str(cfg.get("policy", required["policy"]))
        policy_path = root / policy_rel
        policy_sig = root / (policy_rel + ".sig")
        if bool(policy.get("require_signed_handoff", True)) or bool(policy.get("require_signed_state", True)):
            if not policy_sig.exists():
                warnings.append("CONF-V20-017 federation policy is not signed yet")
            elif not root_public_raw:
                errors.append("CONF-V20-018 federation policy cannot be verified without a trust-root public key")
            else:
                try:
                    policy_env = json.loads(policy_sig.read_text(encoding="utf-8"))
                    ok, reason = verify_payload(policy, policy_env, root_public_raw, "federation-policy")
                except Exception as exc:
                    ok, reason = False, f"VERIFY_ERROR:{exc}"
                if not ok:
                    errors.append(f"CONF-V20-018 federation policy signature invalid: {reason}")
    except Exception as exc:
        errors.append(f"CONF-V20-019 unable to verify federation signatures: {exc}")


def validate_v21_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    if extension_num(manifest) < 2.1:
        return
    profile = str(manifest.get("profile", "")).lower()
    if profile != "full":
        errors.append("CONF-V21-001 UAAF v2.1 federation operations require full profile")
    protocols = manifest.get("protocols") or {}
    if str(protocols.get("federation_ops", "")) != "UAAF-FED-2.1":
        errors.append("CONF-V21-002 protocols.federation_ops must be UAAF-FED-2.1")
    cfg = (manifest.get("extensions") or {}).get("federation_operations") or {}
    if not cfg:
        errors.append("CONF-V21-003 federation_operations configuration missing")
        return
    required = {
        "mode": ".ai/federation/ops/MODE.yaml",
        "cursors": ".ai/federation/ops/CURSORS.yaml",
        "bundles": ".ai/federation/ops/BUNDLES.yaml",
        "revocations": ".ai/federation/ops/REVOCATIONS.yaml",
        "checkpoints": ".ai/federation/ops/CHECKPOINTS.yaml",
        "conflicts": ".ai/federation/ops/CONFLICTS.yaml",
        "observability": ".ai/federation/ops/OBSERVABILITY.jsonl",
    }
    for key, default in required.items():
        rel = str(cfg.get(key, default))
        if not (root / rel).exists():
            errors.append(f"CONF-V21-004 missing {key}: {rel}")
    mode = _safe_yaml(root / required["mode"])
    cursors = _safe_yaml(root / required["cursors"])
    bundles = _safe_yaml(root / required["bundles"])
    revs = _safe_yaml(root / required["revocations"])
    checkpoints = _safe_yaml(root / required["checkpoints"])
    conflicts = _safe_yaml(root / required["conflicts"])
    for name, doc in [("MODE.yaml", mode), ("CURSORS.yaml", cursors), ("BUNDLES.yaml", bundles), ("REVOCATIONS.yaml", revs), ("CHECKPOINTS.yaml", checkpoints), ("CONFLICTS.yaml", conflicts)]:
        if doc.get("schema_version") != "2.1":
            errors.append(f"CONF-V21-005 {name} schema_version must be 2.1")
    if str(mode.get("mode", "ONLINE")).upper() not in {"ONLINE", "OFFLINE", "PARTITIONED", "RECOVERING"}:
        errors.append("CONF-V21-006 invalid federation operational mode")
    if not isinstance(cursors.get("peers", {}), dict):
        errors.append("CONF-V21-007 CURSORS.peers must be a mapping")
    consumed = bundles.get("consumed", [])
    if not isinstance(consumed, list) or len(set(map(str, consumed))) != len(consumed):
        errors.append("CONF-V21-008 BUNDLES consumed must be a unique list")
    try:
        epoch = int(revs.get("revocation_epoch", 0) or 0)
        if epoch < 0:
            raise ValueError
        entries = revs.get("entries", []) or []
        epochs = [int(x.get("revocation_epoch", -1)) for x in entries if isinstance(x, dict)]
        if epochs and max(epochs) > epoch:
            errors.append("CONF-V21-009 revocation_epoch must dominate all entries")
        if epochs and epochs != sorted(epochs):
            warnings.append("CONF-V21-010 revocation entries are not ordered by epoch")
        ids = [str(x.get("revocation_id")) for x in entries if isinstance(x, dict)]
        if len(ids) != len(set(ids)):
            errors.append("CONF-V21-011 duplicate revocation_id")
    except Exception:
        errors.append("CONF-V21-009 invalid revocation epoch structure")
    cps = checkpoints.get("checkpoints", []) or []
    if not isinstance(cps, list):
        errors.append("CONF-V21-012 checkpoints must be a list")
    cfs = conflicts.get("conflicts", []) or []
    valid_states = {"UNRESOLVED", "PROPOSED", "APPROVED", "RESOLVED", "REJECTED"}
    for row in cfs:
        if not isinstance(row, dict) or str(row.get("status", "UNRESOLVED")) not in valid_states:
            errors.append("CONF-V21-013 invalid conflict lifecycle state")
    obs_path = root / required["observability"]
    if obs_path.exists():
        for line_no, line in enumerate(obs_path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                errors.append(f"CONF-V21-014 observability line {line_no} is invalid JSON")
                continue
            forbidden = {"prompt", "prompts", "source", "source_content", "secret", "private_key", "token"}
            if forbidden.intersection(row):
                errors.append(f"CONF-V21-015 observability line {line_no} contains forbidden content fields")
    # Private keys must never exist under federation operations.
    fed_ops = root / ".ai/federation/ops"
    if fed_ops.exists():
        for candidate in fed_ops.rglob("*"):
            if candidate.is_file() and (candidate.name.endswith(".private.pem") or ".private." in candidate.name or candidate.name.endswith(".key")):
                errors.append(f"CONF-V21-016 private key under federation ops: {candidate.relative_to(root)}")



def validate_v22_extensions(root: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    ext = manifest.get("extensions") or {}
    protocols = manifest.get("protocols") or {}
    version = str(ext.get("version", ""))
    if version != "2.2":
        return
    if str(manifest.get("profile", "standard")).lower() != "full":
        errors.append("CONF-V22-001 UAAF v2.2 federation intelligence requires full profile")
    if str(protocols.get("federation", "")) != "UAAF-FED-2.0":
        errors.append("CONF-V22-002 protocols.federation must remain UAAF-FED-2.0")
    if str(protocols.get("federation_ops", "")) != "UAAF-FED-2.1":
        errors.append("CONF-V22-003 protocols.federation_ops must remain UAAF-FED-2.1")
    if str(protocols.get("federation_intelligence", "")) != "UAAF-FED-2.2":
        errors.append("CONF-V22-004 protocols.federation_intelligence must be UAAF-FED-2.2")
    cfg = ext.get("federation_intelligence") or {}
    if not cfg:
        errors.append("CONF-V22-005 federation_intelligence configuration missing")
        return
    required = {
        "policy": ".ai/federation/policy/INHERITANCE.yaml",
        "effective_policy": ".ai/federation/policy/EFFECTIVE.yaml",
        "conflict_analysis": ".ai/federation/intelligence/CONFLICT-ANALYSIS.yaml",
        "checkpoint_selection": ".ai/federation/intelligence/CHECKPOINT-SELECTION.yaml",
        "recovery_recommendation": ".ai/federation/intelligence/RECOVERY-RECOMMENDATION.yaml",
    }
    for key, rel in required.items():
        if str(cfg.get(key, "")) != rel:
            errors.append(f"CONF-V22-006 {key} path must be {rel}")
        if not (root / rel).exists():
            errors.append(f"CONF-V22-007 missing federation intelligence artifact: {rel}")
    inh = root / ".ai/federation/policy/INHERITANCE.yaml"
    eff = root / ".ai/federation/policy/EFFECTIVE.yaml"
    if inh.exists():
        doc = _safe_yaml(inh)
        if str(doc.get("schema_version")) != "2.2": errors.append("CONF-V22-008 policy inheritance schema must be 2.2")
        local = doc.get("local") or {}
        if str(local.get("max_risk", "")).upper() not in {"LOW","MEDIUM","HIGH","CRITICAL"}:
            errors.append("CONF-V22-009 invalid inherited local max_risk")
        try:
            actions = set(local.get("allowed_actions", []) or [])
            denied = set(local.get("denied_actions", []) or [])
            valid_actions = {"handoff","state-pull","state-push","capability-sync","policy-sync"}
            if not actions.issubset(valid_actions) or not denied.issubset(valid_actions):
                errors.append("CONF-V22-010 invalid policy action")
            if actions & denied:
                warnings.append("CONF-V22-011 local policy both allows and denies an action; deny wins")
        except Exception:
            errors.append("CONF-V22-010 invalid policy action structure")
        if bool(doc.get("inherit", False)):
            try:
                from uaf_federation_policy import resolve
                result = resolve(root)
                if result.get("status") != "PASS":
                    errors.append(f"CONF-V22-012 policy inheritance cannot resolve: {result.get('reason','UNKNOWN')}")
            except Exception as exc:
                errors.append(f"CONF-V22-013 policy inheritance resolution error: {exc}")
    if eff.exists():
        edoc = _safe_yaml(eff)
        if str(edoc.get("schema_version")) != "2.2": errors.append("CONF-V22-014 effective policy schema must be 2.2")
        effective = edoc.get("effective") or {}
        if effective and str(effective.get("max_risk", "")).upper() not in {"LOW","MEDIUM","HIGH","CRITICAL"}:
            errors.append("CONF-V22-015 invalid effective policy max_risk")
        if str(edoc.get("status", "")) not in {"UNRESOLVED","PASS","FAIL"}:
            errors.append("CONF-V22-016 invalid effective policy status")
    analysis = root / ".ai/federation/intelligence/CONFLICT-ANALYSIS.yaml"
    if analysis.exists():
        adoc = _safe_yaml(analysis)
        for item in adoc.get("conflicts", []) or []:
            if isinstance(item, dict) and item.get("classification", {}).get("action") == "AUTO_RESOLVE":
                errors.append("CONF-V22-017 semantic conflict intelligence must not emit AUTO_RESOLVE")
    for rel in [".ai/federation/intelligence/CONFLICT-ANALYSIS.yaml", ".ai/federation/intelligence/CHECKPOINT-SELECTION.yaml", ".ai/federation/intelligence/RECOVERY-RECOMMENDATION.yaml"]:
        if (root/rel).exists():
            text=(root/rel).read_text(encoding="utf-8", errors="ignore")
            if "private_key" in text or "secret" in text.lower():
                warnings.append(f"CONF-V22-018 intelligence artifact may contain sensitive field names: {rel}")


def validate_v23_extensions(root: Path, manifest: dict, errors: list[str], warnings: list[str]):
    ext = manifest.get("extensions") or {}
    version = str(ext.get("version", "0"))
    if version != "2.3":
        return
    if str(manifest.get("profile", "")).lower() != "full":
        errors.append("CONF-V23-001 UAAF v2.3 federation negotiation requires full profile")
    protocols = manifest.get("protocols") or {}
    checks = {
        "federation": "UAAF-FED-2.0",
        "federation_ops": "UAAF-FED-2.1",
        "federation_intelligence": "UAAF-FED-2.2",
        "federation_policy": "UAAF-FED-2.3",
    }
    for key, expected in checks.items():
        if str(protocols.get(key, "")) != expected:
            errors.append(f"CONF-V23-00{2+list(checks).index(key)} protocols.{key} must be {expected}")
    cfg = ext.get("federation_policy_negotiation") or {}
    if not cfg:
        errors.append("CONF-V23-006 federation_policy_negotiation configuration missing")
    paths = {
        "contract": ".ai/federation/negotiation/CAPABILITY-CONTRACT.yaml",
        "negotiation": ".ai/federation/negotiation/NEGOTIATION.yaml",
        "enforcement": ".ai/federation/negotiation/ENFORCEMENT-POLICY.yaml",
    }
    for key, rel in paths.items():
        if str(cfg.get(key, "")) != rel:
            errors.append(f"CONF-V23-007 {key} path must be {rel}")
        if not (root / rel).exists():
            errors.append(f"CONF-V23-008 missing federation negotiation artifact: {rel}")
    ep = root / paths["enforcement"]
    if ep.exists():
        doc = _safe_yaml(ep)
        if str(doc.get("schema_version")) != "2.3":
            errors.append("CONF-V23-009 enforcement policy schema must be 2.3")
        if doc.get("default_deny") is not True:
            errors.append("CONF-V23-010 enforcement policy must be default_deny")
        if doc.get("fail_closed") is not True:
            errors.append("CONF-V23-011 enforcement policy must be fail_closed")
    cp = root / paths["contract"]
    if cp.exists():
        doc = _safe_yaml(cp)
        if str(doc.get("schema_version")) != "2.3":
            errors.append("CONF-V23-012 capability contract schema must be 2.3")
        contract = doc.get("contract") or {}
        status = str(doc.get("status", "UNNEGOTIATED"))
        if status == "NEGOTIATED":
            if not doc.get("contract_hash"):
                errors.append("CONF-V23-013 negotiated contract missing contract_hash")
            if contract.get("max_risk") not in {"LOW","MEDIUM","HIGH","CRITICAL"}:
                errors.append("CONF-V23-014 invalid negotiated max_risk")
            if contract.get("min_evidence") not in {f"E{i}" for i in range(6)}:
                errors.append("CONF-V23-015 invalid negotiated min_evidence")
            if contract.get("domain_scope") not in {"ALL", "SET", "NONE"}:
                errors.append("CONF-V23-015 invalid negotiated domain_scope")
            if contract.get("domain_scope") == "NONE":
                errors.append("CONF-V23-015 negotiated contract cannot be active with domain_scope NONE")
            if not contract.get("allowed_actions"):
                errors.append("CONF-V23-015 negotiated contract must contain at least one allowed action")
    np = root / paths["negotiation"]
    if np.exists():
        doc = _safe_yaml(np)
        if str(doc.get("schema_version")) != "2.3":
            errors.append("CONF-V23-016 negotiation schema must be 2.3")
        status = str(doc.get("status", "NOT_RUN"))
        if status not in {"NOT_RUN","NEGOTIATED","REVIEW_REQUIRED","DENIED"}:
            errors.append("CONF-V23-017 invalid negotiation status")
        contract = doc.get("negotiated_policy") or {}
        if contract:
            if contract.get("allowed_actions") and contract.get("status") == "ACTIVE":
                warnings.append("CONF-V23-018 negotiated contract status should be represented by capability contract")
            if contract.get("max_risk") not in {"LOW","MEDIUM","HIGH","CRITICAL"}:
                errors.append("CONF-V23-019 invalid negotiated policy max_risk")
            if contract.get("min_evidence") not in {f"E{i}" for i in range(6)}:
                errors.append("CONF-V23-020 invalid negotiated policy min_evidence")
    # Semantic safety invariant: v2.3 enforcement is a restriction layer, never an escalation layer.
    if cp.exists() and (root / ".ai/federation/policy/EFFECTIVE.yaml").exists():
        try:
            from uaf_federation_negotiation import non_escalating, normalize_policy
            local = normalize_policy(_safe_yaml(root / ".ai/federation/policy/EFFECTIVE.yaml").get("effective") or {})
            cdoc = _safe_yaml(cp)
            c = cdoc.get("contract") or {}
            if cdoc.get("status") == "NEGOTIATED":
                ok, reason = non_escalating(local, local, c)
                if not ok:
                    errors.append(f"CONF-V23-021 negotiated contract is not non-escalating: {reason}")
        except Exception as exc:
            warnings.append(f"CONF-V23-022 could not perform non-escalation cross-check: {exc}")

def validate_v24_extensions(root: Path, manifest: dict, errors: list[str], warnings: list[str]):
    ext = manifest.get("extensions") or {}
    version = str(ext.get("version", "0"))
    if version != "2.4":
        return
    if str(manifest.get("profile", "")).lower() != "full":
        errors.append("CONF-V24-001 UAAF v2.4 protocol negotiation requires full profile")
    protocols = manifest.get("protocols") or {}
    required = {
        "federation": "UAAF-FED-2.0",
        "federation_ops": "UAAF-FED-2.1",
        "federation_intelligence": "UAAF-FED-2.2",
        "federation_policy": "UAAF-FED-2.3",
        "federation_protocol": "UAAF-FED-2.4",
    }
    for i, (key, expected) in enumerate(required.items(), 2):
        if str(protocols.get(key, "")) != expected:
            errors.append(f"CONF-V24-{i:03d} protocols.{key} must be {expected}")
    cfg = ext.get("federation_protocol_negotiation") or {}
    if not cfg:
        errors.append("CONF-V24-007 federation_protocol_negotiation configuration missing")
        return
    paths = {
        "capabilities": ".ai/federation/protocol/CAPABILITIES.yaml",
        "compatibility": ".ai/federation/protocol/COMPATIBILITY.yaml",
        "negotiation": ".ai/federation/protocol/NEGOTIATION.yaml",
        "contract": ".ai/federation/protocol/PROTOCOL-CONTRACT.yaml",
        "audit": ".ai/federation/protocol/AUDIT.jsonl",
    }
    for key, rel in paths.items():
        if str(cfg.get(key, "")) != rel:
            errors.append(f"CONF-V24-008 {key} path must be {rel}")
        if not (root / rel).exists():
            errors.append(f"CONF-V24-009 missing federation protocol artifact: {rel}")
    cap = root / paths["capabilities"]
    if cap.exists():
        doc = _safe_yaml(cap)
        if str(doc.get("schema_version")) != "2.4":
            errors.append("CONF-V24-010 capabilities schema must be 2.4")
        protocols_doc = doc.get("protocols") or {}
        if str((protocols_doc.get("federation_protocol") or [""])[-1]) != "2.4":
            errors.append("CONF-V24-011 local capabilities must advertise federation_protocol 2.4")
        features = doc.get("features") or {}
        for feature in ("capability-exchange", "protocol-negotiation"):
            if feature not in features:
                errors.append(f"CONF-V24-012 required feature missing: {feature}")
    compat = root / paths["compatibility"]
    if compat.exists() and compat.stat().st_size > 0:
        doc = _safe_yaml(compat)
        if str(doc.get("schema_version")) != "2.4":
            errors.append("CONF-V24-013 compatibility schema must be 2.4")
    np = root / paths["negotiation"]
    cp = root / paths["contract"]
    if np.exists():
        nd = _safe_yaml(np)
        if str(nd.get("schema_version")) != "2.4":
            errors.append("CONF-V24-014 negotiation schema must be 2.4")
        if str(nd.get("status", "NOT_RUN")) not in {"NOT_RUN", "NEGOTIATED", "FALLBACK_NEGOTIATED", "DENIED", "REVIEW_REQUIRED"}:
            errors.append("CONF-V24-015 invalid protocol negotiation status")
    if cp.exists():
        cd = _safe_yaml(cp)
        if str(cd.get("schema_version")) != "2.4":
            errors.append("CONF-V24-016 protocol contract schema must be 2.4")
        contract = cd.get("contract") or {}
        if contract and contract.get("authority_change") != "NONE":
            errors.append("CONF-V24-017 protocol contract must not change authority")
        if cd.get("status") in {"NEGOTIATED", "FALLBACK_NEGOTIATED"} and not cd.get("contract_hash"):
            errors.append("CONF-V24-018 active protocol contract missing contract_hash")
        v24_features = {"capability-exchange", "protocol-negotiation", "safe-fallback", "federated-policy", "federation-ops", "conflict-intelligence"}
        for feature in contract.get("enabled_features", []) or []:
            if feature not in v24_features:
                errors.append(f"CONF-V24-019 unknown negotiated feature: {feature}")
        fallbacks = contract.get("fallbacks") or {}
        if fallbacks:
            for family, item in fallbacks.items():
                if not isinstance(item, dict) or not item.get("selected"):
                    errors.append(f"CONF-V24-020 malformed fallback record: {family}")
        # A fallback may never silently select a version newer than a local advertised version.
        for family, version in (contract.get("protocols") or {}).items():
            advertised = (_safe_yaml(cap).get("protocols") or {}).get(family, []) if cap.exists() else []
            if advertised and str(version) not in {str(v) for v in advertised}:
                errors.append(f"CONF-V24-021 selected protocol not locally advertised: {family}:{version}")
        neg = _safe_yaml(np) if np.exists() else {}
        remote_caps = neg.get("remote_capabilities") or {}
        remote_protocols = remote_caps.get("protocols") or {}
        local_protocols = _safe_yaml(cap).get("protocols") or {} if cap.exists() else {}
        for family, version in (contract.get("protocols") or {}).items():
            if str(version) not in {str(v) for v in (remote_protocols.get(family) or [])}:
                errors.append(f"CONF-V24-024 selected protocol not remotely advertised: {family}:{version}")
            if str(version) not in {str(v) for v in (local_protocols.get(family) or [])}:
                errors.append(f"CONF-V24-025 selected protocol not locally advertised: {family}:{version}")
    # Conservative contract checks. Protocol negotiation never grants additional authority.
    if cp.exists() and (root / ".ai/federation/negotiation/CAPABILITY-CONTRACT.yaml").exists():
        try:
            cd = _safe_yaml(cp)
            selected = (cd.get("contract") or {}).get("protocols") or {}
            if str(cd.get("status")) in {"NEGOTIATED", "FALLBACK_NEGOTIATED"} and not selected:
                errors.append("CONF-V24-022 active protocol contract has no selected protocols")
        except Exception as exc:
            warnings.append(f"CONF-V24-023 unable to cross-check protocol contract: {exc}")



def validate_v25_extensions(root: Path, manifest: dict, errors: list[str], warnings: list[str]):
    ext = manifest.get("extensions") or {}
    version = str(ext.get("version", "0"))
    if version != "2.5":
        return
    if str(manifest.get("profile", "")).lower() != "full":
        errors.append("CONF-V25-001 UAAF v2.5 secure transport requires full profile")
    protocols = manifest.get("protocols") or {}
    for key, expected in {
        "federation": "UAAF-FED-2.0",
        "federation_ops": "UAAF-FED-2.1",
        "federation_intelligence": "UAAF-FED-2.2",
        "federation_policy": "UAAF-FED-2.3",
        "federation_protocol": "UAAF-FED-2.4",
        "federation_transport": "UAAF-FED-2.5",
    }.items():
        if str(protocols.get(key, "")) != expected:
            errors.append(f"CONF-V25-002 protocols.{key} must be {expected}")
    cfg = ext.get("federation_transport") or {}
    required_paths = {
        "channels": ".ai/federation/transport/CHANNELS",
        "inbox": ".ai/federation/transport/INBOX",
        "outbox": ".ai/federation/transport/OUTBOX",
        "audit": ".ai/federation/transport/AUDIT.jsonl",
    }
    for key, rel in required_paths.items():
        if str(cfg.get(key, "")) != rel:
            errors.append(f"CONF-V25-003 {key} path must be {rel}")
        if not (root / rel).exists():
            errors.append(f"CONF-V25-004 missing transport artifact: {rel}")
    if cfg.get("confidentiality") is not False:
        errors.append("CONF-V25-005 transport confidentiality must explicitly be false for reference layer")
    for key in ("authentication", "integrity", "anti_replay", "session_binding"):
        if not cfg.get(key):
            errors.append(f"CONF-V25-006 transport {key} must be enabled")
    proto = root / ".ai/federation/protocol/PROTOCOL-CONTRACT.yaml"
    if not proto.exists():
        errors.append("CONF-V25-007 v2.4 protocol contract required before secure transport")
    else:
        contract = _safe_yaml(proto)
        status = str(contract.get("status", ""))
        if status not in {"NEGOTIATED", "FALLBACK_NEGOTIATED"}:
            warnings.append("CONF-V25-008 transport cannot be opened until v2.4 protocol contract is active")
        selected = (contract.get("contract") or {}).get("protocols") or {}
        if str(selected.get("federation_protocol", "")) != "2.4":
            warnings.append("CONF-V25-009 transport reference currently requires negotiated federation_protocol 2.4")
    transport_dir = root / ".ai/federation/transport"
    if transport_dir.exists():
        channels = list((transport_dir / "CHANNELS").glob("CH-*.yaml")) if (transport_dir / "CHANNELS").exists() else []
        for path in channels:
            ch = _safe_yaml(path)
            if str(ch.get("schema_version", "")) != "2.5":
                errors.append(f"CONF-V25-010 channel schema mismatch: {path.name}")
            if str(ch.get("status", "")) == "OPEN" and not ch.get("binding"):
                errors.append(f"CONF-V25-011 open channel missing session binding: {path.name}")
            if int(ch.get("send_seq", 0) or 0) < 0 or int(ch.get("recv_seq", 0) or 0) < 0:
                errors.append(f"CONF-V25-012 negative channel sequence: {path.name}")

def check(path: Path, level: str = "standard", pinned_root_fingerprint: str | None = None) -> tuple[list[str], list[str], list[str]]:
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
    validate_v13_extensions(root, manifest, errors, warnings)
    validate_v14_extensions(root, manifest, errors, warnings)
    validate_v15_extensions(root, manifest, errors, warnings)
    validate_v16_extensions(root, manifest, errors, warnings)
    validate_v17_extensions(root, manifest, errors, warnings)
    validate_v18_extensions(root, manifest, errors, warnings)
    validate_v19_extensions(root, manifest, errors, warnings, pinned_root_fingerprint)
    validate_v20_extensions(root, manifest, errors, warnings)
    validate_v21_extensions(root, manifest, errors, warnings)
    validate_v22_extensions(root, manifest, errors, warnings)
    validate_v23_extensions(root, manifest, errors, warnings)
    validate_v24_extensions(root, manifest, errors, warnings)
    validate_v25_extensions(root, manifest, errors, warnings)

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
    parser = argparse.ArgumentParser(description="Validate a UAAF project")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--level", choices=["minimal", "core", "standard", "full"], default="standard")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument("--pinned-root-fingerprint", default="", help="out-of-band SHA-256 fingerprint for the v1.9 root trust anchor")
    args = parser.parse_args()

    level = "core" if args.level == "minimal" else args.level
    errors, warnings, infos = check(Path(args.path), level, args.pinned_root_fingerprint or None)
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
