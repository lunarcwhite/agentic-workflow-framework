from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CHECK = ROOT / "tools/uaf_check.py"
CONTRACT = ROOT / "tools/uaf_contract.py"


def run(*args: str, cwd: Path | None = None):
    return subprocess.run([sys.executable, *args], cwd=cwd, text=True, capture_output=True)


def test_profiles_conform(tmp_path: Path):
    for profile, level in [("minimal", "core"), ("standard", "standard"), ("full", "full")]:
        dst = tmp_path / profile
        result = run(str(INIT), str(dst), "--profile", profile, "--name", profile.title(), "--type", "test")
        assert result.returncode == 0, result.stderr
        check = run(str(CHECK), str(dst), "--level", level)
        assert check.returncode == 0, check.stdout
        assert "FAIL" not in check.stdout.splitlines()[0]


def test_contract_fingerprint():
    contract = ROOT / "examples/northstar-v22/.ai/tasks/completed/TASK-0001.yaml"
    result = run(str(CONTRACT), str(contract))
    assert result.returncode == 0, result.stdout
    assert "STATUS: VALID" in result.stdout


def test_northstar_full_conformance():
    demo = ROOT / "examples/northstar-v22"
    result = run(str(CHECK), str(demo), "--level", "full")
    assert result.returncode == 0, result.stdout


def test_validator_catches_broken_manifest_reference(tmp_path: Path):
    dst = tmp_path / "broken"
    result = run(str(INIT), str(dst), "--profile", "full", "--name", "Broken", "--type", "test")
    assert result.returncode == 0
    manifest = dst / ".ai/manifest.yaml"
    text = manifest.read_text(encoding="utf-8").replace(".ai/memory/entries", ".ai/memory/does-not-exist")
    manifest.write_text(text, encoding="utf-8")
    check = run(str(CHECK), str(dst), "--level", "full")
    assert check.returncode == 0
    assert "CONF-REF-001" in check.stdout


def test_contract_fingerprint_detects_semantic_change(tmp_path: Path):
    import yaml
    source = ROOT / "examples/northstar-v22/.ai/tasks/completed/TASK-0001.yaml"
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["constraints"][0]["statement"] = "Introduce a dependency."
    changed = tmp_path / "TASK-0001.yaml"
    changed.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    result = run(str(CONTRACT), str(changed))
    assert result.returncode == 1
    assert "STATUS: MISMATCH" in result.stdout


def test_minimal_level_alias_and_autodetect(tmp_path: Path):
    project = tmp_path / "project"
    (project / "src/components").mkdir(parents=True)
    (project / "package.json").write_text('{"name":"frontend-demo"}\n', encoding="utf-8")
    result = run(str(INIT), str(project), "--profile", "standard", "--name", "Demo", "--auto-detect")
    assert result.returncode == 0, result.stderr
    import yaml
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["capabilities"]["frontend"] is True
    assert manifest["capabilities"]["ui"] is True
    check = run(str(CHECK), str(project), "--level", "minimal")
    assert check.returncode == 0, check.stdout


@pytest.mark.parametrize("kind,files,expected_true,expected_false", [
    ("backend", ["requirements.txt", "app/main.py"], ["backend"], ["frontend", "ui"]),
    ("data", ["pyproject.toml", "pipeline/job.py"], ["data"], ["backend", "frontend"]),
    ("frontend", ["package.json", "src/components/Button.tsx"], ["frontend", "ui"], ["backend"]),
])
def test_capability_detection_is_conservative(tmp_path: Path, kind, files, expected_true, expected_false):
    project = tmp_path / kind
    for rel in files:
        fp = project / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("# demo\n", encoding="utf-8")
    result = run(str(INIT), str(project), "--profile", "standard", "--name", kind, "--auto-detect")
    assert result.returncode == 0, result.stderr
    import yaml
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text(encoding="utf-8"))
    caps = manifest["capabilities"]
    for cap in expected_true:
        assert caps[cap] is True, (kind, cap, caps)
    for cap in expected_false:
        assert caps[cap] is False, (kind, cap, caps)


def test_existing_project_files_are_preserved_and_docs_are_adaptive(tmp_path: Path):
    project = tmp_path / "existing"
    project.mkdir()
    (project / "README.md").write_text("PROJECT OWN README\n", encoding="utf-8")
    (project / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (project / "src/components").mkdir(parents=True)
    (project / ".ai/evidence").mkdir(parents=True)
    (project / ".ai/evidence/KEEP.yaml").write_text("id: EVD-9999\n", encoding="utf-8")
    result = run(str(INIT), str(project), "--profile", "standard", "--name", "Demo", "--auto-detect", "--docs", "auto")
    assert result.returncode == 0, result.stderr
    assert (project / "README.md").read_text(encoding="utf-8") == "PROJECT OWN README\n"
    assert (project / ".ai/evidence/KEEP.yaml").exists()
    assert (project / "docs/architecture/ARCHITECTURE.md").exists()
    assert (project / "docs/design/DESIGN.md").exists()
    assert not (project / "docs/data/DATABASE-SCHEMA.md").exists()
    assert not (project / "docs/operations/DEPLOYMENT.md").exists()


def test_docs_all_and_none_modes(tmp_path: Path):
    all_project = tmp_path / "all"
    none_project = tmp_path / "none"
    for project, mode in [(all_project, "all"), (none_project, "none")]:
        result = run(str(INIT), str(project), "--profile", "standard", "--name", project.name, "--docs", mode)
        assert result.returncode == 0, result.stderr
    assert (all_project / "docs/product/PRD.md").exists()
    assert (all_project / "docs/operations/MONITORING.md").exists()
    assert not (none_project / "docs").exists()


def test_doctor_aggregates_clean_project(tmp_path: Path):
    dst = tmp_path / "doctor"
    result = run(str(INIT), str(dst), "--profile", "full", "--name", "Doctor", "--type", "test")
    assert result.returncode == 0
    doctor = run(str(ROOT / "tools/uaf_doctor.py"), str(dst), "--level", "full")
    assert doctor.returncode == 0, doctor.stdout
    assert doctor.stdout.splitlines()[0] == "PASS"
