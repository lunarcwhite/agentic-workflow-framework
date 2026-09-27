# Changelog

## v3.3.0 — 2026-09-27

- **Native Landing Page Design Architecture**:
  - Implemented 2-part landing page framework: Part A Strategy (intake discovery, 12-section conversion hierarchy, PAS/AIDA copywriting, and sequential build order) and Part B Visual System (Geist/Manrope typography, balanced text-wrap, tokenized type scales, and flat cards with full perimeter borders).
  - Shipped pre-bundled native package `landing-page-seo` with high-fidelity `landing-page-design` and `technical-seo` skills.
- **Automated Technical SEO & AEO Governance (`uaf seo`)**:
  - Introduced protocol `UAAF-SEO-1.0`.
  - Added `uaf seo audit <file_or_dir>` with deterministic quality checks for `<title>`, `<meta name="description">`, viewport, canonical tags, OpenGraph, Twitter Cards, heading hierarchy, image `alt` attributes, and Schema.org JSON-LD structured data.
  - Added `uaf seo generate` for generating standards-compliant Schema.org JSON-LD (`SoftwareApplication`, `Organization`, `WebSite`, `FAQPage`).
- **Dynamic Multi-Agent Team Adaptation**:
  - Added `landing_page_pro` and `seo_specialist` to `ROLE_DEFINITIONS` in `uaf_team.py`.
  - Automatic promotion in `uaf team compose` when prompts mention landing pages, marketing, conversion, or SEO.
  - Non-overlapping perimeter assignment to `docs/*` and `src/components/*` enforced by atomic claims lock (`.claims.lock`).
- **Scaffold & Checker Conformance**:
  - Added `--extension v3.3` and `--extension v3.3.0` in `uaf_init.py`.
  - Added conformance assertions `CONF-V33-001` through `CONF-V33-003` in `uaf_check.py`.
  - Tested 100% clean check and audit passes.

## v3.2.0 — 2026-09-27

- **Agentic Plugin Marketplace Manager (`uaf plugin`)**: Introduced protocol `UAAF-PLUGIN-1.0` bridging UAAF to extensive agentic plugin ecosystems (including `wshobson/agents`).
- **Commands**:
  - `uaf plugin list`: Inspect installed plugins in `.ai/plugins/` and browse catalog of available packages.
  - `uaf plugin search <query>`: Fast search across plugin descriptions, specialized agents, skills, and commands.
  - `uaf plugin install <name>`: Download and scaffold plugin manifests, agents, and skills with live GitHub retrieval and offline curated fallback.
  - `uaf plugin govern <name>`: Enforce UAAF Golden Axioms, bounded tools, and generate anchored evidence receipts (`EV-PLUGIN-<HASH>.yaml`).
  - `uaf plugin export <name>`: Multi-target export of plugin personas to Claude Code (`.claude/`), Antigravity (`.agents/`), Cursor (`.cursor/`), and Pi (`.pi/`).
- **Dynamic Team Role Discovery & Domain Adaptation**:
  - Enhanced `uaf team compose` to discover installed roles dynamically from `.ai/plugins/` via `discover_installed_roles()`.
  - Added specialized domain roles to `ROLE_DEFINITIONS`: `fastapi_pro`, `django_pro`, `react_pro`, `nextjs_pro`, `vue_pro`, `postgresql_dba`, `devops_engineer`, and `testing_specialist`.
  - Intelligent keyword matching automatically elevates generic roles to domain specialists and attaches required skills to task contracts.
- **Scaffold & Checker Conformance**: Added `--extension v3.2` and `--extension v3.2.0` in `uaf_init.py` and conformance assertions `CONF-V32-001` through `CONF-V32-003` in `uaf_check.py`.

## v3.1.0 — 2026-09-27

- **Team-Architecture Factory & Multi-Agent Orchestrator (`uaf team`)**: Introduced protocol `UAAF-TEAM-1.0` enabling simultaneous, collision-free multi-agent coordination across heterogeneous coding tools (Claude Code, Antigravity, Cursor, and Pi).
- **Six Architectural Patterns**:
  - `pipeline`: Sequential execution chain with feed-forward context receipts.
  - `producer_reviewer`: Paired dual-agent loop with mandatory evidence verification.
  - `fan_out_fan_in`: High-throughput parallel domain decomposition with synchronized integration.
  - `expert_pool`: Subsystem-driven task routing to specialized domain experts.
  - `supervisor`: Hierarchical task management, claim monitoring, and release approval.
  - `hierarchical`: Multi-tier swarm governance for large-scale enterprise repositories.
- **Disjoint Perimeter Invariant**: Automated prompt decomposition produces strictly non-overlapping `permitted_files` per active concurrent task contract ($\text{permitted\_files}(A) \cap \text{permitted\_files}(B) = \emptyset$).
- **Atomic Claims Leasing**: Native lock lease management backed by `.ai/agents/CLAIMS.yaml` and `.claims.lock` via `uaf team lock` and `uaf team release`.
- **Universal Multi-Target Export**: Seamlessly project team personas and boundary rules into:
  - Claude Code subagent definitions (`.claude/agents/*.md`)
  - Google Antigravity team & role skills (`.agents/skills/team-*/SKILL.md`)
  - Cursor boundary rules (`.cursor/rules/team.mdc`)
  - Pi / pi-agent-harness configurations (`.pi/agents/*.md`, `.pi/prompts/*.md`)
- **Deliverable Verification**: Added `uaf team verify` to ensure deliverable contracts and evidence receipts are satisfied.
- **Scaffold & Checker Conformance**: Added `--extension v3.1` and `--extension v3.1.0` in `uaf_init.py` and conformance assertions `CONF-V31-001` through `CONF-V31-006` in `uaf_check.py`.

## v3.0.1 — 2026-09-26

- Fixed inherited scaffold warning `CONF-REF-001`: ensured `.ai/memory/entries` is tracked in scaffold with `.gitkeep` and automatically provisioned by `uaf init`.
- Fixed inherited scaffold warning `CONF-DOC-001`: removed raw HTML comment placeholders from `.ai/core/CONTEXT.md`, achieving clean 100% `PASS` conformance on freshly generated projects.
- Enhanced semantic version parsing in `uaf_check.py` and `uaf_doctor.py` to prevent conversion errors on multi-dot version strings (`3.0.1`).
- Added support for `--extension v3.0.1` alongside existing `--extension v3.0`.
- Verified 100% clean check and doctor diagnostics for minimal, standard, and full profiles.

## v3.0.0 — 2026-09-26

- Added the Federated Agent Runtime (`UAAF-FED-3.0`) for explicit remote task execution.
- Added capability-aware routing bounded by trusted peer ceilings and concurrency.
- Added signed task contracts binding intent, authority, scope, requirements, acceptance criteria, lease constraints, and change budget.
- Added time-bounded execution leases with start, renewal, expiry, terminal-state protection, and signed lease receipts.
- Added signed cancellation with idempotency and late-cancellation rejection.
- Added signed remote results bound to the exact contract and lease, mandatory evidence, artifact hashing, and delivery evidence.
- Added append-only hash-chained runtime provenance and audit records.
- Added v3.0 initializer, downgrade cleanup, conformance validation, compact doctor integration, and unified CLI support.
- Preserved v2.5 authenticated transport, v2.6 confidentiality, v2.7 lifecycle, v2.8 custody, and v2.9 provider-backed key operations as the lower security layers.
- Disabled remote `delete` by default and rejected silent scope/authority expansion.
- Added fresh integration and field validation for routing, delegation, result verification, delivery, tamper rejection, cancellation, expiry, preserve, and downgrade.

## v2.7.0 — 2026-09-26

- Added explicit secure channel lifecycle states: CLOSED, EXPIRED, REVOKED, and RECOVERY_REQUIRED.
- Added key retirement, monotonic key/channel revocation records, provider abstraction metadata, and secret-export prohibition.
- Added fail-closed lifecycle guards to v2.6 confidential send/receive/rekey operations.
- Added recovery semantics that require a new authenticated handshake when private state is missing or terminal.
- Added `key-lifecycle` CLI command, `CONF-V27-*` conformance validation, compact doctor integration, and v2.7 field validation.
- Documented that the reference filesystem provider performs best-effort deletion and does not claim forensic secure erasure.

## v2.6.0 — 2026-09-26

- Added confidential federation transport using ephemeral X25519 key agreement, HKDF-SHA256, and ChaCha20-Poly1305 AEAD.
- Added per-channel/per-epoch directional key derivation, authenticated rekey, replay/order preservation, and contract/peer binding.
- Added secure federation namespace, key-directory protection, v2.6 initializer support, unified CLI, conformance checks, and compact doctor diagnostics.
- Added dedicated v2.6 crypto tests, five archetype field validation, manual bidirectional E2E evidence, and release archive smoke validation.
- Documented that the reference implementation does not claim traffic-analysis resistance, availability, or guaranteed process-memory zeroization.

## v2.5.0 — 2026-09-26

- Added secure federation transport reference layer with signed channel open/accept/confirm handshake.
- Added project/identity audience separation and session binding to the active v2.4 protocol contract.
- Added per-channel sequence enforcement, replay/out-of-order rejection, tamper detection, and peer-root pinning.
- Added signed reconnect/resume tokens with monotonic resume epochs and replay protection.
- Added `federation-transport` CLI command, `CONF-V25-*` conformance checks, compact doctor integration, field validation, and v2.4 downgrade cleanup.
- Explicitly documented that the reference transport does not provide confidentiality.

# Changelog

## v2.4.0 — 2026-09-26

- Added federation capability exchange and explicit protocol/version negotiation.
- Added bilateral safe fallback with deny-first handling and explicit review for semantic feature loss.
- Added protocol contract, feature compatibility checks, signed capability offers, and metadata-only protocol audit.
- Added `federation-protocol` unified CLI command, initializer support, doctor integration, and `CONF-V24-*` conformance.
- Preserved v2.3 authority semantics; protocol negotiation never grants or escalates authority.

## 2.3.0
- Added federation policy negotiation and bounded capability contracts.
- Added deny-first enforcement and domain-scope safety.
- Added v2.3 conformance and compact doctor integration.

# Changelog

## 2.2.0

- Added federation policy inheritance with monotonic restriction semantics.
- Added conflict classification and advisory sync/recovery planning.
- Added deterministic checkpoint selection.
- Added `CONF-V22-*` conformance checks.
- Added `federation-policy` and `federation-intel` CLI surfaces.
- Added v2.2 field and strict validation.

# Changelog

## v2.1.0 — Federation Operations & Resilience

- Added explicit federation operational modes: ONLINE, OFFLINE, PARTITIONED, and RECOVERING.
- Added idempotent sync bundles, peer cursors, and stale revocation-epoch protection.
- Added revocation propagation validated against the pinned peer trust root.
- Added explicit conflict lifecycle: UNRESOLVED → PROPOSED → APPROVED → RESOLVED/REJECTED.
- Added signed checkpoints, bounded recovery, recovery backups, and preservation of replay protection/unresolved conflicts.
- Added metadata-only federated observability and CONF-V21 conformance checks.
- Preserved v2.0 federation trust semantics; v2.1 remains transport-agnostic and Full-profile only.


## v2.0.0 — Distributed Agent Federation

- Cross-project federation identity with signed identity envelopes
- Signed handoff and state bundles
- Peer pinning and deny-by-default federation policy
- Replay protection with envelope expiry and nonce tracking
- Vector-clock distributed state merge with explicit unresolved conflicts
- Federation audit trail and transport-agnostic bundle exchange
- v2.0 Full-profile initializer, conformance, doctor, and unified CLI support
- Backward-compatible v1.x semantics retained unless explicitly superseded by v2.0 federation contracts


## 1.9.0 — 2026-09-26

- Added Trust Anchoring & Cryptographic Integrity.
- Added Ed25519 detached signatures, public key registry, explicit signature purposes, external root pinning, hash-chained trust audit, and root-rotation evidence.
- Added cryptographic bundle verification, fail-closed enforcement, v1.9 conformance checks, and doctor integration.
- Preserved v1.0-v1.8 semantics; v1.9 is Full-profile and opt-in.

## 1.8.0 — 2026-09-26

- Added Agent Trust & Delegation with explicit capability/authority separation.
- Added bounded delegation by capability, domain, risk, evidence floor, and expiry.
- Added optional recent verified-evidence history requirements without trust scoring.
- Added multi-path delegation evaluation and cycle protection.
- Added revocation, trust audit events, doctor integration, and CONF-V18 conformance.
- Preserved v1.0-v1.7 behavior; v1.8 is Full-profile and opt-in.

## 1.6.0 — 2026-09-26

- Added Adaptive Learning & Context Optimization driven by v1.5 metadata-first telemetry.
- Added advisory context retrieval, memory reuse, planning, and Delivery Gate recommendations.
- Added explicit safety defaults preventing automatic policy, intent, or memory mutation.
- Added v1.6 conformance and doctor support with cumulative extension handling.

## 1.5.0

- Added Context Economics & Observability.
- Added metadata-only event telemetry and configurable budgets.
- Added context, memory, gate, and replan measurements.
- Added privacy guard for observability events.
- Added v1.5 conformance and doctor checks.

## 1.4.0 — 2026-09-26

- Added static, read-only Security Diagnostics with secret-value redaction and permission checks.
- Added semantic Git ↔ Task traceability based on task expected changes and Git state.
- Integrated runtime evidence into a task-aware Delivery Gate.
- Extended unified CLI, doctor diagnostics, initializer, and UAAF-C conformance for v1.4.
- Preserved v1.0-v1.3 compatibility; v1.4 is opt-in and Full-profile only.

## 1.3.0 — 2026-09-26

- Added Git Traceability baseline and task trace commands.
- Added atomic filesystem-backed Claim Leasing with expiry and explicit reclaim.
- Added allowlisted Runtime Verification with evidence receipts and shell-disabled subprocesses.
- Extended unified CLI and conformance coverage.

## 1.2.0 — 2026-09-26

- Added conservative Memory Compaction extension.
- Added Strong Reality & Consistency Engine with fingerprint snapshots.
- Added `uaf memory compact` and `uaf rce snapshot|scan`.
- Added v1.2 conformance rules and regression tests.

## 1.1.0 — 2026-09-26

- Added Capability Override and Context Impact Graph.
- Added unified `uaf` CLI and extension conformance.

## 1.0.1 — 2026-09-26

- Hardened auto-detection and copy-aware profile pruning.
- Added capability-aware docs selection and field validation.

## 1.0.0

- Frozen UAAF v1.0 master specification candidate.
- Added formal UAAF-C conformance validator with machine-readable output and strict mode.
- Added task-contract fingerprint utility, context/evidence/change templates, RCE baseline, migration validator, and adaptive profiles.

## 1.7.0

- Added Policy Governance & Safe Adaptation lifecycle.
- Added explicit review/approval/apply/verify/rollback commands.
- Added allowlisted mutation paths, precondition hashes, audit log, and rollback snapshots.
- Kept adaptive learning advisory-only and protected intent/safety policy from safe mutation.

## UAAF v2.8.0

- Added provider-abstracted key custody namespace.
- Added filesystem, optional OS-keychain, and external KMS/HSM provider contracts.
- Added provider health diagnostics and metadata-only key references.
- Enforced secret export/private-key return disabled policy.
- Added fail-closed provider selection and explicit v2.8 downgrade cleanup.
- Added `uaf key-storage` commands and `CONF-V28-*` conformance checks.

## v2.9.0

Added provider-backed signing and key-reference operations; private key return/export remains disabled.

## v2.9.0

Provider-backed key operations, explicit purpose allowlists, key-reference verification, key rotation/retirement, operation audit, and confidential federation handshake support through key references.
