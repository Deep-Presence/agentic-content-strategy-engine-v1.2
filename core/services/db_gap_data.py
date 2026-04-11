"""DbGapDataService — Postgres-backed implementation of GapDataServiceProtocol.

Reads gap analysis data from SQL via repositories instead of parsing JSON files.
Embedding projections remain filesystem-backed (pre-computed s7 blobs).
"""
from __future__ import annotations

import asyncio
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import HTTPException

from api.schemas.brand_data import SPATrendResponse, SPATrendPoint
from api.schemas.content_data import EmbeddingProjectionResponse
from api.schemas.gap_data import (
    ClusterDomainEntry,
    ClusterListResponse,
    ClusterPatternRow,
    ClusterPerformanceRow,
    ClusterProfileListResponse,
    ClusterProfileResponse,
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
    TerritoryCompanySignals,
    TerritoryContentBrief,
    TerritoryGapExemplar,
    TerritoryGapQuery,
    TerritoryGapsResponse,
    TerritoryProximityStats,
    TerritorySPA,
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


def _slugify_cluster(name: str) -> str:
    """Convert cluster display name to URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _compute_presence(company_share: float) -> str:
    """Derive presence level from company share of citations."""
    if company_share <= 0:
        return "none"
    if company_share < 0.05:
        return "minimal"
    if company_share < 0.15:
        return "low"
    if company_share < 0.30:
        return "moderate"
    return "strong"


def _as_list(val: Any) -> Optional[List[Any]]:
    """Coerce a scalar or dict range to a 2-element list, or None."""
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        return list(val)
    if isinstance(val, dict):
        return [val.get("min", 0), val.get("max", 0)]
    return [val, val]


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
        storage: "StorageBackend",
    ) -> None:
        self._gap_repo = gap_repo
        self._pipeline_repo = pipeline_repo
        self._signal_repo = signal_repo
        self._platform_repo = platform_repo
        self._storage = storage

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

    async def get_summary(self, effective_slug: str, *, ga_run_id: Optional[str] = None) -> GapSummaryResponse:
        # Topic-scoped GA: delegate to JSON/filesystem service (no DB tables for scoped runs)
        if ga_run_id:
            from api.services.gap_data_service import get_summary as _fs_get_summary
            return await asyncio.to_thread(_fs_get_summary, self._storage, effective_slug, ga_run_id=ga_run_id)
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

        # Cluster performance from specs + centroid + SPA results
        centroid_lookup = {c.cluster_name: c for c in centroid_results}
        spa_lookup = {s.cluster_name: s for s in spa_results}
        cluster_perf: List[ClusterPerformanceRow] = []
        for spec in cluster_specs:
            centroid = centroid_lookup.get(spec.cluster_name)
            spa_row = spa_lookup.get(spec.cluster_name)
            cluster_perf.append(
                ClusterPerformanceRow(
                    cluster_id=spec.cluster_id,
                    cluster_name=spec.cluster_name,
                    query_count=spec.query_count,
                    citation_count=spec.total_citations_analyzed,
                    avg_gap=centroid.distance if centroid else 0.0,
                    avg_citation_sim=spa_row.mean_citation_similarity if spa_row else 0.0,
                    avg_company_sim=spa_row.mean_company_similarity if spa_row else 0.0,
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
            company_cited_count=run_summary.get("company_cited_count", 0),
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
                # target_word_count is stored as [min, max] tuple in DB but
                # QueryContentBrief expects {"min": int, "max": int} dict
                raw_twc = gap.content_brief.get("target_word_count", {})
                if isinstance(raw_twc, (list, tuple)) and len(raw_twc) >= 2:
                    twc = {"min": raw_twc[0], "max": raw_twc[1]}
                elif isinstance(raw_twc, dict):
                    twc = raw_twc
                else:
                    twc = {"min": 0, "max": 0}
                brief = QueryContentBrief(
                    title=gap.content_brief.get("title", ""),
                    target_word_count=twc,
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
                citations_analyzed=spec.total_citations_analyzed,
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
                expert_quotes=cp.get("expert_quotes_rate", 0.0),
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
            signals=averages,
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
                name=display,
                total_citations=s["citation_count"],
                unique_domains=s["unique_urls"],
            ))

        return PlatformListResponse(
            platforms=platform_list,
            agreement=agreement,
            citation_exclusivity={},
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
            get_embedding_projection, self._storage, effective_slug, method=method,
        )

    async def get_cluster_profiles(
        self, effective_slug: str,
    ) -> ClusterProfileListResponse:
        """SQL-backed cluster profiles — replaces filesystem delegation."""
        run_id = await self._resolve_run_id(effective_slug)

        cluster_specs = await self._gap_repo.get_cluster_specs(run_id)
        cluster_metrics = await self._gap_repo.get_all_cluster_metrics(run_id)
        proximity_stats = await self._gap_repo.get_cluster_proximity_stats(run_id)
        spa_results = await self._gap_repo.get_spa_results(run_id)
        cross_cluster_domains = await self._gap_repo.get_cross_cluster_domains(run_id)

        spec_lookup = {s.cluster_name: s for s in cluster_specs if s.cluster_name}
        metrics_lookup = {m.cluster_name: m for m in cluster_metrics if m.cluster_name}
        prox_lookup = {p.cluster_name: p for p in proximity_stats}

        all_clusters = set(spec_lookup.keys()) | set(metrics_lookup.keys())
        all_clusters.discard(None)  # type: ignore[arg-type]

        profiles: Dict[str, ClusterProfileResponse] = {}
        for cname in sorted(all_clusters):
            spec = spec_lookup.get(cname)
            metrics = metrics_lookup.get(cname)
            prox = prox_lookup.get(cname)

            total_citations = metrics.total_citations if metrics else 0
            unique_domains = metrics.unique_domains if metrics else 0
            company_citations = metrics.company_citations if metrics else 0
            company_share = (
                company_citations / total_citations if total_citations > 0 else 0.0
            )

            # Per-cluster domain leaderboard + engine breakdown
            domain_rows = await self._gap_repo.get_cluster_domain_leaderboard(
                run_id, cname,
            )
            engine_rows = await self._gap_repo.get_cluster_engine_breakdown(
                run_id, cname,
            )

            # Build company domain set from leaderboard
            company_domains = {d.domain for d in domain_rows if d.is_company}

            # Domain type classification
            top_domains: List[ClusterDomainEntry] = []
            for d in domain_rows:
                share = d.citations / total_citations if total_citations > 0 else 0.0
                domain_str = d.domain or ""
                if d.is_company:
                    dtype = "company"
                elif domain_str in cross_cluster_domains:
                    dtype = "mindshare"
                elif any(domain_str.endswith(s) for s in (
                    ".gov", ".edu", ".org", ".ac.uk", ".gov.uk",
                )):
                    dtype = "authority"
                else:
                    dtype = "direct"
                top_domains.append(ClusterDomainEntry(
                    domain=d.domain or "",
                    citations=d.citations,
                    is_company=d.is_company or False,
                    share=round(share, 4),
                    type=dtype,
                ))

            engine_breakdown = {
                str(e.engine.value): e.citations for e in engine_rows
            }

            slug_id = _slugify_cluster(cname)

            # Company rank among domains
            company_rank = None
            if company_domains:
                for rank, d in enumerate(domain_rows, 1):
                    if d.domain in company_domains:
                        company_rank = rank
                        break

            proximity = None
            if prox:
                proximity = {
                    "mean": prox.citation_mean,
                    "std": prox.citation_std,
                    "count": prox.count,
                }

            wc_range = (
                [spec.word_count_min, spec.word_count_max] if spec else [0, 0]
            )

            profiles[slug_id] = ClusterProfileResponse(
                cluster_id=slug_id,
                cluster_name=cname,
                query_count=spec.query_count if spec else 0,
                total_citations=total_citations,
                unique_domains=unique_domains,
                company_citations=company_citations,
                company_share=round(company_share, 4),
                company_rank=company_rank,
                presence=_compute_presence(company_share),
                avg_word_count=spec.avg_word_count if spec else 0.0,
                word_count_range=wc_range,
                dominant_content_type=(
                    spec.dominant_content_type if spec else None
                ),
                dominant_authority_type=(
                    spec.dominant_authority_type if spec else None
                ),
                structural_rates=spec.structural_rates or {} if spec else {},
                faq_rate=spec.faq_rate if spec else 0.0,
                table_rate=spec.table_rate if spec else 0.0,
                required_elements=(
                    spec.required_elements or [] if spec else []
                ),
                exemplar_themes=spec.exemplar_themes or [] if spec else [],
                authority_signals={},
                proximity=proximity,
                engine_breakdown=engine_breakdown,
                top_domains=top_domains,
            )

        return ClusterProfileListResponse(profiles=profiles)

    async def get_territory_gaps(
        self, effective_slug: str,
    ) -> TerritoryGapsResponse:
        """SQL-backed territory gaps — replaces filesystem delegation."""
        run_id = await self._resolve_run_id(effective_slug)

        gaps = await self._gap_repo.get_territory_gaps_with_signals(run_id)
        proximity_rows = await self._gap_repo.get_cluster_proximity_stats(run_id)
        spa_results = await self._gap_repo.get_spa_results(run_id)

        territory_gaps: List[TerritoryGapQuery] = []
        uncovered = 0

        for gap in gaps:
            cname = gap.cluster_name or ""
            slug_id = _slugify_cluster(cname)
            company_cited = gap.company_cited or False
            if not company_cited:
                uncovered += 1

            # Build exemplars from ORM relationships (sorted by rank)
            sorted_exemplars = sorted(
                gap.exemplars or [], key=lambda e: e.rank or 999,
            )
            exemplars: List[TerritoryGapExemplar] = []
            for ex in sorted_exemplars[:5]:
                ss = None
                if ex.url_enrichment and ex.url_enrichment.structural_signals:
                    ss = ex.url_enrichment.structural_signals
                exemplars.append(TerritoryGapExemplar(
                    domain=ex.domain or "",
                    url=ex.url,
                    similarity=ex.similarity,
                    content_type=(
                        ex.url_enrichment.content_type
                        if ex.url_enrichment else None
                    ),
                    authority_type=ex.authority_type or (
                        ex.url_enrichment.authority_type
                        if ex.url_enrichment else None
                    ),
                    word_count=ss.word_count if ss else None,
                    header_count=ss.header_count if ss else None,
                    has_faq=bool(ss.has_faq_section) if ss else False,
                    has_tables=bool(ss.table_count) if ss else False,
                    reading_level=ss.reading_level if ss else None,
                    list_item_count=ss.list_item_count if ss else 0,
                    stat_count=ss.stat_count if ss else 0,
                    citation_count=ss.citation_count if ss else 0,
                ))

            # Company signals from JSONB
            company_signals = None
            if gap.best_company_structural_signals and isinstance(
                gap.best_company_structural_signals, dict,
            ):
                raw = gap.best_company_structural_signals
                company_signals = TerritoryCompanySignals(
                    word_count=raw.get("word_count"),
                    header_count=raw.get("header_count"),
                    has_faq=bool(raw.get("has_faq_section", False)),
                    has_tables=bool(raw.get("table_count", 0)),
                    reading_level=raw.get("reading_level"),
                    list_item_count=raw.get("list_item_count", 0) or 0,
                )

            # Content brief from JSONB
            content_brief = None
            if gap.content_brief and isinstance(gap.content_brief, dict):
                cb = gap.content_brief
                content_brief = TerritoryContentBrief(
                    word_count_range=_as_list(cb.get("target_word_count")),
                    reading_level_range=_as_list(cb.get("target_reading_level")),
                    header_count_range=_as_list(
                        cb.get("recommended_header_count"),
                    ),
                    header_hierarchy=cb.get("header_hierarchy"),
                    has_faq=cb.get("has_faq_section", 0.0) or 0.0,
                    has_tables=cb.get("has_tables", 0.0) or 0.0,
                    has_definition=cb.get("has_definition_opening", 0.0) or 0.0,
                    has_key_takeaways=cb.get("has_key_takeaways", 0.0) or 0.0,
                    has_step_by_step=cb.get("has_step_by_step", 0.0) or 0.0,
                    dominant_content_type=cb.get("dominant_content_type"),
                    dominant_authority_type=cb.get("dominant_authority_type"),
                )

            territory_gaps.append(TerritoryGapQuery(
                id=gap.query_id,
                query=gap.query_text,
                cluster=cname,
                cluster_id=slug_id,
                gap=gap.gap or 0.0,
                classification=(
                    str(gap.classification.value)
                    if gap.classification else "roughly_equal"
                ),
                company_cited=company_cited,
                company_url=gap.best_company_url,
                company_similarity=gap.best_company_similarity,
                avg_citation_similarity=gap.avg_citation_similarity or 0.0,
                exemplars=exemplars,
                company_signals=company_signals,
                content_brief=content_brief,
            ))

        # SPA — find the "all" entry
        spa = TerritorySPA()
        for sr in spa_results:
            cname = sr.cluster_name or ""
            if cname == "all" or cname == "":
                spa = TerritorySPA(
                    t_stat=sr.t_stat or 0.0,
                    p_value=sr.p_value or 0.0,
                    effect=sr.effect or "unknown",
                )
                break

        # Global proximity from __global__ row
        global_prox = None
        per_cluster_proximity: Dict[str, Dict[str, float]] = {}
        for p in proximity_rows:
            if p.cluster_name == "__global__":
                global_prox = p
            else:
                slug_id = _slugify_cluster(p.cluster_name)
                per_cluster_proximity[slug_id] = {
                    "mean": p.citation_mean,
                    "std": p.citation_std,
                    "min": p.citation_min,
                    "max": p.citation_max,
                    "count": p.count,
                }

        proximity_stats = TerritoryProximityStats(
            citation_mean=global_prox.citation_mean if global_prox else 0.0,
            citation_median=(
                global_prox.citation_median if global_prox else 0.0
            ),
            company_mean=global_prox.company_mean if global_prox else 0.0,
            company_median=(
                global_prox.company_median if global_prox else 0.0
            ),
            similarity_gap=(
                (global_prox.citation_mean - global_prox.company_mean)
                if global_prox else 0.0
            ),
        )

        return TerritoryGapsResponse(
            gaps=territory_gaps,
            proximity_stats=proximity_stats,
            spa=spa,
            per_cluster_proximity=per_cluster_proximity,
            total_gaps=len(territory_gaps),
            uncovered_queries=uncovered,
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
