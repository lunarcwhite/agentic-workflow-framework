from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import uaf_crypto
import uaf_federation
INIT = ROOT / "tools/uaf_init.py"
CRYPTO = ROOT / "tools/uaf_crypto.py"
FED = ROOT / "tools/uaf_federation.py"
CHECK = ROOT / "tools/uaf_check.py"
DOCTOR = ROOT / "tools/uaf_doctor.py"
CLI = ROOT / "tools/uaf.py"


def run(*args: str, timeout: int = 25):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, timeout=timeout)


def init(tmp_path: Path, name: str) -> Path:
    project = tmp_path / name.lower()
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v2.0", "--name", name)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return project


def keygen(tmp_path: Path, key_id: str) -> tuple[Path, Path, str]:
    out = tmp_path / key_id.lower()
    data = uaf_crypto.generate_keypair(out, key_id)
    return Path(data["private_key"]), Path(data["public_key"]), data["fingerprint_sha256"]

def provision(root: Path, tmp_path: Path, project_id: str, agent_id: str, machine_id: str, root_key_id: str, identity_key_id: str):
    root_priv, root_pub, root_fp = keygen(tmp_path, root_key_id)
    uaf_crypto.initialize_trust(root, root_key_id, root_pub)
    identity_priv, identity_pub, identity_fp = keygen(tmp_path, identity_key_id)
    uaf_federation.identity_init(root, project_id, agent_id, machine_id, identity_key_id, identity_pub, root_priv, root_key_id)

    root_path = root / ".ai/trust/ROOT.yaml"
    root_doc = yaml.safe_load(root_path.read_text())
    root_doc["policy"]["cryptographic_required"] = True
    root_doc["policy"]["required_purposes"] += ["federation-identity", "federation-policy", "federation-handoff", "federation-state"]
    root_path.write_text(yaml.safe_dump(root_doc, sort_keys=False))
    policy = uaf_federation.policy_init(root)
    for rel, purpose in [
        (".ai/trust/ROOT.yaml", "trust-root"),
        (".ai/trust/KEYS.yaml", "trust-keys"),
        (".ai/agents/TRUST.yaml", "trust-policy"),
        (".ai/agents/DELEGATIONS.yaml", "delegations"),
    ]:
        sig = uaf_crypto.sign_file(root, root / rel, root_priv, root_key_id, purpose)
        uaf_crypto.append_audit(root, {"action": "SIGN", "file": rel, "key_id": root_key_id, "purpose": purpose, "signature": str(sig.relative_to(root))})
    uaf_federation.policy_sign(root, root_priv, root_key_id)
    return {"root_priv": root_priv, "root_pub": root_pub, "root_fp": root_fp, "id_priv": identity_priv, "id_pub": identity_pub, "id_fp": identity_fp, "id_key": identity_key_id, "root_key": root_key_id}

def test_v20_initializer_doctor_and_legacy_cleanup(tmp_path: Path):
    project = init(tmp_path, "Init")
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
    assert manifest["framework"]["version"] == "2.0.0"
    assert manifest["protocols"]["federation"] == "UAAF-FED-2.0"
    for rel in [
        ".ai/federation/IDENTITY.yaml", ".ai/federation/PEERS.yaml",
        ".ai/federation/FEDERATION-POLICY.yaml", ".ai/federation/REPLAY.yaml",
        ".ai/federation/state/VECTOR.yaml", ".ai/federation/state/REGISTERS.yaml",
        ".ai/federation/state/CONFLICTS.yaml",
    ]:
        assert (project / rel).exists()
    doctor = run(str(DOCTOR), str(project), "--level", "full")
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "FEDERATION 0" in doctor.stdout

    legacy = tmp_path / "legacy"
    proc = run(str(INIT), str(legacy), "--profile", "full", "--extension", "v1.9")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not (legacy / ".ai/federation").exists()


def test_cross_project_identity_and_signed_handoff_replay(tmp_path: Path):
    a = init(tmp_path, "ProjectA")
    b = init(tmp_path, "ProjectB")
    a_keys = provision(a, tmp_path / "a", "project-a", "AGENT-A", "MACHINE-A", "ROOT-A", "IDENT-A")
    b_keys = provision(b, tmp_path / "b", "project-b", "AGENT-B", "MACHINE-B", "ROOT-B", "IDENT-B")

    imported = run(
        str(FED), "peer-import", str(a), "--peer-id", "PEER-B",
        "--identity", str(b / ".ai/federation/IDENTITY.yaml"),
        "--identity-sig", str(b / ".ai/federation/IDENTITY.yaml.sig"),
        "--root-public-key", str(b_keys["root_pub"]),
        "--allowed-action", "handoff", "--allowed-action", "state-push", "--max-risk", "HIGH",
    )
    assert imported.returncode == 0, imported.stdout + imported.stderr

    handoff = b / "handoff.md"
    handoff.write_text("# Handoff\n\nCompleted identity federation bootstrap.\n")
    signed = run(str(FED), "handoff-sign", str(b), "--file", str(handoff), "--private-key", str(b_keys["id_priv"]), "--key-id", "IDENT-B", "--audience-project", "project-a", "--audience-agent", "AGENT-A", "--ttl", "900", "--risk", "MEDIUM")
    assert signed.returncode == 0, signed.stdout + signed.stderr
    bundle = Path(b / json.loads(json.dumps({"file": signed.stdout.split("FILE ", 1)[1].strip()}))["file"])
    verify = run(str(FED), "handoff-verify", str(a), "--file", str(bundle))
    assert verify.returncode == 0, verify.stdout + verify.stderr
    replay = run(str(FED), "handoff-verify", str(a), "--file", str(bundle))
    assert replay.returncode == 1
    assert "REPLAY_DETECTED" in replay.stdout


def test_handoff_tampered_peer_identity_fails_closed(tmp_path: Path):
    a = init(tmp_path, "A")
    b = init(tmp_path, "B")
    provision(a, tmp_path / "a", "project-a", "AGENT-A", "MACHINE-A", "ROOT-A", "IDENT-A")
    b_keys = provision(b, tmp_path / "b", "project-b", "AGENT-B", "MACHINE-B", "ROOT-B", "IDENT-B")
    assert run(str(FED), "peer-import", str(a), "--peer-id", "PEER-B", "--identity", str(b / ".ai/federation/IDENTITY.yaml"), "--identity-sig", str(b / ".ai/federation/IDENTITY.yaml.sig"), "--root-public-key", str(b_keys["root_pub"]), "--allowed-action", "handoff", "--max-risk", "HIGH").returncode == 0
    handoff = b / "h.md"; handoff.write_text("h")
    signed = run(str(FED), "handoff-sign", str(b), "--file", str(handoff), "--private-key", str(b_keys["id_priv"]), "--key-id", "IDENT-B", "--audience-project", "project-a", "--ttl", "900")
    assert signed.returncode == 0
    bundle_rel = signed.stdout.split("FILE ", 1)[1].strip()
    bundle = b / bundle_rel
    peer_identity = a / ".ai/federation/peers/PEER-B/IDENTITY.yaml"
    peer_doc = yaml.safe_load(peer_identity.read_text())
    peer_doc["identity"]["agent_id"] = "AGENT-TAMPERED"
    peer_identity.write_text(yaml.safe_dump(peer_doc, sort_keys=False))
    verify = run(str(FED), "handoff-verify", str(a), "--file", str(bundle))
    assert verify.returncode == 1
    assert "PEER_IDENTITY_INVALID" in verify.stdout


def test_distributed_state_merge_and_conflict(tmp_path: Path):
    a = init(tmp_path, "Astate")
    b = init(tmp_path, "Bstate")
    a_keys = provision(a, tmp_path / "a", "project-a", "AGENT-A", "MACHINE-A", "ROOT-A", "IDENT-A")
    b_keys = provision(b, tmp_path / "b", "project-b", "AGENT-B", "MACHINE-B", "ROOT-B", "IDENT-B")
    assert run(str(FED), "peer-import", str(a), "--peer-id", "PEER-B", "--identity", str(b / ".ai/federation/IDENTITY.yaml"), "--identity-sig", str(b / ".ai/federation/IDENTITY.yaml.sig"), "--root-public-key", str(b_keys["root_pub"]), "--allowed-action", "state-push", "--max-risk", "HIGH").returncode == 0
    assert run(str(FED), "state", str(a), "set", "--key", "feature.flag", "--value", "A").returncode == 0
    assert run(str(FED), "state", str(b), "set", "--key", "feature.flag", "--value", "B").returncode == 0
    out = tmp_path / "state-b.yaml"
    exp = run(str(FED), "state", str(b), "export", "--out", str(out), "--private-key", str(b_keys["id_priv"]), "--key-id", "IDENT-B", "--audience-project", "project-a")
    assert exp.returncode == 0, exp.stdout + exp.stderr
    imp = run(str(FED), "state", str(a), "import", "--file", str(out))
    assert imp.returncode == 0, imp.stdout + imp.stderr
    assert "CONFLICTS 1" in imp.stdout
    conflicts = yaml.safe_load((a / ".ai/federation/state/CONFLICTS.yaml").read_text())
    assert conflicts["conflicts"][0]["status"] == "UNRESOLVED"


def test_federation_policy_denies_unallowlisted_action(tmp_path: Path):
    a = init(tmp_path, "PolicyA")
    b = init(tmp_path, "PolicyB")
    provision(a, tmp_path / "a", "project-a", "AGENT-A", "MACHINE-A", "ROOT-A", "IDENT-A")
    b_keys = provision(b, tmp_path / "b", "project-b", "AGENT-B", "MACHINE-B", "ROOT-B", "IDENT-B")
    assert run(str(FED), "peer-import", str(a), "--peer-id", "PEER-B", "--identity", str(b / ".ai/federation/IDENTITY.yaml"), "--identity-sig", str(b / ".ai/federation/IDENTITY.yaml.sig"), "--root-public-key", str(b_keys["root_pub"]), "--allowed-action", "handoff", "--max-risk", "LOW").returncode == 0
    assert run(str(FED), "state", str(b), "set", "--key", "x", "--value", "1").returncode == 0
    bundle = tmp_path / "state.yaml"
    assert run(str(FED), "state", str(b), "export", "--out", str(bundle), "--private-key", str(b_keys["id_priv"]), "--key-id", "IDENT-B", "--audience-project", "project-a").returncode == 0
    denied = run(str(FED), "state", str(a), "import", "--file", str(bundle))
    assert denied.returncode == 1
    assert "ACTION_NOT_ALLOWED" in denied.stdout


def test_v20_strict_signed_conformance_and_cli(tmp_path: Path):
    project = init(tmp_path, "Strict20")
    keys = provision(project, tmp_path / "strict", "strict-project", "AGENT-STRICT", "MACHINE-STRICT", "ROOT-S", "IDENT-S")
    # Prepare explicit fixture evidence so strict cumulative v1.x checks have no placeholder warnings.
    memory_dir = project / ".ai/memory/entries"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "MEM-0001.md").write_text("---\nid: MEM-0001\ntype: LESSON\nstatus: ACTIVE\ncreated: 2026-09-26\nupdated: 2026-09-26\nauthority: REFERENCE\nconfidence: HIGH\nstability: STABLE\n---\n\nStrict federation fixture knowledge.\n", encoding="utf-8")
    impact = project / ".ai/context/IMPACT-GRAPH.yaml"
    impact.parent.mkdir(parents=True, exist_ok=True)
    impact.write_text(yaml.safe_dump({"schema_version": "1.1", "mode": "advisory", "changed_paths": [], "nodes": []}, sort_keys=False), encoding="utf-8")
    baseline = project / ".ai/health/GIT-BASELINE.yaml"
    baseline.write_text(yaml.safe_dump({"schema_version": "1.3", "generated_at": "2026-09-26T00:00:00Z", "repository": str(project), "head": "a" * 40, "branch": "main", "dirty": False, "dirty_paths": []}, sort_keys=False), encoding="utf-8")
    (project / ".ai/core/CONTEXT.md").write_text("Northstar strict federation fixture context.\n", encoding="utf-8")
    (project / ".ai/core/CONVENTIONS.md").write_text("Northstar fixture conventions.\n", encoding="utf-8")
    # Strong RCE baseline is required by the cumulative v1.x checks.
    assert run(str(CLI), "rce", str(project), "snapshot").returncode == 0
    proc = run(str(CHECK), str(project), "--level", "full", "--strict")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    doctor = run(str(DOCTOR), str(project), "--level", "full", "--strict")
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    fed_doc = run(str(CLI), "federation", "doctor", str(project), "--json")
    assert fed_doc.returncode == 0, fed_doc.stdout + fed_doc.stderr


def test_federation_identity_schema_tamper_and_audience(tmp_path: Path):
    a = init(tmp_path, "AudienceA")
    b = init(tmp_path, "AudienceB")
    a_keys = provision(a, tmp_path / "a", "project-a", "AGENT-A", "MACHINE-A", "ROOT-A", "IDENT-A")
    b_keys = provision(b, tmp_path / "b", "project-b", "AGENT-B", "MACHINE-B", "ROOT-B", "IDENT-B")
    assert run(str(FED), "peer-import", str(a), "--peer-id", "PEER-B", "--identity", str(b / ".ai/federation/IDENTITY.yaml"), "--identity-sig", str(b / ".ai/federation/IDENTITY.yaml.sig"), "--root-public-key", str(b_keys["root_pub"]), "--allowed-action", "handoff", "--max-risk", "HIGH").returncode == 0
    h = b / "h.md"; h.write_text("h")
    signed = run(str(FED), "handoff-sign", str(b), "--file", str(h), "--private-key", str(b_keys["id_priv"]), "--key-id", "IDENT-B", "--audience-project", "wrong-project")
    assert signed.returncode == 0
    bundle = b / signed.stdout.split("FILE ", 1)[1].strip()
    bad = run(str(FED), "handoff-verify", str(a), "--file", str(bundle))
    assert bad.returncode == 1
    assert "AUDIENCE_MISMATCH" in bad.stdout


def test_federation_policy_signature_tamper_fails_conformance(tmp_path: Path):
    project = init(tmp_path, "PolicySig")
    keys = provision(project, tmp_path / "policy-sig", "policy-project", "AGENT-POLICY", "MACHINE-POLICY", "ROOT-P", "IDENT-P")
    # The fixture is now cryptographically initialized and policy signed.
    policy = project / ".ai/federation/FEDERATION-POLICY.yaml"
    data = yaml.safe_load(policy.read_text())
    data["default_deny"] = False
    policy.write_text(yaml.safe_dump(data, sort_keys=False))
    check = run(str(CHECK), str(project), "--level", "full", "--strict")
    assert check.returncode == 1
    assert "CONF-V20-018" in check.stdout
