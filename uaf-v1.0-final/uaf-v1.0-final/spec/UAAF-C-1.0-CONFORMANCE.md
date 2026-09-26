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
| CONF-LIFE-* | LIFECYCLE | States use recognized lifecycle values and transitions. |

Conformance result is `PASS`, `PASS_WITH_WARNINGS`, or `FAIL`. The validator does not emit an overall numeric score.
