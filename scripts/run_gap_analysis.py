#!/usr/bin/env python3
"""
Run the gap analysis pipeline.

Example:
  cd content-strategy-engine && python scripts/run_gap_analysis.py --company-name "Acme" --domain acme.com \
    --company-context-path /artifacts/company_context/acme.md \
    --persona-path /artifacts/personas/acme_icp.md
"""
import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.gap_analysis.pipeline import run_gap_analysis
from core.models.gap_analysis import GapAnalysisInput


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the gap analysis pipeline.")
    p.add_argument("--company-name", required=True, help="Company name")
    p.add_argument("--domain", required=True, help="Company domain (e.g., acme.com)")
    p.add_argument("--company-id", default=None, help="Supabase company UUID (optional)")
    p.add_argument("--company-context-path", default=None, help="DeepAgents path")
    p.add_argument("--persona-path", action="append", default=[], help="Persona path (repeatable)")
    p.add_argument("--style-guide-path", default=None, help="Style guide path")
    p.add_argument("--seed-url", action="append", default=[], help="Seed URL (repeatable)")
    p.add_argument("--max-queries", type=int, default=150, help="Max queries to generate")
    p.add_argument(
        "--platforms",
        default="perplexity,openai,gemini,claude",
        help="Comma-separated platform list",
    )
    p.add_argument(
        "--skip-step",
        action="append",
        default=[],
        help="Skip step number (repeatable, 1-8)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    skip_steps = [int(x) for x in args.skip_step if str(x).isdigit()]

    input_data = GapAnalysisInput(
        company_id=args.company_id,
        company_name=args.company_name,
        domain=args.domain,
        seed_urls=args.seed_url or [],
        company_context_path=args.company_context_path,
        persona_paths=args.persona_path or [],
        style_guide_path=args.style_guide_path,
        max_queries=args.max_queries,
        platforms=platforms,
    )

    report = run_gap_analysis(input_data=input_data, skip_steps=skip_steps)
    print("\n" + "=" * 60)
    print("Gap analysis complete")
    print("=" * 60)
    if report.report_md:
        print("Report: artifacts/gap_analysis/<company_slug>/gap_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
