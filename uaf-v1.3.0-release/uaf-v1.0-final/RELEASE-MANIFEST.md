# UAAF v1.3.0 Release Manifest

Protocol baseline: UAAF 1.0
Extension baseline: UAAF 1.2
New extension version: UAAF 1.3
Release class: backward-compatible additive extension

## Included

- UAAF v1.0 normative specification and conformance catalog
- UAAF v1.1 capability override and context impact graph
- UAAF v1.2 conservative memory compaction and Strong RCE
- UAAF v1.3 Git Traceability
- UAAF v1.3 Real Claim Leasing
- UAAF v1.3 Runtime Verification
- Unified `uaf` CLI
- Adaptive Minimal / Standard / Full scaffold
- Northstar reference project
- Contract fingerprint, reconciliation, migration validator, and doctor diagnostics
- Regression, longitudinal, field, and v1.3 extension tests
- Validation and implementation reports

## Compatibility

- v1.0-v1.2 projects remain valid without v1.3 artifacts.
- v1.3 is opt-in through `--extension v1.3` and requires the Full profile.
- v1.3 initialization is cumulative and includes v1.1/v1.2 extension artifacts.
- Core UAP/IRE/CLE/APRE/ASE/VEE/MEE/RCE semantics remain unchanged.

## Safety properties

- Git history is read-only.
- Claims use atomic exclusive locking, explicit expiry handling, and explicit reclaim.
- Runtime execution is disabled by default, exact-command allowlisted, shell-disabled, timeout-bounded, and evidence-producing.
