# UAAF v3.1.0 Release Manifest

Version: 3.1.0
Framework: UAAF
Profile support: full for the v3.0/v3.1 runtime; cumulative minimal/standard/full core remains available without the runtime extension
v3.1 extension: Full profile (supports alias `v3.1` and `v3.1.0`)

New in v3.1.0:
- **Team-Architecture Factory & Multi-Agent Orchestrator (`uaf team`)**: Introduced protocol `UAAF-TEAM-1.0` enabling simultaneous, collision-free multi-agent coordination.
- **Six Architectural Patterns**: Pipeline, Producer-Reviewer, Fan-Out/Fan-In, Expert Pool, Supervisor, and Hierarchical Swarm.
- **Disjoint Perimeter Invariant**: Automatic decomposition ensuring $\text{permitted\_files}(A) \cap \text{permitted\_files}(B) = \emptyset$.
- **Atomic Claims Leasing**: Lock lease management backed by `.ai/agents/CLAIMS.yaml` and `.claims.lock`.
- **Universal Multi-Target Export**: Seamlessly project team personas to Claude Code, Google Antigravity, Cursor, and Pi.
- **Deliverable Verification**: `uaf team verify` validates task contracts and evidence receipts.

Carried over from v3.0 / v3.0.1:
- Clean scaffold without inherited warnings
- Robust semantic versioning parsing (`3.0.1`, `3.1.0`)
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
