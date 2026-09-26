#!/usr/bin/env python3
"""Unified UAAF distribution CLI."""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMMANDS = {
    "init": "uaf_init.py",
    "check": "uaf_check.py",
    "doctor": "uaf_doctor.py",
    "capabilities": "uaf_capabilities.py",
    "impact": "uaf_context_impact.py",
    "contract": "uaf_contract.py",
    "reconcile": "uaf_reconcile.py",
    "migration": "uaf_migration_check.py",
    "memory": "uaf_memory_compact.py",
    "rce": "uaf_rce_strong.py",
    "git": "uaf_git_trace.py",
    "claims": "uaf_claims.py",
    "runtime": "uaf_runtime.py",
    "security": "uaf_security.py",
    "git-task": "uaf_git_task.py",
    "delivery": "uaf_delivery.py",
    "observe": "uaf_observe.py",
    "adapt": "uaf_adaptive.py",
    "governance": "uaf_governance.py",
    "trust": "uaf_trust.py",
    "crypto": "uaf_crypto.py",
    "federation": "uaf_federation.py",
    "federation-ops": "uaf_federation_ops.py",
    "federation-policy": "uaf_federation_policy.py",
    "federation-intel": "uaf_federation_intel.py",
    "federation-negotiation": "uaf_federation_negotiation.py",
    "federation-enforce": "uaf_federation_enforce.py",
    "federation-protocol": "uaf_federation_protocol.py",
    "federation-transport": "uaf_federation_transport.py",
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="uaf", description="Universal AI Agent Framework CLI")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args, rest = parser.parse_known_args()
    sys.argv = [str(ROOT / COMMANDS[args.command]), *rest]
    runpy.run_path(str(ROOT / COMMANDS[args.command]), run_name="__main__")


if __name__ == "__main__":
    main()
