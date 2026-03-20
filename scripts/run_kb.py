#!/usr/bin/env python3
"""Run the Knowledge Base pipeline — 5 specialist agents + synthesis.

Agents:
  Tier 1 (Perplexity sonar-deep-research): company_overview, customer_reviews,
          competitor_scanner, weakness_analyst
  Tier 2 (Anthropic Claude + web_search): brand_perception
  Tier 3 (LangGraph + Claude Opus): synthesis

Requires env vars:
  PERPLEXITY_API_KEY          — Agents 1-4 (deep research)
  ANTHROPIC_API_KEY           — Agent 5 (brand perception) + Agent 6 (synthesis)

Example:
  python scripts/run_kb.py --company-name "Ramp" --domain ramp.com
  python scripts/run_kb.py --company-name "Ramp" --domain ramp.com --auto-approve
  python scripts/run_kb.py --company-name "Ramp" --refresh company_overview customer_reviews
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.models.knowledge_base import KBDocType, KnowledgeBaseInput
from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Knowledge Base pipeline (5 agents + synthesis).",
    )
    p.add_argument("--company-name", required=True, help="Company name")
    p.add_argument("--domain", default=None, help="Company domain (optional)")
    p.add_argument("--company-slug", default=None, help="Override slug (default: derived from name)")
    p.add_argument("--seed-url", action="append", default=[], help="Seed URL (repeatable)")
    p.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve all 3 HITL checkpoints (skip human review)",
    )
    p.add_argument(
        "--refresh",
        nargs="+",
        choices=[dt.value for dt in KBDocType if dt != KBDocType.SYNTHESIS],
        default=None,
        help="Refresh only these doc types (omit for full run)",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return p.parse_args()


async def main() -> int:
    args = _parse_args()

    from core.shared_tools.structured_logging import configure_logging

    configure_logging(level="DEBUG" if args.verbose else "INFO")

    inp = KnowledgeBaseInput(
        company_name=args.company_name,
        domain=args.domain,
        company_slug=args.company_slug,
        seed_urls=args.seed_url or [],
        auto_approve_checkpoints=[1, 2, 3] if args.auto_approve else [],
        refresh_docs=args.refresh,
    )

    print(f"\n{'=' * 60}")
    print(f"  Knowledge Base Pipeline — {args.company_name}")
    print(f"  Mode: {'refresh ' + str(args.refresh) if args.refresh else 'full'}")
    print(f"  HITL: {'auto-approve' if args.auto_approve else 'interactive'}")
    print(f"{'=' * 60}\n")

    result = await run_knowledge_base_pipeline(inp)

    print(f"\n{'=' * 60}")
    print("  RESULTS")
    print(f"{'=' * 60}")
    print(f"  Slug:            {result.slug}")
    print(f"  Changed docs:    {result.changed_docs}")
    print(f"  KB dir:          {result.knowledge_base_dir}")
    print(f"  Company profile: {result.company_profile_path or '(none)'}")
    print(f"  Time:            {result.total_execution_time_s:.1f}s")

    for name, agent_result in result.agent_results.items():
        status = "ERROR" if agent_result.error else f"{agent_result.word_count} words"
        print(f"  Agent {name:25s} → {status}")
        if agent_result.error:
            print(f"    Error: {agent_result.error}")

    if result.synthesis_md:
        print(f"\n  Synthesis: {len(result.synthesis_md.split())} words")
        print(f"  Preview: {result.synthesis_md[:300]}...")
    else:
        print(f"\n  Synthesis: FAILED (no output produced)")

    from pathlib import Path as _P
    profile = _P(result.company_profile_path) if result.company_profile_path else None
    if profile and profile.exists():
        print(f"  Company profile written: {profile}")
    else:
        print(f"  Company profile: NOT WRITTEN")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
