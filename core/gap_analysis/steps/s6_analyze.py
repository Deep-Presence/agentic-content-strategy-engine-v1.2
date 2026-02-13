from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import ttest_ind

from core.models.gap_analysis import (
    AnalysisResult,
    CentroidResult,
    EnrichedCitation,
    GeneratedQuery,
    QueryGap,
    SemanticUnit,
    SpaResult,
)


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    if np.linalg.norm(a) == 0.0 or np.linalg.norm(b) == 0.0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _cluster_map(queries: List[GeneratedQuery]) -> Dict[str, str]:
    return {q.query_id: q.cluster_name for q in queries}


def compute_gap_analysis(
    queries: List[GeneratedQuery],
    company_units: List[SemanticUnit],
    enriched: List[EnrichedCitation],
) -> AnalysisResult:
    query_lookup = {q.query_id: q for q in queries}
    cluster_lookup = _cluster_map(queries)

    query_to_citation_sims: Dict[str, List[float]] = defaultdict(list)
    query_to_company_best: Dict[str, float] = {}
    for query in queries:
        if not query.embedding:
            continue
        # citation similarities
        for citation in enriched:
            if citation.query_id != query.query_id:
                continue
            for match in citation.best_paragraphs:
                if match.embedding:
                    query_to_citation_sims[query.query_id].append(
                        _cosine_similarity(query.embedding, match.embedding)
                    )
        # company best similarity
        best_sim = 0.0
        for unit in company_units:
            if unit.embedding:
                sim = _cosine_similarity(query.embedding, unit.embedding)
                if sim > best_sim:
                    best_sim = sim
        query_to_company_best[query.query_id] = best_sim

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
        gaps.append(
            QueryGap(
                query_id=query_id,
                cluster_name=cluster_lookup.get(query_id),
                query_text=query_lookup[query_id].query_text,
                best_company_unit=None,
                best_company_similarity=best_company,
                avg_citation_similarity=avg_citation,
                gap=gap,
                interpretation=interpretation,
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
        for match in citation.best_paragraphs:
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
