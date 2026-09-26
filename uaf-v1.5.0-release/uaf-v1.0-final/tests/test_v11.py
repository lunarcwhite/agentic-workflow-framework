from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CHECK = ROOT / "tools/uaf_check.py"
CAP = ROOT / "tools/uaf_capabilities.py"
IMPACT = ROOT / "tools/uaf_context_impact.py"
DOCTOR = ROOT / "tools/uaf_doctor.py"


def run(*args: str):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True)


def test_v11_initializer_and_capability_override(tmp_path: Path):
    project = tmp_path / "frontend"
    (project / "src/components").mkdir(parents=True)
    (project / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    init = run(str(INIT), str(project), "--profile", "standard", "--name", "Demo", "--auto-detect", "--extension", "v1.1")
    assert init.returncode == 0, init.stderr

    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["extensions"]["version"] == "1.1"
    caps = yaml.safe_load((project / ".ai/capabilities.yaml").read_text(encoding="utf-8"))
    assert caps["capabilities"]["frontend"]["detected"] is True

    shown = run(str(CAP), str(project), "show")
    assert shown.returncode == 0
    assert "frontend | true | auto | true" in shown.stdout

    changed = run(str(CAP), str(project), "set", "frontend=force_false", "--reason", "Project is a server-rendered shell; frontend module is not independently maintained.")
    assert changed.returncode == 0, changed.stderr
    manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["capabilities"]["frontend"] is False
    capdoc = yaml.safe_load((project / ".ai/capabilities.yaml").read_text(encoding="utf-8"))
    assert capdoc["capabilities"]["frontend"]["override"] == "force_false"
    assert capdoc["capabilities"]["frontend"]["source"] == "user"


def test_v11_capability_projection_and_invalid_override(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.1", "--name", "P").returncode == 0
    bad = run(str(CAP), str(project), "set", "backend=force_true")
    assert bad.returncode == 1
    assert "--reason is required" in bad.stderr

    good = run(str(CAP), str(project), "set", "backend=force_true", "--reason", "The project has a separately deployed backend.")
    assert good.returncode == 0
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 0, check.stdout


def test_context_impact_graph_explicit_paths(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.1", "--name", "P").returncode == 0
    graph = run(str(IMPACT), str(project), "--paths", "docs/design/DESIGN.md", "src/components/Button.tsx", "--write")
    assert graph.returncode == 0, graph.stderr
    doc = yaml.safe_load((project / ".ai/context/IMPACT-GRAPH.yaml").read_text(encoding="utf-8"))
    assert doc["schema_version"] == "1.1"
    assert doc["mode"] == "advisory"
    assert set(doc["changed_paths"]) == {"docs/design/DESIGN.md", "src/components/Button.tsx"}
    assert "design" in doc["affected_domains"]
    assert len(doc["nodes"]) == 2


def test_v11_strict_conformance_catches_projection_drift(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.1", "--name", "P").returncode == 0
    cap = project / ".ai/capabilities.yaml"
    data = yaml.safe_load(cap.read_text(encoding="utf-8"))
    data["capabilities"]["api"]["override"] = "force_true"
    data["capabilities"]["api"]["reason"] = "Explicit project requirement."
    cap.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    check = run(str(CHECK), str(project), "--level", "full")
    assert check.returncode == 1
    assert "CONF-V11-009 capability projection mismatch for api" in check.stdout


def test_v11_doctor_aggregates_extensions(tmp_path: Path):
    project = tmp_path / "p"
    assert run(str(INIT), str(project), "--profile", "full", "--extension", "v1.1", "--name", "P").returncode == 0
    doctor = run(str(DOCTOR), str(project), "--level", "full")
    assert doctor.returncode == 0, doctor.stdout
    assert "CAPABILITIES 0" in doctor.stdout
    assert "CONTEXT_IMPACT 0" in doctor.stdout


def test_v10_initializer_does_not_emit_v11_artifacts(tmp_path: Path):
    project = tmp_path / "legacy"
    init = run(str(INIT), str(project), "--profile", "standard", "--name", "Legacy")
    assert init.returncode == 0, init.stderr
    assert not (project / ".ai/capabilities.yaml").exists()
    assert not (project / ".ai/context").exists()


def test_unified_cli_dispatches_v11_tools(tmp_path: Path):
    project = tmp_path / "cli"
    cli = ROOT / "tools/uaf.py"
    init = run(str(cli), "init", str(project), "--profile", "full", "--extension", "v1.1", "--name", "CLI")
    assert init.returncode == 0, init.stderr
    check = run(str(cli), "check", str(project), "--level", "full")
    assert check.returncode == 0, check.stdout
    impact = run(str(cli), "impact", str(project), "--paths", "docs/quality/SECURITY.md")
    assert impact.returncode == 0
    assert "security" in impact.stdout


def test_context_impact_non_git_repo_is_fast(tmp_path: Path):
    project = tmp_path / "plain"
    assert run(str(INIT), str(project), "--profile", "standard", "--extension", "v1.1", "--name", "Plain").returncode == 0
    impact = run(str(IMPACT), str(project))
    assert impact.returncode == 0
    assert "SOURCE git-unavailable" in impact.stdout or "SOURCE git-timeout" in impact.stdout
