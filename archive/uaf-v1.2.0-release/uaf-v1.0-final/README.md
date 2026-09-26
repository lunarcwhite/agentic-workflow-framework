# UAAF v1.1.0 Reference Distribution

Universal AI Agent Framework reference implementation.

## Components

- `spec/` — UAAF v1.0 normative specification and conformance catalog
- `scaffold/` — project-side Minimal/Standard/Full knowledge scaffold
- `templates/` — reusable task/evidence/context/handoff artifacts
- `tools/` — distribution-side initializer and validators
- `examples/` — Northstar reference project
- `tests/` — regression, longitudinal, and field-archetype tests

## Initialize an existing project

```bash
python tools/uaf.py init ./my-project --profile standard --auto-detect --docs auto
```

Use `--docs all` for the complete documentation catalog or `--docs none` to omit `docs/`.

## UAAF v1.1 extensions

Enable additive v1.1 capabilities and Context Impact Graph support during initialization:

```bash
python tools/uaf.py init ./my-project --profile standard --auto-detect --extension v1.1
python tools/uaf.py capabilities ./my-project show
python tools/uaf.py capabilities ./my-project set frontend=force_false --reason "Project does not maintain a frontend module."
python tools/uaf.py impact ./my-project --paths docs/design/DESIGN.md src/components/Button.tsx --write
```

Capability detection is advisory. Explicit overrides are persisted with source and reason. The Context Impact Graph is advisory and does not rewrite canonical knowledge.

## Validate

```bash
python tools/uaf.py check ./my-project --level standard
python tools/uaf.py reconcile ./my-project
python tools/uaf.py doctor ./my-project --level standard
python tools/uaf.py doctor ./my-project --level standard
```

The tooling is read-only by default. Project-side artifacts contain knowledge and protocol state; implementation tooling is intentionally kept in the distribution layer.


## UAAF v1.2

Optional extensions now include conservative memory compaction and Strong RCE. Initialize with `--extension v1.2`.

```bash
python tools/uaf.py memory <project> compact
python tools/uaf.py rce <project> snapshot
python tools/uaf.py rce <project> scan
```
