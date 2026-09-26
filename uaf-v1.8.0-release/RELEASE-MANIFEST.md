# UAAF v1.8.0 Release Manifest

Protocol baseline: UAAF 1.0
Extension baseline: UAAF 1.7
New extension version: UAAF 1.8
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
- Unified `uaf` CLI
- Adaptive Minimal / Standard / Full scaffold
- Northstar reference project
- Regression, longitudinal, field, extension, governance, and trust/delegation tests
- Validation and implementation reports

## v1.8 additions

- Distinct capability, authority, and delegation concepts
- Categorical authorization decisions: AUTHORIZED / DENIED / REVIEW_REQUIRED
- Risk ceilings and domain bounds
- Minimum evidence floors
- Optional recent verified-evidence history requirements
- Explicit delegation expiry
- Explicit revocation
- Non-escalation checks for capability, domain, and risk
- Delegation-chain cycle protection
- Multi-path delegation evaluation: any valid path may authorize
- Metadata-only trust audit events
- Trust conformance rules and doctor integration

## Compatibility

- v1.0-v1.7 projects remain valid without v1.8 trust artifacts.
- v1.3-v1.8 extensions require the Full profile.
- v1.8 initialization is cumulative with v1.1-v1.7 extensions.
- Core UAAF protocol semantics remain unchanged.
- v1.8 does not provide OS-level authentication or replace IAM/Git/CI permissions.
- Trust authority is explicit; capability alone never grants permission.

## Validation

Verified isolated test suites total **88/88 PASS**: core 12/12, v1.1 8/8, v1.2 7/7, v1.3 7/7, v1.4 10/10, v1.5 9/9, v1.6 9/9, v1.7 10/10, v1.8 14/14, longitudinal 1/1, field 1/1. The v1.4 process reported 10 passed before the surrounding pytest process exceeded the transport timeout; its assertions completed successfully. The v1.8 file-suite runner similarly exhibited a post-test harness hang, so its 14 tests were validated through isolated subsets whose exit codes all passed.

## Reference Project

Northstar reaches strict full conformance with UAAF v1.8. Trust smoke validation covers root authorization, bounded delegation, risk/evidence review, revocation, and audit behavior.

## Safety Properties

- No authentication claim is made by project metadata alone.
- Delegation cannot silently escalate capability, domain, or risk.
- Expiry and revocation stop the affected delegation path.
- Trust decisions remain categorical; there is no numeric trust score.
- Evidence history can increase review requirements but never silently increases authority.
- Audit records exclude prompts, source contents, and secret values.
