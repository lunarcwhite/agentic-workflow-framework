# UAAF v2.0.0 Release Manifest

Protocol baseline: UAAF 1.0
Major release: UAAF 2.0
Federation protocol: UAAF-FED-2.0
Release class: major architectural evolution

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
- UAAF v2.0 Distributed Agent Federation
- Unified `uaf` CLI and adaptive initializer
- Minimal / Standard / Full project scaffold
- Northstar v2.0 federation reference project
- Extension specifications and implementation notes
- Regression, longitudinal, field, federation, and validation tests

## v2.0 additions

- Cross-project federation identity bound to project, agent, machine, and Ed25519 key fingerprints
- Signed handoff envelopes with audience binding and bounded lifetime
- Peer pinning with allowed federation actions and maximum risk ceiling
- Federation policy with deny-by-default semantics
- Replay protection using envelope IDs, nonces, and expiry
- Vector-clock based distributed state convergence
- Explicit unresolved conflict records for concurrent divergent state
- Signed state-push bundles
- Federation audit trail and transport-agnostic bundle exchange
- v2.0 Full-profile initializer, conformance checks, doctor diagnostics, and unified CLI support

## Compatibility

- v1.x project semantics are retained unless a v2.0 federation contract explicitly applies.
- v2.0 requires the Full profile.
- v2.0 is cumulative with v1.x trust, governance, verification, memory, and cryptographic layers.
- v2.0 does not define a network transport or replace IAM, OS authentication, TLS, or Git permissions.

## Validation

- v2.0 extension scenarios: 8/8 isolated passes
- targeted compatibility smoke: 7/7 passes
- field validation: 5/5 passes
- Northstar strict conformance: PASS
- Northstar doctor: PASS
- release extraction smoke: PASS

The subprocess-heavy combined pytest runner is not treated as an acceptance metric because the environment can hang when many child processes are launched inside one parent test process. Fresh-process exit codes are used instead.

## Reference Project

`examples/northstar-v20` contains only public trust material and detached signatures. Private signing keys remain outside the repository.

## Security properties

- Federation defaults to deny.
- Remote identity, audience, risk, expiry, and replay are checked before accepting a remote action.
- Concurrent distributed-state conflicts are surfaced rather than silently resolved.
- Private key material is excluded from release packaging.
- The reference federation implementation is transport agnostic and does not open network sockets.

## Release integrity

The release archive excludes Python bytecode caches, pytest caches, private keys, and test-generated Git metadata. The archive is re-extracted and smoke-tested before release.
