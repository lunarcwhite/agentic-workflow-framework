# UAAF v1.0 — Master Specification

**Status:** Specification Freeze Candidate
**Version:** 1.0.0
**Framework ID:** UAAF
**Primary Protocol:** UAP-1.0

## 1. Mission

UAAF is a portable protocol and repository structure for AI agents to understand projects, preserve intent, manage context, plan adaptively, verify work, retain durable knowledge, detect inconsistency, and coordinate across sessions/agents.

## 2. Fundamental invariants

1. Intent must not change silently.
2. Current project reality must be checked before relying on consequential memory.
3. Context must be sufficient, not maximal.
4. Existing project patterns are preferred before creating new ones.
5. Evidence is required before consequential completion claims.
6. Scope must not expand silently.
7. Anti-slop is contextual, not novelty-maximization.
8. Capability does not imply authorization.
9. One important fact should have one canonical owner.
10. Historical artifacts must not masquerade as current state.

## 3. Engines

- IRE — Intent & Requirement Engine
- CLE — Context Loading Engine
- APRE — Adaptive Planning & Replanning Engine
- ASE — Anti-Slop Engine
- VEE — Verification & Evaluation Engine
- MEE — Memory Engine
- RCE — Reality & Consistency Engine

Supporting protocols:

- UAP — Universal Agent Protocol
- UAM — Universal Agent Manifest
- KOP — Knowledge Ownership Protocol
- SMAP — Session & Multi-Agent Protocol
- UAAF-C — Conformance Model

## 4. Lifecycle

BOOT → DISCOVER → REALITY CHECK → CLASSIFY → RETRIEVE → CONTEXT RECEIPT → CONTRACT → PLAN → PREFLIGHT → EXECUTE → OBSERVE → REALITY CHECK → REPLAN → VERIFY → EVIDENCE RECEIPT → EVALUATE → DELIVERY GATE → STATE UPDATE → MEMORY PROMOTION → DOCUMENT IMPACT → HANDOFF

Not every stage requires a persisted artifact.

## 5. Canonical ownership

Product requirements belong in PRD; architecture in ARCHITECTURE; detailed technical choices in TECHNICAL-DESIGN; visual/UX direction in DESIGN; schema in DATABASE-SCHEMA; API contracts in API; current state in STATE; durable learned knowledge in memory entries; decisions in decisions; verification in verification.

## 6. Intent and task contract

A consequential task should define intent, requirements, constraints, non-goals, acceptance criteria, scope, risk, verification, and expected changes. Contract integrity is tracked across intent/requirements/constraints/non-goals so strategy can change without silently changing the contract.

## 7. Adaptive planning

Plans may be revised when evidence changes. Material replans record evidence, cause, changed steps, contract impact, scope impact, and verification impact. Strategy changes are distinct from requirement or intent changes.

## 8. Anti-slop

ASE detects generic model-default behavior and challenges unjustified divergence, complexity, repetition, and unsupported claims. Existing project evidence and explicit design direction can legitimately approve a pattern that resembles a known anti-pattern.

## 9. Verification and evidence

Verification maps requirements to acceptance criteria, methods, evidence, and status. Evidence levels range from inspection to real-world/human verification. NOT_RUN is not PASS; assumed evidence is not evidence; partial verification is not full verification.

## 10. Memory

Memory is durable knowledge, not transcript history. Promotion follows Observation → Candidate → Evidence → Validated → Active. Memory has applicability, authority, confidence, stability, provenance, and supersession metadata. Consequential memory is validated against current reality before use.

## 11. Reality and consistency

RCE compares current implementation, tests, configuration, state, documentation, decisions, memory, and task expectations. Findings are classified as consistent, stale, conflict, drift, or unknown. RCE may flag and report semantic issues but must not invent authority when automatically resolving them.

## 12. Sessions and multi-agent coordination

Sessions and handoffs externalize working state. Claims provide leases for semantic resource ownership. Handoffs require resume integrity: handoff + current state + actual repository must be reconciled before work resumes.

## 13. Editions

- Minimal: kernel + state + indexes.
- Standard: kernel + tasks + memory + decisions + verification + anti-slop + session handoff.
- Full: Standard + evidence + health + multi-agent coordination + migration + advanced traceability/operations.

## 14. Conformance

U0 NONE; U1 CORE; U2 STANDARD; U3 FULL. Validator results are PASS, PASS_WITH_WARNINGS, or FAIL with ERROR/WARNING/INFO diagnostics. No global score is required.

## 15. Security

Never store secrets in project knowledge. Generated documentation must not fabricate project facts. Safe repair is mechanical only; semantic repair requires appropriate authority.
