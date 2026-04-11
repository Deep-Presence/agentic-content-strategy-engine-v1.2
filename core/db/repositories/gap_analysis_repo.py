"""Repository for gap analysis domain models (query gaps, cluster specs)."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import GapClassification

# Severity rank: higher = worse gap
_CLASSIFICATION_RANK = {
    GapClassification.significant_gap: 4,
    GapClassification.gap_to_close: 3,
    GapClassification.roughly_equal: 2,
    GapClassification.company_wins: 1,
    GapClassification.no_data: 0,
}
from core.db.models.gap_analysis import (
    CentroidResultModel,
    ClusterProximityStatsModel,
    ClusterSpecModel,
    QueryExemplarModel,
    QueryGapModel,
    RunCitationModel,
    RunQueryModel,
    SpaResultModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class GapAnalysisRepository(SQLAlchemyRepository[QueryGapModel]):
    model_class = QueryGapModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def bulk_insert_query_gaps(
        self, gaps: list[dict[str, object]]
    ) -> Sequence[QueryGapModel]:
        """Insert multiple query gaps in a single flush.

        Each dict in *gaps* is unpacked as keyword arguments to
        ``QueryGapModel()``.
        """
        instances: list[QueryGapModel] = []
        for gap_data in gaps:
            instance = QueryGapModel(**gap_data)
            self._session.add(instance)
            instances.append(instance)
        await self._session.flush()
        return instances

    async def get_gaps_by_run(
        self,
        run_id: _uuid.UUID | str,
        *,
        classification: GapClassification | None = None,
        cluster_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[QueryGapModel]:
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = select(QueryGapModel).where(QueryGapModel.run_id == pk)

        if classification is not None:
            stmt = stmt.where(QueryGapModel.classification == classification)
        if cluster_name is not None:
            stmt = stmt.where(QueryGapModel.cluster_name == cluster_name)

        stmt = (
            stmt.order_by(QueryGapModel.gap.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_gap(
        self, gap_id: _uuid.UUID | str, **kwargs: object
    ) -> QueryGapModel | None:
        return await self.update(gap_id, **kwargs)

    async def get_cluster_specs(
        self, run_id: _uuid.UUID | str
    ) -> Sequence[ClusterSpecModel]:
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(ClusterSpecModel)
            .where(ClusterSpecModel.run_id == pk)
            .order_by(ClusterSpecModel.cluster_name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Phase 3 additions ─────────────────────────────────────────────

    async def count_gaps_by_run(
        self, run_id: _uuid.UUID | str,
    ) -> int:
        """Total gap count for a run."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = select(func.count()).select_from(QueryGapModel).where(
            QueryGapModel.run_id == pk,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_classification_counts(
        self, run_id: _uuid.UUID | str,
    ) -> dict[str, int]:
        """Count gaps per classification for a run."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(
                QueryGapModel.classification,
                func.count().label("cnt"),
            )
            .where(QueryGapModel.run_id == pk)
            .group_by(QueryGapModel.classification)
        )
        result = await self._session.execute(stmt)
        return {
            str(row.classification.value): int(row.cnt)
            for row in result.all()
        }

    async def get_spa_results(
        self, run_id: _uuid.UUID | str,
    ) -> Sequence[SpaResultModel]:
        """Get SPA results for a run."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(SpaResultModel)
            .where(SpaResultModel.run_id == pk)
            .order_by(SpaResultModel.cluster_name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_centroid_results(
        self, run_id: _uuid.UUID | str,
    ) -> Sequence[CentroidResultModel]:
        """Get centroid distances for a run."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(CentroidResultModel)
            .where(CentroidResultModel.run_id == pk)
            .order_by(CentroidResultModel.cluster_name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Phase 4 bulk insert methods ──────────────────────────────────────

    async def bulk_insert_run_queries(
        self, queries: list[dict[str, object]]
    ) -> Sequence[RunQueryModel]:
        """Insert multiple run queries in a single flush."""
        instances = [RunQueryModel(**q) for q in queries]
        self._session.add_all(instances)
        await self._session.flush()
        return instances

    async def bulk_insert_run_citations(
        self, citations: list[dict[str, object]]
    ) -> Sequence[RunCitationModel]:
        """Insert multiple run citations in a single flush.

        Caller MUST ensure the corresponding RunQueryModel rows exist
        (composite FK constraint on run_id + query_id).
        """
        instances = [RunCitationModel(**c) for c in citations]
        self._session.add_all(instances)
        await self._session.flush()
        return instances

    async def bulk_insert_cluster_specs(
        self, specs: list[dict[str, object]]
    ) -> Sequence[ClusterSpecModel]:
        """Insert multiple cluster specs in a single flush."""
        instances = [ClusterSpecModel(**s) for s in specs]
        self._session.add_all(instances)
        await self._session.flush()
        return instances

    async def bulk_insert_spa_results(
        self, results: list[dict[str, object]]
    ) -> Sequence[SpaResultModel]:
        """Insert multiple SPA results in a single flush."""
        instances = [SpaResultModel(**r) for r in results]
        self._session.add_all(instances)
        await self._session.flush()
        return instances

    async def bulk_insert_centroid_results(
        self, results: list[dict[str, object]]
    ) -> Sequence[CentroidResultModel]:
        """Insert multiple centroid results in a single flush."""
        instances = [CentroidResultModel(**r) for r in results]
        self._session.add_all(instances)
        await self._session.flush()
        return instances

    async def bulk_insert_query_exemplars(
        self, exemplars: list[dict[str, object]]
    ) -> Sequence[QueryExemplarModel]:
        """Insert multiple query exemplars in a single flush."""
        instances = [QueryExemplarModel(**e) for e in exemplars]
        self._session.add_all(instances)
        await self._session.flush()
        return instances

    # ── Content Performance: queries covered per page ─────────────────────

    async def count_queries_targeting_inventory_batch(
        self,
        company_id: _uuid.UUID,
    ) -> dict[str, int]:
        """Count gap-analysis queries targeting each published URL.

        Joins query_gaps → content_pieces (via targeted_by_content_id FK).
        Returns {published_url: count} for all targeted content in this company.
        The caller normalises URLs and matches to content_inventory rows.
        """
        from core.db.models.content import ContentPieceModel

        stmt = (
            select(
                ContentPieceModel.published_url,
                func.count(func.distinct(QueryGapModel.id)).label("cnt"),
            )
            .join(
                ContentPieceModel,
                QueryGapModel.targeted_by_content_id == ContentPieceModel.id,
            )
            .where(
                ContentPieceModel.company_id == company_id,
                QueryGapModel.targeted_by_content_id.isnot(None),
            )
            .group_by(ContentPieceModel.published_url)
        )

        result = await self._session.execute(stmt)
        return {
            row.published_url: int(row.cnt)
            for row in result.all()
            if row.published_url
        }

    async def get_cited_exemplar_dates_for_inventory_url(
        self,
        company_id: _uuid.UUID,
        inventory_url: str,
        *,
        normalized_url: str | None = None,
    ) -> list[datetime]:
        """Return cited exemplar modified/published datetimes for one content URL.

        Matches targeted content by published URL and returns the exemplar's best
        freshness date (modified first, then published) from url_enrichment_cache.
        """
        from core.db.models.cache import UrlEnrichmentCacheModel
        from core.db.models.content import ContentPieceModel

        candidates = {
            inventory_url,
            normalized_url or "",
        }
        cleaned_candidates: set[str] = set()
        for url in candidates:
            if not url:
                continue
            cleaned_candidates.add(url)
            if url.endswith("/"):
                cleaned_candidates.add(url.rstrip("/"))
            else:
                cleaned_candidates.add(f"{url}/")

        stmt = (
            select(
                UrlEnrichmentCacheModel.modified_at,
                UrlEnrichmentCacheModel.published_at,
            )
            .join(
                QueryExemplarModel,
                QueryExemplarModel.url_enrichment_id == UrlEnrichmentCacheModel.id,
            )
            .join(
                QueryGapModel,
                QueryGapModel.id == QueryExemplarModel.query_gap_id,
            )
            .join(
                ContentPieceModel,
                ContentPieceModel.id == QueryGapModel.targeted_by_content_id,
            )
            .where(
                ContentPieceModel.company_id == company_id,
                ContentPieceModel.published_url.in_(sorted(cleaned_candidates)),
            )
        )
        result = await self._session.execute(stmt)
        benchmark_dates: list[datetime] = []
        for row in result.all():
            best_date = row.modified_at or row.published_at
            if best_date is not None:
                benchmark_dates.append(best_date)
        return benchmark_dates

    # ── Embedding Lab: cluster profiles & territory gaps ──────────────────

    async def get_all_cluster_metrics(
        self, run_id: _uuid.UUID | str,
    ) -> Sequence[Any]:
        """Per-cluster: total_citations, unique_domains, company_citations."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(
                RunCitationModel.cluster_name,
                func.count().label("total_citations"),
                func.count(func.distinct(RunCitationModel.domain)).label("unique_domains"),
                func.count().filter(
                    RunCitationModel.is_company_citation.is_(True)
                ).label("company_citations"),
            )
            .where(RunCitationModel.run_id == pk)
            .group_by(RunCitationModel.cluster_name)
        )
        result = await self._session.execute(stmt)
        return result.all()

    async def get_cluster_domain_leaderboard(
        self, run_id: _uuid.UUID | str, cluster_name: str, limit: int = 15,
    ) -> Sequence[Any]:
        """Top domains by citation count for a cluster."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(
                RunCitationModel.domain,
                func.count().label("citations"),
                func.bool_or(RunCitationModel.is_company_citation).label("is_company"),
            )
            .where(
                RunCitationModel.run_id == pk,
                RunCitationModel.cluster_name == cluster_name,
            )
            .group_by(RunCitationModel.domain)
            .order_by(func.count().desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.all()

    async def get_cluster_engine_breakdown(
        self, run_id: _uuid.UUID | str, cluster_name: str,
    ) -> Sequence[Any]:
        """Citation count per engine for a cluster."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(
                RunCitationModel.engine,
                func.count().label("citations"),
            )
            .where(
                RunCitationModel.run_id == pk,
                RunCitationModel.cluster_name == cluster_name,
            )
            .group_by(RunCitationModel.engine)
        )
        result = await self._session.execute(stmt)
        return result.all()

    async def get_cluster_proximity_stats(
        self, run_id: _uuid.UUID | str,
    ) -> Sequence[ClusterProximityStatsModel]:
        """Per-cluster (and global) proximity statistics."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(ClusterProximityStatsModel)
            .where(ClusterProximityStatsModel.run_id == pk)
            .order_by(ClusterProximityStatsModel.cluster_name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_territory_gaps_with_signals(
        self, run_id: _uuid.UUID | str,
    ) -> Sequence[QueryGapModel]:
        """All gaps with exemplars → url_enrichment → structural_signals."""
        from sqlalchemy.orm import selectinload

        from core.db.models.cache import UrlEnrichmentCacheModel

        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(QueryGapModel)
            .where(QueryGapModel.run_id == pk)
            .options(
                selectinload(QueryGapModel.exemplars)
                .joinedload(QueryExemplarModel.url_enrichment)
                .joinedload(UrlEnrichmentCacheModel.structural_signals)
            )
            .order_by(QueryGapModel.gap.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().unique().all()

    async def get_cross_cluster_domains(
        self, run_id: _uuid.UUID | str,
    ) -> set[str]:
        """Domains appearing in 2+ clusters (mindshare indicator)."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(RunCitationModel.domain)
            .where(RunCitationModel.run_id == pk)
            .group_by(RunCitationModel.domain)
            .having(func.count(func.distinct(RunCitationModel.cluster_name)) > 1)
        )
        result = await self._session.execute(stmt)
        return {row[0] for row in result.all() if row[0]}

    async def bulk_insert_cluster_proximity_stats(
        self, rows: list[dict[str, object]],
    ) -> Sequence[ClusterProximityStatsModel]:
        """Insert multiple cluster proximity stats in a single flush."""
        instances = [ClusterProximityStatsModel(**r) for r in rows]
        self._session.add_all(instances)
        await self._session.flush()
        return instances

    async def get_gaps_paginated(
        self,
        run_id: _uuid.UUID | str,
        *,
        cluster: str | None = None,
        classification: str | None = None,
        search: str | None = None,
        sort_by: str = "gap",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 15,
    ) -> dict[str, Any]:
        """Enhanced paginated query with search, filter, sort.

        Returns {items: [...], total: int, page: int, page_size: int, total_pages: int}.
        """
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        base = select(QueryGapModel).where(QueryGapModel.run_id == pk)

        if cluster:
            base = base.where(
                (QueryGapModel.cluster_name == cluster)
                | (QueryGapModel.cluster_id == cluster)
            )
        if classification:
            try:
                cls = GapClassification(classification)
                base = base.where(QueryGapModel.classification == cls)
            except ValueError:
                pass  # invalid classification — skip filter
        if search:
            base = base.where(QueryGapModel.query_text.ilike(f"%{search}%"))

        # Count total (before pagination)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one())

        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))  # Clamp to valid range

        # Sort — severity-ranked for classification, column-based otherwise
        if sort_by == "classification":
            severity_expr = case(
                *[
                    (QueryGapModel.classification == cls, rank)
                    for cls, rank in _CLASSIFICATION_RANK.items()
                ],
                else_=0,
            )
            order = severity_expr.desc() if sort_dir == "desc" else severity_expr.asc()
        else:
            sort_col = getattr(QueryGapModel, sort_by, QueryGapModel.gap)
            order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
        base = base.order_by(order)

        # Paginate
        offset = (page - 1) * page_size
        base = base.offset(offset).limit(page_size)

        result = await self._session.execute(base)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
