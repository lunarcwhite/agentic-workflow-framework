#!/usr/bin/env python3
"""UAAF Native SEO & Landing Page Audit Utility.

Provides automated audit and generation of semantic HTML metadata, OpenGraph,
Twitter Cards, and Schema.org JSON-LD Structured Data, compliant with UAAF
Anti-Slop and Web Standards.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def audit_html_content(content: str, filename: str = "document.html") -> dict[str, Any]:
    """Perform a rigorous, deterministic SEO and semantic structure audit on HTML string."""
    results: dict[str, Any] = {
        "file": filename,
        "score": 100,
        "passes": [],
        "warnings": [],
        "errors": [],
        "meta": {},
        "structured_data": [],
    }

    # 1. Document title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    if not title_match:
        results["errors"].append("Missing <title> tag")
        results["score"] -= 25
    else:
        title = title_match.group(1).strip()
        results["meta"]["title"] = title
        if len(title) < 15:
            results["warnings"].append(f"Title is too short ({len(title)} chars, recommend 15-70 chars)")
            results["score"] -= 5
        elif len(title) > 75:
            results["warnings"].append(f"Title is too long ({len(title)} chars, recommend <= 70 chars for SERP display)")
            results["score"] -= 5
        else:
            results["passes"].append(f"Title length optimal ({len(title)} chars)")

    # 2. Meta description
    desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', content, re.IGNORECASE)
    if not desc_match:
        desc_match = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', content, re.IGNORECASE)
    if not desc_match:
        results["errors"].append("Missing <meta name=\"description\"> tag")
        results["score"] -= 20
    else:
        desc = desc_match.group(1).strip()
        results["meta"]["description"] = desc
        if len(desc) < 50:
            results["warnings"].append(f"Meta description too short ({len(desc)} chars, recommend 50-160 chars)")
            results["score"] -= 5
        elif len(desc) > 170:
            results["warnings"].append(f"Meta description too long ({len(desc)} chars, may be truncated in search snippets)")
            results["score"] -= 5
        else:
            results["passes"].append(f"Meta description length optimal ({len(desc)} chars)")

    # 3. Viewport tag
    if re.search(r'<meta[^>]+name=["\']viewport["\']', content, re.IGNORECASE):
        results["passes"].append("Responsive viewport meta tag present")
    else:
        results["errors"].append("Missing mobile viewport <meta name=\"viewport\"> tag")
        results["score"] -= 15

    # 4. Canonical link
    if re.search(r'<link[^>]+rel=["\']canonical["\']', content, re.IGNORECASE):
        results["passes"].append("Canonical link (<link rel=\"canonical\">) present")
    else:
        results["warnings"].append("Missing canonical link tag (recommended to prevent duplicate content indexing)")
        results["score"] -= 5

    # 5. OpenGraph Tags
    og_title = re.search(r'<meta[^>]+property=["\']og:title["\']', content, re.IGNORECASE)
    og_desc = re.search(r'<meta[^>]+property=["\']og:description["\']', content, re.IGNORECASE)
    og_type = re.search(r'<meta[^>]+property=["\']og:type["\']', content, re.IGNORECASE)
    og_url = re.search(r'<meta[^>]+property=["\']og:url["\']', content, re.IGNORECASE)

    og_count = sum(1 for tag in [og_title, og_desc, og_type, og_url] if tag)
    if og_count == 4:
        results["passes"].append("OpenGraph basic tags complete (og:title, og:description, og:type, og:url)")
    else:
        results["warnings"].append(f"Incomplete OpenGraph tags ({og_count}/4 present)")
        results["score"] -= 5 * (4 - og_count)

    # 6. Heading Hierarchy (H1 & H2)
    h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", content, re.IGNORECASE | re.DOTALL)
    if len(h1_matches) == 0:
        results["errors"].append("Missing primary <h1> heading tag")
        results["score"] -= 15
    elif len(h1_matches) > 1:
        results["warnings"].append(f"Multiple <h1> tags found ({len(h1_matches)}). Best practice is exactly one <h1> per landing page")
        results["score"] -= 5
    else:
        results["passes"].append("Single primary <h1> heading found")

    h2_matches = re.findall(r"<h2[^>]*>", content, re.IGNORECASE)
    if h2_matches:
        results["passes"].append(f"Structured subheadings found ({len(h2_matches)} <h2> tags)")

    # 7. Image alt tags
    imgs = re.findall(r"<img\s+([^>]*?)>", content, re.IGNORECASE)
    if imgs:
        missing_alt = [img for img in imgs if 'alt=' not in img.lower()]
        if missing_alt:
            results["warnings"].append(f"{len(missing_alt)} image(s) missing 'alt' attribute for accessibility/SEO")
            results["score"] -= min(10, len(missing_alt) * 2)
        else:
            results["passes"].append(f"All images ({len(imgs)}) have alt attributes")

    # 8. Schema.org JSON-LD Structured Data
    json_ld_matches = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', content, re.IGNORECASE | re.DOTALL)
    if json_ld_matches:
        valid_schemas = 0
        for block in json_ld_matches:
            try:
                schema_data = json.loads(block.strip())
                results["structured_data"].append(schema_data)
                valid_schemas += 1
            except Exception as e:
                results["warnings"].append(f"Malformed JSON-LD script block: {e}")
                results["score"] -= 5
        if valid_schemas > 0:
            results["passes"].append(f"Schema.org JSON-LD structured data detected ({valid_schemas} valid block(s))")
    else:
        results["warnings"].append("No Schema.org JSON-LD structured data found (recommended for rich snippets)")
        results["score"] -= 5

    # Clamp score
    results["score"] = max(0, min(100, results["score"]))
    return results


def cmd_audit(target: Path, min_score: int = 80) -> dict[str, Any]:
    """Audit single HTML file or recursive directory."""
    target = target.resolve()
    html_files: list[Path] = []
    if target.is_file():
        if target.suffix.lower() in [".html", ".htm"]:
            html_files.append(target)
        else:
            print(f"[ERROR] Target file {target.name} is not an HTML file.")
            sys.exit(1)
    elif target.is_dir():
        html_files = sorted(list(target.glob("**/*.html")))
        if not html_files:
            print(f"[WARNING] No HTML files found under {target}.")
            return {"total_files": 0, "status": "NO_FILES"}

    print("=" * 70)
    print("UAAF NATIVE SEO & LANDING PAGE AUDIT")
    print(f"Target: {target} ({len(html_files)} HTML file(s) found)")
    print("=" * 70)

    overall_pass = True
    summary: list[dict[str, Any]] = []

    for f in html_files:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            res = audit_html_content(content, filename=f.name)
            summary.append(res)

            print(f"\n[FILE] {f.name}")
            print(f"Score: {res['score']}/100")

            for p in res["passes"]:
                print(f"  [OK] {p}")
            for w in res["warnings"]:
                print(f"  [WARN] {w}")
            for e in res["errors"]:
                print(f"  [FAIL] {e}")

            if res["score"] < min_score:
                overall_pass = False
                print(f"  --> FAILED: Score {res['score']} is below minimum threshold ({min_score})")
            else:
                print(f"  --> PASSED: Audit satisfied threshold ({min_score})")

        except Exception as e:
            print(f"[ERROR] Failed reading {f}: {e}")
            overall_pass = False

    print("\n" + "=" * 70)
    status_str = "PASS" if overall_pass else "FAIL"
    print(f"OVERALL AUDIT RESULT: [{status_str}]")
    print("=" * 70)

    return {
        "status": status_str,
        "files_checked": len(html_files),
        "results": summary,
        "overall_pass": overall_pass,
    }


def generate_json_ld(
    schema_type: str,
    name: str,
    description: str,
    url: str,
    author_or_org: str = "UAAF",
) -> str:
    """Generate Schema.org compliant JSON-LD string."""
    schema_type = schema_type.strip()
    if schema_type.lower() == "softwareapplication":
        data = {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": name,
            "description": description,
            "url": url,
            "applicationCategory": "DeveloperApplication",
            "operatingSystem": "Cross-platform",
            "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "USD",
            },
            "author": {
                "@type": "Organization",
                "name": author_or_org,
                "url": url,
            },
        }
    elif schema_type.lower() == "organization":
        data = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": name,
            "description": description,
            "url": url,
        }
    elif schema_type.lower() == "faqpage":
        data = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f"What is {name}?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": description,
                    },
                }
            ],
        }
    else:  # Default WebSite
        data = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": name,
            "description": description,
            "url": url,
        }

    return json.dumps(data, indent=2)


def cmd_generate(
    schema_type: str,
    name: str,
    description: str,
    url: str,
    output: Path | None = None,
) -> str:
    """Generate JSON-LD markup and output to stdout or file."""
    json_ld = generate_json_ld(schema_type, name, description, url)
    wrapped = f'<script type="application/ld+json">\n{json_ld}\n</script>'
    if output:
        output.write_text(wrapped, encoding="utf-8")
        print(f"[OK] Generated {schema_type} JSON-LD written to {output}")
    else:
        print(wrapped)
    return wrapped


def main() -> None:
    parser = argparse.ArgumentParser(prog="uaf seo", description="UAAF Native SEO & Landing Page Auditor")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # audit subcommand
    audit_parser = subparsers.add_parser("audit", help="Audit HTML file or directory for SEO and semantic standards")
    audit_parser.add_argument("path", type=str, nargs="?", default="docs", help="File or directory to audit (default: docs)")
    audit_parser.add_argument("--threshold", type=int, default=80, help="Minimum passing score (default: 80)")

    # generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate Schema.org JSON-LD structured data")
    gen_parser.add_argument("--type", type=str, default="SoftwareApplication", choices=["SoftwareApplication", "Organization", "WebSite", "FAQPage"], help="Schema type")
    gen_parser.add_argument("--name", type=str, required=True, help="Product or website name")
    gen_parser.add_argument("--description", type=str, required=True, help="Meta description")
    gen_parser.add_argument("--url", type=str, required=True, help="Canonical URL")
    gen_parser.add_argument("--output", type=str, default=None, help="Optional output file path")

    args = parser.parse_args()

    if args.subcommand == "audit":
        res = cmd_audit(Path(args.path), min_score=args.threshold)
        sys.exit(0 if res.get("overall_pass", False) else 1)
    elif args.subcommand == "generate":
        out_path = Path(args.output) if args.output else None
        cmd_generate(args.type, args.name, args.description, args.url, output=out_path)


if __name__ == "__main__":
    main()
