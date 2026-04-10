"""Service layer for durable TD-entry Content Engine batch/topic runs."""
from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.db.models.content_engine_runs import (
    ContentEngineBatchRunModel,
    ContentEngineTopicEventModel,
    ContentEngineTopicRunModel,
)
from core.db.models.topic_discovery import TopicAssignmentModel
from core.db.repositories.company_repo import CompanyRepository
from core.db.repositories.content_engine_run_repo import (
    ContentEngineBatchRunRepository,
    ContentEngineTopicEventRepository,
    ContentEngineTopicRunRepository,
)
from core.db.repositories.product_repo import ProductRepository
from core.db.repositories.topic_discovery_repo import TopicAssignmentRepository


@dataclass(slots=True)
class TopicRunSnapshot:
    """Lightweight DTO returned to API/router callers."""

    topic_run_id: str
    batch_run_id: str
    topic_assignment_id: str
    display_id: str
    topic_text: str
    brief_id: str
    ga_run_id: str | None
    pipeline_task_id: str | None
    status: str
    stage: str
    seq: int
    content_piece_id: str | None
    created_at: str
    updated_at: str


@dataclass(slots=True)
class TopicRunEventSnapshot:
    """Append-only execution event DTO for one durable topic run."""

    topic_event_id: str
    topic_run_id: str
    topic_assignment_id: str
    display_id: str
    brief_id: str
    event_type: str
    stage: str
    status: str
    seq: int
    content_piece_id: str | None
    pipeline_task_id: str | None
    payload_json: dict
    created_at: str


class ContentEngineTopicRunService:
    """Owns durable topic/batch execution state for TD-entry CE flows."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_td_batch(
        self,
        *,
        company_slug: str,
        effective_slug: str,
        topic_assignment_ids: Sequence[str],
        pipeline_task_id: str | None,
        product_slug: str | None = None,
        source: str = "topic_discovery_pipeline_b",
        source_mode: str = "td_entry_mode",
        entry_mode: str = "topic_discovery",
        initial_status: str = "gap_analysis_pending",
        initial_stage: str = "gap_analysis_pending",
        ga_run_id: str | None = None,
        metadata_json: dict | None = None,
    ) -> tuple[ContentEngineBatchRunModel, list[TopicRunSnapshot]]:
        assignment_uuids = [_uuid.UUID(str(tid)) for tid in topic_assignment_ids]
        ga_run_uuid = _uuid.UUID(ga_run_id) if ga_run_id else None
        async with self._session_factory() as session:
            company_repo = CompanyRepository(session)
            product_repo = ProductRepository(session)
            assignment_repo = TopicAssignmentRepository(session)
            batch_repo = ContentEngineBatchRunRepository(session)
            topic_run_repo = ContentEngineTopicRunRepository(session)
            event_repo = ContentEngineTopicEventRepository(session)

            company = await company_repo.get_by_slug(company_slug)
            if company is None:
                raise ValueError(f"Company not found for slug {company_slug!r}")
            product = (
                await product_repo.get_by_slugs(company.id, product_slug)
                if product_slug
                else None
            )

            assignments = await assignment_repo.get_by_ids(assignment_uuids)
            ordered = self._order_assignments(assignments, assignment_uuids)
            if not ordered:
                raise ValueError("No TopicAssignments found for batch creation")

            batch = await batch_repo.create(
                company_id=company.id,
                product_id=product.id if product else None,
                effective_slug=effective_slug,
                source=source,
                source_mode=source_mode,
                status=initial_status,
                pipeline_task_id=pipeline_task_id,
                submitted_count=len(ordered),
                metadata_json=metadata_json,
            )

            now = datetime.now(timezone.utc)
            models: list[ContentEngineTopicRunModel] = []
            for assignment in ordered:
                display_id = assignment.display_id or str(assignment.id)
                models.append(
                    ContentEngineTopicRunModel(
                        batch_run_id=batch.id,
                        company_id=company.id,
                        product_id=product.id if product else None,
                        effective_slug=effective_slug,
                        topic_assignment_id=assignment.id,
                        display_id=display_id,
                        topic_text=assignment.topic_text,
                        brief_id=display_id,
                        ga_run_id=ga_run_uuid,
                        pipeline_task_id=pipeline_task_id,
                        entry_mode=entry_mode,
                        status=initial_status,
                        current_stage=initial_stage,
                        status_seq=1,
                        started_at=now,
                        metadata_json={
                            "buyer_stage": assignment.buyer_stage.value if hasattr(assignment.buyer_stage, "value") else assignment.buyer_stage,
                            "intent_type": assignment.intent_type.value if hasattr(assignment.intent_type, "value") else assignment.intent_type,
                            **(metadata_json or {}),
                        },
                    )
                )

            created = await topic_run_repo.bulk_create(models)
            for run in created:
                await event_repo.append_event(
                    topic_run_id=run.id,
                    topic_assignment_id=run.topic_assignment_id,
                    display_id=run.display_id,
                    event_type="topic_run_created",
                    stage=run.current_stage,
                    status=run.status,
                    pipeline_task_id=run.pipeline_task_id,
                    seq=run.status_seq,
                    payload_json={
                        "batch_run_id": str(run.batch_run_id),
                        "brief_id": run.brief_id,
                        "topic_text": run.topic_text,
                    },
                )

            await session.commit()
            return batch, [self._to_snapshot(run) for run in created]

    async def advance_topic_runs(
        self,
        *,
        effective_slug: str,
        topic_assignment_ids: Sequence[str],
        status: str,
        stage: str,
        ga_run_id: str | None = None,
        match_ga_run_id: str | None = None,
        match_pipeline_task_id: str | None = None,
        pipeline_task_id: str | None = None,
        content_piece_ids: dict[str, str] | None = None,
        last_error: str | None = None,
        event_type: str = "topic_run_changed",
        payload_json: dict | None = None,
    ) -> list[TopicRunSnapshot]:
        assignment_uuids = [_uuid.UUID(str(tid)) for tid in topic_assignment_ids]
        ga_run_uuid = _uuid.UUID(ga_run_id) if ga_run_id else None
        match_ga_run_uuid = (
            _uuid.UUID(match_ga_run_id)
            if match_ga_run_id
            else (ga_run_uuid if ga_run_uuid is not None and match_pipeline_task_id is None else None)
        )
        async with self._session_factory() as session:
            topic_run_repo = ContentEngineTopicRunRepository(session)
            event_repo = ContentEngineTopicEventRepository(session)
            runs = await topic_run_repo.list_by_assignment_ids(
                assignment_uuids,
                ga_run_id=match_ga_run_uuid,
                pipeline_task_id=match_pipeline_task_id,
                effective_slug=effective_slug,
            )
            latest_by_assignment: dict[_uuid.UUID, ContentEngineTopicRunModel] = {}
            for run in runs:
                latest_by_assignment.setdefault(run.topic_assignment_id, run)

            updated: list[ContentEngineTopicRunModel] = []
            now = datetime.now(timezone.utc)
            content_piece_ids = content_piece_ids or {}
            for assignment_id in assignment_uuids:
                run = latest_by_assignment.get(assignment_id)
                if run is None or run.effective_slug != effective_slug:
                    continue
                run.status_seq += 1
                run.status = status
                run.current_stage = stage
                if pipeline_task_id is not None:
                    run.pipeline_task_id = pipeline_task_id
                if ga_run_uuid is not None:
                    run.ga_run_id = ga_run_uuid
                if last_error is not None:
                    run.last_error = last_error
                    run.failed_at = now
                elif status in {"completed", "content_produced"}:
                    run.completed_at = now
                if run.started_at is None:
                    run.started_at = now
                piece_id = content_piece_ids.get(str(assignment_id))
                if piece_id:
                    run.content_piece_id = _uuid.UUID(piece_id)
                await session.flush()
                await event_repo.append_event(
                    topic_run_id=run.id,
                    topic_assignment_id=run.topic_assignment_id,
                    display_id=run.display_id,
                    content_piece_id=run.content_piece_id,
                    pipeline_task_id=run.pipeline_task_id,
                    event_type=event_type,
                    stage=stage,
                    status=status,
                    seq=run.status_seq,
                    payload_json=payload_json,
                )
                updated.append(run)

            await session.commit()
            return [self._to_snapshot(run) for run in updated]

    async def advance_topic_runs_by_brief_ids(
        self,
        *,
        effective_slug: str,
        brief_ids: Sequence[str],
        status: str,
        stage: str,
        pipeline_task_id: str | None = None,
        match_pipeline_task_id: str | None = None,
        content_piece_ids: dict[str, str] | None = None,
        last_error: str | None = None,
        event_type: str = "topic_run_changed",
        payload_json: dict | None = None,
    ) -> list[TopicRunSnapshot]:
        normalized_brief_ids = [str(brief_id) for brief_id in brief_ids if brief_id]
        async with self._session_factory() as session:
            topic_run_repo = ContentEngineTopicRunRepository(session)
            event_repo = ContentEngineTopicEventRepository(session)
            runs = await topic_run_repo.list_by_brief_ids(
                normalized_brief_ids,
                pipeline_task_id=match_pipeline_task_id,
                effective_slug=effective_slug,
            )
            latest_by_brief: dict[str, ContentEngineTopicRunModel] = {}
            for run in runs:
                latest_by_brief.setdefault(run.brief_id or "", run)

            updated: list[ContentEngineTopicRunModel] = []
            now = datetime.now(timezone.utc)
            content_piece_ids = content_piece_ids or {}
            for brief_id in normalized_brief_ids:
                run = latest_by_brief.get(brief_id)
                if run is None:
                    continue
                run.status_seq += 1
                run.status = status
                run.current_stage = stage
                if pipeline_task_id is not None:
                    run.pipeline_task_id = pipeline_task_id
                if last_error is not None:
                    run.last_error = last_error
                    run.failed_at = now
                elif status in {"completed", "content_produced"}:
                    run.completed_at = now
                if run.started_at is None:
                    run.started_at = now
                piece_id = content_piece_ids.get(brief_id)
                if piece_id:
                    run.content_piece_id = _uuid.UUID(piece_id)
                await session.flush()
                await event_repo.append_event(
                    topic_run_id=run.id,
                    topic_assignment_id=run.topic_assignment_id,
                    display_id=run.display_id,
                    content_piece_id=run.content_piece_id,
                    pipeline_task_id=run.pipeline_task_id,
                    event_type=event_type,
                    stage=stage,
                    status=status,
                    seq=run.status_seq,
                    payload_json=payload_json,
                )
                updated.append(run)

            await session.commit()
            return [self._to_snapshot(run) for run in updated]

    async def list_topic_runs(
        self,
        *,
        effective_slug: str,
        limit: int = 200,
    ) -> list[TopicRunSnapshot]:
        async with self._session_factory() as session:
            repo = ContentEngineTopicRunRepository(session)
            rows = await repo.list_by_slug(effective_slug, limit=limit)
            return [self._to_snapshot(row) for row in rows]

    async def list_topic_run_events(
        self,
        *,
        effective_slug: str,
        topic_run_id: str,
        limit: int = 200,
    ) -> tuple[TopicRunSnapshot | None, list[TopicRunEventSnapshot]]:
        async with self._session_factory() as session:
            topic_run_repo = ContentEngineTopicRunRepository(session)
            event_repo = ContentEngineTopicEventRepository(session)
            run = await topic_run_repo.get_by_id_and_slug(
                topic_run_id,
                effective_slug=effective_slug,
            )
            if run is None:
                return None, []
            events = await event_repo.list_for_topic_run(run.id, limit=limit)
            return self._to_snapshot(run), [
                self._to_event_snapshot(run, event) for event in events
            ]

    @staticmethod
    def _order_assignments(
        assignments: Iterable[TopicAssignmentModel],
        ordered_ids: Sequence[_uuid.UUID],
    ) -> list[TopicAssignmentModel]:
        by_id = {assignment.id: assignment for assignment in assignments}
        return [by_id[assignment_id] for assignment_id in ordered_ids if assignment_id in by_id]

    @staticmethod
    def _to_snapshot(run: ContentEngineTopicRunModel) -> TopicRunSnapshot:
        return TopicRunSnapshot(
            topic_run_id=str(run.id),
            batch_run_id=str(run.batch_run_id),
            topic_assignment_id=str(run.topic_assignment_id),
            display_id=run.display_id,
            topic_text=run.topic_text,
            brief_id=run.brief_id or "",
            ga_run_id=str(run.ga_run_id) if run.ga_run_id else None,
            pipeline_task_id=run.pipeline_task_id,
            status=run.status,
            stage=run.current_stage,
            seq=int(run.status_seq),
            content_piece_id=str(run.content_piece_id) if run.content_piece_id else None,
            created_at=run.created_at.isoformat(),
            updated_at=run.updated_at.isoformat(),
        )

    @staticmethod
    def _to_event_snapshot(
        run: ContentEngineTopicRunModel,
        event: ContentEngineTopicEventModel,
    ) -> TopicRunEventSnapshot:
        payload = dict(event.payload_json or {})
        payload.setdefault("brief_id", run.brief_id or "")
        payload.setdefault("display_id", run.display_id)
        payload.setdefault("topic_text", run.topic_text)
        payload.setdefault("entry_mode", run.entry_mode)
        payload.setdefault("effective_slug", run.effective_slug)
        payload.setdefault("batch_run_id", str(run.batch_run_id))
        if event.content_piece_id is not None:
            payload.setdefault("content_piece_id", str(event.content_piece_id))
        if run.metadata_json:
            buyer_stage = run.metadata_json.get("buyer_stage")
            if buyer_stage:
                payload.setdefault("buyer_stage", str(buyer_stage))
            intent_type = run.metadata_json.get("intent_type")
            if intent_type:
                payload.setdefault("intent_type", str(intent_type))
        return TopicRunEventSnapshot(
            topic_event_id=str(event.id),
            topic_run_id=str(event.topic_run_id),
            topic_assignment_id=str(event.topic_assignment_id),
            display_id=event.display_id,
            brief_id=run.brief_id or "",
            event_type=event.event_type,
            stage=event.stage,
            status=event.status,
            seq=int(event.seq),
            content_piece_id=str(event.content_piece_id) if event.content_piece_id else None,
            pipeline_task_id=event.pipeline_task_id,
            payload_json=payload,
            created_at=event.created_at.isoformat(),
        )
