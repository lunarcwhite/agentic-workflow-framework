#!/usr/bin/env python3
"""UAAF v1.4 static security diagnostics.

Read-only checks for likely secret leakage and unsafe file permissions. Never
prints matched secret values.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

SKIP_DIRS = {".git", ".hg", ".svn", ".pytest_cache", "__pycache__", "node_modules", "vendor", "dist", "build"}
MAX_FILE = 2 * 1024 * 1024
MAX_FILES = 5000

PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("SEC-SECRET-001", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "private key material"),
    ("SEC-SECRET-002", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key identifier"),
    ("SEC-SECRET-003", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"), "GitHub token-like value"),
    ("SEC-SECRET-004", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "API key-like value"),
    ("SEC-SECRET-005", re.compile(r"(?im)^\s*(?:password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*[\"']?(?!$|changeme|change_me|example|placeholder|dummy|test(?:ing)?|null|none|false)[^\"'\s]{8,}"), "credential assignment"),
]

TEXT_EXTS = {".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".env", ".py", ".js", ".ts", ".tsx", ".jsx", ".php", ".java", ".go", ".rs", ".rb", ".sh", ".sql", ".xml", ".html", ".css", ".scss"}


def iter_files(root: Path, explicit: list[str]) -> list[Path]:
    if explicit:
        result = []
        for raw in explicit:
            p = (root / raw).resolve()
            if p.is_file():
                result.append(p)
            elif p.is_dir():
                result.extend(x for x in p.rglob("*") if x.is_file())
        return result[:MAX_FILES]
    result: list[Path] = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            p = Path(base) / name
            try:
                if p.stat().st_size > MAX_FILE:
                    continue
            except OSError:
                continue
            result.append(p)
            if len(result) >= MAX_FILES:
                return result
    return result


def looks_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTS or path.name.startswith(".env"):
        return True
    try:
        data = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\x00" not in data


def tracked(root: Path, rel: str) -> bool:
    import subprocess
    p = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", "--", rel], capture_output=True, text=True)
    return p.returncode == 0


def scan(root: Path, explicit: list[str]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    inspected = 0
    for path in iter_files(root, explicit):
        rel = str(path.relative_to(root))
        if not looks_text(path):
            continue
        inspected += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for code, pattern, description in PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append({"code": code, "severity": "ERROR", "path": rel, "line": line, "description": description, "tracked": tracked(root, rel) if (root / ".git").exists() else False})
                break
        if path.name.startswith(".env") and not rel.startswith(".ai/") and not path.name.endswith(".example"):
            if tracked(root, rel) if (root / ".git").exists() else False:
                findings.append({"code": "SEC-FILE-001", "severity": "WARNING", "path": rel, "line": 1, "description": ".env-like file is tracked by Git; review whether secrets are present", "tracked": True})
        try:
            mode = path.stat().st_mode & 0o777
            if mode & 0o002:
                findings.append({"code": "SEC-PERM-001", "severity": "ERROR", "path": rel, "line": 1, "description": "world-writable file", "tracked": False})
        except OSError:
            pass
    status = "PASS"
    if any(f["severity"] == "ERROR" for f in findings):
        status = "FAIL"
    elif findings:
        status = "WARN"
    return {"status": status, "inspected_files": inspected, "findings": findings}


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.4 security diagnostics")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["scan"], nargs="?", default="scan")
    p.add_argument("--paths", nargs="*", default=[])
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    result = scan(Path(args.path).resolve(), args.paths)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["status"])
        print(f"INSPECTED {result['inspected_files']}")
        for finding in result["findings"]:
            suffix = f" line={finding['line']}" if finding.get("line") else ""
            print(f"{finding['severity']} {finding['code']} {finding['path']}{suffix}: {finding['description']}")
    raise SystemExit(1 if result["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
