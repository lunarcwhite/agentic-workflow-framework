#!/usr/bin/env python3
"""Fresh-process-independent UAAF v3.0 integration validation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import os
import shutil
import tempfile
from pathlib import Path

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


INIT = load_module("uaf_init", ROOT / "tools/uaf_init.py")
CRYPTO = load_module("uaf_crypto", ROOT / "tools/uaf_crypto.py")
FED = load_module("uaf_federation", ROOT / "tools/uaf_federation.py")
KEYOPS = load_module("uaf_key_ops", ROOT / "tools/uaf_key_ops.py")
RT = load_module("uaf_federation_runtime", ROOT / "tools/uaf_federation_runtime.py")


def make_key(path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    private_bytes = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    path.write_bytes(private_bytes)
    path.with_name(path.name.replace(".private.pem", ".ed25519.pem")).write_bytes(private_bytes)
    pub = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    path.with_name(path.name.replace(".private.pem", ".public.pem")).write_bytes(pub)


def setup(root: Path, project_id: str, key_id: str, root_private: Path, key_dir: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    # Mirror initializer semantics by invoking its CLI in-process through argv.
    old = os.sys.argv
    try:
        os.sys.argv = ["uaf_init.py", str(root), "--profile", "full", "--extension", "v3.0", "--name", project_id.lower(), "--type", "backend"]
        try:
            INIT.main()
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
    finally:
        os.sys.argv = old
    root_id = root_private.name.replace(".private.pem", "")
    CRYPTO.initialize_trust(root, root_id, key_dir / f"{root_id}.public.pem")
    FED.identity_init(
        root,
        project_id,
        "AGENT-HUMAN",
        f"MACHINE-{project_id}",
        key_id,
        key_dir / f"{key_id}.public.pem",
        root_private,
        root_id,
    )
    for purpose in [RT.PURPOSE_TASK, RT.PURPOSE_RESULT, RT.PURPOSE_CANCEL, RT.PURPOSE_LEASE]:
        KEYOPS.bind(root, key_id, purpose, key_dir / f"{key_id}.public.pem")


def write_routes(root: Path) -> None:
    (root / RT.ROUTES).write_text(
        yaml.safe_dump(
            {
                "schema_version": "3.0", "default_deny": True,
                "peers": [{
                    "peer_id": "PEER-REMOTE", "status": "ACTIVE", "priority": 10,
                    "capabilities": ["backend", "write", "verify"], "execution_actions": ["write", "verify"],
                    "domains": ["backend"], "max_risk": "HIGH", "concurrent_limit": 2,
                }],
            }, sort_keys=False), encoding="utf-8")


def replace_peer(target: Path, peer_id: str, source: Path, root_public: Path) -> None:
    FED.peer_import(target, peer_id, source / ".ai/federation/IDENTITY.yaml", source / ".ai/federation/IDENTITY.yaml.sig", root_public, ["write", "verify"], "HIGH")


def ns(**kwargs):
    return argparse.Namespace(**kwargs)


def main() -> None:
    base = Path(tempfile.mkdtemp(prefix="uaf-v30-direct-"))
    keys = base / "keys"; keys.mkdir()
    for kid in ["OROOT", "O1", "RROOT", "R1"]:
        make_key(keys / f"{kid}.private.pem")
    origin = base / "origin"; remote = base / "remote"
    os.environ["UAAF_KEY_DIR"] = str(keys)
    try:
        setup(origin, "ORIGIN", "O1", keys / "OROOT.private.pem", keys)
        setup(remote, "REMOTE", "R1", keys / "RROOT.private.pem", keys)
        write_routes(origin)
        replace_peer(origin, "PEER-REMOTE", remote, keys / "RROOT.public.pem")
        replace_peer(remote, "PEER-ORIGIN", origin, keys / "OROOT.public.pem")

        route = RT.cmd_route(ns(path=str(origin), capability=["backend"], domain="backend", risk="HIGH", select=True))
        assert route["selected"]["peer_id"] == "PEER-REMOTE"

        args = dict(path=str(origin), task_id="TASK-3001", agent_id="AGENT-HUMAN", intent_id="INT-3001", parent_task_id="", parent_provenance="", objective="execute backend change", scope_in="", scope_out="", action=["write"], capability=["backend"], domain="backend", risk="HIGH", min_evidence="E3", lease_seconds=60, renewable=False, max_files=20, max_diff_lines=200, requirements_file=None, peer_id="PEER-REMOTE", target_agent="AGENT-HUMAN", key_ref="O1", private_key=None, out=None)
        delegate = RT.cmd_delegate(ns(**args))
        contract_file = origin / RT.TASK_DIR / "TASK-3001.yaml"
        shutil.copy2(contract_file, remote / RT.TASK_DIR / "TASK-3001.yaml")
        accept = RT.cmd_accept(ns(path=str(remote), contract_file=str(remote / RT.TASK_DIR / "TASK-3001.yaml"), agent_id="AGENT-HUMAN", lease_seconds=0))
        lease_id = accept["lease"]["lease_id"]
        shutil.copy2(remote / RT.lease_receipt_path(remote, "TASK-3001"), origin / RT.lease_receipt_path(origin, "TASK-3001"))
        RT.cmd_start(ns(path=str(remote), task_id="TASK-3001"))
        artifact = remote / "change.txt"; artifact.write_text("delegated change\n", encoding="utf-8")
        input_result = base / "result.yaml"; input_result.write_text(yaml.safe_dump({"status": "SUCCEEDED", "summary": "complete", "evidence": [str(artifact)]}), encoding="utf-8")
        result = RT.cmd_complete(ns(path=str(remote), task_id="TASK-3001", lease_id=lease_id, agent_id="AGENT-HUMAN", result_status="SUCCEEDED", summary="", result_file=str(input_result), key_ref="R1", private_key=None, out=None))
        assert result["status"] == "PASS" and result["task_id"] == "TASK-3001"
        result_path = remote / RT.RESULT_DIR / "TASK-3001.yaml"
        shutil.copy2(result_path, origin / RT.RESULT_DIR / "TASK-3001.yaml")
        verified = RT.cmd_verify_result(ns(path=str(origin), result_file=str(origin / RT.RESULT_DIR / "TASK-3001.yaml")))
        assert verified["status"] == "VERIFIED" and verified["signature_verified"]
        delivered = RT.cmd_deliver(ns(path=str(origin), result_file=str(origin / RT.RESULT_DIR / "TASK-3001.yaml")))
        assert delivered["status"] == "PASS"

        # A late cancellation must not resurrect or overwrite a completed lease.
        late_cancel = RT.cmd_cancel(ns(path=str(origin), task_id="TASK-3001", lease_id=lease_id, reason="too late", key_ref="O1", private_key=None, out=None))
        late_file = remote / RT.CANCEL_DIR / "TASK-3001.yaml"; shutil.copy2(origin / RT.CANCEL_DIR / "TASK-3001.yaml", late_file)
        try:
            RT.cmd_apply_cancel(ns(path=str(remote), cancellation_file=str(late_file)))
            raise AssertionError("completed lease was cancelled")
        except ValueError as exc:
            assert str(exc) == "CANCELLATION_TOO_LATE:COMPLETED"

        # Tamper with result signature-bound payload.
        tampered = yaml.safe_load(result_path.read_text())
        tampered["result"]["summary"] = "tampered"
        tampered_path = origin / RT.RESULT_DIR / "TASK-3001-tampered.yaml"
        tampered_path.write_text(yaml.safe_dump(tampered, sort_keys=False), encoding="utf-8")
        try:
            RT.cmd_verify_result(ns(path=str(origin), result_file=str(tampered_path)))
            raise AssertionError("tampered result unexpectedly verified")
        except ValueError as exc:
            assert str(exc) in {"SIGNATURE_PAYLOAD_HASH_MISMATCH", "SIGNATURE_INVALID"}

        # Trusted peer action ceilings are enforced before delegation.
        read_args = copy.deepcopy(args); read_args.update(task_id="TASK-3005", objective="read", action=["read"])
        try:
            RT.cmd_delegate(ns(**read_args))
            raise AssertionError("peer action ceiling was bypassed")
        except ValueError as exc:
            assert str(exc) == "TARGET_ROUTE_ACTION_NOT_ALLOWED"

        # Remote delete remains denied by runtime policy.
        delete_args = copy.deepcopy(args); delete_args.update(task_id="TASK-3004", objective="delete", action=["delete"])
        try:
            RT.cmd_delegate(ns(**delete_args))
            raise AssertionError("remote delete unexpectedly delegated")
        except ValueError as exc:
            assert str(exc) == "REMOTE_DELETE_DISABLED"

        # Cancellation is terminal.
        cancel_args = copy.deepcopy(args); cancel_args.update(task_id="TASK-3002", objective="cancel me", risk="LOW")
        RT.cmd_delegate(ns(**cancel_args))
        cfile = remote / RT.TASK_DIR / "TASK-3002.yaml"; shutil.copy2(origin / RT.TASK_DIR / "TASK-3002.yaml", cfile)
        a2 = RT.cmd_accept(ns(path=str(remote), contract_file=str(cfile), agent_id="AGENT-HUMAN", lease_seconds=0))
        RT.cmd_cancel(ns(path=str(origin), task_id="TASK-3002", lease_id=a2["lease"]["lease_id"], reason="operator", key_ref="O1", private_key=None, out=None))
        cancel_file = remote / RT.CANCEL_DIR / "TASK-3002.yaml"; shutil.copy2(origin / RT.CANCEL_DIR / "TASK-3002.yaml", cancel_file)
        RT.cmd_apply_cancel(ns(path=str(remote), cancellation_file=str(cancel_file)))
        try:
            RT.cmd_complete(ns(path=str(remote), task_id="TASK-3002", lease_id=a2["lease"]["lease_id"], agent_id="AGENT-HUMAN", result_status="SUCCEEDED", summary="", result_file=None, key_ref="R1", private_key=None, out=None))
            raise AssertionError("cancelled lease completed")
        except ValueError as exc:
            assert str(exc).startswith("LEASE_TERMINAL") or str(exc) == "LEASE_CANCELLED"

        # Expiry is terminal; mutate only the local lease clock to avoid sleep/flakiness.
        expire_args = copy.deepcopy(args); expire_args.update(task_id="TASK-3003", objective="expire me", risk="LOW", lease_seconds=2)
        RT.cmd_delegate(ns(**expire_args))
        efile = remote / RT.TASK_DIR / "TASK-3003.yaml"; shutil.copy2(origin / RT.TASK_DIR / "TASK-3003.yaml", efile)
        a3 = RT.cmd_accept(ns(path=str(remote), contract_file=str(efile), agent_id="AGENT-HUMAN", lease_seconds=2))
        lpath = remote / RT.LEASES; ldoc = yaml.safe_load(lpath.read_text())
        for row in ldoc["leases"]:
            if row["lease_id"] == a3["lease"]["lease_id"]:
                row["expires_at"] = "2000-01-01T00:00:00Z"
        lpath.write_text(yaml.safe_dump(ldoc, sort_keys=False), encoding="utf-8")
        swept = RT.cmd_sweep(ns(path=str(remote)))
        assert a3["lease"]["lease_id"] in swept["expired"]
        try:
            RT.cmd_complete(ns(path=str(remote), task_id="TASK-3003", lease_id=a3["lease"]["lease_id"], agent_id="AGENT-HUMAN", result_status="SUCCEEDED", summary="", result_file=None, key_ref="R1", private_key=None, out=None))
            raise AssertionError("expired lease completed")
        except ValueError as exc:
            assert str(exc).startswith("LEASE_TERMINAL") or str(exc) == "LEASE_EXPIRED"

        assert RT.cmd_check(ns(path=str(origin)))["status"] == "PASS"
        print("ALL 10/10 PASSED")
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
