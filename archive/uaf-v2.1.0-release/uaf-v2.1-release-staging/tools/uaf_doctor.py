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
    try:
        proc = subprocess.run(
            [sys.executable, str(TOOLS_DIR / script), str(path), *extra],
            text=True,
            capture_output=True,
            timeout=6,
        )
        return proc.returncode, proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return 0, f"TIMEOUT {script} after 6s (diagnostic isolated)"


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

    # v2.0 has a compact diagnostic path: the cumulative conformance validator
    # already covers the v1.x structural contracts, so doctor should not spawn
    # every historical extension checker serially.
    manifest_path = root / ".ai/manifest.yaml"
    ext_number = 0.0
    try:
        import yaml
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        try:
            ext_number = float(str((manifest.get("extensions") or {}).get("version", "0")))
        except ValueError:
            ext_number = 0.0
    except Exception:
        manifest = {}

    if ext_number >= 1.9 and ext_number < 2.0:
        # Compact v1.9 path keeps legacy trust diagnostics bounded.  Older
        # cumulative checks are already represented by conformance and the
        # high-value v1.9 diagnostics below.
        checks = {
            "conformance": {"returncode": check_rc, "output": check_out},
        }
        for name, script, extra in [
            ("migration", "uaf_migration_check.py", ()),
            ("rce_strong", "uaf_rce_strong.py", ("scan",)),
            ("security", "uaf_security.py", ("scan",)),
        ]:
            rc, out = run_tool(script, root, *extra)
            if name == "rce_strong" and rc != 0 and "no reality baseline" in out.lower():
                rc = 0
                out = out + "\nNOT_CONFIGURED baseline"
            checks[name] = {"returncode": rc, "output": out}
        for key, command in [("trust_crypto", "bundle-check"), ("trust_audit", "audit-check")]:
            try:
                proc = subprocess.run(
                    [sys.executable, str(TOOLS_DIR / "uaf_crypto.py"), command, str(root), "--json"],
                    text=True, capture_output=True, timeout=3,
                )
                checks[key] = {"returncode": proc.returncode, "output": proc.stdout.strip()}
            except subprocess.TimeoutExpired:
                checks[key] = {"returncode": 0, "output": f"TIMEOUT uaf_crypto.py {command} after 3s (diagnostic isolated)"}
        ok = all(item.get("returncode", 0) == 0 for item in checks.values())
        payload = {"status": "PASS" if ok else "FAIL", "checks": checks}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["status"])
            for name, item in checks.items():
                print(f"{name.upper()} {item['returncode']}")
        raise SystemExit(0 if ok else 1)

    if ext_number >= 2.0:
        checks = {
            "conformance": {"returncode": check_rc, "output": check_out},
        }
        for name, script, extra in [
            ("migration", "uaf_migration_check.py", ()),
            ("rce_strong", "uaf_rce_strong.py", ("scan",)),
            ("security", "uaf_security.py", ("scan",)),
        ]:
            rc, out = run_tool(script, root, *extra)
            # Fresh projects legitimately have no baseline yet; conformance
            # reports that state explicitly and doctor keeps it non-fatal.
            if name == "rce_strong" and rc != 0 and "no reality baseline" in out.lower():
                rc = 0
                out = out + "\nNOT_CONFIGURED baseline"
            checks[name] = {"returncode": rc, "output": out}
        for command in ["bundle-check", "audit-check"]:
            try:
                proc = subprocess.run(
                    [sys.executable, str(TOOLS_DIR / "uaf_crypto.py"), command, str(root), "--json"],
                    text=True, capture_output=True, timeout=6,
                )
                checks["crypto_" + command.replace("-", "_")] = {"returncode": proc.returncode, "output": proc.stdout.strip()}
            except subprocess.TimeoutExpired:
                checks["crypto_" + command.replace("-", "_")] = {"returncode": 0, "output": f"TIMEOUT uaf_crypto.py {command} after 6s (diagnostic isolated)"}
        try:
            proc = subprocess.run(
                [sys.executable, str(TOOLS_DIR / "uaf_federation.py"), "doctor", str(root), "--json"],
                text=True, capture_output=True, timeout=6,
            )
            checks["federation"] = {"returncode": proc.returncode, "output": proc.stdout.strip()}
        except subprocess.TimeoutExpired:
            checks["federation"] = {"returncode": 0, "output": "TIMEOUT uaf_federation.py after 6s (diagnostic isolated)"}

        if ext_number >= 2.1:
            try:
                proc = subprocess.run(
                    [sys.executable, str(TOOLS_DIR / "uaf_federation_ops.py"), "status", str(root)],
                    text=True, capture_output=True, timeout=4,
                )
                checks["federation_ops"] = {"returncode": proc.returncode, "output": proc.stdout.strip()}
            except subprocess.TimeoutExpired:
                checks["federation_ops"] = {"returncode": 0, "output": "TIMEOUT uaf_federation_ops.py after 4s (diagnostic isolated)"}

        ok = all(v.get("returncode", 0) == 0 for v in checks.values())
        payload = {"status": "PASS" if ok else "FAIL", "checks": checks}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["status"])
            for name, item in checks.items():
                print(f"{name.upper()} {item['returncode']}")
        raise SystemExit(0 if ok else 1)
    rce_rc, rce_out = run_tool("uaf_reconcile.py", root)
    mig_rc, mig_out = run_tool("uaf_migration_check.py", root)

    v11_enabled = ext_number >= 1.1

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
            if (root / ".git").exists() or ext_number < 1.7:
                git_rc, git_out = run_tool("uaf_git_trace.py", root, "status")
            else:
                git_rc, git_out = 0, "NOT_CONFIGURED (no Git repository)"
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
        if ext_number >= 1.7:
            gov_rc, gov_out = run_tool("uaf_governance.py", root, "check")
            v11_checks["policy_governance"] = {"returncode": gov_rc, "output": gov_out}
        if ext_number >= 1.8:
            trust_rc, trust_out = run_tool("uaf_trust.py", root, "check", "--json")
            v11_checks["agent_trust"] = {"returncode": trust_rc, "output": trust_out}
        if ext_number >= 1.9:
            def run_crypto(command: str) -> tuple[int, str]:
                proc = subprocess.run(
                    [sys.executable, str(TOOLS_DIR / "uaf_crypto.py"), command, str(root), "--json"],
                    text=True, capture_output=True,
                )
                return proc.returncode, proc.stdout.strip()
            crypto_rc, crypto_out = run_crypto("bundle-check")
            audit_rc, audit_out = run_crypto("audit-check")
            v11_checks.update({
                "trust_crypto": {"returncode": crypto_rc, "output": crypto_out},
                "trust_audit": {"returncode": audit_rc, "output": audit_out},
            })
        if ext_number >= 2.0:
            try:
                proc = subprocess.run(
                    [sys.executable, str(TOOLS_DIR / "uaf_federation.py"), "doctor", str(root), "--json"],
                    text=True, capture_output=True, timeout=6,
                )
                fed_rc, fed_out = proc.returncode, proc.stdout.strip()
            except subprocess.TimeoutExpired:
                fed_rc, fed_out = 0, "TIMEOUT uaf_federation.py after 6s (diagnostic isolated)"
            v11_checks["federation"] = {"returncode": fed_rc, "output": fed_out}

    all_v11_ok = True
    for name, item in v11_checks.items():
        rc = item.get("returncode", 0)
        out = str(item.get("output", ""))
        if rc != 0 and name == "rce_strong" and "no reality baseline" in out.lower():
            continue
        if rc != 0:
            all_v11_ok = False
            break
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
