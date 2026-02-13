from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import ttest_ind

from core.models.gap_analysis import (
    AnalysisResult,
    CentroidResult,
    CitationExemplar,
    ClusterContentSpec,
    EnrichedCitation,
    GeneratedQuery,
    QueryGap,
    SemanticUnit,
    SpaResult,
)

TOP_N_CITATIONS = 5   # Max citations per query (ranked by best paragraph similarity)
TOP_K_PARAGRAPHS = 3  # Max paragraphs per citation URL


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    if np.linalg.norm(a) == 0.0 or np.linalg.norm(b) == 0.0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _cluster_map(queries: List[GeneratedQuery]) -> Dict[str, str]:
    return {q.query_id: q.cluster_name for q in queries}


def _select_top_citations(
    citations: List[EnrichedCitation],
    query_embedding: List[float],
    top_n: int = TOP_N_CITATIONS,
    top_k: int = TOP_K_PARAGRAPHS,
) -> List[EnrichedCitation]:
    """Rank citations by their best paragraph's similarity to query, return top-N."""
    scored: List[Tuple[float, EnrichedCitation]] = []
    for citation in citations:
        best_sim = 0.0
        for match in citation.best_paragraphs[:top_k]:
            if match.embedding:
                sim = _cosine_similarity(query_embedding, match.embedding)
                best_sim = max(best_sim, sim)
        scored.append((best_sim, citation))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_n]]


def compute_gap_analysis(
    queries: List[GeneratedQuery],
    company_units: List[SemanticUnit],
    enriched: List[EnrichedCitation],
) -> AnalysisResult:
    query_lookup = {q.query_id: q for q in queries}
    cluster_lookup = _cluster_map(queries)

    # Pre-index citations by query_id for O(1) lookups
    citations_by_query: Dict[str, List[EnrichedCitation]] = defaultdict(list)
    for citation in enriched:
        if citation.query_id:
            citations_by_query[citation.query_id].append(citation)

    query_to_citation_sims: Dict[str, List[float]] = defaultdict(list)
    query_to_company_best: Dict[str, float] = {}
    query_to_best_unit: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    query_to_exemplars: Dict[str, List[CitationExemplar]] = defaultdict(list)

    for query in queries:
        if not query.embedding:
            continue

        # Citation similarities + exemplar collection (top-N citations, top-K paragraphs)
        top_citations = _select_top_citations(
            citations_by_query.get(query.query_id, []),
            query.embedding,
        )
        for citation in top_citations:
            for match in citation.best_paragraphs[:TOP_K_PARAGRAPHS]:
                if match.embedding:
                    sim = _cosine_similarity(query.embedding, match.embedding)
                    query_to_citation_sims[query.query_id].append(sim)
                    query_to_exemplars[query.query_id].append(
                        CitationExemplar(
                            similarity=round(sim, 4),
                            domain=citation.domain,
                            url=str(citation.url),
                            snippet=(match.paragraph[:300] if match.paragraph else None),
                            structural_signals=citation.structural_signals,
                            authority_type=(
                                citation.structural_signals.authority_type
                                if citation.structural_signals
                                else None
                            ),
                        )
                    )

        # Company best similarity — track unit ID and text
        best_sim = 0.0
        best_unit_id: Optional[str] = None
        best_unit_text: Optional[str] = None
        for unit in company_units:
            if unit.embedding:
                sim = _cosine_similarity(query.embedding, unit.embedding)
                if sim > best_sim:
                    best_sim = sim
                    best_unit_id = unit.unit_id
                    best_unit_text = unit.text[:200] if unit.text else None
        query_to_company_best[query.query_id] = best_sim
        query_to_best_unit[query.query_id] = (best_unit_id, best_unit_text)

    # Sort and keep top-3 exemplars per query
    for qid in query_to_exemplars:
        query_to_exemplars[qid].sort(key=lambda e: e.similarity, reverse=True)
        query_to_exemplars[qid] = query_to_exemplars[qid][:3]

    gaps: List[QueryGap] = []
    citation_sims_all: List[float] = []
    company_sims_all: List[float] = []
    for query_id, sims in query_to_citation_sims.items():
        avg_citation = float(np.mean(sims)) if sims else 0.0
        best_company = query_to_company_best.get(query_id, 0.0)
        gap = avg_citation - best_company
        interpretation = "roughly_equal"
        if gap >= 0.15:
            interpretation = "significant_gap"
        elif gap >= 0.05:
            interpretation = "gap_to_close"
        elif gap <= -0.05:
            interpretation = "company_wins"

        unit_id, unit_text = query_to_best_unit.get(query_id, (None, None))
        gaps.append(
            QueryGap(
                query_id=query_id,
                cluster_name=cluster_lookup.get(query_id),
                query_text=query_lookup[query_id].query_text,
                best_company_unit=unit_id,
                best_company_unit_text=unit_text,
                best_company_similarity=best_company,
                avg_citation_similarity=avg_citation,
                gap=gap,
                interpretation=interpretation,
                top_cited_exemplars=query_to_exemplars.get(query_id, []),
            )
        )
        citation_sims_all.extend(sims)
        company_sims_all.append(best_company)

    proximity_stats = {
        "citation_similarity_mean": float(np.mean(citation_sims_all)) if citation_sims_all else 0.0,
        "citation_similarity_median": float(np.median(citation_sims_all)) if citation_sims_all else 0.0,
        "company_similarity_mean": float(np.mean(company_sims_all)) if company_sims_all else 0.0,
        "company_similarity_median": float(np.median(company_sims_all)) if company_sims_all else 0.0,
    }

    # Per-cluster proximity breakdown
    cluster_sims: Dict[str, List[float]] = defaultdict(list)
    for query_id, sims in query_to_citation_sims.items():
        cluster = cluster_lookup.get(query_id, "unknown")
        cluster_sims[cluster].extend(sims)

    proximity_stats["per_cluster"] = {
        cluster: {
            "mean": float(np.mean(s)),
            "std": float(np.std(s)),
            "min": float(np.min(s)),
            "max": float(np.max(s)),
            "count": len(s),
        }
        for cluster, s in cluster_sims.items()
        if s
    }

    spa_results: List[SpaResult] = []
    if citation_sims_all and company_sims_all:
        stat = ttest_ind(citation_sims_all, company_sims_all, equal_var=False)
        effect = "citation_advantage" if stat.statistic > 0 else "company_advantage"
        spa_results.append(
            SpaResult(
                cluster_id=None,
                cluster_name="all",
                t_stat=float(stat.statistic),
                p_value=float(stat.pvalue),
                mean_citation_similarity=float(np.mean(citation_sims_all)),
                mean_company_similarity=float(np.mean(company_sims_all)),
                effect=effect,
            )
        )

    centroids: List[CentroidResult] = []
    for cluster, cluster_queries in _group_by_cluster(queries).items():
        query_embeddings = [q.embedding for q in cluster_queries if q.embedding]
        citation_embeddings = _collect_citation_embeddings(enriched, cluster, query_lookup)
        if not query_embeddings or not citation_embeddings:
            continue
        query_centroid = np.mean(np.array(query_embeddings), axis=0)
        citation_centroid = np.mean(np.array(citation_embeddings), axis=0)
        distance = 1.0 - _cosine_similarity(query_centroid.tolist(), citation_centroid.tolist())
        centroids.append(
            CentroidResult(
                cluster_id=cluster_queries[0].cluster_id,
                cluster_name=cluster,
                query_centroid=query_centroid.tolist(),
                citation_centroid=citation_centroid.tolist(),
                distance=float(distance),
            )
        )

    citation_patterns = _citation_patterns(enriched)
    cluster_specs = _compute_cluster_specs(enriched, queries, gaps)
    decision_metrics = {
        "total_queries": len(queries),
        "total_citations": len(enriched),
        "avg_gap": float(np.mean([g.gap or 0.0 for g in gaps])) if gaps else 0.0,
    }

    return AnalysisResult(
        proximity_stats=proximity_stats,
        spa_results=spa_results,
        centroids=centroids,
        gaps=gaps,
        citation_patterns=citation_patterns,
        decision_metrics=decision_metrics,
        cluster_specs=cluster_specs,
    )


def _group_by_cluster(queries: List[GeneratedQuery]) -> Dict[str, List[GeneratedQuery]]:
    clusters: Dict[str, List[GeneratedQuery]] = defaultdict(list)
    for query in queries:
        clusters[query.cluster_name].append(query)
    return clusters


def _collect_citation_embeddings(
    enriched: List[EnrichedCitation],
    cluster_name: str,
    query_lookup: Dict[str, GeneratedQuery],
) -> List[List[float]]:
    embeddings: List[List[float]] = []
    for citation in enriched:
        query_id = citation.query_id or ""
        if query_id and query_lookup.get(query_id, None):
            if query_lookup[query_id].cluster_name != cluster_name:
                continue
        for match in citation.best_paragraphs[:TOP_K_PARAGRAPHS]:
            if match.embedding:
                embeddings.append(match.embedding)
    return embeddings


def _citation_patterns(enriched: List[EnrichedCitation]) -> Dict[str, Dict[str, int]]:
    domain_counts = Counter()
    authority_counts = Counter()
    content_type_counts = Counter()
    for citation in enriched:
        if citation.domain:
            domain_counts[citation.domain] += 1
        signals = citation.structural_signals
        if signals and signals.authority_type:
            authority_counts[signals.authority_type] += 1
        if signals and signals.content_type:
            content_type_counts[signals.content_type] += 1
    return {
        "domains": dict(domain_counts),
        "authority_types": dict(authority_counts),
        "content_types": dict(content_type_counts),
    }


def _compute_cluster_specs(
    enriched: List[EnrichedCitation],
    queries: List[GeneratedQuery],
    gaps: List[QueryGap],
) -> List[ClusterContentSpec]:
    """Aggregate citation structural signals per cluster into content specs."""

    # Group citations by cluster
    cluster_citations: Dict[str, List[EnrichedCitation]] = defaultdict(list)
    for citation in enriched:
        cluster = citation.cluster_name
        if cluster:
            cluster_citations[cluster].append(citation)

    # Query count per cluster
    cluster_query_counts: Dict[str, int] = Counter()
    cluster_ids: Dict[str, str] = {}
    for q in queries:
        cluster_query_counts[q.cluster_name] += 1
        if q.cluster_name not in cluster_ids:
            cluster_ids[q.cluster_name] = q.cluster_id

    # Avg citation similarity per cluster (from gaps)
    cluster_citation_sims: Dict[str, List[float]] = defaultdict(list)
    for g in gaps:
        if g.cluster_name and g.avg_citation_similarity is not None:
            cluster_citation_sims[g.cluster_name].append(g.avg_citation_similarity)

    specs: List[ClusterContentSpec] = []
    for cluster_name, citations in cluster_citations.items():
        # Word count range
        word_counts = [
            c.structural_signals.word_count
            for c in citations
            if c.structural_signals and c.structural_signals.word_count > 0
        ]
        word_count_range = (
            [int(min(word_counts)), int(max(word_counts))] if word_counts else [0, 0]
        )

        # Authority signals distribution
        authority_signals: Dict[str, int] = Counter()
        for c in citations:
            if c.structural_signals and c.structural_signals.authority_type:
                authority_signals[c.structural_signals.authority_type] += 1

        # Structural rates
        total = len(citations)
        has_header = sum(
            1 for c in citations if c.structural_signals and c.structural_signals.header_count > 0
        )
        has_list = sum(
            1 for c in citations if c.structural_signals and c.structural_signals.list_item_count > 0
        )
        has_stat = sum(
            1 for c in citations if c.structural_signals and c.structural_signals.stat_count > 0
        )
        has_cite = sum(
            1 for c in citations if c.structural_signals and c.structural_signals.citation_count > 0
        )

        structural_rates: Dict[str, float] = {}
        if total > 0:
            structural_rates = {
                "headers": round(has_header / total, 2),
                "lists": round(has_list / total, 2),
                "stats": round(has_stat / total, 2),
                "citations": round(has_cite / total, 2),
            }

        # Required elements: rate >= 0.8
        required_elements: List[str] = [
            name for name, rate in structural_rates.items() if rate >= 0.8
        ]

        # Min similarity threshold: mean - 0.5 * std
        sims = cluster_citation_sims.get(cluster_name, [])
        min_sim_threshold: Optional[float] = None
        if sims:
            mean_sim = float(np.mean(sims))
            std_sim = float(np.std(sims))
            min_sim_threshold = round(mean_sim - 0.5 * std_sim, 4)

        specs.append(
            ClusterContentSpec(
                cluster_id=cluster_ids.get(cluster_name),
                cluster_name=cluster_name,
                query_count=cluster_query_counts.get(cluster_name, 0),
                word_count_range=word_count_range,
                min_similarity_threshold=min_sim_threshold,
                required_elements=required_elements,
                authority_signals=dict(authority_signals),
                structural_rates=structural_rates,
                total_citations_analyzed=total,
            )
        )

    return specs
