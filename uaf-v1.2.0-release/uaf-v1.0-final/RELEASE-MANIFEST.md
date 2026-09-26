# UAAF v1.2.0 Release Manifest

Protocol baseline: UAAF 1.0
Extension baseline: UAAF 1.1
New extension version: UAAF 1.2
Release class: backward-compatible additive extension

## Included

- UAAF v1.0 specification and conformance catalog
- UAAF v1.1 capability override and context impact graph
- UAAF v1.2 conservative memory compaction
- UAAF v1.2 Strong RCE fingerprint snapshots
- UAAF v1.2 memory TASK/DEC/EVD/MEM reference validation
- Unified `uaf` CLI dispatcher
- Adaptive Minimal / Standard / Full scaffold
- Reference Northstar project
- Contract fingerprint, baseline RCE, migration validator, doctor diagnostics
- v1.2 regression and compatibility tests
- Validation reports and implementation maps

## Compatibility

- v1.0 and v1.1 projects remain valid when v1.2 extensions are absent.
- v1.2 is opt-in through `--extension v1.2`.
- Core UAP/IRE/CLE/APRE/ASE/VEE/MEE/RCE semantics are unchanged.

Validation result: 29/29 isolated regression tests passed.
