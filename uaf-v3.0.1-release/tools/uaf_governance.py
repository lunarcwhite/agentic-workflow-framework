#!/usr/bin/env python3
"""UAAF v1.7 Policy Governance & Safe Adaptation.

Explicit review/approval is required before an adaptive proposal may be applied.
Only allowlisted, non-sensitive YAML paths may be mutated. Every apply creates a
rollback snapshot and append-only audit event. No automatic application exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "1.7"
STATUSES = {"PROPOSED", "REVIEWED", "APPROVED", "REJECTED", "APPLIED", "VERIFIED", "EXPIRED"}
TRANSITIONS = {
    "PROPOSED": {"REVIEWED", "REJECTED", "EXPIRED"},
    "REVIEWED": {"APPROVED", "REJECTED", "EXPIRED"},
    "APPROVED": {"APPLIED", "REJECTED", "EXPIRED"},
    "APPLIED": {"VERIFIED", "REJECTED"},
    "VERIFIED": set(),
    "REJECTED": set(),
    "EXPIRED": set(),
}


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def sha256(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def governance_dir(root: Path) -> Path:
    return root / ".ai/governance"


def proposals_path(root: Path) -> Path:
    return governance_dir(root) / "PROPOSALS.yaml"


def audit_path(root: Path) -> Path:
    return governance_dir(root) / "AUDIT.jsonl"


def policy_path(root: Path) -> Path:
    return governance_dir(root) / "POLICY.yaml"


def load_proposals(root: Path) -> dict[str, Any]:
    return load_yaml(proposals_path(root))


def save_proposals(root: Path, doc: dict[str, Any]) -> None:
    governance_dir(root).mkdir(parents=True, exist_ok=True)
    proposals_path(root).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def append_audit(root: Path, event: dict[str, Any]) -> None:
    governance_dir(root).mkdir(parents=True, exist_ok=True)
    event = {"schema_version": SCHEMA_VERSION, "timestamp": now(), **event}
    with audit_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def get_policy(root: Path) -> dict[str, Any]:
    data = load_yaml(policy_path(root))
    if not data:
        data = {
            "schema_version": SCHEMA_VERSION,
            "enabled": True,
            "auto_apply": False,
            "require_reviewer": True,
            "require_precondition_match": True,
            "allowed_mutation_paths": [
                ".ai/optimization/POLICY.yaml",
                ".ai/context/ADAPTIVE-RULES.yaml",
                ".ai/capabilities.yaml",
            ],
            "forbidden_keys": ["intent", "safety.auto_apply", "safety.allow_policy_mutation", "safety.allow_intent_mutation"],
        }
    return data


def find(root: Path, proposal_id: str) -> tuple[int, dict[str, Any], dict[str, Any]]:
    doc = load_proposals(root)
    rows = doc.get("proposals") or []
    for i, item in enumerate(rows):
        if isinstance(item, dict) and str(item.get("id")) == proposal_id:
            return i, item, doc
    raise SystemExit(f"Proposal not found: {proposal_id}")


def import_proposals(root: Path) -> int:
    src = root / ".ai/optimization/PROPOSALS.yaml"
    if not src.exists():
        print("NO_SOURCE_PROPOSALS")
        return 0
    source = load_yaml(src)
    incoming = source.get("recommendations") or []
    doc = load_proposals(root)
    if doc.get("schema_version") != SCHEMA_VERSION:
        doc = {"schema_version": SCHEMA_VERSION, "generated_at": now(), "proposals": []}
    existing = {str(x.get("id")) for x in doc.get("proposals", []) if isinstance(x, dict)}
    added = 0
    for rec in incoming:
        if not isinstance(rec, dict) or not rec.get("id") or str(rec.get("id")) in existing:
            continue
        row = dict(rec)
        row.update({
            "status": "PROPOSED",
            "governance": {"created_at": now(), "source": str(src.relative_to(root)), "approver": None, "approval_reason": None, "preconditions": {}, "backup": None, "applied_at": None, "verified_at": None},
        })
        doc.setdefault("proposals", []).append(row)
        existing.add(str(rec["id"]))
        added += 1
    doc["updated_at"] = now()
    save_proposals(root, doc)
    append_audit(root, {"action": "IMPORT", "added": added})
    print(f"IMPORTED {added}")
    return 0


def transition(root: Path, proposal_id: str, target: str, reviewer: str | None = None, reason: str = "") -> int:
    idx, row, doc = find(root, proposal_id)
    current = str(row.get("status", "PROPOSED"))
    if target not in TRANSITIONS.get(current, set()):
        raise SystemExit(f"Invalid transition {current} -> {target}")
    gov = row.setdefault("governance", {})
    if target in {"REVIEWED", "APPROVED", "REJECTED"}:
        if not reviewer or not reviewer.strip():
            raise SystemExit("A non-empty reviewer/approver is required.")
        if target == "APPROVED":
            policy = get_policy(root)
            if bool(policy.get("auto_apply", False)):
                raise SystemExit("Governance policy forbids auto_apply=true.")
            changes = row.get("changes") or []
            # Approval can happen without changes; such a proposal is reviewable but not applicable.
            gov["approved_by"] = reviewer
        gov["reviewer"] = reviewer
        if reason:
            gov["reason"] = reason
    if target == "APPROVED":
        policy = get_policy(root)
        pre = {}
        for change in row.get("changes") or []:
            path = str(change.get("path", "")) if isinstance(change, dict) else ""
            if path:
                pre[path] = sha256(root / path)
        gov["preconditions"] = pre
        gov["approved_at"] = now()
    elif target == "REJECTED":
        gov["rejected_at"] = now()
    row["status"] = target
    row["updated_at"] = now()
    doc["proposals"][idx] = row
    doc["updated_at"] = now()
    save_proposals(root, doc)
    append_audit(root, {"action": target, "proposal_id": proposal_id, "reviewer": reviewer, "reason": reason})
    print(f"{target} {proposal_id}")
    return 0


def set_dotted(data: Any, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    if not parts or any(not p for p in parts):
        raise ValueError("invalid key")
    cur = data
    for part in parts[:-1]:
        if not isinstance(cur, dict):
            raise ValueError("intermediate path is not a mapping")
        cur = cur.setdefault(part, {})
    if not isinstance(cur, dict):
        raise ValueError("target is not a mapping")
    cur[parts[-1]] = value


def apply(root: Path, proposal_id: str) -> int:
    idx, row, doc = find(root, proposal_id)
    if str(row.get("status")) != "APPROVED":
        raise SystemExit("Only APPROVED proposals may be applied.")
    policy = get_policy(root)
    if bool(policy.get("auto_apply", False)):
        raise SystemExit("auto_apply must remain false.")
    allowed = {str(p) for p in policy.get("allowed_mutation_paths") or []}
    forbidden = {str(p) for p in policy.get("forbidden_keys") or []}
    changes = row.get("changes") or []
    if not changes:
        raise SystemExit("Proposal has no explicit changes; it is advisory-only and cannot be applied.")

    gov = row.setdefault("governance", {})
    if bool(policy.get("require_precondition_match", True)):
        pre = gov.get("preconditions") or {}
        for change in changes:
            path = str(change.get("path", ""))
            if path not in allowed:
                raise SystemExit(f"Mutation path is not allowlisted: {path}")
            current_hash = sha256(root / path)
            if current_hash != str(pre.get(path, "")):
                raise SystemExit(f"Precondition mismatch: {path}")

    backups = []
    for change in changes:
        if not isinstance(change, dict) or change.get("operation") != "set":
            raise SystemExit("Only operation=set is supported in v1.7 safe apply.")
        path = str(change.get("path", ""))
        key = str(change.get("key", ""))
        if path not in allowed:
            raise SystemExit(f"Mutation path is not allowlisted: {path}")
        if any(key == f or key.startswith(f + ".") for f in forbidden):
            raise SystemExit(f"Forbidden governance key: {key}")
        if not key or key.startswith("intent"):
            raise SystemExit(f"Unsafe mutation key: {key}")
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        backup_dir = governance_dir(root) / "rollback" / proposal_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / (path.replace("/", "__") + ".bak")
        if target.exists():
            shutil.copy2(target, backup)
        else:
            backup.write_text("__MISSING__", encoding="utf-8")
        backups.append({"path": path, "backup": str(backup.relative_to(root))})
        data = load_yaml(target) if target.exists() else {}
        set_dotted(data, key, change.get("value"))
        target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    gov["backup"] = backups
    gov["applied_at"] = now()
    gov["status_before_apply"] = "APPROVED"
    row["status"] = "APPLIED"
    row["updated_at"] = now()
    doc["proposals"][idx] = row
    doc["updated_at"] = now()
    save_proposals(root, doc)
    append_audit(root, {"action": "APPLY", "proposal_id": proposal_id, "changes": changes, "backups": backups})
    print(f"APPLIED {proposal_id}")
    return 0


def verify(root: Path, proposal_id: str) -> int:
    idx, row, doc = find(root, proposal_id)
    if str(row.get("status")) != "APPLIED":
        raise SystemExit("Only APPLIED proposals may be verified.")
    for change in row.get("changes") or []:
        path = root / str(change.get("path", ""))
        data = load_yaml(path)
        if path.exists() and not data:
            raise SystemExit(f"Verification failed: invalid/empty YAML at {path.relative_to(root)}")
    row["status"] = "VERIFIED"
    row.setdefault("governance", {})["verified_at"] = now()
    row["updated_at"] = now()
    doc["proposals"][idx] = row
    doc["updated_at"] = now()
    save_proposals(root, doc)
    append_audit(root, {"action": "VERIFIED", "proposal_id": proposal_id})
    print(f"VERIFIED {proposal_id}")
    return 0


def rollback(root: Path, proposal_id: str) -> int:
    idx, row, doc = find(root, proposal_id)
    if str(row.get("status")) not in {"APPLIED", "VERIFIED"}:
        raise SystemExit("Only APPLIED/VERIFIED proposals may be rolled back.")
    backups = (row.get("governance") or {}).get("backup") or []
    if not backups:
        raise SystemExit("No rollback snapshot recorded.")
    for item in backups:
        target = root / str(item["path"])
        backup = root / str(item["backup"])
        if backup.read_text(encoding="utf-8", errors="ignore") == "__MISSING__":
            if target.exists():
                target.unlink()
        else:
            shutil.copy2(backup, target)
    row["status"] = "REJECTED"
    row.setdefault("governance", {})["rolled_back_at"] = now()
    row["updated_at"] = now()
    doc["proposals"][idx] = row
    doc["updated_at"] = now()
    save_proposals(root, doc)
    append_audit(root, {"action": "ROLLBACK", "proposal_id": proposal_id, "backups": backups})
    print(f"ROLLED_BACK {proposal_id}")
    return 0


def check(root: Path) -> int:
    policy = get_policy(root)
    if policy.get("schema_version") != SCHEMA_VERSION:
        print("FAIL\nPOLICY_SCHEMA")
        return 1
    if policy.get("auto_apply") is not False or policy.get("require_reviewer") is not True:
        print("FAIL\nUNSAFE_POLICY")
        return 1
    doc = load_proposals(root)
    if doc.get("schema_version") != SCHEMA_VERSION:
        print("FAIL\nPROPOSALS_SCHEMA")
        return 1
    for row in doc.get("proposals") or []:
        if not isinstance(row, dict) or str(row.get("status")) not in STATUSES:
            print("FAIL\nINVALID_PROPOSAL_STATUS")
            return 1
    print("PASS")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.7 policy governance and safe adaptation")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["import", "status", "review", "approve", "reject", "apply", "verify", "rollback", "check"], nargs="?", default="status")
    p.add_argument("--proposal")
    p.add_argument("--reviewer")
    p.add_argument("--reason", default="")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    root = Path(args.path).resolve()
    if args.action == "import": raise SystemExit(import_proposals(root))
    if args.action == "check": raise SystemExit(check(root))
    if args.action == "status":
        doc = load_proposals(root)
        payload = {"schema_version": SCHEMA_VERSION, "proposals": doc.get("proposals", [])}
        if args.json: print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            for row in payload["proposals"]: print(f"{row.get('id')} {row.get('status')}")
        raise SystemExit(0)
    if not args.proposal:
        raise SystemExit("--proposal is required")
    if args.action == "review": raise SystemExit(transition(root, args.proposal, "REVIEWED", args.reviewer, args.reason))
    if args.action == "approve": raise SystemExit(transition(root, args.proposal, "APPROVED", args.reviewer, args.reason))
    if args.action == "reject": raise SystemExit(transition(root, args.proposal, "REJECTED", args.reviewer, args.reason))
    if args.action == "apply": raise SystemExit(apply(root, args.proposal))
    if args.action == "verify": raise SystemExit(verify(root, args.proposal))
    if args.action == "rollback": raise SystemExit(rollback(root, args.proposal))


if __name__ == "__main__":
    main()
