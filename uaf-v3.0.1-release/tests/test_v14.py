from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CHECK = ROOT / "tools/uaf_check.py"
SEC = ROOT / "tools/uaf_security.py"
GIT_TASK = ROOT / "tools/uaf_git_task.py"
DELIVERY = ROOT / "tools/uaf_delivery.py"
RUNTIME = ROOT / "tools/uaf_runtime.py"
DOCTOR = ROOT / "tools/uaf_doctor.py"
CLI = ROOT / "tools/uaf.py"


def run(*args: str):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, timeout=15)


def git(root: Path, *args: str):
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False, timeout=5)


def test_v14_initializer_and_strict_conformance(tmp_path: Path):
    project = tmp_path / "p"
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.4", "--name", "V14")
    assert proc.returncode == 0, proc.stderr
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
    assert manifest["extensions"]["version"] == "1.4"
    assert "security_diagnostics" in manifest["extensions"]
    assert "git_task_traceability" in manifest["extensions"]
    assert "runtime_evidence" in manifest["extensions"]
    assert (project / ".ai/security/SECURITY-DIAGNOSTICS.md").exists()
    assert (project / ".ai/health/GIT-TASK-TRACEABILITY.md").exists()
    assert (project / ".ai/verification/RUNTIME-EVIDENCE.md").exists()
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 0, check.stdout


def test_v14_requires_full_profile(tmp_path: Path):
    project = tmp_path / "p"
    proc = run(str(INIT), str(project), "--profile", "standard", "--extension", "v1.4")
    assert proc.returncode == 1
    assert "profile full" in proc.stderr.lower()


def test_security_diagnostics_never_echoes_secret_value(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.4", "--name", "Sec").returncode == 0
    secret_value = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
    target = project / "config.py"
    target.write_text(f'TOKEN = "{secret_value}"\n', encoding="utf-8")
    proc = run(str(SEC), str(project), "scan")
    assert proc.returncode == 1
    assert "SEC-SECRET" in proc.stdout
    assert secret_value not in proc.stdout


def test_security_diagnostics_detects_world_writable(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.4", "--name", "Perm").returncode == 0
    target = project / "unsafe.txt"
    target.write_text("public", encoding="utf-8")
    target.chmod(0o666)
    proc = run(str(SEC), str(project), "scan")
    assert proc.returncode == 1
    assert "SEC-PERM-001" in proc.stdout


def make_git_project(project: Path):
    project.mkdir()
    assert git(project, "init").returncode == 0
    (project / "src.py").write_text("print('seed')\n", encoding="utf-8")
    git(project, "add", "src.py")
    assert git(project, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed").returncode == 0
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.4", "--name", "Trace").returncode == 0
    git_tool = ROOT / "tools/uaf_git_trace.py"
    assert run(str(git_tool), str(project), "snapshot").returncode == 0
    task = project / ".ai/tasks/active/TASK-0042.yaml"
    task.write_text(yaml.safe_dump({
        "id": "TASK-0042",
        "type": "feature",
        "status": "ACTIVE",
        "scope": {"level": "FEATURE", "domains": ["BACKEND"], "risk": "MEDIUM"},
        "intent": {"statement": "Update source behavior.", "confidence": "HIGH", "source": "user"},
        "requirements": [{"id": "REQ-1", "statement": "src.py changes"}],
        "constraints": [], "non_goals": [], "acceptance_criteria": [], "verification": [],
        "expected_changes": {"files": ["src.py"], "modules": []},
    }, sort_keys=False), encoding="utf-8")
    return task


def test_git_task_trace_semantic_linked_and_partial(tmp_path: Path):
    project = tmp_path / "repo"
    make_git_project(project)
    (project / "src.py").write_text("print('changed')\n", encoding="utf-8")
    linked = run(str(GIT_TASK), str(project), "trace", "--task", "TASK-0042", "--json")
    assert linked.returncode == 0, linked.stdout
    data = json.loads(linked.stdout)
    assert data["status"] == "LINKED"
    assert "src.py" in data["covered_files"]
    (project / "unrelated.txt").write_text("x\n", encoding="utf-8")
    partial = run(str(GIT_TASK), str(project), "trace", "--task", "TASK-0042", "--json")
    assert partial.returncode == 0
    assert json.loads(partial.stdout)["status"] == "PARTIAL"


def test_delivery_gate_requires_runtime_for_critical_task(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.4", "--name", "Gate").returncode == 0
    task = project / ".ai/tasks/active/TASK-0099.yaml"
    task.write_text(yaml.safe_dump({
        "id": "TASK-0099", "type": "migration", "status": "ACTIVE",
        "scope": {"level": "SYSTEM", "domains": ["DATABASE"], "risk": "CRITICAL"},
        "intent": {"statement": "Perform critical migration.", "confidence": "HIGH", "source": "user"},
        "requirements": [{"id": "REQ-1", "statement": "Migration works"}],
        "constraints": [], "non_goals": [], "acceptance_criteria": [{"id": "AC-1", "statement": "Migration verified"}],
        "verification": [{"type": "runtime_verification", "required": True, "command": "python -c \"print(1)\""}],
        "expected_changes": {"files": ["migration.sql"], "modules": []},
    }, sort_keys=False), encoding="utf-8")
    not_ready = run(str(DELIVERY), str(project), "check", "--task", "TASK-0099", "--json")
    assert not_ready.returncode == 1
    data = json.loads(not_ready.stdout)
    assert data["status"] == "NOT_READY"
    assert data["runtime_required"] is True
    policy_path = project / ".ai/verification/RUNTIME-POLICY.yaml"
    policy = yaml.safe_load(policy_path.read_text())
    policy["enabled"] = True
    policy["allow"] = ["python -c \"print(1)\""]
    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
    runtime = run(str(RUNTIME), str(project), "run", "--command", "python -c \"print(1)\"", "--task", "TASK-0099")
    assert runtime.returncode == 0, runtime.stdout + runtime.stderr
    ready = run(str(DELIVERY), str(project), "check", "--task", "TASK-0099", "--json")
    assert ready.returncode == 0
    assert json.loads(ready.stdout)["runtime_status"] == "VERIFIED"


def test_doctor_v14_fresh_scaffold_is_not_false_failure(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.4", "--name", "Doctor").returncode == 0
    proc = run(str(DOCTOR), str(project), "--level", "full")
    assert proc.returncode in {0, 1}
    assert "SECURITY" in proc.stdout
    assert "GIT_TASK" in proc.stdout
    assert "DELIVERY" in proc.stdout


def test_v14_strict_conformance_with_git_baseline(tmp_path: Path):
    project = tmp_path / "strict"
    project.mkdir()
    assert git(project, "init").returncode == 0
    (project / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(project, "add", "seed.txt")
    assert git(project, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed").returncode == 0
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.4", "--name", "Strict")
    assert proc.returncode == 0, proc.stderr
    context = project / ".ai/core/CONTEXT.md"
    context.write_text("# Project Context\n\nPurpose: v1.4 strict fixture.\nUsers: test agent.\nStack: Python.\nArchitecture summary: small fixture.\nConstraints: none.\nSpecial cases: none.\n", encoding="utf-8")
    assert run(str(ROOT / "tools/uaf_git_trace.py"), str(project), "snapshot").returncode == 0
    impact = run(str(ROOT / "tools/uaf_context_impact.py"), str(project), "--paths", "seed.txt", ".ai/core/CONTEXT.md", "--write")
    assert impact.returncode == 0
    rce = run(str(ROOT / "tools/uaf_rce_strong.py"), str(project), "snapshot")
    assert rce.returncode == 0
    check = run(str(CHECK), str(project), "--level", "full", "--strict")
    assert check.returncode == 0, check.stdout + check.stderr
    assert "PASS" in check.stdout


def test_unified_cli_v14(tmp_path: Path):
    project = tmp_path / "cli"
    init = run(str(CLI), "init", str(project), "--profile", "full", "--extension", "v1.4", "--name", "CLI")
    assert init.returncode == 0, init.stderr
    sec = run(str(CLI), "security", str(project), "scan")
    assert sec.returncode == 0
    check = run(str(CLI), "check", str(project), "--level", "full")
    assert check.returncode == 0, check.stdout


def test_doctor_ignores_completed_task_for_task_scoped_checks(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.4", "--name", "Completed").returncode == 0
    task = project / ".ai/tasks/completed/TASK-0001.yaml"
    task.write_text(yaml.safe_dump({"id": "TASK-0001", "status": "COMPLETED"}, sort_keys=False), encoding="utf-8")
    proc = run(str(DOCTOR), str(project), "--level", "full")
    assert proc.returncode in {0, 1}
    assert "GIT_TASK 0" in proc.stdout
    assert "DELIVERY 0" in proc.stdout
