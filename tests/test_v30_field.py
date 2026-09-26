#!/usr/bin/env python3
"""UAAF v3.0 field validation across representative project archetypes."""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


INIT = load("uaf_init_field", ROOT / "tools/uaf_init.py")
CHECK = load("uaf_check_field", ROOT / "tools/uaf_check.py")

def init_project(path: Path, name: str, kind: str, force: bool = False) -> None:
    old = sys.argv
    try:
        sys.argv = ["uaf_init.py", str(path), "--profile", "full", "--extension", "v3.0", "--name", name, "--type", kind] + (["--force"] if force else [])
        try:
            INIT.main()
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
    finally:
        sys.argv = old


def main() -> None:
    base = Path(tempfile.mkdtemp(prefix="uaf-v30-field-"))
    try:
        archetypes = [
            ("backend", "service"),
            ("frontend", "web"),
            ("cli", "tool"),
            ("docs", "docs"),
            ("infra", "ops"),
        ]
        for kind, name in archetypes:
            project = base / name
            init_project(project, name, kind)
            manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text(encoding="utf-8"))
            assert manifest["framework"]["version"] == "3.0.0"
            assert manifest["extensions"]["version"] == "3.0"
            assert (project / ".ai/federation/runtime/POLICY.yaml").exists()

        check_project = base / "service"
        errors: list[str] = []; warnings: list[str] = []
        CHECK.validate_v30_extensions(check_project, yaml.safe_load((check_project / ".ai/manifest.yaml").read_text()), errors, warnings)
        assert not errors, errors
        preserve = base / "preserve"
        init_project(preserve, "preserve", "backend")
        marker = preserve / "USER-PRESERVE-MARKER.txt"
        marker.write_text("do not remove\n", encoding="utf-8")
        init_project(preserve, "preserve", "backend", force=True)
        assert marker.exists() and marker.read_text(encoding="utf-8") == "do not remove\n"

        # Explicit downgrade: v3 runtime is removed while unrelated user content survives.
        old = sys.argv
        try:
            sys.argv = ["uaf_init.py", str(preserve), "--profile", "full", "--extension", "v2.9", "--name", "preserve", "--type", "backend", "--force"]
            try:
                INIT.main()
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise
        finally:
            sys.argv = old
        downgraded = yaml.safe_load((preserve / ".ai/manifest.yaml").read_text(encoding="utf-8"))
        assert downgraded["framework"]["version"] == "2.9.0"
        assert downgraded["extensions"]["version"] == "2.9"
        assert not (preserve / ".ai/federation/runtime/POLICY.yaml").exists()
        assert marker.exists()
        print("FIELD 5/5 + PRESERVE + DOWNGRADE PASSED")
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
