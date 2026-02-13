#!/usr/bin/env python3
"""
Run the content-strategy-engine pipeline: company_research -> persona_research -> style_guide.

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

from core.research.graphs.pipeline import run_pipeline
from core.models.artifacts import CompanyResearchInput
from core.models.personas import PersonaResearchInput
from core.models.style_guide import StyleGuideResearchInput


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

    company_input = CompanyResearchInput(
        company_id=args.company_id,
        company_name=args.company_name,
        domain=args.domain,
        seed_urls=args.seed_url or [],
        internal_sources=args.internal_source or [],
        language=args.language,
    )

    persona_input = None
    if args.persona:
        persona_input = PersonaResearchInput(
            company_id=args.company_id,
            company_name=args.company_name,
            domain=args.domain,
            max_personas=min(3, max(1, args.max_personas)),
        )

    style_input = None
    if args.style and persona_input:
        style_input = StyleGuideResearchInput(
            company_id=args.company_id,
            company_name=args.company_name,
            domain=args.domain,
        )

    result = run_pipeline(
        company_input=company_input,
        persona_input=persona_input,
        style_input=style_input,
        auto_approve=args.auto_approve,
    )

    stage = result.get("stage", "?")
    if result.get("status") == "interrupt":
        print("\n" + "=" * 60)
        print(f"INTERRUPT at stage: {stage}")
        print("=" * 60)
        values = result.get("values", {})
        print("\nDraft(s) to review:")
        if "draft_path" in values:
            print(f"  Company: {values['draft_path']}")
        if "draft_paths" in values:
            for p in values["draft_paths"]:
                print(f"  - {p}")
        print(f"\nNotes: {values.get('notes', '')}")
        print("\nTo resume: use your frontend/API to call the graph with:")
        print('  {"approval_decision": "approve" | "revise" | "reject", "revision_note": "..."}')
        print("=" * 60)
        return 0

    print("\n" + "=" * 60)
    print(f"Pipeline complete: {stage}")
    print("=" * 60)
    if result.get("company"):
        print(f"Company output: {result['company'].get('output_path', 'N/A')}")
    if result.get("personas"):
        print(f"Persona paths: {result['personas'].get('written_paths', [])}")
    if result.get("style"):
        print(f"Style paths: {result['style'].get('written_paths', [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
