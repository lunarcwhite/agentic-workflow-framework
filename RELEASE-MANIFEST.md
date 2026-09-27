# UAAF v3.2.0 Release Manifest

Version: 3.2.0
Framework: UAAF
Profile support: full for the v3.0/v3.1/v3.2 runtime; cumulative minimal/standard/full core remains available without the runtime extension
v3.2 extension: Full profile (supports alias `v3.2` and `v3.2.0`)

New in v3.2.0:
- **Agentic Plugin Marketplace Manager (`uaf plugin`)**: Introduced protocol `UAAF-PLUGIN-1.0` bridging to external ecosystems (like `wshobson/agents`).
- **Interactive Discovery & Installation**: `uaf plugin search` and `uaf plugin install` with remote GitHub fetching and resilient offline curated fallback.
- **Mandatory Governance Anchoring**: Auto-injection of `GOVERNANCE.md` and cryptographic evidence receipt anchoring for all installed plugins.
- **Dynamic Plugin Discovery**: `discover_installed_roles` dynamically detects agents and skills from `.ai/plugins/` for live team orchestration.
- **Domain Specialist Adaptation**: Automatic promotion of generic roles to specialized personas (`fastapi_pro`, `react_pro`, `postgresql_dba`, etc.) based on task intent.
- **Universal Multi-Target Plugin Export**: Project plugins into native artifacts for Claude Code, Antigravity, Cursor, and Pi.

Carried over from v3.1.0:
- **Team-Architecture Factory & Multi-Agent Orchestrator (`uaf team`)**: Protocol `UAAF-TEAM-1.0`.
- **Six Architectural Patterns**: Pipeline, Producer-Reviewer, Fan-Out/Fan-In, Expert Pool, Supervisor, and Hierarchical Swarm.
- **Disjoint Perimeter Invariant**: Automatic decomposition ensuring $\text{permitted\_files}(A) \cap \text{permitted\_files}(B) = \emptyset$.
- **Atomic Claims Leasing**: Lock lease management backed by `.ai/agents/CLAIMS.yaml` and `.claims.lock`.
- **Deliverable Verification**: `uaf team verify` validates task contracts and evidence receipts.

Carried over from v3.0 / v3.0.1:
- Federated Agent Runtime (`UAAF-FED-3.0`)
- Signed remote contracts, execution leases, and signed lease receipts
- Origin-side result verification and delivery evidence
- Hash-chained provenance and audit

Security invariants:
- deny-by-default
- no silent scope expansion
- no authority escalation
- disjoint perimeter enforcement
- provider-backed signing preferred
- no private key material in project/runtime release contents

Release exclusions:
- private key material
- runtime key directories
- temporary validation projects
- pytest caches / Python bytecode
