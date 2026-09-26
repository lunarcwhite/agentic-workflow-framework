#!/usr/bin/env python3
"""Task-contract fingerprint utility for UAAF v1.0.

Supports canonical YAML task contracts. Markdown task records can be checked for
presence of an integrity block but are not rewritten by this utility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

FIELDS = ["intent", "requirements", "constraints", "non_goals"]


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute(data: dict[str, Any]) -> dict[str, str]:
    return {f"{field}_hash": canonical_hash(data.get(field)) for field in FIELDS}


def load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("task contract must be a YAML mapping")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Check or print UAAF task-contract fingerprints")
    parser.add_argument("contract")
    parser.add_argument("--write", action="store_true", help="write computed hashes into the YAML contract")
    args = parser.parse_args()

    path = Path(args.contract).resolve()
    data = load(path)
    computed = compute(data)
    stored = ((data.get("integrity") or {}) if isinstance(data.get("integrity"), dict) else {})
    mismatches = {k: (stored.get(k), v) for k, v in computed.items() if stored.get(k) not in (None, "", v)}

    if args.write:
        data.setdefault("integrity", {}).update(computed)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        print("WRITTEN")
        return

    for k, v in computed.items():
        print(f"{k}: {v}")
    if mismatches:
        print("STATUS: MISMATCH")
        raise SystemExit(1)
    if not all(stored.get(k) for k in computed):
        print("STATUS: UNPINNED")
        raise SystemExit(2)
    print("STATUS: VALID")


if __name__ == "__main__":
    main()
