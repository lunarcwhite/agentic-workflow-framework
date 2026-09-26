# UAAF v1.8.0 Reference Distribution

Universal AI Agent Framework reference implementation.

## Components

- `spec/` — normative specification and extension contracts
- `scaffold/` — project-side Minimal/Standard/Full knowledge scaffold
- `templates/` — reusable task/evidence/context/handoff artifacts
- `tools/` — distribution-side initializer, validators, RCE, memory, coordination, security, and delivery tools
- `examples/` — Northstar reference project
- `tests/` — regression, longitudinal, field-archetype, and extension tests

## Initialize an existing project

```bash
python tools/uaf.py init ./my-project --profile standard --auto-detect --docs auto
```

Use `--docs all` for the complete documentation catalog or `--docs none` to omit `docs/`.

The v1.5 Context Receipt template supports optional `estimated_tokens` and declared `usage` fields for observability; these contain metadata only.

## Extensions

Versions are cumulative. Selecting a later version includes earlier extension layers.

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

### v1.4 — Security + Semantic Trace + Delivery Evidence

```bash
python tools/uaf.py init ./my-project --profile full --auto-detect --extension v1.4
python tools/uaf.py security ./my-project scan
python tools/uaf.py git-task ./my-project trace --task TASK-0001
python tools/uaf.py delivery ./my-project check --task TASK-0001
```

### v1.5 — Context Economics & Observability

```bash
python tools/uaf.py init ./my-project --profile full --auto-detect --extension v1.5
python tools/uaf.py observe ./my-project report
python tools/uaf.py observe ./my-project check
python tools/uaf.py observe ./my-project record memory --task TASK-0001 --retrieved MEM-0001 MEM-0002 --reused MEM-0001
python tools/uaf.py observe ./my-project record gate --task TASK-0001 --status DONE --evidence-depth E3
```

Observability is metadata-first. It measures context volume/repetition, memory health/reuse, gate outcomes, and replanning without storing prompt or source contents.

Runtime verification is disabled by default. Enable it only for exact trusted commands in `.ai/verification/RUNTIME-POLICY.yaml`; commands run without a shell and produce evidence receipts. Delivery Gate consumes those receipts only when runtime evidence is required by policy or the task contract.

### v1.6 — Adaptive Learning & Context Optimization

```bash
python tools/uaf.py init ./my-project --profile full --auto-detect --extension v1.6
python tools/uaf.py adapt ./my-project analyze
python tools/uaf.py adapt ./my-project recommend
python tools/uaf.py adapt ./my-project analyze --write
python tools/uaf.py adapt ./my-project check
```

v1.6 consumes v1.5 metadata-first telemetry and produces advisory recommendations for context retrieval, memory reuse, planning, and Delivery Gate outcomes. It never mutates intent, policy, or memory automatically.

## Validation

```bash
python tools/uaf.py check ./my-project --level full
python tools/uaf.py reconcile ./my-project
python tools/uaf.py doctor ./my-project --level full
```

`uaf check`, `uaf reconcile`, Git inspection, security diagnostics, and delivery evaluation are read-only. Claim mutations are atomic and lease-based. Runtime verification is explicit and allowlisted.

## Distribution vs project layer

Project-side `.ai/` files contain knowledge and protocol state. The Python tooling stays in the distribution layer so an initialized project does not silently become a copy of the UAAF development repository.

## UAAF v1.7

Policy Governance & Safe Adaptation turns advisory optimization proposals into governed, auditable changes. Apply requires explicit reviewer approval, precondition hashes, an allowlisted YAML mutation path, and a rollback snapshot. Intent and safety controls cannot be mutated by safe apply.


### v1.8 — Agent Trust & Delegation

```bash
python tools/uaf.py init ./my-project --profile full --auto-detect --extension v1.8
python tools/uaf.py trust ./my-project check
python tools/uaf.py trust ./my-project status --json
python tools/uaf.py trust ./my-project evaluate --agent AGENT-CODE --capability write --domain backend --risk HIGH --min-evidence E3
```

v1.8 separates capability, authority, and explicit delegation. Delegations are bounded by domain, risk, evidence floor, expiry, and non-escalation rules. Recent verified-evidence history may trigger review but never increases authority automatically.
