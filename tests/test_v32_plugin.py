#!/usr/bin/env python3
"""UAAF v3.1 Plugin System & Domain Specialist Integration Test Suite."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


INIT = load_module("uaf_init", ROOT / "tools/uaf_init.py")
CHECK = load_module("uaf_check", ROOT / "tools/uaf_check.py")
TEAM = load_module("uaf_team", ROOT / "tools/uaf_team.py")
PLUGIN = load_module("uaf_plugin", ROOT / "tools/uaf_plugin.py")


def init_project(destination: Path, name: str, kind: str, extension: str = "v3.1.0", profile: str = "full") -> None:
    old = sys.argv
    try:
        sys.argv = ["uaf_init.py", str(destination), "--profile", profile, "--name", name, "--type", kind, "--extension", extension]
        INIT.main()
    finally:
        sys.argv = old


def test_plugin_catalog_and_search(base_dir: Path) -> None:
    proj = base_dir / "proj_catalog"
    init_project(proj, "proj_catalog", "backend", extension="v3.1.0")

    list_res = PLUGIN.cmd_list(proj, remote=True)
    assert list_res["catalog_size"] >= 7
    assert "installed" in list_res

    # Search for fastapi
    matches = PLUGIN.cmd_search("fastapi", proj)
    assert len(matches) > 0
    assert any(m["plugin"] == "python-development" for m in matches)

    # Search for security
    sec_matches = PLUGIN.cmd_search("security", proj)
    assert len(sec_matches) > 0
    assert any(m["plugin"] == "security-audit" for m in sec_matches)

    print("[PASS] test_plugin_catalog_and_search")


def test_plugin_install_and_govern(base_dir: Path) -> None:
    proj = base_dir / "proj_install"
    init_project(proj, "proj_install", "backend", extension="v3.1.0")

    # Install python-development
    res = PLUGIN.cmd_install("python-development", proj, force=True)
    assert res["status"] == "INSTALLED"
    assert res["agents_count"] >= 3
    assert res["skills_count"] >= 3

    plugin_dir = proj / ".ai/plugins/python-development"
    assert plugin_dir.exists()
    assert (plugin_dir / "plugin.json").exists()
    assert (plugin_dir / "GOVERNANCE.md").exists()
    assert (plugin_dir / "agents/fastapi-pro.md").exists()
    assert (plugin_dir / "skills/async-python/SKILL.md").exists()

    # Check evidence receipt
    evidence_dir = proj / ".ai/evidence"
    evidence_files = list(evidence_dir.glob("EV-PLUGIN-*.yaml"))
    assert len(evidence_files) >= 1
    ev_data = yaml.safe_load(evidence_files[0].read_text(encoding="utf-8"))
    assert ev_data["status"] == "VERIFIED_COMPLIANT"
    assert "disjoint_perimeter_declared" in ev_data["gates_passed"]

    print("[PASS] test_plugin_install_and_govern")


def test_plugin_multi_target_export(base_dir: Path) -> None:
    proj = base_dir / "proj_export"
    init_project(proj, "proj_export", "backend", extension="v3.1.0")

    PLUGIN.cmd_install("python-development", proj, force=True)
    exp = PLUGIN.cmd_export("python-development", proj, target="all")
    assert exp["status"] == "EXPORTED"

    # 1. Claude Code
    assert (proj / ".claude/agents/fastapi-pro.md").exists()
    # 2. Antigravity
    assert (proj / ".agents/plugins/python-development/plugin.json").exists()
    assert (proj / ".agents/skills/async-python/SKILL.md").exists()
    # 3. Cursor
    assert (proj / ".cursor/rules/plugin-python-development.mdc").exists()
    # 4. Pi
    assert (proj / ".pi/agents/fastapi-pro.md").exists()

    print("[PASS] test_plugin_multi_target_export")


def test_team_compose_domain_specialist_adaptation(base_dir: Path) -> None:
    proj = base_dir / "proj_team_specialists"
    init_project(proj, "proj_team_specialists", "backend", extension="v3.1.0")

    # Install python-development and security-audit
    PLUGIN.cmd_install("python-development", proj, force=True)

    # Compose team with prompt mentioning FastAPI and React
    prompt = "Implement high performance FastAPI backend endpoints and React dashboard"
    team = TEAM.cmd_compose(proj, prompt, pattern="fan_out_fan_in")

    roles = [m["role"] for m in team["members"]]
    # Should have adapted backend to fastapi_pro and frontend to react_pro
    assert "fastapi_pro" in roles, f"fastapi_pro not found in {roles}"
    assert "react_pro" in roles, f"react_pro not found in {roles}"

    # Verify task contracts contain required_skills
    for m in team["members"]:
        task_file = proj / f".ai/tasks/active/{m['task_id']}.yaml"
        assert task_file.exists()
        t_data = yaml.safe_load(task_file.read_text(encoding="utf-8"))
        if t_data["assigned_role"] == "fastapi_pro":
            assert "fastapi_async" in t_data.get("required_skills", [])
            assert t_data["role_title"] == "FastAPI Specialist"
        elif t_data["assigned_role"] == "react_pro":
            assert "react_components" in t_data.get("required_skills", [])

    # Check locking works with domain specialists
    lock_res = TEAM.cmd_lock(proj, None, "specialist-agent", lease=300)
    assert lock_res["status"] == "LOCKED"

    # Multi-target export with domain specialists
    exp_res = TEAM.cmd_export(proj, target="all")
    assert (proj / ".claude/agents/fastapi_pro.md").exists()
    assert (proj / ".agents/skills/team-fastapi_pro/SKILL.md").exists()

    print("[PASS] test_team_compose_domain_specialist_adaptation")


def test_v32_init_and_conformance_check(base_dir: Path) -> None:
    proj = base_dir / "proj_v32_conf"
    init_project(proj, "proj_v32_conf", "backend", extension="v3.2.0")

    # Verify manifest
    manifest_data = yaml.safe_load((proj / ".ai/manifest.yaml").read_text(encoding="utf-8"))
    assert manifest_data["framework"]["version"] == "3.2.0"
    assert manifest_data["protocols"]["plugin_marketplace"] == "UAAF-PLUGIN-1.0"
    assert manifest_data["extensions"]["version"] == "3.2.0"
    assert "plugin_marketplace" in manifest_data["extensions"]

    # Run conformance check
    errors, warnings, infos = CHECK.check(proj, "standard")
    assert errors == [], f"Validation errors: {errors}"
    print("[PASS] test_v32_init_and_conformance_check (0 errors)")


def main() -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="uaf-plugin-test-"))
    try:
        test_plugin_catalog_and_search(temp_dir)
        test_plugin_install_and_govern(temp_dir)
        test_plugin_multi_target_export(temp_dir)
        test_team_compose_domain_specialist_adaptation(temp_dir)
        test_v32_init_and_conformance_check(temp_dir)
        print("\n==========================================")
        print("ALL UAAF v3.2 PLUGIN & SPECIALIST TESTS PASSED")
        print("==========================================")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
