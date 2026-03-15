"""Context Router — two-phase data extraction for the v1.3 content pipeline.

This is a **pure data transformation module** — no LLM calls, no I/O,
no imports from prompts/ or pipeline modules.

Phase 1 (Scorecard Extraction):
  Extracts a lightweight PlannerScorecard (~11K tokens) from the full
  gap analysis output. Used by the Strategic Planner for triage.

Phase 2 (Full Context Extraction):
  Extracts complete QueryGap data for ONLY the approved queries (4-6
  out of 200). Used by the Brief Builder for content architecture.

Design principles:
  - Each agent gets exactly the context it needs, nothing more
  - The HITL boundary is the natural context loading boundary
  - Data extraction is independent of prompt formatting
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from core.models.content_generation_v13 import (
    ClusterSummary,
    PlannerScorecard,
    QueryScorecard,
    TopicSelection,
    WorkerQueryContext,
)
from core.gap_analysis.topic_cluster_map import get_cluster_mapping, get_cluster_name
from core.models.topic_discovery import TopicAssignment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 1: Scorecard Extraction
# ---------------------------------------------------------------------------


def extract_scorecard(
    analysis_json: Dict[str, Any],
    company_context_md: str = "",
    product_focus: Optional[str] = None,
) -> PlannerScorecard:
    """Extract a lightweight scorecard from the full gap analysis output.

    Iterates over ``analysis_json["gaps"]`` and ``analysis_json["cluster_specs"]``
    to produce a summary that fits in ~11K tokens.

    Args:
        analysis_json: The full AnalysisResult dict (from analysis.json).
        company_context_md: Company context markdown (first ~600 chars used).
        product_focus: Optional product focus description.

    Returns:
        PlannerScorecard ready for the Strategic Planner.
    """
    gaps: List[Dict[str, Any]] = analysis_json.get("gaps", [])
    cluster_specs: List[Dict[str, Any]] = analysis_json.get("cluster_specs", [])

    # --- Per-query scorecards ---
    query_scorecards: List[QueryScorecard] = []
    for gap in gaps:
        exemplars = gap.get("top_cited_exemplars", [])
        content_brief = gap.get("content_brief")
        query_scorecards.append(
            QueryScorecard(
                query_id=gap.get("query_id", ""),
                query_text=gap.get("query_text", ""),
                cluster_name=gap.get("cluster_name", "") or "",
                gap=gap.get("gap") or 0.0,
                best_company_similarity=gap.get("best_company_similarity") or 0.0,
                avg_citation_similarity=gap.get("avg_citation_similarity") or 0.0,
                interpretation=gap.get("interpretation", "") or "",
                exemplar_count=len(exemplars),
                has_brief=content_brief is not None,
                company_cited=gap.get("company_cited", False),
            )
        )

    # --- Per-cluster summaries ---
    # Build from cluster_specs first (for dominant type fields)
    spec_by_name: Dict[str, Dict[str, Any]] = {
        spec.get("cluster_name", ""): spec for spec in cluster_specs
    }

    # Aggregate gap statistics per cluster from query scorecards
    cluster_groups: Dict[str, List[QueryScorecard]] = defaultdict(list)
    for qs in query_scorecards:
        cluster_groups[qs.cluster_name].append(qs)

    cluster_summaries: List[ClusterSummary] = []
    for cluster_name, queries in sorted(cluster_groups.items()):
        gaps_values = [q.gap for q in queries if q.gap != 0.0]
        sig_count = sum(
            1 for q in queries if q.interpretation == "significant_gap"
        )
        spec = spec_by_name.get(cluster_name, {})
        cluster_summaries.append(
            ClusterSummary(
                cluster_name=cluster_name,
                query_count=len(queries),
                avg_gap=sum(gaps_values) / len(gaps_values) if gaps_values else 0.0,
                max_gap=max(gaps_values) if gaps_values else 0.0,
                significant_gap_count=sig_count,
                dominant_content_type=spec.get("dominant_content_type"),
                dominant_authority_type=spec.get("dominant_authority_type"),
            )
        )

    # --- Company summary (first ~600 chars) ---
    company_summary = company_context_md[:600].strip() if company_context_md else ""

    scorecard = PlannerScorecard(
        queries=query_scorecards,
        clusters=cluster_summaries,
        company_summary=company_summary,
        product_focus=product_focus,
        total_queries=len(query_scorecards),
        total_clusters=len(cluster_summaries),
    )

    logger.info(
        "Extracted scorecard: %d queries, %d clusters",
        scorecard.total_queries,
        scorecard.total_clusters,
    )
    return scorecard


# ---------------------------------------------------------------------------
# Phase 2: Full Context Extraction
# ---------------------------------------------------------------------------


def extract_worker_context(
    analysis_json: Dict[str, Any],
    approved_query_ids: List[str],
) -> Dict[str, WorkerQueryContext]:
    """Extract full context for approved queries only.

    Filters the gaps list to approved IDs, pulls complete QueryGap data
    including top_cited_exemplars with structural_signals, and matches
    to ClusterContentSpec by cluster_name.

    Args:
        analysis_json: The full AnalysisResult dict (from analysis.json).
        approved_query_ids: List of query_id values approved at HITL-1.

    Returns:
        Dict mapping query_id → WorkerQueryContext with full detail.
    """
    gaps: List[Dict[str, Any]] = analysis_json.get("gaps", [])
    cluster_specs: List[Dict[str, Any]] = analysis_json.get("cluster_specs", [])

    # Index cluster specs by name for O(1) lookup
    spec_by_name: Dict[str, Dict[str, Any]] = {
        spec.get("cluster_name", ""): spec for spec in cluster_specs
    }

    # Index gaps by query_id
    gap_by_id: Dict[str, Dict[str, Any]] = {
        gap.get("query_id", ""): gap for gap in gaps
    }

    approved_set = set(approved_query_ids)
    contexts: Dict[str, WorkerQueryContext] = {}

    for query_id in approved_query_ids:
        gap = gap_by_id.get(query_id)
        if gap is None:
            logger.warning(
                "Approved query_id %r not found in analysis gaps", query_id
            )
            continue

        cluster_name = gap.get("cluster_name", "") or ""
        cluster_spec = spec_by_name.get(cluster_name, {})
        exemplars = gap.get("top_cited_exemplars", [])
        content_brief = gap.get("content_brief")

        contexts[query_id] = WorkerQueryContext(
            query_gap=gap,
            cluster_spec=cluster_spec,
            exemplars=exemplars,
            gap_content_brief=content_brief,
            company_best_text=gap.get("best_company_unit_text", "") or "",
            company_best_url=gap.get("best_company_url", "") or "",
        )

    logger.info(
        "Extracted full context for %d/%d approved queries",
        len(contexts),
        len(approved_query_ids),
    )
    return contexts


# ---------------------------------------------------------------------------
# Scorecard Formatting (for prompt construction)
# ---------------------------------------------------------------------------


def format_scorecard_as_markdown(scorecard: PlannerScorecard) -> str:
    """Format a PlannerScorecard as compact markdown tables.

    Tables are more token-efficient than JSON for tabular data because
    they avoid repeated keys.

    Args:
        scorecard: The extracted scorecard.

    Returns:
        Markdown string with cluster overview + per-query table.
    """
    lines: List[str] = []

    # --- Company summary ---
    if scorecard.company_summary:
        lines.append("## Company Summary")
        lines.append(scorecard.company_summary)
        lines.append("")

    if scorecard.product_focus:
        lines.append("## Product Focus")
        lines.append(scorecard.product_focus)
        lines.append("")

    # --- Cluster overview table ---
    lines.append("## Cluster Overview")
    lines.append(
        "| Cluster | Queries | Avg Gap | Max Gap | Sig. Gaps | Content Type | Authority Type |"
    )
    lines.append(
        "|---------|---------|---------|---------|-----------|--------------|----------------|"
    )
    for c in scorecard.clusters:
        lines.append(
            f"| {c.cluster_name} | {c.query_count} | {c.avg_gap:.3f} "
            f"| {c.max_gap:.3f} | {c.significant_gap_count} "
            f"| {c.dominant_content_type or '-'} "
            f"| {c.dominant_authority_type or '-'} |"
        )
    lines.append("")

    # --- Per-query table ---
    lines.append("## Query Scorecards")
    lines.append(
        "| ID | Query | Cluster | Gap | Co. Sim | Cit. Sim | Class | Exemplars | Brief | Cited |"
    )
    lines.append(
        "|----|-------|---------|-----|---------|----------|-------|-----------|-------|-------|"
    )
    for q in scorecard.queries:
        # Truncate query text to 80 chars for readability
        qtext = q.query_text[:80] + ("..." if len(q.query_text) > 80 else "")
        lines.append(
            f"| {q.query_id} | {qtext} | {q.cluster_name} "
            f"| {q.gap:.3f} | {q.best_company_similarity:.3f} "
            f"| {q.avg_citation_similarity:.3f} | {q.interpretation} "
            f"| {q.exemplar_count} | {'Y' if q.has_brief else 'N'} "
            f"| {'Y' if q.company_cited else 'N'} |"
        )
    lines.append("")

    lines.append(f"**Total queries:** {scorecard.total_queries}")
    lines.append(f"**Total clusters:** {scorecard.total_clusters}")

    return "\n".join(lines)


def format_worker_context_as_markdown(
    context: WorkerQueryContext,
) -> str:
    """Format a WorkerQueryContext for the Brief Builder prompt.

    Structured sections with clear headers for each data component.

    Args:
        context: Full context for one approved query.

    Returns:
        Markdown string with gap data, exemplars, and cluster spec.
    """
    lines: List[str] = []
    gap = context.query_gap

    # --- Query overview ---
    lines.append("## Query Gap Analysis")
    lines.append(f"- **Query ID:** {gap.get('query_id', '')}")
    lines.append(f"- **Query Text:** {gap.get('query_text', '')}")
    lines.append(f"- **Cluster:** {gap.get('cluster_name', '')}")
    lines.append(f"- **Gap Score:** {gap.get('gap', 0):.3f}")
    lines.append(f"- **Company Similarity:** {gap.get('best_company_similarity', 0):.3f}")
    lines.append(f"- **Citation Similarity:** {gap.get('avg_citation_similarity', 0):.3f}")
    lines.append(f"- **Classification:** {gap.get('interpretation', '')}")
    company_cited = gap.get("company_cited", False)
    if company_cited:
        platforms = gap.get("company_cited_platforms", [])
        lines.append(f"- **Company Already Cited:** Yes (on {', '.join(platforms)})")
    else:
        lines.append("- **Company Already Cited:** No")
    lines.append("")

    # --- Company's current content ---
    if context.company_best_text:
        lines.append("## Company's Current Best Content")
        if context.company_best_url:
            lines.append(f"- **Source URL:** {context.company_best_url}")
        lines.append(context.company_best_text[:500])
        lines.append("")

    # --- Company page structural signals ---
    company_signals = gap.get("best_company_structural_signals")
    if company_signals:
        lines.append("## Company Page Structure")
        key_signals = [
            "word_count", "header_count", "h2_count", "h3_count",
            "list_item_count", "table_count", "has_faq_section",
            "has_definition_opening", "has_key_takeaways", "has_step_by_step",
            "paragraph_count", "avg_paragraph_length", "reading_level",
            "stat_count", "citation_count", "authority_type", "content_type",
        ]
        for key in key_signals:
            if key in company_signals:
                lines.append(f"- **{key}:** {company_signals[key]}")
        lines.append("")

    # --- Content brief targets ---
    if context.gap_content_brief:
        lines.append("## Pre-Computed Content Brief Targets")
        brief = context.gap_content_brief
        for key, val in sorted(brief.items()):
            lines.append(f"- **{key}:** {val}")
        lines.append("")

    # --- Exemplars ---
    if context.exemplars:
        lines.append("## Top-Cited Exemplars")
        for i, ex in enumerate(context.exemplars, 1):
            lines.append(f"### Exemplar {i}")
            lines.append(f"- **URL:** {ex.get('url', '')}")
            lines.append(f"- **Similarity:** {ex.get('similarity', 0):.3f}")
            lines.append(f"- **Authority Type:** {ex.get('authority_type', '')}")
            snippet = ex.get("snippet", "")
            if snippet:
                lines.append(f"- **Snippet:** {snippet[:200]}")

            signals = ex.get("structural_signals", {})
            if signals:
                lines.append("- **Structural Signals:**")
                for sk, sv in sorted(signals.items()):
                    lines.append(f"  - {sk}: {sv}")
            lines.append("")

    # --- Cluster spec ---
    if context.cluster_spec:
        lines.append("## Cluster Content Specification")
        spec = context.cluster_spec
        for key, val in sorted(spec.items()):
            lines.append(f"- **{key}:** {val}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Topic Discovery Context Extraction
# ---------------------------------------------------------------------------


def extract_topic_contexts(
    analysis_json: Dict[str, Any],
    topic_query_map: Dict[str, List[str]],
) -> Dict[str, WorkerQueryContext]:
    """Extract per-topic WorkerQueryContext from topic-scoped analysis.

    For each topic, aggregates exemplars across all its queries and uses
    the highest-gap query as the primary context. Returns dict keyed by
    the FIRST query_id of each topic (compat with build_briefs_parallel
    which does ``contexts[topic.query_ids[0]]``).

    Args:
        analysis_json: The full AnalysisResult dict (from analysis.json).
        topic_query_map: Maps topic_assignment_id → [query_ids].

    Returns:
        Dict mapping first_query_id → WorkerQueryContext.
    """
    gaps: List[Dict[str, Any]] = analysis_json.get("gaps", [])
    cluster_specs: List[Dict[str, Any]] = analysis_json.get("cluster_specs", [])

    gap_by_id: Dict[str, Dict[str, Any]] = {
        g.get("query_id", ""): g for g in gaps
    }
    spec_by_name: Dict[str, Dict[str, Any]] = {
        s.get("cluster_name", ""): s for s in cluster_specs
    }

    contexts: Dict[str, WorkerQueryContext] = {}

    for topic_id, query_ids in topic_query_map.items():
        if not query_ids:
            continue

        # Gather all gaps for this topic
        topic_gaps = [gap_by_id[qid] for qid in query_ids if qid in gap_by_id]
        if not topic_gaps:
            continue

        # Use highest-gap query as primary
        primary_gap = max(topic_gaps, key=lambda g: g.get("gap") or 0.0)

        # Aggregate exemplars across all queries (dedupe by URL)
        all_exemplars: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        for g in topic_gaps:
            for ex in g.get("top_cited_exemplars", []):
                url = ex.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_exemplars.append(ex)

        # Use primary gap's cluster for spec lookup
        cluster_name = primary_gap.get("cluster_name", "") or ""
        cluster_spec = spec_by_name.get(cluster_name, {})

        # Key by first query_id (compat with build_briefs_parallel)
        key_qid = query_ids[0]
        contexts[key_qid] = WorkerQueryContext(
            query_gap=primary_gap,
            cluster_spec=cluster_spec,
            exemplars=all_exemplars[:5],  # Cap at 5 exemplars
            gap_content_brief=primary_gap.get("content_brief"),
            company_best_text=primary_gap.get("best_company_unit_text", "") or "",
            company_best_url=primary_gap.get("best_company_url", "") or "",
        )

    logger.info(
        "Extracted topic contexts for %d topics (%d total query groups)",
        len(contexts), len(topic_query_map),
    )
    return contexts


def topic_assignment_to_selection(
    assignment: TopicAssignment,
    query_ids: List[str],
    query_texts: List[str],
    rank: int = 0,
) -> TopicSelection:
    """Convert a TopicAssignment → TopicSelection for Brief Builder.

    Maps TD metadata into the format the Brief Builder expects,
    bypassing the Strategic Planner.

    Args:
        assignment: The approved TopicAssignment from TD.
        query_ids: Query IDs generated for this assignment.
        query_texts: Corresponding query text strings.
        rank: Priority rank (0 = highest).

    Returns:
        TopicSelection ready for the Brief Builder.
    """
    # Map buyer stage to estimated impact
    impact_map = {"bofu": "high", "mofu": "medium", "tofu": "medium"}
    impact = impact_map.get(assignment.buyer_stage.value, "medium")

    # Build rationale from TD metadata
    rationale = (
        f"Topic Discovery: {assignment.subdomain_name} → "
        f"{assignment.buyer_stage.value}/{assignment.intent_type.value} "
        f"for {assignment.audience_segment}. "
        f"Priority score: {assignment.priority_score:.2f}."
    )

    # L2 fix: derive cluster_name from buyer_stage × intent_type mapping
    cluster_name = ""
    mapping = get_cluster_mapping(
        assignment.buyer_stage.value, assignment.intent_type.value,
    )
    if mapping and mapping.primary:
        cluster_name = get_cluster_name(mapping.primary[0])

    return TopicSelection(
        rank=rank,
        query_ids=query_ids,
        query_texts=query_texts,
        cluster_name=cluster_name,
        rationale=rationale,
        consolidation_note=f"TD topic: {assignment.topic_text}",
        estimated_impact=impact,
    )
