# UAAF v1.0.1 Release Manifest

Protocol version: UAAF 1.0.0
Implementation version: 1.0.1
Release class: backward-compatible implementation patch

## Included

- `spec/` — normative UAAF v1.0 specification and conformance catalog
- `scaffold/` — Minimal/Standard/Full project scaffold source
- `templates/` — task/context/evidence/change/handoff templates
- `tools/` — initializer, conformance validator, contract fingerprint, RCE baseline, migration checker
- `examples/northstar/` — reference project
- `tests/` — automated regression + longitudinal + field archetype coverage
- `FIELD-VALIDATION-REPORT.md` — five-archetype field-style validation
- `VALIDATION-REPORT.md` — implementation validation history
- `IMPLEMENTATION.md` — implementation map

## Release invariants

- UAP/IRE/CLE/APRE/ASE/VEE/MEE/RCE semantics remain UAAF v1.0.
- Existing project files are preserved by default.
- Auto-detection is advisory and conservative.
- Adaptive pruning removes only scaffold files created during the current initialization.
- `--docs auto` is default for standard/full and may be replaced with `--docs all` or `--docs none`.
- Validators and RCE remain read-only.
