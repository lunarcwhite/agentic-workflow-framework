#!/usr/bin/env python3
"""UAAF v1.9 Trust Anchoring & Cryptographic Integrity.

Project-local cryptographic verification using Ed25519 signatures. Private keys
must remain outside the project repository. The repository contains public
keys, signatures, trust metadata, and tamper-evident audit records only.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SCHEMA_VERSION = "1.9"
TRUST_DIR = Path(".ai/trust")
ROOT_FILE = TRUST_DIR / "ROOT.yaml"
KEYS_FILE = TRUST_DIR / "KEYS.yaml"
AUDIT_FILE = Path(".ai/agents/TRUST-AUDIT.jsonl")
SIGNATURE_SUFFIX = ".sig"
ALGORITHM = "Ed25519"


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


def canonical_bytes(value: Any) -> bytes:
    """Canonical UTF-8 JSON encoding for stable signatures across machines."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def file_bytes(path: Path) -> bytes:
    return path.read_bytes()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(file_bytes(path))


def load_yaml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else dict(default or {})
    except Exception:
        return dict(default or {})


def load_private_key(path: Path) -> Ed25519PrivateKey:
    raw = path.read_bytes()
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private key is not Ed25519")
    return key


def load_public_key_bytes(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError("invalid base64 public key") from exc


def public_key_bytes(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def fingerprint_public_key(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sig_path(file_path: Path) -> Path:
    return file_path.with_name(file_path.name + SIGNATURE_SUFFIX)


def root_doc(root: Path) -> dict[str, Any]:
    return load_yaml(root / ROOT_FILE, {"schema_version": SCHEMA_VERSION, "anchor": {}, "policy": {}})


def keys_doc(root: Path) -> dict[str, Any]:
    return load_yaml(root / KEYS_FILE, {"schema_version": SCHEMA_VERSION, "keys": []})


def key_entry(root: Path, key_id: str) -> dict[str, Any] | None:
    for row in keys_doc(root).get("keys", []) or []:
        if isinstance(row, dict) and str(row.get("key_id")) == key_id:
            return row
    return None


def key_active(entry: dict[str, Any], *, at: datetime | None = None) -> bool:
    if str(entry.get("status", "ACTIVE")).upper() != "ACTIVE":
        return False
    moment = at or utc_now()
    nb = parse_ts(entry.get("not_before"))
    na = parse_ts(entry.get("not_after"))
    if nb and moment < nb:
        return False
    if na and moment >= na:
        return False
    return True


def signature_envelope(file_path: Path, key_id: str, purpose: str, signature: bytes) -> dict[str, Any]:
    payload = file_bytes(file_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm": ALGORITHM,
        "key_id": key_id,
        "purpose": purpose,
        "payload_sha256": sha256_bytes(payload),
        "signature_b64": base64.b64encode(signature).decode("ascii"),
        "created_at": iso_now(),
    }


def sign_file(root: Path, file_path: Path, private_key_path: Path, key_id: str, purpose: str, out: Path | None = None) -> Path:
    private = load_private_key(private_key_path)
    entry = key_entry(root, key_id)
    if entry is not None and not key_active(entry):
        raise ValueError(f"signing key {key_id} is not active")
    derived = fingerprint_public_key(public_key_bytes(private.public_key()))
    if entry is not None and str(entry.get("fingerprint_sha256", "")) != derived:
        raise ValueError("private key does not match registered public-key fingerprint")
    sig = private.sign(file_bytes(file_path))
    target = out or sig_path(file_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(signature_envelope(file_path, key_id, purpose, sig), indent=2) + "\n", encoding="utf-8")
    return target


def verify_file(root: Path, file_path: Path, signature_path: Path | None = None, *, key_id: str | None = None, pinned_root_fingerprint: str | None = None, purpose: str | None = None) -> dict[str, Any]:
    anchor = root_doc(root)
    keys = keys_doc(root)
    if pinned_root_fingerprint:
        actual = str((anchor.get("anchor") or {}).get("fingerprint_sha256", ""))
        if actual.lower() != pinned_root_fingerprint.lower():
            return {"status": "FAIL", "reason": "ROOT_PIN_MISMATCH", "expected": pinned_root_fingerprint, "actual": actual}
    if not file_path.exists():
        return {"status": "FAIL", "reason": "PAYLOAD_NOT_FOUND", "file": str(file_path)}
    sp = signature_path or sig_path(file_path)
    if not sp.exists():
        return {"status": "FAIL", "reason": "SIGNATURE_NOT_FOUND", "signature": str(sp)}
    try:
        envelope = json.loads(sp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "FAIL", "reason": "SIGNATURE_INVALID_JSON"}
    if str(envelope.get("schema_version")) != SCHEMA_VERSION:
        return {"status": "FAIL", "reason": "SIGNATURE_SCHEMA_MISMATCH"}
    if str(envelope.get("algorithm")) != ALGORITHM:
        return {"status": "FAIL", "reason": "UNSUPPORTED_ALGORITHM"}
    signer_id = str(key_id or envelope.get("key_id", ""))
    if signer_id != str(envelope.get("key_id", "")):
        return {"status": "FAIL", "reason": "KEY_ID_MISMATCH"}
    entry = next((x for x in keys.get("keys", []) or [] if isinstance(x, dict) and str(x.get("key_id")) == signer_id), None)
    if not entry:
        return {"status": "FAIL", "reason": "SIGNER_KEY_NOT_REGISTERED", "key_id": signer_id}
    if not key_active(entry):
        return {"status": "FAIL", "reason": "SIGNER_KEY_INACTIVE", "key_id": signer_id}
    if purpose and str(envelope.get("purpose")) != purpose:
        return {"status": "FAIL", "reason": "PURPOSE_MISMATCH", "expected": purpose, "actual": envelope.get("purpose")}
    payload = file_bytes(file_path)
    actual_hash = sha256_bytes(payload)
    if actual_hash != str(envelope.get("payload_sha256", "")):
        return {"status": "FAIL", "reason": "PAYLOAD_HASH_MISMATCH", "expected": envelope.get("payload_sha256"), "actual": actual_hash}
    try:
        public = Ed25519PublicKey.from_public_bytes(load_public_key_bytes(str(entry.get("public_key", ""))))
        public.verify(base64.b64decode(str(envelope.get("signature_b64", "")), validate=True), payload)
    except (ValueError, InvalidSignature, TypeError):
        return {"status": "FAIL", "reason": "SIGNATURE_INVALID", "key_id": signer_id}
    return {"status": "PASS", "reason": "SIGNATURE_VALID", "key_id": signer_id, "purpose": envelope.get("purpose"), "payload_sha256": actual_hash}


def initialize_trust(root: Path, key_id: str, public_key_path: Path, role: str = "root") -> dict[str, Any]:
    raw = public_key_path.read_bytes()
    public = serialization.load_pem_public_key(raw)
    if not isinstance(public, Ed25519PublicKey):
        raise ValueError("public key is not Ed25519")
    raw32 = public_key_bytes(public)
    fingerprint = fingerprint_public_key(raw32)
    trust_dir = root / TRUST_DIR
    trust_dir.mkdir(parents=True, exist_ok=True)
    root_payload = {
        "schema_version": SCHEMA_VERSION,
        "anchor": {
            "key_id": key_id,
            "algorithm": ALGORITHM,
            "public_key": base64.b64encode(raw32).decode("ascii"),
            "fingerprint_sha256": fingerprint,
            "status": "ACTIVE",
            "created_at": iso_now(),
        },
        "policy": {
            "enabled": True,
            "cryptographic_required": False,
            "external_pin_required": False,
            "required_purposes": ["trust-root", "trust-keys", "trust-policy", "delegations"],
        },
    }
    keys_payload = {
        "schema_version": SCHEMA_VERSION,
        "keys": [{
            "key_id": key_id,
            "algorithm": ALGORITHM,
            "role": role,
            "public_key": base64.b64encode(raw32).decode("ascii"),
            "fingerprint_sha256": fingerprint,
            "status": "ACTIVE",
            "not_before": iso_now(),
        }],
    }
    (trust_dir / "ROOT.yaml").write_text(yaml.safe_dump(root_payload, sort_keys=False), encoding="utf-8")
    (trust_dir / "KEYS.yaml").write_text(yaml.safe_dump(keys_payload, sort_keys=False), encoding="utf-8")
    (trust_dir / "README.md").write_text(
        "# UAAF v1.9 Trust Anchoring\n\nPrivate keys MUST remain outside the project. This directory contains only public trust material and detached signatures.\n",
        encoding="utf-8",
    )
    return {"status": "PASS", "key_id": key_id, "fingerprint_sha256": fingerprint}


def check_audit_chain(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "PASS", "entries": 0, "reason": "AUDIT_EMPTY"}
    previous = "GENESIS"
    entries = 0
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return {"status": "FAIL", "reason": "AUDIT_INVALID_JSON", "line": idx}
        expected_prev = str(event.get("prev_hash", ""))
        if expected_prev != previous:
            return {"status": "FAIL", "reason": "AUDIT_PREV_HASH_MISMATCH", "line": idx}
        actual_entry = str(event.get("entry_hash", ""))
        payload = dict(event)
        payload.pop("entry_hash", None)
        digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        if digest != actual_entry:
            return {"status": "FAIL", "reason": "AUDIT_ENTRY_HASH_MISMATCH", "line": idx}
        previous = actual_entry
        entries += 1
    return {"status": "PASS", "entries": entries, "head": previous}


def append_audit(root: Path, event: dict[str, Any]) -> None:
    path = root / AUDIT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = "GENESIS"
    chain = check_audit_chain(path)
    if chain.get("status") == "PASS":
        previous = str(chain.get("head", "GENESIS"))
    row = {"schema_version": SCHEMA_VERSION, "timestamp": iso_now(), "prev_hash": previous, **event}
    row["entry_hash"] = hashlib.sha256(canonical_bytes(row)).hexdigest()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")



def verify_project_bundle(root: Path, *, pinned_root_fingerprint: str | None = None) -> dict[str, Any]:
    """Verify the v1.9 trust anchor, signed key registry, policy/delegations, and audit chain."""
    anchor_doc = root_doc(root)
    anchor = anchor_doc.get("anchor") or {}
    crypto_policy = anchor_doc.get("policy") or {}
    required = bool(crypto_policy.get("cryptographic_required", False))
    if not anchor.get("public_key"):
        result = {
            "status": "FAIL" if required else "PASS",
            "reason": "TRUST_ANCHOR_NOT_INITIALIZED",
            "cryptographic_required": required,
            "checks": {"anchor": {"status": "FAIL" if required else "PASS", "reason": "NOT_INITIALIZED"}},
        }
        if pinned_root_fingerprint:
            result["checks"]["external_pin"] = {"status": "FAIL", "reason": "ROOT_PIN_UNAVAILABLE"}
            result["status"] = "FAIL"
        result["checks"]["audit_chain"] = check_audit_chain(root / AUDIT_FILE)
        return result
    raw = load_public_key_bytes(str(anchor.get("public_key", "")))
    actual_fp = fingerprint_public_key(raw)
    expected_fp = str(anchor.get("fingerprint_sha256", ""))
    checks: dict[str, Any] = {"anchor": actual_fp.lower() == expected_fp.lower() if expected_fp else False}
    if pinned_root_fingerprint:
        checks["external_pin"] = actual_fp.lower() == pinned_root_fingerprint.lower()
    keyreg = root / KEYS_FILE
    keyreg_sig = sig_path(keyreg)
    root_key_id = str(anchor.get("key_id", ""))
    root_signature = root / ROOT_FILE
    root_sig = sig_path(root_signature)
    if root_signature.exists():
        checks["root_signature"] = verify_file(root, root_signature, root_sig, key_id=root_key_id, purpose="trust-root")
    else:
        checks["root_signature"] = {"status": "FAIL", "reason": "ROOT_NOT_FOUND"}
    if keyreg.exists():
        checks["keys_signature"] = verify_file(root, keyreg, keyreg_sig, key_id=root_key_id, purpose="trust-keys")
    else:
        checks["keys_signature"] = {"status": "FAIL", "reason": "KEY_REGISTRY_NOT_FOUND"}
    policy = root / ".ai/agents/TRUST.yaml"
    deleg = root / ".ai/agents/DELEGATIONS.yaml"
    policy_cfg = anchor_doc.get("policy") or {}
    required = bool(policy_cfg.get("cryptographic_required", False))
    pin_required = bool(policy_cfg.get("external_pin_required", False))
    if pin_required and not pinned_root_fingerprint:
        checks["external_pin"] = {"status": "FAIL", "reason": "EXTERNAL_PIN_REQUIRED"}
        return {"status": "FAIL", "checks": checks, "cryptographic_required": required, "external_pin_required": True, "failed": ["external_pin"]}
    results: dict[str, Any] = {"status": "PASS", "checks": checks, "cryptographic_required": required, "external_pin_required": pin_required}
    if required:
        if policy.exists():
            checks["trust_policy_signature"] = verify_file(root, policy, sig_path(policy), purpose="trust-policy")
        else:
            checks["trust_policy_signature"] = {"status": "FAIL", "reason": "TRUST_POLICY_NOT_FOUND"}
        if deleg.exists():
            checks["delegations_signature"] = verify_file(root, deleg, sig_path(deleg), purpose="delegations")
        else:
            checks["delegations_signature"] = {"status": "FAIL", "reason": "DELEGATIONS_NOT_FOUND"}
    checks["audit_chain"] = check_audit_chain(root / AUDIT_FILE)
    bad = []
    for name, result in checks.items():
        if isinstance(result, dict) and result.get("status") not in {"PASS"}:
            bad.append(name)
        elif result is False:
            bad.append(name)
    if bad:
        results["status"] = "FAIL"
        results["failed"] = bad
    return results


def create_root_rotation(root: Path, old_private_path: Path, old_key_id: str, new_key_id: str, new_public_path: Path, effective_at: str, reason: str, out: Path) -> Path:
    old_private = load_private_key(old_private_path)
    old_entry = key_entry(root, old_key_id)
    if not old_entry or not key_active(old_entry):
        raise ValueError("old root key is not active and registered")
    new_public = serialization.load_pem_public_key(new_public_path.read_bytes())
    if not isinstance(new_public, Ed25519PublicKey):
        raise ValueError("new public key is not Ed25519")
    new_raw = public_key_bytes(new_public)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "type": "ROOT_KEY_ROTATION",
        "from_key_id": old_key_id,
        "to_key_id": new_key_id,
        "new_public_key": base64.b64encode(new_raw).decode("ascii"),
        "new_fingerprint_sha256": fingerprint_public_key(new_raw),
        "effective_at": effective_at,
        "reason": reason,
    }
    payload_bytes = canonical_bytes(payload)
    old_sig = old_private.sign(payload_bytes)
    doc = dict(payload)
    doc["old_signature_b64"] = base64.b64encode(old_sig).decode("ascii")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return out


def verify_root_rotation(root: Path, rotation_path: Path, new_public_path: Path | None = None) -> dict[str, Any]:
    doc = load_yaml(rotation_path, {})
    required = ["schema_version", "type", "from_key_id", "to_key_id", "new_public_key", "new_fingerprint_sha256", "effective_at", "old_signature_b64"]
    if any(k not in doc for k in required):
        return {"status": "FAIL", "reason": "ROTATION_FIELDS_MISSING"}
    if doc.get("schema_version") != SCHEMA_VERSION or doc.get("type") != "ROOT_KEY_ROTATION":
        return {"status": "FAIL", "reason": "ROTATION_SCHEMA_MISMATCH"}
    old = key_entry(root, str(doc["from_key_id"]))
    if not old:
        return {"status": "FAIL", "reason": "OLD_KEY_NOT_REGISTERED"}
    raw_new = load_public_key_bytes(str(doc["new_public_key"]))
    if fingerprint_public_key(raw_new) != str(doc["new_fingerprint_sha256"]):
        return {"status": "FAIL", "reason": "NEW_KEY_FINGERPRINT_MISMATCH"}
    if new_public_path:
        pub = serialization.load_pem_public_key(new_public_path.read_bytes())
        if not isinstance(pub, Ed25519PublicKey) or public_key_bytes(pub) != raw_new:
            return {"status": "FAIL", "reason": "NEW_PUBLIC_KEY_MISMATCH"}
    payload = dict(doc)
    payload.pop("old_signature_b64", None)
    try:
        pub_old = Ed25519PublicKey.from_public_bytes(load_public_key_bytes(str(old.get("public_key", ""))))
        pub_old.verify(base64.b64decode(str(doc["old_signature_b64"]), validate=True), canonical_bytes(payload))
    except (ValueError, InvalidSignature, TypeError):
        return {"status": "FAIL", "reason": "OLD_SIGNATURE_INVALID"}
    return {"status": "PASS", "reason": "ROOT_ROTATION_VALID", "from_key_id": doc["from_key_id"], "to_key_id": doc["to_key_id"]}

def generate_keypair(out_dir: Path, key_id: str) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    private_path = out_dir / f"{key_id}.private.pem"
    public_path = out_dir / f"{key_id}.public.pem"
    private_bytes = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public_bytes_pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    private_path.write_bytes(private_bytes)
    public_path.write_bytes(public_bytes_pem)
    try:
        os.chmod(private_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    raw = public_key_bytes(public)
    return {"status": "PASS", "key_id": key_id, "private_key": str(private_path), "public_key": str(public_path), "fingerprint_sha256": fingerprint_public_key(raw)}


def main() -> None:
    parser = argparse.ArgumentParser(description="UAAF v1.9 cryptographic integrity tools")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("keygen")
    p.add_argument("out_dir")
    p.add_argument("--key-id", required=True)

    p = sub.add_parser("trust-init")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--key-id", required=True)
    p.add_argument("--public-key", required=True)
    p.add_argument("--role", default="root")

    p = sub.add_parser("sign")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--file", required=True)
    p.add_argument("--private-key", required=True)
    p.add_argument("--key-id", required=True)
    p.add_argument("--purpose", required=True)
    p.add_argument("--out")

    p = sub.add_parser("verify")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--file", required=True)
    p.add_argument("--signature")
    p.add_argument("--key-id")
    p.add_argument("--purpose")
    p.add_argument("--pinned-root-fingerprint")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("bundle-check")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--pinned-root-fingerprint")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("rotation-create")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--old-private-key", required=True)
    p.add_argument("--old-key-id", required=True)
    p.add_argument("--new-key-id", required=True)
    p.add_argument("--new-public-key", required=True)
    p.add_argument("--effective-at", required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--out", required=True)

    p = sub.add_parser("rotation-check")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--file", required=True)
    p.add_argument("--new-public-key")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("audit-check")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("anchor-check")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--pinned-root-fingerprint")
    p.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command == "keygen":
        print(json.dumps(generate_keypair(Path(args.out_dir).resolve(), args.key_id), indent=2))
        return
    root = Path(getattr(args, "path", ".")).resolve()
    if args.command == "trust-init":
        print(json.dumps(initialize_trust(root, args.key_id, Path(args.public_key).resolve(), args.role), indent=2))
        return
    if args.command == "sign":
        payload = Path(args.file).resolve()
        out = Path(args.out).resolve() if args.out else None
        result = sign_file(root, payload, Path(args.private_key).resolve(), args.key_id, args.purpose, out)
        append_audit(root, {"action": "SIGN", "file": str(payload.relative_to(root)) if payload.is_relative_to(root) else str(payload), "key_id": args.key_id, "purpose": args.purpose, "signature": str(result.relative_to(root)) if result.is_relative_to(root) else str(result)})
        print(json.dumps({"status": "PASS", "signature": str(result)}, indent=2))
        return
    if args.command == "verify":
        result = verify_file(root, Path(args.file).resolve(), Path(args.signature).resolve() if args.signature else None, key_id=args.key_id, pinned_root_fingerprint=args.pinned_root_fingerprint, purpose=args.purpose)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"{result.get('status')} {result.get('reason')}")
        raise SystemExit(0 if result.get("status") == "PASS" else 1)
    if args.command == "bundle-check":
        result = verify_project_bundle(root, pinned_root_fingerprint=args.pinned_root_fingerprint)
        print(json.dumps(result, indent=2) if args.json else f"{result.get('status')} BUNDLE")
        raise SystemExit(0 if result.get("status") == "PASS" else 1)
    if args.command == "rotation-create":
        result = create_root_rotation(root, Path(args.old_private_key).resolve(), args.old_key_id, args.new_key_id, Path(args.new_public_key).resolve(), args.effective_at, args.reason, Path(args.out).resolve())
        print(json.dumps({"status": "PASS", "rotation": str(result)}, indent=2))
        return
    if args.command == "rotation-check":
        result = verify_root_rotation(root, Path(args.file).resolve(), Path(args.new_public_key).resolve() if args.new_public_key else None)
        print(json.dumps(result, indent=2) if args.json else f"{result.get('status')} {result.get('reason','')}".strip())
        raise SystemExit(0 if result.get("status") == "PASS" else 1)
    if args.command == "audit-check":
        result = check_audit_chain(root / AUDIT_FILE)
        print(json.dumps(result, indent=2) if args.json else f"{result.get('status')} {result.get('reason', '')}".strip())
        raise SystemExit(0 if result.get("status") == "PASS" else 1)
    if args.command == "anchor-check":
        doc = root_doc(root)
        anchor = doc.get("anchor") or {}
        raw = load_public_key_bytes(str(anchor.get("public_key", "")))
        actual = fingerprint_public_key(raw)
        expected = args.pinned_root_fingerprint or str(anchor.get("fingerprint_sha256", ""))
        result = {"status": "PASS" if actual.lower() == expected.lower() else "FAIL", "key_id": anchor.get("key_id"), "fingerprint_sha256": actual, "pinned": bool(args.pinned_root_fingerprint)}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"{result['status']} ROOT_ANCHOR")
        raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
