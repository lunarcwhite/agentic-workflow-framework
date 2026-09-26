#!/usr/bin/env python3
"""Aggregate UAAF diagnostic checks without mutating the project."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent


def run_tool(script: str, path: Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(TOOLS_DIR / script), str(path), *extra],
        text=True,
        capture_output=True,
    )
    return proc.returncode, proc.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run UAAF aggregate diagnostics")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--level", choices=["minimal", "core", "standard", "full"], default="standard")
    parser.add_argument("--strict", action="store_true", help="treat validator warnings as failures")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.path).resolve()

    check_args = ["--level", args.level]
    if args.strict:
        check_args.append("--strict")
    check_rc, check_out = run_tool("uaf_check.py", root, *check_args)
    rce_rc, rce_out = run_tool("uaf_reconcile.py", root)
    mig_rc, mig_out = run_tool("uaf_migration_check.py", root)

    manifest_path = root / ".ai/manifest.yaml"
    v11_enabled = False
    try:
        import yaml
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        ext_version = str((manifest.get("extensions") or {}).get("version", ""))
        v11_enabled = ext_version in {"1.1", "1.2", "1.3", "1.4"}
    except Exception:
        pass

    v11_checks = {}
    if v11_enabled:
        cap_rc, cap_out = run_tool("uaf_capabilities.py", root, "show")
        impact_rc, impact_out = run_tool("uaf_context_impact.py", root)
        v11_checks = {
            "capabilities": {"returncode": cap_rc, "output": cap_out},
            "context_impact": {"returncode": impact_rc, "output": impact_out},
        }

        if ext_version in {"1.2", "1.3", "1.4"}:
            mem_rc, mem_out = run_tool("uaf_memory_compact.py", root, "--check")
            rce_strong_rc, rce_strong_out = run_tool("uaf_rce_strong.py", root, "scan")
            v11_checks.update({
                "memory_compaction": {"returncode": mem_rc, "output": mem_out},
                "rce_strong": {"returncode": rce_strong_rc, "output": rce_strong_out},
            })
        if ext_version in {"1.3", "1.4"}:
            git_rc, git_out = run_tool("uaf_git_trace.py", root, "status")
            claims_rc, claims_out = run_tool("uaf_claims.py", root, "status")
            runtime_rc, runtime_out = run_tool("uaf_runtime.py", root, "policy")
            v11_checks.update({
                "git": {"returncode": git_rc, "output": git_out},
                "claims": {"returncode": claims_rc, "output": claims_out},
                "runtime": {"returncode": runtime_rc, "output": runtime_out},
            })
        if ext_version == "1.4":
            sec_rc, sec_out = run_tool("uaf_security.py", root, "scan")
            # Git↔Task and delivery checks are task-scoped. On a fresh scaffold
            # without an active TASK-0001 they are reported as not configured,
            # rather than being treated as a framework failure.
            task_exists = bool(list((root / ".ai/tasks").rglob("TASK-0001*.yaml"))) if (root / ".ai/tasks").exists() else False
            if task_exists:
                gt_rc, gt_out = run_tool("uaf_git_task.py", root, "trace", "--task", "TASK-0001")
                delivery_rc, delivery_out = run_tool("uaf_delivery.py", root, "check", "--task", "TASK-0001")
            else:
                gt_rc, gt_out = 0, "NOT_CONFIGURED (no TASK-0001 artifact)"
                delivery_rc, delivery_out = 0, "NOT_CONFIGURED (no TASK-0001 artifact)"
            v11_checks.update({
                "security": {"returncode": sec_rc, "output": sec_out},
                "git_task": {"returncode": gt_rc, "output": gt_out},
                "delivery": {"returncode": delivery_rc, "output": delivery_out},
            })

    all_v11_ok = all(item.get("returncode", 0) == 0 for item in v11_checks.values())
    payload = {
        "status": "PASS" if check_rc == 0 and rce_rc == 0 and mig_rc == 0 and all_v11_ok else "FAIL",
        "checks": {
            "conformance": {"returncode": check_rc, "output": check_out},
            "reality": {"returncode": rce_rc, "output": rce_out},
            "migration": {"returncode": mig_rc, "output": mig_out},
            **v11_checks,
        },
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload["status"])
        print(f"CONFORMANCE {check_rc}")
        print(f"REALITY {rce_rc}")
        print(f"MIGRATION {mig_rc}")
        for name, item in v11_checks.items():
            print(f"{name.upper()} {item['returncode']}")
    raise SystemExit(0 if payload["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
