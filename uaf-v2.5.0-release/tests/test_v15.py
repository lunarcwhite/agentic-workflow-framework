from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CHECK = ROOT / "tools/uaf_check.py"
OBS = ROOT / "tools/uaf_observe.py"
DOCTOR = ROOT / "tools/uaf_doctor.py"
CLI = ROOT / "tools/uaf.py"


def run(*args: str):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, timeout=12)


def test_v15_initializer_and_conformance(tmp_path: Path):
    project = tmp_path / "p"
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.5", "--name", "V15")
    assert proc.returncode == 0, proc.stderr
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
    assert manifest["extensions"]["version"] == "1.5"
    assert "observability" in manifest["extensions"]
    assert (project / ".ai/observability/POLICY.yaml").exists()
    assert (project / ".ai/observability/EVENTS.jsonl").exists()
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 0, check.stdout + check.stderr


def test_v15_requires_full_profile(tmp_path: Path):
    project = tmp_path / "p"
    proc = run(str(INIT), str(project), "--profile", "standard", "--extension", "v1.5")
    assert proc.returncode != 0
    assert "profile full" in (proc.stderr + proc.stdout).lower()


def test_context_economics_report_from_receipt(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.5", "--name", "Obs").returncode == 0
    source = project / "context.txt"
    source.write_text("a" * 400, encoding="utf-8")
    receipt = project / ".ai/tasks/completed/context-receipt-TEST.yaml"
    receipt.write_text(yaml.safe_dump({
        "task_id": "TASK-1001",
        "context_depth": 1,
        "loaded": ["context.txt"],
        "excluded": ["docs/product/ROADMAP.md"],
        "usage": {"used": ["context.txt"], "unused": []},
    }, sort_keys=False), encoding="utf-8")
    proc = run(str(OBS), str(project), "report", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["context"]["receipts"] == 1
    assert data["context"]["estimated_tokens_total"] == 100
    assert data["context"]["declared_use_rate"] == 1.0


def test_observability_events_measure_reuse_gate_and_replan(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.5", "--name", "Events").returncode == 0
    for args in [
        ("record", "memory", "--task", "TASK-1002", "--retrieved", "MEM-0001", "MEM-0002", "--reused", "MEM-0001"),
        ("record", "gate", "--task", "TASK-1002", "--status", "DONE", "--evidence-depth", "E3"),
        ("record", "replan", "--task", "TASK-1002"),
    ]:
        proc = run(str(OBS), str(project), *args)
        assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = run(str(OBS), str(project), "report", "--json")
    data = json.loads(proc.stdout)
    assert data["events"]["memory_reuse_rate"] == 0.5
    assert data["events"]["gate_done_rate"] == 1.0
    assert data["events"]["replan_rate_per_task"] == 1.0


def test_privacy_guard_strips_prompt_content_secret_fields(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.5", "--name", "Privacy").returncode == 0
    event_file = project / ".ai/observability/EVENTS.jsonl"
    event_file.write_text(json.dumps({
        "schema_version": "1.5",
        "event_id": "OBS-PRIV",
        "at": "2026-09-26T00:00:00+07:00",
        "type": "gate",
        "task_id": "TASK-1003",
        "prompt": "private prompt",
        "content": "private content",
        "secret": "PRIVATE-SECRET",
        "status": "DONE",
    }) + "\n", encoding="utf-8")
    proc = run(str(OBS), str(project), "report", "--json")
    assert proc.returncode == 0
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 1
    assert "CONF-V15-013" in check.stdout
    assert "PRIVATE-SECRET" not in proc.stdout


def test_observability_budget_warns_without_failing_report(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.5", "--name", "Budget").returncode == 0
    policy = project / ".ai/observability/POLICY.yaml"
    data = yaml.safe_load(policy.read_text())
    data["budgets"]["max_average_context_tokens"] = 1
    policy.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    source = project / "context.txt"
    source.write_text("x" * 200, encoding="utf-8")
    (project / ".ai/tasks/completed/context-receipt-1.yaml").write_text(yaml.safe_dump({"task_id": "TASK-1004", "context_depth": 1, "loaded": ["context.txt"]}, sort_keys=False), encoding="utf-8")
    report = run(str(OBS), str(project), "report")
    assert report.returncode == 0
    assert "OBSERVABILITY WARN" in report.stdout
    check = run(str(OBS), str(project), "check")
    assert check.returncode == 1


def test_doctor_includes_observability(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.5", "--name", "Doctor").returncode == 0
    proc = run(str(DOCTOR), str(project), "--level", "full")
    assert proc.returncode in {0, 1}
    assert "OBSERVABILITY" in proc.stdout


def test_legacy_initializer_does_not_emit_v15_artifacts(tmp_path: Path):
    project = tmp_path / "legacy"
    assert run(str(INIT), str(project), "--profile", "full", "--name", "Legacy").returncode == 0
    assert not (project / ".ai/observability").exists()


def test_unified_cli_observe(tmp_path: Path):
    project = tmp_path / "cli"
    assert run(str(CLI), "init", str(project), "--profile", "full", "--extension", "v1.5", "--name", "CLI").returncode == 0
    proc = run(str(CLI), "observe", str(project), "report")
    assert proc.returncode == 0
    assert "OBSERVABILITY" in proc.stdout
