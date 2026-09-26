from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "uaf.py"
INIT = ROOT / "tools" / "uaf_init.py"
CRYPTO = ROOT / "tools" / "uaf_crypto.py"
OPS = ROOT / "tools" / "uaf_federation_ops.py"
CHECK = ROOT / "tools" / "uaf_check.py"


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=cwd, text=True, capture_output=True)


def gen_key(tmp: Path, name: str) -> tuple[Path, Path]:
    out = tmp / name
    out.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    priv = out / f"{name}.private.pem"
    pub = out / f"{name}.public.pem"
    priv.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    pub.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    return priv, pub


def init_project(tmp_path: Path, name: str) -> Path:
    project = tmp_path / name
    p = run(str(INIT), str(project), "--profile", "full", "--extension", "v2.1")
    assert p.returncode == 0, p.stdout + p.stderr
    return project


def trust_init(project: Path, tmp: Path, name: str = "ROOT") -> tuple[Path, Path]:
    priv, pub = gen_key(tmp, name)
    p = run(str(CRYPTO), "trust-init", str(project), "--key-id", name, "--public-key", str(pub))
    assert p.returncode == 0, p.stdout + p.stderr
    return priv, pub


def test_v21_scaffold_and_mode(tmp_path: Path):
    project = init_project(tmp_path, "mode")
    ops = project / ".ai/federation/ops"
    for rel in ["MODE.yaml", "CURSORS.yaml", "BUNDLES.yaml", "REVOCATIONS.yaml", "CHECKPOINTS.yaml", "CONFLICTS.yaml", "OBSERVABILITY.jsonl"]:
        assert (ops / rel).exists()
    trust = project / ".ai/agents/TRUST.yaml"
    before = trust.read_bytes()
    for mode in ["OFFLINE", "PARTITIONED", "RECOVERING", "ONLINE"]:
        p = run(str(OPS), "mode", str(project), mode)
        assert p.returncode == 0, p.stdout + p.stderr
    assert trust.read_bytes() == before
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
    assert str(manifest["extensions"]["version"]) == "2.1"
    assert manifest["protocols"]["federation_ops"] == "UAAF-FED-2.1"


def test_sync_bundle_idempotency_and_cursor(tmp_path: Path):
    a = init_project(tmp_path, "a")
    b = init_project(tmp_path, "b")
    a_priv, _a_pub = trust_init(a, tmp_path / "keys_a", "ROOT-A")
    b_priv, _b_pub = trust_init(b, tmp_path / "keys_b", "ROOT-B")
    # Local federation identity uses v2.0 primitives; bootstrap identities directly.
    ident_a = {"schema_version": "2.0", "identity": {"project_id": "project-a", "agent_id": "AGENT-A", "machine_id": "M-A", "key_id": "ROOT-A", "algorithm": "Ed25519", "status": "ACTIVE"}}
    ident_b = {"schema_version": "2.0", "identity": {"project_id": "project-b", "agent_id": "AGENT-B", "machine_id": "M-B", "key_id": "ROOT-B", "algorithm": "Ed25519", "status": "ACTIVE"}}
    # Use crypto + federation-compatible public keys for actual peer setup via CLI helper.
    # Populate deterministic public key records from trust roots.
    root_a = yaml.safe_load((a / ".ai/trust/ROOT.yaml").read_text())
    root_b = yaml.safe_load((b / ".ai/trust/ROOT.yaml").read_text())
    for proj, ident, rootdoc, keyid in [(a, ident_a, root_a, "ROOT-A"), (b, ident_b, root_b, "ROOT-B")]:
        raw = base64.b64decode(rootdoc["anchor"]["public_key"])
        ident["identity"]["public_key"] = base64.b64encode(raw).decode()
        ident["identity"]["fingerprint_sha256"] = rootdoc["anchor"]["fingerprint_sha256"]
        body = proj / ".ai/federation/IDENTITY.yaml"
        body.write_text(yaml.safe_dump(ident, sort_keys=False))
        sig = run(str(ROOT / "tools" / "uaf_federation.py"), "identity-init", str(proj), "--project-id", ident["identity"]["project_id"], "--agent-id", ident["identity"]["agent_id"], "--machine-id", ident["identity"]["machine_id"], "--key-id", keyid, "--public-key", str(tmp_path / ("keys_a" if keyid == "ROOT-A" else "keys_b") / keyid / f"{keyid}.public.pem"), "--root-private-key", str(a_priv if keyid == "ROOT-A" else b_priv), "--root-key-id", keyid)
        assert sig.returncode == 0, sig.stdout + sig.stderr
    # Import B into A.
    p = run(str(ROOT / "tools" / "uaf_federation.py"), "peer-import", str(a), "--peer-id", "PEER-B", "--identity", str(b / ".ai/federation/IDENTITY.yaml"), "--identity-sig", str(b / ".ai/federation/IDENTITY.yaml.sig"), "--root-public-key", str(tmp_path / "keys_b" / "ROOT-B" / "ROOT-B.public.pem"), "--allowed-action", "state-push", "--max-risk", "HIGH")
    assert p.returncode == 0, p.stdout + p.stderr
    # A revocation created by the remote root must propagate through the signed sync bundle.
    rp = run(str(OPS), "revoke", str(b), "--target-type", "agent", "--target-id", "AGENT-B", "--reason", "compromised", "--private-key", str(b_priv), "--key-id", "ROOT-B")
    assert rp.returncode == 0, rp.stdout + rp.stderr
    out = tmp_path / "sync.yaml"
    p = run(str(OPS), "sync-export", str(b), "--out", str(out), "--private-key", str(b_priv), "--key-id", "ROOT-B", "--audience-project", "project-a", "--peer-id", "PEER-B")
    assert p.returncode == 0, p.stdout + p.stderr
    # A's peer expects key ROOT-B and the envelope sender project-b.
    # Normalize peer key id for this fixture.
    peers = yaml.safe_load((a / ".ai/federation/PEERS.yaml").read_text())
    peers["peers"][0]["key_id"] = "ROOT-B"
    peers["peers"][0]["identity_public_key"] = ident_b["identity"]["public_key"]
    (a / ".ai/federation/PEERS.yaml").write_text(yaml.safe_dump(peers, sort_keys=False))
    p = run(str(OPS), "sync-import", str(a), "--file", str(out))
    assert p.returncode == 0, p.stdout + p.stderr
    revs = yaml.safe_load((a / ".ai/federation/ops/REVOCATIONS.yaml").read_text())
    assert revs["revocation_epoch"] == 1
    assert revs["entries"][0]["target_id"] == "AGENT-B"
    p2 = run(str(OPS), "sync-import", str(a), "--file", str(out))
    assert p2.returncode == 1
    assert "REPLAY_DETECTED" in p2.stdout or "SYNC_BUNDLE_REPLAY" in p2.stdout
    cursors = yaml.safe_load((a / ".ai/federation/ops/CURSORS.yaml").read_text())
    assert cursors["peers"]["PEER-B"]["cursor"] == 0


def test_conflict_lifecycle_requires_evidence(tmp_path: Path):
    project = init_project(tmp_path, "conflict")
    sys.path.insert(0, str(ROOT / "tools"))
    from uaf_federation_ops import conflict_propose, conflict_transition, conflict_list
    created = conflict_propose(project, "feature.flag", "disable", "AGENT-A", "EVD-100")
    assert created["status"] == "PASS"
    cid = conflict_list(project)["conflicts"][0]["conflict_id"]
    bad = conflict_transition(project, cid, "RESOLVED", "AGENT-A")
    assert bad["status"] == "FAIL"
    assert bad["reason"] == "INVALID_CONFLICT_TRANSITION"
    approved = conflict_transition(project, cid, "APPROVED", "AGENT-A")
    assert approved["status"] == "PASS"
    resolved = conflict_transition(project, cid, "RESOLVED", "AGENT-A")
    assert resolved["status"] == "PASS"


def test_revocation_monotonic_and_root_required(tmp_path: Path):
    project = init_project(tmp_path, "revoke")
    root_priv, _root_pub = trust_init(project, tmp_path / "keys", "ROOT")
    p = run(str(OPS), "revoke", str(project), "--target-type", "peer", "--target-id", "PEER-X", "--reason", "compromised", "--private-key", str(root_priv), "--key-id", "ROOT")
    assert p.returncode == 0, p.stdout + p.stderr
    doc = yaml.safe_load((project / ".ai/federation/ops/REVOCATIONS.yaml").read_text())
    assert doc["revocation_epoch"] == 1
    assert doc["entries"][0]["revocation_epoch"] == 1
    # Non-root key must not create a revocation.
    bad_priv, _ = gen_key(tmp_path / "bad", "BAD")
    p = run(str(OPS), "revoke", str(project), "--target-type", "peer", "--target-id", "PEER-Y", "--reason", "test", "--private-key", str(bad_priv), "--key-id", "BAD")
    assert p.returncode == 1
    assert "REVOCATION_REQUIRES_TRUST_ROOT" in p.stdout


def test_checkpoint_recovery_preserves_replay_and_requires_recovering(tmp_path: Path):
    project = init_project(tmp_path, "recovery")
    root_priv, _root_pub = trust_init(project, tmp_path / "keys", "ROOT")
    # Add deterministic state using v2.0 federation tool after identity bootstrap.
    ident = yaml.safe_load((project / ".ai/trust/ROOT.yaml").read_text())["anchor"]
    fdir = project / ".ai/federation"
    identity = {"schema_version": "2.0", "identity": {"project_id": "recovery", "agent_id": "AGENT-R", "machine_id": "M-R", "key_id": "ROOT", "algorithm": "Ed25519", "public_key": ident["public_key"], "fingerprint_sha256": ident["fingerprint_sha256"], "created_at": "2026-09-26T00:00:00Z", "status": "ACTIVE"}}
    fdir.joinpath("IDENTITY.yaml").write_text(yaml.safe_dump(identity, sort_keys=False))
    p = run(str(ROOT / "tools" / "uaf_federation.py"), "state", str(project), "set", "--key", "feature.flag", "--value", "on")
    assert p.returncode == 0
    out = tmp_path / "cp.yaml"
    p = run(str(OPS), "checkpoint-create", str(project), "--out", str(out), "--private-key", str(root_priv), "--key-id", "ROOT")
    assert p.returncode == 0, p.stdout + p.stderr
    p = run(str(OPS), "checkpoint-verify", str(project), "--file", str(out))
    assert p.returncode == 0
    p = run(str(OPS), "checkpoint-recover", str(project), "--file", str(out))
    assert p.returncode == 1
    assert "RECOVERY_REQUIRES_RECOVERING_MODE" in p.stdout
    (project / ".ai/federation/ops/MODE.yaml").write_text("schema_version: '2.1'\nmode: RECOVERING\nupdated_at: null\n")
    p = run(str(OPS), "checkpoint-recover", str(project), "--file", str(out))
    assert p.returncode == 0, p.stdout + p.stderr
    assert (project / ".ai/federation/state/RECOVERY-BACKUP.yaml").exists()
    replay = yaml.safe_load((project / ".ai/federation/REPLAY.yaml").read_text())
    assert isinstance(replay["seen"], list)


def test_observability_metadata_only_and_doctor(tmp_path: Path):
    project = init_project(tmp_path, "observe")
    p = run(str(OPS), "observe", str(project))
    assert p.returncode == 0
    lines = (project / ".ai/federation/ops/OBSERVABILITY.jsonl").read_text().splitlines()
    assert lines
    row = yaml.safe_load(lines[0])
    forbidden = {"prompt", "source_content", "secret", "private_key", "token"}
    assert not forbidden.intersection(row)
    p = run(str(CLI), "doctor", str(project), "--level", "full")
    assert p.returncode == 0, p.stdout + p.stderr



def test_v21_strict_conformance(tmp_path: Path):
    project = init_project(tmp_path, "strict21")
    root_priv, root_pub = trust_init(project, tmp_path / "strict-root", "ROOT-21")
    # Promote strict cryptographic requirements and sign every required v1.9 object.
    root_path = project / ".ai/trust/ROOT.yaml"
    root_doc = yaml.safe_load(root_path.read_text())
    root_doc["policy"]["cryptographic_required"] = True
    root_doc["policy"]["required_purposes"] += ["federation-identity", "federation-policy", "federation-handoff", "federation-state"]
    root_path.write_text(yaml.safe_dump(root_doc, sort_keys=False))
    (project / ".ai/trust/KEYS.yaml.sig").unlink(missing_ok=True)
    for rel, purpose in [
        (".ai/trust/ROOT.yaml", "trust-root"),
        (".ai/trust/KEYS.yaml", "trust-keys"),
        (".ai/agents/TRUST.yaml", "trust-policy"),
        (".ai/agents/DELEGATIONS.yaml", "delegations"),
    ]:
        p = run(str(CRYPTO), "sign", str(project), "--file", str(project / rel), "--private-key", str(root_priv), "--key-id", "ROOT-21", "--purpose", purpose)
        assert p.returncode == 0, p.stdout + p.stderr
    # Federation identity and policy.
    p = run(str(ROOT / "tools" / "uaf_federation.py"), "identity-init", str(project), "--project-id", "strict21", "--agent-id", "AGENT-21", "--machine-id", "M-21", "--key-id", "ROOT-21", "--public-key", str(root_pub), "--root-private-key", str(root_priv), "--root-key-id", "ROOT-21")
    assert p.returncode == 0, p.stdout + p.stderr
    p = run(str(ROOT / "tools" / "uaf_federation.py"), "policy-init", str(project))
    assert p.returncode == 0
    p = run(str(ROOT / "tools" / "uaf_federation.py"), "policy-sign", str(project), "--private-key", str(root_priv), "--key-id", "ROOT-21")
    assert p.returncode == 0, p.stdout + p.stderr
    (project / ".ai/core/CONTEXT.md").write_text("Strict v2.1 federation fixture context.\n")
    (project / ".ai/core/CONVENTIONS.md").write_text("Strict v2.1 conventions.\n")
    mem = project / ".ai/memory/entries"; mem.mkdir(parents=True, exist_ok=True)
    (mem / "MEM-0001.md").write_text("---\nid: MEM-0001\ntype: LESSON\nstatus: ACTIVE\ncreated: 2026-09-26\nupdated: 2026-09-26\nauthority: REFERENCE\nconfidence: HIGH\nstability: STABLE\n---\n\nStrict federation fixture.\n")
    impact = project / ".ai/context/IMPACT-GRAPH.yaml"; impact.parent.mkdir(parents=True, exist_ok=True)
    impact.write_text("schema_version: '1.1'\nmode: advisory\nchanged_paths: []\nnodes: []\n")
    git = subprocess.run(["git", "init", "-q"], cwd=project, text=True, capture_output=True)
    assert git.returncode == 0, git.stderr
    subprocess.run(["git", "config", "user.email", "uaf@example.invalid"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "UAAF Test"], cwd=project, check=True)
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=project, check=True)
    run(str(ROOT / "tools" / "uaf_git_trace.py"), str(project), "snapshot")
    run(str(ROOT / "tools" / "uaf_rce_strong.py"), str(project), "snapshot")
    check = run(str(CHECK), str(project), "--level", "full", "--strict")
    assert check.returncode == 0, check.stdout + check.stderr
    assert "CONF-V21" not in check.stdout


def test_v20_does_not_receive_v21_ops(tmp_path: Path):
    project = tmp_path / "legacy"
    p = run(str(INIT), str(project), "--profile", "full", "--extension", "v2.0")
    assert p.returncode == 0
    assert not (project / ".ai/federation/ops").exists()
