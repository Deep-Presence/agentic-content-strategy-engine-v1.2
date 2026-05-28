"""Service layer for durable TD-entry Content Engine batch/topic runs."""
from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from sqlalchemy import select
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
from core.shared_tools.task_status import TaskStatus

_UNSET = object()


class TopicRunResumeNotFoundError(ValueError):
    """No durable waiting-human topic run matched the requested task."""


class TopicRunResumeConflictError(ValueError):
    """A durable topic run exists, but it cannot accept another approval resume."""


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
    scheduler_state: str
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


@dataclass(slots=True)
class QueuedTopicRunClaimSnapshot:
    """Dispatchable queued topic-run claim for the Phase 3 CE dispatcher."""

    topic_run_id: str
    batch_run_id: str
    topic_assignment_id: str
    display_id: str
    topic_text: str
    brief_id: str
    ga_run_id: str | None
    pipeline_task_id: str | None
    effective_slug: str
    company_slug: str
    scheduler_state: str
    launch_context: dict[str, Any]
    continuation_payload: dict[str, Any]


@dataclass(slots=True)
class StartupSchedulerRecoverySnapshot:
    companies_to_dispatch: list[str]
    queued_ready_count: int = 0
    requeued_count: int = 0
    waiting_human_restored_count: int = 0
    stale_task_ids_cleared_count: int = 0


class ContentEngineTopicRunService:
    """Owns durable topic/batch execution state for TD-entry CE flows."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _task_status_value(task: Any) -> str | None:
        if task is None:
            return None
        status = getattr(task, "status", None)
        if status is None:
            return None
        return status.value if hasattr(status, "value") else str(status)

    @staticmethod
    def _company_slug_from_effective_slug(effective_slug: str) -> str:
        return effective_slug.split("__", 1)[0]

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
                        scheduler_state="idle",
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
        pipeline_task_id: Any = _UNSET,
        content_piece_ids: dict[str, str] | None = None,
        last_error: str | None = None,
        event_type: str = "topic_run_changed",
        payload_json: dict | None = None,
        metadata_updates: dict | None = None,
        scheduler_state: str | None = None,
        clear_claim_token: bool = False,
        queued_at: Any = _UNSET,
        claimed_at: Any = _UNSET,
        waiting_for_human_at: Any = _UNSET,
        continuation_payload_json: Any = _UNSET,
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
                if scheduler_state is not None:
                    run.scheduler_state = scheduler_state
                if pipeline_task_id is not _UNSET:
                    run.pipeline_task_id = pipeline_task_id
                if ga_run_uuid is not None:
                    run.ga_run_id = ga_run_uuid
                if clear_claim_token:
                    run.claim_token = None
                if queued_at is not _UNSET:
                    run.queued_at = queued_at
                if claimed_at is not _UNSET:
                    run.claimed_at = claimed_at
                if waiting_for_human_at is not _UNSET:
                    run.waiting_for_human_at = waiting_for_human_at
                if continuation_payload_json is not _UNSET:
                    run.continuation_payload_json = continuation_payload_json
                if last_error is not None:
                    run.last_error = last_error
                    run.failed_at = now
                elif status in {"completed", "content_produced"}:
                    run.completed_at = now
                if metadata_updates:
                    merged_metadata = dict(run.metadata_json or {})
                    merged_metadata.update(metadata_updates)
                    run.metadata_json = merged_metadata
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
        pipeline_task_id: Any = _UNSET,
        match_pipeline_task_id: str | None = None,
        content_piece_ids: dict[str, str] | None = None,
        last_error: str | None = None,
        event_type: str = "topic_run_changed",
        payload_json: dict | None = None,
        metadata_updates: dict | None = None,
        scheduler_state: str | None = None,
        clear_claim_token: bool = False,
        waiting_for_human_at: Any = _UNSET,
        continuation_payload_json: Any = _UNSET,
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
                if scheduler_state is not None:
                    run.scheduler_state = scheduler_state
                if pipeline_task_id is not _UNSET:
                    run.pipeline_task_id = pipeline_task_id
                if clear_claim_token:
                    run.claim_token = None
                if waiting_for_human_at is not _UNSET:
                    run.waiting_for_human_at = waiting_for_human_at
                if continuation_payload_json is not _UNSET:
                    run.continuation_payload_json = continuation_payload_json
                if last_error is not None:
                    run.last_error = last_error
                    run.failed_at = now
                elif status in {"completed", "content_produced"}:
                    run.completed_at = now
                if metadata_updates:
                    merged_metadata = dict(run.metadata_json or {})
                    merged_metadata.update(metadata_updates)
                    run.metadata_json = merged_metadata
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

    async def list_topic_runs_by_assignment_ids(
        self,
        *,
        effective_slug: str,
        topic_assignment_ids: Sequence[str],
        ga_run_id: str | None = None,
    ) -> list[TopicRunSnapshot]:
        assignment_uuids = [_uuid.UUID(str(tid)) for tid in topic_assignment_ids]
        ga_run_uuid = _uuid.UUID(ga_run_id) if ga_run_id else None
        async with self._session_factory() as session:
            repo = ContentEngineTopicRunRepository(session)
            runs = await repo.list_by_assignment_ids(
                assignment_uuids,
                ga_run_id=ga_run_uuid,
                effective_slug=effective_slug,
            )
            latest_by_assignment: dict[_uuid.UUID, ContentEngineTopicRunModel] = {}
            for run in runs:
                latest_by_assignment.setdefault(run.topic_assignment_id, run)
            ordered = [
                latest_by_assignment[assignment_id]
                for assignment_id in assignment_uuids
                if assignment_id in latest_by_assignment
            ]
            return [self._to_snapshot(run) for run in ordered]

    async def claim_queued_topic_runs(
        self,
        *,
        company_slug: str,
        limit: int,
    ) -> list[QueuedTopicRunClaimSnapshot]:
        if limit <= 0:
            return []
        claim_token = str(_uuid.uuid4())
        async with self._session_factory() as session:
            company_repo = CompanyRepository(session)
            topic_run_repo = ContentEngineTopicRunRepository(session)
            company = await company_repo.get_by_slug(company_slug)
            if company is None:
                return []
            runs = await topic_run_repo.claim_queued_runs_for_company(
                company_id=company.id,
                limit=limit,
                claim_token=claim_token,
            )
            await session.commit()
            return [
                self._to_claim_snapshot(run, company_slug=company_slug)
                for run in runs
            ]

    async def mark_claimed_topic_runs_dispatched(
        self,
        *,
        topic_run_task_ids: dict[str, str],
    ) -> list[TopicRunSnapshot]:
        if not topic_run_task_ids:
            return []
        run_ids = [_uuid.UUID(topic_run_id) for topic_run_id in topic_run_task_ids]
        async with self._session_factory() as session:
            topic_run_repo = ContentEngineTopicRunRepository(session)
            event_repo = ContentEngineTopicEventRepository(session)
            stmt_runs = await session.execute(
                select(ContentEngineTopicRunModel).where(
                    ContentEngineTopicRunModel.id.in_(run_ids)
                )
            )
            rows = list(stmt_runs.scalars().all())
            by_id = {str(row.id): row for row in rows}
            updated: list[ContentEngineTopicRunModel] = []
            for topic_run_id, task_id in topic_run_task_ids.items():
                run = by_id.get(topic_run_id)
                if run is None:
                    continue
                is_resume = run.scheduler_state == "claimed" and run.continuation_payload_json
                run.scheduler_state = "running"
                run.claim_token = None
                run.pipeline_task_id = task_id
                run.status_seq += 1
                await session.flush()
                await event_repo.append_event(
                    topic_run_id=run.id,
                    topic_assignment_id=run.topic_assignment_id,
                    display_id=run.display_id,
                    pipeline_task_id=task_id,
                    event_type="topic_run_changed",
                    stage=run.current_stage,
                    status=run.status,
                    seq=run.status_seq,
                    payload_json={
                        "source": "td_content_dispatcher",
                        "note": (
                            "Approval continuation claimed for execution"
                            if is_resume
                            else "Queued topic claimed for execution"
                        ),
                    },
                )
                updated.append(run)
            await session.commit()
            return [self._to_snapshot(run) for run in updated]

    async def release_topic_run_claims(
        self,
        *,
        topic_run_ids: Sequence[str],
    ) -> None:
        if not topic_run_ids:
            return
        run_ids = [_uuid.UUID(topic_run_id) for topic_run_id in topic_run_ids]
        async with self._session_factory() as session:
            stmt_runs = await session.execute(
                select(ContentEngineTopicRunModel).where(
                    ContentEngineTopicRunModel.id.in_(run_ids)
                )
            )
            rows = list(stmt_runs.scalars().all())
            for run in rows:
                run.scheduler_state = "resume_queued" if run.continuation_payload_json else "queued"
                run.claim_token = None
            await session.commit()

    async def queue_topic_runs_for_dispatch(
        self,
        *,
        effective_slug: str,
        topic_assignment_ids: Sequence[str],
        pipeline_task_id: str | None = None,
        ga_run_id: str | None = None,
        match_ga_run_id: str | None = None,
        launch_context: dict[str, Any] | None = None,
    ) -> list[TopicRunSnapshot]:
        now = datetime.now(timezone.utc)
        metadata_updates = {"launch_context": launch_context or {}}
        return await self.advance_topic_runs(
            effective_slug=effective_slug,
            topic_assignment_ids=topic_assignment_ids,
            status="content_queued",
            stage="content_queued",
            pipeline_task_id=pipeline_task_id,
            ga_run_id=ga_run_id,
            match_ga_run_id=match_ga_run_id,
            payload_json={
                "source": "td_content_dispatcher",
                "note": "Topic queued for content execution",
            },
            metadata_updates=metadata_updates,
            scheduler_state="queued",
            clear_claim_token=True,
            queued_at=now,
            claimed_at=None,
            waiting_for_human_at=None,
            continuation_payload_json={},
        )

    async def mark_topic_run_waiting_human(
        self,
        *,
        effective_slug: str,
        pipeline_task_id: str,
        status: str,
        stage: str,
        continuation_payload: dict[str, Any],
        payload_json: dict | None = None,
    ) -> list[TopicRunSnapshot]:
        return await self.advance_topic_runs(
            effective_slug=effective_slug,
            topic_assignment_ids=[
                continuation_payload["topic_assignment_id"],
            ],
            status=status,
            stage=stage,
            pipeline_task_id=pipeline_task_id,
            match_pipeline_task_id=pipeline_task_id,
            payload_json=payload_json,
            scheduler_state="waiting_human",
            clear_claim_token=True,
            waiting_for_human_at=datetime.now(timezone.utc),
            continuation_payload_json=continuation_payload,
        )

    async def queue_topic_run_resume(
        self,
        *,
        effective_slug: str,
        pipeline_task_id: str,
        approval_data: dict[str, Any],
    ) -> TopicRunSnapshot:
        async with self._session_factory() as session:
            repo = ContentEngineTopicRunRepository(session)
            run = await repo.get_by_pipeline_task_id(
                pipeline_task_id,
                effective_slug=effective_slug,
            )
            if run is None:
                raise TopicRunResumeNotFoundError(
                    f"No topic run found for pipeline task {pipeline_task_id}"
                )
            if run.scheduler_state == "resume_queued":
                raise TopicRunResumeConflictError(
                    f"Approval already submitted for task {pipeline_task_id}"
                )
            if run.scheduler_state != "waiting_human":
                raise TopicRunResumeConflictError(
                    f"Topic run for task {pipeline_task_id} is not waiting for human approval"
                )
            payload = dict(run.continuation_payload_json or {})
            payload["approval_data"] = approval_data
            now = datetime.now(timezone.utc)
            payload["resumed_at"] = now.isoformat()
            run.scheduler_state = "resume_queued"
            run.claim_token = None
            run.queued_at = now
            run.continuation_payload_json = payload
            await session.commit()
            return self._to_snapshot(run)

    async def reconcile_startup_scheduler(
        self,
        *,
        task_by_id: dict[str, Any],
    ) -> StartupSchedulerRecoverySnapshot:
        async with self._session_factory() as session:
            repo = ContentEngineTopicRunRepository(session)
            event_repo = ContentEngineTopicEventRepository(session)
            runs = await repo.list_recovery_candidates()
            result = StartupSchedulerRecoverySnapshot(companies_to_dispatch=[])
            companies_to_dispatch: set[str] = set()
            now = datetime.now(timezone.utc)

            for run in runs:
                company_slug = self._company_slug_from_effective_slug(run.effective_slug)
                task = task_by_id.get(run.pipeline_task_id or "")
                task_status = self._task_status_value(task)
                task_payload = getattr(task, "approval_payload", None) or {}
                task_continuation = dict(task_payload.get("continuation") or {})
                has_continuation = bool(run.continuation_payload_json or task_continuation)

                if run.scheduler_state == "waiting_human":
                    continue

                if run.scheduler_state in {"queued", "resume_queued"}:
                    if run.pipeline_task_id and task is None:
                        run.pipeline_task_id = None
                        result.stale_task_ids_cleared_count += 1
                    companies_to_dispatch.add(company_slug)
                    result.queued_ready_count += 1
                    continue

                if run.scheduler_state not in {"claimed", "running"}:
                    continue

                if task_status in {
                    TaskStatus.RUNNING.value,
                    TaskStatus.PENDING_APPROVAL.value,
                }:
                    continue

                if (
                    task_status == TaskStatus.FAILED_RESTART.value
                    and task_payload.get("stage")
                    and has_continuation
                ):
                    run.status_seq += 1
                    run.scheduler_state = "waiting_human"
                    run.claim_token = None
                    run.claimed_at = None
                    run.waiting_for_human_at = now
                    run.continuation_payload_json = dict(
                        run.continuation_payload_json or task_continuation
                    )
                    run.status = str(task_payload.get("status") or run.status)
                    run.current_stage = str(task_payload.get("stage") or run.current_stage)
                    await event_repo.append_event(
                        topic_run_id=run.id,
                        topic_assignment_id=run.topic_assignment_id,
                        display_id=run.display_id,
                        content_piece_id=run.content_piece_id,
                        pipeline_task_id=run.pipeline_task_id,
                        event_type="topic_run_recovered",
                        stage=run.current_stage,
                        status=run.status,
                        seq=run.status_seq,
                        payload_json={
                            "source": "startup_recovery",
                            "note": "Recovered TD topic run back to waiting human approval after restart",
                        },
                    )
                    result.waiting_human_restored_count += 1
                    continue

                if has_continuation and task_status in {
                    None,
                    TaskStatus.FAILED_RESTART.value,
                    TaskStatus.FAILED.value,
                    TaskStatus.CANCELLED.value,
                }:
                    run.status_seq += 1
                    run.scheduler_state = "resume_queued"
                    run.claim_token = None
                    run.queued_at = now
                    run.claimed_at = None
                    if run.pipeline_task_id is not None and task is None:
                        run.pipeline_task_id = None
                        result.stale_task_ids_cleared_count += 1
                    if task_continuation and not run.continuation_payload_json:
                        run.continuation_payload_json = task_continuation
                    await event_repo.append_event(
                        topic_run_id=run.id,
                        topic_assignment_id=run.topic_assignment_id,
                        display_id=run.display_id,
                        content_piece_id=run.content_piece_id,
                        pipeline_task_id=run.pipeline_task_id,
                        event_type="topic_run_recovered",
                        stage=run.current_stage,
                        status=run.status,
                        seq=run.status_seq,
                        payload_json={
                            "source": "startup_recovery",
                            "note": "Recovered stranded TD continuation back to resume queue after restart",
                        },
                    )
                    companies_to_dispatch.add(company_slug)
                    result.queued_ready_count += 1
                    continue

                if task_status in {
                    None,
                    TaskStatus.FAILED_RESTART.value,
                    TaskStatus.FAILED.value,
                    TaskStatus.CANCELLED.value,
                }:
                    run.status_seq += 1
                    run.status = "content_queued"
                    run.current_stage = "content_queued"
                    run.scheduler_state = "queued"
                    run.claim_token = None
                    run.queued_at = now
                    run.claimed_at = None
                    run.waiting_for_human_at = None
                    if run.pipeline_task_id is not None:
                        result.stale_task_ids_cleared_count += 1
                    run.pipeline_task_id = None
                    await event_repo.append_event(
                        topic_run_id=run.id,
                        topic_assignment_id=run.topic_assignment_id,
                        display_id=run.display_id,
                        content_piece_id=run.content_piece_id,
                        pipeline_task_id=None,
                        event_type="topic_run_recovered",
                        stage="content_queued",
                        status="content_queued",
                        seq=run.status_seq,
                        payload_json={
                            "source": "startup_recovery",
                            "note": "Recovered stranded TD topic run back to queue after restart",
                        },
                    )
                    companies_to_dispatch.add(company_slug)
                    result.requeued_count += 1

            await session.commit()
            result.companies_to_dispatch = sorted(companies_to_dispatch)
            return result

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
            scheduler_state=run.scheduler_state,
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

    @staticmethod
    def _to_claim_snapshot(
        run: ContentEngineTopicRunModel,
        *,
        company_slug: str,
    ) -> QueuedTopicRunClaimSnapshot:
        launch_context = dict((run.metadata_json or {}).get("launch_context") or {})
        return QueuedTopicRunClaimSnapshot(
            topic_run_id=str(run.id),
            batch_run_id=str(run.batch_run_id),
            topic_assignment_id=str(run.topic_assignment_id),
            display_id=run.display_id,
            topic_text=run.topic_text,
            brief_id=run.brief_id or "",
            ga_run_id=str(run.ga_run_id) if run.ga_run_id else None,
            pipeline_task_id=run.pipeline_task_id,
            effective_slug=run.effective_slug,
            company_slug=company_slug,
            scheduler_state=run.scheduler_state,
            launch_context=launch_context,
            continuation_payload=dict(run.continuation_payload_json or {}),
        )
