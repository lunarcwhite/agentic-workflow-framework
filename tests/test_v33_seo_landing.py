#!/usr/bin/env python3
"""UAAF v3.3 Native Landing Page Design & SEO Governance Test Suite."""
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
SEO = load_module("uaf_seo", ROOT / "tools/uaf_seo.py")


def init_project(destination: Path, name: str, kind: str, extension: str = "v3.3.0", profile: str = "full") -> None:
    old = sys.argv
    try:
        sys.argv = ["uaf_init.py", str(destination), "--profile", profile, "--name", name, "--type", kind, "--extension", extension]
        INIT.main()
    finally:
        sys.argv = old


def test_seo_audit_and_generate(base_dir: Path) -> None:
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UAAF — Universal AI Agent Framework</title>
  <meta name="description" content="Deterministic task contracts, test evidence receipts, and auditable governance for AI coding agents.">
  <link rel="canonical" href="https://example.com/uaaf">
  <meta property="og:title" content="UAAF — Universal AI Agent Framework">
  <meta property="og:description" content="Deterministic task contracts and auditable governance.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://example.com/uaaf">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "UAAF",
    "description": "AI Agent Governance Framework",
    "url": "https://example.com/uaaf"
  }
  </script>
</head>
<body>
  <h1>Discipline AI Coding Agents</h1>
  <h2>Core Lifecycle</h2>
  <img src="logo.png" alt="UAAF Logo">
</body>
</html>
"""
    test_file = base_dir / "test_page.html"
    test_file.write_text(html_content, encoding="utf-8")

    res = SEO.cmd_audit(test_file, min_score=85)
    assert res["status"] == "PASS"
    assert res["results"][0]["score"] >= 85
    assert len(res["results"][0]["errors"]) == 0
    print("[PASS] test_seo_audit_and_generate (Audit passed with high score)")

    # Test JSON-LD generator
    json_ld = SEO.generate_json_ld("SoftwareApplication", "MyProduct", "A great product", "https://myproduct.com")
    assert '"@type": "SoftwareApplication"' in json_ld
    assert '"name": "MyProduct"' in json_ld

    faq_ld = SEO.generate_json_ld("FAQPage", "MyProduct", "Explanation text", "https://myproduct.com")
    assert '"@type": "FAQPage"' in faq_ld
    print("[PASS] test_seo_audit_and_generate (JSON-LD generation verified)")


def test_plugin_install_and_export_landing_seo(base_dir: Path) -> None:
    proj = base_dir / "proj_landing_seo"
    init_project(proj, "proj_landing_seo", "frontend", extension="v3.3.0")

    # Search for landing and seo
    search_res = PLUGIN.cmd_search("landing", proj)
    assert any(p["plugin"] == "landing-page-seo" for p in search_res)

    # Install landing-page-seo
    install_res = PLUGIN.cmd_install("landing-page-seo", proj, force=True)
    assert install_res["status"] == "INSTALLED"

    # Verify custom rich skill files exist and contain Part A & Part B
    landing_skill = proj / ".ai/plugins/landing-page-seo/skills/landing-page-design/SKILL.md"
    assert landing_skill.exists()
    content = landing_skill.read_text(encoding="utf-8")
    assert "PART A — Strategy and Structure" in content
    assert "PART B — Non-Negotiable Visual System" in content
    assert "A1. Intake Discovery" in content
    assert "text-wrap: balance" in content

    seo_skill = proj / ".ai/plugins/landing-page-seo/skills/technical-seo/SKILL.md"
    assert seo_skill.exists()
    assert "uaf seo audit" in seo_skill.read_text(encoding="utf-8")

    # Multi-target export
    export_res = PLUGIN.cmd_export("landing-page-seo", proj, target="all")
    assert len(export_res["files"]) >= 7
    assert (proj / ".claude/agents/landing-page-pro.md").exists()
    assert (proj / ".agents/skills/landing-page-design/SKILL.md").exists()
    assert (proj / ".cursor/rules/plugin-landing-page-seo.mdc").exists()
    print("[PASS] test_plugin_install_and_export_landing_seo")


def test_team_compose_landing_and_seo_adaptation(base_dir: Path) -> None:
    proj = base_dir / "proj_team_landing"
    init_project(proj, "proj_team_landing", "frontend", extension="v3.3.0")

    # Compose team with prompt mentioning landing page conversion and SEO
    prompt = "Design high converting SaaS landing page and optimize technical SEO structured data"
    team = TEAM.cmd_compose(proj, prompt, pattern="fan_out_fan_in")

    roles = [m["role"] for m in team["members"]]
    assert "landing_page_pro" in roles or "seo_specialist" in roles, f"Roles adapted: {roles}"

    # Verify task contracts
    for m in team["members"]:
        task_file = proj / f".ai/tasks/active/{m['task_id']}.yaml"
        assert task_file.exists()
        t_data = yaml.safe_load(task_file.read_text(encoding="utf-8"))
        if t_data["assigned_role"] == "landing_page_pro":
            assert "landing_page_design" in t_data.get("required_skills", [])
        elif t_data["assigned_role"] == "seo_specialist":
            assert "technical_seo" in t_data.get("required_skills", [])

    print("[PASS] test_team_compose_landing_and_seo_adaptation")


def test_v33_init_and_conformance_check(base_dir: Path) -> None:
    proj = base_dir / "proj_v33_conf"
    init_project(proj, "proj_v33_conf", "fullstack", extension="v3.3.0", profile="full")

    # Validate manifest structure
    manifest_data = yaml.safe_load((proj / ".ai/manifest.yaml").read_text(encoding="utf-8"))
    assert manifest_data["framework"]["version"] == "3.3.0"
    assert manifest_data["protocols"]["seo_governance"] == "UAAF-SEO-1.0"
    assert manifest_data["extensions"]["version"] == "3.3.0"
    assert "seo_governance" in manifest_data["extensions"]
    assert manifest_data["extensions"]["seo_governance"]["min_audit_score"] == 80

    # Run conformance check
    errors, warnings, infos = CHECK.check(proj, "standard")
    assert errors == [], f"Validation errors: {errors}"
    print("[PASS] test_v33_init_and_conformance_check (0 errors)")


def main() -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="uaf-v33-test-"))
    try:
        test_seo_audit_and_generate(temp_dir)
        test_plugin_install_and_export_landing_seo(temp_dir)
        test_team_compose_landing_and_seo_adaptation(temp_dir)
        test_v33_init_and_conformance_check(temp_dir)
        print("\n==========================================")
        print("ALL UAAF v3.3 NATIVE LANDING & SEO TESTS PASSED")
        print("==========================================")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
