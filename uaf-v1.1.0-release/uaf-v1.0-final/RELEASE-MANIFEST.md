# UAAF v1.1.0 Release Manifest

Protocol baseline: UAAF 1.0
Extension version: UAAF 1.1
Release class: backward-compatible additive extension

## Included

- UAAF v1.0 specification and conformance catalog
- Capability Override Contract
- Context Impact Graph
- Unified `uaf` CLI dispatcher
- Adaptive Minimal / Standard / Full scaffold
- Reference Northstar project
- Contract fingerprint, RCE baseline, migration validator, doctor diagnostics
- v1.1 test suite and field/longitudinal regression coverage
- Validation reports and implementation maps

## Compatibility

- v1.0 projects remain valid when v1.1 extensions are absent.
- v1.1 capability and context-impact features are opt-in through `--extension v1.1`.
- Core UAP/IRE/CLE/APRE/ASE/VEE/MEE/RCE semantics are unchanged.
