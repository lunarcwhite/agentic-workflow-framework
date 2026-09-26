# UAAF v1.0 — Validation Report

Date: 2026-09-25

## Scope

Validation covers the reference implementation, three installation profiles, conformance checks, contract fingerprints, Reality & Consistency baseline, migration-check behavior, and a deterministic 20-session protocol simulation.

## Automated result

```text
6 passed
```

The suite includes:

- Minimal / Standard / Full profile bootstrap and conformance.
- Reference Northstar full conformance.
- Task-contract fingerprint validation.
- Broken canonical-reference detection.
- Semantic contract-change detection.
- 20-session longitudinal protocol simulation.

## Longitudinal scenarios

The 20-session simulation exercises:

```text
bootstrap
→ task contract
→ contract fingerprint
→ decision
→ evidence
→ memory promotion
→ handoff
→ state versioning
→ multi-agent claim
→ plan/constraint divergence
→ fingerprint mismatch
→ restore/replan
→ change-manifest scope control
→ justified scope consequence
→ reality check
→ canonical-owner drift
→ repair
→ state advance
→ task completion
→ final conformance
```

## Safety properties validated

- Validator is read-only.
- RCE baseline is read-only.
- Semantic contract changes are detectable through fingerprint mismatch.
- Unexpected scope changes require justification.
- Missing canonical references are surfaced as drift.
- Memory/evidence references are checked for integrity.
- Project scaffold does not copy distribution tooling/specification into initialized target projects.
- `--strict` converts warnings into conformance failure.

## Known intentional warning

The full scaffold contains placeholder context content by design. A fresh scaffold may therefore report `PASS_WITH_WARNINGS` until project-specific context is populated. The Northstar reference project passes full conformance in strict mode.

## Remaining non-goals for v1.0

This release does not attempt autonomous semantic conflict resolution, vector-memory requirements, model-specific orchestration, or production-grade repository mutation workflows. Those remain implementation choices layered on top of the protocol.
