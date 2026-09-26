# UAAF v2.2 — Federation Policy & Conflict Intelligence

**Status:** Release Candidate
**Version:** 2.2.0
**Protocol:** UAAF-FED-2.2

## Purpose

v2.2 adds an advisory intelligence layer over v2.0/v2.1 federation. It does not replace cryptographic trust, local authorization, or explicit conflict approval.

## Policy inheritance

Policy inheritance forms a restriction chain. A child policy may narrow an inherited policy but MUST NOT widen it. Allowed actions are intersected; denied actions are unioned; risk ceilings use the most restrictive ceiling; evidence floors use the strongest requirement; signed-state/handoff requirements and approval requirements are monotonic. Cycles MUST fail closed.

Effective policy is materialized as a derived artifact and is not a replacement for signed root policy.

## Conflict intelligence

Conflict analysis classifies conflicts into BYTE_IDENTICAL, CAUSALLY_DOMINATED, POLICY_AUTHORITY, SECURITY, STRUCTURAL_SEMANTIC, or SEMANTIC_VALUE. The analysis MUST remain advisory. Semantic conflicts MUST NOT be auto-resolved.

## Sync planning

The sync planner compares local cursor/vector state with remote inventory and produces an advisory plan. It MUST NOT mutate sync state.

## Checkpoint selection

Checkpoint selection filters candidates against current revocation epoch and chooses deterministically from eligible checkpoints. It is advisory and does not restore state.

## Recovery recommendation

Recovery recommendations inspect operational mode and unresolved conflicts. They MUST preserve unresolved conflicts and replay protection.

## Conformance

`CONF-V22-*` checks verify Full profile, cumulative v2.0/v2.1 protocols, v2.2 namespace/schema, no semantic `AUTO_RESOLVE`, and valid policy inheritance structure.

## Safety

v2.2 intelligence MUST NOT broaden authority, mutate task intent, silently resolve semantic conflicts, apply sync plans, or perform recovery automatically.
