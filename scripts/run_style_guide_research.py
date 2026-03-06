import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.research.graphs.style_guide import build_graph
from core.models.style_guide import StyleGuideResearchInput
from scripts._cli_approval import run_graph_with_approval


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Style Guide Research DeepAgent + write the style guide artifact.",
    )
    p.add_argument("--company-name", required=True, help="Company name")
    p.add_argument("--domain", default=None, help="Company domain (optional)")
    p.add_argument("--company-id", default=None, help="Supabase company UUID (optional; enables mirroring)")
    p.add_argument("--company-slug", default=None, help="Company slug (optional; derived from company-name if omitted)")
    p.add_argument(
        "--company-context-path",
        default=None,
        help="DeepAgents path to the company context md (e.g. /artifacts/company_context/acme.md)",
    )
    p.add_argument(
        "--persona-path",
        action="append",
        default=[],
        help="Persona artifact path (repeatable)",
    )
    p.add_argument(
        "--internal-source",
        action="append",
        default=[],
        help="Path to internal transcript/notes (repeatable)",
    )
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

    inp = StyleGuideResearchInput(
        company_id=args.company_id,
        company_name=args.company_name,
        domain=args.domain,
        company_slug=args.company_slug,
        company_context_path=args.company_context_path,
        persona_paths=args.persona_path,
        internal_sources=args.internal_source,
        language=args.language,
        region=args.region,
        additional_constraints=args.constraints,
    )

    slug = inp.company_slug or inp.company_name.lower().replace(" ", "-")
    initial_state = {"input": inp, "auto_approve": args.auto_approve}

    out = run_graph_with_approval(
        build_graph_fn=build_graph,
        initial_state=initial_state,
        thread_id=f"cli-style-{slug}",
    )

    agent_result = out.get("agent_result", {})
    written_paths = out.get("written_paths") or agent_result.get("written_paths") or []
    notes = agent_result.get("notes", "")

    print("\n===== STYLE GUIDE AGENT NOTES =====\n")
    print(notes)
    print("\n===== ARTIFACTS WRITTEN TO =====\n")
    for p in written_paths:
        print(f"  {p}")

    if not written_paths:
        decision = (out.get("approval_decision") or "").lower()
        if decision == "reject":
            print("  (rejected — no artifacts written)")
        else:
            print("  (none — check agent output for errors)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
