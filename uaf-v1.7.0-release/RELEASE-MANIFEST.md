# UAAF v1.7.0 Release Manifest

Protocol baseline: UAAF 1.0
Extension baseline: UAAF 1.6
New extension version: UAAF 1.7
Release class: backward-compatible additive extension

## Included

- UAAF v1.0 normative specification and conformance catalog
- UAAF v1.1 Capability Override and Context Impact Graph
- UAAF v1.2 Memory Compaction and Strong RCE
- UAAF v1.3 Git Traceability, Claim Leasing, and Runtime Verification
- UAAF v1.4 Security Diagnostics, Git↔Task traceability, and Runtime Evidence Delivery Gate
- UAAF v1.5 Context Economics & Observability
- UAAF v1.6 Adaptive Learning & Context Optimization
- UAAF v1.7 Policy Governance & Safe Adaptation
- Unified `uaf` CLI
- Adaptive Minimal / Standard / Full scaffold
- Northstar reference project
- Regression, longitudinal, field, extension, and governance tests
- Validation and implementation reports

## v1.7 additions

- Explicit governance lifecycle: PROPOSED → REVIEWED → APPROVED → APPLIED → VERIFIED
- REJECTED and EXPIRED terminal states
- Reviewer/approver identity requirement
- Approval-time target precondition hashes
- Allowlisted YAML safe-apply path
- Intent and safety-policy mutation protection
- Pre-apply rollback snapshots
- Explicit rollback command
- Append-oriented audit log
- Governance conformance rules and doctor integration

## Compatibility

- v1.0-v1.6 projects remain valid without v1.7 governance artifacts.
- v1.3-v1.7 extensions remain opt-in and require the Full profile.
- v1.7 initialization is cumulative with v1.1-v1.6 extensions.
- Core UAAF protocol semantics remain unchanged.
- v1.7 does not enable automatic adaptive changes.

## Validation

Verified isolated test suites total **74/74 PASS**: core 12/12, v1.1 8/8, v1.2 7/7, v1.3 7/7, v1.4 10/10, v1.5 9/9, v1.6 9/9, longitudinal 1/1, field 1/1, v1.7 10/10. Individual suites are intentionally executable independently because the subprocess-heavy combined harness can exceed transport timeouts.

## Reference Project

Northstar reaches strict full conformance with UAAF v1.7. Governance smoke test was executed end-to-end and rolled back successfully, restoring the target policy byte-for-byte.

## Safety Properties

- Adaptive recommendations remain advisory until explicitly governed.
- `auto_apply` remains false and cannot be changed through safe apply.
- Intent mutation is forbidden.
- Safety-control mutation is forbidden.
- Apply requires explicit approval and precondition matching.
- Every apply creates rollback evidence.
- Audit records exclude prompts, source contents, and secret values.
