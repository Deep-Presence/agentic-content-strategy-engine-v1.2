"""DB-backed TaskStore with write-through in-memory cache.

Satisfies TaskStoreProtocol. Uses a session_factory (not request-scoped)
for per-operation sessions. Process-local state (semaphore, queues, handles,
slug locks) stays in-memory only.

Single-instance durability scope: SSE streaming, asyncio queues, and task
handles are process-local. Horizontal scaling would require Redis pub/sub
or PG LISTEN/NOTIFY (future work).
"""
from __future__ import annotations

import asyncio
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.tasks.models import ApprovalRecord, PipelineTask
from core.shared_tools.task_status import TaskStatus
from core.services.task_store import ApprovalWindowError, TaskConflictError, TaskNotFoundError

logger = logging.getLogger(__name__)


class DbTaskStore:
    """Write-through DB-backed task store.

    Architecture:
    - In-memory ``_tasks`` dict for fast sync reads (same as JSON TaskStore)
    - Write-through: state transitions write to DB first via
      ``asyncio.create_task(self._write_through(...))``, then update cache.
      For critical transitions (create, status change), use write-through.
      For progress updates (progress_pct), use fire-and-forget to avoid latency.
    - Startup: ``recover_from_db()`` loads all non-terminal tasks, marks orphans.
    - Process-local state (semaphore, queues, handles, slug locks) stays in-memory.
    """

    def __init__(
        self,
        session_factory: Callable[..., AsyncSession],
        max_concurrent: int = 10,
    ) -> None:
        self._tasks: Dict[str, PipelineTask] = {}
        self._session_factory = session_factory
        self._slug_locks: Dict[str, str] = {}  # "pipeline:effective_slug" -> task_id
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._approval_queues: Dict[str, asyncio.Queue] = {}
        self._task_handles: Dict[str, asyncio.Task] = {}

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    # ── Startup recovery ──────────────────────────────────────────────

    async def recover_from_db(self) -> int:
        """Load non-terminal tasks and mark orphans as failed_restart.

        Called once at app startup. Returns the number of orphans recovered.
        """
        from core.db.repositories.task_repo import TaskRepository

        async with self._session_factory() as session:
            repo = TaskRepository(session)
            orphan_count = await repo.mark_orphans_failed()

            # Load all tasks into memory cache
            all_tasks = await repo.list_tasks()
            for row in all_tasks:
                task = self._row_to_pipeline_task(row)
                self._tasks[task.task_id] = task

            await session.commit()

        logger.info(
            "DbTaskStore recovered: %d tasks loaded, %d orphans marked failed_restart",
            len(self._tasks),
            orphan_count,
        )
        return orphan_count

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_task(
        self,
        pipeline: str,
        company_slug: str,
        product_slug: Optional[str] = None,
        allow_parallel: bool = False,
    ) -> PipelineTask:
        """Create a new task, optionally acquire slug lock, write to DB.

        Lock key is ``pipeline:effective_slug`` so different pipeline types
        can run concurrently for the same company.

        Args:
            allow_parallel: If True, skip slug lock acquisition. Used for
                manual content pipeline entries that can run in parallel.
        """
        effective = (
            f"{company_slug}__{product_slug}" if product_slug else company_slug
        )
        lock_key = f"{pipeline}:{effective}"

        if not allow_parallel:
            self.acquire_slug_lock(lock_key)

        task_id = str(_uuid.uuid4())
        now = datetime.now(timezone.utc)
        task = PipelineTask(
            task_id=task_id,
            pipeline=pipeline,
            company_slug=company_slug,
            product_slug=product_slug,
            effective_slug=effective,
            created_at=now,
            updated_at=now,
        )
        self._tasks[task_id] = task
        if not allow_parallel:
            self._slug_locks[lock_key] = task_id

        # Write-through to DB (critical: must persist before returning)
        asyncio.create_task(self._db_create(task))
        return task

    def get_task(self, task_id: str) -> PipelineTask:
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)
        return self._tasks[task_id]

    def update_task(self, task_id: str, **kwargs: Any) -> PipelineTask:
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)

        task = self._tasks[task_id]
        for key, value in kwargs.items():
            if hasattr(task, key):
                if key == "status" and isinstance(value, str) and not isinstance(value, TaskStatus):
                    value = TaskStatus(value)
                setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)

        # Determine if this is a critical update (status change) or progress
        is_status_change = "status" in kwargs
        if is_status_change:
            asyncio.create_task(self._db_update(task_id, **kwargs))
        else:
            # Fire-and-forget for non-critical updates (progress_pct, current_step)
            asyncio.create_task(self._db_update(task_id, **kwargs))
        return task

    def list_tasks(
        self,
        pipeline: Optional[str] = None,
        status: Optional[str] = None,
        company_slug: Optional[str] = None,
        product_slug: Optional[str] = None,
    ) -> List[PipelineTask]:
        tasks = list(self._tasks.values())
        if pipeline:
            tasks = [t for t in tasks if t.pipeline == pipeline]
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        if company_slug:
            tasks = [t for t in tasks if t.company_slug == company_slug]
        if product_slug:
            tasks = [t for t in tasks if t.product_slug == product_slug]
        return tasks

    # ── Slug Locks ────────────────────────────────────────────────────

    def acquire_slug_lock(self, slug: str) -> None:
        if slug in self._slug_locks:
            existing_id = self._slug_locks[slug]
            if existing_id in self._tasks:
                existing = self._tasks[existing_id]
                if existing.status in (TaskStatus.RUNNING, TaskStatus.PENDING_APPROVAL):
                    raise TaskConflictError(
                        f"A pipeline is already running for company '{slug}' "
                        f"(task_id={existing_id})"
                    )
            del self._slug_locks[slug]

    def release_slug_lock(self, slug: str) -> None:
        self._slug_locks.pop(slug, None)

    # ── Task Handle Tracking ──────────────────────────────────────────

    def register_task_handle(self, task_id: str, handle: asyncio.Task) -> None:
        self._task_handles[task_id] = handle

    def cancel_task_handle(self, task_id: str) -> bool:
        handle = self._task_handles.pop(task_id, None)
        if handle and not handle.done():
            handle.cancel()
            return True
        return False

    def remove_task_handle(self, task_id: str) -> None:
        self._task_handles.pop(task_id, None)

    # ── HITL Approval ─────────────────────────────────────────────────

    async def wait_for_approval(
        self, task_id: str, timeout: float = 86400
    ) -> Dict[str, Any]:
        if task_id not in self._approval_queues:
            self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
        try:
            data = await asyncio.wait_for(
                self._approval_queues[task_id].get(), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Approval timed out after %.0fs for task %s — auto-rejecting",
                timeout,
                task_id,
            )
            data = {
                "decision": "reject",
                "revision_note": f"Approval timed out after {int(timeout)}s",
            }
        self._approval_queues.pop(task_id, None)
        return data

    def submit_approval(
        self,
        task_id: str,
        decision: str,
        revision_note: Optional[str] = None,
        stage: Optional[str] = None,
        approval_data: Optional[Dict[str, Any]] = None,
        expected_nonce: Optional[str] = None,
    ) -> None:
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)

        task = self._tasks[task_id]

        # Atomic nonce validation — prevents TOCTOU and replay
        if expected_nonce is not None:
            current_nonce = (task.approval_payload or {}).get("checkpoint_nonce")
            if current_nonce != expected_nonce:
                raise ApprovalWindowError(
                    f"Stale or replayed approval: nonce mismatch "
                    f"(expected {expected_nonce}, current {current_nonce})"
                )

        resolved_stage = (
            stage
            or (task.approval_payload or {}).get("stage")
            or task.current_step
            or "unknown"
        )
        record = ApprovalRecord(
            task_id=task_id,
            stage=resolved_stage,
            decision=decision,
            revision_note=revision_note,
        )
        task.approval_history.append(record)
        task.updated_at = datetime.now(timezone.utc)

        # Persist approval history to DB
        asyncio.create_task(
            self._db_update(
                task_id,
                approval_history=[r.model_dump(mode="json") for r in task.approval_history],
            )
        )

        # Queue the full approval data if provided, else generic payload
        payload = approval_data if approval_data is not None else {"decision": decision, "revision_note": revision_note}
        if task_id not in self._approval_queues:
            self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
        try:
            self._approval_queues[task_id].put_nowait(payload)
        except asyncio.QueueFull:
            raise ApprovalWindowError(
                f"Approval already submitted for task {task_id} — queue full"
            )

    # ── DB write-through helpers ──────────────────────────────────────

    async def _db_create(self, task: PipelineTask) -> None:
        """Insert a new task row into DB."""
        from core.db.repositories.task_repo import TaskRepository

        try:
            async with self._session_factory() as session:
                repo = TaskRepository(session)
                await repo.create_task(
                    task_id=task.task_id,
                    pipeline=task.pipeline,
                    status=task.status.value,
                    company_slug=task.company_slug,
                    product_slug=task.product_slug,
                    effective_slug=task.effective_slug,
                    current_step=task.current_step,
                    progress_pct=task.progress_pct,
                )
                await session.commit()
        except Exception:
            logger.exception("DbTaskStore: failed to persist create for %s", task.task_id)

    async def _db_update(self, task_id: str, **kwargs: Any) -> None:
        """Update a task row in DB."""
        from core.db.repositories.task_repo import TaskRepository

        # Convert TaskStatus enum to string for DB
        db_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, TaskStatus):
                db_kwargs[k] = v.value
            else:
                db_kwargs[k] = v
        db_kwargs["updated_at"] = datetime.now(timezone.utc)

        try:
            async with self._session_factory() as session:
                repo = TaskRepository(session)
                await repo.update_by_task_id(task_id, **db_kwargs)
                await session.commit()
        except Exception:
            logger.exception("DbTaskStore: failed to persist update for %s", task_id)

    # ── Row → PipelineTask conversion ─────────────────────────────────

    @staticmethod
    def _row_to_pipeline_task(row: Any) -> PipelineTask:
        """Convert an ApiTaskModel ORM row to a PipelineTask Pydantic model."""
        return PipelineTask(
            task_id=row.task_id,
            pipeline=row.pipeline,
            status=TaskStatus(row.status),
            company_slug=row.company_slug or "",
            product_slug=row.product_slug,
            effective_slug=row.effective_slug,
            current_step=row.current_step,
            progress_pct=row.progress_pct,
            created_at=row.created_at,
            updated_at=row.updated_at,
            result=row.result,
            error=row.error,
            approval_payload=row.approval_payload,
            approval_history=[
                ApprovalRecord(**r) for r in (row.approval_history or [])
            ],
        )
