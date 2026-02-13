from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import List, Optional

from core.gap_analysis.steps.s1_embed_assets import embed_company_assets
from core.shared_tools.chroma_client import collection_exists, get_all_embeddings

logger = logging.getLogger(__name__)
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
    GapReport,
    GeneratedQuery,
    PlatformResult,
    SemanticUnit,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/


def _company_slug(input_data: GapAnalysisInput) -> str:
    return input_data.company_slug or re.sub(
        r"[^a-z0-9]+", "-", input_data.company_name.lower()
    ).strip("-")


def _artifact_dir(company_slug: str) -> Path:
    path = _PROJECT_ROOT / "artifacts" / "gap_analysis" / company_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_json_list(path: Path, model_cls):
    if not path.exists():
        raise RuntimeError(f"Missing artifact: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [model_cls(**item) for item in data]


def run_gap_analysis(
    input_data: GapAnalysisInput,
    skip_steps: Optional[List[int]] = None,
) -> GapReport:
    skip_steps = skip_steps or []
    slug = _company_slug(input_data)
    artifact_dir = _artifact_dir(slug)

    # Step 1: embed company assets
    if 1 in skip_steps:
        company_units = _load_json_list(
            artifact_dir / "company_embeddings.json", SemanticUnit
        )
        # Hydrate embeddings from ChromaDB if JSON has no raw vectors
        if not any(u.embedding for u in company_units):
            if collection_exists(slug):
                embedding_map = get_all_embeddings(slug)
                hydrated = 0
                for unit in company_units:
                    if unit.unit_id in embedding_map:
                        unit.embedding = embedding_map[unit.unit_id]
                        hydrated += 1
                logger.info(
                    "Hydrated %d/%d unit embeddings from ChromaDB.",
                    hydrated,
                    len(company_units),
                )
            else:
                logger.warning(
                    "No ChromaDB collection found for '%s' and JSON has no embeddings. "
                    "S6/S7 may produce degraded results.",
                    slug,
                )
    else:
        company_units = embed_company_assets(input_data)

    # Step 2: generate queries
    if 2 in skip_steps:
        queries = _load_json_list(artifact_dir / "queries.json", GeneratedQuery)
    else:
        queries = generate_queries(input_data)
        (artifact_dir / "queries.json").write_text(
            json.dumps([q.model_dump(mode="json") for q in queries], indent=2, default=str),
            encoding="utf-8",
        )

    # Step 3: search platforms
    if 3 in skip_steps:
        platform_results = []
        for name in input_data.platforms:
            path = artifact_dir / "platform_results" / f"{name}_results.jsonl"
            if not path.exists():
                continue
            items = [
                PlatformResult(**json.loads(line))
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            platform_results.extend(items)
    else:
        platform_results = asyncio.run(
            search_platforms(queries, input_data.platforms)
        )
        save_platform_results(platform_results, artifact_dir / "platform_results")

    # Step 4: enrich citations
    if 4 in skip_steps:
        enriched = _load_json_list(
            artifact_dir / "enriched_citations.json", EnrichedCitation
        )
    else:
        query_lookup = {q.query_id: q for q in queries}
        enriched = enrich_citations(platform_results, query_lookup=query_lookup)
        save_enriched_citations(enriched, artifact_dir / "enriched_citations.json")

    # Step 5: embed content
    if 5 in skip_steps:
        queries = _load_json_list(
            artifact_dir / "embeddings" / "queries_with_embeddings.json",
            GeneratedQuery,
        )
        enriched = _load_json_list(
            artifact_dir / "embeddings" / "citations_with_embeddings.json",
            EnrichedCitation,
        )
    else:
        queries, enriched = embed_all(queries, enriched, company_slug=slug)
        save_embeddings(queries, enriched, artifact_dir / "embeddings")

    # Step 6: analyze
    if 6 in skip_steps:
        analysis = AnalysisResult(
            **json.loads((artifact_dir / "analysis.json").read_text(encoding="utf-8"))
        )
    else:
        analysis = compute_gap_analysis(queries, company_units, enriched)
        (artifact_dir / "analysis.json").write_text(
            json.dumps(analysis.model_dump(mode="json"), indent=2, default=str), encoding="utf-8"
        )

    # Step 7: visualize
    if 7 in skip_steps:
        visualization_paths = json.loads(
            (artifact_dir / "visualizations" / "visualization_paths.json").read_text(
                encoding="utf-8"
            )
        )
    else:
        visualization_paths = generate_visualizations(
            queries, enriched, company_units, analysis, artifact_dir / "visualizations"
        )
        (artifact_dir / "visualizations" / "visualization_paths.json").write_text(
            json.dumps(visualization_paths, indent=2), encoding="utf-8"
        )

    # Step 8: report
    if 8 in skip_steps:
        report = GapReport(
            report_md=(artifact_dir / "gap_report.md").read_text(encoding="utf-8"),
            report_json=json.loads(
                (artifact_dir / "gap_report.json").read_text(encoding="utf-8")
            ),
            generation_spec_md=(artifact_dir / "generation_spec.md").read_text(
                encoding="utf-8"
            ),
            generation_spec_json=json.loads(
                (artifact_dir / "generation_spec.json").read_text(encoding="utf-8")
            ),
            visualization_paths=list(visualization_paths.values())
            if isinstance(visualization_paths, dict)
            else visualization_paths,
        )
    else:
        report = generate_gap_report(analysis, queries, enriched)
        report.visualization_paths = list(visualization_paths.values())
        save_report(report, artifact_dir)

    return report
