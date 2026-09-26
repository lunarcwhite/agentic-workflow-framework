# UAAF v1.5.0 Release Manifest

Protocol baseline: UAAF 1.0  
Extension baseline: UAAF 1.3  
New extension version: UAAF 1.4  
Release class: backward-compatible additive extension

## Included

- UAAF v1.0 normative specification and conformance catalog
- UAAF v1.1 Capability Override and Context Impact Graph
- UAAF v1.2 Memory Compaction and Strong RCE
- UAAF v1.3 Git Traceability, Claim Leasing, and Runtime Verification
- UAAF v1.4 Security Diagnostics
- UAAF v1.4 semantic Git ↔ Task traceability
- UAAF v1.4 Runtime Evidence integrated with Delivery Gate
- UAAF v1.5 Context Economics & Observability
- Unified `uaf` CLI
- Adaptive Minimal / Standard / Full scaffold
- Northstar reference project
- Regression, longitudinal, field, and extension tests
- Validation and implementation reports

## Compatibility

- v1.0-v1.4 projects remain valid without v1.5 artifacts.
- v1.4 and v1.5 are opt-in and require the Full profile.
- v1.5 initialization is cumulative with v1.1-v1.4 extensions.
- Core UAAF protocol semantics remain unchanged.

## Validation

Verified test suites total 54/54: core 12/12, v1.1 8/8, v1.2 7/7, v1.3 7/7, v1.4 9/9, v1.5 9/9, longitudinal 1/1, field 1/1. The suites are intentionally run independently because the subprocess-heavy combined harness can exceed execution timeout.

## Safety properties

- Security diagnostics are static and read-only; matched secret values are never printed.
- Git history is read-only.
- Git↔Task traceability is advisory and does not replace the task contract or Git.
- Runtime verification remains disabled by default and keeps shell-disabled exact allowlisting.
- Runtime evidence is only one Delivery Gate dimension.

## v1.5 additions

- Context Economics & Observability
- metadata-only event log
- configurable context/memory/replan budgets
- v1.5 conformance and doctor checks
- privacy-safe observability recorder
