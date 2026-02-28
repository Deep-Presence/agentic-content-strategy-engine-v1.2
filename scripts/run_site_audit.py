#!/usr/bin/env python3
"""Run the site audit pipeline from the command line.

Example::

    cd content-strategy-engine
    python scripts/run_site_audit.py --company "Acme Corp" --domain acme.com

    # With optional overrides:
    python scripts/run_site_audit.py \\
        --company "Acme Corp" \\
        --domain acme.com \\
        --max-pages 100 \\
        --max-depth 3
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.models.site_audit import SiteAuditInput


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    p = argparse.ArgumentParser(
        description="Run the site audit pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--company",
        required=True,
        metavar="COMPANY_NAME",
        help="Company name (used to derive the company slug for artifact storage)",
    )
    p.add_argument(
        "--domain",
        required=True,
        help="Domain to audit, e.g. 'example.com'",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=200,
        help="Maximum number of pages to crawl (default: 200)",
    )
    p.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Maximum crawl depth (default: 4)",
    )
    p.add_argument(
        "--no-core-web-vitals",
        action="store_true",
        help="Skip Core Web Vitals checks",
    )
    p.add_argument(
        "--no-schema-validation",
        action="store_true",
        help="Skip JSON-LD schema validation",
    )
    p.add_argument(
        "--no-ai-bot-access",
        action="store_true",
        help="Skip AI-bot access checks",
    )
    p.add_argument(
        "--product-slug",
        default=None,
        help="Optional product slug for product-scoped audits",
    )
    return p.parse_args()


async def _run(args: argparse.Namespace) -> int:
    """Construct SiteAuditInput and run the pipeline."""
    try:
        from core.site_audit.pipeline import run_site_audit
    except ImportError:
        print(
            "ERROR: site_audit pipeline not yet implemented. "
            "Please ensure core/site_audit/pipeline.py exists.",
            file=sys.stderr,
        )
        return 1

    input_data = SiteAuditInput(
        company_name=args.company,
        domain=args.domain,
        product_slug=args.product_slug,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        check_core_web_vitals=not args.no_core_web_vitals,
        check_schema_validation=not args.no_schema_validation,
        check_ai_bot_access=not args.no_ai_bot_access,
    )

    print(f"Starting site audit for {args.domain} ...")
    print(f"  Max pages : {input_data.max_pages}")
    print(f"  Max depth : {input_data.max_depth}")

    result = await run_site_audit(input_data)

    print()
    print("=" * 60)
    print("Site audit complete")
    print("=" * 60)
    print(f"  Domain         : {result.domain}")
    print(f"  Overall score  : {result.overall_score:.1f} / 100  ({result.grade})")
    print(f"  Pages crawled  : {result.pages_crawled}")
    print(f"  Total findings : {result.total_findings}")
    print(f"  Status         : {result.status}")
    if result.error_message:
        print(f"  Error          : {result.error_message}")

    output_path = (
        _PROJECT_ROOT / "artifacts" / "site_audit" / result.audit_id / "audit_result.json"
    )
    print(f"\nArtifacts saved to: {output_path.parent}")
    return 0


def main() -> int:
    """Entry point."""
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
