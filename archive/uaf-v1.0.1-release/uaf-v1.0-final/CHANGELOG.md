# Changelog

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
