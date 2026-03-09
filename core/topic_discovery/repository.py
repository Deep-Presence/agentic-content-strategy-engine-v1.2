"""DB repository for Topic Discovery ORM operations.

Follows the project's SQLAlchemyRepository pattern:
- Repos call session.add() + session.flush() only
- session.commit() is NEVER called here — commit happens in the DI layer
"""
from __future__ import annotations

import uuid as _uuid
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import TDStatus, TopicAssignmentStatus
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
        """Find a discovery by effective_slug."""
        stmt = select(TopicDiscoveryModel).where(
            TopicDiscoveryModel.effective_slug == effective_slug
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

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
        from sqlalchemy import func

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
