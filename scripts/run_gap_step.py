#!/usr/bin/env python3
"""
Run a single step of the gap analysis pipeline independently.

Use this to run each step one-by-one, inspect the output, and debug quality issues.

Example (run Step 1 — crawl & embed Ramp's website):
  cd content-strategy-engine && python scripts/run_gap_step.py --step 1 \
    --company-name "Ramp" --domain ramp.com

Example (run Step 2 — requires Step 1 output; Step 2 uses company context):
  python scripts/run_gap_step.py --step 2 --company-name "Ramp" --domain ramp.com \
    --company-context-path artifacts/company_context/ramp.md \
    --persona-path artifacts/personas/ramp__persona-icp.md

Example (run Step 5 — re-embed; loads queries + enriched citations from disk):
  python scripts/run_gap_step.py --step 5 --company-slug ramp

Steps:
  1 — Crawl company website, extract text, chunk, embed → company_embeddings.json
  2 — Generate buyer queries (3-pass) → queries.json
  3 — Search AI platforms (Perplexity, OpenAI, etc.) → platform_results/*.jsonl
  4 — Enrich citations (fetch cited pages, extract content) → enriched_citations.json
  5 — Embed queries + citation paragraphs → embeddings/*.json
  6 — Compute gap analysis (SPA, gaps, centroids) → analysis.json
  7 — Generate visualizations → visualizations/*.html
  8 — Generate gap report + generation spec → gap_report.*, generation_spec.*
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.gap_analysis.steps.s1_embed_assets import embed_company_assets
from core.gap_analysis.steps.s2_generate_queries import generate_queries
from core.gap_analysis.steps.s3_search_platforms import (
    save_platform_results,
    search_platforms,
)
from core.gap_analysis.steps.s4_enrich_citations import (
    enrich_citations,
    save_enriched_citations,
)
from core.gap_analysis.steps.s5_embed_content import embed_all, save_embeddings
from core.gap_analysis.steps.s6_analyze import compute_gap_analysis
from core.gap_analysis.steps.s7_visualize import generate_visualizations
from core.gap_analysis.steps.s8_generate_report import generate_gap_report, save_report
from core.models.gap_analysis import (
    AnalysisResult,
    EnrichedCitation,
    GapAnalysisInput,
    GeneratedQuery,
    PlatformResult,
    SemanticUnit,
)
from core.shared_tools.vector_store import async_collection_exists, async_get_all_embeddings


def _company_slug(args: argparse.Namespace) -> str:
    if args.company_slug:
        return args.company_slug
    if args.company_name:
        return re.sub(r"[^a-z0-9]+", "-", args.company_name.lower()).strip("-")
    raise ValueError("Provide --company-name or --company-slug")


def _artifact_dir(slug: str) -> Path:
    path = _PROJECT_ROOT / "artifacts" / "gap_analysis" / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_json_list(path: Path, model_cls):
    if not path.exists():
        raise RuntimeError(f"Missing artifact: {path}\nRun earlier steps first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [model_cls(**item) for item in data]


def _build_input(args: argparse.Namespace) -> GapAnalysisInput:
    platforms = [p.strip() for p in (args.platforms or "perplexity,openai,gemini,claude").split(",") if p.strip()]
    seed_urls = []
    if args.seed_url:
        seed_urls = [u.strip() for u in args.seed_url if u.strip()]
    kwargs = dict(
        company_id=args.company_id,
        company_name=args.company_name or "Unknown",
        domain=args.domain,
        company_slug=args.company_slug,
        seed_urls=seed_urls,
        company_context_path=args.company_context_path,
        persona_paths=args.persona_path or [],
        style_guide_path=args.style_guide_path,
        max_queries=args.max_queries or 150,
        platforms=platforms,
    )
    if getattr(args, "max_crawl_pages", None) is not None:
        kwargs["max_crawl_pages"] = args.max_crawl_pages
    if getattr(args, "max_crawl_depth", None) is not None:
        kwargs["max_crawl_depth"] = args.max_crawl_depth
    return GapAnalysisInput(**kwargs)


def _load_company_units_with_embeddings(artifact_dir: Path) -> list[SemanticUnit]:
    """Load company units from JSON and hydrate embeddings from pgvector."""
    company_units = _load_json_list(artifact_dir / "company_embeddings.json", SemanticUnit)
    if not any(u.embedding for u in company_units):
        slug = artifact_dir.name
        if asyncio.run(async_collection_exists(slug)):
            embedding_map = asyncio.run(async_get_all_embeddings(slug))
            hydrated = 0
            for unit in company_units:
                if unit.unit_id in embedding_map:
                    unit.embedding = embedding_map[unit.unit_id]
                    hydrated += 1
            print(f"  Hydrated {hydrated}/{len(company_units)} unit embeddings from pgvector.")
        else:
            print(f"  WARNING: No pgvector collection found for '{slug}' and JSON has no embeddings.")
    return company_units


def run_step_1(args: argparse.Namespace, artifact_dir: Path, input_data: GapAnalysisInput) -> None:
    """Crawl company website, extract text, chunk, embed."""
    if not input_data.domain:
        raise ValueError("Step 1 requires --domain (e.g. ramp.com)")
    print("Step 1: Crawling & embedding company website...")
    units = asyncio.run(embed_company_assets(input_data))
    urls = {str(u.url) for u in units if u.url}
    print(f"\n  Output: {artifact_dir / 'company_embeddings.json'}")
    print(f"  Semantic units: {len(units)}")
    print(f"  Unique pages crawled: {len(urls)}")
    if urls:
        print("  Sample URLs:")
        for u in list(urls)[:5]:
            print(f"    - {u}")


def run_step_2(args: argparse.Namespace, artifact_dir: Path, input_data: GapAnalysisInput) -> None:
    """Generate buyer queries (3-pass)."""
    print("Step 2: Generating buyer queries...")
    queries = asyncio.run(generate_queries(input_data))
    (artifact_dir / "queries.json").write_text(
        json.dumps([q.model_dump(mode="json") for q in queries], indent=2, default=str),
        encoding="utf-8",
    )
    clusters = {}
    for q in queries:
        clusters[q.cluster_name] = clusters.get(q.cluster_name, 0) + 1
    print(f"\n  Output: {artifact_dir / 'queries.json'}")
    print(f"  Total queries: {len(queries)}")
    print(f"  Clusters: {dict(clusters)}")


def run_step_3(args: argparse.Namespace, artifact_dir: Path, input_data: GapAnalysisInput) -> None:
    """Search AI platforms."""
    queries = _load_json_list(artifact_dir / "queries.json", GeneratedQuery)
    print("Step 3: Searching AI platforms...")
    platform_results = asyncio.run(search_platforms(queries, input_data.platforms))
    out_dir = artifact_dir / "platform_results"
    save_platform_results(platform_results, out_dir)
    by_engine = {}
    for r in platform_results:
        by_engine[r.engine] = by_engine.get(r.engine, 0) + 1
    print(f"\n  Output: {out_dir}/*.jsonl")
    print(f"  Total results: {len(platform_results)}")
    print(f"  By engine: {dict(by_engine)}")


def run_step_4(args: argparse.Namespace, artifact_dir: Path, input_data: GapAnalysisInput) -> None:
    """Enrich citations (fetch cited pages, extract content)."""
    queries = _load_json_list(artifact_dir / "queries.json", GeneratedQuery)
    query_lookup = {q.query_id: q for q in queries}
    platform_results = []
    for name in input_data.platforms:
        path = artifact_dir / "platform_results" / f"{name}_results.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    platform_results.append(PlatformResult(**json.loads(line)))
    print("Step 4: Enriching citations (fetching cited pages)...")
    enriched = asyncio.run(enrich_citations(platform_results, query_lookup=query_lookup))
    out_path = artifact_dir / "enriched_citations.json"
    save_enriched_citations(enriched, out_path)
    domains = {}
    for c in enriched:
        d = c.domain or "unknown"
        domains[d] = domains.get(d, 0) + 1
    print(f"\n  Output: {out_path}")
    print(f"  Enriched citations: {len(enriched)}")
    print(f"  Top domains: {dict(sorted(domains.items(), key=lambda x: -x[1])[:5])}")


def run_step_5(args: argparse.Namespace, artifact_dir: Path, input_data: GapAnalysisInput) -> None:
    """Embed queries + citation paragraphs."""
    queries = _load_json_list(artifact_dir / "queries.json", GeneratedQuery)
    enriched = _load_json_list(artifact_dir / "enriched_citations.json", EnrichedCitation)
    company_slug = artifact_dir.name
    print("Step 5: Embedding queries and citation paragraphs...")
    queries, enriched = asyncio.run(embed_all(queries, enriched, company_slug=company_slug))
    out_dir = artifact_dir / "embeddings"
    save_embeddings(queries, enriched, out_dir)
    with_emb = sum(1 for c in enriched if c.best_paragraphs)
    print(f"\n  Output: {out_dir}/queries_with_embeddings.json, citations_with_embeddings.json")
    print(f"  Queries with embeddings: {sum(1 for q in queries if q.embedding)}")
    print(f"  Citations with best_paragraphs: {with_emb} / {len(enriched)}")


def run_step_6(args: argparse.Namespace, artifact_dir: Path, input_data: GapAnalysisInput) -> None:
    """Compute gap analysis."""
    company_units = _load_company_units_with_embeddings(artifact_dir)
    queries = _load_json_list(
        artifact_dir / "embeddings" / "queries_with_embeddings.json",
        GeneratedQuery,
    )
    enriched = _load_json_list(
        artifact_dir / "embeddings" / "citations_with_embeddings.json",
        EnrichedCitation,
    )
    print("Step 6: Computing gap analysis (SPA, gaps, centroids)...")
    analysis = compute_gap_analysis(queries, company_units, enriched)
    out_path = artifact_dir / "analysis.json"
    out_path.write_text(
        json.dumps(analysis.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    prox = analysis.proximity_stats
    print(f"\n  Output: {out_path}")
    print(f"  Mean citation similarity: {prox.get('citation_similarity_mean', 0):.4f}")
    print(f"  Mean company similarity: {prox.get('company_similarity_mean', 0):.4f}")
    print(f"  Gaps computed: {len(analysis.gaps)}")
    print(f"  SPA results: {len(analysis.spa_results)}")


def run_step_7(args: argparse.Namespace, artifact_dir: Path, input_data: GapAnalysisInput) -> None:
    """Generate visualizations."""
    company_units = _load_company_units_with_embeddings(artifact_dir)
    queries = _load_json_list(
        artifact_dir / "embeddings" / "queries_with_embeddings.json",
        GeneratedQuery,
    )
    enriched = _load_json_list(
        artifact_dir / "embeddings" / "citations_with_embeddings.json",
        EnrichedCitation,
    )
    analysis = AnalysisResult(
        **json.loads((artifact_dir / "analysis.json").read_text(encoding="utf-8"))
    )
    print("Step 7: Generating visualizations...")
    out_dir = artifact_dir / "visualizations"
    paths = generate_visualizations(queries, enriched, company_units, analysis, out_dir)
    (out_dir / "visualization_paths.json").write_text(
        json.dumps(paths, indent=2), encoding="utf-8"
    )
    print(f"\n  Output: {out_dir}/")
    for name, p in paths.items():
        print(f"    - {name}: {p}")


def run_step_8(args: argparse.Namespace, artifact_dir: Path, input_data: GapAnalysisInput) -> None:
    """Generate gap report + generation spec."""
    analysis = AnalysisResult(
        **json.loads((artifact_dir / "analysis.json").read_text(encoding="utf-8"))
    )
    queries = _load_json_list(
        artifact_dir / "embeddings" / "queries_with_embeddings.json",
        GeneratedQuery,
    )
    enriched = _load_json_list(
        artifact_dir / "embeddings" / "citations_with_embeddings.json",
        EnrichedCitation,
    )
    viz_paths = json.loads(
        (artifact_dir / "visualizations" / "visualization_paths.json").read_text(encoding="utf-8")
    )
    print("Step 8: Generating gap report + generation spec...")
    report = asyncio.run(generate_gap_report(analysis, queries, enriched))
    report.visualization_paths = list(viz_paths.values()) if isinstance(viz_paths, dict) else viz_paths
    save_report(report, artifact_dir)
    print(f"\n  Output: {artifact_dir / 'gap_report.md'}")
    print(f"         {artifact_dir / 'generation_spec.md'}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run a single step of the gap analysis pipeline independently.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--step", type=int, required=True, choices=range(1, 9), metavar="1-8")
    p.add_argument("--company-name", help="Company name (e.g. Ramp)")
    p.add_argument("--company-slug", help="Artifact dir slug (e.g. ramp). Default: derived from company-name")
    p.add_argument("--domain", help="Company domain (e.g. ramp.com)")
    p.add_argument("--company-id", default=None)
    p.add_argument("--company-context-path", default=None)
    p.add_argument("--persona-path", action="append", default=[], dest="persona_path")
    p.add_argument("--style-guide-path", default=None)
    p.add_argument("--seed-url", action="append", default=[], dest="seed_url")
    p.add_argument("--max-queries", type=int, default=150)
    p.add_argument("--max-crawl-pages", type=int, default=None, help="Max pages to crawl (default: from settings)")
    p.add_argument("--max-crawl-depth", type=int, default=None, help="Max BFS crawl depth (default: from settings)")
    p.add_argument("--platforms", default="perplexity,openai,gemini,claude")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    slug = _company_slug(args)
    artifact_dir = _artifact_dir(slug)
    input_data = _build_input(args)

    print(f"{'='*60}")
    print(f"Gap Analysis — Step {args.step} (company: {slug})")
    print(f"{'='*60}")

    runners = {
        1: run_step_1,
        2: run_step_2,
        3: run_step_3,
        4: run_step_4,
        5: run_step_5,
        6: run_step_6,
        7: run_step_7,
        8: run_step_8,
    }
    runners[args.step](args, artifact_dir, input_data)

    print(f"\n{'='*60}")
    print("Done.")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
