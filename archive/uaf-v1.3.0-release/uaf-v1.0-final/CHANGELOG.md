# Changelog

## 1.3.0 — 2026-09-26

- Added Git Traceability baseline and task trace commands.
- Added atomic filesystem-backed Claim Leasing with expiry and explicit reclaim.
- Added allowlisted Runtime Verification with evidence receipts and shell-disabled subprocesses.
- Extended unified CLI and conformance coverage.
- Added strict v1.3 conformance fixture and cumulative extension validation.

# Changelog

## 1.1.0

- Added optional UAAF v1.1 Capability Override Contract with detected/effective projection, explicit overrides, source, and reason.
- Added optional Context Impact Graph for changed-path to domain/capability/knowledge impact mapping.
- Added `tools/uaf.py` unified command dispatcher.
- Added v1.1 extension conformance checks (`CONF-V11-*`).
- Added v1.1 regression suite covering capability overrides, context impact, projection drift, doctor aggregation, v1.0 compatibility, and unified CLI.
- Kept UAAF v1.0 protocol semantics unchanged.

## 1.0.1

- Fixed auto-detection to inspect the existing project before scaffold copy.
- Made capability detection conservative to reduce false positives.
- Added `data`, `testing`, and `infrastructure` capability fields.
- Added `--level minimal` as an alias for core conformance.
- Made initialization safe for existing projects by preserving existing files by default.
- Made profile pruning copy-aware so UAAF never removes pre-existing files during adaptive pruning.
- Added `--docs auto|all|none` with capability-aware documentation selection.
- Added field-validation report across five representative project archetypes.
- Expanded automated regression suite to 14 tests.

## 1.0.0

- Frozen UAAF v1.0 master specification candidate.
- Added formal UAAF-C conformance validator with machine-readable output and strict mode.
- Added task-contract fingerprint utility.
- Added context receipt, evidence receipt, and change manifest templates.
- Added Reality & Consistency baseline and migration checker.
- Added Minimal, Standard, and Full adaptive initialization.
- Added Northstar reference project and automated conformance tests.


## 1.2.0 — 2026-09-26

- Added conservative Memory Compaction extension.
- Added Strong Reality & Consistency Engine with fingerprint snapshots.
- Added `uaf memory compact` and `uaf rce snapshot|scan`.
- Added v1.2 conformance rules and regression tests.
- Preserved v1.0/v1.1 compatibility; v1.2 remains opt-in.

- Strengthened RCE memory-reference validation for TASK/DEC/EVD/MEM identifiers.
