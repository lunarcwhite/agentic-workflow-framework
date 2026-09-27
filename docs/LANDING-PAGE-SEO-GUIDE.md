# UAAF v3.3 Native Landing Page Architecture & SEO Governance Guide

Comprehensive reference guide for building high-converting, accessible, and search-optimized landing pages using UAAF's native architecture, deterministic quality gates, and automated SEO governance (Protocol `UAAF-SEO-1.0`).

---

## 📑 Table of Contents
1. [The Landing Page Problem in AI Coding](#1-the-landing-page-problem-in-ai-coding)
2. [The UAAF Solution: Protocol UAAF-SEO-1.0](#2-the-uaaf-solution-protocol-uaaf-seo-10)
3. [The 2-Part Methodology (Strategy & Visual System)](#3-the-2-part-methodology)
4. [The 12-Section High-Converting Hierarchy](#4-the-12-section-high-converting-hierarchy)
5. [Anti-Slop Copywriting Frameworks](#5-anti-slop-copywriting-frameworks)
6. [Automated Technical SEO & AEO Gates (uaf seo)](#6-automated-technical-seo--aeo-gates-uaf-seo)
7. [Dynamic Multi-Agent Team Roles](#7-dynamic-multi-agent-team-roles)
8. [Step-by-Step Hands-On Tutorial](#8-step-by-step-hands-on-tutorial)

---

## 1. The Landing Page Problem in AI Coding

When AI agents are tasked with creating web pages or landing pages without strict governance, three recurring failure patterns emerge:
1. **Visual Slop & Generic Aesthetics**: Relying on default browser typography, clashing color schemes, arbitrary padding, and uninspired MVP layouts.
2. **Missing Technical SEO & Machine Discoverability**: Omitting OpenGraph tags, canonical URLs, responsive viewports, single `<h1>` hierarchy, or structured Schema.org JSON-LD data.
3. **Weak, Generic Copywriting**: Filling headlines with empty buzzwords (*"Revolutionize your workflow with next-gen AI"*) instead of concrete value propositions and objection-handling.

---

## 2. The UAAF Solution: Protocol UAAF-SEO-1.0

Protocol `UAAF-SEO-1.0` treats landing page engineering as a **deterministic, governed system**:

```
                       [ User Instruction / Objective ]
                                      │
                                      ▼
                      [ uaf team compose --objective ... ]
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
      [ landing_page_pro ]                         [ seo_specialist ]
    Scope: docs/, src/views/*                    Scope: public/, sitemap.xml
                 │                                         │
                 └────────────────────┬────────────────────┘
                                      ▼
                           [ Sequential Build Order ]
          Intake ➔ 12-Section Hierarchy ➔ Visual Tokens ➔ Implementation
                                      │
                                      ▼
                        [ Automated SEO Quality Gates ]
                          python tools/uaf.py seo audit
                                      │
                                      ▼
                      [ 100/100 Verified Production Page ]
```

---

## 3. The 2-Part Methodology

Inspired by elite conversion engineering principles (such as `elayadesign`), UAAF enforces a strict two-part framework:

### Part A: Strategy & Structure
- **Structured Intake**: Clarifies ideal customer profile (ICP), primary action, top 3 objections, and proof assets.
- **Copywriting First**: Headlines, subheads, and CTAs must be finalized before visual styling.
- **Sequential Build Order**:
  1. Hero (Value proposition & primary CTA)
  2. Benefits & Features (Outcome-oriented)
  3. How It Works (3 clear sequential steps)
  4. Social Proof & Testimonials (Real metrics)
  5. FAQ Section (Handling top objections)
  6. Final CTA Banner & Compliant Footer

### Part B: Non-negotiable Visual System
- **Typography Standards**:
  - Permitted fonts: `Geist`, `Manrope`, `Plus Jakarta Sans`, or `Poppins`.
  - Balanced typography: `text-wrap: balance;` on headings; `text-wrap: pretty;` on body copy.
  - Prohibited: Generic defaults, italics for emphasis, or inconsistent font sizes.
- **Strict UI Rules**:
  - Flat cards with full-perimeter borders (`1px solid rgba(255,255,255,0.08)`).
  - Consistent 4px/8px modular spacing rhythm (`0.5rem`, `1rem`, `1.5rem`, `2rem`, `3rem`, `4rem`).
  - WCAG AA contrast ratio compliance (minimum 4.5:1 for body copy).

---

## 4. The 12-Section High-Converting Hierarchy

Every complete landing page built under UAAF adheres to a logical 12-section architecture:

| Section # | Component | Primary Objective |
| :---: | :--- | :--- |
| **01** | **Navigation Bar** | Logo, anchor links to key sections, GitHub/App link, and Primary CTA button. |
| **02** | **Hero Section** | Above-the-fold value proposition, outcome-driven subhead, primary & secondary CTA. |
| **03** | **Social Proof Bar** | Partner logos, active metrics, or community trust badges. |
| **04** | **Problem Statement** | Validating user frustration (Pain agitation: What is broken today?). |
| **05** | **Solution Overview** | Clear bridge explaining how the product resolves the frustration. |
| **06** | **Features & Benefits Grid** | 3–6 value cards focusing on tangible outcomes, not just specs. |
| **07** | **How It Works** | 3 sequential, frictionless steps showing simplicity. |
| **08** | **Social Proof / Testimonials** | Real user quotes, GitHub stars, or benchmark results. |
| **09** | **Pricing / Offer** | Transparent tiers or open-source tiers with clear deliverables. |
| **10** | **Frequently Asked Questions** | Interactive accordion addressing top objections + Schema.org `FAQPage` JSON-LD. |
| **11** | **Final CTA Banner** | High-contrast closing banner giving the user one clear final action. |
| **12** | **Footer** | Brand metadata, copyright, sitemap links, and legal pages (`privacy-policy.html`, `terms.html`). |

---

## 5. Anti-Slop Copywriting Frameworks

UAAF requires copy to follow proven copywriting formulas rather than vague LLM filler words:

1. **Problem-Agitate-Solve (PAS)**:
   - *Problem*: Autonomous coding assistants silently hallucinate test outputs.
   - *Agitate*: Broken code reaches production, wasting hours of debugging.
   - *Solve*: UAAF enforces deterministic task contracts and cryptographic evidence receipts.

2. **Attention-Interest-Desire-Action (AIDA)**:
   - *Attention*: Hook with real performance metrics.
   - *Interest*: Detail how disjoint perimeters eliminate merge collisions.
   - *Desire*: Show how teams ship 10x faster with zero merge conflicts.
   - *Action*: Install with one simple CLI command.

3. **Forbidden Buzzwords**:
   - Prohibited: *"Revolutionize"*, *"Unleash"*, *"Next-generation"*, *"Seamless"*, *"Supercharge"*.
   - Required: Concrete verbs and metrics (*"Cut merge conflicts to zero"*, *"Audit in 60s"*, *"Cryptographically verified"*).

---

## 6. Automated Technical SEO & AEO Gates (`uaf seo`)

The `tools/uaf_seo.py` module provides deterministic CLI verification:

### 1. Automated HTML Quality Audit
```bash
python tools/uaf.py seo audit docs/index.html --threshold 85
```
Evaluates 8 deterministic quality gates:
1. `<title>` presence and character boundary (optimal 15–70 characters).
2. `<meta name="description">` boundary (optimal 50–160 characters).
3. Mobile viewport `<meta name="viewport">` presence.
4. Canonical link tag `<link rel="canonical" href="...">` presence.
5. Social sharing metadata: OpenGraph (`og:title`, `og:description`, `og:type`, `og:url`) & Twitter Cards.
6. Semantic heading hierarchy: exactly one `<h1>` heading and structured `<h2>`/`<h3>` nesting.
7. Image accessibility: enforcing descriptive `alt="..."` attributes on every `<img>` tag.
8. Schema.org JSON-LD structured data validation.

### 2. Standards-Compliant Schema Generation
```bash
# Software Application Schema
python tools/uaf.py seo generate --type SoftwareApplication \
  --name "My Platform" \
  --description "High-performance autonomous agent engine" \
  --url "https://myplatform.com"

# FAQ Page Schema (Answer Engine Optimization for AI Search)
python tools/uaf.py seo generate --type FAQPage
```

---

## 7. Dynamic Multi-Agent Team Roles

When composing teams via `uaf team compose`, UAAF automatically assigns specialized roles with disjoint file perimeters:

* **`landing_page_pro`**:
  - Focus: Visual hierarchy, conversion structure, typography, responsive styling, and interactive UI components.
  - Permitted files: `docs/*`, `src/views/*`, `src/components/*`, `public/`.
  - Excluded files: Server configuration, database schemas, test harnesses.

* **`seo_specialist`**:
  - Focus: Metadata, OpenGraph cards, Schema.org JSON-LD, sitemap generation, accessibility compliance, and AEO optimization.
  - Permitted files: `public/`, `docs/`, `src/seo/`, `sitemap.xml`, `robots.txt`.
  - Excluded files: Core application runtime.

---

## 8. Step-by-Step Hands-On Tutorial

### Step 1: Install & Govern the Landing Page & SEO Plugin
```bash
python tools/uaf.py plugin install landing-page-seo
python tools/uaf.py plugin export landing-page-seo --target all
```

### Step 2: Compose a Multi-Agent Team
```bash
python tools/uaf.py team compose "Build high-converting landing page with full SEO optimization"
```

### Step 3: Implement & Verify Quality
Once the page is scaffolded, run the deterministic audit:
```bash
python tools/uaf.py seo audit docs/index.html
```

Expected output:
```text
======================================================================
UAAF NATIVE SEO & LANDING PAGE AUDIT
Target: docs/index.html (1 HTML file(s) found)
======================================================================

[FILE] index.html
Score: 100/100
  [OK] Title length optimal (67 chars)
  [OK] Meta description length optimal (113 chars)
  [OK] Responsive viewport meta tag present
  [OK] Canonical link (<link rel="canonical">) present
  [OK] OpenGraph basic tags complete (og:title, og:description, og:type, og:url)
  [OK] Single primary <h1> heading found
  [OK] Structured subheadings found (8 <h2> tags)
  [OK] All images have alt attributes
  [OK] Schema.org JSON-LD structured data detected (1 valid block(s))
  --> PASSED: Audit satisfied threshold (80)

======================================================================
OVERALL AUDIT RESULT: [PASS]
======================================================================
```
