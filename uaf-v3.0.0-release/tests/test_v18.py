from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
TRUST = ROOT / "tools/uaf_trust.py"
CHECK = ROOT / "tools/uaf_check.py"
DOCTOR = ROOT / "tools/uaf_doctor.py"
CLI = ROOT / "tools/uaf.py"


def run(*args: str, timeout: int = 20):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, timeout=timeout)


def init(tmp_path: Path, name: str = "V18") -> Path:
    project = tmp_path / name.lower()
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.8", "--name", name)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return project


def configure_agents(project: Path) -> None:
    trust = project / ".ai/agents/TRUST.yaml"
    doc = yaml.safe_load(trust.read_text())
    doc["agents"] = [
        {"id": "AGENT-HUMAN", "status": "ACTIVE", "direct_authority": True, "authority": "ROOT", "can_delegate": True, "capabilities": ["*"], "domains": ["*"], "max_risk": "CRITICAL", "min_evidence": "E0"},
        {"id": "AGENT-CODE", "status": "ACTIVE", "direct_authority": False, "authority": "DELEGATED", "can_delegate": False, "capabilities": ["write", "read"], "domains": ["backend"], "max_risk": "HIGH", "min_evidence": "E2"},
        {"id": "AGENT-LOW", "status": "ACTIVE", "direct_authority": False, "authority": "DELEGATED", "can_delegate": False, "capabilities": ["read"], "domains": ["backend"], "max_risk": "LOW", "min_evidence": "E0"},
    ]
    trust.write_text(yaml.safe_dump(doc, sort_keys=False))


def future(minutes: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def test_v18_initializer_and_conformance(tmp_path: Path):
    project = init(tmp_path)
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
    assert manifest["extensions"]["version"] == "1.8"
    assert manifest["extensions"]["agent_trust"]["mode"] == "bounded_delegation"
    for rel in [".ai/agents/TRUST.yaml", ".ai/agents/DELEGATIONS.yaml", ".ai/agents/TRUST-AUDIT.jsonl", ".ai/agents/TRUST-DELEGATION.md"]:
        assert (project / rel).exists()
    proc = run(str(CHECK), str(project), "--level", "full")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_legacy_install_does_not_emit_trust(tmp_path: Path):
    project = tmp_path / "legacy"
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.7")
    assert proc.returncode == 0, proc.stderr
    assert not (project / ".ai/agents/TRUST.yaml").exists()


def test_direct_root_authority_can_evaluate(tmp_path: Path):
    project = init(tmp_path)
    configure_agents(project)
    proc = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-HUMAN", "--capability", "delete", "--domain", "database", "--risk", "CRITICAL", "--min-evidence", "E0", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "AUTHORIZED"


def test_delegation_is_bounded_and_evaluable(tmp_path: Path):
    project = init(tmp_path)
    configure_agents(project)
    proc = run(str(TRUST), str(project), "delegate", "--from-agent", "AGENT-HUMAN", "--to-agent", "AGENT-CODE", "--delegation-id", "DEL-0001", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--min-evidence", "E2", "--expires-at", future())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    check = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-CODE", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--min-evidence", "E2", "--json")
    assert check.returncode == 0, check.stdout + check.stderr
    assert json.loads(check.stdout)["decision"] == "AUTHORIZED"


def test_delegation_escalation_is_rejected(tmp_path: Path):
    project = init(tmp_path)
    configure_agents(project)
    base = run(str(TRUST), str(project), "delegate", "--from-agent", "AGENT-HUMAN", "--to-agent", "AGENT-CODE", "--delegation-id", "DEL-ROOT", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--expires-at", future())
    assert base.returncode == 0, base.stderr
    project2 = project
    # Delegated agent cannot create a broader second delegation because can_delegate=false.
    proc = run(str(TRUST), str(project2), "delegate", "--from-agent", "AGENT-CODE", "--to-agent", "AGENT-LOW", "--delegation-id", "DEL-ESC", "--capability", "delete", "--domain", "database", "--risk", "CRITICAL", "--expires-at", future())
    assert proc.returncode == 1
    assert "delegator_not_authorized_to_delegate" in proc.stderr.lower()


def test_risk_and_evidence_floor_are_review_required(tmp_path: Path):
    project = init(tmp_path)
    configure_agents(project)
    assert run(str(TRUST), str(project), "delegate", "--from-agent", "AGENT-HUMAN", "--to-agent", "AGENT-CODE", "--delegation-id", "DEL-0002", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--min-evidence", "E3", "--expires-at", future()).returncode == 0
    risk = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-CODE", "--capability", "write", "--domain", "backend", "--risk", "CRITICAL", "--min-evidence", "E3", "--json")
    assert risk.returncode == 1
    assert json.loads(risk.stdout)["decision"] == "REVIEW_REQUIRED"
    ev = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-CODE", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--min-evidence", "E1", "--json")
    assert ev.returncode == 1
    assert json.loads(ev.stdout)["decision"] == "REVIEW_REQUIRED"
    assert json.loads(ev.stdout)["required"] == "E3"


def test_expired_and_revoked_delegation_deny(tmp_path: Path):
    project = init(tmp_path)
    configure_agents(project)
    old = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    docs = {"schema_version": "1.8", "delegations": [{"delegation_id": "DEL-OLD", "from_agent": "AGENT-HUMAN", "to_agent": "AGENT-CODE", "capabilities": ["write"], "domains": ["backend"], "max_risk": "HIGH", "min_evidence": "E0", "expires_at": old, "status": "ACTIVE"}]}
    (project / ".ai/agents/DELEGATIONS.yaml").write_text(yaml.safe_dump(docs, sort_keys=False))
    proc = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-CODE", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--min-evidence", "E0", "--json")
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["decision"] == "DENIED"
    replacement = run(str(TRUST), str(project), "delegate", "--from-agent", "AGENT-HUMAN", "--to-agent", "AGENT-CODE", "--delegation-id", "DEL-NEW", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--expires-at", future())
    assert replacement.returncode == 0, replacement.stdout + replacement.stderr


def test_revoke_and_audit(tmp_path: Path):
    project = init(tmp_path)
    configure_agents(project)
    assert run(str(TRUST), str(project), "delegate", "--from-agent", "AGENT-HUMAN", "--to-agent", "AGENT-CODE", "--delegation-id", "DEL-REV", "--capability", "read", "--domain", "backend", "--risk", "LOW", "--expires-at", future()).returncode == 0
    assert run(str(TRUST), str(project), "revoke", "--delegation-id", "DEL-REV").returncode == 0
    proc = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-CODE", "--capability", "read", "--domain", "backend", "--risk", "LOW", "--min-evidence", "E0", "--json")
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["decision"] == "DENIED"
    lines = [x for x in (project / ".ai/agents/TRUST-AUDIT.jsonl").read_text().splitlines() if x.strip()]
    assert any(json.loads(x)["action"] == "REVOKE" for x in lines)


def test_doctor_cli_and_unknown_agent(tmp_path: Path):
    project = init(tmp_path)
    configure_agents(project)
    doctor = run(str(DOCTOR), str(project), "--level", "full")
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "AGENT_TRUST 0" in doctor.stdout
    bad = run(str(CLI), "trust", str(project), "evaluate", "--agent", "AGENT-NOPE", "--capability", "read", "--domain", "backend", "--risk", "LOW")
    assert bad.returncode == 1
    assert "AGENT_NOT_REGISTERED" in bad.stdout


def test_unauthorized_delegatee_cannot_authorize(tmp_path: Path):
    project = init(tmp_path)
    configure_agents(project)
    assert run(str(TRUST), str(project), "delegate", "--from-agent", "AGENT-HUMAN", "--to-agent", "AGENT-LOW", "--delegation-id", "DEL-LOW", "--capability", "read", "--domain", "backend", "--risk", "LOW", "--expires-at", future()).returncode == 0
    proc = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-LOW", "--capability", "write", "--domain", "backend", "--risk", "LOW", "--json")
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["reason"] in {"AUTHORIZATION_NOT_GRANTED", "CAPABILITY_NOT_GRANTED", "DELEGATION_CHAIN_INCOMPLETE"}



def test_multiple_delegation_paths_use_any_valid_path(tmp_path: Path):
    project = init(tmp_path, "MultiPath")
    configure_agents(project)
    assert run(str(TRUST), str(project), "delegate", "--from-agent", "AGENT-HUMAN", "--to-agent", "AGENT-CODE", "--delegation-id", "DEL-BAD", "--capability", "read", "--domain", "backend", "--risk", "LOW", "--expires-at", future()).returncode == 0
    assert run(str(TRUST), str(project), "delegate", "--from-agent", "AGENT-HUMAN", "--to-agent", "AGENT-CODE", "--delegation-id", "DEL-GOOD", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--expires-at", future()).returncode == 0
    proc = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-CODE", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "AUTHORIZED"
    assert payload["chain"] == ["AGENT-HUMAN", "AGENT-CODE"]


def test_evidence_history_can_require_review(tmp_path: Path):
    project = init(tmp_path, "History")
    configure_agents(project)
    trust = project / ".ai/agents/TRUST.yaml"
    doc = yaml.safe_load(trust.read_text())
    for agent in doc["agents"]:
        if agent["id"] == "AGENT-CODE":
            agent["min_recent_verified_evidence"] = 1
            agent["evidence_window_days"] = 30
    trust.write_text(yaml.safe_dump(doc, sort_keys=False))
    assert run(str(TRUST), str(project), "delegate", "--from-agent", "AGENT-HUMAN", "--to-agent", "AGENT-CODE", "--delegation-id", "DEL-HIST", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--expires-at", future()).returncode == 0
    proc = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-CODE", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--min-evidence", "E2", "--json")
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["reason"] == "EVIDENCE_HISTORY_INSUFFICIENT"
    receipt = project / ".ai/evidence/EVD-1000.yaml"
    receipt.write_text(yaml.safe_dump({"id": "EVD-1000", "status": "VERIFIED", "verified_by": "AGENT-CODE", "verified_at": datetime.now(timezone.utc).isoformat(), "task_id": "TASK-1000"}, sort_keys=False))
    proc2 = run(str(TRUST), str(project), "evaluate", "--agent", "AGENT-CODE", "--capability", "write", "--domain", "backend", "--risk", "HIGH", "--min-evidence", "E2", "--json")
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    assert json.loads(proc2.stdout)["decision"] == "AUTHORIZED"


def test_v18_requires_full_profile(tmp_path: Path):
    project = tmp_path / "standard"
    proc = run(str(INIT), str(project), "--profile", "standard", "--extension", "v1.8")
    assert proc.returncode == 1
    assert "profile full" in proc.stderr.lower()


def test_conformance_detects_active_delegation_cycle(tmp_path: Path):
    project = init(tmp_path, "Cycle")
    trust = project / ".ai/agents/TRUST.yaml"
    doc = yaml.safe_load(trust.read_text())
    doc["agents"] += [
        {"id": "AGENT-A", "status": "ACTIVE", "direct_authority": False, "authority": "DELEGATED", "can_delegate": True, "capabilities": ["read"], "domains": ["backend"], "max_risk": "LOW", "min_evidence": "E0"},
        {"id": "AGENT-B", "status": "ACTIVE", "direct_authority": False, "authority": "DELEGATED", "can_delegate": True, "capabilities": ["read"], "domains": ["backend"], "max_risk": "LOW", "min_evidence": "E0"},
    ]
    trust.write_text(yaml.safe_dump(doc, sort_keys=False))
    delegations = {
        "schema_version": "1.8",
        "delegations": [
            {"delegation_id": "DEL-A-B", "from_agent": "AGENT-A", "to_agent": "AGENT-B", "capabilities": ["read"], "domains": ["backend"], "max_risk": "LOW", "min_evidence": "E0", "expires_at": future(), "status": "ACTIVE"},
            {"delegation_id": "DEL-B-A", "from_agent": "AGENT-B", "to_agent": "AGENT-A", "capabilities": ["read"], "domains": ["backend"], "max_risk": "LOW", "min_evidence": "E0", "expires_at": future(), "status": "ACTIVE"},
        ],
    }
    (project / ".ai/agents/DELEGATIONS.yaml").write_text(yaml.safe_dump(delegations, sort_keys=False))
    proc = run(str(CHECK), str(project), "--level", "full")
    assert proc.returncode == 1
    assert "CONF-V18-031" in proc.stdout
