"""Repository for structural signal aggregation queries.

Used by ``DbGapDataService`` to compute signal averages, correlations,
and cluster patterns via SQL instead of parsing 20MB JSON files.
"""
from __future__ import annotations

import uuid as _uuid
from typing import Any, Sequence

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.cache import UrlStructuralSignalsModel
from core.db.models.gap_analysis import RunCitationModel


class SignalRepository:
    """Signal aggregation queries across run citations + url_structural_signals."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_signal_averages(
        self, run_id: _uuid.UUID,
    ) -> dict[str, Any]:
        """Compute COALESCE(AVG(...), 0) for all 45 structural signals.

        Returns a dict keyed by signal column name with float values.
        """
        uss = UrlStructuralSignalsModel
        rc = RunCitationModel

        # Build COALESCE(AVG(col), 0) expressions for all numeric signals
        numeric_cols = [
            "word_count", "paragraph_count", "header_count", "list_item_count",
            "stat_count", "citation_count", "main_content_word_count",
            "sentence_count", "avg_paragraph_length", "median_paragraph_length",
            "max_paragraph_word_count", "avg_sentence_length",
            "avg_sentence_count_per_paragraph", "reading_level",
            "self_contained_ratio", "h1_count", "h2_count", "h3_count",
            "h4_count", "ordered_list_count", "unordered_list_count",
            "table_count", "definition_list_count", "blockquote_count",
            "code_block_count", "list_block_count", "bullets_per_list_block",
            "min_bullets_per_list", "data_point_count", "citation_density",
            "named_entity_density",
        ]
        boolean_cols = [
            "has_headers", "has_lists", "has_numbers",
            "has_faq_section", "has_definition_opening", "has_key_takeaways",
            "has_toc", "has_comparison_table", "has_step_by_step",
            "has_research_refs", "has_expert_quotes",
        ]

        avg_exprs = []
        labels = []
        for col_name in numeric_cols:
            col = getattr(uss, col_name)
            avg_exprs.append(func.coalesce(func.avg(cast(col, Float)), 0.0).label(col_name))
            labels.append(col_name)
        for col_name in boolean_cols:
            col = getattr(uss, col_name)
            # AVG of boolean = rate of True
            avg_exprs.append(
                func.coalesce(
                    func.avg(cast(case((col == True, 1), else_=0), Float)),  # noqa: E712
                    0.0,
                ).label(col_name)
            )
            labels.append(col_name)

        count_expr = func.count().label("total_citations")

        stmt = (
            select(*avg_exprs, count_expr)
            .select_from(rc)
            .join(uss, rc.url_enrichment_id == uss.url_enrichment_id)
            .where(rc.run_id == run_id)
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return {"total_citations": 0}

        data: dict[str, Any] = {}
        for label in labels:
            data[label] = float(getattr(row, label, 0) or 0)
        data["total_citations"] = int(row.total_citations or 0)
        return data

    async def get_signal_correlations(
        self,
        run_id: _uuid.UUID,
    ) -> dict[str, float]:
        """Compute Pearson correlation between each signal and best-paragraph similarity.

        Uses ``corr(signal, similarity)`` where similarity comes from
        ``run_paragraph_scores`` (rank=1 = best paragraph).
        Returns COALESCE(corr(...), 0) for each signal.
        """
        from core.db.models.embeddings import RunParagraphScoreModel

        uss = UrlStructuralSignalsModel
        rc = RunCitationModel
        rps = RunParagraphScoreModel

        # Signal columns to correlate
        signal_cols = [
            "word_count", "paragraph_count", "header_count", "list_item_count",
            "stat_count", "citation_count", "sentence_count",
            "avg_paragraph_length", "reading_level", "self_contained_ratio",
            "table_count", "code_block_count", "data_point_count",
            "citation_density", "named_entity_density",
        ]

        corr_exprs = []
        labels = []
        for col_name in signal_cols:
            col = getattr(uss, col_name)
            corr_exprs.append(
                func.coalesce(func.corr(cast(col, Float), rps.similarity), 0.0).label(col_name)
            )
            labels.append(col_name)

        stmt = (
            select(*corr_exprs)
            .select_from(rc)
            .join(uss, rc.url_enrichment_id == uss.url_enrichment_id)
            .join(rps, rps.run_citation_id == rc.id)
            .where(rc.run_id == run_id, rps.rank == 1)
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return {col: 0.0 for col in signal_cols}

        return {label: float(getattr(row, label, 0) or 0) for label in labels}

    async def get_cluster_patterns(
        self,
        run_id: _uuid.UUID,
    ) -> Sequence[dict[str, Any]]:
        """Compute boolean pattern rates per cluster.

        Returns list of dicts: {cluster_name, total, faq_rate, definition_rate, ...}.
        """
        uss = UrlStructuralSignalsModel
        rc = RunCitationModel

        boolean_patterns = [
            ("faq_rate", uss.has_faq_section),
            ("definition_rate", uss.has_definition_opening),
            ("key_takeaways_rate", uss.has_key_takeaways),
            ("toc_rate", uss.has_toc),
            ("comparison_table_rate", uss.has_comparison_table),
            ("step_by_step_rate", uss.has_step_by_step),
            ("research_refs_rate", uss.has_research_refs),
        ]

        pattern_exprs = []
        for label, col in boolean_patterns:
            pattern_exprs.append(
                (
                    cast(
                        func.sum(case((col == True, 1), else_=0)),  # noqa: E712
                        Float,
                    )
                    / func.nullif(func.count(), 0)
                ).label(label)
            )

        stmt = (
            select(
                rc.cluster_name,
                func.count().label("total"),
                *pattern_exprs,
            )
            .select_from(rc)
            .join(uss, rc.url_enrichment_id == uss.url_enrichment_id)
            .where(rc.run_id == run_id)
            .group_by(rc.cluster_name)
            .order_by(rc.cluster_name)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        patterns = []
        for row in rows:
            d: dict[str, Any] = {
                "cluster_name": row.cluster_name,
                "total": int(row.total or 0),
            }
            for label, _ in boolean_patterns:
                d[label] = float(getattr(row, label, 0) or 0)
            patterns.append(d)
        return patterns
