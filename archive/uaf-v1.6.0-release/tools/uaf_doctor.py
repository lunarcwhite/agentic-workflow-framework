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
        try:
            ext_number = float(ext_version)
        except ValueError:
            ext_number = 0.0
        v11_enabled = ext_number >= 1.1
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

        if ext_number >= 1.2:
            mem_rc, mem_out = run_tool("uaf_memory_compact.py", root, "--check")
            rce_strong_rc, rce_strong_out = run_tool("uaf_rce_strong.py", root, "scan")
            v11_checks.update({
                "memory_compaction": {"returncode": mem_rc, "output": mem_out},
                "rce_strong": {"returncode": rce_strong_rc, "output": rce_strong_out},
            })
        if ext_number >= 1.3:
            git_rc, git_out = run_tool("uaf_git_trace.py", root, "status")
            claims_rc, claims_out = run_tool("uaf_claims.py", root, "status")
            runtime_rc, runtime_out = run_tool("uaf_runtime.py", root, "policy")
            v11_checks.update({
                "git": {"returncode": git_rc, "output": git_out},
                "claims": {"returncode": claims_rc, "output": claims_out},
                "runtime": {"returncode": runtime_rc, "output": runtime_out},
            })
        if ext_number >= 1.4:
            sec_rc, sec_out = run_tool("uaf_security.py", root, "scan")
            # Git↔Task and delivery checks are task-scoped. On a fresh scaffold
            # without an active TASK-0001 they are reported as not configured,
            # rather than being treated as a framework failure.
            active_task_id = None
            tasks_root = root / ".ai/tasks"
            if tasks_root.exists():
                try:
                    import yaml
                    for task_path in sorted(tasks_root.rglob("TASK-*.yaml")):
                        try:
                            task_data = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
                        except Exception:
                            continue
                        status = str(task_data.get("status", "")).upper()
                        if status in {"ACTIVE", "IN_PROGRESS"}:
                            candidate = str(task_data.get("id", ""))
                            if candidate:
                                active_task_id = candidate
                                break
                except Exception:
                    active_task_id = None
            if active_task_id:
                gt_rc, gt_out = run_tool("uaf_git_task.py", root, "trace", "--task", active_task_id)
                delivery_rc, delivery_out = run_tool("uaf_delivery.py", root, "check", "--task", active_task_id)
            else:
                gt_rc, gt_out = 0, "NOT_CONFIGURED (no active task)"
                delivery_rc, delivery_out = 0, "NOT_CONFIGURED (no active task)"
            v11_checks.update({
                "security": {"returncode": sec_rc, "output": sec_out},
                "git_task": {"returncode": gt_rc, "output": gt_out},
                "delivery": {"returncode": delivery_rc, "output": delivery_out},
            })
        if ext_number >= 1.5:
            obs_rc, obs_out = run_tool("uaf_observe.py", root, "check")
            v11_checks["observability"] = {"returncode": obs_rc, "output": obs_out}
        if ext_number >= 1.6:
            adapt_rc, adapt_out = run_tool("uaf_adaptive.py", root, "check")
            v11_checks["adaptive_learning"] = {"returncode": adapt_rc, "output": adapt_out}

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
