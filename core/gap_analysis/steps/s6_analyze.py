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
    CompanyPageAnalysis,
    EnrichedCitation,
    GapContentBrief,
    GeneratedQuery,
    QueryGap,
    SemanticUnit,
    SpaResult,
    StructuralSignals,
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


def _compute_content_brief(
    exemplars: List[CitationExemplar],
) -> Optional[GapContentBrief]:
    """Compute a content brief from top-cited exemplar structural signals.

    Dedupes exemplars by URL first to prevent single-URL bias (Codex finding #9).
    Returns None if no exemplars have structural signals.
    """
    # Dedupe by URL
    seen_urls: set[str] = set()
    unique_exemplars: List[CitationExemplar] = []
    for ex in exemplars:
        if ex.url not in seen_urls:
            seen_urls.add(ex.url)
            unique_exemplars.append(ex)

    # Filter to those with structural signals
    with_signals = [e for e in unique_exemplars if e.structural_signals]
    if not with_signals:
        return None

    signals_list = [e.structural_signals for e in with_signals]
    n = len(signals_list)

    def _min_max(values: list) -> tuple:
        if not values:
            return (0, 0)
        return (min(values), max(values))

    word_counts = [s.word_count for s in signals_list if s.word_count > 0]
    reading_levels = [s.reading_level for s in signals_list if s.reading_level > 0]
    avg_para_lengths = [int(s.avg_paragraph_length) for s in signals_list if s.avg_paragraph_length > 0]
    header_counts = [s.header_count for s in signals_list if s.header_count > 0]

    # Header hierarchy: median per level
    h2s = [s.h2_count for s in signals_list]
    h3s = [s.h3_count for s in signals_list]
    header_hierarchy: Dict[str, int] = {}
    if any(h2s):
        header_hierarchy["h2"] = int(np.median(h2s))
    if any(h3s):
        header_hierarchy["h3"] = int(np.median(h3s))

    # Boolean rates
    def _rate(field: str) -> float:
        count = sum(1 for s in signals_list if getattr(s, field, False))
        return round(count / n, 2)

    # Density averages (true per-1000-word densities, not raw counts)
    data_point_densities = [
        s.data_point_count / (s.word_count / 1000)
        for s in signals_list
        if s.data_point_count > 0 and s.word_count > 0
    ]
    citation_densities = [s.citation_density for s in signals_list if s.citation_density > 0]

    target_dpd = round(float(np.mean(data_point_densities)), 2) if data_point_densities else 0.0
    target_cd = round(float(np.mean(citation_densities)), 2) if citation_densities else 0.0

    # Dominant types
    authority_types = Counter(s.authority_type for s in signals_list if s.authority_type)
    content_types = Counter(s.content_type for s in signals_list if s.content_type)

    return GapContentBrief(
        target_word_count=_min_max(word_counts),
        target_reading_level=tuple(
            round(v, 1) for v in _min_max(reading_levels)
        ) if reading_levels else (0.0, 0.0),
        avg_paragraph_length=_min_max(avg_para_lengths),
        recommended_header_count=_min_max(header_counts),
        header_hierarchy=header_hierarchy,
        has_ordered_lists=_rate("ordered_list_count"),
        has_unordered_lists=_rate("unordered_list_count"),
        has_tables=_rate("table_count"),
        has_faq_section=_rate("has_faq_section"),
        has_definition_opening=_rate("has_definition_opening"),
        has_key_takeaways=_rate("has_key_takeaways"),
        has_step_by_step=_rate("has_step_by_step"),
        target_data_point_density=target_dpd,
        target_citation_density=target_cd,
        dominant_authority_type=authority_types.most_common(1)[0][0] if authority_types else None,
        dominant_content_type=content_types.most_common(1)[0][0] if content_types else None,
        exemplar_count=n,
    )


def compute_gap_analysis(
    queries: List[GeneratedQuery],
    company_units: List[SemanticUnit],
    enriched: List[EnrichedCitation],
    *,
    company_citation_map: Optional[Dict[str, List[str]]] = None,
    page_analysis_lookup: Optional[Dict[str, CompanyPageAnalysis]] = None,
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
    query_to_best_unit: Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]] = {}
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
                    # Strip per_paragraph_word_counts from exemplar signals
                    # to prevent artifact bloat (Codex finding #11)
                    exemplar_signals = None
                    if citation.structural_signals:
                        sig_data = citation.structural_signals.model_dump()
                        sig_data["per_paragraph_word_counts"] = []
                        exemplar_signals = StructuralSignals(**sig_data)
                    query_to_exemplars[query.query_id].append(
                        CitationExemplar(
                            similarity=round(sim, 4),
                            domain=citation.domain,
                            url=str(citation.url),
                            snippet=(match.paragraph[:300] if match.paragraph else None),
                            structural_signals=exemplar_signals,
                            authority_type=(
                                citation.structural_signals.authority_type
                                if citation.structural_signals
                                else None
                            ),
                        )
                    )

        # Company best similarity — track unit ID, text, and URL
        best_sim = 0.0
        best_unit_id: Optional[str] = None
        best_unit_text: Optional[str] = None
        best_unit_url: Optional[str] = None
        for unit in company_units:
            if unit.embedding:
                sim = _cosine_similarity(query.embedding, unit.embedding)
                if sim > best_sim:
                    best_sim = sim
                    best_unit_id = unit.unit_id
                    best_unit_text = unit.text[:200] if unit.text else None
                    best_unit_url = str(unit.url) if unit.url else None
        query_to_company_best[query.query_id] = best_sim
        query_to_best_unit[query.query_id] = (best_unit_id, best_unit_text, best_unit_url)

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

        unit_id, unit_text, unit_url = query_to_best_unit.get(
            query_id, (None, None, None)
        )
        exemplars = query_to_exemplars.get(query_id, [])
        content_brief = _compute_content_brief(exemplars) if exemplars else None
        cited_platforms = (
            company_citation_map.get(query_id, [])
            if company_citation_map
            else []
        )
        # Attach structural signals for the best company page
        company_signals_dict = None
        if page_analysis_lookup and unit_url:
            pa = page_analysis_lookup.get(unit_url)
            if pa and pa.structural_signals:
                sig_data = pa.structural_signals.model_dump()
                sig_data.pop("per_paragraph_word_counts", None)
                company_signals_dict = sig_data
        gaps.append(
            QueryGap(
                query_id=query_id,
                cluster_name=cluster_lookup.get(query_id),
                query_text=query_lookup[query_id].query_text,
                best_company_unit=unit_id,
                best_company_unit_text=unit_text,
                best_company_url=unit_url,
                best_company_similarity=best_company,
                avg_citation_similarity=avg_citation,
                gap=gap,
                interpretation=interpretation,
                top_cited_exemplars=exemplars,
                content_brief=content_brief,
                best_company_structural_signals=company_signals_dict,
                company_cited=bool(cited_platforms),
                company_cited_platforms=cited_platforms,
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
        signals_list = [c.structural_signals for c in citations if c.structural_signals]
        total = len(citations)

        # Word count range
        word_counts = [s.word_count for s in signals_list if s.word_count > 0]
        word_count_range = (
            [int(min(word_counts)), int(max(word_counts))] if word_counts else [0, 0]
        )

        # Authority signals distribution
        authority_signals: Dict[str, int] = Counter()
        for s in signals_list:
            if s.authority_type:
                authority_signals[s.authority_type] += 1

        # Original structural rates (backward compat)
        has_header = sum(1 for s in signals_list if s.header_count > 0)
        has_list = sum(1 for s in signals_list if s.list_item_count > 0)
        has_stat = sum(1 for s in signals_list if s.stat_count > 0)
        has_cite = sum(1 for s in signals_list if s.citation_count > 0)

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

        # --- Expanded fields (Phase 2) ---
        def _bool_rate(field: str) -> float:
            if not signals_list:
                return 0.0
            return round(sum(1 for s in signals_list if getattr(s, field, False)) / len(signals_list), 2)

        def _count_rate(field: str) -> float:
            if not signals_list:
                return 0.0
            return round(sum(1 for s in signals_list if getattr(s, field, 0) > 0) / len(signals_list), 2)

        faq_rate = _bool_rate("has_faq_section")
        table_rate = _count_rate("table_count")
        definition_rate = _count_rate("definition_list_count")
        code_block_rate = _count_rate("code_block_count")
        key_takeaways_rate = _bool_rate("has_key_takeaways")

        avg_word_count = round(float(np.mean(word_counts)), 1) if word_counts else 0.0
        avg_para_wcs = [s.avg_paragraph_length for s in signals_list if s.avg_paragraph_length > 0]
        avg_paragraph_word_count = round(float(np.mean(avg_para_wcs)), 1) if avg_para_wcs else 0.0
        avg_sent_per_para = [s.avg_sentence_count_per_paragraph for s in signals_list if s.avg_sentence_count_per_paragraph > 0]
        avg_sentence_count_per_paragraph = round(float(np.mean(avg_sent_per_para)), 1) if avg_sent_per_para else 0.0

        bullets_lists = [s.min_bullets_per_list for s in signals_list if s.min_bullets_per_list > 0]
        min_bullets_per_list = int(np.median(bullets_lists)) if bullets_lists else 0

        # Dominant types
        content_types = Counter(s.content_type for s in signals_list if s.content_type)
        authority_type_counter = Counter(s.authority_type for s in signals_list if s.authority_type)
        dominant_content_type = content_types.most_common(1)[0][0] if content_types else None
        dominant_authority_type = authority_type_counter.most_common(1)[0][0] if authority_type_counter else None

        # Exemplar themes via TF-IDF (Codex: wrap in try/except for empty vocab)
        exemplar_themes: List[str] = []
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            all_docs = [" ".join(c.paragraphs[:5]) for c in citations if c.paragraphs]
            if len(all_docs) >= 2:
                tfidf = TfidfVectorizer(max_features=20, stop_words="english")
                tfidf.fit_transform(all_docs)
                exemplar_themes = list(tfidf.get_feature_names_out()[:10])
        except Exception:
            pass  # Empty vocab or other TF-IDF failure — acceptable

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
                # Expanded fields
                faq_rate=faq_rate,
                table_rate=table_rate,
                definition_rate=definition_rate,
                code_block_rate=code_block_rate,
                key_takeaways_rate=key_takeaways_rate,
                avg_word_count=avg_word_count,
                avg_paragraph_word_count=avg_paragraph_word_count,
                avg_sentence_count_per_paragraph=avg_sentence_count_per_paragraph,
                min_bullets_per_list=min_bullets_per_list,
                dominant_content_type=dominant_content_type,
                dominant_authority_type=dominant_authority_type,
                exemplar_themes=exemplar_themes,
            )
        )

    return specs
