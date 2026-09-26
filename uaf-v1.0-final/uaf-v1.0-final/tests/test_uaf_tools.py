from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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
    contract = ROOT / "examples/northstar/.ai/tasks/completed/TASK-0001.yaml"
    result = run(str(CONTRACT), str(contract))
    assert result.returncode == 0, result.stdout
    assert "STATUS: VALID" in result.stdout


def test_northstar_full_conformance():
    demo = ROOT / "examples/northstar"
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
    source = ROOT / "examples/northstar/.ai/tasks/completed/TASK-0001.yaml"
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["constraints"][0]["statement"] = "Introduce a dependency."
    changed = tmp_path / "TASK-0001.yaml"
    changed.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    result = run(str(CONTRACT), str(changed))
    assert result.returncode == 1
    assert "STATUS: MISMATCH" in result.stdout
