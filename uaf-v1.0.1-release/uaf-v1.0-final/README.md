# UAAF v1.0.1 Reference Distribution

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
python tools/uaf_init.py ./my-project --profile standard --auto-detect --docs auto
```

Use `--docs all` for the complete documentation catalog or `--docs none` to omit `docs/`.

## Validate

```bash
python tools/uaf_check.py ./my-project --level standard
python tools/uaf_reconcile.py ./my-project
python tools/uaf_doctor.py ./my-project --level standard
```

The tooling is read-only by default. Project-side artifacts contain knowledge and protocol state; implementation tooling is intentionally kept in the distribution layer.
