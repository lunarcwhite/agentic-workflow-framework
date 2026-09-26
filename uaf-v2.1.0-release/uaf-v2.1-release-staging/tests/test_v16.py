from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CHECK = ROOT / "tools/uaf_check.py"
ADAPT = ROOT / "tools/uaf_adaptive.py"
DOCTOR = ROOT / "tools/uaf_doctor.py"
CLI = ROOT / "tools/uaf.py"


def run(*args: str):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, timeout=15)


def init(tmp_path: Path, name: str = "V16") -> Path:
    project = tmp_path / name.lower()
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.6", "--name", name)
    assert proc.returncode == 0, proc.stderr
    return project


def write_receipt(project: Path, name: str, loaded: list[str], used: list[str], unused: list[str]) -> None:
    path = project / ".ai/tasks/completed" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({
        "task_id": name.split("-")[-1].split(".")[0],
        "context_depth": 1,
        "loaded": loaded,
        "usage": {"used": used, "unused": unused},
    }, sort_keys=False), encoding="utf-8")


def record_event(project: Path, event: dict) -> None:
    path = project / ".ai/observability/EVENTS.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"schema_version": "1.5", **event}) + "\n")


def test_v16_initializer_and_conformance(tmp_path: Path):
    project = init(tmp_path)
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
    ext = manifest["extensions"]
    assert ext["version"] == "1.6"
    assert ext["adaptive_learning"]["mode"] == "advisory_only"
    for rel in [
        ".ai/optimization/POLICY.yaml",
        ".ai/optimization/ANALYSIS.yaml",
        ".ai/optimization/PROPOSALS.yaml",
        ".ai/optimization/README.md",
    ]:
        assert (project / rel).exists()
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 0, check.stdout + check.stderr


def test_v16_requires_full_profile(tmp_path: Path):
    project = tmp_path / "p"
    proc = run(str(INIT), str(project), "--profile", "standard", "--extension", "v1.6")
    assert proc.returncode == 1
    assert "profile full" in proc.stderr.lower()


def test_v16_context_retrieval_recommendation_is_advisory(tmp_path: Path):
    project = init(tmp_path, "Ctx")
    target = project / "heavy.md"
    target.write_text("x" * 800, encoding="utf-8")
    for i in range(3):
        write_receipt(project, f"context-receipt-TASK-{100+i}.yaml", ["heavy.md"], [], ["heavy.md"])
    proc = run(str(ADAPT), str(project), "analyze", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    recs = data["recommendations"]
    assert any(r["type"] == "CONTEXT_RETRIEVAL_REVIEW" for r in recs)
    assert all(r["safety"] == "ADVISORY_ONLY" for r in recs)
    assert target.exists()


def test_v16_memory_and_workflow_recommendations(tmp_path: Path):
    project = init(tmp_path, "Mem")
    for i in range(5):
        record_event(project, {"type": "memory_reuse", "task_id": "TASK-0200", "retrieved_ids": ["MEM-0001", "MEM-0002"], "reused_ids": []})
    record_event(project, {"type": "replan", "task_id": "TASK-0200"})
    record_event(project, {"type": "replan", "task_id": "TASK-0200"})
    record_event(project, {"type": "replan", "task_id": "TASK-0200"})
    for i in range(2):
        record_event(project, {"type": "gate", "task_id": "TASK-0200", "status": "BLOCKED"})
    proc = run(str(ADAPT), str(project), "recommend", "--json")
    assert proc.returncode == 0
    recs = json.loads(proc.stdout)
    kinds = {r["type"] for r in recs}
    assert "MEMORY_RETRIEVAL_REVIEW" in kinds
    assert "PLANNING_PREREQUISITE_REVIEW" in kinds
    assert "DELIVERY_GATE_REVIEW" in kinds
    assert all(r["status"] == "PROPOSED" for r in recs)


def test_v16_write_does_not_mutate_policy_or_intent(tmp_path: Path):
    project = init(tmp_path, "Write")
    policy_path = project / ".ai/optimization/POLICY.yaml"
    policy_before = policy_path.read_text()
    proc = run(str(ADAPT), str(project), "analyze", "--write")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert policy_path.read_text() == policy_before
    proposals = yaml.safe_load((project / ".ai/optimization/PROPOSALS.yaml").read_text())
    assert proposals["mode"] == "advisory"
    for rec in proposals.get("recommendations", []):
        assert rec["safety"] == "ADVISORY_ONLY"


def test_v16_legacy_initializer_does_not_emit_optimization(tmp_path: Path):
    project = tmp_path / "legacy"
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.5", "--name", "Legacy")
    assert proc.returncode == 0
    assert not (project / ".ai/optimization").exists()


def test_v16_doctor_and_unified_cli(tmp_path: Path):
    project = init(tmp_path, "CLI")
    doctor = run(str(DOCTOR), str(project), "--level", "full")
    assert doctor.returncode in {0, 1}
    assert "ADAPTIVE_LEARNING" in doctor.stdout
    cli = run(str(CLI), "adapt", str(project), "recommend")
    assert cli.returncode == 0
    assert "ADAPTIVE" in cli.stdout


def test_v16_conformance_rejects_non_advisory_proposal(tmp_path: Path):
    project = init(tmp_path, "Reject")
    prop = project / ".ai/optimization/PROPOSALS.yaml"
    prop.write_text(yaml.safe_dump({
        "schema_version": "1.6", "mode": "advisory",
        "recommendations": [{"id": "OPT-X", "type": "X", "target": "x", "status": "PROPOSED", "safety": "AUTO_APPLY", "evidence": {"x": 1}}]
    }, sort_keys=False), encoding="utf-8")
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 1
    assert "CONF-V16-012" in check.stdout


def test_v16_repeated_context_is_recommended_without_auto_policy_change(tmp_path: Path):
    project = init(tmp_path, "Repeat")
    source = project / "shared.md"
    source.write_text("context", encoding="utf-8")
    for i in range(3):
        write_receipt(project, f"context-receipt-TASK-{400+i}.yaml", ["shared.md"], ["shared.md"], [])
    proc = run(str(ADAPT), str(project), "recommend", "--json")
    assert proc.returncode == 0
    recs = json.loads(proc.stdout)
    rec = next(r for r in recs if r["type"] == "CONTEXT_REUSE_REVIEW")
    assert rec["safety"] == "ADVISORY_ONLY"
    policy = yaml.safe_load((project / ".ai/optimization/POLICY.yaml").read_text())
    assert policy["safety"]["auto_apply"] is False
