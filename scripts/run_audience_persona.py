#!/usr/bin/env python3
"""
Run the Audience Persona pipeline: Suggester → HITL-1 → Profile Generator → HITL-2 → Finalize.

Two-agent architecture that reads company context + customer reviews from the
Knowledge Base, then generates detailed persona profiles via Perplexity deep research.

Requires env vars:
  - GOOGLE_API_KEY_AUDIENCE_PERSONA (or GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT)
  - PERPLEXITY_API_KEY

Example:
  python scripts/run_audience_persona.py --company-name "Lovable" --domain lovable.dev --auto-approve
  python scripts/run_audience_persona.py --company-name "Ramp" --auto-approve --max-personas 5
"""
import argparse
import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.models.audience_persona import AudiencePersonaInput
from core.research.audience_persona.pipeline import run_audience_persona_pipeline


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Audience Persona pipeline (Suggester + Profile Generator).",
    )
    p.add_argument("--company-name", required=True, help="Company name")
    p.add_argument("--domain", default=None, help="Company domain (optional)")
    p.add_argument("--company-slug", default=None, help="Company slug (derived from name if omitted)")
    p.add_argument("--product-slug", default=None, help="Product slug for product-level personas")
    p.add_argument("--product-name", default=None, help="Product name (optional)")
    p.add_argument("--max-personas", type=int, default=5, help="Max personas to suggest (3-7, default: 5)")
    p.add_argument("--language", default="en", help="Language code (default: en)")
    p.add_argument("--region", default=None, help="Region (optional)")
    p.add_argument("--constraints", default=None, help="Additional constraints (optional)")
    p.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve both HITL checkpoints (brief review + profile review).",
    )
    p.add_argument(
        "--auto-approve-briefs",
        action="store_true",
        help="Auto-approve only HITL-1 (brief review).",
    )
    p.add_argument(
        "--auto-approve-profiles",
        action="store_true",
        help="Auto-approve only HITL-2 (profile review).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    auto_approve_cps = []
    if args.auto_approve:
        auto_approve_cps = [1, 2]
    else:
        if args.auto_approve_briefs:
            auto_approve_cps.append(1)
        if args.auto_approve_profiles:
            auto_approve_cps.append(2)

    inp = AudiencePersonaInput(
        company_name=args.company_name,
        domain=args.domain,
        company_slug=args.company_slug,
        product_slug=args.product_slug,
        product_name=args.product_name,
        max_personas=args.max_personas,
        language=args.language,
        region=args.region,
        additional_constraints=args.constraints,
        auto_approve_checkpoints=auto_approve_cps,
    )

    print(f"\nRunning Audience Persona pipeline for: {inp.company_name}")
    print(f"  Max personas: {inp.max_personas}")
    print(f"  Auto-approve checkpoints: {auto_approve_cps or 'none (manual HITL)'}")
    print()

    result = asyncio.run(run_audience_persona_pipeline(inp))

    print("\n" + "=" * 60)
    print("  AUDIENCE PERSONA PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Briefs suggested:   {result.briefs_suggested}")
    print(f"  Briefs approved:    {result.briefs_approved}")
    print(f"  Profiles generated: {result.profiles_generated}")
    print(f"  Persona directory:  {result.persona_dir}")
    print(f"  Total time:         {result.total_execution_time_s:.1f}s")
    print()

    if result.persona_results:
        for pid, pr in result.persona_results.items():
            if pr.error:
                print(f"  [{pid}] {pr.persona_name} — ERROR: {pr.error}")
            else:
                print(f"  [{pid}] {pr.persona_name} — {pr.word_count} words")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
