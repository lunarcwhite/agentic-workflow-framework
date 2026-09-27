# UAAF v3.2 Extension Contract: Agentic Plugin Marketplace & Domain Specialists

## Extension Identity

```yaml
version: "3.2.0"
protocol: "UAAF-PLUGIN-1.0"
profile: full
mode: agentic_marketplace_and_domain_specialists
```

## Architectural Foundations

UAAF v3.2 builds directly upon the Team-Architecture Factory of v3.1, establishing an interoperable bridge to extensive agentic plugin ecosystems (such as `wshobson/agents`). It provides a governed CLI (`uaf plugin`) and dynamic runtime adapters that allow hundreds of domain-specialized agents (e.g. FastAPI, React, PostgreSQL DBA, DevOps, and QA test specialists) to be instantiated and orchestrated while strictly enforcing UAAF Golden Axioms, disjoint perimeters, and verifiable evidence receipts.

## Subsystem Capabilities

### 1. Governed Plugin Marketplace Manager (`uaf plugin`)
- **Discovery**: `uaf plugin search <query>` inspects both the local catalog index and remote GitHub registries.
- **Scaffolding**: `uaf plugin install <name>` downloads plugin manifests, agent definitions, and skills into `.ai/plugins/<name>/`.
- **Governance Mandate**: Automatically creates `.ai/plugins/<name>/GOVERNANCE.md` and generates an anchored evidence receipt in `.ai/evidence/EV-PLUGIN-<HASH>.yaml`.
- **Multi-Target Export**: Seamlessly emits native harness formats for Claude Code (`.claude/agents/*.md`), Antigravity (`.agents/skills/`, `.agents/plugins/`), Cursor (`.cursor/rules/*.mdc`), and Pi (`.pi/agents/*.md`).

### 2. Dynamic Team Role Discovery & Domain Adaptation
- The team orchestrator (`uaf team compose`) automatically discovers installed roles in `.ai/plugins/` via `discover_installed_roles()`.
- Intelligent prompt keyword matching automatically elevates generic roles (backend, frontend, qa) into domain-specialized personas (`fastapi_pro`, `django_pro`, `react_pro`, `vue_pro`, `postgresql_dba`, `devops_engineer`, `testing_specialist`).
- Task contracts (`.ai/tasks/active/TASK-*.yaml`) automatically attach required domain skills to prevent context bloat and hallucination.

## Core Invariants

1. **Governance Mandate Invariant**:
   Every installed plugin MUST contain a valid `GOVERNANCE.md` and a verified evidence receipt. Unaudited plugins are flagged by `uaf check`.
2. **Disjoint Perimeter Preservation**:
   Domain specialists operate strictly within non-overlapping `permitted_files` perimeters guarded by atomic claims locking (`.claims.lock`).
3. **Anti-Slop Hard Gate**:
   Specialist code generation must contain zero mock stubs, empty placeholders, or silent regressions.
4. **Verifiable Receipts**:
   Task completion claims require exit code 0 test executions and cryptographic hashes.

## Conformance Assertions

- `CONF-V32-001`: `protocols.plugin_marketplace` must be `UAAF-PLUGIN-1.0`.
- `CONF-V32-002`: `extensions.plugin_marketplace` section must be present when extension version is `3.2.0`.
- `CONF-V32-003`: Every directory in `.ai/plugins/` must contain a valid `GOVERNANCE.md`.
