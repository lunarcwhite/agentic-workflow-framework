from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
MEMORY = ROOT / "tools/uaf_memory_compact.py"
RCE = ROOT / "tools/uaf_rce_strong.py"
CHECK = ROOT / "tools/uaf_check.py"
CLI = ROOT / "tools/uaf.py"


def run(*args: str):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True)


def test_v12_initializer_and_strict_conformance(tmp_path: Path):
    project = tmp_path / "p"
    proc = run(str(INIT), str(project), "--profile", "full", "--extension", "v1.2", "--name", "P")
    assert proc.returncode == 0, proc.stderr
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
    assert manifest["extensions"]["version"] == "1.2"
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 0, check.stdout
    assert "PASS" in check.stdout


def test_memory_compaction_dry_run_and_apply(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.2", "--name", "P").returncode == 0
    entries = project / ".ai/memory/entries"
    base = """---\nid: MEM-{id}\ntype: PATTERN\nstatus: ACTIVE\nscope: project\nauthority: CONTROLLED\nconfidence: HIGH\nstability: STABLE\ncreated: 2026-09-26\nupdated: 2026-09-26\n---\n\n# Shared pattern\nThe task service uses idempotent completion behavior and repeated requests are safe to retry.\n"""
    (entries / "MEM-1001.md").write_text(base.format(id="1001"), encoding="utf-8")
    (entries / "MEM-1002.md").write_text(base.format(id="1002"), encoding="utf-8")
    dry = run(str(MEMORY), str(project), "--check")
    assert dry.returncode == 1
    assert "DUPLICATES_FOUND" in dry.stdout
    apply = run(str(MEMORY), str(project), "--apply")
    assert apply.returncode == 0
    archived = list((project / ".ai/memory/archive/compaction").rglob("MEM-1002.md"))
    assert archived, "duplicate must be archived, not deleted"


def test_strong_rce_snapshot_then_drift(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.2", "--name", "P").returncode == 0
    source = project / ".ai/memory/STATE.md"
    source.write_text(source.read_text(encoding="utf-8") + "baseline\n", encoding="utf-8")
    snap = run(str(RCE), str(project), "snapshot")
    assert snap.returncode == 0, snap.stderr
    assert (project / ".ai/health/REALITY-INDEX.yaml").exists()
    source.write_text("changed\n", encoding="utf-8")
    scan = run(str(RCE), str(project), "scan")
    assert scan.returncode == 0
    assert "DRIFT" in scan.stdout
    assert "fingerprint drift" in scan.stdout


def test_strong_rce_catches_missing_canonical_owner(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.2", "--name", "P").returncode == 0
    manifest_path = project / ".ai/manifest.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["source_of_truth"]["security"] = "docs/quality/MISSING.md"
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    scan = run(str(RCE), str(project), "scan")
    assert scan.returncode == 1
    assert "RCE-S-005" in scan.stdout


def test_v11_project_has_no_v12_artifacts(tmp_path: Path):
    project = tmp_path / "legacy"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.1", "--name", "Legacy").returncode == 0
    assert not (project / ".ai/memory/compaction").exists()
    assert not (project / ".ai/health/RCE-STRONG.md").exists()
    assert not (project / ".ai/health/REALITY-INDEX.yaml").exists()


def test_strong_rce_checks_memory_id_references(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.2", "--name", "P").returncode == 0
    entry = project / ".ai/memory/entries/MEM-2001.md"
    entry.write_text("""---\nid: MEM-2001\ntype: LESSON\nstatus: ACTIVE\nscope: project\ncreated: 2026-09-26\nupdated: 2026-09-26\nsource:\n  - TASK-9999\n---\n\nMissing task reference.\n""", encoding="utf-8")
    scan = run(str(RCE), str(project), "scan")
    assert scan.returncode == 0
    assert "RCE-S-007" in scan.stdout


def test_unified_cli_v12(tmp_path: Path):
    project = tmp_path / "cli"
    assert run(str(CLI), "init", str(project), "--profile", "full", "--extension", "v1.2", "--name", "CLI").returncode == 0
    mem = run(str(CLI), "memory", str(project), "compact")
    assert mem.returncode == 0
    rce = run(str(CLI), "rce", str(project), "snapshot")
    assert rce.returncode == 0
    assert (project / ".ai/health/REALITY-INDEX.yaml").exists()
