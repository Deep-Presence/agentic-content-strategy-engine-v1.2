import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Allow running this script from any working directory by ensuring the project root
# is on the Python path (so `import core.*` works).
_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.research.graphs.company_research import build_graph
from core.models.artifacts import CompanyResearchInput


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Company Research DeepAgent + write the Company Context artifact.",
    )
    p.add_argument("--company-name", required=True, help="Company name (used for artifact slug)")
    p.add_argument("--domain", default=None, help="Company domain (optional)")
    p.add_argument("--company-id", default=None, help="Supabase company UUID (optional; enables mirroring)")
    p.add_argument("--seed-url", action="append", default=[], help="Seed URL (repeatable)")
    p.add_argument(
        "--internal-source",
        action="append",
        default=[],
        help="Path to internal transcript/notes (repeatable; absolute paths recommended)",
    )
    p.add_argument("--language", default="en", help="Language code (default: en)")
    p.add_argument("--region", default=None, help="Region (optional)")
    p.add_argument("--constraints", default=None, help="Additional constraints (optional)")
    p.add_argument(
        "--no-print",
        action="store_true",
        help="Don't print the final Markdown to stdout (still writes artifact).",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing artifact file if it already exists.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    graph = build_graph()
    inp = CompanyResearchInput(
        company_id=args.company_id,
        company_name=args.company_name,
        domain=args.domain,
        seed_urls=args.seed_url,
        internal_sources=args.internal_source,
        language=args.language,
        region=args.region,
        additional_constraints=args.constraints,
    )

    out = graph.invoke({"input": inp, "overwrite": args.overwrite})

    if not args.no_print:
        print("\n===== RESEARCH RESPONSE (final markdown) =====\n")
        print(out.get("artifact_md", ""))

    print("\n===== ARTIFACT WRITTEN TO =====\n")
    print(out.get("output_path", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
