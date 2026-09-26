from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CHECK = ROOT / "tools/uaf_check.py"
CONTRACT = ROOT / "tools/uaf_contract.py"
RCE = ROOT / "tools/uaf_reconcile.py"


def run(*args: str):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True)


def test_twenty_session_protocol(tmp_path: Path):
    project = tmp_path / "northstar"
    assert run(str(INIT), str(project), "--profile", "full", "--name", "Northstar", "--type", "service").returncode == 0

    # S01 bootstrap
    assert run(str(CHECK), str(project), "--level", "full").returncode == 0
    # S02 task contract created
    task = project / ".ai/tasks/active/TASK-0002.yaml"
    data = {
        "id": "TASK-0002", "type": "FEATURE", "status": "PLANNED",
        "scope": {"level": "FEATURE", "domains": ["BACKEND"], "risk": "MEDIUM"},
        "intent": {"statement": "Expose a safe retry operation.", "confidence": "HIGH", "source": "user"},
        "requirements": [{"id": "REQ-001", "priority": "MUST", "statement": "Retries are bounded."}],
        "constraints": [{"id": "CON-001", "statement": "Reuse the existing service."}],
        "non_goals": ["Queue redesign"],
        "acceptance_criteria": [{"id": "AC-001", "given": "a transient error", "when": "retry runs", "then": "attempts stay within the configured bound"}],
        "verification": [{"method": "targeted_test", "evidence": "EVD-0002"}],
        "expected_changes": {"files": ["src.py", "test_src.py"], "modules": ["task-service"]},
        "change_budget": {"mode": "strict"}, "context": [], "decisions": [], "memory_candidates": [], "related": [],
        "integrity": {},
    }
    task.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    assert run(str(CONTRACT), str(task), "--write").returncode == 0
    # S03 contract valid
    assert run(str(CONTRACT), str(task)).returncode == 0
    # S04 plan recorded as current implementation change (decision is persistent)
    (project / ".ai/decisions/DEC-0002.md").write_text(
        "# DEC-0002\n\nstatus: ACTIVE\nscope: task\n\n## Decision\nUse the existing retry helper.\n\n## Rationale\nAvoid duplicate retry logic.\n",
        encoding="utf-8",
    )
    # S05 evidence receipt references real sources
    (project / "src.py").write_text("def retry(attempts, limit=3):\n    return min(attempts + 1, limit)\n", encoding="utf-8")
    (project / "test_src.py").write_text("def test_retry():\n    assert True\n", encoding="utf-8")
    (project / ".ai/evidence/EVD-0002.yaml").write_text(
        "id: EVD-0002\ntype: evidence\nsubject:\n  type: TASK\n  id: TASK-0002\nmethod: [source_inspection]\nsources: [src.py, test_src.py]\nresult: observed\nverified_at: 2026-09-25\nverified_by: AGENT-TEST\n",
        encoding="utf-8",
    )
    # S06 RCE sees a consistent evidence source set
    assert run(str(RCE), str(project)).returncode == 0
    # S07 memory candidate becomes active after evidence
    mem = project / ".ai/memory/entries/MEM-0002.md"
    mem.write_text(
        "---\nid: MEM-0002\ntype: PATTERN\nstatus: ACTIVE\nscope: task-service\nauthority: CONTROLLED\nconfidence: HIGH\nstability: STABLE\ncreated: 2026-09-25\nupdated: 2026-09-25\nsource:\n  - TASK-0002\n  - EVD-0002\ntags: [retry]\nowner: project\n---\n\nRetry logic is bounded by configuration.\n",
        encoding="utf-8",
    )
    # S08 session handoff created
    handoff = project / ".ai/agents/handoffs/HND-20260925-002.md"
    handoff.write_text("# HND-20260925-002\n\nobjective: Continue TASK-0002\nstatus: complete\n", encoding="utf-8")
    # S09 state version advances
    state = project / ".ai/memory/STATE.md"
    state_text = state.read_text(encoding="utf-8")
    state.write_text(state_text.replace("version: 1", "version: 2", 1), encoding="utf-8")
    # S10 agent claim starts
    claims = project / ".ai/agents/CLAIMS.yaml"
    claims.write_text("schema_version: '1.0'\nclaims:\n  - resource: task-service\n    agent: AGENT-CODE\n    task: TASK-0002\n    status: ACTIVE\n", encoding="utf-8")
    # S11 plan is challenged: change constraint and detect fingerprint mismatch
    changed = yaml.safe_load(task.read_text(encoding="utf-8"))
    changed["constraints"][0]["statement"] = "Introduce Queue X."
    task.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")
    mismatch = run(str(CONTRACT), str(task))
    assert mismatch.returncode == 1
    # S12 restore original contract, record strategy change without changing intent
    changed["constraints"][0]["statement"] = "Reuse the existing service."
    task.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")
    assert run(str(CONTRACT), str(task), "--write").returncode == 0
    # S13 unexpected change is flagged
    cm = project / ".ai/tasks/active/change-manifest.yaml"
    cm.write_text("task_id: TASK-0002\nexpected:\n  files: [src.py]\nactual:\n  files: [src.py, docs/API.md]\nunexpected:\n  docs/API.md: api-doc\njustification: {}\nstatus: draft\n", encoding="utf-8")
    bad = run(str(CHECK), str(project), "--level", "full")
    assert bad.returncode == 1
    # S14 justify direct API consequence
    cm.write_text("task_id: TASK-0002\nexpected:\n  files: [src.py]\nactual:\n  files: [src.py, docs/API.md]\nunexpected:\n  docs/API.md: api-doc\njustification:\n  docs/API.md: API behavior changed as a direct consequence of the required implementation.\nstatus: accepted\n", encoding="utf-8")
    res14 = run(str(CHECK), str(project), "--level", "full")
    assert res14.returncode == 0, res14.stdout
    # S15 reality check stays clean after justified scope extension
    assert run(str(RCE), str(project)).returncode == 0
    # S16 documentation drift signal: missing source-of-truth owner
    manifest = project / ".ai/manifest.yaml"
    m = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    m["source_of_truth"]["api"] = "docs/development/MISSING-API.md"
    manifest.write_text(yaml.safe_dump(m, sort_keys=False), encoding="utf-8")
    drift = run(str(RCE), str(project))
    assert drift.returncode == 0 and "DRIFT" in drift.stdout
    # S17 repair canonical owner pointer
    m["source_of_truth"]["api"] = "docs/development/API.md"
    manifest.write_text(yaml.safe_dump(m, sort_keys=False), encoding="utf-8")
    assert run(str(RCE), str(project)).returncode == 0
    # S18 state advances after verification
    state_text = state.read_text(encoding="utf-8")
    state.write_text(state_text.replace("version: 2", "version: 3", 1), encoding="utf-8")
    # S19 task moves to completed
    completed = project / ".ai/tasks/completed/TASK-0002.yaml"
    data = yaml.safe_load(task.read_text(encoding="utf-8"))
    data["status"] = "COMPLETED"
    completed.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    task.unlink()
    # S20 final gate
    final = run(str(CHECK), str(project), "--level", "full")
    assert final.returncode == 0, final.stdout
