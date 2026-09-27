# UAAF v3.3.0 Release Manifest

Version: 3.3.0
Framework: UAAF
Profile support: full for the v3.0/v3.1/v3.2/v3.3 runtime; cumulative minimal/standard/full core remains available without the runtime extension
v3.3 extension: Full profile (supports alias `v3.3` and `v3.3.0`)

New in v3.3.0:
- **Native Landing Page Design Architecture**: 2-part framework with Part A Strategy (intake discovery, 12-section conversion hierarchy, PAS/AIDA copywriting, and sequential build order) and Part B Visual System (strict Geist/Manrope typography, balanced text-wrap, tokenized type scales, and flat cards with full perimeter borders).
- **Automated Technical SEO & AEO Governance (`uaf seo`)**: Protocol `UAAF-SEO-1.0`.
  - `uaf seo audit`: Automated scanning for semantic HTML5 metadata, OpenGraph, Twitter Cards, canonical tags, single `<h1>` hierarchy, image accessibility, and Schema.org JSON-LD blocks.
  - `uaf seo generate`: Standards-compliant Schema.org JSON-LD generator for `SoftwareApplication`, `Organization`, `WebSite`, and `FAQPage`.
- **Native Multi-Agent Roles (`landing_page_pro` & `seo_specialist`)**: Automatic dynamic promotion in `uaf team compose` based on marketing, conversion, and SEO prompt keywords with disjoint perimeters.
- **Native Package `landing-page-seo`**: Pre-bundled within UAAF's built-in catalog for instant offline installation and multi-target export to Claude Code (`.claude/`), Antigravity (`.agents/`), Cursor (`.cursor/`), and Pi (`.pi/`).

Carried over from v3.2.0:
- **Agentic Plugin Marketplace Manager (`uaf plugin`)**: Protocol `UAAF-PLUGIN-1.0`.
- **Dynamic Role Discovery**: `discover_installed_roles` dynamically detects installed agents and skills from `.ai/plugins/`.
- **Mandatory Governance Anchoring**: Auto-injection of `GOVERNANCE.md` and evidence receipts.

Carried over from v3.1.0:
- **Team-Architecture Factory & Multi-Agent Orchestrator (`uaf team`)**: Protocol `UAAF-TEAM-1.0`.
- **Six Architectural Patterns**: Pipeline, Producer-Reviewer, Fan-Out/Fan-In, Expert Pool, Supervisor, and Hierarchical Swarm.
- **Disjoint Perimeter Invariant**: Automatic decomposition ensuring $\text{permitted\_files}(A) \cap \text{permitted\_files}(B) = \emptyset$.
- **Atomic Claims Leasing**: Lock lease management backed by `.claims.lock`.

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
