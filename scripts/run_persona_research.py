import argparse
import sys
from pathlib import Path

# Allow running this script from any working directory by ensuring the project root
# is on the Python path (so `import core.*` works).
_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.research.graphs.persona_research import build_graph
from core.models.personas import PersonaResearchInput


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Persona Research DeepAgent + write persona artifacts.",
    )
    p.add_argument("--company-name", required=True, help="Company name")
    p.add_argument("--domain", default=None, help="Company domain (optional)")
    p.add_argument("--company-id", default=None, help="Supabase company UUID (optional; enables mirroring)")
    p.add_argument("--company-slug", default=None, help="Company slug (optional; derived from company-name if omitted)")
    p.add_argument(
        "--company-context-path",
        default=None,
        help="DeepAgents path to the company context md (e.g. /artifacts/company_context/acme.md). Derived from slug if omitted.",
    )
    p.add_argument(
        "--internal-source",
        action="append",
        default=[],
        help="Path to internal transcript/notes (repeatable)",
    )
    p.add_argument("--max-personas", type=int, default=3, help="Max personas to generate (1-3, default: 3)")
    p.add_argument("--language", default="en", help="Language code (default: en)")
    p.add_argument("--region", default=None, help="Region (optional)")
    p.add_argument("--constraints", default=None, help="Additional constraints (optional)")
    p.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip the human approval gate (for testing).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    graph = build_graph()
    inp = PersonaResearchInput(
        company_id=args.company_id,
        company_name=args.company_name,
        domain=args.domain,
        company_slug=args.company_slug,
        company_context_path=args.company_context_path,
        internal_sources=args.internal_source,
        max_personas=args.max_personas,
        language=args.language,
        region=args.region,
        additional_constraints=args.constraints,
    )

    out = graph.invoke({"input": inp, "auto_approve": args.auto_approve})

    agent_result = out.get("agent_result", {})
    written_paths = out.get("written_paths") or agent_result.get("written_paths") or []
    notes = agent_result.get("notes", "")

    print("\n===== PERSONA AGENT NOTES =====\n")
    print(notes)
    print("\n===== ARTIFACTS WRITTEN TO =====\n")
    for p in written_paths:
        print(f"  {p}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
