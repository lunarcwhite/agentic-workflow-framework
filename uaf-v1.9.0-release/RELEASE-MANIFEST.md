# UAAF v1.9.0 Release Manifest

Protocol baseline: UAAF 1.0
Extension baseline: UAAF 1.8
New extension version: UAAF 1.9
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
- UAAF v1.8 Agent Trust & Delegation
- UAAF v1.9 Trust Anchoring & Cryptographic Integrity
- Unified `uaf` CLI
- Adaptive Minimal / Standard / Full scaffold
- Northstar reference project
- Regression, longitudinal, field, extension, governance, trust/delegation, and cryptographic integrity tests
- Validation and implementation reports

## v1.9 additions

- Ed25519 detached signatures for exact file bytes
- Public trust root and key registry
- Explicit signature purposes: trust-root, trust-keys, trust-policy, delegations
- External root fingerprint pinning with fail-closed enforcement
- Hash-chained v1.9 trust audit
- Explicit root-rotation evidence
- Cryptographic bundle verification integrated with trust evaluation and conformance
- Private-key exclusion from project trust directories
- Legacy v1.8 audit preservation during v1.9 migration

## Compatibility

- v1.0-v1.8 projects remain valid without v1.9 trust artifacts.
- v1.9 initialization requires the Full profile.
- v1.9 initialization is cumulative with v1.1-v1.8 extensions.
- Core UAAF protocol semantics remain unchanged.
- v1.9 does not provide OS-level authentication or replace IAM/Git/CI permissions.
- Private signing keys are external to the repository.

## Validation

The release qualification uses isolated subprocess exit codes for the subprocess-heavy suites. v1.9 cryptographic scenarios include signed-bundle strict conformance, tamper detection, external-pin fail-closed behavior, audit-chain validation, and private-key conformance rejection.

## Reference Project

Northstar reaches strict Full-profile conformance with v1.9 cryptographic integrity enabled. Public trust material and detached signatures are included; private signing keys are not.

## Safety Properties

- A trust signature is tied to an explicit purpose.
- Root policy changes invalidate the root signature until re-signed.
- Required external pins fail closed when omitted or mismatched.
- Cryptographic-required trust evaluation fails closed on invalid bundle state.
- Audit tampering is detectable through the hash chain.
- Root rotation is explicit and signed by the previous root.

## Release integrity

The archive excludes Python bytecode caches, pytest caches, private signing keys, and test-generated Git metadata. The release package is re-extracted and smoke-tested before publication.
