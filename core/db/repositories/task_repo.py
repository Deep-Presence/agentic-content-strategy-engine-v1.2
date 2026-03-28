"""Repository for ApiTaskModel — CRUD + domain queries."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.api_tasks import ApiTaskModel
from core.db.repositories.base import SQLAlchemyRepository


class TaskRepository(SQLAlchemyRepository[ApiTaskModel]):
    """Async repository for api_tasks table."""

    model_class = ApiTaskModel

    async def get_by_task_id(self, task_id: str) -> Optional[ApiTaskModel]:
        """Look up a task by its API-facing UUID string."""
        stmt = select(ApiTaskModel).where(ApiTaskModel.task_id == task_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_task(self, **kwargs: Any) -> ApiTaskModel:
        """Insert a new task row."""
        instance = ApiTaskModel(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def update_by_task_id(
        self, task_id: str, **kwargs: Any
    ) -> Optional[ApiTaskModel]:
        """Update a task by its API-facing task_id."""
        instance = await self.get_by_task_id(task_id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self._session.flush()
        return instance

    async def list_tasks(
        self,
        pipeline: Optional[str] = None,
        status: Optional[str] = None,
        company_slug: Optional[str] = None,
        product_slug: Optional[str] = None,
    ) -> Sequence[ApiTaskModel]:
        """List tasks with optional filters."""
        stmt = select(ApiTaskModel).order_by(ApiTaskModel.created_at.desc())
        if pipeline is not None:
            stmt = stmt.where(ApiTaskModel.pipeline == pipeline)
        if status is not None:
            stmt = stmt.where(ApiTaskModel.status == status)
        if company_slug is not None:
            stmt = stmt.where(ApiTaskModel.company_slug == company_slug)
        if product_slug is not None:
            stmt = stmt.where(ApiTaskModel.product_slug == product_slug)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def find_active_by_slug(self, slug: str) -> Sequence[ApiTaskModel]:
        """Find tasks that are actively running for a given effective_slug."""
        active_statuses = {"running", "pending_approval"}
        stmt = (
            select(ApiTaskModel)
            .where(
                ApiTaskModel.effective_slug == slug,
                ApiTaskModel.status.in_(active_statuses),
            )
            .order_by(ApiTaskModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def mark_orphans_failed(self) -> int:
        """Mark all non-terminal tasks as failed_restart.

        Called on startup to recover from unclean shutdowns.
        Returns the number of rows updated.
        """
        non_terminal = {"running", "pending_approval"}
        stmt = (
            update(ApiTaskModel)
            .where(ApiTaskModel.status.in_(non_terminal))
            .values(
                status="failed_restart",
                error="Process restarted — task was in-flight",
                updated_at=datetime.now(timezone.utc),
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def mark_worker_orphans_failed(
        self, worker_id: str
    ) -> Tuple[int, List[str]]:
        """Mark non-terminal tasks belonging to this worker as failed_restart.

        Also claims NULL worker_id tasks (legacy rows from before worker
        tracking was added). This ensures old tasks are recovered by the
        first worker to start after the upgrade.

        Returns ``(count, list_of_orphan_task_ids)`` — the task IDs are used
        for scoped semaphore cleanup.
        """
        non_terminal = {"running", "pending_approval"}
        stmt = (
            update(ApiTaskModel)
            .where(
                ApiTaskModel.status.in_(non_terminal),
                or_(
                    ApiTaskModel.worker_id == worker_id,
                    ApiTaskModel.worker_id.is_(None),
                ),
            )
            .values(
                status="failed_restart",
                error="Process restarted — task was in-flight",
                updated_at=datetime.now(timezone.utc),
            )
            .returning(ApiTaskModel.task_id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        orphan_ids = [row[0] for row in result.fetchall()]
        return len(orphan_ids), orphan_ids
