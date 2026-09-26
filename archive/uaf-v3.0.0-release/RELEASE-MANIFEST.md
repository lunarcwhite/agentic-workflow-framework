# UAAF v3.0.0 Release Manifest

Version: 3.0.0
Framework: UAAF
Profile support: full for the v3.0 runtime; cumulative minimal/standard/full core remains available without the runtime extension
v3.0 extension: Full profile

New in v3.0:
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
