"""DbGapDataService — Postgres-backed implementation of GapDataServiceProtocol.

Reads gap analysis data from SQL via repositories instead of parsing JSON files.
Embedding projections remain filesystem-backed (pre-computed s7 blobs).
"""
from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import HTTPException

from api.schemas.brand_data import SPATrendResponse, SPATrendPoint
from api.schemas.content_data import EmbeddingProjectionResponse
from api.schemas.gap_data import (
    ClusterListResponse,
    ClusterPatternRow,
    ClusterPerformanceRow,
    ClusterSpecResponse,
    GapClassificationCounts,
    GapSummaryResponse,
    HeatmapCluster,
    HeatmapQuery,
    HeatmapResponse,
    PlatformListResponse,
    PlatformSummaryResponse,
    ProximityStats,
    QueryContentBrief,
    QueryExemplar,
    QueryListResponse,
    QueryRow,
    SignalAverageRow,
    SignalAveragesResponse,
    SignalCorrelationRow,
    SPAScore,
)
from core.db.enums import PipelineStatus, PipelineType
from core.db.repositories.gap_analysis_repo import GapAnalysisRepository
from core.db.repositories.pipeline_repo import PipelineRepository
from core.db.repositories.platform_repo import PlatformRepository
from core.db.repositories.signal_repo import SignalRepository

# Signal definition table — same as gap_data_service.py
_SIGNAL_DEFS: List[Dict[str, str]] = [
    {"field": "word_count", "name": "Word Count", "category": "Text Composition", "unit": "words"},
    {"field": "sentence_count", "name": "Sentence Count", "category": "Text Composition", "unit": "count"},
    {"field": "paragraph_count", "name": "Paragraph Count", "category": "Text Composition", "unit": "count"},
    {"field": "avg_paragraph_length", "name": "Avg Paragraph Length", "category": "Text Composition", "unit": "words"},
    {"field": "reading_level", "name": "Reading Level", "category": "Text Composition", "unit": "grade level"},
    {"field": "self_contained_ratio", "name": "Self-Contained Ratio", "category": "Text Composition", "unit": "%"},
    {"field": "h1_count", "name": "H1 Count", "category": "Structural Elements", "unit": "count"},
    {"field": "h2_count", "name": "H2 Count", "category": "Structural Elements", "unit": "count"},
    {"field": "h3_count", "name": "H3 Count", "category": "Structural Elements", "unit": "count"},
    {"field": "h4_count", "name": "H4 Count", "category": "Structural Elements", "unit": "count"},
    {"field": "list_block_count", "name": "List Count", "category": "Structural Elements", "unit": "count"},
    {"field": "ordered_list_count", "name": "Ordered List Count", "category": "Structural Elements", "unit": "count"},
    {"field": "table_count", "name": "Table Count", "category": "Structural Elements", "unit": "count"},
    {"field": "code_block_count", "name": "Code Block Count", "category": "Structural Elements", "unit": "count"},
    {"field": "has_faq_section", "name": "FAQ Section", "category": "Content Patterns", "unit": "%"},
    {"field": "has_definition_opening", "name": "Definition Opening", "category": "Content Patterns", "unit": "%"},
    {"field": "has_key_takeaways", "name": "Key Takeaways", "category": "Content Patterns", "unit": "%"},
    {"field": "has_comparison_table", "name": "Comparison Table", "category": "Content Patterns", "unit": "%"},
    {"field": "has_step_by_step", "name": "Step-by-Step", "category": "Content Patterns", "unit": "%"},
    {"field": "has_research_refs", "name": "Research References", "category": "Content Patterns", "unit": "%"},
    {"field": "has_expert_quotes", "name": "Expert Quotes", "category": "Content Patterns", "unit": "%"},
    {"field": "data_point_count", "name": "Data Point Count", "category": "Factual Density", "unit": "data points"},
    {"field": "citation_density", "name": "Citation Density", "category": "Factual Density", "unit": "per word"},
    {"field": "named_entity_density", "name": "Named Entity Density", "category": "Factual Density", "unit": "per word"},
]

_ENGINE_DISPLAY: Dict[str, str] = {
    "openai": "ChatGPT", "claude": "Claude",
    "perplexity": "Perplexity", "gemini": "Gemini",
}
_ENGINE_KEYS: Dict[str, str] = {
    "openai": "chatgpt", "claude": "claude",
    "perplexity": "perplexity", "gemini": "gemini",
}


def _map_engine_display(engine: Optional[str]) -> str:
    if engine is None:
        return "Unknown"
    return _ENGINE_DISPLAY.get(engine, engine.title())


class DbGapDataService:
    """Postgres-backed gap data service.

    Uses SQL for heavy aggregation (signal averages, correlations, cluster
    patterns). Delegates embedding projections to filesystem.
    """

    def __init__(
        self,
        gap_repo: GapAnalysisRepository,
        pipeline_repo: PipelineRepository,
        signal_repo: SignalRepository,
        platform_repo: PlatformRepository,
        artifacts_root: Path,
    ) -> None:
        self._gap_repo = gap_repo
        self._pipeline_repo = pipeline_repo
        self._signal_repo = signal_repo
        self._platform_repo = platform_repo
        self._artifacts_root = artifacts_root

    async def _resolve_run_id(self, effective_slug: str) -> Any:
        """Resolve effective_slug → latest completed gap_analysis run_id."""
        run = await self._pipeline_repo.get_latest_completed(
            effective_slug, PipelineType.gap_analysis,
        )
        if run is None:
            raise HTTPException(
                404, f"No completed gap analysis found for '{effective_slug}'",
            )
        return run.id

    async def get_summary(self, effective_slug: str) -> GapSummaryResponse:
        run_id = await self._resolve_run_id(effective_slug)

        # Parallel-ish fetches (serial in practice, but fast in SQL)
        spa_results = await self._gap_repo.get_spa_results(run_id)
        classification_counts = await self._gap_repo.get_classification_counts(run_id)
        cluster_specs = await self._gap_repo.get_cluster_specs(run_id)
        centroid_results = await self._gap_repo.get_centroid_results(run_id)
        total_gaps = await self._gap_repo.count_gaps_by_run(run_id)

        # SPA score — find the "all" cluster result
        spa = SPAScore()
        for sr in spa_results:
            cname = sr.cluster_name or ""
            if cname == "all" or cname == "":
                spa = SPAScore(
                    t_stat=sr.t_stat or 0.0,
                    p_value=sr.p_value or 0.0,
                    effect=sr.effect or "unknown",
                    mean_citation_similarity=sr.mean_citation_similarity or 0.0,
                    mean_company_similarity=sr.mean_company_similarity or 0.0,
                )
                break

        # Classification counts
        counts = GapClassificationCounts(
            significant_gap=classification_counts.get("significant_gap", 0),
            gap_to_close=classification_counts.get("gap_to_close", 0),
            roughly_equal=classification_counts.get("roughly_equal", 0),
            company_wins=classification_counts.get("company_wins", 0),
        )

        # Cluster performance from specs + centroid results
        centroid_lookup = {c.cluster_name: c for c in centroid_results}
        cluster_perf: List[ClusterPerformanceRow] = []
        for spec in cluster_specs:
            cluster_perf.append(
                ClusterPerformanceRow(
                    cluster_id=spec.cluster_id,
                    cluster_name=spec.cluster_name,
                    query_count=spec.query_count,
                    citation_count=spec.total_citations_analyzed,
                    avg_gap=0.0,
                    avg_citation_sim=0.0,
                    avg_company_sim=0.0,
                    structural_rates=spec.structural_rates or {},
                )
            )

        # Get pipeline run for summary/executive_summary
        run = await self._pipeline_repo.get_by_id(run_id)
        run_summary = run.summary or {} if run else {}

        return GapSummaryResponse(
            spa_score=spa,
            proximity_stats=ProximityStats(),
            classification_counts=counts,
            cluster_performance=cluster_perf,
            total_queries=total_gaps,
            total_citations=run_summary.get("total_citations", 0),
            average_gap=run_summary.get("avg_gap", 0.0),
            executive_summary=run_summary.get("executive_summary", ""),
            recommendations=run_summary.get("recommendations", []),
        )

    async def get_queries(
        self,
        effective_slug: str,
        *,
        cluster: Optional[str] = None,
        classification: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "gap_score",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 15,
    ) -> QueryListResponse:
        run_id = await self._resolve_run_id(effective_slug)

        # Map sort_by from frontend field to DB column
        db_sort = "gap" if sort_by == "gap_score" else sort_by

        result = await self._gap_repo.get_gaps_paginated(
            run_id,
            cluster=cluster,
            classification=classification,
            search=search,
            sort_by=db_sort,
            sort_dir=sort_dir,
            page=page,
            page_size=page_size,
        )

        rows: List[QueryRow] = []
        for gap in result["items"]:
            exemplars: List[QueryExemplar] = []
            if hasattr(gap, "exemplars") and gap.exemplars:
                for ex in gap.exemplars[:3]:
                    exemplars.append(QueryExemplar(
                        url=ex.url,
                        domain=ex.domain or "",
                        similarity=ex.similarity,
                        snippet=ex.snippet or "",
                    ))

            brief = None
            if gap.content_brief:
                brief = QueryContentBrief(
                    title=gap.content_brief.get("title", ""),
                    target_word_count=gap.content_brief.get("target_word_count", {}),
                    patterns=gap.content_brief.get("patterns", []),
                )

            rows.append(QueryRow(
                query_id=gap.query_id,
                query_text=gap.query_text,
                cluster_name=gap.cluster_name,
                cluster_id=gap.cluster_id,
                gap_score=gap.gap or 0.0,
                classification=str(gap.classification.value) if gap.classification else "roughly_equal",
                best_company_similarity=gap.best_company_similarity or 0.0,
                avg_citation_similarity=gap.avg_citation_similarity or 0.0,
                top_exemplars=exemplars,
                content_brief=brief,
                platforms={},
            ))

        return QueryListResponse(
            queries=rows,
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            total_pages=result["total_pages"],
        )

    async def get_clusters(self, effective_slug: str) -> ClusterListResponse:
        run_id = await self._resolve_run_id(effective_slug)
        specs = await self._gap_repo.get_cluster_specs(run_id)
        centroids = await self._gap_repo.get_centroid_results(run_id)
        centroid_lookup = {c.cluster_name: c.distance for c in centroids}

        cluster_responses: List[ClusterSpecResponse] = []
        for spec in specs:
            cluster_responses.append(ClusterSpecResponse(
                cluster_id=spec.cluster_id or "",
                cluster_name=spec.cluster_name,
                query_count=spec.query_count,
                total_citations_analyzed=spec.total_citations_analyzed,
                word_count_range={"min": spec.word_count_min, "max": spec.word_count_max},
                avg_word_count=spec.avg_word_count,
                dominant_content_type=spec.dominant_content_type or "article",
                dominant_authority_type=spec.dominant_authority_type or "mixed",
                structural_rates=spec.structural_rates or {},
                centroid_distance=centroid_lookup.get(spec.cluster_name, 0.0),
            ))

        return ClusterListResponse(clusters=cluster_responses)

    async def get_signals(self, effective_slug: str) -> SignalAveragesResponse:
        run_id = await self._resolve_run_id(effective_slug)

        signal_avgs = await self._signal_repo.get_signal_averages(run_id)
        signal_corrs = await self._signal_repo.get_signal_correlations(run_id)
        cluster_patterns = await self._signal_repo.get_cluster_patterns(run_id)
        cluster_specs = await self._gap_repo.get_cluster_specs(run_id)

        # Build signal average rows
        averages: List[SignalAverageRow] = []
        for sig_def in _SIGNAL_DEFS:
            avg_val = signal_avgs.get(sig_def["field"], 0.0)
            if avg_val == 0.0 and sig_def["field"] not in signal_avgs:
                continue  # skip signals with no data
            rec = f"Citation average: {avg_val:.2f} {sig_def['unit']}"
            averages.append(SignalAverageRow(
                signal=sig_def["name"],
                category=sig_def["category"],
                citation_avg=round(avg_val, 4),
                company_avg=0.0,
                unit=sig_def["unit"],
                recommendation=rec,
            ))

        # Build correlation rows
        correlations: List[SignalCorrelationRow] = []
        for sig_def in _SIGNAL_DEFS:
            corr_val = signal_corrs.get(sig_def["field"], 0.0)
            if corr_val != 0.0:
                correlations.append(SignalCorrelationRow(
                    signal=sig_def["name"],
                    correlation=round(corr_val, 4),
                    category=sig_def["category"],
                ))
        correlations.sort(key=lambda r: abs(r.correlation), reverse=True)

        # Build cluster pattern rows
        pattern_rows: List[ClusterPatternRow] = []
        spec_lookup = {s.cluster_name: s for s in cluster_specs}
        for cp in cluster_patterns:
            cname = cp["cluster_name"]
            spec = spec_lookup.get(cname)
            pattern_rows.append(ClusterPatternRow(
                cluster_id=spec.cluster_id if spec else "",
                cluster_name=cname,
                faq=cp.get("faq_rate", 0.0),
                definition_opening=cp.get("definition_rate", 0.0),
                key_takeaways=cp.get("key_takeaways_rate", 0.0),
                comparison_table=cp.get("comparison_table_rate", 0.0),
                step_by_step=cp.get("step_by_step_rate", 0.0),
                research_refs=cp.get("research_refs_rate", 0.0),
                expert_quotes=0.0,
            ))

        # Build cluster fingerprints from specs
        fingerprints: Dict[str, Dict[str, float]] = {}
        for spec in cluster_specs:
            cid = spec.cluster_id or spec.cluster_name
            rates = spec.structural_rates or {}
            fingerprints[cid] = {
                "word_count": spec.avg_word_count or 0,
                "headers": rates.get("headers", 0),
                "lists": rates.get("lists", 0),
                "tables": spec.table_rate or 0,
                "faq": spec.faq_rate or 0,
                "stats": rates.get("stats", 0),
                "citations": rates.get("citations", 0),
            }
        # Normalize fingerprints
        if fingerprints:
            dimensions = list(next(iter(fingerprints.values())).keys())
            maxes = {dim: max((v.get(dim, 0) for v in fingerprints.values()), default=1.0) or 1.0 for dim in dimensions}
            fingerprints = {
                cid: {dim: round(vals.get(dim, 0) / maxes[dim], 2) for dim in dimensions}
                for cid, vals in fingerprints.items()
            }

        return SignalAveragesResponse(
            averages=averages,
            correlations=correlations,
            cluster_patterns=pattern_rows,
            cluster_fingerprints=fingerprints,
        )

    async def get_platforms(self, effective_slug: str) -> PlatformListResponse:
        run_id = await self._resolve_run_id(effective_slug)

        summaries = await self._platform_repo.get_platform_summaries(run_id)
        url_sets = await self._platform_repo.get_platform_url_sets(run_id)
        exclusivity = await self._platform_repo.get_citation_exclusivity(run_id)

        # Compute Jaccard agreement in Python (per plan W4)
        display_url_sets: Dict[str, set[str]] = {}
        for engine, urls in url_sets.items():
            display = _map_engine_display(engine)
            display_url_sets[display] = urls

        platforms_sorted = sorted(display_url_sets.keys())
        agreement: Dict[str, Dict[str, float]] = {}
        for p1 in platforms_sorted:
            agreement[p1] = {}
            for p2 in platforms_sorted:
                if p1 == p2:
                    agreement[p1][p2] = 1.0
                else:
                    s1, s2 = display_url_sets[p1], display_url_sets[p2]
                    union = len(s1 | s2)
                    agreement[p1][p2] = round(len(s1 & s2) / union, 2) if union else 0.0

        # Build platform summaries
        platform_list: List[PlatformSummaryResponse] = []
        for s in summaries:
            display = _map_engine_display(s["engine"])
            platform_list.append(PlatformSummaryResponse(
                engine=display,
                citation_count=s["citation_count"],
                unique_urls=s["unique_urls"],
                exclusive_urls=exclusivity.get(s["engine"], 0),
            ))

        return PlatformListResponse(
            platforms=platform_list,
            agreement_matrix=agreement,
            exclusivity={},
        )

    async def get_heatmap(self, effective_slug: str) -> HeatmapResponse:
        run_id = await self._resolve_run_id(effective_slug)

        # Fetch all gaps grouped by cluster
        gaps = await self._gap_repo.get_gaps_by_run(run_id, limit=10000)

        cluster_map: Dict[str, List[HeatmapQuery]] = defaultdict(list)
        for gap in gaps:
            cluster_map[gap.cluster_name].append(HeatmapQuery(
                query_id=gap.query_id,
                query_text=gap.query_text,
                gap_score=gap.gap or 0.0,
                classification=str(gap.classification.value) if gap.classification else "roughly_equal",
            ))

        clusters: List[HeatmapCluster] = []
        for cname in sorted(cluster_map.keys()):
            queries = cluster_map[cname]
            avg_gap = sum(q.gap_score for q in queries) / len(queries) if queries else 0.0
            clusters.append(HeatmapCluster(
                cluster_name=cname,
                queries=queries,
                avg_gap=round(avg_gap, 4),
            ))

        return HeatmapResponse(clusters=clusters)

    async def get_embedding_projection(
        self,
        effective_slug: str,
        method: Literal["umap", "tsne"] = "umap",
    ) -> EmbeddingProjectionResponse:
        """Delegates to filesystem — embedding projections are pre-computed s7 blobs."""
        import asyncio
        from api.services.gap_data_service import get_embedding_projection
        return await asyncio.to_thread(
            get_embedding_projection, self._artifacts_root, effective_slug, method=method,
        )

    async def get_spa_trend(self, effective_slug: str) -> SPATrendResponse:
        """SPA trend from completed gap analysis runs."""
        runs = await self._pipeline_repo.list_runs_by_slug(
            effective_slug,
            pipeline_type=PipelineType.gap_analysis,
            status=PipelineStatus.completed,
            limit=50,
        )

        points: List[SPATrendPoint] = []
        for run in reversed(runs):  # oldest first for chart x-axis
            summary = run.summary or {}
            spa_score = summary.get("spa_score") or summary.get("t_stat")
            if spa_score is None:
                continue
            try:
                score = float(spa_score)
                if not math.isfinite(score):
                    continue
            except (TypeError, ValueError):
                continue

            points.append(SPATrendPoint(
                run_id=str(run.id),
                spa_score=round(score, 4),
                date=run.completed_at.isoformat() if run.completed_at else run.created_at.isoformat(),
                total_queries=int(summary.get("total_queries", 0)),
                total_citations=int(summary.get("total_citations", 0)),
            ))

        return SPATrendResponse(trend=points)
