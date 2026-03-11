"""DB repositories for Topic Discovery ORM operations.

Follows the project's SQLAlchemyRepository pattern:
- Repos call session.add() + session.flush() only
- session.commit() is NEVER called here — commit happens in the DI layer

Four table-specific repositories:
- TopicDiscoveryRepository  — topic_discoveries
- TaxonomyTreeRepository    — taxonomy_trees
- SubdomainNodeRepository   — subdomain_nodes
- TopicAssignmentRepository — topic_assignments
"""
from __future__ import annotations

import uuid as _uuid
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import (
    BuyerStage,
    IntentType,
    RelevanceCell,
    TDStatus,
    TopicAssignmentStatus,
)
from core.db.models.topic_discovery import (
    SubdomainNodeModel,
    TaxonomyTreeModel,
    TopicAssignmentModel,
    TopicDiscoveryModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class TopicDiscoveryRepository(SQLAlchemyRepository[TopicDiscoveryModel]):
    """Repository for topic_discoveries table."""

    model_class = TopicDiscoveryModel

    async def get_by_effective_slug(
        self, effective_slug: str
    ) -> Optional[TopicDiscoveryModel]:
        """Find the latest discovery by effective_slug."""
        stmt = (
            select(TopicDiscoveryModel)
            .where(TopicDiscoveryModel.effective_slug == effective_slug)
            .order_by(TopicDiscoveryModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_company(
        self, company_id: _uuid.UUID | str
    ) -> Sequence[TopicDiscoveryModel]:
        """List discoveries for a company."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(TopicDiscoveryModel)
            .where(TopicDiscoveryModel.company_id == cid)
            .order_by(TopicDiscoveryModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self, discovery_id: _uuid.UUID | str, status: TDStatus
    ) -> Optional[TopicDiscoveryModel]:
        """Update the status of a discovery run."""
        return await self.update(discovery_id, status=status)

    async def update_versions(
        self,
        discovery_id: _uuid.UUID | str,
        *,
        taxonomy_version: Optional[int] = None,
        matrix_version: Optional[int] = None,
    ) -> Optional[TopicDiscoveryModel]:
        """Update taxonomy/matrix version counters."""
        kwargs: dict = {}
        if taxonomy_version is not None:
            kwargs["taxonomy_version"] = taxonomy_version
        if matrix_version is not None:
            kwargs["matrix_version"] = matrix_version
        if not kwargs:
            return await self.get_by_id(discovery_id)
        return await self.update(discovery_id, **kwargs)

    async def upsert_discovery(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        *,
        pipeline_run_id: _uuid.UUID | None = None,
        product_id: _uuid.UUID | None = None,
        domain_name: str | None = None,
        status: TDStatus = TDStatus.draft,
    ) -> TopicDiscoveryModel:
        """Find-or-create by (company_id, effective_slug). Updates if exists."""
        stmt = (
            select(TopicDiscoveryModel)
            .where(
                TopicDiscoveryModel.company_id == company_id,
                TopicDiscoveryModel.effective_slug == effective_slug,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing is not None:
            existing.status = status
            if pipeline_run_id is not None:
                existing.pipeline_run_id = pipeline_run_id
            if domain_name is not None:
                existing.domain_name = domain_name
            if product_id is not None:
                existing.product_id = product_id
            await self._session.flush()
            return existing

        discovery = TopicDiscoveryModel(
            company_id=company_id,
            effective_slug=effective_slug,
            pipeline_run_id=pipeline_run_id,
            product_id=product_id,
            domain_name=domain_name,
            status=status,
        )
        self._session.add(discovery)
        await self._session.flush()
        return discovery


class TaxonomyTreeRepository(SQLAlchemyRepository[TaxonomyTreeModel]):
    """Repository for taxonomy_trees table."""

    model_class = TaxonomyTreeModel

    async def get_by_discovery(
        self, discovery_id: _uuid.UUID | str, version: Optional[int] = None
    ) -> Optional[TaxonomyTreeModel]:
        """Get a taxonomy tree by discovery_id, optionally by version."""
        did = _uuid.UUID(str(discovery_id)) if isinstance(discovery_id, str) else discovery_id
        stmt = select(TaxonomyTreeModel).where(
            TaxonomyTreeModel.discovery_id == did
        )
        if version is not None:
            stmt = stmt.where(TaxonomyTreeModel.version == version)
        else:
            stmt = stmt.order_by(TaxonomyTreeModel.version.desc())
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_discovery(
        self, discovery_id: _uuid.UUID | str
    ) -> Sequence[TaxonomyTreeModel]:
        """List all taxonomy versions for a discovery."""
        did = _uuid.UUID(str(discovery_id)) if isinstance(discovery_id, str) else discovery_id
        stmt = (
            select(TaxonomyTreeModel)
            .where(TaxonomyTreeModel.discovery_id == did)
            .order_by(TaxonomyTreeModel.version.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert_taxonomy(
        self,
        discovery_id: _uuid.UUID,
        version: int,
        tree_json: dict,
        *,
        total_subdomains: int = 0,
        max_depth: int = 0,
        coverage_score: float | None = None,
        chao1_estimate: float | None = None,
        capture_recapture_est: dict | None = None,
        status: TDStatus = TDStatus.draft,
    ) -> TaxonomyTreeModel:
        """Find-or-create by (discovery_id, version). Updates if exists."""
        stmt = (
            select(TaxonomyTreeModel)
            .where(
                TaxonomyTreeModel.discovery_id == discovery_id,
                TaxonomyTreeModel.version == version,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing is not None:
            existing.tree_json = tree_json
            existing.total_subdomains = total_subdomains
            existing.max_depth = max_depth
            existing.coverage_score = coverage_score
            existing.chao1_estimate = chao1_estimate
            existing.capture_recapture_est = capture_recapture_est
            existing.status = status
            await self._session.flush()
            return existing

        taxonomy = TaxonomyTreeModel(
            discovery_id=discovery_id,
            version=version,
            tree_json=tree_json,
            total_subdomains=total_subdomains,
            max_depth=max_depth,
            coverage_score=coverage_score,
            chao1_estimate=chao1_estimate,
            capture_recapture_est=capture_recapture_est,
            status=status,
        )
        self._session.add(taxonomy)
        await self._session.flush()
        return taxonomy


class SubdomainNodeRepository(SQLAlchemyRepository[SubdomainNodeModel]):
    """Repository for subdomain_nodes table."""

    model_class = SubdomainNodeModel

    async def bulk_create(
        self, nodes: List[SubdomainNodeModel]
    ) -> List[SubdomainNodeModel]:
        """Bulk insert subdomain nodes."""
        self._session.add_all(nodes)
        await self._session.flush()
        return nodes

    async def get_by_taxonomy(
        self, taxonomy_id: _uuid.UUID | str
    ) -> Sequence[SubdomainNodeModel]:
        """Get all nodes for a taxonomy."""
        tid = _uuid.UUID(str(taxonomy_id)) if isinstance(taxonomy_id, str) else taxonomy_id
        stmt = (
            select(SubdomainNodeModel)
            .where(SubdomainNodeModel.taxonomy_id == tid)
            .order_by(SubdomainNodeModel.depth, SubdomainNodeModel.sort_order)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_root_nodes(
        self, taxonomy_id: _uuid.UUID | str
    ) -> Sequence[SubdomainNodeModel]:
        """Get root-level nodes (parent_id IS NULL) for a taxonomy."""
        tid = _uuid.UUID(str(taxonomy_id)) if isinstance(taxonomy_id, str) else taxonomy_id
        stmt = (
            select(SubdomainNodeModel)
            .where(
                SubdomainNodeModel.taxonomy_id == tid,
                SubdomainNodeModel.parent_id.is_(None),
            )
            .order_by(SubdomainNodeModel.sort_order)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def delete_by_taxonomy(self, taxonomy_id: _uuid.UUID) -> int:
        """Delete all nodes for a taxonomy. Returns deleted count."""
        stmt = delete(SubdomainNodeModel).where(
            SubdomainNodeModel.taxonomy_id == taxonomy_id
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount


class TopicAssignmentRepository(SQLAlchemyRepository[TopicAssignmentModel]):
    """Repository for topic_assignments table."""

    model_class = TopicAssignmentModel

    async def bulk_create(
        self, assignments: List[TopicAssignmentModel]
    ) -> List[TopicAssignmentModel]:
        """Bulk insert topic assignments."""
        self._session.add_all(assignments)
        await self._session.flush()
        return assignments

    async def get_by_discovery(
        self,
        discovery_id: _uuid.UUID | str,
        *,
        matrix_version: Optional[int] = None,
    ) -> Sequence[TopicAssignmentModel]:
        """Get assignments for a discovery, optionally filtered by matrix version."""
        did = _uuid.UUID(str(discovery_id)) if isinstance(discovery_id, str) else discovery_id
        stmt = select(TopicAssignmentModel).where(
            TopicAssignmentModel.discovery_id == did
        )
        if matrix_version is not None:
            stmt = stmt.where(
                TopicAssignmentModel.matrix_version == matrix_version
            )
        stmt = stmt.order_by(TopicAssignmentModel.priority_score.desc().nullslast())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_assignment_status(
        self,
        assignment_id: _uuid.UUID | str,
        status: TopicAssignmentStatus,
    ) -> Optional[TopicAssignmentModel]:
        """Update the lifecycle status of a single assignment."""
        return await self.update(assignment_id, status=status)

    async def count_by_discovery(
        self,
        discovery_id: _uuid.UUID | str,
        *,
        matrix_version: Optional[int] = None,
    ) -> int:
        """Count assignments for a discovery."""
        did = _uuid.UUID(str(discovery_id)) if isinstance(discovery_id, str) else discovery_id
        stmt = select(func.count(TopicAssignmentModel.id)).where(
            TopicAssignmentModel.discovery_id == did
        )
        if matrix_version is not None:
            stmt = stmt.where(
                TopicAssignmentModel.matrix_version == matrix_version
            )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_by_discovery(
        self,
        discovery_id: _uuid.UUID,
        *,
        matrix_version: int | None = None,
    ) -> int:
        """Delete assignments for a discovery (optionally scoped to version)."""
        stmt = delete(TopicAssignmentModel).where(
            TopicAssignmentModel.discovery_id == discovery_id
        )
        if matrix_version is not None:
            stmt = stmt.where(
                TopicAssignmentModel.matrix_version == matrix_version
            )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def list_paginated(
        self,
        discovery_id: _uuid.UUID,
        *,
        buyer_stage: BuyerStage | None = None,
        intent_type: IntentType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[Sequence[TopicAssignmentModel], int]:
        """Filtered + paginated query. Returns (items, total_count)."""
        base = select(TopicAssignmentModel).where(
            TopicAssignmentModel.discovery_id == discovery_id
        )
        if buyer_stage is not None:
            base = base.where(TopicAssignmentModel.buyer_stage == buyer_stage)
        if intent_type is not None:
            base = base.where(TopicAssignmentModel.intent_type == intent_type)

        # Count
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        items_stmt = (
            base.order_by(TopicAssignmentModel.priority_score.desc().nullslast())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._session.execute(items_stmt)
        items = items_result.scalars().all()

        return items, total

    async def get_stats(self, discovery_id: _uuid.UUID) -> dict:
        """Aggregate counts by buyer_stage, intent_type, relevance, status."""
        # Total
        total_stmt = select(func.count(TopicAssignmentModel.id)).where(
            TopicAssignmentModel.discovery_id == discovery_id
        )
        total = (await self._session.execute(total_stmt)).scalar() or 0

        # Group-by helpers
        async def _group_by(col):
            stmt = (
                select(col, func.count(TopicAssignmentModel.id))
                .where(TopicAssignmentModel.discovery_id == discovery_id)
                .group_by(col)
            )
            result = await self._session.execute(stmt)
            return {
                (label.value if hasattr(label, "value") else str(label)): count
                for label, count in result.all()
            }

        return {
            "total": total,
            "by_buyer_stage": await _group_by(TopicAssignmentModel.buyer_stage),
            "by_intent_type": await _group_by(TopicAssignmentModel.intent_type),
            "by_relevance": await _group_by(TopicAssignmentModel.relevance),
            "by_status": await _group_by(TopicAssignmentModel.status),
        }
