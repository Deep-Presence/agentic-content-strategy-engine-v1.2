#!/usr/bin/env python3
"""
Run the Voice Style Guide pipeline: Discovery → HITL-1 → Research → Synthesis.

Three-agent architecture that discovers influential authors, deep-researches their
writing style, and synthesizes a brand voice guide.

Requires env vars:
  - GOOGLE_API_KEY (or GOOGLE_API_KEY_AUDIENCE_PERSONA) — for Gemini Flash (discovery)
  - PERPLEXITY_API_KEY — for sonar-deep-research (author research)
  - ANTHROPIC_API_KEY — for Claude Sonnet (voice synthesis)

Prerequisites:
  - Company context artifact: artifacts/company_context/{slug}.md
  - Persona profiles: artifacts/audience_personas/{slug}/ (at least 1 active persona)

Example:
  python scripts/run_voice_style_guide.py --company-name "Lovable" --domain lovable.dev --auto-approve
  python scripts/run_voice_style_guide.py --company-name "Ramp" --domain ramp.com --max-authors 2 --auto-approve
"""
import argparse
import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.models.voice_style_guide import VSG_MAX_AUTHORS_LIMIT, VSG_MIN_AUTHORS, VoiceStyleGuideInput
from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Voice Style Guide pipeline (Discovery + Research + Synthesis).",
    )
    p.add_argument("--company-name", required=True, help="Company name")
    p.add_argument("--domain", default=None, help="Company domain (optional)")
    p.add_argument("--company-slug", default=None, help="Company slug (derived from name if omitted)")
    p.add_argument("--product-slug", default=None, help="Product slug for product-level guides")
    p.add_argument("--product-name", default=None, help="Product name (optional)")
    p.add_argument(
        "--max-authors", type=int, default=VSG_MAX_AUTHORS_LIMIT,
        help=f"Max authors to discover ({VSG_MIN_AUTHORS}-{VSG_MAX_AUTHORS_LIMIT}, default: {VSG_MAX_AUTHORS_LIMIT})",
    )
    p.add_argument("--language", default="en", help="Language code (default: en)")
    p.add_argument("--region", default=None, help="Region (optional)")
    p.add_argument("--constraints", default=None, help="Additional constraints (optional)")
    p.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve the HITL checkpoint (author review).",
    )
    p.add_argument(
        "--artifacts-root", default="artifacts",
        help="Artifacts root directory (default: artifacts)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    auto_approve_cps = [1] if args.auto_approve else []

    inp = VoiceStyleGuideInput(
        company_name=args.company_name,
        domain=args.domain,
        company_slug=args.company_slug,
        product_slug=args.product_slug,
        product_name=args.product_name,
        max_authors=args.max_authors,
        language=args.language,
        region=args.region,
        additional_constraints=args.constraints,
        auto_approve_checkpoints=auto_approve_cps,
    )

    print(f"\nRunning Voice Style Guide pipeline for: {inp.company_name}")
    print(f"  Max authors: {inp.max_authors}")
    print(f"  Auto-approve: {'yes' if auto_approve_cps else 'no (manual HITL)'}")
    print()

    result = asyncio.run(
        run_voice_style_guide_pipeline(
            inp,
            artifacts_root=Path(args.artifacts_root),
        )
    )

    print("\n" + "=" * 60)
    print("  VOICE STYLE GUIDE PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Authors discovered:  {result.authors_discovered}")
    print(f"  Authors approved:    {result.authors_approved}")
    print(f"  Authors researched:  {result.authors_researched}")
    print(f"  Guide generated:     {result.guide_generated}")
    print(f"  Guide directory:     {result.guide_dir}")
    if result.style_guide_path:
        print(f"  Style guide path:    {result.style_guide_path}")
    print(f"  Total time:          {result.total_execution_time_s:.1f}s")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
