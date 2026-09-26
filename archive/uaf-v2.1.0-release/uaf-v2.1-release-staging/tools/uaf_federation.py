#!/usr/bin/env python3
"""UAAF v2.0 Distributed Agent Federation.

Transport-agnostic federation primitives for cross-project identity, signed
handoffs, replay protection, federated policy, and vector-clock state merge.
Private keys remain outside projects. The filesystem is the reference transport.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
SCHEMA = "2.0"
FED_DIR = Path(".ai/federation")
IDENTITY = FED_DIR / "IDENTITY.yaml"
IDENTITY_SIG = FED_DIR / "IDENTITY.yaml.sig"
PEERS = FED_DIR / "PEERS.yaml"
POLICY = FED_DIR / "FEDERATION-POLICY.yaml"
POLICY_SIG = FED_DIR / "FEDERATION-POLICY.yaml.sig"
REPLAY = FED_DIR / "REPLAY.yaml"
AUDIT = FED_DIR / "AUDIT.jsonl"
STATE_DIR = FED_DIR / "state"
VECTOR = STATE_DIR / "VECTOR.yaml"
REGISTERS = STATE_DIR / "REGISTERS.yaml"
CONFLICTS = STATE_DIR / "CONFLICTS.yaml"
HANDOFF_DIR = FED_DIR / "HANDOFFS"
BUNDLE_DIR = FED_DIR / "BUNDLES"
RISK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
ALLOWED_ACTIONS = {"handoff", "state-pull", "state-push", "capability-sync", "policy-sync"}
MAX_CLOCK_SKEW_SECONDS = 300


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")


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
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else dict(default or {})
    except Exception:
        return dict(default or {})


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def public_raw_from_pem(path: Path) -> bytes:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("public key is not Ed25519")
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def private_from_pem(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private key is not Ed25519")
    return key


def local_identity(root: Path) -> dict[str, Any]:
    return load_yaml(root / IDENTITY, {"schema_version": SCHEMA, "identity": {}}).get("identity") or {}


def peer_doc(root: Path) -> dict[str, Any]:
    return load_yaml(root / PEERS, {"schema_version": SCHEMA, "peers": []})


def policy_doc(root: Path) -> dict[str, Any]:
    return load_yaml(root / POLICY, {"schema_version": SCHEMA, "default_deny": True, "require_signed_handoff": True, "require_signed_state": True, "peers": []})


def local_key_entry(root: Path, key_id: str) -> dict[str, Any] | None:
    data = load_yaml(root / ".ai/trust/KEYS.yaml", {})
    for row in data.get("keys", []) or []:
        if isinstance(row, dict) and str(row.get("key_id")) == key_id:
            return row
    return None


def active_key_match(root: Path, key_id: str, private: Ed25519PrivateKey) -> None:
    entry = local_key_entry(root, key_id)
    if entry:
        raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if fingerprint(raw) != str(entry.get("fingerprint_sha256", "")):
            raise ValueError("private key does not match registered key")
        if str(entry.get("status", "ACTIVE")).upper() != "ACTIVE":
            raise ValueError("signing key is not active")


def sign_payload(payload: dict[str, Any], private_path: Path, root: Path, key_id: str, purpose: str) -> dict[str, Any]:
    private = private_from_pem(private_path)
    active_key_match(root, key_id, private)
    body = canonical_bytes(payload)
    sig = private.sign(body)
    return {
        "schema_version": SCHEMA,
        "algorithm": "Ed25519",
        "key_id": key_id,
        "purpose": purpose,
        "payload_sha256": fingerprint(body),
        "signature_b64": base64.b64encode(sig).decode("ascii"),
    }


def verify_payload(payload: dict[str, Any], envelope: dict[str, Any], public_raw: bytes, expected_purpose: str) -> tuple[bool, str]:
    if envelope.get("schema_version") != SCHEMA:
        return False, "SCHEMA_MISMATCH"
    if envelope.get("algorithm") != "Ed25519":
        return False, "UNSUPPORTED_ALGORITHM"
    if envelope.get("purpose") != expected_purpose:
        return False, "PURPOSE_MISMATCH"
    body = canonical_bytes(payload)
    if fingerprint(body) != str(envelope.get("payload_sha256", "")):
        return False, "PAYLOAD_HASH_MISMATCH"
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(
            base64.b64decode(str(envelope.get("signature_b64", "")), validate=True), body
        )
    except (ValueError, InvalidSignature, TypeError):
        return False, "SIGNATURE_INVALID"
    return True, "OK"


def audit(root: Path, event: dict[str, Any]) -> None:
    path = root / AUDIT
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = "GENESIS"
    if path.exists():
        lines = [x for x in path.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
        if lines:
            try:
                prior = str(json.loads(lines[-1]).get("entry_hash", prior))
            except Exception:
                prior = "BROKEN"
    row = {"schema_version": SCHEMA, "timestamp": iso_now(), "prev_hash": prior, **event}
    row["entry_hash"] = fingerprint(canonical_bytes(row))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def identity_init(root: Path, project_id: str, agent_id: str, machine_id: str, key_id: str, public_key: Path, root_private: Path, root_key_id: str) -> dict[str, Any]:
    raw = public_raw_from_pem(public_key)
    ident = {
        "schema_version": SCHEMA,
        "identity": {
            "project_id": project_id,
            "agent_id": agent_id,
            "machine_id": machine_id,
            "key_id": key_id,
            "algorithm": "Ed25519",
            "public_key": base64.b64encode(raw).decode("ascii"),
            "fingerprint_sha256": fingerprint(raw),
            "created_at": iso_now(),
            "status": "ACTIVE",
        },
    }
    dump_yaml(root / IDENTITY, ident)
    env = sign_payload(ident, root_private, root, root_key_id, "federation-identity")
    (root / IDENTITY_SIG).write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
    peers = peer_doc(root)
    peers.setdefault("peers", [])
    dump_yaml(root / PEERS, peers)
    return {"status": "PASS", "fingerprint_sha256": fingerprint(raw), "identity": ident["identity"]}


def identity_verify(identity_path: Path, sig_path: Path, root_public_key: Path) -> dict[str, Any]:
    ident = load_yaml(identity_path, {})
    env = json.loads(sig_path.read_text(encoding="utf-8"))
    root_raw = public_raw_from_pem(root_public_key)
    ok, reason = verify_payload(ident, env, root_raw, "federation-identity")
    if not ok:
        return {"status": "FAIL", "reason": reason}
    inner = ident.get("identity") or {}
    raw = base64.b64decode(str(inner.get("public_key", "")), validate=True)
    if len(raw) != 32 or fingerprint(raw) != str(inner.get("fingerprint_sha256", "")):
        return {"status": "FAIL", "reason": "IDENTITY_FINGERPRINT_MISMATCH"}
    return {"status": "PASS", "reason": "IDENTITY_VALID", "identity": inner}


def peer_import(root: Path, peer_id: str, identity: Path, identity_sig: Path, root_public_key: Path, allowed_actions: list[str], max_risk: str, require_signed_handoff: bool = True, require_signed_state: bool = True) -> dict[str, Any]:
    verified = identity_verify(identity, identity_sig, root_public_key)
    if verified.get("status") != "PASS":
        return verified
    inner = verified["identity"]
    if max_risk.upper() not in RISK:
        raise ValueError("invalid max_risk")
    actions = sorted({a for a in allowed_actions if a in ALLOWED_ACTIONS})
    target = root / FED_DIR / "peers" / peer_id
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(identity, target / "IDENTITY.yaml")
    shutil.copy2(identity_sig, target / "IDENTITY.yaml.sig")
    shutil.copy2(root_public_key, target / "ROOT.pub.pem")
    peer = {
        "peer_id": peer_id,
        "project_id": inner.get("project_id"),
        "agent_id": inner.get("agent_id"),
        "machine_id": inner.get("machine_id"),
        "key_id": inner.get("key_id"),
        "identity_public_key": inner.get("public_key"),
        "identity_fingerprint": inner.get("fingerprint_sha256"),
        "identity_signature": str((target / "IDENTITY.yaml.sig").relative_to(root)),
        "root_public_key": str((target / "ROOT.pub.pem").relative_to(root)),
        "root_fingerprint": fingerprint(public_raw_from_pem(root_public_key)),
        "allowed_actions": actions,
        "max_risk": max_risk.upper(),
        "require_signed_handoff": bool(require_signed_handoff),
        "require_signed_state": bool(require_signed_state),
        "status": "ACTIVE",
    }
    doc = peer_doc(root)
    items = [x for x in doc.get("peers", []) or [] if str(x.get("peer_id")) != peer_id]
    items.append(peer)
    doc["peers"] = sorted(items, key=lambda x: str(x.get("peer_id")))
    dump_yaml(root / PEERS, doc)
    audit(root, {"action": "PEER_IMPORT", "peer_id": peer_id})
    return {"status": "PASS", "peer": peer}


def peer_lookup(root: Path, project_id: str | None = None, peer_id: str | None = None) -> dict[str, Any] | None:
    for peer in peer_doc(root).get("peers", []) or []:
        if not isinstance(peer, dict) or str(peer.get("status", "ACTIVE")).upper() != "ACTIVE":
            continue
        if peer_id and str(peer.get("peer_id")) == peer_id:
            return peer
        if project_id and str(peer.get("project_id")) == project_id:
            return peer
    return None


def policy_allows(root: Path, project_id: str, action: str, risk: str, signed_required_default: bool) -> tuple[bool, str, dict[str, Any] | None]:
    peer = peer_lookup(root, project_id=project_id)
    if not peer:
        return False, "PEER_NOT_TRUSTED", None
    if action not in set(peer.get("allowed_actions", []) or []):
        return False, "ACTION_NOT_ALLOWED", peer
    if RISK.get(risk.upper(), 99) > RISK.get(str(peer.get("max_risk", "LOW")).upper(), 0):
        return False, "RISK_EXCEEDS_PEER_CEILING", peer
    policy = policy_doc(root)
    if action == "handoff" and bool(peer.get("require_signed_handoff", signed_required_default)) and not bool(policy.get("require_signed_handoff", True)):
        return False, "SIGNED_HANDOFF_POLICY_DISABLED", peer
    if action in {"state-pull", "state-push"} and bool(peer.get("require_signed_state", signed_required_default)) and not bool(policy.get("require_signed_state", True)):
        return False, "SIGNED_STATE_POLICY_DISABLED", peer
    return True, "OK", peer


def replay_load(root: Path) -> dict[str, Any]:
    return load_yaml(root / REPLAY, {"schema_version": SCHEMA, "seen": []})


def replay_check_and_consume(root: Path, sender: str, envelope_id: str, nonce: str, expires_at: str, consume: bool) -> tuple[bool, str]:
    doc = replay_load(root)
    current = utc_now()
    kept = []
    for row in doc.get("seen", []) or []:
        exp = parse_ts(row.get("expires_at"))
        if exp is None or exp > current:
            kept.append(row)
    for row in kept:
        if row.get("envelope_id") == envelope_id or (row.get("sender") == sender and row.get("nonce") == nonce):
            return False, "REPLAY_DETECTED"
    exp = parse_ts(expires_at)
    if exp is None or exp <= current:
        return False, "ENVELOPE_EXPIRED"
    if consume:
        kept.append({"sender": sender, "envelope_id": envelope_id, "nonce": nonce, "expires_at": expires_at, "consumed_at": iso_now()})
        doc["seen"] = kept[-5000:]
        dump_yaml(root / REPLAY, doc)
    return True, "OK"


def build_envelope(action: str, payload: dict[str, Any], private: Path, root: Path, key_id: str, audience_project: str, audience_agent: str | None, ttl: int, sequence: int | None) -> dict[str, Any]:
    ident = local_identity(root)
    issued = utc_now()
    expires = issued + timedelta(seconds=max(1, min(ttl, 86400)))
    body = {
        "schema_version": SCHEMA,
        "type": "UAAF_FEDERATION_ENVELOPE",
        "action": action,
        "envelope_id": f"ENV-{issued.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(6)}",
        "nonce": secrets.token_urlsafe(18),
        "sequence": sequence,
        "issued_at": issued.isoformat().replace("+00:00", "Z"),
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
        "sender": {
            "project_id": ident.get("project_id"),
            "agent_id": ident.get("agent_id"),
            "machine_id": ident.get("machine_id"),
            "key_id": ident.get("key_id"),
        },
        "audience": {"project_id": audience_project, "agent_id": audience_agent},
        "payload": payload,
    }
    signer = sign_payload(body, private, root, key_id, f"federation-{action}")
    return {"envelope": body, "signature": signer}


def save_signed(path: Path, bundle: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(bundle, sort_keys=False), encoding="utf-8")


def verify_remote_bundle(root: Path, bundle: dict[str, Any], action: str, consume_replay: bool = True) -> dict[str, Any]:
    envelope = bundle.get("envelope") or {}
    signature = bundle.get("signature") or {}
    sender = envelope.get("sender") or {}
    audience = envelope.get("audience") or {}
    if audience.get("project_id") != local_identity(root).get("project_id"):
        return {"status": "FAIL", "reason": "AUDIENCE_MISMATCH"}
    if envelope.get("action") != action:
        return {"status": "FAIL", "reason": "ACTION_MISMATCH"}
    now = utc_now()
    issued = parse_ts(envelope.get("issued_at"))
    expires = parse_ts(envelope.get("expires_at"))
    if issued is None or expires is None:
        return {"status": "FAIL", "reason": "INVALID_TIME_WINDOW"}
    if issued - now > timedelta(seconds=MAX_CLOCK_SKEW_SECONDS) or expires <= now:
        return {"status": "FAIL", "reason": "ENVELOPE_TIME_INVALID"}
    peer = peer_lookup(root, project_id=str(sender.get("project_id")))
    if not peer:
        return {"status": "FAIL", "reason": "PEER_NOT_TRUSTED"}
    if str(signature.get("key_id")) != str(peer.get("key_id")):
        return {"status": "FAIL", "reason": "SIGNER_KEY_MISMATCH"}
    if action not in set(peer.get("allowed_actions", []) or []):
        return {"status": "FAIL", "reason": "ACTION_NOT_ALLOWED"}
    risk = str((envelope.get("payload") or {}).get("risk", "LOW")).upper()
    if RISK.get(risk, 99) > RISK.get(str(peer.get("max_risk", "LOW")).upper(), 0):
        return {"status": "FAIL", "reason": "RISK_EXCEEDS_PEER_CEILING"}
    # Re-verify the pinned peer identity chain on every remote envelope so a
    # locally modified peer record cannot silently change the trust boundary.
    peer_identity_sig = root / str(peer.get("identity_signature", ""))
    peer_identity_path = peer_identity_sig.with_name("IDENTITY.yaml")
    peer_root_pub = root / str(peer.get("root_public_key", ""))
    identity_check = identity_verify(peer_identity_path, peer_identity_sig, peer_root_pub)
    if identity_check.get("status") != "PASS":
        return {"status": "FAIL", "reason": "PEER_IDENTITY_INVALID", "detail": identity_check.get("reason")}
    if str(identity_check.get("identity", {}).get("project_id")) != str(sender.get("project_id")) or str(identity_check.get("identity", {}).get("key_id")) != str(sender.get("key_id")):
        return {"status": "FAIL", "reason": "PEER_IDENTITY_MISMATCH"}
    raw = base64.b64decode(str(peer.get("identity_public_key", "")), validate=True)
    if fingerprint(raw) != str(peer.get("identity_fingerprint", "")):
        return {"status": "FAIL", "reason": "PEER_KEY_FINGERPRINT_MISMATCH"}
    ok, reason = verify_payload(envelope, signature, raw, f"federation-{action}")
    if not ok:
        return {"status": "FAIL", "reason": reason}
    replay_ok, replay_reason = replay_check_and_consume(root, str(sender.get("project_id")), str(envelope.get("envelope_id")), str(envelope.get("nonce")), str(envelope.get("expires_at")), consume_replay)
    if not replay_ok:
        return {"status": "FAIL", "reason": replay_reason}
    audit(root, {"action": "FEDERATION_VERIFY", "envelope_id": envelope.get("envelope_id"), "sender_project": sender.get("project_id"), "federation_action": action})
    return {"status": "PASS", "reason": "ENVELOPE_VALID", "payload": envelope.get("payload"), "sender": sender, "envelope_id": envelope.get("envelope_id")}


def handoff_sign(root: Path, handoff_file: Path, private: Path, key_id: str, audience_project: str, audience_agent: str | None, ttl: int, sequence: int | None, risk: str) -> Path:
    payload = {"handoff": handoff_file.read_text(encoding="utf-8"), "risk": risk.upper()}
    bundle = build_envelope("handoff", payload, private, root, key_id, audience_project, audience_agent, ttl, sequence)
    out = root / HANDOFF_DIR / f"{bundle['envelope']['envelope_id']}.yaml"
    save_signed(out, bundle)
    audit(root, {"action": "HANDOFF_SIGN", "envelope_id": bundle["envelope"]["envelope_id"], "audience": audience_project})
    return out


def vector_compare(a: dict[str, int], b: dict[str, int]) -> int:
    """Return 1 if a dominates b, -1 if b dominates a, 0 if equal, 2 if concurrent."""
    keys = set(a) | set(b)
    ge_a = all(int(a.get(k, 0)) >= int(b.get(k, 0)) for k in keys)
    ge_b = all(int(b.get(k, 0)) >= int(a.get(k, 0)) for k in keys)
    if ge_a and ge_b:
        return 0
    if ge_a:
        return 1
    if ge_b:
        return -1
    return 2


def state_docs(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_yaml(root / VECTOR, {"schema_version": SCHEMA, "clock": {}}),
        load_yaml(root / REGISTERS, {"schema_version": SCHEMA, "entries": {}}),
        load_yaml(root / CONFLICTS, {"schema_version": SCHEMA, "conflicts": []}),
    )


def state_set(root: Path, key: str, value: Any) -> dict[str, Any]:
    ident = local_identity(root)
    node = str(ident.get("machine_id") or ident.get("agent_id") or ident.get("project_id"))
    vec, regs, conflicts = state_docs(root)
    clock = {str(k): int(v) for k, v in (vec.get("clock") or {}).items()}
    clock[node] = clock.get(node, 0) + 1
    vec["clock"] = clock
    entry = {"value": value, "value_hash": fingerprint(canonical_bytes(value)), "vector": dict(clock), "updated_by": ident.get("agent_id"), "updated_at": iso_now()}
    regs.setdefault("entries", {})[key] = entry
    dump_yaml(root / VECTOR, vec)
    dump_yaml(root / REGISTERS, regs)
    dump_yaml(root / CONFLICTS, conflicts)
    audit(root, {"action": "STATE_SET", "key": key, "node": node})
    return {"status": "PASS", "key": key, "entry": entry, "clock": clock}


def state_export(root: Path, out: Path, private: Path, key_id: str, audience_project: str, ttl: int = 900) -> Path:
    vec, regs, _ = state_docs(root)
    payload = {"risk": "MEDIUM", "clock": vec.get("clock", {}), "entries": regs.get("entries", {})}
    bundle = build_envelope("state-push", payload, private, root, key_id, audience_project, None, ttl, None)
    save_signed(out, bundle)
    return out


def state_import(root: Path, bundle_path: Path) -> dict[str, Any]:
    bundle = load_yaml(bundle_path, {})
    verified = verify_remote_bundle(root, bundle, "state-push", True)
    if verified.get("status") != "PASS":
        return verified
    incoming = verified.get("payload") or {}
    local_vec, local_regs, conflicts = state_docs(root)
    inc_clock = {str(k): int(v) for k, v in (incoming.get("clock") or {}).items()}
    loc_clock = {str(k): int(v) for k, v in (local_vec.get("clock") or {}).items()}
    relation = vector_compare(inc_clock, loc_clock)
    if relation == -1:
        return {"status": "PASS", "reason": "LOCAL_DOMINATES", "merged": 0, "conflicts": 0}
    merged = 0
    conflict_count = 0
    if relation == 1:
        local_vec["clock"] = inc_clock
    for key, inc in (incoming.get("entries") or {}).items():
        cur = (local_regs.get("entries") or {}).get(key)
        if cur is None:
            local_regs.setdefault("entries", {})[key] = inc
            merged += 1
            continue
        rel = vector_compare(inc.get("vector") or {}, cur.get("vector") or {})
        if rel == 1:
            local_regs["entries"][key] = inc
            merged += 1
        elif rel == 2 and str(inc.get("value_hash")) != str(cur.get("value_hash")):
            conflict_count += 1
            conflicts.setdefault("conflicts", []).append({"key": key, "local": cur, "incoming": inc, "detected_at": iso_now(), "status": "UNRESOLVED"})
    dump_yaml(root / VECTOR, local_vec)
    dump_yaml(root / REGISTERS, local_regs)
    dump_yaml(root / CONFLICTS, conflicts)
    audit(root, {"action": "STATE_IMPORT", "sender": verified.get("sender"), "merged": merged, "conflicts": conflict_count})
    return {"status": "PASS" if conflict_count == 0 else "REVIEW_REQUIRED", "merged": merged, "conflicts": conflict_count, "relation": relation}


def policy_init(root: Path) -> Path:
    ident = local_identity(root)
    doc = {
        "schema_version": SCHEMA,
        "federation_id": f"FED-{ident.get('project_id', 'UNKNOWN')}",
        "default_deny": True,
        "require_signed_handoff": True,
        "require_signed_state": True,
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "peers": [],
    }
    dump_yaml(root / POLICY, doc)
    return root / POLICY


def policy_sign(root: Path, private: Path, key_id: str) -> Path:
    payload = load_yaml(root / POLICY, {})
    env = sign_payload(payload, private, root, key_id, "federation-policy")
    (root / POLICY_SIG).write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
    audit(root, {"action": "POLICY_SIGN", "key_id": key_id})
    return root / POLICY_SIG


def ensure_scaffold(root: Path) -> None:
    for p in [IDENTITY, PEERS, POLICY, REPLAY, AUDIT, VECTOR, REGISTERS, CONFLICTS]:
        (root / p).parent.mkdir(parents=True, exist_ok=True)
    if not (root / PEERS).exists(): dump_yaml(root / PEERS, {"schema_version": SCHEMA, "peers": []})
    if not (root / POLICY).exists(): policy_init(root)
    if not (root / REPLAY).exists(): dump_yaml(root / REPLAY, {"schema_version": SCHEMA, "seen": []})
    if not (root / VECTOR).exists(): dump_yaml(root / VECTOR, {"schema_version": SCHEMA, "clock": {}})
    if not (root / REGISTERS).exists(): dump_yaml(root / REGISTERS, {"schema_version": SCHEMA, "entries": {}})
    if not (root / CONFLICTS).exists(): dump_yaml(root / CONFLICTS, {"schema_version": SCHEMA, "conflicts": []})
    (root / AUDIT).touch(exist_ok=True)


def doctor(root: Path) -> dict[str, Any]:
    ensure_scaffold(root)
    identity = local_identity(root)
    peers = peer_doc(root).get("peers", []) or []
    replay = replay_load(root)
    conflicts = load_yaml(root / CONFLICTS, {}).get("conflicts", []) or []
    checks = {
        "identity": bool(identity.get("project_id") and identity.get("agent_id") and identity.get("public_key")),
        "policy": (root / POLICY).exists(),
        "replay_store": isinstance(replay.get("seen", []), list),
        "state_vector": (root / VECTOR).exists(),
        "state_registers": (root / REGISTERS).exists(),
        "state_conflicts": (root / CONFLICTS).exists(),
        "unresolved_conflicts": len([x for x in conflicts if str(x.get("status", "UNRESOLVED")) == "UNRESOLVED"]) == 0,
        "audit": (root / AUDIT).exists(),
    }
    # A fresh scaffold is structurally healthy even before a real federation
    # identity is initialized. The missing identity is reported, not treated as
    # corruption.
    structural = [v for k, v in checks.items() if k != "identity"]
    status = "PASS" if all(structural) else "FAIL"
    result = {"status": status, "checks": checks, "peer_count": len(peers)}
    if not checks["identity"]:
        result["identity_state"] = "NOT_INITIALIZED"
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v2.0 Distributed Agent Federation")
    p.add_argument("command", choices=["identity-init", "identity-verify", "peer-import", "policy-init", "policy-sign", "handoff-sign", "handoff-verify", "state", "doctor"])
    p.add_argument("path")
    p.add_argument("action", nargs="?")
    p.add_argument("--project-id")
    p.add_argument("--agent-id")
    p.add_argument("--machine-id")
    p.add_argument("--key-id")
    p.add_argument("--public-key")
    p.add_argument("--private-key")
    p.add_argument("--root-private-key")
    p.add_argument("--root-key-id")
    p.add_argument("--identity")
    p.add_argument("--identity-sig")
    p.add_argument("--root-public-key")
    p.add_argument("--peer-id")
    p.add_argument("--allowed-action", action="append", default=[])
    p.add_argument("--max-risk", default="MEDIUM")
    p.add_argument("--file")
    p.add_argument("--audience-project")
    p.add_argument("--audience-agent")
    p.add_argument("--ttl", type=int, default=900)
    p.add_argument("--sequence", type=int)
    p.add_argument("--risk", default="LOW")
    p.add_argument("--key")
    p.add_argument("--value")
    p.add_argument("--out")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    root = Path(args.path).resolve()

    try:
        if args.command == "identity-init":
            result = identity_init(root, args.project_id or "", args.agent_id or "", args.machine_id or "", args.key_id or "", Path(args.public_key), Path(args.root_private_key), args.root_key_id or args.key_id or "")
        elif args.command == "identity-verify":
            result = identity_verify(Path(args.identity), Path(args.identity_sig), Path(args.root_public_key))
        elif args.command == "peer-import":
            result = peer_import(root, args.peer_id or "", Path(args.identity), Path(args.identity_sig), Path(args.root_public_key), args.allowed_action, args.max_risk)
        elif args.command == "policy-init":
            result = {"status": "PASS", "file": str(policy_init(root))}
        elif args.command == "policy-sign":
            result = {"status": "PASS", "file": str(policy_sign(root, Path(args.private_key), args.key_id))}
        elif args.command == "handoff-sign":
            out = handoff_sign(root, Path(args.file), Path(args.private_key), args.key_id, args.audience_project or "", args.audience_agent, args.ttl, args.sequence, args.risk)
            result = {"status": "PASS", "file": str(out.relative_to(root))}
        elif args.command == "handoff-verify":
            result = verify_remote_bundle(root, load_yaml(Path(args.file), {}), "handoff", True)
        elif args.command == "state":
            if args.action == "set":
                value: Any = args.value
                if args.value and args.value[:1] in "[{":
                    try: value = json.loads(args.value)
                    except Exception: pass
                result = state_set(root, args.key or "", value)
            elif args.action == "export":
                out = Path(args.out).resolve()
                result = {"status": "PASS", "file": str(state_export(root, out, Path(args.private_key), args.key_id, args.audience_project or "", args.ttl))}
            elif args.action == "import":
                result = state_import(root, Path(args.file))
            else:
                raise SystemExit("state action must be set/export/import")
        elif args.command == "doctor":
            result = doctor(root)
        else:
            raise SystemExit("unsupported command")
    except Exception as exc:
        result = {"status": "FAIL", "reason": str(exc)}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result.get("status", "FAIL"))
        if result.get("reason"):
            print(f"REASON {result['reason']}")
        if "file" in result:
            print(f"FILE {result['file']}")
        if "merged" in result:
            print(f"MERGED {result['merged']}")
        if "conflicts" in result:
            print(f"CONFLICTS {result['conflicts']}")
    raise SystemExit(0 if result.get("status") in {"PASS", "REVIEW_REQUIRED"} else 1)


if __name__ == "__main__":
    main()
