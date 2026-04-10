"""Repositories for durable Content Engine batch/topic runs."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.content_engine_runs import (
    ContentEngineBatchRunModel,
    ContentEngineTopicEventModel,
    ContentEngineTopicRunModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class ContentEngineBatchRunRepository(SQLAlchemyRepository[ContentEngineBatchRunModel]):
    model_class = ContentEngineBatchRunModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_slug(
        self,
        effective_slug: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ContentEngineBatchRunModel]:
        stmt = (
            select(ContentEngineBatchRunModel)
            .where(ContentEngineBatchRunModel.effective_slug == effective_slug)
            .order_by(ContentEngineBatchRunModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class ContentEngineTopicRunRepository(SQLAlchemyRepository[ContentEngineTopicRunModel]):
    model_class = ContentEngineTopicRunModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def bulk_create(
        self,
        runs: list[ContentEngineTopicRunModel],
    ) -> list[ContentEngineTopicRunModel]:
        self._session.add_all(runs)
        await self._session.flush()
        return runs

    async def list_by_slug(
        self,
        effective_slug: str,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[ContentEngineTopicRunModel]:
        stmt = (
            select(ContentEngineTopicRunModel)
            .where(ContentEngineTopicRunModel.effective_slug == effective_slug)
            .order_by(ContentEngineTopicRunModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_assignment_ids(
        self,
        assignment_ids: list[_uuid.UUID],
        *,
        ga_run_id: _uuid.UUID | None = None,
        pipeline_task_id: str | None = None,
        effective_slug: str | None = None,
    ) -> Sequence[ContentEngineTopicRunModel]:
        if not assignment_ids:
            return []
        stmt = select(ContentEngineTopicRunModel).where(
            ContentEngineTopicRunModel.topic_assignment_id.in_(assignment_ids)
        )
        if ga_run_id is not None:
            stmt = stmt.where(ContentEngineTopicRunModel.ga_run_id == ga_run_id)
        if pipeline_task_id is not None:
            stmt = stmt.where(ContentEngineTopicRunModel.pipeline_task_id == pipeline_task_id)
        if effective_slug is not None:
            stmt = stmt.where(ContentEngineTopicRunModel.effective_slug == effective_slug)
        stmt = stmt.order_by(ContentEngineTopicRunModel.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_brief_ids(
        self,
        brief_ids: list[str],
        *,
        pipeline_task_id: str | None = None,
        effective_slug: str | None = None,
    ) -> Sequence[ContentEngineTopicRunModel]:
        if not brief_ids:
            return []
        stmt = select(ContentEngineTopicRunModel).where(
            ContentEngineTopicRunModel.brief_id.in_(brief_ids)
        )
        if pipeline_task_id is not None:
            stmt = stmt.where(ContentEngineTopicRunModel.pipeline_task_id == pipeline_task_id)
        if effective_slug is not None:
            stmt = stmt.where(ContentEngineTopicRunModel.effective_slug == effective_slug)
        stmt = stmt.order_by(ContentEngineTopicRunModel.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_latest_by_assignment(
        self,
        topic_assignment_id: _uuid.UUID | str,
        *,
        ga_run_id: _uuid.UUID | None = None,
    ) -> ContentEngineTopicRunModel | None:
        pk = (
            _uuid.UUID(str(topic_assignment_id))
            if isinstance(topic_assignment_id, str)
            else topic_assignment_id
        )
        stmt = select(ContentEngineTopicRunModel).where(
            ContentEngineTopicRunModel.topic_assignment_id == pk
        )
        if ga_run_id is not None:
            stmt = stmt.where(ContentEngineTopicRunModel.ga_run_id == ga_run_id)
        stmt = stmt.order_by(ContentEngineTopicRunModel.created_at.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_id_and_slug(
        self,
        topic_run_id: _uuid.UUID | str,
        *,
        effective_slug: str,
    ) -> ContentEngineTopicRunModel | None:
        pk = _uuid.UUID(str(topic_run_id)) if isinstance(topic_run_id, str) else topic_run_id
        stmt = select(ContentEngineTopicRunModel).where(
            ContentEngineTopicRunModel.id == pk,
            ContentEngineTopicRunModel.effective_slug == effective_slug,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_pipeline_task_id(
        self,
        pipeline_task_id: str,
        *,
        effective_slug: str | None = None,
    ) -> ContentEngineTopicRunModel | None:
        stmt = select(ContentEngineTopicRunModel).where(
            ContentEngineTopicRunModel.pipeline_task_id == pipeline_task_id
        )
        if effective_slug is not None:
            stmt = stmt.where(ContentEngineTopicRunModel.effective_slug == effective_slug)
        stmt = stmt.order_by(ContentEngineTopicRunModel.updated_at.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def count_by_batch(self, batch_run_id: _uuid.UUID | str) -> int:
        pk = _uuid.UUID(str(batch_run_id)) if isinstance(batch_run_id, str) else batch_run_id
        stmt = select(func.count(ContentEngineTopicRunModel.id)).where(
            ContentEngineTopicRunModel.batch_run_id == pk
        )
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)

    async def claim_queued_runs_for_company(
        self,
        *,
        company_id: _uuid.UUID,
        limit: int,
        claim_token: str,
    ) -> Sequence[ContentEngineTopicRunModel]:
        if limit <= 0:
            return []

        stmt = (
            select(ContentEngineTopicRunModel)
            .where(
                ContentEngineTopicRunModel.company_id == company_id,
                ContentEngineTopicRunModel.scheduler_state.in_(
                    ("queued", "resume_queued")
                ),
            )
            .order_by(
                ContentEngineTopicRunModel.scheduler_state.desc(),
                ContentEngineTopicRunModel.updated_at.asc(),
                ContentEngineTopicRunModel.created_at.asc(),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        now = datetime.now(timezone.utc)
        for row in rows:
            row.scheduler_state = "claimed"
            row.claim_token = claim_token
            row.claimed_at = now
        await self._session.flush()
        return rows

    async def list_recovery_candidates(self) -> Sequence[ContentEngineTopicRunModel]:
        stmt = (
            select(ContentEngineTopicRunModel)
            .where(
                ContentEngineTopicRunModel.scheduler_state.in_(
                    ("queued", "resume_queued", "claimed", "running", "waiting_human")
                )
            )
            .order_by(
                ContentEngineTopicRunModel.updated_at.asc(),
                ContentEngineTopicRunModel.created_at.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class ContentEngineTopicEventRepository(SQLAlchemyRepository[ContentEngineTopicEventModel]):
    model_class = ContentEngineTopicEventModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_next_seq(self, topic_run_id: _uuid.UUID | str) -> int:
        pk = _uuid.UUID(str(topic_run_id)) if isinstance(topic_run_id, str) else topic_run_id
        stmt = select(func.max(ContentEngineTopicEventModel.seq)).where(
            ContentEngineTopicEventModel.topic_run_id == pk
        )
        result = await self._session.execute(stmt)
        current = result.scalar()
        return int(current or 0) + 1

    async def append_event(
        self,
        *,
        topic_run_id: _uuid.UUID,
        topic_assignment_id: _uuid.UUID,
        display_id: str,
        event_type: str,
        stage: str,
        status: str,
        pipeline_task_id: str | None = None,
        content_piece_id: _uuid.UUID | None = None,
        seq: int | None = None,
        payload_json: dict | None = None,
    ) -> ContentEngineTopicEventModel:
        next_seq = seq if seq is not None else await self.get_next_seq(topic_run_id)
        event = ContentEngineTopicEventModel(
            topic_run_id=topic_run_id,
            topic_assignment_id=topic_assignment_id,
            display_id=display_id,
            content_piece_id=content_piece_id,
            pipeline_task_id=pipeline_task_id,
            event_type=event_type,
            stage=stage,
            status=status,
            seq=next_seq,
            payload_json=payload_json,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_for_topic_run(
        self,
        topic_run_id: _uuid.UUID | str,
        *,
        limit: int = 200,
    ) -> Sequence[ContentEngineTopicEventModel]:
        pk = _uuid.UUID(str(topic_run_id)) if isinstance(topic_run_id, str) else topic_run_id
        stmt = (
            select(ContentEngineTopicEventModel)
            .where(ContentEngineTopicEventModel.topic_run_id == pk)
            .order_by(ContentEngineTopicEventModel.seq.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
