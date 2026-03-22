"""TaskStoreProtocol — interface for task persistence + coordination.

Both ``TaskStore`` (JSON-file-backed) and ``DbTaskStore`` (PostgreSQL)
implement this protocol.  Router/runner code programs to the protocol,
and the DI layer picks the implementation based on configuration.

Re-exports the exception types so consumers only import from here.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from api.tasks.models import PipelineTask
from api.tasks.store import ApprovalWindowError, TaskConflictError, TaskNotFoundError  # noqa: F401

__all__ = ["TaskStoreProtocol", "TaskNotFoundError", "TaskConflictError", "ApprovalWindowError"]


@runtime_checkable
class TaskStoreProtocol(Protocol):
    """Async-compatible task store interface."""

    @property
    def semaphore(self) -> asyncio.Semaphore: ...

    # ── CRUD ──────────────────────────────────────────────────────

    def create_task(
        self,
        pipeline: str,
        company_slug: str,
        product_slug: Optional[str] = None,
        allow_parallel: bool = False,
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
    ) -> None: ...
