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
        max_concurrent: int = 3,
    ) -> None:
        self._tasks: Dict[str, PipelineTask] = {}
        self._base_dir = base_dir
        self._event_bus = event_bus
        self._slug_locks: Dict[str, str] = {}  # slug -> task_id
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._approval_events: Dict[str, asyncio.Event] = {}
        self._approval_data: Dict[str, Dict[str, Any]] = {}
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._recover_from_disk()

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_task(self, pipeline: str, company_slug: str) -> PipelineTask:
        """Create a new task and acquire slug lock."""
        self.acquire_slug_lock(company_slug)

        task_id = str(uuid.uuid4())
        task = PipelineTask(
            task_id=task_id,
            pipeline=pipeline,
            company_slug=company_slug,
        )
        self._tasks[task_id] = task
        self._slug_locks[company_slug] = task_id
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
                setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)
        self._persist(task)
        return task

    def list_tasks(
        self,
        pipeline: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[PipelineTask]:
        """List tasks with optional filters."""
        tasks = list(self._tasks.values())
        if pipeline:
            tasks = [t for t in tasks if t.pipeline == pipeline]
        if status:
            tasks = [t for t in tasks if t.status.value == status]
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

    # ── HITL Approval ─────────────────────────────────────────────────

    async def wait_for_approval(self, task_id: str) -> Dict[str, Any]:
        """Block until an approval is submitted for this task."""
        event = asyncio.Event()
        self._approval_events[task_id] = event
        await event.wait()
        data = self._approval_data.pop(task_id, {"decision": "approve"})
        self._approval_events.pop(task_id, None)
        return data

    def submit_approval(
        self,
        task_id: str,
        decision: str,
        revision_note: Optional[str] = None,
    ) -> None:
        """Submit an approval decision, unblocking wait_for_approval."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)

        self._approval_data[task_id] = {
            "decision": decision,
            "revision_note": revision_note,
        }
        event = self._approval_events.get(task_id)
        if event:
            event.set()

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
