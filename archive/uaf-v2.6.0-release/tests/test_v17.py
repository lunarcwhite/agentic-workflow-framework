from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CHECK = ROOT / "tools/uaf_check.py"
GOV = ROOT / "tools/uaf_governance.py"
DOCTOR = ROOT / "tools/uaf_doctor.py"
CLI = ROOT / "tools/uaf.py"


def run(*args: str, timeout: int = 20):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, timeout=timeout)


def init(tmp_path: Path, name: str = "V17") -> Path:
    project = tmp_path / name.lower()
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.7", "--name", name)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return project


def test_v17_initializer_conformance_and_doctor(tmp_path: Path):
    project = init(tmp_path)
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
    assert manifest["extensions"]["version"] == "1.7"
    assert manifest["extensions"]["governance"]["mode"] == "explicit_approval"
    for rel in [".ai/governance/POLICY.yaml", ".ai/governance/PROPOSALS.yaml", ".ai/governance/AUDIT.jsonl", ".ai/governance/README.md"]:
        assert (project / rel).exists()
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 0, check.stdout + check.stderr
    doctor = run(str(DOCTOR), str(project), "--level", "full")
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "POLICY_GOVERNANCE 0" in doctor.stdout


def test_v17_requires_full_profile(tmp_path: Path):
    project = tmp_path / "p"
    proc = run(str(INIT), str(project), "--profile", "standard", "--extension", "v1.7")
    assert proc.returncode == 1
    assert "profile full" in proc.stderr.lower()


def test_legacy_install_does_not_emit_governance(tmp_path: Path):
    project = tmp_path / "legacy"
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.6")
    assert proc.returncode == 0, proc.stderr
    assert not (project / ".ai/governance").exists()


def test_import_review_approve_creates_preconditions(tmp_path: Path):
    project = init(tmp_path, "Import")
    opt = project / ".ai/optimization/PROPOSALS.yaml"
    opt.write_text(yaml.safe_dump({"schema_version": "1.6", "mode": "advisory", "recommendations": [
        {"id": "OPT-CTX-ABCD1234", "type": "CONTEXT_RETRIEVAL_REVIEW", "target": "x", "status": "PROPOSED", "confidence": "HIGH", "reason": "test", "evidence": {"x": 1}, "safety": "ADVISORY_ONLY"}
    ]}, sort_keys=False))
    imp = run(str(GOV), str(project), "import")
    assert imp.returncode == 0, imp.stdout + imp.stderr
    rev = run(str(GOV), str(project), "review", "--proposal", "OPT-CTX-ABCD1234", "--reviewer", "HUMAN-1")
    assert rev.returncode == 0, rev.stdout + rev.stderr
    app = run(str(GOV), str(project), "approve", "--proposal", "OPT-CTX-ABCD1234", "--reviewer", "HUMAN-1", "--reason", "Reviewed")
    assert app.returncode == 0, app.stdout + app.stderr
    doc = yaml.safe_load((project / ".ai/governance/PROPOSALS.yaml").read_text())
    row = doc["proposals"][0]
    assert row["status"] == "APPROVED"
    assert row["governance"]["approved_by"] == "HUMAN-1"
    assert row["governance"]["preconditions"] == {}


def test_approval_requires_reviewer(tmp_path: Path):
    project = init(tmp_path, "Reviewer")
    prop = project / ".ai/governance/PROPOSALS.yaml"
    prop.write_text(yaml.safe_dump({"schema_version": "1.7", "proposals": [{"id": "OPT-X", "status": "REVIEWED", "governance": {}}]}, sort_keys=False))
    proc = run(str(GOV), str(project), "approve", "--proposal", "OPT-X")
    assert proc.returncode == 1
    assert "reviewer" in proc.stderr.lower()


def test_safe_apply_verify_and_rollback(tmp_path: Path):
    project = init(tmp_path, "Apply")
    policy = project / ".ai/optimization/POLICY.yaml"
    before = policy.read_text()
    prop = project / ".ai/governance/PROPOSALS.yaml"
    prop.write_text(yaml.safe_dump({"schema_version": "1.7", "proposals": [{
        "id": "OPT-POL-0001",
        "type": "PLANNING_PREREQUISITE_REVIEW",
        "status": "PROPOSED",
        "changes": [{"path": ".ai/optimization/POLICY.yaml", "operation": "set", "key": "adaptive.max_replan_rate_per_task", "value": 3.0}],
        "governance": {"created_at": ""}
    }]}, sort_keys=False))
    assert run(str(GOV), str(project), "review", "--proposal", "OPT-POL-0001", "--reviewer", "HUMAN").returncode == 0
    assert run(str(GOV), str(project), "approve", "--proposal", "OPT-POL-0001", "--reviewer", "HUMAN").returncode == 0
    apply = run(str(GOV), str(project), "apply", "--proposal", "OPT-POL-0001")
    assert apply.returncode == 0, apply.stdout + apply.stderr
    changed = yaml.safe_load(policy.read_text())
    assert changed["adaptive"]["max_replan_rate_per_task"] == 3.0
    verify = run(str(GOV), str(project), "verify", "--proposal", "OPT-POL-0001")
    assert verify.returncode == 0, verify.stdout + verify.stderr
    rollback = run(str(GOV), str(project), "rollback", "--proposal", "OPT-POL-0001")
    assert rollback.returncode == 0, rollback.stdout + rollback.stderr
    assert policy.read_text() == before


def test_precondition_mismatch_blocks_apply(tmp_path: Path):
    project = init(tmp_path, "Mismatch")
    policy = project / ".ai/optimization/POLICY.yaml"
    prop = project / ".ai/governance/PROPOSALS.yaml"
    prop.write_text(yaml.safe_dump({"schema_version": "1.7", "proposals": [{
        "id": "OPT-POL-0002", "status": "PROPOSED", "changes": [{"path": ".ai/optimization/POLICY.yaml", "operation": "set", "key": "adaptive.max_replan_rate_per_task", "value": 4.0}], "governance": {"created_at": ""}
    }]}, sort_keys=False))
    assert run(str(GOV), str(project), "review", "--proposal", "OPT-POL-0002", "--reviewer", "HUMAN").returncode == 0
    assert run(str(GOV), str(project), "approve", "--proposal", "OPT-POL-0002", "--reviewer", "HUMAN").returncode == 0
    policy.write_text(policy.read_text() + "\n# changed after approval\n")
    proc = run(str(GOV), str(project), "apply", "--proposal", "OPT-POL-0002")
    assert proc.returncode == 1
    assert "precondition mismatch" in proc.stderr.lower()


def test_safe_apply_rejects_intent_and_safety(tmp_path: Path):
    project = init(tmp_path, "Unsafe")
    prop = project / ".ai/governance/PROPOSALS.yaml"
    for pid, key in [("OPT-BAD-1", "intent"), ("OPT-BAD-2", "safety.auto_apply")]:
        prop.write_text(yaml.safe_dump({"schema_version": "1.7", "proposals": [{
            "id": pid, "status": "APPROVED", "changes": [{"path": ".ai/optimization/POLICY.yaml", "operation": "set", "key": key, "value": True}], "governance": {"approved_by": "HUMAN", "preconditions": {".ai/optimization/POLICY.yaml": "MISSING"}}
        }]}, sort_keys=False))
        proc = run(str(GOV), str(project), "apply", "--proposal", pid)
        assert proc.returncode == 1
        assert "unsafe" in proc.stderr.lower() or "forbidden" in proc.stderr.lower() or "precondition" in proc.stderr.lower()


def test_unapproved_proposal_cannot_apply(tmp_path: Path):
    project = init(tmp_path, "NoApply")
    prop = project / ".ai/governance/PROPOSALS.yaml"
    prop.write_text(yaml.safe_dump({"schema_version": "1.7", "proposals": [{
        "id": "OPT-X", "status": "PROPOSED", "changes": [{"path": ".ai/optimization/POLICY.yaml", "operation": "set", "key": "adaptive.max_replan_rate_per_task", "value": 5.0}], "governance": {}
    }]}, sort_keys=False))
    proc = run(str(GOV), str(project), "apply", "--proposal", "OPT-X")
    assert proc.returncode == 1
    assert "approved" in proc.stderr.lower()


def test_cli_governance_and_audit(tmp_path: Path):
    project = init(tmp_path, "Audit")
    proc = run(str(CLI), "governance", str(project), "check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    imp = run(str(CLI), "governance", str(project), "status", "--json")
    assert imp.returncode == 0
    data = json.loads(imp.stdout)
    assert data["schema_version"] == "1.7"
