#!/usr/bin/env python3
"""UAAF v2.1 federation operations and resilience layer."""
from __future__ import annotations

import argparse
import base64
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from uaf_federation import (
    FED_DIR, REPLAY, STATE_DIR, VECTOR, REGISTERS, CONFLICTS,
    audit, build_envelope, dump_yaml, load_yaml, local_identity,
    save_signed, verify_remote_bundle,
    canonical_bytes, fingerprint, utc_now, iso_now,
)

SCHEMA = "2.1"
OPS_DIR = FED_DIR / "ops"
MODE = OPS_DIR / "MODE.yaml"
CURSORS = OPS_DIR / "CURSORS.yaml"
BUNDLES = OPS_DIR / "BUNDLES.yaml"
REVOCATIONS = OPS_DIR / "REVOCATIONS.yaml"
CHECKPOINTS = OPS_DIR / "CHECKPOINTS.yaml"
CONFLICTS_V21 = OPS_DIR / "CONFLICTS.yaml"
OBSERVABILITY = OPS_DIR / "OBSERVABILITY.jsonl"

MODES = {"ONLINE", "OFFLINE", "PARTITIONED", "RECOVERING"}


def now() -> datetime:
    return utc_now()


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None



def load_private(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private key is not Ed25519")
    return key


def sign_v21(payload: dict[str, Any], private_path: Path, key_id: str, purpose: str) -> dict[str, Any]:
    raw = canonical_bytes(payload)
    private = load_private(private_path)
    sig = private.sign(raw)
    return {
        "schema_version": SCHEMA,
        "algorithm": "Ed25519",
        "key_id": key_id,
        "purpose": purpose,
        "payload_sha256": fingerprint(raw),
        "signature_b64": base64.b64encode(sig).decode("ascii"),
    }


def verify_v21(payload: dict[str, Any], sig: dict[str, Any], public_raw: bytes, purpose: str) -> tuple[bool, str]:
    if sig.get("schema_version") != SCHEMA or sig.get("algorithm") != "Ed25519":
        return False, "SIGNATURE_SCHEMA_MISMATCH"
    if sig.get("purpose") != purpose:
        return False, "PURPOSE_MISMATCH"
    raw = canonical_bytes(payload)
    if fingerprint(raw) != str(sig.get("payload_sha256", "")):
        return False, "PAYLOAD_HASH_MISMATCH"
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(base64.b64decode(str(sig.get("signature_b64", "")), validate=True), raw)
    except (ValueError, InvalidSignature, TypeError):
        return False, "SIGNATURE_INVALID"
    return True, "OK"


def root_public(root: Path) -> bytes:
    anchor = load_yaml(root / ".ai/trust/ROOT.yaml", {}).get("anchor") or {}
    raw = base64.b64decode(str(anchor.get("public_key", "")), validate=True)
    if len(raw) != 32:
        raise ValueError("trust root public key is not configured")
    return raw


def root_key_id(root: Path) -> str:
    return str((load_yaml(root / ".ai/trust/ROOT.yaml", {}).get("anchor") or {}).get("key_id", ""))

def ensure(root: Path) -> None:
    (root / OPS_DIR).mkdir(parents=True, exist_ok=True)
    if not (root / MODE).exists():
        dump_yaml(root / MODE, {"schema_version": SCHEMA, "mode": "ONLINE", "updated_at": iso_now()})
    if not (root / CURSORS).exists():
        dump_yaml(root / CURSORS, {"schema_version": SCHEMA, "peers": {}})
    if not (root / BUNDLES).exists():
        dump_yaml(root / BUNDLES, {"schema_version": SCHEMA, "consumed": []})
    if not (root / REVOCATIONS).exists():
        dump_yaml(root / REVOCATIONS, {"schema_version": SCHEMA, "revocation_epoch": 0, "entries": []})
    if not (root / CHECKPOINTS).exists():
        dump_yaml(root / CHECKPOINTS, {"schema_version": SCHEMA, "checkpoints": []})
    if not (root / CONFLICTS_V21).exists():
        dump_yaml(root / CONFLICTS_V21, {"schema_version": SCHEMA, "conflicts": []})
    (root / OBSERVABILITY).parent.mkdir(parents=True, exist_ok=True)
    (root / OBSERVABILITY).touch(exist_ok=True)


def set_mode(root: Path, mode: str) -> dict[str, Any]:
    ensure(root)
    mode = mode.upper()
    if mode not in MODES:
        return {"status": "FAIL", "reason": "INVALID_MODE"}
    doc = load_yaml(root / MODE, {})
    previous = doc.get("mode", "ONLINE")
    doc.update({"schema_version": SCHEMA, "mode": mode, "updated_at": iso_now()})
    dump_yaml(root / MODE, doc)
    audit(root, {"action": "FED_MODE_SET", "previous": previous, "mode": mode})
    return {"status": "PASS", "previous": previous, "mode": mode}


def status(root: Path) -> dict[str, Any]:
    ensure(root)
    mode = load_yaml(root / MODE, {}).get("mode", "ONLINE")
    cursors = load_yaml(root / CURSORS, {}).get("peers", {})
    consumed = load_yaml(root / BUNDLES, {}).get("consumed", [])
    rev = load_yaml(root / REVOCATIONS, {})
    conflicts = load_yaml(root / CONFLICTS_V21, {}).get("conflicts", [])
    return {
        "status": "PASS",
        "mode": mode,
        "sync_lag": {k: v for k, v in cursors.items()},
        "peer_count": len(cursors),
        "consumed_bundles": len(consumed),
        "revocation_epoch": int(rev.get("revocation_epoch", 0) or 0),
        "unresolved_conflicts": len([c for c in conflicts if c.get("status") in {"UNRESOLVED", "PROPOSED", "APPROVED"}]),
    }


def current_local_state(root: Path) -> dict[str, Any]:
    vec = load_yaml(root / VECTOR, {}).get("clock", {})
    regs = load_yaml(root / REGISTERS, {}).get("entries", {})
    conflicts = load_yaml(root / CONFLICTS, {}).get("conflicts", [])
    return {
        "clock": vec,
        "registers_hash": fingerprint(canonical_bytes(regs)),
        "conflicts_hash": fingerprint(canonical_bytes(conflicts)),
    }


def sync_export(root: Path, out: Path, private: Path, key_id: str, audience_project: str, peer_id: str) -> Path:
    ensure(root)
    ident = local_identity(root)
    rev = load_yaml(root / REVOCATIONS, {})
    payload = {
        "risk": "MEDIUM",
        "sync": {
            "peer_id": peer_id,
            "cursor": load_yaml(root / CURSORS, {}).get("peers", {}).get(peer_id, {}).get("cursor", 0),
            "source_state": current_local_state(root),
            "revocation_epoch": int(rev.get("revocation_epoch", 0) or 0),
            "checkpoint_count": len(load_yaml(root / CHECKPOINTS, {}).get("checkpoints", []) or []),
            "revocations": load_yaml(root / REVOCATIONS, {}).get("entries", [])[-100:],
        },
    }
    bundle = build_envelope("state-push", payload, private, root, key_id, audience_project, None, 900, payload["sync"]["cursor"] + 1)
    bundle["sync_version"] = SCHEMA
    bundle["sync_id"] = f"SYNC-{ident.get('project_id')}-{bundle['envelope']['envelope_id']}"
    save_signed(out, bundle)
    cursors = load_yaml(root / CURSORS, {})
    cursors.setdefault("peers", {}).setdefault(peer_id, {})["last_export"] = iso_now()
    dump_yaml(root / CURSORS, cursors)
    audit(root, {"action": "SYNC_EXPORT", "sync_id": bundle["sync_id"], "peer_id": peer_id})
    return out


def sync_import(root: Path, bundle_path: Path) -> dict[str, Any]:
    ensure(root)
    bundle = load_yaml(bundle_path, {})
    sync_id = str(bundle.get("sync_id", ""))
    if not sync_id:
        return {"status": "FAIL", "reason": "SYNC_ID_MISSING"}
    consumed = load_yaml(root / BUNDLES, {}).get("consumed", []) or []
    if sync_id in consumed:
        return {"status": "FAIL", "reason": "SYNC_BUNDLE_REPLAY"}
    verified = verify_remote_bundle(root, bundle, "state-push", True)
    if verified.get("status") != "PASS":
        return verified
    payload = verified.get("payload") or {}
    sync = payload.get("sync") or {}
    peer_id = str(sync.get("peer_id", ""))
    remote_epoch = int(sync.get("revocation_epoch", 0) or 0)
    peer = None
    try:
        from uaf_federation import peer_lookup
        peer = peer_lookup(root, project_id=str((verified.get("sender") or {}).get("project_id")))
    except Exception:
        peer = None
    if not peer:
        return {"status": "FAIL", "reason": "PEER_NOT_TRUSTED"}
    try:
        peer_root_doc = load_yaml(root / str(peer.get("root_public_key", "")), {})
        # root_public_key is a PEM path, not YAML; load directly below.
        peer_root_pem = (root / str(peer.get("root_public_key", ""))).read_bytes()
        peer_root = serialization.load_pem_public_key(peer_root_pem).public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    except Exception:
        return {"status": "FAIL", "reason": "PEER_ROOT_KEY_INVALID"}
    local_rev = load_yaml(root / REVOCATIONS, {})
    local_epoch = int(local_rev.get("revocation_epoch", 0) or 0)
    if remote_epoch < local_epoch:
        return {"status": "FAIL", "reason": "STALE_REVOCATION_EPOCH"}
    if remote_epoch > local_epoch:
        local_rev["revocation_epoch"] = remote_epoch
        dump_yaml(root / REVOCATIONS, local_rev)
    doc = load_yaml(root / BUNDLES, {})
    doc.setdefault("consumed", []).append(sync_id)
    doc["consumed"] = doc["consumed"][-5000:]
    dump_yaml(root / BUNDLES, doc)
    cursors = load_yaml(root / CURSORS, {})
    cursors.setdefault("peers", {}).setdefault(peer_id, {})["cursor"] = int(sync.get("cursor", 0) or 0)
    cursors["peers"][peer_id]["last_import"] = iso_now()
    dump_yaml(root / CURSORS, cursors)
    rev_imported = 0
    local_rev = load_yaml(root / REVOCATIONS, {})
    existing_ids = {str(x.get("revocation_id")) for x in local_rev.get("entries", []) or [] if isinstance(x, dict)}
    for rec in sync.get("revocations", []) or []:
        if not isinstance(rec, dict) or str(rec.get("revocation_id")) in existing_ids:
            continue
        ok, reason = revoke_verify(root, rec, peer_root, None)
        if not ok:
            return {"status": "FAIL", "reason": "REVOCATION_INVALID", "detail": reason}
        local_rev.setdefault("entries", []).append(rec)
        existing_ids.add(str(rec.get("revocation_id")))
        rev_imported += 1
    local_rev["revocation_epoch"] = max(int(local_rev.get("revocation_epoch", 0) or 0), remote_epoch)
    dump_yaml(root / REVOCATIONS, local_rev)
    audit(root, {"action": "SYNC_IMPORT", "sync_id": sync_id, "peer_id": peer_id, "revocation_epoch": remote_epoch, "revocations_imported": rev_imported})
    return {"status": "PASS", "reason": "SYNC_ACCEPTED", "sync_id": sync_id, "peer_id": peer_id, "revocations_imported": rev_imported}


def conflict_list(root: Path) -> dict[str, Any]:
    ensure(root)
    return {"status": "PASS", "conflicts": load_yaml(root / CONFLICTS_V21, {}).get("conflicts", []) or []}


def conflict_propose(root: Path, key: str, resolution: Any, proposer: str, evidence: str) -> dict[str, Any]:
    ensure(root)
    doc = load_yaml(root / CONFLICTS_V21, {})
    cid = f"CF-{hashlib.sha256(f'{key}|{iso_now()}'.encode()).hexdigest()[:12]}"
    row = {"conflict_id": cid, "key": key, "status": "PROPOSED", "resolution": resolution, "proposer": proposer, "evidence": evidence, "proposed_at": iso_now()}
    doc.setdefault("conflicts", []).append(row)
    dump_yaml(root / CONFLICTS_V21, doc)
    audit(root, {"action": "CONFLICT_PROPOSE", "conflict_id": cid, "key": key})
    return {"status": "PASS", "conflict_id": cid}


def conflict_transition(root: Path, conflict_id: str, target: str, actor: str) -> dict[str, Any]:
    ensure(root)
    target = target.upper()
    if target not in {"APPROVED", "RESOLVED", "REJECTED"}:
        return {"status": "FAIL", "reason": "INVALID_CONFLICT_STATE"}
    doc = load_yaml(root / CONFLICTS_V21, {})
    for row in doc.get("conflicts", []) or []:
        if str(row.get("conflict_id")) != conflict_id:
            continue
        current = str(row.get("status", "UNRESOLVED"))
        valid = (current == "PROPOSED" and target in {"APPROVED", "REJECTED"}) or (current == "APPROVED" and target == "RESOLVED")
        if not valid:
            return {"status": "FAIL", "reason": "INVALID_CONFLICT_TRANSITION", "current": current}
        if target == "RESOLVED" and not row.get("evidence"):
            return {"status": "FAIL", "reason": "RESOLUTION_EVIDENCE_REQUIRED"}
        row["status"] = target
        row["actor"] = actor
        row["updated_at"] = iso_now()
        dump_yaml(root / CONFLICTS_V21, doc)
        audit(root, {"action": "CONFLICT_TRANSITION", "conflict_id": conflict_id, "status": target, "actor": actor})
        return {"status": "PASS", "conflict_id": conflict_id, "state": target}
    return {"status": "FAIL", "reason": "CONFLICT_NOT_FOUND"}


def revoke(root: Path, target_type: str, target_id: str, reason: str, private: Path, key_id: str, effective_at: str | None = None) -> dict[str, Any]:
    ensure(root)
    if key_id != root_key_id(root):
        return {"status": "FAIL", "reason": "REVOCATION_REQUIRES_TRUST_ROOT"}
    rev = load_yaml(root / REVOCATIONS, {})
    epoch = int(rev.get("revocation_epoch", 0) or 0) + 1
    rec = {
        "schema_version": SCHEMA,
        "revocation_id": f"REV-{epoch}-{hashlib.sha256(f'{target_type}|{target_id}'.encode()).hexdigest()[:10]}",
        "target_type": target_type,
        "target_id": target_id,
        "reason": reason,
        "effective_at": effective_at or iso_now(),
        "revocation_epoch": epoch,
    }
    rec["signature"] = sign_v21(rec, private, key_id, "federation-revocation")
    rev["revocation_epoch"] = epoch
    rev.setdefault("entries", []).append(rec)
    dump_yaml(root / REVOCATIONS, rev)
    audit(root, {"action": "REVOCATION_CREATE", "revocation_id": rec["revocation_id"], "epoch": epoch})
    return {"status": "PASS", "revocation": rec}


def revoke_verify(root: Path, rec: dict[str, Any], public_raw: bytes | None = None, expected_key_id: str | None = None) -> tuple[bool, str]:
    sig = rec.get("signature") or {}
    payload = {k: v for k, v in rec.items() if k != "signature"}
    key_id = str(sig.get("key_id", ""))
    if expected_key_id is None:
        if key_id != root_key_id(root):
            return False, "REVOCATION_SIGNER_NOT_ROOT"
        public_raw = root_public(root)
    else:
        if key_id != expected_key_id:
            return False, "REVOCATION_SIGNER_MISMATCH"
    return verify_v21(payload, sig, public_raw or root_public(root), "federation-revocation")


def revocation_import(root: Path, file: Path) -> dict[str, Any]:
    ensure(root)
    bundle = load_yaml(file, {})
    rec = bundle.get("revocation") or {}
    ok, reason = revoke_verify(root, rec)
    if not ok:
        return {"status": "FAIL", "reason": reason}
    local = load_yaml(root / REVOCATIONS, {})
    incoming_epoch = int(rec.get("revocation_epoch", 0) or 0)
    local_epoch = int(local.get("revocation_epoch", 0) or 0)
    existing_ids = {str(x.get("revocation_id")) for x in local.get("entries", []) or [] if isinstance(x, dict)}
    if incoming_epoch < local_epoch:
        return {"status": "FAIL", "reason": "STALE_REVOCATION_EPOCH"}
    if str(rec.get("revocation_id")) in existing_ids:
        return {"status": "PASS", "reason": "REVOCATION_ALREADY_PRESENT"}
    local["revocation_epoch"] = max(local_epoch, incoming_epoch)
    local.setdefault("entries", []).append(rec)
    dump_yaml(root / REVOCATIONS, local)
    audit(root, {"action": "REVOCATION_IMPORT", "revocation_id": rec.get("revocation_id"), "epoch": incoming_epoch})
    return {"status": "PASS", "reason": "REVOCATION_ACCEPTED", "revocation_id": rec.get("revocation_id")}


def checkpoint_create(root: Path, private: Path, key_id: str, out: Path) -> Path:
    ensure(root)
    if key_id != root_key_id(root):
        raise ValueError("checkpoint requires trust root key")
    vec = load_yaml(root / VECTOR, {})
    regs = load_yaml(root / REGISTERS, {})
    conflicts = load_yaml(root / CONFLICTS, {})
    replay = load_yaml(root / REPLAY, {})
    rev = load_yaml(root / REVOCATIONS, {})
    state = {
        "vector": vec.get("clock", {}),
        "registers": regs.get("entries", {}),
        "conflicts": conflicts.get("conflicts", []),
        "replay_seen": replay.get("seen", []),
        "revocation_epoch": int(rev.get("revocation_epoch", 0) or 0),
    }
    payload = {
        "schema_version": SCHEMA,
        "checkpoint_id": f"CHK-{iso_now().replace(':','').replace('-','')}-{hashlib.sha256(canonical_bytes(state)).hexdigest()[:12]}",
        "created_at": iso_now(),
        "state": state,
        "registers_hash": fingerprint(canonical_bytes(state["registers"])),
        "conflicts_hash": fingerprint(canonical_bytes(state["conflicts"])),
        "replay_watermark": len(state["replay_seen"]),
    }
    sig = sign_v21(payload, private, key_id, "federation-checkpoint")
    doc = {"checkpoint": payload, "signature": sig}
    save_signed(out, doc)
    index = load_yaml(root / CHECKPOINTS, {})
    index.setdefault("checkpoints", []).append({"checkpoint_id": payload["checkpoint_id"], "created_at": payload["created_at"], "registers_hash": payload["registers_hash"], "conflicts_hash": payload["conflicts_hash"]})
    dump_yaml(root / CHECKPOINTS, index)
    audit(root, {"action": "CHECKPOINT_CREATE", "checkpoint_id": payload["checkpoint_id"]})
    return out


def checkpoint_verify(root: Path, path: Path) -> dict[str, Any]:
    ensure(root)
    bundle = load_yaml(path, {})
    cp = bundle.get("checkpoint") or {}
    sig = bundle.get("signature") or {}
    if cp.get("schema_version") != SCHEMA:
        return {"status": "FAIL", "reason": "CHECKPOINT_SCHEMA_MISMATCH"}
    ok, reason = verify_v21(cp, sig, root_public(root), "federation-checkpoint")
    if not ok:
        return {"status": "FAIL", "reason": reason}
    state = cp.get("state") or {}
    actual_regs = load_yaml(root / REGISTERS, {}).get("entries", {})
    actual_conflicts = load_yaml(root / CONFLICTS, {}).get("conflicts", [])
    if fingerprint(canonical_bytes(state.get("registers", {}))) != fingerprint(canonical_bytes(actual_regs)):
        return {"status": "FAIL", "reason": "CHECKPOINT_STATE_MISMATCH"}
    if fingerprint(canonical_bytes(state.get("conflicts", []))) != fingerprint(canonical_bytes(actual_conflicts)):
        return {"status": "FAIL", "reason": "CHECKPOINT_STATE_MISMATCH"}
    return {"status": "PASS", "reason": "CHECKPOINT_VALID", "checkpoint_id": cp.get("checkpoint_id")}


def checkpoint_recover(root: Path, path: Path) -> dict[str, Any]:
    ensure(root)
    current = load_yaml(root / MODE, {})
    if str(current.get("mode", "ONLINE")).upper() != "RECOVERING":
        return {"status": "FAIL", "reason": "RECOVERY_REQUIRES_RECOVERING_MODE"}
    bundle = load_yaml(path, {})
    cp = bundle.get("checkpoint") or {}
    sig = bundle.get("signature") or {}
    ok, reason = verify_v21(cp, sig, root_public(root), "federation-checkpoint")
    if not ok:
        return {"status": "FAIL", "reason": reason}
    state = cp.get("state") or {}
    if not state.get("registers") and not state.get("vector"):
        return {"status": "FAIL", "reason": "CHECKPOINT_STATE_EMPTY"}
    backup = root / STATE_DIR / "RECOVERY-BACKUP.yaml"
    backup.parent.mkdir(parents=True, exist_ok=True)
    current_vec = load_yaml(root / VECTOR, {})
    current_regs = load_yaml(root / REGISTERS, {})
    current_conflicts = load_yaml(root / CONFLICTS, {})
    backup.write_text(yaml.safe_dump({"vector": current_vec, "registers": current_regs, "conflicts": current_conflicts}, sort_keys=False), encoding="utf-8")
    recovered_conflicts = list(state.get("conflicts", []) or [])
    existing_conflict_ids = {str(c.get("conflict_id")) for c in recovered_conflicts if isinstance(c, dict)}
    # Recovery never silently discards unresolved local conflicts.
    for c in current_conflicts.get("conflicts", []) or []:
        if isinstance(c, dict) and str(c.get("status", "UNRESOLVED")) in {"UNRESOLVED", "PROPOSED", "APPROVED"} and str(c.get("conflict_id")) not in existing_conflict_ids:
            recovered_conflicts.append(c)
    dump_yaml(root / VECTOR, {"schema_version": SCHEMA, "clock": state.get("vector", {})})
    dump_yaml(root / REGISTERS, {"schema_version": SCHEMA, "entries": state.get("registers", {})})
    dump_yaml(root / CONFLICTS, {"schema_version": SCHEMA, "conflicts": recovered_conflicts})
    audit(root, {"action": "CHECKPOINT_RECOVER", "checkpoint_id": cp.get("checkpoint_id"), "backup": str(backup.relative_to(root))})
    return {"status": "PASS", "reason": "RECOVERY_APPLIED", "checkpoint_id": cp.get("checkpoint_id"), "backup": str(backup)}


def observe(root: Path) -> dict[str, Any]:
    ensure(root)
    state = status(root)
    event = {"timestamp": iso_now(), **state}
    with (root / OBSERVABILITY).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="UAAF v2.1 federation operations")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("mode"); p.add_argument("path", nargs="?", default="."); p.add_argument("value")
    p = sub.add_parser("status"); p.add_argument("path", nargs="?", default=".")
    p = sub.add_parser("sync-export"); p.add_argument("path", nargs="?", default="."); p.add_argument("--out", required=True); p.add_argument("--private-key", required=True); p.add_argument("--key-id", required=True); p.add_argument("--audience-project", required=True); p.add_argument("--peer-id", required=True)
    p = sub.add_parser("sync-import"); p.add_argument("path", nargs="?", default="."); p.add_argument("--file", required=True)
    p = sub.add_parser("conflicts"); p.add_argument("path", nargs="?", default=".");
    p = sub.add_parser("conflict-propose"); p.add_argument("path", nargs="?", default="."); p.add_argument("--key", required=True); p.add_argument("--resolution", required=True); p.add_argument("--proposer", required=True); p.add_argument("--evidence", required=True)
    p = sub.add_parser("conflict-transition"); p.add_argument("path", nargs="?", default="."); p.add_argument("--conflict-id", required=True); p.add_argument("--status", required=True); p.add_argument("--actor", required=True)
    p = sub.add_parser("revoke"); p.add_argument("path", nargs="?", default="."); p.add_argument("--target-type", required=True); p.add_argument("--target-id", required=True); p.add_argument("--reason", required=True); p.add_argument("--private-key", required=True); p.add_argument("--key-id", required=True); p.add_argument("--effective-at")
    p = sub.add_parser("revoke-import"); p.add_argument("path", nargs="?", default="."); p.add_argument("--file", required=True)
    p = sub.add_parser("checkpoint-create"); p.add_argument("path", nargs="?", default="."); p.add_argument("--out", required=True); p.add_argument("--private-key", required=True); p.add_argument("--key-id", required=True)
    p = sub.add_parser("checkpoint-verify"); p.add_argument("path", nargs="?", default="."); p.add_argument("--file", required=True)
    p = sub.add_parser("checkpoint-recover"); p.add_argument("path", nargs="?", default="."); p.add_argument("--file", required=True)
    p = sub.add_parser("observe"); p.add_argument("path", nargs="?", default=".")
    args = parser.parse_args(); root = Path(getattr(args, "path", ".")).resolve()
    if args.command == "mode": result = set_mode(root, args.value)
    elif args.command == "status": result = status(root)
    elif args.command == "sync-export": result = {"status": "PASS", "file": str(sync_export(root, Path(args.out).resolve(), Path(args.private_key).resolve(), args.key_id, args.audience_project, args.peer_id))}
    elif args.command == "sync-import": result = sync_import(root, Path(args.file).resolve())
    elif args.command == "conflicts": result = conflict_list(root)
    elif args.command == "conflict-propose": result = conflict_propose(root, args.key, args.resolution, args.proposer, args.evidence)
    elif args.command == "conflict-transition": result = conflict_transition(root, args.conflict_id, args.status, args.actor)
    elif args.command == "revoke": result = revoke(root, args.target_type, args.target_id, args.reason, Path(args.private_key).resolve(), args.key_id, args.effective_at)
    elif args.command == "revoke-import": result = revocation_import(root, Path(args.file).resolve())
    elif args.command == "checkpoint-create": result = {"status": "PASS", "file": str(checkpoint_create(root, Path(args.private_key).resolve(), args.key_id, Path(args.out).resolve()))}
    elif args.command == "checkpoint-verify": result = checkpoint_verify(root, Path(args.file).resolve())
    elif args.command == "checkpoint-recover": result = checkpoint_recover(root, Path(args.file).resolve())
    elif args.command == "observe": result = observe(root)
    else: result = {"status": "FAIL", "reason": "UNSUPPORTED_COMMAND"}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result.get("status") in {"PASS", "REVIEW_REQUIRED"} else 1)

if __name__ == "__main__": main()
