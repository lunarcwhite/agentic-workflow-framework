"""Regression and conformance tests for UAAF WebForge Project Kit."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None

WORKSPACE = Path(__file__).resolve().parents[1]
KIT_DIR = WORKSPACE / "uaaf-webforge-kit"
TOOLS_DIR = WORKSPACE / "tools"


def test_webforge_kit_tools_integrity():
    """Ensure all required runtime and validation tools are present in the kit."""
    assert KIT_DIR.exists(), f"Kit directory {KIT_DIR} must exist"
    
    tools_dir = KIT_DIR / "tools"
    assert tools_dir.exists(), "tools/ directory must exist in kit"
    
    required_tools = ["uaf.py", "uaf_check.py", "uaf_seo.py", "uaf_blocker.py"]
    for tool in required_tools:
        tool_path = tools_dir / tool
        assert tool_path.is_file(), f"Missing required tool {tool} in {tools_dir}"
        assert tool_path.stat().st_size > 0, f"Tool {tool} is empty"


def test_webforge_kit_conformance_check_python():
    """Verify that uaf_check validator passes on uaaf-webforge-kit with zero errors."""
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    import uaf_check

    errors, warnings, _ = uaf_check.check(KIT_DIR, level="standard")
    assert errors == [], f"Kit failed conformance check with errors: {errors}"


def test_webforge_kit_cli_check_execution():
    """Verify that 'python tools/uaf.py check' runs successfully inside the kit without FileNotFoundError."""
    res = subprocess.run(
        [sys.executable, str(KIT_DIR / "tools" / "uaf.py"), "check"],
        cwd=str(KIT_DIR),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"uaf check failed with code {res.returncode}. Stderr: {res.stderr}"
    assert "PASS" in res.stdout, f"'PASS' not found in stdout: {res.stdout}"
    assert "FileNotFoundError" not in res.stderr


def test_webforge_kit_cli_blocker_execution():
    """Verify that 'python tools/uaf.py blocker --list' runs successfully inside the kit."""
    res = subprocess.run(
        [sys.executable, str(KIT_DIR / "tools" / "uaf.py"), "blocker", "--list"],
        cwd=str(KIT_DIR),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"uaf blocker failed with code {res.returncode}. Stderr: {res.stderr}"
    assert "None recorded" in res.stdout or "-" in res.stdout


if __name__ == "__main__":
    print("Running test_webforge_kit_tools_integrity...")
    test_webforge_kit_tools_integrity()
    print("Running test_webforge_kit_conformance_check_python...")
    test_webforge_kit_conformance_check_python()
    print("Running test_webforge_kit_cli_check_execution...")
    test_webforge_kit_cli_check_execution()
    print("Running test_webforge_kit_cli_blocker_execution...")
    test_webforge_kit_cli_blocker_execution()
    print("All tests passed successfully!")

