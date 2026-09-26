# Changelog

## v2.5.0 — 2026-09-26

- Added secure federation transport reference layer with signed channel open/accept/confirm handshake.
- Added project/identity audience separation and session binding to the active v2.4 protocol contract.
- Added per-channel sequence enforcement, replay/out-of-order rejection, tamper detection, and peer-root pinning.
- Added signed reconnect/resume tokens with monotonic resume epochs and replay protection.
- Added `federation-transport` CLI command, `CONF-V25-*` conformance checks, compact doctor integration, field validation, and v2.4 downgrade cleanup.
- Explicitly documented that the reference transport does not provide confidentiality.

# Changelog

## v2.4.0 — 2026-09-26

- Added federation capability exchange and explicit protocol/version negotiation.
- Added bilateral safe fallback with deny-first handling and explicit review for semantic feature loss.
- Added protocol contract, feature compatibility checks, signed capability offers, and metadata-only protocol audit.
- Added `federation-protocol` unified CLI command, initializer support, doctor integration, and `CONF-V24-*` conformance.
- Preserved v2.3 authority semantics; protocol negotiation never grants or escalates authority.

## 2.3.0
- Added federation policy negotiation and bounded capability contracts.
- Added deny-first enforcement and domain-scope safety.
- Added v2.3 conformance and compact doctor integration.

# Changelog

## 2.2.0

- Added federation policy inheritance with monotonic restriction semantics.
- Added conflict classification and advisory sync/recovery planning.
- Added deterministic checkpoint selection.
- Added `CONF-V22-*` conformance checks.
- Added `federation-policy` and `federation-intel` CLI surfaces.
- Added v2.2 field and strict validation.

# Changelog

## v2.1.0 — Federation Operations & Resilience

- Added explicit federation operational modes: ONLINE, OFFLINE, PARTITIONED, and RECOVERING.
- Added idempotent sync bundles, peer cursors, and stale revocation-epoch protection.
- Added revocation propagation validated against the pinned peer trust root.
- Added explicit conflict lifecycle: UNRESOLVED → PROPOSED → APPROVED → RESOLVED/REJECTED.
- Added signed checkpoints, bounded recovery, recovery backups, and preservation of replay protection/unresolved conflicts.
- Added metadata-only federated observability and CONF-V21 conformance checks.
- Preserved v2.0 federation trust semantics; v2.1 remains transport-agnostic and Full-profile only.


## v2.0.0 — Distributed Agent Federation

- Cross-project federation identity with signed identity envelopes
- Signed handoff and state bundles
- Peer pinning and deny-by-default federation policy
- Replay protection with envelope expiry and nonce tracking
- Vector-clock distributed state merge with explicit unresolved conflicts
- Federation audit trail and transport-agnostic bundle exchange
- v2.0 Full-profile initializer, conformance, doctor, and unified CLI support
- Backward-compatible v1.x semantics retained unless explicitly superseded by v2.0 federation contracts


## 1.9.0 — 2026-09-26

- Added Trust Anchoring & Cryptographic Integrity.
- Added Ed25519 detached signatures, public key registry, explicit signature purposes, external root pinning, hash-chained trust audit, and root-rotation evidence.
- Added cryptographic bundle verification, fail-closed enforcement, v1.9 conformance checks, and doctor integration.
- Preserved v1.0-v1.8 semantics; v1.9 is Full-profile and opt-in.

## 1.8.0 — 2026-09-26

- Added Agent Trust & Delegation with explicit capability/authority separation.
- Added bounded delegation by capability, domain, risk, evidence floor, and expiry.
- Added optional recent verified-evidence history requirements without trust scoring.
- Added multi-path delegation evaluation and cycle protection.
- Added revocation, trust audit events, doctor integration, and CONF-V18 conformance.
- Preserved v1.0-v1.7 behavior; v1.8 is Full-profile and opt-in.

## 1.6.0 — 2026-09-26

- Added Adaptive Learning & Context Optimization driven by v1.5 metadata-first telemetry.
- Added advisory context retrieval, memory reuse, planning, and Delivery Gate recommendations.
- Added explicit safety defaults preventing automatic policy, intent, or memory mutation.
- Added v1.6 conformance and doctor support with cumulative extension handling.

## 1.5.0

- Added Context Economics & Observability.
- Added metadata-only event telemetry and configurable budgets.
- Added context, memory, gate, and replan measurements.
- Added privacy guard for observability events.
- Added v1.5 conformance and doctor checks.

## 1.4.0 — 2026-09-26

- Added static, read-only Security Diagnostics with secret-value redaction and permission checks.
- Added semantic Git ↔ Task traceability based on task expected changes and Git state.
- Integrated runtime evidence into a task-aware Delivery Gate.
- Extended unified CLI, doctor diagnostics, initializer, and UAAF-C conformance for v1.4.
- Preserved v1.0-v1.3 compatibility; v1.4 is opt-in and Full-profile only.

## 1.3.0 — 2026-09-26

- Added Git Traceability baseline and task trace commands.
- Added atomic filesystem-backed Claim Leasing with expiry and explicit reclaim.
- Added allowlisted Runtime Verification with evidence receipts and shell-disabled subprocesses.
- Extended unified CLI and conformance coverage.

## 1.2.0 — 2026-09-26

- Added conservative Memory Compaction extension.
- Added Strong Reality & Consistency Engine with fingerprint snapshots.
- Added `uaf memory compact` and `uaf rce snapshot|scan`.
- Added v1.2 conformance rules and regression tests.

## 1.1.0 — 2026-09-26

- Added Capability Override and Context Impact Graph.
- Added unified `uaf` CLI and extension conformance.

## 1.0.1 — 2026-09-26

- Hardened auto-detection and copy-aware profile pruning.
- Added capability-aware docs selection and field validation.

## 1.0.0

- Frozen UAAF v1.0 master specification candidate.
- Added formal UAAF-C conformance validator with machine-readable output and strict mode.
- Added task-contract fingerprint utility, context/evidence/change templates, RCE baseline, migration validator, and adaptive profiles.

## 1.7.0

- Added Policy Governance & Safe Adaptation lifecycle.
- Added explicit review/approval/apply/verify/rollback commands.
- Added allowlisted mutation paths, precondition hashes, audit log, and rollback snapshots.
- Kept adaptive learning advisory-only and protected intent/safety policy from safe mutation.
