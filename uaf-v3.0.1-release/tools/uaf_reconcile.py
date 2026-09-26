#!/usr/bin/env python3
"""UAAF RCE baseline: detect broken references and simple knowledge drift signals.

Read-only by design. It never rewrites semantic content.
"""
import argparse
from pathlib import Path
import re
import yaml


def frontmatter(text: str):
    if not text.startswith('---\n'):
        return {}
    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}


def main():
    p = argparse.ArgumentParser(description='Run UAAF Reality & Consistency checks')
    p.add_argument('path', nargs='?', default='.')
    args = p.parse_args()
    root = Path(args.path).resolve()
    errors, warnings, info = [], [], []

    # Memory source integrity.
    entries = root / '.ai/memory/entries'
    if entries.exists():
        for f in entries.glob('*.md'):
            meta = frontmatter(f.read_text(encoding='utf-8'))
            for source in meta.get('source', []) or []:
                source = str(source)
                # Task / decision / evidence IDs are checked against plausible locations.
                if re.fullmatch(r'TASK-\d+', source):
                    found = list((root / '.ai/tasks').glob(f'**/{source}*'))
                    if not found:
                        warnings.append(f'RCE-MEM-001 {f.name}: source {source} not found')
                elif re.fullmatch(r'DEC-\d+', source):
                    if not list((root / '.ai/decisions').glob(f'{source}*')):
                        warnings.append(f'RCE-MEM-002 {f.name}: decision {source} not found')
                elif re.fullmatch(r'EVD-\d+', source):
                    if not list((root / '.ai/evidence').glob(f'{source}*')):
                        warnings.append(f'RCE-MEM-003 {f.name}: evidence {source} not found')

    # Evidence source integrity.
    evidence = root / '.ai/evidence'
    if evidence.exists():
        for f in evidence.glob('*.yaml'):
            try:
                data = yaml.safe_load(f.read_text(encoding='utf-8')) or {}
            except Exception as exc:
                errors.append(f'RCE-EVD-001 invalid evidence file {f.name}: {exc}')
                continue
            for source in data.get('sources', []) or []:
                src = root / str(source)
                if not src.exists():
                    warnings.append(f'RCE-EVD-002 {f.name}: source path missing: {source}')

    # Manifest source-of-truth references.
    manifest = root / '.ai/manifest.yaml'
    if manifest.exists():
        try:
            data = yaml.safe_load(manifest.read_text(encoding='utf-8')) or {}
            for domain, owner in (data.get('source_of_truth') or {}).items():
                if owner == 'repository':
                    continue
                if not (root / str(owner)).exists():
                    warnings.append(f'RCE-SOT-001 {domain}: canonical owner missing: {owner}')
        except Exception as exc:
            errors.append(f'RCE-MAN-001 cannot parse manifest: {exc}')

    status = 'CONFLICT' if errors else ('DRIFT' if warnings else 'CONSISTENT')
    print(status)
    for x in errors: print('ERROR', x)
    for x in warnings: print('WARNING', x)
    for x in info: print('INFO', x)
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
