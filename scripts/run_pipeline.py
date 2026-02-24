#!/usr/bin/env python3
"""
Run the content-strategy-engine pipeline: company_research -> persona_research -> style_guide.

Uses run_graph_with_approval() for each stage, which handles LangGraph >=1.0
interrupt/resume cycle interactively in the terminal.

Requires env vars (see README):
  - GOOGLE_API_KEY_COMPANY_DEEPAGENT
  - GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT (for persona stage)
  - PERPLEXITY_API_KEY (for web research; get at https://perplexity.ai/account/api)
  - Optional: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (for mirroring)

Example:
  cd content-strategy-engine && python scripts/run_pipeline.py --company-name "Acme Corp" --domain acme.com
  cd content-strategy-engine && python scripts/run_pipeline.py --company-name "Acme" --auto-approve
"""
import argparse
import sys
from pathlib import Path

# Ensure content-strategy-engine/ is on Python path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.research.graphs.company_research import build_graph as build_company_graph
from core.research.graphs.persona_research import build_graph as build_persona_graph
from core.research.graphs.style_guide import build_graph as build_style_graph
from core.models.artifacts import CompanyResearchInput
from core.models.personas import PersonaResearchInput
from core.models.style_guide import StyleGuideResearchInput
from scripts._cli_approval import run_graph_with_approval


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the content pipeline: company -> persona -> style_guide.",
    )
    p.add_argument("--company-name", required=True, help="Company name")
    p.add_argument("--domain", default=None, help="Company domain (optional)")
    p.add_argument("--company-id", default=None, help="Supabase company UUID (optional)")
    p.add_argument("--seed-url", action="append", default=[], help="Seed URL (repeatable)")
    p.add_argument("--internal-source", action="append", default=[], help="Internal source path (repeatable)")
    p.add_argument("--language", default="en", help="Language code")
    p.add_argument(
        "--persona",
        action="store_true",
        help="Run persona stage after company (requires company to complete first)",
    )
    p.add_argument(
        "--style",
        action="store_true",
        help="Run style_guide stage after persona (requires persona to complete first)",
    )
    p.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve all drafts (skips human review; for testing only)",
    )
    p.add_argument(
        "--max-personas",
        type=int,
        default=1,
        help="Max personas to generate (1-3, default 1 for speed)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    slug = args.company_name.lower().replace(" ", "-")

    # ── Stage 1: Company research ─────────────────────────────────
    company_input = CompanyResearchInput(
        company_id=args.company_id,
        company_name=args.company_name,
        domain=args.domain,
        seed_urls=args.seed_url or [],
        internal_sources=args.internal_source or [],
        language=args.language,
    )

    print("\n" + "=" * 60)
    print("  STAGE 1: Company Research")
    print("=" * 60)

    company_result = run_graph_with_approval(
        build_graph_fn=build_company_graph,
        initial_state={"input": company_input, "auto_approve": args.auto_approve},
        thread_id=f"cli-pipeline-company-{slug}",
    )

    company_decision = (company_result.get("approval_decision") or "").lower()
    if company_decision == "reject":
        print("\nCompany stage rejected — stopping pipeline.")
        return 0

    company_output_path = company_result.get("output_path")
    print(f"\nCompany artifact: {company_output_path or '(none)'}")

    # ── Stage 2: Persona research ─────────────────────────────────
    persona_paths = []
    if args.persona:
        persona_input = PersonaResearchInput(
            company_id=args.company_id,
            company_name=args.company_name,
            domain=args.domain,
            company_slug=slug,
            company_context_path=company_output_path,
            max_personas=min(3, max(1, args.max_personas)),
        )

        print("\n" + "=" * 60)
        print("  STAGE 2: Persona Research")
        print("=" * 60)

        persona_result = run_graph_with_approval(
            build_graph_fn=build_persona_graph,
            initial_state={"input": persona_input, "auto_approve": args.auto_approve},
            thread_id=f"cli-pipeline-persona-{slug}",
        )

        persona_decision = (persona_result.get("approval_decision") or "").lower()
        if persona_decision == "reject":
            print("\nPersona stage rejected — stopping pipeline.")
            return 0

        persona_paths = persona_result.get("written_paths") or []
        print(f"\nPersona artifacts: {persona_paths or '(none)'}")

    # ── Stage 3: Style guide research ─────────────────────────────
    if args.style and args.persona:
        style_input = StyleGuideResearchInput(
            company_id=args.company_id,
            company_name=args.company_name,
            domain=args.domain,
            company_slug=slug,
            company_context_path=company_output_path,
            persona_paths=persona_paths,
        )

        print("\n" + "=" * 60)
        print("  STAGE 3: Style Guide Research")
        print("=" * 60)

        style_result = run_graph_with_approval(
            build_graph_fn=build_style_graph,
            initial_state={"input": style_input, "auto_approve": args.auto_approve},
            thread_id=f"cli-pipeline-style-{slug}",
        )

        style_decision = (style_result.get("approval_decision") or "").lower()
        if style_decision == "reject":
            print("\nStyle guide stage rejected.")
        else:
            style_paths = style_result.get("written_paths") or []
            print(f"\nStyle guide artifacts: {style_paths or '(none)'}")

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
