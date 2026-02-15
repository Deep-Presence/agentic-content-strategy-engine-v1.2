#!/usr/bin/env python3
"""
Run the content generation pipeline.

Example:
  cd content-strategy-engine && python scripts/run_content_engine.py \
    --company-name "Carta" --domain carta.com \
    --company-context-path artifacts/company_context/carta.md \
    --persona-path artifacts/personas/carta__persona-icp.md \
    --style-guide-path artifacts/style_guides/carta.md \
    --gap-slug carta \
    --max-briefs 5 --max-workers 3 --max-revisions 2 \
    --auto-approve
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.content_engine.pipeline import run_content_generation
from core.models.content_generation import ContentGenerationInput


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the content generation pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate content for Carta with auto-approve
  python scripts/run_content_engine.py \\
    --company-name "Carta" --domain carta.com \\
    --gap-slug carta --max-briefs 5 --auto-approve

  # Generate content with HITL review
  python scripts/run_content_engine.py \\
    --company-name "Ramp" --domain ramp.com \\
    --company-context-path artifacts/company_context/ramp.md \\
    --gap-slug ramp --max-briefs 10
""",
    )

    # Required
    p.add_argument("--company-name", required=True, help="Company name")
    p.add_argument("--domain", required=True, help="Company domain (e.g., carta.com)")

    # Artifact paths
    p.add_argument("--company-context-path", default=None, help="Path to company context MD")
    p.add_argument(
        "--persona-path", action="append", default=[], help="Path to persona MD (repeatable)"
    )
    p.add_argument("--style-guide-path", default=None, help="Path to style guide MD")

    # Gap analysis artifacts (auto-resolve from slug)
    p.add_argument(
        "--gap-slug",
        default=None,
        help="Gap analysis slug — auto-discovers gap_report.json, generation_spec.json, analysis.json",
    )
    p.add_argument("--gap-report-json-path", default=None, help="Path to gap report JSON")
    p.add_argument(
        "--generation-spec-json-path", default=None, help="Path to generation spec JSON"
    )
    p.add_argument("--analysis-json-path", default=None, help="Path to analysis JSON")

    # Pipeline config
    p.add_argument("--max-briefs", type=int, default=10, help="Max content briefs to generate")
    p.add_argument("--max-workers", type=int, default=3, help="Max concurrent workers")
    p.add_argument("--max-revisions", type=int, default=2, help="Max revision cycles per brief")
    p.add_argument("--auto-approve", action="store_true", help="Skip HITL review")
    p.add_argument(
        "--skip-stage",
        action="append",
        default=[],
        help="Skip stage number (repeatable, 1-4)",
    )

    return p.parse_args()


def _resolve_gap_artifacts(args: argparse.Namespace) -> None:
    """Auto-discover gap analysis artifacts from slug if not explicitly provided."""
    if not args.gap_slug:
        return

    gap_dir = _PROJECT_ROOT / "artifacts" / "gap_analysis" / args.gap_slug

    if not args.gap_report_json_path:
        candidate = gap_dir / "gap_report.json"
        if candidate.exists():
            args.gap_report_json_path = str(candidate)

    if not args.generation_spec_json_path:
        candidate = gap_dir / "generation_spec.json"
        if candidate.exists():
            args.generation_spec_json_path = str(candidate)

    if not args.analysis_json_path:
        candidate = gap_dir / "analysis.json"
        if candidate.exists():
            args.analysis_json_path = str(candidate)


def main() -> int:
    args = _parse_args()
    _resolve_gap_artifacts(args)

    skip_stages = [int(x) for x in args.skip_stage if str(x).isdigit()]

    input_data = ContentGenerationInput(
        company_name=args.company_name,
        domain=args.domain,
        company_context_path=args.company_context_path,
        persona_paths=args.persona_path or [],
        style_guide_path=args.style_guide_path,
        gap_report_json_path=args.gap_report_json_path,
        generation_spec_json_path=args.generation_spec_json_path,
        analysis_json_path=args.analysis_json_path,
        max_briefs=args.max_briefs,
        max_concurrent_workers=args.max_workers,
        max_revision_cycles=args.max_revisions,
        auto_approve=args.auto_approve,
        skip_stages=skip_stages,
    )

    # Event-loop detection for Jupyter compatibility
    try:
        asyncio.get_running_loop()
        import nest_asyncio

        nest_asyncio.apply()
    except RuntimeError:
        pass

    output = asyncio.run(run_content_generation(input_data=input_data))

    print("\n" + "=" * 60)
    print("Content generation complete")
    print(f"  Approved: {output.total_approved}")
    print(f"  Rejected: {output.total_rejected}")
    print(f"  Total:    {output.total_briefs}")
    if output.pieces:
        print(f"\n  Artifacts: artifacts/content/{output.company_slug}/")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
