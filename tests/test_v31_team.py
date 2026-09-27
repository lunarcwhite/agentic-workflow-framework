#!/usr/bin/env python3
"""UAAF v3.1 Team-Architecture Factory & Multi-Agent Orchestrator Test Suite."""
from __future__ import annotations

import gc
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


def init_project(destination: Path, name: str, kind: str, extension: str = "v3.1.0", profile: str = "full") -> None:
    old = sys.argv
    try:
        sys.argv = ["uaf_init.py", str(destination), "--profile", profile, "--name", name, "--type", kind, "--extension", extension]
        INIT.main()
    finally:
        sys.argv = old


def test_compose_all_patterns(base_dir: Path) -> None:
    patterns = ["pipeline", "producer_reviewer", "fan_out_fan_in", "expert_pool", "supervisor", "hierarchical"]
    for pat in patterns:
        proj = base_dir / f"proj_{pat}"
        init_project(proj, f"proj_{pat}", "backend", extension="v3.1.0")

        res = TEAM.cmd_compose(proj, f"Implement distributed feature for {pat}", pattern=pat)
        assert res["status"] in {"CONFIGURED", "COMPOSED"}, f"Failed compose for pattern {pat}: {res}"

        team_file = proj / ".ai/agents/TEAM.yaml"
        assert team_file.exists(), f"TEAM.yaml missing for {pat}"
        team_data = yaml.safe_load(team_file.read_text(encoding="utf-8"))
        assert team_data["schema_version"] == "3.1"
        assert team_data["pattern"] == pat
        assert len(team_data["members"]) > 0

        # Invariant 1: Disjoint file perimeters across active members
        seen_files: dict[str, str] = {}
        for member in team_data["members"]:
            for f in member.get("permitted_files", []):
                assert f not in seen_files, f"Overlapping file {f} between {seen_files[f]} and {member['role']} in pattern {pat}"
                seen_files[f] = member["role"]

        # Check task contract files exist
        for member in team_data["members"]:
            contract_path = proj / f".ai/tasks/active/{member['task_id']}.yaml"
            assert contract_path.exists(), f"Contract {member['task_id']} missing for {member['role']}"

    print("[PASS] test_compose_all_patterns (6 patterns validated with disjoint perimeters)")


def test_claims_locking_and_release(base_dir: Path) -> None:
    proj = base_dir / "proj_claims"
    init_project(proj, "proj_claims", "backend", extension="v3.1.0")
    TEAM.cmd_compose(proj, "Concurrent multi-agent data pipeline", pattern="fan_out_fan_in")

    # Lock all
    lock_res = TEAM.cmd_lock(proj, None, "claude-code-agent", lease=600)
    assert lock_res["status"] == "LOCKED", f"Locking failed: {lock_res}"
    assert lock_res["acquired_count"] >= 4

    claims_file = proj / ".ai/agents/CLAIMS.yaml"
    assert claims_file.exists()
    claims_data = yaml.safe_load(claims_file.read_text(encoding="utf-8"))
    assert len(claims_data["claims"]) >= 4

    # Status check
    stat = TEAM.cmd_status(proj)
    assert stat["status"] == "ACTIVE"
    for m in stat["members"]:
        assert len(m["active_locked_resources"]) > 0

    # Release single task
    t0 = stat["members"][0]["task_id"]
    rel_res = TEAM.cmd_release(proj, t0, "claude-code-agent")
    assert rel_res["status"] == "RELEASED"
    assert rel_res["released_count"] >= 1

    # Release remaining
    rel_all = TEAM.cmd_release(proj, None, "claude-code-agent")
    assert rel_all["status"] == "RELEASED"
    assert rel_all["released_count"] >= 1

    stat2 = TEAM.cmd_status(proj)
    for m in stat2["members"]:
        assert len(m["active_locked_resources"]) == 0

    print("[PASS] test_claims_locking_and_release (atomic locking and releasing verified)")


def test_multi_target_export(base_dir: Path) -> None:
    proj = base_dir / "proj_export"
    init_project(proj, "proj_export", "fullstack", extension="v3.1.0")
    TEAM.cmd_compose(proj, "Fullstack ecommerce dashboard", pattern="fan_out_fan_in")

    exp_res = TEAM.cmd_export(proj, target="all")
    assert exp_res["status"] == "EXPORTED"

    # Claude Code target
    claude_dir = proj / ".claude/agents"
    assert claude_dir.exists()
    assert (claude_dir / "coordinator.md").exists()
    assert (claude_dir / "backend_specialist.md").exists()
    assert (claude_dir / "frontend_specialist.md").exists()

    # Antigravity target
    agy_dir = proj / ".agents/skills"
    assert agy_dir.exists()
    assert (agy_dir / "team-coordinator/SKILL.md").exists()
    assert (agy_dir / "team-backend_specialist/SKILL.md").exists()

    # Cursor target
    cursor_rule = proj / ".cursor/rules/team.mdc"
    assert cursor_rule.exists()
    content = cursor_rule.read_text(encoding="utf-8")
    assert "UAAF Multi-Agent Team Invariants" in content

    # Pi target
    pi_agents = proj / ".pi/agents"
    pi_prompts = proj / ".pi/prompts"
    assert pi_agents.exists()
    assert pi_prompts.exists()
    assert (pi_agents / "coordinator.md").exists()
    assert (pi_prompts / "team-fan_out_fan_in.md").exists()

    print("[PASS] test_multi_target_export (Claude Code, Antigravity, Cursor, Pi targets exported)")


def test_verification(base_dir: Path) -> None:
    proj = base_dir / "proj_verify"
    init_project(proj, "proj_verify", "backend", extension="v3.1.0")
    TEAM.cmd_compose(proj, "Audit security flaws", pattern="producer_reviewer")

    ver_res = TEAM.cmd_verify(proj)
    assert ver_res["status"] == "PASS"
    assert len(ver_res["verified_tasks"]) == 2

    print("[PASS] test_verification (deliverable contract verification passed)")


def test_conformance_check_v31(base_dir: Path) -> None:
    proj = base_dir / "proj_conf_v31"
    init_project(proj, "proj_conf_v31", "backend", extension="v3.1.0")

    # Initial conformance check on clean v3.1 scaffold
    errors, warnings, infos = CHECK.check(proj, level="standard")
    assert len(errors) == 0, f"scaffold errors found: {errors}"

    # Compose team and re-verify conformance
    TEAM.cmd_compose(proj, "Build authentication subsystem", pattern="pipeline")
    errors2, warnings2, infos2 = CHECK.check(proj, level="standard")
    assert len(errors2) == 0, f"team errors found: {errors2}"

    print("[PASS] test_conformance_check_v31 (UAAF v3.1 check cleanly passes 0 errors)")


def main() -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="uaf-v31-team-test-"))
    try:
        test_compose_all_patterns(temp_dir)
        test_claims_locking_and_release(temp_dir)
        test_multi_target_export(temp_dir)
        test_verification(temp_dir)
        test_conformance_check_v31(temp_dir)
        print("\n==========================================")
        print("ALL UAAF v3.1 TEAM ORCHESTRATOR TESTS PASSED")
        print("==========================================")
    finally:
        gc.collect()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
