# UAAF v1.3.0 Reference Distribution

Universal AI Agent Framework reference implementation.

## Components

- `spec/` — normative specification and extension contracts
- `scaffold/` — project-side Minimal/Standard/Full knowledge scaffold
- `templates/` — reusable task/evidence/context/handoff artifacts
- `tools/` — distribution-side initializer, validators, RCE, memory, coordination, and runtime tools
- `examples/` — Northstar reference project
- `tests/` — regression, longitudinal, field-archetype, and v1.3 tests

## Initialize an existing project

```bash
python tools/uaf.py init ./my-project --profile standard --auto-detect --docs auto
```

Use `--docs all` for the complete documentation catalog or `--docs none` to omit `docs/`.

## Extensions

Versions are cumulative: selecting v1.3 includes the v1.1 and v1.2 extensions as well as the v1.3 additions. v1.3 requires the Full profile.

### v1.1 — Capability + Context Impact

```bash
python tools/uaf.py init ./my-project --profile full --auto-detect --extension v1.1
python tools/uaf.py capabilities ./my-project show
python tools/uaf.py impact ./my-project --paths docs/design/DESIGN.md src/components/Button.tsx --write
```

### v1.2 — Memory Compaction + Strong RCE

```bash
python tools/uaf.py init ./my-project --profile full --auto-detect --extension v1.2
python tools/uaf.py memory ./my-project compact
python tools/uaf.py rce ./my-project snapshot
python tools/uaf.py rce ./my-project scan
```

### v1.3 — Git + Claims + Runtime

```bash
python tools/uaf.py init ./my-project --profile full --auto-detect --extension v1.3
python tools/uaf.py git ./my-project snapshot
python tools/uaf.py git ./my-project trace --task TASK-0001
python tools/uaf.py claims ./my-project acquire --resource src/service.py --agent AGENT-CODE --task TASK-0001 --lease 900
python tools/uaf.py claims ./my-project release --claim-id CLM-0001 --agent AGENT-CODE
python tools/uaf.py runtime ./my-project policy
```

Runtime verification is disabled by default. Enable it only for exact trusted commands in `.ai/verification/RUNTIME-POLICY.yaml`; commands run without a shell and produce evidence receipts.

## Validation

```bash
python tools/uaf.py check ./my-project --level full
python tools/uaf.py reconcile ./my-project
python tools/uaf.py doctor ./my-project --level full
```

`uaf check`, `uaf reconcile`, `uaf git`, and migration inspection are read-only. Claim mutations are atomic and lease-based. Runtime verification is explicit and allowlisted.

## Distribution vs project layer

Project-side `.ai/` files contain knowledge and protocol state. The Python tooling stays in the distribution layer so an initialized project does not silently become a copy of the UAAF development repository.
