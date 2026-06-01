"""TaskStoreProtocol — interface for task persistence + coordination.

``DbTaskStore`` (PostgreSQL) is the sole production implementation.
Router/runner code programs to the protocol, and the DI layer provides
the implementation. DATABASE_URL is required at startup.

Re-exports the exception types so consumers only import from here.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from api.tasks.models import PipelineTask
from api.tasks.exceptions import ApprovalDeliveryError, ApprovalWindowError, TaskConflictError, TaskNotFoundError  # noqa: F401

__all__ = ["TaskStoreProtocol", "TaskNotFoundError", "TaskConflictError", "ApprovalWindowError", "ApprovalDeliveryError"]


@runtime_checkable
class TaskStoreProtocol(Protocol):
    """Async-compatible task store interface."""

    @property
    def semaphore(self) -> asyncio.Semaphore: ...

    def pipeline_semaphore(
        self,
        task_id: str,
        *,
        pool: str = "default",
        company_slug: Optional[str] = None,
    ): ...  # Returns async context manager

    # ── CRUD ──────────────────────────────────────────────────────

    def create_task(
        self,
        pipeline: str,
        company_slug: str,
        product_slug: Optional[str] = None,
        allow_parallel: bool = False,
        workspace_id: Optional[str] = None,
    ) -> PipelineTask: ...

    def get_task(self, task_id: str) -> PipelineTask: ...

    def update_task(self, task_id: str, **kwargs: Any) -> PipelineTask: ...

    def list_tasks(
        self,
        pipeline: Optional[str] = None,
        status: Optional[str] = None,
        company_slug: Optional[str] = None,
        product_slug: Optional[str] = None,
    ) -> List[PipelineTask]: ...

    # ── Slug Locks ────────────────────────────────────────────────

    def acquire_slug_lock(self, slug: str, task_id: Optional[str] = None) -> None: ...

    def release_slug_lock(self, slug: str) -> None: ...

    # ── Task Handle Tracking ──────────────────────────────────────

    def register_task_handle(self, task_id: str, handle: asyncio.Task) -> None: ...

    def cancel_task_handle(self, task_id: str) -> bool: ...

    def remove_task_handle(self, task_id: str) -> None: ...

    # ── HITL Approval ─────────────────────────────────────────────

    async def wait_for_approval(
        self, task_id: str, timeout: float = 86400,
    ) -> Dict[str, Any]: ...

    def submit_approval(
        self,
        task_id: str,
        decision: str,
        revision_note: Optional[str] = None,
        stage: Optional[str] = None,
        approval_data: Optional[Dict[str, Any]] = None,
        expected_nonce: Optional[str] = None,
        delivery_mode: str = "queue",
    ) -> None: ...

    def validate_approval_submission(
        self,
        task_id: str,
        *,
        expected_nonce: Optional[str] = None,
    ) -> None: ...

    def record_approval_submission(
        self,
        task_id: str,
        *,
        decision: str,
        revision_note: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> None: ...

    # ── Durability (Session 3) ─────────────────────────────────────

    async def ensure_created(self, task_id: str) -> None:
        """Await DB persistence of a recently created task. No-op for non-DB stores."""
        ...

    async def flush_terminal(self, task_id: str) -> None:
        """Await DB persistence of terminal status update. No-op for non-DB stores."""
        ...

    async def drain_pending(self) -> None:
        """Await all pending DB writes. Called during graceful shutdown."""
        ...
