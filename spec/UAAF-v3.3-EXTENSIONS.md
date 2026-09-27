# UAAF v3.3 Extension Contract: Native Landing Page Architecture & SEO Governance

## Extension Identity

```yaml
version: "3.3.0"
protocol: "UAAF-SEO-1.0"
profile: full
mode: landing_page_and_seo_governance
```

## Architectural Foundations

UAAF v3.3 extends the Multi-Agent Team Orchestrator (v3.1) and Plugin Marketplace (v3.2) with native, first-class capabilities for high-converting landing page engineering and automated technical SEO/AEO governance.

Rather than relying on unvetted, unstructured external prompts, UAAF v3.3 introduces:
1. **The 2-Part Native Landing Page Framework**: Combining Part A Strategy & Structure (intake discovery, 12-section conversion hierarchy, PAS/AIDA copywriting, and sequential build order) with Part B Non-negotiable Visual Systems (disciplined typography, tokenized type scales, zero orphaned words with `text-wrap: balance`, and WCAG AA contrast).
2. **Automated SEO & Structured Data CLI (`uaf seo`)**: Providing automated SERP metadata auditing and Schema.org JSON-LD generation (`SoftwareApplication`, `Organization`, `WebSite`, `FAQPage`).
3. **Specialized Multi-Agent Roles (`landing_page_pro` & `seo_specialist`)**: Automatically activated during `uaf team compose` when prompts involve web pages, conversion, marketing, or SEO.
4. **Native Plugin & Skill Package (`landing-page-seo`)**: Shipped offline-ready inside UAAF with full export capability to Claude Code (`.claude/`), Antigravity (`.agents/`), Cursor (`.cursor/`), and Pi (`.pi/`).

## Subsystem Capabilities

### 1. Native SEO & Semantic Auditor (`uaf seo audit`)
- **Deterministic HTML Quality Gates**:
  - `<title>` presence and character boundary (15–70 chars).
  - `<meta name="description">` presence and boundary (50–160 chars).
  - Mobile viewport `<meta name="viewport">` presence.
  - Canonical link tag (`<link rel="canonical">`) presence.
  - Social sharing compliance: OpenGraph (`og:title`, `og:description`, `og:type`, `og:url`) and Twitter Cards.
  - Semantic heading hierarchy: exactly one `<h1>` per landing page and logical `<h2>`/`<h3>` nesting.
  - Image accessibility: enforcing `alt="..."` attributes across all `<img>` tags.
  - Schema.org validation: parses and validates embedded `<script type="application/ld+json">` blocks.
  - Exit code 0 if score meets or exceeds threshold (`--threshold 80`).

### 2. Schema.org JSON-LD Generator (`uaf seo generate`)
- Generates standards-compliant JSON-LD for:
  - `SoftwareApplication` (developer tools, AI agent frameworks, SaaS).
  - `WebSite` (marketing surfaces and documentation portals).
  - `Organization` (company and foundation trust roots).
  - `FAQPage` (Answer Engine Optimization for Google, Perplexity, ChatGPT).

### 3. Native Landing Page Design Playbook (`landing-page-design`)
- **Part A (Strategy)**:
  - A1. Intake discovery batch (Primary action, offer details, ICP, top 3 objections, proof assets).
  - A2. 12-Section conversion hierarchy (Above the fold, mid-page argument, bottom objection handling).
  - A3. Copywriting formulas (Outcome without pain, PAS, clear action verbs).
  - A4. Build order: `Hero` → `Benefits` → `How It Works` → `Proof` → `FAQ` → `Final CTA`.
- **Part B (Visual System)**:
  - B1. Typography: Permitted fonts (Geist, Manrope, Plus Jakarta Sans, Poppins), prohibited fonts (Inter, Arial, Helvetica), no italics, `text-wrap: balance` for headings, `text-wrap: pretty` for body.
  - B2. Disciplined 4px/8px modular rhythm, card perimeter borders, flat backgrounds.

### 4. Dynamic Team Orchestrator Adaptation
- `uaf team compose` automatically promotes generic frontend roles to `landing_page_pro` when prompts mention landing pages, conversion, or marketing.
- Automatically assigns `seo_specialist` for search optimization tasks.
- Non-overlapping perimeters allocated to `docs/*` and `src/components/*` backed by `.claims.lock`.

## Conformance Assertions

- `CONF-V33-001`: `protocols.seo_governance` must be `UAAF-SEO-1.0`.
- `CONF-V33-002`: `extensions.seo_governance` section must be present when extension version is `3.3.0`.
- `CONF-V33-003`: `min_audit_score` must be an integer >= 70.
