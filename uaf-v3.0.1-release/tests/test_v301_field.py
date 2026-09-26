#!/usr/bin/env python3
"""UAAF v3.0.1 clean-state and archetype validation."""
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


def init_project(destination: Path, name: str, kind: str, extension: str = "v3.0.1", profile: str = "full", force: bool = False) -> None:
    old = sys.argv
    try:
        args = ["uaf_init.py", str(destination), "--profile", profile, "--name", name, "--type", kind]
        if extension != "none":
            args.extend(["--extension", extension])
        if force:
            args.append("--force")
        sys.argv = args
        INIT.main()
    finally:
        sys.argv = old


def main() -> None:
    base = Path(tempfile.mkdtemp(prefix="uaf-v301-field-"))
    try:
        # Validate 5 archetypes sequentially
        archetypes = [
            ("backend", "service"),
            ("frontend", "web"),
            ("cli", "tool"),
            ("docs", "docs"),
            ("infra", "ops"),
        ]
        for kind, name in archetypes:
            project = base / name
            init_project(project, name, kind, extension="v3.0.1")
            manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text(encoding="utf-8"))
            assert manifest["framework"]["version"] == "3.0.1"
            assert manifest["extensions"]["version"] == "3.0.1"
            assert (project / ".ai/memory/entries").exists()
            assert (project / ".ai/federation/runtime/POLICY.yaml").exists()

            # Verify that conformance validator emits 0 warnings and 0 errors.
            errors: list[str] = []
            warnings: list[str] = []
            CHECK.validate_v30_extensions(project, manifest, errors, warnings)
            assert not errors, f"Errors found in {name}: {errors}"
            assert not warnings, f"Warnings found in {name}: {warnings}"
            shutil.rmtree(project, ignore_errors=True)
            gc.collect()

        # Validate minimal, standard, and full clean profiles
        for prof in ["minimal", "standard", "full"]:
            prof_proj = base / f"prof_{prof}"
            ext = "v3.0.1" if prof == "full" else "none"
            init_project(prof_proj, f"prof_{prof}", "service", extension=ext, profile=prof)
            level = "core" if prof == "minimal" else prof
            res_errors, res_warnings, _ = CHECK.check(prof_proj, level=level)
            assert not res_errors, f"Errors in {prof}: {res_errors}"
            assert not res_warnings, f"Warnings in {prof}: {res_warnings}"
            shutil.rmtree(prof_proj, ignore_errors=True)
            gc.collect()

        print("V3.0.1 ALL 5 ARCHETYPES + MINIMAL/STANDARD/FULL CLEAN CONFORMANCE PASSED")
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
