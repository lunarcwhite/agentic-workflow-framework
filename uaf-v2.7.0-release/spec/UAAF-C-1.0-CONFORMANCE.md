# UAAF-C 1.0 — Conformance Catalog

## Status

This catalog defines normative validator categories. Severity is `ERROR`, `WARNING`, or `INFO`.

| ID | Domain | Rule |
|---|---|---|
| CONF-STR-001 | STRUCTURE | Required profile artifacts exist. |
| CONF-MAN-001..010 | MANIFEST | Manifest schema, framework, protocol, project, and profile fields are valid. |
| CONF-FEA-* | FEATURES | Enabled features have their required artifacts. |
| CONF-MEM-* | MEMORY | State/version and memory metadata are valid. |
| CONF-TASK-* | TASKS | Task contracts contain intent, requirements, AC, verification, and scope controls. |
| CONF-DEC-001 | DECISIONS | Decision records contain status, scope, decision, and rationale. |
| CONF-VER-* | VERIFICATION | Verification matrix and delivery gate semantics are present. |
| CONF-REF-* | REFERENCES | Canonical owners and referenced IDs/paths resolve. |
| CONF-MA-* | MULTI_AGENT | Registry and claims have valid shape. |
| CONF-V11-* | EXTENSIONS | Capability override and context-impact semantics are valid when v1.1+ is enabled. |
| CONF-V12-* | EXTENSIONS | Memory compaction and Strong RCE contracts are valid when v1.2+ is enabled. |
| CONF-V13-* | EXTENSIONS | Git, claim leasing, and runtime verification contracts are valid when v1.3+ is enabled. |
| CONF-V14-* | EXTENSIONS | Security, semantic Git↔Task, and runtime-evidence contracts are valid when v1.4+ is enabled. |
| CONF-V15-* | EXTENSIONS | Observability contract and privacy controls are valid when v1.5+ is enabled. |
| CONF-V16-* | EXTENSIONS | Adaptive-learning policies and advisory constraints are valid when v1.6+ is enabled. |
| CONF-V17-* | EXTENSIONS | Governance lifecycle, approval, preconditions, audit, and rollback are valid when v1.7+ is enabled. |
| CONF-V18-* | EXTENSIONS | Trust registry, delegation bounds, expiry, revocation, evidence floor, and cycle checks are valid when v1.8+ is enabled. |
| CONF-LIFE-* | LIFECYCLE | States use recognized lifecycle values and transitions. |

Conformance result is `PASS`, `PASS_WITH_WARNINGS`, or `FAIL`. The validator does not emit an overall numeric score.
