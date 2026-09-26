#!/usr/bin/env python3
"""UAAF v3.0 Federated Agent Runtime.

Reference runtime for explicit remote task delegation, capability-aware routing,
execution leases, cancellation, signed remote results/evidence, and an
end-to-end provenance hash chain.

Security/authority rules:
- remote execution is deny-by-default and contract-bound;
- capability is not authorization; local trust policy is still evaluated;
- delegated authority cannot exceed the local delegator's trust profile;
- signed task contracts are required;
- leases bound execution in time and to one agent;
- cancellation and expiry are terminal for a lease;
- results must bind to the exact task contract and lease;
- evidence is attested with hashes; optional local artifact hashing upgrades the
  receipt from metadata-only to independently artifact-checked;
- no private key material is stored by this module or in the runtime bundle.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

TOOLS = Path(__file__).resolve().parent
SCHEMA = "3.0"
FED = Path(".ai/federation")
RUNTIME = FED / "runtime"
POLICY = RUNTIME / "POLICY.yaml"
ROUTES = RUNTIME / "ROUTES.yaml"
TASK_DIR = RUNTIME / "TASK-CONTRACTS"
LEASES = RUNTIME / "LEASES.yaml"
LEASE_RECEIPT_DIR = RUNTIME / "LEASE-RECEIPTS"
CANCEL_DIR = RUNTIME / "CANCELLATIONS"
RESULT_DIR = RUNTIME / "RESULTS"
EVIDENCE_DIR = RUNTIME / "EVIDENCE"
PROVENANCE = RUNTIME / "PROVENANCE.jsonl"
AUDIT = RUNTIME / "AUDIT.jsonl"
PEERS = FED / "PEERS.yaml"
IDENTITY = FED / "IDENTITY.yaml"
KEY_REFS = FED / "secure" / "KEY-REFERENCES.yaml"
RISK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
EVIDENCE_LEVEL = {f"E{i}": i for i in range(6)}
ACTIONS = {"read", "write", "delete", "migrate", "approve", "apply", "verify"}
PURPOSE_TASK = "federation-task-delegation"
PURPOSE_RESULT = "federation-task-result"
PURPOSE_CANCEL = "federation-task-cancellation"
PURPOSE_LEASE = "federation-task-lease"
ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]*-[A-Z0-9_-]{2,}$")


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def load_yaml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return value if isinstance(value, dict) else dict(default or {})
    except Exception:
        return dict(default or {})


def save_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def project_id(root: Path) -> str:
    manifest = load_yaml(root / ".ai/manifest.yaml", {})
    return str((manifest.get("project") or {}).get("name") or root.name)


def local_identity(root: Path) -> dict[str, Any]:
    return load_yaml(root / IDENTITY, {"schema_version": "2.0", "identity": {}}).get("identity") or {}


def local_project_id(root: Path) -> str:
    identity = local_identity(root)
    return str(identity.get("project_id") or project_id(root))


def peers_doc(root: Path) -> dict[str, Any]:
    return load_yaml(root / PEERS, {"schema_version": "2.0", "peers": []})


def peer_by_id(root: Path, peer_id: str) -> dict[str, Any] | None:
    for peer in peers_doc(root).get("peers", []) or []:
        if isinstance(peer, dict) and str(peer.get("peer_id")) == peer_id and str(peer.get("status", "ACTIVE")).upper() == "ACTIVE":
            return peer
    return None


def runtime_policy(root: Path) -> dict[str, Any]:
    return load_yaml(root / POLICY, {})


def routes_doc(root: Path) -> dict[str, Any]:
    return load_yaml(root / ROUTES, {"schema_version": SCHEMA, "default_deny": True, "peers": []})


def leases_doc(root: Path) -> dict[str, Any]:
    return load_yaml(root / LEASES, {"schema_version": SCHEMA, "leases": []})


def contract_path(root: Path, task_id: str) -> Path:
    return root / TASK_DIR / f"{task_id}.yaml"


def result_path(root: Path, task_id: str) -> Path:
    return root / RESULT_DIR / f"{task_id}.yaml"


def lease_receipt_path(root: Path, task_id: str) -> Path:
    return root / LEASE_RECEIPT_DIR / f"{task_id}.yaml"


def cancel_path(root: Path, task_id: str) -> Path:
    return root / CANCEL_DIR / f"{task_id}.yaml"


def validate_id(value: str, prefix: str) -> None:
    if not value or not value.startswith(prefix + "-") or not ID_RE.match(value):
        raise ValueError(f"INVALID_{prefix}_ID")


def parse_csv(values: list[str] | str) -> list[str]:
    result: list[str] = []
    if isinstance(values, str):
        values = [values]
    for value in values:
        for token in str(value).split(","):
            token = token.strip()
            if token and token not in result:
                result.append(token)
    return result


def read_data_file(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise ValueError(f"INVALID_YAML:{exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("INPUT_MUST_BE_MAPPING")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def audit(root: Path, event: dict[str, Any]) -> None:
    append_hash_chain(root / AUDIT, {"schema_version": SCHEMA, "timestamp": iso(), **event})


def provenance(root: Path, event: dict[str, Any]) -> str:
    return append_hash_chain(root / PROVENANCE, {"schema_version": SCHEMA, "timestamp": iso(), **event})


def append_hash_chain(path: Path, row: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = "GENESIS"
    if path.exists():
        lines = [line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
        if lines:
            try:
                previous = str(json.loads(lines[-1]).get("entry_hash", "BROKEN"))
            except Exception:
                previous = "BROKEN"
    row = dict(row)
    row["prev_hash"] = previous
    row["entry_hash"] = sha256_bytes(canon(row))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return str(row["entry_hash"])


def load_key_reference(root: Path, key_id: str) -> dict[str, Any] | None:
    doc = load_yaml(root / KEY_REFS, {"schema_version": "2.9", "references": []})
    for row in doc.get("references", []) or []:
        if isinstance(row, dict) and str(row.get("key_id")) == key_id:
            return row
    return None


def validate_signing_key_ref(root: Path, requested_ref: str | None, identity_key_id: str) -> None:
    selected = requested_ref or identity_key_id
    if not selected:
        raise ValueError("SIGNING_KEY_REFERENCE_REQUIRED")
    if selected != identity_key_id:
        raise ValueError("SIGNING_KEY_REF_MUST_MATCH_LOCAL_IDENTITY")
    ref = load_key_reference(root, selected)
    if requested_ref and not ref:
        raise ValueError("KEY_REFERENCE_NOT_FOUND")
    if ref:
        identity_fp = str(local_identity(root).get("fingerprint_sha256") or "")
        bound_fp = str(ref.get("public_fingerprint") or "")
        if identity_fp and bound_fp and identity_fp != bound_fp:
            raise ValueError("SIGNING_KEY_NOT_BOUND_TO_LOCAL_IDENTITY")
        if str(ref.get("status", "ACTIVE")).upper() != "ACTIVE":
            raise ValueError("SIGNING_KEY_REFERENCE_NOT_ACTIVE")


def provider_sign(root: Path, payload: dict[str, Any], key_id: str, purpose: str) -> dict[str, Any]:
    try:
        sys.path.insert(0, str(TOOLS))
        from uaf_key_ops import sign_payload  # type: ignore
        ref = load_key_reference(root, key_id)
        if not ref:
            raise ValueError("KEY_REFERENCE_NOT_FOUND")
        purposes = [str(x) for x in (ref.get("allowed_purposes") or [ref.get("purpose")]) if x]
        if purpose not in purposes:
            raise ValueError("KEY_PURPOSE_MISMATCH")
        return sign_payload(root, payload, key_id, purpose, schema=SCHEMA)
    finally:
        if str(TOOLS) in sys.path:
            sys.path.remove(str(TOOLS))


def legacy_sign(payload: dict[str, Any], private_path: Path, key_id: str, purpose: str) -> dict[str, Any]:
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("PRIVATE_KEY_NOT_ED25519")
    body = canon(payload)
    return {
        "schema_version": SCHEMA,
        "algorithm": "Ed25519",
        "purpose": purpose,
        "key_id": key_id,
        "payload_sha256": sha256_bytes(body),
        "signature_b64": base64.b64encode(key.sign(body)).decode("ascii"),
        "created_at": iso(),
        "provider": "legacy-private-key-compat",
    }


def sign(root: Path, payload: dict[str, Any], key_id: str, purpose: str, key_ref: str | None = None, private_key: Path | None = None) -> dict[str, Any]:
    if key_ref and private_key:
        raise ValueError("CHOOSE_KEY_REF_OR_PRIVATE_KEY")
    selected = key_ref or key_id
    if not selected:
        raise ValueError("SIGNING_KEY_REFERENCE_REQUIRED")
    if key_ref or load_key_reference(root, selected):
        return provider_sign(root, payload, selected, purpose)
    if private_key is None:
        raise ValueError("PROVIDER_KEY_REFERENCE_REQUIRED")
    return legacy_sign(payload, private_key, selected, purpose)


def peer_public_key(root: Path, peer_id: str) -> tuple[Ed25519PublicKey, dict[str, Any]]:
    peer = peer_by_id(root, peer_id)
    if not peer:
        raise ValueError("PEER_NOT_TRUSTED")
    public_b64 = str(peer.get("identity_public_key") or "")
    if not public_b64:
        identity_file = root / FED / "peers" / peer_id / "IDENTITY.yaml"
        identity = load_yaml(identity_file, {})
        public_b64 = str((identity.get("identity") or {}).get("public_key") or "")
    try:
        raw = base64.b64decode(public_b64, validate=True)
    except Exception as exc:
        raise ValueError("PEER_IDENTITY_PUBLIC_KEY_INVALID") from exc
    if len(raw) != 32:
        raise ValueError("PEER_IDENTITY_PUBLIC_KEY_INVALID")
    return Ed25519PublicKey.from_public_bytes(raw), peer


def verify_signature(payload: dict[str, Any], envelope: dict[str, Any], public_key: Ed25519PublicKey, purpose: str) -> tuple[bool, str]:
    if str(envelope.get("schema_version")) != SCHEMA:
        return False, "SIGNATURE_SCHEMA_MISMATCH"
    if str(envelope.get("algorithm")) != "Ed25519":
        return False, "SIGNATURE_ALGORITHM_MISMATCH"
    if str(envelope.get("purpose")) != purpose:
        return False, "SIGNATURE_PURPOSE_MISMATCH"
    body = canon(payload)
    if str(envelope.get("payload_sha256")) != sha256_bytes(body):
        return False, "SIGNATURE_PAYLOAD_HASH_MISMATCH"
    try:
        raw = base64.b64decode(str(envelope.get("signature_b64", "")), validate=True)
        public_key.verify(raw, body)
    except (ValueError, InvalidSignature, TypeError):
        return False, "SIGNATURE_INVALID"
    return True, "OK"


def verify_signer_binding(peer: dict[str, Any], envelope: dict[str, Any]) -> tuple[bool, str]:
    expected = str(peer.get("key_id") or "")
    actual = str(envelope.get("key_id") or "")
    if expected and actual != expected:
        return False, "SIGNER_KEY_ID_NOT_BOUND_TO_PEER_IDENTITY"
    return True, "OK"


def route_candidates(root: Path, capabilities: list[str], domain: str, risk: str) -> list[dict[str, Any]]:
    if risk.upper() not in RISK:
        raise ValueError("INVALID_RISK")
    requested = {c.lower() for c in capabilities}
    routes = routes_doc(root)
    peers_index = {str(p.get("peer_id")): p for p in (routes.get("peers") or []) if isinstance(p, dict)}
    candidates: list[dict[str, Any]] = []
    leases = active_leases(root)
    active_by_peer: dict[str, int] = {}
    for lease in leases:
        active_by_peer[str(lease.get("peer_id"))] = active_by_peer.get(str(lease.get("peer_id")), 0) + 1
    for peer_id, route in peers_index.items():
        if str(route.get("status", "ACTIVE")).upper() != "ACTIVE":
            continue
        peer = peer_by_id(root, peer_id)
        if not peer:
            continue
        if not requested.issubset({str(x).lower() for x in (route.get("capabilities") or [])}):
            continue
        domains = {str(x).lower() for x in (route.get("domains") or [])}
        if domains and "*" not in domains and domain.lower() not in domains:
            continue
        route_max_risk = str(route.get("max_risk", "LOW")).upper()
        peer_max_risk = str(peer.get("max_risk", "LOW")).upper()
        max_risk = min(RISK.get(route_max_risk, 0), RISK.get(peer_max_risk, 0))
        if RISK.get(risk.upper(), 99) > max_risk:
            continue
        limit = int(route.get("concurrent_limit", 1) or 1)
        if active_by_peer.get(peer_id, 0) >= limit:
            continue
        candidates.append({**route, "peer": peer, "active_leases": active_by_peer.get(peer_id, 0)})
    candidates.sort(key=lambda row: (int(row.get("priority", 100)), str(row.get("peer_id"))))
    return candidates


def active_leases(root: Path) -> list[dict[str, Any]]:
    doc = leases_doc(root)
    now_dt = now()
    result = []
    for row in doc.get("leases", []) or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "UNKNOWN")).upper()
        exp = parse_ts(row.get("expires_at"))
        if status == "ACTIVE" and exp and exp > now_dt:
            result.append(row)
    return result


def authorized_agent(root: Path, agent_id: str, actions: list[str], domain: str, risk: str, evidence: str) -> tuple[bool, str]:
    try:
        sys.path.insert(0, str(TOOLS))
        from uaf_trust import evaluate, effective_profiles  # type: ignore
        profiles = list(effective_profiles(root, agent_id))
        if not profiles:
            return False, "AGENT_NOT_AUTHORIZED"
        if not any(bool(profile.get("can_delegate", False)) for profile, _ in profiles):
            return False, "DELEGATOR_NOT_AUTHORIZED_TO_DELEGATE"
        for action in actions:
            decision = evaluate(root, agent_id, action, domain, risk, evidence)
            if decision.get("decision") != "AUTHORIZED":
                return False, f"DELEGATION_AUTHORIZATION_FAILED:{action}:{decision.get('reason')}"
        return True, "OK"
    except ImportError:
        return False, "TRUST_MODULE_UNAVAILABLE"
    finally:
        if str(TOOLS) in sys.path:
            sys.path.remove(str(TOOLS))


def agent_profile_authorized(root: Path, agent_id: str, actions: list[str], capabilities: list[str], domain: str, risk: str, evidence: str, allow_delegate: bool = False) -> tuple[bool, str]:
    try:
        sys.path.insert(0, str(TOOLS))
        from uaf_trust import evaluate, effective_profiles, has_capability, allows_domain, allowed_risk, evidence_ok  # type: ignore
        profiles = list(effective_profiles(root, agent_id))
        if not profiles:
            return False, "AGENT_NOT_AUTHORIZED"
        if allow_delegate and not any(bool(profile.get("can_delegate", False)) for profile, _ in profiles):
            return False, "AGENT_CANNOT_DELEGATE"
        for profile, _ in profiles:
            if not all(has_capability(profile, action) for action in actions):
                continue
            if not all(has_capability(profile, capability) for capability in capabilities):
                continue
            if not allows_domain(profile, domain):
                continue
            if not allowed_risk(profile, risk):
                continue
            if not evidence_ok(profile, evidence):
                continue
            return True, "OK"
        return False, "AGENT_CAPABILITY_OR_AUTHORITY_MISMATCH"
    except ImportError:
        return False, "TRUST_MODULE_UNAVAILABLE"
    finally:
        if str(TOOLS) in sys.path:
            sys.path.remove(str(TOOLS))


def ensure_policy(root: Path) -> dict[str, Any]:
    policy = runtime_policy(root)
    if not policy:
        raise ValueError("V30_RUNTIME_NOT_INITIALIZED")
    if policy.get("default_deny") is not True:
        raise ValueError("RUNTIME_POLICY_NOT_DEFAULT_DENY")
    if policy.get("require_signed_contract") is not True:
        raise ValueError("SIGNED_CONTRACT_REQUIRED")
    return policy


def contract_from_file(root: Path, task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    path = contract_path(root, task_id)
    if not path.exists():
        raise ValueError("TASK_CONTRACT_NOT_FOUND")
    bundle = load_yaml(path, {})
    if str(bundle.get("schema_version")) != SCHEMA or str(bundle.get("type")) != "federated_task_contract":
        raise ValueError("TASK_CONTRACT_SCHEMA_MISMATCH")
    payload = bundle.get("contract") or {}
    signature = bundle.get("signature") or {}
    if str(payload.get("task_id")) != task_id:
        raise ValueError("TASK_ID_BINDING_MISMATCH")
    expected_hash = current_contract_hash(payload)
    if str(bundle.get("contract_hash")) != expected_hash or str(payload.get("contract_hash")) != expected_hash:
        raise ValueError("TASK_CONTRACT_HASH_MISMATCH")
    return payload, signature


def sign_bundle(payload: dict[str, Any], signature: dict[str, Any], typ: str, content_hash_key: str = "contract_hash") -> dict[str, Any]:
    content_hash = sha256_bytes(canon(payload))
    payload = dict(payload)
    payload[content_hash_key] = content_hash
    return {"schema_version": SCHEMA, "type": typ, content_hash_key: content_hash, "payload": payload, "signature": signature}


def make_contract(args: argparse.Namespace, root: Path, selected_peer: dict[str, Any]) -> dict[str, Any]:
    validate_id(args.task_id, "TASK")
    actions = parse_csv(args.action)
    if not actions or any(action not in ACTIONS for action in actions):
        raise ValueError("INVALID_ACTION")
    capabilities = parse_csv(args.capability)
    if not capabilities:
        raise ValueError("CAPABILITY_REQUIRED")
    domains = parse_csv(args.domain)
    if len(domains) != 1:
        raise ValueError("ONE_DOMAIN_REQUIRED")
    domain = domains[0]
    risk = args.risk.upper()
    if risk not in RISK:
        raise ValueError("INVALID_RISK")
    evidence = args.min_evidence.upper()
    if evidence not in EVIDENCE_LEVEL:
        raise ValueError("INVALID_EVIDENCE")
    policy = ensure_policy(root)
    if "delete" in actions and policy.get("allow_remote_delete") is not True:
        raise ValueError("REMOTE_DELETE_DISABLED")
    max_risk = str(policy.get("max_remote_risk", "HIGH")).upper()
    if RISK[risk] > RISK.get(max_risk, 0):
        raise ValueError("RUNTIME_RISK_CEILING_EXCEEDED")
    sender = local_identity(root)
    if not sender:
        raise ValueError("LOCAL_FEDERATION_IDENTITY_REQUIRED")
    target_peer = selected_peer.get("peer") or selected_peer
    target_project = str(target_peer.get("project_id") or "")
    if not target_project:
        raise ValueError("TARGET_PROJECT_ID_MISSING")
    execution_actions = {str(x) for x in (selected_peer.get("execution_actions") or [])}
    if not execution_actions:
        raise ValueError("TARGET_ROUTE_ACTION_SCOPE_MISSING")
    if not set(actions).issubset(execution_actions):
        raise ValueError("TARGET_ROUTE_ACTION_NOT_ALLOWED")
    route_max = str(selected_peer.get("max_risk", risk)).upper()
    peer_max = str(target_peer.get("max_risk", risk)).upper()
    if RISK.get(risk, 99) > min(RISK.get(route_max, 0), RISK.get(peer_max, 0)):
        raise ValueError("TARGET_PEER_RISK_CEILING_EXCEEDED")
    authorized, reason = authorized_agent(root, args.agent_id, actions, domain, risk, evidence)
    if not authorized:
        raise ValueError(reason)
    start = now()
    requested = max(1, int(args.lease_seconds))
    max_lease = min(requested, int(policy.get("max_lease_seconds", 3600) or 3600))
    contract_expires = start + timedelta(seconds=max_lease + int(policy.get("result_grace_seconds", 300) or 300))
    requirements = []
    acceptance = []
    if args.requirements_file:
        data = read_data_file(Path(args.requirements_file).resolve())
        requirements = data.get("requirements") or []
        acceptance = data.get("acceptance_criteria") or []
    else:
        requirements = [{"id": "REQ-REMOTE-001", "statement": args.objective, "priority": "MUST"}]
        acceptance = [{"id": "AC-REMOTE-001", "given": "the delegated task is executed", "when": "the remote agent submits a result", "then": "the declared acceptance criteria are satisfied"}]
    parent_provenance = args.parent_provenance or ""
    contract = {
        "task_id": args.task_id,
        "created_at": iso(start),
        "expires_at": iso(contract_expires),
        "sender": {
            "project_id": str(sender.get("project_id") or local_project_id(root)),
            "agent_id": args.agent_id,
            "key_id": str(sender.get("key_id") or ""),
        },
        "target": {
            "peer_id": str(target_peer.get("peer_id")),
            "project_id": target_project,
            "agent_id": args.target_agent or "",
        },
        "intent": {
            "intent_id": args.intent_id or "",
            "objective": args.objective,
            "parent_task_id": args.parent_task_id or "",
            "parent_provenance_hash": parent_provenance,
        },
        "authority": {
            "actions": actions,
            "domains": [domain],
            "capabilities": capabilities,
            "risk": risk,
            "min_evidence": evidence,
        },
        "scope": {
            "in": args.scope_in,
            "out": args.scope_out,
        },
        "requirements": requirements,
        "acceptance_criteria": acceptance,
        "lease": {
            "requested_seconds": requested,
            "max_seconds": max_lease,
            "renewable": bool(args.renewable),
            "cancellation_allowed": True,
        },
        "execution": {
            "timeout_seconds": max_lease,
            "result_required": True,
            "signed_result_required": bool(policy.get("require_signed_result", True)),
            "evidence_required": bool(policy.get("require_evidence", True)),
        },
        "change_budget": {
            "max_files": int(args.max_files),
            "max_diff_lines": int(args.max_diff_lines),
        },
        "status": "ISSUED",
    }
    return contract


def current_contract_hash(contract: dict[str, Any]) -> str:
    body = dict(contract)
    body.pop("contract_hash", None)
    return sha256_bytes(canon(body))


def cmd_route(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    ensure_policy(root)
    capabilities = parse_csv(args.capability)
    candidates = route_candidates(root, capabilities, args.domain, args.risk.upper())
    result = {"status": "PASS", "requested": {"capabilities": capabilities, "domain": args.domain, "risk": args.risk.upper()}, "candidates": candidates}
    if args.select:
        if not candidates:
            result["status"] = "DENIED"
            result["reason"] = "NO_ROUTE_MATCH"
        else:
            row = candidates[0]
            result["selected"] = {k: row.get(k) for k in ["peer_id", "priority", "capabilities", "domains", "max_risk", "concurrent_limit", "active_leases"]}
    return result


def cmd_delegate(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    ensure_policy(root)
    selected_peer: dict[str, Any] | None = None
    if args.peer_id:
        peer = peer_by_id(root, args.peer_id)
        if not peer:
            raise ValueError("PEER_NOT_TRUSTED")
        route = next((r for r in routes_doc(root).get("peers", []) or [] if isinstance(r, dict) and str(r.get("peer_id")) == args.peer_id), None)
        if not route or str(route.get("status", "ACTIVE")).upper() != "ACTIVE":
            raise ValueError("PEER_ROUTE_NOT_ACTIVE")
        selected_peer = {**route, "peer": peer}
    else:
        routed = route_candidates(root, parse_csv(args.capability), args.domain, args.risk.upper())
        if not routed:
            raise ValueError("NO_ROUTE_MATCH")
        selected_peer = routed[0]
    contract = make_contract(args, root, selected_peer)
    contract_hash = current_contract_hash(contract)
    contract["contract_hash"] = contract_hash
    key_id = str(local_identity(root).get("key_id") or "")
    validate_signing_key_ref(root, args.key_ref, key_id) if args.key_ref else None
    signature = sign(root, contract, key_id, PURPOSE_TASK, key_ref=args.key_ref, private_key=Path(args.private_key).resolve() if args.private_key else None)
    bundle = {"schema_version": SCHEMA, "type": "federated_task_contract", "contract_hash": contract_hash, "contract": contract, "signature": signature}
    out = Path(args.out).resolve() if args.out else contract_path(root, args.task_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_yaml(out, bundle)
    p_hash = provenance(root, {
        "event": "CONTRACT_ISSUED",
        "task_id": args.task_id,
        "contract_hash": contract_hash,
        "intent_id": contract["intent"]["intent_id"],
        "sender_project_id": contract["sender"]["project_id"],
        "target_peer_id": contract["target"]["peer_id"],
        "target_project_id": contract["target"]["project_id"],
        "agent_id": args.agent_id,
    })
    audit(root, {"event": "CONTRACT_ISSUED", "task_id": args.task_id, "contract_hash": contract_hash, "provenance_hash": p_hash})
    return {"status": "PASS", "task_id": args.task_id, "contract_hash": contract_hash, "path": str(out), "target": contract["target"], "provenance_hash": p_hash}


def verify_contract_for_target(root: Path, contract: dict[str, Any], signature: dict[str, Any]) -> tuple[dict[str, Any], str]:
    peer_id = str(contract.get("sender", {}).get("project_id") or "")
    if not peer_id:
        raise ValueError("SENDER_PROJECT_ID_MISSING")
    matching_peer = None
    for peer in peers_doc(root).get("peers", []) or []:
        if isinstance(peer, dict) and str(peer.get("project_id")) == peer_id and str(peer.get("status", "ACTIVE")).upper() == "ACTIVE":
            matching_peer = peer
            break
    if not matching_peer:
        raise ValueError("SENDER_PEER_NOT_TRUSTED")
    # The v2.0 `allowed_actions` field governs federation protocol operations,
    # not task-execution actions. v3.0 action authority is evaluated by the
    # target agent's local trust policy; outgoing routes may add a narrower
    # `execution_actions` ceiling.
    contract_risk = str(contract.get("authority", {}).get("risk", "LOW")).upper()
    peer_risk = str(matching_peer.get("max_risk", "LOW")).upper()
    if RISK.get(contract_risk, 99) > RISK.get(peer_risk, 0):
        raise ValueError("SENDER_DELEGATED_RISK_EXCEEDS_PEER_CEILING")
    public, peer = peer_public_key(root, str(matching_peer.get("peer_id")))
    bound, reason = verify_signer_binding(peer, signature)
    if not bound:
        raise ValueError(reason)
    ok, why = verify_signature(contract, signature, public, PURPOSE_TASK)
    if not ok:
        raise ValueError(why)
    return peer, str(matching_peer.get("peer_id"))


def find_local_agent_id(root: Path, requested: str) -> str:
    if requested:
        return requested
    identity = local_identity(root)
    return str(identity.get("agent_id") or "AGENT-HUMAN")


def lease_record(root: Path, lease_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    doc = leases_doc(root)
    for row in doc.get("leases", []) or []:
        if isinstance(row, dict) and str(row.get("lease_id")) == lease_id:
            return doc, row
    return None


def get_lease(root: Path, lease_id: str) -> dict[str, Any] | None:
    record = lease_record(root, lease_id)
    return record[1] if record else None


def get_task_lease(root: Path, task_id: str) -> dict[str, Any] | None:
    matches = [row for row in leases_doc(root).get("leases", []) or [] if isinstance(row, dict) and str(row.get("task_id")) == task_id]
    matches.sort(key=lambda row: str(row.get("granted_at", "")), reverse=True)
    return matches[0] if matches else None


def task_lease_record(root: Path, task_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    doc = leases_doc(root)
    matches = [row for row in doc.get("leases", []) or [] if isinstance(row, dict) and str(row.get("task_id")) == task_id]
    matches.sort(key=lambda row: str(row.get("granted_at", "")), reverse=True)
    return (doc, matches[0]) if matches else None


def is_cancelled(root: Path, task_id: str, lease_id: str | None = None) -> bool:
    path = cancel_path(root, task_id)
    if not path.exists():
        return False
    bundle = load_yaml(path, {})
    payload = bundle.get("cancellation") or {}
    if lease_id and str(payload.get("lease_id") or "") not in {"", lease_id}:
        return False
    return str(payload.get("status", "CANCEL_REQUESTED")).upper() in {"CANCEL_REQUESTED", "APPLIED", "CANCELLED"}


def cmd_accept(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    ensure_policy(root)
    bundle = load_yaml(Path(args.contract_file).resolve(), {})
    if str(bundle.get("schema_version")) != SCHEMA or str(bundle.get("type")) != "federated_task_contract":
        raise ValueError("TASK_CONTRACT_SCHEMA_MISMATCH")
    contract = bundle.get("contract") or {}
    task_id = str(contract.get("task_id"))
    if not task_id:
        raise ValueError("TASK_ID_MISSING")
    local_pid = local_project_id(root)
    target = contract.get("target") or {}
    if str(target.get("project_id")) != local_pid:
        raise ValueError("CONTRACT_TARGET_PROJECT_MISMATCH")
    peer, peer_id = verify_contract_for_target(root, contract, bundle.get("signature") or {})
    expected_hash = current_contract_hash(contract)
    if expected_hash != str(contract.get("contract_hash")) or expected_hash != str(bundle.get("contract_hash")):
        raise ValueError("TASK_CONTRACT_HASH_MISMATCH")
    policy = runtime_policy(root)
    actions = [str(x) for x in (contract.get("authority", {}).get("actions") or [])]
    if "delete" in actions and policy.get("allow_remote_delete") is not True:
        raise ValueError("REMOTE_DELETE_DISABLED")
    caps = [str(x) for x in (contract.get("authority", {}).get("capabilities") or [])]
    domain = str((contract.get("authority", {}).get("domains") or ["*"])[0])
    risk = str(contract.get("authority", {}).get("risk", "LOW")).upper()
    evidence = str(contract.get("authority", {}).get("min_evidence", "E0")).upper()
    agent_id = find_local_agent_id(root, args.agent_id or str(target.get("agent_id") or ""))
    ok, reason = agent_profile_authorized(root, agent_id, actions, caps, domain, risk, evidence)
    if not ok:
        raise ValueError(reason)
    requested = int(contract.get("lease", {}).get("requested_seconds", 1) or 1)
    max_seconds = int(contract.get("lease", {}).get("max_seconds", requested) or requested)
    lease_seconds = min(max(1, int(args.lease_seconds or requested)), max_seconds, int(policy.get("max_lease_seconds", 3600) or 3600))
    contract_expiry = parse_ts(contract.get("expires_at"))
    if not contract_expiry:
        raise ValueError("CONTRACT_EXPIRY_INVALID")
    lease_expiry = min(now() + timedelta(seconds=lease_seconds), contract_expiry)
    if lease_expiry <= now():
        raise ValueError("CONTRACT_EXPIRED")
    leases = leases_doc(root)
    if any(str(row.get("task_id")) == task_id and str(row.get("status", "")).upper() in {"ACTIVE", "COMPLETED", "RESULT_SUBMITTED", "CANCELLED", "EXPIRED"} for row in leases.get("leases", []) or []):
        raise ValueError("TASK_ALREADY_ACCEPTED")
    lease_id = "LEX-" + now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(4).upper()
    lease = {
        "lease_id": lease_id,
        "task_id": task_id,
        "contract_hash": expected_hash,
        "peer_id": peer_id,
        "sender_project_id": str(contract.get("sender", {}).get("project_id")),
        "owner_agent_id": agent_id,
        "granted_at": iso(),
        "expires_at": iso(lease_expiry),
        "requested_seconds": requested,
        "granted_seconds": lease_seconds,
        "renewable": bool(contract.get("lease", {}).get("renewable", False)),
        "status": "ACTIVE",
        "last_action": "ACCEPTED",
    }
    leases.setdefault("leases", []).append(lease)
    leases["schema_version"] = SCHEMA
    save_yaml(root / LEASES, leases)
    signer_key_id = str(local_identity(root).get("key_id") or "")
    lease_signature = sign(root, lease, signer_key_id, PURPOSE_LEASE, key_ref=signer_key_id)
    lease_bundle = {"schema_version": SCHEMA, "type": "federated_lease_receipt", "lease": lease, "signature": lease_signature}
    save_yaml(lease_receipt_path(root, task_id), lease_bundle)
    contract_out = contract_path(root, task_id)
    save_yaml(contract_out, bundle)
    p_hash = provenance(root, {"event": "LEASE_GRANTED", "task_id": task_id, "contract_hash": expected_hash, "lease_id": lease_id, "agent_id": agent_id, "sender_project_id": lease["sender_project_id"]})
    audit(root, {"event": "LEASE_GRANTED", "task_id": task_id, "lease_id": lease_id, "provenance_hash": p_hash})
    return {"status": "PASS", "task_id": task_id, "lease": lease, "path": str(contract_out), "lease_receipt": str(lease_receipt_path(root, task_id)), "provenance_hash": p_hash}


def cmd_start(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    ensure_policy(root)
    task_id = args.task_id
    validate_id(task_id, "TASK")
    lease_record_item = task_lease_record(root, task_id)
    if not lease_record_item:
        raise ValueError("LEASE_NOT_FOUND")
    doc, lease = lease_record_item
    if str(lease.get("status")) != "ACTIVE":
        raise ValueError(f"LEASE_NOT_ACTIVE:{lease.get('status')}")
    exp = parse_ts(lease.get("expires_at"))
    if not exp or exp <= now():
        lease["status"] = "EXPIRED"
        lease["last_action"] = "START_REJECTED_EXPIRED"
        save_yaml(root / LEASES, doc)
        raise ValueError("LEASE_EXPIRED")
    if is_cancelled(root, task_id, str(lease.get("lease_id"))):
        lease["status"] = "CANCELLED"
        lease["last_action"] = "START_REJECTED_CANCELLED"
        save_yaml(root / LEASES, doc)
        raise ValueError("LEASE_CANCELLED")
    lease["status"] = "RUNNING"
    lease["started_at"] = iso()
    lease["last_action"] = "STARTED"
    save_yaml(root / LEASES, doc)
    p_hash = provenance(root, {"event": "EXECUTION_STARTED", "task_id": task_id, "lease_id": lease["lease_id"], "agent_id": lease.get("owner_agent_id")})
    audit(root, {"event": "EXECUTION_STARTED", "task_id": task_id, "lease_id": lease["lease_id"], "provenance_hash": p_hash})
    return {"status": "PASS", "task_id": task_id, "lease": lease, "provenance_hash": p_hash}


def cmd_renew(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    ensure_policy(root)
    lease_record_item = lease_record(root, args.lease_id)
    if not lease_record_item:
        raise ValueError("LEASE_NOT_FOUND")
    doc, lease = lease_record_item
    if str(lease.get("status")) not in {"ACTIVE", "RUNNING"}:
        raise ValueError(f"LEASE_TERMINAL:{lease.get('status')}")
    agent = args.agent_id or str(lease.get("owner_agent_id"))
    if agent != str(lease.get("owner_agent_id")):
        raise ValueError("LEASE_OWNER_MISMATCH")
    if not bool(lease.get("renewable")):
        raise ValueError("LEASE_NOT_RENEWABLE")
    current_exp = parse_ts(lease.get("expires_at"))
    if not current_exp or current_exp <= now():
        lease["status"] = "EXPIRED"
        lease["last_action"] = "RENEW_REJECTED_EXPIRED"
        save_yaml(root / LEASES, doc)
        raise ValueError("LEASE_EXPIRED")
    seconds = max(1, int(args.seconds))
    policy = runtime_policy(root)
    max_lease = int(policy.get("max_lease_seconds", 3600) or 3600)
    granted = int(lease.get("granted_seconds", 0) or 0)
    new_total = min(granted + seconds, max_lease)
    base = parse_ts(lease.get("granted_at")) or now()
    new_exp = min(base + timedelta(seconds=new_total), parse_ts((contract_from_file(root, str(lease.get("task_id")))[0]).get("expires_at")) or (now() + timedelta(seconds=seconds)))
    if new_exp <= current_exp:
        raise ValueError("LEASE_MAXIMUM_REACHED")
    lease["expires_at"] = iso(new_exp)
    lease["granted_seconds"] = max(granted, int((new_exp - base).total_seconds()))
    lease["last_action"] = "RENEWED"
    lease["renewed_at"] = iso()
    save_yaml(root / LEASES, doc)
    p_hash = provenance(root, {"event": "LEASE_RENEWED", "task_id": lease.get("task_id"), "lease_id": lease["lease_id"], "agent_id": agent, "expires_at": lease["expires_at"]})
    audit(root, {"event": "LEASE_RENEWED", "lease_id": lease["lease_id"], "provenance_hash": p_hash})
    return {"status": "PASS", "lease": lease, "provenance_hash": p_hash}


def cmd_sweep(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    doc = leases_doc(root)
    changed = []
    current = now()
    for row in doc.get("leases", []) or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "UNKNOWN")).upper()
        exp = parse_ts(row.get("expires_at"))
        if status in {"ACTIVE", "RUNNING"} and exp and exp <= current:
            row["status"] = "EXPIRED"
            row["expired_at"] = iso(current)
            row["last_action"] = "SWEEP_EXPIRED"
            changed.append(row.get("lease_id"))
            provenance(root, {"event": "LEASE_EXPIRED", "task_id": row.get("task_id"), "lease_id": row.get("lease_id"), "agent_id": row.get("owner_agent_id")})
    save_yaml(root / LEASES, doc)
    return {"status": "PASS", "expired": changed, "count": len(changed)}


def cmd_cancel(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    ensure_policy(root)
    task_id = args.task_id
    lease = get_task_lease(root, task_id)
    contract, _ = contract_from_file(root, task_id)
    sender_project = str(contract.get("sender", {}).get("project_id"))
    if sender_project != local_project_id(root):
        raise ValueError("ONLY_SENDER_PROJECT_MAY_CANCEL")
    lease_id = str(args.lease_id or (lease.get("lease_id") if lease else ""))
    if not lease_id:
        raise ValueError("LEASE_ID_REQUIRED")
    payload = {
        "cancellation_id": "CAN-" + now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(4).upper(),
        "task_id": task_id,
        "lease_id": lease_id,
        "contract_hash": str(contract.get("contract_hash")),
        "sender_project_id": sender_project,
        "reason": args.reason or "operator_requested",
        "requested_at": iso(),
        "status": "CANCEL_REQUESTED",
    }
    key_id = str(local_identity(root).get("key_id") or "")
    validate_signing_key_ref(root, args.key_ref, key_id) if args.key_ref else None
    signature = sign(root, payload, key_id, PURPOSE_CANCEL, key_ref=args.key_ref, private_key=Path(args.private_key).resolve() if args.private_key else None)
    bundle = {"schema_version": SCHEMA, "type": "federated_task_cancellation", "cancellation": payload, "signature": signature}
    out = Path(args.out).resolve() if args.out else cancel_path(root, task_id)
    save_yaml(out, bundle)
    p_hash = provenance(root, {"event": "CANCELLATION_ISSUED", "task_id": task_id, "lease_id": lease_id, "cancellation_id": payload["cancellation_id"], "contract_hash": payload["contract_hash"]})
    audit(root, {"event": "CANCELLATION_ISSUED", "task_id": task_id, "lease_id": lease_id, "provenance_hash": p_hash})
    return {"status": "PASS", "task_id": task_id, "lease_id": lease_id, "path": str(out), "cancellation_id": payload["cancellation_id"], "provenance_hash": p_hash}


def cmd_apply_cancel(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    ensure_policy(root)
    bundle = load_yaml(Path(args.cancellation_file).resolve(), {})
    if str(bundle.get("schema_version")) != SCHEMA or str(bundle.get("type")) != "federated_task_cancellation":
        raise ValueError("CANCELLATION_SCHEMA_MISMATCH")
    payload = bundle.get("cancellation") or {}
    task_id = str(payload.get("task_id"))
    lease_id = str(payload.get("lease_id"))
    contract, _ = contract_from_file(root, task_id)
    contract_hash = str(contract.get("contract_hash"))
    if str(payload.get("contract_hash")) != contract_hash:
        raise ValueError("CANCELLATION_CONTRACT_HASH_MISMATCH")
    sender_project = str(payload.get("sender_project_id"))
    matching_peer = None
    for peer in peers_doc(root).get("peers", []) or []:
        if isinstance(peer, dict) and str(peer.get("project_id")) == sender_project and str(peer.get("status", "ACTIVE")).upper() == "ACTIVE":
            matching_peer = peer
            break
    if not matching_peer:
        raise ValueError("CANCELLATION_SENDER_NOT_TRUSTED")
    public, peer = peer_public_key(root, str(matching_peer.get("peer_id")))
    bound, reason = verify_signer_binding(peer, bundle.get("signature") or {})
    if not bound:
        raise ValueError(reason)
    ok, why = verify_signature(payload, bundle.get("signature") or {}, public, PURPOSE_CANCEL)
    if not ok:
        raise ValueError(why)
    lease_record_item = lease_record(root, lease_id)
    if not lease_record_item:
        raise ValueError("LEASE_NOT_FOUND")
    doc, lease = lease_record_item
    if str(lease.get("contract_hash")) != contract_hash or str(lease.get("task_id")) != task_id:
        raise ValueError("LEASE_BINDING_MISMATCH")
    current_status = str(lease.get("status", "")).upper()
    if current_status == "CANCELLED":
        return {"status": "PASS", "task_id": task_id, "lease_id": lease_id, "idempotent": True}
    if current_status in {"COMPLETED", "RESULT_SUBMITTED", "EXPIRED"}:
        raise ValueError(f"CANCELLATION_TOO_LATE:{current_status}")
    lease["status"] = "CANCELLED"
    lease["cancelled_at"] = iso()
    lease["cancellation_id"] = str(payload.get("cancellation_id"))
    lease["last_action"] = "CANCEL_APPLIED"
    save_yaml(root / LEASES, doc)
    out = cancel_path(root, task_id)
    save_yaml(out, bundle)
    p_hash = provenance(root, {"event": "CANCELLATION_APPLIED", "task_id": task_id, "lease_id": lease_id, "cancellation_id": payload.get("cancellation_id")})
    audit(root, {"event": "CANCELLATION_APPLIED", "task_id": task_id, "lease_id": lease_id, "provenance_hash": p_hash})
    return {"status": "PASS", "task_id": task_id, "lease_id": lease_id, "provenance_hash": p_hash}


def collect_evidence(root: Path, evidence_items: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(evidence_items, list):
        raise ValueError("EVIDENCE_MUST_BE_LIST")
    result = []
    for index, item in enumerate(evidence_items, 1):
        if isinstance(item, str):
            row: dict[str, Any] = {"path": item}
        elif isinstance(item, dict):
            row = dict(item)
        else:
            raise ValueError(f"EVIDENCE_ITEM_INVALID:{index}")
        path_value = str(row.get("path") or "")
        if not path_value:
            raise ValueError(f"EVIDENCE_PATH_MISSING:{index}")
        path = (root / path_value).resolve() if not Path(path_value).is_absolute() else Path(path_value).resolve()
        if not path.exists() or not path.is_file():
            raise ValueError(f"EVIDENCE_ARTIFACT_NOT_FOUND:{path_value}")
        try:
            display = str(path.relative_to(root))
        except ValueError:
            display = "external:" + path.name
        row["path"] = display
        row["sha256"] = sha256_file(path)
        row.setdefault("status", "VERIFIED")
        row.setdefault("method", "local_hash")
        result.append(row)
    return result


def cmd_complete(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    ensure_policy(root)
    task_id = args.task_id
    contract, _ = contract_from_file(root, task_id)
    lease_record_item = lease_record(root, args.lease_id) if args.lease_id else task_lease_record(root, task_id)
    if not lease_record_item:
        raise ValueError("LEASE_NOT_FOUND")
    doc, lease = lease_record_item
    lease_id = str(lease.get("lease_id"))
    if str(lease.get("status")) not in {"ACTIVE", "RUNNING"}:
        raise ValueError(f"LEASE_TERMINAL:{lease.get('status')}")
    if is_cancelled(root, task_id, str(lease.get("lease_id"))):
        raise ValueError("LEASE_CANCELLED")
    exp = parse_ts(lease.get("expires_at"))
    if not exp or exp <= now():
        lease["status"] = "EXPIRED"
        lease["last_action"] = "COMPLETE_REJECTED_EXPIRED"
        save_yaml(root / LEASES, doc)
        raise ValueError("LEASE_EXPIRED")
    if args.result_file:
        result_input = read_data_file(Path(args.result_file).resolve())
    else:
        result_input = {"status": args.result_status, "summary": args.summary, "changes": []}
    status = str(result_input.get("status", args.result_status)).upper()
    if status not in {"SUCCEEDED", "FAILED", "BLOCKED", "PARTIALLY_SUCCEEDED"}:
        raise ValueError("INVALID_RESULT_STATUS")
    evidence = collect_evidence(root, result_input.get("evidence", []))
    policy = runtime_policy(root)
    if policy.get("require_evidence", True) and not evidence:
        raise ValueError("EVIDENCE_REQUIRED")
    sender = local_identity(root)
    agent_id = str(args.agent_id or lease.get("owner_agent_id") or sender.get("agent_id") or "")
    if agent_id != str(lease.get("owner_agent_id")):
        raise ValueError("LEASE_OWNER_MISMATCH")
    contract_hash = str(contract.get("contract_hash"))
    payload = {
        "result_id": "RES-" + now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(4).upper(),
        "task_id": task_id,
        "lease_id": str(lease.get("lease_id")),
        "contract_hash": contract_hash,
        "sender_project_id": str(sender.get("project_id") or local_project_id(root)),
        "agent_id": agent_id,
        "completed_at": iso(),
        "status": status,
        "summary": str(result_input.get("summary", "")),
        "changes": result_input.get("changes", []) or [],
        "evidence": evidence,
        "verification": {
            "attestation": "REMOTE_AGENT_SIGNED",
            "independent_artifact_check": False,
        },
    }
    key_id = str(sender.get("key_id") or "")
    validate_signing_key_ref(root, args.key_ref, key_id) if args.key_ref else None
    signature = sign(root, payload, key_id, PURPOSE_RESULT, key_ref=args.key_ref, private_key=Path(args.private_key).resolve() if args.private_key else None)
    bundle = {"schema_version": SCHEMA, "type": "federated_task_result", "result": payload, "signature": signature}
    out = Path(args.out).resolve() if args.out else result_path(root, task_id)
    save_yaml(out, bundle)
    lease["status"] = "COMPLETED" if status == "SUCCEEDED" else "RESULT_SUBMITTED"
    lease["completed_at"] = payload["completed_at"]
    lease["result_id"] = payload["result_id"]
    lease["last_action"] = "RESULT_SUBMITTED"
    save_yaml(root / LEASES, doc)
    for item in evidence:
        evid_id = "EVD-" + now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(3).upper()
        receipt = {
            "schema_version": SCHEMA,
            "id": evid_id,
            "type": "remote_execution_evidence",
            "status": item.get("status", "VERIFIED"),
            "task_id": task_id,
            "lease_id": lease["lease_id"],
            "contract_hash": contract_hash,
            "remote_result_id": payload["result_id"],
            "artifact": item,
            "verified_by": agent_id,
            "verified_at": payload["completed_at"],
            "verification_level": "REMOTE_ATTESTED",
        }
        save_yaml(root / EVIDENCE_DIR / f"{evid_id}.yaml", receipt)
    p_hash = provenance(root, {"event": "RESULT_SUBMITTED", "task_id": task_id, "lease_id": lease["lease_id"], "result_id": payload["result_id"], "contract_hash": contract_hash, "agent_id": agent_id})
    audit(root, {"event": "RESULT_SUBMITTED", "task_id": task_id, "result_id": payload["result_id"], "provenance_hash": p_hash})
    return {"status": "PASS", "task_id": task_id, "result_id": payload["result_id"], "path": str(out), "provenance_hash": p_hash}


def verify_evidence_artifacts(root: Path, evidence: list[Any]) -> tuple[bool, list[dict[str, Any]]]:
    all_ok = True
    rows = []
    for item in evidence:
        row = dict(item) if isinstance(item, dict) else {"path": str(item)}
        path_value = str(row.get("path", ""))
        if path_value.startswith("external:"):
            row["artifact_status"] = "NOT_LOCAL"
            rows.append(row)
            continue
        path = (root / path_value).resolve()
        if not path.exists() or not path.is_file():
            row["artifact_status"] = "NOT_LOCAL"
            rows.append(row)
            all_ok = False
            continue
        actual = sha256_file(path)
        expected = str(row.get("sha256", ""))
        row["artifact_status"] = "VERIFIED" if actual == expected else "HASH_MISMATCH"
        row["actual_sha256"] = actual
        if actual != expected:
            all_ok = False
        rows.append(row)
    return all_ok, rows


def cmd_verify_result(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    ensure_policy(root)
    bundle = load_yaml(Path(args.result_file).resolve(), {})
    if str(bundle.get("schema_version")) != SCHEMA or str(bundle.get("type")) != "federated_task_result":
        raise ValueError("RESULT_SCHEMA_MISMATCH")
    result = bundle.get("result") or {}
    task_id = str(result.get("task_id"))
    contract, _ = contract_from_file(root, task_id)
    if str(result.get("contract_hash")) != str(contract.get("contract_hash")):
        raise ValueError("RESULT_CONTRACT_HASH_MISMATCH")
    lease = get_lease(root, str(result.get("lease_id")))
    peer_project = str(contract.get("target", {}).get("project_id"))
    # On the origin project the result signer is the target peer.
    peer = peer_by_id(root, str(contract.get("target", {}).get("peer_id")))
    if not peer:
        raise ValueError("TARGET_PEER_NOT_TRUSTED")
    if lease is None:
        receipt = load_yaml(lease_receipt_path(root, task_id), {})
        lease = receipt.get("lease") or None
        if lease:
            receipt_sig = receipt.get("signature") or {}
            public_lease, peer_lease = peer_public_key(root, str(peer.get("peer_id")))
            bound_lease, reason_lease = verify_signer_binding(peer_lease, receipt_sig)
            if not bound_lease:
                raise ValueError(reason_lease)
            ok_lease, why_lease = verify_signature(lease, receipt_sig, public_lease, PURPOSE_LEASE)
            if not ok_lease:
                raise ValueError(why_lease)
    if not lease:
        raise ValueError("LEASE_RECEIPT_NOT_FOUND")
    if str(lease.get("contract_hash")) != str(contract.get("contract_hash")):
        raise ValueError("RESULT_LEASE_CONTRACT_MISMATCH")
    if str(lease.get("task_id")) != task_id or str(lease.get("lease_id")) != str(result.get("lease_id")):
        raise ValueError("RESULT_LEASE_BINDING_MISMATCH")
    contract_expiry = parse_ts(contract.get("expires_at"))
    lease_expiry = parse_ts(lease.get("expires_at"))
    max_seconds = int(contract.get("lease", {}).get("max_seconds", 0) or 0)
    if not lease_expiry or not contract_expiry or lease_expiry > contract_expiry:
        raise ValueError("LEASE_EXPIRY_OUTSIDE_CONTRACT")
    if int(lease.get("granted_seconds", 0) or 0) > max_seconds:
        raise ValueError("LEASE_GRANT_EXCEEDS_CONTRACT")
    public, peer_doc_item = peer_public_key(root, str(peer.get("peer_id")))
    bound, reason = verify_signer_binding(peer_doc_item, bundle.get("signature") or {})
    if not bound:
        raise ValueError(reason)
    ok, why = verify_signature(result, bundle.get("signature") or {}, public, PURPOSE_RESULT)
    if not ok:
        raise ValueError(why)
    artifact_ok, artifact_rows = verify_evidence_artifacts(root, result.get("evidence", []) or [])
    complete = all([str(result.get("status")) in {"SUCCEEDED", "FAILED", "BLOCKED", "PARTIALLY_SUCCEEDED"}, bool(result.get("result_id")), bool(result.get("lease_id"))])
    attested = True
    independently_verified = artifact_ok and bool(result.get("evidence"))
    p_hash = provenance(root, {"event": "RESULT_VERIFIED", "task_id": task_id, "lease_id": result.get("lease_id"), "result_id": result.get("result_id"), "contract_hash": result.get("contract_hash"), "artifact_verification": "PASS" if independently_verified else "METADATA_ONLY"})
    audit(root, {"event": "RESULT_VERIFIED", "task_id": task_id, "result_id": result.get("result_id"), "provenance_hash": p_hash})
    return {
        "status": "VERIFIED" if complete and attested else "FAILED",
        "task_id": task_id,
        "result_id": result.get("result_id"),
        "contract_hash": result.get("contract_hash"),
        "remote_project": peer_project,
        "signature_verified": True,
        "evidence_attested": bool(result.get("evidence")),
        "artifact_verification": "PASS" if independently_verified else "METADATA_ONLY",
        "artifact_results": artifact_rows,
        "provenance_hash": p_hash,
    }


def cmd_deliver(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    verified = cmd_verify_result(argparse.Namespace(path=str(root), result_file=args.result_file))
    if verified.get("status") != "VERIFIED":
        raise ValueError("REMOTE_RESULT_NOT_VERIFIED")
    result_bundle = load_yaml(Path(args.result_file).resolve(), {})
    result = result_bundle.get("result") or {}
    evidence_id = "EVD-" + now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(3).upper()
    receipt = {
        "schema_version": SCHEMA,
        "id": evidence_id,
        "type": "federated_delivery_evidence",
        "status": "VERIFIED",
        "task_id": result.get("task_id"),
        "lease_id": result.get("lease_id"),
        "contract_hash": result.get("contract_hash"),
        "result_id": result.get("result_id"),
        "intent_id": (load_yaml(contract_path(root, str(result.get("task_id"))), {}).get("contract") or {}).get("intent", {}).get("intent_id", ""),
        "verified_at": iso(),
        "signature_verified": True,
        "artifact_verification": verified.get("artifact_verification"),
        "evidence_attested": verified.get("evidence_attested"),
        "provenance_hash": verified.get("provenance_hash"),
        "remote_result_status": result.get("status"),
    }
    out = root / EVIDENCE_DIR / f"{evidence_id}.yaml"
    save_yaml(out, receipt)
    p_hash = provenance(root, {"event": "DELIVERY_RECORDED", "task_id": result.get("task_id"), "result_id": result.get("result_id"), "evidence_id": evidence_id})
    audit(root, {"event": "DELIVERY_RECORDED", "task_id": result.get("task_id"), "evidence_id": evidence_id, "provenance_hash": p_hash})
    return {"status": "PASS", "evidence_id": evidence_id, "path": str(out), "provenance_hash": p_hash}


def validate_chain(path: Path, label: str) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return errors
    previous = "GENESIS"
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"{label}_MALFORMED:{line_no}")
            continue
        if row.get("prev_hash") != previous:
            errors.append(f"{label}_CHAIN_BROKEN:{line_no}")
        claimed = row.get("entry_hash")
        base = dict(row)
        base.pop("entry_hash", None)
        expected = sha256_bytes(canon(base))
        if claimed != expected:
            errors.append(f"{label}_HASH_MISMATCH:{line_no}")
        previous = str(claimed or "BROKEN")
    return errors


def cmd_check(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    errors: list[str] = []
    required = [POLICY, ROUTES, LEASES, TASK_DIR, LEASE_RECEIPT_DIR, CANCEL_DIR, RESULT_DIR, EVIDENCE_DIR, PROVENANCE, AUDIT]
    for rel in required:
        if not (root / rel).exists():
            errors.append(f"MISSING:{rel}")
    policy = runtime_policy(root)
    if policy:
        if policy.get("default_deny") is not True:
            errors.append("POLICY_DEFAULT_DENY_REQUIRED")
        if policy.get("require_signed_contract") is not True:
            errors.append("POLICY_SIGNED_CONTRACT_REQUIRED")
        if policy.get("require_signed_result") is not True:
            errors.append("POLICY_SIGNED_RESULT_REQUIRED")
        if policy.get("require_evidence") is not True:
            errors.append("POLICY_EVIDENCE_REQUIRED")
        if policy.get("allow_silent_scope_expansion") is not False:
            errors.append("POLICY_SILENT_SCOPE_EXPANSION_FORBIDDEN")
        if policy.get("authority_escalation") is not False:
            errors.append("POLICY_AUTHORITY_ESCALATION_FORBIDDEN")
        if policy.get("private_key_storage") is not False:
            errors.append("POLICY_PRIVATE_KEY_STORAGE_FORBIDDEN")
    routes = routes_doc(root)
    if routes and routes.get("default_deny") is not True:
        errors.append("ROUTES_DEFAULT_DENY_REQUIRED")
    leases = leases_doc(root)
    for row in leases.get("leases", []) or []:
        if not isinstance(row, dict):
            errors.append("LEASE_ENTRY_INVALID")
            continue
        status = str(row.get("status", ""))
        if status in {"CANCELLED", "EXPIRED", "COMPLETED"} and str(row.get("last_action", "")) == "ACCEPTED":
            errors.append(f"LEASE_TERMINAL_WITH_ACCEPTED_ACTION:{row.get('lease_id')}")
        if status in {"CANCELLED", "EXPIRED"} and row.get("renewable") and row.get("renewed_at"):
            errors.append(f"LEASE_TERMINAL_WAS_RENEWED:{row.get('lease_id')}")
    errors.extend(validate_chain(root / PROVENANCE, "PROVENANCE"))
    errors.extend(validate_chain(root / AUDIT, "AUDIT"))
    for path in (root / TASK_DIR).glob("*.yaml") if (root / TASK_DIR).exists() else []:
        try:
            payload, signature = contract_from_file(root, path.stem)
            if str(signature.get("purpose")) != PURPOSE_TASK:
                errors.append(f"TASK_PURPOSE_MISMATCH:{path.name}")
            if current_contract_hash(payload) != str(payload.get("contract_hash")):
                errors.append(f"TASK_HASH_MISMATCH:{path.name}")
        except Exception as exc:
            errors.append(f"TASK_INVALID:{path.name}:{exc}")
    status = "PASS" if not errors else "FAIL"
    return {"status": status, "errors": sorted(set(errors)), "schema_version": SCHEMA, "runtime": {"policy": str(POLICY), "routes": str(ROUTES), "leases": str(LEASES)}}


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.path).resolve()
    return {
        "status": "PASS",
        "schema_version": SCHEMA,
        "policy": runtime_policy(root),
        "routes": routes_doc(root),
        "active_leases": active_leases(root),
        "task_contracts": sorted(p.name for p in (root / TASK_DIR).glob("*.yaml")) if (root / TASK_DIR).exists() else [],
        "lease_receipts": sorted(p.name for p in (root / LEASE_RECEIPT_DIR).glob("*.yaml")) if (root / LEASE_RECEIPT_DIR).exists() else [],
        "results": sorted(p.name for p in (root / RESULT_DIR).glob("*.yaml")) if (root / RESULT_DIR).exists() else [],
        "cancellations": sorted(p.name for p in (root / CANCEL_DIR).glob("*.yaml")) if (root / CANCEL_DIR).exists() else [],
        "evidence": sorted(p.name for p in (root / EVIDENCE_DIR).glob("*.yaml")) if (root / EVIDENCE_DIR).exists() else [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="UAAF v3.0 Federated Agent Runtime")
    sub = parser.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("status")
    q.add_argument("path", nargs="?", default=".")

    q = sub.add_parser("check")
    q.add_argument("path", nargs="?", default=".")

    q = sub.add_parser("route")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--capability", action="append", default=[])
    q.add_argument("--domain", default="*")
    q.add_argument("--risk", default="LOW")
    q.add_argument("--select", action="store_true")

    q = sub.add_parser("delegate")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--task-id", required=True)
    q.add_argument("--agent-id", required=True)
    q.add_argument("--intent-id", default="")
    q.add_argument("--parent-task-id", default="")
    q.add_argument("--parent-provenance", default="")
    q.add_argument("--objective", required=True)
    q.add_argument("--scope-in", default="")
    q.add_argument("--scope-out", default="")
    q.add_argument("--action", action="append", default=[])
    q.add_argument("--capability", action="append", default=[])
    q.add_argument("--domain", required=True)
    q.add_argument("--risk", default="LOW")
    q.add_argument("--min-evidence", default="E0")
    q.add_argument("--lease-seconds", type=int, default=900)
    q.add_argument("--renewable", action="store_true")
    q.add_argument("--max-files", type=int, default=100)
    q.add_argument("--max-diff-lines", type=int, default=1000)
    q.add_argument("--requirements-file")
    q.add_argument("--peer-id")
    q.add_argument("--target-agent", default="")
    q.add_argument("--key-ref")
    q.add_argument("--private-key")
    q.add_argument("--out")

    q = sub.add_parser("accept")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--contract-file", required=True)
    q.add_argument("--agent-id", default="")
    q.add_argument("--lease-seconds", type=int, default=0)

    q = sub.add_parser("start")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--task-id", required=True)

    q = sub.add_parser("renew")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--lease-id", required=True)
    q.add_argument("--seconds", type=int, required=True)
    q.add_argument("--agent-id", default="")

    q = sub.add_parser("sweep")
    q.add_argument("path", nargs="?", default=".")

    q = sub.add_parser("cancel")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--task-id", required=True)
    q.add_argument("--lease-id")
    q.add_argument("--reason", default="")
    q.add_argument("--key-ref")
    q.add_argument("--private-key")
    q.add_argument("--out")

    q = sub.add_parser("apply-cancel")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--cancellation-file", required=True)

    q = sub.add_parser("complete")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--task-id", required=True)
    q.add_argument("--lease-id")
    q.add_argument("--agent-id", default="")
    q.add_argument("--result-status", default="SUCCEEDED")
    q.add_argument("--summary", default="")
    q.add_argument("--result-file")
    q.add_argument("--key-ref")
    q.add_argument("--private-key")
    q.add_argument("--out")

    q = sub.add_parser("verify-result")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--result-file", required=True)

    q = sub.add_parser("deliver")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--result-file", required=True)

    q = sub.add_parser("help")
    args = parser.parse_args()
    root = Path(getattr(args, "path", ".")).resolve()
    try:
        if args.cmd == "status": result = cmd_status(args)
        elif args.cmd == "check": result = cmd_check(args)
        elif args.cmd == "route": result = cmd_route(args)
        elif args.cmd == "delegate": result = cmd_delegate(args)
        elif args.cmd == "accept": result = cmd_accept(args)
        elif args.cmd == "start": result = cmd_start(args)
        elif args.cmd == "renew": result = cmd_renew(args)
        elif args.cmd == "sweep": result = cmd_sweep(args)
        elif args.cmd == "cancel": result = cmd_cancel(args)
        elif args.cmd == "apply-cancel": result = cmd_apply_cancel(args)
        elif args.cmd == "complete": result = cmd_complete(args)
        elif args.cmd == "verify-result": result = cmd_verify_result(args)
        elif args.cmd == "deliver": result = cmd_deliver(args)
        else:
            result = {"status": "PASS", "commands": ["status", "check", "route", "delegate", "accept", "start", "renew", "sweep", "cancel", "apply-cancel", "complete", "verify-result", "deliver"]}
    except Exception as exc:
        result = {"status": "DENIED", "reason": str(exc)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result.get("status") in {"PASS", "VERIFIED"} else 1)


if __name__ == "__main__":
    main()
