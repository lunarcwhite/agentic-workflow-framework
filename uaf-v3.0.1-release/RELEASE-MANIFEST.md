# UAAF v3.0.1 Release Manifest

Version: 3.0.1
Framework: UAAF
Profile support: full for the v3.0 runtime; cumulative minimal/standard/full core remains available without the runtime extension
v3.0 extension: Full profile (supports alias `v3.0` and `v3.0.1`)

New in v3.0.1:
- Fixed inherited scaffold warning `CONF-REF-001`: `.ai/memory/entries` is now automatically created on initialization and included in the scaffold.
- Fixed inherited scaffold warning `CONF-DOC-001`: removed raw HTML comment placeholders from `.ai/core/CONTEXT.md`, achieving clean 100% `PASS` conformance on fresh projects.
- Enhanced `extension_num` in `uaf_check.py` and `uaf_doctor.py` to robustly handle semantic versioning strings (e.g., `3.0.1`).
- Added `v3.0.1` alias support to `uaf init --extension v3.0.1`.
- Added automated regression test suite for v3.0.1 clean-state conformance.

Carried over from v3.0:
- Federated Agent Runtime (`UAAF-FED-3.0`)
- capability-aware routing bounded by trusted peer ceilings
- signed remote task contracts
- execution leases and signed lease receipts
- cancellation and timeout/expiry lifecycle
- signed result bundles and mandatory evidence
- origin-side result verification and delivery evidence
- hash-chained provenance and audit
- v3.0 conformance and compact doctor diagnostics

Security invariants:
- deny-by-default
- no silent scope expansion
- no authority escalation
- remote `delete` disabled by default
- remote actions/risk cannot exceed trusted peer ceilings
- terminal lease state cannot be resurrected
- provider-backed signing preferred
- no private key material in project/runtime release contents

Release exclusions:
- private key material
- runtime key directories
- temporary validation projects
- pytest caches / Python bytecode
