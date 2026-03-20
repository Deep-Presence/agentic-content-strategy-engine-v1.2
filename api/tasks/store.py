"""JSON-file-backed TaskStore for managing pipeline runs."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask, TaskStatus

logger = logging.getLogger(__name__)


class TaskNotFoundError(Exception):
    """Raised when a task ID is not found."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class TaskConflictError(Exception):
    """Raised when a conflicting operation is attempted (e.g., same slug running)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ApprovalWindowError(Exception):
    """Raised when an approval is submitted outside the valid window.

    Covers: stale nonce (TOCTOU/replay), or queue already consumed (duplicate).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class TaskStore:
    """In-memory + JSON-file-backed task persistence.

    - Fast reads from in-memory dict
    - Atomic JSON writes on every mutation
    - Startup recovery: mark stale "running" tasks as failed_restart
    - Per-slug locks prevent concurrent runs for the same company
    - Global semaphore caps concurrent pipeline runs
    """

    def __init__(
        self,
        base_dir: Path,
        event_bus: EventBus,
        max_concurrent: int = 10,
    ) -> None:
        self._tasks: Dict[str, PipelineTask] = {}
        self._base_dir = base_dir
        self._event_bus = event_bus
        self._slug_locks: Dict[str, str] = {}  # "pipeline:effective_slug" -> task_id
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._approval_queues: Dict[str, asyncio.Queue] = {}
        self._task_handles: Dict[str, asyncio.Task] = {}  # task_id -> asyncio.Task
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._recover_from_disk()

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_task(
        self,
        pipeline: str,
        company_slug: str,
        product_slug: Optional[str] = None,
        allow_parallel: bool = False,
    ) -> PipelineTask:
        """Create a new task and optionally acquire slug lock.

        Lock key is ``pipeline:effective_slug`` so different pipeline types
        can run concurrently for the same company.  When product_slug is set,
        effective_slug = ``company_slug__product_slug``.

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

        task_id = str(uuid.uuid4())
        task = PipelineTask(
            task_id=task_id,
            pipeline=pipeline,
            company_slug=company_slug,
            product_slug=product_slug,
            effective_slug=effective,
        )
        self._tasks[task_id] = task
        if not allow_parallel:
            self._slug_locks[lock_key] = task_id
        self._persist(task)
        return task

    def get_task(self, task_id: str) -> PipelineTask:
        """Retrieve a task by ID."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)
        return self._tasks[task_id]

    def update_task(self, task_id: str, **kwargs: Any) -> PipelineTask:
        """Update task fields and persist."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)

        task = self._tasks[task_id]
        for key, value in kwargs.items():
            if hasattr(task, key):
                if key == "status" and isinstance(value, str) and not isinstance(value, TaskStatus):
                    value = TaskStatus(value)
                setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)
        self._persist(task)
        return task

    def list_tasks(
        self,
        pipeline: Optional[str] = None,
        status: Optional[str] = None,
        company_slug: Optional[str] = None,
        product_slug: Optional[str] = None,
    ) -> List[PipelineTask]:
        """List tasks with optional filters."""
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
        """Acquire a per-slug lock. Raises TaskConflictError if already locked."""
        if slug in self._slug_locks:
            existing_id = self._slug_locks[slug]
            if existing_id in self._tasks:
                existing = self._tasks[existing_id]
                if existing.status in (TaskStatus.RUNNING, TaskStatus.PENDING_APPROVAL):
                    raise TaskConflictError(
                        f"A pipeline is already running for company '{slug}' "
                        f"(task_id={existing_id})"
                    )
            # Lock is stale — remove it
            del self._slug_locks[slug]

    def release_slug_lock(self, slug: str) -> None:
        """Release a per-slug lock."""
        self._slug_locks.pop(slug, None)

    # ── Task Handle Tracking ──────────────────────────────────────────

    def register_task_handle(self, task_id: str, handle: asyncio.Task) -> None:
        """Register an asyncio.Task handle for cancellation support."""
        self._task_handles[task_id] = handle

    def cancel_task_handle(self, task_id: str) -> bool:
        """Cancel the asyncio.Task for a running pipeline. Returns True if cancelled."""
        handle = self._task_handles.pop(task_id, None)
        if handle and not handle.done():
            handle.cancel()
            return True
        return False

    def remove_task_handle(self, task_id: str) -> None:
        """Remove a task handle (called on task completion)."""
        self._task_handles.pop(task_id, None)

    # ── HITL Approval ─────────────────────────────────────────────────

    async def wait_for_approval(
        self, task_id: str, timeout: float = 86400
    ) -> Dict[str, Any]:
        """Block until an approval is submitted for this task.

        Uses asyncio.Queue instead of Event to prevent lost-wakeup:
        submit_approval can be called before or after wait_for_approval
        and the message will still be delivered.

        Args:
            task_id: The task to wait for.
            timeout: Max seconds to wait (default 24h). On timeout, returns
                     a reject decision so the pipeline doesn't hang forever.
        """
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
        """Submit an approval decision, unblocking wait_for_approval.

        If the queue doesn't exist yet (wait hasn't started), creates it
        and puts the data — the waiter will find it when it starts.
        Also records the decision in the task's approval_history for audit.

        Args:
            approval_data: If provided, the full stage-specific approval dict
                is placed on the queue (used by v1.3 content pipeline).
                If None, a generic ``{decision, revision_note}`` dict is queued
                (backward-compatible for research pipeline callers).
            expected_nonce: If provided, validates that the task's current
                ``approval_payload.checkpoint_nonce`` matches before queuing.
                Prevents TOCTOU races and replay attacks.  Callers that don't
                use nonces (research/content-v1.0) omit this parameter.

        Raises:
            TaskNotFoundError: If *task_id* is unknown.
            ApprovalWindowError: If nonce mismatches or queue is already full
                (duplicate submission).
        """
        from api.tasks.models import ApprovalRecord

        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)

        task = self._tasks[task_id]

        # Atomic nonce validation — prevents TOCTOU and replay.
        # Nonce check + queue put are in the same synchronous function
        # (no await between them), making them atomic in async Python.
        if expected_nonce is not None:
            current_nonce = (task.approval_payload or {}).get("checkpoint_nonce")
            if current_nonce != expected_nonce:
                raise ApprovalWindowError(
                    f"Stale or replayed approval: nonce mismatch "
                    f"(expected {expected_nonce}, current {current_nonce})"
                )

        # Record in approval history
        resolved_stage = (
            stage
            or (task.approval_payload or {}).get("stage")
            or task.current_step
            or "unknown"
        )
        if resolved_stage == "unknown":
            logger.warning(
                "Approval for task %s has no stage info — recording as 'unknown'",
                task_id,
            )
        record = ApprovalRecord(
            task_id=task_id,
            stage=resolved_stage,
            decision=decision,
            revision_note=revision_note,
        )
        task.approval_history.append(record)
        task.updated_at = datetime.now(timezone.utc)
        self._persist(task)

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

    # ── Persistence ───────────────────────────────────────────────────

    def _persist(self, task: PipelineTask) -> None:
        """Atomic JSON write: write to temp file, then os.replace()."""
        target = self._base_dir / f"{task.task_id}.json"
        data = task.model_dump(mode="json")
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._base_dir), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, str(target))
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _recover_from_disk(self) -> None:
        """Scan base_dir for task JSON files and reload into memory.

        Marks any tasks with status 'running' or 'pending_approval' as
        'failed_restart' (orphan recovery).
        """
        for json_file in self._base_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                task = PipelineTask(**data)
                if task.status in (TaskStatus.RUNNING, TaskStatus.PENDING_APPROVAL):
                    task.status = TaskStatus.FAILED_RESTART
                    task.updated_at = datetime.now(timezone.utc)
                    self._persist(task)
                    logger.info(
                        "Orphan recovery: task %s marked as failed_restart",
                        task.task_id,
                    )
                self._tasks[task.task_id] = task
            except Exception:
                logger.warning("Skipping corrupt task file: %s", json_file)
