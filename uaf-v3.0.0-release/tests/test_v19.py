from __future__ import annotations

import base64
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CRYPTO = ROOT / "tools/uaf_crypto.py"
CHECK = ROOT / "tools/uaf_check.py"
TRUST = ROOT / "tools/uaf_trust.py"
CLI = ROOT / "tools/uaf.py"


def run(*args: str, timeout: int = 20):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, timeout=timeout)


def init(tmp_path: Path, name: str = "V19") -> Path:
    project = tmp_path / name.lower()
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.9", "--name", name)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return project


def keygen(tmp_path: Path, key_id: str = "AGENT-ROOT-001") -> tuple[Path, Path, str]:
    out = tmp_path / "keys"
    proc = run(str(CRYPTO), "keygen", str(out), "--key-id", key_id)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    return Path(data["private_key"]), Path(data["public_key"]), data["fingerprint_sha256"]


def test_v19_initializer_conformance_and_cli(tmp_path: Path):
    project = init(tmp_path)
    for rel in [".ai/trust/ROOT.yaml", ".ai/trust/KEYS.yaml", ".ai/trust/KEY-ROTATION.yaml", ".ai/health/TRUST-CRYPTOGRAPHIC-INTEGRITY.md"]:
        assert (project / rel).exists()
    assert not list((project / ".ai/trust").glob("*.private.pem"))
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 0, check.stdout + check.stderr
    doctor = run(str(ROOT / "tools/uaf_doctor.py"), str(project), "--level", "full")
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "TRUST_CRYPTO 0" in doctor.stdout
    assert run(str(CLI), "crypto", "audit-check", str(project)).returncode == 0


def test_v19_requires_full_profile(tmp_path: Path):
    project = tmp_path / "standard"
    proc = run(str(INIT), str(project), "--profile", "standard", "--extension", "v1.9")
    assert proc.returncode == 1
    assert "profile full" in proc.stderr.lower()


def test_v19_legacy_install_does_not_emit_trust_namespace(tmp_path: Path):
    project = tmp_path / "legacy"
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.8")
    assert proc.returncode == 0, proc.stderr
    assert not (project / ".ai/trust").exists()


def test_keygen_and_trust_init(tmp_path: Path):
    project = init(tmp_path, "Init")
    private, public, fingerprint = keygen(tmp_path)
    proc = run(str(CRYPTO), "trust-init", str(project), "--key-id", "AGENT-ROOT-001", "--public-key", str(public))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    root = yaml.safe_load((project / ".ai/trust/ROOT.yaml").read_text())
    assert root["anchor"]["fingerprint_sha256"] == fingerprint
    mode = stat.S_IMODE(private.stat().st_mode)
    assert mode & stat.S_IRWXG == 0
    assert mode & stat.S_IRWXO == 0


def test_sign_verify_and_tamper_detection(tmp_path: Path):
    project = init(tmp_path, "Sign")
    private, public, fingerprint = keygen(tmp_path)
    assert run(str(CRYPTO), "trust-init", str(project), "--key-id", "AGENT-ROOT-001", "--public-key", str(public)).returncode == 0
    keys = project / ".ai/trust/KEYS.yaml"
    assert run(str(CRYPTO), "sign", str(project), "--file", str(keys), "--private-key", str(private), "--key-id", "AGENT-ROOT-001", "--purpose", "trust-keys").returncode == 0
    verify = run(str(CRYPTO), "verify", str(project), "--file", str(keys), "--purpose", "trust-keys", "--pinned-root-fingerprint", fingerprint, "--json")
    assert verify.returncode == 0, verify.stdout + verify.stderr
    keys.write_text(keys.read_text() + "# tamper\n")
    bad = run(str(CRYPTO), "verify", str(project), "--file", str(keys), "--purpose", "trust-keys")
    assert bad.returncode == 1
    assert "PAYLOAD_HASH_MISMATCH" in bad.stdout


def test_bundle_required_signatures(tmp_path: Path):
    project = init(tmp_path, "Bundle")
    private, public, fingerprint = keygen(tmp_path)
    assert run(str(CRYPTO), "trust-init", str(project), "--key-id", "AGENT-ROOT-001", "--public-key", str(public)).returncode == 0
    for rel, purpose in [(".ai/trust/ROOT.yaml", "trust-root"), (".ai/trust/KEYS.yaml", "trust-keys"), (".ai/agents/TRUST.yaml", "trust-policy"), (".ai/agents/DELEGATIONS.yaml", "delegations")]:
        assert run(str(CRYPTO), "sign", str(project), "--file", str(project / rel), "--private-key", str(private), "--key-id", "AGENT-ROOT-001", "--purpose", purpose).returncode == 0
    root_path = project / ".ai/trust/ROOT.yaml"
    root = yaml.safe_load(root_path.read_text())
    root["policy"]["cryptographic_required"] = True
    root["policy"]["external_pin_required"] = True
    root_path.write_text(yaml.safe_dump(root, sort_keys=False))
    # policy was changed after its signature, so bundle must reject until re-signed.
    bad = run(str(CRYPTO), "bundle-check", str(project), "--pinned-root-fingerprint", fingerprint, "--json")
    assert bad.returncode == 1
    # Re-sign the root policy and bundle should pass.
    assert run(str(CRYPTO), "sign", str(project), "--file", str(root_path), "--private-key", str(private), "--key-id", "AGENT-ROOT-001", "--purpose", "trust-root").returncode == 0
    good = run(str(CRYPTO), "bundle-check", str(project), "--pinned-root-fingerprint", fingerprint, "--json")
    assert good.returncode == 0, good.stdout + good.stderr


def test_external_pin_required_fails_closed_when_pin_missing(tmp_path: Path):
    project = init(tmp_path, "PinRequired")
    private, public, _ = keygen(tmp_path)
    assert run(str(CRYPTO), "trust-init", str(project), "--key-id", "AGENT-ROOT-001", "--public-key", str(public)).returncode == 0
    root = project / ".ai/trust/ROOT.yaml"
    data = yaml.safe_load(root.read_text())
    data["policy"]["external_pin_required"] = True
    root.write_text(yaml.safe_dump(data, sort_keys=False))
    for rel, purpose in [(".ai/trust/ROOT.yaml", "trust-root"), (".ai/trust/KEYS.yaml", "trust-keys")]:
        assert run(str(CRYPTO), "sign", str(project), "--file", str(project / rel), "--private-key", str(private), "--key-id", "AGENT-ROOT-001", "--purpose", purpose).returncode == 0
    missing = run(str(CRYPTO), "bundle-check", str(project), "--json")
    assert missing.returncode == 1
    payload = json.loads(missing.stdout)
    assert payload["checks"]["external_pin"]["reason"] == "EXTERNAL_PIN_REQUIRED"


def test_audit_chain_detects_tamper(tmp_path: Path):
    project = init(tmp_path, "Audit")
    private, public, _ = keygen(tmp_path)
    assert run(str(CRYPTO), "trust-init", str(project), "--key-id", "AGENT-ROOT-001", "--public-key", str(public)).returncode == 0
    keys = project / ".ai/trust/KEYS.yaml"
    assert run(str(CRYPTO), "sign", str(project), "--file", str(keys), "--private-key", str(private), "--key-id", "AGENT-ROOT-001", "--purpose", "trust-keys").returncode == 0
    good = run(str(CRYPTO), "audit-check", str(project), "--json")
    assert good.returncode == 0
    audit = project / ".ai/agents/TRUST-AUDIT.jsonl"
    rows = audit.read_text().splitlines()
    assert rows
    row = json.loads(rows[0]); row["action"] = "TAMPERED"
    audit.write_text(json.dumps(row) + "\n")
    bad = run(str(CRYPTO), "audit-check", str(project), "--json")
    assert bad.returncode == 1
    assert "AUDIT_ENTRY_HASH_MISMATCH" in bad.stdout


def test_root_pin_and_rotation(tmp_path: Path):
    project = init(tmp_path, "Rotate")
    private, public, fingerprint = keygen(tmp_path, "ROOT-OLD")
    assert run(str(CRYPTO), "trust-init", str(project), "--key-id", "ROOT-OLD", "--public-key", str(public)).returncode == 0
    _, new_public, new_fp = keygen(tmp_path / "new", "ROOT-NEW")
    out = project / ".ai/trust/KEY-ROTATION.yaml"
    rot = run(str(CRYPTO), "rotation-create", str(project), "--old-private-key", str(private), "--old-key-id", "ROOT-OLD", "--new-key-id", "ROOT-NEW", "--new-public-key", str(new_public), "--effective-at", "2030-01-01T00:00:00Z", "--reason", "scheduled", "--out", str(out))
    assert rot.returncode == 0, rot.stdout + rot.stderr
    chk = run(str(CRYPTO), "rotation-check", str(project), "--file", str(out), "--new-public-key", str(new_public), "--json")
    assert chk.returncode == 0, chk.stdout + chk.stderr
    pin = run(str(CRYPTO), "anchor-check", str(project), "--pinned-root-fingerprint", fingerprint)
    assert pin.returncode == 0
    wrong = run(str(CRYPTO), "anchor-check", str(project), "--pinned-root-fingerprint", new_fp)
    assert wrong.returncode == 1


def test_conformance_rejects_private_key(tmp_path: Path):
    project = init(tmp_path, "Private")
    private, _, _ = keygen(tmp_path)
    (project / ".ai/trust/leaked.private.pem").write_bytes(private.read_bytes())
    proc = run(str(CHECK), str(project), "--level", "full")
    assert proc.returncode == 1
    assert "CONF-V19-016" in proc.stdout


def test_trust_evaluation_fails_closed_when_crypto_required(tmp_path: Path):
    project = init(tmp_path, "FailClosed")
    private, public, _ = keygen(tmp_path)
    assert run(str(CRYPTO), "trust-init", str(project), "--key-id", "AGENT-ROOT-001", "--public-key", str(public)).returncode == 0
    root = project / ".ai/trust/ROOT.yaml"
    data = yaml.safe_load(root.read_text())
    data["policy"]["cryptographic_required"] = True
    root.write_text(yaml.safe_dump(data, sort_keys=False))
    proc = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-HUMAN", "--capability", "read", "--domain", "backend", "--risk", "LOW", "--min-evidence", "E0", "--json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["reason"] in {"CRYPTOGRAPHIC_BUNDLE_INVALID", "CRYPTOGRAPHIC_CHECK_ERROR"}

def test_v19_strict_signed_bundle_conformance(tmp_path: Path):
    project = init(tmp_path, "Strict")
    private, public, fingerprint = keygen(tmp_path, "AGENT-ROOT-STRICT")
    assert run(str(CRYPTO), "trust-init", str(project), "--key-id", "AGENT-ROOT-STRICT", "--public-key", str(public)).returncode == 0
    root = project / ".ai/trust/ROOT.yaml"
    root_data = yaml.safe_load(root.read_text())
    root_data["policy"]["cryptographic_required"] = True
    root_data["policy"]["external_pin_required"] = True
    root.write_text(yaml.safe_dump(root_data, sort_keys=False))
    # Establish non-crypto strict prerequisites.
    (project / ".ai/memory/entries").mkdir(parents=True, exist_ok=True)
    (project / ".ai/memory/entries/MEM-0001.md").write_text("---\nid: MEM-0001\ntype: LESSON\nstatus: ACTIVE\nscope: project\nauthority: REFERENCE\nconfidence: HIGH\nstability: STABLE\ncreated: 2026-09-26\nupdated: 2026-09-26\n---\n\nVerified project memory.\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "uaf@example.invalid"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "UAAF Test"], cwd=project, check=True)
    (project / ".ai/core/CONTEXT.md").write_text("Project-specific context.\n", encoding="utf-8")
    (project / ".ai/core/CONVENTIONS.md").write_text("Project-specific conventions.\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=project, check=True, capture_output=True, text=True)
    assert run(str(ROOT / "tools/uaf_git_trace.py"), str(project), "snapshot").returncode == 0
    assert run(str(ROOT / "tools/uaf_context_impact.py"), str(project), "--paths", "README.md", "--write").returncode == 0
    assert run(str(ROOT / "tools/uaf_rce_strong.py"), str(project), "snapshot").returncode == 0
    for rel, purpose in [(".ai/trust/ROOT.yaml", "trust-root"), (".ai/trust/KEYS.yaml", "trust-keys"), (".ai/agents/TRUST.yaml", "trust-policy"), (".ai/agents/DELEGATIONS.yaml", "delegations")]:
        assert run(str(CRYPTO), "sign", str(project), "--file", str(project / rel), "--private-key", str(private), "--key-id", "AGENT-ROOT-STRICT", "--purpose", purpose).returncode == 0
    # Root policy was changed after the initial signature; re-sign it.
    assert run(str(CRYPTO), "sign", str(project), "--file", str(root), "--private-key", str(private), "--key-id", "AGENT-ROOT-STRICT", "--purpose", "trust-root").returncode == 0
    check = run(str(CHECK), str(project), "--level", "full", "--strict", "--pinned-root-fingerprint", fingerprint)
    assert check.returncode == 0, check.stdout + check.stderr

