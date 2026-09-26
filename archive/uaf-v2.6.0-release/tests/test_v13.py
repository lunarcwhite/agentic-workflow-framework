from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CHECK = ROOT / "tools/uaf_check.py"
GIT = ROOT / "tools/uaf_git_trace.py"
CLAIMS = ROOT / "tools/uaf_claims.py"
RUNTIME = ROOT / "tools/uaf_runtime.py"
DOCTOR = ROOT / "tools/uaf_doctor.py"
CLI = ROOT / "tools/uaf.py"


def run(*args: str):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, timeout=12)


def git(root: Path, *args: str):
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)


def test_v13_initializer_and_cumulative_conformance(tmp_path: Path):
    project = tmp_path / "p"
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.3", "--name", "P")
    assert proc.returncode == 0, proc.stderr
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
    assert manifest["extensions"]["version"] == "1.3"
    assert "memory_compaction" in manifest["extensions"]
    assert "rce_strong" in manifest["extensions"]
    assert (project / ".ai/capabilities.yaml").exists()
    assert (project / ".ai/memory/compaction/README.md").exists()
    assert (project / ".ai/health/RCE-STRONG.md").exists()
    assert (project / ".ai/health/GIT-BASELINE.yaml").exists()
    assert yaml.safe_load((project / ".ai/agents/CLAIMS.yaml").read_text())["schema_version"] == "1.3"
    assert yaml.safe_load((project / ".ai/verification/RUNTIME-POLICY.yaml").read_text())["enabled"] is False
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 0, check.stdout


def test_v13_requires_full_profile(tmp_path: Path):
    project = tmp_path / "p"
    proc = run(str(INIT), str(project), "--profile", "standard", "--extension", "v1.3")
    assert proc.returncode != 0
    assert "profile full" in proc.stderr or "profile full" in proc.stdout


def test_git_snapshot_and_trace_include_dirty_worktree(tmp_path: Path):
    project = tmp_path / "repo"
    project.mkdir()
    assert git(project, "init").returncode == 0
    (project / "README.md").write_text("initial\n", encoding="utf-8")
    git(project, "add", "README.md")
    assert git(project, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "initial").returncode == 0
    init = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.3", "--name", "Git")
    assert init.returncode == 0, init.stderr
    snap = run(str(GIT), str(project), "snapshot")
    assert snap.returncode == 0, snap.stdout
    (project / "README.md").write_text("changed\n", encoding="utf-8")
    trace = run(str(GIT), str(project), "trace", "--task", "TASK-0001")
    assert trace.returncode == 0, trace.stdout
    data = __import__("json").loads(trace.stdout)
    assert "README.md" in data["changed_files"]
    assert data["task_id"] == "TASK-0001"


def test_claim_lease_conflict_expiry_and_owner_release(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.3", "--name", "Claims").returncode == 0
    first = run(str(CLAIMS), str(project), "acquire", "--resource", "src/service.py", "--agent", "AGENT-A", "--task", "TASK-0001", "--lease", "900", "--claim-id", "CLM-0001")
    assert first.returncode == 0, first.stderr
    conflict = run(str(CLAIMS), str(project), "acquire", "--resource", "src/service.py", "--agent", "AGENT-B", "--task", "TASK-0002")
    assert conflict.returncode != 0
    assert "CLAIM_CONFLICT" in conflict.stdout or "CLAIM_CONFLICT" in conflict.stderr
    claims_path = project / ".ai/agents/CLAIMS.yaml"
    data = yaml.safe_load(claims_path.read_text())
    data["claims"][0]["lease_until"] = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    claims_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    blocked_after_expiry = run(str(CLAIMS), str(project), "acquire", "--resource", "src/service.py", "--agent", "AGENT-B", "--task", "TASK-0002", "--lease", "900", "--claim-id", "CLM-0002")
    assert blocked_after_expiry.returncode != 0
    reclaim = run(str(CLAIMS), str(project), "reclaim", "--claim-id", "CLM-0001")
    assert reclaim.returncode == 0, reclaim.stderr
    second = run(str(CLAIMS), str(project), "acquire", "--resource", "src/service.py", "--agent", "AGENT-B", "--task", "TASK-0002", "--lease", "900", "--claim-id", "CLM-0002")
    assert second.returncode == 0, second.stderr
    bad_release = run(str(CLAIMS), str(project), "release", "--claim-id", "CLM-0002", "--agent", "AGENT-A")
    assert bad_release.returncode != 0
    good_release = run(str(CLAIMS), str(project), "release", "--claim-id", "CLM-0002", "--agent", "AGENT-B")
    assert good_release.returncode == 0, good_release.stderr


def test_runtime_verification_allowlist_and_receipt(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.3", "--name", "Runtime").returncode == 0
    policy_path = project / ".ai/verification/RUNTIME-POLICY.yaml"
    policy = yaml.safe_load(policy_path.read_text())
    policy["enabled"] = True
    policy["allow"] = ["python -c \"print(\'ok\')\""]
    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
    denied = run(str(RUNTIME), str(project), "run", "--command", "python -c \"print(\'no\')\"")
    assert denied.returncode != 0
    assert "RUNTIME_COMMAND_NOT_ALLOWED" in denied.stdout or "RUNTIME_COMMAND_NOT_ALLOWED" in denied.stderr
    ok = run(str(RUNTIME), str(project), "run", "--command", "python -c \"print(\'ok\')\"", "--task", "TASK-0001")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    receipts = list((project / ".ai/evidence").glob("RTV-*.yaml"))
    assert receipts
    receipt = yaml.safe_load(receipts[0].read_text())
    assert receipt["status"] == "VERIFIED"
    assert receipt["exit_code"] == 0


def test_doctor_includes_v13_checks(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.3", "--name", "Doctor").returncode == 0
    # No Git repository is expected here; doctor should expose the Git diagnostic as a failure.
    proc = run(str(DOCTOR), str(project), "--level", "full")
    assert proc.returncode != 0
    assert "CAPABILITIES" in proc.stdout
    assert "MEMORY_COMPACTION" in proc.stdout
    assert "RCE_STRONG" in proc.stdout


def test_v13_strict_conformance_with_git_baseline_and_impact_graph(tmp_path: Path):
    project = tmp_path / "strict"
    project.mkdir()
    assert git(project, "init").returncode == 0
    (project / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(project, "add", "seed.txt")
    assert git(project, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed").returncode == 0
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.3", "--name", "Strict")
    assert proc.returncode == 0, proc.stderr
    assert run(str(GIT), str(project), "snapshot").returncode == 0
    # Remove scaffold placeholder comments so strict mode can evaluate actual project context.
    context = project / ".ai/core/CONTEXT.md"
    context.write_text("# Project Context\n\nPurpose: strict conformance fixture.\nUsers: test agent.\nStack: Python.\nArchitecture summary: small fixture.\nConstraints: none known.\nSpecial cases: none.\n", encoding="utf-8")
    impact = run(str(ROOT / "tools/uaf_context_impact.py"), str(project), "--paths", "seed.txt", ".ai/core/CONTEXT.md", "--write")
    assert impact.returncode == 0, impact.stderr
    strong_rce = run(str(ROOT / "tools/uaf_rce_strong.py"), str(project), "snapshot")
    assert strong_rce.returncode == 0, strong_rce.stdout + strong_rce.stderr
    check = run(str(CHECK), str(project), "--level", "full", "--strict")
    assert check.returncode == 0, check.stdout + check.stderr
    assert "PASS" in check.stdout
